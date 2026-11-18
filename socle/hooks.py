"""Les hooks : accélérateurs, jamais garanties (principe 3).

Hooks de l'agent (Claude Code, déclarés dans `.claude/settings.json`) :
- `session-start` : l'état dérivé entre dans le contexte, au démarrage et
  après chaque compactage ;
- `pre-tool-use`  : refuse une action irréversible ou externe, l'écriture d'un
  fichier protégé, une référence inventée, l'ancien numéro d'une entrée
  renumérotée dans un texte neuf, une demande hors contrat ;
- `stop`          : refuse de conclure tant que les contrôles échouent.

Hooks git (`core.hooksPath = .socle/git-hooks`) :
- `git-pre-commit`        : contrôles rapides avant le commit ;
- `git-prepare-commit-msg`: ajoute à un commit d'agent la trace des hooks qui
  ont tiré pendant sa session (`Socle-Hooks:`), que la CI exige ;
- `git-pre-push`          : `verify --fast`.

Chaque hook laisse une trace datée dans `.socle/trace/hooks.log` : un script
ne peut pas dire s'il a été CHARGÉ, il ne tourne que s'il l'a été. La trace
rend « les hooks tournent-ils ? » vérifiable.
"""

from __future__ import annotations

import ast
import dataclasses
import fnmatch
import glob
import json
import os
import posixpath
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from socle import (commands as commandes, config, requests as demandes, memory as memoire, utils as outils,
                   private as prive)
from socle.messages import trad

OUTILS_ECRITURE = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# Ce que le moteur refuse se juge sur chaque commande simple, découpée
# (`commandes.analyser`), pas sur le texte : voir `irreversible`. La
# politique peut AJOUTER des motifs (`[irreversible] bash`), appliqués à
# chaque commande simple ; elle ne retire rien à ceux du moteur.
IRREVERSIBLES_BASH: list[str] = []
IRREVERSIBLES_OUTILS = [
    r"mcp__github__(merge_pull_request|delete_file|create_repository|fork_repository|create_release|push_files"
    r"|create_or_update_file|enable_pr_auto_merge)",
]
# Les réglages de Claude Code commandent ses hooks : un réglage local peut
# les couper tous. Seul l'humain les modifie, où qu'ils soient.
REGLAGES_AGENT = re.compile(r"(^|/)\.claude/settings(\.local)?\.json$")
# Ce qui part hors du dépôt par le shell : un message de commit, un tag, une
# pull request ou un commentaire par `gh`. Ce qui vise le dépôt privé n'est
# pas une publication.
PUBLIE_BASH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?(?:commit|tag)\b|\bgh\s+(?:pr|issue|release|api)\b")
PUSH_BASH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b")


def tracer(racine: Path, evenement: str, session: str = "", source: str = ""):
    try:
        p = config.chemin_trace(racine)
        p.parent.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().astimezone().isoformat(timespec="seconds")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{horodatage}\t{evenement}\t{session}\t{source}\n")
    except OSError:
        pass  # une trace manquante se voit dans le trailer ; un hook qui casse bloquerait tout


def tracer_refus(racine: Path, etage: str, quoi: str, session: str = ""):
    """Un refus d'un hook, dans la trace : `Refus` et, en source, l'étage et
    ce qui a refusé. Le banc d'évaluation y lit quel étage attrape quoi."""
    tracer(racine, "Refus", session, f"{etage}:{' '.join(quoi.split())[:160]}")


def lire_entree() -> dict:
    try:
        brut = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    try:
        return json.loads(brut) if brut.strip() else {}
    except json.JSONDecodeError:
        return {}


def _depot_commun(dossier: Path) -> tuple[Path, Path] | None:
    """La racine du worktree qui contient `dossier`, et le répertoire git
    commun de son dépôt ; rien hors de tout dépôt."""
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
                       cwd=dossier, capture_output=True, text=True)
    lignes = r.stdout.split("\n")
    if r.returncode != 0 or len(lignes) < 2 or not lignes[0] or not lignes[1]:
        return None
    return Path(lignes[0]).resolve(), Path(lignes[1]).resolve()


def arbre_juge(racine: Path, entree: dict) -> Path:
    """L'arbre où une action de l'agent a lieu (B-0164, ADR-0064). Claude
    Code lance ses hooks à la racine de sa session (`CLAUDE_PROJECT_DIR`), la
    copie principale du dépôt ; un sous-agent travaille pourtant dans un
    worktree, où il crée ses entrées de mémoire. L'arbre est celui du
    fichier écrit, pour un outil d'écriture, sinon le dossier courant de
    l'agent (`cwd` de l'entrée), s'il est un autre worktree du même dépôt,
    équipé du socle ; un autre dépôt, un dossier hors de tout dépôt, ou la
    racine elle-même, rendent `racine`. Le hook avant outil le juge EN PLUS
    de la racine, jamais à sa place : le dossier courant ne lève aucun
    refus."""
    depart = None
    args = entree.get("tool_input") or {}
    if entree.get("tool_name") in OUTILS_ECRITURE and isinstance(args, dict):
        chemin = args.get("file_path") or args.get("notebook_path") or ""
        if chemin and Path(chemin).is_absolute():
            depart = Path(chemin).parent
    if depart is None and entree.get("cwd"):
        depart = Path(str(entree["cwd"]))
    if depart is None:
        return racine
    try:
        # Un fichier nouveau peut être dans un dossier encore absent.
        while not depart.is_dir() and depart != depart.parent:
            depart = depart.parent
        ici, ailleurs = _depot_commun(racine), _depot_commun(depart)
        if not ici or not ailleurs or ailleurs[0] == ici[0] or ailleurs[1] != ici[1]:
            return racine
        if not (ailleurs[0] / ".socle").is_dir():
            return racine
    except OSError:
        # Un dossier que l'agent n'a pas le droit de lire (les réglages d'un
        # autre utilisateur) n'est pas un worktree du projet ; un hook qui
        # planterait ici laisserait passer la commande qu'il devait juger.
        return racine
    return ailleurs[0]


def installer_hooks_git(racine: Path) -> bool:
    """Pointe git vers `.socle/git-hooks` s'il ne pointe nulle part ailleurs.
    Rend vrai si la configuration est en place."""
    if not (racine / config.GIT_HOOKS).is_dir() or not outils.est_depot(racine):
        return False
    actuel = outils.git(racine, "config", "--get", "core.hooksPath", check=False).strip()
    if actuel == config.GIT_HOOKS:
        return True
    if actuel:
        return False  # un choix local existe : ne pas l'écraser
    outils.git_reussit(racine, "config", "core.hooksPath", config.GIT_HOOKS)
    return True


# --------------------------------------------------------------------------
# SessionStart
# --------------------------------------------------------------------------


def session_start(projet: config.Projet, entree: dict) -> int:
    from socle import state as etat

    tracer(projet.racine, "SessionStart", entree.get("session_id", ""), entree.get("source", ""))
    git_ok = installer_hooks_git(projet.racine)
    # Ses lignes entrent dans l'état, en tête avec les autres lignes d'action :
    # toute la sortie du hook tient sous la borne du démarrage (ADR-0071).
    # Gardées, `socle state --short` les redit, où la ligne de coupe renvoie.
    # L'historique, puis les outils, sous un seul délai : celui du hook.
    fin = time.monotonic() + DELAI_OUTILS
    supplement = completer_historique(projet.racine, fin) + installer_outils(projet, fin)
    if not git_ok and (projet.racine / config.GIT_HOOKS).is_dir():
        supplement.append(trad("\n!! hooks git non branchés : `git config core.hooksPath .socle/git-hooks`"))
    etat.retenir_demarrage(projet, supplement)
    print(etat.calculer(projet, supplement=supplement))
    return 0


# Claude Code la pose dans ses sessions cloud, dont le conteneur repart de
# zéro à chaque session.
SESSION_CLOUD = "CLAUDE_CODE_REMOTE"
# Le travail du démarrage en session cloud, l'historique puis les outils,
# sous le délai de son hook (`.claude/settings.json`).
DELAI_OUTILS = 270
# L'historique en prend au plus cette part ; les outils ont le reste.
DELAI_HISTORIQUE = 120
# Arrêté au délai, git a ce temps pour retirer ses verrous avant d'être tué.
ARRET_HISTORIQUE = 10
# Une ligne de la sortie d'un échec des outils, en octets au plus.
LIGNE_DE_SORTIE = 200
# La commande qui complète un clone superficiel, telle que l'agent la relance.
COMPLETER = "git fetch --unshallow"


def completer_historique(racine: Path, fin: float | None = None) -> list[str]:
    """En session cloud, l'historique d'un clone superficiel : sans lui,
    `memoire.references` ne trouve pas les commits que la mémoire cite, et
    refuse le premier commit de l'agent (B-0202). Complété, le clone ne
    l'est plus : rien à marquer. Un échec se dit sans bloquer le démarrage,
    et se retente au suivant. Rend les lignes à montrer à l'agent."""
    if os.environ.get(SESSION_CLOUD) != "true":
        return []
    r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=racine, capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "true":
        return []
    reste = (fin if fin is not None else time.monotonic() + DELAI_OUTILS) - time.monotonic()
    # Aucune invite d'identifiants : personne ne la verrait.
    p = subprocess.Popen(["git", "fetch", "--quiet", "--unshallow"], cwd=racine, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                         env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    try:
        sortie, erreurs = p.communicate(timeout=max(1, min(DELAI_HISTORIQUE, reste)))
    except subprocess.TimeoutExpired:
        # Tué d'emblée (SIGKILL), git laisserait `.git/shallow.lock`, et le
        # clone resterait superficiel, la commande relancée à la main
        # comprise : arrêté (SIGTERM), il retire ses verrous.
        p.terminate()
        try:
            p.communicate(timeout=ARRET_HISTORIQUE)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
        return [trad("!! clone superficiel : `{commande}` dépasse le délai du démarrage ; le relancer avant de "
                     "commiter, sans quoi les commits que la mémoire cite manquent", commande=COMPLETER)]
    if p.returncode == 0:
        return [trad("historique du clone complété (session cloud) : `{commande}`", commande=COMPLETER)]
    derniere = (sortie + erreurs).strip().splitlines()[-1:] or [""]
    return [trad("!! clone superficiel : `{commande}` a rendu {code} ; le relancer avant de commiter, sans quoi "
                 "les commits que la mémoire cite manquent\n    {queue}", commande=COMPLETER, code=p.returncode,
                 queue=outils.raccourcir(derniere[0], LIGNE_DE_SORTIE))]


def installer_outils(projet: config.Projet, fin: float | None = None) -> list[str]:
    """En session cloud, les outils de l'adaptateur, par les commandes que la
    CI lance pour eux : sans eux, la première vérification de l'agent échoue
    (D-0048). Une fois par conteneur ; un échec se dit sans bloquer le
    démarrage. `fin`, l'heure (`time.monotonic`) où le délai du démarrage
    s'achève, que l'historique a pu entamer. Rend les lignes à montrer à
    l'agent."""
    from socle import verification

    if os.environ.get(SESSION_CLOUD) != "true":
        return []
    commandes_ci = verification.commandes_ci(projet)
    # Une commande qui attend son fichier de build ne se lance pas : elle
    # échouerait à chaque session neuve (B-0179).
    attente = verification.commandes_en_attente(projet)
    dit = [trad("outils de l'adaptateur {ligne}", ligne=verification.attente_dite(attente))] if attente else []
    if not commandes_ci:
        return dit
    marque = config.chemin_trace(projet.racine).parent / "outils-installes"
    empreinte = outils.sha256("\n".join(commandes_ci))
    try:
        if marque.read_text(encoding="utf-8").strip() == empreinte:
            return dit
    except OSError:
        pass
    fin = fin if fin is not None else time.monotonic() + DELAI_OUTILS
    lignes, reussi = list(dit), True
    for c in commandes_ci:
        try:
            p = subprocess.run(c, shell=True, cwd=projet.racine, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=max(1, fin - time.monotonic()))
        except subprocess.TimeoutExpired:
            reussi = False
            lignes.append(trad("!! outils de l'adaptateur : `{commande}` dépasse le délai du démarrage ; la "
                               "relancer avant de vérifier", commande=c))
            continue
        if p.returncode == 0:
            lignes.append(trad("outils de l'adaptateur installés (session cloud) : `{commande}`", commande=c))
            continue
        reussi = False
        # Ses cinq dernières lignes, chacune bornée : une ligne de pip peut
        # faire plusieurs Ko, que la borne du démarrage compte (ADR-0071).
        queue = "\n    ".join(outils.raccourcir(l, LIGNE_DE_SORTIE)
                              for l in (p.stdout + p.stderr).strip().splitlines()[-5:])
        lignes.append(trad("!! outils de l'adaptateur : `{commande}` a rendu {code} ; la relancer avant de "
                           "vérifier\n    {queue}", commande=c, code=p.returncode, queue=queue))
    if reussi:
        try:
            marque.parent.mkdir(parents=True, exist_ok=True)
            marque.write_text(empreinte + "\n", encoding="utf-8")
        except OSError:
            pass
    return lignes


# --------------------------------------------------------------------------
# PreToolUse
# --------------------------------------------------------------------------


def _refus(raison: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": raison,
        }
    }, ensure_ascii=False))
    return 0


def _relatif(racine: Path, chemin: str) -> str | None:
    if not chemin:
        return None
    p = Path(chemin)
    if not p.is_absolute():
        p = racine / p
    try:
        return str(p.resolve().relative_to(racine.resolve())).replace(os.sep, "/")
    except ValueError:
        return None


def contenu_apres(racine: Path, outil: str, args: dict, rel: str) -> tuple[str | None, str | None]:
    """(avant, après) d'une écriture, sans l'exécuter."""
    avant = outils.lire_a(racine, None, rel)
    if outil == "Write":
        return avant, args.get("content", "")
    if outil == "Edit":
        if avant is None:
            return None, None
        old, new = args.get("old_string", ""), args.get("new_string", "")
        if args.get("replace_all"):
            return avant, avant.replace(old, new)
        return avant, avant.replace(old, new, 1)
    if outil == "MultiEdit":
        if avant is None:
            return None, None
        t = avant
        for e in args.get("edits", []):
            old, new = e.get("old_string", ""), e.get("new_string", "")
            t = t.replace(old, new) if e.get("replace_all") else t.replace(old, new, 1)
        return avant, t
    return avant, None


def sha_fabrique(racine: Path, texte: str) -> str | None:
    """Un SHA de 40 caractères inconnu dont le préfixe de 7 est connu : la
    signature d'un SHA complété de tête."""
    for sha in sorted(set(re.findall(r"\b[0-9a-f]{40}\b", texte))):
        if outils.git_reussit(racine, "cat-file", "-e", sha):
            continue
        if not outils.git_reussit(racine, "cat-file", "-e", sha[:7]):
            continue
        reel = outils.git(racine, "rev-parse", sha[:7], check=False).strip() or "<introuvable>"
        return trad("SHA fabriqué : {sha} n'est pas un objet de ce dépôt, alors que son préfixe {prefixe} en est "
                    "un. Le SHA complet de {prefixe} est {reel}. Ne jamais compléter un SHA de tête : "
                    "`git rev-parse`.", sha=sha, prefixe=sha[:7], reel=reel)
    return None


def references_inventees(projet: config.Projet, rel: str, avant: str | None, apres: str) -> list[str]:
    """Les références que cette écriture AJOUTE et qui ne mènent nulle part."""
    return references_refusees(projet, rel, avant, apres)[0]


def references_refusees(projet: config.Projet, rel: str, avant: str | None,
                        apres: str) -> tuple[list[str], list[str]]:
    """Ce que cette écriture AJOUTE et que le hook refuse : les références
    inventées, qui ne mènent nulle part, et les anciens numéros (ADR-0083),
    chacun avec l'identifiant actuel de l'entrée qui le porte. Un texte neuf
    cite l'entrée par celui-ci, seul ou sur la ligne de l'ancien ; le
    journal d'avant garde l'ancien, qui se résout."""
    from socle import readings as lp

    fautes, vieux = [], []
    mem_avant = memoire.Memoire.charger(projet.racine)
    mem = memoire.Memoire.charger(projet.racine)
    if memoire.couche_attendue(rel) not in (None, "inconnue"):
        mem.fichiers[rel] = memoire.analyser(rel, apres)
    defs = mem.definitions()
    # Lecture prouvée, par la même fonction que `memoire.lectures` :
    # la base du travail, ses commits et l'arbre. Le refus ne
    # donne pas la bonne empreinte : elle s'obtient en relisant.
    base = outils.base_de_travail(projet.racine)
    commits = outils.git(projet.racine, "rev-list", "--reverse", f"{base}..HEAD", check=False).split() if base else []
    plage = lp.Plage(projet.racine, memoire.Memoire.charger(projet.racine, base) if base else None, mem, commits)
    # Un ancien numéro (ADR-0083) se résout : son empreinte se juge contre
    # l'entrée qui le porte désormais.
    anciens = mem.anciens()
    for ident, h, ligne in memoire.citations(apres):
        soi = lp.entree_englobante(mem, rel, ligne)
        if (ident in defs or ident in anciens) and not lp.deja_citee(soi, f"{ident}@{h}", mem_avant, avant or "") \
                and not lp.entree_lue(plage, rel, soi, ident, h):
            fautes.append(trad("`{ident}@{h}` (ligne {ligne}) n'est pas l'empreinte de la version actuelle de "
                               "{ident} : la relire, `python3 .socle/socle show {ident}`",
                               ident=ident, h=h, ligne=ligne))
    for index, h, ligne in memoire.citations_index(apres):
        soi = lp.entree_englobante(mem, rel, ligne)
        if not lp.deja_citee(soi, f"{index}@{h}", mem_avant, avant or "") \
                and not lp.index_lu(plage, rel, soi, index, h):
            fautes.append(trad("`{index}@{h}` (ligne {ligne}) n'est l'empreinte d'aucune version récente de "
                               "l'index : le relire, `python3 .socle/socle show --index {index}`",
                               index=index, h=h, ligne=ligne))
    deja = {i for i, _ in memoire.mentions(avant or "")}
    par_ligne: dict[int, set[str]] = {}
    for ident, ligne in memoire.mentions(apres):
        par_ligne.setdefault(ligne, set()).add(ident)
    for ident, ligne in memoire.mentions(apres):
        if ident in deja or ident in defs or ident.startswith("P"):
            continue
        if ident in anciens:
            # Sur la ligne qui nomme aussi l'identifiant actuel, l'ancien
            # numéro se lit pour ce qu'il est (« B-0224 → JA-0005 », le
            # bilan de la mise à jour, ou une citation de l'humain).
            if anciens[ident].id not in par_ligne[ligne]:
                vieux.append(trad("`{ident}` (ligne {ligne}) est l'ancien numéro de {actuel} : un texte neuf cite "
                                  "l'entrée par son identifiant actuel, {actuel}, seul ou sur la même ligne que "
                                  "l'ancien", ident=ident, ligne=ligne, actuel=anciens[ident].id))
            continue
        fautes.append(trad("`{ident}` (ligne {ligne}) ne désigne aucune entrée de la mémoire — créer l'entrée "
                           "d'abord, ou corriger l'identifiant ; ne jamais en inventer un", ident=ident, ligne=ligne))
    refs_avant = set(memoire.references(avant or ""))
    for type_, cible in memoire.references(apres):
        if (type_, cible) in refs_avant:
            continue
        if type_ == "commit" and re.fullmatch(r"[0-9a-f]{7,40}", cible) and not outils.objet_existe(projet.racine, cible):
            fautes.append(trad("`commit:{cible}` n'existe pas dans ce dépôt — lire le SHA avec `git rev-parse`, "
                               "jamais de tête", cible=cible))
    return fautes, vieux


