"""Le contexte d'un passage de contrôles et le registre des contrôles.

Un contrôle est une fonction `(ctx, rapport)`. Il déclare les étages où il
tourne — `agent` (fin de tour), `git` (commit), `ci` — et s'il a besoin d'une
révision de base (les contrôles « ajout seul », le cliquet, la correspondance
code ↔ doc). Sans base, un tel contrôle le dit au lieu d'être sauté en silence.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from socle import config, requests as demandes, memory as memoire, utils as outils
from socle.messages import trad

ETAGES = ("agent", "git", "ci")


@dataclass
class Controle:
    id: str
    fonction: object
    etages: tuple[str, ...]
    base: bool
    lent: bool
    doc: str
    # Un contrôle qui lit l'adaptateur tourne une fois par adaptateur dans un
    # projet qui en a plusieurs, chaque fois avec ses seuls motifs (ADR-0051).
    par_adaptateur: bool = False


REGISTRE: dict[str, Controle] = {}


def resume(doc: str) -> str:
    """La première phrase d'une docstring, sur une ligne : ce que `socle
    checks` montre d'un contrôle, et la clé de sa traduction."""
    paragraphe = " ".join(l.strip() for l in (doc or "").strip().split("\n\n")[0].splitlines())
    m = re.match(r".+?[.!?](?=\s|$)", paragraphe)
    return m.group(0) if m else paragraphe


def controle(id_: str, etages=ETAGES, base=False, lent=False, par_adaptateur=False):
    def deco(f):
        REGISTRE[id_] = Controle(id_, f, tuple(etages), base, lent, (f.__doc__ or "").strip(), par_adaptateur)
        return f

    return deco


@dataclass
class Contexte:
    projet: config.Projet
    etage: str = "ci"
    base: str | None = None
    tete: str | None = None  # None : l'arbre de travail
    rapide: bool = False
    # Le message du commit en cours d'écriture (hook commit-msg) : il compte
    # comme le dernier commit de la plage, ses trailers avec lui.
    message: str | None = None
    # La plage qu'un push envoie, jugée comme la CI la jugera, depuis le hook
    # avant push : ce que l'étage git laisse passer y passe aussi (D-0071).
    avant_push: bool = False
    _cache: dict = field(default_factory=dict)

    @property
    def racine(self) -> Path:
        return self.projet.racine

    def pour(self, a: config.Adaptateur) -> "Contexte":
        """Le même passage, vu par un seul adaptateur : les fichiers, les
        lectures et l'historique se partagent, seul l'adaptateur change."""
        vue = copy.copy(self)
        vue.projet = self.projet.pour(a)
        return vue

    # Les fichiers d'un outil tiers sont hors de ces listes :
    # aucun contrôle ne les voit, ni à la tête ni à la base.

    @cached_property
    def fichiers(self) -> list[str]:
        if self.tete is None:
            # Le clone du dépôt privé (mode compagnon) est ignoré par git,
            # mais c'est de la mémoire : les contrôles la lisent.
            tous = set(outils.fichiers_courants(self.racine)) | set(memoire.fichiers_compagnon(self.racine))
            return self.projet.hors_tiers(sorted(tous))
        return self.projet.hors_tiers(outils.fichiers_a(self.racine, self.tete))

    @cached_property
    def fichiers_base(self) -> list[str]:
        res = outils.fichiers_a(self.racine, self.base) if self.base else []
        return self.projet.hors_tiers(res)

    def lire(self, chemin: str) -> str | None:
        """Le texte d'un fichier de la tête ; un fichier privé chiffré ici
        n'a pas de texte lisible, les contrôles le prennent pour absent."""
        cle = ("t", chemin)
        if cle not in self._cache:
            texte = outils.lire_a(self.racine, self.tete, chemin)
            if memoire.est_prive(chemin) and not memoire.lisible(texte):
                texte = None
            self._cache[cle] = texte
        return self._cache[cle]

    def lire_base(self, chemin: str) -> str | None:
        if not self.base:
            return None
        cle = ("b", chemin)
        if cle not in self._cache:
            self._cache[cle] = outils.lire_a(self.racine, self.base, chemin)
        return self._cache[cle]

    @cached_property
    def memoire(self) -> memoire.Memoire:
        return memoire.Memoire.charger(self.racine, self.tete)

    @cached_property
    def memoire_base(self) -> memoire.Memoire | None:
        if not self.base:
            return None
        return memoire.Memoire.charger(self.racine, self.base)

    @cached_property
    def demandes(self) -> list[demandes.Demande]:
        return demandes.toutes(self.racine, self.tete)

    @cached_property
    def changes(self) -> list[str]:
        """Ce qui a changé depuis la base (arbre de travail compris si
        `tete` est None)."""
        if not self.base:
            return list(self.fichiers)
        return self.projet.hors_tiers(outils.fichiers_changes(self.racine, self.base, self.tete))

    @cached_property
    def renommes(self) -> dict[str, str]:
        """Les fichiers que la plage renomme, de leur nom à la base à leur nom
        à la tête, tels que git les reconnaît."""
        if not self.base:
            return {}
        tiers = self.projet.chemins_tiers()
        return {a: b for a, b in outils.renommes(self.racine, self.base, self.tete).items()
                if not outils.correspond(b, tiers)}

    @cached_property
    def rev_commit(self) -> str:
        """Le commit de la tête. La tête peut être un arbre (l'index, au hook
        pre-commit) : son historique est alors celui de HEAD."""
        if self.tete and outils.rev_existe(self.racine, self.tete):
            return self.tete
        return "HEAD"

    @cached_property
    def commits(self) -> list[dict]:
        res = outils.commits(self.racine, self.base, self.rev_commit) if outils.a_des_commits(self.racine) else []
        if self.message is not None:
            res.append({"sha": "en-cours", "parents": [], "message": self.message})
        return res

    @cached_property
    def validations(self) -> list[demandes.Demande]:
        return demandes.validations_ajoutees(self.racine, self.base, self.tete)

    @cached_property
    def projet_base(self) -> config.Projet | None:
        if not self.base:
            return None
        return config.Projet.charger(self.racine, self.base)

    def textes(self, motifs, exclus=()) -> dict[str, str]:
        res = {}
        for c in outils.filtrer(self.fichiers, motifs, exclus):
            t = self.lire(c)
            if t is not None and "\0" not in t[:4096]:
                res[c] = t
        return res

    def documents(self) -> dict[str, str]:
        """Les documents markdown du projet, hors archives et exclusions."""
        return self.textes(["**/*.md"], self.projet.exclusions_docs())


def selectionner(etage: str, ids: list[str] | None = None, rapide: bool = False) -> list[Controle]:
    res = []
    for c in REGISTRE.values():
        if ids and c.id not in ids:
            continue
        if not ids and etage not in c.etages:
            continue
        if rapide and c.lent and not ids:
            continue
        res.append(c)
    return res


def charger_controles() -> dict[str, Controle]:
    """Tous les contrôles : leurs modules s'enregistrent à l'import. Une
    seule liste, pour que `socle checks` et l'exécution voient les mêmes."""
    from socle import (checks_ratchet as controles_cliquet,  # noqa: F401
                       checks_docs as controles_docs, checks_memory as controles_memoire,
                       checks_skills as controles_skills, checks_tests as controles_tests, private as prive)

    return REGISTRE


def _lancer(c: Controle, ctx: Contexte, rapport):
    try:
        c.fonction(ctx, rapport)
    except Exception as e:  # un contrôle en panne échoue, il ne se tait pas
        rapport.erreur(c.id, trad("le contrôle a planté : {erreur}", erreur=f"{type(e).__name__}: {e}"))


def _par_adaptateur(c: Controle, ctx: Contexte, rapport):
    """Le contrôle, une fois par adaptateur. Un constat que chacun rend à
    l'identique se dit une fois : sans nom s'il porte sur un fichier
    qu'aucun adaptateur ne désigne (un fichier de cas, les garde-fous), avec
    le nom de tous sinon (deux correctifs refusés de même dans deux
    langages). Les autres nomment leur adaptateur."""
    from socle.report import Rapport

    tous = ctx.projet.adaptateurs
    passages = []
    for a in tous:
        r = Rapport()
        _lancer(c, ctx.pour(a), r)
        passages.append((a, r.constats))

    def cle(k):
        return k.gravite, k.message, k.chemin, k.ligne

    communs = set.intersection(*({cle(k) for k in constats} for _, constats in passages))
    vus = set()
    for a, constats in passages:
        for k in constats:
            if cle(k) in communs:
                if cle(k) in vus:
                    continue
                vus.add(cle(k))
                if k.chemin and not any(ctx.projet.designes(x, [k.chemin]) for x in tous):
                    rapport.constats.append(k)
                    continue
                noms = ", ".join(x.nom for x in tous)
            else:
                noms = a.nom
            k.message = trad("{adaptateur} : {message}", adaptateur=noms, message=k.message)
            rapport.constats.append(k)


def executer(ctx: Contexte, ids: list[str] | None = None):
    from socle.report import Rapport  # import local : pas de cycle
    from socle.report import AVERTISSEMENT, ERREUR

    charger_controles()

    rapport = Rapport()
    for chemin, erreur in ctx.projet.erreurs_config:
        rapport.erreur("config", erreur, chemin)
    for motif in ctx.projet.erreurs_tiers():
        rapport.erreur("config", trad("chemin tiers « {motif} » ignoré : il couvrirait un fichier du socle, de la "
                                      "mémoire ou de la politique, que les contrôles doivent juger", motif=motif),
                       ctx.projet.chemins.garde_fous)
    # Mode adoption : sur un projet existant, ces contrôles avertissent au lieu
    # d'échouer, le temps de résorber l'existant. Retirer un contrôle de la
    # liste durcit (libre) ; en ajouter un assouplit (cliquet).
    adoption = set(ctx.projet.gf("adoption", "warn_only", defaut=[]) or [])
    for c in selectionner(ctx.etage, ids, ctx.rapide):
        rapport.execute(c.id)
        if c.base and not ctx.base:
            rapport.indisponible(c.id, trad("aucune révision de base : contrôle non exécuté"))
            continue
        debut = len(rapport.constats)
        if c.par_adaptateur and ctx.projet.plusieurs_adaptateurs:
            _par_adaptateur(c, ctx, rapport)
        else:
            _lancer(c, ctx, rapport)
        if c.id in adoption:
            for constat in rapport.constats[debut:]:
                if constat.gravite == ERREUR:
                    constat.gravite = AVERTISSEMENT
                    constat.message = "(adoption) " + constat.message
    # En CI, le journal d'un dépôt public est public : un constat de la zone
    # privée n'y montre ni son texte ni son chemin, seulement qu'il existe.
    if ctx.etage == "ci" and ctx.projet.pol("private", "mode"):
        for constat in rapport.constats:
            if constat.chemin and memoire.est_prive(constat.chemin):
                constat.message = trad("constat masqué : zone privée (relancer les contrôles là où elle se lit)")
                constat.chemin, constat.ligne = ctx.projet.chemins.prive + "/…", None
    return rapport
