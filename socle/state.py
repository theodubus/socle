"""L'état dérivé : calculé à chaque démarrage de session et après chaque
compactage, jamais écrit à la main.

Tout ce qui est imprimé ici vient de git, de la mémoire ou de la trace des
hooks : rien n'est recopié, donc rien ne peut vieillir. Ce script ne doit
jamais empêcher une session de démarrer : un échec se traduit par une ligne
en moins, jamais par un code non nul.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path
from typing import Callable

from socle import config, requests as demandes, memory as memoire, utils as outils
from socle.messages import a_traduire, trad


def _ligne_ci(racine, branche) -> str:
    """L'état de la CI, si `gh` est là et authentifié. Sinon on le dit : le
    moteur n'exige aucun service externe."""
    if not shutil.which("gh"):
        return trad("non disponible localement (gh absent) — voir la pull request")
    try:
        p = subprocess.run(
            ["gh", "run", "list", "--branch", branche, "--limit", "1",
             "--json", "status,conclusion,workflowName,headSha"],
            cwd=racine, capture_output=True, text=True, timeout=8,
        )
    except (subprocess.TimeoutExpired, OSError):
        return trad("non disponible (gh ne répond pas)")
    if p.returncode != 0 or not p.stdout.strip() or p.stdout.strip() == "[]":
        return trad("non disponible (gh non authentifié ou aucune exécution)")
    import json

    try:
        r = json.loads(p.stdout)[0]
    except (ValueError, IndexError):
        return trad("non disponible (réponse illisible)")
    return trad("{ci} : {etat} sur {sha}", ci=r.get("workflowName"), etat=r.get("conclusion") or r.get("status"),
                sha=r.get("headSha", "")[:7])


def _gh_json(racine, chemin: str):
    """Une réponse de l'API de GitHub par `gh`, ou `None`."""
    import json

    try:
        p = subprocess.run(["gh", "api", chemin], cwd=racine, capture_output=True, text=True, timeout=5)
        return json.loads(p.stdout) if p.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def nom_de_la_ci(projet: config.Projet) -> str:
    """Le nom du travail de la CI du socle, tel que GitHub l'exige."""
    return outils.nom_du_travail(outils.lire_a(projet.racine, None, ".github/workflows/socle.yml") or "") or "Socle"


def ci_exigee(projet: config.Projet) -> tuple[bool | None, str]:
    """La CI du socle est-elle exigée avant de fusionner sur la branche par
    défaut, par un ensemble de règles ou une protection de branche de
    GitHub ? Sans elle, une CI rouge n'empêche pas de fusionner : la
    garantie « seule la CI est incontournable » tombe. `None` quand on ne peut pas le savoir, avec la raison ; sinon
    le nom de la branche, et si la revue des propriétaires du code est
    exigée aussi."""
    from socle import links as liens

    url = liens.url_depot(projet) or ""
    if not url.startswith("https://github.com/"):
        return None, trad("dépôt hors de GitHub")
    nom = (outils.branche_par_defaut(projet.racine) or "").removeprefix("origin/")
    if not nom:
        return None, trad("aucune branche par défaut connue")
    if not shutil.which("gh"):
        return None, trad("gh absent")
    depot = url.removeprefix("https://github.com/")
    regles = _gh_json(projet.racine, f"repos/{depot}/rules/branches/{nom}")
    branche = _gh_json(projet.racine, f"repos/{depot}/branches/{nom}")
    if not isinstance(regles, list) or not isinstance(branche, dict):
        return None, trad("gh non authentifié, ou réponse illisible")
    ci = nom_de_la_ci(projet)
    exigees = [c.get("context") for r in regles if r.get("type") == "required_status_checks"
               for c in (r.get("parameters") or {}).get("required_status_checks", [])]
    classique = ((branche.get("protection") or {}).get("required_status_checks") or {})
    if classique.get("enforcement_level", "off") != "off":
        exigees += classique.get("contexts", []) + [c.get("context") for c in classique.get("checks", [])]
    revue = any((r.get("parameters") or {}).get("require_code_owner_review") for r in regles
                if r.get("type") == "pull_request")
    return ci in exigees, nom + (trad(" ; revue des propriétaires du code exigée") if revue else
                                 trad(" ; revue des propriétaires du code non exigée"))


def _balayage(projet: config.Projet, elements: list) -> list[str]:
    """La ligne du balayage de mutation planifié, quand l'adaptateur en
    déclare un ; endormi ou arrêté, le réveiller revient à l'humain."""
    from socle import human as humain, mutation

    niveau, message, _, page = mutation.etat_du_balayage(
        projet, outils.fichiers_courants(projet.racine), lambda f: outils.lire_a(projet.racine, None, f))
    if not message:
        return []
    if niveau == "erreur":
        elements.append(humain.Element("action", trad("remettre en marche le balayage de mutation : {message}",
                                                      message=message), page or ""))
    return [trad("mutation : {message}", message=message)]


