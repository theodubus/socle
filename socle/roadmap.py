"""La suite du projet (`socle roadmap`), pour que l'humain pilote son
projet, lue sur un téléphone : ce qui se fait maintenant, les étapes qui
suivent, chacune avec ses besoins clos sur son total, la prochaine dépliée
en ses besoins, ce qui revient à l'humain, et la réserve comptée. Elle se
calcule depuis le backlog comme l'état, par les mêmes fonctions
(`memory.Graphe`, `memory.ordre_de`) : rien n'y est écrit à la main.

Une seule forme (D-0212, D-0214), un seul texte : aligné, chaque titre
suivi de son identifiant, aucune demande nommée par le sien (collé dans
une réponse, il ne citerait pas une demande en attente sans son lien).
Le terminal le reçoit tel quel (`text`) ; la conversation et le résumé
d'une exécution de la CI, dans un bloc de code (`markdown`), où il garde
son alignement : rendu en Markdown, il n'était pas lisible sur un
téléphone (D-0228). Sa spécification :
`docs/fabrication/feuille-de-route-specification.md` dans l'atelier du
socle."""

from __future__ import annotations

import datetime
import re
import textwrap
from dataclasses import dataclass, field
from itertools import combinations

from socle import config, memory as memoire
from socle.messages import a_traduire, trad

FORMATS = ("text", "markdown")
# La largeur d'une ligne du rendu du terminal, en caractères : ce qu'un
# téléphone montre d'un bloc de code sans le faire défiler. Une ligne plus
# longue passe à la suivante, sous sa propre colonne.
LARGEUR = 48
# Un titre se lit jusqu'à son premier « : » suivi d'une espace, hors d'une
# citation entre guillemets ou d'un code en ligne : ce qui suit le précise.
# Sa tête se coupe au-delà de `TITRE` caractères.
SEPARATEURS = re.compile(r"«|»|`|\s*:(?=\s|$)")
TITRE = 72
# Les tâches ouvertes qu'un lot en cours nomme sous lui, au plus.
RESTE = 3
# La marque d'un besoin d'une étape dépliée : clos, servi par une tâche d'un
# lot en cours, autre.
CLOS, SERVI, AUTRE = "✓", "▶", "·"
MOIS = (a_traduire("janvier"), a_traduire("février"), a_traduire("mars"), a_traduire("avril"), a_traduire("mai"),
        a_traduire("juin"), a_traduire("juillet"), a_traduire("août"), a_traduire("septembre"),
        a_traduire("octobre"), a_traduire("novembre"), a_traduire("décembre"))
# Les comptes, au singulier et au pluriel.
BESOINS = (a_traduire("{n} besoin"), a_traduire("{n} besoins"))
PRIORITAIRES = (a_traduire("dont {n} prioritaire"), a_traduire("dont {n} prioritaires"))
AUTRES = (a_traduire("et {n} autre"), a_traduire("et {n} autres"))
CLOS_N = (a_traduire("{n} besoin clos"), a_traduire("{n} besoins clos"))
VOYELLES = "aeiouyàâäéèêëîïôöûüù"


@dataclass
class Tache:
    entree: memoire.Entree
    # Où elle en est (son statut, ou, ouverte, `pret` ou `attend`), et ce
    # qu'elle attend encore : des entrées du backlog, des demandes sans
    # réponse.
    avancement: str
    attend: list[str]
    priorite: str | None
    lot: str | None = None

    @property
    def besoin(self) -> str | None:
        return memoire.besoin_de(self.entree)

    @property
    def close(self) -> bool:
        return self.avancement in memoire.BACKLOG_CLOS


@dataclass
class Lot:
    entree: memoire.Entree
    taches: list[Tache]
    # Les demandes sans réponse que le lot attend lui-même.
    demandes: list[str]

    @property
    def en_cours(self) -> bool:
        return self.entree.statut == "en-cours"

    @property
    def closes(self) -> int:
        return sum(t.close for t in self.taches)


@dataclass
class Jalon:
    entree: memoire.Entree
    clos: int
    total: int


