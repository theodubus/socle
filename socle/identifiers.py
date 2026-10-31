"""Les identifiants que deux branches prennent ensemble.

`socle new` calcule un identifiant sur l'arbre de sa branche, qui ne voit
pas les autres : deux branches parties du même commit prennent le même.
Trois gestes : voir les identifiants que les branches distantes
ont déjà pris, refuser avant la fusion un identifiant que la branche par
défaut a pris aussi depuis que la branche s'en est séparée, et le
renuméroter.
"""

from __future__ import annotations

import re
from pathlib import Path

from socle import config, memory as memoire, utils as outils
from socle.messages import trad


def pris_ailleurs(racine: Path, type_: str) -> set[str]:
    """Les identifiants de ce type que définissent les branches distantes
    que le dépôt connaît, lus par `git grep` sur leurs titres, sans charger
    leur mémoire."""
    refs = [r for r in outils.git(racine, "for-each-ref", "--format=%(refname)", "refs/remotes", check=False).split()
            if not r.endswith("/HEAD")]
    motif = rf"^#{{1,6}} P?{re.escape(type_)}-[0-9A-Z-]+ "
    res = set()
    for ref in refs:
        sortie = outils.git(racine, "grep", "-h", "-o", "-E", motif, ref, "--", memoire.DOSSIER, check=False)
        res |= {l.split()[1] for l in sortie.splitlines() if len(l.split()) > 1}
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


def renumeroter(projet: config.Projet, ident: str) -> list[str]:
    """Donne à une entrée de la branche le prochain identifiant libre — dans
    la branche, la branche par défaut et les branches distantes —, le reporte
    dans chaque fichier que la branche a changé, renomme le fichier qui
    porte l'entrée seule, et récrit les citations de son empreinte. Rend ce
    qui a été fait."""
    racine = projet.racine
    mem = memoire.Memoire.charger(racine)
    e = mem.entree(ident)
    if e is None:
        raise ValueError(trad("`{ident}` ne désigne aucune entrée de la mémoire", ident=ident))
    base = outils.base_de_travail(racine)
    if base and ident in memoire.Memoire.charger(racine, base).definitions():
        raise ValueError(trad("`{ident}` existait avant la branche : ce n'est pas à elle de le renuméroter",
                              ident=ident))
    if e.type == "D" and any(c.endswith(memoire.SUFFIXE_REPONSE) and c.startswith(e.fichier.removesuffix(".md"))
                             for c in outils.fichiers_courants(racine)):
        raise ValueError(trad("`{ident}` a reçu sa réponse : une demande répondue est gelée", ident=ident))
    pris = set(mem.definitions()) | pris_ailleurs(racine, e.type)
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
    for chemin in sorted(set(outils.fichiers_changes(racine, base)) | {fichier}):
        p = racine / chemin
        if not p.is_file() or not outils.est_texte(p):
            continue
        avant = p.read_text(encoding="utf-8")
        apres = seul.sub(nouvel, cite.sub(marque, avant))
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
