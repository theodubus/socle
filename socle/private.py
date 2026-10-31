"""La mémoire privée : des notes du projet qui ne doivent pas être
publiques, rangées sous `memory/private/` avec le même format que le reste.

Deux modes, au choix de l'humain dans la politique (`[private] mode`) :

- **compagnon** : la zone privée est le clone d'un dépôt privé, ignoré par
  le dépôt public ; un verrou commité (`.socle/private.lock`) dit à quel commit
  du dépôt privé correspond chaque commit public ;
- **chiffre** : les fichiers privés sont commités chiffrés dans le dépôt
  public, par un filtre git (git-crypt ou équivalent). Le moteur ne connaît
  pas l'outil : il vérifie que ce qui est commité n'est pas en clair, et que
  la mémoire est lisible là où on la lit.

Sans accès (nouveau clone, CI d'un fork, clé absente), la mémoire privée est
« indisponible » : les contrôles qui en dépendent le disent, ils ne passent
pas en silence.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from socle import config, memory as memoire, utils as outils
from socle.messages import trad
from socle.context import controle



def dossier(racine: Path, rev: str | None = None) -> str:
    """La zone privée du projet."""
    return config.FORMAT_ACTUEL.prive


def fichier_verrou(racine: Path, rev: str | None = None) -> str:
    return config.FORMAT_ACTUEL.prive_lock


def fichier_termes(racine: Path, rev: str | None = None) -> str:
    return config.FORMAT_ACTUEL.termes


MODES = ("compagnon", "chiffre")
# La liste des termes qui ne doivent jamais paraître en public :
# l'agent y ajoute librement, seul l'humain en retire.
ENTETE_TERMES = memoire.ENTETE_TERMES
# La relecture humaine avant publication : au choix de l'humain.
RELECTURES = ("aucune", "chaque-push", "lots")
# Les couches dont le contenu nouveau peut être privé par défaut ; le
# chantier actif, réécrit à la main, n'a pas d'entrée à placer.
COUCHES_PRIVABLES = ("canonique", "backlog", "decisions", "journal", "demandes")


def mode(projet: config.Projet) -> str | None:
    m = projet.pol("private", "mode")
    return str(m) if m else None


est_prive = memoire.est_prive
lisible = memoire.lisible


def depot_compagnon(racine: Path) -> Path | None:
    p = racine / dossier(racine)
    return p if (p / ".git").exists() else None


def commit_compagnon(racine: Path) -> str | None:
    p = depot_compagnon(racine)
    if p is None or not outils.a_des_commits(p):
        return None
    return outils.git(p, "rev-parse", "HEAD").strip()


def compagnon_modifie(racine: Path) -> list[str]:
    p = depot_compagnon(racine)
    if p is None:
        return []
    return [l[3:] for l in outils.git(p, "status", "--porcelain", check=False).splitlines() if l.strip()]


def lire_verrou(racine: Path, rev: str | None = None) -> str | None:
    import tomllib

    texte = outils.lire_a(racine, rev, fichier_verrou(racine, rev))
    if not texte:
        return None
    try:
        return str(tomllib.loads(texte).get("commit", "")) or None
    except tomllib.TOMLDecodeError:
        return None


def ecrire_verrou(racine: Path, sha: str):
    (racine / fichier_verrou(racine)).write_text(
        trad("# Le commit du dépôt privé qui correspond à ce commit public (mode compagnon).\n"
             "# Écrit par `socle private lock`, jamais à la main.\n") +
        f'commit = "{sha}"\n', encoding="utf-8")


def recuperer(projet: config.Projet) -> int:
    """En CI : cloner le dépôt privé au commit du verrou, avec la clé de
    déploiement que donnent les secrets `SOCLE_PRIVE_DEPOT` et
    `SOCLE_PRIVE_CLE`. Sans eux (pull request d'un fork), la mémoire privée
    reste indisponible, et les contrôles le disent. Le journal de la CI est
    public : ni l'adresse ni la sortie de git n'y sont écrites."""
    import os
    import subprocess
    import tempfile

    racine = projet.racine
    depot, cle = os.environ.get("SOCLE_PRIVE_DEPOT", ""), os.environ.get("SOCLE_PRIVE_CLE", "")
    verrou = lire_verrou(racine)
    if not depot or not cle:
        print(trad("mémoire privée : indisponible ici, sans clé de déploiement (pull request d'un fork ?)"))
        return 0
    if verrou is None:
        print(trad("mémoire privée : pas de verrou ({verrou})", verrou=fichier_verrou(racine)))
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        fichier = Path(tmp) / "cle"
        fichier.write_text(cle.strip() + "\n", encoding="utf-8")
        fichier.chmod(0o600)
        env = {**os.environ, "GIT_SSH_COMMAND": f"ssh -i {fichier} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"}
        cible = racine / dossier(racine)
        for args in (["clone", "-q", "--no-checkout", depot, str(cible)], ["-C", str(cible), "checkout", "-q", verrou]):
            if subprocess.run(["git", *args], cwd=racine, env=env, capture_output=True).returncode != 0:
                print(trad("mémoire privée : récupération impossible (étape `git {etape}`)",
                           etape=args[0] if args[0] != "-C" else "checkout"))
                return 1
    print(trad("mémoire privée : récupérée au verrou {verrou}", verrou=verrou[:10]))
    return 0


def lire_prive(projet: config.Projet, rev: str | None, chemin: str) -> str | None:
    """Le texte en clair d'un fichier privé, tel qu'il était à une révision du
    dépôt public (`None` : l'arbre de travail). En mode compagnon, la
    révision publique désigne, par son verrou, un commit du dépôt privé ; en
    mode chiffré, git applique le filtre de déchiffrement s'il le peut."""
    import subprocess

    racine = projet.racine
    m = mode(projet)
    if rev is None or m not in MODES:
        return outils.lire_a(racine, None, chemin) if m in MODES else None
    if m == "compagnon":
        depot, verrou = depot_compagnon(racine), lire_verrou(racine, rev)
        if depot is None or not verrou:
            return None
        r = subprocess.run(["git", "show", f"{verrou}:{memoire.hors_zone_privee(chemin)}"], cwd=depot, capture_output=True)
    else:
        r = subprocess.run(["git", "cat-file", "--filters", f"{rev}:{chemin}"], cwd=racine, capture_output=True)
    return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None


@dataclass
class Termes:
    liste: list[str]
    disponible: bool
    texte: str = ""


def termes(projet: config.Projet, rev: str | None = None) -> Termes:
    """La liste des termes privés : un par ligne, `#` pour un commentaire,
    `re:` devant une expression régulière. Illisible ici (chiffrée, ou le
    dépôt privé absent), elle est indisponible, jamais vide en silence."""
    m = mode(projet)
    if m is None:
        return Termes([], True)
    texte = lire_prive(projet, rev, fichier_termes(projet.racine, rev))
    if texte is None:
        dispo = (depot_compagnon(projet.racine) is not None) if m == "compagnon" else (
            rev is not None or not (projet.racine / fichier_termes(projet.racine)).is_file())
        return Termes([], dispo)
    if not texte.lstrip().startswith(ENTETE_TERMES):
        return Termes([], False)
    liste = [l.strip() for l in texte.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return Termes(liste, True, texte)


def ajouter_terme(projet: config.Projet, terme: str) -> bool:
    """Ajoute un terme à la liste (libre : cela durcit le contrôle). Faux
    s'il y était déjà. Une liste illisible ici (chiffrée sans la clé, dépôt
    privé absent) n'est pas réécrite : elle serait écrasée."""
    p = projet.racine / fichier_termes(projet.racine)
    actuels, ouverte = termes(projet), acces(projet)
    if not ouverte.disponible or not actuels.disponible or (p.is_file() and not actuels.texte):
        raise RuntimeError(trad("liste des termes privés illisible ici (`{fichier_termes}`) : le terme n'est "
                                "pas ajouté à l'aveugle, la liste serait écrasée ({raison})",
                                fichier_termes=fichier_termes(projet.racine), raison=ouverte.raison))
    if terme.strip() in actuels.liste:
        return False
    texte = actuels.texte or f"{ENTETE_TERMES} — un par ligne, `re:` pour une expression régulière.\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texte.rstrip("\n") + "\n" + terme.strip() + "\n", encoding="utf-8")
    return True


def fuites(texte: str, liste: list[str], identifiants: bool = True) -> list[str]:
    """Ce qu'un texte public laisse fuir du privé. Le terme trouvé n'est
    jamais réécrit : la réponse ne donne que son rang dans la liste."""
    res = []
    if identifiants:
        vus = []
        for m in memoire.ID_RE.finditer(texte):
            if m["prive"] and memoire.id_valide(m["type"], m["num"]) and m.group(0) not in vus:
                vus.append(m.group(0))
        res += [trad("identifiant privé `{i}`", i=i) for i in vus]
    norme = outils.sans_accents(texte)
    for i, terme in enumerate(liste, 1):
        if terme.startswith("re:"):
            try:
                trouve = re.search(terme[3:], texte, re.I)
            except re.error:
                res.append(trad("terme privé n°{i} : expression régulière invalide", i=i))
                continue
        else:
            trouve = _terme_present(terme, norme)
        if trouve:
            res.append(trad("terme privé n°{i} de la liste", i=i))
    return res


def _terme_present(terme: str, texte: str) -> bool:
    """Le terme, sous ses variantes d'écriture : casse et
    accents ignorés, ses mots séparés par n'importe quels séparateurs ou par
    rien (`acme corp`, `acme_corp`, `AcmeCorp`, coupé en fin de ligne d'un
    commentaire). Il commence et finit sur une frontière de mot : un
    séparateur, un passage minuscule-majuscule, ou lettre-chiffre."""
    mots = re.findall(r"[^\W_]+", outils.sans_accents(terme))
    if not mots:
        return False
    for m in re.finditer(r"[\W_]*".join(re.escape(x) for x in mots), texte, re.I):
        if _frontiere(texte, m.start() - 1, m.start()) and _frontiere(texte, m.end() - 1, m.end()):
            return True
    return False


def _frontiere(texte: str, i: int, j: int) -> bool:
    """Une frontière de mot entre les caractères `i` et `j` du texte."""
    if i < 0 or j >= len(texte) or not texte[i].isalnum() or not texte[j].isalnum():
        return True
    a, b = texte[i], texte[j]
    return a.isdigit() != b.isdigit() or (a.islower() and b.isupper())


def relecture(projet: config.Projet) -> str | None:
    """Le mode de relecture avant publication choisi par l'humain, ou `None`
    s'il n'en a pas choisi."""
    r = projet.pol("private", "review")
    return str(r) if r else None


def fichier_relectures(racine: Path) -> Path:
    """Les publications relues, dans le répertoire git commun : un état
    local, comme la trace des hooks."""
    return config.chemin_trace(racine).parent / "relectures.log"


def relue(racine: Path, sha: str) -> bool:
    p = fichier_relectures(racine)
    if not p.is_file():
        return False
    return any(l.split("\t", 1)[0] == sha for l in p.read_text(encoding="utf-8").splitlines())


def noter_relecture(racine: Path, sha: str, par: str, canal: str, citation: str):
    import json
    from datetime import datetime

    p = fichier_relectures(racine)
    p.parent.mkdir(parents=True, exist_ok=True)
    quand = datetime.now().astimezone().isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"{sha}\t{quand}\t{par}\t{canal}\t{json.dumps(citation, ensure_ascii=False)}\n")


def publication_refusee(projet: config.Projet, shas: list[str]) -> str | None:
    """Pourquoi pousser ces commits vers le dépôt public attend une
    relecture humaine, ou `None`."""
    r = relecture(projet)
    if mode(projet) is None or r in (None, "aucune"):
        return None
    manquants = [s for s in shas if s and not set(s) <= {"0"} and not relue(projet.racine, s)]
    if not manquants:
        return None
    return (trad("relecture avant publication (politique : {relecture}) : {sha} n'a pas été relu. Montrer à "
                 "l'humain ce qui part (diff, messages de commit), puis consigner son accord avec son texte exact : "
                 "`socle reviewed --relayed --by <nom> --quote-file <fichier>`. ", relecture=r, sha=manquants[0][:10])
            + (trad("Une relecture à chaque push.") if r == "chaque-push" else trad("Une relecture par lot de commits.")))


@dataclass
class Acces:
    disponible: bool
    raison: str


def acces(projet: config.Projet, illisibles: list[str] | None = None) -> Acces:
    """La mémoire privée est-elle là, et lisible ?"""
    m = mode(projet)
    racine = projet.racine
    if m == "compagnon":
        sha = commit_compagnon(racine)
        if sha is None:
            return Acces(False, trad("le dépôt privé n'est pas cloné dans `{dossier}/`", dossier=dossier(racine)))
        verrou = lire_verrou(racine)
        if verrou and verrou != sha:
            return Acces(True, trad("disponible, mais au commit {sha} et non au verrou {verrou} (`socle "
                                    "private extract` pour revenir au verrou, `socle private lock` pour "
                                    "l'avancer)", sha=sha[:10], verrou=verrou[:10]))
        return Acces(True, trad("disponible, au commit {sha}", sha=sha[:10]))
    if m == "chiffre":
        if illisibles is None:
            illisibles = [c for c in outils.fichiers_courants(racine)
                          if est_prive(c) and not lisible(outils.lire_a(racine, None, c))]
        if illisibles:
            return Acces(False, trad("{n} fichier(s) privé(s) illisible(s) : chiffrés, la clé manque ici",
                                     n=len(illisibles)))
        return Acces(True, trad("disponible, déchiffrée"))
    return Acces(False, trad("aucun mode de mémoire privée dans la politique"))


def ligne_etat(projet: config.Projet) -> str:
    m = mode(projet)
    if m is None:
        return trad("mémoire privée : non configurée (mode public seul)")
    if m not in MODES:
        return trad("mémoire privée : mode « {m} » inconnu (attendu : {liste})", m=m, liste=', '.join(MODES))
    a = acces(projet)
    if a.disponible:
        return trad("mémoire privée : {raison} (mode {m})", raison=a.raison, m=m)
    return (trad("mémoire privée : INDISPONIBLE (mode {m}) — {raison} ; les contrôles qui l'exigent le "
                 "signalent ; ne pas conclure sur ce qui en dépend", m=m, raison=a.raison))


def memoire_privee(ctx) -> memoire.Memoire | None:
    """La mémoire privée telle qu'elle est à la tête jugée : l'arbre de
    travail, ou, à une révision, le dépôt privé au commit du verrou (mode
    compagnon) et les fichiers déchiffrés par le filtre (mode chiffré).
    `None` : elle ne se lit pas ici."""
    projet, racine = ctx.projet, ctx.racine
    if ctx.tete is None:
        return ctx.memoire if acces(projet, ctx.memoire.illisibles).disponible else None
    m = mode(projet)
    if m == "compagnon":
        depot, verrou = depot_compagnon(racine), lire_verrou(racine, ctx.tete)
        if depot is None or not verrou:
            return None
        noms = outils.git(depot, "ls-tree", "-r", "--name-only", verrou, check=False).splitlines()
        chemins = [f"{dossier(racine, ctx.tete)}/{n}" for n in noms]
    elif m == "chiffre":
        chemins = [c for c in ctx.fichiers if est_prive(c)]
    else:
        return None
    return _lire_zone(projet, ctx.tete, chemins)


def memoire_privee_a(projet: config.Projet, rev: str) -> memoire.Memoire | None:
    """La mémoire privée à une révision du dépôt public, la base d'une plage :
    vide quand elle n'existait pas encore, `None` quand elle existait mais ne
    se lit pas ici. Sans elle, « ajout seul » ne la protégerait pas."""
    racine = projet.racine
    m = mode(projet)
    if m == "compagnon":
        verrou = lire_verrou(racine, rev)
        if not verrou:
            return memoire.Memoire(racine=racine, rev=rev)
        depot = depot_compagnon(racine)
        if depot is None or not outils.git_reussit(depot, "cat-file", "-e", f"{verrou}^{{commit}}"):
            return None
        noms = outils.git(depot, "ls-tree", "-r", "--name-only", verrou, check=False).splitlines()
        chemins = [f"{dossier(racine, rev)}/{n}" for n in noms]
    elif m == "chiffre":
        chemins = [c for c in outils.fichiers_a(racine, rev) if est_prive(c)]
    else:
        return None
    return _lire_zone(projet, rev, chemins)


def _lire_zone(projet: config.Projet, rev: str, chemins: list[str]) -> memoire.Memoire | None:
    res = memoire.Memoire(racine=projet.racine, rev=rev)
    for c in chemins:
        if memoire.couche_attendue(c) is None:
            continue
        texte = lire_prive(projet, rev, c)
        if texte is None or not lisible(texte):
            return None
        res.fichiers[c] = memoire.analyser(c, texte)
    return res


def arbre_commite(ctx) -> str | None:
    """Ce qui est, ou sera, commité : la tête jugée, ou l'index."""
    if ctx.tete:
        return ctx.tete
    if not outils.est_depot(ctx.racine):
        return None
    return outils.arbre_de_l_index(ctx.racine)


# --------------------------------------------------------------------------
# Contrôles
# --------------------------------------------------------------------------


@controle("prive.acces")
def controle_acces(ctx, r):
    """La mémoire privée configurée est accessible, sinon c'est dit ; des
    fichiers privés sans mode configuré sont publics, donc refusés."""
    m = mode(ctx.projet)
    if m is None:
        commites = [c for c in outils.fichiers_a(ctx.racine, arbre_commite(ctx)) if est_prive(c)]
        if commites:
            r.erreur("prive.acces", trad("{n} fichier(s) sous `{dossier}/` commité(s) sans mode de mémoire "
                                         "privée : ils sont publics. Choisir un mode (`[private] mode` de la "
                                         "politique) ou les déplacer",
                                         n=len(commites), dossier=dossier(ctx.racine)),
                     commites[0])
        return
    if m not in MODES:
        r.erreur("prive.acces", trad("mode de mémoire privée « {m} » inconnu (attendu : {liste})",
                                     m=m, liste=', '.join(MODES)), ctx.projet.chemins.politique)
        return
    a = acces(ctx.projet, ctx.memoire.illisibles if ctx.tete is None else None)
    if not a.disponible:
        r.indisponible("prive.acces", trad("mémoire privée indisponible : {raison}", raison=a.raison))
    rel = relecture(ctx.projet)
    if rel is None:
        r.avertir("prive.acces", trad("relecture avant publication non choisie (`[private] review` : {liste}) "
                                      ": aucune n'est exigée", liste=', '.join(RELECTURES)), ctx.projet.chemins.politique)
    elif rel not in RELECTURES:
        r.erreur("prive.acces", trad("relecture « {rel} » inconnue (attendu : {liste})",
                                     rel=rel, liste=', '.join(RELECTURES)), ctx.projet.chemins.politique)


@controle("prive.verrou")
def controle_verrou(ctx, r):
    """Mode compagnon : rien de privé n'est commité dans le dépôt public, et
    le verrou désigne le commit du dépôt privé qui va avec ce commit."""
    if mode(ctx.projet) != "compagnon":
        return
    arbre = arbre_commite(ctx)
    for c in outils.fichiers_a(ctx.racine, arbre):
        if est_prive(c):
            r.erreur("prive.verrou", trad("fichier privé commité dans le dépôt public : il appartient au dépôt "
                                          "privé, que `{dossier}/` clone (le retirer de l'index)",
                                          dossier=dossier(ctx.racine)), c)
    # Le verrou de la tête jugée ; en fin de tour, celui de l'arbre de
    # travail, qui sera commité.
    verrou = lire_verrou(ctx.racine, ctx.tete)
    if verrou is None:
        if commit_compagnon(ctx.racine) is None:
            # Rien n'est encore en place : c'est à l'humain.
            r.erreur("prive.verrou", trad("mode compagnon sans dépôt privé ni verrou : sa mise en place "
                                          "revient à l'humain, `private install --repo <adresse du dépôt "
                                          "privé>`"), fichier_verrou(ctx.racine))
        else:
            r.erreur("prive.verrou", trad("mode compagnon sans verrou : `socle private lock`"),
                     fichier_verrou(ctx.racine))
        return
    sha = commit_compagnon(ctx.racine)
    if sha is None:
        r.indisponible("prive.verrou", trad("dépôt privé non cloné : verrou non vérifiable"))
        return
    modifies = compagnon_modifie(ctx.racine)
    if modifies and ctx.etage != "ci":
        r.erreur("prive.verrou", trad("{n} changement(s) de la mémoire privée hors de tout commit du dépôt "
                                      "privé : les y commiter, puis `socle private lock`", n=len(modifies)), dossier(ctx.racine))
    if sha != verrou:
        r.erreur("prive.verrou", trad("le verrou désigne {verrou}, le dépôt privé est à {sha} : `socle private "
                                      "lock` pour l'avancer, ou `socle private extract` pour y revenir",
                                      verrou=verrou[:10], sha=sha[:10]), fichier_verrou(ctx.racine))


@controle("prive.chiffre")
def controle_chiffre(ctx, r):
    """Mode chiffré : aucun fichier privé n'est commité en clair, et un
    filtre de chiffrement couvre la zone privée."""
    if mode(ctx.projet) != "chiffre":
        return
    arbre = arbre_commite(ctx)
    for c in outils.fichiers_a(ctx.racine, arbre):
        if est_prive(c) and lisible(outils.lire_a(ctx.racine, arbre, c)):
            r.erreur("prive.chiffre", trad("fichier privé commité EN CLAIR : le filtre de chiffrement n'a pas "
                                           "tourné. Retirer le commit avant tout push ; si c'est poussé, "
                                           "l'historique public l'a gardé"), c)
    if outils.est_depot(ctx.racine):
        attribut = outils.git(ctx.racine, "check-attr", "filter", "--", ctx.projet.chemins.dans_prive(ctx.projet.chemins.canonique), check=False)
        if attribut.strip().endswith(": unspecified") or not attribut.strip():
            zone = dossier(ctx.racine)
            r.erreur("prive.chiffre", trad("aucun filtre de chiffrement ne couvre `{zone}/` (`.gitattributes` "
                                           ": `{zone}/** filter=…`)", zone=zone), ".gitattributes")


@controle("prive.fuites")
def controle_fuites(ctx, r):
    """Aucun terme de la liste privée dans un fichier public modifié, et ni
    terme ni identifiant privé dans un message de commit. Le terme trouvé
    n'est jamais écrit : le journal de la CI est public."""
    if mode(ctx.projet) is None:
        return
    lt = termes(ctx.projet, ctx.tete)
    if not lt.disponible:
        r.indisponible("prive.fuites", trad("liste des termes privés illisible ici : seuls les identifiants "
                                            "privés sont cherchés"))
    moteur = ctx.projet.dossier_moteur.rstrip("/") + "/"
    presents, anciens = set(ctx.fichiers), set(ctx.fichiers_base)
    for c in ctx.changes:
        if c not in presents or est_prive(c) or c.startswith(moteur):
            continue
        if c not in anciens:
            # Le nom d'un fichier nouveau est publié comme son contenu.
            for f in fuites(c, lt.liste):
                r.erreur("prive.fuites", trad("fuite de la mémoire privée dans le nom du fichier : {fuite}", fuite=f), c)
        texte = ctx.lire(c)
        if texte is None or "\0" in texte[:4096]:
            continue
        for f in fuites(texte, lt.liste, identifiants=False):
            r.erreur("prive.fuites", trad("fuite de la mémoire privée : {fuite}", fuite=f), c)
    for commit in ctx.commits:
        for f in fuites(commit["message"], lt.liste):
            r.erreur("prive.fuites", trad("fuite de la mémoire privée dans le message du commit {sha} : {fuite}",
                                          sha=commit['sha'][:10], fuite=f))
    branche = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") if ctx.etage == "ci" else None
    for f in fuites(branche or "", lt.liste):
        r.erreur("prive.fuites", trad("fuite de la mémoire privée dans le nom de la branche : {fuite}", fuite=f))


@controle("prive.termes", base=True)
def controle_termes(ctx, r):
    """Ajouter un terme à la liste privée est libre ; en retirer un exige une
    demande validée qui cite la liste et son empreinte nouvelle."""
    if mode(ctx.projet) is None:
        return
    avant, apres = termes(ctx.projet, ctx.base), termes(ctx.projet, ctx.tete)
    if not (avant.disponible and apres.disponible):
        r.indisponible("prive.termes", trad("liste des termes privés illisible ici : retraits non vérifiables"))
        return
    retires = [x for x in avant.liste if x not in apres.liste]
    if not retires:
        return
    from socle.checks_ratchet import _valide_par

    cite = "sha256:" + outils.sha256(apres.texte)[:16]
    termes_ici = fichier_termes(ctx.racine)
    d = _valide_par(ctx, termes_ici, cite)
    if d:
        r.avertir("prive.termes", trad("{n} terme(s) retiré(s), validé par {id}", n=len(retires), id=d.id), termes_ici)
    else:
        r.erreur("prive.termes", trad("{n} terme(s) retiré(s) de la liste privée sans validation humaine : une "
                                      "demande validée doit citer `{termes_ici}` et `{cite}`",
                                      n=len(retires), termes_ici=termes_ici, cite=cite), termes_ici)



# --------------------------------------------------------------------------
# Couche par couche, entrée par entrée
# --------------------------------------------------------------------------


def couches_privees(projet: config.Projet) -> set[str]:
    """Les couches dont le contenu nouveau est privé par défaut : celles que
    la politique nomme (`[private] layers`) ; à défaut, toutes sauf les
    demandes, que `[private] requests` rend privées. Aucune sans mémoire
    privée."""
    if mode(projet) is None:
        return set()
    choix = projet.pol("private", "layers")
    if choix is None:
        return set(COUCHES_PRIVABLES[:-1]) | ({"demandes"} if projet.pol("private", "requests", defaut=False) else set())
    return {outils.cle(c) for c in choix} & set(COUCHES_PRIVABLES)


def couches_inconnues(projet: config.Projet) -> list[str]:
    """Les noms de `[private] layers` qui ne désignent aucune couche."""
    return [c for c in projet.pol("private", "layers", defaut=[]) or [] if outils.cle(c) not in COUCHES_PRIVABLES]


def adresse_ssh(adresse: str) -> str:
    """L'adresse SSH d'un dépôt, que la CI clone avec la clé de déploiement :
    `https://hote/o/r` devient `git@hote:o/r.git` ; une autre forme reste."""
    m = re.match(r"^https?://(?P<hote>[\w.-]+)/(?P<o>[\w.-]+)/(?P<r>[\w.-]+?)(?:\.git)?/?$", adresse)
    return f"git@{m['hote']}:{m['o']}/{m['r']}.git" if m else adresse
