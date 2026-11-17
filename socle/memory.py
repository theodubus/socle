"""Lecture de la mémoire : six couches de markdown qu'un script sait lire.

Le format est décrit dans `engine/socle/FORMAT.md`. En bref :

- chaque fichier de mémoire commence par `<!-- socle: couche=… zone=… -->` ;
- une entrée est un titre `## <ID> — <titre>`, suivi d'une ligne de
  métadonnées `> clé : valeur · clé : valeur` ;
- un identifiant est stable : `F-0001` (fait), `B-0001` (besoin),
  `T-0001` (tâche), `L-0001` (lot), `JA-0001` (jalon), `ADR-0001`
  (décision), `D-0001` (demande), `J-2026-10-10-A` (journal) ; préfixé de
  `P` dans la zone privée (`PF-0001`, `PJ-…`).

Ce module ne juge rien : il lit. Les contrôles vivent dans `controles_memoire`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from socle import config, language as langue, utils as outils
from socle.messages import a_traduire, trad

TYPES = {
    "F": "canonique",
    "B": "backlog",
    "T": "backlog",
    "L": "backlog",
    "JA": "backlog",
    "ADR": "decisions",
    "J": "journal",
    "D": "demandes",
}
# Les quatre formes d'une entrée du backlog, chacune son préfixe (ADR-0083) :
# un besoin, une tâche, un lot, un jalon. La forme se lit sur l'identifiant.
BACKLOG = ("B", "T", "L", "JA")
FORMES = {"B": "besoin", "T": "tache", "L": "lot", "JA": "jalon"}
COUCHES = ("canonique", "actif", "decisions", "journal", "backlog", "demandes")
ZONES = ("publique", "privee")

# Un identifiant, où qu'il soit. La forme du numéro est vérifiée après coup :
# `J-` exige une date et une lettre, les autres quatre chiffres.
ID_RE = re.compile(
    r"(?<![\w-])(?P<prive>P?)(?P<type>ADR|JA|F|B|T|L|D|J)-"
    r"(?P<num>\d{4}(?:-\d{2}-\d{2}-[A-Z]{1,2})?)(?![\w-])"
)
NUM_JOURNAL = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Z]{1,2}$")
NUM_SIMPLE = re.compile(r"^\d{4}$")

TITRE_RE = re.compile(r"^(?P<niveau>#{1,6})\s+(?P<reste>.*?)\s*#*\s*$")
ENTETE_ENTREE = re.compile(
    r"^(?P<id>P?(?:ADR|JA|F|B|T|L|D|J)-[\d-]+[A-Z]{0,2})\s*[—–-]\s*(?P<titre>.+)$"
)
# Un titre qui commence comme une entrée, lisible ou non.
TITRE_D_ENTREE = re.compile(r"^P?(?:ADR|JA|F|B|T|L|D|J)-\d")
ENTETE_FICHIER = re.compile(r"<!--\s*socle\s*:(?P<corps>.*?)-->")
# La liste des termes privés n'est pas un fichier de mémoire : son en-tête est
# celui d'un texte brut, et la dit lisible comme l'autre.
ENTETE_TERMES = "# socle: termes privés"
CLOTURE_CODE = re.compile(r"^\s*(```|~~~)")

# Statuts lisibles par machine, sous leur forme canonique (sans accents).
STATUTS = {
    "F": {"mesure", "suppose", "refute", "valide"},
    **{t: {"ouvert", "en-cours", "bloque", "fait", "abandonne"} for t in BACKLOG},
    "ADR": {"proposee", "acceptee", "remplacee", "rejetee", "abandonnee"},
}
BACKLOG_CLOS = {"fait", "abandonne"}
# Le sous-dossier du backlog en dossier où `socle archive` range les sujets
# clos, à l'écart des ouverts.
DOSSIER_CLOS = "closed"

# Une entrée publique basculée dans la mémoire privée : elle garde
# son identifiant, pour que les renvois restent valides, et perd son titre et
# son texte, repris par une copie privée qui cite `depuis : <identifiant>`.
TITRE_BASCULEE = langue.TEXTES["titre-basculee"]["fr"]
TEXTE_BASCULEE = langue.TEXTES["texte-basculee"]["fr"]


# La mémoire et sa zone privée (même arborescence).
DOSSIER = config.FORMAT_ACTUEL.memoire
DOSSIER_PRIVE = config.FORMAT_ACTUEL.prive
SUFFIXE_REPONSE = config.FORMAT_ACTUEL.reponse


def est_memoire(chemin: str) -> bool:
    return chemin.startswith(DOSSIER + "/")


def est_prive(chemin: str) -> bool:
    return chemin.startswith(DOSSIER_PRIVE + "/")


def est_reponse(chemin: str) -> bool:
    """Une réponse humaine, à côté de sa demande."""
    return est_memoire(chemin) and chemin.endswith(SUFFIXE_REPONSE)


def demande_de_reponse(chemin: str) -> str:
    """Le chemin de la demande à laquelle répond un fichier de réponse."""
    return chemin[: -len(SUFFIXE_REPONSE)] + ".md" if chemin.endswith(SUFFIXE_REPONSE) else chemin


def dossier_propre(chemin: str) -> str | None:
    """Le dossier d'un fichier qui porte une seule entrée (une décision, une
    demande, un sujet du backlog) ; `None` pour un fichier qui en porte
    plusieurs."""
    if couche_attendue(chemin) in ("decisions", "demandes", "backlog"):
        return chemin.rsplit("/", 1)[0]
    return None


def nom_de_fichier(titre: str) -> str:
    """Le titre d'une entrée qui a son propre fichier (décision, demande,
    sujet du backlog), réduit pour son nom : `ADR-0003-<ceci>.md`."""
    s = re.sub(r"[^a-z0-9]+", "-", outils.sans_accents(titre).lower()).strip("-")
    return s[:50].rstrip("-") or "sans-titre"


def hors_zone_privee(chemin: str) -> str:
    """Un chemin de la zone privée, relatif à elle (son chemin dans le dépôt
    privé) ; inchangé hors de la zone privée."""
    return chemin[len(DOSSIER_PRIVE) + 1:] if est_prive(chemin) else chemin


def lisible(texte: str | None) -> bool:
    """Un fichier de mémoire se lit en clair quand sa première ligne non vide
    porte l'en-tête du socle ; chiffré, il ne se lit pas. La liste des termes
    privés se reconnaît au sien."""
    for ligne in (texte or "").splitlines():
        if ligne.strip():
            return bool(ENTETE_FICHIER.search(ligne)) or ligne.lstrip().startswith(ENTETE_TERMES)
    return False


def fichiers_compagnon(racine: Path) -> list[str]:
    """Les fichiers du clone du dépôt privé (mode compagnon), que le dépôt
    public ignore : `git ls-files` ne les voit pas."""
    import os

    p = racine / config.FORMAT_ACTUEL.prive
    if not (p / ".git").exists():
        return []
    res = []
    for dossier, sous, noms in os.walk(p):
        sous[:] = [s for s in sous if s != ".git"]
        res += [str((Path(dossier) / n).relative_to(racine)).replace(os.sep, "/") for n in noms]
    return sorted(res)


def id_valide(type_: str, num: str) -> bool:
    if type_ == "J":
        return bool(NUM_JOURNAL.match(num))
    return bool(NUM_SIMPLE.match(num))


def decouper_id(ident: str) -> tuple[bool, str, str] | None:
    m = ID_RE.fullmatch(ident)
    if not m or not id_valide(m["type"], m["num"]):
        return None
    return bool(m["prive"]), m["type"], m["num"]


def fichier_journal(dossier: Path, mois: str, budget: int | None = None, ajout: int = 0) -> Path:
    """Le fichier du journal où écrire une entrée de `ajout` octets : celui du
    mois (`AAAA-MM.md`), puis `AAAA-MM-2.md`, `AAAA-MM-3.md`… quand le
    précédent dépasserait son budget. Le journal est en ajout seul : un
    fichier plein ne se vide pas, le mois continue dans le suivant."""
    n = 1
    while True:
        p = dossier / (f"{mois}.md" if n == 1 else f"{mois}-{n}.md")
        suivant = dossier / f"{mois}-{n + 1}.md"
        if not suivant.is_file() and (not p.is_file() or budget is None or p.stat().st_size + ajout <= budget):
            return p
        n += 1


def lignes_hors_code(texte: str):
    """(numéro de ligne, ligne, dans_un_bloc_de_code) pour chaque ligne."""
    dedans = False
    for i, ligne in enumerate(texte.splitlines(), start=1):
        if CLOTURE_CODE.match(ligne):
            yield i, ligne, True
            dedans = not dedans
            continue
        yield i, ligne, dedans


# Un texte barré (`~~…~~`, `<s>…</s>`, `<del>…</del>`) dit ce qui n'est plus :
# ses chemins et ses liens ne se jugent pas comme vivants (B-0087).
TEXTE_BARRE = re.compile(r"~~[^~\n]+?~~|<(?P<balise>s|del|strike)>.*?</(?P=balise)>", re.I)


def sans_barre(ligne: str) -> str:
    """La ligne sans ce qu'elle barre."""
    return TEXTE_BARRE.sub(" ", ligne)


