"""La lecture prouvée, en une seule fonction que partagent le
contrôle `memoire.lectures` et le hook de l'agent.

Une citation `ID@empreinte` vaut pour la version actuelle de l'entrée, ou
pour celle du commit de la plage où la citation paraît pour la première
fois : une demande répondue est gelée et ne peut plus suivre l'entrée
qu'elle cite. Une citation d'index (`backlog@…`, `decisions@…`) vaut pour
toute version de l'index dans la plage, sans l'entrée qui cite ni celles du
même type ajoutées après elle : l'index lu au début du travail reste lu,
et le verdict ne dépend plus de la base choisie, sinon pour s'élargir avec
elle. Une citation déjà présente à la base dans la même
entrée (ou dans celle dont elle vient) ne se rejuge pas ; hors de toute
entrée, dans le même fichier.
"""

from __future__ import annotations

from pathlib import Path

from socle import memory as memoire, utils as outils


class Plage:
    """Les versions de la mémoire qu'une citation a pu lire : la base, chaque
    commit de la plage, dans l'ordre, et l'arbre. Les commits se chargent au
    besoin seulement."""

    def __init__(self, racine: Path, base: memoire.Memoire | None, courante: memoire.Memoire,
                 commits: list[str]):
        self.racine, self.base, self.courante, self.commits = racine, base, courante, commits
        self._charges: dict[str, memoire.Memoire] = {}
        self._rang = {sha: k for k, sha in enumerate(commits)}
        self._changeants: dict[str, list[str]] = {}

    def _log(self, *args: str) -> list[str]:
        """Les commits de la plage que `git log` retient, dans l'ordre."""
        if not self.commits:
            return []
        sortie = outils.git(self.racine, "log", "--format=%H", "--reverse", *args, self.commits[-1],
                            "--not", f"{self.commits[0]}^", check=False) if \
            outils.git_reussit(self.racine, "rev-parse", "--verify", "--quiet", f"{self.commits[0]}^") else \
            outils.git(self.racine, "log", "--format=%H", "--reverse", *args, self.commits[-1], check=False)
        return [sha for sha in sortie.split() if sha in self._rang]

    def a(self, sha: str) -> memoire.Memoire:
        if sha not in self._charges:
            self._charges[sha] = memoire.Memoire.charger(self.racine, sha)
        return self._charges[sha]

    def parution(self, chemin: str, citation: str, soi: memoire.Entree | None) -> int | None:
        """Le rang du commit où la citation paraît pour la première fois :
        dans ce fichier, ou dans l'entrée qui la porte, où qu'elle soit alors
        (un sujet créé puis rangé avec les clos sur la même branche)."""
        # `git log -S` trouve les commits où le nombre d'occurrences change,
        # sans charger la mémoire de chacun. Un déplacement renomme le
        # fichier sans suivre son histoire : l'entrée qui porte la citation,
        # cherchée partout, donne la parution la plus ancienne.
        rangs = []
        for sha in self._log(f"-S{citation}", "--", chemin):
            texte = outils.lire_a(self.racine, sha, chemin)
            if texte and citation in texte:
                rangs.append(self._rang[sha])
                break
        if soi is not None:
            for sha in self._log(f"-S{citation}"):
                if rangs and self._rang[sha] >= rangs[0]:
                    break
                porteuse = self.a(sha).entree(soi.id)
                if porteuse is not None and citation in porteuse.texte:
                    rangs.append(self._rang[sha])
                    break
        return min(rangs) if rangs else None

    def changeant(self, type_: str) -> list[str]:
        """Les commits de la plage qui touchent un fichier où vivent des
        entrées de ce type : l'index ne change qu'avec eux."""
        if type_ not in self._changeants:
            self._changeants[type_] = self._changeant(type_)
        return self._changeants[type_]

    def _changeant(self, type_: str) -> list[str]:
        # Les décisions et les sujets du backlog vivent un par fichier : leur
        # dossier entier, pour ceux ajoutés en route.
        lieux = sorted({memoire.dossier_propre(c) or c for m in (self.courante, self.base) if m is not None
                        for c, f in m.fichiers.items() if any(e.type == type_ for e in f.entrees)})
        if not lieux:
            return []
        return self._log("--", *lieux)


def entree_englobante(mem: memoire.Memoire, chemin: str, ligne: int) -> memoire.Entree | None:
    """L'entrée qui porte la ligne : la plus profonde de celles qui l'englobent."""
    f = mem.fichiers.get(chemin)
    if f is None:
        return None
    dedans = [e for e in f.entrees if e.ligne <= ligne <= e.ligne + e.texte.count("\n")]
    return max(dedans, key=lambda e: e.ligne) if dedans else None


def deja_citee(soi: memoire.Entree | None, citation: str, avant: memoire.Memoire | None, texte_avant: str) -> bool:
    """La citation était là avant, dans la même entrée ou dans celle dont
    elle vient (une entrée basculée en privé, un sujet archivé) ; hors de
    toute entrée, dans le même fichier. Recopiée d'une autre entrée du
    fichier, elle se juge."""
    if soi is None:
        return citation in texte_avant
    if avant is None:
        return False
    defs = avant.definitions()
    return any(ident in defs and citation in defs[ident][0].texte for ident in (soi.id, *soi.depuis))


def entree_lue(plage: Plage, chemin: str, soi: memoire.Entree | None, ident: str, h: str) -> bool:
    """`ident@h` désigne la version actuelle de l'entrée, ou celle du commit
    où la citation paraît."""
    e = plage.courante.entree(ident)
    if e is not None and memoire.empreinte_entree(e) == h:
        return True
    k = plage.parution(chemin, f"{ident}@{h}", soi)
    if k is None:
        return False
    e = plage.a(plage.commits[k]).entree(ident)
    return e is not None and memoire.empreinte_entree(e) == h


def _empreintes(m: memoire.Memoire, index: str, soi: memoire.Entree | None) -> set[str]:
    """L'index d'une version tel qu'affiché, sans l'entrée qui cite, et sans
    les entrées du même type ajoutées après elle : elle ne pouvait pas les
    lire, et elles ne périment pas sa lecture."""
    if soi is None:
        return {memoire.empreinte_index(m, index)}
    sauf = {soi.id}
    apres = {n for n, d in m.definitions().items() if d[0].type == soi.type and n > soi.id}
    return {memoire.empreinte_index(m, index, s) for s in (set(), sauf, apres, sauf | apres)}


def index_lu(plage: Plage, chemin: str, soi: memoire.Entree | None, index: str, h: str) -> bool:
    """`index@h` désigne une version de l'index dans la plage : la base, un
    commit de la plage ou l'arbre. Une lecture de l'index prouve qu'il a
    été consulté, pas une version de son contenu : celle d'un commit
    postérieur à la citation, relue en route, vaut aussi."""
    for m in (plage.courante, plage.base):
        if m is not None and h in _empreintes(m, index, soi):
            return True
    # Du plus récent au plus ancien : la version lue est le plus souvent la
    # dernière.
    return any(h in _empreintes(plage.a(sha), index, soi)
               for sha in reversed(plage.changeant(memoire.INDEX_TYPES[index])))
