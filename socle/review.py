"""Le dossier de la revue adversariale d'un lot (ADR-0042).

Avant le push qui livre un lot qui change du code, une spécification ou un
test, l'agent le fait relire par un relecteur qui n'a pas son contexte, et
qui cherche à le prendre en défaut. Le moteur ne connaît aucun agent : il
ne lance pas le relecteur, il prépare ce que celui-ci reçoit, et rien
d'autre. La procédure vit côté agent, dans le skill `socle-review`.

La relecture à froid d'une demande (ADR-0046) procède de même : un lecteur
qui n'a que son texte, dans le rôle de l'humain qui revient sur le projet
après des semaines ; le skill `socle-request` dit quand.

Un lot en cours garde l'historique de ses passes dans sa section
« Revues » (ADR-0084, ADR-0100) : `socle review` y écrit chaque passe, sa
date et les commits relus ; l'agent y consigne les bloquants de chacune.
Aucun recul n'est exigé, ni avant une passe ni à la clôture.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import date

from socle import config, language as langue, memory as memoire, utils as outils
from socle.messages import a_traduire, trad

# Au-delà, le diff se tronque, et le dossier le dit : un relecteur qui reçoit
# un diff énorme le survole.
PLAFOND_DIFF = 60_000
# Au-delà, le dossier ne donne que le chemin du fichier qu'approuve une
# décision de séance, que le relecteur lit dans le dépôt (B-0286) : 20 000
# octets, un tiers du plafond du diff, tiennent un document de proposition
# entier (une page de spécification en fait souvent la moitié) sans noyer le
# diff.
PLAFOND_SUJET = 20_000


def _amont(racine) -> str:
    """La branche distante de la branche courante, `""` sans elle."""
    return outils.git(racine, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                      check=False).strip()


def base_du_lot(racine) -> str | None:
    """Ce que le lot change se mesure depuis la branche distante de la
    branche courante, ce qu'elle n'a pas encore poussé ; sans branche
    distante, depuis la branche par défaut."""
    return _amont(racine) or outils.branche_par_defaut(racine)


class ReferenceRefusee(ValueError):
    """Une base ou un `--since` qui ne mesure pas le lot (ADR-0081) : le
    dossier ne se fait pas, au lieu d'un dossier vide ou étranger."""


class CourtRefuse(ValueError):
    """Un dossier court demandé pour un lot qui touche un garde-fou
    (B-0288) : son relecteur doit pouvoir lire au-delà du diff, et le
    dossier complet le lui dit. Rien ne s'écrit ni ne se relit."""


class PasseRefusee(ValueError):
    """Une passe de revue d'un lot qu'on ne sait pas désigner (ADR-0084) :
    plusieurs lots en cours, ou un lot nommé qui n'est pas un lot ouvert.
    Rien ne s'écrit ni ne se relit."""


def debut_du_lot(racine, base: str) -> str | None:
    """Le commit d'où se mesure le lot : l'ancêtre commun de `base` et de
    HEAD (ADR-0081). Une base qui a avancé sans la branche n'apporte ainsi
    au lot ni ses changements ni ses sujets. `None` sans ancêtre commun."""
    return outils.git(racine, "merge-base", base, "HEAD", check=False).strip() or None


def _debut(racine, base: str) -> str:
    """L'ancêtre commun de `base` et de HEAD ; `base` lui-même sans lui,
    dont l'arbre que rend `sans_la_fusion`, déjà l'origine du lot."""
    return debut_du_lot(racine, base) or base


def sans_la_fusion(projet: config.Projet, debut: str) -> tuple[str, str | None]:
    """D'où se mesurent le diff et les sujets du lot, et la note qui le
    dit : `debut` ; ou, si la branche a fusionné la branche par défaut
    depuis `debut`, l'arbre de cette fusion refaite sur `debut` (`git
    merge-tree`), dont HEAD ne diffère que par ce que le lot change
    lui-même (B-0241). Une fusion qui ne se refait pas sans conflit, ou un
    git sans `merge-tree --write-tree` (2.38), laisse `debut`, et la note
    dit que le dossier montre aussi ce qu'elle a apporté."""
    racine = projet.racine
    defaut = outils.branche_par_defaut(racine)
    if not defaut or not outils.rev_existe(racine, defaut):
        return debut, None
    fusionne = outils.git(racine, "merge-base", defaut, "HEAD", check=False).strip()
    if not fusionne or outils.git_reussit(racine, "merge-base", "--is-ancestor", fusionne, debut):
        return debut, None
    # Sur la lignée des premiers parents de la branche, ce commit est du
    # lot : la branche par défaut l'a reçu d'elle, en avance rapide.
    lignee = outils.git(racine, "rev-list", "--first-parent", f"{debut}..HEAD", check=False).split()
    if fusionne in lignee:
        return debut, None
    r = subprocess.run(["git", "merge-tree", "--write-tree", debut, fusionne], cwd=racine, capture_output=True,
                       text=True)
    arbre = r.stdout.split("\n", 1)[0].strip() if r.returncode == 0 else ""
    if not arbre:
        return debut, trad("(la branche a fusionné {defaut} depuis {debut}, et cette fusion ne se refait pas sans "
                           "conflit, ou ce git ne sait pas la refaire (`git merge-tree --write-tree`, git 2.38) : le "
                           "dossier montre aussi ce qu'elle a apporté jusqu'à {fusionne}, qui n'est pas du lot)",
                           defaut=defaut, debut=_court(projet, debut), fusionne=_court(projet, fusionne))
    return arbre, trad("(la branche a fusionné {defaut} depuis {debut} : le lot se mesure sans ce que cette fusion a "
                       "apporté, depuis l'arbre {arbre}, {debut} fusionné avec {fusionne})",
                       defaut=defaut, debut=_court(projet, debut), fusionne=_court(projet, fusionne),
                       arbre=arbre[:12])


