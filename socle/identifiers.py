"""Les identifiants que deux branches prennent ensemble.

`socle new` calcule un identifiant sur l'arbre de sa branche, qui ne voit
pas les autres : deux branches parties du même commit prennent le même.
Trois gestes : voir les identifiants que les branches distantes
ont déjà pris, refuser avant la fusion un identifiant que la branche par
défaut a pris aussi depuis que la branche s'en est séparée, et le
renuméroter.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from socle import config, links as liens, memory as memoire, utils as outils
from socle.messages import trad


def pris_ailleurs(racine: Path, type_: str) -> set[str]:
    """Les identifiants de ce type que définissent les branches distantes
    que le dépôt connaît, lus par `git grep` sur leurs titres, sans charger
    leur mémoire, et ceux que créent les correctifs suivis du dépôt."""
    refs = [r for r in outils.git(racine, "for-each-ref", "--format=%(refname)", "refs/remotes", check=False).split()
            if not r.endswith("/HEAD")]
    motif = rf"^#{{1,6}} P?{re.escape(type_)}-[0-9A-Z-]+ "
    res = set()
    for ref in refs:
        sortie = outils.git(racine, "grep", "-h", "-o", "-E", motif, ref, "--", memoire.DOSSIER, check=False)
        res |= {l.split()[1] for l in sortie.splitlines() if len(l.split()) > 1}
    return res | pris_par_les_correctifs(racine, type_)


CIBLE_DU_CORRECTIF = re.compile(r"^\+\+\+ b/(\S+)")


def pris_par_les_correctifs(racine: Path, type_: str) -> set[str]:
    """Les identifiants de ce type que créent les correctifs suivis du dépôt
    (`*.patch`, `*.diff`) : les titres d'entrée qu'ils ajoutent à un fichier
    de la mémoire. Une passation range en correctifs les commits pas encore
    relus ; une entrée écrite avant leur application prendrait leurs
    numéros (B-0280)."""
    titre = re.compile(rf"^\+#{{1,6}}\s+(P?{re.escape(type_)}-[0-9A-Z-]+)\s")
    res = set()
    for chemin in outils.filtrer(outils.fichiers_suivis(racine) or [], ["**/*.patch", "**/*.diff"]):
        try:
            texte = (racine / chemin).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cible = ""
        for ligne in texte.splitlines():
            m = CIBLE_DU_CORRECTIF.match(ligne)
            if m:
                cible = m.group(1)
            elif cible.startswith(memoire.DOSSIER + "/") and (t := titre.match(ligne)):
                res.add(t.group(1))
    return res


def _nouveaux(avant: memoire.Memoire | None, apres: memoire.Memoire) -> dict[str, memoire.Entree]:
    """Les entrées définies dans `apres` et pas dans `avant`."""
    connus = set(avant.definitions()) if avant is not None else set()
    return {i: d[0] for i, d in apres.definitions().items() if i not in connus}


def collisions(racine: Path, tete: str | None, ici: memoire.Memoire,
               bases: list[str]) -> list[tuple[str, memoire.Entree, memoire.Entree]]:
    """[(identifiant, entrée de la branche, entrée de la base)] : ce que la
    branche définit et qu'une base définit aussi, pour une autre entrée,
    depuis leur point de divergence. Une base dont la branche descend n'a
    rien ajouté de son côté : rien à comparer."""
    res, vus = [], set()
    for base in bases:
        if not base or not outils.rev_existe(racine, base):
            continue
        sha = outils.resoudre(racine, base)
        point = outils.git(racine, "merge-base", tete or "HEAD", sha, check=False).strip()
        if not point or point == sha or sha in vus:
            continue
        vus.add(sha)
        avant = memoire.Memoire.charger(racine, point)
        la_bas = _nouveaux(avant, memoire.Memoire.charger(racine, sha))
        for ident, e in sorted(_nouveaux(avant, ici).items()):
            autre = la_bas.get(ident)
            if autre is not None and autre.texte != e.texte and ident not in {c[0] for c in res}:
                res.append((ident, e, autre))
    return res


def bases_a_comparer(racine: Path, base: str | None) -> list[str]:
    """La base de la vérification, et la tête de la branche par défaut : à la
    fin du tour et au commit, la base est le point de divergence lui-même,
    qui ne voit rien de ce que la branche par défaut a reçu depuis."""
    return [b for b in (base, outils.branche_par_defaut(racine)) if b]


def _a_renumeroter(racine: Path, ident: str, definitions: list[memoire.Entree],
                   base: str | None) -> tuple[memoire.Entree, str | None]:
    """L'entrée que la branche ajoute, et la version où l'autre existait
    déjà sans elle. Seule, l'entrée est à la branche si la base ne la
    définit pas. Deux entrées du même identifiant, nées d'un rebase ou d'un
    cherry-pick (B-0176) : celle qu'ajoute la branche depuis la base, ou
    depuis son dernier commit poussé, l'autre y étant déjà. La base
    d'abord : une branche poussée qui a fusionné la branche par défaut a
    deux commits poussés parmi ses ancêtres, et le sien porte l'entrée de
    la branche, pas celle que la fusion a apportée."""
    if len(definitions) == 1:
        if base and ident in memoire.Memoire.charger(racine, base).definitions():
            raise ValueError(trad("`{ident}` existait avant la branche : ce n'est pas à elle de le renuméroter",
                                  ident=ident))
        return definitions[0], base
    pousse = liens.commit_pousse(racine)
    versions = [v for v in dict.fromkeys((base, pousse)) if v]
    for version in versions:
        deja = {d.texte for d in memoire.Memoire.charger(racine, version).definitions().get(ident, [])}
        nouvelles = [d for d in definitions if d.texte not in deja]
        if deja and len(nouvelles) == 1:
            return nouvelles[0], version
    raise ValueError(trad("`{ident}` est défini {n} fois, et aucune version poussée ne dit laquelle la branche "
                          "ajoute : renuméroter à la main", ident=ident, n=len(definitions)))


def _remplacer_dans_l_ajoute(avant: str | None, apres: str, remplacer) -> str:
    """`apres`, où `remplacer` ne s'applique qu'aux lignes absentes de
    `avant` : celles que la branche a ajoutées ou changées. Une ligne
    qu'elle garde, l'entrée de l'autre et ses mentions, reste telle quelle."""
    if avant is None:
        return remplacer(apres)
    lignes_avant = avant.splitlines(keepends=True)
    lignes = apres.splitlines(keepends=True)
    res = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, lignes_avant, lignes, autojunk=False).get_opcodes():
        bloc = "".join(lignes[j1:j2])
        res.append(bloc if tag == "equal" else remplacer(bloc))
    return "".join(res)


