"""Archivage : `socle archive` range les entrées closes du backlog, de
toutes formes, à l'écart des ouvertes, et les consignes levées de l'humain
dans le journal, comme les faits archivés."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from socle import config, language as langue, memory as memoire, utils as outils
from socle.messages import trad


def archiver_backlog(projet: config.Projet) -> int:
    deplaces = ranger_backlog(projet.racine)
    for avant, apres in deplaces:
        print(f"{avant} → {apres}")
    print(trad("{n} entrée(s) rangée(s) : les closes dans `{dossier}/`, les ouvertes hors de lui",
               n=len(deplaces), dossier=memoire.DOSSIER_CLOS) if deplaces else trad("le backlog est déjà rangé"))
    rangees = ranger_consignes(projet, date.today().isoformat())
    for ident, journal in rangees:
        print(f"{ident} → {journal}")
    if rangees:
        print(trad("{n} consigne(s) levée(s) rangée(s) dans le journal : leur identifiant reste résolu",
                   n=len(rangees)))
    return 0


def ranger_consignes(projet: config.Projet, jour: str) -> list[tuple[str, str]]:
    """Range chaque consigne levée dans le journal, sous une entrée du jour
    qui le dit, comme un fait archivé : elle garde son identifiant, sa ligne
    de métadonnées et son texte exact, ses titres un niveau plus bas. Dans la
    zone publique, puis dans la privée quand elle se lit ici. Rend les
    consignes rangées, (identifiant, fichier du journal)."""
    from socle import identifiers as identifiants

    racine, ch = projet.racine, projet.chemins
    lg = langue.du_projet(projet)
    res = []
    for prive in (False, True):
        chemin = ch.dans_prive(ch.consignes) if prive else ch.consignes
        mem = memoire.Memoire.charger(racine)
        f = mem.fichiers.get(chemin)
        levees = [e for e in (f.entrees if f else []) if e.type == "C" and not e.archivee and e.statut == "levee"]
        if not levees:
            continue
        ident = mem.prochain_id("J", prive=prive, date=jour, pris_ailleurs=identifiants.pris_ailleurs(racine, "J"))
        bloc = (f"\n## {ident} — {langue.mot(langue.TEXTES, 'titre-consignes-rangees', lg)}\n\n"
                f"{langue.mot(langue.TEXTES, 'texte-consignes-rangees', lg)}\n\n"
                + "\n\n".join(re.sub(r"(?m)^(#{1,5})(?=\s)", r"\1#", e.texte) for e in levees) + "\n")
        journal = ch.dans_prive(ch.journal) if prive else ch.journal
        cible = memoire.fichier_journal(racine / journal, jour[:7], projet.budget_octets(f"{ch.journal}/{jour[:7]}.md"),
                                        len(bloc.encode("utf-8")))
        if not cible.is_file():
            outils.ecrire(cible, f"{langue.entete_fichier('journal', 'privee' if prive else 'publique', lg)}\n"
                                 f"# {langue.mot(langue.TEXTES, 'titre-journal', lg)} — {jour[:7]}\n")
        texte = cible.read_text(encoding="utf-8")
        cible.write_text(texte.rstrip("\n") + "\n" + bloc, encoding="utf-8")
        # Chaque consigne rangée quitte son fichier, avec les lignes vides
        # qui la suivent : le texte des autres ne change pas.
        texte = (racine / chemin).read_text(encoding="utf-8")
        for e in levees:
            debut = texte.find(e.texte)
            if debut < 0:
                continue
            fin = debut + len(e.texte)
            while fin < len(texte) and texte[fin] == "\n":
                fin += 1
            texte = texte[:debut] + texte[fin:]
        (racine / chemin).write_text(texte.rstrip("\n") + "\n", encoding="utf-8")
        relatif = str(cible.relative_to(racine)).replace("\\", "/")
        res += [(e.id, relatif) for e in levees]
    return res


def ranger_backlog(racine: Path) -> list[tuple[str, str]]:
    """Range chaque entrée du backlog selon son statut : une entrée
    close dans le sous-dossier des clos, une ouverte hors de lui, dans la
    zone publique comme dans la privée. Un déplacement suivi par
    le dépôt est indexé ; dans le dépôt compagnon, il reste à y commiter.
    Rend les déplacements, (avant, après) ; idempotent."""
    suivis = set(outils.git(racine, "ls-files", "-z", check=False).split("\0")) - {""} \
        if outils.est_depot(racine) else set()
    res = []
    for e in memoire.Memoire.charger(racine).entrees(memoire.BACKLOG):
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