def _hors_memoire(projet: config.Projet) -> list[str]:
    return ["--", ".", f":(exclude){projet.chemins.memoire}"]


def _commits_hors_memoire(projet: config.Projet, depuis: str, jusqua: str) -> int:
    """Les commits de `depuis..jusqua` qui changent autre chose que la mémoire."""
    sortie = outils.git(projet.racine, "rev-list", "--count", f"{depuis}..{jusqua}", *_hors_memoire(projet),
                        check=False).strip()
    return int(sortie) if sortie.isdigit() else 0


def refus_des_references(projet: config.Projet, base: str | None, depuis: str | None) -> str | None:
    """Pourquoi `--base` ou `--since` ne mesurent pas le lot, `None` s'ils
    le mesurent (ADR-0081) : une référence inconnue, un `--since` qui n'est
    pas un ancêtre de HEAD."""
    for option, ref in (("--base", base), ("--since", depuis)):
        if ref and not outils.rev_existe(projet.racine, ref):
            return trad("{option} {ref} : aucune branche, étiquette ni commit de ce nom dans ce dépôt ; rien "
                        "n'est relu", option=option, ref=ref)
    if depuis and not outils.git_reussit(projet.racine, "merge-base", "--is-ancestor", depuis, "HEAD"):
        return trad("--since {ref} n'est pas un ancêtre de HEAD : une seconde revue se mesure depuis le commit relu "
                    "par la première, que la branche contient ; rien n'est relu", ref=depuis)
    return None


def contient_le_lot(projet: config.Projet, base: str, depuis: str | None = None) -> bool:
    """`base` contient déjà le lot (ADR-0075) : avec `depuis`, le commit relu
    par la première revue y est déjà ; sans, rien n'en diffère hors de la
    mémoire depuis leur ancêtre commun (ADR-0081), ni un commit, ni
    l'arbre : un commit que `base` a reçu d'ailleurs n'y change rien."""
    if depuis:
        return outils.git_reussit(projet.racine, "merge-base", "--is-ancestor", depuis, base)
    return outils.git_reussit(projet.racine, "diff", "--quiet", _debut(projet.racine, base), *_hors_memoire(projet))


def base_par_defaut(projet: config.Projet, depuis: str | None = None) -> tuple[str | None, str | None]:
    """La base du lot sans `--base`, et ce que le dossier en dit (ADR-0075,
    ADR-0081). Une branche distante qui contient déjà le lot, poussé avant
    sa revue, n'y laisse rien : il se mesure alors depuis l'ancêtre commun
    de HEAD et de la branche par défaut. Si celui-ci le contient aussi, ou
    qu'il n'y en a pas, la base reste, et la note dit pourquoi le dossier
    est vide, et quoi lancer. Une branche distante qui porte déjà des
    commits du lot, ou d'un lot d'avant, le dit aussi."""
    racine = projet.racine
    base = base_du_lot(racine)
    amont = _amont(racine)
    if not base or base != amont:
        return base, None
    defaut = outils.branche_par_defaut(racine) or base
    devinee = outils.branche_par_defaut_devinee(racine)
    commun = None if devinee else outils.base_de_travail(racine)
    seconde = f" --since {depuis}" if depuis else ""
    # Une branche distante restée en arrière de la branche par défaut, que
    # la branche a reprise depuis son dernier push (une fusion par
    # écrasement, son image locale gardée) : son ancêtre commun avec HEAD
    # précède celui de la branche par défaut, et ramènerait le lot fusionné.
    debut_amont = debut_du_lot(racine, base)
    if commun and debut_amont and debut_amont != commun and outils.git_reussit(
            racine, "merge-base", "--is-ancestor", debut_amont, commun):
        return commun, trad("(la branche distante {amont} est restée en arrière de {defaut}, que la branche a reprise "
                            "depuis son dernier push, après une fusion par écrasement peut-être : le lot se mesure "
                            "depuis {commun}, l'ancêtre commun de HEAD et de {defaut} ; s'il commence plus tard, "
                            "`socle review --base <le commit d'avant le lot>{seconde}`)",
                            amont=base, defaut=defaut, commun=commun, seconde=seconde)
    if not contient_le_lot(projet, base, depuis):
        n = _commits_hors_memoire(projet, commun, _debut(racine, base)) if commun else 0
        if not n:
            return base, None
        return base, trad("(la branche distante {amont} porte déjà {n} commit(s) hors de la mémoire depuis {commun}, "
                          "l'ancêtre commun de HEAD et de {defaut}, que ce dossier ne montre pas : si le lot en "
                          "comprend, `socle review --base <le commit d'avant le lot>{seconde}`)",
                          amont=base, n=n, commun=commun, defaut=defaut, seconde=seconde)
    if devinee:
        return base, trad("(la branche distante {amont} contient déjà le lot, et ce clone ne connaît pas la branche "
                          "par défaut : ni `origin/HEAD`, ni `main`, ni `master`. Un lot déjà poussé se relit depuis "
                          "le commit d'avant lui : `socle review --base <ce commit>{seconde}`)",
                          amont=base, seconde=seconde)
    if not commun:
        return base, trad("(la branche distante {amont} contient déjà le lot, et HEAD n'a pas d'ancêtre commun avec la "
                          "branche par défaut {defaut} dans ce clone, superficiel peut-être (`git fetch --unshallow`). "
                          "Un lot déjà poussé se relit depuis le commit d'avant lui : `socle review --base <ce "
                          "commit>{seconde}`)", amont=base, defaut=defaut, seconde=seconde)
    if not contient_le_lot(projet, commun, depuis):
        return commun, trad("(la branche distante {amont} contient déjà le lot : il se mesure depuis {commun}, "
                            "l'ancêtre commun de HEAD et de {defaut}, sur {n} commit(s) hors de la mémoire ; s'il "
                            "commence plus tard, `socle review --base <le commit d'avant le lot>{seconde}`)",
                            amont=base, commun=commun, defaut=defaut, seconde=seconde,
                            n=_commits_hors_memoire(projet, commun, "HEAD"))
    return base, trad("(la branche distante {amont} contient déjà le lot, et la branche par défaut {defaut} aussi : "
                      "rien à relire depuis elles. Un lot déjà poussé se relit depuis le commit d'avant lui : "
                      "`socle review --base <ce commit>{seconde}`)", amont=base, defaut=defaut, seconde=seconde)


