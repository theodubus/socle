"""Les hooks : accélérateurs, jamais garanties (principe 3).

Hooks de l'agent (Claude Code, déclarés dans `.claude/settings.json`) :
- `session-start` : l'état dérivé entre dans le contexte, au démarrage et
  après chaque compactage ;
- `pre-tool-use`  : refuse une action irréversible ou externe, l'écriture d'un
  fichier protégé, une référence inventée, une demande hors contrat ;
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
    installes = installer_outils(projet)
    print(etat.calculer(projet))
    if installes:
        print("\n" + "\n".join(installes))
    if not git_ok and (projet.racine / config.GIT_HOOKS).is_dir():
        print(trad("\n!! hooks git non branchés : `git config core.hooksPath .socle/git-hooks`"))
    return 0


# Claude Code la pose dans ses sessions cloud, dont le conteneur repart de
# zéro à chaque session.
SESSION_CLOUD = "CLAUDE_CODE_REMOTE"
# Sous le délai du hook de démarrage (`.claude/settings.json`).
DELAI_OUTILS = 270


def installer_outils(projet: config.Projet) -> list[str]:
    """En session cloud, les outils de l'adaptateur, par les commandes que la
    CI lance pour eux : sans eux, la première vérification de l'agent échoue
    (D-0048). Une fois par conteneur ; un échec se dit sans bloquer le
    démarrage. Rend les lignes à montrer à l'agent."""
    from socle import verification

    if os.environ.get(SESSION_CLOUD) != "true":
        return []
    commandes_ci = verification.commandes_ci(projet)
    if not commandes_ci:
        return []
    marque = config.chemin_trace(projet.racine).parent / "outils-installes"
    empreinte = outils.sha256("\n".join(commandes_ci))
    try:
        if marque.read_text(encoding="utf-8").strip() == empreinte:
            return []
    except OSError:
        pass
    fin = time.monotonic() + DELAI_OUTILS
    lignes, reussi = [], True
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
        queue = "\n    ".join((p.stdout + p.stderr).strip().splitlines()[-5:])
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
    from socle import readings as lp

    fautes = []
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
    for ident, h, ligne in memoire.citations(apres):
        soi = lp.entree_englobante(mem, rel, ligne)
        if ident in defs and not lp.deja_citee(soi, f"{ident}@{h}", mem_avant, avant or "") \
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
    for ident, ligne in memoire.mentions(apres):
        if ident in deja or ident in defs or ident.startswith("P"):
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
    return fautes


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
    res = list(c.redirige)
    nom = c.programme
    options, args = commandes.options_et_arguments(c.argv[1:])
    if nom in ECRIVAINS:
        res += args
    elif nom in ("cp", "ln", "install", "rsync") and args:
        res.append(args[-1])
    elif nom in ("sed", "perl") and commandes.drapeau(options, "i", ("--in-place",)):
        res += args if any(o in ("-e", "-f", "--expression", "--file") for o in options) else args[1:]
    elif nom == "dd":
        res += [a[3:] for a in c.argv[1:] if a.startswith("of=")]
    elif nom == "git":
        sous, reste = commandes.git_sous_commande(c.argv)
        if sous in ("rm", "mv", "restore", "clean"):
            res += commandes.options_et_arguments(reste)[1]
        elif sous == "checkout" and "--" in reste:
            res += reste[reste.index("--") + 1:]
    return [c.chemin(x) for x in res if x]


def cibles_ecrites(cmd: str) -> list[str]:
    """Les chemins qu'une commande shell écrit, toutes commandes simples
    confondues."""
    return [x for c in commandes.analyser(cmd) for x in ecrits(c)]