def statut_valide_ajoute(rel: str, avant: str | None, apres: str, projet) -> str | None:
    if memoire.couche_attendue(rel) != "canonique":
        return None
    av = {e.id: e for e in memoire.analyser(rel, avant or "").entrees}
    par_id = {d.id: d for d in demandes.toutes(projet.racine)}
    for e in memoire.analyser(rel, apres).entrees:
        if e.type != "F" or e.statut != "valide":
            continue
        if e.id in av and av[e.id].statut == "valide" and av[e.id].meta == e.meta:
            continue
        cites = [c for t, c in e.refs("validation") if t == "id"]
        if not any(par_id.get(c) and par_id[c].validee for c in cites):
            return (trad("`{id}` passe à « validé » sans demande validée par l'humain : ce statut ne s'écrit que "
                         "par l'humain (politique, point 5). Émettre une demande `D-NNNN`.", id=e.id))
    return None


ECRIVAINS = {"rm", "mv", "truncate", "chmod", "chown", "touch", "unlink", "shred", "tee"}


def ecrits(c: commandes.Commande) -> list[str]:
    """Les chemins qu'une commande simple écrit, rapportés au dossier de
    départ : ses redirections, les arguments de `rm`, `mv`, `touch`…, la
    destination de `cp`, les fichiers d'un `sed -i` ou d'un `perl -i`, et ce
    que `git rm`, `git mv`, `git restore` ou `git checkout -- …` réécrivent.
    Exécuter ou lire un fichier n'est pas l'écrire."""
    return [c.chemin(x) for x in ecrits_bruts(c)]


def ecrits_bruts(c: commandes.Commande) -> list[str]:
    """Les chemins qu'écrit `ecrits`, tels que la commande les écrit, ni
    développés ni rapportés au dossier de départ."""
    res = list(c.redirige)
    nom = c.programme
    args = commandes.options_et_arguments(c.argv[1:])[1]
    if nom in ECRIVAINS:
        res += args
        if nom == "mv" and (cible := _dossier_cible(c)) is not None and cible not in args:
            res.append(cible)
    elif nom in ("cp", "ln", "install") and (cible := _dossier_cible(c)) is not None:
        res.append(cible)  # `-t <dossier>` : la destination, les arguments sont lus (B-0206)
    elif nom in ("cp", "ln", "install", "rsync") and args:
        res.append(args[-1])
    elif nom == "sort" and (sortie := _valeur_d_option(c.argv[1:], "o", "--output", "kotST")) is not None:
        res.append(sortie)
    elif nom == "find":
        # Ce qu'écrivent ses `-exec` hors des fichiers qu'il trouve, que
        # `_supprime_par_find` juge (B-0206).
        res += [x for sous, _ in _lire_find(c)[1] if sous is not None for x in ecrits_bruts(sous) if SONDE not in x]
    elif nom in ("sed", "perl") and (script := _fichiers_d_un_script(nom, c.argv[1:]))[0]:
        res += script[1]
    elif nom == "dd":
        res += [a[3:] for a in c.argv[1:] if a.startswith("of=")]
    elif nom == "git":
        sous, reste = commandes.git_sous_commande(c.argv)
        if sous in ("rm", "mv", "restore", "clean"):
            res += commandes.options_et_arguments(reste)[1]
        elif sous == "checkout" and "--" in reste:
            res += reste[reste.index("--") + 1:]
        elif sous == "checkout":
            # Sans `--` : `git checkout <révision> <chemins>`, ou un seul
            # nom, branche ou chemin (B-0165).
            args = commandes.options_et_arguments(reste)[1]
            res += args[1:] if len(args) > 1 else args
    return [x for x in res if x]


def suppressions(c: commandes.Commande) -> list[tuple[str, bool]]:
    """Les chemins qu'une commande simple supprime avec tout ce qu'ils
    contiennent, tels qu'elle les écrit (B-0208) : les arguments de `rm`, les
    sources d'un `mv` (pas sa destination), ce que balaie `git clean` (ses
    chemins, ou son dossier, sous ses `-C`) et les points de départ d'un
    `find` qui supprime (`-delete`, ou un `-exec` qui supprime ce qu'il
    trouve) ; et, d'un autre programme (B-0228), ce que supprime un `rsync`
    (`_supprime_par_rsync`), le worktree que retire ou déplace `git
    worktree` et ce qu'un `python -c` supprime en toutes lettres
    (`_supprimes_par_python`). Chacun avec `True` quand supprimer la racine
    du projet elle-même compte : un `find` qu'aucun filtre de nom ou de
    chemin ne garde la viderait, et un autre programme ne l'écrit pas
    (`ecrits`). Pour `rm`, `mv` et `git clean`, la racine est déjà un
    dossier qui contient un fichier protégé."""
    nom, argv = c.programme, c.argv[1:]
    if nom == "rm":
        return [(x, False) for x in commandes.options_et_arguments(argv)[1] if x]
    if nom == "mv":
        return [(x, False) for x in _sources_de_mv(argv) if x]
    if nom == "find":
        return _departs_de_find(c)
    if nom == "rsync":
        return [(x, True) for x in _supprime_par_rsync(argv)]
    if nom == "git" and commandes.git_sous_commande(c.argv)[0] == "clean":
        return [(x, False) for x in _balaye_par_git_clean(c.argv)]
    if nom == "git" and commandes.git_sous_commande(c.argv)[0] == "worktree":
        return [(x, True) for x in _retire_par_git_worktree(c.argv)]
    script = _script_python(c)
    if script is not None:
        return [(x, True) for x in _supprimes_par_python(script)]
    return []


# Les options de `rsync` qui suppriment dans la destination ce que les
# sources n'ont pas, et celles d'un essai à blanc ou d'une liste, qui ne
# touchent à rien (B-0228).
RSYNC_SUPPRIME = frozenset(("--del", "--delete", "--delete-before", "--delete-during", "--delete-delay",
                            "--delete-after", "--delete-excluded"))
RSYNC_A_BLANC = frozenset(("--dry-run", "--list-only"))
# Les options courtes de `rsync` qui prennent une valeur, collée au groupe ou
# l'argument suivant, et les longues qui la prennent en argument suivant
# quand elles n'ont pas de `=`.
RSYNC_COURTES_A_VALEUR = "efBTM@"
RSYNC_LONGUES_A_VALEUR = frozenset((
    "--rsh", "--rsync-path", "--filter", "--exclude", "--include", "--exclude-from", "--include-from",
    "--files-from", "--block-size", "--temp-dir", "--remote-option", "--modify-window", "--backup-dir", "--suffix",
    "--compare-dest", "--copy-dest", "--link-dest", "--partial-dir", "--max-delete", "--max-size", "--min-size",
    "--max-alloc", "--chmod", "--chown", "--usermap", "--groupmap", "--copy-as", "--timeout", "--contimeout",
    "--bwlimit", "--port", "--sockopts", "--address", "--protocol", "--iconv", "--checksum-seed",
    "--checksum-choice", "--cc", "--compress-choice", "--zc", "--compress-level", "--zl", "--skip-compress",
    "--log-file", "--log-file-format", "--out-format", "--log-format", "--password-file", "--early-input",
    "--write-batch", "--only-write-batch", "--read-batch", "--info", "--debug", "--stderr", "--outbuf",
    "--stop-after", "--stop-at", "--time-limit"))
# Un chemin que `rsync` lit sur un autre hôte : un `:` avant toute barre
# oblique (`hôte:chemin`, `hôte::module`, `rsync://`).
RSYNC_DISTANT = re.compile(r"[^/]*:")


def _supprime_par_rsync(argv: list[str]) -> list[str]:
    """Ce que supprime un `rsync` (`argv` sans le programme), tel qu'il
    l'écrit : sa destination, le dernier argument, s'il supprime ce que les
    sources n'ont pas (`--delete` et ses variantes), et ses sources s'il en
    retire les fichiers copiés (`--remove-source-files`) ; un chemin distant
    n'est pas du projet. Ses options se lisent où qu'elles soient, la valeur
    de celles qui en prennent une avec elles (`-e ssh`, `--exclude .git`) ;
    rien pour un essai à blanc (`-n`, `--dry-run`) ni pour une liste (un
    seul argument, `--list-only`) (B-0228)."""
    args, supprime, retire, i, fin = [], False, False, 0, False
    while i < len(argv):
        a = argv[i]
        i += 1
        if fin or a == "-" or not a.startswith("-"):
            args.append(a)
        elif a == "--":
            fin = True
        elif a.startswith("--"):
            cle = a.split("=", 1)[0]
            if cle in RSYNC_A_BLANC:
                return []
            supprime = supprime or cle in RSYNC_SUPPRIME
            retire = retire or cle == "--remove-source-files"
            if cle in RSYNC_LONGUES_A_VALEUR and "=" not in a:
                i += 1
        else:
            for k, o in enumerate(a[1:], 1):
                if o == "n":
                    return []
                if o in RSYNC_COURTES_A_VALEUR:
                    if k == len(a) - 1:
                        i += 1
                    break
    if len(args) < 2:
        return []
    res = args[-1:] if supprime else []
    res += args[:-1] if retire else []
    return [x for x in res if x and not RSYNC_DISTANT.match(x)]