def _diff(projet: config.Projet, base: str) -> tuple[str, list[str]]:
    """Le diff du lot depuis l'ancêtre commun de `base` et de HEAD
    (ADR-0081), l'arbre compris, la mémoire mise à part : elle se donne par
    ses sujets, plus bas."""
    debut = _debut(projet.racine, base)
    diff = outils.git(projet.racine, "diff", debut, *_hors_memoire(projet), check=False)
    fichiers = outils.git(projet.racine, "diff", "--name-only", debut, *_hors_memoire(projet), check=False).split()
    return diff, fichiers


def sujets_du_lot(projet: config.Projet, base: str) -> tuple[list, list]:
    """Les sujets du backlog que le lot touche (ADR-0073), mesurés depuis
    l'ancêtre commun de `base` et de HEAD (ADR-0081) : ceux qu'il sert,
    dont le « Fait quand » est la barre du relecteur, qui existaient à son
    début et dont il change le statut ou le « Fait quand », ou qu'il ouvre
    et clôt ; puis ceux qu'il ouvre sans les clore, ce qu'il renvoie au
    backlog. Un sujet dont il ne change que le reste (un `après`, un
    constat ajouté, sa place parmi les clos) n'est ni l'un ni l'autre."""
    debut = _debut(projet.racine, base)
    touches = set(outils.git(projet.racine, "diff", "--name-only", debut, "--", projet.chemins.backlog,
                             check=False).split())
    avant = memoire.Memoire.charger(projet.racine, debut)
    mem = memoire.Memoire.charger(projet.racine)
    servis, ouverts = [], []
    for e in mem.entrees(memoire.BACKLOG):
        if e.fichier not in touches or memoire.est_prive(e.fichier):
            continue
        # Sous son numéro, ou sous l'ancien d'une entrée renumérotée (ADR-0083).
        ancien = next((avant.entree(i) for i in (e.id, *e.anciens) if avant.entree(i)), None)
        if ancien is None:
            (servis if e.statut in memoire.BACKLOG_CLOS else ouverts).append(e)
        elif e.statut != ancien.statut or _cases(e) != _cases(ancien):
            servis.append(e)
    return servis, ouverts


def _cases(e) -> list:
    """Les critères d'une entrée, dans ses deux sections possibles : « Fait
    quand » et « Satisfait quand » (ADR-0083) ; une section renommée ne
    change pas la barre."""
    return [x for s in (memoire.SECTION_FAIT_QUAND, memoire.SECTION_SATISFAIT_QUAND) for x in memoire.criteres(e, s)]


def messages_depuis(racine, depuis: str) -> list[str]:
    """Les messages des commits depuis `depuis`, du plus ancien au plus
    récent, sans leurs lignes de fin (`Co-Authored-By:`, `Socle-Hooks:`…) :
    ce que la correction dit corriger. Seul le dernier paragraphe se retire,
    s'il n'est fait que de lignes de fin, et jamais le titre : un titre
    `fix: …` ou `Corrige: B-NNNN` reste. Sur la lignée des premiers parents
    de la branche : ceux qu'une fusion de la branche par défaut a apportés
    n'y sont pas, son commit de fusion y est (B-0241)."""
    brut = outils.git(racine, "log", "--reverse", "--first-parent", "--format=%x00%B", f"{depuis}..HEAD",
                      check=False)
    res = []
    for message in brut.split("\0"):
        paragraphes = [p.strip("\n") for p in re.split(r"\n[ \t]*\n", message.strip()) if p.strip()]
        if len(paragraphes) > 1 and all(re.match(r"^[A-Za-z][\w-]*: \S", ligne)
                                        for ligne in paragraphes[-1].splitlines()):
            paragraphes.pop()
        if paragraphes:
            res.append("\n\n".join(paragraphes))
    return res


def decisions_ecrites(projet: config.Projet, base: str) -> list:
    """Les décisions et les demandes que le lot ajoute à la mémoire : la
    spécification ou le modèle de menace écrits avant son code, que ses
    sujets, plus anciens, ne citent pas (ADR-0073), depuis l'ancêtre commun
    de `base` et de HEAD (ADR-0081)."""
    ajoutes = set(outils.git(projet.racine, "diff", "--name-only", "--diff-filter=A", _debut(projet.racine, base),
                             "--", projet.chemins.memoire, check=False).split())
    mem = memoire.Memoire.charger(projet.racine)
    return [e for e in mem.entrees() if e.fichier in ajoutes and e.id.startswith(("ADR-", "D-"))
            and not memoire.est_prive(e.fichier)]


