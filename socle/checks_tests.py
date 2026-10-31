"""Garde-fous de tests : un test ne prouve rien tant qu'un contrôle n'a pas
montré qu'il peut échouer.

- `tests.creux`      : test sans assertion, assertion tautologique, test
                       désactivé sans raison écrite ;
- `tests.attendus`   : test supprimé ou valeur attendue changée sans
                       changement de spécification ni validation humaine ;
- `tests.regression` : tout correctif livre un test qui échoue sur le commit
                       parent et passe sur le correctif ;
- `mutation.couverture` : tout module qui porte du code a un plafond de
                       mutants survivants ;
- `adaptateur.capacites` : chaque capacité est déclarée, ou absente avec sa
                       raison et son contrôle de remplacement ;
- `tests.code-teste` : une fonction publique ajoutée ou modifiée est nommée
                       par au moins un test, ou dispensée avec sa raison.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from socle import config, language as langue, utils as outils, tests_reader as tests_lecture
from socle.messages import trad
from socle.context import controle

CAPACITES = ("format", "lint", "build", "tests", "mutation", "coverage", "regression")
# `f(x) == f(x)` est creux… sauf dans un test de déterminisme, qui appelle
# deux fois pour comparer. La raison s'écrit, comme pour un test désactivé.
VOULU = re.compile(r"socle\s*:\s*(?:voulu|intended)\s*[—–:-]\s*\S.{2,}", re.I)
FIX_DEFAUT = r"(?i)^(fix|corrige|correctif|correction)\b"


def cfg_tests(projet) -> dict | None:
    t = projet.adaptateur.get("tests")
    if not t or "function" not in t:
        return None
    return t


def fonctions(ctx, chemins, rev_tete=True) -> list[tests_lecture.Fonction]:
    cfg = cfg_tests(ctx.projet)
    res = []
    for c in chemins:
        texte = ctx.lire(c) if rev_tete else ctx.lire_base(c)
        if texte is not None:
            res += tests_lecture.extraire(texte, c, cfg)
    return res


def fichiers_tests(ctx, liste) -> list[str]:
    cfg = cfg_tests(ctx.projet)
    return outils.filtrer(liste, cfg.get("paths", []), cfg.get("exclude", []))


@controle("adaptateur.capacites")
def capacites(ctx, r):
    """Aucune capacité n'est omise en silence : déclarée, ou absente avec sa
    raison et son contrôle de remplacement."""
    if not ctx.projet.adaptateur:
        r.erreur("adaptateur.capacites", trad("aucun adaptateur (`{adaptateur}`)",
                                              adaptateur=ctx.projet.chemins.adaptateur))
        return
    caps = ctx.projet.adaptateur.get("capabilities", {})
    for nom in CAPACITES:
        c = caps.get(nom)
        if c is None:
            r.erreur("adaptateur.capacites", trad("capacité « {nom} » non déclarée : une commande, ou `absent` "
                                                  "+ `replacement`", nom=nom), ctx.projet.chemins.adaptateur)
        elif "command" not in c and not ("absent" in c and "replacement" in c):
            r.erreur("adaptateur.capacites", trad("capacité « {nom} » : ni `command`, ni `absent` avec "
                                                  "`replacement`", nom=nom), ctx.projet.chemins.adaptateur)
    if cfg_tests(ctx.projet) is None:
        r.erreur("adaptateur.capacites", trad("section `[tests]` sans `function` : les tests creux ne peuvent "
                                              "pas être détectés"), ctx.projet.chemins.adaptateur)


@controle("tests.creux")
def creux(ctx, r):
    """Pas de test sans assertion, d'assertion tautologique, ni de test
    désactivé sans raison écrite. Sur le diff aux étages agent et git ; partout en CI."""
    cfg = cfg_tests(ctx.projet)
    if cfg is None:
        r.indisponible("tests.creux", trad("adaptateur sans `[tests]` : détection impossible"))
        return
    tous = fichiers_tests(ctx, ctx.fichiers)
    cibles = tous if ctx.etage == "ci" or not ctx.base else fichiers_tests(ctx, ctx.changes)
    cibles = [c for c in cibles if c in set(ctx.fichiers)]
    # Les aides se cherchent dans TOUS les fichiers de test et de source : une
    # aide qui affirme peut vivre ailleurs que le test qui l'appelle. Mais
    # dans un fichier de code, seulement dans ses lignes de test (le module
    # de tests de Rust) : un `assert` du code de production n'affirme rien
    # pour le test qui l'appelle.
    sources = outils.filtrer(ctx.fichiers, ctx.projet.adaptateur.get("sources", []))
    toutes = fonctions(ctx, sorted(set(tous) | set(sources)))
    assertion = re.compile(cfg.get("assertion", r"assert"))
    chemins_code, exclus_code, _ = config_code(ctx.projet)
    zones: dict[str, list[tuple[int, int]]] = {}

    def de_test(f) -> bool:
        if not outils.filtrer([f.fichier], chemins_code, exclus_code):
            return True
        if f.fichier not in zones:
            zones[f.fichier] = tests_lecture.zones_de_test(ctx.lire(f.fichier) or "", f.fichier, cfg)
        return any(d <= f.ligne - 1 < e for d, e in zones[f.fichier])

    aides = tests_lecture.aides_qui_affirment([f for f in toutes if de_test(f)], assertion, cfg)
    ignore = re.compile(cfg["ignore"]) if cfg.get("ignore") else None
    raison = re.compile(cfg["ignore_reason"]) if cfg.get("ignore_reason") else None
    tautos = [re.compile(t) for t in cfg.get("tautology", [])]
    for f in [f for f in toutes if f.fichier in cibles and f.est_test]:
        # Un test se désactive par un attribut (`#[ignore]`, `@Disabled`), sur
        # la ligne qui le définit (`test.skip(…)`, `xit "…"`) ou dans son corps
        # (`t.Skip(…)`, `markTestSkipped(…)`).
        # Dans le corps, la marque se cherche hors des chaînes : un test qui
        # parle d'un `skip` ne se désactive pas.
        litteraux = cfg.get("strings", tests_lecture.LITTERAUX)
        corps_nu = [re.sub(litteraux, '""', l) for l in f.lignes_corps]
        marques = [*f.attributs, f.entete, *f.lignes_corps]
        desactive = ignore and any(ignore.search(a) for a in [*f.attributs, f.entete, *corps_nu])
        if desactive and not (raison and any(raison.search(a) for a in marques)):
            r.erreur("tests.creux", trad("test `{nom}` désactivé sans raison écrite", nom=f.nom), f.fichier, f.ligne)
        if not tests_lecture.affirme(f, assertion, aides, cfg):
            r.erreur("tests.creux", trad("test `{nom}` sans assertion : il passe sans rien mesurer", nom=f.nom), f.fichier, f.ligne)
        for k, ligne in enumerate(f.lignes_corps):
            precedente = f.lignes_corps[k - 1] if k else ""
            if VOULU.search(ligne) or VOULU.search(precedente):
                continue  # une tautologie voulue, raison écrite (un test de déterminisme)
            for t in tautos:
                if t.search(ligne):
                    r.erreur("tests.creux", trad("assertion tautologique dans `{nom}` : « {ligne} » — si elle "
                                                 "est voulue (déterminisme), l'écrire : commentaire `socle: "
                                                 "voulu — <raison>`", nom=f.nom, ligne=ligne.strip()),
                             f.fichier, f.ligne + k + 1)
    # Un groupe entier se désactive hors de tout test : une classe sous
    # `@unittest.skip`, un `describe.skip`, un `@Disabled` de classe, un
    # `skip` dans un `before`.
    if ignore is None:
        return
    comm = re.compile(cfg["comment"]) if cfg.get("comment") else None
    for chemin in cibles:
        texte = ctx.lire(chemin) or ""
        dedans = [(f.debut - 1, f.fin) for f in tests_lecture.extraire(texte, chemin, cfg) if f.est_test]
        litteraux = cfg.get("strings", tests_lecture.LITTERAUX)
        for i, ligne in enumerate(texte.splitlines()):
            if not ignore.search(re.sub(litteraux, '""', ligne)) or (comm and comm.match(ligne)) \
                    or any(d <= i < e for d, e in dedans):
                continue
            if not (raison and raison.search(ligne)):
                r.erreur("tests.creux", trad("groupe de tests désactivé sans raison écrite : « {ligne} »",
                                             ligne=ligne.strip()[:80]),
                         chemin, i + 1)


def _nomme(texte: str, nom: str) -> bool:
    """Le nom y est, en mot entier : une validation qui nomme
    `test_double_negatif` ne vaut pas pour `test_double` (relevé de la passe
    de recul, D)."""
    return bool(re.search(rf"(?<![\w]){re.escape(nom)}(?![\w])", texte))


def _justifie(ctx, nom: str) -> str | None:
    """Une validation humaine, ou une spécification que l'humain a changée et
    qui nomme le test (politique, point 2) : une spécification que l'agent écrit dans le même travail ne
    l'autorise pas à changer le test."""
    for d in ctx.validations:
        if _nomme(d.texte, nom):
            return trad("validé par {id}", id=d.id)
    for c in _specs_nommant(ctx, nom):
        if _ecrite_par_l_humain(ctx, c, nom):
            return trad("spécification changée par l'humain : {chemin}", chemin=c)
    return None