def _git_global(argv: list[str]) -> tuple[str, int]:
    """Le dossier où travaille un `git` (`argv` entier, depuis `git`), ses
    `-C` joints (`""` : le dossier de la commande), et la place de sa
    sous-commande, derrière ses options globales."""
    base, i = "", 1
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] == "-C" and i + 1 < len(argv):
            base = posixpath.join(base, argv[i + 1])
        i += 2 if argv[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path") else 1
    return base, i


def _retire_par_git_worktree(argv: list[str], suffixe: bool = False) -> list[str]:
    """Le worktree que retire `git worktree remove` (`-f`, `--force`,
    répétés), ou que déplace `git worktree move`, comme les sources d'un
    `mv` (`argv` entier, depuis `git`), rapporté à ses `-C` (B-0228). Avec
    `suffixe`, son argument tel qu'il est écrit, que git cherche d'abord
    comme la fin du chemin d'un de ses worktrees, quels que soient ses `-C`
    (`_trouve_par_son_suffixe`)."""
    base, i = _git_global(argv)
    reste = argv[i + 1:]
    if not reste or reste[0] not in ("remove", "move"):
        return []
    chemins = [x for x in commandes.options_et_arguments(reste[1:])[1][:1] if x]
    return chemins if suffixe or not base else [posixpath.join(base, x) for x in chemins]


def _nommes_par_leur_suffixe(c: commandes.Commande) -> list[str]:
    """Ce que git cherche d'abord comme la fin du chemin d'un de ses
    worktrees, tel que la commande l'écrit : l'argument d'un `git worktree
    remove` ou `move`, et les points de départ d'un `find` qui le lui passe
    par `-exec` (`{}`), avec ce qu'il trouve sous eux (`départ/*`)."""
    if c.programme == "git" and commandes.git_sous_commande(c.argv)[0] == "worktree":
        return _retire_par_git_worktree(c.argv, suffixe=True)
    if c.programme == "find":
        departs, actions = _lire_find(c)
        if any(sous is not None and SONDE in _nommes_par_leur_suffixe(sous) for sous, _ in actions):
            return [y for x in departs for y in (x, posixpath.join(x, "*"))]
    return []


# Les fonctions de python qui suppriment, avec ce qu'il contient, le chemin
# qu'elles reçoivent en premier, ou le déplacent comme les sources d'un `mv`
# (`(module, nom)` ; `rmtree` sous tout nom de module, ou importé seul), et
# les classes d'un chemin de `pathlib` (B-0228).
PYTHON_SUPPRIME = frozenset((("shutil", "move"), ("os", "rename"), ("os", "replace"), ("os", "renames")))
PYTHON_PATH = frozenset(("Path", "PurePath", "PosixPath", "PurePosixPath"))


def _nom_appele(f: ast.expr) -> tuple[str | None, str | None]:
    """Ce qu'appelle un appel de python : le texte de ce qui porte la
    fonction (`os.path`), ou `None` pour un nom seul, et son nom."""
    if isinstance(f, ast.Attribute):
        return ast.unparse(f.value), f.attr
    return None, f.id if isinstance(f, ast.Name) else None


def _est_un_path(n: ast.expr) -> bool:
    """L'expression est-elle un `Path(…)`, résolu ou non (`.resolve()`,
    `.absolute()`)."""
    while (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr in ("resolve", "absolute") and not n.args):
        n = n.func.value
    return isinstance(n, ast.Call) and _nom_appele(n.func)[1] in PYTHON_PATH


def _chemin_ecrit(n: ast.expr | None) -> str | None:
    """Le chemin qu'une expression de python écrit en toutes lettres : une
    chaîne, un `Path(…)` ou un `os.path.join(…)` de tels chemins, joints par
    `/`, résolu ou non ; `None` pour un chemin construit autrement."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
        parts = [_chemin_ecrit(n.left), _chemin_ecrit(n.right)]
    elif isinstance(n, ast.Call) and not n.keywords:
        module, nom = _nom_appele(n.func)
        if nom in ("resolve", "absolute") and module is not None and not n.args:
            return _chemin_ecrit(n.func.value)
        if nom not in PYTHON_PATH and (module, nom) not in (("os.path", "join"), ("posixpath", "join")):
            return None
        parts = [_chemin_ecrit(a) for a in n.args] or ["."]
    else:
        return None
    return None if None in parts else posixpath.join(*parts)


def _supprimes_par_python(script: str) -> list[str]:
    """Les chemins qu'un script de python supprime avec ce qu'ils
    contiennent, lus dans son arbre et écrits en toutes lettres
    (`_chemin_ecrit`) : le chemin de `rmtree` (`shutil.rmtree`, `path=`), la
    source de `shutil.move`, `os.rename`, `os.replace`, `os.renames`
    (`src=`), et le `Path` que `rename` ou `replace` déplace. Un chemin
    construit au vol (`os.getcwd()`, `sys.argv[1]`, une variable) n'en est
    pas, hors du modèle du hook (ADR-0080) ; rien pour un script que python
    ne lirait pas (B-0228)."""
    try:
        res = []
        for n in ast.walk(ast.parse(script)):
            if not isinstance(n, ast.Call):
                continue
            module, nom = _nom_appele(n.func)
            if nom == "rmtree" or (module, nom) in PYTHON_SUPPRIME:
                cles = {k.arg: k.value for k in n.keywords}
                cible = n.args[0] if n.args else cles.get("path", cles.get("src"))
            elif nom in ("rename", "replace") and isinstance(n.func, ast.Attribute) and _est_un_path(n.func.value):
                cible = n.func.value
            else:
                continue
            if chemin := _chemin_ecrit(cible):
                res.append(chemin)
        return res
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []


def _sources_de_mv(argv: list[str]) -> list[str]:
    """Les sources d'un `mv` : ses arguments, moins la destination, le
    dernier, ou celle de `-t` (`--target-directory`), et moins la valeur de
    `-S` (`--suffix`)."""
    args, vers_t, i, fin = [], False, 0, False
    while i < len(argv):
        a = argv[i]
        i += 1
        if fin or a == "-" or not a.startswith("-"):
            args.append(a)
        elif a == "--":
            fin = True
        elif a.startswith("--"):
            vers_t = vers_t or a.split("=", 1)[0] == "--target-directory"
            if a in ("--target-directory", "--suffix"):
                i += 1
        else:
            for k, o in enumerate(a[1:], 1):
                if o in "tS":
                    vers_t = vers_t or o == "t"
                    if k == len(a) - 1:
                        i += 1
                    break
    return args if vers_t else args[:-1]


# Les tests, options et actions d'un `find` qui prennent des valeurs, et
# combien ; un autre mot en `-` n'en prend pas. Les filtres que le hook sait
# lire : de nom, sur le dernier élément du chemin, et de chemin, sur le
# chemin entier tel que `find` l'écrit (B-0206).
FIND_VALEURS = {
    **dict.fromkeys(("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex",
                     "-lname", "-ilname", "-type", "-xtype", "-size", "-perm", "-user", "-group", "-uid", "-gid",
                     "-links", "-inum", "-samefile", "-newer", "-anewer", "-cnewer", "-amin", "-atime", "-cmin",
                     "-ctime", "-mmin", "-mtime", "-used", "-fstype", "-context", "-maxdepth", "-mindepth",
                     "-regextype", "-printf", "-fprint", "-fprint0", "-fls", "-files0-from"), 1),
    "-fprintf": 2,
}
FIND_NOMS = ("-name", "-iname")
FIND_CHEMINS = ("-path", "-ipath", "-wholename", "-iwholename")
FIND_EXEC = ("-exec", "-execdir", "-ok", "-okdir")
# Ce qui garde une action d'un `find` : si un chemin peut l'atteindre sans
# qu'un filtre de nom ou de chemin lui réponde, et ces filtres
# (`("nom", motif)`, `("chemin", motif)`).
LIBRE: tuple[bool, tuple] = (True, ())


def _et(a: tuple[bool, tuple], b: tuple[bool, tuple]) -> tuple[bool, tuple]:
    return a[0] and b[0], tuple(dict.fromkeys(a[1] + b[1]))


def _ou(a: tuple[bool, tuple], b: tuple[bool, tuple]) -> tuple[bool, tuple]:
    return a[0] or b[0], tuple(dict.fromkeys(a[1] + b[1]))


def _expression_find(argv: list[str], i: int) -> list[tuple[list[str] | None, tuple[bool, tuple]]]:
    """Les actions de l'expression d'un `find` (`argv` depuis `i`) qui
    touchent ce qu'il trouve : `-delete` (`None`), et la commande de chaque
    `-exec`, `-execdir`, `-ok`, `-okdir` ; chacune avec ce qui la garde. Un
    filtre de nom ou de chemin ne garde que ce qui le suit dans sa
    conjonction : placé après l'action, nié (`!`, `-not`), ou de l'autre
    côté d'un `-o` (`-or`) ou d'une `,`, il ne la garde pas ; une parenthèse
    garde ce qui la suit si chacune de ses branches a un filtre (la revue
    du lot 3, J-2026-11-14-AH)."""
    actions: list[tuple[list[str] | None, tuple[bool, tuple]]] = []
    pos = i
    fins = (None, ")", ",", "-o", "-or")

    def mot() -> str | None:
        return argv[pos] if pos < len(argv) else None

    def liste(garde):
        nonlocal pos
        valeur = ou(garde)
        while mot() == ",":
            pos += 1
            valeur = ou(garde)
        return valeur

    def ou(garde):
        nonlocal pos
        valeur = et(garde)
        while mot() in ("-o", "-or"):
            pos += 1
            # L'autre branche, prise quand la première est fausse : rien de ce
            # qui la précède ne la garde.
            valeur = _ou(valeur, et(garde))
        return valeur

    def et(garde):
        nonlocal pos
        valeur = un(garde)
        while mot() not in fins:
            if mot() in ("-a", "-and"):
                pos += 1
            valeur = _et(valeur, un(_et(garde, valeur)))
        return valeur

    def un(garde):
        nonlocal pos
        m = mot()
        if m in fins:
            return LIBRE
        pos += 1
        if m in ("!", "-not"):
            while mot() in ("!", "-not"):
                pos += 1
            un(garde)
            return LIBRE
        if m == "(":
            valeur = liste(garde)
            if mot() == ")":
                pos += 1
            return valeur
        if (m in FIND_NOMS or m in FIND_CHEMINS) and pos < len(argv):
            pos += 1
            return False, (("nom" if m in FIND_NOMS else "chemin", argv[pos - 1]),)
        if m == "-delete":
            actions.append((None, garde))
        elif m in FIND_EXEC:
            # Jusqu'à `;` (`\;`) ou `+` ; sans eux, au bout de la commande.
            j = next((k for k in range(pos, len(argv)) if argv[k] in (";", "+")), len(argv))
            actions.append((argv[pos:j], garde))
            pos = j + 1
        else:
            pos += FIND_VALEURS.get(m, 1 if re.fullmatch(r"-newer[aBcmt]{2}", m) else 0)
        return LIBRE

    while pos < len(argv):
        liste(LIBRE)
        pos += 1  # une `)` sans `(`
    return actions


def _departs_de_find(c: commandes.Commande) -> list[tuple[str, bool]]:
    """Les points de départ d'un `find` qui supprime ce qu'il trouve
    (`-delete`, ou `-exec`, `-execdir`, `-ok`, `-okdir` qui lancent `rm`, ou
    un programme qui supprime `{}` selon `suppressions`, B-0228), `.` s'il
    n'en nomme aucun ; chacun avec `True` quand une de ces actions n'est
    gardée par aucun filtre de nom ou de chemin (`_expression_find`) : il
    supprimerait le point de départ et tout ce qu'il contient, quels que
    soient ses autres tests (`-type`, `-empty`). Rien pour un `find` qui ne
    supprime pas."""
    departs, actions = _lire_find(c)
    gardes = [garde for sous, garde in actions if sous is None or sous.programme == "rm"
              or any(SONDE in x for x, _ in suppressions(sous))]
    return [(x, any(libre for libre, _ in gardes)) for x in departs] if gardes else []


def _balaye_par_git_clean(argv: list[str]) -> list[str]:
    """Ce que balaie un `git clean` (`argv` entier, depuis `git`) : ses
    chemins, ou son dossier, rapportés à ses `-C` ; rien pour un essai à
    blanc (`-n`, `--dry-run`). `-e` (`--exclude`) prend une valeur, collée
    au groupe ou l'argument suivant."""
    base, i = _git_global(argv)
    chemins, j, fin, reste = [], 0, False, argv[i + 1:]
    while j < len(reste):
        a = reste[j]
        j += 1
        if fin or a == "-" or not a.startswith("-"):
            chemins.append(a)
        elif a == "--":
            fin = True
        elif a.startswith("--"):
            if a == "--dry-run":
                return []
            if a == "--exclude":
                j += 1
        else:
            groupe = a[1:].split("e", 1)
            if "n" in groupe[0]:
                return []
            if len(groupe) == 2 and not groupe[1]:
                j += 1
    return [posixpath.join(base, x) if base else x for x in chemins or ["."]]


def _contient_le_projet(racine: Path, chemin: str, racine_comprise: bool = False) -> bool:
    """Supprimer `chemin`, absolu, supprimerait-il le projet : il contient
    sa racine, sans être elle, sauf si `racine_comprise` (B-0208). Le
    chemin tel qu'il est écrit et résolu, contre la racine telle qu'elle est
    donnée et résolue : un lien symbolique vers un dossier qui la contient
    compte aussi."""
    if not chemin.startswith("/"):
        return False  # un chemin relatif ne se résoudrait que contre le dossier du hook
    for p in {Path(chemin), Path(os.path.realpath(chemin))}:
        for r in {racine, racine.resolve()}:
            if r.is_relative_to(p) and (racine_comprise or r != p):
                return True
    return False


# Les options courtes d'un `sed` ou d'un `perl` qui prennent une valeur,
# collée au groupe (`-es/a/b/`) ou, sauf celles qui la veulent collée,
# l'argument suivant ; et celles qui donnent le script (B-0171). `perl -0`
# et `perl -l` ne prennent que les chiffres qui les suivent (`-0777`,
# `-0x1FF`, `-l015`) : la suite du groupe est d'autres options (`-lpi`,
# `-0pi`, seconde revue de B-0171, constat 5).
OPTIONS_A_VALEUR = {"sed": "efl", "perl": "eEIMmdDxCV"}
OPTIONS_COLLEES = {"sed": "", "perl": "IMmdDxCV"}
OPTIONS_SCRIPT = {"sed": "ef", "perl": "eE"}
OPTIONS_CHIFFREES = {"sed": {}, "perl": {"0": re.compile(r"x[0-9A-Fa-f]*|[0-7]*"), "l": re.compile(r"[0-7]*")}}


def _fichiers_d_un_script(nom: str, argv: list[str]) -> tuple[bool, list[str]]:
    """Si un `sed` ou un `perl` réécrit ses fichiers (`-i`, `--in-place`), et
    lesquels : ses arguments, moins le script et les valeurs de ses options.
    Le script est celui de `-e`, `-f`, `--expression`, collé au groupe
    (`-e"s/a/b/"`, `-pe's/a/b/'`) ou l'argument suivant, sinon le premier
    argument ; `-i` prend le reste de son groupe pour suffixe (`-i.bak`, et
    `-ie`, dont le `e` est un suffixe). Le script n'est pas un chemin : une
    variable qu'il cite ne fait rien refuser (B-0171)."""
    en_place, script, fichiers, i = False, False, [], 0
    while i < len(argv):
        a = argv[i]
        i += 1
        if a == "--":
            fichiers += argv[i:]
            break
        if a.startswith("--"):
            cle = a.split("=", 1)[0]
            en_place = en_place or cle == "--in-place"
            script = script or cle in ("--expression", "--file")
            if cle in ("--expression", "--file", "--line-length") and "=" not in a:
                i += 1
            continue
        if not a.startswith("-") or a == "-":
            fichiers.append(a)
            continue
        k = 1
        while k < len(a):
            o = a[k]
            if o == "i":
                en_place = True
                break
            if o in OPTIONS_CHIFFREES[nom]:
                k = OPTIONS_CHIFFREES[nom][o].match(a, k + 1).end()
                continue
            if o in OPTIONS_A_VALEUR[nom]:
                script = script or o in OPTIONS_SCRIPT[nom]
                if k == len(a) - 1 and o not in OPTIONS_COLLEES[nom]:
                    i += 1
                break
            k += 1
    return en_place, fichiers if script else fichiers[1:]


# Un argument que le hook ajoute à une commande pour savoir si elle écrit ce
# qu'on lui donne : ce que `xargs` lit, ce que `find` trouve (`{}`).
SONDE = "\0sonde"
# Les options courtes de `cp`, `ln`, `install` et `mv` qui prennent une
# valeur ; `-t` donne le dossier où ils écrivent (B-0206).
OPTIONS_A_VALEUR_COPIE = {"cp": "St", "ln": "St", "install": "gmoSt", "mv": "St"}


def _valeur_d_option(argv: list[str], courte: str, longue: str, a_valeur: str) -> str | None:
    """La valeur de l'option `-<courte>`, seule, collée ou au bout d'un groupe
    (`-tDIR`, `-rt DIR`), ou `--<longue>` et ses préfixes (`--target=DIR`),
    la dernière donnée l'emportant ; `a_valeur`, les options courtes qui
    prennent une valeur. `None` si elle n'est pas donnée."""
    valeur, i = None, 0
    while i < len(argv):
        a = argv[i]
        i += 1
        if a == "--":
            break
        if a.startswith("--"):
            cle, egal, reste = a.partition("=")
            if len(cle) >= 3 and longue.startswith(cle):
                if egal:
                    valeur = reste
                elif i < len(argv):
                    valeur, i = argv[i], i + 1
            continue
        if not a.startswith("-") or a == "-":
            continue
        for k, o in enumerate(a[1:], 1):
            if o in a_valeur:
                v = a[k + 1:]
                if not v and i < len(argv):
                    v, i = argv[i], i + 1
                if o == courte:
                    valeur = v
                break
    return valeur


def _dossier_cible(c: commandes.Commande) -> str | None:
    """Le dossier où `cp`, `ln`, `install` ou `mv` écrivent par `-t`."""
    return _valeur_d_option(c.argv[1:], "t", "--target-directory", OPTIONS_A_VALEUR_COPIE[c.programme])


def _lire_find(c: commandes.Commande) -> tuple[list[str], list[tuple[commandes.Commande | None,
                                                                     tuple[bool, tuple]]]]:
    """Ce que juge le hook d'un `find` : ses points de départ, `.` s'il n'en
    nomme aucun ; et ses actions qui touchent ce qu'il trouve, chacune avec
    ce qui la garde (`_expression_find`) : `None` pour `-delete`, la
    commande d'un `-exec`, `-execdir`, `-ok` ou `-okdir`, `{}` remplacé par
    `SONDE` (B-0206)."""
    argv, i = c.argv, 1
    while i < len(argv) and (argv[i] in ("-H", "-L", "-P", "-D") or re.fullmatch(r"-O\d*", argv[i])):
        i += 2 if argv[i] == "-D" else 1
    departs = []
    while i < len(argv) and not argv[i].startswith("-") and argv[i] not in ("(", ")", "!", ","):
        departs.append(argv[i])
        i += 1
    actions = [(None if sous is None else dataclasses.replace(c, argv=[x.replace("{}", SONDE) for x in sous],
                                                               redirige=[], prefixe=[]), garde)
               for sous, garde in _expression_find(argv, i) if sous is None or sous]
    return departs or ["."], actions


def _filtres_de_find(c: commandes.Commande) -> tuple[list[str], tuple | None] | None:
    """Les points de départ d'un `find` qui supprime ou écrit ce qu'il trouve
    (`-delete`, un `-exec` d'un écrivain de `{}`), et les filtres de nom et
    de chemin qui gardent ces actions (`(noms, chemins)`), ou `None` quand
    l'une d'elles n'en a pas : elle touche tout ce qui est sous ses départs.
    `None` pour un `find` qui n'écrit rien de ce qu'il trouve (B-0206)."""
    departs, actions = _lire_find(c)
    gardes = [garde for sous, garde in actions if sous is None or any(SONDE in x for x in ecrits_bruts(sous))]
    if not gardes:
        return None
    if any(libre for libre, _ in gardes):
        return departs, None
    filtres = list(dict.fromkeys(f for _, fs in gardes for f in fs))
    return departs, ([v for genre, v in filtres if genre == "nom"], [v for genre, v in filtres if genre == "chemin"])


def _motifs_de_chemin(tete: str, haut: str, motif: str) -> list[str]:
    """Les motifs, rapportés à la racine du projet, des chemins que vise le
    filtre de chemin d'un `find` (`-path`, `-ipath`, `-wholename`) : il
    répond au chemin entier tel que `find` l'écrit, `tete` (son départ, et
    ce qui mène de lui à la racine) devant ce qui correspond, sous la
    racine, à `haut` ; son `*` traverse les `/` et rend les noms en `.`, et
    se lit comme `**`. Une étoile qui suit une part de `tete` en rend la
    suite, et ce qui vient après dans le projet ; un motif qui ne peut pas
    commencer comme `tete` ne vise rien (la revue du lot 3,
    J-2026-11-14-AH)."""
    def etoiles(m: str) -> str:
        return re.sub(r"\*+", "**", m)

    if motif.startswith(tete):
        return [haut + etoiles(motif[len(tete):])]
    litteral = re.match(r"[^*?\[\\]*", motif).group()
    suite = motif[len(litteral):]
    if not tete.startswith(litteral):
        return []
    if not suite:
        return [haut.rstrip("/") or "**"]  # le départ lui-même, ou un dossier qui le contient
    if suite.startswith("*"):
        reste = suite.lstrip("*")
        return ["**" + etoiles(reste)] + ([haut + etoiles(reste[1:])] if reste.startswith("/") else [])
    return ["**"]  # un `?`, un `[…]` ou un `\` dans le départ : le hook ne le suit pas


def _proteges_presents(projet: config.Projet, cache: dict) -> list[str]:
    """Les fichiers suivis du projet que protège la politique."""
    if "proteges presents" not in cache:
        if "suivis" not in cache:
            cache["suivis"] = outils.fichiers_courants(projet.racine)
        motifs = projet.chemins_proteges()
        cache["proteges presents"] = [f for f in cache["suivis"] if outils.correspond(f, motifs)]
    return cache["proteges presents"]


def _reglages_presents(projet: config.Projet, cache: dict) -> list[str]:
    """Les réglages de Claude Code présents dans le projet : ceux que git
    voit, et ceux de la racine, que git ignore souvent
    (`settings.local.json`)."""
    if "reglages presents" not in cache:
        if "suivis" not in cache:
            cache["suivis"] = outils.fichiers_courants(projet.racine)
        racine = [x for x in (".claude/settings.json", ".claude/settings.local.json") if (projet.racine / x).is_file()]
        cache["reglages presents"] = list(dict.fromkeys(racine + [f for f in cache["suivis"]
                                                                  if REGLAGES_AGENT.search(f)]))
    return cache["reglages presents"]


def _supprime_par_find(projet: config.Projet, c: commandes.Commande, environnement: dict,
                       cache: dict) -> list[tuple[str, str]]:
    """Les constats d'un `find` qui supprime ou écrit ce qu'il trouve
    (`-delete`, `-exec rm {} +`) : ses points de départ et les filtres qui
    gardent ces actions (`_filtres_de_find`), jugés contre les motifs des
    chemins protégés à toute profondeur (un `find` voit les noms en `.`), et
    contre les réglages de Claude Code présents ; un départ que le hook ne
    sait pas développer et qui peut tomber dans le projet est illisible
    (B-0206)."""
    lu = _filtres_de_find(c)
    if lu is None:
        return []
    departs, filtres = lu
    racine = projet.racine.resolve()
    variables = commandes.variables_de(c, environnement)
    res: list[tuple[str, str]] = []
    for depart in departs:
        d = commandes.developper(depart, variables)[0]
        plein = commandes.normaliser(d if d.startswith(("/", commandes.INCONNU)) else posixpath.join(c.lieu, d))
        if commandes.INCONNU in plein:
            lieu = commandes.lieu_sur(plein)
            if lieu is None or _atteint(racine, Path(lieu)):
                res.append(("illisible", f"`{depart}`"))
            continue
        lieu = Path(os.path.realpath(plein))
        # Ce que `find` écrit devant un chemin du projet : son départ, et ce
        # qui mène de lui à la racine s'il la contient.
        tete = d.rstrip("/") + "/"
        if lieu.is_relative_to(racine):
            base = lieu.relative_to(racine).as_posix()
            base = "" if base == "." else base
        elif racine.is_relative_to(lieu):
            base = ""  # un dossier qui contient le projet : tout le projet, à toute profondeur
            tete += racine.relative_to(lieu).as_posix() + "/"
        else:
            continue
        haut = (base + "/") if base else ""
        if filtres is None:
            motifs = [base or "**"]
        else:
            noms, chemins = filtres
            motifs = [m for n in noms for m in (haut + n, haut + "**/" + n)]
            motifs += [m for p in chemins for m in _motifs_de_chemin(tete, haut, p)]
        # Un filtre nomme ce que `find` trouve ; sans filtre, il trouve tout ce
        # qui est sous son départ. Un filtre se juge contre les fichiers
        # protégés présents d'un motif de dossier (`.socle/git-hooks/**`),
        # que tout nom croiserait (`-name '*.pyc'`), et contre les autres
        # motifs (un fichier protégé absent le reste) ; un réglage de Claude
        # Code, à toute profondeur, contre ceux qui sont présents, et contre
        # leurs motifs si le filtre les nomme (`.claude`, `settings`) : git
        # ne voit pas un réglage ignoré sous un dossier du projet.
        dessous = filtres is None
        for motif in dict.fromkeys(motifs):
            for m in projet.chemins_proteges():
                if dessous or not m.endswith("/**"):
                    touches = [m] if commandes.se_croisent(motif, m, dessous, True) else []
                else:
                    touches = [f for f in _proteges_presents(projet, cache) if outils.correspond(f, [m])
                               and commandes.se_croisent(motif, f, False, True)]
                res += [("protege", trad("{chemin}, par `{mot}`", chemin=t, mot=f"find {depart}")) for t in touches]
            res += [("reglage", f) for f in _reglages_presents(projet, cache)
                    if commandes.se_croisent(motif, f, dessous, True)]
            if not dessous and re.search(r"claude|settings", motif, re.I):
                res += [("reglage", motif) for m in REGLAGES_MOTIFS if commandes.se_croisent(motif, m, False, True)]
    return res


def _script_python(c: commandes.Commande) -> str | None:
    """Le script d'un `python -c`, derrière les options de python ; `None`
    pour un autre programme ou une autre forme (B-0206)."""
    if not re.fullmatch(r"python[\d.]*", c.programme):
        return None
    reste = c.argv[1:]
    while reste and reste[0].startswith("-") and reste[0] not in ("-", "--"):
        opt, reste = reste[0], reste[1:]
        if opt.startswith("--"):
            reste = reste[1:] if opt in OPTIONS_LONGUES_PYTHON_A_VALEUR else reste
            continue
        for k, lettre in enumerate(opt[1:], 1):
            colle = opt[k + 1:]
            if lettre == "c":
                return colle or (reste[0] if reste else None)
            if lettre == "m":
                return None
            if lettre in OPTIONS_PYTHON_A_VALEUR:
                reste = reste if colle else reste[1:]
                break
    return None


def _xargs_ecrit_ce_qu_il_lit(c: commandes.Commande) -> bool:
    """La commande qu'un `xargs` lance écrit-elle ce qu'il lit : ce qu'il
    ajoute au bout de ses arguments, ou ce qui remplace la chaîne de `-I`
    (`-i`, `--replace`, `{}` par défaut) (B-0206)."""
    noms = [p.rsplit("/", 1)[-1] for p in c.prefixe]
    if "xargs" not in noms or not c.argv:
        return False
    options, remplace = c.prefixe[noms.index("xargs") + 1:], None
    for k, o in enumerate(options):
        if o == "-I" and k + 1 < len(options):
            remplace = options[k + 1]
        elif o.startswith("-I") and len(o) > 2:
            remplace = o[2:]
        elif o in ("-i", "--replace"):
            remplace = "{}"
        elif o.startswith("--replace="):
            remplace = o.split("=", 1)[1] or "{}"
        elif o.startswith("-i"):
            remplace = o[2:]
    argv = [x.replace(remplace, SONDE) for x in c.argv] if remplace else c.argv + [SONDE]
    return any(SONDE in x for x in ecrits_bruts(dataclasses.replace(c, argv=argv, redirige=[], prefixe=[])))


# Un chemin cité dans un texte que le hook ne sait pas lire : une suite de
# lettres, de chiffres, de `.`, `/`, `~` et `-`.
CHEMIN_CITE = re.compile(r"[\w./~-]+")


def _cites(projet: config.Projet, c: commandes.Commande, texte: str, qui: str, cache: dict) -> list[tuple[str, str]]:
    """Les chemins protégés que `texte` cite en toutes lettres, pour un
    écrivain que le hook ne sait pas lire (`qui`) : un fichier protégé, un
    réglage de Claude Code, ou un dossier qui en contient, écrit avec une
    barre oblique ou un point de tête (`.socle`, `memory/requests`) ; ni la
    racine ni un dossier hors du projet. Un chemin relatif part du dossier
    de la commande (B-0206)."""
    racine = projet.racine
    res: list[tuple[str, str]] = []
    for mot in dict.fromkeys(CHEMIN_CITE.findall(texte)):
        mot = os.path.expanduser(mot) if mot.startswith("~") else mot
        plein = commandes.normaliser(mot if mot.startswith("/") else posixpath.join(c.lieu, mot))
        if commandes.INCONNU in plein or not plein.startswith("/"):
            continue
        rel = _relatif(racine, plein)
        if rel in (None, "", "."):
            continue
        cible = _protege(projet, rel, cache)
        if cible and (cible == rel or "/" in mot or mot.startswith(".")):
            res.append(("protege", trad("{chemin}, cité par `{qui}`, un écrivain que le hook ne sait pas lire : il "
                                        "peut l'écrire ; un fichier protégé se lit par `cat` ou par l'outil de "
                                        "lecture", chemin=cible, qui=qui)))
        if REGLAGES_AGENT.search(plein):
            res.append(("reglage", rel))
    return res


def _ecrivains_illisibles(projet: config.Projet, c: commandes.Commande, cmd: str, environnement: dict,
                          cache: dict) -> list[tuple[str, str]]:
    """Les constats des écrivains que le hook ne lit pas comme les autres :
    `python -c` et `xargs` d'un écrivain, par les chemins protégés qu'ils
    citent (le script ; la commande entière, dont `xargs` lit l'entrée), et
    `find` qui supprime ou écrit ce qu'il trouve (B-0206)."""
    res: list[tuple[str, str]] = []
    script = _script_python(c)
    if script is not None:
        res += _cites(projet, c, script, f"{c.programme} -c", cache)
    if _xargs_ecrit_ce_qu_il_lit(c):
        res += _cites(projet, c, cmd, f"xargs {c.programme}", cache)
    if c.programme == "find":
        res += _supprime_par_find(projet, c, environnement, cache)
    return res


# Ce qui, dans le texte d'une commande, peut écrire selon `ecrits` : une
# redirection, ou le nom d'un programme qu'il lit comme écrivain, ou qui
# supprime selon `suppressions` (`find`, B-0208).
PEUT_ECRIRE = re.compile(r">|(?<![\w.-])(?:" + "|".join(sorted(
    ECRIVAINS | {"cp", "ln", "install", "rsync", "sed", "perl", "dd", "git", "sort", "find", "xargs"})) + r")(?![\w.-])")


def peut_ecrire(cmd: str) -> bool:
    """La commande peut-elle écrire, à en juger par son texte seul, sans la
    découper : une redirection, ou le nom d'un programme que le hook lit
    comme écrivain (`rm`, `sed`, `git`…), guillemets et barres obliques
    inverses retirés (`r''m`, `\\rm`)."""
    return bool(PEUT_ECRIRE.search(re.sub(r"[\\'\"]", "", cmd)))


# Le temps que se donne le jugement des écritures d'une commande du shell :
# au-delà, il la refuse (`injugeable`) plutôt que de laisser le délai du hook
# la faire passer. Deux jugements, quand l'action a lieu dans un autre
# worktree, tiennent sous les 20 s que Claude Code donne au hook.
DELAI_JUGEMENT = 5


def _dans_le_delai(limite: float | None):
    """Lève `TimeoutError` si le jugement a passé sa `limite` (`time.monotonic`)."""
    if limite is not None and time.monotonic() > limite:
        raise TimeoutError


def injugeable(cmd: str, erreur: BaseException | None = None) -> str | None:
    """Le refus d'une commande dont le hook ne sait pas juger les écritures,
    si elle peut écrire (`peut_ecrire`) : trop longue ou trop imbriquée pour
    se découper sans risque (`commandes.demesure`), ou dont le découpage ou
    le jugement a levé `erreur` (`TimeoutError`, au-delà de
    `DELAI_JUGEMENT`). Un hook qui plante ou dépasse son délai laisse passer
    la commande : ce qui ne se juge pas ne passe pas (seconde revue de
    B-0171, constat 4, ADR-0072)."""
    if isinstance(erreur, TimeoutError):
        pourquoi = trad("son jugement a pris plus de {n} secondes", n=DELAI_JUGEMENT)
    elif erreur is not None:
        pourquoi = trad("son découpage a levé {erreur}", erreur=type(erreur).__name__)
    elif (mesure := commandes.demesure(cmd)) and mesure[0] == "longueur":
        pourquoi = trad("{n} caractères hors du corps de ses heredocs, au-delà de {max}", n=mesure[1],
                        max=commandes.LONGUEUR_MAX)
    elif mesure:
        pourquoi = trad("{n} parenthèses ou accolades ouvertes à la fois, au-delà de {max}", n=mesure[1],
                        max=commandes.PROFONDEUR_MAX)
    else:
        return None
    if not peut_ecrire(cmd):
        return None
    return trad("écriture par le shell dans une commande que le hook ne sait pas juger ({pourquoi}) : il ne peut "
                "dire si elle écrit un fichier protégé. La découper en commandes plus simples, lancées une à une ; "
                "un long texte s'écrit par l'outil d'écriture de fichiers, ou dans le corps d'un heredoc, qui "
                "ne compte pas (B-0171).", pourquoi=pourquoi)


def cibles_ecrites(cmd: str) -> list[str]:
    """Les chemins qu'une commande shell écrit, toutes commandes simples
    confondues."""
    return [x for c in commandes.analyser(cmd) for x in ecrits(c)]


def _protege(projet: config.Projet, rel: str, cache: dict) -> str | None:
    """`rel` dit comme le refus le cite, s'il est protégé ou contient un
    fichier protégé ; `None` sinon."""
    motifs = projet.chemins_proteges()
    if outils.correspond(rel, motifs):
        return rel
    if "suivis" not in cache:
        cache["suivis"] = outils.fichiers_courants(projet.racine)
    prefixe = "" if rel in ("", ".") else rel.rstrip("/") + "/"
    touche = next((f for f in cache["suivis"] if f.startswith(prefixe) and outils.correspond(f, motifs)), None)
    return trad("{chemin}/ (dont {touche})", chemin=rel or ".", touche=touche) if touche else None


def ecriture_protegee(projet: config.Projet, cmd: str) -> str | None:
    """Le chemin protégé qu'une commande shell écrit, s'il y en a un : un
    fichier protégé, ou un dossier qui en contient (`rm -rf .socle`), écrit
    en toutes lettres ou que le shell développerait (`$F`, `.socle/pol*`,
    B-0171). La remise d'un fichier protégé à son état du dernier commit,
    que `remise_en_etat` admet, n'en est pas une (D-0098)."""
    return next((quoi for genre, quoi in ecritures_jugees(projet, cmd) if genre == "protege"), None)


# Un motif du shell : un joker, ou une classe fermée.
MOTIF_SHELL = re.compile(r"[*?]|\[.+\]")
# Les réglages de Claude Code, comme motifs de chemin (`REGLAGES_AGENT`).
REGLAGES_MOTIFS = ("**/.claude/settings.json", "**/.claude/settings.local.json")


def _atteint(racine: Path, lieu: Path) -> bool:
    """Un chemin sous `lieu` peut-il être dans le projet : `lieu` y est, ou
    le contient."""
    lieu, racine = Path(os.path.realpath(lieu)), racine.resolve()
    return lieu.is_relative_to(racine) or racine.is_relative_to(lieu)


def depart_de(racine: Path, cwd: str | None) -> str:
    """Le dossier, absolu, où part une commande de l'agent : son dossier
    courant (`cwd` de l'entrée du hook) s'il est connu, sinon la racine
    (B-0205)."""
    return posixpath.normpath(posixpath.join(str(racine), cwd)) if cwd else str(racine)


def _globbing_elargi(simples: list[commandes.Commande]) -> bool:
    """Un `shopt`, ou une affectation de `GLOBIGNORE`, dans la commande : ses
    motifs peuvent rendre les noms en `.` (`dotglob`), traverser les
    dossiers (`globstar`) ou ignorer la casse (`nocaseglob`)."""
    return any(c.programme == "shopt" or "GLOBIGNORE" in (c.connues or dict(c.affectations))
               or any(p.startswith("GLOBIGNORE=") for p in c.prefixe) for c in simples)


def ecritures_jugees(projet: config.Projet, cmd: str, cwd: str | None = None,
                     limite: float | None = None) -> list[tuple[str, str]]:
    """Ce que le hook retient des chemins qu'une commande shell écrit, hors
    des fichiers qu'une remise admise remet (D-0098), chacun développé comme
    le shell le ferait (B-0171) : ses accolades, son `~`, les variables de
    l'environnement du hook (hors des variables spéciales du shell) et
    celles que la commande affecte avant, chaque valeur entière et chacun de
    ses mots, puis ses motifs, contre les fichiers présents et contre les
    motifs des chemins protégés (un fichier protégé absent le reste). Un
    chemin relatif, un motif et `$PWD` partent du dossier courant de l'agent
    (`cwd`) s'il est connu, sinon de la racine (B-0205). Ce qu'une commande
    supprime (`suppressions`) se développe de même. Chaque constat :
    `("protege", cible)`, `("reglage", chemin)`, `("supprime", chemin)` pour
    la suppression d'un dossier qui contient le projet (B-0208) ou, pour un
    chemin que le hook ne sait pas développer et qui peut tomber dans le
    projet, `("illisible", mot)`. Passé sa `limite` (`time.monotonic`), il
    lève `TimeoutError`."""
    depart = depart_de(projet.racine, cwd)
    environnement = commandes.environnement_du_shell(os.environ, depart)
    simples = commandes.analyser(cmd, environnement=environnement)
    elargi = _globbing_elargi(simples)
    cache: dict = {}
    res: list[tuple[str, str]] = []
    for c in simples:
        _dans_le_delai(limite)
        res += _ecrivains_illisibles(projet, c, cmd, environnement, cache)
        mots = _ecrits_hors_remise(projet, c, remise_en_etat(projet, c, cmd, depart), depart)
        supprimes = dict(suppressions(c))
        suffixes = _nommes_par_leur_suffixe(c)
        if not mots and not supprimes and not suffixes:
            continue
        variables = commandes.variables_de(c, environnement)
        for mot in dict.fromkeys(mots + list(supprimes) + suffixes):
            _dans_le_delai(limite)
            genre = {"ecrit": mot in mots, "supprime": mot in supprimes, "racine_comprise": supprimes.get(mot, False),
                     "suffixe": mot in suffixes}
            mot = mot.strip("'\"")
            try:
                for forme in commandes.accolades(mot):
                    res += _juger_forme(projet, c, mot, forme, variables, cache, depart, elargi, **genre)
            except (OSError, RuntimeError, ValueError, re.error):
                # Un hook qui lèverait laisserait passer la commande sans la
                # juger : ce qui ne se juge pas ne passe pas.
                res.append(("illisible", f"`{mot}`"))
    return list(dict.fromkeys(res))


def _dit(mot: str, chemin: str) -> str:
    """Le chemin visé, et le mot qui le vise si le shell le développe."""
    return trad("{chemin}, par `{mot}`", chemin=chemin, mot=mot) if re.search(r"[$`*?\[{~(]", mot) else chemin


def _juger_forme(projet: config.Projet, c: commandes.Commande, mot: str, forme: str, variables: dict,
                 cache: dict, depart: str, elargi: bool, suffixe: bool = False, **genre) -> list[tuple[str, str]]:
    """Les constats d'`ecritures_jugees` pour une forme d'un mot que `c`
    écrit ou supprime (une par accolade ; `genre`, comme `_juger_chemin`). Développé, le mot se juge entier et, s'il
    porte une variable ou une substitution, mot par mot : hors des
    guillemets, le shell le couperait en mots, que le découpage ne
    distingue plus d'un mot entre guillemets (B-0171). Un mot que git
    cherche comme la fin du chemin d'un worktree (`suffixe`) se juge aussi
    ainsi (`_trouve_par_son_suffixe`)."""
    d, inconnus = commandes.developper(forme, variables)
    champs = [d]
    if re.search(r"[$`]", forme):
        separateurs = variables.get("IFS")
        separateurs = " \t\n" if separateurs is None or commandes.INCONNU in separateurs else separateurs
        if separateurs:
            champs += [x for x in re.split("[" + re.escape(separateurs) + "]+", d) if x]
    res: list[tuple[str, str]] = []
    for champ in dict.fromkeys(champs):
        if not champ:  # un mot vide : le shell n'écrit rien
            continue
        if suffixe:
            res += _trouve_par_son_suffixe(projet.racine, mot, champ)
        if genre["ecrit"] or genre["supprime"]:
            res += _juger_chemin(projet, c, mot, champ, inconnus, cache, depart, elargi, **genre)
    return res


def _trouve_par_son_suffixe(racine: Path, mot: str, d: str) -> list[tuple[str, str]]:
    """Le constat pour l'argument `d`, développé, d'un `git worktree remove`
    ou `move`. Git cherche d'abord, parmi ses worktrees, celui dont le
    chemin finit par lui, à une frontière de dossier, s'il est le seul, et
    ne le lit qu'ensuite comme un chemin relatif (`find_worktree`,
    J-2026-11-15-O) : `git worktree remove agent-x`, lancé dans
    `.claude/worktrees/agent-x`, le retire. Refusé si la racine, ou un
    dossier qui la contient, a un chemin qui finit par lui, sans égard à la
    casse (`core.ignorecase`) ; une part inconnue vaut tout texte, et un
    motif, ce qu'il filtre. Sans appel à git, qui dirait si ce dossier est
    un worktree et le seul de ce suffixe : un refus de trop accepté. Un
    chemin absolu, que git compare entier, se juge comme un chemin."""
    if d.startswith("/"):
        return []
    fin, motif = d.casefold(), "*/" + d.replace(commandes.INCONNU, "*").casefold()
    for r in dict.fromkeys((racine, racine.resolve())):
        for p in (r, *r.parents):
            if str(p).casefold().endswith("/" + fin) or fnmatch.fnmatchcase(str(p).casefold(), motif):
                return [("supprime", trad("{chemin}, que git trouve par la fin de son chemin, `{mot}`",
                                          chemin=str(p), mot=mot))]
    return []


def _juger_chemin(projet: config.Projet, c: commandes.Commande, mot: str, d: str, inconnus: list[str],
                  cache: dict, depart: str, elargi: bool, ecrit: bool = True, supprime: bool = False,
                  racine_comprise: bool = False) -> list[tuple[str, str]]:
    """Les constats pour un chemin développé `d` que `c` écrit (`ecrit`)
    ou supprime avec ce qu'il contient (`supprime`) par `mot` ; supprimer
    la racine elle-même compte si `racine_comprise` (`suppressions`)."""
    racine = projet.racine
    relatif = not d.startswith(("/", commandes.INCONNU))
    plein = commandes.normaliser(posixpath.join(c.lieu, d) if relatif else d)
    if commandes.INCONNU in plein:
        # Ce qui ne se développe pas : la part écrite en toutes lettres qui
        # le précède, remontée des `..` qui le suivent, dit seule où il tombe.
        lieu = commandes.lieu_sur(plein)
        if not ecrit:
            # Supprimé sans être écrit (le départ d'un `find`, ce que balaie
            # `git clean`) : refusé s'il peut contenir le projet (B-0208).
            if lieu is None or _contient_le_projet(racine, lieu, racine_comprise):
                return [("supprime", trad("`{mot}`, que le hook ne sait pas développer", mot=mot))]
            return []
        if lieu is not None and not _atteint(racine, Path(lieu)):
            return []
        if commandes.INCONNU not in d:
            return [("illisible", trad("`{mot}`, dans le dossier `{dossier}`", mot=mot, dossier=c.dossier))]
        if inconnus in ([mot], []):
            return [("illisible", f"`{mot}`")]
        return [("illisible", trad("`{mot}`, dont {parts}", mot=mot, parts=", ".join(f"`{x}`" for x in inconnus)))]
    res = []
    dedans = plein.startswith(depart + "/")
    if MOTIF_SHELL.search(plein[len(depart):] if dedans else plein):
        # Le motif contre les fichiers présents, comme le shell, puis contre
        # les motifs des chemins protégés ; le dossier de départ, que la
        # commande n'écrit pas, ne se lit pas comme un motif.
        for trouve in sorted(glob.glob(glob.escape(depart) + plein[len(depart):] if dedans else plein,
                                       recursive=elargi, include_hidden=elargi)):
            if supprime and _contient_le_projet(racine, trouve, racine_comprise):
                res.append(("supprime", _dit(mot, trouve)))
            if not ecrit:
                continue
            rel = _relatif(racine, trouve)
            cible = _protege(projet, rel, cache) if rel is not None else None
            if cible:
                res.append(("protege", _dit(mot, cible)))
            if REGLAGES_AGENT.search(trouve):
                res.append(("reglage", rel or trouve))
        base = next((b for b in {str(racine), str(racine.resolve())} if plein.startswith(b + "/")), None)
        if ecrit and base is not None:
            motif = plein[len(base) + 1:]
            res += [("protege", _dit(mot, m)) for m in projet.chemins_proteges()
                    if commandes.se_croisent(motif, m, True, elargi)]
            res += [("reglage", mot) for m in REGLAGES_MOTIFS if commandes.se_croisent(motif, m, permissif=elargi)]
        return res
    if supprime and _contient_le_projet(racine, plein, racine_comprise):
        res.append(("supprime", _dit(mot, plein)))
    if not ecrit:
        return res
    rel = _relatif(racine, plein)
    cible = _protege(projet, rel, cache) if rel is not None else None
    if cible:
        res.append(("protege", _dit(mot, cible)))
    if REGLAGES_AGENT.search(posixpath.normpath(plein)):
        res.append(("reglage", rel or plein))
    return res


# D-0098 : ce que l'agent peut lancer pour remettre un fichier protégé changé
# par erreur, chaque chemin écrit en toutes lettres.
REMISE_FORMES = ("`git restore --source=HEAD --staged --worktree -- <chemin>`", "`git checkout HEAD -- <chemin>`",
                 "`rm <chemin>`")
# Les options de `git restore` qui gardent la remise à l'état du dernier
# commit ; sans `--source=HEAD`, elle viendrait de l'index.
REMISE_OPTIONS = {"--source=HEAD", "--staged", "-S", "--worktree", "-W", "-SW", "-WS"}
# Un chemin que le shell réécrirait (variable, substitution, motif,
# dossier de l'utilisateur) ou que git lirait comme un motif (`:(glob)…`).
NON_LITTERAL = re.compile(r"[$`*?\[\]{}~\\!]|^:")
# Ce qui change, dans la même commande, l'environnement ou le dossier où
# git lit : une affectation (`GIT_DIR=…`), un `export`, un `pushd`.
AFFECTATION = re.compile(r"[A-Za-z_]\w*=")
ENVIRONNEMENT = {"export", "declare", "typeset", "readonly", "local", "source", ".", "set", "alias", "pushd", "popd"}


def _environnement_change(texte: str) -> bool:
    return any(AFFECTATION.match(j) for j in commandes.jetons(texte)) or any(
        c.programme in ENVIRONNEMENT for c in commandes.analyser(texte))


def _ecrits_hors_remise(projet: config.Projet, c: commandes.Commande,
                        remise: tuple[list[str], str | None] | None, depart: str | None = None) -> list[str]:
    """Ce que la commande écrit, tel qu'elle l'écrit, moins les fichiers
    qu'une remise admise remet : ses redirections et ses autres chemins se
    jugent comme avant. `depart`, le dossier où part la commande."""
    if remise is None or remise[1] is not None:
        return ecrits_bruts(c)
    sans = dataclasses.replace(c, redirige=[])
    return [x for x in c.redirige if x] + [
        x for x in ecrits_bruts(sans)
        if _relatif(projet.racine, posixpath.join(depart or str(projet.racine), c.chemin(x))) not in remise[0]]


def _cite_chemin(texte: str, rel: str) -> bool:
    """Le texte cite `rel`, ou un dossier qui le contient (`.socle/`,
    `.socle/**`, `.socle`), écrit seul et non comme début d'un autre chemin."""
    if rel in texte:
        return True
    parties = rel.split("/")[:-1]
    for i in range(1, len(parties) + 1):
        dossier = re.escape("/".join(parties[:i]))
        if re.search(r"(?<![\w./-])" + dossier + r"(?:/\**)?(?![\w./-])", texte):
            return True
    return False


def _demande_qui_epargne(projet: config.Projet, rel: str):
    """La demande qui cite `rel`, ou un dossier qui le contient, et dont ce
    qu'elle approuve n'est pas encore commité : en attente, ou validée quand
    sa réponse n'est pas dans `HEAD` ou que l'empreinte du fichier présent
    est celle qu'elle cite."""
    from socle import fingerprint as empreinte

    racine = projet.racine
    present = racine / rel
    actuelle = empreinte.courte(empreinte.fichier(present)) if present.is_file() else None
    for d in demandes.toutes(racine):
        if not d.id or d.entree is None or "retiree" in d.entree.meta or not _cite_chemin(d.texte, rel):
            continue
        if d.reponse is None:
            return d
        if d.validee and ((actuelle and actuelle in d.texte) or not d.chemin_reponse or outils.git(
                racine, "cat-file", "-t", f"HEAD:{d.chemin_reponse}", check=False).strip() != "blob"):
            return d
    return None


def remise_en_etat(projet: config.Projet, c: commandes.Commande, texte: str = "",
                   depart: str | None = None) -> tuple[list[str], str | None] | None:
    """D-0098 : une commande simple qui remet des fichiers protégés à leur
    état du dernier commit. `None` si elle n'en vise aucun ; sinon les
    chemins protégés qu'elle remet, et la raison de son refus, ou `None`
    si elle passe. Passent `git restore --source=HEAD [--staged]
    [--worktree] -- <fichiers>` et `git checkout HEAD -- <fichiers>`, chaque
    fichier écrit en toutes lettres et présent dans `HEAD`, et `rm [-f]
    <fichiers>` d'un fichier apparu sous un chemin protégé que git ne suit
    pas. Un fichier que cite une demande dont ce qu'elle approuve n'est pas
    commité, lui ou son dossier, ne se remet pas : c'est peut-être la
    modification que l'humain y soumet. `texte`, la commande entière, fait
    refuser la remise quand elle change l'environnement de git ; `depart`,
    le dossier où elle part, situe ses chemins relatifs (B-0205)."""
    racine = projet.racine
    depart = depart or str(racine)

    def refus(chemins: list[str], pourquoi: str) -> tuple[list[str], str]:
        return chemins, trad("remise en état d'un fichier protégé refusée ({pourquoi}). Seule passe la remise "
                             "d'un fichier protégé changé par erreur, hors des réglages de Claude Code, à son état "
                             "du dernier commit, chaque chemin "
                             "écrit en toutes lettres : {formes}, ce dernier pour un fichier que git ne suit pas "
                             "(D-0098). Le reste revient à l'humain.", pourquoi=pourquoi,
                             formes=", ".join(REMISE_FORMES))

    if c.programme == "git":
        sous, reste = commandes.git_sous_commande(c.argv)
        if sous not in ("restore", "checkout"):
            return None
        if any(o.startswith(("--pathspec-from-file", "--pathspec-file-nul")) for o in reste):
            return refus([], trad("chemins lus dans un fichier"))
        if sous == "checkout" and "--" in reste:
            options, args = reste[:reste.index("--")], reste[reste.index("--") + 1:]
        elif sous == "checkout":
            options, args = commandes.options_et_arguments(reste)
            if len(args) > 1:
                options, args = options + args[:1], args[1:]
        else:
            options, args = commandes.options_et_arguments(reste)
        if sous == "checkout":
            forme = options == ["HEAD"]
        else:
            forme = "--source=HEAD" in options and set(options) <= REMISE_OPTIONS
        forme = forme and c.argv[1] == sous
        suivi = True
    elif c.programme == "rm":
        options, args = commandes.options_et_arguments(c.argv[1:])
        if not all(re.fullmatch(r"-[fv]+", o) for o in options):
            return None  # `rm -r` : une suppression, jugée comme toute écriture
        forme, suivi = True, False
    else:
        return None
    cache: dict = {}
    proteges = [(a, rel) for a in args if (rel := _relatif(racine, posixpath.join(depart, c.chemin(a)))) is not None
                and _protege(projet, rel, cache)]
    if not proteges:
        return None
    chemins = [rel for _, rel in proteges]

    if not forme:
        return refus(chemins, trad("forme de commande : une autre source que le dernier commit, ou d'autres "
                                   "options"))
    if c.prefixe or (texte and _environnement_change(texte)):
        return refus(chemins, trad("une variable, `env`, `export` ou un préfixe change l'environnement de la "
                                   "commande"))
    for brut, rel in proteges:
        if NON_LITTERAL.search(brut) or rel in ("", "."):
            return refus(chemins, trad("`{brut}` n'est pas un chemin écrit en toutes lettres", brut=brut))
        dans_head = outils.git(racine, "cat-file", "-t", f"HEAD:{rel}", check=False).strip() == "blob"
        if suivi and not dans_head:
            return refus(chemins, trad("`{rel}` n'est pas un fichier du dernier commit", rel=rel))
        if not suivi:
            indexe = bool(outils.git(racine, "ls-files", "--cached", "--", rel, check=False).strip())
            if dans_head or indexe or not (racine / rel).is_file() or (racine / rel).is_symlink():
                return refus(chemins, trad("`{rel}` n'est pas un fichier que git ne suit pas", rel=rel))
    for rel in chemins:
        d = _demande_qui_epargne(projet, rel)
        if d:
            return chemins, trad("`{rel}` est cité par la demande {id}, en attente, ou validée sans que ce "
                                 "qu'elle approuve soit commité : sa remise en état revient à l'humain (D-0098).",
                                 rel=rel, id=d.id)
    return chemins, None


def _branches_protegees(racine: Path) -> set[str]:
    defaut = outils.branche_par_defaut(racine) or ""
    return {"main", "master", defaut.split("/", 1)[-1]} - {""}


def irreversible(racine: Path, c: commandes.Commande) -> str | None:
    """L'action irréversible ou externe qu'une commande simple lance
    (politique, point 4), dite en clair ; `None` sinon."""
    nom, argv = c.programme, c.argv
    if nom == "git":
        sous, reste = commandes.git_sous_commande(argv)
        options, args = commandes.options_et_arguments(reste)
        if sous == "push":
            if commandes.drapeau(options, "f", ("--force", "--force-with-lease", "--force-if-includes")):
                return trad("push forcé")
            if commandes.drapeau(options, "d", ("--delete", "--prune")):
                return trad("suppression d'une branche distante")
            if commandes.drapeau(options, "", ("--mirror", "--all", "--tags")):
                return trad("push de toutes les références")
            refs = args[1:]
            if any(r.startswith("+") for r in refs):
                return trad("push forcé (+)")
            if any(r.startswith(":") for r in refs):
                return trad("suppression d'une branche distante")
            cibles = [r.split(":", 1)[-1].removeprefix("refs/heads/") for r in refs] or \
                [outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()]
            protegee = next((x for x in cibles if x in _branches_protegees(racine)), None)
            if protegee and protegee not in ("main", "master") and outils.branche_par_defaut_devinee(racine):
                return trad("push sur {protegee}, prise pour la branche par défaut faute de mieux : ce clone n'a ni "
                            "`origin/HEAD`, ni `main`, ni `master`. Si la branche par défaut du dépôt distant est "
                            "une autre, `git fetch origin <elle>` la fait connaître ; relancer ensuite le push",
                            protegee=protegee)
            return trad("push sur la branche par défaut ({protegee})", protegee=protegee) if protegee else None
        if sous == "reset" and "--hard" in options:
            return "git reset --hard"
        if sous in ("filter-branch", "filter-repo"):
            return f"git {sous}"
        return None
    if nom in ("npm", "cargo", "poetry", "uv", "pnpm", "yarn") and "publish" in argv[1:3]:
        return f"{nom} publish"
    if (nom, argv[1:2]) in (("twine", ["upload"]), ("gem", ["push"])):
        return f"{nom} {argv[1]}"
    if nom == "gh":
        sous = tuple(argv[1:3])
        if sous == ("pr", "merge") \
                or (sous[:1] == ("release",) and sous[1:] in (("create",), ("delete",), ("edit",))) \
                or (sous[:1] == ("repo",) and sous[1:] in (("create",), ("delete",), ("edit",), ("rename",),
                                                          ("archive",))) \
                or (sous[:1] == ("secret",) and sous[1:] in (("set",), ("delete",))):
            return "gh " + " ".join(sous)
        if sous[:1] == ("api",):
            for i, a in enumerate(argv):
                if a in ("-X", "--method") and i + 1 < len(argv):
                    methode = argv[i + 1]
                elif a.startswith("--method="):
                    methode = a.split("=", 1)[1]
                elif a.startswith("-X") and len(a) > 2:
                    methode = a[2:]
                else:
                    continue
                if methode.upper() in ("DELETE", "PUT", "PATCH"):
                    return f"gh api {methode.upper()}"
    if nom == "rm":
        options, args = commandes.options_et_arguments(argv[1:])
        if commandes.drapeau(options, "r", ("--recursive",)) or commandes.drapeau(options, "R"):
            for a in args:
                cible = c.chemin(a).rstrip("/")
                if a.rstrip("/*") in ("", "~", "$HOME") or cible == ".git" or cible.endswith("/.git"):
                    return f"rm -r {a}"
    return None


def contournement(racine: Path, c: commandes.Commande, depart: str | None = None) -> str | None:
    """Un `git commit`, `git merge` ou `git push` qui saute les hooks du
    dépôt du projet (`--no-verify`, ou `-n` pour un commit), dit en clair ;
    `None` sinon, et pour un autre dépôt, désigné par `-C` ou après un `cd`
    (un dépôt jetable) : seuls les hooks du projet y sont en jeu."""
    if c.programme != "git":
        return None
    sous, reste = commandes.git_sous_commande(c.argv)
    if sous not in ("commit", "merge", "push"):
        return None
    options, _ = commandes.options_et_arguments(reste)
    if not commandes.drapeau(options, "n" if sous == "commit" else "", ("--no-verify",)):
        return None
    globales = c.argv[1:len(c.argv) - len(reste) - 1]
    dossier = next((globales[i + 1] for i, x in enumerate(globales[:-1]) if x == "-C"), ".")
    cible = Path(c.chemin(dossier)).expanduser()
    if not cible.is_absolute():
        cible = Path(depart or racine) / cible
    try:
        cible.resolve().relative_to(racine.resolve())
    except ValueError:
        return None
    return f"git {sous} --no-verify"


# Les options de python qui prennent une valeur, collée ou séparée (B-0187).
OPTIONS_PYTHON_A_VALEUR = "WXQ"
OPTIONS_LONGUES_PYTHON_A_VALEUR = ("--check-hash-based-pycs",)


def options_de_python(args: list[str]) -> list[str] | None:
    """Les arguments de python après ses options, valeurs comprises
    (`-W ignore`, `-Xutf8`, `-bW error`) : le script en tête. `-m socle`
    rend `["-m socle", …]` ; `-c`, ou `-m` d'un autre module, `None` : ce
    n'est pas le lanceur du socle (B-0187)."""
    reste = list(args)
    while reste and reste[0].startswith("-") and reste[0] != "-":
        opt, reste = reste[0], reste[1:]
        if opt == "--":
            break
        if opt.startswith("--"):
            if opt in OPTIONS_LONGUES_PYTHON_A_VALEUR:
                reste = reste[1:]
            continue
        for i, lettre in enumerate(opt[1:], 1):
            colle = opt[i + 1:]
            if lettre in "cm":
                valeur = colle or (reste[0] if reste else "")
                reste = reste if colle else reste[1:]
                return ["-m socle", *reste] if lettre == "m" and valeur == "socle" else None
            if lettre in OPTIONS_PYTHON_A_VALEUR:
                if not colle:
                    reste = reste[1:]
                break
    return reste


def arguments_socle(c: commandes.Commande) -> list[str] | None:
    """Les arguments d'une invocation du socle, sous-commande en tête et
    options globales (`--root`) retirées, quel que soit le chemin du lanceur
    (entre guillemets, après un `cd`) ; `None` si la commande ne lance pas
    le socle."""
    argv = c.argv
    if not argv:
        return None

    def lanceur(chemin: str) -> bool:
        return posixpath.normpath(c.chemin(chemin)).endswith(".socle/socle") or chemin.endswith(".socle/socle")

    if re.fullmatch(r"python[\d.]*", c.programme):
        reste = options_de_python(argv[1:])
        if reste is None:
            return None
        if reste[:1] == ["-m socle"]:
            reste = reste[1:]
        elif not reste or not lanceur(reste[0]):
            return None
        else:
            reste = reste[1:]
    elif c.programme == "socle" or lanceur(argv[0]):
        reste = argv[1:]
    else:
        return None
    while reste and (reste[0] == "--root" or reste[0].startswith("--root=")):
        reste = reste[2:] if reste[0] == "--root" else reste[1:]
    return reste


def commande_humaine(c: commandes.Commande) -> tuple[str, list[str]] | None:
    """Une commande du socle réservée à l'humain (`answer`, `approve`,
    `reviewed`, `private install`), quel que soit le chemin du lanceur (entre
    guillemets, après un `cd`) : son nom et ses arguments ; `None` sinon."""
    reste = arguments_socle(c)
    if reste is None:
        return None
    if reste[:2] == ["private", "install"]:
        return "private install", reste
    if reste and reste[0] in ("answer", "decision", "approve", "reviewed"):
        return reste[0], reste
    return None


class _Repere:
    """L'interface d'une expression régulière (`search`), gardée pour les
    appelants d'avant le découpage des commandes : elle trouve une
    INVOCATION, pas un texte qui la nomme."""

    def __init__(self, noms: tuple[str, ...]):
        self.noms = noms

    def search(self, cmd: str):
        for c in commandes.analyser(cmd):
            h = commande_humaine(c)
            if h and h[0] in self.noms:
                return _Trouve(h[0])
        return None


class _Trouve:
    def __init__(self, nom: str):
        self.nom = nom

    def group(self, *_):
        return self.nom


def _valeur_option(args: list[str], nom: str, defaut: str) -> str:
    """La valeur d'une option longue (`--nom x` ou `--nom=x`), la dernière
    donnée l'emportant, comme pour `argparse`."""
    valeur = defaut
    for i, x in enumerate(args):
        if x == nom and i + 1 < len(args):
            valeur = args[i + 1]
        elif x.startswith(nom + "="):
            valeur = x.split("=", 1)[1]
    return valeur


def _cible_illisible(texte: str) -> bool:
    """Un chemin que le hook ne sait pas résoudre comme le shell le fera :
    une substitution (`$D`, `$(pwd)`, un accent grave), que le shell neuf de
    chaque appel peut rendre vide ou changer, ou un `~` autre que le dossier
    de l'utilisateur (`~autre`, `~+`)."""
    if "$" in texte or "`" in texte:
        return True
    return texte.startswith("~") and os.path.expanduser(texte).startswith("~")


def installeur_hors_mode(projet: config.Projet, c: commandes.Commande,
                         depart: str | None = None) -> tuple[str, str, str] | None:
    """L'installeur (`socle install`) lancé sur un projet équipé dans un autre
    mode que celui de son verrou (ADR-0062) : sa cible, le mode demandé et
    celui du verrou ; `None` sinon. Le projet équipé est la racine du projet,
    ou toute cible qui porte son propre verrou (un worktree, une copie).
    Une cible sans verrou, une première installation dans un dossier
    temporaire, passe ; la mise à jour dans le mode du verrou aussi.
    Une cible que le hook ne sait pas résoudre, elle ou le `cd` qui la
    précède (une variable, une substitution, `~autre`), rend un mode du
    verrou vide : le hook refuse, faute de savoir ce qu'elle vise. Aucune
    exception n'en sort : le hook qui lèverait laisserait passer toute la
    commande sans la juger."""
    reste = arguments_socle(c)
    if not reste or reste[0] != "install":
        return None
    args = reste[1:]
    demande = _valeur_option(args, "--mode", config.MODE_PROJET)
    brute = c.chemin(_valeur_option(args, "--target", "."))
    if _cible_illisible(brute) or _cible_illisible(c.dossier):
        return (brute, demande, "")
    try:
        cible = Path(os.path.expanduser(brute))
        if not cible.is_absolute():
            cible = Path(depart or projet.racine) / cible
        cible = cible.resolve()
    except (OSError, RuntimeError, ValueError):
        return (brute, demande, "")
    if cible == projet.racine.resolve():
        verrou = projet.lock
    else:
        try:
            verrou = config.lire_toml((cible / projet.chemins.lock).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    if not verrou:
        return None
    attendu = verrou.get("mode", config.MODE_PROJET)
    return (str(cible), demande, attendu) if demande != attendu else None


COMMANDES_HUMAINES = _Repere(("answer", "decision", "approve", "reviewed"))
INSTALLER_PRIVE = _Repere(("private install",))


def refus_bash(projet: config.Projet, cmd: str, cwd: str | None = None) -> str | None:
    """La raison pour laquelle le hook refuse une commande du shell, ou rien :
    le même jugement pour une commande que l'agent lance et pour une
    commande qu'un skill lui ferait lancer (`skills.commandes`)."""
    racine = projet.racine
    limite = time.monotonic() + DELAI_JUGEMENT
    # Une commande trop longue ou trop imbriquée ne se découpe pas : elle
    # dépasserait le délai du hook, ou épuiserait la pile de python.
    trop = injugeable(cmd)
    if trop:
        return trop
    # Chaque commande simple, découpée : ce qu'elle lance, pas le texte
    # qu'elle cite (un heredoc, un message de commit).
    try:
        simples = commandes.analyser(cmd)
    except Exception as e:  # ce qui ne se découpe pas ne passe pas, s'il peut écrire
        raison = injugeable(cmd, e)
        if raison:
            return raison
        raise
    en_plus = projet.pol("irreversible", "bash", defaut=IRREVERSIBLES_BASH) or []
    for c in simples:
        action = irreversible(racine, c) or next(
            (" ".join(c.argv)[:120] for m in en_plus if re.search(m, " ".join(c.argv))), None)
        if action:
            return trad("commande irréversible ou externe ({action}) : « {commande} » — validation humaine "
                        "requise (politique, point 4), et une demande validée ne la débloque pas : "
                        "l'action revient à l'humain. Si c'est une décision, émettre une demande "
                        "`D-NNNN` ; une fois l'action décidée, l'inscrire au backlog avec `pour : humain`, "
                        "sa commande exacte, où la lancer et ce qu'elle doit produire. Puis continuer sur "
                        "autre chose.",
                        action=action, commande=cmd.strip()[:200])
        saut = contournement(racine, c, cwd)
        if saut:
            return trad("`{saut}` contourne les hooks du projet : la CI exécute tout, et rien ne la "
                        "contourne. Corriger ce que le hook refuse ; s'il refuse à tort, l'inscrire au "
                        "backlog et le dire à l'humain.", saut=saut)
        hors_mode = installeur_hors_mode(projet, c, cwd)
        if hors_mode and not hors_mode[2]:
            return trad("l'installeur visé sur une cible que le hook ne sait pas résoudre (« {cible} ») : une "
                        "variable, une substitution ou un `~` autre que le dossier de l'utilisateur, dans la cible "
                        "ou dans le `cd` qui la précède. Chaque appel repart d'un shell neuf, où une variable est "
                        "vide : la cible serait le dossier courant, le projet. Écrire le chemin en toutes lettres, "
                        "absolu, par exemple celui que `mktemp -d` a rendu.", cible=hors_mode[0])
        if hors_mode:
            return trad("l'installeur visé sur un projet équipé ({cible}) en mode « {demande} », dans un autre "
                        "mode que celui de son verrou (« {attendu} ») : il en réécrirait le verrou, les hooks, "
                        "la CI et CODEOWNERS. La mise à jour se relance dans le mode du verrou (`--mode "
                        "{attendu}`) ; pour éprouver l'installeur, viser un dossier temporaire créé hors du "
                        "dépôt. Changer de mode revient à l'humain.",
                        cible=hors_mode[0], demande=hors_mode[1], attendu=hors_mode[2])
        h = commande_humaine(c)
        if h and h[0] == "private install":
            return trad("`socle private install` est réservé à l'humain : il pousse vers le dépôt privé "
                        "et crée une clé de déploiement (politique, point 4). L'inscrire au backlog avec "
                        "`pour : humain`.")
        if h and h[0] == "approve":
            return trad("`socle approve` est réservé à l'humain : il valide ses propres changements "
                        "protégés.")
        # Les drapeaux du relais se cherchent dans la commande elle-même,
        # pas ailleurs dans le texte.
        relais = "--relayed" in h[1] and any(x.split("=", 1)[0] in ("--quote", "--quote-file") for x in h[1]) \
            if h else True
        # L'aide seule (`socle answer --help`) ne répond à rien (B-0184) ;
        # glissée parmi d'autres arguments, elle ne fait rien passer.
        if h and h[0] in ("answer", "decision", "reviewed") and h[1][1:] in (["--help"], ["-h"]):
            relais = True
        if not relais:
            return trad("l'agent ne répond jamais à la place de l'humain. Il ne peut que relayer une "
                        "réponse donnée dans la conversation : `socle answer D-NNNN <réponse> --relayed "
                        "--by <nom> --quote-file <texte exact>`, `socle decision "
                        "\"<question>\" <réponse> --relayed --by <nom> --quote-file <texte exact>` pour une "
                        "décision prise en séance, ou `socle reviewed --relayed --by <nom> "
                        "--quote-file <texte exact>` pour une relecture avant publication.")
    faute = _fuite_bash(projet, cmd, cwd)
    if faute:
        return faute
    depart = depart_de(racine, cwd)
    # Chaque chemin écrit, développé comme le shell le ferait (B-0171),
    # depuis le dossier courant de l'agent (B-0205), dans le délai.
    try:
        remises = []
        for c in simples:
            _dans_le_delai(limite)
            remises.append((c, remise_en_etat(projet, c, cmd, depart)))
        refusee = next((r[1] for _, r in remises if r is not None and r[1]), None)
        if refusee:
            return refusee
        jugees = ecritures_jugees(projet, cmd, cwd, limite)
    except Exception as e:  # ce qui ne se juge pas ne passe pas, s'il peut écrire
        raison = injugeable(cmd, e)
        if raison:
            return raison
        raise
    # Supprimer le projet, ou un dossier qui le contient : rien ne le
    # rattrape ensuite (B-0208, ADR-0080).
    supprime = next((quoi for genre, quoi in jugees if genre == "supprime"), None)
    if supprime:
        return trad("suppression par le shell d'un dossier qui contient le projet, ou peut le contenir ({quoi}) : "
                    "elle emporterait le code, la mémoire, la politique et les hooks, et aucun contrôle ne la "
                    "rattrape ensuite. Viser un dossier du projet, ou hors de lui un dossier qui ne le contient pas "
                    "(`/tmp/…`), son chemin écrit en toutes lettres (B-0208).", quoi=supprime)
    # Les réglages de Claude Code restent à l'humain, remise comprise
    # (sa réponse : « Exclure »).
    reglage = next((x for c in simples for x in ecrits(c) if REGLAGES_AGENT.search(x)), None) or next(
        (quoi for genre, quoi in jugees if genre == "reglage"), None)
    if reglage:
        return trad("`{reglage}` : les réglages de Claude Code commandent ses hooks, seul l'humain les "
                    "modifie (un réglage local peut les couper tous).", reglage=reglage)
    cible = next((quoi for genre, quoi in jugees if genre == "protege"), None)
    illisible = next((quoi for genre, quoi in jugees if genre == "illisible"), None)
    if not cible and illisible:
        return trad("écriture par le shell vers un chemin que le hook ne sait pas développer : {quoi}. Une "
                    "variable que ni l'environnement du hook ni la commande ne donnent, une substitution de "
                    "commande (`$(…)`, accents graves) ou un `cd` vers un tel chemin peuvent viser un fichier "
                    "protégé ; un tel chemin ne passe que si la part écrite en toutes lettres qui le précède, "
                    "remontée des `..` qui le suivent, le place hors du projet (`/tmp/$X`). Écrire le chemin en "
                    "toutes lettres, ou affecter la variable plus tôt dans la même commande (`F=/tmp/x; echo y > "
                    "\"$F\"`) (B-0171).", quoi=illisible)
    if cible:
        return trad("écriture d'un fichier protégé ({cible}) par le shell : seul l'humain modifie la "
                    "politique, les hooks, la CI et le moteur (relance de l'installeur). Un fichier protégé "
                    "changé par erreur, hors des réglages de Claude Code, se remet à son état du dernier "
                    "commit : {formes} (D-0098).", cible=cible,
                    formes=", ".join(REMISE_FORMES))
    return None


# Le widget de questions de l'agent (B-0105) : l'humain y lit un texte brut,
# sans liens à suivre, et n'y répond qu'à des options écrites par l'agent.
QUESTIONS_AGENT = ("AskUserQuestion",)


def pre_tool_use(projet: config.Projet, entree: dict) -> int:
    """Le hook avant outil. Tout se juge contre la racine de la session,
    comme toujours ; si l'action a lieu dans un autre worktree du même dépôt
    (`arbre_juge`), elle se juge en plus contre lui : refusée dans l'un des
    deux arbres, elle est refusée. Seule une référence citée vaut si elle
    existe dans l'un ou l'autre (B-0164)."""
    racine = projet.racine
    outil = entree.get("tool_name", "")
    tracer(racine, "PreToolUse", entree.get("session_id", ""), outil)
    arbre = arbre_juge(racine, entree)
    autre = config.Projet.charger(arbre) if arbre != racine else None
    raison = _raison_avant_outil(projet, entree, autre)
    if raison is None and autre is not None:
        raison = _raison_avant_outil(autre, entree, projet)
    if raison is None:
        return 0
    tracer_refus(racine, "PreToolUse", f"{outil} — {raison}", entree.get("session_id", ""))
    return _refus(raison)


def _raison_avant_outil(projet: config.Projet, entree: dict, autre: config.Projet | None) -> str | None:
    """Ce que le hook avant outil refuse, jugé contre `projet` ; `autre`, le
    second arbre jugé, ne sert qu'à lire les références qu'il définit."""
    racine = projet.racine
    outil = entree.get("tool_name", "")
    args = entree.get("tool_input") or {}

    def refus(raison: str) -> str:
        return raison  # la raison, que `pre_tool_use` trace et rend

    if outil in QUESTIONS_AGENT:
        return refus(trad("une question à l'humain ne passe pas par le widget de questions de l'agent : son texte y "
                          "est brut et ses liens ne s'y suivent pas. Une décision qui demande du contexte (approuver "
                          "un document, choisir entre des options) s'écrit en demande (`socle new request`), dont le "
                          "lien se donne dans la conversation ; une question courte se pose dans le texte de la "
                          "réponse."))

    motifs_outils = projet.pol("irreversible", "tools", defaut=IRREVERSIBLES_OUTILS)
    for m in motifs_outils:
        if re.fullmatch(m, outil):
            return refus(trad("action externe ou irréversible ({outil}) : validation humaine requise (politique, "
                              "point 4), et une demande validée ne la débloque pas : l'action revient à "
                              "l'humain. Émettre une demande, travailler sur autre chose en attendant.", outil=outil))

    if outil == "Bash":
        raison = refus_bash(projet, args.get("command", ""), entree.get("cwd"))
        if raison:
            return refus(raison)

    faute = _fuite_outil(projet, outil, args)
    if faute:
        return refus(faute)

    if outil in OUTILS_ECRITURE:
        chemin = args.get("file_path") or args.get("notebook_path") or ""
        if REGLAGES_AGENT.search(chemin.replace(os.sep, "/")):
            return refus(trad("`{chemin}` : les réglages de Claude Code commandent ses hooks, seul l'humain les "
                              "modifie (un réglage local peut les couper tous).", chemin=chemin))
        rel = _relatif(racine, chemin)
        if rel and outils.correspond(rel, projet.chemins_proteges()):
            return refus(trad("`{rel}` est protégé par la politique : seul l'humain le modifie (CODEOWNERS), ou "
                              "l'installeur pour les hooks, la CI et le moteur. Proposer le changement par une "
                              "demande.", rel=rel))
        if rel and rel.endswith(".md"):
            avant, apres = contenu_apres(racine, outil, args, rel)
            if apres is not None:
                fautes, vieux = references_refusees(projet, rel, avant, apres)
                if fautes and autre is not None:
                    # Une référence vaut si elle existe dans l'autre arbre.
                    rel_autre = _relatif(autre.racine, chemin)
                    av, ap = contenu_apres(autre.racine, outil, args, rel_autre) if rel_autre else (None, None)
                    if ap is not None and not references_inventees(autre, rel_autre, av, ap):
                        fautes = []
                if fautes:
                    return refus(trad("référence inventée — {fautes}", fautes=" ; ".join(fautes[:5])))
                if vieux:
                    return refus(trad("ancien numéro — {fautes}", fautes=" ; ".join(vieux[:5])))
                faute = statut_valide_ajoute(rel, avant, apres, projet)
                if faute:
                    return refus(faute)
                if memoire.couche_attendue(rel) == "demandes":
                    d = demandes.charger(racine, None, rel, apres)
                    if d.reponse is None:
                        fautes = demandes.linter(d, projet)
                        if fautes:
                            return refus(trad("demande hors contrat (elle doit se lire sans le projet en tête) "
                                              "— {fautes} ; la procédure : le skill `socle-request`",
                                              fautes=" ; ".join(fautes[:8])))

    faute = sha_fabrique(racine, json.dumps(args, ensure_ascii=False))
    if faute:
        return refus(faute)
    return None


# --------------------------------------------------------------------------
# Fuites de la mémoire privée : le hook de l'agent voit, avant
# qu'elles partent, les écritures et les publications que ni les hooks git ni
# la CI ne voient à temps (une description de pull request, un commentaire).
# --------------------------------------------------------------------------


def _vers_le_prive(racine: Path, cmd: str) -> bool:
    return bool(re.search(r"(?:-C|cd)\s+(?:\S*/)?" + re.escape(memoire.DOSSIER_PRIVE), cmd))


def _fuites_dans(projet: config.Projet, texte: str) -> str | None:
    t = prive.termes(projet)
    trouve = prive.fuites(texte, t.liste)
    if not trouve:
        return None
    return trad("fuite de la mémoire privée : {termes}. Une écriture publique ne cite ni identifiant privé ni "
                "terme de la liste privée : reformuler sans eux (politique, mémoire privée ; le skill "
                "`socle-private-memory`).",
                termes=", ".join(trouve[:5]))


# Les options qui publient le contenu d'un fichier (corps d'une pull request,
# notes d'une version, message de commit) : il part comme s'il était écrit
# dans la commande.
OPTIONS_FICHIER = {"--body-file", "--notes-file", "--file", "-F", "--field", "-f", "--raw-field"}


def textes_publies(racine: Path, simples: list, cwd: str | None = None) -> list[str]:
    """Ce que les commandes `git` et `gh` publient depuis un fichier :
    `--body-file x`, `-F x`, et `gh api -F champ=@x`. Un chemin relatif se
    lit depuis le dossier courant de l'agent (`cwd`) s'il est connu, sinon
    depuis la racine, et après les `cd` de la commande (B-0205)."""
    depart = Path(depart_de(racine, cwd))
    res = []
    for c in simples:
        if c.programme not in ("git", "gh"):
            continue
        api = c.programme == "gh" and c.argv[1:2] == ["api"]
        for i, x in enumerate(c.argv[1:], 1):
            nom, egal, valeur = x.partition("=") if x.startswith("--") else (x, "", "")
            if nom not in OPTIONS_FICHIER:
                continue
            if not egal:
                valeur = c.argv[i + 1] if i + 1 < len(c.argv) else ""
            if api or nom in ("--field", "-f", "--raw-field"):
                if "=@" not in valeur:
                    continue  # un champ écrit dans la commande, déjà lu avec elle
                valeur = valeur.split("=@", 1)[1]
            if valeur in ("", "-"):
                continue
            chemin = Path(os.path.expanduser(c.chemin(valeur)))
            try:
                res.append((chemin if chemin.is_absolute() else depart / chemin).read_text(
                    encoding="utf-8", errors="replace")[:1_000_000])
            except OSError:
                continue
    return res


def _noms_publies(racine: Path, simples: list) -> list[str]:
    """Les noms de branche qu'une commande crée ou pousse : publiés eux
    aussi."""
    res = []
    for c in simples:
        if c.programme != "git":
            continue
        sous, reste = commandes.git_sous_commande(c.argv)
        if sous in ("push", "checkout", "switch", "branch"):
            res += commandes.options_et_arguments(reste)[1]
        if sous == "push":
            res.append(outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip())
    return res


def _fuite_bash(projet: config.Projet, cmd: str, cwd: str | None = None) -> str | None:
    if prive.mode(projet) is None or _vers_le_prive(projet.racine, cmd):
        return None
    if PUSH_BASH.search(cmd):
        tete = outils.git(projet.racine, "rev-parse", "HEAD", check=False).strip()
        refus = prive.publication_refusee(projet, [tete])
        if refus:
            return refus
    simples = commandes.analyser(cmd)
    publie = _noms_publies(projet.racine, simples)
    if PUBLIE_BASH.search(cmd):
        publie += [cmd] + textes_publies(projet.racine, simples, cwd)
    return _fuites_dans(projet, "\n".join(publie)) if publie else None


def _fuite_outil(projet: config.Projet, outil: str, args: dict) -> str | None:
    if prive.mode(projet) is None:
        return None
    if outil.startswith("mcp__"):
        return _fuites_dans(projet, json.dumps(args, ensure_ascii=False))
    if outil in OUTILS_ECRITURE:
        rel = _relatif(projet.racine, args.get("file_path") or args.get("notebook_path") or "")
        if not rel or prive.est_prive(rel):
            return None
        avant, apres = contenu_apres(projet.racine, outil, args, rel)
        if apres is None:
            return None
        # Seul ce qui s'ajoute compte : une fuite plus ancienne ne bloque pas
        # chaque écriture suivante du même fichier. Le nom d'un fichier
        # nouveau est publié comme son contenu.
        anciennes = set((avant or "").splitlines())
        ajout = "\n".join(l for l in apres.splitlines() if l not in anciennes)
        return _fuites_dans(projet, (rel + "\n" if avant is None else "") + ajout)
    return None


# --------------------------------------------------------------------------
# Stop
# --------------------------------------------------------------------------


def _empreinte_arbre(racine: Path) -> str:
    """L'arbre tel qu'une vérification l'a vu (`outils.empreinte_arbre`)."""
    return outils.empreinte_arbre(racine)


def signature_d_echec(racine: Path, echecs: list[str]) -> str:
    """Ce qui distingue un échec de fin de tour d'un autre : l'arbre que les
    contrôles ont vu et les contrôles en échec, sans le texte des erreurs.
    Pour une étape de l'adaptateur, ce texte est la fin de la sortie de
    l'outil, qui change à chaque relance (une durée, « Ran N tests in
    X.XXXs ») : il ferait de chaque relance un échec nouveau. Deux
    tentatives de même signature n'ont rien changé (B-0143)."""
    return outils.sha256(_empreinte_arbre(racine) + "\n" + "\n".join(echecs))[:16]


def stop(projet: config.Projet, entree: dict) -> int:
    from socle import context as contexte, verification

    racine = projet.racine
    tracer(racine, "Stop", entree.get("session_id", ""))
    compteur = racine / config.COMPTEUR_STOP
    session = entree.get("session_id", "")
    base = outils.base_de_travail(racine)
    ctx = contexte.Contexte(projet, etage="agent", base=base, tete=None, rapide=True)
    rapport = contexte.executer(ctx)

    # Les capacités rapides de l'adaptateur, seulement si du code a changé, et
    # pas sur un arbre où elles ont déjà passé (la vérification que l'agent
    # vient de lancer) : inutile de payer une compilation de plus. Un fichier
    # de tests que l'adaptateur déclare compte comme du code (B-0182).
    if outils.filtrer(ctx.changes, projet.chemins_code()) or projet.fichiers_de_tests(ctx.changes):
        verification.etapes_rapides(projet, rapport)

    # Le seuil des étapes rapides avertit et n'échoue jamais : il ne bloque
    # pas la fin de tour, qui le dit à l'humain, qu'elle passe ou qu'elle
    # bloque pour un autre contrôle (B-0258).
    duree = "\n".join(_avertissements(rapport, (verification.CONTROLE_DUREE,))) or None
    if rapport.reussi:
        compteur.unlink(missing_ok=True)
        return exiger_recap(projet, entree, avertissement=duree)
    # Le compteur appartient à sa session : une session nouvelle ne commence
    # pas à l'escalade sur les échecs d'une autre (relevé de la passe de
    # recul, F).
    cle = session or "-"
    # Les fichiers qu'une mise à jour a posés, en une ligne : relue à chaque
    # tentative, la liste n'apprend rien que `socle check` ne redise (ADR-0077).
    texte = rapport.texte(trad("contrôles de fin de tour (`socle check --stage agent`)"), regrouper=True)
    signature = signature_d_echec(racine, rapport.controles_en_echec())
    precedent = compteur.read_text().split() if compteur.is_file() else []
    sien = len(precedent) >= 2 and precedent[1] == cle and precedent[0].isdigit()
    # B-0143 (ADR-0061) : une relance que le hook a lui-même provoquée, sur le
    # même échec et le même arbre, ne peut rien apporter ; elle ne bloque
    # plus. L'humain lit le rapport dans le message du hook ; le commit et la
    # CI refusent toujours. Le compteur ne bouge pas : la relance n'était pas
    # une tentative, et le premier arrêt du tour suivant bloque de nouveau.
    if entree.get("stop_hook_active") and sien and precedent[2:] == [signature]:
        tracer(racine, "Stop-inchange", session, ",".join(rapport.controles_en_echec()))
        print(json.dumps({"systemMessage": trad(
            "Les contrôles échouent encore, sans changement depuis la tentative précédente : le hook ne relance "
            "plus ce tour, que l'agent n'a pas pu corriger. À l'humain de regarder ; le commit et la CI refusent "
            "toujours.\n\n{rapport}", rapport=texte)}, ensure_ascii=False))
        return 0
    essais = int(precedent[0]) + 1 if sien else 1
    compteur.parent.mkdir(parents=True, exist_ok=True)
    compteur.write_text(f"{essais} {cle} {signature}")
    if essais >= projet.maximum_tentatives():
        compteur.unlink(missing_ok=True)
        print(json.dumps({"systemMessage": trad(
            "Les contrôles échouent encore après {essais} tentatives : ARRÊT ET ESCALADE (politique, point 7). "
            "Écrire une demande `D-NNNN` qui résume l'échec, ce qui a été tenté et ce qui est supposé, "
            "puis s'arrêter.\n\n{rapport}", essais=essais, rapport=texte)}, ensure_ascii=False))
        return 0
    tracer_refus(racine, "Stop", ",".join(rapport.controles_en_echec()), entree.get("session_id", ""))
    sortie = {"decision": "block", "reason": trad(
        "Les contrôles échouent (tentative {essais}/{maximum}) : corriger avant de conclure. Si tu ne peux pas "
        "corriger (un fichier que tu n'as pas le droit de remettre), réponds en une ligne qui dit pourquoi, sans "
        "redire ton récap : une relance sur le même échec et le même arbre ne bloque plus, et l'humain reçoit le "
        "rapport.\n\n{rapport}",
        essais=essais, maximum=projet.maximum_tentatives(), rapport=texte)}
    # La raison, rapport compris, n'est lue que de l'agent ; les deux
    # messages plus haut portent le rapport à l'humain. Le seuil dépassé lui
    # est dit ici, une fois : la relance sur le même arbre ne relance pas les
    # étapes, qui ne le rediraient pas (B-0258).
    if duree:
        sortie["systemMessage"] = duree
    print(json.dumps(sortie, ensure_ascii=False))
    return 0


def _appels_externes(racine: Path, session: str) -> bool:
    """Un outil externe (`mcp__…` : pull request, commentaire…) a-t-il été
    appelé depuis la fin de tour précédente de cette session ?"""
    if not session:
        return False
    lignes = [l.split("\t") for l in config.lire_trace(racine)]
    siennes = [l for l in lignes if len(l) >= 4 and l[2] == session]
    stops = [i for i, l in enumerate(siennes) if l[1] == "Stop"]
    debut = stops[-2] + 1 if len(stops) >= 2 else 0
    return any(l[1] == "PreToolUse" and l[3].startswith("mcp__") for l in siennes[debut:])


def exiger_recap(projet: config.Projet, entree: dict, avertissement: str | None = None) -> int:
    """Un tour où l'agent a agi se termine par un récap et deux lignes,
    `Pour toi :` et `Ensuite :`. Tout dernier message,
    qu'il ait agi ou non, ne donne que des liens que l'humain peut suivre.
    `avertissement`, celui des étapes rapides que la fin de tour vient de
    lancer, ne change rien à ce jugement : il se joint au message à
    l'humain, et à la raison donnée à l'agent si le hook bloque (B-0258)."""
    from socle import human as humain, links as liens

    racine = projet.racine
    fichier = racine / ".socle/trace/derniere-fin-de-tour"
    marque = _empreinte_arbre(racine) if outils.a_des_commits(racine) else ""
    a_agi = (not fichier.is_file() or fichier.read_text().strip() != marque
             or _appels_externes(racine, entree.get("session_id", "")))

    def retenir():
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(marque)

    def dire(sortie: dict | None) -> int:
        if avertissement:
            sortie = dict(sortie or {})
            sortie["systemMessage"] = "\n\n".join(x for x in (sortie.get("systemMessage"), avertissement) if x)
            if sortie.get("decision") == "block":
                sortie["reason"] += "\n\n" + avertissement
        if sortie:
            print(json.dumps(sortie, ensure_ascii=False))
        return 0

    chemin = entree.get("transcript_path")
    message = humain.dernier_message(Path(chemin)) if chemin else None
    if message is None:
        if a_agi:
            retenir()
            return dire({"systemMessage": trad("récap de fin d'intervention non vérifiable : transcript illisible")})
        return dire(None)
    manque = humain.recap_manquant(projet, message) if a_agi else []
    morts, sans_lien = liens.problemes(projet, message)
    if not (manque or morts or sans_lien):
        if a_agi:
            retenir()
        return dire(None)
    if entree.get("stop_hook_active"):
        if a_agi:
            retenir()
        defauts = ([trad("sans {manque}", manque=trad(" ni ").join(manque))] if manque else []) + (
            [trad("{n} lien(s) que l'humain ne pourra pas suivre", n=len(morts) + len(sans_lien))]
            if morts or sans_lien else [])
        return dire({"systemMessage": trad("fin d'intervention {defauts}, malgré un rappel",
                                           defauts=", ".join(defauts))})
    raisons = []
    if manque:
        liste = "\n".join(humain.texte(humain.a_faire(projet)))
        suite = humain.prochaines_etapes(projet) or trad("(le chantier actif n'a pas de section « Prochaines "
                                                         "étapes »)")
        ordre = memoire.lignes_ordre(memoire.Memoire.charger(projet.racine))
        if ordre:
            suite += "\n\n" + trad("Selon l'ordre du backlog :") + "\n" + "\n".join(f"- {l}" for l in ordre)
        raisons.append(trad(
            "Tu as agi pendant ce tour, et ton dernier message n'a pas {manque}. Termine par un récap de ce qui a "
            "été fait, puis, en texte, hors de tout bloc de code :\n"
            "- « Pour toi : » ce qui revient à l'humain — décisions, actions qu'il est seul à pouvoir faire — ou "
            "« rien » ;\n"
            "- « Ensuite : » la suite proposée (prochain jalon, ce qu'il reste à faire avant), et ce que tu "
            "attends, s'il y a lieu (une CI, un match : quoi, et jusqu'à quand).\n\n"
            "Ce qui revient à l'humain, calculé maintenant :\n{liste}\n\n"
            "Prochaines étapes, selon le chantier actif :\n{suite}",
            manque=trad(" ni ").join(manque), liste=liste, suite=suite))
    if morts:
        raisons.append(trad(
            "Ton dernier message contient des liens que l'humain ne pourra pas suivre : il lit dans la "
            "conversation ou sur GitHub, pas dans ton conteneur.\n{liens}\nDonne un fichier par son permalien "
            "(`socle url <chemin|ID>`, après le push) ; n'écris entre accents graves que des chemins qui existent "
            "dans ce dépôt, et ceux d'un autre dépôt sous la forme `depot:chemin`.",
            liens="\n".join(f"- {m}" for m in morts)))
    if sans_lien:
        raisons.append(trad(
            "Ton dernier message cite {demandes}, en attente de l'humain, sans son lien : il doit pouvoir l'ouvrir "
            "d'un clic. Ajoute la sortie de `socle url {ids}`.",
            demandes=", ".join(sans_lien), ids=" ".join(sans_lien)))
    tracer_refus(racine, "Stop", ",".join(x for x, oui in (("recap", manque), ("liens", morts), ("lien-de-demande", sans_lien))
                                         if oui), entree.get("session_id", ""))
    return dire({"decision": "block", "reason": "\n\n".join(raisons)})


# --------------------------------------------------------------------------
# Hooks git
# --------------------------------------------------------------------------


def git_pre_commit(projet: config.Projet) -> int:
    from socle import context as contexte

    tracer(projet.racine, "git-pre-commit")
    sans_filtre = filtre_absent(projet)
    if sans_filtre:
        from socle.checks_ratchet import REMEDE_HOOKS

        tracer_refus(projet.racine, "git-pre-commit", "hooks.filtre")
        if hooks_non_charges(projet):
            print(trad("socle — commit refusé : commit d'agent sans aucun passage du filtre de l'agent depuis le "
                       "commit précédent (`{depuis}`) : ses hooks ne sont pas chargés. {remede}", depuis=sans_filtre,
                       remede=trad(REMEDE_HOOKS)), file=sys.stderr)
        else:
            # Le filtre vient de passer pour la session : c'est un second commit
            # dans la même commande que le précédent.
            print(trad("socle — commit refusé : un second commit dans la même commande que le précédent. Le "
                       "filtre de l'agent ne passe qu'une fois par commande, et chaque commit d'agent doit le "
                       "passer : lancer ce commit dans une commande à part."), file=sys.stderr)
        return 1
    base = outils.base_de_travail(projet.racine)
    # On juge ce qui sera commité : l'index, figé en arbre par `write-tree`,
    # et non les fichiers sur disque, qui peuvent cacher un défaut indexé ou
    # en montrer un qui ne sera pas commité.
    index = outils.arbre_de_l_index(projet.racine)
    ctx = contexte.Contexte(projet, etage="git", base=base, tete=index, rapide=True)
    rapport = contexte.executer(ctx)
    if not rapport.reussi:
        tracer_refus(projet.racine, "git-pre-commit", ",".join(rapport.controles_en_echec()))
        rapport.afficher(trad("socle — contrôles avant commit"), flux=sys.stderr, court=True)
        if "protege.fichiers" in rapport.controles_en_echec():
            print(trad("\nFichiers protégés : si c'est l'humain qui les a changés (une mise à jour du socle, sa "
                       'politique), `python3 .socle/socle approve --text "<raison>"` les liste et les approuve — '
                       "réservé à l'humain ; l'agent, lui, ouvre une demande."), file=sys.stderr)
        print(trad("\nCommit refusé. `git commit --no-verify` contourne ce hook, jamais la CI."), file=sys.stderr)
        return 1
    _dire_avertissements(rapport)
    return 0


def compter_session(racine: Path, session: str | None = None) -> str:
    """`SessionStart=1 PreToolUse=12 Stop=3` pour la session donnée, ou à
    défaut la plus récente de la trace ; `aucun` sans trace. Le commit d'une
    session dont les hooks sont coupés compte ainsi zéro, au lieu d'emprunter
    la trace d'une session plus ancienne."""
    lignes = [l.split("\t") for l in config.lire_trace(racine)]
    agent = [l for l in lignes if len(l) >= 3 and l[1] in ("SessionStart", "PreToolUse", "Stop")]
    if not agent and not session:
        return "aucun"
    session = session or next((l[2] for l in reversed(agent) if l[2]), "")
    de_la_session = [l for l in agent if l[2] == session]
    compte = {e: sum(1 for l in de_la_session if l[1] == e) for e in ("SessionStart", "PreToolUse", "Stop")}
    if compte["SessionStart"] == 0 and installe_pendant(lignes, session):
        return f"SessionStart=installation PreToolUse={compte['PreToolUse']} Stop={compte['Stop']}"
    return " ".join(f"{k}={v}" for k, v in compte.items())


def installe_pendant(lignes: list[list[str]], session: str) -> bool:
    """Le socle a été installé PENDANT cette session : la première trace de
    la session suit l'installation. Son SessionStart a eu lieu avant que le
    hook n'existe, et ses hooks tirent dès l'appel d'outil suivant (F-0003)."""
    premier = next((i for i, l in enumerate(lignes) if len(l) >= 3 and l[2] == session), None)
    return premier is not None and premier > 0 and lignes[premier - 1][1] == "Install"


def compter_depuis_le_commit(racine: Path, session: str | None = None, tous: bool = False) -> str:
    """`PreToolUse=3` : les passages du filtre de l'agent depuis le commit
    précédent du même worktree (sa ligne `git-prepare-commit-msg` dans la
    trace, qui nomme son worktree ; une ligne qui n'en nomme aucun vaut pour
    tous), pour la session donnée ou, à défaut, la plus récente depuis. La
    trace est commune aux worktrees : un commit dans un autre ne fait pas du
    suivant un second commit de la même commande (B-0136). La commande qui
    commite passe elle-même par le filtre : des hooks chargés en comptent
    toujours au moins un. Le compte de toute la session ne voit pas des hooks
    qui cessent de tirer en cours de route. `tous` : depuis le commit
    précédent de n'importe quel worktree."""
    lignes = [l.split("\t") for l in config.lire_trace(racine)]
    ici = worktree(racine)
    debut = next((i + 1 for i in range(len(lignes) - 1, -1, -1)
                  if len(lignes[i]) >= 2 and lignes[i][1] == "git-prepare-commit-msg"
                  and (tous or len(lignes[i]) < 4 or lignes[i][3] in ("", ici))), 0)
    filtre = [l for l in lignes[debut:] if len(l) >= 3 and l[1] == "PreToolUse"]
    session = session or next((l[2] for l in reversed(filtre) if l[2]), "")
    return f"PreToolUse={sum(1 for l in filtre if l[2] == session)}"


def worktree(racine: Path) -> str:
    """Le worktree d'un commit, tel que la trace le nomme : sa racine."""
    return str(Path(racine).resolve())


# Des hooks chargés laissent une trace fraîche : `socle state` tourne au
# démarrage, juste après le SessionStart, ou dans une commande que le filtre
# vient de voir passer. Une session reprise hors de la racine du projet
# garde son identifiant et les traces d'avant la reprise, mais n'en ajoute
# plus : la plus récente vieillit.
FRAICHEUR_HOOKS = 600  # secondes


def hooks_non_charges(projet: config.Projet, maintenant: datetime | None = None) -> bool:
    """Sous Claude Code (`CLAUDECODE`), les hooks de la session courante
    (`CLAUDE_CODE_SESSION_ID`) ne tirent pas : la trace n'a aucun
    SessionStart pour elle, sauf si le socle a été installé pendant elle, ou
    son dernier passage (démarrage ou filtre) date de plus de
    `FRAICHEUR_HOOKS` secondes. La session a démarré, ou repris, hors de la
    racine du projet. Faux hors d'un agent, sans
    identifiant de session, ou quand la politique n'outille pas Claude Code."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not os.environ.get("CLAUDECODE") or not session or not projet.pol("agents", "claude_code", defaut=True):
        return False
    lignes = [l.split("\t") for l in config.lire_trace(projet.racine)]
    passages = [l for l in lignes if len(l) >= 3 and l[2] == session and l[1] in ("SessionStart", "PreToolUse")]
    if not any(l[1] == "SessionStart" for l in passages) and not installe_pendant(lignes, session):
        return True
    try:
        dernier = datetime.fromisoformat(passages[-1][0])
    except ValueError:
        return False
    return ((maintenant or datetime.now(dernier.tzinfo)) - dernier).total_seconds() > FRAICHEUR_HOOKS


def filtre_absent(projet: config.Projet) -> str | None:
    """Un commit d'agent (`CLAUDECODE`) sans aucun passage du filtre de
    l'agent depuis le commit précédent : le compte (`PreToolUse=0`), à
    refuser dès le hook avant commit, au lieu du seul avertissement du
    message de commit. `None` sinon. La commande qui commite passe
    elle-même par le filtre : des hooks chargés en comptent au moins un.

    Le compte part du commit précédent du même worktree (B-0136). Un commit
    d'un autre worktree depuis le dernier passage du filtre n'excuse que des
    hooks qui tirent encore : la trace de la session doit être fraîche, sans
    quoi un worktree neuf compterait toute la session, et ne verrait pas des
    hooks qui ont cessé de tirer (B-0058)."""
    if not os.environ.get("CLAUDECODE") or not projet.pol("agents", "claude_code", defaut=True):
        return None
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    depuis = compter_depuis_le_commit(projet.racine, session)
    if depuis == "PreToolUse=0":
        return depuis
    partout = compter_depuis_le_commit(projet.racine, session, tous=True)
    return partout if partout == "PreToolUse=0" and hooks_non_charges(projet) else None


def sous_un_agent(geste: str) -> bool:
    """Défense en profondeur : une commande réservée à l'humain
    refuse de tourner dans une session d'agent, que le hook l'ait reconnue
    ou non. Le dit, et rend vrai."""
    if not os.environ.get("CLAUDECODE"):
        return False
    print(trad("refus : {geste} est réservé à l'humain, et cette commande tourne dans une session d'agent "
               "(CLAUDECODE) — l'humain la lance dans son propre terminal", geste=geste), file=sys.stderr)
    return True


def git_prepare_commit_msg(projet: config.Projet, fichier: str, source: str = "") -> int:
    """Sur un commit fait dans une session d'agent (`CLAUDECODE` dans
    l'environnement), ajoute `Socle-Agent`, `Socle-Hooks` et
    `Socle-Hooks-Since-Commit`."""
    # Le compte depuis le commit précédent se lit avant de tracer celui-ci.
    depuis = compter_depuis_le_commit(projet.racine, os.environ.get("CLAUDE_CODE_SESSION_ID"))
    tracer(projet.racine, "git-prepare-commit-msg", "", worktree(projet.racine))
    if not os.environ.get("CLAUDECODE") or source in ("merge", "squash"):
        return 0
    p = Path(fichier)
    message = p.read_text(encoding="utf-8")
    if re.search(r"(?im)^socle-hooks:", message):
        return 0
    # Sous la ligne de coupe de `git commit -v`, le diff : git l'ôte du
    # message, il reste tel quel en bas, hors de ce qu'on réordonne.
    coupe = re.search(r"(?m)^# -+ >8 -+$", message)
    corps, bas = (message[:coupe.start()], message[coupe.start():]) if coupe else (message, "")
    lignes = [
        "Socle-Agent: claude-code",
        f"Socle-Hooks: {compter_session(projet.racine, os.environ.get('CLAUDE_CODE_SESSION_ID'))}",
        f"Socle-Hooks-Since-Commit: {depuis}",
    ]
    # Les trailers vont dans le dernier paragraphe, avant les commentaires.
    contenu, commentaires = [], []
    for l in corps.rstrip("\n").splitlines():
        (commentaires if l.startswith("#") else contenu).append(l)
    texte = "\n".join(contenu).rstrip()
    sep = "\n" if outils.trailers(texte) else "\n\n"
    nouveau = texte + sep + "\n".join(lignes) + "\n"
    if commentaires:
        nouveau += "\n" + "\n".join(commentaires) + "\n"
    p.write_text(nouveau + bas, encoding="utf-8")
    return 0


def git_commit_msg(projet: config.Projet, fichier: str = "") -> int:
    """Le message d'un commit public ne cite ni identifiant privé ni terme de
    la liste privée : le seul étage, hors de l'agent, qui le voit avant le
    commit. Il avertit aussi d'une fonction que la CI refusera faute
    de test ou de dispense."""
    tracer(projet.racine, "git-commit-msg")
    if not fichier:
        return 0
    try:
        brut = Path(fichier).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    # Sous la ligne de coupe de `git commit -v`, le diff : il ne fait pas
    # partie du message.
    coupe = re.search(r"(?m)^# -+ >8 -+$", brut)
    brut = brut[:coupe.start()] if coupe else brut
    message = "\n".join(l for l in brut.splitlines() if not l.startswith("#"))
    faute = _fuites_dans(projet, message) if prive.mode(projet) is not None else None
    if faute:
        tracer_refus(projet.racine, "git-commit-msg", "fuite")
        print(trad("socle — commit refusé : {faute}", faute=faute), file=sys.stderr)
        return 1
    for avertissement in (code_sans_test(projet, message), hooks_absents(projet, message),
                          correctif_sans_test(projet, message)):
        if avertissement:
            print(avertissement, file=sys.stderr)
    return 0


def amendement_en_cours() -> bool:
    """Le hook tourne sous un `git commit --amend` : git lance ses hooks
    sans leur dire qu'il amende, mais sa ligne de commande le dit."""
    import subprocess

    try:
        args = [x.decode(errors="replace") for x in Path(f"/proc/{os.getppid()}/cmdline").read_bytes().split(b"\0")]
    except OSError:
        r = subprocess.run(["ps", "-o", "args=", "-p", str(os.getppid())], capture_output=True, text=True)
        args = r.stdout.split()
    return "--amend" in args


def correctif_sans_test(projet: config.Projet, message: str, amendement: bool | None = None) -> str | None:
    """Un correctif (`fix:`, `Corrige:`) dont le commit n'ajoute ni ne change
    aucun test : la CI le refusera (`tests.regression`), seule à pouvoir
    rejouer un test sur le commit d'avant. Le hook commit-msg le dit dès le
    commit, sans refuser, quand l'amender suffit encore. Un commit amendé se
    juge contre le parent de celui qu'il remplace, qui porte peut-être déjà
    ses tests (B-0084)."""
    from socle import checks_tests as controles_tests

    if not controles_tests.est_correctif(projet, message) or not outils.a_des_commits(projet.racine):
        return None
    arbre = outils.arbre_de_l_index(projet.racine)
    if not arbre:
        return None
    if amendement is None:
        amendement = amendement_en_cours()
    parent = "HEAD"
    if amendement:
        parent = "HEAD^" if outils.rev_existe(projet.racine, "HEAD^") else outils.ARBRE_VIDE
    touches = [f for f in outils.git(projet.racine, "diff", "--name-only", "-z", parent, arbre,
                                     check=False).split("\0") if f]
    # La CI juge un correctif hors de tout adaptateur dans la vue du
    # principal, et seulement si celui-ci sait rejouer un test.
    principal = projet.pour(projet.adaptateurs[0]) if projet.plusieurs_adaptateurs else projet
    rejoue = "command" in principal.adaptateur.get("capabilities", {}).get("regression", {})
    hors = controles_tests.hors_de_tout_adaptateur(projet, projet.hors_tiers(touches)) if rejoue else []
    if hors:
        # Aucun adaptateur ne juge ses fichiers : un test n'y peut rien
        # (D-0088).
        return trad("socle — avertissement : ce correctif ne touche aucun fichier qu'un adaptateur juge ({liste}) : "
                    "la CI le refusera (`tests.regression`), sauf si une demande validée nomme ce commit et "
                    "l'admet sans test ; sinon, un adaptateur pour leur langage, ou ces fichiers déclarés tiers, par "
                    "une demande.", liste=", ".join(hors[:5]) + (" …" if len(hors) > 5 else ""))
    # Dans un projet à plusieurs adaptateurs, un test par langage du code
    # corrigé (ADR-0051, point 3).
    vues = [projet.pour(a) for a in projet.adaptateurs] if projet.plusieurs_adaptateurs else [projet]
    manquants = []
    for vue in vues:
        if projet.plusieurs_adaptateurs and not controles_tests.concerne(vue, touches):
            continue
        cap = vue.adaptateur.get("capabilities", {}).get("regression", {})
        if "command" not in cap:
            continue
        motifs = cap.get("test_paths") or (controles_tests.cfg_tests(vue) or {}).get("paths", [])
        if outils.filtrer(touches, motifs):
            continue
        code = vue.adaptateur.get("sources", []) if projet.plusieurs_adaptateurs else projet.chemins_code()
        if "module_command" in cap and outils.filtrer(touches, code):
            continue  # un test peut vivre dans le module du code : la CI le cherche
        manquants += [m for m in motifs if m not in manquants]
    if not manquants:
        return None
    return (trad("socle — avertissement : ce correctif n'ajoute ni ne change aucun test ({liste}) : la CI le "
                 "refusera (`tests.regression`), faute d'un test qui échoue sur le commit d'avant. L'ajouter à ce "
                 "commit (`git commit --amend`), tant qu'il n'est pas poussé.", liste=', '.join(manquants)))


def hooks_absents(projet: config.Projet, message: str) -> str | None:
    """Un commit d'agent dont la trace ne compte aucun PreToolUse : les hooks
    de l'agent n'ont pas tiré pendant sa session, et la CI refusera le commit
    (`hooks.trace`). Le hook commit-msg, qui voit la trace que le hook
    précédent vient d'écrire, le dit dès le commit, sans refuser."""
    from socle import checks_ratchet as controles_cliquet

    if not controles_cliquet.est_agent(projet, message):
        return None
    valeurs = outils.trailers(message).get("socle-hooks")
    if not valeurs:
        return None
    conseil = trad(controles_cliquet.REMEDE_HOOKS)
    tirs = controles_cliquet.lire_trailer_hooks(valeurs[-1]).get("PreToolUse", "0")
    if not tirs.isdigit() or int(tirs) < 1:
        return (trad("socle — avertissement : commit d'agent sans aucun hook de l'agent pendant sa session "
                     "(`Socle-Hooks: {valeurs}`) : la CI le refusera (`hooks.trace`). ", valeurs=valeurs[-1]) + conseil)
    # Des hooks qui ont tiré en début de session, puis plus du tout.
    depuis = outils.trailers(message).get("socle-hooks-since-commit")
    tirs = controles_cliquet.lire_trailer_hooks(depuis[-1]).get("PreToolUse", "0") if depuis else "1"
    if tirs.isdigit() and int(tirs) >= 1:
        return None
    return (trad("socle — avertissement : commit d'agent sans aucun hook de l'agent depuis le commit précédent "
                 "(`Socle-Hooks-Since-Commit: {depuis}`) : ses hooks ont cessé de tirer en cours de session, et la "
                 "CI le refusera (`hooks.trace`). ", depuis=depuis[-1]) + conseil)


def code_sans_test(projet: config.Projet, message: str) -> str | None:
    """Une fonction publique que ni un test ni une dispense ne nomme : la CI
    refusera le commit (`tests.code-teste`). Le hook commit-msg, le premier
    étage qui voit le message et ses dispenses, le dit sans refuser : un
    humain qui commite son code l'apprend ici, pas en CI."""
    from socle import context as contexte, checks_tests as controles_tests
    from socle.report import Rapport

    base = outils.base_de_travail(projet.racine)
    index = outils.arbre_de_l_index(projet.racine)
    ctx = contexte.Contexte(projet, etage="git", base=base, tete=index, rapide=True, message=message)
    r = Rapport()
    try:
        controles_tests.code_teste(ctx, r)
    except Exception:  # un avertissement ne bloque jamais un commit
        return None
    erreurs = r.erreurs("tests.code-teste")
    if not erreurs:
        return None
    return (trad("socle — avertissement : la CI refusera ce commit (`tests.code-teste`) :\n")
            + "\n".join(f"  ! {c.en_ligne()}" for c in erreurs)
            + trad("\nLe commit passe ici. Écrire le test dans un commit suivant, ou amender ce message (`git "
                   "commit --amend`) avec la dispense."))


def plage_poussee(projet: config.Projet, lignes: list[str]):
    """Les contrôles qui comparent à une base, sur la plage qui part : du
    commit distant au commit local de chaque référence déjà présente en
    face. C'est la plage que la CI d'un push jugera ; contre la branche par
    défaut, une dispense ou une validation plus anciennes de la branche
    couvraient ce qu'elle refusera. Une branche jetable n'a pas de CI aux
    envois : rien à juger comme elle (D-0087)."""
    from socle import context as contexte
    from socle.report import Rapport

    rapport = Rapport()
    contexte.charger_controles()
    ids = [c.id for c in contexte.selectionner("ci", rapide=True) if c.base]
    for l in lignes:
        morceaux = l.split()
        if len(morceaux) < 4:
            continue
        local, distant = morceaux[1], morceaux[3]
        if set(local) == {"0"} or set(distant) == {"0"} or not outils.rev_existe(projet.racine, distant):
            continue  # une branche neuve, une suppression, ou un distant qu'on n'a pas : rien à comparer
        if projet.branche_jetable(morceaux[2].removeprefix("refs/heads/")):
            continue  # une branche jetable : la CI ne la juge pas aux envois (D-0087)
        ctx = contexte.Contexte(projet, etage="ci", base=distant, tete=local, rapide=True, avant_push=True)
        rapport.fusionner(contexte.executer(ctx, ids))
    return rapport


def branches_envoyees(lignes: list[str]) -> list[str]:
    """Les références distantes qu'un push met à jour, d'après les lignes
    que git donne au hook avant push, sans les suppressions ; une étiquette
    garde son nom complet, qui n'est celui d'aucune branche."""
    res = []
    for ligne in lignes:
        morceaux = ligne.split()
        if len(morceaux) >= 4 and set(morceaux[1]) != {"0"}:
            res.append(morceaux[2].removeprefix("refs/heads/"))
    return res


def git_pre_push(projet: config.Projet) -> int:
    from socle import context as contexte, verification

    tracer(projet.racine, "git-pre-push")
    # Les commits qui partent : `<réf locale> <sha local> <réf distante> <sha distant>` par ligne.
    lignes = [] if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read().splitlines()
    if prive.mode(projet):
        # Le nom de la branche distante est publié lui aussi.
        noms = [l.split()[2].removeprefix("refs/heads/") for l in lignes if len(l.split()) >= 4]
        trouve = prive.fuites("\n".join(noms), prive.termes(projet).liste)
        if trouve:
            tracer_refus(projet.racine, "git-pre-push", "fuite")
            print(trad("socle — push refusé : fuite de la mémoire privée dans le nom de la branche : {liste}",
                       liste=', '.join(trouve)),
                  file=sys.stderr)
            return 1
    refus = prive.publication_refusee(projet, [l.split()[1] for l in lignes if len(l.split()) >= 2])
    if refus:
        tracer_refus(projet.racine, "git-pre-push", "relecture")
        print(trad("socle — push refusé : {refus}", refus=refus), file=sys.stderr)
        return 1
    base = outils.base_de_travail(projet.racine)
    # On juge ce qui part : le dernier commit, et non l'arbre, dont un
    # changement non commité ne part pas. Une mise à jour en session cloud y
    # laisse ses fichiers protégés en attendant la validation de l'humain,
    # que la demande poussée ici lui permet de lire (B-0115).
    tete = outils.git(projet.racine, "rev-parse", "HEAD", check=False).strip() or None
    # Ce qui part se juge pour les branches qui le reçoivent : une branche
    # jetable extraite qu'on pousse ailleurs ne relâche rien (D-0087).
    ctx = contexte.Contexte(projet, etage="git", base=base, tete=tete, rapide=True,
                            branches=branches_envoyees(lignes))
    rapport = contexte.executer(ctx)
    for constat in plage_poussee(projet, lignes).constats:
        if constat not in rapport.constats:
            rapport.constats.append(constat)
    verification.etapes_rapides(projet, rapport)
    if not rapport.reussi:
        tracer_refus(projet.racine, "git-pre-push", ",".join(rapport.controles_en_echec()))
        rapport.afficher(trad("socle — vérification avant push"), flux=sys.stderr, court=True)
        return 1
    _dire_avertissements(rapport, (verification.CONTROLE_DUREE,))
    return 0


def _avertissements(rapport, controles) -> list[str]:
    """Les avertissements de ces contrôles, chacun sur sa ligne, tels qu'un
    hook qui laisse passer les dit."""
    from socle.report import AVERTISSEMENT

    return [trad("socle — avertissement ({controle}) : {constat}", controle=c.controle, constat=c.en_ligne())
            for c in rapport.constats if c.controle in controles and c.gravite == AVERTISSEMENT]


def _dire_avertissements(rapport, aussi: tuple[str, ...] = ()) -> None:
    """Le hook git qui laisse passer se tait, sauf pour ceci, qu'il dit sur
    sa sortie d'erreur : une réponse `valider` qui part sans le changement
    qu'elle autorise, et ne le couvrira pas au push suivant
    (`demandes.reponse-seule`, B-0142) ; et `aussi`, au hook avant push,
    le total des étapes rapides qu'il vient de lancer au-delà de leur seuil
    (`verify.duree`, B-0258), que l'agent lit dans la sortie de son
    `git push`. Le rapport d'un refus les montre déjà."""
    for ligne in _avertissements(rapport, ("demandes.reponse-seule",) + aussi):
        print(ligne, file=sys.stderr)
