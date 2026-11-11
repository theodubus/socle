"""L'initialisation d'un projet : trois entrées cumulables, un document de
cadrage, rien du tout, un dépôt existant (cadrage, section « Initialisation »).

Le moteur fait ce qui se fait sans juger : il archive le document tel quel
avec son empreinte, audite le dépôt en lecture seule et n'en tire que du
vérifiable (un fait « mesuré » a un fichier pour preuve), et pose les
questions de départ, chacune avec son défaut, plafonnées par la politique.
Ce qui demande de comprendre — extraire du document les objectifs et les
contraintes, confronter le document et le dépôt — revient à l'agent, avec
les règles que `socle init` lui imprime. Rien n'est inventé : un fait sans
source est « supposé ».
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from socle import config, language as langue, memory as memoire, messages, mutation, utils as outils
from socle.messages import trad
from socle.templates import gabarit


@dataclass
class Fait:
    titre: str
    preuve: str  # un chemin du dépôt


@dataclass
class Question:
    texte: str
    defaut: str
    effet: str  # ce que le défaut change


def archiver_cadrage(racine: Path, document: Path, prive: bool = False) -> tuple[str, str]:
    """Le document, copié tel quel dans les archives de la mémoire, et son
    empreinte. Son nom perd ses espaces (une référence `fichier:` n'en a pas) ;
    un document différent du même nom prend un suffixe au lieu d'écraser
    l'archive, et le même document se retrouve tel quel. Avec
    une mémoire privée, il s'archive dans sa zone : c'est de lui que viennent
    les termes privés."""
    ch = config.FORMAT_ACTUEL
    dossier = racine / (ch.dans_prive(ch.archives) if prive else ch.archives)
    dossier.mkdir(parents=True, exist_ok=True)
    nom = re.sub(r"\s+", "-", document.name.strip())
    base, ext = (nom.rsplit(".", 1)[0], "." + nom.rsplit(".", 1)[1]) if "." in nom else (nom, "")
    emp = outils.empreinte_fichier(document)
    for n in range(1, 1000):
        dest = dossier / (nom if n == 1 else f"{base}-{n}{ext}")
        if dest.resolve() == document.resolve() or not dest.exists():
            break
        if outils.empreinte_fichier(dest) == emp:
            break  # le même document, déjà archivé
    if document.resolve() != dest.resolve() and not dest.exists():
        shutil.copyfile(document, dest)
    return str(dest.relative_to(racine)), "sha256:" + outils.empreinte_fichier(dest)


def auditer_depot(projet: config.Projet) -> list[Fait]:
    """Ce que le dépôt prouve par ses fichiers : langage, tests, CI, docs."""
    racine = projet.racine
    fichiers = [f for f in outils.fichiers_courants(racine)
                if not f.startswith((config.DOSSIER + "/", ".claude/")) and not memoire.est_memoire(f)]
    faits = []
    if "Cargo.toml" in fichiers:
        faits.append(Fait(trad("Le projet se construit avec cargo (Rust)"), "Cargo.toml"))
    for f in ("pyproject.toml", "setup.py", "setup.cfg"):
        if f in fichiers:
            faits.append(Fait(trad("Le projet est un paquet Python"), f))
            break
    from socle import tests_reader as tests_lecture

    par_fichier = {}
    for a in projet.adaptateurs:
        cfg = a.donnees.get("tests") or {}
        if not cfg.get("function"):
            continue
        for f in outils.filtrer(fichiers, cfg.get("paths", []), cfg.get("exclude", [])):
            texte = outils.lire_a(racine, None, f) or ""
            n = sum(1 for fn in tests_lecture.extraire(texte, f, cfg) if fn.est_test)
            if n:
                par_fichier[f] = n
    if par_fichier:
        premier = sorted(par_fichier)[0]
        faits.append(Fait(trad("Le dépôt a {n} fonction(s) de test, dans {fichiers} fichier(s), dont "
                               "`{premier}`", n=sum(par_fichier.values()), fichiers=len(par_fichier),
                               premier=premier), premier))
    # La CI du socle et son balayage de mutation ne sont pas ceux du projet :
    # l'installeur vient de les poser.
    # Tous les workflows tiennent en un fait, relu à chaque session (B-0170).
    # Pour preuve, le premier, comme pour les tests.
    chemins = sorted(f for f in fichiers if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))
                     and f not in (".github/workflows/socle.yml", mutation.WORKFLOW))
    if chemins:
        workflows = {f.rsplit("/", 1)[1]: declencheurs(outils.lire_a(racine, None, f) or "") for f in chemins}
        faits.append(Fait(resumer_workflows(workflows), chemins[0]))
    for doc in ("README.md", "README", "README.rst"):
        if doc in fichiers:
            faits.append(Fait(trad("Le dépôt a un README"), doc))
            break
    return faits


CLE_ON = re.compile(r"""^(?:on|"on"|'on'|true)\s*:(.*)$""")
EVENEMENT = re.compile(r"[a-z_]+")
JUGENT = {"push", "pull_request", "pull_request_target"}
# Un push qui ne filtre que des tags ne juge ni une branche ni une pull
# request : il se rend sous ce nom, hors de JUGENT.
PUSH_TAGS = "push_tags"


def _nu(el: str) -> str:
    return re.sub(r"\s+#.*$", "", el).strip()


def declencheurs(texte: str) -> set[str] | None:
    """Les événements qui lancent un workflow GitHub, lus de sa clé `on`
    sans bibliothèque YAML : un mot (`on: push`), une liste (`on: [push,
    pull_request]`, ou un tiret par ligne), ou les clés du bloc indenté
    dessous. Un `push` dont le bloc ne filtre que des tags se rend
    `push_tags`. `None` quand rien ne se lit sûrement : on ne devine pas."""
    lignes = texte.lstrip("﻿").splitlines()
    for i, ligne in enumerate(lignes):
        m = CLE_ON.match(ligne)
        if not m:
            continue
        reste = _nu(m.group(1))
        sous: dict[str, set[str]] = {}
        if reste:
            if reste[0] in "[{":
                if reste[-1] != {"[": "]", "{": "}"}[reste[0]] or "tags" in reste:
                    return None  # sur plusieurs lignes, ou des tags qui ne se lisent pas sûrement
                mots = [x.split(":")[0].strip().strip("'\"") for x in reste[1:-1].split(",") if x.strip()]
            else:
                mots = [reste.strip("'\"")]
        else:
            entrees = []
            for suite in lignes[i + 1:]:
                if not suite.strip() or suite.lstrip().startswith("#"):
                    continue
                r, el = len(suite) - len(suite.lstrip()), _nu(suite)
                if r == 0 and not el.startswith("-"):
                    break
                entrees.append((r, el))
            mots, cles, courant = [], False, None
            retrait = entrees[0][0] if entrees else 0
            for r, el in entrees:
                if r < retrait:
                    return None
                if r == retrait and el.startswith("-"):
                    if not cles:  # sinon, la liste compacte sous un événement
                        mots.append(el[1:].strip().strip("'\""))
                elif r == retrait:
                    cles, courant = True, el.split(":")[0].strip().strip("'\"")
                    mots.append(courant)
                    valeur = el.split(":", 1)[1].strip() if ":" in el else ""
                    if courant == "push" and "tags" in valeur:
                        return None  # des sous-clés en ligne : ne se lisent pas sûrement
                    sous[courant] = set()
                elif courant and ":" in el and not el.startswith("-"):
                    sous[courant].add(el.split(":")[0].strip().strip("'\""))
        if not mots or not all(EVENEMENT.fullmatch(x) for x in mots):
            return None
        evts = set(mots)
        filtres = sous.get("push", set())
        if filtres & {"tags", "tags-ignore"} and not filtres & {"branches", "branches-ignore"}:
            evts = evts - {"push"} | {PUSH_TAGS}
        return evts
    return None


def resumer_workflows(workflows: dict[str, set[str] | None]) -> str:
    """Le fait unique des workflows : ceux qui jugent un push de branche ou
    une pull request, les autres (à la main, planifiés, sur un tag, autre
    événement), les non lus. La ponctuation suit la langue du projet."""
    groupes = {"jugent": [], "autres": [], "non_lus": []}
    for nom, evts in sorted(workflows.items()):
        groupes["non_lus" if evts is None else "jugent" if evts & JUGENT else "autres"].append(nom)

    def liste(noms):
        return f"{len(noms)} ({', '.join(f'`{n}`' for n in noms)})" if noms else trad("aucun")

    texte = trad("qui jugent un push de branche ou une pull request : {liste}", liste=liste(groupes["jugent"]))
    if groupes["autres"]:
        texte = trad("{gauche} ; {droite}", gauche=texte, droite=trad(
            "autres (à la main, planifiés, autre événement) : {liste}", liste=liste(groupes["autres"])))
    if groupes["non_lus"]:
        texte = trad("{gauche} ; {droite}", gauche=texte,
                     droite=trad("non lus : {liste}", liste=liste(groupes["non_lus"])))
    return trad("Workflows GitHub du projet, {parties}", parties=texte)


def questions_de_depart(projet: config.Projet, cadrage: str | None, depot: bool) -> list[Question]:
    """Ce que l'agent ne peut pas déduire, avec un défaut chacune : le
    langage et les outils se lisent dans le dépôt, l'objectif et la
    confidentialité non."""
    q = []
    if cadrage:
        but = trad("celui du document de cadrage, tel qu'il est écrit")
    elif depot:
        but = trad("celui que dit le README, s'il en a un ; sinon aucun, et le backlog reste vide")
    else:
        but = trad("aucun : le backlog reste vide jusqu'à ce que tu en donnes un")
    q.append(Question(trad("Quel est le but du projet, en une phrase ?"), but,
                      trad("le but alimente le backlog ; en défaut, il est noté « supposé »")))
    if not (depot and detecter(projet)):
        q.append(Question(trad("Dans quel langage, avec quels outils de test ?"),
                          trad("celui de l'adaptateur posé à l'installation"),
                          trad("l'adaptateur décide comment le socle lance les tests ; le changer demande ton "
                               "accord")))
    q.append(Question(trad("Une partie de la mémoire doit-elle rester privée ?"),
                      trad("non : toute la mémoire est publique"),
                      trad("une mémoire privée se pose par l'installeur, en dépôt privé à côté ou chiffrée")))
    q.append(Question(trad("La politique d'autonomie par défaut (les huit points du cadrage) te convient-elle ?"),
                      trad("oui, telle quelle"),
                      trad("la politique dit ce que l'agent décide seul et ce qu'il te demande ; toi seul la "
                           "modifies")))
    # La livraison (D-0058) : une pull request par sujet en fait une à
    # fusionner par sujet, d'où une branche de développement par défaut.
    q.append(Question(trad("Le travail se livre-t-il par une branche de développement, une seule pull request "
                           "ouverte à la fois, ou par une branche et une pull request par sujet ?"),
                      trad("une branche de développement : chaque lot fini s'ajoute à la pull request ouverte, "
                           "que tu fusionnes quand tu veux"),
                      trad("une pull request par sujet se relit sujet par sujet, mais il y en a une à fusionner "
                           "par sujet ; le choix devient un fait de la mémoire, que l'agent suit")))
    q.append(Question(trad("Des contraintes à respecter (licence, dépendances, plateformes, délais) ?"),
                      trad("aucune connue"),
                      trad("une contrainte devient un fait « supposé » jusqu'à ce que tu la valides")))
    plafond = int(projet.pol("init_questions_max", defaut=7))
    return q[:plafond]


def detecter(projet: config.Projet) -> bool:
    from socle import installer as installeur

    return installeur.detecter_adaptateur(projet.racine) is not None


def demande_de_depart(projet: config.Projet, ident: str, questions: list[Question], cadrage: str | None,
                      entrees: str) -> str:
    plafond = int(projet.pol("init_questions_max", defaut=7))
    lignes = []
    for i, q in enumerate(questions, 1):
        lignes.append(trad("{i}. **{question}** Défaut : {defaut}. Ce que ça change : {effet}.", i=i,
                           question=q.texte, defaut=q.defaut, effet=q.effet))
    if cadrage:
        cite = trad("- Le document de cadrage, archivé tel quel sous `{cadrage}` : ce que le projet veut, d'où "
                    "l'agent tire les faits « supposés » et le backlog de départ.", cadrage=cadrage)
        lien = trad("- Le document de cadrage : [{nom}]({lien}).", nom=Path(cadrage).name,
                    lien=f"../{Path(cadrage).relative_to(projet.chemins.memoire)}")
    else:
        cite = trad("- Aucun élément de la mémoire : le projet commence, et ces questions en posent le départ.")
        # Le fichier d'instructions qui existe : l'installeur garde CLAUDE.md
        # quand le projet le lit par son nom.
        instr = config.INSTRUCTIONS if (projet.racine / config.INSTRUCTIONS).is_file() else "CLAUDE.md"
        lien = trad("- Les instructions du projet : [{instr}]({lien}), section de la politique d'autonomie.",
                    instr=instr, lien=f"../../{instr}")
    return gabarit("starting-questions.md", langue.du_projet(projet)).format(
        id=ident, date=date.today().isoformat(), nom=projet.racine.name, entrees=entrees, n=len(questions),
        plafond=plafond,
        questions="\n".join(lignes), elements=cite, lien=lien)


def initialiser(projet: config.Projet, cadrage: Path | None = None, depot: bool = False) -> int:
    """Ce que `socle init` fait, dans la langue de la mémoire du projet :
    ce qu'il écrit dans la mémoire comme ce qu'il imprime."""
    with messages.dans(langue.du_projet(projet)):
        return _initialiser(projet, cadrage, depot)


def _initialiser(projet: config.Projet, cadrage: Path | None, depot: bool) -> int:
    from socle import cli, private as prive

    racine = projet.racine
    if not projet.installe:
        print(trad("refus : le socle n'est pas installé ici (`socle install` d'abord)"))
        return 2
    jour = date.today().isoformat()
    lg = langue.du_projet(projet)
    mem = memoire.Memoire.charger(racine)
    entrees = trad(" et ").join(x for x in (
        trad("un document de cadrage") if cadrage else "", trad("un dépôt existant") if depot else "") if x) \
        or trad("rien du tout")
    sortie = [trad("initialisation depuis {entrees}", entrees=entrees)]

    archive = None
    if cadrage:
        en_prive = prive.mode(projet) is not None
        if en_prive and not prive.acces(projet).disponible:
            print(trad("refus : avec une mémoire privée, le cadrage s'archive dans sa zone, indisponible ici "
                       "({raison}) ; la mettre en place d'abord", raison=prive.acces(projet).raison))
            return 2
        archive, emp = archiver_cadrage(racine, cadrage, prive=en_prive)
        journal_prive = en_prive and "journal" in prive.couches_privees(projet)
        ident = mem.prochain_id("J", prive=journal_prive, date=jour)
        journal = projet.chemins.dans_prive(projet.chemins.journal) if journal_prive else projet.chemins.journal
        cli._ajouter(memoire.fichier_journal(racine / journal, jour[:7],
                                             projet.budget_octets(f"{projet.chemins.journal}/{jour[:7]}.md"), 2000),
                     trad("\n## {ident} — Document de cadrage archivé tel quel\n\n{meta} · empreinte : {emp}\n\n"
                          "Archivé sans réécriture. Ce qu'il affirme entre dans la mémoire en « supposé », avec ce "
                          "fichier pour source, jusqu'à validation humaine.\n", ident=ident, emp=emp,
                          meta=langue.meta(lg, type="initialisation", ref=langue.ref_fichier(archive, lg))),
                     langue.entete_fichier("journal", "privee" if journal_prive else "publique", lg))
        sortie.append(trad("document archivé : {archive} ({empreinte}…), journal {ident}", archive=archive,
                           empreinte=emp[:23], ident=ident))
        mem = memoire.Memoire.charger(racine)

    if depot:
        faits = auditer_depot(projet)
        premier = int(mem.prochain_id("F").split("-")[1])
        bloc = ""
        for k, f in enumerate(faits):
            bloc += (f"\n## F-{premier + k:04d} — {f.titre}\n\n"
                     + langue.meta(lg, "F", statut="mesure", preuve=langue.ref_fichier(f.preuve, lg),
                                   source=trad("audit d'initialisation"), date=jour) + "\n")
        if bloc:
            cli._ajouter(racine / projet.chemins.canonique, bloc, langue.entete_fichier("canonique", "publique", lg))
        sortie.append(trad("audit du dépôt en lecture seule : {n} fait(s) mesuré(s), chacun avec son fichier",
                           n=len(faits)))
        mem = memoire.Memoire.charger(racine)

    qs = questions_de_depart(projet, archive, depot)
    ident = mem.prochain_id("D")
    chemin = racine / projet.chemins.demandes / f"{ident}-{'starting-questions' if lg == 'en' else 'questions-de-depart'}.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(demande_de_depart(projet, ident, qs, archive, entrees), encoding="utf-8")
    sortie.append(trad("questions de départ : {ident}, {n} question(s), chacune avec son défaut", ident=ident,
                       n=len(qs)))

    for l in sortie:
        print(f"  - {l}")
    print(trad("\nPour toi :"))
    for i, etape in enumerate(pour_toi(ident), 1):
        print(f"  {i}. {etape}")
    print("\n" + gabarit("initialization.md", lg))
    return 0


def pour_toi(ident: str) -> list[str]:
    """Ce qui revient à l'humain après `init`, avant la part de l'agent,
    écrite pour lui."""
    return [
        trad('commiter puis pousser : `git add -A && git commit -m "Initialiser la mémoire" && git push` (la '
             "demande {ident} doit être sur GitHub pour que tu puisses la lire)", ident=ident),
        trad("ouvrir l'agent dans le projet : il relit les questions de départ et te les pose dans la "
             "conversation, avec leur lien"),
        trad("y répondre dans la conversation, une ligne par question ou « défauts » : l'agent consigne ta "
             "réponse telle quelle"),
    ]