@dataclass
class Suite:
    jalons: list[Jalon]
    lots: list[Lot]
    # Le rang du lot en cours parmi les lots : le premier en cours, sinon le
    # premier.
    courant: int
    hors_lot: list[Tache]
    # Toutes les tâches, par identifiant, et les besoins qu'elles servent.
    taches: dict[str, Tache]
    besoins: dict[str, memoire.Entree]
    a_decouper: list[memoire.Entree]
    a_fermer: list[memoire.Entree]
    bloques: list[memoire.Entree]
    pour_l_humain: list[memoire.Entree]
    demandes: list[memoire.Entree]
    sans_jalon: list[memoire.Entree]
    # (lot, lot, le lot qu'ils attendent tous deux), sans ordre entre eux.
    alertes: list[tuple[str, str, str]]
    # La première tâche prête, dans l'ordre de l'état ; de priorité basse
    # s'il n'en est pas d'autre.
    prete: memoire.Entree | None = None
    # La réserve, les besoins ouverts d'aucun jalon ouvert, qu'il y ait des
    # jalons ou non, et ceux d'entre eux à placer (ADR-0118).
    reserve: list[memoire.Entree] = field(default_factory=list)
    a_placer: list[memoire.Entree] = field(default_factory=list)


def calculer(mem: memoire.Memoire) -> Suite:
    """La suite, depuis le backlog d'une mémoire."""
    g = memoire.Graphe(mem)
    o = memoire.ordre_de(g)
    entrees = g.entrees

    def tache(i: str) -> Tache:
        e = entrees[i]
        reste = g.attend(i) if e.statut == "ouvert" else []
        avancement = e.statut if e.statut != "ouvert" else ("attend" if reste else "pret")
        return Tache(e, avancement, reste, memoire.priorite_effective(e, entrees))

    taches = {i: tache(i) for i in sorted(entrees) if memoire.est_tache(entrees[i])}
    lots = []
    for i in g.dans_l_ordre(memoire.est_lot):
        attendus = list(dict.fromkeys(memoire.dependances(entrees[i])))
        siennes = [taches[d] for d in attendus if d in taches]
        for t in siennes:
            t.lot = t.lot or i
        lots.append(Lot(entrees[i], siennes, [d for d in attendus if d in g.demandes and g.ouvert(d)]))
    courant = next((k for k, lot in enumerate(lots) if lot.en_cours), 0)
    jalons = []
    for i in g.dans_l_ordre(memoire.est_jalon):
        besoins = [d for d in dict.fromkeys(memoire.dependances(entrees[i])) if memoire.type_d_id(d) == "B"]
        jalons.append(Jalon(entrees[i], sum(not g.ouvert(b) for b in besoins), len(besoins)))
    reserve = memoire.reserve(g)
    ouverts = [entrees[i] for i in g.ouverts]
    return Suite(
        jalons=jalons, lots=lots, courant=courant,
        hors_lot=[t for t in taches.values() if t.lot is None and not t.close],
        taches=taches, besoins={e.id: e for e in entrees.values() if memoire.est_besoin(e)},
        a_decouper=o.a_decouper, a_fermer=o.a_fermer,
        bloques=[e for e in ouverts if e.statut == "bloque" and not memoire.est_tache(e)],
        pour_l_humain=[e for e in ouverts if memoire.pour_l_humain(e)],
        demandes=[e for i, e in sorted(g.demandes.items()) if g.ouvert(i)],
        sans_jalon=reserve if jalons else [],
        alertes=alertes(g, [lot.entree.id for lot in lots]),
        prete=next(iter([*o.prets, *o.basses]), None),
        reserve=reserve, a_placer=memoire.a_placer(g),
    )


def alertes(g: memoire.Graphe, lots: list[str]) -> list[tuple[str, str, str]]:
    """Deux lots ouverts qui attendent le même lot sans que l'un attende
    l'autre, de proche en proche : leur ordre n'est pas déduit, il est
    choisi par leur identifiant."""
    attendants: dict[str, list[str]] = {}
    for i in lots:
        for d in dict.fromkeys(memoire.dependances(g.entrees[i])):
            if memoire.type_d_id(d) == "L":
                attendants.setdefault(d, []).append(i)
    return [(a, b, p) for p, ws in sorted(attendants.items()) for a, b in combinations(ws, 2)
            if a not in g.attendus(b) and b not in g.attendus(a)]


