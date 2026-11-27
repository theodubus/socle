"""Archivage : `socle archive` range les entrées closes du backlog, de
toutes formes, à l'écart des ouvertes, et les consignes levées de l'humain
dans le journal, comme les faits archivés ; `socle close` clôt une entrée
du backlog en un geste, son statut, sa référence et son rangement
(ADR-0117)."""

from __future__ import annotations

import re
import sys
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


def ranger_backlog(racine: Path, indexer: bool = True) -> list[tuple[str, str]]:
    """Range chaque entrée du backlog selon son statut : une entrée
    close dans le sous-dossier des clos, une ouverte hors de lui, dans la
    zone publique comme dans la privée. Un déplacement suivi par
    le dépôt est indexé, sauf `indexer` faux, à la mise à jour, dont la
    demande seule se commite avant ses fichiers (T-0200) ; dans le dépôt
    compagnon, il reste à y commiter. Rend les déplacements, (avant,
    après) ; idempotent."""
    suivis = set(outils.git(racine, "ls-files", "-z", check=False).split("\0")) - {""} \
        if indexer and outils.est_depot(racine) else set()
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



class ClotureRefusee(Exception):
    """`socle close` refuse : sa raison, ou les messages des contrôles."""


# Les contrôles qui jugent une entrée close : ses critères et sa référence,
# les tâches d'un besoin, ce qu'elle attend, et, pour un jalon, la réserve
# triée (ADR-0118), que le contexte juge contre sa base. La commande ne
# copie pas leurs règles : elle les fait juger l'entrée écrite close.
CONTROLES_DE_CLOTURE = ["memoire.backlog", "memoire.formes", "memoire.ordre", "memoire.reserve"]


def cloturer(projet: config.Projet, ident: str, ref: str | None = None) -> int:
    try:
        avant, apres, ajoutee = clore(projet, ident, ref)
    except ClotureRefusee as refus:
        print(trad("refus : {raison}", raison=refus), file=sys.stderr)
        return 1
    print(trad("`{id}` clos « fait », ref : {ref}", id=ident, ref=ajoutee))
    if avant != apres:
        print(f"{avant} → {apres}")
    print(trad("Ensuite : le commiter avec le travail qui le fait"))
    return 0


def clore(projet: config.Projet, ident: str, ref: str | None = None) -> tuple[str, str, str]:
    """Clôt « fait » l'entrée ouverte `ident` du backlog en un geste
    (ADR-0117) : son statut, la référence ajoutée à son champ `ref` (`ce
    commit` par défaut, dans la langue du projet) et son rangement parmi
    les closes, indexé si le fichier est suivi. Ne coche rien. Refuse, par
    `ClotureRefusee`, une entrée inconnue, hors du backlog, close ou
    basculée, et celle que les contrôles du backlog refuseraient close :
    son fichier revient alors comme avant. Rend (fichier d'avant, fichier
    d'après, référence ajoutée)."""
    from socle import context as contexte, migration

    racine = projet.racine
    e = memoire.Memoire.charger(racine).resoudre(ident)
    if e is None:
        raise ClotureRefusee(trad("{ident} : aucune entrée de ce nom dans la mémoire", ident=ident))
    if e.type not in memoire.BACKLOG or e.archivee or memoire.couche_attendue(e.fichier) != "backlog":
        raise ClotureRefusee(trad("`{id}` n'est pas une entrée du backlog : `socle close` ne clôt que le backlog",
                                  id=e.id))
    if e.basculee:
        raise ClotureRefusee(trad("`{id}` est basculée dans la mémoire privée : sa copie privée se clôt", id=e.id))
    if e.statut in memoire.BACKLOG_CLOS:
        raise ClotureRefusee(trad("`{id}` est déjà clos (« {statut} »)", id=e.id, statut=e.statut))
    lg = langue.du_projet(projet)
    ref = memoire.nettoyer(ref or "") or langue.mot(langue.VALEURS, "ce-commit", lg)
    remplacer = {"statut": langue.mot(langue.STATUTS[e.type], "fait", lg)}
    ajouter = []
    deja = [memoire.nettoyer(m) for m in re.split(r"[,;]", e.meta.get("ref", ""))]
    if "ref" in e.meta:
        remplacer["ref"] = e.meta["ref"].strip() + ("" if ref in deja else f", {ref}")
    else:
        ajouter.append(f"{langue.mot(langue.CHAMPS, 'ref', lg)} : {ref}")
    source = racine / e.fichier
    texte = source.read_text(encoding="utf-8")
    nouveau = migration._remeta(texte, remplacer=remplacer, ajouter=ajouter)
    if nouveau == texte:
        raise ClotureRefusee(trad("`{id}` n'a pas de ligne de métadonnées lisible", id=e.id))
    dossier, nom = e.fichier.rsplit("/", 1)
    relatif = e.fichier if memoire.parmi_les_clos(e.fichier) else f"{dossier}/{memoire.DOSSIER_CLOS}/{nom}"
    cible = racine / relatif
    # Un fichier déjà à la place de l'entrée close (une copie, une fusion) :
    # ni écrasé, ni perdu au refus.
    if cible != source and cible.exists():
        raise ClotureRefusee(trad("`{id}` ne se clôt pas : `{chemin}` existe déjà, à la place où elle se range",
                                  id=e.id, chemin=relatif))
    cree = not cible.parent.is_dir()
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(nouveau, encoding="utf-8")
    if cible != source:
        source.unlink()

    def remettre():
        if cible != source:
            cible.unlink()
            if cree:
                cible.parent.rmdir()
        source.write_text(texte, encoding="utf-8")

    try:
        ctx = contexte.Contexte(projet, etage="git", base=outils.base_de_travail(racine))
        fautes = [c.message for c in contexte.executer(ctx, CONTROLES_DE_CLOTURE).erreurs() if c.chemin == relatif]
    except BaseException:
        remettre()
        raise
    if fautes:
        remettre()
        raise ClotureRefusee(trad("`{id}` ne se clôt pas, rien n'est changé ; les contrôles du backlog le "
                                  "refuseraient clos :", id=e.id) + "".join(f"\n  - {f}" for f in fautes))
    if outils.est_depot(racine) and outils.git_reussit(racine, "ls-files", "--error-unmatch", "--", e.fichier):
        outils.git(racine, "add", "-A", "--", e.fichier, relatif)
    return e.fichier, relatif, ref


def commit_qui_clot(racine: Path, e: memoire.Entree) -> str | None:
    """Le commit que désigne la valeur `ce commit` du champ `ref` de
    l'entrée (ADR-0117) : le plus ancien de l'historique de son fichier,
    rangement compris, qui l'a écrite sur une ligne de métadonnées, par son
    SHA court et son titre. `None` sans cette valeur, ou tant qu'aucun
    commit ne l'a écrite. Dans le dépôt qui suit le fichier, celui de la
    mémoire privée compris."""
    mot = memoire.ref_ce_commit(e)
    if not mot:
        return None
    chemin = racine / e.fichier
    if not outils.est_depot(chemin.parent):
        return None
    # Une expression de git, non de Python ; `--follow` ne va pas avec
    # `--reverse` : le plus ancien est le dernier.
    motif = "^>.*" + re.sub(r"([.\[\]\\*^$])", r"\\\1", mot)
    sortie = outils.git(chemin.parent, "log", "--follow", "--format=%h %s", "-G", motif, "--", chemin.name,
                        check=False)
    return sortie.splitlines()[-1] if sortie.strip() else None