def page_protection(projet: config.Projet) -> str | None:
    """La page des réglages de GitHub où l'humain pose ses ensembles de
    règles (rulesets)."""
    from socle import links as liens

    url = liens.url_depot(projet) or ""
    return f"{url}/settings/rules" if url.startswith("https://github.com/") else None


# La sortie du démarrage (ADR-0071) : chaque groupe a sa part de la borne
# `[startup] max_bytes`, en fraction. 9 500 octets donnent 2 375 à l'état
# dérivé, 3 800 au chantier actif, 2 090 aux faits, 1 235 aux décisions. Le
# budget du chantier actif des garde-fous (3 700 dans le gabarit), que le
# chantier actif public et privé tiennent ensemble (`memoire.budgets`), tient
# dans sa part, leurs en-têtes déduits (`budget_actif_permis`) : un chantier
# actif dans son budget n'est pas coupé.
PARTS = {"etat": 0.25, "actif": 0.40, "faits": 0.22, "decisions": 0.13}
# Une ligne de l'état dérivé, en octets au plus (l'alerte des hooks non
# chargés, la plus longue des lignes fixes, en fait 953) ; une ligne de
# titre (un commit, un fait, une décision), bien moins ; le titre d'un sujet
# du backlog, que sa ligne précède et que sa priorité peut suivre, moins
# encore.
LIGNE = 1000
TITRE = 80
TITRE_DE_SUJET = 70
# Les éléments montrés de chaque liste de l'état dérivé : `socle state
# --short` donne le reste, et la ligne qui compte les autres le dit.
COMMITS_MONTRES = 5
PRETS_MONTRES = 5
ELEMENTS_MONTRES = 4
BASSES_MONTREES = 10
# Le rang de coupe d'un bloc de l'état dérivé : ce qui se relit ailleurs (les
# commits, les listes du backlog) part d'abord, puis ce qui informe ; ce qui
# demande d'agir (l'humain, les lignes du hook), en dernier. À rang égal,
# depuis la fin.
RELU, INFO, ACTION = 0, 1, 2


def budget_actif_permis(projet: config.Projet) -> int:
    """La taille, en octets, que le chantier actif, public et privé
    ensemble, peut avoir sans être coupé au démarrage : sa part de la
    borne, moins leurs deux en-têtes."""
    ch = projet.chemins
    return int(projet.borne_demarrage() * PARTS["actif"]) - _octets(
        ["", f"--- {ch.actif} ---", "", f"--- {ch.dans_prive(ch.actif)} ---"])


def alerte_budget_actif(projet: config.Projet) -> list[str]:
    """Un budget du chantier actif au-dessus de sa part de la sortie du
    démarrage, la borne baissée ou le budget d'un projet installé avant : à
    son budget, le chantier actif y serait coupé à chaque session. L'état le
    redit à chaque démarrage, l'installeur à chaque mise à jour."""
    budget, permis = projet.budget_octets(projet.chemins.actif), budget_actif_permis(projet)
    if budget is None or budget <= permis:
        return []
    return [trad("!! le budget de {chemin} ({budget} octets, public et privé ensemble) dépasse la part du chantier "
                 "actif dans la sortie du démarrage ({permis} octets, en-têtes déduits) : à son budget, il y serait "
                 "coupé à chaque session ; le baisser à {permis} au plus, ce qui durcit et reste libre, et resserrer "
                 "le chantier actif", chemin=projet.chemins.actif, budget=budget, permis=permis)]


def _elements(entete: list[str], elements: list[list[str]], plafond: int | None) -> list[list[str]]:
    """Les blocs insécables d'une liste : chaque élément avec ses lignes (son
    lien), l'en-tête avec le premier, et, au-delà de `plafond`, le nombre des
    autres et où les lire avec le dernier montré. Coupée, la liste perd ses
    éléments depuis la fin, et son en-tête avec le dernier : un en-tête ne
    reste jamais sans ses éléments, ni un élément sans son lien."""
    res = [list(e) for e in elements[:plafond]]
    if not res:
        return [list(entete)] if entete else []
    res[0] = list(entete) + res[0]
    if plafond is not None and len(elements) > plafond:
        res[-1].append(trad("  … et {n} autre(s) : `python3 .socle/socle state --short`", n=len(elements) - plafond))
    return res


def _blocs(lignes: list[str]) -> list[list[str]]:
    """Une ligne par bloc."""
    return [[l] for l in lignes]


def chemin_demarrage(racine: Path) -> Path:
    """Les lignes du dernier hook de démarrage, à côté de la trace des hooks,
    non versionnées."""
    return config.chemin_trace(racine).parent / "startup.json"


