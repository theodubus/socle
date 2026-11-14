"""Contrôles de la mémoire et des demandes humaines.

Chaque fonction est un contrôle déterministe : elle ajoute des constats au
rapport, et un constat de gravité « erreur » fait échouer le passage.
"""

from __future__ import annotations

import re
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from socle import config, requests as demandes, language as langue, links as liens, memory as memoire, utils as outils
from socle.messages import trad
from socle.context import controle

TYPE_DE_COUCHE = {v: k for k, v in memoire.TYPES.items()}
TRANSITIONS_ADR = {
    ("proposee", "acceptee"), ("proposee", "rejetee"), ("proposee", "abandonnee"),
    ("acceptee", "remplacee"), ("acceptee", "abandonnee"),
}


est_prive = memoire.est_prive


# --------------------------------------------------------------------------
# Format
# --------------------------------------------------------------------------


@controle("memoire.format")
def format_memoire(ctx, r):
    """En-têtes, couches, identifiants, statuts : la mémoire se lit par script."""
    ch = ctx.projet.chemins
    # Le backlog est un dossier, qu'aucun sujet ne rend requis.
    for requis in (ch.canonique, ch.actif):
        if requis not in ctx.fichiers:
            r.erreur("memoire.format", trad("fichier de mémoire requis absent"), requis)
    for chemin, f in sorted(ctx.memoire.fichiers.items()):
        attendue = memoire.couche_attendue(chemin)
        if attendue == "inconnue":
            r.erreur("memoire.format", trad("fichier hors des couches connues de la mémoire"), chemin)
            continue
        if f.couche is None:
            r.erreur("memoire.format", trad("en-tête `<!-- socle: couche=… zone=… -->` absent"), chemin, 1)
            continue
        if f.couche != attendue:
            r.erreur("memoire.format", trad("couche déclarée « {couche} », l'emplacement impose « {attendue} »",
                                            couche=f.couche, attendue=attendue), chemin, 1)
        zone_lieu = "privee" if est_prive(chemin) else "publique"
        if f.zone not in memoire.ZONES:
            r.erreur("memoire.format", trad("zone non déclarée (`zone=publique` ou `zone=privee`)"), chemin, 1)
        elif f.zone != zone_lieu:
            r.erreur("memoire.format", trad("zone déclarée « {zone} » dans un emplacement « {zone_lieu} »",
                                            zone=f.zone, zone_lieu=zone_lieu), chemin, 1)
        _format_entrees(r, chemin, f, attendue, zone_lieu == "privee")
        # Un titre mal formé fait disparaître l'entrée de toute lecture
        #.
        for ligne, titre in f.illisibles:
            r.erreur("memoire.format", trad("titre d'entrée illisible : « {titre} » — l'entrée n'est pas lue ; "
                                            "forme attendue : `## J-AAAA-MM-JJ-X — titre`", titre=titre[:60]), chemin, ligne)

    for ident, defs in ctx.memoire.definitions().items():
        if len(defs) > 1:
            lieux = ", ".join(f"{d.fichier}:{d.ligne}" for d in defs)
            r.erreur("memoire.format", trad("`{ident}` est défini {n} fois ({lieux})",
                                            ident=ident, n=len(defs), lieux=lieux), defs[0].fichier, defs[0].ligne)


def _format_entrees(r, chemin, f, couche, prive):
    nom = chemin.rsplit("/", 1)[-1]
    if couche == "actif":
        for e in f.entrees:
            r.erreur("memoire.format", trad("`{id}` défini dans le chantier actif, qui est réécrit : un "
                                            "identifiant stable vit dans une couche durable", id=e.id), chemin, e.ligne)
        return
    attendu = TYPE_DE_COUCHE[couche]
    # `AAAA-MM.md`, puis `AAAA-MM-2.md`… quand le mois dépasse son budget.
    if couche == "journal" and not re.match(r"^\d{4}-\d{2}(?:-[2-9]|-[1-9]\d+)?\.md$", nom):
        r.erreur("memoire.format", trad("un fichier de journal se nomme `AAAA-MM.md`, ou `AAAA-MM-N.md` quand "
                                        "le mois continue (N à partir de 2)"), chemin)
    premiers = [e for e in f.entrees if e.parent is None]
    if couche in ("decisions", "demandes"):
        if len(premiers) != 1:
            r.erreur("memoire.format", trad("un fichier de {couche} porte exactement une entrée ({n} "
                                            "trouvée(s))", couche=couche, n=len(premiers)), chemin)
        elif not nom.startswith(premiers[0].id):
            r.erreur("memoire.format", trad("le nom du fichier doit commencer par {id}", id=premiers[0].id), chemin)
    for e in f.entrees:
        if e.prive != prive:
            r.erreur("memoire.format", trad("`{id}` : un identifiant privé commence par P", id=e.id) if prive
                     else trad("`{id}` : un identifiant public ne commence pas par P", id=e.id), chemin, e.ligne)
        if e.parent is not None:
            if couche != "journal" or e.type not in ("F", "B"):
                r.erreur("memoire.format", trad("`{id}` imbriqué hors d'une archive de journal", id=e.id), chemin, e.ligne)
            continue
        if e.type != attendu:
            r.erreur("memoire.format", trad("`{id}` n'a pas sa place dans la couche « {couche} »",
                                            id=e.id, couche=couche), chemin, e.ligne)
            continue
        if couche == "journal":
            date = e.id.lstrip("P")[2:12]
            if not nom.startswith(date[:7]):
                r.erreur("memoire.format", trad("`{id}` est daté hors du mois de son fichier", id=e.id), chemin, e.ligne)
        if e.basculee:
            # Ni titre ni texte propres : ce sont eux qui sont privés.
            if prive:
                r.erreur("memoire.format", trad("`{id}` : seule une entrée publique se bascule", id=e.id), chemin, e.ligne)
            if e.titre not in langue.textes("titre-basculee") or \
                    _norm(e.corps) not in {"", *(_norm(x) for x in langue.textes("texte-basculee"))}:
                r.erreur("memoire.format", trad("`{id}` basculée garde un titre ou un texte : seuls « "
                                                "{titre} » et « {texte} » restent en public",
                                                id=e.id, titre=memoire.TITRE_BASCULEE, texte=memoire.TEXTE_BASCULEE), chemin, e.ligne)
            continue
        statuts = memoire.STATUTS.get(e.type)
        if statuts is not None:
            if not e.statut:
                r.erreur("memoire.format", trad("`{id}` sans `statut` (attendu : {liste})",
                                                id=e.id, liste=', '.join(sorted(statuts))), chemin, e.ligne)
            elif e.statut not in statuts:
                r.erreur("memoire.format", trad("`{id}` : statut « {statut} » inconnu (attendu : {liste})",
                                                id=e.id, statut=e.statut, liste=', '.join(sorted(statuts))), chemin, e.ligne)
        if e.barre and e.type == "F" and e.statut != "refute":
            r.erreur("memoire.format", trad("`{id}` est barré sans être « réfuté »", id=e.id), chemin, e.ligne)


# --------------------------------------------------------------------------
# Références
# --------------------------------------------------------------------------

LIEN_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
CODE_EN_LIGNE = re.compile(r"`([^`\n]+)`")
INTERDITS_CHEMIN = set("*?[]{}<>$|~\"' =,;()")


def ancres(texte: str) -> set[str]:
    res, vus = set(), {}
    for _, ligne, code in memoire.lignes_hors_code(texte):
        if code:
            continue
        m = memoire.TITRE_RE.match(ligne)
        if m:
            s = liens.ancre(m["reste"])
            n = vus.get(s, 0)
            res.add(s if n == 0 else f"{s}-{n}")
            vus[s] = n + 1
    return res


def _existe(ctx, chemin: str, historique: bool = False) -> bool:
    """Le chemin existe. Avec `historique` (une couche qui ne se réécrit
    pas), un chemin qui a existé dans l'historique du dépôt vaut aussi : la
    mémoire ne suit pas un renommage."""
    chemin = chemin.strip("/")
    if _existe_tel_quel(ctx, chemin) or historique and _a_existe(ctx, chemin):
        return True
    return _basculee(ctx, chemin) is not None or _dans_une_rustine(ctx, chemin)


RUSTINE = re.compile(r"^\+\+\+ b/(\S+)", re.M)


def _dans_une_rustine(ctx, chemin: str) -> bool:
    """Le chemin est un fichier qu'une rustine suivie du dépôt (`*.patch`,
    `*.diff`) écrit, ou l'un de ses dossiers : il existe une fois la rustine
    appliquée."""
    ecrits = ctx._cache.get("rustines")
    if ecrits is None:
        ecrits = set()
        for f in outils.filtrer(ctx.fichiers, ["**/*.patch", "**/*.diff"]):
            for m in RUSTINE.finditer(ctx.lire(f) or ""):
                parts = m.group(1).split("/")
                ecrits |= {"/".join(parts[:i]) for i in range(1, len(parts) + 1)}
        ctx._cache["rustines"] = ecrits
    return chemin in ecrits