def decisions_citees(projet: config.Projet, sujets: list) -> list:
    """Les décisions et les demandes que ces sujets citent, en entier."""
    mem = memoire.Memoire.charger(projet.racine)
    vus, res = set(), []
    for s in sujets:
        for ident, _ in memoire.mentions(s.texte):
            if ident in vus or not ident.startswith(("ADR-", "D-")):
                continue
            vus.add(ident)
            e = mem.entree(ident)
            if e is not None and not memoire.est_prive(e.fichier):
                res.append(e)
    return res


def contenus_approuves(projet: config.Projet, decisions: list, plafond: int = PLAFOND_SUJET,
                       debut: str | None = None) -> list[str]:
    """Ce qu'approuvent les décisions de séance de `decisions` qui désignent
    un fichier, leur champ `sujet` (B-0286) : sous un titre qui nomme la
    décision et le chemin, le texte du fichier tel qu'il était au début du
    lot (`debut`), la version que l'humain a approuvée, que le lot peut avoir
    changée, ce que le dossier dit alors ; dans l'arbre de travail si le lot
    le crée ou sans `debut`. Son chemin seul au-delà de `plafond` octets, ou
    s'il n'existe pas. Un fichier privé, jugé sur son chemin normalisé
    quelle qu'en soit l'écriture, ou hors du dépôt, ne se donne pas. Vide
    sans aucune. Relevé par la revue de L-0018 : lu dans l'arbre, le
    dossier donnait pour barre la version que le lot avait modifiée."""
    from socle import requests as demandes

    voulues = [e.id for e in decisions if e.id.startswith("D-")]
    if not voulues:
        return []
    par_id = {d.entree.id: d for d in demandes.toutes(projet.racine) if d.entree is not None}
    racine = projet.racine.resolve()
    lignes = []
    for ident in voulues:
        d = par_id.get(ident)
        if d is None or not d.seance or not d.sujet or not d.sujet[0]:
            continue
        chemin, empreinte = d.sujet
        fichier = (projet.racine / chemin).resolve()
        # Le chemin normalisé, non le brut : `./memory/private/…` est privé
        # comme `memory/private/…` (B-0297).
        if not fichier.is_relative_to(racine) or memoire.est_prive(fichier.relative_to(racine).as_posix()):
            continue
        lignes += [f"### {ident} — `{chemin}`" + (f" (@{empreinte})" if empreinte else ""), ""]
        actuel = fichier.read_text(encoding="utf-8", errors="replace") if fichier.is_file() else None
        avant = outils.lire_a(projet.racine, debut, chemin) if debut else None
        texte = avant if avant is not None else actuel
        if avant is not None and actuel != avant:
            lignes += [trad("(le lot change `{chemin}` : voici sa version d'avant le lot, celle qu'approuve la "
                            "décision ; le diff montre le changement)", chemin=chemin), ""]
        if texte is None:
            lignes += [trad("(`{chemin}` : introuvable dans l'arbre de travail)", chemin=chemin), ""]
        elif len(texte.encode("utf-8")) > plafond:
            lignes += [trad("(`{chemin}` : {n} octets, au-delà de la borne du dossier ({borne}) : le lire dans le "
                            "dépôt)", chemin=chemin, n=len(texte.encode("utf-8")), borne=plafond), ""]
        else:
            # Une clôture plus longue que toute suite d'accents graves du
            # texte : un document Markdown garde ses propres blocs.
            cloture = "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", texte)), default=0))
            lignes += [cloture, texte.rstrip("\n"), cloture, ""]
    if lignes:
        lignes = [trad("## Ce qu'approuvent les décisions de séance qu'elles citent : ta barre, comme leurs "
                       "critères"), ""] + lignes
    return lignes


def dossier_demande(projet: config.Projet, ident: str) -> str | None:
    """Ce que reçoit le lecteur de la relecture à froid d'une demande
    (ADR-0046) : la consigne, puis le texte de la demande, rien d'autre.
    `None` si aucune demande ne porte cet identifiant."""
    from socle import requests as demandes

    trouvees = [d for d in demandes.toutes(projet.racine) if d.entree is not None and d.entree.id == ident]
    if not trouvees:
        return None
    consigne = trad(
        "Tu es l'humain à qui cette demande s'adresse. Tu n'as pas ouvert ce projet depuis trois semaines : tu ne "
        "te souviens ni de ce qu'il fait en détail, ni du travail en cours, ni de ce que tu as décidé avant. Tu "
        "n'as que le texte ci-dessous : n'ouvre aucun lien, ne lis aucun fichier, ne cherche rien. Lis la "
        "demande, puis rends, sans rien modifier nulle part :\n\n"
        "1. Le projet et le but du travail en cours, en tes mots, tels que la demande te les apprend ; « je ne "
        "sais pas » pour ce qu'elle ne dit pas.\n"
        "2. La décision qu'on te demande, et ce que change chacune des réponses possibles.\n"
        "3. Chaque mot, nom, sigle ou renvoi que le texte emploie sans te l'expliquer, avec la phrase où il "
        "apparaît.\n"
        "4. Ce qu'il te manquerait pour décider sans aller chercher ailleurs.\n\n"
        "Ne juge pas si la décision est bonne : seulement si le texte seul te permet de la prendre.")
    return "\n".join([trad("# Relecture à froid d'une demande"), "", consigne, "", trad("## La demande"), "",
                      trouvees[0].texte.strip(), ""])


