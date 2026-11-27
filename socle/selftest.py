"""Auto-test du dispositif : un garde-fou qu'on n'a jamais vu échouer ne
prouve rien.

On fabrique un petit projet Python, on y installe le moteur courant, puis on
injecte un à un les défauts connus du cadrage. Chacun doit être attrapé par
le contrôle prévu, à l'étage prévu, en passant par le vrai point d'entrée
(hook de l'agent, hook git, commande de CI). Des témoins sains doivent passer,
sans quoi un contrôle qui échoue toujours passerait pour un contrôle qui
marche.

Chaque cas tourne dans un clone jetable du projet de base, avec un `origin`
comme dans la vraie vie : la base des contrôles est `origin/main`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from socle.messages import trad
from socle.report import Rapport, en_echec_dans

# Les fils de l'auto-test : un clone chacun, au plus quatre (L6).
FILS = min(4, os.cpu_count() or 1)
# Posée par `socle ci` pendant la suite de tests, quand il lance l'auto-test
# juste après : le test qui le joue lui cède la place.
ENSUITE = "SOCLE_AUTOTEST_ENSUITE"

CALC = '''"""Calculs du projet d'essai."""

FACTEUR = 2


def double(x):
    return FACTEUR * x
'''
TEST_CALC = '''import unittest

from calc import double


class TestCalc(unittest.TestCase):
    def test_double(self):
        self.assertEqual(double(2), 4)
'''
# Un test d'un peu plus d'une seconde : les étapes rapides du projet d'essai
# passent alors le seuil d'une seconde, et restent loin de celui du gabarit
# (B-0258).
TEST_LENT = '''import time
import unittest

from calc import double


class TestLent(unittest.TestCase):
    def test_double_lent(self):
        time.sleep(1.2)
        self.assertEqual(double(3), 6)
'''
DOC_CALC = """# Calcul

`double` multiplie par <!-- valeur:facteur -->2<!-- /valeur -->, la
constante `FACTEUR` de `calc.py`.
"""
GARDE_FOUS_ESSAI = '''
[[docmap]]
code = ["calc.py"]
docs = ["docs/calc.md"]

