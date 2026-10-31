"""L'état dérivé : calculé à chaque démarrage de session et après chaque
compactage, jamais écrit à la main.

Tout ce qui est imprimé ici vient de git, de la mémoire ou de la trace des
hooks : rien n'est recopié, donc rien ne peut vieillir. Ce script ne doit
jamais empêcher une session de démarrer : un échec se traduit par une ligne
en moins, jamais par un code non nul.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections import Counter

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


def calculer(projet: config.Projet, contenus: bool = True) -> str:
    racine = projet.racine
    lignes = []
    nom = racine.name
    from socle import hooks
    from socle.checks_ratchet import REMEDE_HOOKS

    if hooks.hooks_non_charges(projet):
        # En tête, avant tout le reste : rien de ce qui suit n'est protégé
        # par les hooks de l'agent.
        lignes.append(trad("!! LES HOOKS DE L'AGENT NE SONT PAS CHARGÉS dans cette session : aucun n'a tiré "
                           "pour elle récemment, ni au démarrage ni avant cette commande (une session reprise hors "
                           "de la racine du projet garde ses traces d'avant). Ni le filtre des commandes, ni les "
                           "contrôles de fin de tour, ni l'état au démarrage ne tournent. Le dire à l'humain avant "
                           "tout travail. {remede}",
                           remede=trad(REMEDE_HOOKS)))
        lignes.append("")
    lignes.append(trad("== {nom} — état dérivé par `socle state`, rien de recopié ==", nom=nom))
    try:
        lignes += _git(racine, projet)
    except outils.ErreurGit as e:
        lignes.append(trad("git : indisponible ({erreur})", erreur=e))
    try:
        mem = memoire.Memoire.charger(racine)
        lignes += _memoire(mem, projet)
    except Exception as e:  # l'état ne bloque jamais le démarrage
        lignes.append(trad("mémoire : illisible ({erreur}) — lancer `python3 .socle/socle check`",
                           erreur=f"{type(e).__name__}: {e}"))
    try:
        lignes += _demandes(racine)
    except Exception as e:
        lignes.append(trad("demandes : illisibles ({erreur})", erreur=f"{type(e).__name__}: {e}"))
    try:
        lignes += audit_adaptateur(projet)
    except Exception as e:
        lignes.append(trad("adaptateur : audit impossible ({erreur})", erreur=f"{type(e).__name__}: {e}"))
    try:
        from socle import human as humain

        elements = humain.a_faire(projet)
        exigee, detail = ci_exigee(projet)
        # Le détail commence par le nom de la branche, suivi de ce que dit la
        # revue des propriétaires du code.
        nom = (outils.branche_par_defaut(racine) or "").removeprefix("origin/")
        revue = detail[len(nom):] if nom and detail.startswith(nom) else ""
        if exigee is False:
            elements.append(humain.Element(
                "action", trad("protéger la branche `{nom}` : y exiger la CI « {ci} » avant toute fusion", nom=nom,
                               ci=nom_de_la_ci(projet)),
                page_protection(projet) or ""))
        lignes += _balayage(projet, elements)
        if exigee:
            lignes.append(trad("branche  : {nom} — CI du socle exigée avant fusion{revue}", nom=nom, revue=revue))
        elif exigee is False:
            lignes.append(trad("branche  : {nom} — CI du socle NON exigée : une CI rouge n'empêche pas de fusionner",
                               nom=nom))
        else:
            lignes.append(trad("branche  : protection inconnue ({detail})", detail=detail))
        lignes += humain.texte(elements)
    except Exception as e:
        lignes.append(trad("ce qui revient à l'humain : incalculable ({erreur})", erreur=f"{type(e).__name__}: {e}"))
    try:
        from socle import human as humain

        faits = humain.fait_par_l_humain(projet)
        if faits:
            lignes.append(trad("écrit par l'humain lui-même depuis le dernier commit de l'agent : {n} — à lui "
                               "citer, avec le lien", n=len(faits)))
            for e in faits:
                lignes.append(f"  {humain.genre(e)} : {e.quoi}")
                lignes.append(f"    {e.lien}")
    except Exception as e:
        lignes.append(trad("ce que l'humain a écrit lui-même : incalculable ({erreur})",
                           erreur=f"{type(e).__name__}: {e}"))
    lignes += _hooks(racine)
    from socle import private as prive

    lignes.append(prive.ligne_etat(projet))
    lignes.append(trad("vérifier : `python3 .socle/socle verify --fast` (tout : sans `--fast`)"))
    if contenus:
        # Le chantier actif et les faits, publics puis privés : une
        # mémoire privée lisible ici en fait partie, illisible elle est
        # signalée plus haut.
        ch = projet.chemins
        for chemin in (ch.actif, ch.canonique, ch.dans_prive(ch.actif), ch.dans_prive(ch.canonique)):
            texte = outils.lire_a(racine, None, chemin)
            if texte is not None and memoire.est_prive(chemin) and not memoire.lisible(texte):
                continue
            if texte is not None:
                lignes.append("")
                lignes.append(f"--- {chemin} ---")
                lignes.append(texte.rstrip())
    return "\n".join(lignes)


def audit_adaptateur(projet: config.Projet) -> list[str]:
    """L'audit de l'adaptateur, à chaque état : un langage dont le
    dépôt porte un fichier marqueur, et que l'adaptateur ne couvre pas, voit
    son code échapper aux capacités ; la décision revient à l'humain."""
    from socle import installer as installeur

    couvert = projet.adaptateur.get("language")
    if not couvert:
        return []
    presents = installeur.langages_presents(projet.hors_tiers(outils.fichiers_courants(projet.racine)))
    autres = {l: f for l, f in presents.items() if l != couvert}
    if not autres:
        return []
    liste = ", ".join(f"{l} ({', '.join(f[:2])}{' …' if len(f) > 2 else ''})" for l, f in sorted(autres.items()))
    return [trad("adaptateur : !! langage(s) que l'adaptateur ({couvert}) ne couvre pas : {liste} — leurs tests, leur "
                 "compilation et leur mutation ne passent par aucune capacité ; le dire à l'humain par une demande "
                 "(un autre adaptateur, ou ces fichiers déclarés tiers)", couvert=couvert, liste=liste)]