def besoins_dans_l_ordre(s: Suite) -> list[str]:
    """Les besoins qui ont des tâches, dans l'ordre des lots qui les mènent ;
    puis ceux dont les tâches ouvertes ne sont dans aucun lot."""
    vus = [t.besoin for lot in s.lots for t in lot.taches] + [t.besoin for t in s.hors_lot]
    return [b for b in dict.fromkeys(vus) if b in s.besoins and s.besoins[b].statut not in memoire.BACKLOG_CLOS]


def taches_du_besoin(s: Suite, b: str) -> list[Tache]:
    return [t for t in s.taches.values() if t.besoin == b]


def besoins_du_jalon(j: Jalon) -> list[str]:
    return [d for d in dict.fromkeys(memoire.dependances(j.entree)) if memoire.type_d_id(d) == "B"]


def court(titre: str, largeur: int = TITRE) -> str:
    """La tête d'un titre : sa partie avant le premier « : » (suivi d'une
    espace ou en fin) hors de guillemets et de code en ligne, coupée à
    `largeur` caractères avec « … » ; une tête plus courte reste entière."""
    tete, guillemets, code = titre, 0, False
    for m in SEPARATEURS.finditer(titre):
        if m.group() == "`":
            code = not code
        elif m.group() in "«»":
            guillemets = max(guillemets + (1 if m.group() == "«" else -1), 0)
        elif not code and not guillemets:
            tete = titre[:m.start()]
            break
    tete = tete.strip() or titre.strip()
    return tete if len(tete) <= largeur else tete[:max(largeur - 1, 0)].rstrip() + "…"


# --- La forme -------------------------------------------------------------


@dataclass
class Mene:
    """Un besoin qu'un lot en cours mène : ses tâches ouvertes de ce lot
    nommées, et combien d'autres. Une tâche dont le besoin est inconnu va
    sous `None`."""
    besoin: memoire.Entree | None
    reste: list[memoire.Entree]
    autres: int


@dataclass
class EnCours:
    """Un lot en cours, et les besoins qu'il mène, dans l'ordre de ses
    tâches (D-0230)."""
    lot: memoire.Entree
    besoins: list[Mene]


@dataclass
class Etape:
    """Un jalon ouvert, à son rang : s'il est déplié, ses besoins clos
    comptés sur une ligne (D-0231), puis les autres avec leur marque ;
    sinon, aucun."""
    rang: int
    jalon: Jalon
    besoins: list[tuple[str, memoire.Entree]] = field(default_factory=list)
    clos: int = 0


@dataclass
class Forme:
    """Ce que disent les deux rendus, dans leur ordre : Maintenant, Ensuite,
    Pour toi, En réserve, et les alertes."""
    en_cours: list[EnCours]
    prete: memoire.Entree | None
    etapes: list[Etape]
    # Les entrées pour l'humain, puis les demandes en attente.
    pour_toi: list[memoire.Entree]
    demandes: list[memoire.Entree]
    # Les besoins en réserve, et parmi eux ceux de priorité haute.
    reserve: int
    prioritaires: int
    bloques: list[memoire.Entree]
    alertes: list[tuple[str, str, str]]
    # Parmi ceux de la réserve, ceux à placer (ADR-0118).
    a_placer: int = 0