def mentions(texte: str) -> list[tuple[str, int]]:
    """Les identifiants mentionnés hors des blocs de code clôturés, avec leur
    ligne. Les blocs clôturés portent des exemples, pas des références."""
    res = []
    for i, ligne, code in lignes_hors_code(texte):
        if code:
            continue
        for m in ID_RE.finditer(ligne):
            if id_valide(m["type"], m["num"]):
                res.append((m.group(0), i))
    return res


def parser_meta(lignes: list[str]) -> dict[str, str]:
    """`> statut : mesuré · preuve : commit:abc1234` → {"statut": "mesuré", …}.

    Clés sans accents ni majuscules, valeurs telles qu'écrites (accents graves
    compris : ils délimitent les commandes). Le séparateur est le point médian
    seul — une barre verticale apparaît trop souvent dans une commande."""
    brut = " · ".join(l.lstrip().removeprefix(">").strip() for l in lignes)
    meta: dict[str, str] = {}
    for morceau in re.split(r"\s+·\s+|^·\s+", brut):
        if ":" not in morceau:
            continue
        k, v = morceau.split(":", 1)
        k = outils.cle(k)
        if not k or " " in k:
            continue
        meta[langue.champ(k)] = v.strip()
    return meta


def nettoyer(valeur: str) -> str:
    return valeur.strip().strip("`").strip()


# Une référence dans une valeur de métadonnée : `commit:abc1234`,
# `fichier:chemin[#ancre|:ligne]`, `cmd:outil` ou ``cmd:`commande, avec virgule` ``,
# `url:…` (jamais suivie : aucun service externe). Les identifiants de mémoire
# se reconnaissent seuls.
# Une forme entre accents graves commence sans espace : sinon « `commit:` et
# la suite » se lirait comme une référence qui court jusqu'au prochain accent.
REF_RE = re.compile(
    r"(?P<type>commit|fichier|file|cmd|url):(?:`(?P<entre>[^`\s][^`]*)`|(?P<nu>[^\s,;`]+))"
)


def sans_ponctuation_finale(cible: str) -> str:
    """Une référence nue en fin de phrase, ou entre parenthèses, sans le point
    ou la parenthèse qui la suit ; une parenthèse ouverte dans la
    référence garde sa fermante."""
    while cible:
        fin = cible[-1]
        if fin in ".:!?»\"'" or (fin == ")" and cible.count(")") > cible.count("(")) \
                or (fin == "]" and cible.count("]") > cible.count("[")):
            cible = cible[:-1]
        else:
            break
    return cible


def references(valeur: str) -> list[tuple[str, str]]:
    """[(type, cible)] : types `commit`, `fichier`, `cmd`, `url`, `id`."""
    res = []
    for m in REF_RE.finditer(valeur):
        cible = m["entre"] if m["entre"] else sans_ponctuation_finale(m["nu"])
        res.append((langue.reference(m["type"]), cible.strip()))
    sans_refs = REF_RE.sub(" ", valeur)
    for m in ID_RE.finditer(sans_refs):
        if id_valide(m["type"], m["num"]):
            res.append(("id", m.group(0)))
    return res


@dataclass
class Entree:
    id: str
    type: str
    prive: bool
    titre: str
    barre: bool
    meta: dict[str, str]
    niveau: int
    fichier: str
    ligne: int
    texte: str
    corps: str
    parent: str | None = None  # l'entrée de journal qui l'archive, le cas échéant

    @property
    def statut(self) -> str:
        """Sous sa clé interne, quelle que soit la langue où il est écrit."""
        return langue.statut(self.type, nettoyer(self.meta.get("statut", "")))

    def refs(self, *cles: str) -> list[tuple[str, str]]:
        res = []
        for k in cles:
            if k in self.meta:
                res += references(self.meta[k])
        return res

    @property
    def archivee(self) -> bool:
        return self.parent is not None

    @property
    def basculee(self) -> bool:
        """Une entrée publique dont le contenu est passé dans la mémoire privée."""
        return "basculee" in self.meta

    @property
    def depuis(self) -> list[str]:
        """Les entrées publiques que cette copie privée reprend."""
        return [c for t, c in self.refs("depuis") if t == "id"]

    @property
    def anciens(self) -> list[str]:
        """Les numéros qu'une entrée renumérotée a portés (`ancien : B-0235`,
        ADR-0083) : ils se résolvent vers elle, et ne se réattribuent
        jamais."""
        return [c for t, c in self.refs("ancien") if t == "id"]

    @property
    def forme(self) -> str | None:
        """La forme d'une entrée du backlog, lue sur son identifiant :
        `besoin`, `tache`, `lot` ou `jalon` ; `None` hors du backlog."""
        return FORMES.get(self.type)