def retenir_demarrage(projet: config.Projet, supplement: list[str]) -> None:
    """Garde les lignes que le hook de démarrage ajoute à l'état (les outils
    de l'adaptateur, les hooks git) : `socle state` et `socle state --short`,
    qui ne les calculent pas, les redisent, datées, et la ligne de coupe
    peut y renvoyer. Sans lignes, il n'en reste rien."""
    from datetime import datetime, timezone

    chemin = chemin_demarrage(projet.racine)
    try:
        if not supplement:
            chemin.unlink(missing_ok=True)
            return
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps({"date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "blocs": [str(b) for b in supplement]}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _retenu(projet: config.Projet) -> tuple[str, list[str]] | None:
    """La date et les blocs du dernier hook de démarrage, ou `None`."""
    try:
        d = json.loads(chemin_demarrage(projet.racine).read_text(encoding="utf-8"))
        blocs = [str(b) for b in d["blocs"]]
        return (str(d["date"]), blocs) if blocs else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def calculer(projet: config.Projet, contenus: bool = True, supplement: list[str] | None = None) -> str:
    """L'état du démarrage : l'état dérivé, puis, avec `contenus`, le
    chantier actif, les faits par leur titre et les dix dernières décisions,
    chaque groupe dans sa part de la borne des garde-fous (`[startup]
    max_bytes`, ADR-0071), que Claude Code remet entière à l'agent ; l'état
    dérivé y a ses lignes bornées et ses listes plafonnées. En tête, ce qui
    demande d'agir : ce qui revient à l'humain, les demandes, ce qu'il a
    écrit lui-même, les lignes du hook ; puis ce qui informe, puis le
    backlog. La coupe de l'état retire d'abord ce qui se relit ailleurs.
    `supplement` : les lignes que le hook de démarrage ajoute (les outils de
    l'adaptateur, les hooks git) ; sans, celles de son dernier passage,
    datées. Sans `contenus` (`socle state --short`), l'état dérivé seul,
    entier : ni borne, ni plafond."""
    racine = projet.racine
    blocs: list[tuple[int, list[str]]] = []

    def ajouter(rang: int, groupes: list[list[str]]):
        blocs.extend((rang, b) for b in groupes if b)

    plafond = ELEMENTS_MONTRES if contenus else None
    from socle import hooks, human as humain, private as prive
    from socle.checks_ratchet import REMEDE_HOOKS

    def erreur_(e: Exception) -> str:
        return f"{type(e).__name__}: {e}"

    if hooks.hooks_non_charges(projet):
        # En tête, avant tout le reste : rien de ce qui suit n'est protégé
        # par les hooks de l'agent.
        ajouter(ACTION, [[trad("!! LES HOOKS DE L'AGENT NE SONT PAS CHARGÉS dans cette session : aucun n'a tiré "
                               "pour elle récemment, ni au démarrage ni avant cette commande (une session reprise hors "
                               "de la racine du projet garde ses traces d'avant). Ni le filtre des commandes, ni les "
                               "contrôles de fin de tour, ni l'état au démarrage ne tournent. Le dire à l'humain avant "
                               "tout travail. {remede}", remede=trad(REMEDE_HOOKS)), ""]])
    ajouter(ACTION, [[trad("== {nom} — état dérivé par `socle state`, rien de recopié ==", nom=racine.name)]])
    # Ce qui revient à l'humain : chaque calcul a son repli, et les demandes
    # en attente se disent quoi qu'il arrive aux autres.
    elements, erreur = None, ""
    try:
        elements = humain.a_faire(projet)
    except Exception as e:  # l'état ne bloque jamais le démarrage
        erreur = erreur_(e)
    autres, branche, mutation = [], [], []
    try:
        exigee, detail = ci_exigee(projet)
        # Le détail commence par le nom de la branche, suivi de ce que dit la
        # revue des propriétaires du code.
        nom = (outils.branche_par_defaut(racine) or "").removeprefix("origin/")
        revue = detail[len(nom):] if nom and detail.startswith(nom) else ""
        if exigee is False:
            autres.append(humain.Element(
                "action", trad("protéger la branche `{nom}` : y exiger la CI « {ci} » avant toute fusion", nom=nom,
                               ci=nom_de_la_ci(projet)),
                page_protection(projet) or ""))
        if exigee:
            branche = [trad("branche  : {nom} — CI du socle exigée avant fusion{revue}", nom=nom, revue=revue)]
        elif exigee is False:
            branche = [trad("branche  : {nom} — CI du socle NON exigée : une CI rouge n'empêche pas de fusionner",
                            nom=nom)]
        else:
            branche = [trad("branche  : protection inconnue ({detail})", detail=detail)]
    except Exception as e:
        branche = [trad("branche  : protection inconnue ({detail})", detail=erreur_(e))]
    try:
        mutation = _balayage(projet, autres)
    except Exception as e:
        mutation = [trad("mutation : état inconnu ({erreur})", erreur=erreur_(e))]
    if elements is not None:
        elements += autres
        entete = [trad("ce qui revient à l'humain : {n}", n=len(elements))] if elements else \
            [trad("ce qui revient à l'humain : rien")]
        ajouter(ACTION, _elements(entete, [humain.lignes(e) for e in elements], plafond))
    else:
        ajouter(ACTION, _elements([trad("ce qui revient à l'humain : incalculable ({erreur})", erreur=erreur)],
                                  [humain.lignes(e) for e in autres], plafond))
    try:
        ajouter(ACTION, _demandes(projet, plafond, dites=elements is not None))
    except Exception as e:
        ajouter(ACTION, [[trad("demandes : illisibles ({erreur})", erreur=erreur_(e))]])
    try:
        faits = humain.fait_par_l_humain(projet)
        if faits:
            ajouter(ACTION, _elements([trad("écrit par l'humain lui-même depuis le dernier commit de l'agent : {n} — à "
                                            "lui citer, avec le lien", n=len(faits))],
                                      [humain.lignes(e) for e in faits], plafond))
    except Exception as e:
        ajouter(ACTION, [[trad("ce que l'humain a écrit lui-même : incalculable ({erreur})", erreur=erreur_(e))]])
    # Les lignes du hook, chaque bloc insécable (un échec avec sa sortie).
    if supplement is not None:
        ajouter(ACTION, [str(b).strip("\n").splitlines() for b in supplement])
    else:
        retenu = _retenu(projet)
        if retenu:
            ajouter(ACTION, _elements(
                [trad("au dernier démarrage de session ({date}), le hook a ajouté :", date=retenu[0])],
                [[f"  {l}" for l in b.strip("\n").splitlines()] for b in retenu[1]], None))
    try:
        ajouter(ACTION, _blocs(audit_adaptateur(projet)))
    except Exception as e:
        ajouter(ACTION, [[trad("adaptateur : audit impossible ({erreur})", erreur=erreur_(e))]])
    ajouter(ACTION, _blocs(alerte_budget_actif(projet)))
    # Ce qui informe.
    try:
        blocs.extend(_git(racine, projet, borne=contenus))
    except outils.ErreurGit as e:
        ajouter(INFO, [[trad("git : indisponible ({erreur})", erreur=e)]])
    ajouter(INFO, _blocs(branche + mutation))
    mem, backlog = None, []
    try:
        mem = memoire.Memoire.charger(racine)
        ajouter(INFO, _blocs(_memoire(mem, projet)))
        backlog = _backlog(mem, borne=contenus)
    except Exception as e:
        ajouter(INFO, [[trad("mémoire : illisible ({erreur}) — lancer `python3 .socle/socle check`",
                             erreur=erreur_(e))]])
    ajouter(INFO, _blocs(_hooks(racine)))
    try:
        from socle import context as contexte

        ajouter(INFO, _blocs(contexte.bilan_adoption(projet)))
    except Exception as e:
        ajouter(INFO, [[trad("adoption : illisible ({erreur})", erreur=erreur_(e))]])
    ajouter(INFO, [[prive.ligne_etat(projet)]])
    blocs.extend(backlog)
    ajouter(INFO, [[trad("vérifier : `python3 .socle/socle verify --fast` (tout : sans `--fast`)")]])
    if not contenus:
        return "\n".join(l for _, b in blocs for l in b)
    etat = Partie("etat", [outils.raccourcir(l, LIGNE) for _, b in blocs for l in b],
                  lambda n, total: trad("{n} ligne(s) sur {total} ; l'état entier : `python3 .socle/socle state "
                                        "--short`", n=n, total=total),
                  unites=[len(b) for _, b in blocs],
                  ordre=sorted(range(len(blocs)), key=lambda k: (blocs[k][0], -k)))
    return "\n".join(borner([etat, *parties_injectees(projet, mem)], projet.borne_demarrage()))


def _sans_entete(montrees: int, total: int) -> list[str]:
    return []


@dataclass
class Partie:
    """Une partie de la sortie du démarrage : le groupe dont elle partage la
    part de la borne (`PARTS`), ses lignes, ce que dit la coupe quand elle en
    retire `n` sur `total`, et son en-tête selon les lignes montrées. Ses
    blocs insécables, `unites`, en nombre de lignes, dans l'ordre (une ligne
    chacun à défaut) ; l'ordre dans lequel la coupe les retire, `ordre`
    (depuis la fin à défaut)."""

    groupe: str
    lignes: list[str]
    manque: Callable[[int, int], str]
    entete: Callable[[int, int], list[str]] = _sans_entete
    unites: list[int] | None = None
    ordre: list[int] | None = None


# Les décisions que le démarrage injecte ; l'index entier se lit à la demande.
DERNIERES_DECISIONS = 10
# Ce que dit la ligne de coupe de chaque groupe.
GROUPES = {"etat": a_traduire("l'état dérivé"), "actif": a_traduire("le chantier actif"),
           "faits": a_traduire("les faits"), "decisions": a_traduire("les décisions")}


def ligne_de_titre(ident: str, titre: str, suffixe: str = "") -> str:
    """`ID — titre (suffixe)`, en `TITRE` octets au plus : le titre se
    raccourcit, l'identifiant et le suffixe restent."""
    debut = f"{ident} — "
    place = TITRE - len(debut.encode("utf-8")) - len(suffixe.encode("utf-8"))
    return debut + outils.raccourcir(titre, max(place, 3)) + suffixe


def parties_injectees(projet: config.Projet, mem: memoire.Memoire | None) -> list[Partie]:
    """Le chantier actif, public puis privé, entier ; les faits par leur
    titre, publics puis privés, le statut dit quand il n'est pas « mesuré » ;
    les dix dernières décisions, la plus récente d'abord, le statut dit
    quand elle n'est pas acceptée ; les titres raccourcis, les statuts dans
    la langue du projet. Une mémoire privée illisible ici n'en donne rien :
    l'état dérivé le dit plus haut."""
    from socle import language as langue

    racine, ch = projet.racine, projet.chemins
    lg = langue.du_projet(projet)
    res = []
    for chemin in (ch.actif, ch.dans_prive(ch.actif)):
        texte = outils.lire_a(racine, None, chemin)
        if not texte or not texte.strip() or (memoire.est_prive(chemin) and not memoire.lisible(texte)):
            continue
        res.append(Partie("actif", texte.rstrip().splitlines(),
                          lambda n, total, c=chemin: trad("la fin du chantier actif, {n} ligne(s) sur {total} : lire "
                                                          "{chemin}", n=n, total=total, chemin=c),
                          lambda montrees, total, c=chemin: ["", f"--- {c} ---"]))
    if mem is None:
        return res

    def statut(e: memoire.Entree, attendu: str) -> str:
        if e.statut == attendu:
            return ""
        table = langue.STATUTS.get(e.type, {})
        libelle = langue.mot(table, e.statut, lg) if e.statut in table else memoire.nettoyer(e.meta.get("statut", ""))
        return f" ({libelle})"

    for chemin in (ch.canonique, ch.dans_prive(ch.canonique)):
        f = mem.fichiers.get(chemin)
        faits = [e for e in (f.entrees if f else []) if e.type == "F" and not e.archivee and not e.basculee]
        if not faits:
            continue
        res.append(Partie(
            "faits", [ligne_de_titre(e.id, e.titre, statut(e, "mesure")) for e in faits],
            lambda n, total, c=chemin: trad("{n} fait(s) sur {total} : lire {chemin}", n=n, total=total, chemin=c),
            lambda montrees, total, c=chemin: ["", trad(
                "--- {chemin} : {n} fait(s) par leur titre ; un en entier : `python3 .socle/socle show F-NNNN` ---",
                chemin=c, n=montrees) if montrees == total else trad(
                "--- {chemin} : {n} fait(s) sur {total} par leur titre ; un en entier : `python3 .socle/socle show "
                "F-NNNN` ---", chemin=c, n=montrees, total=total)]))
    decisions = [e for e in mem.entrees("ADR") if not e.archivee and not e.basculee]
    if decisions:
        # Les plus récentes : par date, puis par numéro (une décision privée
        # a sa propre suite de numéros).
        decisions.sort(key=lambda e: (e.meta.get("date", ""), e.id.rsplit("-", 1)[-1], e.prive), reverse=True)
        nombre = len(decisions)
        res.append(Partie(
            "decisions", [ligne_de_titre(e.id, e.titre, statut(e, "acceptee"))
                          for e in decisions[:DERNIERES_DECISIONS]],
            lambda n, total: trad("{n} des {total} dernières décisions : `python3 .socle/socle show --index "
                                  "decisions`", n=n, total=total),
            lambda montrees, total: ["", trad(
                "--- la dernière décision sur {total} ; avant toute décision de conception, l'index entier : "
                "`python3 .socle/socle show --index decisions` ---", total=nombre) if montrees == 1 else trad(
                "--- les {n} dernières décisions sur {total}, la plus récente d'abord ; avant toute décision de "
                "conception, l'index entier : `python3 .socle/socle show --index decisions` ---",
                n=montrees, total=nombre)]))
    return res


def _octets(lignes: list[str]) -> int:
    """La taille, en octets UTF-8, de ces lignes imprimées, chacune suivie
    de son saut de ligne : les octets majorent les unités UTF-16 que
    compte Claude Code."""
    return sum(len(l.encode("utf-8")) + 1 for l in lignes)


def borner(parties: list[Partie], borne: int) -> list[str]:
    """Les parties, en `borne` octets au plus, sauts de ligne compris. Chaque
    groupe a sa part de la borne (`PARTS`) ; ce qu'un groupe laisse de sa
    part, ou libère en coupant par blocs entiers, va à ceux qui dépassent la
    leur, dans l'ordre, jusqu'à ce que rien ne change. Un groupe au-delà de
    ce qui lui revient perd des blocs entiers dans l'ordre de ses parties
    (depuis la fin à défaut), un en-tête avec la dernière ligne qu'il
    annonce : jamais une partie ne mange la part d'une autre. Une dernière
    ligne dit ce qui est coupé, de quel groupe, sa taille pour sa part, et
    où lire le reste : jamais en silence, jamais au milieu d'une ligne. La
    place de cette ligne se prend sur les groupes coupés. Les tailles se
    tiennent à jour bloc par bloc : linéaire en lignes."""
    n = len(parties)
    unites = [p.unites if p.unites is not None else [1] * len(p.lignes) for p in parties]
    ordres = [p.ordre if p.ordre is not None else list(range(len(u) - 1, -1, -1)) for p, u in zip(parties, unites)]
    debuts = [list(accumulate(u, initial=0))[:-1] for u in unites]
    poids = [[_octets(p.lignes[d:d + k]) for d, k in zip(debuts[i], unites[i])] for i, p in enumerate(parties)]
    retirees = [0] * n  # les blocs retirés de chaque partie : `ordres[i][:retirees[i]]`
    montrees = [len(p.lignes) for p in parties]
    corps = [sum(w) for w in poids]
    groupes = list(dict.fromkeys(p.groupe for p in parties))
    membres = {g: [i for i, p in enumerate(parties) if p.groupe == g] for g in groupes}

    def taille(i: int) -> int:
        p = parties[i]
        return corps[i] + _octets(p.entete(montrees[i], len(p.lignes))) if montrees[i] else 0

    def taille_groupe(g: str) -> int:
        return sum(taille(i) for i in membres[g])

    def retirer(g: str) -> bool:
        """Le bloc suivant du groupe, dans sa dernière partie qui en montre."""
        for i in reversed(membres[g]):
            if retirees[i] < len(unites[i]):
                u = ordres[i][retirees[i]]
                retirees[i] += 1
                corps[i] -= poids[i][u]
                montrees[i] -= unites[i][u]
                return True
        return False

    def remettre(g: str) -> bool:
        """Le dernier bloc retiré du groupe : l'inverse exact de `retirer`."""
        for i in membres[g]:
            if retirees[i]:
                retirees[i] -= 1
                u = ordres[i][retirees[i]]
                corps[i] += poids[i][u]
                montrees[i] += unites[i][u]
                return True
        return False

    def coupe(g: str) -> bool:
        return any(retirees[i] for i in membres[g])

    part = {g: int(borne * PARTS.get(g, 0)) for g in groupes}
    demande = {g: taille_groupe(g) for g in groupes}

    def segment(g: str) -> str:
        """Ce que la ligne de coupe dit du groupe : sa taille pour sa part,
        ce qui en est coupé, où le lire."""
        coupees = ", ".join(parties[i].manque(len(parties[i].lignes) - montrees[i], len(parties[i].lignes))
                            for i in membres[g] if retirees[i])
        return trad("{groupe}, {demande} octets pour une part de {part} — {coupees}",
                    groupe=trad(GROUPES.get(g, g)), demande=demande[g], part=part[g], coupees=coupees)

    def place(g: str) -> int:
        """Ce qu'occupe le groupe : ses lignes, et ce que la coupe dit de lui."""
        return taille_groupe(g) + (len(segment(g).encode("utf-8")) + len(" ; ") if coupe(g) else 0)

    def note() -> list[str]:
        manque = [segment(g) for g in groupes if coupe(g)]
        if not manque:
            return []
        return [trad("!! coupé à la borne du démarrage ({borne} octets, `[startup] max_bytes` des garde-fous) : "
                     "{manque}", borne=borne, manque=" ; ".join(manque))]

    def total() -> int:
        return sum(taille(i) for i in range(n)) + _octets(note())

    # Chaque groupe dans sa part ; ce que laissent ceux qui tiennent dans la
    # leur, et ce qu'un groupe coupé n'emploie pas, va aux suivants qui
    # dépassent.
    reste = borne - sum(min(demande[g], part[g]) for g in groupes)
    for g in groupes:
        if demande[g] <= part[g]:
            continue
        limite = part[g] + max(reste, 0)
        while place(g) > limite and retirer(g):
            pass
        reste = limite - place(g)
    # Le début de la ligne de coupe, sur ce qui reste de la borne, ou sur les
    # groupes coupés, le dernier d'abord.
    while total() > borne:
        if not any(retirer(g) for g in reversed(groupes) if coupe(g)) and \
                not any(retirer(g) for g in reversed(groupes)):
            break
    # Ce qui reste libre revient aux groupes coupés, dans l'ordre, jusqu'à ce
    # que rien ne change.
    change = True
    while change:
        change = False
        for g in groupes:
            while coupe(g):
                remettre(g)
                if total() > borne:
                    retirer(g)
                    break
                change = True
    res = []
    for i, p in enumerate(parties):
        if not montrees[i]:
            continue
        res += p.entete(montrees[i], len(p.lignes))
        gardes = set(ordres[i][retirees[i]:])
        res += [l for u, (d, k) in enumerate(zip(debuts[i], unites[i])) if u in gardes for l in p.lignes[d:d + k]]
    fin = note()
    if fin:
        # Une borne plus petite que la ligne de coupe : elle, raccourcie à
        # ce qui reste.
        fin = [outils.raccourcir(fin[0], max(0, borne - _octets(res) - 1))]
    return res + fin


def audit_adaptateur(projet: config.Projet) -> list[str]:
    """L'audit de l'adaptateur, à chaque état : un langage dont le
    dépôt porte un fichier marqueur, et que l'adaptateur ne couvre pas, voit
    son code échapper aux capacités ; la décision revient à l'humain."""
    from socle import installer as installeur

    couverts = [str(a.donnees["language"]) for a in projet.adaptateurs if a.donnees.get("language")]
    if not couverts:
        return []
    couvert = ", ".join(couverts)
    presents = installeur.langages_presents(projet.hors_tiers(outils.fichiers_courants(projet.racine)))
    autres = {l: f for l, f in presents.items() if l not in couverts}
    if not autres:
        return []
    liste = ", ".join(f"{l} ({', '.join(f[:2])}{' …' if len(f) > 2 else ''})" for l, f in sorted(autres.items()))
    return [trad("adaptateur : !! langage(s) que l'adaptateur ({couvert}) ne couvre pas : {liste} — leurs tests, leur "
                 "compilation et leur mutation ne passent par aucune capacité ; le dire à l'humain par une demande "
                 "(un autre adaptateur, ou ces fichiers déclarés tiers)", couvert=couvert, liste=liste)]


def _git(racine, projet, borne: bool = False) -> list[tuple[int, list[str]]]:
    """Le commit, la base et ce qui n'y est pas fusionné, la CI, en blocs de
    l'état avec leur rang de coupe ; avec `borne`, les commits plafonnés et
    leur sujet raccourci. Leur liste se relit (`socle state --short`) : elle
    part la première."""
    if not outils.est_depot(racine) or not outils.a_des_commits(racine):
        return [(INFO, [trad("commit   : aucun (dépôt neuf)")])]
    res = []
    court = outils.git(racine, "rev-parse", "--short", "HEAD").strip()
    branche = outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD").strip()
    sales = [l for l in outils.git(racine, "status", "--porcelain").splitlines() if l.strip()]
    propre = trad("arbre propre") if not sales else trad("ATTENTION, {n} fichier(s) non commité(s)", n=len(sales))
    res.append((INFO, [trad("commit   : {sha} sur {branche} ({propre})", sha=court, branche=branche, propre=propre)]))
    defaut = outils.branche_par_defaut(racine)
    if defaut:
        non = outils.git(racine, "log", "--oneline", f"{defaut}..HEAD", check=False).splitlines()
        res.append((INFO, [trad("base     : {defaut} — non fusionné : {n} commit(s)", defaut=defaut, n=len(non))]))
        if outils.branche_par_defaut_devinee(racine):
            res.append((INFO, [trad("  ^ devinée : ce clone n'a ni `origin/HEAD`, ni `main`, ni `master` ; si la "
                                    "branche par défaut du dépôt distant est une autre, `git fetch origin <elle>` la "
                                    "fait connaître")]))
        res += [(RELU, b) for b in _elements([], [[outils.raccourcir(f"  {l}", TITRE) if borne else f"  {l}"]
                                                   for l in non], COMMITS_MONTRES if borne else None)]
        base = outils.base_de_travail(racine)
        if base:
            changes = projet.hors_tiers(outils.fichiers_changes(racine, base))
            code = outils.filtrer(changes, projet.chemins_code())
            docs = [c for c in changes if c.endswith(".md")]
            mem = [c for c in changes if memoire.est_memoire(c)]
            res.append((INFO, [trad("depuis la base : {code} fichier(s) de code, {docs} de doc, {memoire} de mémoire",
                                    code=len(code), docs=len(docs), memoire=len(mem))]))
            if code and not mem:
                res.append((INFO, [trad("  ^ du code a changé et la mémoire non : la fin de tour le refusera")]))
    else:
        res.append((INFO, [trad("base     : aucune branche par défaut connue")]))
    res.append((INFO, [trad("CI       : {ci}", ci=_ligne_ci(racine, branche))]))
    return res


def _memoire(mem: memoire.Memoire, projet) -> list[str]:
    faits = Counter(e.statut or "?" for e in mem.entrees("F") if not e.archivee)
    libelles = {"mesure": a_traduire("mesuré(s)"), "suppose": a_traduire("supposé(s)"),
                "refute": a_traduire("réfuté(s)"), "valide": a_traduire("validé(s)")}
    detail = ", ".join(f"{n} {trad(libelles[s]) if s in libelles else s}" for s, n in sorted(faits.items()))
    adrs = list(mem.entrees("ADR"))
    journal = sorted((e.id for e in mem.entrees("J")), key=lambda i: i.lstrip("P"))
    res = [
        trad("mémoire  : {faits} fait(s) ({detail}) · {adrs} décision(s) · journal : {journal} entrée(s), dernière "
             "{dernier}", faits=sum(faits.values()), detail=detail or trad("aucun"), adrs=len(adrs),
             journal=len(journal), dernier=journal[-1] if journal else "—")
    ]
    # L'index des décisions, que le cadrage prévoit, ne s'injecte plus en
    # entier : les dix dernières suivent les faits, et l'index se lit par
    # `socle show --index decisions`, qui en donne l'empreinte (ADR-0071).
    jours = projet.gf("staleness", "active_days", defaut=7)
    t = outils.git(mem.racine, "log", "-1", "--format=%ct", "--", config.FORMAT_ACTUEL.actif, check=False).strip() \
        if outils.a_des_commits(mem.racine) else ""
    if t:
        age = (time.time() - float(t)) / 86400
        if age > jours:
            res.append(trad("péremption : chantier actif inchangé depuis {age} jours (seuil {jours})",
                            age=f"{age:.0f}", jours=jours))
    return res


def _backlog(mem: memoire.Memoire, borne: bool = False) -> list[tuple[int, list[str]]]:
    """Le backlog, en blocs de l'état avec leur rang de coupe : ses comptes,
    puis ce qui est en cours ou bloqué, et ce qui vient ensuite, qui se
    relisent (`socle show --index backlog`) et partent les premiers ; avec
    `borne`, chaque liste plafonnée et les titres raccourcis."""
    backlog = [e for e in mem.entrees("B") if not e.archivee]
    par = Counter(e.statut for e in backlog)
    res = [(INFO, [trad("backlog  : {ouverts} ouvert(s), {en_cours} en cours, {bloques} bloqué(s), {clos} clos",
                        ouverts=par.get("ouvert", 0), en_cours=par.get("en-cours", 0),
                        bloques=par.get("bloque", 0), clos=par.get("fait", 0) + par.get("abandonne", 0))])]
    titre = TITRE_DE_SUJET if borne else None
    for statut, libelle in (("en-cours", a_traduire("en cours")), ("bloque", a_traduire("bloqué"))):
        res += [(RELU, b) for b in _elements([], [[f"  {trad(libelle)} : {e.id} — "
                                                   f"{outils.raccourcir(e.titre, titre) if titre else e.titre}"]
                                                  for e in backlog if e.statut == statut],
                                             PRETS_MONTRES if borne else None)]
    res += [(RELU, [f"  {l}"]) for l in memoire.lignes_ordre(mem, plafond=PRETS_MONTRES if borne else None,
                                                             titre=titre, basses=BASSES_MONTREES if borne else None)]
    return res


def _demandes(projet: config.Projet, plafond: int | None = None, dites: bool = True) -> list[list[str]]:
    """Les demandes en attente, en blocs de l'état : leur nombre ; une
    lisible se dit sous « ce qui revient à l'humain », avec son lien, quand
    il se calcule (`dites`), et ici sinon, avec son lien ; une illisible se
    dit ici, telle, par son chemin. Puis les demandes renvoyées. Au-delà de
    `plafond`, le nombre des autres et où les lire."""
    from socle import human as humain, links as liens

    toutes = demandes.toutes(projet.racine)
    attente = [d for d in toutes if d.reponse is None and d.statut == "en attente"]

    def lien(d) -> str:
        try:
            return liens.lien(projet, d.chemin)[0] or trad("(pas encore poussée : pas de lien)")
        except Exception:
            return ""

    if dites and any(d.entree for d in attente):
        entete = [trad("demandes humaines en attente : {n} — sous « ce qui revient à l'humain », avec leur lien",
                       n=len(attente))]
        ici = [d for d in attente if not d.entree]
    else:
        entete = [trad("demandes humaines en attente : {n}", n=len(attente))]
        ici = attente
    res = _elements(entete, [humain.lignes(humain.Element("décision", f"{d.id} — {d.entree.titre}", lien(d)))
                             if d.entree else
                             [trad("  illisible : {chemin} — `python3 .socle/socle check` dit pourquoi",
                                   chemin=d.chemin)] for d in ici], plafond)
    res += _elements([], [[trad("  RENVOYÉE (contexte insuffisant) : {id} — à réécrire en une demande qui la "
                                "remplace", id=d.id)] for d in toutes if d.statut == "renvoyée"], plafond)
    return res


def _hooks(racine) -> list[str]:
    lignes = config.lire_trace(racine)
    if not lignes:
        return [trad("hooks    : aucune trace — ils n'ont encore jamais tiré dans ce clone")]
    dernier = " ".join(lignes[-1].split("\t")[:2])
    return [trad("hooks    : {n} déclenchement(s) tracé(s), dernier : {dernier}", n=len(lignes), dernier=dernier)]