def _en_attente(ctx, nom: str) -> str | None:
    """À la fin du tour seulement (étage agent), une demande en attente,
    poussée telle quelle, qui nomme le test : le travail qui attend
    la réponse de l'humain peut rester dans l'arbre, au lieu d'être remisé
    hors de la mémoire. Le commit et la CI le refusent toujours."""
    from socle import requests as demandes

    if ctx.etage != "agent":
        return None
    for d in ctx.demandes:
        if (d.id and d.reponse is None and d.entree is not None and "retiree" not in d.entree.meta
                and _nomme(d.texte, nom) and demandes.illisible(ctx.projet, d) is None):
            return d.id
    return None


def _specs_nommant(ctx, nom: str) -> list[str]:
    """Les spécifications changées dans la plage qui nomment le test."""
    specs = ctx.projet.gf("tests", "spec_paths", defaut=[ctx.projet.chemins.decisions + "/**"])
    return [c for c in outils.filtrer(ctx.changes, specs)
            if _nomme(ctx.lire(c) or "", nom) and not _nomme(ctx.lire_base(c) or "", nom)]


def _ecrite_par_l_humain(ctx, chemin: str, nom: str) -> bool:
    """La mention du test est commitée, et aucun commit d'agent de la plage
    n'a touché la spécification : une écriture en cours est celle de
    l'agent qui travaille."""
    from socle.checks_ratchet import est_agent

    if not _nomme(outils.lire_a(ctx.racine, ctx.rev_commit, chemin) or "", nom):
        return False
    plage = ctx.rev_commit if ctx.base in (None, outils.ARBRE_VIDE) else f"{ctx.base}..{ctx.rev_commit}"
    touches = set(outils.git(ctx.racine, "log", "--format=%H", plage, "--", chemin, check=False).split())
    return not any(c["sha"] in touches and est_agent(ctx.projet, c["message"]) for c in ctx.commits)


