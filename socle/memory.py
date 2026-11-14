"""Lecture de la mémoire : six couches de markdown qu'un script sait lire.

Le format est décrit dans `engine/socle/FORMAT.md`. En bref :

- chaque fichier de mémoire commence par `<!-- socle: couche=… zone=… -->` ;
- une entrée est un titre `## <ID> — <titre>`, suivi d'une ligne de
  métadonnées `> clé : valeur · clé : valeur` ;
- un identifiant est stable : `F-0001` (fait), `B-0001` (backlog),
  `ADR-0001` (décision), `D-0001` (demande), `J-2026-10-10-A` (journal) ;
  préfixé de `P` dans la zone privée (`PF-0001`, `PJ-…`).

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
    "ADR": "decisions",
    "J": "journal",
    "D": "demandes",
}
COUCHES = ("canonique", "actif", "decisions", "journal", "backlog", "demandes")
ZONES = ("publique", "privee")

# Un identifiant, où qu'il soit. La forme du numéro est vérifiée après coup :
# `J-` exige une date et une lettre, les autres quatre chiffres.
ID_RE = re.compile(
    r"(?<![\w-])(?P<prive>P?)(?P<type>ADR|F|B|D|J)-"
    r"(?P<num>\d{4}(?:-\d{2}-\d{2}-[A-Z]{1,2})?)(?![\w-])"
)
NUM_JOURNAL = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Z]{1,2}$")
NUM_SIMPLE = re.compile(r"^\d{4}$")

TITRE_RE = re.compile(r"^(?P<niveau>#{1,6})\s+(?P<reste>.*?)\s*#*\s*$")
ENTETE_ENTREE = re.compile(
    r"^(?P<id>P?(?:ADR|F|B|D|J)-[\d-]+[A-Z]{0,2})\s*[—–-]\s*(?P<titre>.+)$"
)
# Un titre qui commence comme une entrée, lisible ou non.
TITRE_D_ENTREE = re.compile(r"^P?(?:ADR|F|B|D|J)-\d")
ENTETE_FICHIER = re.compile(r"<!--\s*socle\s*:(?P<corps>.*?)-->")
# La liste des termes privés n'est pas un fichier de mémoire : son en-tête est
# celui d'un texte brut, et la dit lisible comme l'autre.
ENTETE_TERMES = "# socle: termes privés"
CLOTURE_CODE = re.compile(r"^\s*(```|~~~)")

# Statuts lisibles par machine, sous leur forme canonique (sans accents).
STATUTS = {
    "F": {"mesure", "suppose", "refute", "valide"},
    "B": {"ouvert", "en-cours", "bloque", "fait", "abandonne"},
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

    def entrees(self, type_: str | None = None):
        for f in self.fichiers.values():
            for e in f.entrees:
                if type_ is None or e.type == type_:
                    yield e

    def definitions(self) -> dict[str, list[Entree]]:
        res: dict[str, list[Entree]] = {}
        for e in self.entrees():
            res.setdefault(e.id, []).append(e)
        return res

    def entree(self, ident: str) -> Entree | None:
        defs = self.definitions().get(ident)
        return defs[0] if defs else None

    def prochain_id(self, type_: str, prive: bool = False, date: str | None = None,
                    pris_ailleurs: set[str] = frozenset()) -> str:
        """Le prochain identifiant libre d'un type. Calculé, jamais deviné :
        deux sessions qui devinent tombent sur le même. `pris_ailleurs` : ceux
        que d'autres branches ont déjà pris."""
        return prochain_libre(type_, set(self.definitions()) | set(pris_ailleurs), prive, date)


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
    r"(?<![\w-])(?P<id>P?(?:ADR|F|B|D|J)-\d{4}(?:-\d{2}-\d{2}-[A-Z]{1,2})?)@(?P<empreinte>[0-9a-f]{8})(?![\w-])"
)
INDEX_RE = re.compile(r"(?<![\w-])(?P<index>decisions|backlog)@(?P<empreinte>[0-9a-f]{8})(?![\w-])")
INDEX_TYPES = {"decisions": "ADR", "backlog": "B"}


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
    type_ = INDEX_TYPES[index]
    res = []
    for e in mem.entrees(type_):
        if e.archivee or e.basculee or e.id in sauf:
            continue
        if index == "backlog" and e.statut in BACKLOG_CLOS:
            continue
        res.append(f"{e.id} — {e.titre} ({e.statut})")
    return sorted(res)


# --------------------------------------------------------------------------
# L'ordre du backlog : un sujet attend d'autres sujets (`après`), un jalon
# est un sujet qui attend ses tâches, un lot un sujet qui attend les sujets
# qu'on mène ensemble ; ce qui vient ensuite se calcule.
# --------------------------------------------------------------------------