def ecriture_protegee(projet: config.Projet, cmd: str) -> str | None:
    """Le chemin protégé qu'une commande shell écrit, s'il y en a un : un
    fichier protégé, ou un dossier qui en contient (`rm -rf .socle`)."""
    motifs = projet.chemins_proteges()
    suivis = None
    for jeton in cibles_ecrites(cmd):
        rel = _relatif(projet.racine, jeton.strip("'\""))
        if rel is None:
            continue
        if outils.correspond(rel, motifs):
            return rel
        if suivis is None:
            suivis = outils.fichiers_courants(projet.racine)
        prefixe = "" if rel in ("", ".") else rel.rstrip("/") + "/"
        touche = next((f for f in suivis if f.startswith(prefixe) and outils.correspond(f, motifs)), None)
        if touche:
            return trad("{chemin}/ (dont {touche})", chemin=rel or ".", touche=touche)
    return None


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


def commande_humaine(c: commandes.Commande) -> tuple[str, list[str]] | None:
    """Une commande du socle réservée à l'humain (`answer`, `approve`,
    `reviewed`, `private install`), quel que soit le chemin du lanceur (entre
    guillemets, après un `cd`, par `python3 -m socle`) : son nom et ses
    arguments ; `None` sinon."""
    argv = c.argv
    if not argv:
        return None

    def lanceur(chemin: str) -> bool:
        return posixpath.normpath(c.chemin(chemin)).endswith(".socle/socle") or chemin.endswith(".socle/socle")

    if re.fullmatch(r"python[\d.]*", c.programme):
        reste = argv[1:]
        while reste and reste[0].startswith("-"):
            reste = reste[1:]
        if not reste or not lanceur(reste[0]):
            return None
        reste = reste[1:]
    elif c.programme == "socle" or lanceur(argv[0]):
        reste = argv[1:]
    else:
        return None
    while reste and (reste[0] == "--root" or reste[0].startswith("--root=")):
        reste = reste[2:] if reste[0] == "--root" else reste[1:]
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


COMMANDES_HUMAINES = _Repere(("answer", "decision", "approve", "reviewed"))
INSTALLER_PRIVE = _Repere(("private install",))


def refus_bash(projet: config.Projet, cmd: str, cwd: str | None = None) -> str | None:
    """La raison pour laquelle le hook refuse une commande du shell, ou rien :
    le même jugement pour une commande que l'agent lance et pour une
    commande qu'un skill lui ferait lancer (`skills.commandes`)."""
    racine = projet.racine
    # Chaque commande simple, découpée : ce qu'elle lance, pas le texte
    # qu'elle cite (un heredoc, un message de commit).
    simples = commandes.analyser(cmd)
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
        if not relais:
            return trad("l'agent ne répond jamais à la place de l'humain. Il ne peut que relayer une "
                        "réponse donnée dans la conversation : `socle answer D-NNNN <réponse> --relayed "
                        "--by <nom> --quote-file <texte exact>`, `socle decision "
                        "\"<question>\" <réponse> --relayed --by <nom> --quote-file <texte exact>` pour une "
                        "décision prise en séance, ou `socle reviewed --relayed --by <nom> "
                        "--quote-file <texte exact>` pour une relecture avant publication.")
    faute = _fuite_bash(projet, cmd)
    if faute:
        return faute
    reglage = next((x for c in simples for x in ecrits(c) if REGLAGES_AGENT.search(x)), None)
    if reglage:
        return trad("`{reglage}` : les réglages de Claude Code commandent ses hooks, seul l'humain les "
                    "modifie (un réglage local peut les couper tous).", reglage=reglage)
    cible = ecriture_protegee(projet, cmd)
    if cible:
        return trad("écriture d'un fichier protégé ({cible}) par le shell : seul l'humain modifie la "
                    "politique, les hooks, la CI et le moteur (relance de l'installeur).", cible=cible)
    return None


# Le widget de questions de l'agent (B-0105) : l'humain y lit un texte brut,
# sans liens à suivre, et n'y répond qu'à des options écrites par l'agent.
QUESTIONS_AGENT = ("AskUserQuestion",)


def pre_tool_use(projet: config.Projet, entree: dict) -> int:
    racine = projet.racine
    outil = entree.get("tool_name", "")
    args = entree.get("tool_input") or {}
    tracer(racine, "PreToolUse", entree.get("session_id", ""), outil)

    def refus(raison: str) -> int:
        tracer_refus(racine, "PreToolUse", f"{outil} — {raison}", entree.get("session_id", ""))
        return _refus(raison)

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
                fautes = references_inventees(projet, rel, avant, apres)
                if fautes:
                    return refus(trad("référence inventée — {fautes}", fautes=" ; ".join(fautes[:5])))
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
    return 0


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