@dataclass
class FichierMemoire:
    chemin: str
    texte: str
    couche: str | None = None
    zone: str | None = None
    entete: dict[str, str] = field(default_factory=dict)
    entrees: list[Entree] = field(default_factory=list)
    # Les titres qui commencent comme une entrée sans en être une lisible
    # (`## J-2026-10-10 titre`) : (ligne, titre). L'entrée n'est pas lue.
    illisibles: list[tuple[int, str]] = field(default_factory=list)


def couche_attendue(chemin: str) -> str | None:
    """La couche que l'emplacement impose. `None` : pas un fichier de mémoire.
    Les couches gardent leurs noms internes, quel que soit le nom du fichier."""
    if not est_memoire(chemin) or not chemin.endswith(".md"):
        return None
    f = config.FORMAT_ACTUEL
    if est_prive(chemin):  # la zone privée reprend la même arborescence
        chemin = f.memoire + "/" + hors_zone_privee(chemin)
    if chemin.startswith(f.archives + "/") or chemin == f.memoire + "/README.md":
        return None
    for couche, lieu in (("canonique", f.canonique), ("actif", f.actif)):
        if chemin == lieu:
            return couche
    for couche, lieu in (("backlog", f.backlog), ("decisions", f.decisions),
                         ("journal", f.journal), ("demandes", f.demandes)):
        reste = chemin[len(lieu) + 1:] if chemin.startswith(lieu + "/") else None
        if couche == "backlog" and reste and reste.startswith(DOSSIER_CLOS + "/"):
            reste = reste[len(DOSSIER_CLOS) + 1:]
        if reste is not None and "/" not in reste:
            return couche
    return "inconnue"


def parmi_les_clos(chemin: str) -> bool:
    """Le fichier d'un sujet rangé avec les sujets clos."""
    return couche_attendue(chemin) == "backlog" and chemin.rsplit("/", 2)[-2:-1] == [DOSSIER_CLOS]


def hors_des_clos(chemin: str) -> str:
    """Le chemin d'un sujet comme s'il était parmi les ouverts : ce que
    ses plafonds visent, où qu'il soit rangé."""
    if not parmi_les_clos(chemin):
        return chemin
    dossier, nom = chemin.rsplit("/", 1)
    return dossier.removesuffix("/" + DOSSIER_CLOS) + "/" + nom


def analyser(chemin: str, texte: str) -> FichierMemoire:
    f = FichierMemoire(chemin=chemin, texte=texte)
    lignes = texte.splitlines()
    for ligne in lignes:
        if ligne.strip():
            m = ENTETE_FICHIER.search(ligne)
            if m:
                for paire in m["corps"].split():
                    if "=" in paire:
                        k, v = langue.entete(*paire.split("=", 1))
                        f.entete[k] = v
                f.couche = f.entete.get("couche")
                f.zone = f.entete.get("zone")
            break

    # Les titres hors des blocs de code.
    titres = []
    for i, ligne, code in lignes_hors_code(texte):
        if code:
            continue
        m = TITRE_RE.match(ligne)
        if m:
            titres.append((i, len(m["niveau"]), m["reste"]))

    pile: list[Entree] = []  # entrées ouvertes, pour rattacher les archives
    for k, (i, niveau, reste) in enumerate(titres):
        # Fin du bloc : le prochain titre de niveau inférieur ou égal.
        fin = len(lignes)
        for j, niv2, _ in titres[k + 1 :]:
            if niv2 <= niveau:
                fin = j - 1
                break
        while pile and pile[-1].niveau >= niveau:
            pile.pop()
        m = ENTETE_ENTREE.match(reste)
        morceaux = decouper_id(m["id"]) if m else None
        if morceaux is None:
            if TITRE_D_ENTREE.match(reste):
                f.illisibles.append((i, reste))
            continue
        prive, type_, _ = morceaux
        titre = m["titre"].strip()
        barre = titre.startswith("~~") and titre.endswith("~~") and len(titre) > 4
        bloc = lignes[i - 1 : fin]
        # La ligne de métadonnées : les lignes `>` qui suivent le titre,
        # après d'éventuelles lignes vides.
        j = 1
        while j < len(bloc) and not bloc[j].strip():
            j += 1
        meta_lignes = []
        while j < len(bloc) and bloc[j].lstrip().startswith(">"):
            meta_lignes.append(bloc[j])
            j += 1
        e = Entree(
            id=m["id"],
            type=type_,
            prive=prive,
            titre=titre.strip("~").strip() if barre else titre,
            barre=barre,
            meta=parser_meta(meta_lignes),
            niveau=niveau,
            fichier=chemin,
            ligne=i,
            texte="\n".join(bloc).rstrip(),
            corps="\n".join(bloc[j:]).strip(),
        )
        parents = [p for p in pile if p.type == "J"]
        if parents and type_ != "J":
            e.parent = parents[-1].id
        f.entrees.append(e)
        pile.append(e)
    return f