def dependances(e: Entree) -> list[str]:
    """Ce qu'un sujet du backlog attend (`après : B-0012, D-0014`) : des
    sujets, et des demandes, attendues jusqu'à leur réponse (D-0064)."""
    return [c for t, c in e.refs("apres") if t == "id"]


def est_jalon(e: Entree) -> bool:
    return langue.valeur(nettoyer(e.meta.get("forme", ""))) == "jalon"


def est_lot(e: Entree) -> bool:
    """Un lot (`forme : lot`, `form: batch`) : les sujets qu'on mène
    ensemble, qu'il attend par `après`, avec le lot d'avant (ADR-0079). Il
    n'est jamais à prendre ; il se clôt quand ses sujets le sont."""
    return langue.valeur(nettoyer(e.meta.get("forme", ""))) == "lot"


PRIORITES = ("haute", "basse")


def priorite(e: Entree) -> str | None:
    """La priorité d'un sujet (`priorité : haute` ou `basse`, D-0062), sous
    sa clé interne ; `None` pour la priorité normale, qui ne s'écrit pas."""
    v = nettoyer(e.meta.get("priorite", ""))
    return langue.valeur(v) if v else None


def demande_close(mem: "Memoire", e: Entree) -> bool:
    """Une demande qui n'est plus attendue : répondue, ou retirée."""
    return e.fichier in mem.repondues or "retiree" in e.meta


SECTION_FAIT_QUAND = re.compile(r"^#{2,4}\s+(?:%s)\s*$" % "|".join(re.escape(x) for x in langue.FAIT_QUAND.values()),
                                re.M | re.I)
CASE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$")


def criteres(e: Entree) -> list[tuple[bool, str]]:
    """Les critères de la section « Fait quand » d'un sujet (D-0064) :
    (coché, texte), dans l'ordre ; vide sans section."""
    m = SECTION_FAIT_QUAND.search(e.corps)
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


@dataclass
class Ordre:
    """Ce qui vient ensuite : les sujets prêts (ouverts, pas encore en cours,
    dont tout ce qu'ils attendent est clos), le prochain jalon et ce qui lui
    reste, le nombre de sujets qui attendent un sujet non clos, et le
    prochain lot avec l'avancement de ses sujets."""

    prets: list[Entree]
    jalon: Entree | None
    restants: list[str]
    en_attente: int
    # Les sujets prêts de priorité basse, à part : l'agent les prend quand
    # c'est commode, et le dit (D-0062).
    basses: list[Entree] = field(default_factory=list)
    # Le prochain lot, et où en est ce qu'il attend hors des lots :
    # (identifiant, mot interne), dans l'ordre de son `après` (ADR-0079).
    lot: Entree | None = None
    avancement: list[tuple[str, str]] = field(default_factory=list)