def textes_publies(racine: Path, simples: list) -> list[str]:
    """Ce que les commandes `git` et `gh` publient depuis un fichier :
    `--body-file x`, `-F x`, et `gh api -F champ=@x`."""
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
                res.append((chemin if chemin.is_absolute() else racine / chemin).read_text(
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


def _fuite_bash(projet: config.Projet, cmd: str) -> str | None:
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
        publie += [cmd] + textes_publies(projet.racine, simples)
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
    # vient de lancer) : inutile de payer une compilation de plus.
    if outils.filtrer(ctx.changes, projet.chemins_code()):
        verification.etapes_rapides(projet, rapport)

    if rapport.reussi:
        compteur.unlink(missing_ok=True)
        return exiger_recap(projet, entree)
    # Le compteur appartient à sa session : une session nouvelle ne commence
    # pas à l'escalade sur les échecs d'une autre (relevé de la passe de
    # recul, F).
    cle = session or "-"
    precedent = compteur.read_text().split() if compteur.is_file() else []
    essais = int(precedent[0]) + 1 if len(precedent) == 2 and precedent[1] == cle and \
        precedent[0].isdigit() else 1
    compteur.parent.mkdir(parents=True, exist_ok=True)
    compteur.write_text(f"{essais} {cle}")
    texte = rapport.texte(trad("contrôles de fin de tour (`socle check --stage agent`)"))
    if essais >= projet.maximum_tentatives():
        compteur.unlink(missing_ok=True)
        print(json.dumps({"systemMessage": trad(
            "Les contrôles échouent encore après {essais} tentatives : ARRÊT ET ESCALADE (politique, point 7). "
            "Écrire une demande `D-NNNN` qui résume l'échec, ce qui a été tenté et ce qui est supposé, "
            "puis s'arrêter.\n\n{rapport}", essais=essais, rapport=texte)}, ensure_ascii=False))
        return 0
    tracer_refus(racine, "Stop", ",".join(rapport.controles_en_echec()), entree.get("session_id", ""))
    print(json.dumps({"decision": "block", "reason": trad(
        "Les contrôles échouent (tentative {essais}/{maximum}) : corriger avant de conclure.\n\n{rapport}",
        essais=essais, maximum=projet.maximum_tentatives(), rapport=texte)}, ensure_ascii=False))
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


def exiger_recap(projet: config.Projet, entree: dict) -> int:
    """Un tour où l'agent a agi se termine par un récap et deux lignes,
    `Pour toi :` et `Ensuite :`. Tout dernier message,
    qu'il ait agi ou non, ne donne que des liens que l'humain peut suivre."""
    from socle import human as humain, links as liens

    racine = projet.racine
    fichier = racine / ".socle/trace/derniere-fin-de-tour"
    marque = _empreinte_arbre(racine) if outils.a_des_commits(racine) else ""
    a_agi = (not fichier.is_file() or fichier.read_text().strip() != marque
             or _appels_externes(racine, entree.get("session_id", "")))

    def retenir():
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(marque)

    chemin = entree.get("transcript_path")
    message = humain.dernier_message(Path(chemin)) if chemin else None
    if message is None:
        if a_agi:
            retenir()
            print(json.dumps({"systemMessage": trad("récap de fin d'intervention non vérifiable : transcript "
                                                    "illisible")}, ensure_ascii=False))
        return 0
    manque = humain.recap_manquant(projet, message) if a_agi else []
    morts, sans_lien = liens.problemes(projet, message)
    if not (manque or morts or sans_lien):
        if a_agi:
            retenir()
        return 0
    if entree.get("stop_hook_active"):
        if a_agi:
            retenir()
        defauts = ([trad("sans {manque}", manque=trad(" ni ").join(manque))] if manque else []) + (
            [trad("{n} lien(s) que l'humain ne pourra pas suivre", n=len(morts) + len(sans_lien))]
            if morts or sans_lien else [])
        print(json.dumps({"systemMessage": trad("fin d'intervention {defauts}, malgré un rappel",
                                                defauts=", ".join(defauts))}, ensure_ascii=False))
        return 0
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
            "été fait, puis :\n"
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
    print(json.dumps({"decision": "block", "reason": "\n\n".join(raisons)}, ensure_ascii=False))
    return 0


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


def compter_depuis_le_commit(racine: Path, session: str | None = None) -> str:
    """`PreToolUse=3` : les passages du filtre de l'agent depuis le commit
    précédent du dépôt (sa ligne `git-prepare-commit-msg` dans la trace),
    pour la session donnée ou, à défaut, la plus récente depuis. La commande
    qui commite passe elle-même par le filtre : des hooks chargés en comptent
    toujours au moins un. Le compte de toute la session ne voit pas des hooks
    qui cessent de tirer en cours de route."""
    lignes = [l.split("\t") for l in config.lire_trace(racine)]
    debut = next((i + 1 for i in range(len(lignes) - 1, -1, -1)
                  if len(lignes[i]) >= 2 and lignes[i][1] == "git-prepare-commit-msg"), 0)
    filtre = [l for l in lignes[debut:] if len(l) >= 3 and l[1] == "PreToolUse"]
    session = session or next((l[2] for l in reversed(filtre) if l[2]), "")
    return f"PreToolUse={sum(1 for l in filtre if l[2] == session)}"


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
    elle-même par le filtre : des hooks chargés en comptent au moins un."""
    if not os.environ.get("CLAUDECODE") or not projet.pol("agents", "claude_code", defaut=True):
        return None
    depuis = compter_depuis_le_commit(projet.racine, os.environ.get("CLAUDE_CODE_SESSION_ID"))
    return depuis if depuis == "PreToolUse=0" else None


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
    tracer(projet.racine, "git-prepare-commit-msg")
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
    cap = projet.adaptateur.get("capabilities", {}).get("regression", {})
    arbre = outils.arbre_de_l_index(projet.racine)
    if "command" not in cap or not arbre:
        return None
    motifs = cap.get("test_paths") or (controles_tests.cfg_tests(projet) or {}).get("paths", [])
    if amendement is None:
        amendement = amendement_en_cours()
    parent = "HEAD"
    if amendement:
        parent = "HEAD^" if outils.rev_existe(projet.racine, "HEAD^") else outils.ARBRE_VIDE
    touches = [f for f in outils.git(projet.racine, "diff", "--name-only", "-z", parent, arbre,
                                     check=False).split("\0") if f]
    if outils.filtrer(touches, motifs):
        return None
    if "module_command" in cap and outils.filtrer(touches, projet.chemins_code()):
        return None  # un test peut vivre dans le module du code : la CI le cherche
    return (trad("socle — avertissement : ce correctif n'ajoute ni ne change aucun test ({liste}) : la CI le "
                 "refusera (`tests.regression`), faute d'un test qui échoue sur le commit d'avant. L'ajouter à ce "
                 "commit (`git commit --amend`), tant qu'il n'est pas poussé.", liste=', '.join(motifs)))


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
    couvraient ce qu'elle refusera."""
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
        ctx = contexte.Contexte(projet, etage="ci", base=distant, tete=local, rapide=True, avant_push=True)
        rapport.fusionner(contexte.executer(ctx, ids))
    return rapport


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
    ctx = contexte.Contexte(projet, etage="git", base=base, tete=tete, rapide=True)
    rapport = contexte.executer(ctx)
    for constat in plage_poussee(projet, lignes).constats:
        if constat not in rapport.constats:
            rapport.constats.append(constat)
    verification.etapes_rapides(projet, rapport)
    if not rapport.reussi:
        tracer_refus(projet.racine, "git-pre-push", ",".join(rapport.controles_en_echec()))
        rapport.afficher(trad("socle — vérification avant push"), flux=sys.stderr, court=True)
        return 1
    return 0