@controle("tests.attendus", base=True)
def attendus(ctx, r):
    """Supprimer un test ou changer une valeur attendue exige une validation
    humaine, ou un changement de spécification qui le nomme, fait par
    l'humain (politique, point 2)."""
    cfg = cfg_tests(ctx.projet)
    if cfg is None:
        r.indisponible("tests.attendus", trad("adaptateur sans `[tests]`"))
        return
    # Les lignes qui portent une valeur attendue : les assertions, et ce que
    # l'adaptateur y ajoute (`expected` : en Go, la condition `if got != 4`).
    assertion = re.compile(cfg.get("expected") or cfg.get("assertion", r"assert"))
    changes = set(ctx.changes)
    avant_fichiers = [c for c in fichiers_tests(ctx, ctx.fichiers_base) if c in changes]
    if not avant_fichiers:
        return
    avant = [f for f in fonctions(ctx, avant_fichiers, rev_tete=False) if f.est_test]
    apres_tous = [f for f in fonctions(ctx, fichiers_tests(ctx, ctx.fichiers)) if f.est_test]
    par_corps = {re.sub(r"\s+", " ", f.corps) for f in apres_tous}

    def valeurs(f) -> Counter:
        return Counter({k: len(v) for k, v in tests_lecture.enonces(f.lignes_corps, assertion, cfg).items()})

    # Des tests homonymes dans un fichier (deux classes) s'apparient dans
    # l'ordre où ils viennent, à nombre égal ; sinon chacun avec celui qui
    # lui retire le moins d'assertions.
    groupes_avant, groupes_apres = defaultdict(list), defaultdict(list)
    for f in avant:
        groupes_avant[(f.fichier, f.nom)].append(f)
    for f in apres_tous:
        groupes_apres[(f.fichier, f.nom)].append(f)
    paires = []
    for cle, anciens in groupes_avant.items():
        nouveaux = groupes_apres.get(cle, [])
        if len(nouveaux) == len(anciens):
            paires += zip(anciens, nouveaux)
        else:
            paires += [(a, min(nouveaux, key=lambda b: sum((valeurs(a) - valeurs(b)).values()), default=None))
                       for a in anciens]
    def signaler(nom, fichier, ligne, quoi, faute):
        pourquoi = _justifie(ctx, nom)
        attente = None if pourquoi else _en_attente(ctx, nom)
        if pourquoi:
            r.avertir("tests.attendus", f"{quoi} ({pourquoi})", fichier, ligne)
        elif attente:
            r.avertir("tests.attendus", trad("{quoi}, en attente de {attente} : le tour peut finir, le commit "
                                             "et la CI attendent la réponse de l'humain",
                                             quoi=quoi, attente=attente), fichier, ligne)
        else:
            r.erreur("tests.attendus", faute + _note_agent(ctx, nom), fichier, ligne)

    hors: dict[str, list[tuple[str, str]]] = {}

    def lits(f) -> Counter:
        return tests_lecture.litteraux("\n".join([*f.attributs, f.entete, f.corps]), cfg)

    for a, b in paires:
        if b is None:
            if re.sub(r"\s+", " ", a.corps) in par_corps:
                continue  # déplacé tel quel
            signaler(a.nom, a.fichier, a.ligne, trad("test `{nom}` supprimé", nom=a.nom),
                     trad("test `{nom}` supprimé sans validation humaine ni changement de spécification qui le "
                          "nomme", nom=a.nom))
            continue
        disparues = valeurs(a) - valeurs(b)
        if disparues:
            exemple = tests_lecture.enonces(a.lignes_corps, assertion, cfg)[next(iter(disparues))][0]
            signaler(a.nom, b.fichier, b.ligne, trad("assertion changée dans `{nom}`", nom=a.nom),
                     trad("assertion changée ou retirée dans `{nom}` : « {exemple} » — valeur attendue "
                          "modifiée sans spécification ni validation humaine", nom=a.nom, exemple=exemple))
            continue
        # Une valeur attendue vit aussi hors de la ligne d'assertion : une
        # variable, une table, un paramètre. Rien ne la distingue d'une
        # donnée de test : elle est dite, pas refusée.
        valeurs_parties = lits(a) - lits(b)
        if valeurs_parties and not _justifie(ctx, a.nom):
            hors.setdefault(b.fichier, []).append((b.nom, next(iter(valeurs_parties))))
    _attendus_hors_tests(ctx, cfg, avant_fichiers, [b for _, b in paires if b is not None], hors)
    for fichier, liste in sorted(hors.items()):
        noms = sorted({n for n, _ in liste})
        r.avertir("tests.attendus", trad(
            "valeurs changées hors des assertions dans {n} test(s) — {tests} (« {valeur} ») : si l'une est une "
            "valeur attendue (une variable, une table, un paramètre, une constante), la changer exige une "
            "validation humaine (politique, point 2)", n=len(noms),
            tests=", ".join(f"`{n}`" for n in noms[:5]) + (" …" if len(noms) > 5 else ""), valeur=liste[0][1][:40]),
            fichier)