def ordre(mem: "Memoire") -> Ordre | None:
    """L'ordre du backlog, s'il en a un : sans `après`, jalon, lot ni
    priorité, rien."""
    sujets = {e.id: e for e in mem.entrees("B") if not e.archivee and not e.basculee}
    demandes = {e.id: e for e in mem.entrees("D") if not e.basculee}
    if not any(dependances(e) or est_jalon(e) or est_lot(e) or priorite(e) for e in sujets.values()):
        return None

    def ouvert(i: str) -> bool:
        """Encore attendu : un sujet non clos, ou une demande sans réponse."""
        if i in demandes:
            return not demande_close(mem, demandes[i])
        return i in sujets and sujets[i].statut not in BACKLOG_CLOS

    def attendus(i: str) -> set[str]:
        """Les sujets et les demandes encore attendus qu'un sujet attend, de
        proche en proche ; un cycle s'arrête (le contrôle de l'ordre le
        refuse)."""
        vus, pile = set(), list(dependances(sujets[i]))
        while pile:
            d = pile.pop()
            if d in vus or d == i or (d not in sujets and d not in demandes):
                continue
            vus.add(d)
            if d in sujets:
                pile += dependances(sujets[d])
        return {d for d in vus if ouvert(d)}

    ouverts = sorted(i for i in sujets if ouvert(i))
    # Un attendu peut être une demande, qui n'est jamais un jalon (B-0146).
    jalons = [i for i in ouverts
              if est_jalon(sujets[i]) and not any(d in sujets and est_jalon(sujets[d]) for d in attendus(i))]
    jalon = jalons[0] if jalons else None
    restants = sorted(attendus(jalon)) if jalon else []
    # Le prochain lot : celui qu'aucun lot ouvert ne précède, l'en cours
    # d'abord, puis par identifiant.
    lots = sorted((i for i in ouverts
                   if est_lot(sujets[i]) and not any(d in sujets and est_lot(sujets[d]) for d in attendus(i))),
                  key=lambda i: (sujets[i].statut != "en-cours", i))
    lot = sujets[lots[0]] if lots else None
    # Un sujet en cours ou bloqué n'est plus à prendre : l'état le dit à part.
    # Un jalon ni un lot ne se prennent : ils attendent leurs sujets.
    a_prendre = [i for i in ouverts
                 if sujets[i].statut == "ouvert" and not est_jalon(sujets[i]) and not est_lot(sujets[i])]
    # Ceux du prochain jalon d'abord, puis par priorité ; les basses à part.
    rang = {"haute": 0, None: 1}
    prets = sorted((i for i in a_prendre if not any(ouvert(d) for d in dependances(sujets[i]))),
                   key=lambda i: (i not in restants, rang.get(priorite(sujets[i]), 2), i))
    basses = [i for i in prets if priorite(sujets[i]) == "basse"]
    prets = [i for i in prets if i not in basses]
    attente = len(a_prendre) - len(prets) - len(basses)

    def ou_en_est(i: str) -> str:
        """Où en est ce qu'un lot attend, en mot interne : le statut d'un
        sujet qui n'est plus ouvert, sinon `pret` ou `attend` ; pour une
        demande, `repondue` ou `sans-reponse` ; `inconnu` pour le reste."""
        if i in demandes:
            return "repondue" if demande_close(mem, demandes[i]) else "sans-reponse"
        if i not in sujets:
            return "inconnu"
        if sujets[i].statut != "ouvert":
            return sujets[i].statut
        return "attend" if any(ouvert(d) for d in dependances(sujets[i])) else "pret"

    avancement = [(d, ou_en_est(d)) for d in dict.fromkeys(dependances(lot))
                  if not (d in sujets and est_lot(sujets[d]))] if lot else []
    return Ordre([sujets[i] for i in prets], sujets[jalon] if jalon else None, restants, attente,
                 [sujets[i] for i in basses], lot, avancement)


# Où en est ce qu'un lot attend, tel que l'état le dit ; un sujet clos ou
# une demande répondue ne se détaille pas.
AVANCEMENT = {"en-cours": a_traduire("en cours"), "bloque": a_traduire("bloqué"), "pret": a_traduire("prêt"),
              "attend": a_traduire("attend"), "sans-reponse": a_traduire("sans réponse"),
              "inconnu": a_traduire("inconnu")}
CLOS_DANS_UN_LOT = ("fait", "abandonne", "repondue")


def lignes_ordre(mem: "Memoire", plafond: int | None = 8, titre: int | None = None,
                 basses: int | None = None) -> list[str]:
    """L'ordre du backlog en lignes, pour l'état et le rappel de fin de tour :
    `plafond` sujets prêts au plus, `basses` sujets de priorité basse, chaque
    titre en `titre` octets au plus (sans limite : `None`)."""
    o = ordre(mem)
    if o is None:
        return []

    def t(e) -> str:
        return outils.raccourcir(e.titre, titre) if titre else e.titre

    res = []
    if o.jalon:
        res.append(trad("prochain jalon : {id} — {titre} ; reste : {restants}", id=o.jalon.id, titre=t(o.jalon),
                        restants=", ".join(o.restants) if o.restants else trad("rien, il se clôt")))
    if o.lot:
        reste = [(i, a) for i, a in o.avancement if a not in CLOS_DANS_UN_LOT]
        res.append(trad("prochain lot : {id} — {titre} ; {clos} clos sur {total} ; reste : {restants}",
                        id=o.lot.id, titre=t(o.lot), clos=len(o.avancement) - len(reste), total=len(o.avancement),
                        restants=", ".join(f"{i} ({trad(AVANCEMENT.get(a, a))})" for i, a in reste)
                        if reste else trad("rien, il se clôt")))
    res += [trad("prêt : {id} — {titre} (priorité haute)", id=e.id, titre=t(e)) if priorite(e) == "haute"
            else trad("prêt : {id} — {titre}", id=e.id, titre=t(e)) for e in o.prets[:plafond]]
    if plafond is not None and len(o.prets) > plafond:
        res.append(trad("… et {n} autre(s) prêt(s)", n=len(o.prets) - plafond))
    if o.basses:
        ids = ", ".join(e.id for e in o.basses[:basses])
        if basses is not None and len(o.basses) > basses:
            ids = trad("{ids} … et {n} autre(s)", ids=ids, n=len(o.basses) - basses)
        res.append(trad("prêts aussi, de priorité basse : {ids}", ids=ids))
    if o.en_attente:
        res.append(trad("{n} sujet(s) attendent un sujet ouvert", n=o.en_attente))
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