@dataclass
class Memoire:
    """Toute la mémoire d'une révision (ou de l'arbre de travail)."""

    racine: Path
    rev: str | None
    fichiers: dict[str, FichierMemoire] = field(default_factory=dict)
    illisibles: list[str] = field(default_factory=list)  # privés, chiffrés ici
    # Les demandes qui ont leur réponse, par le chemin de la demande : un sujet
    # qui en attend une est prêt une fois qu'elle est répondue (D-0064).
    repondues: set[str] = field(default_factory=set)

    @classmethod
    def charger(cls, racine: Path, rev: str | None = None) -> "Memoire":
        mem = cls(racine=racine, rev=rev)
        if rev is None:
            chemins = sorted(set(outils.fichiers_courants(racine)) | set(fichiers_compagnon(racine)))
        else:
            chemins = outils.fichiers_a(racine, rev)
        mem.repondues = {demande_de_reponse(c) for c in chemins if est_reponse(c)}
        chemins = [c for c in chemins if couche_attendue(c) is not None]
        # À une révision, tous les fichiers d'un coup : un `git show` par
        # fichier coûtait l'essentiel de la lecture prouvée.
        textes = outils.lire_plusieurs(racine, rev, chemins) if rev is not None else {}
        for c in chemins:
            texte = textes.get(c) if rev is not None else outils.lire_a(racine, rev, c)
            if texte is None:
                continue
            if est_prive(c) and not lisible(texte):
                mem.illisibles.append(c)
                continue
            mem.fichiers[c] = analyser(c, texte)
        return mem

    def entrees(self, type_: str | tuple[str, ...] | None = None):
        """Les entrées d'un type, ou de plusieurs (`BACKLOG`, les quatre
        formes du backlog)."""
        types = (type_,) if isinstance(type_, str) else type_
        for f in self.fichiers.values():
            for e in f.entrees:
                if types is None or e.type in types:
                    yield e

    def definitions(self) -> dict[str, list[Entree]]:
        res: dict[str, list[Entree]] = {}
        for e in self.entrees():
            res.setdefault(e.id, []).append(e)
        return res

    def entree(self, ident: str) -> Entree | None:
        defs = self.definitions().get(ident)
        return defs[0] if defs else None

    def anciens(self) -> dict[str, Entree]:
        """{ancien numéro : l'entrée qui le porte désormais} (ADR-0083)."""
        return {a: e for e in self.entrees(BACKLOG) for a in e.anciens}

    def resoudre(self, ident: str) -> Entree | None:
        """L'entrée d'un identifiant, ou celle qu'un ancien numéro désigne
        désormais."""
        return self.entree(ident) or self.anciens().get(ident)

    def prochain_id(self, type_: str, prive: bool = False, date: str | None = None,
                    pris_ailleurs: set[str] = frozenset()) -> str:
        """Le prochain identifiant libre d'un type. Calculé, jamais deviné :
        deux sessions qui devinent tombent sur le même. `pris_ailleurs` : ceux
        que d'autres branches ont déjà pris. Un ancien numéro reste pris."""
        return prochain_libre(type_, set(self.definitions()) | set(self.anciens()) | set(pris_ailleurs), prive,
                              date)


def prochain_libre(type_: str, pris: set[str], prive: bool = False, date: str | None = None) -> str:
    """Le premier identifiant d'un type que `pris` ne contient pas : le
    numéro qui suit le plus grand, ou la lettre suivante du jour."""
    prefixe = ("P" if prive else "") + type_ + "-"
    if type_ == "J":
        if date is None:
            raise ValueError(trad("un identifiant de journal exige une date"))
        for lettre in _lettres():
            cand = f"{prefixe}{date}-{lettre}"
            if cand not in pris:
                return cand
    n = 1 + max(
        (int(i[len(prefixe):]) for i in pris if i.startswith(prefixe) and i[len(prefixe):].isdigit()),
        default=0,
    )
    return f"{prefixe}{n:04d}"


def _lettres():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    yield from alphabet
    for a in alphabet:
        for b in alphabet:
            yield a + b


# --------------------------------------------------------------------------
# Lecture prouvée
# --------------------------------------------------------------------------
#
# Une entrée a une empreinte : les huit premiers caractères du SHA-256 de son
# texte. Citer `ADR-0003@1a2b3c4d`, c'est montrer qu'on a eu sous les yeux
# CETTE version de l'entrée : l'empreinte ne s'obtient qu'en la lisant
# (`socle show`), et elle change dès que l'entrée change. Un index — la liste
# des décisions, celle du backlog ouvert — a la sienne, `decisions@…` ou
# `backlog@…`, qui prouve qu'on a consulté l'ensemble avant d'y ajouter.
# Ça ne prouve pas qu'on a compris ; ça prouve qu'on a lu, et quelle version.

CITATION_RE = re.compile(
    r"(?<![\w-])(?P<id>P?(?:ADR|JA|F|B|T|L|D|J)-\d{4}(?:-\d{2}-\d{2}-[A-Z]{1,2})?)@(?P<empreinte>[0-9a-f]{8})(?![\w-])"
)
INDEX_RE = re.compile(r"(?<![\w-])(?P<index>decisions|backlog)@(?P<empreinte>[0-9a-f]{8})(?![\w-])")
INDEX_TYPES = {"decisions": ("ADR",), "backlog": BACKLOG}


def empreinte_entree(e: Entree) -> str:
    """L'empreinte d'une entrée : son titre et son corps, sans sa ligne de
    métadonnées (les lignes `>` qui suivent le titre). Changer un statut, ce
    qu'une entrée attend ou ce qu'elle a lu ne périme plus ses citations, et
    deux entrées qui se citent dans leurs métadonnées ne se périment plus
    l'une l'autre (D-0086, ADR-0053)."""
    lignes = e.texte.strip().splitlines()
    j = 1
    while j < len(lignes) and not lignes[j].strip():
        j += 1
    k = j
    while k < len(lignes) and lignes[k].lstrip().startswith(">"):
        k += 1
    corps = "\n".join(l.rstrip() for l in lignes[k:]).strip()
    titre = lignes[0].rstrip() if lignes else ""
    return outils.sha256(f"{titre}\n{corps}" if corps else titre)[:8]


def empreinte_texte_entier(e: Entree) -> str:
    """L'empreinte du texte entier de l'entrée, métadonnées comprises : celle
    des citations écrites avant D-0086, qui restent valides tant qu'elles
    correspondent."""
    texte = "\n".join(l.rstrip() for l in e.texte.strip().splitlines())
    return outils.sha256(texte)[:8]


def empreintes_entree(e: Entree) -> set[str]:
    """Les empreintes qu'une citation de cette version peut porter."""
    return {empreinte_entree(e), empreinte_texte_entier(e)}


def lignes_index(mem: "Memoire", index: str, sauf: set[str] = frozenset()) -> list[str]:
    """Une ligne par entrée : décisions en vigueur ou non, backlog non clos."""
    res = []
    for e in mem.entrees(INDEX_TYPES[index]):
        if e.archivee or e.basculee or e.id in sauf:
            continue
        if index == "backlog" and e.statut in BACKLOG_CLOS:
            continue
        res.append(f"{e.id} — {e.titre} ({e.statut})")
    return sorted(res)


# --------------------------------------------------------------------------
# L'ordre du backlog (ADR-0083) : un besoin, une tâche, un lot ou un jalon
# attend d'autres entrées (`après`) ; une tâche nomme son besoin, un lot
# attend ses tâches, un jalon ses besoins ; ce qui vient ensuite se calcule.
# --------------------------------------------------------------------------