def _attendus_hors_tests(ctx, cfg, chemins, apres, hors):
    """Une valeur des fichiers de test hors de tout test (une constante, une
    aide qui affirme) : retirée ou changée, elle compte pour chaque test qui
    nomme sa constante ou son aide. Dans un fichier de code, seules ses
    lignes de test comptent : le module de tests de Rust, jamais le code de
    production."""
    chemins_code, exclus_code, _ = config_code(ctx.projet)

    def reste(texte, chemin) -> list[str]:
        lignes = texte.splitlines()
        tests = [(f.debut - 1, f.fin) for f in tests_lecture.extraire(texte, chemin, cfg) if f.est_test]
        dedans = tests_lecture.zones_de_test(texte, chemin, cfg) if outils.filtrer([chemin], chemins_code, exclus_code) \
            else [(0, len(lignes))]
        return [l if any(d <= i < e for d, e in dedans) and not any(d <= i < e for d, e in tests) else ""
                for i, l in enumerate(lignes)]

    for chemin in chemins:
        avant, maintenant = ctx.lire_base(chemin), ctx.lire(chemin)
        if avant is None or maintenant is None:
            continue
        lignes_avant = reste(avant, chemin)
        parties = tests_lecture.litteraux("\n".join(lignes_avant), cfg) - \
            tests_lecture.litteraux("\n".join(reste(maintenant, chemin)), cfg)
        if not parties:
            continue
        aides = [f for f in tests_lecture.extraire(avant, chemin, cfg) if not f.est_test]
        # Chaque ligne qui portait une valeur disparue : la même valeur peut
        # vivre dans une constante et dans une aide.
        for i, valeur in [(k, v) for k, l in enumerate(lignes_avant)
                          for v in parties if v in tests_lecture.litteraux(l, cfg)]:
            m = re.match(r"^\s*(?:(?:pub|const|let|var|static|final|export|private|public)\s+)*([A-Za-z_]\w*)\s*"
                         r"(?::[^=]*)?=(?!=)", lignes_avant[i])
            englobante = next((f.nom for f in aides if f.debut - 1 <= i < f.fin), None)
            nom = englobante or (m.group(1) if m else None)
            touches = [b for b in apres if b.fichier == chemin and nom and _nomme(b.corps, nom)]
            if not touches:
                continue  # une valeur qu'aucun test ne nomme n'en est pas une valeur attendue
            for b in touches:
                if not _justifie(ctx, b.nom):
                    hors.setdefault(b.fichier, []).append((b.nom, valeur))