# La consigne du relecteur (ADR-0042, ADR-0044, ADR-0073), en trois parties :
# son rôle, sa barre, les classes de ses constats (D-0112, D-0116).
CONSIGNE_ROLE = a_traduire(
    "Tu relis le lot de travail d'un autre agent, sans sa conversation ni son raisonnement : tu as ce dossier, et "
    "tu peux lire le dépôt pour vérifier un constat, mais tu ne modifies rien. Pour éprouver une commande "
    "(l'installeur, un script), crée d'abord un dossier temporaire hors du dépôt (`mktemp -d`), et n'écris que "
    "là : chaque commande qui écrit y vise par son chemin absolu, jamais par le dossier courant, écrit en toutes "
    "lettres tel que `mktemp -d` l'a rendu, jamais par une variable, qui ne survit pas d'un appel à l'autre. Ton "
    "rôle est de le prendre en défaut.")
CONSIGNE_BARRE = a_traduire(
    "Ta barre est celle des entrées du backlog que sert le lot, plus bas : leurs critères (« Fait quand » d'une "
    "tâche, « Satisfait quand » d'un besoin), les décisions qu'elles citent, et, pour une entrée qui pose ou "
    "change un garde-fou, son modèle de menace, ce que le garde-fou arrête et ce qu'il laisse passer. Cherche ce qui casse (un cas limite, une erreur de logique, une régression), ce "
    "qu'aucun test ne prouve, et ce qui contredit un critère ou une décision. Ne juge ni le style, ni ce que les "
    "contrôles automatiques jugent déjà : la forme de la mémoire, les liens, la présence des tests.")
CONSIGNE_CLASSES = a_traduire(
    "Classe chaque constat. **Bloquant** : il contredit un critère coché ou une décision citée, fait régresser "
    "ce qui marchait avant le lot, perd des données, ou contourne un garde-fou dans son modèle de menace ; un "
    "garde-fou que le lot pose ou change sans modèle de menace écrit est lui-même un constat bloquant. **Pour le "
    "backlog** : un constat qui ne bloque pas, seulement s'il est important et a été vu en usage réel (une "
    "session, une CI, un message de l'humain le montre), ou si son effet serait irréversible (une perte de "
    "données, un push sur la branche par défaut, une suppression) ; un critère que le lot ne coche pas, un "
    "défaut voisin, une amélioration, jugés de même. **Écarté** : tout autre constat, dont un cas imaginé et "
    "jamais vu, une légère gêne que l'agent règle lui-même, un contournement hors du modèle de menace, et un "
    "constat infondé ; en cas de doute, il s'écarte, et revient s'il est vu en usage réel. Seuls les bloquants se "
    "corrigent dans le lot. Rends trois listes numérotées, « Bloquants », « Pour le backlog » "
    "puis « Écartés », chaque constat avec son fichier et sa ligne, ce qui casse et comment le vérifier, pour "
    "un bloquant ce qu'il contredit, pour un écarté pourquoi ; ou « aucun constat ».")
CONSIGNE_SECONDE = a_traduire(
    "Seconde revue : ce diff corrige des constats bloquants d'une première revue, que disent les messages de ses "
    "commits ci-dessous ; le reste du lot a déjà été relu. Ne juge que cette correction : un bloquant mal "
    "corrigé, ce qu'elle fait régresser, contre les mêmes entrées.")


# Une case d'une tâche qui livre une demande, un relevé ou une entrée de
# la mémoire se juge par ce qu'elle produit (ADR-0088, T-0087), dans le
# dossier complet comme dans le dossier court.
CONSIGNE_CASES = a_traduire(
    "Une case d'une tâche se vérifie par un test, sauf celle dont le livrable est une demande posée, un relevé "
    "écrit (le compte rendu d'une mesure ou d'un essai) ou une entrée de la mémoire récrite : elle se vérifie par "
    "ce qu'elle produit, que la case nomme (la demande, et la réponse de l'humain consignée au journal une fois "
    "donnée ; le fichier du relevé ; ce qu'en montre `socle show` ou `socle roadmap`). Juge alors que ce produit "
    "existe et dit ce que la case promet ; l'absence d'un test n'y est pas un constat.")


# Le dossier court d'un petit lot (B-0288) : son relecteur juge le diff et
# les fichiers qu'il touche, contre les critères des tâches du lot, sans
# explorer au-delà. Le skill `socle-review` dit quand le donner.
CONSIGNE_COURTE = a_traduire(
    "Tu relis un petit lot de travail d'un autre agent, sans sa conversation ni son raisonnement : tu as ce "
    "dossier, son diff et les critères des tâches qu'il sert. Juge le diff et les fichiers qu'il touche, que tu "
    "peux lire en entier pour vérifier un constat ; n'explore pas au-delà, ne lance rien, ne modifie rien. Ton "
    "rôle est de le prendre en défaut : cherche ce qui casse (un cas limite, une erreur de logique, une "
    "régression), ce qu'aucun test ne prouve, et ce qui contredit un critère. Ne juge ni le style, ni ce que "
    "les contrôles automatiques jugent déjà : la forme de la mémoire, les liens, la présence des tests.")