[[values]]
name = "facteur"
file = "calc.py"
regex = '^FACTEUR = (\\d+)'
'''
# Un fichier de cas que le projet d'essai déclare (D-0066) : des résultats
# attendus écrits en données.
CAS_ESSAI = """[
  {
    "id": "c1",
    "entree": 2,
    "attendu": 4
  },
  {
    "id": "c2",
    "entree": 3,
    "attendu": 6
  }
]
"""
CANONIQUE_ESSAI = """
## F-0001 — `double` multiplie par la constante du module

> statut : mesuré · preuve : fichier:tests/test_calc.py

Le test unitaire l'établit.
"""
CANONIQUE_PRIVEE = """<!-- socle: couche=canonique zone=privee -->
# Mémoire canonique privée

## PF-0001 — Le module de calcul servira au projet Mistral

> statut : supposé · source : F-0001
"""
FILTRE_ESSAI = """import base64, sys
donnees = sys.stdin.buffer.read()
if sys.argv[1] == "clean":
    sys.stdout.buffer.write(donnees if donnees.startswith(b"ESSAI:") else b"ESSAI:" + base64.b64encode(donnees))
else:
    sys.stdout.buffer.write(base64.b64decode(donnees[6:]) if donnees.startswith(b"ESSAI:") else donnees)
"""
BACKLOG_ESSAI = """
## B-0001 — Ajouter une fonction triple

> statut : ouvert · origine : {journal}

Demandé pour l'essai.
"""
# La section d'un besoin nouveau (ADR-0083).
SATISFAIT_ESSAI = "\n## Satisfait quand\n\n- [ ] le module le fait\n"
# Une consigne de l'humain (B-0161) : sa ligne de résumé, sa source, son
# texte exact.
CONSIGNE_ESSAI = """
## {ident} — Le module de calcul reste sans dépendance

> statut : {statut} · source : {journal} · date : 2026-10-10

> « Pas de dépendance externe dans le module de calcul. »
"""


def tache_essai(a, c: Path, statut: str = "ouvert", criteres: str = "- [x] le test passe") -> str:
    """La tâche T-0001 du besoin B-0001, dans sa forme : son besoin, sa
    lecture de l'index, son « Fait quand »."""
    return (f"\n## T-0001 — Écrire triple et son test\n\n> statut : {statut} · origine : {a.journal} · "
            f"besoin : B-0001 · lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n\n"
            f"## Fait quand\n\n{criteres}\n")


def lot_essai(a, c: Path, ident: str, apres: str, champs: str = "") -> str:
    """Un lot qui attend `apres`."""
    return (f"\n## {ident} — Le lot de la multiplication\n\n> statut : ouvert · origine : {a.journal} · "
            f"après : {apres}{champs} · lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")


@dataclass
class Cas:
    id: str
    defaut: str
    etage: str
    controle: str
    fonction: Callable


class Atelier:
    """Un projet d'essai : un dépôt `origine` et des clones jetables."""

    def __init__(self, moteur: Path, bavard: bool):
        self.moteur = moteur
        self.bavard = bavard
        self.dossier = Path(tempfile.mkdtemp(prefix="socle-autotest-"))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "GIT_"))}
        self.env.update({
            "GIT_AUTHOR_NAME": "autotest", "GIT_AUTHOR_EMAIL": "autotest@socle",
            "GIT_COMMITTER_NAME": "autotest", "GIT_COMMITTER_EMAIL": "autotest@socle",
            "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(self.dossier),
            # La maintenance automatique de git, lancée en arrière-plan par
            # un commit ou une réception, n'a rien à faire dans des dépôts
            # jetables. Ce qui faisait échouer les clones parallèles de
            # l'origine était la quarantaine d'un push : voir `clone`.
            "GIT_CONFIG_COUNT": "3",
            "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0",
            "GIT_CONFIG_KEY_1": "maintenance.auto", "GIT_CONFIG_VALUE_1": "false",
            "GIT_CONFIG_KEY_2": "receive.autogc", "GIT_CONFIG_VALUE_2": "false",
        })
        self.n = 0
        # Les cas tournent sur plusieurs fils (L6) : le compteur des clones
        # et les origines privées, préparées une fois, sont partagés.
        self._verrou = threading.RLock()

    def run(self, cwd: Path, *args, entree: str | None = None, env: dict | None = None):
        e = dict(self.env)
        if env:
            e.update(env)
        return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, input=entree, env=e)

    def git(self, cwd, *args, env=None):
        r = self.run(cwd, "git", *args, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} : {r.stderr.strip()}")
        return r.stdout

    def socle(self, cwd, *args, entree=None, env=None):
        return self.run(cwd, sys.executable, str(cwd / ".socle/socle"), *args, entree=entree, env=env)

    def preparer(self):
        origine = self.dossier / "origine"
        origine.mkdir()
        self.git(origine, "init", "-q", "-b", "main")
        (origine / "calc.py").write_text(CALC)
        (origine / "tests").mkdir()
        (origine / "tests/__init__.py").write_text("")
        (origine / "tests/test_calc.py").write_text(TEST_CALC)
        r = self.run(origine, sys.executable, "-c",
                     "import sys; sys.path.insert(0, sys.argv[1]); from socle.cli import main; "
                     "sys.exit(main(sys.argv[2:]))", str(self.moteur),
                     "install", "--target", ".", "--adapter", "python", "--owner", "@essai")
        if r.returncode != 0:
            raise RuntimeError(trad("installation du projet d'essai : {stdout}{stderr}",
                                    stdout=r.stdout[-3000:], stderr=r.stderr[-3000:]))
        # La doc qui cite une valeur liée vient après sa déclaration : posée
        # avant, l'audit d'installation la refuserait, à raison.
        (origine / "docs").mkdir()
        (origine / "docs/calc.md").write_text(DOC_CALC)
        (origine / "docs/double.cas.json").write_text(CAS_ESSAI)
        gf = origine / ".socle/guardrails.toml"
        texte = gf.read_text().replace('[mutation.caps]\n', '[mutation.caps]\n"calc.py" = { max = 0 }\n')
        texte = texte.replace("spec_paths = ", 'case_paths = ["docs/*.cas.json"]\nspec_paths = ', 1)
        gf.write_text(texte + GARDE_FOUS_ESSAI)
        journal = sorted((origine / "memory/journal").glob("*.md"))[0]
        ident = journal.read_text().split("## ", 2)[1].split(" ", 1)[0]
        self._ajouter(origine / "memory/canonical.md", CANONIQUE_ESSAI)
        ajouter_sujet(origine, BACKLOG_ESSAI.format(journal=ident))
        # L'origine est un dossier local : l'adresse web où l'humain lirait
        # se règle dans la politique, comme pour un relais.
        pol = origine / ".socle/policy.toml"
        pol.write_text(pol.read_text().replace("[human]\n", f'[human]\nrepo_url = "{DEPOT_ESSAI}"\n', 1))
        self.journal = ident
        self.git(origine, "add", "-A")
        r = self.run(origine, "git", "commit", "-q", "-m", "Projet d'essai")
        if r.returncode != 0:
            raise RuntimeError(trad("le témoin de base ne passe pas le hook pre-commit :\n{stdout}{stderr}",
                                    stdout=r.stdout, stderr=r.stderr))
        self.origine = origine

    @staticmethod
    def _ajouter(p: Path, bloc: str):
        p.write_text(p.read_text().rstrip("\n") + "\n" + bloc)

    def clone(self, origine: Path | None = None, config: tuple[str, ...] = ()) -> Path:
        """Un clone jetable de l'origine, par le protocole (`--no-local`) :
        d'autres cas y poussent en même temps, et un clone local, qui lit
        le dossier des objets, y rencontre la quarantaine d'un push en
        cours (« hardlink different from source », « failed to copy
        file » ; B-0341)."""
        with self._verrou:
            self.n += 1
            c = self.dossier / f"cas-{self.n:02d}"
        options = [x for cle in config for x in ("-c", cle)]
        self.git(self.dossier, "clone", "-q", "--no-local", *options, str(origine or self.origine), str(c))
        self.git(c, "config", "core.hooksPath", ".socle/git-hooks")
        self.git(c, "checkout", "-q", "-b", "travail")
        return c

    def origine_privee(self, mode: str) -> Path:
        """Une origine d'essai avec une mémoire privée, préparée une fois par
        mode : le projet d'essai, plus la politique qui choisit le mode."""
        with self._verrou:
            return self._origine_privee(mode)

    def _origine_privee(self, mode: str) -> Path:
        o = self.dossier / f"origine-{mode}"
        if o.is_dir():
            return o
        self.git(self.dossier, "clone", "-q", "--no-local", *(x for cle in self.filtre() for x in ("-c", cle)),
                 str(self.origine), str(o))
        pol = o / ".socle/policy.toml"
        relecture = 'review = "lots"\n' if mode == "compagnon" else ""
        pol.write_text(pol.read_text() + f'\n[private]\nmode = "{mode}"\n' + relecture)
        if mode == "compagnon":
            depot = self.dossier / "prive-origine"
            if not depot.is_dir():
                (depot / "journal").mkdir(parents=True)
                (depot / "canonical.md").write_text(CANONIQUE_PRIVEE)
                (depot / "terms.txt").write_text("# socle: termes privés\nMistral\n")
                self.git(depot, "init", "-q", "-b", "main")
                self.git(depot, "add", "-A")
                self.git(depot, "commit", "-q", "-m", "mémoire privée d'essai")
            (o / ".gitignore").write_text(((o / ".gitignore").read_text() if (o / ".gitignore").is_file() else "")
                                          + "memory/private/\n")
            sha = self.git(depot, "rev-parse", "HEAD").strip()
            (o / ".socle/private.lock").write_text(f'commit = "{sha}"\n')
        else:
            (o / ".gitattributes").write_text("memory/private/** filter=essai\n")
            (o / "memory/private").mkdir(parents=True)
            (o / "memory/private/canonical.md").write_text(CANONIQUE_PRIVEE)
        self.git(o, "add", "-A")
        self.git(o, "commit", "-q", "--no-verify", "-m", f"Mémoire privée, mode {mode}")
        return o

    def filtre(self) -> tuple[str, ...]:
        """Le « chiffrement » d'essai : un filtre git réversible, comme
        git-crypt en pose un ; le moteur ne connaît pas l'outil."""
        f = self.dossier / "filtre.py"
        with self._verrou:
            if not f.is_file():
                f.write_text(FILTRE_ESSAI)
        return (f"filter.essai.clean={sys.executable} {f} clean", f"filter.essai.smudge={sys.executable} {f} smudge")

    def clone_prive(self, mode: str, cle: bool = True, compagnon: bool = True) -> Path:
        """Un clone d'une origine à mémoire privée : avec la clé du filtre
        (mode chiffré) ou le clone du dépôt privé (mode compagnon), ou sans."""
        o = self.origine_privee(mode)
        c = self.clone(o, self.filtre() if mode == "chiffre" and cle else ())
        if mode == "compagnon" and compagnon:
            self.git(c, "clone", "-q", "--no-local", str(self.dossier / "prive-origine"), "memory/private")
        return c

    def commit(self, c: Path, message: str, verifier: bool = False, env=None):
        self.git(c, "add", "-A")
        args = ["commit", "-q", "-m", message] + ([] if verifier else ["--no-verify"])
        return self.run(c, "git", *args, env=env)

    def nettoyer(self):
        shutil.rmtree(self.dossier, ignore_errors=True)


# --------------------------------------------------------------------------
# Les étages, par leurs vrais points d'entrée
# --------------------------------------------------------------------------


def etage_git(a: Atelier, c: Path, env=None) -> str:
    """Le hook pre-commit, sur un commit réel : rend la sortie s'il refuse."""
    a.git(c, "add", "-A")
    r = a.run(c, "git", "commit", "-q", "-m", "essai", env=env)
    return "" if r.returncode == 0 else r.stdout + r.stderr


def etage_ci(a: Atelier, c: Path, message: str = "essai", env=None) -> str:
    if a.run(c, "git", "status", "--porcelain").stdout.strip():
        r = a.commit(c, message, env=env)
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
    r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main")
    return "" if r.returncode == 0 else r.stdout + r.stderr


def etage_push(a: Atelier, c: Path, hooks: bool = True, env=None) -> str:
    """Le hook pre-push, sur un push réel vers l'origine : rend la sortie s'il
    refuse. Chaque clone pousse sur sa branche : l'origine est partagée."""
    r = a.run(c, "git", "push", "-q", *([] if hooks else ["--no-verify"]), "origin", f"HEAD:refs/heads/essai-{c.name}",
              env=env)
    return "" if r.returncode == 0 else r.stdout + r.stderr


def ci_exigee(a: Atelier, c: Path) -> dict:
    """Un `gh` qui dit la CI du socle exigée avant toute fusion sur la branche
    par défaut, comme l'installation le conseille : l'environnement à passer
    aux étages (D-0071)."""
    from socle import config, state as etat

    ci = etat.nom_de_la_ci(config.Projet.charger(c))
    regles = json.dumps([{"type": "required_status_checks",
                          "parameters": {"required_status_checks": [{"context": ci}]}}], ensure_ascii=False)
    dossier = c.parent / f"{c.name}-gh"
    dossier.mkdir(exist_ok=True)
    gh = dossier / "gh"
    gh.write_text(f"#!/bin/sh\ncase \"$2\" in\n  *rules/branches/*) echo '{regles}' ;;\n  *) echo '{{}}' ;;\nesac\n")
    gh.chmod(0o755)
    return {"PATH": f"{dossier}{os.pathsep}{a.env.get('PATH', os.environ.get('PATH', ''))}"}


def protege_en_attente(a: Atelier, c: Path) -> None:
    """Une mise à jour en session cloud (B-0115) : un fichier protégé changé
    dans l'arbre, et la demande poussée qui le cite avec son empreinte."""
    from socle import fingerprint as empreintes

    ajouter(c, ".github/CODEOWNERS", "# une ligne de plus\n")
    nouveau = (c / ".github/CODEOWNERS").read_text()
    cite = empreintes.courte(empreintes.fichier(c / ".github/CODEOWNERS"))
    a.git(c, "checkout", "-q", "--", ".github/CODEOWNERS")
    ajouter(c, "memory/requests/D-0001-refactor.md", demande_bonne(a, c).replace(
        "## Où regarder", f"- `.github/CODEOWNERS` et `{cite}` — le fichier protégé changé.\n\n## Où regarder", 1))
    pousser(a, c, "La demande")
    (c / ".github/CODEOWNERS").write_text(nouveau)


def _valeur_en_attente(a: Atelier, c: Path) -> None:
    """La valeur attendue de `test_double` changée dans l'arbre, sous la
    demande poussée qui nomme le test (D-0147)."""
    ajouter(c, "memory/requests/D-0001-refactor.md", _demande_nommant_le_test(a, c))
    pousser(a, c, "La demande")
    remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
    maj_memoire(c, "Le test suit la demande, en attendant la réponse.")


def _pousser_un_cas_de_plus(a: Atelier, c: Path) -> None:
    """Un cas de plus pour `double`, que seule la branche a, poussé par le
    hook avant push, qui garde le commit poussé (ADR-0104)."""
    ajouter(c, "tests/test_calc.py", "    def test_double_de_trois(self):\n        self.assertEqual(double(3), 6)\n")
    maj_memoire(c, "Un cas de plus pour double.")
    a.commit(c, "Un cas de plus")
    refus = etage_push(a, c)
    if refus:
        raise RuntimeError(refus)


def _demande_d_une_mise_a_jour(a: Atelier, c: Path, fichiers: int, prose: str = "") -> None:
    """La demande qui approuve une mise à jour : chaque fichier protégé sur
    sa ligne d'empreinte (ADR-0058), ou la même ligne suivie de prose."""
    liste = "".join(f"- `.socle/engine/socle/module_{i}.py` — `sha256:{i:015x}a`{prose}\n" for i in range(fichiers))
    ajouter(c, "memory/requests/D-0001-refactor.md",
            demande_bonne(a, c).replace("## Où regarder", f"{liste}\n## Où regarder", 1))


def etage_stop(a: Atelier, c: Path, dernier_message: str | None = None) -> str:
    """Le hook de fin de tour. Avec `dernier_message`, un transcript au format
    de Claude Code lui donne le dernier message de l'agent à lire."""
    entree = {"session_id": "autotest", "stop_hook_active": False}
    if dernier_message is not None:
        transcript = c.parent / f"{c.name}-transcript.jsonl"
        transcript.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in (
            {"type": "user", "message": {"role": "user", "content": "fais le travail"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": dernier_message}]}},
        )) + "\n")
        entree["transcript_path"] = str(transcript)
    r = a.socle(c, "hook", "stop", entree=json.dumps(entree))
    if not r.stdout.strip():
        return ""
    sortie = json.loads(r.stdout)
    return sortie.get("reason", "") if sortie.get("decision") == "block" else ""


def _etage_stop_apres_refus(a: Atelier, c: Path, refuse: str, corrige: str) -> str:
    """Deux fins de tour du même tour, au format de Claude Code : `refuse`,
    que le hook doit refuser, puis, après la pièce jointe de ce refus,
    `corrige`, jugé à la relance du hook (`stop_hook_active`). Rend ce que la
    relance dit à l'humain, ou pourquoi le premier message n'est pas
    refusé (B-0371)."""
    transcript = c.parent / f"{c.name}-transcript.jsonl"

    def agent(texte: str) -> dict:
        return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": texte}]}}

    def fin(relance: bool) -> dict:
        r = a.socle(c, "hook", "stop", entree=json.dumps({"session_id": "autotest", "stop_hook_active": relance,
                                                          "transcript_path": str(transcript)}))
        return json.loads(r.stdout) if r.stdout.strip() else {}

    transcript.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in (
        {"type": "user", "message": {"role": "user", "content": "fais le travail"}}, agent(refuse))) + "\n")
    premier = fin(False)
    if premier.get("decision") != "block":
        return f"le premier message n'est pas refusé : {premier}"
    with transcript.open("a", encoding="utf-8") as f:
        for x in ({"type": "attachment", "attachment": {"type": "hook_blocking_error", "hookName": "Stop",
                                                         "hookEvent": "Stop",
                                                         "blockingError": {"blockingError": premier["reason"]}}},
                  agent(corrige)):
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    second = fin(True)
    return second.get("reason", "") if second.get("decision") == "block" else second.get("systemMessage", "")


def etage_demarrage(a: Atelier, c: Path) -> str:
    """Le hook de démarrage de session : il imprime l'état dérivé."""
    return a.socle(c, "hook", "session-start", entree=json.dumps({"session_id": "autotest", "source": "startup"})).stdout


def etage_outil(a: Atelier, c: Path, outil: str, args: dict, cwd: Path | None = None) -> str:
    entree = {"session_id": "autotest", "tool_name": outil, "tool_input": args}
    if cwd is not None:
        entree["cwd"] = str(cwd)
    r = a.socle(c, "hook", "pre-tool-use", entree=json.dumps(entree))
    if not r.stdout.strip():
        return ""
    sortie = json.loads(r.stdout).get("hookSpecificOutput", {})
    return sortie.get("permissionDecisionReason", "") if sortie.get("permissionDecision") == "deny" else ""


def ajouter(c: Path, rel: str, bloc: str):
    p = c / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((p.read_text() if p.is_file() else "").rstrip("\n") + "\n" + bloc)


def remplacer(c: Path, rel: str, avant: str, apres: str):
    p = c / rel
    t = p.read_text()
    if avant not in t:
        raise RuntimeError(trad("injection impossible : « {avant} » absent de {rel}", avant=avant, rel=rel))
    p.write_text(t.replace(avant, apres, 1))


def empreinte(a: Atelier, c: Path, cible: str) -> str:
    """L'empreinte d'une entrée ou d'un index, lue comme l'agent la lit :
    dans la sortie de `socle show`."""
    args = ["show", "--index", cible] if cible in ("decisions", "backlog") else ["show", cible]
    sortie = a.socle(c, *args).stdout
    m = re.search(rf"{re.escape(cible)}@([0-9a-f]{{8}})", sortie)
    if not m:
        raise RuntimeError(trad("pas d'empreinte pour {cible} : {sortie}", cible=cible, sortie=sortie[:200]))
    return m.group(1)


# Les trois paragraphes qui ouvrent le contexte d'une demande récente
# (ADR-0046).
PARAGRAPHES_DU_CONTEXTE = (
    "**Le projet.** Un module de calcul, petit et public, que d'autres projets importent pour doubler et "
    "multiplier des nombres.\n\n"
    "**Le chantier.** Le backlog demande d'y ajouter une fonction triple ; rien n'est encore écrit, et aucune "
    "décision passée ne porte sur la forme du module.\n\n"
    "**La question.** Ajouter triple sur le modèle de double dupliquerait sa logique, d'où le choix d'une "
    "refonte avant d'écrire.\n\n")


def demande_bonne(a: Atelier, c: Path) -> str:
    return DEMANDE_BONNE.replace("- B-0001 —", f"- B-0001@{empreinte(a, c, 'B-0001')} —")


SKILL_ESSAI = """---
name: verifier-calc
description: Vérifier le module de calcul avant de le livrer, ses tests et sa documentation. À utiliser quand le module de calcul change.
---

# Vérifier le module de calcul

```sh
python3 -m unittest discover -s tests -q
```

Ne jamais lancer `git commit --no-verify` : la CI exécute tout.
"""


def _poser_skill(c: Path, texte: str):
    """Le skill d'essai, son en-tête en tête du fichier, là où l'agent le lit."""
    p = c / ".claude/skills/verifier-calc/SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texte)


def _demande_de_choix(a: Atelier, c: Path, cite: str) -> str:
    """La demande saine, en choix entre deux réponses dont aucune n'est
    `valider`, qui cite `cite` à l'appui de sa recommandation."""
    return (demande_bonne(a, c)
            .replace("Vérifié : un seul appelant.", f"Vérifié : un seul appelant, que {cite} exerce.")
            .replace("- `valider` — je refonds d'abord.", "- `refondre` — je refonds d'abord.")
            .replace("- `refuser` — j'ajoute tel quel.", "- `ajouter` — j'ajoute tel quel."))


ADR_ESSAI = """<!-- socle: couche=decisions zone=publique -->
# ADR-0001 — Garder une seule fonction de multiplication

> statut : acceptée · date : 2026-10-10{lu}

## Contexte

Le fait {fait} établit que `double` multiplie par une constante.

## Décision

Toute nouvelle multiplication passe par la même constante.
"""


MESSAGE_AGENT = ("Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nSocle-Agent: claude-code\n"
                 "Socle-Hooks: SessionStart=1 PreToolUse=4 Stop=1")


def _adr_test_double(a: "Atelier", c: Path) -> str:
    """Une décision qui nomme le test `test_double`, et prouve ses lectures."""
    return ("<!-- socle: couche=decisions zone=publique -->\n# ADR-0001 — Le test de double compare à un flottant\n\n"
            f"> statut : acceptée · date : 2026-10-10 · lu : decisions@{empreinte(a, c, 'decisions')}\n\n"
            "## Décision\n\n`test_double` compare désormais le résultat à un flottant.\n")


DEPOT_ESSAI = "https://github.com/essai/calc"
RECAP = "\n\nPour toi : rien.\nEnsuite : rien."
# Une sortie collée dans un bloc de code au récap, qui finit par sa propre
# ligne « Ensuite : », comme le format compact que `socle roadmap` rendait
# avant sa forme unique : elle ne tient pas lieu de récap (ADR-0089).
COMPACT_COLLE = ("JA-0001  Le premier jalon      0/1 besoins clos\n"
                 " ▶ L-0001  Le premier lot  0/1  en cours\n"
                 "Hors lot : rien\n"
                 "Ensuite : JA-0002 Le second jalon (B-0002)")
# La forme unique de `socle roadmap`, dans son rendu du terminal, collée de
# même au récap de la clôture d'un lot : sa ligne « Pour toi : » ne tient pas
# lieu de celle du récap.
FORME_COLLEE = ("La suite de calc — 27 novembre\n\n"
                "Maintenant\n ▶ Le premier lot (L-0001)\n   reste : Écrire triple (T-0001)\n\n"
                "Ensuite\n1. [0/1] Le premier jalon (JA-0001)\n\n"
                "Pour toi : copier les données (B-0002)")


def _demande_nommant_le_test(a: "Atelier", c: Path) -> str:
    """Une demande au contrat qui nomme `test_double`, pour en changer la
    valeur attendue."""
    return demande_bonne(a, c).replace(
        "## Où regarder", "- `test_double` — le test du module, qui attend le double de deux.\n\n## Où regarder", 1)


def _demande_nommant_la_cle(a: "Atelier", c: Path) -> str:
    """Une demande au contrat qui nomme la clé des garde-fous
    `staleness.active_days`, pour la relâcher."""
    return demande_bonne(a, c).replace(
        "## Où regarder", "- `staleness.active_days` — la péremption du chantier actif, de 7 à 14 jours.\n\n"
                          "## Où regarder", 1)


def _pousser_la_reponse(a: "Atelier", c: Path, avec_le_test: bool, cle: bool = False) -> tuple[int, str]:
    """La demande qui nomme `test_double` (ou, avec `cle`, la clé des
    garde-fous `staleness.active_days`), poussée ; la réponse `valider` de
    l'humain, consignée et commitée, avec le changement qu'elle autorise ou
    sans lui ; puis le push, par le hook avant push : son code et sa
    sortie."""
    demande = _demande_nommant_la_cle(a, c) if cle else _demande_nommant_le_test(a, c)
    (c / "memory/requests/D-0001-refactor.md").write_text(demande)
    pousser(a, c)
    (c / "citation.txt").write_text("oui, compare à un flottant")
    r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
    (c / "citation.txt").unlink()
    if r.returncode != 0:
        return r.returncode, r.stdout + r.stderr
    if avec_le_test and cle:
        remplacer(c, ".socle/guardrails.toml", "active_days = 7", "active_days = 14")
    elif avec_le_test:
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
    a.commit(c, "La réponse de Théo")
    r = a.run(c, "git", "push", "-q", "origin", f"travail:{c.name}")
    return r.returncode, r.stdout + r.stderr


def _changer_sous_une_validation_fusionnee(a: "Atelier", c: Path, tache: str | None, avec_le_test: bool = False,
                                           bouge: bool = False) -> str:
    """La demande qui nomme `test_double`, poussée, sa réponse `valider`,
    et, si `tache` est un statut, la tâche T-0001 qui la cite ; avec
    `avec_le_test`, la valeur attendue changée dans le même commit. Le
    tout fusionné dans la branche par défaut de ce clone seul (l'origine
    est partagée). Avec `bouge`, le test change ensuite dans la branche par
    défaut, d'un commentaire. Puis une nouvelle valeur attendue sur la
    branche : ce qu'en dit la CI (D-0189, piste B)."""
    (c / "memory/requests/D-0001-refactor.md").write_text(_demande_nommant_le_test(a, c))
    pousser(a, c, "La demande")
    (c / "citation.txt").write_text("oui, compare à un flottant")
    r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
    (c / "citation.txt").unlink()
    if r.returncode != 0:
        return r.stdout + r.stderr
    if tache:
        statut = "fait · ref : D-0001" if tache == "fait" else tache
        ajouter_sujet(c, tache_essai(a, c, statut=statut).replace("Pour l'essai.", "Change `test_double` sous "
                                                                                     "D-0001."))
    attendu = "4"
    if avec_le_test:
        attendu = "4.0"
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
    a.commit(c, "La réponse de Théo")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")
    if bouge:
        remplacer(c, "tests/test_calc.py", f"self.assertEqual(double(2), {attendu})",
                  f"self.assertEqual(double(2), {attendu})  # deux fois deux")
        a.commit(c, "Le test commenté")
        a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")
    remplacer(c, "tests/test_calc.py", f"self.assertEqual(double(2), {attendu})",
              "self.assertEqual(double(2), 4.00)")
    maj_memoire(c, "La valeur attendue suit la réponse.")
    return etage_ci(a, c)


def _test_change_sous_une_decision_donnee(a: "Atelier", c: Path, texte: str) -> str:
    """Une décision que l'humain donne de lui-même, `texte`, consignée par
    `socle decision --unprompted` (B-0185), puis la valeur attendue de
    `test_double` changée : ce qu'en dit la CI."""
    (c / "citation.txt").write_text(texte)
    r = a.socle(c, "decision", "Comparer le test du module à un flottant", "--unprompted", "--relayed", "--by",
                "Théo", "--quote-file", "citation.txt")
    (c / "citation.txt").unlink()
    if r.returncode != 0:
        return r.stdout + r.stderr
    remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
    maj_memoire(c)
    return etage_ci(a, c)


def _pousser_des_etapes_lentes(a: "Atelier", c: Path) -> tuple[int, str]:
    """Un test d'un peu plus d'une seconde, commité, puis poussé par le hook
    avant envoi, qui lance les étapes rapides : son code et sa sortie."""
    ajouter(c, "tests/test_lent.py", TEST_LENT)
    maj_memoire(c, "Un test plus lent.")
    a.commit(c, "Un test plus lent")
    r = a.run(c, "git", "push", "-q", "origin", f"travail:{c.name}")
    return r.returncode, r.stdout + r.stderr


def _seuil_rapide_nan_en_base(a: "Atelier", c: Path) -> None:
    """Le seuil des étapes rapides à `nan`, à la base de la CI de ce clone
    seulement : l'origine est partagée."""
    remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = 300", "fast_max_seconds = nan")
    a.commit(c, "le seuil à nan")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")


def _lot_de_deux_taches(a: "Atelier", c: Path, seuil: int) -> tuple[str, str]:
    """Un lot ouvert qui attend deux tâches, sous `[batches] max_tasks =
    seuil` : ce qu'en disent l'état du démarrage, puis le rappel de fin de
    tour d'un dernier message sans récap (B-0233)."""
    remplacer(c, ".socle/guardrails.toml", "max_tasks = 9", f"max_tasks = {seuil}")
    ajouter_sujet(c, tache_essai(a, c))
    ajouter_sujet(c, tache_essai(a, c).replace("T-0001 — Écrire triple", "T-0002 — Écrire quadruple"))
    ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001, T-0002"))
    return etage_demarrage(a, c), etage_stop(a, c, "J'ai formé le lot.")


def pousser(a: Atelier, c: Path, message: str = "essai"):
    """Commit et push de la branche de travail vers l'origine d'essai, sous
    le nom du clone : les cas partagent la même origine."""
    if a.run(c, "git", "status", "--porcelain").stdout.strip():
        r = a.commit(c, message)
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
    a.git(c, "push", "-q", "--no-verify", "-u", "origin", f"travail:{c.name}")


def tous_refuses(a: Atelier, c: Path, essais: list[tuple[str, dict]], cwd: Path | None = None) -> str:
    """Chaque appel doit être refusé par le hook de l'agent : leurs raisons,
    ou le premier qui passe, sans raison, pour que le défaut se dise non
    attrapé. `cwd`, le dossier courant de l'agent."""
    raisons = []
    for outil, args in essais:
        refus = etage_outil(a, c, outil, args, cwd)
        if not refus:
            return f"passé sans refus : {outil} {json.dumps(args, ensure_ascii=False)[:200]}"
        raisons.append(refus)
    return "\n".join(raisons)


# Une mutation factice : l'adaptateur du projet d'essai n'a pas
# de mutation, et `mutation.couverture` ne s'y exerçait jamais. Le balayage
# se simule par une sortie de mutmut écrite à la main.
MUTATION_FACTICE = """[capabilities.mutation]
command = "python3 -c pass"
parser = "mutmut"
modules = ["*.py"]

"""


def avec_mutation(c: Path):
    p = c / ".socle/adapter.toml"
    t = p.read_text()
    debut = t.index("[capabilities.mutation]")
    fin = t.index("\n[", debut) + 1
    p.write_text(t[:debut] + MUTATION_FACTICE + t[fin:])


# `gh`, simulé : l'état du workflow de mutation et sa dernière exécution,
# d'hier.
GH_FACTICE = """#!{python}
import json, sys
from datetime import datetime, timedelta, timezone
chemin = sys.argv[2] if sys.argv[1:2] == ["api"] else ""
hier = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
if chemin.endswith("/actions/workflows/socle-mutation.yml") and "{etat}" == "inconnu":
    sys.stderr.write("gh: Not Found (HTTP 404)\\n")
    sys.exit(1)
elif chemin.endswith("/actions/workflows/socle-mutation.yml"):
    print(json.dumps({{"state": "{etat}", "created_at": "2026-01-01T00:00:00Z"}}))
elif "/actions/workflows/socle-mutation.yml/runs?" in chemin:
    print(json.dumps({{"workflow_runs": [{{"created_at": hier}}]}}))
else:
    sys.exit(1)
"""


def _balayage_planifie(a: "Atelier", c: Path, etat: str, jours: int = 0) -> dict:
    """Le projet d'essai avec un balayage planifié, posé à la base il y a
    `jours` jours : la mutation factice, son workflow et la doc qui le nomme.
    Rend l'environnement où `gh`, simulé, dit l'état du workflow
    (`inconnu` : GitHub ne le connaît pas)."""
    avec_mutation(c)
    (c / ".github/workflows/socle-mutation.yml").write_text('name: Socle — mutation\non:\n  schedule:\n'
                                                            '    - cron: "23 2 * * 2"\n')
    ajouter(c, "docs/calc.md", "\nLe balayage de mutation, chaque semaine : `socle-mutation.yml`.\n")
    date = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    a.commit(c, "balayage planifié", env={"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date})
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")
    outils_ = c.parent / f"{c.name}-bin"
    outils_.mkdir()
    gh = outils_ / "gh"
    gh.write_text(GH_FACTICE.format(python=sys.executable, etat=etat))
    gh.chmod(0o755)
    return {"PATH": f"{outils_}{os.pathsep}{a.env.get('PATH', '')}"}


def _adopte_avec_une_reference_morte(a: "Atelier", c: Path):
    """Le projet d'essai adopté avec une référence morte d'avant
    l'installation, tolérée par l'installeur lui-même, posé à la base
    (B-0180)."""
    from socle import installer as installeur

    ajouter(c, "docs/calc.md", "Voir F-0098.\n")
    ajouter(c, ".socle/guardrails.toml", '\n[adoption]\nwarn_only = ["memoire.references"]\n')
    installeur.consigner_tolerances(c)
    a.commit(c, "adoption")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")


def balayage(c: Path, lignes: str) -> Path:
    d = c.parent / f"{c.name}-mutants"
    d.mkdir(exist_ok=True)
    (d / "mutmut-results.txt").write_text(lignes)
    return d


def _collision(a: "Atelier", c: Path) -> str:
    """La branche par défaut avance, dans ce clone seulement, avec un B-0002
    pris par une autre branche ; la branche de travail, partie d'avant, prend
    B-0002 pour un autre sujet. Rend le point de divergence, la
    base de la CI."""
    point = a.git(c, "rev-parse", "HEAD").strip()

    def prendre(titre: str):
        ajouter_sujet(c, f"\n## B-0002 — {titre}\n\n> statut : ouvert · origine : {a.journal} · "
                f"lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n{SATISFAIT_ESSAI}")

    a.git(c, "switch", "-q", "-c", "autre")
    prendre("Documenter le module")
    a.commit(c, "un sujet sur une autre branche")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")
    a.git(c, "switch", "-q", "travail")
    prendre("Ajouter une fonction quadruple")
    a.commit(c, "un sujet ici")
    return point


def ajouter_sujet(c: Path, bloc: str):
    """Une entrée de plus au backlog, écrite `## B-… — titre` (ou `T-`,
    `L-`, `JA-`), ses métadonnées, son corps : dans son propre fichier, son
    titre remonté d'un niveau."""
    from socle import config, memory as memoire, utils as outils

    ch = config.FORMAT_ACTUEL
    m = re.match(r"\s*## ((?:B|T|L|JA)-\d{4}) — (.+)", bloc)
    texte = "<!-- socle: couche=backlog zone=publique -->\n" + bloc.strip("\n").replace("## ", "# ", 1) + "\n"
    rel = f"{ch.backlog}/{m[1]}-{memoire.nom_de_fichier(m[2])}.md"
    # Un sujet clos va d'emblée avec les clos.
    if any(e.statut in memoire.BACKLOG_CLOS for e in memoire.analyser(rel, texte).entrees):
        rel = f"{ch.backlog}/{memoire.DOSSIER_CLOS}/{rel.rsplit('/', 1)[-1]}"
    outils.ecrire(c / rel, texte)


def _sujet(c: Path, ident: str) -> str:
    """Le fichier qui porte un sujet du backlog, quel que soit le format."""
    from socle import memory as memoire

    return memoire.Memoire.charger(c).entree(ident).fichier


def _clore(c: Path, ident: str):
    """Clôt un sujet du backlog, avec sa référence, sans le déplacer."""
    p = c / _sujet(c, ident)
    p.write_text(re.sub(r"(?m)^> statut : ouvert( · [^\n]*)?$",
                        lambda m: "> statut : fait" + (m[1] or "") + " · ref : fichier:calc.py", p.read_text(), count=1))


def _consigne(a: Atelier, ident: str = "C-0001", statut: str = "en vigueur") -> str:
    return CONSIGNE_ESSAI.format(ident=ident, statut=statut, journal=a.journal)


def _consigne_en_base(a: Atelier, c: Path):
    """La consigne C-0001, en vigueur, dans la base : commitée, et la branche
    par défaut avancée jusqu'à elle, dans ce clone seulement."""
    ajouter(c, "memory/directives.md", _consigne(a))
    a.commit(c, "une consigne de l'humain")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")


def _jalon_en_base(a: Atelier, c: Path, apres: str | None = "B-0001"):
    """Le jalon ouvert JA-0001, qui attend `apres` (rien : `None`), dans la
    base : commité, et la branche par défaut avancée jusqu'à lui, dans ce
    clone seulement."""
    ajouter_sujet(c, "\n## JA-0001 — Le module complet\n\n"
                     f"> statut : ouvert · origine : {a.journal} · " + (f"après : {apres} · " if apres else "")
                     + f"lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")
    a.commit(c, "un jalon ouvert")
    a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")


def _clore_le_jalon(c: Path):
    """Clôt JA-0001 à la main, avec sa référence, rangé parmi les clos."""
    from socle import memory as memoire

    p = c / _sujet(c, "JA-0001")
    clos = p.parent / memoire.DOSSIER_CLOS / p.name
    clos.parent.mkdir(parents=True, exist_ok=True)
    clos.write_text(p.read_text().replace("> statut : ouvert", "> statut : fait · ref : fichier:calc.py", 1))
    p.unlink()


def _renumeroter_en_lot(c: Path, ident: str) -> str:
    """Le besoin `ident`, écrit lot comme avant ADR-0083 (`forme : lot`),
    renuméroté par la migration de la mise à jour : il prend le préfixe `L-`
    et garde son ancien numéro (`ancien : ident`). Rend son numéro nouveau,
    que les branches d'autres cas, poussées sur l'origine, peuvent décaler."""
    from socle import migration

    remplacer(c, _sujet(c, ident), "> statut : ouvert", "> statut : ouvert · forme : lot")
    return dict(migration.migrer_backlog(c).renumerotees)[ident]


def _citer_par_l_ancien_numero(a: Atelier, c: Path, ancien: str, h: str):
    """Une entrée de journal qui cite une entrée renumérotée par son ancien
    numéro, sous l'empreinte `h`."""
    ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
            f"\n## {a.journal[:-1]}B — Constat\n\nVoir {ancien}@{h}.\n")
    maj_memoire(c, "Le backlog migré en quatre formes.")


# L'historique des revues d'un lot (ADR-0084, ADR-0100) : les corrections
# successives du code, une par passe, et ce que l'agent consigne au retour du
# relecteur.
CORRECTIONS = ("return x * FACTEUR", "return (x * FACTEUR)", "return (FACTEUR * x)", "return ((x * FACTEUR))",
               "return FACTEUR * (x)")


def _bloquant_essai() -> str:
    return "\n- Bloquant : la correction change la lecture du facteur\n- Ouvre : rien\n"


# Un paragraphe de l'agent sous les bloquants d'une passe, replié sur une
# ligne qui commence par « bloquants » : ce n'est pas une ligne de bloquant.
NOTE_REPLIEE = ("\nLa passe relit la correction de la multiplication ; ses\nbloquants sont consignés au-dessus, "
                "un par ligne.\n")


def _passes(a: Atelier, c: Path, consignes: list[str]) -> str:
    """Le lot L-0001 en cours, qui attend la tâche T-0001 ; puis, pour
    chaque consigne, une correction du code commitée, une passe de `socle
    review` et la consigne ajoutée au lot ; enfin une passe de plus : la
    sortie de `socle review` s'il la refuse, rien s'il la produit."""
    ajouter_sujet(c, tache_essai(a, c))
    ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001").replace("> statut : ouvert", "> statut : en cours"))
    precedent = "return FACTEUR * x"
    for i, consigne in enumerate([*consignes, None]):
        remplacer(c, "calc.py", precedent, CORRECTIONS[i])
        precedent = CORRECTIONS[i]
        a.commit(c, f"la passe {i + 1}")
        r = a.socle(c, "review")
        if consigne is None:
            return "" if r.returncode == 0 else r.stdout + r.stderr
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)
        ajouter(c, _sujet(c, "L-0001"), consigne)
    return ""


def _lot_relu_clos(a: Atelier, c: Path, *suivantes: str):
    """La tâche T-0001 faite, et le lot L-0001 qui l'attendait clos « fait »,
    sa passe 1 et son bloquant, puis une passe par consigne de `suivantes`,
    à partir de la deuxième."""
    revues = "\n## Revues\n\n### Passe 1 — 2026-11-16\n\nCommits : 1a2b3c4..5d6e7f8\n" + _bloquant_essai()
    for i, consigne in enumerate(suivantes, start=2):
        revues += f"\n### Passe {i} — 2026-11-{15 + i}\n\nCommits : 5d6e7f8..9a8b7c6\n" + consigne
    ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : fichier:calc.py"))
    ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001", " · ref : fichier:calc.py").replace(
        "> statut : ouvert", "> statut : fait") + revues)
    maj_memoire(c, "Le lot de la multiplication relu et clos.")


def _lot_en_cours_relu(a: Atelier, c: Path, bloquant: str):
    """Le lot L-0001 en cours, qui attend la tâche T-0001, et sa passe 1, où
    l'agent consigne la ligne `bloquant`, puis un paragraphe dont une ligne
    repliée commence par « bloquants »."""
    revues = ("\n## Revues\n\n### Passe 1 — 2026-11-16\n\nCommits : 1a2b3c4..5d6e7f8\n\n" + bloquant +
              "\n- Ouvre : rien\n" + NOTE_REPLIEE)
    ajouter_sujet(c, tache_essai(a, c))
    ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001").replace("> statut : ouvert", "> statut : en cours") + revues)
    maj_memoire(c, "Le lot de la multiplication en revue.")


def _declarer_ui_tierce(a: Atelier, c: Path):
    """L'interface, travaillée par d'autres sessions d'agents, déclarée tierce
    par l'humain qui l'approuve, dans un commit à lui (B-0169)."""
    remplacer(c, ".socle/guardrails.toml", TIERS_VIDE, '\npaths = ["ui/**"]\n')
    r = a.socle(c, "approve", "--keys", "thirdparty.paths", "--text", "L'interface, travaillée ailleurs")
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    r = a.commit(c, "L'interface déclarée tierce")
    if r.returncode != 0:
        raise RuntimeError(r.stderr)


def maj_memoire(c: Path, texte: str = "Travail en cours sur l'essai."):
    remplacer(c, "memory/active.md", "## En cours\n\nRien pour l'instant.", f"## En cours\n\n{texte}")


def _clone_d_un_clone(a: Atelier, c: Path, ref: str | None) -> Path:
    """Un commit de `c` que seul `ref` garde (aucun ref, s'il est `None`),
    cité par la mémoire du clone ; puis un clone de `c` tel qu'un agent le
    fait hors de GitHub, qui ne reçoit pas les objets qu'aucun ref
    n'atteint (`--no-local`, B-0175)."""
    a.git(c, "checkout", "-q", "-b", "piste")
    (c / "piste.txt").write_text("piste\n")
    a.commit(c, "piste")
    sha = a.git(c, "rev-parse", "HEAD").strip()
    if ref:
        a.git(c, "update-ref", ref, sha)
    a.git(c, "checkout", "-q", "travail")
    a.git(c, "branch", "-q", "-D", "piste")
    maj_memoire(c, f"Repris de la piste (commit:{sha[:7]}).")
    a.commit(c, "essai")
    d = c.parent / f"{c.name}-clone"
    a.git(a.dossier, "clone", "-q", "--no-local", str(c), str(d))
    a.git(d, "config", "core.hooksPath", ".socle/git-hooks")
    return d


def _ranger(a: Atelier, c: Path, pousser: bool = True) -> Path:
    """Le rangement de la session qui part, `c`, dans une origine nue à soi :
    l'origine partagée reçoit les branches des autres cas, que la garde
    lirait. Commité, et poussé si `pousser`. Rend le chemin de l'origine."""
    nu = c.parent / f"{c.name}-nu"
    a.git(a.dossier, "clone", "-q", "--bare", "--no-local", "--single-branch", "--branch", "main", str(a.origine),
          str(nu))
    a.git(c, "remote", "set-url", "origin", str(nu))
    a.git(c, "fetch", "-q", "origin")
    maj_memoire(c, "La passation de l'essai.")
    a.commit(c, "le rangement")
    if pousser:
        a.git(c, "push", "-q", "--no-verify", "-u", "origin", "travail")
    return nu


def _ecrire_la_passation(a: Atelier, c: Path, commiter: bool = True, pousser: bool = True):
    """La session qui part, `c`, range (`_ranger`, sans pousser), écrit sa
    passation (`socle handoff write`), la commite en dernier et pousse."""
    _ranger(a, c, pousser=False)
    r = a.socle(c, "handoff", "write")
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    if commiter:
        a.commit(c, "la passation")
    if commiter and pousser:
        a.git(c, "push", "-q", "--no-verify", "-u", "origin", "travail")


def _passation(a: Atelier, c: Path) -> tuple[Path, datetime]:
    """Une passation écrite, commitée et poussée (`_ecrire_la_passation`).
    Rend le clone de la session neuve, et l'heure `écrite` de la
    passation."""
    _ecrire_la_passation(a, c)
    texte = (c / "memory/handoff.md").read_text(encoding="utf-8")
    ecrite = re.search(r"écrite : (\S+)", texte)
    if not ecrite:
        raise RuntimeError(texte)
    neuve = c.parent / f"{c.name}-neuve"
    a.git(a.dossier, "clone", "-q", "--no-local", str(c.parent / f"{c.name}-nu"), str(neuve))
    return neuve, datetime.strptime(ecrite.group(1), "%Y-%m-%dT%H:%M:%SZ")


def _fusion_par_squash(a: Atelier, c: Path):
    """La pull request de la branche passée, fusionnée par squash dans la
    branche par défaut de l'origine de `_ranger`, sa branche supprimée."""
    github = c.parent / f"{c.name}-github"
    a.git(a.dossier, "clone", "-q", "--no-local", str(c.parent / f"{c.name}-nu"), str(github))
    a.git(github, "merge", "-q", "--squash", "origin/travail")
    a.commit(github, "Le lot (#1)")
    a.git(github, "push", "-q", "--no-verify", "origin", "main", ":travail")


def _apres_la_passation(ecrite: datetime) -> dict:
    """L'environnement d'un commit écrit et daté d'une minute après la
    passation."""
    date = (ecrite + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    return {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date}


# La marque d'un commit d'agent, telle que la politique d'essai la reconnaît.
MARQUE_AGENT = "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
BRANCHE_ELAGUEE = "travail-fini"


def _branche_a_elaguer(a: Atelier, c: Path, agent: bool, fusionner: bool = True) -> Path:
    """Un clone d'une origine à soi, nue : la commande y supprime sans
    toucher aux branches que les autres cas poussent sur l'origine commune.
    La branche `travail-fini` y est poussée, d'un commit de l'agent ou de
    l'humain, et fusionnée dans `main` si `fusionner`."""
    # `main` seule : les branches que les autres cas poussent en même temps
    # sur l'origine commune n'y entrent pas.
    origine = a.dossier / f"origine-elagage-{c.name}"
    a.git(a.dossier, "clone", "-q", "--bare", "--no-local", "--single-branch", "--branch", "main", str(a.origine),
          str(origine))
    clone = a.clone(origine)
    a.git(clone, "switch", "-q", "-c", BRANCHE_ELAGUEE, "origin/main")
    ajouter(clone, "calc.py", "\n# fini\n")
    a.commit(clone, "Le travail fini" + (MARQUE_AGENT if agent else ""))
    a.git(clone, "push", "-q", "--no-verify", "origin", BRANCHE_ELAGUEE)
    a.git(clone, "switch", "-q", "travail")
    if fusionner:
        a.git(clone, "push", "-q", "--no-verify", "origin", f"{BRANCHE_ELAGUEE}:main")
    a.git(clone, "fetch", "-q", "origin")
    return clone


def _elagage_vu(a: Atelier, clone: Path, r: subprocess.CompletedProcess) -> str:
    """La sortie de la commande si la branche est restée sur l'origine ;
    rien si elle l'a supprimée : le défaut passe alors inaperçu."""
    restee = a.git(clone, "ls-remote", "--heads", "origin", f"refs/heads/{BRANCHE_ELAGUEE}").strip()
    return r.stdout + r.stderr if restee else ""


def _session_neuve(a: Atelier, neuve: Path) -> subprocess.CompletedProcess:
    """La session neuve, sur une demande de reprendre : `git fetch`, puis
    `socle handoff check` sans argument."""
    a.git(neuve, "fetch", "-q", "origin")
    return a.socle(neuve, "handoff", "check")


# --------------------------------------------------------------------------
# Les défauts du cadrage, puis quelques autres
# --------------------------------------------------------------------------

DEMANDE_BONNE = """<!-- socle: couche=demandes zone=publique -->
# D-0001 — Faut-il refondre le module de calcul avant d'ajouter la fonction triple ?

> date : 2026-10-10

## Décision demandée

Refondre le module de calcul avant d'y ajouter la fonction triple, ou ajouter
la fonction telle quelle.

## Contexte

Le backlog demande une fonction triple dans le module de calcul. Le module ne
contient aujourd'hui qu'une fonction, double, qui multiplie son argument par
une constante du module. Ajouter triple sur le même modèle dupliquerait cette
logique ; une refonte introduirait une fonction générique qui multiplie par
un facteur donné, dont double et triple deviendraient deux cas. La refonte
touche une fonction publique, donc tout appelant existant.

## Éléments cités

- B-0001 — le sujet du backlog qui demande d'ajouter une fonction triple au module.

## Où regarder

- Le module : [calc.py](../../calc.py), fonction `double` ; ce qu'il faut voir : qu'elle est seule et publique.

## Options

Refondre : effort d'une heure, risque faible sur les appelants, réversible.
Ajouter tel quel : effort de dix minutes, risque nul, réversible.

## Conséquences

Si tu valides, je refonds puis j'ajoute ; si tu refuses, j'ajoute tel quel ;
sans réponse, j'ajoute tel quel et je note la refonte au backlog.

## Recommandation

Ajouter tel quel. Vérifié : un seul appelant. Supposé : que d'autres
facteurs ne viendront pas.

## Réponses possibles

- `valider` — je refonds d'abord.
- `refuser` — j'ajoute tel quel.
- `contexte-insuffisant` — je réécris la demande.
"""

DEMANDE_NUE = """<!-- socle: couche=demandes zone=publique -->
# D-0001 — Valider le refactor du module de calcul

> date : 2026-10-10

## Décision demandée

Je propose un refactor du code évoqué en B-0001, tu valides ?

## Contexte

Le refactor évoqué en B-0001 simplifierait la suite.

## Éléments cités

Voir le backlog.

## Options

Refactor ou pas : effort faible, risque faible, réversible.

## Conséquences

Si tu valides, je le fais ; si tu refuses, rien ; sans réponse, j'attends.

## Recommandation

Vérifié : rien. Supposé : que c'est mieux.

## Réponses possibles

- `valider` — je fais le refactor.
- `contexte-insuffisant` — je réécris la demande.
"""


# La liste vide des chemins tiers, telle que l'installeur la pose.
TIERS_VIDE = "\npaths = []\n"


def _cas() -> list[Cas]:
    cas = []

    def defaut(id_, texte, etage, controle):
        def deco(f):
            cas.append(Cas(id_, texte, etage, controle, f))
            return f
        return deco

    @defaut("valeur-divergente", "valeur de la doc divergente de sa source", "git", "docs.valeurs")
    def _(a, c):
        remplacer(c, "docs/calc.md", "-->2<!--", "-->3<!--")
        return etage_git(a, c)

    @defaut("reference-morte", "lien ou identifiant mort", "git", "memoire.references")
    def _(a, c):
        ajouter(c, "docs/calc.md", "Voir F-0099 et [le guide](guide.md).\n")
        return etage_git(a, c)

    @defaut("commit-sans-ref", "commit cité que l'origine ne garde par aucun ref, absent d'un clone neuf", "ci",
            "memoire.references")
    def _(a, c):
        return etage_ci(a, _clone_d_un_clone(a, c, None))

    @defaut("code-sans-doc", "code modifié sans doc associée", "agent", "docs.correspondance")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        maj_memoire(c)
        return etage_stop(a, c)

    @defaut("test-sans-assertion", "test sans assertion", "git", "tests.creux")
    def _(a, c):
        ajouter(c, "tests/test_calc.py", "    def test_rien(self):\n        double(3)\n")
        return etage_git(a, c)

    @defaut("test-tautologique", "assertion tautologique", "git", "tests.creux")
    def _(a, c):
        ajouter(c, "tests/test_calc.py", "    def test_toujours(self):\n        self.assertEqual(double(3), double(3))\n")
        return etage_git(a, c)

    @defaut("test-desactive", "test désactivé sans raison écrite", "git", "tests.creux")
    def _(a, c):
        remplacer(c, "tests/test_calc.py", "    def test_double", "    @unittest.skip\n    def test_double")
        return etage_git(a, c)

    @defaut("assertion-en-commentaire", "test dont la seule assertion est en commentaire", "git", "tests.creux")
    def _(a, c):
        ajouter(c, "tests/test_calc.py", "    def test_rien(self):\n        double(3)  # self.assertEqual(double(3), 6)\n")
        return etage_git(a, c)

    @defaut("groupe-desactive", "classe de tests entière désactivée sans raison écrite", "git", "tests.creux")
    def _(a, c):
        remplacer(c, "tests/test_calc.py", "class TestCalc", "@unittest.skip\nclass TestCalc")
        return etage_git(a, c)

    @defaut("plafond-releve", "plafond de mutation relevé", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", '"calc.py" = { max = 0 }', '"calc.py" = { max = 3, reason = "équivalents" }')
        return etage_ci(a, c)

    @defaut("plafond-remis-a-mesurer", "plafond de mutation remis « à mesurer »", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", '"calc.py" = { max = 0 }', '"calc.py" = { pending = true }')
        return etage_ci(a, c)

    @defaut("plafond-invente", "plafond de mutation écrit à la main, sans la mesure", "ci", "cliquet.garde-fous")
    def _(a, c):
        ajouter(c, "unites.py", "CENTIMES = 100\n")
        remplacer(c, ".socle/guardrails.toml", '"calc.py" = { max = 0 }',
                  '"calc.py" = { max = 0 }\n"unites.py" = { max = 40, reason = "équivalents" }')
        maj_memoire(c, "Un module de constantes.")
        return etage_ci(a, c)

    @defaut("docmap-elargie", "doc ajoutée à une correspondance code ↔ doc", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", 'docs = ["docs/calc.md"]', 'docs = ["docs/calc.md", "README.md"]')
        return etage_ci(a, c)

    @defaut("depot-declare", "autre dépôt déclaré sans validation, pour que ses chemins échappent au contrôle",
            "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", "repos = []", 'repos = ["x.patch"]')
        return etage_ci(a, c)

    @defaut("tiers-declare", "chemin tiers déclaré sans validation, pour qu'un fichier du projet échappe aux "
            "contrôles", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", TIERS_VIDE, '\npaths = ["calc.py"]\n')
        return etage_ci(a, c)

    @defaut("tiers-sur-la-memoire", "chemin tiers qui couvrirait la mémoire", "ci", "config")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", TIERS_VIDE, '\npaths = ["memory/**"]\n')
        a.socle(c, "approve", "--keys", "thirdparty.paths", "--text", "La mémoire comme outil")
        return etage_ci(a, c)

    @defaut("decision-sans-relais", "décision en séance consignée par l'agent sans la citer", "agent",
            "commande humaine")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} decision 'Approuver la spec x' valider"})

    @defaut("budget-releve", "budget de mémoire relevé", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", '"memory/active.md" = { max_bytes = 1600 }', '"memory/active.md" = { max_bytes = 60000 }')
        return etage_ci(a, c)

    @defaut("seuil-rapide-releve", "seuil de durée des étapes rapides relevé", "ci", "cliquet.garde-fous")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = 300", "fast_max_seconds = 900")
        return etage_ci(a, c)

    @defaut("seuil-rapide-nan-releve", "seuil de durée des étapes rapides à `nan` en base, puis relevé",
            "ci", "cliquet.garde-fous")
    def _(a, c):
        # Aucun ordre ne compare `nan` : le relever depuis lui passait sans
        # demande (B-0258).
        _seuil_rapide_nan_en_base(a, c)
        remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = nan", "fast_max_seconds = 900")
        return etage_ci(a, c)

    @defaut("etapes-lentes", "étapes rapides plus longues que leur seuil d'une seconde", "verify", "verify.duree")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = 300", "fast_max_seconds = 1")
        ajouter(c, "tests/test_lent.py", TEST_LENT)
        r = a.socle(c, "verify", "--fast")
        return r.stdout + r.stderr

    @defaut("etapes-lentes-poussees", "étapes rapides plus longues que leur seuil d'une seconde, lancées par le "
            "hook avant envoi", "git", "verify.duree")
    def _(a, c):
        # B-0258 : le hook laisse passer, et le dit sur la sortie du push.
        remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = 300", "fast_max_seconds = 1")
        return _pousser_des_etapes_lentes(a, c)[1]

    @defaut("correctif-sans-test", "correctif sans test de régression", "ci", "tests.regression")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        maj_memoire(c, "Correctif de `double` sur les chaînes.")
        return etage_ci(a, c, "fix: double accepte une chaîne")

    @defaut("correctif-egare-sans-test", "correctif dont le `Corrige:` est hors du dernier paragraphe du message, "
            "sans test de régression", "ci", "tests.regression")
    def _(a, c):
        # Une ligne que git ne lit pas comme un trailer, dans un paragraphe à
        # part, avant les lignes d'attribution : le commit reste un correctif
        # (B-0348, ADR-0109).
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        maj_memoire(c, "Correctif de `double` sur les chaînes.")
        return etage_ci(a, c, MESSAGE_CORRIGE_EGARE)

    @defaut("regression-qui-ne-se-charge-pas", "test de régression qui échoue sur le parent faute de s'y charger",
            "ci", "tests.regression")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        ajouter(c, "calc.py", "\n\ndef triple(x):\n    return 3 * x\n")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        (c / "tests/test_regression.py").write_text(TEST_REGRESSION.replace("from calc import double",
                                                                             "from calc import double, triple"))
        maj_memoire(c, "Correctif de `double` sur les chaînes.")
        return etage_ci(a, c, "fix: double accepte une chaîne")

    @defaut("correctif-de-la-doc-et-d-un-autre-fichier", "correctif de la documentation qui touche aussi un "
            "fichier qu'aucun adaptateur ne juge, sans test", "ci", "tests.regression")
    def _(a, c):
        # B-0373 : la documentation seule n'est pas jugée ; avec un autre
        # fichier, le correctif l'est encore.
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        ajouter(c, "outils/lancer.sh", "#!/bin/sh\npython3 calc.py\n")
        maj_memoire(c, "Correction de la doc de `double` et du lanceur.")
        return etage_ci(a, c, "Correction : la doc de double et le lanceur")

    @defaut("dispense-d-un-autre-commit", "code sans sa doc, couvert par la dispense d'un autre commit", "ci",
            "docs.correspondance")
    def _(a, c):
        maj_memoire(c, "Un renommage interne.")
        a.commit(c, "Renommage\n\nDispense-doc: un renommage interne, rien de visible à documenter")
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        remplacer(c, "memory/active.md", "Un renommage interne.", "Un renommage, puis le calcul retouché.")
        return etage_ci(a, c, "Le calcul retouché")

    @defaut("hook-jamais-tire", "hook de l'agent absent ou jamais tiré", "ci", "hooks.trace")
    def _(a, c):
        maj_memoire(c, "Commit d'agent sans hooks.")
        return etage_ci(a, c, "Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    @defaut("hook-absent-hors-tiers", "commit d'agent sans trace des hooks qui touche un chemin déclaré tiers et "
            "un fichier du projet", "ci", "hooks.trace")
    def _(a, c):
        _declarer_ui_tierce(a, c)
        ajouter(c, "ui/app.py", "def rendu(x):\n    return x\n")
        maj_memoire(c, "L'interface et la mémoire.")
        return etage_ci(a, c, "Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    @defaut("hooks-arretes-en-session", "hooks de l'agent arrêtés depuis le commit précédent", "ci", "hooks.trace")
    def _(a, c):
        maj_memoire(c, "Commit d'agent après l'arrêt de ses hooks.")
        return etage_ci(a, c, "Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
                        "Socle-Agent: claude-code\nSocle-Hooks: SessionStart=1 PreToolUse=4 Stop=1\n"
                        "Socle-Hooks-Since-Commit: PreToolUse=0")

    # Une session d'agent démarrée hors de la racine du projet n'a
    # pas ses hooks ; l'état le dit en tête, le hook avant commit refuse.
    @defaut("hooks-non-charges", "session d'agent démarrée hors de la racine : ses hooks ne sont pas chargés",
            "agent", "hooks non chargés")
    def _(a, c):
        r = a.socle(c, "state", "--short", env={"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "sans-hooks"})
        return "\n".join(l for l in r.stdout.splitlines() if l.startswith("!!"))

    @defaut("commit-sans-filtre", "commit d'agent sans passage du filtre depuis le précédent", "git",
            "commit sans filtre")
    def _(a, c):
        maj_memoire(c, "Commit d'agent sans hooks chargés.")
        a.git(c, "add", "-A")
        r = a.run(c, "git", "commit", "-q", "-m", "essai",
                  env={"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "sans-hooks"})
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("moteur-altere", "moteur altéré dans le projet", "ci", "moteur.empreinte")
    def _(a, c):
        ajouter(c, ".socle/engine/socle/utils.py", "# retouche locale\n")
        return etage_ci(a, c)

    @defaut("politique-alteree", "politique altérée sans validation", "ci", "protege.fichiers")
    def _(a, c):
        remplacer(c, ".socle/policy.toml", "max_attempts = 3", "max_attempts = 30")
        return etage_ci(a, c)

    @defaut("test-renomme", "fichier de test renommé hors des chemins de test : ses tests disparaissent", "ci",
            "tests.attendus")
    def _(a, c):
        a.git(c, "mv", "tests/test_calc.py", "tests/calc_verifications.py")
        maj_memoire(c, "Tests rangés.")
        return etage_ci(a, c)

    @defaut("protege-renomme", "fichier protégé renommé : son ancien chemin disparaît", "ci", "protege.fichiers")
    def _(a, c):
        a.git(c, "mv", ".github/workflows/socle.yml", "ancien-socle.yml")
        return etage_ci(a, c)

    @defaut("protege-au-commit", "fichier protégé changé, commité sans validation", "git", "protege.fichiers")
    def _(a, c):
        remplacer(c, ".socle/policy.toml", "max_attempts = 3", "max_attempts = 30")
        return etage_git(a, c)

    @defaut("protege-en-attente-a-la-ci", "fichier protégé commité sous une demande en attente, la CI du socle "
            "exigée", "ci", "protege.fichiers")
    def _(a, c):
        # D-0071 : il se commite et se pousse, mais la CI le refuse jusqu'à la
        # réponse de l'humain.
        protege_en_attente(a, c)
        a.commit(c, "La mise à jour")
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=ci_exigee(a, c))
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("valeur-attendue-en-attente-a-la-ci", "valeur attendue commitée sous une demande en attente, la CI "
            "du socle exigée", "ci", "tests.attendus")
    def _(a, c):
        # D-0147 : elle se commite et se pousse, mais la CI la refuse jusqu'à
        # la réponse de l'humain.
        _valeur_en_attente(a, c)
        a.commit(c, "Le test suit")
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=ci_exigee(a, c))
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("valeur-attendue-sans-demande-ci-exigee", "valeur attendue commitée sans demande, la CI du socle "
            "exigée", "git", "tests.attendus")
    def _(a, c):
        # La tolérance de D-0147 ne vaut que sous une demande poussée.
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        return etage_git(a, c, env=ci_exigee(a, c))

    @defaut("demande-identifiant-nu", "demande humaine avec identifiant nu", "agent", "demandes.contrat")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"), "content": DEMANDE_NUE})

    @defaut("demande-sans-le-projet", "demande dont le contexte ne part pas du projet : l'humain qui y revient "
            "après des semaines ne sait plus de quoi elle parle", "agent", "contexte du projet")
    def _(a, c):
        # ADR-0046 : la demande saine, datée d'après la règle, sans les trois
        # paragraphes qui ouvrent son contexte.
        recente = demande_bonne(a, c).replace("> date : 2026-10-10", "> date : 2026-11-08")
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"),
                                           "content": recente})

    @defaut("demande-sans-lien", "demande qui ne dit pas où regarder", "agent", "où regarder")
    def _(a, c):
        sans = demande_bonne(a, c).replace("[calc.py](../../calc.py)", "le module")
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"), "content": sans})

    @defaut("demande-sans-valider", "demande qui nomme un test sans proposer `valider` : aucune réponse ne "
            "l'autoriserait", "agent", "geste sans valider")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"),
                                           "content": _demande_de_choix(a, c, "`test_double`")})

    @defaut("reponse-synonyme", "demande qui propose « approuver » au lieu de la réponse de base `valider`", "agent",
            "demandes.contrat")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"),
                                           "content": demande_bonne(a, c).replace("- `valider` —", "- `approuver` —")})

    @defaut("skill-sans-description", "skill dont la description ne dit pas quand s'en servir", "git",
            "skills.contrat")
    def _(a, c):
        _poser_skill(c, SKILL_ESSAI.replace(
            "Vérifier le module de calcul avant de le livrer, ses tests et sa documentation. À utiliser quand le "
            "module de calcul change.", "Vérifier le calcul."))
        return etage_git(a, c)

    @defaut("skill-commande-refusee", "skill qui fait lancer une commande que le hook refuse", "git",
            "skills.commandes")
    def _(a, c):
        _poser_skill(c, SKILL_ESSAI.replace(
            "python3 -m unittest discover -s tests -q", "git commit -q --no-verify -m livraison"))
        return etage_git(a, c)

    @defaut("budget-depasse", "couche de mémoire au-delà de son budget", "git", "memoire.budgets")
    def _(a, c):
        ajouter(c, "memory/active.md", "\n" + ("Une ligne de remplissage pour dépasser le budget. " * 200) + "\n")
        return etage_git(a, c)

    @defaut("empreintes-bavardes", "demande au-delà de son budget, ses fichiers protégés cités avec de la prose",
            "git", "memoire.budgets")
    def _(a, c):
        # Une ligne d'empreinte ne dit qu'un chemin et une empreinte : un
        # mot de plus, et elle compte (ADR-0058).
        _demande_d_une_mise_a_jour(a, c, 150, ", un fichier du moteur que la mise à jour change.")
        return etage_git(a, c)

    @defaut("identifiant-prive", "identifiant privé dans un fichier public", "git", "memoire.prive")
    def _(a, c):
        ajouter(c, "docs/calc.md", "Motivation : voir PJ-2026-10-10-A.\n")
        return etage_git(a, c)

    @defaut("memoire-privee-absente", "mémoire privée non accessible", "agent", "signal indisponible")
    def _(a, c):
        c = a.clone_prive("compagnon", compagnon=False)
        sortie = etage_demarrage(a, c)
        return sortie if "INDISPONIBLE" in sortie else ""

    @defaut("verrou-perime", "mémoire privée commitée sans avancer le verrou", "git", "prive.verrou")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "memory/private/canonical.md", "\nPrécision privée.\n")
        a.git(c / "memory/private", "commit", "-q", "-am", "précision")
        maj_memoire(c)
        return etage_git(a, c)

    @defaut("fuite-terme", "terme de la liste privée écrit dans un fichier public", "git", "prive.fuites")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "docs/calc.md", "Le module servira au projet Mistral.\n")
        return etage_git(a, c)

    @defaut("fuite-variante", "terme privé écrit sous une variante (collé, souligné)", "agent", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        return etage_outil(a, c, "Write", {"file_path": str(c / "docs/notes.md"), "content": "Le client mistral_api.\n"})

    @defaut("fuite-nom-de-fichier", "terme privé dans le nom d'un fichier public", "git", "prive.fuites")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "docs/plan-mistral.md", "Un plan.\n")
        return etage_git(a, c)

    @defaut("fuite-archive", "document archivé en public qui cite un terme privé", "git", "prive.fuites")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "memory/archives/cadrage.md", "Le projet Mistral.\n")
        return etage_git(a, c)

    @defaut("fuite-branche", "terme privé dans le nom d'une branche créée", "agent", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        return etage_outil(a, c, "Bash", {"command": "git switch -c essai-mistral"})

    @defaut("fuite-corps-par-fichier", "corps de pull request passé par un fichier hors du dépôt", "agent", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        corps = a.dossier / f"corps-{c.name}.md"
        corps.write_text("Avance sur Mistral.\n")
        return etage_outil(a, c, "Bash", {"command": f"gh pr create --title Essai --body-file {corps}"})

    @defaut("fuite-fichier-du-dossier-courant", "message de commit passé par un fichier relatif au dossier courant "
            "de l'agent, qui cite un terme privé", "agent", "fuite")
    def _(a, c):
        # B-0205 : le hook lisait le fichier de la racine, qui ne cite rien.
        c = a.clone_prive("compagnon")
        ajouter(c, "docs/message.txt", "Avance sur Mistral.\n")
        ajouter(c, "message.txt", "Avance.\n")
        return etage_outil(a, c, "Bash", {"command": "git commit -F message.txt"}, cwd=c / "docs")

    @defaut("prive-dans-un-bloc-de-code", "identifiant privé dans un bloc de code d'un fichier public", "ci",
            "memoire.prive")
    def _(a, c):
        ajouter(c, "docs/calc.md", "\n```\nvoir " + "P" + "F-0001\n```\n")
        return etage_ci(a, c)

    @defaut("prive-efface", "fait privé effacé de la mémoire privée", "ci", "memoire.ajout-seul")
    def _(a, c):
        c = a.clone_prive("compagnon")
        p = c / "memory/private/canonical.md"
        p.write_text(p.read_text().split("\n## ")[0] + "\n")
        a.git(c / "memory/private", "commit", "-q", "-am", "effacement")
        sha = a.git(c / "memory/private", "rev-parse", "HEAD").strip()
        (c / ".socle/private.lock").write_text(f'commit = "{sha}"\n')
        maj_memoire(c)
        return etage_ci(a, c)

    @defaut("termes-en-clair", "liste des termes privés commitée en clair", "git", "prive.chiffre")
    def _(a, c):
        c = a.clone_prive("chiffre")
        (c / ".gitattributes").write_text("memory/private/canonical.md filter=essai\n")
        (c / "memory/private/terms.txt").write_text("# socle: termes privés\nMistral\n")
        return etage_git(a, c)

    @defaut("terme-a-l-aveugle", "terme ajouté sans accès à la mémoire privée", "agent", "écriture à l'aveugle")
    def _(a, c):
        c = a.clone_prive("chiffre", cle=False)
        r = a.socle(c, "private", "term", "Zephyr")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("entree-privee-a-l-aveugle", "entrée privée écrite sans accès à la mémoire privée", "agent",
            "écriture à l'aveugle")
    def _(a, c):
        c = a.clone_prive("chiffre", cle=False)
        r = a.socle(c, "new", "fact", "Un fait")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("fuite-message", "identifiant privé dans un message de commit", "git", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        maj_memoire(c, "Travail du tour.")
        a.git(c, "add", "-A")
        r = a.run(c, "git", "commit", "-q", "-m", "Avancer vers " + "P" + "F-0001")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("fuite-ecriture-agent", "l'agent écrit un terme privé dans un fichier public", "agent", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        return etage_outil(a, c, "Write", {"file_path": str(c / "docs/notes.md"), "content": "Projet Mistral.\n"})

    @defaut("fuite-pull-request", "description de pull request qui cite un identifiant privé", "agent", "fuite")
    def _(a, c):
        c = a.clone_prive("compagnon")
        return etage_outil(a, c, "mcp__github__create_pull_request",
                           {"title": "Essai", "body": "Voir " + "P" + "F-0001 pour le contexte."})

    @defaut("terme-retire", "terme retiré de la liste privée sans validation humaine", "git", "prive.termes")
    def _(a, c):
        c = a.clone_prive("compagnon")
        (c / "memory/private/terms.txt").write_text("# socle: termes privés\n")
        a.git(c / "memory/private", "commit", "-q", "-am", "retrait")
        a.socle(c, "private", "lock")
        maj_memoire(c, "Liste privée raccourcie.")
        return etage_git(a, c)

    @defaut("clos-sans-ref-en-anglais", "besoin « done » sans référence, écrit en anglais", "git", "memoire.backlog")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> status : done")
        maj_memoire(c)
        return etage_git(a, c)

    @defaut("bascule-sans-copie", "entrée publique « basculée » sans copie privée qui la reprenne", "git",
            "memoire.ajout-seul")
    def _(a, c):
        c = a.clone_prive("compagnon")
        from socle import memory as memoire

        e = memoire.Memoire.charger(c).entree("B-0001")
        backlog = c / e.fichier
        backlog.write_text(backlog.read_text().replace(e.texte, f"{'#' * e.niveau} B-0001 — Entrée basculée dans "
                                                       "la mémoire privée\n\n> basculée : 2026-10-11\n", 1))
        maj_memoire(c, "Sujet rendu privé.")
        return etage_git(a, c)

    @defaut("publication-sans-relecture", "push vers le dépôt public sans relecture humaine", "agent", "relecture")
    def _(a, c):
        c = a.clone_prive("compagnon")
        return etage_outil(a, c, "Bash", {"command": "git push origin travail"})

    @defaut("prive-en-clair", "fichier privé commité en clair, sans filtre de chiffrement", "git", "prive.chiffre")
    def _(a, c):
        c = a.clone_prive("chiffre", cle=False)
        ajouter(c, "memory/private/journal/2026-10.md", "<!-- socle: couche=journal zone=privee -->\n# Journal privé\n")
        return etage_git(a, c)

    @defaut("backlog-clos-sans-ref", "entrée de backlog close sans référence", "git", "memoire.backlog")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : fait")
        return etage_git(a, c)

    @defaut("clos-ref-en-prose", "tâche faite dont la `ref` n'est que de la prose, ni une référence ni « ce "
            "commit »", "git", "memoire.backlog")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : le prochain commit"))
        return etage_git(a, c)

    @defaut("clos-parmi-les-ouverts", "besoin clos, avec sa référence, laissé parmi les ouverts", "git",
            "memoire.backlog")
    def _(a, c):
        _clore(c, "B-0001")
        return etage_git(a, c)

    @defaut("sujet-qui-s-attend", "besoin qui s'attend lui-même (`après`)", "git", "memoire.ordre")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · après : B-0001")
        return etage_git(a, c)

    @defaut("fait-avant-ce-qu-il-attend", "jalon fait alors que le besoin qu'il attend est ouvert", "git",
            "memoire.ordre")
    def _(a, c):
        ajouter_sujet(c, "\n## JA-0001 — Livrer la multiplication\n\n"
                         f"> statut : fait · origine : {a.journal} · ref : fichier:calc.py · "
                         f"après : B-0001 · lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")
        return etage_git(a, c)

    @defaut("besoin-sans-place", "besoin nouveau qu'aucun jalon ouvert n'attend, sans raison de réserve, quand un "
            "jalon est ouvert (ADR-0118)", "git", "memoire.reserve")
    def _(a, c):
        _jalon_en_base(a, c)
        ajouter_sujet(c, "\n## B-0002 — Ajouter une fonction quadruple\n\n"
                         f"> statut : ouvert · origine : {a.journal} · lu : backlog@{empreinte(a, c, 'backlog')}\n\n"
                         f"Pour l'essai.\n{SATISFAIT_ESSAI}")
        return etage_git(a, c)

    @defaut("jalon-clos-sur-reserve-non-triee", "jalon clos alors qu'un besoin de la réserve n'a pas sa raison "
            "(ADR-0118)", "git", "memoire.reserve")
    def _(a, c):
        _jalon_en_base(a, c, None)
        _clore_le_jalon(c)
        return etage_git(a, c)

    @defaut("cas-change", "cas existant d'un fichier de cas changé sans validation humaine", "git", "tests.attendus")
    def _(a, c):
        remplacer(c, "docs/double.cas.json", '"attendu": 6', '"attendu": 7')
        return etage_git(a, c)

    @defaut("priorite-inconnue", "besoin d'une priorité ni haute ni basse", "git", "memoire.ordre")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · priorité : urgente")
        return etage_git(a, c)

    @defaut("fait-avant-sa-demande", "besoin fait alors que la demande qu'il attend est sans réponse", "git",
            "memoire.ordre")
    def _(a, c):
        ajouter(c, "memory/requests/D-0001-refactor.md", demande_bonne(a, c))
        ajouter_sujet(c, "\n## B-0002 — Livrer la multiplication\n\n"
                         f"> statut : fait · origine : {a.journal} · ref : fichier:calc.py · après : D-0001 · "
                         f"lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")
        return etage_git(a, c)

    @defaut("fait-avec-critere-ouvert", "tâche faite avec un critère de « Fait quand » non coché", "git",
            "memoire.backlog")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : fichier:calc.py",
                                     criteres="- [x] le test passe\n- [ ] le guide le dit"))
        return etage_git(a, c)

    @defaut("besoin-fait-case-vide", "besoin fait, sa tâche faite, avec un critère de « Satisfait quand » non "
            "coché", "git", "memoire.backlog")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : fichier:calc.py"))
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : fait · ref : fichier:calc.py")
        ajouter(c, _sujet(c, "B-0001"), "\n## Satisfait quand\n\n- [x] triple existe\n- [ ] le guide le dit\n")
        return etage_git(a, c)

    # La structure du backlog (ADR-0083) : un refus, un défaut.

    @defaut("forme-ecrite", "entrée ouverte du backlog qui écrit encore `forme`", "git", "memoire.formes")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · forme : lot")
        return etage_git(a, c)

    @defaut("besoin-hors-d-une-tache", "besoin qui écrit `besoin`, le champ d'une tâche", "git", "memoire.formes")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · besoin : B-0001")
        return etage_git(a, c)

    @defaut("priorite-d-un-lot", "lot qui écrit une priorité, lui qui n'est jamais prêt", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001", " · priorité : haute"))
        return etage_git(a, c)

    @defaut("tache-sans-besoin", "tâche qui ne nomme pas son besoin", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c).replace(" · besoin : B-0001", ""))
        return etage_git(a, c)

    @defaut("besoin-qui-n-est-pas-un-besoin", "tâche dont le champ `besoin` nomme un lot, et non un besoin", "git",
            "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c).replace(" · besoin : B-0001", " · besoin : L-0001"))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001"))
        return etage_git(a, c)

    @defaut("tache-nouvelle-sans-section", "tâche nouvelle sans sa section « Fait quand »", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c).split("\n## Fait quand")[0] + "\n")
        return etage_git(a, c)

    @defaut("tache-dans-deux-lots", "tâche que deux lots attendent", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001"))
        ajouter_sujet(c, lot_essai(a, c, "L-0002", "T-0001"))
        return etage_git(a, c)

    @defaut("lot-qui-attend-un-besoin", "lot qui attend un besoin, et non sa tâche", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "B-0001"))
        return etage_git(a, c)

    @defaut("apres-par-un-ancien-numero", "`après` qui nomme l'ancien numéro d'une entrée renumérotée", "git",
            "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001", " · ancien : B-0002"))
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · après : B-0002")
        return etage_git(a, c)

    @defaut("ancien-numero-reattribue", "entrée nouvelle sous l'ancien numéro d'une entrée renumérotée", "git",
            "memoire.format")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001", " · ancien : B-0001"))
        return etage_git(a, c)

    @defaut("besoin-clos-tache-ouverte", "besoin abandonné avec sa tâche encore ouverte", "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : abandonné · ref : fichier:calc.py")
        return etage_git(a, c)

    @defaut("besoin-fait-sans-tache-faite", "besoin fait sans aucune tâche faite", "git", "memoire.formes")
    def _(a, c):
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : fait · ref : fichier:calc.py")
        return etage_git(a, c)

    @defaut("fait-quand-d-un-besoin", "besoin ouvert dont la section est « Fait quand », celle d'une tâche", "git",
            "memoire.formes")
    def _(a, c):
        ajouter(c, _sujet(c, "B-0001"), "\n## Fait quand\n\n- [ ] triple existe\n")
        return etage_git(a, c)

    @defaut("satisfait-quand-d-une-tache", "tâche ouverte qui porte « Satisfait quand », la section d'un besoin",
            "git", "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c) + SATISFAIT_ESSAI)
        return etage_git(a, c)

    @defaut("besoin-nouveau-sans-section", "besoin nouveau sans sa section « Satisfait quand »", "git",
            "memoire.formes")
    def _(a, c):
        ajouter_sujet(c, "\n## B-0002 — Ajouter une fonction quadruple\n\n"
                         f"> statut : ouvert · origine : {a.journal} · lu : backlog@{empreinte(a, c, 'backlog')}"
                         "\n\nPour l'essai.\n")
        return etage_git(a, c)

    # Le dossier court d'un petit lot (B-0288) : refusé pour un lot qui touche
    # un garde-fou, que son relecteur doit pouvoir lire au-delà du diff.
    @defaut("revue-courte-sur-un-garde-fou", "dossier court de revue pour un lot qui touche un garde-fou", "revue",
            "revue courte refusée")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        ajouter(c, ".socle/guardrails.toml", "\n# Un garde-fou que le lot touche.\n")
        a.commit(c, "un lot qui touche un garde-fou")
        r = a.socle(c, "review", "--short")
        return r.stdout + r.stderr

    # La garde de la passation (`socle handoff check`, sans argument) : la
    # session neuve, sur une demande de reprendre, ne travaille pas
    # par-dessus une autre.
    @defaut("passation-poussee-depuis", "session neuve d'une passation alors que la session qui part a poussé après "
            "elle", "passation", "passation poussée depuis")
    def _(a, c):
        neuve, _ = _passation(a, c)
        remplacer(c, "memory/active.md", "La passation de l'essai.", "Un commit poussé après la passation.")
        a.commit(c, "après la passation")
        a.git(c, "push", "-q", "--no-verify", "origin", "travail")
        r = _session_neuve(a, neuve)
        return r.stdout + r.stderr

    @defaut("passation-autre-session", "session neuve d'une passation alors qu'une autre session a écrit la mémoire "
            "sur une autre branche depuis", "passation", "passation d'une autre session")
    def _(a, c):
        neuve, ecrite = _passation(a, c)
        autre = c.parent / f"{c.name}-autre"
        a.git(a.dossier, "clone", "-q", "--no-local", str(c.parent / f"{c.name}-nu"), str(autre))
        a.git(autre, "checkout", "-q", "-b", "autre", "origin/main")
        maj_memoire(autre, "Le travail d'une autre session.")
        r = a.commit(autre, "une autre session", env=_apres_la_passation(ecrite))
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        a.git(autre, "push", "-q", "--no-verify", "origin", "autre")
        r = _session_neuve(a, neuve)
        return r.stdout + r.stderr

    # Reprise par une session dont le retrait n'est pas encore dans la
    # branche par défaut : une seconde demande de reprendre est refusée.
    @defaut("passation-deja-reprise", "session neuve d'une passation qu'une autre session a déjà reprise, son retrait "
            "poussé sur la branche de la passation", "passation", "passation déjà reprise")
    def _(a, c):
        neuve, ecrite = _passation(a, c)
        reprise = c.parent / f"{c.name}-reprise"
        a.git(a.dossier, "clone", "-q", "--no-local", str(c.parent / f"{c.name}-nu"), str(reprise))
        a.git(reprise, "checkout", "-q", "-B", "travail", "origin/travail")
        a.git(reprise, "rm", "-q", "memory/handoff.md")
        r = a.commit(reprise, "la passation reprise et retirée", env=_apres_la_passation(ecrite))
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        a.git(reprise, "push", "-q", "--no-verify", "origin", "travail")
        r = _session_neuve(a, neuve)
        return r.stdout + r.stderr

    # Fusionnée par squash, sa branche supprimée, la pull request du lot
    # porte la passation dans la branche par défaut, d'où la session repart ;
    # la mémoire d'une autre session, fusionnée avant le squash, ancêtre de la
    # tête, fait toujours refuser.
    @defaut("passation-squash-autre-session", "session neuve d'une passation dont la pull request a été fusionnée par "
            "squash, sa branche supprimée, après la mémoire d'une autre session écrite depuis l'heure de la passation",
            "passation", "passation squash d'une autre session")
    def _(a, c):
        neuve, ecrite = _passation(a, c)
        nu = c.parent / f"{c.name}-nu"
        autre = c.parent / f"{c.name}-autre"
        a.git(a.dossier, "clone", "-q", "--no-local", str(nu), str(autre))
        a.git(autre, "checkout", "-q", "-b", "autre", "origin/main")
        ajouter(autre, "memory/canonical.md", "<!-- le travail d'une autre session -->\n")
        r = a.commit(autre, "une autre session", env=_apres_la_passation(ecrite))
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        a.git(autre, "push", "-q", "--no-verify", "origin", "autre")
        github = c.parent / f"{c.name}-github"
        a.git(a.dossier, "clone", "-q", "--no-local", str(nu), str(github))
        a.git(github, "merge", "-q", "--no-ff", "-m", "Fusion de la pull request d'une autre session", "origin/autre")
        a.git(github, "merge", "-q", "--squash", "origin/travail")
        a.commit(github, "Le lot (#1)")
        a.git(github, "push", "-q", "--no-verify", "origin", "main", ":travail", ":autre")
        a.git(neuve, "config", "fetch.prune", "true")
        r = _session_neuve(a, neuve)
        return r.stdout + r.stderr

    # La passation (`socle handoff write`) : programmée, aux bornes d'une
    # chaîne sans l'humain (D-0174) ; puis la vérification de la session qui
    # part, après son push, qui doit la retrouver en attente.
    @defaut("passation-non-poussee", "passation commitée mais pas poussée, que la session qui part vérifie",
            "passation", "passation non poussée")
    def _(a, c):
        _ecrire_la_passation(a, c, pousser=False)
        r = a.socle(c, "handoff", "check")
        return r.stdout + r.stderr

    @defaut("passation-non-commitee", "passation écrite mais pas commitée, que la session qui part vérifie",
            "passation", "passation non commitée")
    def _(a, c):
        _ecrire_la_passation(a, c, commiter=False)
        r = a.socle(c, "handoff", "check")
        return r.stdout + r.stderr

    @defaut("passation-borne-de-la-chaine", "session programmée après deux lots menés sans message de l'humain",
            "passation", "borne de la chaîne")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        _ranger(a, c)
        r = a.socle(c, "handoff", "write", "--scheduled", "--chain", "2")
        return r.stdout + r.stderr

    @defaut("passation-sans-tache-prete", "session programmée alors qu'aucune tâche n'est prête", "passation",
            "passation sans tâche prête")
    def _(a, c):
        _ranger(a, c)
        r = a.socle(c, "handoff", "write", "--scheduled")
        return r.stdout + r.stderr

    # La suppression des branches de l'agent (`socle prune-branches`,
    # ADR-0114) : une branche de l'humain, une branche qui n'est contenue
    # nulle part, ou la suppression que la politique coupe, restent ; la
    # commande le dit.
    @defaut("elagage-branche-de-l-humain", "branche de l'humain contenue dans la branche par défaut, que la commande "
            "de l'agent supprimerait", "elagage", "branche de l'humain")
    def _(a, c):
        clone = _branche_a_elaguer(a, c, agent=False)
        r = a.socle(clone, "prune-branches")
        return _elagage_vu(a, clone, r)

    @defaut("elagage-branche-non-contenue", "branche de l'agent qu'aucune branche poussée ne contient, que la "
            "commande supprimerait", "elagage", "branche non contenue")
    def _(a, c):
        clone = _branche_a_elaguer(a, c, agent=True, fusionner=False)
        r = a.socle(clone, "prune-branches")
        return _elagage_vu(a, clone, r)

    @defaut("elagage-coupe", "branche de l'agent supprimée alors que la politique coupe la suppression", "elagage",
            "suppression coupée")
    def _(a, c):
        clone = _branche_a_elaguer(a, c, agent=True)
        pol = clone / ".socle/policy.toml"
        pol.write_text(pol.read_text().replace("[irreversible]\n", "[irreversible]\nprune_branches = false\n", 1))
        r = a.socle(clone, "prune-branches")
        return _elagage_vu(a, clone, r)

    # La couche `passation` du format : son estampille, et aucun
    # identifiant.
    @defaut("passation-sans-estampille", "passation sans son estampille : ni heure `écrite`, ni branche, ni chaîne",
            "git", "memoire.format")
    def _(a, c):
        (c / "memory/handoff.md").write_text("<!-- socle: couche=passation zone=publique -->\n# Passation\n\n"
                                             "Ce qui attend : rien.\n")
        return etage_git(a, c)

    @defaut("passation-avec-une-entree", "identifiant défini dans la passation, que la session neuve retire", "git",
            "memoire.format")
    def _(a, c):
        r = a.socle(c, "handoff", "write")
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)
        ajouter(c, "memory/handoff.md", "\n## F-0099 — Un fait dans la passation\n\n> statut : supposé · source : "
                                        "l'essai\n")
        return etage_git(a, c)

    # L'historique des revues d'un lot (ADR-0084, ADR-0100) : une ligne de
    # bloquant qu'il ne lit pas.

    @defaut("bloquant-mal-ecrit", "ligne de bloquant d'une passe de revue écrite autrement que « - Bloquant : … », "
            "que rien ne lit", "git", "memoire.backlog")
    def _(a, c):
        _lot_en_cours_relu(a, c, "- **Bloquant** : la correction change la lecture du facteur")
        return etage_git(a, c)

    @defaut("bloquant-sans-puce", "ligne de bloquant d'une passe de revue écrite sans puce, que rien ne lit",
            "git", "memoire.backlog")
    def _(a, c):
        _lot_en_cours_relu(a, c, "Bloquant 2 — la correction change la lecture du facteur")
        return etage_git(a, c)

    # Au-delà du tableau du cadrage.

    @defaut("titre-d-entree-illisible", "entrée de journal au titre mal formé, que rien ne lit", "git", "memoire.format")
    def _(a, c):
        ajouter(c, f"memory/journal/{a.journal[2:9]}.md", f"\n## {a.journal[:12]} Sans sa lettre ni son tiret\n\nTexte.\n")
        return etage_git(a, c)

    @defaut("journal-reecrit", "entrée de journal réécrite", "git", "memoire.ajout-seul")
    def _(a, c):
        remplacer(c, f"memory/journal/{a.journal[2:9]}.md", "Le rapport d'installation", "Le compte rendu d'installation")
        return etage_git(a, c)

    @defaut("fait-efface", "fait canonique effacé", "git", "memoire.ajout-seul")
    def _(a, c):
        remplacer(c, "memory/canonical.md", CANONIQUE_ESSAI.strip(), "")
        return etage_git(a, c)

    @defaut("valeur-attendue", "valeur attendue changée sans spécification", "git", "tests.attendus")
    def _(a, c):
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        return etage_git(a, c)

    @defaut("valeur-attendue-adr-agent", "valeur attendue changée sous une ADR que l'agent écrit lui-même", "ci",
            "tests.attendus")
    def _(a, c):
        ajouter(c, "memory/decisions/ADR-0001-test-double.md", _adr_test_double(a, c))
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        return etage_ci(a, c, MESSAGE_AGENT)

    @defaut("valeur-attendue-demande-non-poussee", "valeur attendue changée sous une demande que l'humain n'a pas "
            "pu lire, faute d'être poussée", "agent", "tests.attendus")
    def _(a, c):
        ajouter(c, "memory/requests/D-0001-refactor.md", _demande_nommant_le_test(a, c))
        a.commit(c, "La demande, commitée mais pas poussée")
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        return etage_stop(a, c, "J'ai changé le test en attendant la réponse." + RECAP)

    # D-0189, piste B : une validation d'avant la plage ne couvre que tant
    # qu'une tâche ouverte la cite et que ce qu'elle nomme n'a pas bougé.
    @defaut("validation-epuisee", "valeur attendue changée une seconde fois sous une validation fusionnée avec "
            "son test, sa tâche close", "ci", "tests.attendus")
    def _(a, c):
        return _changer_sous_une_validation_fusionnee(a, c, tache="fait", avec_le_test=True)

    @defaut("validation-sans-tache", "valeur attendue changée sous une validation fusionnée qu'aucune tâche "
            "ouverte ne cite", "ci", "tests.attendus")
    def _(a, c):
        return _changer_sous_une_validation_fusionnee(a, c, tache=None)

    @defaut("validation-test-bouge", "valeur attendue changée sous une validation fusionnée dont le test a bougé "
            "depuis dans la branche par défaut", "ci", "tests.attendus")
    def _(a, c):
        return _changer_sous_une_validation_fusionnee(a, c, tache="ouvert", bouge=True)

    @defaut("valeur-attendue-decision-donnee-sans-le-test", "valeur attendue changée sous une décision que "
            "l'humain a donnée de lui-même sans nommer le test", "ci", "tests.attendus")
    def _(a, c):
        return _test_change_sous_une_decision_donnee(a, c, "Compare le test du module à un flottant.")

    @defaut("test-supprime", "test supprimé sans validation", "ci", "tests.attendus")
    def _(a, c):
        remplacer(c, "tests/test_calc.py", "    def test_double(self):\n        self.assertEqual(double(2), 4)\n",
                  "    def test_placeholder(self):\n        self.assertTrue(callable(double))\n")
        return etage_ci(a, c)

    @defaut("valide-sans-demande", "fait passé à « validé » par l'agent", "agent", "memoire.preuves")
    def _(a, c):
        p = c / "memory/canonical.md"
        nouveau = p.read_text().replace("> statut : mesuré · preuve : fichier:tests/test_calc.py", "> statut : validé")
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": nouveau})

    @defaut("sha-fabrique", "SHA complété de tête", "agent", "anti-fabrication")
    def _(a, c):
        vrai = a.git(c, "rev-parse", "HEAD").strip()
        faux = vrai[:7] + "0" * 33
        return etage_outil(a, c, "Bash", {"command": f"git show {faux}"})

    @defaut("action-irreversible", "force-push sans validation humaine", "agent", "politique point 4")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "git push --force origin travail"})

    @defaut("push-force-groupe", "push forcé caché dans des drapeaux groupés", "agent", "politique point 4")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "git -C . push -fu origin travail"})

    @defaut("push-par-une-variable", "push forcé ou vers la branche par défaut dont l'option ou la branche vient "
            "d'une variable, des arguments d'une fonction ou d'une substitution", "agent", "politique point 4")
    def _(a, c):
        # B-0254 : `irreversible` lisait l'argv d'un push tel qu'écrit. Il se
        # développe ; un argument qui ne se développe pas est refusé.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "F=--force; git push $F origin travail", "B=main; git push origin \"$B\"",
            "f() { git push \"$@\"; }; f --force origin travail", "git push \"$SOCLE_ESSAI_CIBLE\" origin travail",
            "git push origin \"$(echo main)\"")])

    @defaut("push-de-la-branche-substituee", "push vers la branche par défaut par une substitution qui rend la "
            "branche courante, lancé depuis elle, ou après un changement de branche ou de dossier dans la même "
            "commande", "agent", "politique point 4")
    def _(a, c):
        # B-0254, T-0106 : `$(git branch --show-current)` se développe en la
        # branche courante, que le push vise alors ; elle ne se lit plus quand
        # la commande change de branche ou de dossier avant lui.
        refus = tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git checkout main && git push origin \"$(git branch --show-current)\"",
            "cd .. && git push -u origin `git rev-parse --abbrev-ref HEAD`",
            "B=$(git symbolic-ref --short HEAD); git switch -q main; git push origin \"$B\"")])
        if refus.startswith("passé sans refus"):
            return refus
        a.git(c, "switch", "-q", "main")
        depuis_main = tous_refuses(a, c, [("Bash", {"command": "git push -u origin \"$(git branch --show-current)\""})])
        return depuis_main if depuis_main.startswith("passé sans refus") else refus + "\n" + depuis_main

    @defaut("push-refspec-defaut", "push vers la branche par défaut par une référence complète", "agent",
            "politique point 4")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "git push origin HEAD:refs/heads/main"})

    @defaut("suppression-distante-api", "branche distante supprimée par l'API de GitHub", "agent", "politique point 4")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "gh api -X DELETE repos/o/r/git/refs/heads/travail"})

    @defaut("protege-par-le-shell", "fichier protégé écrit par une redirection du shell", "agent", "écriture protégée")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "cd .socle && echo 'max_attempts = 99' 1>> policy.toml"})

    @defaut("protege-dossier-shell", "dossier qui contient des fichiers protégés déplacé par le shell", "agent",
            "écriture protégée")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "mv .github /tmp/github-de-cote"})

    @defaut("protege-developpe", "fichier protégé écrit par le shell à travers une variable affectée, un motif, une "
            "accolade ou un `pushd`", "agent", "écriture protégée")
    def _(a, c):
        # B-0171 : le hook jugeait les chemins tels qu'ils sont tapés.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "F=.socle/policy.toml; echo 'max_attempts = 99' >> \"$F\"", "rm .socle/pol*",
            "echo 'max_attempts = 99' >> .socle/{policy,adapter}.toml",
            "pushd .socle && echo 'max_attempts = 99' >> policy.toml")])

    @defaut("ecriture-illisible", "chemin écrit par le shell à travers une variable ou une substitution que le hook "
            "ne sait pas développer, dans le projet", "agent", "écriture illisible")
    def _(a, c):
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "echo 'max_attempts = 99' >> $SOCLE_ESSAI_CIBLE", "echo x > .socle/$(ls .socle | head -1)",
            "cd $SOCLE_ESSAI_DOSSIER && echo 'max_attempts = 99' >> policy.toml")])

    @defaut("protege-etat-du-shell", "fichier protégé écrit par le shell après un sous-shell, une substitution, un "
            "pipeline ou une commande en arrière-plan, dont le dossier et les variables ne passent pas à la suite", "agent",
            "écriture protégée")
    def _(a, c):
        # La revue de B-0171, constat 1 : leur état passait à la suite.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "(cd /tmp && ls) && echo 'max_attempts = 99' >> .socle/policy.toml",
            "X=$(pushd /tmp); echo 'max_attempts = 99' >> .socle/policy.toml",
            "cd /tmp | true; echo 'max_attempts = 99' >> .socle/policy.toml",
            "F=.socle/policy.toml; (F=/tmp/x); echo 'max_attempts = 99' >> $F",
            "cd /tmp && ls & echo 'max_attempts = 99' >> .socle/policy.toml")])

    @defaut("protege-forme-du-shell", "fichier protégé écrit par le shell à travers `cd \"$OLDPWD\"`, une option de "
            "`cd`, les mots d'une variable, `$'…'`, `+=`, `shopt`, une classe POSIX ou un script collé à `sed -e`",
            "agent", "écriture protégée")
    def _(a, c):
        # La revue de B-0171, constats 2, 3, 6, 7, 8, 10 et 11.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "cd /tmp && cd \"$OLDPWD\" && echo 'max_attempts = 99' >> .socle/policy.toml",
            "cd -P .socle && echo 'max_attempts = 99' >> policy.toml",
            "F=\"calc.py .socle/policy.toml\"; sed -i s/3/9/ $F",
            "echo 'max_attempts = 99' >> $'.socle/policy.toml'",
            "F=.socle/pol; F+=icy.toml; echo 'max_attempts = 99' >> $F",
            "shopt -s dotglob; rm -f */policy.toml",
            "echo 'max_attempts = 99' >> .socle/[[:alpha:]]olicy.toml",
            "sed -i -e\"s/3/9/\" .socle/policy.toml")])

    @defaut("ecriture-illisible-remontee", "chemin écrit par le shell que le hook ne sait pas développer : un `..` "
            "après une part inconnue, un `cd` vers une cible inconnue, `$_`, une référence (`declare -n`), des "
            "accolades au-delà du plafond", "agent", "écriture illisible")
    def _(a, c):
        # La revue de B-0171, constats 2, 4, 5, 7 et 9 : chacun passait.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            f"echo 'max_attempts = 99' >> {ailleurs}/$SOCLE_ESSAI_CIBLE/../..{c}/.socle/policy.toml",
            "cd /tmp && cd \"$(git rev-parse --show-toplevel)\" && echo 'max_attempts = 99' >> .socle/policy.toml",
            "ls .socle/policy.toml && echo 'max_attempts = 99' >> \"$_\"",
            "declare -n R=F; F=.socle/policy.toml; echo 'max_attempts = 99' >> $R",
            "rm -f .socle/{,a}{,b}{,c}{,d}{,e}{,f}{,g}{,h}{,i}policy.toml")])

    @defaut("commande-injugeable", "fichier protégé écrit par le shell dans une commande trop imbriquée ou trop "
            "longue pour être jugée, ou dont le découpage plante", "agent", "commande injugeable")
    def _(a, c):
        # La seconde revue de B-0171, constat 4 : le hook plantait, ou
        # dépassait son délai, et laissait passer.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "X=" + "$(" * 500 + "echo" + ")" * 500 + "; echo 'max_attempts = 99' >> .socle/policy.toml",
            "eval " * 500 + "echo 'max_attempts = 99' >> .socle/policy.toml",
            "cd /tmp; " * 1500 + f"cd {c}; echo 'max_attempts = 99' >> .socle/policy.toml")])

    @defaut("protege-dossier-courant", "fichier protégé écrit par le shell par un chemin relatif au dossier courant "
            "de l'agent, un motif ou `$PWD`", "agent", "écriture protégée")
    def _(a, c):
        # B-0205, et la revue de B-0171, constat 12 : le hook jugeait un
        # chemin relatif depuis la racine.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "echo 'max_attempts = 99' >> policy.toml", "echo 'max_attempts = 99' >> $PWD/policy.toml",
            "rm pol*")], c / ".socle")

    @defaut("suppression-du-projet", "dossier qui contient le projet supprimé par le shell : `rm -rf ..`, un "
            "`cd` puis `../..`, les sources d'un `mv`, `git clean` sous `-C ..`, un `find` qui supprime depuis un "
            "dossier qui le contient, ou depuis la racine sans filtre de nom ou de chemin qui garde sa suppression",
            "agent", "suppression du projet")
    def _(a, c):
        # B-0208 : rien ne rattrape ensuite la suppression du projet.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "rm -rf ..", "cd .socle && rm -rf ../..", "mv .. /tmp/ailleurs", "git -C .. clean -ffdx",
            "find .. -name '*.pyc' -delete", "find . -delete", "find . -delete -name '*.pyc'",
            "find . \\( -type f \\) -delete")])

    @defaut("suppression-par-un-autre-programme", "dossier qui contient le projet, ou le projet lui-même, supprimé par "
            "un autre programme que `rm`, `mv`, `git clean` ou `find` : la destination d'un `rsync --delete`, les "
            "sources d'un `rsync --remove-source-files`, le worktree de l'agent retiré par `git worktree remove`, un "
            "`python3 -c` qui passe son chemin en toutes lettres à `shutil.rmtree`, un `find -exec` de l'un d'eux",
            "agent", "suppression du projet")
    def _(a, c):
        # B-0228 : la lecture de ces programmes se prouve à part de celle de
        # `rm` et des siens (`suppression-du-projet`) ; leur refus est le même.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "rsync -a --delete vide/ ..", "rsync -a vide/ .. --delete-after --exclude .git",
            "rsync -a --remove-source-files . /tmp/sauve", "git worktree remove --force .",
            f"git worktree remove -f -f {c}", f"cd .. && git worktree remove {c.name}",
            "python3 -c \"import shutil; shutil.rmtree('..')\"",
            f"python3 -I -c \"import shutil; shutil.rmtree('{c}')\"",
            "find .. -maxdepth 0 -exec git worktree remove {} \\;")])

    @defaut("suppression-par-un-lanceur", "dossier qui contient le projet supprimé par une commande que lancent "
            "`uv run` ou `poetry run`, leurs options avant `run` comme après", "agent", "suppression du projet")
    def _(a, c):
        # B-0248 : ni `uv run` ni `poetry run` n'étaient des préfixes ; la
        # commande lancée se lisait comme le programme `uv` ou `poetry`.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "uv run rm -rf ..", "poetry run rm -rf ..", "uv run --with requests -p 3.12 -- rm -rf ..",
            "uv --directory . run --frozen rm -rf ..", "poetry -C . run -n rm -rf ..",
            "uv run python -c \"import shutil; shutil.rmtree('..')\"")])

    @defaut("find-conjonction-protegee", "fichier protégé supprimé par un `find` dont chaque filtre d'une même "
            "conjonction le vise, ou par un `-path` à étoile de tête depuis la racine", "agent", "écriture protégée")
    def _(a, c):
        # B-0231 : la conjonction de ses filtres se juge entière ; ce qu'elle
        # atteint reste refusé.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "find . -name '*.toml' -path './.socle/*' -delete", "find . -path '*.toml' -delete",
            "find .socle -path '*e/policy.toml' -delete")])

    @defaut("suppression-par-xargs","dossier qui contient le projet, ou le projet lui-même, supprimé par `xargs rm` "
            "derrière un `find` qui lui donne sa liste", "agent", "suppression du projet")
    def _(a, c):
        # B-0246 : `xargs rm` ne se jugeait que par les chemins protégés que
        # la commande cite ; derrière un `find`, il se juge comme un `find`
        # qui supprime depuis ses départs.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "find .. -maxdepth 0 | xargs rm -rf", "find . -type f | xargs rm -f",
            "find .. -maxdepth 0 -print0 | xargs -0 -I{} rm -rf {}")])

    @defaut("heredoc-donne-a-python","fichier protégé écrit, ou dossier qui contient le projet supprimé, par le "
            "script qu'un heredoc donne à python (`python3 - <<'EOF'`)", "agent", "écriture protégée")
    def _(a, c):
        # B-0229 : le corps d'un heredoc n'était que du texte pour le
        # découpage ; le script que python lit sur son entrée se juge comme
        # celui d'un `python -c`.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "python3 - <<'EOF'\nopen('.socle/policy.toml', 'a').write('max_attempts = 99')\nEOF",
            "python3 <<EOF\nimport shutil\nshutil.rmtree('..')\nEOF")])

    @defaut("arguments-de-python-c", "fichier protégé passé en argument au script d'un `python -c`, ou d'un script "
            "qu'un heredoc donne à python", "agent", "écriture protégée")
    def _(a, c):
        # B-0230 : seul le script se jugeait ; le chemin que le script lit
        # dans `sys.argv` s'écrivait sans refus.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "python3 -c \"import sys; open(sys.argv[1], 'a').write('max_attempts = 99')\" .socle/policy.toml",
            "F=.socle/policy.toml; python3 -c \"import sys; open(sys.argv[1], 'a')\" \"$F\"",
            "python3 - .socle/policy.toml <<'EOF'\nimport sys\nopen(sys.argv[1], 'a')\nEOF")])

    @defaut("argument-illisible-de-python-c", "argument que le hook ne sait pas développer, passé au script d'un "
            "`python -c` ou d'un heredoc donné à python qui lit ses arguments, dans le projet", "agent",
            "écriture illisible")
    def _(a, c):
        # La revue de L-0019, passe 1 : l'argument inconnu ne se jugeait pas,
        # et le script l'écrivait.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "python3 -c \"import sys; open(sys.argv[1], 'a').write('max_attempts = 99')\" \"$SOCLE_ESSAI_CIBLE\"",
            "cd .socle && python3 -c \"import sys; open(sys.argv[1], 'a')\" \"$(ls | head -1)\"",
            "python3 - \"$SOCLE_ESSAI_CIBLE\" <<'EOF'\nimport sys\nopen(sys.argv[1], 'a')\nEOF")])

    @defaut("substitution-entre-guillemets","dossier qui contient le projet supprimé par la commande que lance une "
            "substitution entre guillemets, `\"$(…)\"` ou des accents graves, après un `cd` ou l'appel d'une fonction "
            "qui change de dossier", "agent", "suppression du projet")
    def _(a, c):
        # B-0260 : ce que lance une substitution entre guillemets ne se
        # jugeait jamais, quand `x="$(…)"` est une forme qu'un agent écrit.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "echo \"$(rm -rf ..)\"", "x=\"`rm -rf ..`\"", "x=\"$(cd memory && rm -rf ../..)\"",
            f"f() {{ cd memory; }}; x=\"$(f; rm -rf ../../{c.name})\"")])

    @defaut("push-par-un-lanceur", "push forcé ou vers la branche par défaut lancé par `uv run` ou `poetry run`",
            "agent", "politique point 4")
    def _(a, c):
        # B-0248 : le push se lisait comme le programme `uv` ou `poetry`.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "poetry run git push --force origin main", "uv run git push --force origin travail",
            "uv run --python=3.12 -- git push origin main")])

    @defaut("worktree-par-son-suffixe", "worktree de l'agent retiré ou déplacé depuis lui par `git worktree remove` "
            "ou `move` qui le nomme par la fin de son chemin (`agent-x`, `.claude/worktrees/agent-x`), que git "
            "cherche parmi ses worktrees avant de le lire comme un chemin relatif", "agent", "suppression du projet")
    def _(a, c):
        # La revue du lot B-0234 (J-2026-11-15-O) : le hook ne lisait le
        # worktree que comme un chemin relatif au dossier de la commande.
        arbre = c / ".claude/worktrees/sous-agent"
        a.git(c, "worktree", "add", "-q", "-b", "sous-agent", str(arbre))
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git worktree remove .claude/worktrees/sous-agent", "git worktree remove -f -f sous-agent",
            "git worktree move sous-agent /tmp/ailleurs")], cwd=arbre)

    @defaut("fonction-sans-parentheses", "dossier qui contient le projet supprimé, ou push forcé, dans le corps d'une "
            "fonction `function nom { …; }` écrite sans parenthèses, son corps sur la même ligne ou la suivante",
            "agent", "suppression du projet")
    def _(a, c):
        # B-0232 : la commande lue avait pour programme `function`, et rien de
        # son corps ne se jugeait. Un défaut à part, et non une forme de plus
        # de `suppression-du-projet` : c'est la lecture de la définition qui
        # se prouve, pour ce que rien ne rattrape, la suppression comme le push.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "function f { rm -rf ..; }; f", "function f\n{\n  rm -rf ..\n}\nf",
            "function f { git push --force origin travail; }; f",
            "function f if git push --force origin travail; then :; fi")])

    @defaut("appel-de-fonction", "suppression du projet depuis le dossier qu'une fonction appelée laisse derrière "
            "elle, son corps `{ … }` ayant changé de dossier ou de variable, ou appelé une fonction définie après "
            "lui, et l'appel derrière `time`, dans un `eval` ou dans une substitution (la seconde revue du lot "
            "B-0234, ses deux passes)", "agent", "écriture illisible")
    def _(a, c):
        # B-0232 : à l'appel d'une fonction dont le corps change le dossier,
        # le hook ne suivait rien, et `../../<racine>`, sans danger depuis la
        # racine, visait le projet depuis le dossier laissé derrière. L'appel
        # rend inconnu ce que le corps change (ADR-0072, point 6). Aussi la
        # forme `f() { … }` (troisième constat), un appel par une fonction qui
        # en appelle une autre, et une redéfinition. La seconde passe de la
        # revue (J-2026-11-16-B) : une fonction appelée définie après celle
        # qui l'appelle, ou dans elle, `time f`, et l'appel dans un `eval` ou
        # une substitution (B-0250).
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            f"function f {{ cd memory; }}; f; rm -rf ../../{c.name}",
            f"f() {{ cd memory; }}; f; rm -rf ../../{c.name}",
            f"f() {{ cd memory; }}; g() {{ f; }}; g; rm -rf ../../{c.name}",
            f"f() {{ ls; }}; f() {{ cd memory; }}; f; rm -rf ../../{c.name}",
            f"g() {{ f; }}; f() {{ cd memory; }}; g; rm -rf ../../{c.name}",
            f"f() {{ g() {{ cd memory; }}; g; }}; f; rm -rf ../../{c.name}",
            f"f() {{ cd memory; }}; time -p f; rm -rf ../../{c.name}",
            f"f() {{ cd memory; }}; eval f; rm -rf ../../{c.name}",
            f"f() {{ cd memory; }}; x=$(f; rm -rf ../../{c.name})")])

    @defaut("mot-reserve-cite", "mot réservé cité ou échappé lu comme réservé : le groupe qui suit `\"function\"` "
            "s'exécute sur place, ou un `}` cité ferme trop tôt le corps d'une fonction, et une suppression du "
            "projet passe (la seconde revue du lot B-0234, bloquant 3)", "agent", "écriture protégée")
    def _(a, c):
        # B-0232 : `"function"`, `\function`, `$'function'` et `'function'` se
        # lisaient comme réservés ; bash les lance comme une commande, puis
        # exécute sur place le groupe qui suit, dont le `cd`. Un `}` cité ne
        # ferme plus trop tôt le corps d'une fonction (quatrième constat).
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            f'"function" f\n{{ cd memory; }}\nrm -rf ../../{c.name}',
            f"\\function f\n{{ cd memory; }}\nrm -rf ../../{c.name}",
            f"$'function' f\n{{ cd memory; }}\nrm -rf ../../{c.name}",
            f'f() {{ cd memory; "}}"; rm -rf ../../{c.name}; }}; f')])

    @defaut("protege-mot-reserve", "fichier protégé écrit par le shell derrière un mot réservé (`then`, `else`, "
            "`do`, `!`, `{`), par la variable d'un `for`, après un groupe dans un pipeline ou après la définition "
            "d'une fonction", "agent", "écriture protégée")
    def _(a, c):
        # B-0204 : `then rm …` se lisait comme le programme `then`.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "if true; then echo 'max_attempts = 99' >> .socle/policy.toml; fi",
            "if false; then :; else sed -i s/3/9/ .socle/policy.toml; fi",
            "! sed -i s/3/9/ .socle/policy.toml",
            "for f in .socle/*.toml; do sed -i s/3/9/ \"$f\"; done",
            "for d in .socle memory; do cd $d; echo 'max_attempts = 99' >> policy.toml; done",
            "for f in a policy.toml; do echo 'max_attempts = 99' >> .socle/$f; done",
            "{ cd /tmp; } | cat; echo 'max_attempts = 99' >> .socle/policy.toml",
            "build() { cd /tmp; }; echo 'max_attempts = 99' >> .socle/policy.toml")])

    @defaut("protege-diese-guillemets", "fichier protégé écrit par le shell après un commentaire en fin de ligne, un "
            "`#` au milieu d'un mot ou une substitution aux guillemets imbriqués", "agent", "écriture protégée")
    def _(a, c):
        # B-0207 : la commande qui suivait se perdait.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "echo ok # une note\necho 'max_attempts = 99' >> .socle/policy.toml",
            "[ $# -eq 0 ]; echo 'max_attempts = 99' >> .socle/policy.toml",
            "X=\"$(echo \"l'apostrophe\")\"; sed -i s/3/9/ .socle/policy.toml",
            "X=\"$(echo \"; cd /tmp; \")\"; echo 'max_attempts = 99' >> .socle/policy.toml")])

    @defaut("protege-ecrivain-par-option", "fichier protégé écrit par `cp -t`, `find -delete`, `xargs`, `bash -ec`, "
            "`sort -o` ou `python -c`", "agent", "écriture protégée")
    def _(a, c):
        # B-0206 : chacune de ces écritures passait le hook.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "cp -t .socle/git-hooks calc.py", "find .socle -name policy.toml -delete",
            "find . -path '*/.socle/*' -delete",
            "echo .socle/policy.toml | xargs sed -i s/3/9/", "bash -ec 'sed -i s/3/9/ .socle/policy.toml'",
            "sort -o .socle/policy.toml calc.py",
            "python3 -c \"open('.socle/policy.toml', 'a').write('max_attempts = 99')\"")])

    @defaut("ecriture-illisible-composee", "chemin écrit par le shell après une condition ou une boucle qui change "
            "le dossier ou une variable, ou dans la branche qui suit", "agent", "écriture illisible")
    def _(a, c):
        # B-0204 : le hook ne sait pas quelle branche le shell prendra.
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "if [ -n \"$SOCLE_ESSAI_CIBLE\" ]; then cd /tmp; fi; echo 'max_attempts = 99' >> .socle/policy.toml",
            "if [ -n \"$SOCLE_ESSAI_CIBLE\" ]; then cd /tmp; else echo 'max_attempts = 99' >> .socle/policy.toml; fi",
            "if [ -n \"$SOCLE_ESSAI_CIBLE\" ]; then F=.socle/policy.toml; else F=/tmp/x; fi; echo x >> \"$F\"",
            "for d in .socle memory; do cd $d; break; cd ..; done; echo 'max_attempts = 99' >> policy.toml")])

    @defaut("protege-depuis-un-worktree", "fichier protégé de la copie principale écrit depuis un worktree du dépôt",
            "agent", "écriture protégée")
    def _(a, c):
        # Revue de B-0164 : le dossier courant ne lève aucun refus de la
        # racine de la session.
        arbre = c / ".claude/worktrees/sous-agent"
        a.git(c, "worktree", "add", "-q", "-b", "sous-agent", str(arbre))
        return etage_outil(a, c, "Bash", {"command": f"echo 'max_attempts = 99' >> {c.resolve()}/.socle/policy.toml"},
                           cwd=arbre)

    @defaut("remise-hors-head", "fichier protégé remis à un autre état que le dernier commit, ou tout un dossier",
            "agent", "remise hors forme")
    def _(a, c):
        ajouter(c, ".socle/policy.toml", "# changé par erreur\n")
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git checkout HEAD~1 -- .socle/policy.toml", "git restore --source=main -- .socle/policy.toml",
            "git restore .socle/policy.toml", "git restore --source=HEAD -- .", "git checkout HEAD -- .socle",
            "git restore --source=HEAD -- '.socle/git-hooks/*'")])

    @defaut("remise-redirigee", "remise admise d'un fichier protégé dont la redirection écrit un autre fichier "
            "protégé", "agent", "écriture protégée")
    def _(a, c):
        ajouter(c, ".socle/policy.toml", "# changé par erreur\n")
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git restore --source=HEAD -- .socle/policy.toml > .github/CODEOWNERS",
            "git checkout HEAD -- .socle/policy.toml > .socle/git-hooks/pre-commit")])

    @defaut("remise-autre-depot", "remise d'un fichier protégé depuis un autre dépôt, une autre révision sans `--`, "
            "ou des chemins lus dans un fichier", "agent", "remise hors forme")
    def _(a, c):
        ajouter(c, ".socle/policy.toml", "# changé par erreur\n")
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "GIT_DIR=/tmp/autre/.git git checkout HEAD -- .socle/policy.toml",
            "env GIT_WORK_TREE=/tmp git restore --source=HEAD -- .socle/policy.toml",
            "git checkout HEAD~1 .socle/policy.toml",
            "git restore --source=HEAD --pathspec-from-file=/tmp/chemins.txt")])

    @defaut("remise-reglages", "réglages de Claude Code remis à l'état du dernier commit par l'agent", "agent",
            "réglage de l'agent")
    def _(a, c):
        ajouter(c, ".claude/settings.json", " ")
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git restore --source=HEAD -- .claude/settings.json", "git checkout HEAD -- .claude/settings.json")])

    @defaut("remise-sous-demande", "fichier protégé remis alors qu'une demande en attente le cite", "agent",
            "remise sous demande")
    def _(a, c):
        protege_en_attente(a, c)
        return etage_outil(a, c, "Bash", {"command": "git restore --source=HEAD --staged --worktree -- "
                                                     ".github/CODEOWNERS"})

    @defaut("reglage-local-agent", "l'agent coupe ses hooks par un réglage local de Claude Code", "agent",
            "réglage de l'agent")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / ".claude/settings.local.json"),
                                           "content": '{"disableAllHooks": true}\n'})

    @defaut("irreversibles-tous", "chaque forme d'action irréversible ou externe", "agent", "politique point 4")
    def _(a, c):
        return tous_refuses(a, c, [("Bash", {"command": x}) for x in (
            "git push --delete origin travail", "git push origin +travail", "git push --mirror origin",
            "git reset --hard HEAD~1", "git filter-branch --tree-filter true HEAD", "npm publish",
            "cargo publish", "twine upload dist/*", "gem push essai.gem", "gh pr merge 1 --squash",
            "gh release create v1", "gh repo delete o/r --yes", "gh secret set JETON", "gh api --method=PUT repos/o/r",
            "rm -rf ~/", "rm -r -f .git")])

    @defaut("outils-externes", "chaque outil externe d'écriture", "agent", "politique point 4")
    def _(a, c):
        return tous_refuses(a, c, [("mcp__github__" + x, {"owner": "o", "repo": "r"}) for x in (
            "merge_pull_request", "delete_file", "create_repository", "fork_repository", "create_release",
            "push_files", "create_or_update_file", "enable_pr_auto_merge")])

    @defaut("reference-inventee", "référence à une entrée qui n'existe pas", "agent", "référence inventée")
    def _(a, c):
        p = c / "docs/calc.md"
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": p.read_text() + "\nVoir F-0099.\n"})

    @defaut("ancien-numero-dans-un-texte-neuf", "entrée renumérotée mentionnée par son ancien numéro dans un texte "
            "neuf", "agent", "ancien numéro")
    def _(a, c):
        _renumeroter_en_lot(c, "B-0001")
        p = c / "docs/calc.md"
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": p.read_text() + "\nVoir B-0001.\n"})

    @defaut("ancien-numero-repris", "entrée renumérotée mentionnée par son ancien numéro dans une ligne neuve d'un "
            "fichier qui le cite déjà", "agent", "ancien numéro")
    def _(a, c):
        # T-0083 : le hook sautait toute mention que le fichier portait déjà ;
        # le journal du mois d'une migration les cite presque tous.
        _renumeroter_en_lot(c, "B-0001")
        p = c / "docs/calc.md"
        p.write_text(p.read_text() + "\nLe lot B-0001 avance.\n")
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": p.read_text() + "\nVoir B-0001.\n"})

    @defaut("echecs-repetes", "contrôles rouges trois tours de suite, sans escalade", "agent", "escalade")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        maj_memoire(c)
        sortie = ""
        for _ in range(3):
            r = a.socle(c, "hook", "stop", entree=json.dumps({"session_id": "autotest", "stop_hook_active": False}))
            sortie = r.stdout
        return sortie

    @defaut("echec-inchange-relance", "relance du hook sur un échec et un arbre inchangés, que l'humain ne voit pas",
            "agent", "échec inchangé")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        maj_memoire(c)
        sortie = ""
        for relance in (False, True):
            sortie = a.socle(c, "hook", "stop", entree=json.dumps({"session_id": "autotest",
                                                                   "stop_hook_active": relance})).stdout
        # Une relance qui bloquerait encore n'attrape rien : elle doit passer
        # la main à l'humain, par le message du hook (B-0143).
        return "" if '"block"' in sortie else sortie

    @defaut("validation-ecrite-en-ci", "fait « validé » commité sans réponse de l'humain", "ci", "memoire.preuves")
    def _(a, c):
        remplacer(c, "memory/canonical.md", "> statut : mesuré · preuve : fichier:tests/test_calc.py", "> statut : validé")
        return etage_ci(a, c)

    @defaut("demande-incomplete-en-ci", "demande hors contrat commitée", "ci", "demandes.contrat")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(DEMANDE_NUE)
        return etage_ci(a, c)

    @defaut("capacite-sans-remplacement", "capacité absente sans son remplacement", "ci", "adaptateur.capacites")
    def _(a, c):
        p = c / ".socle/adapter.toml"
        p.write_text(re.sub(r'(?m)^replacement = "capacité `mutation`.*\n', "", p.read_text()))
        return etage_ci(a, c)

    @defaut("fichier-de-deux-adaptateurs", "fichier désigné par deux adaptateurs", "ci", "adaptateur.recouvrement")
    def _(a, c):
        # Un second adaptateur aux motifs du premier : chaque fichier Python
        # serait jugé deux fois (ADR-0051, point 2).
        (c / ".socle/adapters").mkdir(exist_ok=True)
        shutil.copyfile(c / ".socle/adapter.toml", c / ".socle/adapters/doublon.toml")
        return etage_ci(a, c)

    @defaut("reponse-a-une-demande-changee", "demande réécrite après sa réponse", "ci", "demandes.reponses")
    def _(a, c):
        ajouter(c, ".github/CODEOWNERS", "# une ligne de plus\n")
        r = a.socle(c, "approve", "--text", "Une ligne de plus", "--yes")
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)
        pousser(a, c)
        d = next((c / "memory/requests").glob("D-*-approbation-humaine.md"))
        d.write_text(d.read_text().replace("## Options", "Une phrase glissée après coup.\n\n## Options", 1))
        return etage_ci(a, c)

    @defaut("hooks-non-declares", "hooks de l'agent retirés de ses réglages", "ci", "hooks.configuration")
    def _(a, c):
        (c / ".claude/settings.json").write_text('{"hooks": {}}\n')
        return etage_ci(a, c)

    @defaut("instructions-copiees", "CLAUDE.md qui recopie des instructions", "ci", "instructions.source-unique")
    def _(a, c):
        (c / "CLAUDE.md").write_text("@AGENTS.md\n\nToujours répondre en anglais.\n")
        return etage_ci(a, c)

    @defaut("instructions-absentes", "AGENTS.md supprimé, CLAUDE.md sans la section du socle", "ci",
            "instructions.source-unique")
    def _(a, c):
        a.run(c, "git", "rm", "-q", "AGENTS.md")
        return etage_ci(a, c)

    @defaut("memoire-sans-entete", "fichier de mémoire sans son en-tête", "ci", "memoire.format")
    def _(a, c):
        p = c / _sujet(c, "B-0001")
        p.write_text(p.read_text().split("\n", 1)[1])
        return etage_ci(a, c)

    @defaut("chantier-perime", "chantier actif qui ne bouge plus", "ci", "memoire.peremption")
    def _(a, c):
        maj_memoire(c)
        a.commit(c, "essai", env={"GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"})
        return a.socle(c, "check", "--stage", "ci", "--base", "origin/main").stdout

    @defaut("prive-sans-mode", "fichiers privés commités sans mode de mémoire privée", "git", "prive.acces")
    def _(a, c):
        ajouter(c, "memory/private/canonical.md", CANONIQUE_PRIVEE)
        return etage_git(a, c)

    @defaut("module-hors-cliquet", "module de code hors du cliquet de mutation", "ci", "mutation.couverture")
    def _(a, c):
        avec_mutation(c)
        ajouter(c, "unites.py", "CENTIMES = 100\n")
        maj_memoire(c, "Un module de constantes.")
        return etage_ci(a, c)

    @defaut("balayage-endormi", "balayage de mutation planifié endormi par GitHub", "ci", "mutation.vivante")
    def _(a, c):
        env = _balayage_planifie(a, c, "disabled_inactivity")
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=env)
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("balayage-inconnu", "balayage de mutation fusionné depuis dix jours, que GitHub ne connaît pas", "ci",
            "mutation.vivante")
    def _(a, c):
        env = _balayage_planifie(a, c, "inconnu", jours=10)
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=env)
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("mutants-survivants", "survivants de mutation au-delà du plafond", "ci", "mutation.verdict")
    def _(a, c):
        avec_mutation(c)
        r = a.socle(c, "mutation-verdict", str(balayage(c, "calc.x_double__mutmut_1: survived\n")))
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("reponse-par-agent", "l'agent écrit une réponse humaine", "agent", "fichier protégé")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-x.answer.toml"), "content": 'reponse = "valider"\n'})

    @defaut("agent-repond", "l'agent répond à la place de l'humain", "agent", "commande humaine")
    def _(a, c):
        lanceur = ".socle/" + "socle"  # en deux morceaux : ce fichier n'est pas une invocation
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} answer D-0001 valider"})

    @defaut("agent-repond-aide-glissee", "l'agent répond à la place de l'humain, `--help` glissé dans la réponse",
            "agent", "commande humaine")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} answer D-0001 valider --help"})

    @defaut("agent-repond-option-python", "l'agent répond à la place de l'humain, une option de python à valeur "
            "devant le lanceur", "agent", "commande humaine")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 -W ignore {lanceur} answer D-0001 valider"})

    @defaut("agent-approuve", "l'agent approuve lui-même un changement protégé", "agent", "commande de l'humain seul")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} approve --text 'mise à jour' --yes"})

    @defaut("agent-saute-les-hooks", "l'agent commite en sautant les hooks du projet", "agent",
            "contournement d'un hook")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "git add -A && git commit -q -m essai --" + "no-verify"})

    @defaut("agent-saute-les-hooks-cache", "l'agent pousse en sautant les hooks, par -C vers le projet", "agent",
            "contournement d'un hook")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": f"git -C {c} push --" + "no-verify origin HEAD"})

    @defaut("agent-repond-cache", "l'agent répond à la place de l'humain, lanceur entre guillemets après un cd",
            "agent", "commande humaine")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": 'cd .socle && python3 "socle" answer D-0001 valider; '
                                                     "echo --relayed --quote-file x"})

    @defaut("agent-installe-compagnon", "l'agent met en place le dépôt compagnon (pousse, crée une clé)", "agent",
            "commande de l'humain seul")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} private " + "install --repo git@h:o/p.git"})

    @defaut("agent-installe-hors-mode", "l'agent relance l'installeur sur le projet dans un autre mode que son verrou",
            "agent", "installeur hors mode")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} " + "install --target . --mode amont"})

    @defaut("agent-installe-cible-illisible", "l'agent relance l'installeur sur une cible écrite par une variable, "
            "vide dans le shell neuf de l'appel : elle viserait le projet", "agent", "installeur cible illisible")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} " + 'install --target "$D" --mode amont'})

    @defaut("relais-sans-citation", "réponse relayée sans le texte exact de l'humain", "agent", "commande humaine")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} answer D-0001 valider --relayed --by Théo"})

    @defaut("relais-demande-non-lue", "réponse relayée à une demande que l'humain n'a pas pu lire", "agent",
            "demande non lue")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(demande_bonne(a, c))
        (c / "citation.txt").write_text("ok, refonds d'abord")
        r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("copie", "paragraphe copié dans deux fichiers", "git", "docs.copie")
    def _(a, c):
        p = ("Ce paragraphe décrit en détail la manière dont le module de calcul multiplie ses entrées "
             "par une constante, et il est assez long pour qu'une copie ailleurs soit un vrai doublon "
             "qui divergera tôt ou tard de sa source.\n")
        ajouter(c, "docs/calc.md", "\n" + p)
        ajouter(c, "docs/autre.md", "# Autre\n\n" + p)
        return etage_git(a, c)

    @defaut("outil-non-documente", "dispositif qu'aucune doc ne nomme", "git", "docs.outillage")
    def _(a, c):
        ajouter(c, ".github/workflows/nuit.yml", "name: Nuit\non: [push]\njobs: {}\n")
        return etage_git(a, c)

    @defaut("question-en-widget", "décision posée à l'humain dans le widget de questions de l'agent", "agent",
            "question en widget")
    def _(a, c):
        return etage_outil(a, c, "AskUserQuestion", {"questions": [{
            "question": "Approuves-tu la spécification, docs/calc.md ?", "header": "Spécification",
            "multiSelect": False, "options": [{"label": "Approuver", "description": "La spécification est validée."},
                                              {"label": "Refuser", "description": "Elle se réécrit."}]}]})

    @defaut("fin-sans-recap", "fin d'intervention sans dire ce qui revient à l'humain", "agent", "récap")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "J'ai mis à jour le chantier actif. Tout passe.")

    @defaut("lot-trop-long", "lot ouvert qui attend plus de tâches qu'une session n'en mène, au-delà de "
            "`[batches] max_tasks`", "agent", "lot trop long")
    def _(a, c):
        # Un avertissement, dit par l'état et par le rappel de fin de tour :
        # attrapé s'il est dans les deux (B-0233).
        etat, rappel = _lot_de_deux_taches(a, c, 1)
        phrase = RAISONS_AGENT["lot trop long"]
        return etat + rappel if phrase in etat and phrase in rappel else ""

    @defaut("fin-sans-suite", "fin d'intervention qui ne dit pas la suite", "agent", "suite")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "J'ai mis à jour le chantier actif.\n\nPour toi : rien.")

    @defaut("suite-dans-un-bloc-de-code", "fin d'intervention dont la seule ligne « Ensuite : » est celle d'une "
            "sortie collée dans un bloc de code", "agent", "suite")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "Lot clos.\n\n```text\n" + COMPACT_COLLE + "\n```\n\nPour toi : rien.")

    @defaut("recap-dans-un-bloc-de-code", "fin d'intervention dont la seule ligne « Pour toi : » est celle de la "
            "suite du projet collée dans un bloc de code", "agent", "récap")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "Lot clos.\n\n```text\n" + FORME_COLLEE + "\n```\n\nEnsuite : le lot suivant.")

    @defaut("chemin-inexistant", "chemin donné à l'humain qui n'existe pas dans le dépôt", "agent", "liens")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "La doc est dans `docs/calcul.md`." + RECAP)

    @defaut("chemin-nom-nu", "nom nu d'un fichier suivi donné à l'humain entre accents graves, sans son chemin",
            "agent", "chemin complet")
    def _(a, c):
        # B-0371 : le refus donne le chemin complet du seul fichier suivi.
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "La doc est dans `calc.md`." + RECAP)

    @defaut("recap-absent-apres-refus-du-recap", "message sans récap qui suit, dans le même tour, un message refusé "
            "pour son récap et ses liens", "agent", "récap malgré un rappel")
    def _(a, c):
        # B-0371 : seul un message refusé pour ses seuls liens, qui portait
        # le récap, dispense le message qui les corrige de le redire.
        maj_memoire(c, "Travail du tour.")
        return _etage_stop_apres_refus(a, c, "La doc est dans `docs/calcul.md`.", "La doc est dans `docs/calc.md`.")

    @defaut("lien-relatif", "lien relatif, que l'humain ne peut pas suivre hors du conteneur", "agent", "liens")
    def _(a, c):
        return etage_stop(a, c, "Voir [la doc](docs/calc.md)." + RECAP)

    @defaut("pr-sans-lien", "pull request à fusionner citée sans son lien", "agent", "liens")
    def _(a, c):
        return etage_stop(a, c, "La pull request 2 reste à fusionner." + RECAP)

    @defaut("lien-non-pousse", "permalien vers un fichier absent de la version poussée", "agent", "liens")
    def _(a, c):
        ajouter(c, "docs/nouveau.md", "# Nouveau\n")
        sha = a.git(c, "rev-parse", "origin/main").strip()
        return etage_stop(a, c, f"Voir [la doc]({DEPOT_ESSAI}/blob/{sha}/docs/nouveau.md)." + RECAP)

    @defaut("demande-sans-lien", "demande en attente citée sans son lien", "agent", "lien de demande")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(demande_bonne(a, c))
        maj_memoire(c, "Demande D-0001 posée.")
        pousser(a, c)
        return etage_stop(a, c, "J'ai posé la demande D-0001.\n\nPour toi : répondre à D-0001.\nEnsuite : rien.")

    @defaut("branche-a-supprimer-absente", "branche donnée à supprimer à l'humain que l'origine n'a plus", "agent",
            "branche absente")
    def _(a, c):
        # B-0311 (D-0178) : reprise d'une entrée du journal sans la vérifier.
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, f"Lot clos.\n\nPour toi : supprimer la branche distante `fantome-{c.name}`, déjà "
                          "fusionnée.\nEnsuite : rien.")

    @defaut("fonction-sans-test", "fonction publique ajoutée sans test qui la nomme", "ci", "tests.code-teste")
    def _(a, c):
        ajouter(c, "calc.py", "\n\ndef triple(x):\n    return 3 * x\n")
        ajouter(c, "docs/calc.md", "`triple` multiplie par trois.\n")
        maj_memoire(c, "Ajout de triple.")
        return etage_ci(a, c)

    @defaut("plage-poussee", "fonction modifiée sans test, couverte seulement par une dispense déjà poussée", "git",
            "tests.code-teste")
    def _(a, c):
        # Contre la branche par défaut, la dispense du premier commit couvre
        # `triple` ; la plage du second push, celle que la CI jugera, non.
        ajouter(c, "calc.py", "\n\ndef triple(x):\n    return 3 * x\n")
        ajouter(c, "docs/calc.md", "`triple` multiplie par trois.\n")
        maj_memoire(c, "Ajout de triple, dispensée.")
        a.commit(c, "Ajout de triple\n\nDispense-test: triple — appelée par l'interface, testée de bout en bout")
        etage_push(a, c, hooks=False)
        remplacer(c, "calc.py", "return 3 * x", "return x * 3")
        remplacer(c, "docs/calc.md", "`triple` multiplie par trois.", "`triple` multiplie par trois, à droite.")
        remplacer(c, "memory/active.md", "Ajout de triple, dispensée.", "Triple, réécrite.")
        a.commit(c, "Triple réécrite")
        return etage_push(a, c)

    @defaut("plage-branche-disparue", "valeur attendue d'un test de la branche, poussée, puis affaiblie et repoussée "
            "après la suppression de la branche distante", "git", "tests.attendus")
    def _(a, c):
        # Contre la branche par défaut, où le test n'existe pas, la valeur
        # affaiblie passerait : la plage se juge depuis le dernier commit que
        # ce clone a poussé sur la branche disparue (ADR-0104).
        _pousser_un_cas_de_plus(a, c)
        pousse = a.git(c, "rev-parse", "HEAD").strip()
        a.git(c, "push", "-q", "--no-verify", "origin", "--delete", f"essai-{c.name}")
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(3), 6)", "self.assertEqual(double(3), 6.0)")
        remplacer(c, "memory/active.md", "Un cas de plus pour double.", "Le cas de plus, réécrit.")
        a.commit(c, "Le cas de plus, réécrit")
        sortie = etage_push(a, c)
        # Le refus dit d'où la plage se juge : sans cela, il n'est pas celui-ci.
        return sortie if not sortie or pousse[:10] in sortie else "le refus ne dit pas le dernier commit poussé"

    @defaut("decision-sans-lecture", "décision ajoutée sans avoir consulté l'index des décisions", "git", "memoire.lectures")
    def _(a, c):
        f1 = f"F-0001@{empreinte(a, c, 'F-0001')}"
        ajouter(c, "memory/decisions/ADR-0001-une-seule-multiplication.md", ADR_ESSAI.format(lu="", fait=f1))
        return etage_git(a, c)

    @defaut("citation-perimee", "entrée citée dans une version qu'elle n'a plus", "git", "memoire.lectures")
    def _(a, c):
        perimee = empreinte(a, c, "F-0001")
        remplacer(c, "memory/canonical.md", "Le test unitaire l'établit.", "Le test unitaire l'établit, sur deux cas.")
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nVoir F-0001@{perimee}.\n")
        return etage_git(a, c)

    @defaut("citation-par-un-ancien-numero", "entrée renumérotée citée par son ancien numéro, sous une empreinte "
            "inventée", "git", "memoire.lectures")
    def _(a, c):
        _renumeroter_en_lot(c, "B-0001")
        _citer_par_l_ancien_numero(a, c, "B-0001", "deadbeef")
        return etage_git(a, c)

    @defaut("identifiant-pris-deux-fois", "identifiant que la branche par défaut a pris aussi", "ci", "memoire.collisions")
    def _(a, c):
        r = a.socle(c, "check", "--stage", "ci", "--base", _collision(a, c))
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("consigne-citee-sans-empreinte", "consigne de l'humain citée dans le journal sans son empreinte", "git",
            "memoire.lectures")
    def _(a, c):
        _consigne_en_base(a, c)
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nSelon C-0001, rien à ajouter au module.\n")
        return etage_git(a, c)

    @defaut("consigne-citee-perimee", "consigne de l'humain citée dans le journal sous une empreinte périmée", "git",
            "memoire.lectures")
    def _(a, c):
        _consigne_en_base(a, c)
        perimee = empreinte(a, c, "C-0001")
        remplacer(c, "memory/directives.md", "reste sans dépendance", "reste sans aucune dépendance")
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nSelon C-0001@{perimee}, rien à ajouter au module.\n")
        return etage_git(a, c)

    @defaut("consigne-d-avant-la-plage-citee-sans-empreinte", "consigne d'avant la plage citée sans son empreinte "
            "dans le commit qui en pose une autre", "git", "memoire.lectures")
    def _(a, c):
        # B-0372 : seule la consigne née dans la plage s'y cite sans
        # empreinte ; celle de la base reste exigée avec la sienne.
        _consigne_en_base(a, c)
        ajouter(c, "memory/directives.md", _consigne(a, "C-0002").replace("reste sans dépendance",
                                                                          "reste en un seul fichier"))
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nThéo pose C-0002, qui s'ajoute à C-0001.\n")
        return etage_git(a, c)

    @defaut("consigne-resume-trop-long", "consigne dont la ligne de résumé dépasse 120 octets", "git", "memoire.format")
    def _(a, c):
        ajouter(c, "memory/directives.md", _consigne(a).replace(
            "reste sans dépendance", "reste sans dépendance, ni bibliothèque externe, ni module tiers, ni outil "
                                     "de construction, ni rien que la bibliothèque standard"))
        return etage_git(a, c)

    @defaut("consigne-sans-source", "consigne sans la source où la parole de l'humain est consignée", "git",
            "memoire.format")
    def _(a, c):
        ajouter(c, "memory/directives.md", _consigne(a).replace(f" · source : {a.journal}", ""))
        return etage_git(a, c)

    @defaut("consigne-sans-texte-exact", "consigne sans le texte exact de l'humain cité dans son corps", "git",
            "memoire.format")
    def _(a, c):
        ajouter(c, "memory/directives.md", _consigne(a).replace(
            "> « Pas de dépendance externe dans le module de calcul. »", "Pas de dépendance externe."))
        return etage_git(a, c)

    @defaut("consigne-levee-sans-demande", "consigne levée sans la demande validée qui la lève", "git",
            "memoire.preuves")
    def _(a, c):
        ajouter(c, "memory/directives.md", _consigne(a, statut="levée"))
        return etage_git(a, c)

    @defaut("consigne-levee-demande-sans-reponse", "consigne levée par une demande à laquelle l'humain n'a pas "
            "répondu", "git", "memoire.preuves")
    def _(a, c):
        ajouter(c, "memory/requests/D-0001-refondre-le-module.md", DEMANDE_BONNE)
        ajouter(c, "memory/directives.md", _consigne(a, statut="levée · levée-par : D-0001"))
        return etage_git(a, c)

    @defaut("consigne-texte-change", "texte exact d'une consigne de l'humain réécrit", "git", "memoire.ajout-seul")
    def _(a, c):
        _consigne_en_base(a, c)
        remplacer(c, "memory/directives.md", "Pas de dépendance externe", "Peu de dépendances externes")
        return etage_git(a, c)

    @defaut("consigne-effacee", "consigne de l'humain effacée", "git", "memoire.ajout-seul")
    def _(a, c):
        _consigne_en_base(a, c)
        remplacer(c, "memory/directives.md", _consigne(a).strip(), "")
        return etage_git(a, c)

    @defaut("consigne-rangee-en-vigueur", "consigne en vigueur rangée dans le journal, sans la parole de l'humain "
            "qui la lève", "git", "memoire.ajout-seul")
    def _(a, c):
        _consigne_en_base(a, c)
        remplacer(c, "memory/directives.md", _consigne(a).strip(), "")
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Consigne rangée\n\nRangée.\n"
                + _consigne(a).replace("## C-0001", "### C-0001"))
        return etage_git(a, c)

    @defaut("backlog-sans-lecture", "besoin ajouté au backlog sans l'avoir consulté", "git", "memoire.lectures")
    def _(a, c):
        ajouter_sujet(c, "\n## B-0002 — Ajouter une fonction quadruple\n\n"
                f"> statut : ouvert · origine : {a.journal}\n\nPour l'essai.\n")
        return etage_git(a, c)

    @defaut("constat-neuf-sous-adoption", "référence morte née après l'adoption, sous un contrôle en "
            "`warn_only`", "git", "memoire.references")
    def _(a, c):
        _adopte_avec_une_reference_morte(a, c)
        ajouter(c, "docs/calc.md", "Voir F-0097.\n")
        return etage_git(a, c)

    @defaut("defaut-indexe-masque", "défaut indexé, corrigé seulement sur disque", "git", "memoire.references")
    def _(a, c):
        ajouter(c, "docs/calc.md", "Voir F-0099.\n")
        a.git(c, "add", "docs/calc.md")
        remplacer(c, "docs/calc.md", "Voir F-0099.\n", "")  # corrigé sur disque, pas dans l'index
        r = a.run(c, "git", "commit", "-q", "-m", "essai")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @defaut("chemin-cite-hors-depot", "chemin cité présent sur le disque seulement, qu'une règle locale de git "
            "ignore", "agent", "memoire.references")
    def _(a, c):
        # B-0166 : passé en local, il manquait au clone neuf de la CI.
        ajouter(c, "docs/essais/x.md", "# Essai local\n")
        exclusions = Path(a.git(c, "rev-parse", "--git-path", "info/exclude").strip())
        exclusions = exclusions if exclusions.is_absolute() else c / exclusions
        exclusions.parent.mkdir(parents=True, exist_ok=True)
        exclusions.write_text("docs/essais/\n")
        maj_memoire(c, "Les essais vivent dans `docs/essais/`.")
        return etage_stop(a, c)

    @defaut("memoire-en-retard", "code changé sans mise à jour de la mémoire", "agent", "memoire.retard")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nmême")
        return etage_stop(a, c)

    return cas


# --------------------------------------------------------------------------
# Les témoins : ce qui est sain doit passer
# --------------------------------------------------------------------------

TEST_REGRESSION = '''import unittest