def _note_agent(ctx, nom: str) -> str:
    specs = _specs_nommant(ctx, nom)
    if not specs:
        return ""
    return (trad(" ; la spécification {specs} le nomme, mais elle est écrite par l'agent : elle ne suffit pas "
                 "(politique, point 2). Poser une demande à l'humain, ou qu'il change lui-même la spécification",
                 specs=specs[0]))


# `Dispense-test: f, g — raison` : les fonctions nommées, puis pourquoi
# aucun test ne les nomme.
DISPENSE_TEST = re.compile(r"^(?P<noms>[\w.]+(?:\s*,\s*[\w.]+)*)\s+[—–-]+\s+(?P<raison>\S.{9,})$")


def config_code(projet) -> tuple[list, list, str | None]:
    """(chemins, exclusions, motif d'une fonction privée) du code soumis à
    `tests.code-teste`. La section `[code]` de l'adaptateur du projet ; à
    défaut, les sources hors fichiers de test, toute fonction comptant comme
    publique."""
    code = projet.adaptateur.get("code")
    # Le dossier du socle n'est jamais du code du projet : le moteur y est
    # installé, immuable, et ses fonctions ne sont pas celles du projet.
    socle = [f"{config.DOSSIER}/**"]
    if code and "paths" in code:
        return code.get("paths", []), code.get("exclude", []) + socle, code.get("private")
    return projet.adaptateur.get("sources", []), (cfg_tests(projet) or {}).get("paths", []) + socle, None


def dispenses_tests(ctx, r) -> set[str]:
    noms = set()
    for c in ctx.commits:
        for v in langue.trailers(c["message"]).get("dispense-test", []):
            m = DISPENSE_TEST.match(v.strip())
            if not m:
                r.erreur("tests.code-teste", trad("dispense illisible dans le commit {sha} : « {dispense} » — forme "
                                                  "attendue : `Dispense-test: f, g — <raison d'au moins dix "
                                                  "caractères>`", sha=c['sha'][:7], dispense=v.strip()))
                continue
            noms |= {n.strip() for n in m["noms"].split(",")}
    return noms


def _externes(fns: list[tests_lecture.Fonction]) -> list[tests_lecture.Fonction]:
    """Les fonctions qui ne sont pas imbriquées dans une autre : une
    fonction locale compte pour celle qui la contient."""
    res, fin = [], 0
    for f in sorted(fns, key=lambda f: f.ligne):
        if f.ligne > fin:
            res.append(f)
            fin = f.fin
    return res


@controle("tests.code-teste", etages=("agent", "ci"), base=True)
def code_teste(ctx, r):
    """Une fonction publique ajoutée ou modifiée est nommée par au moins un
    test — ou une dispense motivée la nomme (`Dispense-test: f — <raison>`).

    Pas à l'étage git : le hook pre-commit ne voit pas le message du commit,
    donc pas la dispense qu'il porte."""
    cfg = cfg_tests(ctx.projet)
    if cfg is None:
        r.indisponible("tests.code-teste", trad("adaptateur sans `[tests]` : fonctions illisibles"))
        return
    chemins, exclus, prive = config_code(ctx.projet)
    prive_re = re.compile(prive) if prive else None
    presents = set(ctx.fichiers)
    code = outils.filtrer([c for c in ctx.changes if c in presents], chemins, exclus)
    if not code:
        return
    # Ce que les tests nomment : tout le texte d'un fichier de test qui n'est
    # pas du code ; le corps des seules fonctions de test d'un fichier qui en
    # est (les tests unitaires de Rust vivent dans les sources).
    nommes = []
    for f in fichiers_tests(ctx, ctx.fichiers):
        texte = ctx.lire(f) or ""
        # Hors des commentaires : y citer une fonction ne la teste pas.
        if outils.filtrer([f], chemins, exclus):
            nommes += [tests_lecture.sans_commentaires(fn.corps, cfg)
                       for fn in tests_lecture.extraire(texte, f, cfg) if fn.est_test]
        else:
            nommes.append(tests_lecture.sans_commentaires(texte, cfg))
    nommes = "\n".join(nommes)
    dispenses = dispenses_tests(ctx, r)
    # Un fichier renommé se compare à son ancien nom : ses fonctions n'y sont
    # pas nouvelles.
    ancien_nom = {neuf: ancien for ancien, neuf in ctx.renommes.items()}
    for chemin in code:
        texte = ctx.lire(chemin) or ""
        lignes_texte = texte.splitlines()
        ancien = ancien_nom.get(chemin)
        changees = outils.lignes_changees(ctx.racine, ctx.base, ctx.tete, chemin, ancien)
        avant = {f.nom for f in tests_lecture.extraire(ctx.lire_base(ancien or chemin) or "", chemin, cfg)}
        for f in _externes(tests_lecture.extraire(texte, chemin, cfg)):
            if f.est_test or (prive_re and prive_re.match(lignes_texte[f.ligne - 1])):
                continue
            if changees is not None and not any(f.ligne <= l <= f.fin for l in changees):
                continue
            if f.nom in dispenses or re.search(rf"(?<![\w]){re.escape(f.nom)}(?![\w])", nommes):
                continue
            texte_ = (trad("fonction `{nom}` modifiée, qu'aucun test ne nomme : écrire le test qui l'appelle, ou la "
                           "dispenser par un trailer de commit `Dispense-test: {nom} — <raison>`", nom=f.nom)
                      if f.nom in avant else
                      trad("fonction `{nom}` ajoutée, qu'aucun test ne nomme : écrire le test qui l'appelle, ou la "
                           "dispenser par un trailer de commit `Dispense-test: {nom} — <raison>`", nom=f.nom))
            r.erreur("tests.code-teste", texte_, chemin, f.ligne)