def garde_fous_touches(projet: config.Projet, fichiers: list[str]) -> list[str]:
    """Les fichiers de `fichiers` qui sont un garde-fou (B-0288) : la
    politique et les garde-fous eux-mêmes, les chemins que la politique
    protège (`chemins_proteges`, ceux que le hook de l'agent refuse
    d'écrire) et ceux que les garde-fous déclarent comme l'outillage (les
    hooks, la CI : `[tooling] paths`, que le contrôle de la documentation
    lit). Un lot qui en touche un garde la revue complète."""
    from socle.checks_docs import MOTIFS_OUTILLAGE_DEFAUT

    motifs = [projet.chemins.politique, projet.chemins.garde_fous, *projet.chemins_proteges(),
              *projet.gf("tooling", "paths", defaut=MOTIFS_OUTILLAGE_DEFAUT)]
    return [f for f in fichiers if outils.correspond(f, motifs)]


def _criteres_du_lot(servis: list) -> list[str]:
    """Les critères des entrées que sert le lot, sous leur titre : la barre
    du dossier court, sans le reste des entrées."""
    lignes = []
    for s in servis:
        lignes += [f"### {s.id} — {s.titre}", ""]
        lignes += [f"- [{'x' if coche else ' '}] {texte}" for coche, texte in _cases(s)] or [
            trad("(aucun critère)")]
        lignes.append("")
    return lignes


def _mesurer(projet: config.Projet, base: str | None, depuis: str | None) -> tuple[str | None, str | None,
                                                                                    str | None]:
    """La base du lot, la note qui en parle, et le commit d'où il se
    mesure (ADR-0075, ADR-0081) ; `(None, note, None)` sans base connue.
    Une référence qui ne mesure pas le lot lève `ReferenceRefusee`."""
    refus = refus_des_references(projet, base, depuis)
    if refus:
        raise ReferenceRefusee(refus)
    note = None
    if not base:
        base, note = base_par_defaut(projet, depuis)
    if not base:
        return None, note, None
    debut = debut_du_lot(projet.racine, base)
    if not debut:
        raise ReferenceRefusee(trad("aucun ancêtre commun entre HEAD et {base} dans ce clone : rien ne mesure le lot. "
                                    "Un clone superficiel s'approfondit par `git fetch --unshallow` ; sinon, `socle "
                                    "review --base <le commit d'avant le lot>`", base=base))
    return base, note, debut


