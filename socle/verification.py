"""Le contrat `verify` : les capacités de l'adaptateur, puis les contrôles du
socle, un seul code de sortie.

Toutes les étapes s'exécutent même après un échec. Une étape qui échoue
rapporte sa sortie — la fin, pas un extrait choisi : c'est le moment où on en
a besoin, et la tronquer oblige à relancer.
"""

from __future__ import annotations

import os
import re
import subprocess

from socle import config, utils as outils
from socle.messages import trad
from socle.report import Rapport

ORDRE = ("format", "lint", "build", "tests")
LIGNES_SORTIE = 120
# L'empreinte du dernier arbre sur lequel les étapes rapides ont toutes passé.
MARQUE = ".socle/trace/derniere-verification"
# Un outil absent de l'environnement : le shell ne trouve pas la commande
# (code 127), ou Python le module que la commande lance.
OUTIL_ABSENT = re.compile(r"(?m)^\S*python[\d.]*: No module named \S+")


def etapes_rapides(projet: config.Projet, rapport: Rapport, flux=None, refaire: bool = False) -> bool:
    """Les étapes rapides de l'adaptateur, sauf si elles ont déjà toutes passé
    sur ce contenu exact (fichiers non suivis compris) : la vérification que
    l'agent lance, la fin de tour et le hook avant push ne paient pas trois
    fois la même compilation. Un commit qui ne change pas le contenu, ou qui
    ne change que la mémoire, que les étapes ne lisent pas, ne les relance pas
    (B-0086). La CI, elle, refait tout. Rend vrai si elles ont tourné."""
    racine = projet.racine
    hors = (projet.chemins.memoire.rstrip("/") + "/",)
    marque = outils.empreinte_contenu(racine, hors) if outils.a_des_commits(racine) else ""
    fichier = racine / MARQUE
    if marque and not refaire and fichier.is_file() and fichier.read_text().strip() == marque:
        if flux:
            print(trad("  … étapes rapides déjà passées sur cet arbre exact : non relancées (`--redo` pour les "
                       "relancer)"), file=flux, flush=True)
        return False
    avant = len(rapport.erreurs())
    executer_etapes(projet, True, rapport, flux)
    if marque and not any(c.controle.startswith("verify.") for c in rapport.erreurs()[avant:]):
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(marque)
    return True


def etapes(projet: config.Projet, rapide: bool) -> list[tuple[str, dict]]:
    caps = projet.adaptateur.get("capabilities", {})
    res = []
    for nom in ORDRE:
        c = caps.get(nom)
        if c is None:
            continue
        res.append((nom, c))
    for extra in projet.adaptateur.get("steps", []) or []:
        res.append((extra.get("name", "étape"), extra))
    if rapide:
        res = [(n, c) for n, c in res if c.get("fast", False) or "command" not in c]
    return res


# Posée pendant les étapes rapides : un test trop long pour une fin
# de tour s'y met de côté, avec sa raison écrite, et la CI, qui lance toutes
# les étapes sans elle, le joue toujours.
RAPIDE = "SOCLE_RAPIDE"


def sans_code(projet: config.Projet) -> bool:
    """Vrai quand le projet n'a encore aucun fichier source à lui : un projet
    neuf, installé avant sa première ligne, n'a rien à compiler ni à tester
    (B-0089). Ni le dossier du socle ni les fichiers d'un outil tiers n'en
    sont."""
    sources = projet.adaptateur.get("sources", [])
    if not sources:
        return False
    fichiers = projet.hors_tiers(outils.fichiers_courants(projet.racine))
    return not outils.filtrer(fichiers, sources, [f"{config.DOSSIER}/**"])


def commandes_ci(projet: config.Projet) -> list[str]:
    """Les commandes que la CI lance pour les outils des adaptateurs, avant
    le socle (leurs étapes `ci_setup`) : l'environnement de l'agent en a
    besoin aussi (B-0090). Un bloc `run: |` donne une commande, ses lignes
    jointes ; une commande que deux adaptateurs partagent ne se répète pas."""
    res = []
    for a in projet.adaptateurs:
        res += [c for c in _commandes_ci(a.donnees.get("ci_setup") or "") if c not in res]
    return res


