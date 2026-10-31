"""Le projet tel que le socle le voit : sa racine et ses quatre fichiers.

- `.socle/engine.lock`     — version et empreinte du moteur (installeur seul) ;
- `.socle/policy.toml`     — politique d'autonomie (humain seul) ;
- `.socle/adapter.toml`    — capacités du langage (validé par l'humain) ;
- `.socle/guardrails.toml` — seuils et couverture des contrôles (cliquet :
  durcir est libre, assouplir exige une demande validée).

Les chemins et les clés sont en anglais, les commentaires et messages en
français.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from socle import utils as outils
from socle.messages import trad

DOSSIER = ".socle"
LANCEUR = ".socle/socle"
GIT_HOOKS = ".socle/git-hooks"
TRACE = ".socle/trace/hooks.log"  # hors dépôt git seulement
COMPTEUR_STOP = ".socle/trace/stop-echecs"
INSTRUCTIONS = "AGENTS.md"
# Ce qui ouvre la section du socle dans le fichier d'instructions : AGENTS.md,
# ou CLAUDE.md quand l'installeur l'a gardé comme source.
DEBUT_SOCLE = "<!-- socle:debut — section posée par l'installeur, régénérée à chaque mise à jour -->"


@dataclass(frozen=True)
class Chemins:
    """Où vivent les fichiers d'un projet."""

    memoire: str
    canonique: str
    actif: str
    backlog: str  # un dossier, un fichier par sujet
    decisions: str
    journal: str
    demandes: str
    archives: str
    prive: str
    termes: str
    reponse: str  # le suffixe d'une réponse humaine, à côté de sa demande
    lock: str
    politique: str
    garde_fous: str
    adaptateur: str
    prive_lock: str
    moteur: str  # le dossier du moteur installé

    def dans_prive(self, chemin: str) -> str:
        """Le miroir d'un chemin de la mémoire dans la zone privée."""
        return self.prive + chemin[len(self.memoire):] if chemin.startswith(self.memoire + "/") else chemin


FORMAT_ACTUEL = Chemins("memory", "memory/canonical.md", "memory/active.md", "memory/backlog",
                        "memory/decisions", "memory/journal", "memory/requests", "memory/archives", "memory/private",
                        "memory/private/terms.txt", ".answer.toml", ".socle/engine.lock", ".socle/policy.toml",
                        ".socle/guardrails.toml", ".socle/adapter.toml", ".socle/private.lock", ".socle/engine")
# Le format de la mémoire, que le verrou note.
FORMAT = 3

MODE_AMONT = "amont"   # le dépôt qui fabrique le moteur : il le modifie
MODE_PROJET = "projet"  # un projet qui l'utilise : le moteur y est immuable


def chemin_trace(racine: Path) -> Path:
    """La trace des hooks vit dans le répertoire git commun
    (`.git/socle/hooks.log`), que partagent tous les worktrees du dépôt : les
    hooks de l'agent y écrivent depuis le dépôt principal, et le hook git d'un
    commit fait dans un autre worktree y lit la même trace. Hors
    dépôt git, sous `.socle/trace/`."""
    import subprocess

    r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       cwd=racine, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()) / "socle" / "hooks.log"
    return racine / TRACE


def lire_trace(racine: Path) -> list[str]:
    """Les lignes de la trace."""
    p = chemin_trace(racine)
    if not p.is_file():
        return []
    return [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]


def lire_toml(texte: str | None) -> dict:
    if not texte:
        return {}
    return tomllib.loads(texte)


def charger_toml(racine: Path, chemin: str, rev: str | None = None) -> dict:
    return lire_toml(outils.lire_a(racine, rev, chemin))