def forme(s: Suite, tout: bool = False) -> Forme:
    """La forme de la suite : les lots en cours dans leur ordre d'exécution,
    chacun avec les besoins qu'il mène et leurs premières tâches ouvertes,
    ou à défaut la première tâche prête ; les jalons ouverts, le premier seul déplié (tous avec `tout`) ;
    ce qui revient à l'humain ; la réserve, les besoins ouverts d'aucun jalon
    que rien ne montre plus haut ; les entrées bloquées et les alertes."""
    en_cours = []
    for lot in s.lots:
        if lot.en_cours:
            par_besoin: dict[str | None, list[Tache]] = {}
            for t in lot.taches:
                par_besoin.setdefault(t.besoin if t.besoin in s.besoins else None, []).append(t)
            menes = []
            for b, taches in par_besoin.items():
                ouvertes = [t.entree for t in taches if not t.close]
                menes.append(Mene(s.besoins.get(b), ouvertes[:RESTE], max(len(ouvertes) - RESTE, 0)))
            en_cours.append(EnCours(lot.entree, menes))
    servis = {t.besoin for lot in s.lots if lot.en_cours for t in lot.taches}
    etapes = []
    for k, j in enumerate(s.jalons):
        etape = Etape(k + 1, j)
        if tout or k == 0:
            for b in besoins_du_jalon(j):
                e = s.besoins.get(b)
                if e is not None and e.statut in memoire.BACKLOG_CLOS:
                    etape.clos += 1
                elif e is not None:
                    etape.besoins.append((SERVI if b in servis else AUTRE, e))
        etapes.append(etape)
    humain = {e.id for e in s.pour_l_humain}
    # La réserve, qu'il y ait des jalons ou non : sans jalon, elle dit encore
    # ce qui attend ; ce que « Maintenant » ou « Pour toi » montrent n'y est
    # pas compté.
    reserve = [e for e in s.reserve if e.id not in servis and e.id not in humain]
    places = {e.id for e in s.a_placer}
    return Forme(en_cours=en_cours, prete=None if en_cours else s.prete, etapes=etapes,
                 pour_toi=list(s.pour_l_humain), demandes=list(s.demandes), reserve=len(reserve),
                 prioritaires=sum(memoire.priorite(e) == "haute" for e in reserve), bloques=list(s.bloques),
                 alertes=list(s.alertes), a_placer=sum(e.id in places for e in reserve))


def _nombre(n: int, formes: tuple[str, str]) -> str:
    """Un compte, au singulier ou au pluriel."""
    return trad(formes[0] if n == 1 else formes[1], n=n)


def entete(nom: str, jour: datetime.date | None = None) -> str:
    """« La suite de <projet> — <jour> <mois> » : le jour, celui de
    l'appel ; « de » s'élide devant une voyelle."""
    jour = jour or datetime.date.today()
    date = f"{jour.day} {trad(MOIS[jour.month - 1])}"
    if not nom:
        return trad("La suite — {date}", date=date)
    if nom[0].lower() in VOYELLES:
        return trad("La suite d'{nom} — {date}", nom=nom, date=date)
    return trad("La suite de {nom} — {date}", nom=nom, date=date)


def _reserve(f: Forme) -> str | None:
    if not f.reserve:
        return None
    compte = _nombre(f.reserve, BESOINS)
    if f.prioritaires:
        compte += ", " + _nombre(f.prioritaires, PRIORITAIRES)
    if f.a_placer:
        compte += ", " + trad("{n} à placer", n=f.a_placer)
    return trad("En réserve : {compte}", compte=compte)


def _attention(mot: str, alerte: str) -> str:
    """Une ligne d'alerte : « Attention : <alerte> »."""
    return trad("{attention} : {alerte}", attention=mot, alerte=alerte)


def _alerte(a: str, b: str, p: str) -> str:
    return trad("ordre ambigu : {a} et {b} attendent tous deux {p}, sans ordre entre eux — que l'un attende "
                "l'autre", a=a, b=b, p=p)


def _crochets(etapes: list[Etape]) -> tuple[int, int]:
    """La largeur des numéros des étapes, et celle de chaque nombre de
    `[K/N]` : celle du plus grand total, pour que tous les crochets aient la
    même largeur et que les titres s'alignent."""
    return (max((len(str(e.rang)) for e in etapes), default=1),
            max((len(str(e.jalon.total)) for e in etapes), default=1))


def _compte(e: Etape, largeur: int) -> str:
    """« [K/N] », K aligné à droite et N à gauche sur `largeur`."""
    return f"[{e.jalon.clos:>{largeur}}/{e.jalon.total:<{largeur}}]"


# --- Le rendu du terminal ---------------------------------------------------