# Les couches qui ne se réécrivent pas : ce qu'elles citent a existé quand
# elles l'ont écrit.
COUCHES_GELEES = ("journal", "decisions", "demandes", "canonique")


def _a_existe(ctx, chemin: str) -> bool:
    """Le chemin, ou un dossier, a existé dans l'historique du dépôt, toutes
    branches comprises. Un seul `git log` par contexte, au premier besoin."""
    connus = ctx._cache.get("historique")
    if connus is None:
        sortie = outils.git(ctx.racine, "log", "--all", "--no-renames", "--format=", "--name-only", check=False)
        connus = set()
        for f in sortie.splitlines():
            if f:
                parts = f.split("/")
                connus.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
        ctx._cache["historique"] = connus
    return chemin in connus


def _basculee(ctx, chemin: str) -> str | None:
    """Le fichier qui remplace celui d'une décision basculée dans la mémoire
    privée (`ADR-0003-basculee.md` pour `ADR-0003-un-titre.md`), ou
    d'un sujet du backlog."""
    remplacant = _nom_basculee(chemin)
    return remplacant if remplacant and _existe_tel_quel(ctx, remplacant) else None


def _nom_basculee(chemin: str) -> str | None:
    dossier, _, nom = chemin.rpartition("/")
    m = re.match(r"^((?:ADR|B)-\d{4})-.+\.md$", nom)
    if not m or not memoire.est_memoire(chemin):
        return None
    remplacant = f"{dossier}/{m[1]}-{BASCULEE}.md"
    return remplacant if remplacant != chemin else None


BASCULEE = "basculee"


def _alias(ctx, chemin: str) -> str:
    """Le chemin tel qu'il existe : le sien, ou celui du fichier qui remplace
    une décision basculée."""
    if _existe_tel_quel(ctx, chemin.strip("/")):
        return chemin
    return _basculee(ctx, chemin) or chemin


def _lien_d_un_ancien_nom(ctx, chemin_doc: str, lien: str) -> bool:
    """Un lien relatif d'une couche gelée, écrit quand son fichier avait un
    autre nom : lu depuis l'un de ses anciens emplacements, il mène à un
    chemin qui a existé."""
    anciens = ctx._cache.setdefault("anciens-noms", {})
    if chemin_doc not in anciens:
        sortie = outils.git(ctx.racine, "log", "--follow", "--name-only", "--format=", "--", chemin_doc, check=False)
        anciens[chemin_doc] = {c for c in sortie.splitlines() if c and c != chemin_doc}
    return any(_a_existe(ctx, _normaliser_chemin(c.rpartition("/")[0], lien)) for c in anciens[chemin_doc])


def _citables(ctx) -> set[str]:
    """Les fichiers qu'une référence peut désigner : ceux de l'arbre jugé
    (un commit, l'index au commit) ; sur l'arbre de travail, ceux que git
    suit, l'index compris, et le clone du dépôt privé. Un fichier présent sur
    le disque seulement manque à un clone neuf : la CI le dirait absent
    (B-0166). Hors d'un dépôt, ceux du disque."""
    ens = ctx._cache.get("ensemble")
    if ens is None:
        ens = set(ctx.fichiers)
        # Un dépôt sans commit, celui qu'on vient d'équiper : tout y est
        # neuf, et le premier commit jugera son index.
        if ctx.tete is None and outils.a_des_commits(ctx.racine):
            suivis = outils.fichiers_suivis(ctx.racine)
            if suivis is not None:
                ens &= set(suivis) | set(memoire.fichiers_compagnon(ctx.racine))
        ctx._cache["ensemble"] = ens
    return ens


def _existe_tel_quel(ctx, chemin: str) -> bool:
    if chemin in _citables(ctx) or chemin == "":
        return True
    dossiers = ctx._cache.get("dossiers")
    if dossiers is None:
        dossiers = set()
        for f in _citables(ctx):
            parts = f.split("/")
            for i in range(1, len(parts)):
                dossiers.add("/".join(parts[:i]))
        ctx._cache["dossiers"] = dossiers
    return chemin in dossiers