def _git(racine, projet) -> list[str]:
    if not outils.est_depot(racine) or not outils.a_des_commits(racine):
        return [trad("commit   : aucun (dépôt neuf)")]
    res = []
    court = outils.git(racine, "rev-parse", "--short", "HEAD").strip()
    branche = outils.git(racine, "rev-parse", "--abbrev-ref", "HEAD").strip()
    sales = [l for l in outils.git(racine, "status", "--porcelain").splitlines() if l.strip()]
    propre = trad("arbre propre") if not sales else trad("ATTENTION, {n} fichier(s) non commité(s)", n=len(sales))
    res.append(trad("commit   : {sha} sur {branche} ({propre})", sha=court, branche=branche, propre=propre))
    defaut = outils.branche_par_defaut(racine)
    if defaut:
        non = outils.git(racine, "log", "--oneline", f"{defaut}..HEAD", check=False).splitlines()
        res.append(trad("base     : {defaut} — non fusionné : {n} commit(s)", defaut=defaut, n=len(non)))
        if outils.branche_par_defaut_devinee(racine):
            res.append(trad("  ^ devinée : ce clone n'a ni `origin/HEAD`, ni `main`, ni `master` ; si la branche par "
                            "défaut du dépôt distant est une autre, `git fetch origin <elle>` la fait connaître"))
        res += [f"  {l}" for l in non[:10]]
        if len(non) > 10:
            res.append(trad("  … et {n} autre(s)", n=len(non) - 10))
        base = outils.base_de_travail(racine)
        if base:
            changes = projet.hors_tiers(outils.fichiers_changes(racine, base))
            code = outils.filtrer(changes, projet.chemins_code())
            docs = [c for c in changes if c.endswith(".md")]
            mem = [c for c in changes if memoire.est_memoire(c)]
            res.append(trad("depuis la base : {code} fichier(s) de code, {docs} de doc, {memoire} de mémoire",
                            code=len(code), docs=len(docs), memoire=len(mem)))
            if code and not mem:
                res.append(trad("  ^ du code a changé et la mémoire non : la fin de tour le refusera"))
    else:
        res.append(trad("base     : aucune branche par défaut connue"))
    res.append(trad("CI       : {ci}", ci=_ligne_ci(racine, branche)))
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
    # L'index des décisions, que le cadrage prévoit : une ligne par décision
    # en vigueur, à lire en entier (`socle show ADR-NNNN`) avant d'en rouvrir une.
    # Toutes, rejetées et remplacées comprises : on ne rouvre pas non plus une
    # décision écartée. L'empreinte de l'index se cite dans une décision
    # nouvelle (`lu : decisions@…`).
    lignes_index = memoire.lignes_index(mem, "decisions")
    if lignes_index:
        res.append(trad("décisions, index decisions@{empreinte} (une en entier : `python3 .socle/socle show "
                        "ADR-NNNN`) :", empreinte=memoire.empreinte_index(mem, "decisions")))
        res += [f"  {l}" for l in lignes_index]
    backlog = [e for e in mem.entrees("B") if not e.archivee]
    par = Counter(e.statut for e in backlog)
    res.append(
        trad("backlog  : {ouverts} ouvert(s), {en_cours} en cours, {bloques} bloqué(s), {clos} clos",
             ouverts=par.get("ouvert", 0), en_cours=par.get("en-cours", 0), bloques=par.get("bloque", 0),
             clos=par.get("fait", 0) + par.get("abandonne", 0)))
    for statut, libelle in (("en-cours", a_traduire("en cours")), ("bloque", a_traduire("bloqué"))):
        for e in [e for e in backlog if e.statut == statut][:8]:
            res.append(f"  {trad(libelle)} : {e.id} — {e.titre}")
    res += [f"  {l}" for l in memoire.lignes_ordre(mem)]
    jours = projet.gf("staleness", "active_days", defaut=7)
    t = outils.git(mem.racine, "log", "-1", "--format=%ct", "--", config.FORMAT_ACTUEL.actif, check=False).strip() \
        if outils.a_des_commits(mem.racine) else ""
    if t:
        age = (time.time() - float(t)) / 86400
        if age > jours:
            res.append(trad("péremption : chantier actif inchangé depuis {age} jours (seuil {jours})",
                            age=f"{age:.0f}", jours=jours))
    return res


def _demandes(racine) -> list[str]:
    toutes = demandes.toutes(racine)
    attente = [d for d in toutes if d.reponse is None and d.statut == "en attente"]
    res = [trad("demandes humaines en attente : {n}", n=len(attente))]
    for d in attente:
        date = d.entree.meta.get("date", "") if d.entree else ""
        res.append(f"  {d.id} — {d.entree.titre if d.entree else d.chemin}"
                   + (trad(" (du {date})", date=date) if date else ""))
    renvoyees = [d for d in toutes if d.statut == "renvoyée"]
    for d in renvoyees:
        res.append(trad("  RENVOYÉE (contexte insuffisant) : {id} — à réécrire en une demande qui la remplace",
                        id=d.id))
    return res


def _hooks(racine) -> list[str]:
    lignes = config.lire_trace(racine)
    if not lignes:
        return [trad("hooks    : aucune trace — ils n'ont encore jamais tiré dans ce clone")]
    dernier = " ".join(lignes[-1].split("\t")[:2])
    return [trad("hooks    : {n} déclenchement(s) tracé(s), dernier : {dernier}", n=len(lignes), dernier=dernier)]