def est_correctif(projet, message: str) -> bool:
    sujet = message.strip().splitlines()[0] if message.strip() else ""
    motif = projet.gf("regression", "fix_subject", defaut=FIX_DEFAUT)
    tr = outils.trailers(message)
    return bool(re.search(motif, sujet)) or "corrige" in tr or "fixes" in tr


@controle("tests.regression", etages=("ci",), base=True, lent=True)
def regression(ctx, r):
    """Tout correctif livre un test qui échoue sur le commit parent et passe sur
    le correctif, vérifié en l'exécutant."""
    cap = ctx.projet.adaptateur.get("capabilities", {}).get("regression", {})
    correctifs = [c for c in ctx.commits if len(c["parents"]) == 1 and est_correctif(ctx.projet, c["message"])]
    if not correctifs:
        return
    if "command" not in cap:
        absent = trad(cap["absent"]) if "absent" in cap else trad("non déclarée")
        remplacement = trad(cap["replacement"]) if "replacement" in cap else "?"
        r.indisponible("tests.regression", trad("capacité absente : {absent} — remplacement : {remplacement}",
                                                absent=absent, remplacement=remplacement))
        return
    motifs = cap.get("test_paths") or (cfg_tests(ctx.projet) or {}).get("paths", [])
    for c in correctifs:
        sha, parent = c["sha"], c["parents"][0]
        sujet = c["message"].strip().splitlines()[0]
        touches = ctx.projet.hors_tiers(outils.fichiers_changes(ctx.racine, parent, sha))
        tests = [t for t in outils.filtrer(touches, motifs) if outils.lire_a(ctx.racine, sha, t) is not None]
        if tests:
            fichiers = {t: outils.lire_a(ctx.racine, sha, t) or "" for t in tests}
            commande = commande_regression(cap, tests)
        else:
            # Un test écrit dans le module du code :
            # sur le parent, le seul changement de ses fonctions de test.
            fichiers, noms = tests_du_module(ctx, parent, sha, [t for t in touches if t not in tests])
            commande = cap["module_command"].replace("{names}", " ".join(noms)) \
                if noms and "module_command" in cap else None
        if commande is None:
            ailleurs = trad(" ; ni test changé dans un module de code") if "module_command" in cap else ""
            r.erreur("tests.regression", trad("correctif sans test de régression : {sha} « {sujet} » (aucun "
                                              "fichier de {liste} ajouté ou modifié{ailleurs})",
                                              sha=sha[:10], sujet=sujet, liste=', '.join(motifs), ailleurs=ailleurs))
            continue
        sur_parent = _executer_superpose(ctx, parent, fichiers, commande, cap)
        if sur_parent is None:
            r.erreur("tests.regression", trad("{sha} : impossible de préparer le commit parent", sha=sha[:10]))
            continue
        code_parent, sortie = sur_parent
        if code_parent == 0:
            admise = _admis_par(ctx, sha)
            if admise:
                r.avertir("tests.regression", trad("{sha} « {sujet} » : son test passe déjà sur le parent ; admis "
                                                   "par {id}, une demande validée qui nomme ce commit",
                                                   sha=sha[:10], sujet=sujet, id=admise))
                continue
            r.erreur("tests.regression", trad("{sha} « {sujet} » : son test passe déjà sur le parent — il ne "
                                              "prouve pas le correctif ; si sa preuve dépend de l'environnement, "
                                              "une demande validée qui nomme ce commit l'admet", sha=sha[:10],
                                              sujet=sujet))
            continue
        # Un test qui ne se charge pas sur le parent (une compilation cassée,
        # un import manquant) y échoue pour une autre raison que le défaut
        #.
        chargement = re.search(cap["load_error"], sortie) if cap.get("load_error") else None
        if chargement:
            r.erreur("tests.regression", trad("{sha} « {sujet} » : son test ne se charge pas sur le parent (« "
                                              "{erreur} ») : il y échoue pour une autre raison que le défaut. "
                                              "L'écrire contre ce qui existe déjà sur le parent",
                                              sha=sha[:10], sujet=sujet, erreur=chargement.group(0).strip()[:80]))
            continue
        code = (_executer_superpose(ctx, sha, {}, commande, cap) or (None, ""))[0]
        if code != 0:
            r.erreur("tests.regression", trad("{sha} « {sujet} » : son test de régression échoue sur le "
                                              "correctif lui-même", sha=sha[:10], sujet=sujet))