def _plier(texte_: str, tete: str, retrait: int | None = None) -> list[str]:
    """Un texte derrière sa tête, passé à la ligne à `LARGEUR` : les lignes
    qui suivent commencent sous sa première lettre, ou à `retrait`."""
    retrait = len(tete) if retrait is None else retrait
    lignes = textwrap.wrap(texte_, max(LARGEUR - retrait, 16), break_on_hyphens=False) or [""]
    return [(tete + lignes[0]).replace("\u00a0", " "), *(" " * retrait + l.replace("\u00a0", " ") for l in lignes[1:])]


def _nomme(e: memoire.Entree) -> str:
    """Une entrée dans le terminal : son titre, puis son identifiant, collé
    au dernier mot par une espace insécable que `_plier` rend ordinaire."""
    return f"{court(e.titre)}\u00a0({e.id})"


def texte(s: Suite, tout: bool = False, nom: str = "", jour: datetime.date | None = None) -> str:
    """Le rendu du terminal, en texte brut aligné : chaque titre suivi de son
    identifiant, une demande en attente dite par son titre seul."""
    f = forme(s, tout)
    blocs = [[entete(nom, jour)]]
    if f.en_cours or f.prete:
        maintenant = [trad("Maintenant")]
        for c in f.en_cours:
            maintenant += _plier(_nomme(c.lot), " ▶ ")
            for m in c.besoins:
                retrait = 3
                if m.besoin is not None:
                    maintenant += _plier(_nomme(m.besoin), "   " + trad("besoin :") + " ")
                    retrait = 5
                tete = " " * retrait + trad("reste :") + " "
                for k, t in enumerate(m.reste):
                    maintenant += _plier(_nomme(t), tete if k == 0 else " " * len(tete), len(tete))
                if m.autres:
                    maintenant += _plier(_nombre(m.autres, AUTRES), " " * len(tete))
        if f.prete:
            maintenant += _plier(_nomme(f.prete), "   " + trad("prête :") + " ")
        blocs.append(maintenant)
    else:
        blocs.append([trad("{maintenant} : rien en cours", maintenant=trad("Maintenant"))])
    if f.etapes:
        numero, largeur = _crochets(f.etapes)
        ensuite = [trad("Ensuite")]
        for e in f.etapes:
            tete = f"{e.rang:>{numero}}. {_compte(e, largeur)} "
            ensuite += _plier(_nomme(e.jalon.entree), tete)
            if e.clos:
                ensuite.append(" " * len(tete) + CLOS + " " + _nombre(e.clos, CLOS_N))
            for marque, b in e.besoins:
                ensuite += _plier(_nomme(b), " " * len(tete) + marque + " ")
        blocs.append(ensuite)
    fin = []
    gestes = [_nomme(e) for e in f.pour_toi] + [court(e.titre) for e in f.demandes]
    tete = trad("Pour toi :") + " "
    for k, g in enumerate(gestes):
        fin += _plier(g, tete if k == 0 else " " * len(tete), len(tete))
    reserve = _reserve(f)
    if reserve:
        fin += _plier(reserve, "")
    attention = _attention(trad("Attention"), "")
    fin += [l for e in f.bloques for l in _plier(trad("bloqué : {entree}", entree=_nomme(e)), attention)]
    fin += [l for a in f.alertes for l in _plier(_alerte(*a), attention)]
    if fin:
        blocs.append(fin)
    return "\n\n".join("\n".join(b) for b in blocs)


# --- Le bloc de code -------------------------------------------------------


def markdown(s: Suite, tout: bool = False, nom: str = "", jour: datetime.date | None = None) -> str:
    """Le texte du terminal dans un bloc de code, pour la conversation et le
    résumé de la CI : sa clôture, plus longue que toute suite d'accents
    graves d'un titre, ne se ferme pas en route."""
    corps = texte(s, tout, nom, jour)
    cloture = "`" * max([3, *(len(m) + 1 for m in re.findall(r"`+", corps))])
    return f"{cloture}text\n{corps}\n{cloture}\n"


def rendre(projet: config.Projet, format_: str = "text", tout: bool = False,
           jour: datetime.date | None = None) -> str:
    """La suite du projet, dans le rendu demandé, sous le nom du dossier de
    sa racine."""
    s = calculer(memoire.Memoire.charger(projet.racine))
    rendu = markdown if format_ == "markdown" else texte
    return rendu(s, tout, projet.racine.name, jour)
