"""Le contrat `verify` : les capacités de l'adaptateur, puis les contrôles du
socle, un seul code de sortie.

Toutes les étapes s'exécutent même après un échec. Une étape qui échoue
rapporte sa sortie — la fin, pas un extrait choisi : c'est le moment où on en
a besoin, et la tronquer oblige à relancer.

Chaque étape lancée dit sa durée, puis leur total ; celui des étapes
rapides a un seuil, `[verify] fast_max_seconds` des garde-fous, au-delà
duquel un avertissement nomme la plus longue, jamais un échec (B-0258).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time

from socle import config, utils as outils
from socle.messages import trad
from socle.report import Rapport, ligne_utile

ORDRE = ("format", "lint", "build", "tests")
LIGNES_SORTIE = 120
# L'empreinte du dernier arbre sur lequel les étapes rapides ont toutes passé.
MARQUE = ".socle/trace/derniere-verification"
# Le dernier passage complet des étapes rapides, à côté de sa marque : leur
# total et la plus longue, avec sa durée (B-0258). Un fichier local : la
# durée dépend de la machine qui l'a mesurée.
DUREES = ".socle/trace/duree-des-etapes-rapides"
# Le nom sous lequel le rapport donne l'avertissement d'un total au-delà du
# seuil.
CONTROLE_DUREE = "verify.duree"
# Un outil absent de l'environnement : le shell ne trouve pas la commande
# (code 127), ou Python le module que la commande lance.
OUTIL_ABSENT = re.compile(r"(?m)^\S*python[\d.]*: No module named \S+")
# Une ligne de la sortie d'une étape qui dit un échec (B-0290) : un mot
# d'échec en tête de ligne, après son décor (`FAIL: test_x (…)`, `--- FAIL:
# TestX`, `FAILED tests/a.py::t`, `*** Error compiling`), ou en fin
# (`test x ... FAILED`). Le motif ne nomme ni langage ni outil : il lit le
# vocabulaire commun des outils de test, et la ligne de code d'une trace
# (`self.fail(…)`) n'y répond pas. L'essentiel d'un rapport en garde au plus
# MAXIMUM_LIGNES_D_ECHEC ; la commande qu'il donne montre le reste.
LIGNE_D_ECHEC = re.compile(r"(?i)^\W*(?:fail|failed|failure|error|échec)\b|\b(?:fail|failed|failure|error|échec)\W*$")
MAXIMUM_LIGNES_D_ECHEC = 10


def etapes_rapides(projet: config.Projet, rapport: Rapport, flux=None, refaire: bool = False) -> bool:
    """Les étapes rapides de l'adaptateur, sauf si elles ont déjà toutes passé
    sur ce contenu exact (fichiers non suivis compris) : la vérification que
    l'agent lance, la fin de tour et le hook avant push ne paient pas trois
    fois la même compilation. Un commit qui ne change pas le contenu, ou qui
    ne change que la mémoire, que les étapes ne lisent pas, ne les relance pas
    (B-0086). La CI, elle, refait tout. Rend vrai si elles ont tourné.
    Un passage où elles ont toutes passé garde leur total et la plus
    longue ; au-delà du seuil des garde-fous, un avertissement le dit à sa
    fin, puis sur la ligne qui dit les étapes déjà passées (B-0258)."""
    racine = projet.racine
    hors = (projet.chemins.memoire.rstrip("/") + "/",)
    marque = outils.empreinte_contenu(racine, hors) if outils.a_des_commits(racine) else ""
    fichier = racine / MARQUE
    if marque and not refaire and fichier.is_file() and fichier.read_text().strip() == marque:
        if flux:
            alerte = alerte_duree(projet)
            print(trad("  … étapes rapides déjà passées sur cet arbre exact : non relancées (`--redo` pour les "
                       "relancer)") + (f" — !! {alerte}" if alerte else ""), file=flux, flush=True)
        return False
    avant = len(rapport.erreurs())
    durees = executer_etapes(projet, True, rapport, flux)
    if not any(c.controle.startswith("verify.") for c in rapport.erreurs()[avant:]):
        # Un passage où une étape échoue ne remplace pas le dernier passage
        # complet, et n'avertit pas : son total ne mesure pas des étapes qui
        # passent (ADR-0086).
        if marque:
            fichier.parent.mkdir(parents=True, exist_ok=True)
            fichier.write_text(marque)
        garder_duree(racine, durees)
        alerte = alerte_duree(projet)
        if alerte:
            rapport.avertir(CONTROLE_DUREE, alerte)
    return True


def secondes(valeur: float) -> str:
    """Une durée en secondes : un seuil entier tel quel, une durée mesurée
    au dixième, avec la virgule en français."""
    from socle.messages import FRANCAIS, langue

    texte = str(valeur) if isinstance(valeur, int) else f"{valeur:.1f}"
    return (texte.replace(".", ",") if langue() == FRANCAIS else texte) + " s"


def garder_duree(racine, durees: list[tuple[str, float]]) -> None:
    """La trace d'un passage complet des étapes rapides : leur total et la
    plus longue avec sa durée ; sans étape, s'il n'en a lancé aucune."""
    etape, duree = max(durees, key=lambda x: x[1]) if durees else (None, 0.0)
    fichier = racine / DUREES
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps({"total": sum(d for _, d in durees), "etape": etape, "duree": duree}) + "\n")


def derniere_duree(racine) -> dict | None:
    """Le dernier passage complet des étapes rapides gardé sur cette
    machine ; rien s'il n'y en a pas, ou si sa trace est illisible."""
    try:
        donnees = json.loads((racine / DUREES).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(donnees, dict) or not all(
            isinstance(donnees.get(k), (int, float)) and not isinstance(donnees.get(k), bool)
            for k in ("total", "duree")):
        return None
    return donnees


def alerte_duree(projet: config.Projet) -> str | None:
    """L'avertissement, tant que le total du dernier passage complet des
    étapes rapides dépasse le seuil des garde-fous : le total, le seuil et
    la plus longue avec sa durée. Jamais un échec : la durée dépend de la
    machine. La CI ne passe pas par ici : elle lance toutes les étapes, sur
    une autre machine, et n'en imprime que les durées."""
    passage = derniere_duree(projet.racine)
    seuil = projet.seuil_rapide()
    if passage is None or passage["total"] <= seuil:
        return None
    return trad("durée des étapes rapides au dernier passage complet : {total}, au-delà du seuil de {seuil} "
                "(`[verify] fast_max_seconds` des garde-fous) ; la plus longue : `{etape}`, {duree} — la "
                "raccourcir, ou relever le seuil par une demande validée",
                total=secondes(passage["total"]), seuil=secondes(seuil), etape=passage.get("etape") or "?",
                duree=secondes(passage["duree"]))


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
    jointes ; une commande que deux adaptateurs partagent ne se répète pas.
    Une commande dont l'étape attend un fichier de build (`if: hashFiles(…)
    != ''`) n'en est que si un fichier du projet répond à l'un de ses motifs,
    comme dans la CI (B-0179) : sinon, elle est dans `commandes_en_attente`."""
    return _commandes_du_projet(projet, [a.donnees for a in projet.adaptateurs])[0]


def commandes_en_attente(projet: config.Projet) -> list[tuple[str, list[str]]]:
    """Les commandes de CI dont l'étape attend un fichier de build qu'aucun
    fichier du projet n'est encore, chacune avec les motifs qu'elle attend :
    la CI les saute, l'agent ne les lance pas non plus (B-0179)."""
    return _commandes_du_projet(projet, [a.donnees for a in projet.adaptateurs])[1]


def _commandes_du_projet(projet: config.Projet,
                         adaptateurs: list[dict]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    pretes, attente, fichiers = [], [], None
    for a in adaptateurs:
        for commande, motifs in etapes_ci(a.get("ci_setup") or ""):
            if motifs:
                if fichiers is None:
                    fichiers = outils.fichiers_courants(projet.racine)
                if not outils.filtrer(fichiers, motifs):
                    if all(c != commande for c, _ in attente):
                        attente.append((commande, motifs))
                    continue
            if commande not in pretes:
                pretes.append(commande)
    return pretes, [(c, m) for c, m in attente if c not in pretes]


def attente_dite(attente: list[tuple[str, list[str]]]) -> str:
    """La ligne qui dit les commandes de CI qui attendent leur fichier de
    build, au lieu de les lancer pour qu'elles échouent."""
    return trad("en attente de leur fichier de build, comme dans la CI : {commandes}",
                commandes=" ; ".join(trad("`{commande}` (attend {motifs})", commande=c,
                                          motifs=", ".join(f"`{m}`" for m in motifs)) for c, motifs in attente))


def etapes_ci(texte: str) -> list[tuple[str, list[str]]]:
    """Les commandes d'un `ci_setup`, chacune avec les motifs de la condition
    `if: hashFiles(…) != ''` de son étape (une liste vide sans condition)."""
    lignes = re.findall(r"(?m)^( *)- ", texte)
    if not lignes:
        return [(c, []) for c in _commandes_ci(texte)]
    retrait = min(len(x) for x in lignes)
    res = []
    for bloc in re.split(rf"(?m)^(?= {{{retrait}}}- )", texte):
        m = re.search(r"(?m)^\s*(?:- )?if:\s*hashFiles\(([^)]*)\)\s*!=\s*''", bloc)
        motifs = re.findall(r"'([^']+)'", m.group(1)) if m else []
        res += [(c, motifs) for c in _commandes_ci(bloc)]
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


def executer_etapes(projet: config.Projet, rapide: bool, rapport: Rapport, flux=None) -> list[tuple[str, float]]:
    """Les étapes de chaque adaptateur, l'un après l'autre, jusqu'au bout
    même après un échec. Dans un projet à plusieurs adaptateurs, chaque
    étape porte le nom du sien : `verify.kotlin.tests` (ADR-0051, point 4).
    Chaque étape lancée dit sa durée au bout de sa ligne, puis leur total,
    sans seuil (B-0258) ; rend la durée de chacune, en secondes écoulées."""
    env = dict(os.environ)
    env.setdefault("LC_ALL", "C.UTF-8")
    if rapide:
        env[RAPIDE] = "1"
    else:
        env.pop(RAPIDE, None)
    durees: list[tuple[str, float]] = []
    if not projet.plusieurs_adaptateurs:
        _executer_etapes_de(projet, "verify", rapide, rapport, flux, env, durees)
    else:
        for a in projet.adaptateurs:
            _executer_etapes_de(projet.pour(a), f"verify.{a.nom}", rapide, rapport, flux, env, durees)
    if flux and durees:
        print(trad("  … total des étapes lancées : {total}", total=secondes(sum(d for _, d in durees))),
              file=flux, flush=True)
    return durees


def _executer_etapes_de(projet: config.Projet, prefixe: str, rapide: bool, rapport: Rapport, flux, env,
                        durees: list[tuple[str, float]]):
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
            # Sa durée ira au bout de cette ligne, la commande finie.
            print(f"  … {ident} : {c['command']}", file=flux, end="", flush=True)
        debut = time.monotonic()
        try:
            p = subprocess.run(c["command"], shell=True, cwd=projet.racine, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env,
                               timeout=c.get("timeout", 3600))
        except subprocess.TimeoutExpired:
            _duree(ident, debut, durees, flux)
            rapport.erreur(ident, trad("délai dépassé : {commande}", commande=c['command']))
            continue
        _duree(ident, debut, durees, flux)
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
            entete = trad("`{commande}` a rendu {code}", commande=c['command'], code=p.returncode)
            message = entete + "\n        " + queue
            essentiel = [entete, *lignes_d_echec(sortie)]
            if p.returncode == 127 or OUTIL_ABSENT.search(sortie):
                ci = _commandes_du_projet(projet, [projet.adaptateur])[0]
                manque = (trad("l'outil manque à cet environnement ; la CI l'installe ainsi : {commandes} "
                               "— l'installer ici ; en session cloud, le hook de démarrage du "
                               "socle l'installe dans chaque session neuve",
                               commandes=" ; ".join(f"`{x}`" for x in ci)) if ci
                          else trad("l'outil manque à cet environnement : l'installer"))
                message += "\n        " + manque
                essentiel.append(manque)
            rapport.erreur(ident, message, essentiel=essentiel)


def lignes_d_echec(sortie: str) -> list[str]:
    """L'essentiel de la sortie d'une étape en échec (B-0290) : la ligne de
    chaque test en échec, celles que reconnaît `LIGNE_D_ECHEC`, sans doublon,
    les `MAXIMUM_LIGNES_D_ECHEC` dernières, après le compte de celles d'avant :
    le bilan d'un outil de test vient en fin de sortie, après le journal
    capturé de ses tests, dont les lignes `ERROR` prendraient sinon toute la
    place (pytest) ; à défaut, la dernière ligne utile de la sortie, son
    bilan le plus souvent."""
    vues: list[str] = []
    for ligne in sortie.splitlines():
        ligne = ligne.strip()
        if LIGNE_D_ECHEC.search(ligne) and ligne not in vues:
            vues.append(ligne)
    if not vues:
        utiles = [l.strip() for l in sortie.splitlines() if ligne_utile(l)]
        return utiles[-1:]
    reste = len(vues) - MAXIMUM_LIGNES_D_ECHEC
    if reste > 0:
        return [trad("… et {n} autre(s) ligne(s) d'échec", n=reste)] + vues[-MAXIMUM_LIGNES_D_ECHEC:]
    return vues


def _duree(ident: str, debut: float, durees: list[tuple[str, float]], flux) -> None:
    duree = time.monotonic() - debut
    durees.append((ident, duree))
    if flux:
        print(f" — {secondes(duree)}", file=flux, flush=True)