def dossier(projet: config.Projet, base: str | None = None, plafond: int = PLAFOND_DIFF,
            depuis: str | None = None, court: bool = False) -> str:
    """Ce que reçoit le relecteur, en plus du dépôt qu'il peut lire : la
    consigne, le diff du lot, les sujets du lot, les décisions qu'il écrit
    et celles que citent ses sujets et ses décisions, une fois chacune
    (ADR-0073). Avec `depuis`, le dossier d'une seconde revue : le
    diff depuis ce commit, les messages de ses commits, et toujours les
    sujets du lot entier, depuis `base`. Sans `base`, celle de
    `base_par_defaut` (ADR-0075). Le lot se mesure depuis l'ancêtre commun
    de la base et de HEAD ; une référence qui ne le mesure pas lève
    `ReferenceRefusee` (ADR-0081). Chaque passe d'un lot reçoit le même
    dossier, sans les causes des passes d'avant (ADR-0100). `court` : le
    dossier court d'un petit lot
    (B-0288), la consigne de ne juger que le diff et les fichiers touchés,
    le diff et les critères des tâches du lot, sans le reste de leurs
    entrées ni les décisions qu'elles citent ; un lot qui touche un
    garde-fou (`garde_fous_touches`, mesuré sur tout le lot) lève
    `CourtRefuse`."""
    base, note, debut = _mesurer(projet, base, depuis)
    # Le diff et les sujets du lot, sans ce qu'une fusion de la branche par
    # défaut a apporté depuis son début (B-0241) ; ses passes gardent `debut`.
    origine_du_lot, note_fusion = sans_la_fusion(projet, debut) if debut else (debut, None)
    if court and base:
        touches = garde_fous_touches(projet, _diff(projet, origine_du_lot)[1])
        if touches:
            raise CourtRefuse(trad(
                "le lot touche un garde-fou : {chemins}. Son relecteur doit pouvoir lire au-delà du diff : pas de "
                "dossier court, `socle review` sans `--short` donne le dossier complet",
                chemins=", ".join(touches[:PLAFOND_LISTE]) + (" …" if len(touches) > PLAFOND_LISTE else "")))
    if court:
        lignes = [trad("# Revue adversariale d'un petit lot, le dossier court"), "", trad(CONSIGNE_COURTE), "", trad(CONSIGNE_CASES), "",
                  trad(CONSIGNE_CLASSES), ""]
    else:
        lignes = [trad("# Revue adversariale d'un lot"), "", trad(CONSIGNE_ROLE), "", trad(CONSIGNE_BARRE), "", trad(CONSIGNE_CASES), "",
                  trad(CONSIGNE_CLASSES), ""]
    if not base:
        lignes.append(trad("(aucune base connue : ni branche distante, ni branche par défaut ; rien à relire)"))
        return "\n".join(lignes) + "\n"
    # La base elle-même quand elle est l'ancêtre commun : son nom se lit
    # mieux que son SHA.
    tel_quel = outils.git(projet.racine, "rev-parse", "--verify", "-q", f"{base}^{{commit}}",
                          check=False).strip() == debut
    origine = base if tel_quel else debut
    if note:
        lignes += [note, ""]
    if note_fusion:
        lignes += [note_fusion, ""]
    if depuis:
        # La correction, sans ce qu'une fusion de la branche par défaut a
        # apporté depuis le commit relu (B-0241).
        origine_correction, note_correction = sans_la_fusion(projet, depuis)
        if note_correction and note_correction != note_fusion:
            lignes += [note_correction, ""]
        lignes += [trad("## Seconde revue"), "", trad(CONSIGNE_SECONDE), ""]
        for message in messages_depuis(projet.racine, depuis):
            lignes += ["```text", message, "```", ""]
        diff, fichiers = _diff(projet, origine_correction)
        origine = origine_correction
        lignes += [trad("## Le diff de la correction ({n} fichier(s), depuis {base})", n=len(fichiers),
                        base=depuis), ""]
    else:
        diff, fichiers = _diff(projet, origine_du_lot)
        if origine_du_lot != debut:
            origine = origine_du_lot
        if tel_quel:
            lignes += [trad("## Le diff du lot ({n} fichier(s), depuis {base})", n=len(fichiers), base=base), ""]
        else:
            lignes += [trad("## Le diff du lot ({n} fichier(s), depuis {commun}, l'ancêtre commun de HEAD et de "
                            "{base})", n=len(fichiers), commun=debut, base=base), ""]
    if not diff.strip():
        lignes.append(trad("(aucun changement hors de la mémoire : rien à relire)"))
    else:
        montre = diff.encode("utf-8")[:plafond].decode("utf-8", errors="ignore")
        lignes += ["```diff", montre.rstrip("\n"), "```"]
        if len(montre) < len(diff):
            lignes.append(trad("(diff tronqué : {n} caractère(s) de plus non montrés ; `git diff {base}` les "
                               "donne)", n=len(diff) - len(montre), base=origine))
    servis, ouverts = sujets_du_lot(projet, origine_du_lot)
    if court:
        lignes += ["", trad("## Les critères des tâches du lot : ta barre"), ""]
        lignes += _criteres_du_lot(servis) or [trad("(aucune entrée du backlog servie)")]
        lignes += contenus_approuves(projet, decisions_citees(projet, servis), debut=origine_du_lot)
        return "\n".join(lignes).rstrip() + "\n"
    if servis:
        lignes += ["", trad("## Les entrées du backlog que sert le lot : leurs critères sont ta barre"), ""]
        for s in servis:
            lignes += [s.texte.strip(), ""]
    if ouverts:
        lignes += ["", trad("## Les entrées que le lot ouvre : ce qu'il renvoie au backlog"), ""]
        lignes += [f"- {s.id} — {s.titre}" for s in ouverts]
    ecrites = decisions_ecrites(projet, origine_du_lot)
    if ecrites:
        lignes += ["", trad("## Les décisions et les demandes que le lot écrit"), ""]
        for e in ecrites:
            lignes += [e.texte.strip(), ""]
    # Celles que citent les entrées du lot, puis celles que citent les
    # décisions qu'il écrit, chacune une fois : la spécification validée
    # qu'une décision du lot applique est la barre du relecteur (B-0273).
    citees = decisions_citees(projet, servis + ecrites)
    decisions = [e for e in citees if e.id not in {d.id for d in ecrites}]
    if decisions:
        lignes += ["", trad("## Les décisions et les demandes qu'elles citent"), ""]
        for e in decisions:
            lignes += [e.texte.strip(), ""]
    approuves = contenus_approuves(projet, citees, debut=origine_du_lot)
    if approuves:
        lignes += [""] + approuves
    return "\n".join(lignes).rstrip() + "\n"


# --------------------------------------------------------------------------
# L'historique des passes d'un lot (D-0124, ADR-0084)
# --------------------------------------------------------------------------

# Au-delà, une liste du refus se coupe, et le dit.
PLAFOND_LISTE = 30


def lot_de_la_revue(projet: config.Projet, nom: str | None = None) -> memoire.Entree | None:
    """Le lot dont `socle review` produit la passe (ADR-0084) : celui que
    `--batch` nomme, ouvert ; sinon le seul lot `en cours` du backlog
    public, `None` s'il n'y en a pas. Plusieurs, ou un nom qui ne désigne
    pas un lot ouvert, lèvent `PasseRefusee`."""
    mem = memoire.Memoire.charger(projet.racine)
    if nom:
        e = mem.resoudre(nom)
        if e is None or not memoire.est_lot(e) or e.basculee or memoire.est_prive(e.fichier):
            raise PasseRefusee(trad("--batch {nom} : aucun lot de ce nom au backlog public ; rien n'est relu",
                                    nom=nom))
        if e.statut in memoire.BACKLOG_CLOS:
            raise PasseRefusee(trad("--batch {nom} : le lot est clos (« {statut} ») ; une passe s'écrit dans un lot "
                                    "ouvert ; rien n'est relu", nom=nom, statut=e.statut))
        return e
    lots = sorted((e for e in mem.entrees("L") if e.statut == "en-cours" and not e.archivee and not e.basculee
                   and not memoire.est_prive(e.fichier)), key=lambda e: e.id)
    if len(lots) > 1:
        raise PasseRefusee(trad("{n} lots sont en cours ({lots}) : `socle review --batch L-NNNN` nomme celui de cette "
                                "revue ; rien n'est relu", n=len(lots), lots=", ".join(e.id for e in lots)))
    return lots[0] if lots else None