def _admis_par(ctx, sha: str) -> str | None:
    """La demande validée dans la plage qui nomme ce correctif par son SHA,
    sept caractères au moins : l'humain y admet un test dont la preuve dépend
    de l'environnement (D-0047)."""
    for d in ctx.validations:
        if any(sha.startswith(m.group(0)) for m in re.finditer(r"\b[0-9a-f]{7,40}\b", d.texte)):
            return d.id
    return None


def tests_du_module(ctx, parent: str, sha: str, chemins: list[str]) -> tuple[dict[str, str], list[str]]:
    """Les fichiers de code où le correctif ajoute ou change des fonctions de
    test (Rust les écrit dans le module qu'elles testent) : pour chacun, sa
    version du parent où ne s'applique que ce qui touche les lignes de test,
    et les noms de ces fonctions. Un changement qui touche une ligne de test
    et du code à la fois s'applique en entier : il ne se sépare pas."""
    import difflib

    cfg = cfg_tests(ctx.projet)
    if cfg is None:
        return {}, []
    fichiers, noms = {}, []
    for chemin in outils.filtrer(chemins, cfg.get("paths", []), cfg.get("exclude", [])):
        avant, apres = outils.lire_a(ctx.racine, parent, chemin), outils.lire_a(ctx.racine, sha, chemin)
        if avant is None or apres is None:
            continue
        anciens = {f.nom: (f.attributs, f.corps) for f in tests_lecture.extraire(avant, chemin, cfg) if f.est_test}
        changes = [f.nom for f in tests_lecture.extraire(apres, chemin, cfg)
                   if f.est_test and anciens.get(f.nom) != (f.attributs, f.corps)]
        if not changes:
            continue
        zones = tests_lecture.zones_de_test(apres, chemin, cfg)
        a, b = avant.splitlines(keepends=True), apres.splitlines(keepends=True)
        res = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            # Une suppression pure est dedans si elle tombe entre deux lignes
            # de la même zone.
            dedans = any(debut < j2 and j1 < fin if j2 > j1 else debut < j1 < fin for debut, fin in zones)
            res += b[j1:j2] if op == "equal" or dedans else a[i1:i2]
        fichiers[chemin] = "".join(res)
        noms += [n for n in changes if n not in noms]
    return fichiers, noms


def commande_regression(cap: dict, tests: list[str]) -> str:
    """Remplit `{files}`, `{stems}` et `{test_args}` (un `test_arg` par
    fichier, où `{file}`, `{stem}`, `{module}` et `{dir}`, son dossier, se
    remplacent ; un même argument ne se répète pas). Les arguments se
    joignent par `test_arg_separator`, une espace sinon : Maven veut une
    virgule dans `-Dtest=`, le filtre de `dotnet test` un `|`."""
    gabarit = cap.get("test_arg", "--test {stem}")
    separateur = cap.get("test_arg_separator", " ")
    args = []
    for t in tests:
        module = t[: -len(Path(t).suffix)].replace("/", ".") if Path(t).suffix else t.replace("/", ".")
        dossier = str(Path(t).parent) if str(Path(t).parent) != "." else ""
        arg = (gabarit.replace("{file}", t).replace("{stem}", Path(t).stem).replace("{module}", module)
               .replace("{dir}", dossier))
        if arg not in args:
            args.append(arg)
    return (
        cap["command"]
        .replace("{files}", " ".join(tests))
        .replace("{stems}", " ".join(Path(t).stem for t in tests))
        .replace("{test_args}", separateur.join(args))
    )