def dependances(e: Entree) -> list[str]:
    """Ce qu'une entrée du backlog attend (`après : B-0012, D-0014`) : des
    entrées du backlog, et des demandes, attendues jusqu'à leur réponse
    (D-0064)."""
    return [c for t, c in e.refs("apres") if t == "id"]


def est_besoin(e: Entree) -> bool:
    return e.type == "B"


def est_tache(e: Entree) -> bool:
    return e.type == "T"


def est_lot(e: Entree) -> bool:
    """Un lot (`L-`) : les tâches qu'on mène et relit ensemble, qu'il attend
    par `après`, avec le lot d'avant (ADR-0079, ADR-0083). Il n'est jamais à
    prendre ; il se clôt quand ses tâches le sont."""
    return e.type == "L"


def est_jalon(e: Entree) -> bool:
    """Un jalon (`JA-`) : les besoins qui servent un même but, qu'il attend,
    avec le jalon d'avant."""
    return e.type == "JA"


def besoin_de(e: Entree) -> str | None:
    """Le besoin qu'une tâche sert (`besoin : B-NNNN`)."""
    ids = [c for t, c in e.refs("besoin") if t == "id"]
    return ids[0] if ids else None


def type_d_id(ident: str) -> str | None:
    """Le type d'un identifiant (`T`, `JA`…), `None` s'il n'en est pas un."""
    morceaux = decouper_id(ident)
    return morceaux[1] if morceaux else None


# Ce que chaque forme attend par `après` (D-0123, point 2) : un besoin, des
# besoins et des demandes ; une tâche, des tâches, des besoins et des
# demandes ; un lot, ses tâches, des demandes et le lot d'avant ; un jalon,
# ses besoins, des demandes et le jalon d'avant.
ATTENDUS = {"B": ("B", "D"), "T": ("T", "B", "D"), "L": ("T", "D", "L"), "JA": ("B", "D", "JA")}

PRIORITES = ("haute", "basse")


def priorite(e: Entree) -> str | None:
    """La priorité écrite d'une entrée (`priorité : haute` ou `basse`,
    D-0062), sous sa clé interne ; `None` pour la priorité normale, qui ne
    s'écrit pas."""
    v = nettoyer(e.meta.get("priorite", ""))
    return langue.valeur(v) if v else None


def priorite_effective(e: Entree, entrees: dict[str, Entree]) -> str | None:
    """Celle d'une entrée, et celle de son besoin pour une tâche qui n'en a
    pas (ADR-0083)."""
    p = priorite(e)
    if p is None and est_tache(e) and besoin_de(e) in entrees:
        p = priorite(entrees[besoin_de(e)])
    return p


def demande_close(mem: "Memoire", e: Entree) -> bool:
    """Une demande qui n'est plus attendue : répondue, ou retirée."""
    return e.fichier in mem.repondues or "retiree" in e.meta


def _section(mots: dict) -> re.Pattern:
    return re.compile(r"^#{2,4}\s+(?:%s)\s*$" % "|".join(re.escape(x) for x in mots.values()), re.M | re.I)


SECTION_FAIT_QUAND = _section(langue.FAIT_QUAND)
SECTION_SATISFAIT_QUAND = _section(langue.SATISFAIT_QUAND)
CASE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$")


def section_de(e: Entree) -> re.Pattern:
    """La section des critères d'une entrée : « Satisfait quand » pour un
    besoin, un résultat ; « Fait quand » pour les autres formes."""
    return SECTION_SATISFAIT_QUAND if est_besoin(e) else SECTION_FAIT_QUAND


def criteres(e: Entree, section: re.Pattern | None = None) -> list[tuple[bool, str]]:
    """Les critères de la section d'une entrée (D-0064, ADR-0083), ou de
    `section` : (coché, texte), dans l'ordre ; vide sans section."""
    m = (section or section_de(e)).search(e.corps)
    if not m:
        return []
    res = []
    for ligne in e.corps[m.end():].splitlines():
        if ligne.startswith("#"):
            break
        c = CASE.match(ligne)
        if c:
            res.append((c.group(1) != " ", c.group(2)))
    return res


# --------------------------------------------------------------------------
# Les revues d'un lot (D-0124, ADR-0084) : sa section « Revues », une passe
# par dossier de `socle review`, chacune ses bloquants et son recul.
# --------------------------------------------------------------------------


def _mots(cle: str) -> str:
    return "|".join(re.escape(m) for m in langue.REVUES[cle].values())


SECTION_REVUES = _section(langue.REVUES["revues"])
TITRE_DE_PASSE = re.compile(r"^#{3,6}\s+(?:%s)\s+(?P<n>\d+)\b\s*(?:[—–-]\s*(?P<date>.*?))?\s*$" % _mots("passe"),
                            re.I)
LIGNE_COMMITS = re.compile(r"^\s*(?:%s)\s*:\s*(?P<debut>[0-9a-f]{4,40})\.\.(?P<tete>[0-9a-f]{4,40})\s*$"
                           % _mots("commits"), re.I)
LIGNE_BLOQUANT = re.compile(r"^\s*[-*]\s+(?:%s)\s*:\s*(?P<texte>.+?)\s*$" % _mots("bloquant"), re.I)
# Le regard du relecteur sur un bloquant, à partir de la deuxième passe :
# `· même cause` (suivi, au besoin, de laquelle) ou `· cause nouvelle`.
REGARD = re.compile(r"\s*·\s*(?:(?P<meme>%s)|(?P<nouvelle>%s))(?![\w-]).*$" % (_mots("meme-cause"),
                                                                                  _mots("cause-nouvelle")), re.I)
DEBUT_DU_RECUL = re.compile(r"^\s*(?:%s)\s*:" % _mots("recul"), re.I)
MOT = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
# Un recul répond aux trois questions de nature en soixante mots au moins
# (D-0124, point 4).
MOTS_DU_RECUL = 60
DECISIONS_DU_RECUL = {outils.cle(m): cle for cle in ("continuer", "s-arreter")
                      for m in langue.REVUES[cle].values()}


@dataclass
class Passe:
    """Une passe de revue d'un lot, telle que sa section « Revues » la
    garde : son numéro et sa date, les commits relus (`debut..tete`, tels
    que `socle review` les a écrits), ses bloquants (leur cause, et le
    regard du relecteur : `meme`, `nouvelle`, ou `None` s'il n'est pas
    consigné), et son recul, le paragraphe qui commence par « Recul : »."""

    numero: int
    date: str
    debut: str | None = None
    tete: str | None = None
    bloquants: list[tuple[str, str | None]] = field(default_factory=list)
    recul: str | None = None

    @property
    def voit_revenir(self) -> bool:
        """Le relecteur y voit au moins une cause revenir."""
        return any(regard == "meme" for _, regard in self.bloquants)