from calc import double


class TestChaine(unittest.TestCase):
    def test_double_d_une_chaine(self):
        self.assertEqual(double("3"), 6)
'''

# Un correctif dont le `Corrige:` est dans un paragraphe à part, avant les
# lignes d'attribution, où git ne lit pas de trailer (B-0348).
MESSAGE_CORRIGE_EGARE = ("Double accepte une chaîne\n\nLe calcul convertit son entrée.\n\nCorrige: B-0001\n\n"
                         "Signed-off-by: Essai <essai@example.org>")


def _temoins() -> list[tuple[str, Callable]]:
    t = []

    def temoin(nom):
        def deco(f):
            t.append((nom, f))
            return f
        return deco

    @temoin("un changement complet passe la fin de tour, le commit et la CI")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nnommée")
        maj_memoire(c)
        return etage_stop(a, c) or etage_git(a, c) or etage_ci(a, c)

    @temoin("un correctif avec son test de régression passe la CI")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        (c / "tests/test_regression.py").write_text(TEST_REGRESSION)
        maj_memoire(c, "Correctif de `double` sur les chaînes, avec son test.")
        return etage_ci(a, c, "fix: double accepte une chaîne")

    @temoin("un correctif de la seule documentation, avec la mémoire, passe la CI sans test")
    def _(a, c):
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        maj_memoire(c, "Correction de la doc de `double`.")
        return etage_ci(a, c, "Correction : la doc de double")

    @temoin("un correctif dont le `Corrige:` est hors du dernier paragraphe du message, avec son test de "
            "régression, passe la CI")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        (c / "tests/test_regression.py").write_text(TEST_REGRESSION)
        maj_memoire(c, "Correctif de `double` sur les chaînes, avec son test.")
        return etage_ci(a, c, MESSAGE_CORRIGE_EGARE)

    @temoin("sous l'adoption, une référence morte d'avant l'installation, déplacée d'une ligne, reste en "
            "avertissement au commit (B-0180)")
    def _(a, c):
        _adopte_avec_une_reference_morte(a, c)
        remplacer(c, "docs/calc.md", "# Calcul\n", "# Calcul\n\nUne ligne de plus.\n")
        return etage_git(a, c)

    @temoin("un commit sans hooks dans un dépôt jetable, hors du projet, passe le hook de l'agent")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "cd /tmp/jetable && git commit -q -m x --" + "no-verify"})

    @temoin("l'installeur relancé dans le mode du verrou, ou sur un dossier temporaire, passe le hook de l'agent")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return (etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} " + "install --target . --owner @moi"})
                or etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} " + "install --target /tmp/jetable-socle "
                                                         "--mode amont"}))

    @temoin("un chemin écrit par le shell à travers une variable sous un dossier hors du projet, une variable "
            "affectée vers un fichier libre ou un motif qui ne nomme aucun fichier protégé passent le hook de "
            "l'agent (B-0171)")
    def _(a, c):
        # Un dossier voisin de l'atelier, qui ne contient pas le projet
        # (le dossier temporaire, lui, le contient).
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": f"echo x > {ailleurs}/$SOCLE_ESSAI_CIBLE"})
                or etage_outil(a, c, "Bash", {"command": "F=notes.txt; echo x > \"$F\" && rm -f build/*.o"})
                or etage_outil(a, c, "Bash", {"command": f"pushd {ailleurs} && echo x > rapport-$SOCLE_ESSAI_CIBLE"
                                                         "; popd"}))

    @temoin("après un sous-shell, un fichier libre, une valeur par défaut hors du projet, un `sed` sans `-i` qui lit "
            "un fichier protégé et, depuis un dossier hors du projet, un motif relatif passent le hook de l'agent "
            "(B-0171, B-0205)")
    def _(a, c):
        # La revue de B-0171, constats 12 et 13 : ces faux refus ne sont
        # pas venus avec les corrections.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": "(cd /tmp && ls) && echo x > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": f"D={ailleurs}; echo x > \"${{D:-/tmp}}/rapport.txt\""})
                or etage_outil(a, c, "Bash", {"command": "sed -n -e's/i/j/p' .socle/policy.toml"})
                or etage_outil(a, c, "Bash", {"command": "rm -rf ./*"}, cwd=ailleurs))

    @temoin("une boucle sur des fichiers libres, une condition et un groupe qui écrivent un fichier libre, et une "
            "boucle qui revient à son dossier, passent le hook de l'agent (B-0204)")
    def _(a, c):
        return (etage_outil(a, c, "Bash", {"command": "for f in *.py; do sed -i s/3/9/ \"$f\"; done"})
                or etage_outil(a, c, "Bash", {"command": "if [ -f calc.py ]; then echo ok > notes.txt; else rm -f "
                                                         "notes.txt; fi"})
                or etage_outil(a, c, "Bash", {"command": "{ echo a; echo b; } > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "for d in */; do cd \"$d\"; ls; cd ..; done; "
                                                         "echo ok > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "for d in memory tests; do cd \"$d\" || continue; ls; cd ..; "
                                                         "done; echo ok > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "for d in */; do cd \"$d\" || { echo \"$d\" >&2; continue; }; "
                                                         "for f in *.log; do grep -q E \"$f\" && break; done; cd ..; "
                                                         "done; echo ok > notes.txt"}))

    @temoin("un `#` dans un mot, une redirection dans un commentaire et une substitution aux guillemets imbriqués "
            "qui lit un fichier protégé passent le hook de l'agent (B-0207)")
    def _(a, c):
        return (etage_outil(a, c, "Bash", {"command": "echo \"a#b\" > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "echo ok # > .socle/policy.toml"})
                or etage_outil(a, c, "Bash", {"command": "echo \"$(grep -c \"=\" .socle/policy.toml)\" > notes.txt"}))

    @temoin("`find -delete` d'un motif libre, `xargs` et `python -c` qui ne citent aucun fichier protégé et `cp -t` "
            "vers un dossier hors du projet passent le hook de l'agent (B-0206)")
    def _(a, c):
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": "find . -name '*.pyc' -delete"})
                or etage_outil(a, c, "Bash", {"command": "find . -name '*.py' | xargs sed -i s/3/9/"})
                or etage_outil(a, c, "Bash", {"command": "python3 -c \"print(open('calc.py').read())\""})
                or etage_outil(a, c, "Bash", {"command": f"cp -t {ailleurs} calc.py"}))

    @temoin("une commande trop imbriquée qui n'écrit rien, un long heredoc et 500 `cd` vers un dossier hors du "
            "projet passent le hook de l'agent (B-0171)")
    def _(a, c):
        # La seconde revue de B-0171, constat 4 : seuls les seuils et le
        # délai refusent, et seulement ce qui peut écrire.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": "echo " + "$(" * 40 + "true" + ")" * 40})
                or etage_outil(a, c, "Bash", {"command": f"cat > {ailleurs}/long.txt <<'FIN'\n"
                                                         + "une ligne de texte\n" * 1000 + "FIN"})
                or etage_outil(a, c, "Bash", {"command": f"cd {ailleurs}; " + "cd a; " * 500 + "echo x > notes.txt"}))

    @temoin("la suppression d'un dossier voisin du projet, d'un dossier du projet, un `find` sans filtre sous un "
            "dossier du projet et un `find` qui filtre ce qu'il supprime sous la racine passent le hook de l'agent "
            "(B-0208)")
    def _(a, c):
        # Le pendant sain de `suppression-du-projet` : seul ce qui contient
        # le projet est refusé.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": f"rm -rf {ailleurs} && rm -rf build"})
                or etage_outil(a, c, "Bash", {"command": "find . -name '*.pyc' -delete && mv calc.py .."})
                or etage_outil(a, c, "Bash", {"command": "find build -delete"})
                or etage_outil(a, c, "Bash", {"command": f"cd {ailleurs} && rm -rf ./*"}))

    @temoin("l'orchestrateur, à la racine du projet, retire le worktree d'un sous-agent, et `rsync --delete`, `git "
            "worktree remove` ou `python3 -c` qui suppriment un dossier du projet ou voisin de lui passent le hook de "
            "l'agent (B-0228)")
    def _(a, c):
        # Le pendant sain de `suppression-par-un-autre-programme` : seul ce
        # qui contient le projet, ou le projet lui-même, est refusé.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        return (etage_outil(a, c, "Bash", {"command": "git worktree remove .claude/worktrees/agent-x"})
                or etage_outil(a, c, "Bash", {"command": "git worktree remove -f -f .claude/worktrees/agent-x"})
                or etage_outil(a, c, "Bash", {"command": f"rsync -a --delete build/ {ailleurs}/sauve"})
                or etage_outil(a, c, "Bash", {"command": f"rsync -a --delete ./ {ailleurs}/sauve"})
                or etage_outil(a, c, "Bash", {"command": "python3 -c \"import shutil; shutil.rmtree('build')\""}))

    @temoin("un push de la branche de travail, sa branche écrite en toutes lettres ou dans une variable affectée "
            "plus tôt, et un `git` dont une option globale ne se développe pas, passent le hook de l'agent (B-0254)")
    def _(a, c):
        # Le pendant sain de `push-par-une-variable` : seul l'argument du
        # push qui ne se développe pas est refusé.
        return (etage_outil(a, c, "Bash", {"command": "git push -u origin travail"})
                or etage_outil(a, c, "Bash", {"command": "B=travail; git push origin \"$B\""})
                or etage_outil(a, c, "Bash", {"command": "D=.; git -C \"$D\" push origin travail"})
                or etage_outil(a, c, "Bash", {"command": "git -C \"$SOCLE_ESSAI_CIBLE\" status"}))

    @temoin("un push de la branche de travail par une substitution qui rend la branche courante, nue, entre "
            "guillemets, entre accents graves ou par une variable, passe le hook de l'agent (B-0254)")
    def _(a, c):
        # Le pendant sain de `push-de-la-branche-substituee` : depuis une
        # branche de travail, la substitution vaut elle.
        return (etage_outil(a, c, "Bash", {"command": "git push -u origin \"$(git branch --show-current)\""})
                or etage_outil(a, c, "Bash", {"command": "git push -u origin `git rev-parse --abbrev-ref HEAD`"})
                or etage_outil(a, c, "Bash", {"command": "B=$(git symbolic-ref --short HEAD); git push -u origin "
                                                         "\"$B\""})
                or etage_outil(a, c, "Bash", {"command": "git add -A && git commit -qm x && git push origin "
                                                         "$(git branch --show-current)"}))

    @temoin("une substitution entre guillemets qui lance une commande ordinaire, un calcul entre guillemets et un "
            "message de commit par `\"$(cat <<'EOF' … EOF)\"` qui cite une suppression passent le hook de l'agent "
            "(B-0260)")
    def _(a, c):
        # Le pendant sain de `substitution-entre-guillemets` : la commande
        # lancée se juge comme celle d'une substitution nue.
        return (etage_outil(a, c, "Bash", {"command": "x=\"$(git rev-parse HEAD)\"; echo \"$x\" > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "echo \"$((1 + 2)) `date`\" > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "f() { ls; }; x=\"$(f; rm -rf build)\""})
                or etage_outil(a, c, "Bash", {"command": "git commit -q -m \"$(cat <<'EOF'\nfix: x\n\nrm -rf ..\n"
                                                         "EOF\n)\""}))

    @temoin("les commandes ordinaires que lancent `uv run` et `poetry run`, et `uv sync`, passent le hook de "
            "l'agent (B-0248)")
    def _(a, c):
        # Le pendant sain de `suppression-par-un-lanceur` et de
        # `push-par-un-lanceur` : la commande lancée se juge comme sans eux.
        return (etage_outil(a, c, "Bash", {"command": "uv run pytest -q && uv run -m pytest && uv sync --frozen"})
                or etage_outil(a, c, "Bash", {"command": "poetry run pytest -x && poetry -C . run python -m unittest"})
                or etage_outil(a, c, "Bash", {"command": "uv run --with requests python -c \"print(open('calc.py')"
                                                         ".read())\""})
                or etage_outil(a, c, "Bash", {"command": "uv run git push -u origin travail"}))

    @temoin("un nettoyage ciblé par un `find` dont la conjonction des filtres, ou le `-path` sous son départ, "
            "n'atteint aucun fichier protégé passe le hook de l'agent (B-0231)")
    def _(a, c):
        # Le pendant sain de `find-conjonction-protegee` : un filtre seul ne
        # fait plus refuser ce que la conjonction écarte.
        return (etage_outil(a, c, "Bash", {"command": "find . -name '*.json' -path './build/*' -delete"})
                or etage_outil(a, c, "Bash", {"command": "find build -path '*.toml' -delete"}))

    @temoin("un nettoyage par `xargs rm` sous le projet, derrière un `find` dont un filtre garde ce qu'il liste ou "
            "qui part d'un dossier du projet, passe le hook de l'agent (B-0246)")
    def _(a, c):
        # Le pendant sain de `suppression-par-xargs` : seul ce qui contient
        # le projet, ou le projet lui-même, est refusé.
        return (etage_outil(a, c, "Bash", {"command": "find . -name '*.pyc' | xargs rm -f"})
                or etage_outil(a, c, "Bash", {"command": "find build -type f -print0 | xargs -0 rm -f"}))

    @temoin("le script qu'un heredoc donne à python sans citer de fichier protégé ni supprimer le projet, et un "
            "heredoc donné à un autre programme qui cite un fichier protégé, passent le hook de l'agent (B-0229)")
    def _(a, c):
        # Le pendant sain de `heredoc-donne-a-python` : seul le script que
        # python lit se juge, comme celui d'un `python -c`.
        return (etage_outil(a, c, "Bash", {"command": "python3 - <<'EOF'\nprint(open('calc.py').read())\nEOF"})
                or etage_outil(a, c, "Bash", {"command": "python3 - <<'EOF'\nimport shutil\n"
                                                         "shutil.rmtree('build', ignore_errors=True)\nEOF"})
                or etage_outil(a, c, "Bash", {"command": "cat > notes.txt <<'EOF'\n"
                                                         "open('.socle/policy.toml', 'w')\nEOF"}))

    @temoin("un `python -c` dont les arguments ne nomment aucun fichier protégé passe le hook de l'agent (B-0230)")
    def _(a, c):
        # Le pendant sain de `arguments-de-python-c` : seul l'argument qui
        # nomme un fichier protégé est refusé.
        return (etage_outil(a, c, "Bash", {"command": "python3 -c \"import sys; print(open(sys.argv[1]).read())\" "
                                                     "calc.py"})
                or etage_outil(a, c, "Bash", {"command": "python3 -c \"import sys; open(sys.argv[1], 'w')\" "
                                                         "notes.txt /tmp/x"}))

    @temoin("un `python -c` dont l'argument que le hook ne sait pas développer tombe hors du projet, ou dont le "
            "script ne lit pas ses arguments, et une boucle sur des fichiers connus passent le hook de l'agent")
    def _(a, c):
        # Le pendant sain de `argument-illisible-de-python-c` : seul l'argument
        # inconnu qui peut tomber dans le projet est refusé.
        ailleurs = a.dossier.parent / (a.dossier.name + "-ailleurs")
        ouvre = "python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\""
        return (etage_outil(a, c, "Bash", {"command": f"{ouvre} {ailleurs}/$SOCLE_ESSAI_CIBLE"})
                or etage_outil(a, c, "Bash", {"command": "python3 -c 'print(1)' \"$SOCLE_ESSAI_CIBLE\""})
                or etage_outil(a, c, "Bash", {"command": f"for f in docs/*.md; do {ouvre} \"$f\"; done"}))

    @temoin("l'orchestrateur, à la racine, retire le worktree d'un sous-agent par la fin de son chemin, et un "
            "sous-agent retire ou déplace un worktree voisin du sien, sans refus du hook de l'agent (B-0228)")
    def _(a, c):
        # Le pendant sain de `worktree-par-son-suffixe` : seul est refusé ce
        # qui finit le chemin de l'arbre jugé, ou d'un dossier qui le contient.
        arbre = c / ".claude/worktrees/sous-agent"
        a.git(c, "worktree", "add", "-q", "-b", "sous-agent", str(arbre))
        return (etage_outil(a, c, "Bash", {"command": "git worktree remove -f -f sous-agent"})
                or etage_outil(a, c, "Bash", {"command": "git worktree remove -f -f voisin"}, cwd=arbre)
                or etage_outil(a, c, "Bash", {"command": "git worktree remove .claude/worktrees/voisin"}, cwd=arbre)
                or etage_outil(a, c, "Bash", {"command": "git worktree move voisin /tmp/ailleurs"}, cwd=arbre))

    @temoin("une fonction `function nom { …; }` sans parenthèses dont le corps ne fait rien d'irréversible passe le "
            "hook de l'agent, et son corps ne s'exécute pas là où il s'écrit (B-0232)")
    def _(a, c):
        # Le pendant sain de `fonction-sans-parentheses` : le corps se juge
        # comme toute commande, et rend en se fermant l'état d'avant lui.
        return (etage_outil(a, c, "Bash", {"command": "function f { ls; }; f"})
                or etage_outil(a, c, "Bash", {"command": "function nettoyer\n{\n  rm -rf build\n}\nnettoyer"})
                or etage_outil(a, c, "Bash", {"command": "function f { cd .socle; }; echo ok > policy.toml"}))

    @temoin("l'appel d'une fonction qui ne change ni dossier ni variable ne rend rien inconnu, seul, derrière "
            "`time`, dans un `eval` ou une substitution, ni celui d'une fonction qui en appelle une autre définie "
            "après elle, et un préfixe programme (`command f`) ou une substitution ne laissent rien fuir (B-0232)")
    def _(a, c):
        # Le pendant sain d'`appel-de-fonction` : seul l'appel d'une fonction
        # dont le corps change le dossier ou une variable rend la suite
        # inconnue ; l'usage normal reste libre.
        return (etage_outil(a, c, "Bash", {"command": "f() { ls; }; f; rm -rf build"})
                or etage_outil(a, c, "Bash", {"command": "f() { echo x > /tmp/y; }; f; echo ok > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "f() { cd memory; }; command f; echo ok > notes.txt"})
                or etage_outil(a, c, "Bash", {"command": "g() { f; }; f() { ls; }; g; rm -rf build"})
                or etage_outil(a, c, "Bash", {"command": "f() { ls; }; time -p f; x=$(f); eval f; rm -rf build"})
                or etage_outil(a, c, "Bash", {"command": "f() { cd memory; }; x=$(f); rm -rf build"}))

    @temoin("un mot réservé cité, lu comme un mot et non comme une structure, passe le hook de l'agent quand il ne "
            "vise rien de protégé (B-0232)")
    def _(a, c):
        # Le pendant sain de `mot-reserve-cite` : un mot réservé entre
        # guillemets est un argument comme un autre.
        return (etage_outil(a, c, "Bash", {"command": 'echo "}" ; echo done'})
                or etage_outil(a, c, "Bash", {"command": 'echo "function" "{" "then"'}))

    @temoin("un fichier protégé changé par erreur, remis à son état du dernier commit, et un fichier apparu sous un "
            "chemin protégé, supprimé, passent le hook de l'agent (D-0098)")
    def _(a, c):
        ajouter(c, ".socle/policy.toml", "# changé par erreur\n")
        ajouter(c, ".github/CODEOWNERS", "* @essai\n")
        ajouter(c, ".socle/git-hooks/post-merge", "#!/bin/sh\n")
        return (etage_outil(a, c, "Bash", {"command": "git restore --source=HEAD --staged --worktree -- "
                                                      ".socle/policy.toml"})
                or etage_outil(a, c, "Bash", {"command": "git checkout HEAD -- .github/CODEOWNERS"})
                or etage_outil(a, c, "Bash", {"command": "rm .socle/git-hooks/post-merge"}))

    @temoin("un commit d'agent qui porte la trace de ses hooks passe la CI")
    def _(a, c):
        maj_memoire(c, "Commit d'agent avec hooks.")
        return etage_ci(a, c, "Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
                        "Socle-Agent: claude-code\nSocle-Hooks: SessionStart=1 PreToolUse=4 Stop=1\n"
                        "Socle-Hooks-Since-Commit: PreToolUse=2")

    @temoin("une valeur attendue changée sous une spécification que l'humain a commitée passe la CI")
    def _(a, c):
        ajouter(c, "memory/decisions/ADR-0001-test-double.md", _adr_test_double(a, c))
        a.commit(c, "Spécification : test_double compare à un flottant")  # un commit de l'humain
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        return etage_ci(a, c, MESSAGE_AGENT)

    @temoin("CLAUDE.md gardé comme seule source, avec la section du socle, passe la CI")
    def _(a, c):
        a.run(c, "git", "rm", "-q", "CLAUDE.md")
        a.run(c, "git", "mv", "AGENTS.md", "CLAUDE.md")
        remplacer(c, ".socle/guardrails.toml", '"AGENTS.md" = { max_bytes = 16000 }',
                  '"AGENTS.md" = { max_bytes = 16000 }\n"CLAUDE.md" = { max_bytes = 16000 }')
        return etage_ci(a, c)

    @temoin("une assertion reformatée à valeur égale passe la CI (relevé de recul, E)")
    def _(a, c):
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)",
                  "self.assertEqual(\n            double(2),\n            4,\n        )")
        maj_memoire(c, "Test reformaté.")
        return etage_ci(a, c, MESSAGE_AGENT)

    @temoin("un chemin d'un autre dépôt, non déclaré, est signalé sans refus")
    def _(a, c):
        remplacer(c, "memory/active.md", "## En cours\n\nRien pour l'instant.",
                  "## En cours\n\nLe modèle vient de `ailleurs:tools/etat.sh`.")
        return etage_ci(a, c)

    @temoin("un fichier neuf cité par la mémoire, ajouté par le même commit, passe la fin de tour, le commit et "
            "la CI")
    def _(a, c):
        ajouter(c, "docs/neuf.md", "# Neuf\n")
        maj_memoire(c, "La note vit dans `docs/neuf.md`.")
        return etage_stop(a, c) or etage_git(a, c) or etage_ci(a, c)

    @temoin("une référence de commit en fin de phrase passe la CI")
    def _(a, c):
        sha = a.run(c, "git", "rev-parse", "HEAD").stdout.strip()
        maj_memoire(c, f"Repris de l'essai (commit:{sha}).")
        return etage_ci(a, c)

    @temoin("un commit cité que l'origine ne garde que par une tête de pull request récupérée passe la CI d'un "
            "clone neuf hors de GitHub (B-0175)")
    def _(a, c):
        return etage_ci(a, _clone_d_un_clone(a, c, "refs/socle/pull/7"))

    @temoin("un skill du projet bien formé, qui cite dans son texte une commande à ne pas lancer, passe le "
            "commit et la CI")
    def _(a, c):
        _poser_skill(c, SKILL_ESSAI)
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un jalon qui attend un besoin ouvert, dans l'ordre, passe le commit et la CI")
    def _(a, c):
        ajouter_sujet(c, "\n## JA-0001 — Livrer la multiplication\n\n"
                         f"> statut : ouvert · origine : {a.journal} · après : B-0001 · "
                         f"lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")
        maj_memoire(c, "Le jalon de la multiplication posé.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une entrée renumérotée par la migration, qui porte `ancien`, et sa citation par l'ancien numéro sous "
            "l'empreinte de sa version actuelle passent le commit et la CI")
    def _(a, c):
        nouvel = _renumeroter_en_lot(c, "B-0001")
        if "ancien : B-0001" not in (c / _sujet(c, nouvel)).read_text():
            return trad("la migration n'a pas posé `ancien : B-0001` sur {id}", id=nouvel)
        _citer_par_l_ancien_numero(a, c, "B-0001", empreinte(a, c, nouvel))
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une entrée renumérotée mentionnée dans un texte neuf par son identifiant actuel, seul ou sur la ligne "
            "de l'ancien, passe le hook de l'agent")
    def _(a, c):
        nouvel = _renumeroter_en_lot(c, "B-0001")
        p = c / "docs/calc.md"
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": p.read_text() + f"\nVoir {nouvel}.\n"
                                                                                       f"B-0001 → {nouvel}.\n"})

    @temoin("une écriture qui garde telle quelle la ligne d'avant qui cite une entrée renumérotée par son ancien "
            "numéro, et change ce qui l'entoure, passe le hook de l'agent (T-0083)")
    def _(a, c):
        # Le pendant sain d'`ancien-numero-repris` : seules les lignes que
        # l'écriture ajoute ou change se jugent.
        _renumeroter_en_lot(c, "B-0001")
        p = c / "docs/calc.md"
        p.write_text("# Calcul\n\nLe lot B-0001 avance.\n\n" + p.read_text())
        return etage_outil(a, c, "Write", {"file_path": str(p), "content": "# Le calcul, revu\n" + p.read_text()
                                           .removeprefix("# Calcul\n") + "\nUne note.\n"})

    @temoin("un besoin et sa tâche posés par `socle new need --task`, un lot qui attend la tâche et un jalon qui "
            "attend le besoin, chacun dans sa forme, passent le commit et la CI")
    def _(a, c):
        r = a.socle(c, "new", "need", "Ajouter une fonction quadruple", "--task", "Écrire quadruple et son test")
        if r.returncode != 0 or "T-0001" not in r.stdout:
            return r.stdout + r.stderr
        for ident in ("B-0002", "T-0001"):
            p = c / _sujet(c, ident)
            p.write_text(re.sub(r"<J-…[^>]*>", a.journal, re.sub(r"- \[ \] <[^>]*>", "- [ ] quadruple existe",
                                                                     p.read_text())))
        ajouter_sujet(c, lot_essai(a, c, "L-0001", "T-0001"))
        ajouter_sujet(c, "\n## JA-0001 — Le module complet\n\n"
                         f"> statut : ouvert · origine : {a.journal} · après : B-0001, B-0002 · "
                         f"lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n")
        maj_memoire(c, "Le lot de la quadruple formé.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un besoin nouveau rangé dans le jalon ouvert par `socle new need --milestone`, et un autre gardé en "
            "réserve par `--reserve`, passent le commit et la CI (ADR-0118)")
    def _(a, c):
        _jalon_en_base(a, c)
        for titre, place in (("Ajouter une fonction quadruple", ("--milestone", "JA-0001")),
                             ("Ajouter une fonction quintuple", ("--reserve", "attend la quadruple"))):
            r = a.socle(c, "new", "need", titre, *place)
            if r.returncode != 0:
                return r.stdout + r.stderr
        for ident in ("B-0002", "B-0003"):
            p = c / _sujet(c, ident)
            p.write_text(re.sub(r"<J-…[^>]*>", a.journal, re.sub(r"- \[ \] <[^>]*>", "- [ ] elle existe",
                                                                     p.read_text())))
        maj_memoire(c, "Deux besoins rangés.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un jalon clos par `socle close` sur une réserve triée, chaque besoin avec sa raison, passe le commit et "
            "la CI (ADR-0118)")
    def _(a, c):
        _jalon_en_base(a, c, None)
        remplacer(c, _sujet(c, "B-0001"), "> statut : ouvert", "> statut : ouvert · réserve : après la multiplication")
        r = a.socle(c, "close", "JA-0001")
        if r.returncode != 0:
            return r.stdout + r.stderr
        maj_memoire(c, "Le jalon clos, la réserve triée.")
        return etage_git(a, c) or etage_ci(a, c)

    # L'historique des revues d'un lot (ADR-0084, ADR-0100) : des passes au-delà
    # de la première, et la clôture, sans recul.

    @temoin("une deuxième et une troisième passe de revue, sans recul, `socle review` les produit et les écrit dans "
            "le lot")
    def _(a, c):
        sortie = _passes(a, c, [_bloquant_essai(), _bloquant_essai()])
        if sortie:
            return sortie
        return "" if "### Passe 3 — " in (c / _sujet(c, "L-0001")).read_text() else "### Passe 3 ?"

    @temoin("un petit lot qui ne touche aucun garde-fou, `socle review --short` en donne le dossier court")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        a.commit(c, "un petit lot")
        r = a.socle(c, "review", "--short")
        return "" if r.returncode == 0 and "n'explore pas au-delà" in r.stdout else r.stdout + r.stderr

    @temoin("une passation dont la pull request est fusionnée par un commit de fusion pendant l'attente, un robot "
            "ayant poussé sans toucher la mémoire, passe sa garde, qui place la session neuve sur la branche par "
            "défaut")
    def _(a, c):
        neuve, ecrite = _passation(a, c)
        github = c.parent / f"{c.name}-github"
        a.git(a.dossier, "clone", "-q", "--no-local", str(c.parent / f"{c.name}-nu"), str(github))
        a.git(github, "checkout", "-q", "-b", "dependances", "origin/main")
        remplacer(github, "calc.py", '"""Calculs du projet d\'essai."""', '"""Calculs du projet d\'essai, à jour."""')
        r = a.commit(github, "une dépendance à jour", env=_apres_la_passation(ecrite))
        if r.returncode != 0:
            return r.stdout + r.stderr
        a.git(github, "push", "-q", "--no-verify", "origin", "dependances")
        a.git(github, "checkout", "-q", "main")
        a.git(github, "merge", "-q", "--no-ff", "-m", "Fusion de la pull request du lot", "origin/travail")
        a.git(github, "push", "-q", "--no-verify", "origin", "main")
        r = _session_neuve(a, neuve)
        return "" if r.returncode == 0 and "se placer sur origin/main" in r.stdout else r.stdout + r.stderr

    @temoin("une passation dont la pull request est fusionnée par squash pendant l'attente, sa branche supprimée et "
            "le `git fetch` de la session neuve élaguant, passe sa garde, qui place la session neuve sur la branche "
            "par défaut")
    def _(a, c):
        neuve, _ = _passation(a, c)
        _fusion_par_squash(a, c)
        a.git(neuve, "config", "fetch.prune", "true")
        r = _session_neuve(a, neuve)
        return "" if r.returncode == 0 and "se placer sur origin/main" in r.stdout else r.stdout + r.stderr

    @temoin("une branche de l'agent contenue dans la branche par défaut se supprime par sa commande, le hook avant "
            "push laissant passer la suppression")
    def _(a, c):
        clone = _branche_a_elaguer(a, c, agent=True)
        r = a.socle(clone, "prune-branches")
        restee = a.git(clone, "ls-remote", "--heads", "origin", f"refs/heads/{BRANCHE_ELAGUEE}").strip()
        return r.stdout + r.stderr if r.returncode or restee or "supprimée : " not in r.stdout else ""

    @temoin("la session qui part, sa passation commitée et poussée, la retrouve en attente après son push")
    def _(a, c):
        _ecrire_la_passation(a, c)
        r = a.socle(c, "handoff", "check")
        return "" if r.returncode == 0 and "se placer sur origin/travail" in r.stdout else r.stdout + r.stderr

    @temoin("une session programmée, une tâche prête et un lot mené sans message de l'humain, écrit sa passation")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        _ranger(a, c)
        r = a.socle(c, "handoff", "write", "--scheduled", "--chain", "1")
        ecrite = (c / "memory/handoff.md").read_text() if (c / "memory/handoff.md").is_file() else ""
        return "" if r.returncode == 0 and "· chaîne : 1\n" in ecrite else r.stdout + r.stderr + ecrite

    @temoin("une passation écrite par `socle handoff write` passe le commit et la CI")
    def _(a, c):
        r = a.socle(c, "handoff", "write", "--waiting", "la CI du commit de tête")
        if r.returncode != 0:
            return r.stdout + r.stderr
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un lot relu clos « fait », ses deux passes sans recul, passe le commit et la CI")
    def _(a, c):
        _lot_relu_clos(a, c, _bloquant_essai())
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un lot en cours dont la passe consigne son bloquant « - Bloquant : … », et un paragraphe replié sur une "
            "ligne qui commence par « bloquants », passe le commit et la CI")
    def _(a, c):
        _lot_en_cours_relu(a, c, "- Bloquant : la correction change la lecture du facteur")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une tâche de priorité haute faite après la réponse qu'elle attendait, ses critères cochés, passe le "
            "commit et la CI")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(demande_bonne(a, c))
        pousser(a, c)
        (c / "citation.txt").write_text("oui")
        r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
        if r.returncode != 0:
            return r.stdout + r.stderr
        (c / "citation.txt").unlink()
        ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : fichier:calc.py · après : D-0001 · priorité : haute"))
        maj_memoire(c, "La multiplication livrée.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("un cas ajouté à un fichier de cas passe le commit et la CI")
    def _(a, c):
        remplacer(c, "docs/double.cas.json", '"attendu": 6\n  }\n]',
                  '"attendu": 6\n  },\n  {\n    "id": "c3",\n    "entree": 5,\n    "attendu": 10\n  }\n]')
        maj_memoire(c, "Un cas de plus.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("durcir un garde-fou est libre")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", '"memory/active.md" = { max_bytes = 1600 }', '"memory/active.md" = { max_bytes = 1500 }')
        return etage_ci(a, c)

    @temoin("un lot ouvert qui attend autant de tâches que `[batches] max_tasks` : ni l'état ni le rappel de fin "
            "de tour n'avertissent")
    def _(a, c):
        etat, rappel = _lot_de_deux_taches(a, c, 2)
        if "prochain lot : L-0001" not in etat or "prochain lot : L-0001" not in rappel:
            return trad("l'état ou le rappel de fin de tour ne disent pas le lot :\n{etat}\n{rappel}",
                        etat=etat[-1500:], rappel=rappel[-1500:])
        phrase = RAISONS_AGENT["lot trop long"]
        return etat + rappel if phrase in etat or phrase in rappel else ""

    @temoin("baisser le seuil de durée des étapes rapides est libre : la CI passe")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", "fast_max_seconds = 300", "fast_max_seconds = 120")
        return etage_ci(a, c)

    @temoin("un seuil de durée des étapes rapides à `nan` en base, gardé tel quel, passe la CI")
    def _(a, c):
        _seuil_rapide_nan_en_base(a, c)
        maj_memoire(c, "Le seuil gardé tel quel.")
        return etage_ci(a, c)

    @temoin("des étapes rapides d'un peu plus d'une seconde, sous le seuil du gabarit, poussées : le hook avant "
            "envoi laisse passer sans avertir")
    def _(a, c):
        code, sortie = _pousser_des_etapes_lentes(a, c)
        return (sortie or "push refusé") if code or RAISONS_AGENT["verify.duree"] in sortie else ""

    @temoin("des étapes rapides d'un peu plus d'une seconde, sous le seuil du gabarit : `verify --fast` dit leurs "
            "durées, sans avertir")
    def _(a, c):
        ajouter(c, "tests/test_lent.py", TEST_LENT)
        r = a.socle(c, "verify", "--fast")
        sortie = r.stdout + r.stderr
        if RAISONS_AGENT["verify.duree"] in sortie or "… total des étapes lancées : " not in r.stderr:
            return sortie
        return ""

    @temoin("un module nouveau entre au cliquet de mutation « à mesurer » : la CI passe")
    def _(a, c):
        ajouter(c, "unites.py", "CENTIMES = 100\n")
        remplacer(c, ".socle/guardrails.toml", '"calc.py" = { max = 0 }',
                  '"calc.py" = { max = 0 }\n"unites.py" = { pending = true }')
        maj_memoire(c, "Un module de constantes, à mesurer.")
        return etage_ci(a, c)

    @temoin("un plafond de mutation posé par la mesure passe la CI")
    def _(a, c):
        ajouter(c, "unites.py", "CENTIMES = 100\n")
        remplacer(c, ".socle/guardrails.toml", '"calc.py" = { max = 0 }',
                  '"calc.py" = { max = 0 }\n"unites.py" = { max = 2, reason = "mesuré le 2026-10-12 : 2 survivant(s)" }')
        maj_memoire(c, "Un module de constantes, mesuré.")
        return etage_ci(a, c)

    @temoin("une demande de choix qui propose les réponses de base et ses options passe, et une demande qui nomme "
            "un test passe avec `valider`")
    def _(a, c):
        chemin = str(c / "memory/requests/D-0001-refactor.md")
        # D-0053 : les réponses de base dans toute demande, les options en plus.
        choix = demande_bonne(a, c).replace("- `refuser` — j'ajoute tel quel.\n",
                                            "- `refuser` — j'ajoute tel quel.\n- `scinder` — je scinde le module.\n")
        return (etage_outil(a, c, "Write", {"file_path": chemin, "content": choix})
                or etage_outil(a, c, "Write", {"file_path": chemin, "content": demande_bonne(a, c).replace(
                    "Vérifié : un seul appelant.", "Vérifié : un seul appelant, que `test_double` exerce.")}))

    @temoin("une commande qui ne fait que citer une action refusée passe le hook de l'agent")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        for commande in (f'git commit -m "doc: ne jamais lancer python3 {lanceur} answer D-0001 valider"',
                         "cat > docs/regles.md <<'EOF'\nInterdit : git push --force, rm -rf /.\nEOF",
                         "grep -rn 'push --force' docs/", "git push -u origin travail"):
            refus = etage_outil(a, c, "Bash", {"command": commande})
            if refus:
                return f"{commande} : {refus}"
        return ""

    @temoin("un mot proche d'un terme privé, sans l'être, passe le commit")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "docs/calc.md", "Un vent mistralien souffle sur le module.\n")
        maj_memoire(c, "Une phrase de plus.")
        return etage_git(a, c)

    @temoin("un balayage de mutation planifié qui tourne passe la CI")
    def _(a, c):
        env = _balayage_planifie(a, c, "active")
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=env)
        if r.returncode != 0:
            return r.stdout + r.stderr
        # Lu et vivant, pas indisponible : sinon ce témoin passerait sans
        # rien prouver.
        ligne = next((l.split() for l in r.stdout.splitlines() if l.strip().startswith("mutation.vivante")), [])
        return "" if ligne[-1:] == ["ok"] else f"mutation.vivante, attendu « ok » : {r.stdout}"

    @temoin("un balayage de mutation fusionné aujourd'hui, que GitHub ne connaît pas encore, passe la CI")
    def _(a, c):
        env = _balayage_planifie(a, c, "inconnu")
        r = a.socle(c, "check", "--stage", "ci", "--base", "origin/main", env=env)
        if r.returncode != 0:
            return r.stdout + r.stderr
        return "" if "ne le connaît pas encore" in r.stdout else f"mutation.vivante, avertissement attendu : {r.stdout}"

    @temoin("un balayage de mutation sous le plafond passe le verdict")
    def _(a, c):
        avec_mutation(c)
        r = a.socle(c, "mutation-verdict", str(balayage(c, "calc.x_double__mutmut_1: killed\n")))
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @temoin("un garde-fou assoupli par l'humain, qui l'approuve, passe la CI")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", '"memory/active.md" = { max_bytes = 1600 }',
                  '"memory/active.md" = { max_bytes = 9000 }')
        r = a.socle(c, "approve", "--keys", 'budgets."memory/active.md".max_bytes', "--text", "Plus de place")
        return (r.stdout + r.stderr) if r.returncode != 0 else etage_ci(a, c)

    @temoin("les fichiers d'un outil tiers, déclaré par l'humain qui l'approuve, échappent aux contrôles : la CI "
            "passe")
    def _(a, c):
        remplacer(c, ".socle/guardrails.toml", TIERS_VIDE, '\npaths = ["_outil/**"]\n')
        r = a.socle(c, "approve", "--keys", "thirdparty.paths", "--text", "Les fichiers de l'outil")
        if r.returncode != 0:
            return r.stdout + r.stderr
        ajouter(c, "_outil/aide.py", "def aide(x):\n    return x\n")
        ajouter(c, "_outil/test_outil.py", "def test_rien():\n    pass\n")
        ajouter(c, "_outil/LISEZMOI.md", "Chaque constat cite `file:line`, et F-0099.\n")
        return etage_ci(a, c)

    @temoin("le commit d'un agent d'une autre session, sans les hooks du socle, qui ne touche que des chemins "
            "déclarés tiers, passe la CI")
    def _(a, c):
        _declarer_ui_tierce(a, c)
        ajouter(c, "ui/app.py", "def rendu(x):\n    return x\n")
        return etage_ci(a, c, "fix: l'interface rend mieux\n\nCo-Authored-By: Claude <noreply@anthropic.com>")

    @temoin("un chemin qui n'existe que dans une rustine suivie du dépôt passe la CI")
    def _(a, c):
        (c / "attic").mkdir(exist_ok=True)
        (c / "attic/sondes.patch").write_text("--- /dev/null\n+++ b/attic/sondes/lecteur.py\n@@ -0,0 +1 @@\n+X = 1\n")
        ajouter(c, "docs/calc.md", "Le lecteur `attic/sondes/lecteur.py` vient de la rustine.\n")
        return etage_ci(a, c)

    @temoin("une demande que seules ses lignes d'empreinte portent au-delà de son budget, un fichier protégé et "
            "son empreinte sur chacune, sans description, se commite")
    def _(a, c):
        _demande_d_une_mise_a_jour(a, c, 300)
        return etage_git(a, c)

    @temoin("un fichier protégé changé par l'humain, qui l'approuve, passe la CI")
    def _(a, c):
        ajouter(c, ".github/CODEOWNERS", "# une ligne de plus\n")
        r = a.socle(c, "approve", "--text", "Une ligne de plus", "--yes")
        return (r.stdout + r.stderr) if r.returncode != 0 else etage_ci(a, c)

    @temoin("un second adaptateur aux motifs disjoints, posé par l'installeur et approuvé par l'humain, passe la CI")
    def _(a, c):
        # La mise à jour qui ajoute Kotlin : son adaptateur, l'outil de sa
        # CI et son balayage planifié (ADR-0051, point 6).
        r = a.run(c, sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from socle.cli import main; "
                  "sys.exit(main(sys.argv[2:]))", str(a.moteur), "install", "--target", ".", "--adapter", "python",
                  "--adapter", "kotlin", "--owner", "@essai")
        if not (c / ".socle/adapters/kotlin.toml").is_file():
            return r.stdout + r.stderr
        r = a.socle(c, "approve", "--text", "L'adaptateur Kotlin", "--yes")
        return (r.stdout + r.stderr) if r.returncode != 0 else etage_ci(a, c)

    @temoin("une valeur attendue changée sous une demande validée par l'humain passe la CI")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(_demande_nommant_le_test(a, c))
        pousser(a, c)
        (c / "citation.txt").write_text("oui, compare à un flottant")
        r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
        if r.returncode != 0:
            return r.stdout + r.stderr
        (c / "citation.txt").unlink()
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        return etage_ci(a, c)

    @temoin("une valeur attendue changée sous une décision que l'humain a donnée de lui-même et qui nomme le test, "
            "consignée par `socle decision --unprompted`, passe la CI")
    def _(a, c):
        return _test_change_sous_une_decision_donnee(a, c, "Change test_double : il compare à un flottant.")

    @temoin("une réponse « valider » poussée avec le test qu'elle autorise à changer part sans avertissement")
    def _(a, c):
        code, sortie = _pousser_la_reponse(a, c, avec_le_test=True)
        return (sortie or "push refusé") if code else ""

    @temoin("une réponse « valider » poussée avec la clé des garde-fous qu'elle autorise à relâcher part sans "
            "avertissement")
    def _(a, c):
        code, sortie = _pousser_la_reponse(a, c, avec_le_test=True, cle=True)
        return (sortie or "push refusé") if code else ""

    @temoin("une réponse « valider » poussée seule couvre le test qu'elle autorise à changer, poussé au push "
            "suivant")
    def _(a, c):
        code, sortie = _pousser_la_reponse(a, c, avec_le_test=False)
        if code:
            return sortie or "push refusé"
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        a.commit(c, "Le test que la réponse autorise")
        r = a.run(c, "git", "push", "-q", "origin", f"travail:{c.name}")
        return (r.stdout + r.stderr or "push refusé") if r.returncode else ""

    @temoin("une valeur attendue changée sous une validation fusionnée qu'une tâche ouverte cite, son test "
            "inchangé depuis, passe la CI")
    def _(a, c):
        return _changer_sous_une_validation_fusionnee(a, c, tache="ouvert")

    @temoin("un correctif dont le test passe sur le parent, admis par une demande validée qui nomme son commit, "
            "passe la CI")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return FACTEUR * int(x)")
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nentière")
        (c / "tests/test_regression.py").write_text(TEST_REGRESSION.replace('double("3")', "double(3)"))
        maj_memoire(c, "Correctif de `double` sur les chaînes.")
        r = a.commit(c, "fix: double accepte une chaîne")
        if r.returncode != 0:
            return r.stdout + r.stderr
        sha = a.git(c, "rev-parse", "HEAD").strip()[:8]
        demande = demande_bonne(a, c).replace(
            "- B-0001@", f"- {sha} — le correctif de double, dont le test passe sur le parent dans la CI.\n- B-0001@", 1)
        (c / "memory/requests/D-0001-refactor.md").write_text(demande)
        pousser(a, c)
        (c / "citation.txt").write_text("valider")
        r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
        (c / "citation.txt").unlink()
        if r.returncode != 0:
            return r.stdout + r.stderr
        return etage_ci(a, c)

    @temoin("une demande récente, ouverte sur le projet, le chantier et la question, passe le hook de l'agent")
    def _(a, c):
        # ADR-0046 : le pendant sain de `demande-sans-le-projet`.
        recente = demande_bonne(a, c).replace("> date : 2026-10-10", "> date : 2026-11-08").replace(
            "## Contexte\n\n", "## Contexte\n\n" + PARAGRAPHES_DU_CONTEXTE, 1)
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"),
                                           "content": recente})

    @temoin("dans un worktree du dépôt, une commande qui cite une entrée créée là passe le hook de l'agent")
    def _(a, c):
        # B-0164 : le hook, lancé à la racine de la session, juge l'arbre où
        # l'action a lieu ; la copie principale n'a pas encore l'entrée.
        arbre = c / ".claude/worktrees/sous-agent"
        a.git(c, "worktree", "add", "-q", "-b", "sous-agent", str(arbre))
        ajouter(arbre, "memory/decisions/ADR-0090-travailler-dans-un-worktree.md",
                "<!-- socle: couche=decisions zone=publique -->\n# ADR-0090 — Travailler dans un worktree\n\n"
                "> statut : acceptée · date : 2026-11-11\n\n## Décision\n\nLe sous-agent travaille à part.\n")
        p = arbre / "docs/calc.md"
        return (etage_outil(a, c, "Write", {"file_path": str(p), "content": p.read_text() + "\nVoir ADR-0090.\n"},
                            cwd=arbre)
                or etage_outil(a, c, "Bash", {"command": "grep -n ADR-0090 docs/calc.md"}, cwd=arbre))

    @temoin("une demande complète passe le hook de l'agent")
    def _(a, c):
        return etage_outil(a, c, "Write", {"file_path": str(c / "memory/requests/D-0001-refactor.md"), "content": demande_bonne(a, c)})

    @temoin("une réponse donnée dans la conversation, relayée avec sa citation, passe le hook et la CI")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(demande_bonne(a, c))
        pousser(a, c)  # l'humain la lit, puis répond dans la conversation
        (c / "citation.txt").write_text("ok, refonds d'abord")
        lanceur = ".socle/" + "socle"
        commande = f"python3 {lanceur} answer D-0001 valider --relayed --by Théo --quote-file citation.txt"
        refus = etage_outil(a, c, "Bash", {"command": commande})
        if refus:
            return refus
        r = a.socle(c, "answer", "D-0001", "valider", "--relayed", "--by", "Théo", "--quote-file", "citation.txt")
        (c / "citation.txt").unlink()
        if r.returncode != 0:
            return r.stdout + r.stderr
        maj_memoire(c, "Refonte validée dans la conversation.")
        return etage_ci(a, c)

    @temoin("une fin d'intervention avec « Pour toi : » et « Ensuite : » passe le hook de fin de tour")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "J'ai mis à jour le chantier actif. Tout passe.\n\nPour toi : rien.\n"
                          "Ensuite : le sujet suivant du backlog.")

    @temoin("une fin d'intervention avec ses deux lignes en texte et la suite du projet collée dans un bloc de code "
            "passe le hook de fin de tour")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, "Lot clos.\n\n```text\n" + FORME_COLLEE + "\n```\n\nPour toi : rien.\n"
                          "Ensuite : le lot suivant.")

    @temoin("des liens que l'humain peut suivre passent le hook de fin de tour")
    def _(a, c):
        (c / "memory/requests/D-0001-refactor.md").write_text(demande_bonne(a, c))
        maj_memoire(c, "Demande D-0001 posée.")
        pousser(a, c)
        r = a.socle(c, "url", "D-0001", "docs/calc.md")
        if r.returncode != 0:
            return r.stdout + r.stderr
        return etage_stop(a, c, "J'ai posé la demande D-0001, sur le module `calc.py` et sa doc `docs/calc.md`.\n\n"
                          + r.stdout + "\nPour toi : répondre à D-0001.\nEnsuite : rien.")

    @temoin("un message qui ne corrige que les liens d'un message refusé pour eux seuls, qui portait le récap, passe "
            "le hook de fin de tour sans redire le récap (B-0371)")
    def _(a, c):
        maj_memoire(c, "Travail du tour.")
        return _etage_stop_apres_refus(a, c, "La doc est dans `calc.md`." + RECAP, "La doc est dans `docs/calc.md`.")

    @temoin("une branche donnée à supprimer que l'origine a encore passe le hook de fin de tour")
    def _(a, c):
        a.git(c, "push", "-q", "--no-verify", "origin", f"HEAD:refs/heads/morceau-{c.name}")
        maj_memoire(c, "Travail du tour.")
        return etage_stop(a, c, f"Lot clos.\n\nPour toi : supprimer la branche distante `morceau-{c.name}`, déjà "
                          "fusionnée.\nEnsuite : rien.")

    @temoin("une fonction ajoutée avec le test qui la nomme passe la CI")
    def _(a, c):
        ajouter(c, "calc.py", "\n\ndef triple(x):\n    return 3 * x\n")
        ajouter(c, "docs/calc.md", "`triple` multiplie par trois.\n")
        ajouter(c, "tests/test_calc.py", "    def test_triple(self):\n        from calc import triple\n"
                "        self.assertEqual(triple(2), 6)\n")
        maj_memoire(c, "Ajout de triple, avec son test.")
        return etage_ci(a, c)

    @temoin("deux pushes sains de suite passent le hook avant push, qui juge la plage de chacun")
    def _(a, c):
        ajouter(c, "calc.py", "\n\ndef triple(x):\n    return 3 * x\n")
        ajouter(c, "docs/calc.md", "`triple` multiplie par trois.\n")
        ajouter(c, "tests/test_calc.py", "    def test_triple(self):\n        from calc import triple\n"
                "        self.assertEqual(triple(2), 6)\n")
        maj_memoire(c, "Ajout de triple, avec son test.")
        a.commit(c, "Ajout de triple")
        refus = etage_push(a, c)
        if refus:
            return refus
        remplacer(c, "docs/calc.md", "`triple` multiplie par trois.", "`triple` multiplie par trois, toujours.")
        a.commit(c, "La doc de triple")
        return etage_push(a, c)

    @temoin("une branche fusionnée, que l'humain a changée sur la branche par défaut, puis repartie d'elle sous le "
            "même nom après la suppression de la branche distante, passe le hook avant push")
    def _(a, c):
        # Le dernier commit poussé est dans la branche par défaut : la branche
        # se juge comme une branche neuve, contre elle, et non depuis lui,
        # d'où la valeur que l'humain a changée serait refusée (ADR-0104).
        _pousser_un_cas_de_plus(a, c)
        a.git(c, "checkout", "-q", "main")
        a.git(c, "merge", "-q", "--no-ff", "--no-verify", "-m", "Fusion de la branche", "travail")
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(3), 6)", "self.assertEqual(double(3), 6.0)")
        a.commit(c, "L'humain change la valeur")
        # La fusion, connue de ce clone comme après un fetch, sans toucher la
        # branche par défaut de l'origine, que les cas partagent.
        a.git(c, "update-ref", "refs/remotes/origin/main", "HEAD")
        a.git(c, "push", "-q", "--no-verify", "origin", "--delete", f"essai-{c.name}")
        a.git(c, "checkout", "-q", "-B", "travail", "origin/main")
        remplacer(c, "memory/active.md", "Un cas de plus pour double.", "La suite, après la fusion.")
        a.commit(c, "La suite")
        return etage_push(a, c)

    @temoin("une fonction privée, ou publique et dispensée avec sa raison, passe la CI")
    def _(a, c):
        ajouter(c, "calc.py", "\n\ndef _aide(x):\n    return x\n\n\ndef triple(x):\n    return 3 * _aide(x)\n")
        ajouter(c, "docs/calc.md", "`triple` multiplie par trois.\n")
        maj_memoire(c, "Ajout de triple, dispensée.")
        return etage_ci(a, c, "Ajout de triple\n\nDispense-test: triple — appelée par l'interface, testée de bout en bout")

    @temoin("mode compagnon : une entrée privée commitée et verrouillée passe la fin de tour, le commit et la CI")
    def _(a, c):
        c = a.clone_prive("compagnon")
        ajouter(c, "memory/private/canonical.md", "\n## PF-0002 — Une seconde idée privée\n\n> statut : supposé · source : PF-0001\n")
        a.git(c / "memory/private", "commit", "-q", "-am", "seconde idée")
        r = a.socle(c, "private", "lock")
        if r.returncode != 0:
            return r.stdout + r.stderr
        maj_memoire(c, "Mémoire privée avancée.")
        return etage_stop(a, c) or etage_git(a, c) or etage_ci(a, c)

    @temoin("mode chiffré : une entrée privée part chiffrée et passe le commit et la CI")
    def _(a, c):
        c = a.clone_prive("chiffre")
        ajouter(c, "memory/private/canonical.md", "\n## PF-0002 — Une seconde idée privée\n\n> statut : supposé · source : PF-0001\n")
        maj_memoire(c, "Mémoire privée avancée.")
        sortie = etage_git(a, c) or etage_ci(a, c)
        if not sortie and not a.git(c, "show", "HEAD:memory/private/canonical.md").startswith("ESSAI:"):
            sortie = "le fichier privé est commité en clair"
        return sortie

    @temoin("mode compagnon : un message de commit passé par un fichier du dossier courant de l'agent, qui ne cite "
            "aucun terme privé, passe le hook de l'agent, quand la racine a un fichier du même nom qui en cite un "
            "(B-0205)")
    def _(a, c):
        # Le pendant sain de `fuite-fichier-du-dossier-courant`.
        c = a.clone_prive("compagnon")
        ajouter(c, "docs/message.txt", "Avance.\n")
        ajouter(c, "message.txt", "Avance sur Mistral.\n")
        return etage_outil(a, c, "Bash", {"command": "git commit -F message.txt"}, cwd=c / "docs")

    @temoin("ajouter un terme à la liste privée est libre : le commit et la CI passent")
    def _(a, c):
        c = a.clone_prive("compagnon")
        r = a.socle(c, "private", "term", "Zephyr")
        a.git(c / "memory/private", "commit", "-q", "-am", "un terme de plus")
        a.socle(c, "private", "lock")
        maj_memoire(c, "Un terme privé de plus.")
        return (r.stderr if r.returncode else "") or etage_git(a, c) or etage_ci(a, c)

    @temoin("mode compagnon : un besoin public basculé dans la mémoire privée passe la fin de tour, le commit et la "
            "CI")
    def _(a, c):
        c = a.clone_prive("compagnon")
        r = a.socle(c, "private", "move", "B-0001")
        if r.returncode != 0:
            return r.stdout + r.stderr
        a.git(c / "memory/private", "add", "-A")
        a.git(c / "memory/private", "commit", "-q", "-m", "B-0001 basculé")
        a.socle(c, "private", "lock")
        maj_memoire(c, "Sujet basculé dans la mémoire privée.")
        return etage_stop(a, c) or etage_git(a, c) or etage_ci(a, c)

    @temoin("une mémoire en anglais : ses entrées, écrites par `socle new`, passent le commit et la CI")
    def _(a, c):
        o = a.dossier / "origine-en"
        o.mkdir()
        a.git(o, "init", "-q", "-b", "main")
        (o / "calc.py").write_text(CALC)
        r = a.run(o, sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from socle.cli import main; "
                  "sys.exit(main(sys.argv[2:]))", str(a.moteur), "install", "--target", ".", "--adapter", "python",
                  "--owner", "@essai", "--language", "en")
        if r.returncode != 0:
            return r.stdout + r.stderr
        a.git(o, "add", "-A")
        a.git(o, "commit", "-q", "--no-verify", "-m", "Project in English")
        c = a.clone(o)
        a.socle(c, "new", "fact", "Double doubles")
        remplacer(c, "memory/canonical.md", "> status : assumed · source : <where this fact comes from>\n\n"
                  "<the fact, and what would prove it>", "> status : measured · proof : file:calc.py\n\nRead in the code.")
        remplacer(c, "memory/active.md", "## In progress\n\nNothing yet.", "## In progress\n\nA first fact.")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une valeur attendue changée sous une demande en attente, poussée : le tour finit, le commit attend")
    def _(a, c):
        ajouter(c, "memory/requests/D-0001-refactor.md", _demande_nommant_le_test(a, c))
        pousser(a, c, "La demande")
        remplacer(c, "tests/test_calc.py", "self.assertEqual(double(2), 4)", "self.assertEqual(double(2), 4.0)")
        maj_memoire(c)
        sortie = etage_stop(a, c, "J'ai changé le test en attendant la réponse." + RECAP)
        if sortie:
            return sortie
        return "" if etage_git(a, c) else "le commit d'une valeur attendue en attente de validation passe"

    @temoin("un fichier protégé changé sous une demande en attente, poussée : le tour finit, le commit attend")
    def _(a, c):
        from socle import fingerprint as empreintes

        # Une mise à jour en session cloud (B-0115) : la demande cite le
        # fichier changé et son empreinte, poussée avant que l'humain réponde.
        ajouter(c, ".github/CODEOWNERS", "# une ligne de plus\n")
        nouveau = (c / ".github/CODEOWNERS").read_text()
        cite = empreintes.courte(empreintes.fichier(c / ".github/CODEOWNERS"))
        a.git(c, "checkout", "-q", "--", ".github/CODEOWNERS")
        ajouter(c, "memory/requests/D-0001-refactor.md", demande_bonne(a, c).replace(
            "## Où regarder", f"- `.github/CODEOWNERS` et `{cite}` — le fichier protégé changé.\n\n## Où regarder", 1))
        pousser(a, c, "La demande")
        (c / ".github/CODEOWNERS").write_text(nouveau)
        sortie = etage_stop(a, c, "J'ai mis le socle à jour en attendant la réponse." + RECAP)
        if sortie:
            return sortie
        return "" if etage_git(a, c) else "le commit d'un fichier protégé en attente de validation passe"

    @temoin("un fichier protégé sous une demande en attente, poussée, la CI du socle exigée : il se commite et se "
            "pousse")
    def _(a, c):
        protege_en_attente(a, c)
        env = ci_exigee(a, c)
        # La branche existe déjà en face : le hook avant push juge aussi la
        # plage qui part, comme la CI la jugera.
        return (etage_push(a, c, hooks=False, env=env) or etage_git(a, c, env=env)
                or etage_push(a, c, env=env))

    @temoin("une valeur attendue changée sous une demande en attente, poussée, la CI du socle exigée : elle se "
            "commite et se pousse")
    def _(a, c):
        _valeur_en_attente(a, c)
        env = ci_exigee(a, c)
        return (etage_push(a, c, hooks=False, env=env) or etage_git(a, c, env=env)
                or etage_push(a, c, env=env))

    @temoin("un push relu par l'humain, son accord relayé avec son texte exact, passe le hook de l'agent")
    def _(a, c):
        c = a.clone_prive("compagnon")
        (c / "accord.txt").write_text("ok, tu peux publier")
        commande = "python3 .socle/" + "socle reviewed --relayed --by Théo --quote-file accord.txt"
        refus = etage_outil(a, c, "Bash", {"command": commande})
        if refus:
            return refus
        r = a.socle(c, "reviewed", "--relayed", "--by", "Théo", "--quote-file", "accord.txt")
        if r.returncode:
            return r.stdout + r.stderr
        return etage_outil(a, c, "Bash", {"command": "git push origin travail"})

    @temoin("sans la clé (une CI de fork), la mémoire privée est indisponible et rien n'échoue")
    def _(a, c):
        c = a.clone_prive("chiffre", cle=False)
        maj_memoire(c, "Travail sans la clé.")
        sortie = etage_ci(a, c)
        if not sortie and "INDISPONIBLE" not in etage_demarrage(a, c):
            sortie = "l'état ne signale pas la mémoire privée indisponible"
        return sortie

    @temoin("en CI, un constat de la zone privée échoue sans montrer son contenu")
    def _(a, c):
        c = a.clone_prive("compagnon")
        remplacer(c, "memory/private/canonical.md", "statut : supposé", "statut : inventé")
        a.git(c / "memory/private", "commit", "-q", "-am", "statut faux")
        a.socle(c, "private", "lock")
        maj_memoire(c, "Statut privé faux.")
        sortie = etage_ci(a, c)
        if not sortie:
            return "la CI passe malgré un statut inconnu dans la zone privée"
        if "Mistral" in sortie or "inventé" in sortie or "canonical.md" in sortie:
            return "la CI montre le contenu de la zone privée :\n" + sortie
        return ""

    @temoin("une fin de tour sans travail n'exige pas de récap")
    def _(a, c):
        etage_stop(a, c, "Pour toi : rien.\nEnsuite : rien.")  # retient l'état de l'arbre
        return etage_stop(a, c, "Réponse à une question, sans rien changer.")

    @temoin("une relance du hook après une correction passe la fin de tour")
    def _(a, c):
        remplacer(c, "calc.py", "return FACTEUR * x", "return x * FACTEUR")
        maj_memoire(c)
        if not etage_stop(a, c):
            return "la fin de tour passe sur un code sans sa doc"
        remplacer(c, "docs/calc.md", "la\nconstante", "la constante\nnommée")
        r = a.socle(c, "hook", "stop", entree=json.dumps({"session_id": "autotest", "stop_hook_active": True}))
        return r.stdout if "sans changement" in r.stdout or '"block"' in r.stdout else ""

    @temoin("un identifiant renuméroté après une collision passe la CI")
    def _(a, c):
        point = _collision(a, c)
        r = a.socle(c, "renumber", "B-0002")
        if r.returncode != 0:
            return r.stdout + r.stderr
        a.commit(c, "renuméroté")
        r = a.socle(c, "check", "--stage", "ci", "--base", point)
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @temoin("un besoin clos après sa tâche faite, rangés avec les clos par `socle archive`, passent la CI")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c, statut="fait · ref : fichier:calc.py"))
        _clore(c, "B-0001")
        r = a.socle(c, "archive")
        if r.returncode != 0 or not list((c / "memory/backlog/closed").glob("B-0001-*.md")):
            return r.stdout + r.stderr or "B-0001 n'est pas rangé"
        return etage_ci(a, c, "B-0001 clos et rangé")

    @temoin("une tâche cochée close par `socle close`, sa référence « ce commit », passe le commit et la CI "
            "(ADR-0117)")
    def _(a, c):
        ajouter_sujet(c, tache_essai(a, c))
        r = a.socle(c, "close", "T-0001")
        if r.returncode != 0 or not list((c / "memory/backlog/closed").glob("T-0001-*.md")):
            return r.stdout + r.stderr or "T-0001 n'est pas rangée"
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une décision qui prouve ses lectures passe le commit")
    def _(a, c):
        lu = f" · lu : decisions@{empreinte(a, c, 'decisions')}"
        f1 = f"F-0001@{empreinte(a, c, 'F-0001')}"
        ajouter(c, "memory/decisions/ADR-0001-une-seule-multiplication.md", ADR_ESSAI.format(lu=lu, fait=f1))
        ajouter_sujet(c, "\n## B-0002 — Ajouter une fonction quadruple\n\n"
                f"> statut : ouvert · origine : {a.journal} · lu : backlog@{empreinte(a, c, 'backlog')}\n\nPour l'essai.\n"
                f"{SATISFAIT_ESSAI}")
        return etage_git(a, c)

    @temoin("une consigne citée dans le journal sous l'empreinte de sa version actuelle, sa ligne de résumé "
            "récrite, passe le commit")
    def _(a, c):
        _consigne_en_base(a, c)
        remplacer(c, "memory/directives.md", "reste sans dépendance", "reste sans aucune dépendance")
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nSelon C-0001@{empreinte(a, c, 'C-0001')}, rien à ajouter "
                "au module.\n")
        return etage_git(a, c)

    @temoin("une consigne posée dans la plage, citée sans son empreinte dans le journal du même commit, passe le "
            "commit et la CI (B-0372)")
    def _(a, c):
        ajouter(c, "memory/directives.md", _consigne(a))
        ajouter(c, "memory/journal/" + a.journal[2:9] + ".md",
                f"\n## {a.journal[:-1]}B — Constat\n\nThéo pose C-0001 : rien à ajouter au module.\n")
        return etage_git(a, c) or etage_ci(a, c)

    @temoin("une consigne levée par la parole de l'humain, consignée en séance, puis rangée par `socle archive`, "
            "passe la CI")
    def _(a, c):
        _consigne_en_base(a, c)
        (c / "citation.txt").write_text("La consigne C-0001 ne vaut plus : le module peut avoir des dépendances.")
        r = a.socle(c, "decision", "Lever la consigne C-0001 sur les dépendances", "--unprompted", "--relayed",
                    "--by", "Théo", "--quote-file", "citation.txt")
        (c / "citation.txt").unlink()
        # Son identifiant, que les branches poussées par d'autres cas peuvent
        # avoir fait avancer.
        demande = re.search(r"\bD-\d{4}\b", r.stdout)
        if r.returncode != 0 or not demande:
            return r.stdout + r.stderr
        remplacer(c, "memory/directives.md", "> statut : en vigueur", f"> statut : levée · levée-par : {demande.group(0)}")
        r = a.socle(c, "archive")
        if r.returncode != 0 or "C-0001" in (c / "memory/directives.md").read_text():
            return r.stdout + r.stderr or "C-0001 n'est pas rangée"
        sortie = a.socle(c, "show", "C-0001").stdout
        if "archivée dans" not in sortie:
            return f"C-0001 rangée ne se résout pas : {sortie}"
        return etage_ci(a, c)

    @temoin("une consigne nouvelle posée par `socle new directive`, sa source et le texte exact écrits, passe le "
            "commit, et l'état donne sa ligne de résumé")
    def _(a, c):
        r = a.socle(c, "new", "directive", "Le module de calcul reste sans dépendance")
        ident = re.match(r"C-\d{4}\tmemory/directives\.md$", r.stdout.strip())
        if r.returncode != 0 or not ident:
            return r.stdout + r.stderr
        remplacer(c, "memory/directives.md", "<J-… ou D-… où la parole de l'humain est consignée>", a.journal)
        remplacer(c, "memory/directives.md", "<le texte exact de l'humain, mot pour mot>",
                  "Pas de dépendance externe dans le module de calcul.")
        etat = a.socle(c, "state").stdout
        if f"{ident.group(0)[:6]} — Le module de calcul reste sans dépendance" not in etat:
            return f"l'état ne donne pas la consigne : {etat[-2000:]}"
        return etage_git(a, c)

    @temoin("un commit d'agent fait dans un autre worktree porte la trace des hooks et passe la CI")
    def _(a, c):
        # Les hooks de l'agent tirent dans le dépôt principal…
        entree = {"session_id": "autotest-wt", "source": "startup"}
        a.socle(c, "hook", "session-start", entree=json.dumps(entree))
        a.socle(c, "hook", "pre-tool-use", entree=json.dumps({**entree, "tool_name": "Bash", "tool_input": {"command": "ls"}}))
        # … et le commit se fait dans un autre worktree, comme la pull request
        # de démonstration.
        wt = c.parent / f"{c.name}-wt"
        a.git(c, "worktree", "add", "-q", "-b", "autre", str(wt))
        maj_memoire(wt, "Travail fait dans un autre worktree.")
        r = a.commit(wt, "Travail d'agent\n\nCo-Authored-By: Claude <noreply@anthropic.com>", verifier=True,
                     env={"CLAUDECODE": "1"})
        if r.returncode != 0:
            return r.stdout + r.stderr
        r = a.socle(wt, "check", "--stage", "ci", "--base", "origin/main")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @temoin("une session d'agent dont le hook de démarrage a tiré : l'état n'avertit pas")
    def _(a, c):
        a.socle(c, "hook", "session-start", entree=json.dumps({"session_id": "avec-hooks", "source": "startup"}))
        r = a.socle(c, "state", "--short", env={"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "avec-hooks"})
        return "\n".join(l for l in r.stdout.splitlines() if l.startswith("!!"))

    @temoin("un commit d'agent dont le filtre a tiré depuis le commit précédent passe le hook avant commit")
    def _(a, c):
        a.socle(c, "hook", "pre-tool-use", entree=json.dumps(
            {"session_id": "avec-filtre", "tool_name": "Bash", "tool_input": {"command": "git commit -m essai"}}))
        maj_memoire(c, "Commit d'agent, ses hooks chargés.")
        a.git(c, "add", "-A")
        r = a.run(c, "git", "commit", "-q", "-m", "essai",
                  env={"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "avec-filtre"})
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @temoin("un défaut sur disque mais pas dans l'index ne bloque pas le commit de ce qui est indexé")
    def _(a, c):
        maj_memoire(c, "Seul ce changement est indexé.")
        a.git(c, "add", "memory/active.md")
        ajouter(c, "docs/calc.md", "Voir F-0099.\n")  # en cours, non indexé
        r = a.run(c, "git", "commit", "-q", "-m", "essai")
        return "" if r.returncode == 0 else r.stdout + r.stderr

    @temoin("une tautologie voulue, raison écrite, passe le commit")
    def _(a, c):
        ajouter(c, "tests/test_calc.py", "    def test_deterministe(self):\n"
                "        self.assertEqual(double(3), double(3))  # socle: voulu — double est déterministe\n")
        return etage_git(a, c)

    @temoin("l'aide de `socle answer`, `decision` et `reviewed` passe le hook de l'agent")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} answer --help && python3 {lanceur} "
                                                     f"decision -h && python3 {lanceur} reviewed --help"})

    @temoin("une commande qui CITE `socle answer` sans l'appeler passe")
    def _(a, c):
        return etage_outil(a, c, "Bash", {"command": "grep -n 'socle answer' AGENTS.md"})

    @temoin("l'agent verrouille la mémoire privée : seule sa mise en place est réservée à l'humain")
    def _(a, c):
        lanceur = ".socle/" + "socle"
        return etage_outil(a, c, "Bash", {"command": f"python3 {lanceur} private lock"})

    @temoin("une écriture ordinaire passe le hook de l'agent")
    def _(a, c):
        return etage_outil(a, c, "Edit", {"file_path": str(c / "docs/calc.md"), "old_string": "# Calcul", "new_string": "# Le calcul"})

    return t


# --------------------------------------------------------------------------


def jouer(a: Atelier, tache) -> tuple:
    """Un cas ou un témoin dans son clone : (sa sortie, None), ou (None,
    l'exception). Le clone est dans le `try` : un clone qui échoue n'échoue
    que son cas, pas l'auto-test entier (B-0341)."""
    nom, f, cas = tache
    try:
        return (f or cas.fonction)(a, a.clone()), None
    except Exception as e:
        return None, e


def executer(projet=None, bavard: bool = False) -> Rapport:
    import socle

    r = Rapport()
    moteur = Path(socle.__file__).resolve().parent.parent
    a = Atelier(moteur, bavard)
    try:
        try:
            a.preparer()
        except Exception as e:
            r.execute("autotest")
            r.erreur("autotest", trad("projet d'essai impossible à préparer : {erreur}", erreur=e))
            return r
        # Chaque cas dans son clone, sur plusieurs fils : l'auto-test passe de
        # 76 à moins de 40 secondes sur quatre cœurs (L6). Le rapport garde
        # l'ordre des cas.
        taches = [(nom, f, None) for nom, f in _temoins()] + [(None, None, cas) for cas in _cas()]
        with ThreadPoolExecutor(max_workers=FILS) as fils:
            resultats = list(fils.map(lambda tache: jouer(a, tache), taches))
        for (nom, f, cas), (sortie, panne) in zip(taches, resultats):
            if cas is None:
                ident = "autotest.temoins"
                r.execute(ident)
                if panne is not None:
                    sortie = trad("le témoin a planté : {erreur}", erreur=f"{type(panne).__name__}: {panne}")
                if sortie:
                    r.erreur(ident, trad("témoin en échec — {nom} : un contrôle crie sur un cas sain\n        {sortie}",
                                         nom=trad(nom), sortie="\n        ".join(sortie.strip().splitlines()[-25:])))
                elif bavard:
                    print(trad("  témoin ok : {nom}", nom=trad(nom)), file=sys.stderr)
                continue
            ident = f"autotest.{cas.id}"
            r.execute(ident)
            if panne is not None:
                r.erreur(ident, trad("{defaut} : injection impossible — {erreur}", defaut=trad(cas.defaut),
                                     erreur=f"{type(panne).__name__}: {panne}"))
                continue
            if not sortie:
                r.erreur(ident, trad("DÉFAUT NON ATTRAPÉ : {defaut} (attendu : {controle}, étage {etage})",
                                     defaut=trad(cas.defaut), controle=cas.controle, etage=cas.etage))
            elif not _attrape_par(cas, sortie):
                r.erreur(ident, trad("{defaut} : attrapé, mais pas par {controle}\n        {sortie}",
                                     defaut=trad(cas.defaut), controle=cas.controle,
                                     sortie="\n        ".join(sortie.strip().splitlines()[-15:])))
            elif bavard:
                print(trad("  attrapé : {defaut} — {controle}, étage {etage}",
                           defaut=trad(cas.defaut), controle=cas.controle, etage=cas.etage), file=sys.stderr)
    finally:
        a.nettoyer()
    return r


# Le hook PreToolUse ne nomme pas de contrôle : il rend sa raison, qu'on
# reconnaît à ces mots.
# Les contrôles du registre qu'aucun défaut injecté n'éprouve, chacun avec
# sa raison écrite : un test exige que tout autre en ait un.
SANS_DEFAUT: dict[str, str] = {}

RAISONS_AGENT = {
    "demandes.contrat": "demande hors contrat",
    "memoire.preuves": "sans demande validée par l'humain",
    "anti-fabrication": "SHA fabriqué",
    "politique point 4": "politique, point 4",
    "fichier protégé": "est protégé par la politique",
    "commande humaine": "ne répond jamais à la place de l'humain",
    "commande de l'humain seul": "est réservé à l'humain",
    "contournement d'un hook": "contourne les hooks du projet",
    "installeur hors mode": "dans un autre mode que celui de son verrou",
    "installeur cible illisible": "une cible que le hook ne sait pas résoudre",
    "écriture protégée": "par le shell : seul l'humain",
    "écriture illisible": "un chemin que le hook ne sait pas développer",
    "commande injugeable": "une commande que le hook ne sait pas juger",
    "suppression du projet": "d'un dossier qui contient le projet",
    "remise hors forme": "Seule passe la remise",
    "remise sous demande": "en attente, ou validée sans que ce qu'elle approuve",
    "écriture à l'aveugle": "à l'aveugle",
    "référence inventée": "référence inventée",
    "ancien numéro": "est l'ancien numéro de",
    "escalade": "ARRÊT ET ESCALADE",
    "échec inchangé": "sans changement depuis la tentative précédente",
    "memoire.peremption": "chantier actif inchangé depuis",
    # L'avertissement des étapes rapides au-delà de leur seuil (B-0258).
    "verify.duree": "durée des étapes rapides au dernier passage complet",
    # L'avertissement d'un lot ouvert qui ne se mène pas en une session
    # (B-0233), dans l'état et le rappel de fin de tour.
    "lot trop long": "plus de tâches qu'une session n'en mène",
    "réglage de l'agent": "les réglages de Claude Code commandent ses hooks",
    "où regarder": "« Où regarder » doit donner un lien",
    "contexte du projet": "« Contexte » : il commence par trois paragraphes",
    "récap": "pas Pour toi :",
    "suite": "pas Ensuite :",
    "liens": "liens que l'humain ne pourra pas suivre",
    # B-0371 : le nom nu d'un seul fichier suivi, refusé avec son chemin
    # complet ; le récap qui manque encore à la relance, dit à l'humain.
    "chemin complet": "le seul fichier suivi de ce nom est `docs/calc.md` : écrire ce chemin complet",
    "récap malgré un rappel": "fin d'intervention sans Pour toi :",
    "lien de demande": "sans son lien",
    "branche absente": "que l'origine n'a plus",
    "signal indisponible": "mémoire privée : INDISPONIBLE",
    "fuite": "fuite de la mémoire privée",
    "relecture": "relecture avant publication",
    "demande non lue": "n'a pas pu être lue par l'humain",
    "hooks non chargés": "LES HOOKS DE L'AGENT NE SONT PAS CHARGÉS",
    "commit sans filtre": "commit d'agent sans aucun passage du filtre",
    "geste sans valider": "que seule une réponse `valider` autorise à changer",
    "question en widget": "widget de questions de l'agent",
    # `socle review` ne nomme pas de contrôle non plus : il refuse le dossier
    # court d'un lot qui touche un garde-fou (B-0288).
    "revue courte refusée": "le lot touche un garde-fou",
    # `socle handoff check` non plus : il refuse la passation, en disant
    # pourquoi, dans la session neuve comme dans celle qui part, après son
    # push.
    "passation poussée depuis": "quelqu'un a poussé sur origin/travail depuis la passation",
    "passation d'une autre session": "une autre session travaille sur le projet",
    "passation déjà reprise": "est déjà reprise : origin/travail porte son retrait",
    "passation squash d'une autre session": "porte parmi ses ancêtres 1 commit(s) écrit(s) après",
    "passation non poussée": "n'est pas poussée : aucune branche de origin ne la porte",
    "passation non commitée": "des changements ne sont pas commités (memory/handoff.md)",
    # `socle handoff write` non plus : il refuse la passation programmée, en
    # disant pourquoi.
    "borne de la chaîne": "lots menés sans message de l'humain, sa borne est",
    "passation sans tâche prête": "le prochain lot n'a aucune tâche prête",
    # `socle prune-branches` laisse la branche, en disant pourquoi.
    "branche de l'humain": "son dernier commit ne porte pas la marque d'un agent",
    "branche non contenue": "aucune branche de l'agent à supprimer",
    "suppression coupée": "`prune_branches = false`",
}


def _attrape_par(cas: Cas, sortie: str) -> bool:
    """Le défaut est-il attrapé par le contrôle ATTENDU ? Le rapport liste
    tous les contrôles exécutés, réussis compris : seule la ligne de synthèse
    `ECHEC — n contrôle(s) : …` dit lesquels ont échoué, dans toutes les langues. Un étage ou un
    contrôle qui plante n'attrape rien : il refuse par accident."""
    if "Traceback (most recent call last)" in sortie or "le contrôle a planté" in sortie \
            or "the check crashed" in sortie:
        return False
    # Un rapport d'étage d'abord : un contrôle que le hook de l'agent nomme
    # aussi (`memoire.preuves`, `demandes.contrat`) s'attrape en CI par sa
    # ligne de synthèse, pas par la phrase de son refus.
    if cas.controle in en_echec_dans(sortie):
        return True
    if cas.controle in RAISONS_AGENT:
        return RAISONS_AGENT[cas.controle] in sortie
    return False