def empreinte_de_l_arbre(projet: config.Projet, tete: str) -> str | None:
    """L'empreinte de ce que l'arbre de travail change hors de la mémoire
    depuis `tete`, fichiers suivis modifiés compris, ce que le dossier juge
    en plus des commits ; `None` s'il n'y change rien."""
    diff = outils.git(projet.racine, "diff", "--no-ext-diff", "--no-color", "--no-renames", "--full-index",
                      "--binary", tete, *_hors_memoire(projet), check=False)
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()[:12] if diff else None


def meme_passe(projet: config.Projet, p: memoire.Passe) -> bool:
    """Rien n'a changé hors de la mémoire depuis ce que la passe a relu :
    son commit de tête, et les changements de l'arbre de travail qu'elle a
    relus en plus, par leur empreinte (`Passe.arbre`) ; c'est la même passe,
    dont le dossier se redonne. Relevé par la revue de T-0047 : comparé au
    seul commit de tête, un arbre sale inchangé faisait une passe nouvelle."""
    return bool(p.tete) and outils.rev_existe(projet.racine, p.tete) and \
        empreinte_de_l_arbre(projet, p.tete) == p.arbre


def _court(projet: config.Projet, rev: str) -> str:
    return outils.git(projet.racine, "rev-parse", "--short", rev, check=False).strip() or rev


def ecrire_passe(projet: config.Projet, lot: memoire.Entree, numero: int, debut: str, tete: str, jour: str,
                 arbre: str | None = None) -> str:
    """Ajoute la passe `numero` à la section « Revues » du lot, posée à la
    fin de son entrée si elle n'y est pas : son titre, sa date et ses
    commits, suivis de l'empreinte `arbre` des changements de l'arbre de
    travail qu'elle relit en plus, s'il y en a. Rend le fichier du lot."""
    lg = langue.du_projet(projet)
    mots = {cle: m[lg] for cle, m in langue.REVUES.items()}
    chemin = projet.racine / lot.fichier
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    passe = [f"### {mots['passe']} {numero} — {jour}", "",
             f"{mots['commits']}{' :' if lg == 'fr' else ':'} {debut}..{tete}"
             + (f" + {mots['arbre']} {arbre}" if arbre else "")]
    premiere = lot.ligne - 1
    fin = premiere + len(lot.texte.split("\n"))
    section = next((i for i in range(premiere + 1, fin) if memoire.SECTION_REVUES.match(lignes[i])), None)
    if section is None:
        k, ajout = fin, ["", f"## {mots['revues']}", "", *passe]
    else:
        niveau = len(lignes[section]) - len(lignes[section].lstrip("#"))
        k = next((i for i in range(section + 1, fin) if re.match(r"#{1,%d}\s" % niveau, lignes[i])), fin)
        while k > section + 1 and not lignes[k - 1].strip():
            k -= 1
        ajout = ["", *passe]
    lignes[k:k] = ajout
    outils.ecrire(chemin, "\n".join(lignes))
    return lot.fichier


def relire(projet: config.Projet, base: str | None = None, plafond: int = PLAFOND_DIFF, depuis: str | None = None,
           nom_du_lot: str | None = None, jour: str | None = None, court: bool = False) -> tuple[str, str | None]:
    """Ce que fait `socle review` (ADR-0084, ADR-0100) : le dossier d'une
    passe, et la ligne que la sortie d'erreur en dit. Sans lot en cours, le
    dossier d'avant, sans rien écrire. Avec lui : la même passe se redonne
    tant que rien n'a changé hors de la mémoire depuis son commit de tête ;
    sinon, la suivante s'écrit dans le lot, sans recul exigé de la
    précédente. Un lot qui ne change rien hors de la mémoire n'a pas de
    passe. `court` : le dossier court (B-0288), qu'un lot qui touche
    un garde-fou refuse (`CourtRefuse`) avant que rien ne s'écrive. L'état
    relu est celui de l'arbre de travail : ses fichiers suivis modifiés
    hors de la mémoire comptent, et la passe en garde l'empreinte."""
    lot = lot_de_la_revue(projet, nom_du_lot)
    if lot is None:
        return dossier(projet, base, plafond, depuis, court=court), trad(
            "(aucun lot en cours au backlog : cette passe ne s'écrit dans aucun lot ; `socle review --batch L-NNNN` "
            "nomme le sien)")
    _, _, debut = _mesurer(projet, base, depuis)
    if debut is None:
        return dossier(projet, base, plafond, depuis, court=court), None
    deja = memoire.passes(lot)
    if deja and meme_passe(projet, deja[-1]):
        return dossier(projet, base, plafond, depuis, court=court), trad(
            "(la passe {n} du lot {lot} : rien n'a changé hors de la mémoire depuis ce qu'elle a relu, son commit et "
            "l'arbre de travail ; son dossier se redonne, rien ne s'écrit)", n=deja[-1].numero, lot=lot.id)
    texte = dossier(projet, base, plafond, depuis, court=court)
    depart = depuis or debut
    if outils.git_reussit(projet.racine, "diff", "--quiet", depart, *_hors_memoire(projet)):
        return texte, None
    numero = deja[-1].numero + 1 if deja else 1
    chemin = ecrire_passe(projet, lot, numero, _court(projet, depart), _court(projet, "HEAD"),
                          jour or date.today().isoformat(), empreinte_de_l_arbre(projet, "HEAD"))
    return texte, trad(
        "passe {n} du lot {lot} écrite dans {chemin} : au retour du relecteur, y écrire une ligne « - Bloquant : <sa "
        "cause, en quelques mots> » par bloquant, et « - Ouvre : <les entrées que la passe ouvre> »", n=numero,
        lot=lot.id, chemin=chemin)