def _bornes_des_revues(e: Entree) -> tuple[int, int] | None:
    """Où commence et finit la section « Revues » dans le corps d'une
    entrée : jusqu'au titre suivant de même niveau ou plus haut."""
    m = SECTION_REVUES.search(e.corps)
    if not m:
        return None
    niveau = len(m.group(0)) - len(m.group(0).lstrip("#"))
    fin = re.compile(r"^#{1,%d}\s" % niveau, re.M).search(e.corps, m.end())
    return m.start(), fin.start() if fin else len(e.corps)


def section_des_revues(e: Entree) -> str | None:
    """Le texte de la section « Revues » d'une entrée, titre compris."""
    bornes = _bornes_des_revues(e)
    return e.corps[bornes[0]:bornes[1]].strip() if bornes else None


def passes(e: Entree) -> list[Passe]:
    """Les passes de revue qu'un lot garde, dans l'ordre de sa section."""
    texte = section_des_revues(e)
    if texte is None:
        return []
    res: list[Passe] = []
    lignes = texte.splitlines()[1:]
    recul: list[str] | None = None
    for ligne in lignes:
        t = TITRE_DE_PASSE.match(ligne)
        if t:
            res.append(Passe(int(t["n"]), (t["date"] or "").strip()))
            recul = None
            continue
        if not res:
            continue
        p = res[-1]
        if recul is not None:
            if not ligne.strip() or ligne.lstrip().startswith(("#", "- ", "* ")):
                p.recul, recul = " ".join(recul), None
            else:
                recul.append(ligne.strip())
                continue
        c = LIGNE_COMMITS.match(ligne)
        if c and p.debut is None:
            p.debut, p.tete = c["debut"], c["tete"]
            continue
        b = LIGNE_BLOQUANT.match(ligne)
        if b:
            r = REGARD.search(b["texte"])
            regard = None if r is None else ("meme" if r["meme"] else "nouvelle")
            p.bloquants.append(((b["texte"][:r.start()] if r else b["texte"]).strip(), regard))
            continue
        if DEBUT_DU_RECUL.match(ligne) and p.recul is None:
            recul = [ligne.strip()]
    if recul is not None and res:
        res[-1].recul = " ".join(recul)
    return res


def mots_du_recul(recul: str) -> list[str]:
    return MOT.findall(recul)


def decision_du_recul(recul: str | None) -> str | None:
    """`continuer` ou `s-arreter`, le dernier mot du recul, ponctuation,
    accents et apostrophe mis à part ; `None` s'il n'est ni l'un ni
    l'autre."""
    mots = mots_du_recul(recul or "")
    return DECISIONS_DU_RECUL.get(outils.cle(mots[-1].replace("’", "'"))) if mots else None


def refus_du_recul(p: Passe) -> str | None:
    """Pourquoi la passe n'a pas son recul (D-0124, point 4), `None` si elle
    l'a : un paragraphe qui commence par « Recul : », de soixante mots au
    moins, dont le dernier est « continuer » ou « s'arrêter »."""
    if p.recul is None:
        return trad("la passe {n} n'a pas son recul : un paragraphe qui commence par « Recul : »", n=p.numero)
    n = len(mots_du_recul(p.recul))
    if n < MOTS_DU_RECUL:
        return trad("le recul de la passe {n} a {mots} mot(s) : il en faut {seuil} au moins, qui répondent aux trois "
                    "questions", n=p.numero, mots=n, seuil=MOTS_DU_RECUL)
    if decision_du_recul(p.recul) is None:
        return trad("le recul de la passe {n} ne finit ni par « continuer » ni par « s'arrêter » : son dernier mot "
                    "est sa décision, et ce qui rendra la passe suivante différente s'écrit avant", n=p.numero)
    return None


def demandes_du_recul(p: Passe) -> list[str]:
    """Les demandes que nomme un recul : celle qu'un arrêt pose à
    l'humain."""
    return list(dict.fromkeys(i for i, _ in mentions(p.recul or "") if type_d_id(i) == "D"))


def cite_le_lot(e: Entree, lot: Entree) -> bool:
    """L'entrée `e` cite le lot dans son texte, par son identifiant ou par
    un ancien numéro."""
    return bool({lot.id, *lot.anciens} & {i for i, _ in mentions(e.texte)})


def leve_l_arret(mem: "Memoire", lot: Entree, demande: str) -> bool:
    """La demande `demande`, qu'un recul « s'arrêter » nomme, lève l'arrêt
    du lot (ADR-0084, point 6) : elle cite le lot, et l'humain y a répondu.
    Retirée, ou ancienne et d'un autre sujet, elle ne le lève pas."""
    e = mem.entree(demande)
    return e is not None and e.fichier in mem.repondues and "retiree" not in e.meta and cite_le_lot(e, lot)


def _revient(p: Passe) -> bool:
    """Le relecteur voit une cause revenir : à partir de la deuxième passe."""
    return p.numero >= 2 and p.voit_revenir