def _executer_superpose(ctx, rev: str, fichiers: dict[str, str], commande: str, cap: dict) -> tuple[int, str] | None:
    """Exécute `commande` sur l'arbre de `rev`, où `fichiers` (chemin, texte)
    sont posés par-dessus, dans un worktree jetable. Rend le code de sortie
    et la sortie."""
    atelier = Path(tempfile.mkdtemp(prefix="socle-regression-"))
    arbre = atelier / "arbre"
    try:
        if not outils.git_reussit(ctx.racine, "worktree", "add", "--detach", str(arbre), rev):
            return None
        # Les dépendances installées, que git ignore (`node_modules`, `vendor`) :
        # le worktree les partage avec l'arbre de travail au lieu de les
        # réinstaller (`shared` de la capacité), ou les copie (`copied`) quand
        # leur chargeur résout les liens : l'autoload de Composer chargerait
        # sinon le code de l'arbre de travail, pas celui du parent.
        for d in cap.get("shared", []):
            if (ctx.racine / d).exists() and not (arbre / d).exists():
                (arbre / d).symlink_to(ctx.racine / d, target_is_directory=(ctx.racine / d).is_dir())
        for d in cap.get("copied", []):
            if (ctx.racine / d).is_dir() and not (arbre / d).exists():
                shutil.copytree(ctx.racine / d, arbre / d, symlinks=True)
        for t, contenu in fichiers.items():
            cible = arbre / t
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(contenu, encoding="utf-8")
        p = subprocess.run(commande, shell=True, cwd=arbre, capture_output=True, text=True,
                           timeout=cap.get("timeout", 1800))
        return p.returncode, p.stdout + p.stderr
    finally:
        outils.git_reussit(ctx.racine, "worktree", "remove", "--force", str(arbre))
        shutil.rmtree(atelier, ignore_errors=True)


@controle("mutation.couverture")
def couverture_mutation(ctx, r):
    """Tout module qui porte du code est dans le cliquet de mutation, et le
    cliquet ne nomme que des modules qui existent."""
    cap = ctx.projet.adaptateur.get("capabilities", {}).get("mutation", {})
    if "command" not in cap:
        return  # absence déclarée : `adaptateur.capacites` en répond
    caps = ctx.projet.gf("mutation", "caps", defaut={}) or {}
    porte = re.compile(cap.get("has_code", r"."))
    # `modules_exclude` : ce que l'outil ne mute pas (les tests de Go vivent à
    # côté du code qu'ils testent).
    modules = outils.filtrer(ctx.fichiers, cap.get("modules", []), cap.get("modules_exclude", []))
    for m in modules:
        if m not in caps and porte.search(ctx.lire(m) or ""):
            r.erreur("mutation.couverture", trad("module hors du cliquet de mutation : l'y poser à mesurer "
                                                 '(`"{m}" = { pending = true }` sous `[mutation.caps]` des '
                                                 "garde-fous), puis le mesurer par un balayage (`socle "
                                                 "mutation-run --record`)", m=m), m)
        elif m in caps and caps[m].get("pending"):
            # À mesurer : un avertissement, jusqu'au premier
            # balayage, qui pose le plafond mesuré.
            r.avertir("mutation.couverture", trad("module à mesurer : lancer le balayage de mutation et poser "
                                                  "son plafond (`socle mutation-run --record`), ou recopier "
                                                  "celui du dernier balayage planifié"), m)
    for m in caps:
        if m not in ctx.fichiers:
            r.erreur("mutation.couverture", trad("le cliquet nomme `{m}`, qui n'existe pas", m=m), ctx.projet.chemins.garde_fous)
        elif "reason" not in caps[m] and caps[m].get("max", 0) > 0:
            r.erreur("mutation.couverture", trad("plafond non nul sans raison écrite pour `{m}`", m=m), ctx.projet.chemins.garde_fous)


@controle("mutation.vivante", etages=("ci",))
def vivante(ctx, r):
    """Le balayage de mutation planifié tourne encore. GitHub endort les
    workflows planifiés d'un dépôt public après soixante jours sans activité,
    et le verdict ne peut pas signaler sa propre absence : ce contrôle tourne
    à chaque push, quand le code bouge."""
    from socle import mutation

    niveau, message, flux, _ = mutation.etat_du_balayage(ctx.projet, ctx.fichiers, ctx.lire)
    if niveau == "erreur":
        r.erreur("mutation.vivante", message, flux)
    elif niveau == "avertir":
        r.avertir("mutation.vivante", message, flux)
    elif niveau == "indisponible":
        r.indisponible("mutation.vivante", message)
