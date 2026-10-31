"""Garde-fous documentation ↔ code.

Chaque règle est un contrôle qui échoue en cas de divergence, au lieu de
compter sur la vigilance de l'agent. Les ensembles contrôlés sont parcourus
par motif, jamais énumérés à la main : une liste écrite à la main laisserait
le jugement décider de la couverture.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict

from socle import language as langue, memory as memoire, utils as outils
from socle.messages import trad
from socle.context import controle

# Le marqueur d'une valeur liée, lu dans les deux langues.
MARQUEUR_VALEUR = re.compile(
    r"<!--\s*(?:valeur|value)\s*:\s*(?P<nom>[\w.-]+)\s*-->(?P<valeur>.*?)<!--\s*/(?:valeur|value)\s*-->", re.S
)
MOTIFS_OUTILLAGE_DEFAUT = [
    ".socle/git-hooks/*",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".claude/settings.json",
]


@controle("docs.outillage")
def outillage(ctx, r):
    """Tout dispositif du dépôt est nommé dans la documentation."""
    motifs = ctx.projet.gf("tooling", "paths", defaut=MOTIFS_OUTILLAGE_DEFAUT)
    docs = ctx.documents()
    for chemin in outils.filtrer(ctx.fichiers, motifs):
        nom = chemin.rsplit("/", 1)[-1]
        if not any(nom in texte for c, texte in docs.items() if c != chemin):
            r.erreur("docs.outillage", trad("dispositif qu'aucun document ne nomme : `{nom}` — le nommer, avec "
                                            "ce qu'il fait et pourquoi", nom=nom), chemin)


def normaliser_valeur(v: str) -> str:
    """`70 452`, `70 452`, `70,452` et `70452` se valent : un séparateur de
    milliers précède trois chiffres. `3,5` et `3.5` se valent aussi, et ne
    valent pas `35` : une virgule ou un point devant un autre nombre de
    chiffres est décimal."""
    v = re.sub(r"<[^>]+>|[`*_]", "", v)
    v = v.strip()
    if re.fullmatch(r"\d{1,3}(?:[\s  .,]\d{3})+|\d+", v):
        return re.sub(r"[\s  .,]", "", v)
    m = re.fullmatch(r"(\d{1,3}(?:[\s  ]\d{3})*|\d+)[.,](\d+)", v)
    if m:
        return re.sub(r"[\s  ]", "", m.group(1)) + "." + m.group(2)
    return re.sub(r"\s+", " ", v)


def valeur_source(ctx, decl: dict) -> tuple[str | None, str | None]:
    """(valeur, erreur). Une source est un fichier ou une commande, lu par une
    expression régulière dont le premier groupe est la valeur."""
    regex = decl.get("regex")
    if not regex:
        return None, trad("déclaration sans `regex`")
    if "file" in decl:
        texte = ctx.lire(decl["file"])
        if texte is None:
            return None, trad("source absente : {fichier}", fichier=decl["file"])
    elif "command" in decl:
        try:
            p = subprocess.run(decl["command"], shell=True, cwd=ctx.racine, capture_output=True,
                               text=True, timeout=decl.get("timeout", 600))
        except subprocess.TimeoutExpired:
            return None, trad("la commande source a dépassé son délai : {commande}", commande=decl["command"])
        if p.returncode != 0:
            return None, trad("la commande source a échoué ({code}) : {commande}",
                              code=p.returncode, commande=decl["command"])
        texte = p.stdout
    else:
        return None, trad("déclaration sans `file` ni `command`")
    m = re.search(regex, texte, re.M)
    if not m:
        return None, trad("la regex `{regex}` ne trouve rien dans la source", regex=regex)
    return (m.group(1) if m.groups() else m.group(0)), None


@controle("docs.valeurs")
def valeurs(ctx, r):
    """Toute valeur citée dans la doc est liée à sa source, et les deux concordent."""
    decls = {d.get("name"): d for d in ctx.projet.gf("values", defaut=[]) or []}
    docs = ctx.documents()
    sources: dict[str, str | None] = {}
    for nom, decl in decls.items():
        if not nom:
            r.erreur("docs.valeurs", trad("valeur déclarée sans `name`"), ctx.projet.chemins.garde_fous)
            continue
        if "command" in decl and ctx.rapide and not decl.get("fast", False):
            sources[nom] = None
            continue
        v, err = valeur_source(ctx, decl)
        if err:
            r.erreur("docs.valeurs", f"`{nom}` : {err}", ctx.projet.chemins.garde_fous)
        sources[nom] = v

    cites = defaultdict(int)
    for chemin, texte in docs.items():
        for m in MARQUEUR_VALEUR.finditer(texte):
            nom = m["nom"]
            ligne = texte.count("\n", 0, m.start()) + 1
            cites[nom] += 1
            if nom not in decls:
                r.erreur("docs.valeurs", trad("valeur `{nom}` citée sans source déclarée (`[[values]]`)",
                                              nom=nom), chemin, ligne)
                continue
            attendu = sources.get(nom)
            if attendu is None:
                continue
            if normaliser_valeur(m["valeur"]) != normaliser_valeur(attendu):
                r.erreur("docs.valeurs", trad("`{nom}` vaut « {attendu} » à la source, la doc dit « {doc} »",
                                              nom=nom, attendu=attendu.strip(), doc=m['valeur'].strip()), chemin, ligne)

    # Une copie non liée de la valeur courante : la doc la porte sans marqueur.
    for nom, v in sources.items():
        if not v or len(normaliser_valeur(v)) < 3:
            continue
        motif = _motif_libre(v)
        for chemin, texte in docs.items():
            if memoire.couche_attendue(chemin) == "journal":
                continue  # le journal consigne des valeurs passées, pas des copies
            nu = MARQUEUR_VALEUR.sub(" ", texte)
            for m in motif.finditer(nu):
                ligne = nu.count("\n", 0, m.start()) + 1
                r.avertir("docs.valeurs", trad("« {extrait} » ressemble à la valeur `{nom}` sans marqueur : "
                                               "l'encadrer de `<!-- valeur:{nom} -->…<!-- /valeur -->`",
                                               extrait=m.group(0).strip(), nom=nom), chemin, ligne)


def _motif_libre(v: str) -> re.Pattern:
    n = normaliser_valeur(v)
    if n.isdigit():
        # Les chiffres, un séparateur permis seulement devant un groupe de trois.
        corps = "".join((r"[\s  ,.]?" if k and (len(n) - k) % 3 == 0 else "") + re.escape(c)
                        for k, c in enumerate(n))
        return re.compile(rf"(?<![\d.,]){corps}(?![\d]|[.,]\d)")
    if re.fullmatch(r"\d+\.\d+", n):
        # Un décimal, à la virgule ou au point.
        entier, dec = n.split(".")
        return re.compile(rf"(?<![\d.,]){re.escape(entier)}[.,]{re.escape(dec)}(?![\d])")
    return re.compile(re.escape(n))


def dispenses(ctx) -> list[str]:
    res = []
    for c in ctx.commits:
        for v in langue.trailers(c["message"]).get("dispense-doc", []):
            if len(v.strip()) >= 15:
                res.append(v.strip())
    return res


def fichiers_dispenses(ctx) -> dict[str, str]:
    """{fichier : raison} : les fichiers que change un commit qui porte une
    dispense de doc motivée."""
    res = {}
    for c in ctx.commits:
        raisons = [v.strip() for v in langue.trailers(c["message"]).get("dispense-doc", []) if len(v.strip()) >= 15]
        if raisons and c["parents"]:
            for f in outils.fichiers_changes(ctx.racine, c["parents"][0], c["sha"]):
                res.setdefault(f, raisons[0])
    return res


@controle("docs.correspondance", etages=("agent", "ci"), base=True)
def correspondance(ctx, r):
    """Si du code change, la doc qui lui est associée change aussi — ou une
    dispense écrite et motivée l'accompagne (`Dispense-doc: <raison>`), qui
    ne vaut que pour le code de son propre commit.

    Pas à l'étage git : le hook pre-commit ne voit pas le message du commit,
    donc pas la dispense qu'il porte."""
    table = ctx.projet.gf("docmap", defaut=[]) or []
    if not table:
        return
    changes = ctx.changes
    dispenses = fichiers_dispenses(ctx)
    for ligne in table:
        code = outils.filtrer(changes, ligne.get("code", []))
        if not code:
            continue
        docs = outils.filtrer(changes, ligne.get("docs", []))
        if docs:
            continue
        # Une dispense couvre le code du commit qui la porte, pas toute la
        # plage ni toute la table.
        restants = [c for c in code if c not in dispenses]
        if not restants:
            r.avertir("docs.correspondance", trad("{n} fichier(s) de code sans doc associée, dispensé : « "
                                                  "{dispenses} »", n=len(code), dispenses=dispenses[code[0]]))
            continue
        r.erreur(
            "docs.correspondance",
            trad("code changé sans sa doc associée : {code} → mettre à jour {docs}, ou motiver une dispense par un "
                 "trailer de commit `Dispense-doc: <raison>`, dans le commit qui change ce code",
                 code=", ".join(restants[:5]) + (" …" if len(restants) > 5 else ""),
                 docs=trad(" ou ").join(ligne.get("docs", []))),
        )