def refus_de_la_suite(mem: "Memoire", lot: Entree, deja: list[Passe]) -> tuple[str, str] | None:
    """Pourquoi rien ne suit la dernière passe de `deja`, ni une passe de
    plus, que `socle review` refuse, ni la clôture « fait » du lot, que le
    contrôle du backlog refuse (D-0124, points 2, 3, 5 et 6 ; ADR-0084) :
    les mêmes règles, sans ce que git donne. `None` si rien ne l'arrête ;
    sinon (nature, raison), la nature disant ce que l'agent fait ensuite :
    `regard`, consigner le regard du relecteur sur un bloquant, à partir de
    la deuxième passe ; `recul`, écrire le recul ; `arret`, s'arrêter sur
    une demande qui cite le lot, après deux passes de suite où une même
    cause revient, ou sur un arrêt qu'aucune demande nommée ne lève ;
    `attente`, attendre la réponse de l'humain à la demande de l'arrêt."""
    derniere = deja[-1]
    n = derniere.numero
    sans = [cause for cause, regard in derniere.bloquants if regard is None] if n >= 2 else []
    if sans:
        return "regard", trad("la passe {n} ne consigne pas le regard du relecteur sur {m} bloquant(s), « · même "
                              "cause » ou « · cause nouvelle » au bout de sa ligne : {causes}", n=n, m=len(sans),
                              causes=" ; ".join(sans))
    raison = refus_du_recul(derniere)
    if raison:
        return "recul", raison
    decision = decision_du_recul(derniere.recul)
    precedente = deja[-2] if len(deja) > 1 else None
    if decision == "continuer" and precedente and _revient(precedente) and _revient(derniere):
        return "arret", trad("le relecteur a vu une même cause revenir deux passes de suite, aux passes {a} et {b} "
                             ": « continuer » est refusé, le lot s'arrête", a=precedente.numero, b=n)
    if decision != "s-arreter":
        return None
    demandes = demandes_du_recul(derniere)
    if not demandes:
        return "arret", trad("le recul de la passe {n} s'arrête sans nommer sa demande (`D-NNNN`), la décision qu'il "
                             "pose à l'humain", n=n)
    if any(leve_l_arret(mem, lot, d) for d in demandes):
        return None
    # Une demande que la mémoire n'a pas encore se dit attendue, comme une
    # demande du lot qui attend sa réponse.
    attendues = [d for d in demandes if (e := mem.entree(d)) is None or (
        cite_le_lot(e, lot) and e.fichier not in mem.repondues and "retiree" not in e.meta)]
    if attendues:
        return "attente", trad("le lot s'est arrêté à la passe {n}, et attend la réponse à {demandes} : il avance "
                               "ailleurs jusque-là", n=n, demandes=", ".join(attendues))
    return "arret", trad("l'arrêt de la passe {n} n'est levé par aucune des demandes que nomme son recul "
                         "({demandes}) : seule le lève la réponse de l'humain à une demande qui cite le lot ({lot}) ; "
                         "une demande retirée, ou qui ne le cite pas, ne le lève pas", n=n,
                         demandes=", ".join(demandes), lot=lot.id)


@dataclass
class Ordre:
    """Ce qui vient ensuite : les tâches prêtes (ouvertes, pas encore en
    cours, dont tout ce qu'elles attendent, et ce qu'attend leur besoin, est
    clos), le prochain jalon et ses besoins ouverts, le prochain lot et
    l'avancement de ses tâches, les besoins à découper et à fermer, et le
    nombre d'entrées qui attendent encore, selon ce qu'elles attendent."""

    prets: list[Entree]
    jalon: Entree | None
    restants: list[str]
    en_attente: int
    # Les tâches prêtes de priorité basse, à part : l'agent les prend quand
    # c'est commode, et le dit (D-0062).
    basses: list[Entree] = field(default_factory=list)
    # Le prochain lot, et où en est ce qu'il attend hors des lots :
    # (identifiant, mot interne), dans l'ordre de son `après` (ADR-0079).
    lot: Entree | None = None
    avancement: list[tuple[str, str]] = field(default_factory=list)
    # Parmi celles qui attendent, celles qui attendent une entrée du backlog
    # non close, et celles qui attendent une demande sans réponse (D-0064,
    # B-0153).
    attendent_une_entree: int = 0
    attendent_une_demande: int = 0
    # Les besoins sans tâche ouverte ni rien d'ouvert qu'ils attendent, et
    # ceux dont les tâches sont closes, l'une au moins faite (ADR-0083).
    a_decouper: list[Entree] = field(default_factory=list)
    a_fermer: list[Entree] = field(default_factory=list)


def ordre(mem: "Memoire") -> Ordre | None:
    """L'ordre du backlog, s'il en a un : sans `après`, tâche, lot, jalon ni
    priorité, rien."""
    entrees = {e.id: e for e in mem.entrees(BACKLOG) if not e.archivee and not e.basculee}
    demandes = {e.id: e for e in mem.entrees("D") if not e.basculee}
    if not any(dependances(e) or not est_besoin(e) or priorite(e) for e in entrees.values()):
        return None

    def ouvert(i: str) -> bool:
        """Encore attendu : une entrée non close, ou une demande sans réponse."""
        if i in demandes:
            return not demande_close(mem, demandes[i])
        return i in entrees and entrees[i].statut not in BACKLOG_CLOS

    def deps(i: str) -> list[str]:
        """Ce qu'une entrée attend ; pour une tâche, aussi ce qu'attend son
        besoin (ADR-0083)."""
        e = entrees[i]
        res = dependances(e)
        b = entrees.get(besoin_de(e) or "") if est_tache(e) else None
        return res + [d for d in dependances(b) if d not in res] if b else res

    def attendus(i: str) -> set[str]:
        """Les entrées et les demandes encore attendues qu'une entrée attend,
        de proche en proche ; un cycle s'arrête (le contrôle de l'ordre le
        refuse)."""
        vus, pile = set(), list(deps(i))
        while pile:
            d = pile.pop()
            if d in vus or d == i or (d not in entrees and d not in demandes):
                continue
            vus.add(d)
            if d in entrees:
                pile += deps(d)
        return {d for d in vus if ouvert(d)}

    ouverts = sorted(i for i in entrees if ouvert(i))

    def premier(est) -> list[str]:
        """Ceux de cette forme, ouverts, qu'aucun autre de la forme ne précède,
        l'en cours d'abord, puis par identifiant."""
        return sorted((i for i in ouverts
                       if est(entrees[i]) and not any(d in entrees and est(entrees[d]) for d in attendus(i))),
                      key=lambda i: (entrees[i].statut != "en-cours", i))

    jalons = premier(est_jalon)
    jalon = jalons[0] if jalons else None
    restants = sorted(d for d in dependances(entrees[jalon])
                      if ouvert(d) and (d in demandes or (d in entrees and est_besoin(entrees[d])))) if jalon else []
    du_jalon = set(restants)
    lots = premier(est_lot)
    lot = entrees[lots[0]] if lots else None
    rang = {"haute": 0, None: 1}

    def cle(i: str):
        """Celles du prochain jalon d'abord, puis par priorité."""
        e = entrees[i]
        return ((besoin_de(e) if est_tache(e) else i) not in du_jalon,
                rang.get(priorite_effective(e, entrees), 2), i)

    # Une tâche en cours ou bloquée n'est plus à prendre : l'état le dit à
    # part. Un besoin, un lot ni un jalon ne se prennent.
    a_prendre = [i for i in ouverts if est_tache(entrees[i]) and entrees[i].statut == "ouvert"]
    prets = sorted((i for i in a_prendre if not any(ouvert(d) for d in deps(i))), key=cle)
    basses = [i for i in prets if priorite_effective(entrees[i], entrees) == "basse"]
    prets = [i for i in prets if i not in basses]
    # Les besoins : ceux qui n'ont plus de tâche ouverte sont à fermer, si
    # l'une est faite, ou à découper, s'ils n'attendent plus rien.
    taches: dict[str, list[Entree]] = {}
    for e in entrees.values():
        if est_tache(e) and besoin_de(e):
            taches.setdefault(besoin_de(e), []).append(e)
    a_fermer, a_decouper, attendent = [], [], []
    for i in ouverts:
        if not est_besoin(entrees[i]):
            continue
        siennes = taches.get(i, [])
        if any(t.statut not in BACKLOG_CLOS for t in siennes):
            continue
        if any(t.statut == "fait" for t in siennes):
            a_fermer.append(i)
        elif any(ouvert(d) for d in deps(i)):
            attendent.append(i)
        elif entrees[i].statut == "ouvert":
            a_decouper.append(i)
    # Ce qu'attendent celles qui ne sont pas prêtes : une entrée du backlog,
    # une demande, ou les deux (B-0153).
    attendus_ouverts = {i: [d for d in deps(i) if ouvert(d)]
                        for i in [*(i for i in a_prendre if i not in prets and i not in basses), *attendent]}
    attente_entree = sum(1 for ds in attendus_ouverts.values() if any(d in entrees for d in ds))
    attente_demande = sum(1 for ds in attendus_ouverts.values() if any(d in demandes for d in ds))

    def ou_en_est(i: str) -> str:
        """Où en est ce qu'un lot attend, en mot interne : le statut d'une
        tâche qui n'est plus ouverte, sinon `pret` ou `attend` ; pour une
        demande, `repondue` ou `sans-reponse` ; `inconnu` pour le reste."""
        if i in demandes:
            return "repondue" if demande_close(mem, demandes[i]) else "sans-reponse"
        if i not in entrees:
            return "inconnu"
        if entrees[i].statut != "ouvert":
            return entrees[i].statut
        return "attend" if any(ouvert(d) for d in deps(i)) else "pret"

    avancement = [(d, ou_en_est(d)) for d in dict.fromkeys(dependances(lot))
                  if not (d in entrees and est_lot(entrees[d]))] if lot else []
    return Ordre([entrees[i] for i in prets], entrees[jalon] if jalon else None, restants, len(attendus_ouverts),
                 [entrees[i] for i in basses], lot, avancement, attente_entree, attente_demande,
                 [entrees[i] for i in sorted(a_decouper, key=cle)], [entrees[i] for i in a_fermer])


