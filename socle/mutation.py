"""Le verdict de mutation : les survivants d'un balayage, module par module,
confrontés au plafond des garde-fous.

Le plafond est un cliquet : il CASSE à la hausse et SIGNALE la baisse. Un
mutant qui expire sur une machine chargée est compté « expiré » plutôt que
« survivant », donc une baisse peut n'être qu'un artefact de charge ; une
hausse, jamais.

Les lecteurs de résultats sont propres à chaque outil ; l'adaptateur nomme le
sien (`parser`). Un module du plafond sans aucun résultat est un balayage qui
n'a pas tourné : il casse, il ne passe pas pour une couverture parfaite.

Le balayage lui-même (`balayer`) lance la commande de l'adaptateur, module
par module quand elle nomme `{module}`, puis rend le verdict : c'est ce que
fait chaque semaine le workflow que pose l'installeur. Et parce qu'un
cliquet ne peut pas signaler sa propre absence, `vivacite` dit quand ce
workflow cesse de tourner.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from socle import config, utils as outils
from socle.messages import a_traduire, trad
from socle.report import Rapport


def lire_cargo_mutants(dossier: Path) -> dict[str, Counter]:
    """`missed.txt`, `caught.txt`, `timeout.txt`, `unviable.txt` de chaque
    `mutants.out` sous `dossier` : une ligne `chemin:ligne:col: description`."""
    res: dict[str, Counter] = {}
    vus: set[tuple[str, str]] = set()
    for nom, issue in (("missed.txt", "survivants"), ("caught.txt", "attrapes"),
                       ("timeout.txt", "expires"), ("unviable.txt", "inviables")):
        for f in sorted(dossier.rglob(nom)):
            for ligne in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ligne.strip() or (issue, ligne) in vus:
                    continue
                vus.add((issue, ligne))
                module = ligne.split(":", 1)[0]
                res.setdefault(module, Counter())[issue] += 1
    return res


# Ce que mutmut prouve d'un mutant. Un statut absent d'ici ne prouve pas le
# mutant attrapé (`not checked`, un balayage interrompu, un statut nouveau) :
# il compte comme survivant, et casse au lieu de passer.
STATUTS_MUTMUT = {"killed": "attrapes", "caught by type check": "attrapes", "timeout": "expires",
                  "suspicious": "expires", "segfault": "expires", "skipped": "inviables"}
# Le module est tout ce qui précède le dernier `.x_` ou `.xǁ` : le nom de la
# fonction n'a pas de point, et un module peut commencer par `x_`.
NOM_MUTMUT = re.compile(r"^(?P<module>[\w.]+)\.x[_ǁ][^.]*__mutmut_\d+$")


def lire_mutmut(dossier: Path) -> dict[str, Counter]:
    """La sortie de `mutmut results --all true` redirigée dans
    `mutmut-results.txt` (sans `--all`, les mutants attrapés manquent, et un
    module tout attrapé passerait pour jamais balayé) : une ligne par mutant,
    `paquet.module.x_fonction__mutmut_N: statut`, ou `xǁClasseǁméthode` pour
    une méthode. Le nom ne dit pas où vit le fichier : le mutant compte pour
    chaque chemin possible (module, `__init__.py` d'un paquet, sous `src/`),
    et le verdict ne lit que celui du plafond."""
    res: dict[str, Counter] = {}
    for f in sorted(dossier.rglob("mutmut-results.txt")):
        for ligne in f.read_text(encoding="utf-8", errors="replace").splitlines():
            nom, _, statut = ligne.rpartition(":")
            m = NOM_MUTMUT.match(nom.strip())
            if not m:
                continue
            issue = STATUTS_MUTMUT.get(statut.strip(), "survivants")
            chemin = m["module"].replace(".", "/")
            for module in (f"{chemin}.py", f"{chemin}/__init__.py", f"src/{chemin}.py", f"src/{chemin}/__init__.py"):
                res.setdefault(module, Counter())[issue] += 1
    return res


def _suffixes(chemin: str) -> list[str]:
    """Un chemin et tous ses suffixes (`/a/b/src/x.js` → `src/x.js`, `x.js`…) :
    un outil qui écrit des chemins absolus, ou relatifs à un autre dossier,
    compte pour chacun, et le verdict ne lit que celui du plafond."""
    morceaux = [m for m in chemin.replace("\\", "/").split("/") if m and m != "."]
    return ["/".join(morceaux[i:]) for i in range(len(morceaux))]


def _compter(res: dict[str, Counter], chemin: str, issue: str):
    for module in _suffixes(chemin):
        res.setdefault(module, Counter())[issue] += 1


def _json(f: Path):
    import json

    try:
        return json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return None


# Stryker (JavaScript, TypeScript) et Stryker.NET (C#) : le rapport du schéma
# commun des rapports de mutation, `mutation.json` pour l'un,
# `mutation-report.json` pour l'autre, qui écrit des chemins absolus. Un
# statut absent d'ici compte survivant.
STATUTS_STRYKER = {"Killed": "attrapes", "Timeout": "expires", "CompileError": "inviables",
                   "RuntimeError": "inviables", "Ignored": "inviables"}
RAPPORTS_STRYKER = ("mutation.json", "mutation-report.json")


def lire_stryker(dossier: Path) -> dict[str, Counter]:
    res: dict[str, Counter] = {}
    for f in sorted(f for nom in RAPPORTS_STRYKER for f in dossier.rglob(nom)):
        if "node_modules" in f.parts or not isinstance(d := _json(f), dict):
            continue
        for chemin, contenu in (d.get("files") or {}).items():
            for m in contenu.get("mutants", []):
                _compter(res, chemin, STATUTS_STRYKER.get(m.get("status", ""), "survivants"))
    return res


# gremlins (Go) : `gremlins unleash --output=gremlins.json`.
STATUTS_GREMLINS = {"KILLED": "attrapes", "TIMED OUT": "expires", "NOT VIABLE": "inviables", "SKIPPED": "inviables"}


def lire_gremlins(dossier: Path) -> dict[str, Counter]:
    res: dict[str, Counter] = {}
    for f in sorted(dossier.rglob("gremlins.json")):
        if not isinstance(d := _json(f), dict):
            continue
        for fichier in d.get("files") or []:
            for m in fichier.get("mutations") or []:
                _compter(res, fichier.get("file_name", ""), STATUTS_GREMLINS.get(m.get("status", ""), "survivants"))
    return res


# PIT (Java, Kotlin) : `target/pit-reports/mutations.xml` sous Maven,
# `build/reports/pitest/mutations.xml` sous Gradle. Le fichier se déduit du
# paquet de la classe mutée et du nom de son fichier source.
STATUTS_PIT = {"KILLED": "attrapes", "TIMED_OUT": "expires", "MEMORY_ERROR": "expires",
               "RUN_ERROR": "inviables", "NON_VIABLE": "inviables"}
# Ce que produit la construction, où un fichier source n'est qu'une copie.
DOSSIERS_DE_CONSTRUCTION = {"build", "target", ".gradle", "out"}


def _source_pit(dossier: Path, paquet: str, source: str, connus: dict) -> str:
    """Le fichier source d'une mutation de PIT, qui ne connaît que le paquet de
    la classe et le nom du fichier : celui du dépôt dont le chemin finit par
    le paquet puis le nom (`src/main/kotlin/essai/Calc.kt`) ; sinon le seul de
    ce nom qui déclare ce paquet, Kotlin permettant de ne pas ranger un
    fichier sous son paquet ; à défaut, le chemin de Maven,
    `src/main/java/<paquet>/<fichier>`."""
    cle = (paquet, source)
    if cle not in connus:
        attendu = f"{paquet}/{source}" if paquet else source
        trouves = [p for p in dossier.rglob(source)
                   if p.is_file() and not DOSSIERS_DE_CONSTRUCTION & set(p.relative_to(dossier).parts[:-1])]
        rangs = [p for p in trouves if p.relative_to(dossier).as_posix().endswith(attendu)]
        if len(rangs) != 1 and paquet:
            declare = re.compile(rf"^\s*package\s+{re.escape(paquet.replace('/', '.'))}\s*;?\s*$", re.M)
            rangs = [p for p in trouves if declare.search(p.read_text(encoding="utf-8", errors="replace"))]
        connus[cle] = rangs[0].relative_to(dossier).as_posix() if len(rangs) == 1 else f"src/main/java/{attendu}"
    return connus[cle]


def lire_pit(dossier: Path) -> dict[str, Counter]:
    import xml.etree.ElementTree as ET

    res: dict[str, Counter] = {}
    connus: dict = {}
    for f in sorted(dossier.rglob("mutations.xml")):
        try:
            racine = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for m in racine.iter("mutation"):
            classe, source = m.findtext("mutatedClass", ""), m.findtext("sourceFile", "")
            paquet = "/".join(classe.split(".")[:-1])
            _compter(res, _source_pit(dossier, paquet, source, connus), STATUTS_PIT.get(m.get("status", ""),
                                                                                    "survivants"))
    return res


def lire_mutant(dossier: Path) -> dict[str, Counter]:
    """mutant (Ruby) : la session la plus récente sous `.mutant/results/`
    (leurs noms, des UUID v7, se rangent dans le temps). Une mutation est
    attrapée si l'un de ses critères l'a tuée (un test a échoué, le
    processus s'est arrêté) ; expirée si seul le délai l'a fait."""
    res: dict[str, Counter] = {}
    sessions = sorted(dossier.rglob(".mutant/results/*.json"), key=lambda f: f.name)
    if not sessions or not isinstance(d := _json(sessions[-1]), dict):
        return res
    for sujet in d.get("subject_results") or []:
        for r in sujet.get("coverage_results") or []:
            c = r.get("criteria_result") or {}
            issue = ("attrapes" if c.get("test_result") or c.get("process_abort")
                     else "expires" if c.get("timeout") else "survivants")
            _compter(res, sujet.get("source_path", ""), issue)
    return res


# Infection (PHP) : le journal JSON (`logs.json` de `infection.json5`).
ISSUES_INFECTION = {"killed": "attrapes", "timeouted": "expires", "errored": "inviables",
                    "syntaxErrors": "inviables", "ignored": "inviables", "escaped": "survivants",
                    "uncovered": "survivants"}


def lire_infection(dossier: Path) -> dict[str, Counter]:
    res: dict[str, Counter] = {}
    for f in sorted(dossier.rglob("infection.json")):
        if "vendor" in f.parts or not isinstance(d := _json(f), dict) or "stats" not in d:
            continue
        for cle, issue in ISSUES_INFECTION.items():
            for m in d.get(cle) or []:
                _compter(res, (m.get("mutator") or {}).get("originalFilePath", ""), issue)
    return res


LECTEURS = {"cargo-mutants": lire_cargo_mutants, "mutmut": lire_mutmut, "stryker": lire_stryker,
            "gremlins": lire_gremlins, "pit": lire_pit, "mutant": lire_mutant, "infection": lire_infection}


def verdict(projet: config.Projet, dossier: Path, poser: bool = False) -> Rapport:
    """Les survivants de chaque module du plafond, confrontés à son plafond.
    Un module « à mesurer » (`pending`) n'a pas encore de plafond : son compte
    se dit, et `poser` l'écrit dans les garde-fous, ce qui durcit le cliquet."""
    r = Rapport()
    ident = "mutation.verdict"
    r.execute(ident)
    cap = projet.adaptateur.get("capabilities", {}).get("mutation", {})
    if "command" not in cap:
        r.indisponible(ident, trad("capacité absente : {absent}",
                                   absent=trad(cap["absent"]) if "absent" in cap else trad("non déclarée")))
        return r
    lecteur = LECTEURS.get(cap.get("parser", ""))
    if lecteur is None:
        r.erreur(ident, trad("lecteur de résultats inconnu : « {parser} » (connus : {liste})",
                             parser=cap.get('parser'), liste=', '.join(LECTEURS)))
        return r
    if not dossier.is_dir():
        r.erreur(ident, trad("dossier de résultats introuvable : {dossier}", dossier=dossier))
        return r
    plafonds = plafonds_de(projet)
    if not plafonds:
        r.erreur(ident, trad("plafond vide : rien à comparer — un vert ici serait silencieux"))
        return r
    resultats = lecteur(dossier)
    mesures = {}
    for module, p in plafonds.items():
        c = resultats.get(module)
        if p.get("pending"):
            if not c:
                r.avertir(ident, trad("{module} : à mesurer, et pas encore balayé", module=module))
                continue
            mesures[module] = c["survivants"]
            r.avertir(ident, trad("{module} : à mesurer — {n} survivant(s) ; ", module=module, n=c["survivants"])
                      + (trad("plafond posé") if poser else trad("`--record` l'écrit comme plafond")))
            continue
        if not c:
            r.erreur(ident, trad("{module} : aucun résultat — le balayage n'a pas tourné sur ce module",
                                 module=module))
            continue
        n = c["survivants"]
        if n > p.get("max", 0):
            r.erreur(ident, trad("{module} : {n} survivant(s) pour un plafond de {plafond} — du code a cessé "
                                 "d'être couvert. Corriger les tests, ou demander à relever le plafond (raison "
                                 "écrite).", module=module, n=n, plafond=p.get('max', 0)))
        elif n < p.get("max", 0):
            r.avertir(ident, trad("{module} : {n} survivant(s) sous le plafond {plafond} — resserrer le plafond",
                                  module=module, n=n, plafond=p.get('max', 0)))
    if poser and mesures:
        for module in poser_plafonds(projet, mesures):
            r.erreur(ident, trad("{module} : plafond annoncé mais non écrit — la forme de sa clé dans "
                                 "`{fichier}` n'est pas reconnue ; l'écrire à la main",
                                 module=module, fichier=projet.chemins.garde_fous))
    return r


def plafonds_de(projet: config.Projet) -> dict:
    """Les plafonds que juge l'adaptateur de la vue. Dans un projet à
    plusieurs adaptateurs, ceux de ses seuls modules : deux langages ne se
    mêlent pas (ADR-0051, point 5). Seul, il les juge tous."""
    plafonds = projet.gf("mutation", "caps", defaut={}) or {}
    if not projet.plusieurs_adaptateurs:
        return plafonds

    def modules_de(a) -> set[str]:
        cap = a.donnees.get("capabilities", {}).get("mutation", {})
        return set(outils.filtrer(sorted(plafonds), cap.get("modules", []), cap.get("modules_exclude", [])))

    siens = modules_de(projet.adaptateur_courant)
    # Un plafond qu'aucun adaptateur ne désigne revient au principal, qui le
    # jugeait seul avant : un module sans résultat casse toujours.
    if projet.adaptateur_courant.chemin == projet.adaptateurs[0].chemin:
        designes = set().union(*(modules_de(a) for a in projet.adaptateurs))
        siens |= set(plafonds) - designes
    return {m: p for m, p in plafonds.items() if m in siens}


def poser_plafonds(projet: config.Projet, mesures: dict[str, int]) -> list[str]:
    """Remplace, dans les garde-fous, l'entrée « à mesurer » de chaque module
    par son plafond mesuré, avec sa raison quand il n'est pas nul. La clé
    s'écrit entre guillemets doubles ou simples, en table en ligne ou en
    table ; rend les modules dont le plafond n'a pas pu s'écrire, relu après
    coup."""
    import json
    import tomllib
    from datetime import date

    p = projet.racine / projet.chemins.garde_fous
    lignes = p.read_text(encoding="utf-8").splitlines()
    for module, n in mesures.items():
        cle = json.dumps(module, ensure_ascii=False)
        cles = rf"(?:{re.escape(cle)}|'{re.escape(module)}')"
        raison = json.dumps(trad("mesuré le {date} : {n} survivant(s)", date=date.today().isoformat(), n=n),
                            ensure_ascii=False)
        valeur = f"{{ max = {n}, reason = {raison} }}" if n else "{ max = 0 }"
        en_ligne = re.compile(rf"^\s*{cles}\s*=\s*\{{[^}}]*\bpending\b")
        en_table = re.compile(rf"^\s*\[\s*mutation\s*\.\s*caps\s*\.\s*{cles}\s*\]\s*$")
        res, dans = [], False
        for l in lignes:
            if en_ligne.match(l):
                l = f"{cle} = {valeur}"
            elif en_table.match(l):
                dans = True
            elif l.lstrip().startswith("["):
                dans = False
            elif dans and re.match(r"^\s*pending\s*=", l):
                l = f"max = {n}" + (f"\nreason = {raison}" if n else "")
            elif dans and re.match(r"^\s*reason\s*=", l):
                continue  # la raison de l'attente cède à celle de la mesure
            res.append(l)
        lignes = "\n".join(res).splitlines()
    p.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    try:
        caps = tomllib.loads(p.read_text(encoding="utf-8")).get("mutation", {}).get("caps", {})
    except tomllib.TOMLDecodeError:
        return list(mesures)
    return [m for m, n in mesures.items() if caps.get(m, {}).get("pending") or caps.get(m, {}).get("max") != n]

# --------------------------------------------------------------------------
# Le balayage, puis son verdict
# --------------------------------------------------------------------------

# Les sorties d'un balayage module par module : sous la trace, ignorée par
# git, donc hors de la copie de l'arbre que fait l'outil pour chaque mutant.
SORTIES = ".socle/trace/mutation"


def commandes_de_balayage(projet: config.Projet) -> tuple[list[str], Path | None, str | None]:
    """(commandes, dossier des résultats, faute). Une commande qui nomme
    `{module}` se lance une fois par module du plafond, chacune dans son
    propre dossier `{output}` : sans lui, chaque balayage écraserait le
    précédent, et le verdict ne lirait que le dernier."""
    cap = projet.adaptateur.get("capabilities", {}).get("mutation", {})
    commande = cap.get("command")
    if not commande:
        return [], None, trad("capacité absente : {absent}",
                              absent=trad(cap["absent"]) if "absent" in cap else trad("non déclarée"))
    if "{module}" not in commande:
        return [commande.replace("{output}", ".")], projet.racine, None
    if "{output}" not in commande:
        return [], None, (trad("la commande de l'adaptateur balaie module par module sans `{output}` : chaque "
                               "balayage écraserait le précédent ; y ajouter l'option de l'outil qui choisit "
                               "son dossier de sortie, `{output}` en valeur"))
    modules = sorted(plafonds_de(projet))
    if not modules:
        return [], None, trad("plafond vide : aucun module à balayer")
    dossier = projet.racine / SORTIES
    if projet.plusieurs_adaptateurs:
        dossier = dossier / projet.adaptateur_courant.nom
    return [commande.replace("{module}", shlex.quote(m)).replace("{output}", shlex.quote(str(dossier / f"{k:03d}")))
            for k, m in enumerate(modules)], dossier, None


def balayer(projet: config.Projet, poser: bool = False, flux=None) -> Rapport:
    """Lance le balayage de chaque adaptateur, puis rend son verdict. Le code
    de sortie de l'outil ne décide rien (des survivants le font souvent
    échouer) : le verdict lit ses résultats, et un module sans résultat
    casse. Sans `flux`, la sortie de l'outil passe telle quelle, au fil du
    balayage. Dans un projet à plusieurs adaptateurs, chaque constat nomme le
    sien (ADR-0051, point 5)."""
    if not projet.plusieurs_adaptateurs:
        return _balayer(projet, poser, flux)
    r = Rapport()
    for a in projet.adaptateurs:
        siens = _balayer(projet.pour(a), poser, flux)
        for k in siens.constats:
            k.message = trad("{adaptateur} : {message}", adaptateur=a.nom, message=k.message)
        r.fusionner(siens)
    return r


def _balayer(projet: config.Projet, poser: bool, flux) -> Rapport:
    r = Rapport()
    ident = "mutation.balayage"
    r.execute(ident)
    commandes, dossier, faute = commandes_de_balayage(projet)
    if faute:
        absente = "command" not in projet.adaptateur.get("capabilities", {}).get("mutation", {})
        (r.indisponible if absente else r.erreur)(ident, faute)
        return r
    if dossier != projet.racine:
        shutil.rmtree(dossier, ignore_errors=True)
        dossier.mkdir(parents=True)
    for c in commandes:
        print(f"$ {c}", file=flux or sys.stdout, flush=True)
        if flux is None:
            subprocess.run(c, shell=True, cwd=projet.racine)
        else:
            p = subprocess.run(c, shell=True, cwd=projet.racine, capture_output=True, text=True)
            flux.write(p.stdout + p.stderr)
    r.fusionner(verdict(projet, dossier, poser))
    return r


# --------------------------------------------------------------------------
# Le workflow planifié, et sa vivacité
# --------------------------------------------------------------------------

WORKFLOW = ".github/workflows/socle-mutation.yml"
# Ce qui, dans un workflow, désigne l'outil de mutation d'un adaptateur : un
# projet qui balaie déjà par son propre workflow n'en reçoit pas un second.
MARQUES_OUTIL = {"cargo-mutants": r"\bcargo[ -]mutants\b", "mutmut": r"\bmutmut\b", "stryker": r"\bstryker\b",
                 "gremlins": r"\bgremlins\b", "pit": r"\bpitest\b", "mutant": r"\bmutant\s+run\b",
                 "infection": r"\binfection\b"}
# GitHub endort les workflows planifiés d'un dépôt public après soixante
# jours sans activité. Quinze jours laissent passer un balayage hebdomadaire
# manqué, pas deux.
SEUIL_JOURS = 15


def workflow_de_balayage(cap: dict, fichiers: list[str], lire: Callable[[str], str | None],
                         sauf_le_sien: bool = False) -> str | None:
    """Le workflow qui lance le balayage : celui du socle, sinon un workflow
    du projet qui nomme son outil de mutation."""
    if not sauf_le_sien and WORKFLOW in fichiers:
        return WORKFLOW
    marque = MARQUES_OUTIL.get(cap.get("parser", ""))
    if marque is None:
        return None
    for f in sorted(fichiers):
        if (re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", f) and f not in (WORKFLOW, ".github/workflows/socle.yml")
                and re.search(marque, lire(f) or "")):
            return f
    return None


def _date(texte: str) -> datetime:
    d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def vivacite(etat: str | None, derniere: str | None, cree: str | None,
             maintenant: datetime | None = None) -> tuple[str | None, str]:
    """(niveau, message) d'après l'état du workflow que rend GitHub, la date
    de sa dernière exécution achevée et celle où il est apparu. Le niveau
    vaut `erreur`, `avertir` ou `None` (il tourne)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    if etat != "active":
        return "erreur", (trad("le workflow est « {etat} » : GitHub endort les workflows planifiés d'un dépôt "
                               "public après soixante jours sans activité, et plus rien ne mesure le cliquet. "
                               "Le réactiver (Actions → le workflow → Enable workflow), puis le lancer à la "
                               "main", etat=etat))
    if derniere is None:
        age = (maintenant - _date(cree)).days if cree else 0
        if age > SEUIL_JOURS:
            return "erreur", (trad("aucun balayage en {age} jours d'existence du workflow : son cron ne part "
                                   "pas. Le lancer à la main, et chercher pourquoi", age=age))
        return "avertir", trad("pas encore de balayage : le premier part au prochain créneau du cron, ou à la "
                               "main")
    age = (maintenant - _date(derniere)).days
    if age > SEUIL_JOURS:
        return "erreur", (trad("dernier balayage il y a {age} jours ({derniere}) : le workflow est actif mais "
                               "ne tourne plus. Le lancer à la main, et chercher pourquoi son cron ne part plus",
                               age=age, derniere=derniere[:10]))
    return None, trad("dernier balayage il y a {age} jour(s)", age=age)


# Un workflow présent sur la branche par défaut, que GitHub ne connaît pas :
# le délai qu'on lui laisse pour l'enregistrer, en jours.
DELAI_ENREGISTREMENT = 2
REMEDE_ENREGISTREMENT = a_traduire(
    "Pousser un commit sur la branche par défaut qui modifie ce fichier (une ligne de commentaire suffit ; c'est "
    "un fichier protégé, que l'humain approuve) : GitHub n'enregistre un workflow qu'au push qui modifie son "
    "fichier, pas toujours au premier push qui le pose. Puis vérifier dans l'onglet Actions qu'il y apparaît")


def arrivee_sur_la_branche_par_defaut(racine: Path, flux: str) -> str | None:
    """La date du plus ancien commit visible de la branche par défaut qui
    touche `flux`, s'il y est ; `None` sinon."""
    from socle import utils as outils

    defaut = outils.branche_par_defaut(racine)
    if not defaut or not outils.git_reussit(racine, "cat-file", "-e", f"{defaut}:{flux}"):
        return None
    dates = outils.git(racine, "log", "--format=%cI", defaut, "--", flux, check=False).split()
    return dates[-1] if dates else None


def inconnu_de_github(nom: str, arrivee: str | None, maintenant: datetime | None = None) -> tuple[str, str]:
    """(niveau, message) quand GitHub ne connaît pas le workflow : pas encore
    fusionné, un avertissement ; présent sur la branche par défaut sans être
    enregistré, son cron ne part jamais, une erreur passé le délai."""
    if arrivee is None:
        return "avertir", trad("`{nom}` n'est pas encore sur la branche par défaut : GitHub ne le planifie "
                               "qu'une fois fusionné", nom=nom)
    age = ((maintenant or datetime.now(timezone.utc)) - _date(arrivee)).days
    if age >= DELAI_ENREGISTREMENT:
        return "erreur", trad("`{nom}` est sur la branche par défaut depuis le {date}, mais GitHub ne le connaît "
                              "pas : son cron ne part jamais, et plus rien ne mesure le cliquet. {remede}",
                              nom=nom, date=arrivee[:10], remede=trad(REMEDE_ENREGISTREMENT))
    return "avertir", trad("`{nom}` est sur la branche par défaut depuis le {date}, mais GitHub ne le connaît pas "
                           "encore. {remede}", nom=nom, date=arrivee[:10], remede=trad(REMEDE_ENREGISTREMENT))


def _gh_api(racine: Path, chemin: str) -> tuple[object | None, str]:
    """(réponse, faute) de l'API de GitHub par `gh` ; la faute vaut `404`
    quand la ressource n'existe pas."""
    try:
        p = subprocess.run(["gh", "api", chemin], cwd=racine, capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, type(e).__name__
    if p.returncode != 0:
        return None, "404" if "404" in p.stderr else (p.stderr.strip().splitlines() or [trad("gh a échoué")])[-1]
    try:
        return json.loads(p.stdout), ""
    except ValueError:
        return None, trad("réponse illisible")


def etat_du_balayage(projet: config.Projet, fichiers: list[str],
                     lire: Callable[[str], str | None]) -> tuple[str | None, str, str | None, str | None]:
    """(niveau, message, workflow, page) : le balayage planifié tourne-t-il
    encore ? Le niveau vaut `erreur`, `avertir`, `indisponible`, ou `None`
    quand il tourne, ou quand l'adaptateur ne déclare pas de mutation."""
    from socle import links as liens

    # Un balayage planifié lance les outils de tous les adaptateurs : un
    # workflow qui nomme celui de l'un d'eux compte.
    caps = [c for a in projet.adaptateurs
            if "command" in (c := a.donnees.get("capabilities", {}).get("mutation", {}))]
    if not caps:
        return None, "", None, None
    # Le workflow du socle balaie tous les adaptateurs ; sans lui, chaque
    # outil doit avoir le sien.
    trouves = [workflow_de_balayage(c, fichiers, lire) for c in caps]
    flux = trouves[0] if all(trouves) else None
    if flux is None:
        return "erreur", (trad("aucun workflow ne lance le balayage de mutation : le cliquet ne se mesure "
                               "jamais. Relancer l'installeur, qui pose `{workflow}`", workflow=WORKFLOW)), None, None
    url = liens.url_depot(projet) or ""
    if not url.startswith("https://github.com/"):
        return "indisponible", trad("dépôt hors de GitHub : la vivacité du balayage ne s'y lit pas"), flux, None
    if not shutil.which("gh"):
        return "indisponible", trad("gh absent : la vivacité du balayage ne se lit pas"), flux, None
    depot, nom = url.removeprefix("https://github.com/"), flux.rsplit("/", 1)[-1]
    page = f"{url}/actions/workflows/{nom}"
    wf, faute = _gh_api(projet.racine, f"repos/{depot}/actions/workflows/{nom}")
    if faute == "404":
        return (*inconnu_de_github(nom, arrivee_sur_la_branche_par_defaut(projet.racine, flux)), flux, page)
    if not isinstance(wf, dict):
        return "indisponible", (trad("API de GitHub injoignable ({faute}) : dans la CI, il faut `GH_TOKEN` et "
                                     "le droit `actions: read`", faute=faute)), flux, page
    if wf.get("state") != "active":
        # Endormi : ses exécutions n'y changent rien.
        return (*vivacite(wf.get("state"), None, None), flux, page)
    runs, faute = _gh_api(projet.racine, f"repos/{depot}/actions/workflows/{nom}/runs?per_page=1&status=completed")
    if not isinstance(runs, dict):
        return "indisponible", trad("exécutions du balayage illisibles ({faute})", faute=faute), flux, page
    derniere = next(iter(runs.get("workflow_runs") or []), {}).get("created_at")
    niveau, message = vivacite(wf.get("state"), derniere, wf.get("created_at"))
    return niveau, message, flux, page