def paragraphes(texte: str):
    """(ligne de début, paragraphe normalisé) ; les blocs de code comptent
    pour un paragraphe chacun."""
    bloc, debut = [], None
    for i, ligne in enumerate(texte.splitlines(), start=1):
        if ligne.strip():
            if debut is None:
                debut = i
            bloc.append(ligne.strip())
        elif bloc:
            yield debut, " ".join(bloc)
            bloc, debut = [], None
    if bloc:
        yield debut, " ".join(bloc)


@controle("docs.copie")
def copie(ctx, r):
    """Un même contenu dans deux fichiers est une copie qui divergera : refusé.

    Sauf dans les demandes : le contrat veut qu'une demande se lise seule,
    son contexte résumé sur place plutôt que renvoyé ailleurs, et elle est
    gelée une fois répondue. Deux approbations écrites par le même gabarit
    se ressemblent forcément."""
    minimum = ctx.projet.gf("nocopy", "min_chars", defaut=200)
    ch = ctx.projet.chemins
    exclus = ctx.projet.exclusions_docs() + list(ctx.projet.gf("nocopy", "exclude", defaut=[])) + [
        f"{ch.demandes}/**", f"{ch.dans_prive(ch.demandes)}/**"]
    vus: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for chemin, texte in ctx.textes(["**/*.md"], exclus).items():
        for debut, p in paragraphes(texte):
            if len(p) >= minimum:
                vus[re.sub(r"\s+", " ", p)].append((chemin, debut))
    for p, lieux in vus.items():
        fichiers = {c for c, _ in lieux}
        if len(fichiers) > 1:
            premier = lieux[0]
            autres = ", ".join(f"{c}:{l}" for c, l in lieux[1:])
            r.erreur("docs.copie", trad("paragraphe identique aussi présent en {autres} : garder une source, "
                                        "renvoyer vers elle", autres=autres), premier[0], premier[1])
