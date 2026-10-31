"""Archivage : `socle archive` range les sujets clos du backlog à l'écart
des ouverts."""

from __future__ import annotations

from pathlib import Path

from socle import config, memory as memoire, utils as outils
from socle.messages import trad


def archiver_backlog(projet: config.Projet) -> int:
    deplaces = ranger_backlog(projet.racine)
    for avant, apres in deplaces:
        print(f"{avant} → {apres}")
    print(trad("{n} sujet(s) rangé(s) : les clos dans `{dossier}/`, les ouverts hors de lui",
               n=len(deplaces), dossier=memoire.DOSSIER_CLOS) if deplaces else trad("le backlog est déjà rangé"))
    return 0


def ranger_backlog(racine: Path) -> list[tuple[str, str]]:
    """Range chaque sujet du backlog selon son statut : un sujet
    clos dans le sous-dossier des clos, un sujet ouvert hors de lui, dans la
    zone publique comme dans la privée. Un déplacement suivi par
    le dépôt est indexé ; dans le dépôt compagnon, il reste à y commiter.
    Rend les déplacements, (avant, après) ; idempotent."""
    suivis = set(outils.git(racine, "ls-files", "-z", check=False).split("\0")) - {""} \
        if outils.est_depot(racine) else set()
    res = []
    for e in memoire.Memoire.charger(racine).entrees("B"):
        if e.basculee or memoire.couche_attendue(e.fichier) != "backlog":
            continue
        clos = e.statut in memoire.BACKLOG_CLOS
        if clos == memoire.parmi_les_clos(e.fichier):
            continue
        dossier, nom = e.fichier.rsplit("/", 1)
        cible = f"{dossier}/{memoire.DOSSIER_CLOS}/{nom}" if clos else memoire.hors_des_clos(e.fichier)
        (racine / cible).parent.mkdir(parents=True, exist_ok=True)
        (racine / e.fichier).rename(racine / cible)
        if e.fichier in suivis:
            outils.git(racine, "add", "-A", "--", e.fichier, cible)
        res.append((e.fichier, cible))
    return res