@lru_cache(maxsize=4096)
def _ignore(racine, rev: str, chemin: str) -> bool:
    """Le chemin est ignoré par une règle d'un `.gitignore` de la version
    jugée : un dossier produit (`/tools/arbiters/`) se cite sans exister. La
    version jugée est l'arbre `rev` (un commit, l'index figé), ou l'index si
    `rev` est vide : une règle écrite sur le disque sans `git add`, comme une
    règle locale (`.git/info/exclude`, `core.excludesFile`), manque à un
    clone neuf, celui de la CI, et ne compte pas (B-0166, ADR-0063)."""
    r = subprocess.run(["git", "check-ignore", "-v", "--no-index", chemin], cwd=racine,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False
    # `source:ligne:motif<TAB>chemin`
    source, _, reste = r.stdout.partition("\t")[0].partition(":")
    motif = reste.partition(":")[2]
    if motif.startswith("!") or source.rsplit("/", 1)[-1] != ".gitignore" or source.startswith(("/", ".git/")):
        return False
    juge = subprocess.run(["git", "show", f"{rev}:{source}"], cwd=racine, capture_output=True, text=True)
    return juge.returncode == 0 and motif in {l.rstrip() for l in juge.stdout.splitlines()}


def _racines(ctx) -> set[str]:
    if "racines" not in ctx._cache:
        ctx._cache["racines"] = {f.split("/", 1)[0] for f in ctx.fichiers}
    return ctx._cache["racines"]


def _normaliser_chemin(base_dir: str, cible: str) -> str:
    parts = [] if cible.startswith("/") else [p for p in base_dir.split("/") if p]
    for p in cible.split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            if parts:
                parts.pop()
            continue
        parts.append(p)
    return "/".join(parts)


def textes_scannes(ctx) -> dict[str, str]:
    motifs = ctx.projet.gf("references", "scan", defaut=["**/*.md"])
    res = ctx.textes(motifs, ctx.projet.exclusions_docs())
    for chemin, f in ctx.memoire.fichiers.items():
        res.setdefault(chemin, f.texte)
    return res


@controle("memoire.references")
def references(ctx, r):
    """Tout identifiant, commit, fichier, lien ou chemin cité existe."""
    defs = ctx.memoire.definitions()
    prive_dispo = any(est_prive(c) for c in ctx.memoire.fichiers)
    autres: dict[str, list[tuple[str, int, str]]] = {}
    textes = textes_scannes(ctx)
    connus = depots_connus(ctx, textes.values())
    essais = ajoutes_par_une_branche_jetable(ctx, textes)

    def signaler(faute: str, chemin: str, ligne: int, objet: str):
        # Sur une branche jetable, hors de la CI, un fichier qu'elle ajoute
        # n'est qu'averti, quelle que soit la faute de référence ; sa pull
        # request le rejuge en entier (D-0087). Un fichier qu'un `git add`
        # livrerait n'est qu'averti sur l'arbre de travail : le commit, qui
        # juge l'index, le refuse s'il ne l'ajoute pas (ADR-0063).
        if isinstance(faute, AAjouter):
            r.avertir("memoire.references", faute, chemin, ligne, objet)
        elif chemin in essais:
            r.avertir("memoire.references", trad("{faute} — branche jetable, fichier qu'elle ajoute : averti, sa "
                                                 "pull request le jugera", faute=faute), chemin, ligne, objet)
        else:
            r.erreur("memoire.references", faute, chemin, ligne, objet)
    for chemin, texte in sorted(textes.items()):
        dossier = chemin.rsplit("/", 1)[0] if "/" in chemin else ""
        gele = memoire.couche_attendue(chemin) in COUCHES_GELEES
        demande = memoire.couche_attendue(chemin) == "demandes"
        for ident, ligne in memoire.mentions(texte):
            if ident.startswith("P"):
                if not est_prive(chemin) or not prive_dispo:
                    continue  # fuite : `memoire.prive` ; indisponible : signalé à part
            if ident not in defs:
                signaler(trad("`{ident}` ne désigne aucune entrée de la mémoire", ident=ident), chemin, ligne, ident)
        for i, ligne, code in memoire.lignes_hors_code(texte):
            if code:
                continue
            for type_, cible in memoire.references(ligne):
                if type_ == "id":
                    continue
                faute = verifier_ref(ctx, type_, cible, gele)
                if faute:
                    signaler(faute, chemin, i, f"{type_}:{cible}")
            vivante = memoire.sans_barre(ligne)
            for m in LIEN_RE.finditer(vivante):
                faute = _verifier_lien(ctx, chemin, dossier, m.group(1), gele)
                if faute:
                    signaler(faute, chemin, i, m.group(1))
            sans_refs = memoire.REF_RE.sub(" ", vivante)
            for m in CODE_EN_LIGNE.finditer(sans_refs):
                faute = _verifier_chemin_cite(ctx, m.group(1), gele)
                if faute and demande and protege_cite(ctx, m.group(1)):
                    faute = None
                if faute:
                    # Le genre de faute dans l'objet : un lien mort vers la même
                    # cible n'a pas la même clé d'adoption (B-0189).
                    signaler(faute, chemin, i, f"chemin:{m.group(1)}")
                depot = depot_non_declare(ctx, m.group(1), connus)
                if depot:
                    autres.setdefault(depot, []).append((chemin, i, m.group(1)))
    # Un avertissement par dépôt, au premier endroit qui le cite.
    for depot, ou in sorted(autres.items()):
        chemin, i, jeton = ou[0]
        r.avertir("memoire.references", trad("`{jeton}` : dépôt « {depot} » non déclaré, {n} chemin(s) cité(s) "
                                             "que rien ne vérifie, et aucune adresse du projet ne le lie : un "
                                             "lien vers ce dépôt le fait connaître ; sinon ce n'est pas un "
                                             "dépôt, et la forme `x:chemin` ne lui convient pas",
                                             jeton=jeton, depot=depot, n=len(ou)), chemin, i)


def ajoutes_par_une_branche_jetable(ctx, chemins) -> set[str]:
    """Hors de la CI, sur une branche jetable, les fichiers qu'elle ajoute :
    absents de la base, son point de divergence avec la branche par défaut
    (D-0087). Un ensemble vide sinon : sans base, rien ne dit ce qu'elle
    ajoute ; avant un push, chaque branche qui part doit être jetable. La
    mémoire privée reste jugée : aucune CI ne la relit."""
    noms = ctx.branches if ctx.branches is not None else [outils.branche_courante(ctx.racine)]
    if ctx.etage == "ci" or not ctx.base or not noms or not all(ctx.projet.branche_jetable(n) for n in noms):
        return set()
    base = set(ctx.fichiers_base)
    return {c for c in chemins if c not in base and not memoire.est_prive(c)}


def verifier_ref(ctx, type_: str, cible: str, historique: bool = False) -> str | None:
    if re.search(r"[<>…]", cible):
        return None  # un gabarit (`commit:<sha>`), pas une référence
    if type_ == "commit":
        if not re.fullmatch(r"[0-9a-f]{7,40}", cible):
            return trad("`commit:{cible}` n'est pas un SHA", cible=cible)
        # Absent du clone, il peut n'être plus que dans une pull request :
        # on les récupère avant de le dire absent, de GitHub ou de l'origine
        # qui les a récupérées (B-0117, B-0175).
        if not outils.objet_existe(ctx.racine, cible) and not (
                outils.recuperer_pull_requests(ctx.racine) and outils.objet_existe(ctx.racine, cible)):
            # Sa branche supprimée sans pull request, un clone qui l'a encore
            # le rend par une étiquette (B-0116).
            return trad("`commit:{cible}` n'existe pas dans ce dépôt, ni dans ses pull requests (historique "
                        "complet ? `fetch-depth: 0` ; sa branche supprimée sans pull request ? depuis un clone qui "
                        "l'a encore, `{commande}` le rend)", cible=cible, commande=outils.etiqueter([cible]))
    elif type_ == "fichier":
        chemin = re.split(r"[#]|:(?=\d)", cible, maxsplit=1)[0]
        if not _existe(ctx, chemin, historique) and not _ignore(ctx.racine, ctx.tete or "", chemin):
            return _faute_absent(ctx, chemin, trad("`fichier:{cible}` : {chemin} n'existe pas", cible=cible,
                                                   chemin=chemin))
    elif type_ == "cmd":
        premier = cible.split()[0] if cible.split() else ""
        if "/" in premier and not _existe(ctx, premier.removeprefix("./"), historique):
            return _faute_absent(ctx, premier.removeprefix("./"),
                                 trad("`cmd:{cible}` : {premier} n'existe pas", cible=cible, premier=premier))
    return None


def _verifier_lien(ctx, chemin_doc: str, dossier: str, cible: str, historique: bool = False) -> str | None:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", cible) or cible.startswith("//"):
        return None  # URL : jamais suivie, aucun service externe
    # Un lien s'écrit encodé (`%20` pour une espace, `%C3%A9` pour un « é ») :
    # il désigne le chemin et l'ancre décodés.
    chemin, _, ancre = (unquote(x) for x in cible.partition("#"))
    if chemin:
        cible_n = _normaliser_chemin(dossier, chemin)
        if not _existe(ctx, cible_n, historique) and not _ignore(ctx.racine, ctx.tete or "", cible_n) \
                and not (historique and _lien_d_un_ancien_nom(ctx, chemin_doc, chemin)):
            return _faute_absent(ctx, cible_n, trad("lien mort : {cible}", cible=cible))
    else:
        cible_n = chemin_doc
    # Une couche gelée ne voit vérifiés que ses fichiers : le titre qu'une
    # ancre visait a pu changer depuis.
    if ancre and cible_n.endswith(".md") and not historique:
        lieu = _alias(ctx, cible_n)
        texte = ctx.lire(lieu)
        if texte is not None and ancre not in ancres(texte) and not _ancre_deplacee(ctx, lieu, ancre):
            return trad("ancre morte : {cible}", cible=cible)
    return None


def _ancre_deplacee(ctx, chemin: str, ancre: str) -> bool:
    """L'ancre d'une entrée basculée en privé, écrite avant : elle n'a plus
    son titre."""
    f = ctx.memoire.fichiers.get(chemin)
    return f is not None and any(e.basculee and ancre.startswith(liens.ancre(e.id) + "--") for e in f.entrees)


# Ce qui précède `:` sans désigner un dépôt : un schéma d'URL, un type de
# référence de la mémoire, une révision de git (`HEAD:chemin`).
SCHEMAS = {"http", "https", "ftp", "file", "mailto", "ssh", "git", "data", "commit", "fichier", "cmd", "url"}
REVISION = re.compile(r"^(?:[A-Z_]*HEAD|[0-9a-f]{7,40})(?:[~^]\d*)*$")


# Un dépôt que le projet lie par son adresse : `https://hôte/propriétaire/dépôt`,
# ou `git@hôte:propriétaire/dépôt.git`.
DEPOT_LIE = re.compile(r"(?:\bhttps?://[\w.-]+\.[A-Za-z]{2,}(?::\d+)?/|\bgit@[\w.-]+:)[\w.-]+/([\w.-]+?)(?:\.git)?"
                       r"(?=[/#?\s)\]>\"'`]|$)")


def depots_connus(ctx, textes) -> set[str]:
    """Les dépôts que le projet connaît déjà, sans réglage : ceux qu'il lie
    par leur adresse, dans les textes lus ou dans `.gitmodules`, et ceux que
    les garde-fous déclarent (`[references] repos`), pour un dépôt qu'aucune
    adresse ne nomme. L'outil s'adapte au projet : il ne demande pas ce que
    le projet dit déjà."""
    connus = set(ctx.projet.gf("references", "repos", defaut=[]) or [])
    for texte in [*textes, ctx.lire(".gitmodules") or ""]:
        connus |= {m.group(1).rstrip(".") for m in DEPOT_LIE.finditer(texte)}  # une adresse en fin de phrase
    return connus


def depot_non_declare(ctx, jeton: str, connus: set[str] | None = None) -> str | None:
    """Le dépôt d'un `depot:chemin` cité, si le projet ne le connaît pas
    (`depots_connus`) : son chemin n'est vérifié nulle part, et n'importe
    quelle chaîne `x:chemin` passerait."""
    m = re.match(r"^([A-Za-z0-9][\w.+-]*):([^:\s]*/[^\s]*|[^:\s/]+\.\w+)$", jeton.strip())
    if not m or m.group(1).lower() in SCHEMAS or m.group(2).startswith("//") or REVISION.match(m.group(1)):
        return None
    if connus is None:
        connus = set(ctx.projet.gf("references", "repos", defaut=[]) or [])
    return None if m.group(1) in connus else m.group(1)


def protege_cite(ctx, jeton: str) -> bool:
    """Un fichier protégé, cité par une demande : elle peut proposer de
    l'ajouter ou de le retirer, et `protege.fichiers` juge le changement avec
    son empreinte. Une mise à jour du socle qui pose un fichier protégé
    nouveau, un skill par exemple, ne se faisait pas valider : sa demande,
    qui citait un chemin encore absent, était refusée (B-0127)."""
    j = jeton.strip().strip("/")
    return bool(j) and bool(outils.filtrer([j], ctx.projet.chemins_proteges()))


def _verifier_chemin_cite(ctx, jeton: str, historique: bool = False) -> str | None:
    """Un chemin du dépôt cité entre accents graves. Ne juge que ce qui en a
    clairement la forme et commence par une racine du dépôt."""
    j = jeton.strip()
    if "/" not in j or any(c in INTERDITS_CHEMIN for c in j):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", j) or j.startswith(("/", "../")):
        return None
    j = j.removeprefix("./")
    j = re.sub(r"(:\d+)+$", "", j).split("#", 1)[0]
    dossier = j.endswith("/")
    j = j.rstrip("/")
    if not j or j.split("/", 1)[0] not in _racines(ctx):
        return None
    if _existe(ctx, j, historique):
        return None
    # Un répertoire ignoré (`/tools/arbiters/`) ne se reconnaît qu'avec sa
    # barre finale : sans elle, git ne sait pas que c'est un répertoire,
    # sauf s'il est sur le disque, et un clone neuf ne l'a pas. Cité sans
    # elle, présent ici, il serait jugé autrement dans la CI (B-0166).
    if not dossier and (Path(ctx.racine) / j).is_dir() and not (ctx.tete is None and _a_ajouter(ctx, j)):
        return trad("dossier non suivi cité sans barre finale : `{jeton}` — sans elle, il ne se juge pas comme dans "
                    "un clone neuf : écrire `{j}/`", jeton=jeton, j=j)
    if _ignore(ctx.racine, ctx.tete or "", j + "/" if dossier else j):
        return None
    imbrique = outils.depot_imbrique(ctx.racine, j) if ctx.tete is None else None
    if imbrique:
        return trad("chemin cité dans le dépôt git imbriqué `{depot}/` : `{jeton}` — le dépôt ne le suit pas, et "
                    "`git add` n'en ferait qu'un lien de sous-module : ne pas le citer", depot=imbrique, jeton=jeton)
    if ctx.tete is None and _a_ajouter(ctx, j):
        return AAjouter(trad("chemin cité non suivi par git : `{jeton}` — à ajouter (`git add`) : le commit qui ne "
                             "l'ajoute pas sera refusé, et la CI le dirait inexistant", jeton=jeton))
    if ctx.tete is None and (Path(ctx.racine) / j).exists():
        return trad("chemin cité ignoré par git : `{jeton}` — présent sur le disque seulement (une règle locale, "
                    "ou d'un `.gitignore` pas encore ajouté à l'index, l'ignore), il manquera à un clone neuf, celui "
                    "de la CI : ne pas le citer, ou ajouter la règle (`git add` du `.gitignore`)", jeton=jeton)
    return trad("chemin cité inexistant : `{jeton}`", jeton=jeton)


class AAjouter(str):
    """La faute d'un chemin cité qu'un `git add` livrerait : avertie sur
    l'arbre de travail ; le commit, qui juge l'index, la refuse s'il ne
    l'ajoute pas (ADR-0063)."""


def _faute_absent(ctx, chemin: str, faute: str) -> str:
    """La faute d'un fichier lié ou référencé hors des fichiers suivis :
    avertie s'il est à ajouter (`AAjouter`), refusée sinon."""
    c = chemin.strip("/")
    if ctx.tete is None and (_a_ajouter(ctx, c) or _a_ajouter(ctx, _nom_basculee(c) or c)):
        return AAjouter(trad("{faute} — non suivi par git, à ajouter (`git add`)", faute=faute))
    return faute


def _a_ajouter(ctx, chemin: str) -> bool:
    """Le chemin est un fichier non suivi de l'arbre de travail qu'aucune
    règle de git n'ignore, ou un dossier qui en contient : `git add` le
    livre."""
    hors_index = ctx._cache.get("a-ajouter")
    if hors_index is None:
        hors_index = set()
        for f in set(ctx.fichiers) - _citables(ctx):
            parts = f.split("/")
            hors_index.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
        ctx._cache["a-ajouter"] = hors_index
    return chemin in hors_index


@controle("memoire.prive")
def prive(ctx, r):
    """Aucun identifiant privé dans un fichier public : le public ne référence
    jamais le privé. Un bloc de code et une archive sont publics comme le
    reste."""
    moteur = ctx.projet.dossier_moteur.rstrip("/") + "/"
    for chemin in ctx.fichiers:
        if est_prive(chemin) or chemin.startswith(moteur):
            continue
        texte = ctx.lire(chemin)
        if texte is None or "\0" in texte[:4096] or len(texte) > 2_000_000:
            continue
        for ligne, contenu in enumerate(texte.splitlines(), start=1):
            for m in memoire.ID_RE.finditer(contenu):
                if m["prive"] and memoire.id_valide(m["type"], m["num"]):
                    r.erreur("memoire.prive", trad("identifiant privé `{ident}` dans un fichier public",
                                                   ident=m.group(0)), chemin, ligne)


# --------------------------------------------------------------------------
# Lecture prouvée
# --------------------------------------------------------------------------



# Une décision prise en séance, et sa question : la conversation que
# l'humain a lue, recopiée telle quelle.
SEANCE = re.compile(r"(?m)^> .*\b(?:forme : séance|form: session)\b")
QUESTION_SEANCE = re.compile(r"(?ms)^## (?:Question posée|Question asked)\n.*?(?=^## |\Z)")


def sans_question_de_seance(texte: str) -> str:
    """Le texte d'une entrée, sans la question d'une décision prise en séance :
    elle recopie ce que l'humain a lu dans la conversation, et ne se corrige
    plus une fois sa réponse écrite (B-0100). La lecture se prouve dans ce que
    l'agent écrit lui-même. Le titre, qui nomme la question, peut nommer ce
    qu'elle cite (B-0103) ; ce que seul le titre cite se prouve encore."""
    if not SEANCE.search(texte):
        return texte
    m = QUESTION_SEANCE.search(texte)
    cites = {i for i, _ in memoire.mentions(m.group(0))} if m else set()
    titre, _, corps = QUESTION_SEANCE.sub("", texte).partition("\n")
    if titre.startswith("#"):
        for ident in cites:
            titre = re.sub(rf"\b{re.escape(ident)}\b(?!@)", "", titre)
    return f"{titre}\n{corps}"

@controle("memoire.lectures", base=True)
def lectures(ctx, r):
    """Une citation `ID@empreinte` ou `index@empreinte` ajoutée désigne une
    version que l'agent a pu lire (`socle.readings`) ; une
    décision, une demande ou un sujet de backlog nouveaux prouvent ce qu'ils
    ont lu avant d'être écrits."""
    from socle import readings as lp

    mem, base = ctx.memoire, ctx.memoire_base
    defs = mem.definitions()
    nouveaux = set(defs) - set(base.definitions())
    plage = lp.Plage(ctx.racine, base, mem, [c["sha"] for c in ctx.commits])

    for chemin, texte in sorted(textes_scannes(ctx).items()):
        avant = ctx.lire_base(chemin) or ""
        for ident, h, ligne in memoire.citations(texte):
            soi = lp.entree_englobante(mem, chemin, ligne)
            if ident not in defs or lp.deja_citee(soi, f"{ident}@{h}", base, avant):
                continue
            if not lp.entree_lue(plage, chemin, soi, ident, h):
                r.erreur("memoire.lectures", trad("`{ident}@{h}` ne correspond pas à la version actuelle de "
                                                  "{ident} (lue avant un changement, ou inventée) : la relire, "
                                                  "`python3 .socle/socle show {ident}`, et citer l'empreinte "
                                                  "affichée", ident=ident, h=h), chemin, ligne)
        for index, h, ligne in memoire.citations_index(texte):
            soi = lp.entree_englobante(mem, chemin, ligne)
            if lp.deja_citee(soi, f"{index}@{h}", base, avant):
                continue
            if not lp.index_lu(plage, chemin, soi, index, h):
                r.erreur("memoire.lectures", trad("`{index}@{h}` ne correspond à aucune version récente de "
                                                  "l'index : le relire, `python3 .socle/socle show --index "
                                                  "{index}`, et citer l'empreinte affichée", index=index, h=h),
                         chemin, ligne)

    # Ce que les entrées nouvelles doivent prouver avoir lu.
    for ident in sorted(nouveaux):
        e = defs[ident][0]
        if e.archivee:
            continue
        if e.depuis and all(d in defs and defs[d][0].basculee for d in e.depuis):
            continue  # la copie privée d'une entrée basculée : ce n'est pas une entrée nouvelle
        if e.type == "ADR" and not any(i == "decisions" for i, _, _ in memoire.citations_index(e.texte)):
            r.erreur("memoire.lectures", trad("décision nouvelle `{ident}` sans `lu : decisions@…` : consulter "
                                              "l'index des décisions avant d'en ajouter une (`socle show "
                                              "--index decisions`)", ident=ident), e.fichier, e.ligne)
        if e.type == "B" and not any(i == "backlog" for i, _, _ in memoire.citations_index(e.texte)):
            r.erreur("memoire.lectures", trad("sujet nouveau `{ident}` sans `lu : backlog@…` : consulter le "
                                              "backlog avant d'y ajouter, pour ne pas dupliquer (`socle show "
                                              "--index backlog`)", ident=ident), e.fichier, e.ligne)
        if e.type in ("ADR", "D"):
            texte = sans_question_de_seance(e.texte)
            prouves = {i for i, _, _ in memoire.citations(texte)}
            for cite in sorted({i for i, _ in memoire.mentions(texte)} - prouves - {ident}):
                r.erreur("memoire.lectures", trad("`{ident}` s'appuie sur `{cite}` sans montrer l'avoir lu : "
                                                  "citer `{cite}@<empreinte>`, l'empreinte que donne `socle "
                                                  "show {cite}`", ident=ident, cite=cite), e.fichier, e.ligne)


# --------------------------------------------------------------------------
# Preuves, backlog
# --------------------------------------------------------------------------

TYPES_PREUVE = {"commit", "fichier", "cmd", "id"}


@controle("memoire.preuves")
def preuves(ctx, r):
    """Un fait mesuré pointe vers sa preuve ; un fait réfuté garde sa trace ; un
    fait validé cite la demande que l'humain a validée."""
    par_id = {d.id: d for d in ctx.demandes if d.id}
    for e in ctx.memoire.entrees("F"):
        if e.statut == "mesure":
            if not {t for t, _ in e.refs("preuve")} & TYPES_PREUVE:
                r.erreur("memoire.preuves", trad("`{id}` est « mesuré » sans `preuve` (commit:, fichier:, cmd: "
                                                 "ou identifiant)", id=e.id), e.fichier, e.ligne)
        elif e.statut == "refute":
            if not e.barre:
                r.erreur("memoire.preuves", trad("`{id}` réfuté : son titre se barre (`~~…~~`), il ne s'efface "
                                                 "pas", id=e.id), e.fichier, e.ligne)
            if not {t for t, _ in e.refs("refutation", "preuve")} & TYPES_PREUVE:
                r.erreur("memoire.preuves", trad("`{id}` réfuté sans `refutation` qui pointe vers la mesure",
                                                 id=e.id), e.fichier, e.ligne)
        elif e.statut == "valide":
            cites = [c for t, c in e.refs("validation") if t == "id" and c.lstrip("P").startswith("D-")]
            if not cites:
                r.erreur("memoire.preuves", trad("`{id}` « validé » sans `validation : D-NNNN` — ce statut ne "
                                                 "s'écrit que par l'humain, via une demande", id=e.id), e.fichier, e.ligne)
            for c in cites:
                d = par_id.get(c)
                if d is None or not d.validee:
                    r.erreur("memoire.preuves", trad("`{id}` cite `{demande}`, qui n'a pas de réponse « valider »",
                                                     id=e.id, demande=c), e.fichier, e.ligne)


@controle("memoire.collisions", base=True)
def collisions(ctx, r):
    """Un identifiant que la branche définit et que la branche par défaut a
    pris aussi depuis leur divergence, pour une autre entrée, serait défini
    deux fois à la fusion : dit avant, avec la commande qui répare."""
    from socle import identifiers as identifiants

    bases = identifiants.bases_a_comparer(ctx.racine, ctx.base)
    for ident, ici, la_bas in identifiants.collisions(ctx.racine, ctx.tete, ctx.memoire, bases):
        r.erreur("memoire.collisions", trad("`{ident}` est pris aussi sur la branche par défaut, depuis que "
                                            "cette branche s'en est séparée, pour « {titre} » : à la fusion, "
                                            "il serait défini deux fois. `python3 .socle/socle renumber "
                                            "{ident}` lui donne le prochain libre et le reporte",
                                            ident=ident, titre=la_bas.titre), ici.fichier, ici.ligne)


@controle("memoire.backlog")
def backlog(ctx, r):
    """Chaque sujet a une origine ; un sujet clos a une référence, et il est rangé avec les clos ; un sujet
    fait a coché tout ce que dit sa section « Fait quand »."""
    for e in ctx.memoire.entrees("B"):
        if e.basculee:
            continue
        if not e.refs("origine"):
            r.erreur("memoire.backlog", trad("`{id}` sans `origine` (entrée de journal, commit ou demande)",
                                             id=e.id), e.fichier, e.ligne)
        clos = e.statut in memoire.BACKLOG_CLOS
        # Fait quand ce que dit sa section « Fait quand » est fait (D-0064).
        ouverts = [texte for coche, texte in memoire.criteres(e) if not coche]
        if e.statut == "fait" and ouverts:
            r.erreur("memoire.backlog", trad("`{id}` est clos « fait » avec un critère de « Fait quand » non coché : "
                                             "{criteres}", id=e.id, criteres=" ; ".join(ouverts[:3])),
                     e.fichier, e.ligne)
        if clos and not e.refs("ref"):
            r.erreur("memoire.backlog", trad("`{id}` est clos (« {statut} ») sans `ref` vers ce qui l'a clos",
                                             id=e.id, statut=e.statut), e.fichier, e.ligne)
        # Un sujet clos quitte les ouverts.
        if memoire.couche_attendue(e.fichier) == "backlog" and clos != memoire.parmi_les_clos(e.fichier):
            r.erreur("memoire.backlog", trad("`{id}` est clos (« {statut} ») mais reste parmi les sujets ouverts : "
                                             "`python3 .socle/socle archive` le range dans `{dossier}/`",
                                             id=e.id, statut=e.statut, dossier=memoire.DOSSIER_CLOS) if clos else
                     trad("`{id}` est rangé parmi les sujets clos alors qu'il est « {statut} » : `python3 "
                          ".socle/socle archive` le remet parmi les ouverts", id=e.id, statut=e.statut),
                     e.fichier, e.ligne)


@controle("memoire.ordre")
def ordre(ctx, r):
    """Un sujet n'attend (`après`) que des sujets du backlog ou des demandes,
    jamais lui-même de proche en proche, et ne se dit fait qu'une fois clos
    ce qu'il attend : un jalon ne se clôt pas sur des tâches ouvertes, ni un
    sujet sur une demande sans réponse. Sa priorité, s'il en a une, est
    haute ou basse."""
    sujets = {e.id: e for e in ctx.memoire.entrees("B") if not e.archivee and not e.basculee}
    demandes = {e.id: e for e in ctx.memoire.entrees("D") if not e.basculee}
    for e in sujets.values():
        p = memoire.priorite(e)
        if p is not None and p not in memoire.PRIORITES:
            r.erreur("memoire.ordre", trad("`{id}` : `priorité` vaut `haute` ou `basse`, la normale ne s'écrit pas "
                                           "({valeur})", id=e.id, valeur=e.meta["priorite"]), e.fichier, e.ligne)
        if "apres" not in e.meta:
            continue
        refs = e.refs("apres")
        if not refs or any(t != "id" or not re.fullmatch(r"P?[BD]-\d{4}", c) for t, c in refs):
            r.erreur("memoire.ordre", trad("`{id}` : `après` ne nomme que des sujets du backlog ou des demandes "
                                           "({valeur})", id=e.id, valeur=e.meta["apres"]), e.fichier, e.ligne)
        if e.statut == "fait":
            for d in memoire.dependances(e):
                if d in sujets and sujets[d].statut not in memoire.BACKLOG_CLOS:
                    r.erreur("memoire.ordre", trad("`{id}` est fait avant `{dep}`, qu'il attend, encore « {statut} »",
                                                   id=e.id, dep=d, statut=sujets[d].statut), e.fichier, e.ligne)
                elif d in demandes and not memoire.demande_close(ctx.memoire, demandes[d]):
                    r.erreur("memoire.ordre", trad("`{id}` est fait avant `{dep}`, qu'il attend, encore sans réponse",
                                                   id=e.id, dep=d), e.fichier, e.ligne)
    # Un cycle se dit une fois, depuis le plus petit de ses sujets.
    for depart in sorted(sujets):
        pile = [[depart]]
        while pile:
            chemin = pile.pop()
            suivants = memoire.dependances(sujets[chemin[-1]])
            if depart in suivants:
                e = sujets[depart]
                r.erreur("memoire.ordre", trad("`{id}` s'attend lui-même : {cycle}", id=depart,
                                               cycle=" → ".join(chemin + [depart])), e.fichier, e.ligne)
                break
            pile += [chemin + [d] for d in suivants if d in sujets and d > depart and d not in chemin]


# --------------------------------------------------------------------------
# Budgets, péremption, retard
# --------------------------------------------------------------------------


@controle("memoire.budgets")
def budgets(ctx, r):
    """Chaque couche et le fichier d'instructions ont un plafond de taille."""
    budgets = ctx.projet.gf("budgets", defaut={}) or {}
    couverts = set()
    # La zone privée suit les budgets de la zone publique : mêmes formats,
    # mêmes contrôles (cadrage, règles de classement, point 5).
    ch = ctx.projet.chemins
    miroirs = {c: ch.memoire + "/" + memoire.hors_zone_privee(c) for c in ctx.fichiers if est_prive(c)}
    # Un sujet rangé avec les clos garde le plafond d'un sujet.
    miroirs = {c: memoire.hors_des_clos(miroirs.get(c, c)) for c in ctx.fichiers
               if c in miroirs or memoire.parmi_les_clos(c)}
    for motif, b in budgets.items():
        vises = set(outils.filtrer(ctx.fichiers, [motif])) | {c for c, m in miroirs.items() if outils.correspond(m, [motif])}
        for chemin in sorted(vises):
            couverts.add(chemin)
            texte = ctx.lire(chemin) or ""
            # Les lignes d'empreinte d'une demande, un fichier protégé et son
            # empreinte, ne comptent pas : l'humain lit les fichiers dans la
            # pull request, et la liste d'une mise à jour ne doit rien
            # coûter au contexte (ADR-0058).
            demande = miroirs.get(chemin, chemin).startswith(ch.demandes + "/") and not memoire.est_reponse(chemin)
            if demande:
                texte = demandes.hors_empreintes(texte, ctx.projet)
            octets = len(texte.encode("utf-8"))
            lignes = texte.count("\n") + (0 if texte.endswith("\n") or not texte else 1)
            # Rien ne s'archive d'un fichier d'instructions, et la section du
            # socle s'y régénère à chaque mise à jour (B-0129).
            instructions_ = chemin in (config.INSTRUCTIONS, "CLAUDE.md")
            if "max_bytes" in b and octets > b["max_bytes"] and instructions_:
                r.erreur("memoire.budgets", trad("{octets} octets pour un budget de {budget} ({motif}) : resserrer "
                                                 "la partie propre au projet, hors de la section du socle, ou "
                                                 "relever le budget par une demande validée", octets=octets,
                                                 budget=b['max_bytes'], motif=motif), chemin)
            elif "max_bytes" in b and octets > b["max_bytes"] and demande:
                r.erreur("memoire.budgets", trad("{octets} octets pour un budget de {budget} ({motif}), les lignes "
                                                 "d'empreinte mises à part : resserrer la demande, ou y ramener à "
                                                 "une ligne d'empreinte, le chemin et l'empreinte sans rien "
                                                 "d'autre, chaque fichier protégé qu'elle fait approuver",
                                                 octets=octets, budget=b['max_bytes'], motif=motif), chemin)
            elif "max_bytes" in b and octets > b["max_bytes"]:
                r.erreur("memoire.budgets", trad("{octets} octets pour un budget de {budget} ({motif}) : archiver "
                                                 "dans le journal", octets=octets, budget=b['max_bytes'], motif=motif), chemin)
            if "max_lines" in b and lignes > b["max_lines"] and instructions_:
                r.erreur("memoire.budgets", trad("{lignes} lignes pour un budget de {budget} ({motif}) : resserrer "
                                                 "la partie propre au projet, hors de la section du socle, ou "
                                                 "relever le budget par une demande validée", lignes=lignes,
                                                 budget=b['max_lines'], motif=motif), chemin)
            elif "max_lines" in b and lignes > b["max_lines"]:
                r.erreur("memoire.budgets", trad("{lignes} lignes pour un budget de {budget} ({motif}) : archiver "
                                                 "dans le journal", lignes=lignes, budget=b['max_lines'], motif=motif), chemin)
    # Le chantier actif public et privé s'injectent ensemble au démarrage,
    # dans la même part de sa borne (ADR-0071) : le budget du chantier actif
    # juge leur somme, qui n'y est alors jamais coupée.
    actif, actif_prive = ch.actif, ch.dans_prive(ch.actif)
    budget = ctx.projet.budget_octets(actif)
    if budget is not None and actif in ctx.fichiers and actif_prive in ctx.fichiers:
        public, prive = ctx.lire(actif) or "", ctx.lire(actif_prive) or ""
        tailles = [len(public.encode("utf-8")), len(prive.encode("utf-8"))]
        # Seul au-delà, chacun l'a déjà dit ; chiffré, le privé ne se mesure pas.
        if memoire.lisible(prive) and max(tailles) <= budget < sum(tailles):
            r.erreur("memoire.budgets", trad("{public} + {prive} octets pour le chantier actif public et privé, qui "
                                             "partagent une part de la sortie du démarrage, pour un budget de "
                                             "{budget} à eux deux : archiver dans le journal", public=tailles[0],
                                             prive=tailles[1], budget=budget), actif_prive)
    # Le fichier d'instructions est AGENTS.md ; tant qu'une adoption garde
    # CLAUDE.md comme source (renommage en attente), c'est lui qui est relu.
    instructions = [config.INSTRUCTIONS]
    if (ctx.lire("CLAUDE.md") or "").strip() not in ("", "@AGENTS.md"):
        instructions.append("CLAUDE.md")
    for chemin in list(ctx.memoire.fichiers) + instructions:
        if chemin in ctx.fichiers and chemin not in couverts:
            r.erreur("memoire.budgets", trad("aucun budget ne couvre ce fichier (`[budgets]` des garde-fous)"), chemin)


def date_derniere_modif(ctx, chemin: str) -> float | None:
    if ctx.tete is None and chemin in ctx._cache.setdefault("sales", _sales(ctx)):
        return time.time()
    rev = ctx.rev_commit
    if not outils.a_des_commits(ctx.racine):
        return time.time()
    sortie = outils.git(ctx.racine, "log", "-1", "--format=%ct", rev, "--", chemin, check=False).strip()
    return float(sortie) if sortie else None


def _sales(ctx) -> set[str]:
    if not outils.a_des_commits(ctx.racine):
        return set(ctx.fichiers)
    sortie = outils.git(ctx.racine, "status", "--porcelain", "-z", check=False)
    return {e[3:] for e in sortie.split("\0") if len(e) > 3}


@controle("memoire.peremption")
def peremption(ctx, r):
    """Un chantier actif qui ne bouge plus est signalé — un avertissement, pas un échec."""
    jours = ctx.projet.gf("staleness", "active_days", defaut=7)
    chemin = ctx.projet.chemins.actif
    if chemin not in ctx.fichiers:
        return
    t = date_derniere_modif(ctx, chemin)
    if t is None:
        return
    age = (time.time() - t) / 86400
    if age > jours:
        r.avertir("memoire.peremption", trad("chantier actif inchangé depuis {age} jours (seuil : {jours})",
                                             age=format(age, '.0f'), jours=jours), chemin)


@controle("memoire.retard", etages=("agent",), base=True)
def retard(ctx, r):
    """Du code a changé et la mémoire non : la fin de tour attend sa mise à jour."""
    if not ctx.projet.gf("memory", "require_update_on_code_change", defaut=True):
        return
    code = outils.filtrer(ctx.changes, ctx.projet.chemins_code())
    if code and not any(memoire.est_memoire(c) for c in ctx.changes):
        r.erreur("memoire.retard", trad("{n} fichier(s) de code changé(s) depuis la base et aucun de "
                                        "`{memoire}/` : mettre à jour le chantier actif ou le journal avant de "
                                        "conclure", n=len(code), memoire=ctx.projet.chemins.memoire))


# --------------------------------------------------------------------------
# Ajout seul : comparé à la base
# --------------------------------------------------------------------------


def _corps_sans_meta(e: memoire.Entree) -> str:
    """Le texte de l'entrée sans son titre ni sa ligne de métadonnées, celle
    qui suit le titre. Une citation du corps en fait partie : la réécrire,
    c'est réécrire la décision."""
    lignes = e.texte.splitlines()[1:]
    j = 0
    while j < len(lignes) and not lignes[j].strip():
        j += 1
    while j < len(lignes) and lignes[j].lstrip().startswith(">"):
        j += 1
    return "\n".join(lignes[j:]).strip()


def _norm(t: str) -> str:
    return "\n".join(l.rstrip() for l in t.strip().splitlines())


@controle("memoire.ajout-seul", base=True)
def ajout_seul(ctx, r):
    """Journal et décisions en ajout seul ; un fait ne disparaît pas, ne change
    qu'avec une nouvelle preuve, et se barre quand il est réfuté. La mémoire
    privée aussi, relue à la base."""
    from socle import private as prive

    _comparer(ctx, r, ctx.memoire_base.definitions(), ctx.memoire.definitions())
    if prive.mode(ctx.projet):
        avant, apres = prive.memoire_privee_a(ctx.projet, ctx.base), prive.memoire_privee(ctx)
        if avant is None or apres is None:
            r.indisponible("memoire.ajout-seul", trad("mémoire privée illisible ici : son ajout seul n'est pas "
                                                      "vérifié"))
        else:
            _comparer(ctx, r, {i: d for i, d in avant.definitions().items() if i.startswith("P")},
                      apres.definitions())

    reponses_base = {c for c in ctx.fichiers_base if memoire.est_reponse(c)}
    for c in sorted(reponses_base):
        if ctx.lire(c) != ctx.lire_base(c):
            r.erreur("memoire.ajout-seul", trad("réponse humaine modifiée ou supprimée : elle est définitive"), c)


def _comparer(ctx, r, avant: dict, apres: dict):
    for ident, defs in avant.items():
        a = defs[0]
        b = apres.get(ident, [None])[0]
        if a.basculee:
            if b is None or not b.basculee or _norm(a.texte) != _norm(b.texte):
                r.erreur("memoire.ajout-seul", trad("`{ident}` basculée dans la mémoire privée : elle reste "
                                                    "telle quelle", ident=ident),
                         (b or a).fichier, (b or a).ligne)
            continue
        if b is not None and b.basculee:
            _bascule(ctx, r, a, b)
            continue
        if a.type == "J":
            if b is None:
                r.erreur("memoire.ajout-seul", trad("entrée de journal `{ident}` supprimée (le journal est en "
                                                    "ajout seul)", ident=ident), a.fichier, a.ligne)
            elif _norm(a.texte) != _norm(b.texte) and not _seulement_ajouts(a.texte, b.texte):
                r.erreur("memoire.ajout-seul", trad("entrée de journal `{ident}` modifiée (le journal est en "
                                                    "ajout seul)", ident=ident), b.fichier, b.ligne)
        elif a.type == "ADR":
            if b is None:
                r.erreur("memoire.ajout-seul", trad("décision `{ident}` supprimée (une décision se remplace, "
                                                    "elle ne s'efface pas)", ident=ident), a.fichier, a.ligne)
                continue
            if _norm(_corps_sans_meta(a)) != _norm(_corps_sans_meta(b)) or a.titre != b.titre:
                r.erreur("memoire.ajout-seul", trad("décision `{ident}` réécrite : seul son statut peut "
                                                    "changer, une décision nouvelle la remplace", ident=ident), b.fichier, b.ligne)
            if a.statut != b.statut and (a.statut, b.statut) not in TRANSITIONS_ADR:
                r.erreur("memoire.ajout-seul", trad("décision `{ident}` : passage « {statut} » → « {apres} » "
                                                    "interdit", ident=ident, statut=a.statut, apres=b.statut), b.fichier, b.ligne)
            if b.statut == "remplacee" and not [c for t, c in b.refs("remplacee-par") if t == "id"]:
                r.erreur("memoire.ajout-seul", trad("décision `{ident}` remplacée sans `remplacée-par : "
                                                    "ADR-NNNN`", ident=ident), b.fichier, b.ligne)
        elif a.type == "F":
            if b is None:
                r.erreur("memoire.ajout-seul", trad("fait `{ident}` effacé : un fait se barre (réfuté) ou "
                                                    "s'archive dans le journal, jamais ne disparaît",
                                                    ident=ident), a.fichier, a.ligne)
                continue
            if b.archivee:
                continue
            if _norm(a.texte) == _norm(b.texte):
                continue
            nouvelles = set(b.refs("preuve", "refutation", "validation")) - set(a.refs("preuve", "refutation", "validation"))
            if not nouvelles:
                r.erreur("memoire.ajout-seul", trad("fait `{ident}` modifié sans référence de preuve nouvelle",
                                                    ident=ident), b.fichier, b.ligne)
            if b.statut == "refute" and a.statut != "refute":
                if _norm(a.corps) and _norm(a.corps) not in _norm(b.corps):
                    r.erreur("memoire.ajout-seul", trad("fait `{ident}` réfuté : son texte se garde, barré ; "
                                                        "il ne se réécrit pas", ident=ident), b.fichier, b.ligne)
        elif a.type == "B":
            # Un sujet ne quitte pas le backlog : clos, il se range avec les
            # clos.
            if b is None or b.archivee and not a.archivee:
                r.erreur("memoire.ajout-seul", trad("sujet `{ident}` disparu du backlog : un sujet clos se range "
                                                    "par `socle archive`, il ne s'efface pas", ident=ident),
                         a.fichier, a.ligne)
        elif a.type == "D":
            if b is None:
                r.erreur("memoire.ajout-seul", trad("demande `{ident}` supprimée (la retirer : `retirée : "
                                                    "<raison>` dans ses métadonnées)", ident=ident), a.fichier, a.ligne)


def _bascule(ctx, r, a: memoire.Entree, b: memoire.Entree):
    """Une entrée publique basculée dans la mémoire privée : une copie
    privée qui cite `depuis : <identifiant>` en reprend le texte, sans quoi la
    bascule serait un effacement."""
    from socle import private as prive

    privee = prive.memoire_privee(ctx) if prive.mode(ctx.projet) else None
    if privee is None and prive.mode(ctx.projet):
        r.avertir("memoire.ajout-seul", trad("`{id}` basculée : sa copie privée ne se lit pas ici", id=a.id), b.fichier, b.ligne)
        return
    copies = [e for e in privee.entrees() if e.prive and a.id in e.depuis] if privee else []
    if not copies:
        r.erreur("memoire.ajout-seul", trad("`{id}` basculée sans copie privée qui la reprenne (`depuis : "
                                            "{id}`) : son contenu serait perdu ; `socle private move` fait les "
                                            "deux", id=a.id), b.fichier, b.ligne)
        return
    if not any(_norm(a.corps) in _norm(c.corps) and a.titre == c.titre for c in copies):
        r.erreur("memoire.ajout-seul", trad("`{id}` basculée : sa copie privée n'en reprend ni le titre ni le "
                                            "texte", id=a.id),
                 b.fichier, b.ligne)


def _seulement_ajouts(avant: str, apres: str) -> bool:
    """Une entrée de journal qui reçoit une archive imbriquée à la suite de son
    texte reste en ajout seul ; un ajout commence sur une ligne nouvelle,
    jamais au milieu d'une phrase."""
    a, b = _norm(avant), _norm(apres)
    return b == a or b.startswith(a + "\n")


# --------------------------------------------------------------------------
# Demandes
# --------------------------------------------------------------------------


@controle("demandes.contrat")
def contrat(ctx, r):
    """Toute demande en attente est autonome : huit champs, aucun identifiant nu."""
    for d in ctx.demandes:
        if d.reponse is not None:
            continue  # gelée : elle a été lintée quand elle a été écrite
        for faute in demandes.linter(d, ctx.projet):
            r.erreur("demandes.contrat", faute, d.chemin)


@controle("demandes.reponses")
def reponses(ctx, r):
    """Une réponse porte sur le texte exact de sa demande et en est une réponse possible."""
    for d in ctx.demandes:
        for faute in demandes.verifier_reponse(d):
            r.erreur("demandes.reponses", faute, d.chemin_reponse or d.chemin)
    for c in ctx.fichiers:
        if memoire.est_reponse(c):
            if memoire.demande_de_reponse(c) not in ctx.fichiers:
                r.erreur("demandes.reponses", trad("réponse sans demande"), c)


@controle("demandes.reponse-seule", etages=("agent", "git"), base=True)
def reponse_seule(ctx, r):
    """Une réponse `valider` pas encore poussée part avec le changement
    qu'elle autorise : poussée seule, elle ne le couvrira pas — un
    avertissement, pas un refus.

    La CI d'un push et le hook avant push ne comptent que les validations
    de leur plage (B-0043) : la réponse poussée avant le test ou le fichier
    protégé qu'elle nomme ne les couvre plus au push suivant (B-0142,
    ADR-0076). La plage est celle qui n'est pas encore poussée ; le
    changement se mesure sur la branche, depuis la branche par défaut : un
    fichier poussé sous une demande en attente (D-0071) précède sa réponse
    sans dommage.

    Une clé des garde-fous que la demande nomme se suit comme un test : le
    cliquet ne compte lui aussi que les validations de sa plage. Un
    avertissement ne refuse rien : le contrôle qui plante le dit en
    avertissement, jamais en erreur (B-0215, ADR-0076)."""
    try:
        _reponse_seule(ctx, r)
    except Exception as e:  # un avertissement en panne ne refuse ni commit, ni push, ni fin de tour
        r.avertir("demandes.reponse-seule", trad("le contrôle a planté : {erreur}",
                                                 erreur=f"{type(e).__name__}: {e}"))


def _reponse_seule(ctx, r):
    base = outils.base_non_poussee(ctx.racine, ctx.branches)
    if not base:
        return
    # Le plus souvent, la plage n'ajoute aucune réponse : un diff suffit.
    if not any(memoire.est_reponse(c) for c in outils.fichiers_changes(ctx.racine, base, ctx.tete)):
        return
    for d in demandes.validations_ajoutees(ctx.racine, base, ctx.tete):
        # Un test ne précède jamais sa réponse (`tests.attendus` le refuse),
        # ni une clé des garde-fous (`cliquet.garde-fous`) : ils se mesurent
        # sur la plage pas encore poussée, et un test changé plus tôt sur la
        # branche, sous une validation antérieure, ne compte pas (la revue de
        # B-0142). Seul un fichier protégé se mesure sur la branche entière
        # (D-0071).
        nommes = _tests_nommes(ctx, d.texte, base) + _cles_nommees(ctx, d.texte, base) \
            + _fichiers_nommes(ctx, d.texte)
        if not nommes or any(change for _, change in nommes):
            continue
        noms = [n for n, _ in nommes]
        r.avertir("demandes.reponse-seule", trad(
            "réponse `valider` de {id}, pas encore poussée, sans le changement qu'elle autorise : la branche ne "
            "change encore rien de ce qu'elle nomme ({liste}). Poussée seule, elle ne couvrira pas ce changement : "
            "la CI d'un push, et le hook avant push, ne comptent que les validations de leur plage. La commiter et "
            "la pousser avec lui, dans le même push", id=d.id or d.chemin,
            liste=", ".join(f"`{n}`" for n in noms[:5]) + (" …" if len(noms) > 5 else "")),
            d.chemin_reponse or d.chemin)


def _tests_nommes(ctx, texte: str, depuis: str | None = None) -> list[tuple[str, bool]]:
    """Les tests que le texte nomme en mot entier, comme `tests.attendus`
    les reconnaît, et les fichiers de cas qu'il cite, chacun avec un
    booléen : a-t-il changé depuis `depuis` (par défaut, la base de la
    branche) ?"""
    from collections import defaultdict

    from socle import checks_tests as controles_tests, tests_reader as tests_lecture

    if depuis:
        changes = set(outils.fichiers_changes(ctx.racine, depuis, ctx.tete))
        fichiers_avant = outils.fichiers_a(ctx.racine, depuis)

        def lire_avant(vue, c):
            return outils.lire_a(ctx.racine, depuis, c)
    else:
        changes = set(ctx.changes)
        fichiers_avant = None

        def lire_avant(vue, c):
            return vue.lire_base(c)
    res: dict[str, bool] = {}

    def forme(f) -> str:
        return re.sub(r"\s+", " ", "\n".join([*f.attributs, f.entete, f.corps]))

    for a in ctx.projet.adaptateurs:
        vue = ctx.pour(a)
        cfg = controles_tests.cfg_tests(vue.projet)
        if cfg is None:
            continue

        def nommes(texte_fichier: str | None, chemin: str) -> dict[str, list[str]]:
            par_nom = defaultdict(list)
            for f in tests_lecture.extraire(texte_fichier or "", chemin, cfg) if texte_fichier else []:
                if f.est_test and controles_tests._nomme(texte, f.nom):
                    par_nom[f.nom].append(forme(f))
            return par_nom

        apres = controles_tests.fichiers_tests(vue, vue.fichiers)
        for c in apres:
            maintenant = nommes(vue.lire(c), c)
            avant = nommes(lire_avant(vue, c), c) if c in changes else maintenant
            for nom in set(maintenant) | set(avant):
                res[nom] = res.get(nom, False) or sorted(maintenant.get(nom, [])) != sorted(avant.get(nom, []))
        base_vue = vue.fichiers_base if fichiers_avant is None else vue.projet.hors_tiers(fichiers_avant)
        for c in controles_tests.fichiers_tests(vue, base_vue):
            if c in changes and c not in apres:
                for nom in nommes(lire_avant(vue, c), c):
                    res[nom] = True  # le fichier de tests est parti, et le test avec lui
    motifs = ctx.projet.gf("tests", "case_paths", defaut=[]) or []
    avant = set(ctx.fichiers_base) if fichiers_avant is None else set(fichiers_avant)
    for c in outils.filtrer(sorted(set(ctx.fichiers) | avant), motifs) if motifs else []:
        if controles_tests._nomme(texte, c):
            res[c] = c in changes
    return sorted(res.items())


def _cles_nommees(ctx, texte: str, depuis: str) -> list[tuple[str, bool]]:
    """Les clés des garde-fous que le texte cite, comme `cliquet.garde-fous`
    les reconnaît : la clé citable, en toutes lettres dans la demande
    (D-0040) ; et pour chacune, a-t-elle changé depuis `depuis` ? Les
    candidates : les clés des garde-fous avant et après, celles qui ont une
    valeur par défaut, et celles que les règles du cliquet nomment sans
    motif. Des garde-fous illisibles ne nomment rien : d'autres contrôles le
    disent."""
    import json
    import tomllib

    from socle import checks_ratchet as cliquet

    chemin = ctx.projet.chemins.garde_fous
    try:
        avant = config.charger_toml(ctx.racine, chemin, depuis)
        apres = config.lire_toml(ctx.lire(chemin))
    except tomllib.TOMLDecodeError:
        return []

    def valeurs(gf: dict) -> dict[str, object]:
        plats = cliquet.aplatir(gf)
        for c, defaut in cliquet.DEFAUTS.items():
            plats.setdefault(c, defaut)
        res = {cliquet._cle(c): v for c, v in plats.items() if cliquet._regle(c) != "libre"}
        for ligne in gf.get("docmap", []):
            for g in ligne.get("code", []):
                res.setdefault(f"docmap {json.dumps(g, ensure_ascii=False)}", []).append(sorted(ligne.get("docs", [])))
        for v in gf.get("values", []):
            res[f"values {json.dumps(v.get('name'), ensure_ascii=False)}"] = v
        return res

    va, vb = valeurs(avant), valeurs(apres)
    sans_motif = {cliquet._cle(m) for m, sens in cliquet.REGLES
                  if sens != "libre" and all(re.fullmatch(r"[A-Za-z0-9_-]+", c) for c in m)}
    return sorted((k, va.get(k, cliquet.ABSENT) != vb.get(k, cliquet.ABSENT))
                  for k in set(va) | set(vb) | sans_motif if k in texte)


# Ce qu'un chemin de fichier ne porte pas : un motif, un lien Markdown.
_PAS_UN_CHEMIN = re.compile(r"[*?\[\]()<>]")


def _fichiers_nommes(ctx, texte: str) -> list[tuple[str, bool]]:
    """Les fichiers protégés que le texte cite avec une empreinte sur la
    même ligne, comme une demande qui approuve un changement les cite, et
    pour chacun : la branche l'a-t-elle changé depuis sa base ? Les
    réponses humaines, que `protege.fichiers` ne juge pas, n'en sont pas."""
    motifs = sorted(set(ctx.projet.chemins_proteges())
                    | set(ctx.projet_base.chemins_proteges() if ctx.projet_base else []))
    changes = set(ctx.changes)
    res: dict[str, bool] = {}
    for ligne in texte.splitlines():
        jetons = [re.sub(r"^[*(]+|[*.,;:)]+$", "", j) for j in ligne.replace("`", " ").split()]
        empreintes = {j for j in jetons if demandes.EMPREINTE_DE_FICHIER.fullmatch(j)
                      or j in demandes.FICHIER_SUPPRIME}
        if not empreintes:
            continue
        for j in jetons:
            if (j and j not in empreintes and not j.endswith("/") and not _PAS_UN_CHEMIN.search(j)
                    and not memoire.est_reponse(j) and outils.correspond(j, motifs)):
                res[j] = j in changes
    return sorted(res.items())


@controle("instructions.source-unique")
def source_unique(ctx, r):
    """Un seul fichier d'instructions fait foi : `AGENTS.md`, que `CLAUDE.md`
    importe en une ligne ; ou, sans `AGENTS.md`, `CLAUDE.md` qui porte la
    section du socle, quand l'installeur l'a gardé parce que le projet le
    nomme."""
    if config.INSTRUCTIONS not in ctx.fichiers:
        if "CLAUDE.md" in ctx.fichiers and config.DEBUT_SOCLE in (ctx.lire("CLAUDE.md") or ""):
            return
        r.erreur("instructions.source-unique", trad("AGENTS.md absent, et CLAUDE.md ne porte pas la section du "
                                                    "socle : aucun fichier d'instructions ne fait foi"))
        return
    if "CLAUDE.md" in ctx.fichiers:
        texte = (ctx.lire("CLAUDE.md") or "").strip()
        if texte != "@AGENTS.md":
            r.erreur("instructions.source-unique", trad("CLAUDE.md doit contenir la seule ligne `@AGENTS.md` "
                                                        "(aucune copie à synchroniser)"), "CLAUDE.md")
