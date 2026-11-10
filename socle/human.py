"""Ce qui revient à l'humain : les décisions qu'il doit prendre et les actions
que lui seul peut faire.

Trois sources, toutes dérivées, rien de recopié :
- les demandes en attente de réponse (décisions) ;
- les entrées du backlog marquées `pour : humain` (actions déclarées : un
  réglage de GitHub, un fichier à fournir, une action que le hook refuse à
  l'agent) ;
- ce qui se calcule : les branches distantes que la branche par défaut,
  ou la branche de travail poussée, contient en entier, donc supprimables
  sans rien perdre — une action distante que le hook refuse à l'agent.

La liste sert deux fois : dans l'état dérivé au démarrage, et dans le récap
que le hook de fin de tour exige quand l'agent a agi.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from socle import config, requests as demandes, language as langue, links as liens, memory as memoire, utils as outils
from socle.messages import a_traduire, trad

# Les lignes qu'un récap de fin d'intervention doit contenir : ce qui revient
# à l'humain, puis la suite ; en gras
# (`**Pour toi** :`) aussi.
MARQUEURS_RECAP = {
    "Pour toi :": r"(?im)^[\W_]*pour toi[\s*_]*:",
    "Ensuite :": r"(?im)^[\W_]*ensuite[\s*_]*:",
}
# Les mêmes, quand la mémoire du projet est en anglais.
MARQUEURS_RECAP_EN = {
    "For you:": r"(?im)^[\W_]*for you[\s*_]*:",
    "Next:": r"(?im)^[\W_]*next[\s*_]*:",
}


# Le genre d'un élément, dit dans la langue du projet à l'affichage.
GENRES = {"décision": a_traduire("décision"), "action": a_traduire("action"), "réponse": a_traduire("réponse")}


@dataclass
class Element:
    genre: str  # « décision », « action » ou « réponse »
    quoi: str
    lien: str = ""  # où l'humain le lit, quand c'est un fichier poussé


def branches_a_supprimer(projet: config.Projet) -> list[str]:
    """Les branches distantes que la branche par défaut contient en entier :
    jamais la branche par défaut, ni la branche de travail, ni celles que la
    politique garde (`[human] keep_branches`). Calculé sur le dernier fetch."""
    racine = projet.racine
    defaut = outils.branche_par_defaut(racine)
    if not defaut or not defaut.startswith("origin/"):
        return []
    courante = outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
    garder = projet.pol("human", "keep_branches", defaut=[]) or []
    res = []
    refs = outils.git(racine, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", check=False)
    for ref in refs.split():
        nom = ref.removeprefix("origin/")
        if ref in ("origin", "origin/HEAD", defaut) or nom == courante or outils.correspond(nom, garder):
            continue
        absents = outils.git(racine, "rev-list", "--count", f"{defaut}..{ref}", check=False).strip()
        if absents == "0":
            res.append(nom)
    return sorted(res)


def branches_contenues_dans_le_travail(projet: config.Projet) -> list[tuple[str, str]]:
    """Les branches distantes que la branche de travail poussée contient en
    entier, sans que la branche par défaut les contienne : (nom, branche
    poussée qui les contient). Leur contenu est déjà sur le distant, dans
    la branche de travail : les supprimer ne le perd pas (B-0145). Mêmes
    exceptions que `branches_a_supprimer`, et calculé comme elle sur le
    dernier fetch. Une branche de travail jetable, qu'on ne fusionne pas,
    n'en garde aucune (D-0087) ; une branche au même sommet qu'elle n'est
    pas dite, chacune contenant l'autre."""
    racine = projet.racine
    defaut = outils.branche_par_defaut(racine)
    courante = outils.branche_courante(racine)
    if not defaut or not defaut.startswith("origin/") or not courante or projet.branche_jetable(courante):
        return []
    poussee = f"origin/{courante}"
    if not outils.rev_existe(racine, poussee):
        return []
    garder = projet.pol("human", "keep_branches", defaut=[]) or []
    res = []
    refs = outils.git(racine, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin", check=False)
    for ref in refs.split():
        nom = ref.removeprefix("origin/")
        if ref in ("origin", "origin/HEAD", defaut, poussee) or outils.correspond(nom, garder):
            continue
        hors_defaut = outils.git(racine, "rev-list", "--count", f"{defaut}..{ref}", check=False).strip()
        hors_travail = outils.git(racine, "rev-list", "--count", f"{poussee}..{ref}", check=False).strip()
        travail_en_plus = outils.git(racine, "rev-list", "--count", f"{ref}..{poussee}", check=False).strip()
        if hors_defaut not in ("", "0") and hors_travail == "0" and travail_en_plus not in ("", "0"):
            res.append((nom, poussee))
    return sorted(res)


# Au-delà, une branche non fusionnée qui ne bouge plus se signale (B-0112).
JOURS_INACTIVITE = 7


def branches_inactives(projet: config.Projet, jours: int = JOURS_INACTIVITE,
                       maintenant: float | None = None) -> list[tuple[str, int, int]]:
    """Les branches distantes que la branche par défaut ne contient pas, sans
    commit depuis `jours` jours : (nom, commits absents, jours d'inactivité).
    Leur travail est peut-être à livrer, peut-être à abandonner : l'humain en
    décide. Mêmes exceptions que `branches_a_supprimer` ; calculé sur le
    dernier fetch."""
    import time

    racine = projet.racine
    defaut = outils.branche_par_defaut(racine)
    if not defaut or not defaut.startswith("origin/"):
        return []
    maintenant = time.time() if maintenant is None else maintenant
    courante = outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
    garder = projet.pol("human", "keep_branches", defaut=[]) or []
    res = []
    refs = outils.git(racine, "for-each-ref", "--format=%(refname:short) %(committerdate:unix)",
                      "refs/remotes/origin", check=False)
    for ligne in refs.splitlines():
        ref, _, date = ligne.partition(" ")
        nom = ref.removeprefix("origin/")
        if ref in ("origin", "origin/HEAD", defaut) or nom == courante or outils.correspond(nom, garder):
            continue
        absents = int(outils.git(racine, "rev-list", "--count", f"{defaut}..{ref}", check=False).strip() or 0)
        age = int((maintenant - int(date or maintenant)) // 86400)
        if absents and age >= jours:
            res.append((nom, absents, age))
    return sorted(res)


def commits_cites(projet: config.Projet) -> set[str]:
    """Les SHA que la mémoire cite sous la forme `commit:`."""
    res = set()
    for f in memoire.Memoire.charger(projet.racine).fichiers.values():
        for type_, cible in memoire.references(f.texte):
            if type_ == "commit" and re.fullmatch(r"[0-9a-f]{7,40}", cible):
                res.add(cible)
    return res


def commits_cites_seuls(projet: config.Projet, branche: str, cites: set[str] | None = None) -> list[str]:
    """Les commits que la mémoire cite et que seule la branche distante
    `branche` garde : ni la branche par défaut, ni une autre branche, ni une
    étiquette, ni une pull request de l'origine ne les contient. La supprimer
    les ôterait à la CI, dont le clone ne les retrouverait plus : c'est
    arrivé à ce dépôt le 1er novembre (B-0116)."""
    racine = projet.racine
    defaut = outils.branche_par_defaut(racine)
    if not defaut:
        return []
    ref = f"refs/remotes/origin/{branche}"
    propres = outils.git(racine, "rev-list", f"{defaut}..{ref}", check=False).split()
    cites = commits_cites(projet) if cites is None else cites
    candidats = [(sha, c) for sha in sorted(cites) for c in propres if c.startswith(sha)]
    if not candidats:
        return []
    # Une pull request garde ses commits, que la CI va chercher (B-0117).
    outils.recuperer_pull_requests(racine)
    res = []
    for sha, complet in candidats:
        gardiens = outils.git(racine, "for-each-ref", "--contains", complet, "--format=%(refname)",
                              "refs/remotes/origin", "refs/tags", "refs/socle/pull", check=False).split()
        if not [g for g in gardiens if g not in (ref, "refs/remotes/origin/HEAD")]:
            res.append(sha)
    return res


# Les réponses qui n'approuvent pas ce qu'une demande soumet.
NON_APPROBATIONS = ("refuser", "contexte-insuffisant")


def specifications_non_soumises(projet: config.Projet, toutes: list | None = None) -> list[str]:
    """Les spécifications que le projet déclare (`[specs] paths` des
    garde-fous) et qu'aucune demande ne soumet à l'humain : ni en attente,
    ni approuvée (D-0066). Le pilote avait écrit le code de deux d'entre
    elles sans que l'humain les ait vues."""
    motifs = projet.gf("specs", "paths", defaut=[]) or []
    if not motifs:
        return []
    textes = [d.texte for d in (demandes.toutes(projet.racine) if toutes is None else toutes)
              if d.reponse is None or langue.reponse(str(d.reponse.get("reponse", ""))) not in NON_APPROBATIONS]
    return [c for c in outils.filtrer(outils.fichiers_courants(projet.racine), motifs)
            if not any(c in t for t in textes)]


def a_faire(projet: config.Projet) -> list[Element]:
    res = []
    toutes = demandes.toutes(projet.racine)
    for d in toutes:
        if d.reponse is None and d.statut == "en attente" and d.entree:
            url, _ = liens.lien(projet, d.chemin)
            res.append(Element("décision", f"{d.id} — {d.entree.titre}", url or trad("(pas encore poussée : pas de lien)")))
    for c in specifications_non_soumises(projet, toutes):
        url, _ = liens.lien(projet, c)
        res.append(Element("action", trad("approuver la spécification `{chemin}` : aucune demande ne vous l'a "
                                          "soumise ; l'agent la soumet", chemin=c), url or ""))
    mem = memoire.Memoire.charger(projet.racine)
    for e in mem.entrees("B"):
        if e.archivee or e.statut in memoire.BACKLOG_CLOS:
            continue
        if langue.valeur(memoire.nettoyer(e.meta.get("pour", ""))) == "humain":
            # Le lien du sujet, où vit son mode d'emploi : commandes,
            # résultats attendus.
            url, _ = liens.lien(projet, e.id)
            res.append(Element("action", f"{e.id} — {e.titre}", url or trad("(pas encore poussé : pas de lien)")))
    depot = liens.url_depot(projet)
    page = f"{depot}/branches" if depot else ""
    for b in branches_a_supprimer(projet):
        res.append(Element("action", trad("supprimer la branche distante `{branche}`, déjà contenue dans la branche "
                                          "par défaut", branche=b), page))
    contenues = branches_contenues_dans_le_travail(projet)
    for b, poussee in contenues:
        res.append(Element("action", trad("supprimer la branche distante `{branche}`, déjà contenue dans `{travail}`, "
                                          "la branche de travail poussée : son contenu ne se perd pas ; une pull "
                                          "request ouverte qui en part se fermerait avec elle", branche=b,
                                          travail=poussee), page))
    dites = {b for b, _ in contenues}
    inactives = [i for i in branches_inactives(projet) if i[0] not in dites]
    cites = commits_cites(projet) if inactives else set()
    for b, absents, age in inactives:
        seuls = commits_cites_seuls(projet, b, cites)
        if seuls:
            res.append(Element("action", trad(
                "examiner la branche distante `{branche}` : {n} commit(s) absents de la branche par défaut, sans "
                "activité depuis {jours} jours, dont {cites}, que la mémoire cite et qu'elle seule garde ; la livrer "
                "par une pull request si son travail sert, sinon étiqueter d'abord ces commits (`{commande}`), puis "
                "la supprimer : sans quoi la CI ne les retrouve plus",
                branche=b, n=absents, jours=age, cites=", ".join(seuls), commande=outils.etiqueter(seuls)), page))
            continue
        res.append(Element("action", trad("examiner la branche distante `{branche}` : {n} commit(s) absents de la "
                                          "branche par défaut, sans activité depuis {jours} jours ; la livrer par "
                                          "une pull request si son travail sert, sinon la supprimer",
                                          branche=b, n=absents, jours=age), page))
    return res


def dernier_commit_agent(projet: config.Projet, profondeur: int = 500) -> str | None:
    """Le dernier commit de l'agent, en remontant depuis HEAD."""
    from socle.checks_ratchet import est_agent

    if not outils.a_des_commits(projet.racine):
        return None
    sortie = outils.git(projet.racine, "log", f"-{profondeur}", "--format=%H%x00%B%x1e", "HEAD", check=False)
    for bloc in sortie.split("\x1e"):
        sha, _, message = bloc.strip("\n").partition("\0")
        if sha and est_agent(projet, message):
            return sha
    return None


def fait_par_l_humain(projet: config.Projet) -> list[Element]:
    """Les réponses que l'humain a écrites lui-même (`socle answer` dans son
    terminal, une approbation de ses changements protégés), depuis le dernier
    commit de l'agent, commitées ou non : l'agent ne les a pas vues passer,
    et l'humain ne connaît pas toujours le numéro que la commande a donné."""
    depuis = dernier_commit_agent(projet)
    res = []
    for d in demandes.toutes(projet.racine):
        if d.reponse is None or d.reponse.get("canal") != "terminal" or not d.chemin_reponse:
            continue
        if depuis and outils.git_reussit(projet.racine, "cat-file", "-e", f"{depuis}:{d.chemin_reponse}"):
            continue
        r = d.reponse
        quoi = (f"{d.id} — {d.entree.titre if d.entree else d.chemin} : « {r.get('reponse', '')} »"
                f" ({', '.join(x for x in (str(r.get('par', '')), str(r.get('date', ''))) if x)})")
        url, _ = liens.lien(projet, d.chemin)
        res.append(Element("réponse", quoi, url or trad("(pas encore poussée : pas de lien)")))
    return res


def genre(e: Element) -> str:
    """Le genre d'un élément dans la langue du projet."""
    return trad(GENRES[e.genre]) if e.genre in GENRES else e.genre


def texte(elements: list[Element]) -> list[str]:
    if not elements:
        return [trad("ce qui revient à l'humain : rien")]
    lignes = [trad("ce qui revient à l'humain : {n}", n=len(elements))]
    for e in elements:
        lignes.append(f"  {genre(e)} : {e.quoi}")
        if e.lien:
            lignes.append(f"    {e.lien}")
    return lignes


def dernier_message(transcript: Path) -> str | None:
    """Le texte du dernier message de l'agent, lu dans le transcript JSONL de
    Claude Code. `None` si illisible : le format appartient à l'agent, le
    moteur ne fait que le lire."""
    try:
        lignes = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for ligne in reversed(lignes):
        try:
            obj = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        contenu = (obj.get("message") or {}).get("content")
        if isinstance(contenu, str) and contenu.strip():
            return contenu
        if isinstance(contenu, list):
            textes = [b.get("text", "") for b in contenu if isinstance(b, dict) and b.get("type") == "text"]
            if any(t.strip() for t in textes):
                return "\n".join(textes)
    return None


def recap_manquant(projet: config.Projet, message: str) -> list[str]:
    """Les lignes du récap absentes du message ; vide, le récap est complet."""
    defaut = MARQUEURS_RECAP_EN if langue.du_projet(projet) == "en" else MARQUEURS_RECAP
    marqueurs = projet.pol("human", "recap_markers", defaut=defaut)
    return [nom for nom, motif in marqueurs.items() if not re.search(motif, message)]


def prochaines_etapes(projet: config.Projet) -> str:
    """La section « Prochaines étapes » du chantier actif, telle qu'écrite."""
    texte = outils.lire_a(projet.racine, None, projet.chemins.actif) or ""
    m = re.search(r"^##\s+(?:Prochaines étapes|Next steps)\s*$(.*?)(?=^##\s|\Z)", texte, re.M | re.S)
    return m.group(1).strip() if m else ""