@dataclass
class Projet:
    racine: Path
    chemins: Chemins = FORMAT_ACTUEL
    lock: dict = field(default_factory=dict)
    politique: dict = field(default_factory=dict)
    garde_fous: dict = field(default_factory=dict)
    adaptateur: dict = field(default_factory=dict)
    erreurs_config: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def charger(cls, racine: Path | None = None, rev: str | None = None) -> "Projet":
        racine = outils.trouver_racine(racine)
        p = cls(racine=racine)
        for attr, chemin in (
            ("lock", p.chemins.lock),
            ("politique", p.chemins.politique),
            ("garde_fous", p.chemins.garde_fous),
            ("adaptateur", p.chemins.adaptateur),
        ):
            try:
                setattr(p, attr, charger_toml(racine, chemin, rev))
            except tomllib.TOMLDecodeError as e:
                p.erreurs_config.append((chemin, trad("TOML illisible : {erreur}", erreur=e)))
        return p

    @property
    def installe(self) -> bool:
        return bool(self.lock)

    @property
    def mode(self) -> str:
        return self.lock.get("mode", MODE_PROJET)

    @property
    def dossier_moteur(self) -> str:
        """Le répertoire qui contient le paquet `socle`."""
        return self.lock.get("engine_dir", self.chemins.moteur)

    # --- garde-fous -----------------------------------------------------

    def budget_octets(self, chemin: str) -> int | None:
        """Le plafond de taille, en octets, que les garde-fous donnent à ce
        chemin ; `None` sans plafond."""
        from socle import utils as outils

        for motif, b in (self.gf("budgets", defaut={}) or {}).items():
            if outils.correspond(chemin, [motif]) and "max_bytes" in b:
                return int(b["max_bytes"])
        return None

    def gf(self, *chemin, defaut=None):
        noeud = self.garde_fous
        for c in chemin:
            if not isinstance(noeud, dict) or c not in noeud:
                return defaut
            noeud = noeud[c]
        return noeud

    def pol(self, *chemin, defaut=None):
        noeud = self.politique
        for c in chemin:
            if not isinstance(noeud, dict) or c not in noeud:
                return defaut
            noeud = noeud[c]
        return noeud

    def chemins_code(self) -> list[str]:
        """Ce qui compte comme du code : l'adaptateur le déclare, les
        garde-fous peuvent l'étendre."""
        res = list(self.adaptateur.get("sources", []))
        res += list(self.gf("memory", "code", defaut=[]))
        return res

    def exclusions_docs(self) -> list[str]:
        """Ce qui n'est pas de la documentation du projet : les archives
        (gardées telles quelles) et le moteur (ses gabarits et son format)."""
        return [self.chemins.archives + "/**", self.dossier_moteur.rstrip("/") + "/**"] + list(
            self.gf("references", "exclude", defaut=[])
        )

    def chemins_tiers(self) -> list[str]:
        """Les fichiers d'un outil tiers installé dans le projet (ses skills,
        ses scripts) : aucun contrôle ne les juge. Un motif qui
        couvrirait un fichier du socle, de la mémoire ou de la politique est
        écarté, et signalé par `erreurs_tiers`."""
        motifs = self.gf("thirdparty", "paths", defaut=[]) or []
        return [m for m in motifs if isinstance(m, str) and not self._couvre_le_socle(m)]

    def erreurs_tiers(self) -> list[str]:
        """Les motifs de chemins tiers qui couvriraient un fichier que le
        socle garde : ils sont ignorés, et la configuration est en erreur."""
        motifs = self.gf("thirdparty", "paths", defaut=[]) or []
        return [m for m in motifs if not isinstance(m, str) or self._couvre_le_socle(m)]

    def _couvre_le_socle(self, motif: str) -> bool:
        ch = self.chemins
        gardes = [DOSSIER + "/x", ch.memoire + "/x", "AGENTS.md", "CLAUDE.md", ".claude/settings.json"]
        gardes += [re.sub(r"\*+", "x", m) for m in self.pol("protected", "paths", defaut=[]) or []]
        return any(outils.correspond(g, [motif]) for g in gardes)

    def hors_tiers(self, chemins):
        """Les chemins donnés, sans ceux d'un outil tiers."""
        tiers = self.chemins_tiers()
        return [c for c in chemins if not outils.correspond(c, tiers)] if tiers else list(chemins)

    def chemins_proteges(self) -> list[str]:
        res = list(self.pol("protected", "paths", defaut=[]))
        # La zone privée suit les règles de la zone publique : une réponse
        # humaine privée est protégée comme une réponse publique.
        ch = self.chemins
        res += [ch.dans_prive(m) for m in res if m.startswith(ch.memoire + "/") and not m.startswith(ch.prive + "/")]
        if self.mode == MODE_AMONT:
            # Dans le dépôt amont, le moteur EST la source : le protéger
            # empêcherait de le fabriquer.
            res = [m for m in res if not m.startswith(ch.moteur + "/")]
        return res

    def maximum_tentatives(self) -> int:
        return int(self.pol("max_attempts", defaut=3))