# Où en est ce qu'un lot attend, tel que l'état le dit ; une tâche close ou
# une demande répondue ne se détaille pas.
AVANCEMENT = {"en-cours": a_traduire("en cours"), "bloque": a_traduire("bloqué"), "pret": a_traduire("prête"),
              "attend": a_traduire("attend"), "sans-reponse": a_traduire("sans réponse"),
              "inconnu": a_traduire("inconnu")}
CLOS_DANS_UN_LOT = ("fait", "abandonne", "repondue")


def _ids(entrees: list[Entree], plafond: int | None) -> str:
    ids = ", ".join(e.id for e in entrees[:plafond])
    if plafond is not None and len(entrees) > plafond:
        ids = trad("{ids} … et {n} autre(s)", ids=ids, n=len(entrees) - plafond)
    return ids


def lignes_ordre(mem: "Memoire", plafond: int | None = 8, titre: int | None = None,
                 basses: int | None = None) -> list[str]:
    """L'ordre du backlog en lignes, pour l'état et le rappel de fin de tour :
    `plafond` tâches prêtes au plus, `basses` tâches de priorité basse et
    besoins par liste, chaque titre en `titre` octets au plus (sans limite :
    `None`)."""
    o = ordre(mem)
    if o is None:
        return []

    def t(e) -> str:
        return outils.raccourcir(e.titre, titre) if titre else e.titre

    res = []
    if o.jalon:
        res.append(trad("prochain jalon : {id} — {titre} ; besoins ouverts : {restants}", id=o.jalon.id,
                        titre=t(o.jalon), restants=", ".join(o.restants) if o.restants else trad("aucun, il se clôt")))
    if o.lot:
        reste = [(i, a) for i, a in o.avancement if a not in CLOS_DANS_UN_LOT]
        res.append(trad("prochain lot : {id} — {titre} ; {clos} close(s) sur {total} ; reste : {restants}",
                        id=o.lot.id, titre=t(o.lot), clos=len(o.avancement) - len(reste), total=len(o.avancement),
                        restants=", ".join(f"{i} ({trad(AVANCEMENT.get(a, a))})" for i, a in reste)
                        if reste else trad("rien, il se clôt")))
    besoins = {b.id: b for b in mem.entrees("B")}
    res += [trad("tâche prête : {id} — {titre} (priorité haute)", id=e.id, titre=t(e))
            if priorite_effective(e, besoins) == "haute"
            else trad("tâche prête : {id} — {titre}", id=e.id, titre=t(e)) for e in o.prets[:plafond]]
    if plafond is not None and len(o.prets) > plafond:
        res.append(trad("… et {n} autre(s) tâche(s) prête(s)", n=len(o.prets) - plafond))
    if o.basses:
        res.append(trad("prêtes aussi, de priorité basse : {ids}", ids=_ids(o.basses, basses)))
    if o.a_fermer:
        res.append(trad("besoins à fermer, leurs tâches closes : {ids}", ids=_ids(o.a_fermer, basses)))
    if o.a_decouper:
        res.append(trad("besoins à découper en tâches : {ids}", ids=_ids(o.a_decouper, basses)))
    if o.attendent_une_entree:
        res.append(trad("{n} entrée(s) attendent une entrée ouverte du backlog", n=o.attendent_une_entree))
    if o.attendent_une_demande:
        res.append(trad("{n} entrée(s) attendent une demande sans réponse", n=o.attendent_une_demande))
    return res


def empreinte_index(mem: "Memoire", index: str, sauf: set[str] = frozenset()) -> str:
    return outils.sha256("\n".join(lignes_index(mem, index, sauf)))[:8]


def citations(texte: str) -> list[tuple[str, str, int]]:
    """(identifiant, empreinte, ligne) des citations `ID@empreinte`, hors code clôturé."""
    res = []
    for i, ligne, code in lignes_hors_code(texte):
        if not code:
            res += [(m["id"], m["empreinte"], i) for m in CITATION_RE.finditer(ligne)]
    return res


def citations_index(texte: str) -> list[tuple[str, str, int]]:
    res = []
    for i, ligne, code in lignes_hors_code(texte):
        if not code:
            res += [(m["index"], m["empreinte"], i) for m in INDEX_RE.finditer(ligne)]
    return res