def renumeroter(projet: config.Projet, ident: str) -> list[str]:
    """Donne à une entrée de la branche le prochain identifiant libre — dans
    la branche, la branche par défaut et les branches distantes —, le reporte
    dans les lignes que la branche a ajoutées à chaque fichier changé,
    renomme le fichier qui porte l'entrée seule, et récrit les citations de
    son empreinte. Rend ce qui a été fait."""
    racine = projet.racine
    mem = memoire.Memoire.charger(racine)
    definitions = mem.definitions().get(ident, [])
    if not definitions:
        raise ValueError(trad("`{ident}` ne désigne aucune entrée de la mémoire", ident=ident))
    base = outils.base_de_travail(racine)
    e, depuis = _a_renumeroter(racine, ident, definitions, base)
    if e.type == "D" and any(c.endswith(memoire.SUFFIXE_REPONSE) and c.startswith(e.fichier.removesuffix(".md"))
                             for c in outils.fichiers_courants(racine)):
        raise ValueError(trad("`{ident}` a reçu sa réponse : une demande répondue est gelée", ident=ident))
    pris = set(mem.definitions()) | set(mem.anciens()) | pris_ailleurs(racine, e.type)
    defaut = outils.branche_par_defaut(racine)
    if defaut:
        pris |= set(memoire.Memoire.charger(racine, outils.resoudre(racine, defaut)).definitions())
    nouvel = memoire.prochain_libre(e.type, pris, prive=e.prive, date=e.id.lstrip("P")[2:12] if e.type == "J" else None)

    res = []
    fichier = e.fichier
    if memoire.dossier_propre(fichier):
        dossier, nom = fichier.rsplit("/", 1)
        neuf = f"{dossier}/{nouvel}{nom[len(ident):]}"
        if outils.git_reussit(racine, "ls-files", "--error-unmatch", fichier):
            outils.git(racine, "mv", fichier, neuf)
        else:
            (racine / fichier).rename(racine / neuf)
        res.append(f"{fichier} → {neuf}")
        fichier = neuf
    # La citation de l'empreinte attend la nouvelle empreinte, que l'entrée
    # n'a qu'une fois renumérotée.
    marque = "\0RENUMEROTE\0"
    seul = re.compile(rf"(?<![\w-]){re.escape(ident)}(?![\w-])")
    cite = re.compile(rf"(?<![\w-]){re.escape(ident)}@[0-9a-f]{{8}}(?![\w-])")
    touches = []
    for chemin in sorted(set(outils.fichiers_changes(racine, depuis)) | {fichier}):
        p = racine / chemin
        if not p.is_file() or not outils.est_texte(p):
            continue
        avant = p.read_text(encoding="utf-8")
        apres = _remplacer_dans_l_ajoute(outils.lire_a(racine, depuis, chemin) if depuis else None, avant,
                                         lambda s: seul.sub(nouvel, cite.sub(marque, s)))
        if apres != avant:
            p.write_text(apres, encoding="utf-8")
            touches.append(chemin)
    renumerote = memoire.Memoire.charger(racine).entree(nouvel)
    empreinte = memoire.empreinte_entree(renumerote) if renumerote else ""
    for chemin in touches:
        p = racine / chemin
        p.write_text(p.read_text(encoding="utf-8").replace(marque, f"{nouvel}@{empreinte}"), encoding="utf-8")
    res.insert(0, f"{ident} → {nouvel}")
    res.append(trad("reporté dans {n} fichier(s) : {liste}", n=len(touches), liste=', '.join(touches)))
    return res