def _commandes_ci(texte: str) -> list[str]:
    res, bloc = [], None
    for ligne in texte.splitlines():
        if bloc is not None:
            if ligne.strip() and len(ligne) - len(ligne.lstrip()) > bloc[0]:
                bloc[1].append(ligne.strip())
                continue
            if bloc[1]:
                res.append(" ; ".join(bloc[1]))
            bloc = None
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*?)\s*$", ligne)
        if m and m.group(2) in ("|", ">"):
            bloc = (len(m.group(1)), [])
        elif m and m.group(2):
            res.append(m.group(2))
    if bloc and bloc[1]:
        res.append(" ; ".join(bloc[1]))
    return res


def executer_etapes(projet: config.Projet, rapide: bool, rapport: Rapport, flux=None):
    """Les étapes de chaque adaptateur, l'un après l'autre, jusqu'au bout
    même après un échec. Dans un projet à plusieurs adaptateurs, chaque
    étape porte le nom du sien : `verify.kotlin.tests` (ADR-0051, point 4)."""
    env = dict(os.environ)
    env.setdefault("LC_ALL", "C.UTF-8")
    if rapide:
        env[RAPIDE] = "1"
    else:
        env.pop(RAPIDE, None)
    if not projet.plusieurs_adaptateurs:
        _executer_etapes_de(projet, "verify", rapide, rapport, flux, env)
        return
    for a in projet.adaptateurs:
        _executer_etapes_de(projet.pour(a), f"verify.{a.nom}", rapide, rapport, flux, env)


def _executer_etapes_de(projet: config.Projet, prefixe: str, rapide: bool, rapport: Rapport, flux, env):
    vide = sans_code(projet)
    for nom, c in etapes(projet, rapide):
        ident = f"{prefixe}.{nom}"
        rapport.execute(ident)
        if "command" not in c:
            rapport.indisponible(ident, trad("capacité absente : {absent} — remplacement : {remplacement}",
                                             absent=trad(c['absent']) if 'absent' in c else '?',
                                             remplacement=trad(c['replacement']) if 'replacement' in c else '?'))
            continue
        if vide and nom in ORDRE:
            # Les étapes d'un projet déclarées par lui (`steps`) tournent
            # toujours : elles ne jugent pas forcément son code.
            rapport.avertir(ident, trad("pas encore de code (aucun fichier {sources}) : `{commande}` non lancée ; "
                                        "elle tournera dès le premier fichier",
                                        sources=", ".join(f"`{s}`" for s in projet.adaptateur["sources"]),
                                        commande=c['command']))
            continue
        if flux:
            print(f"  … {ident} : {c['command']}", file=flux, flush=True)
        try:
            p = subprocess.run(c["command"], shell=True, cwd=projet.racine, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env,
                               timeout=c.get("timeout", 3600))
        except subprocess.TimeoutExpired:
            rapport.erreur(ident, trad("délai dépassé : {commande}", commande=c['command']))
            continue
        if p.returncode != 0:
            sortie = (p.stdout + p.stderr).rstrip()
            queue = "\n        ".join(sortie.splitlines()[-LIGNES_SORTIE:])
            if c.get("no_tests") and re.search(c["no_tests"], sortie):
                # Un projet qui commence n'a pas encore de test : l'outil le
                # dit par un échec, que l'adaptateur reconnaît.
                rapport.avertir(ident, trad("aucun test trouvé (`{commande}`) : un projet qui commence n'en a "
                                            "pas encore ; le premier code s'écrit avec son test",
                                            commande=c['command']))
                continue
            message = trad("`{commande}` a rendu {code}\n        {queue}",
                           commande=c['command'], code=p.returncode, queue=queue)
            if p.returncode == 127 or OUTIL_ABSENT.search(sortie):
                ci = _commandes_ci(projet.adaptateur.get("ci_setup") or "")
                message += "\n        " + (trad("l'outil manque à cet environnement ; la CI l'installe ainsi : {commandes} "
                                               "— l'installer ici ; en session cloud, le hook de démarrage du "
                                               "socle l'installe dans chaque session neuve",
                                               commandes=" ; ".join(f"`{x}`" for x in ci)) if ci
                                         else trad("l'outil manque à cet environnement : l'installer"))
            rapport.erreur(ident, message)
