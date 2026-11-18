"""La suite du projet d'un coup d'œil (`socle roadmap`) : les jalons et
leurs besoins clos, les lots dans leur ordre d'exécution avec leurs tâches,
les besoins, et ce qui n'est dans aucun lot. Elle se calcule depuis le
backlog comme l'état, par les mêmes fonctions (`memory.Graphe`,
`memory.ordre_de`) : rien n'y est écrit à la main.

Deux formats : compact (`text`), une ligne par jalon et par lot, ou par
besoin, pour le terminal et le récap de la clôture d'un lot ; détaillé
(`markdown`), le lot en cours et les deux suivants tâche par tâche, pour la
conversation et le résumé d'une exécution de la CI. Le compact ne nomme
aucune demande : collé dans une réponse, il ne citerait pas une demande en
attente sans son lien ; le détaillé donne le lien de chacune."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from socle import config, memory as memoire, utils as outils
from socle.messages import a_traduire, trad

FORMATS = ("text", "markdown")
LECTURES = ("batch", "need")
# Sans `--all`, le format détaillé suit tâche par tâche le lot en cours et
# les deux suivants.
DETAILLES = 3
# Un titre du format compact, en octets au plus.
TITRE = 70
# Les besoins hors de tout jalon que le format détaillé nomme sans `--all`.
SANS_JALON_NOMMES = 15
COMMANDE = "python3 .socle/socle roadmap"

# Où en est une tâche, sous sa clé interne : son statut, ou, ouverte, `pret`
# ou `attend`.
AVANCEMENT = {"fait": a_traduire("faite"), "abandonne": a_traduire("abandonnée"),
              "en-cours": a_traduire("en cours"), "bloque": a_traduire("bloquée"), "pret": a_traduire("prête"),
              "attend": a_traduire("attend")}
ORDRE_DES_COMPTES = ("en-cours", "pret", "attend", "bloque")
COMPTES = {"en-cours": a_traduire("{n} en cours"), "pret": a_traduire("{n} prête(s)"),
           "attend": a_traduire("{n} qui attend(ent)"), "bloque": a_traduire("{n} bloquée(s)")}
PRIORITES = {"haute": a_traduire("priorité haute"), "basse": a_traduire("priorité basse")}


@dataclass
class Tache:
    entree: memoire.Entree
    # Sa clé dans `AVANCEMENT`, et ce qu'elle attend encore : des entrées du
    # backlog, des demandes sans réponse.
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
    jalonnes = {d for j in jalons for d in memoire.dependances(j.entree)}
    ouverts = [entrees[i] for i in g.ouverts]
    return Suite(
        jalons=jalons, lots=lots, courant=courant,
        hors_lot=[t for t in taches.values() if t.lot is None and not t.close],
        taches=taches, besoins={e.id: e for e in entrees.values() if memoire.est_besoin(e)},
        a_decouper=o.a_decouper, a_fermer=o.a_fermer,
        bloques=[e for e in ouverts if e.statut == "bloque" and not memoire.est_tache(e)],
        pour_l_humain=[e for e in ouverts if memoire.pour_l_humain(e)],
        demandes=[e for i, e in sorted(g.demandes.items()) if g.ouvert(i)],
        sans_jalon=[e for e in ouverts if memoire.est_besoin(e) and e.id not in jalonnes] if jalons else [],
        alertes=alertes(g, [lot.entree.id for lot in lots]),
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


def detailles(s: Suite, tout: bool) -> list[Lot]:
    """Les lots que le format détaillé suit tâche par tâche : le lot en
    cours et les deux suivants, et tout lot en cours ; tous avec `--all`."""
    if tout:
        return list(s.lots)
    fenetre = s.lots[s.courant:s.courant + DETAILLES]
    return [lot for lot in s.lots if lot in fenetre or lot.en_cours]


def besoins_dans_l_ordre(s: Suite) -> list[str]:
    """Les besoins qui ont des tâches, dans l'ordre des lots qui les mènent ;
    puis ceux dont les tâches ouvertes ne sont dans aucun lot."""
    vus = [t.besoin for lot in s.lots for t in lot.taches] + [t.besoin for t in s.hors_lot]
    return [b for b in dict.fromkeys(vus) if b in s.besoins and s.besoins[b].statut not in memoire.BACKLOG_CLOS]


def taches_du_besoin(s: Suite, b: str) -> list[Tache]:
    return [t for t in s.taches.values() if t.besoin == b]


# --- Les deux formats -----------------------------------------------------


def _titre(e: memoire.Entree, court: bool) -> str:
    return outils.raccourcir(e.titre, TITRE) if court else e.titre


def _ligne_jalon(j: Jalon, prochain: bool, court: bool, gras: bool = False) -> str:
    ident = f"**{j.entree.id}**" if gras else j.entree.id
    ligne = trad("{id} — {titre} : {clos} besoin(s) clos sur {total}", id=ident, titre=_titre(j.entree, court),
                 clos=j.clos, total=j.total)
    return ligne + trad(" — le prochain") if prochain else ligne


def _comptes(taches: list[Tache]) -> str:
    """Ce qui reste d'un lot ou d'un besoin, compté par avancement."""
    ouvertes = [t.avancement for t in taches if not t.close]
    return ", ".join(trad(COMPTES[a], n=ouvertes.count(a)) for a in ORDRE_DES_COMPTES if a in ouvertes)


def _avancement_lot(lot: Lot, demandes: bool) -> str:
    """Ses tâches closes sur le total, ce qui reste, et les demandes sans
    réponse qu'il attend : nommées en Markdown, comptées sinon."""
    morceaux = [trad("{clos} tâche(s) close(s) sur {total}", clos=lot.closes, total=len(lot.taches))]
    reste = _comptes(lot.taches)
    if reste:
        morceaux.append(reste)
    if lot.demandes:
        morceaux.append(trad("attend {ids}", ids=", ".join(lot.demandes)) if demandes
                        else trad("{n} demande(s) sans réponse", n=len(lot.demandes)))
    return " · ".join(morceaux)


def _ligne_lot(lot: Lot, court: bool) -> str:
    """Un lot en une ligne : en compact, sans nommer les demandes qu'il
    attend."""
    return trad("{id} — {titre} : {avancement}", id=lot.entree.id, titre=_titre(lot.entree, court),
                avancement=_avancement_lot(lot, demandes=not court))


def _ligne_besoin(s: Suite, b: str, court: bool) -> str:
    siennes = taches_du_besoin(s, b)
    lots = list(dict.fromkeys(t.lot for t in siennes if t.lot))
    ligne = trad("{id} — {titre} : {clos} tâche(s) close(s) sur {total}", id=b, titre=_titre(s.besoins[b], court),
                 clos=sum(t.close for t in siennes), total=len(siennes))
    return ligne + (trad(" — lot(s) : {lots}", lots=", ".join(lots)) if lots else trad(" — dans aucun lot"))


def _resume_hors_lot(s: Suite) -> str:
    return trad("hors des lots : {taches} tâche(s) ouverte(s), {decouper} besoin(s) à découper, {fermer} à fermer, "
                "{bloques} entrée(s) bloquée(s), {humain} pour l'humain, {demandes} demande(s) en attente",
                taches=len(s.hors_lot), decouper=len(s.a_decouper), fermer=len(s.a_fermer), bloques=len(s.bloques),
                humain=len(s.pour_l_humain), demandes=len(s.demandes))


def _alerte(a: str, b: str, p: str) -> str:
    return trad("ordre ambigu : {a} et {b} attendent tous deux {p}, sans ordre entre eux — que l'un attende "
                "l'autre", a=a, b=b, p=p)


def texte(s: Suite, par: str = "batch") -> str:
    """Le format compact : une ligne par jalon, puis par lot (le lot en cours
    marqué), ou par besoin ; ce qui est hors des lots, compté ; les
    alertes."""
    res = [trad("La suite du projet, calculée depuis le backlog — détaillée : `{commande} --format markdown`",
                commande=COMMANDE)]
    if s.jalons:
        res.append(trad("jalons, dans leur ordre :"))
        res += [f"  {_ligne_jalon(j, k == 0, court=True)}" for k, j in enumerate(s.jalons)]
    if par == "need":
        besoins = besoins_dans_l_ordre(s)
        if besoins:
            res.append(trad("besoins, dans l'ordre des lots :"))
            res += [f"  {_ligne_besoin(s, b, court=True)}" for b in besoins]
    elif s.lots:
        res.append(trad("lots, dans leur ordre (▶ en cours) :"))
        for lot in s.lots:
            res.append(f"{'▶' if lot.en_cours else ' '} " + _ligne_lot(lot, court=True))
    if not (s.jalons or s.lots):
        res.append(trad("ni jalon ni lot au backlog"))
    res.append(_resume_hors_lot(s))
    if s.sans_jalon:
        res.append(trad("après les jalons : {n} besoin(s) ouvert(s) dans aucun jalon", n=len(s.sans_jalon)))
    res += [f"!! {_alerte(*a)}" for a in s.alertes]
    return "\n".join(res)


def _ligne_tache(t: Tache, avec_lot: bool) -> str:
    morceaux = [f"{t.entree.id} — {t.entree.titre}"]
    if avec_lot:
        morceaux.append(trad("lot {id}", id=t.lot) if t.lot else trad("dans aucun lot"))
    elif t.besoin:
        morceaux.append(trad("besoin {id}", id=t.besoin))
    if t.priorite in PRIORITES:
        morceaux.append(trad(PRIORITES[t.priorite]))
    etat = trad(AVANCEMENT.get(t.avancement, t.avancement))
    morceaux.append(trad("{etat} : {ids}", etat=etat, ids=", ".join(t.attend)) if t.attend else etat)
    return "- " + " · ".join(morceaux)


def _liste(titre: str, lignes: list[str]) -> list[str]:
    return [f"- **{titre}**", *(f"  {l}" for l in lignes)] if lignes else []


def markdown(s: Suite, par: str = "batch", tout: bool = False, liens: dict[str, str] | None = None) -> str:
    """Le format détaillé, en Markdown : les jalons ; le lot en cours et les
    deux suivants tâche par tâche, les autres en une ligne (`tout` : tous
    détaillés), ou chaque besoin avec ses tâches et le lot de chacune ; ce
    qui est hors des lots, nommé ; les alertes. `liens` : le lien d'une
    demande ou d'une entrée pour l'humain, par identifiant."""
    liens = liens or {}
    res = ["## " + trad("La suite du projet"), "",
           trad("Calculée depuis le backlog par `{commande} --format markdown` : rien n'y est écrit à la main.",
                commande=COMMANDE), ""]
    if s.jalons:
        res += ["### " + trad("Jalons, dans leur ordre"), ""]
        res += [f"- {_ligne_jalon(j, k == 0, court=False, gras=True)}" for k, j in enumerate(s.jalons)] + [""]
    suivis = detailles(s, tout)
    if par == "need":
        besoins = besoins_dans_l_ordre(s)
        if besoins:
            res += ["### " + trad("Besoins, dans l'ordre des lots"), ""]
            lots_suivis = {lot.entree.id for lot in suivis}
            autres = []
            for b in besoins:
                siennes = taches_du_besoin(s, b)
                if tout or any(t.lot in lots_suivis for t in siennes):
                    res += [f"#### {_ligne_besoin(s, b, court=False)}", ""]
                    res += [_ligne_tache(t, avec_lot=True) for t in siennes] + [""]
                else:
                    autres.append(f"- {_ligne_besoin(s, b, court=False)}")
            if autres:
                res += ["#### " + trad("Les autres besoins"), "", *autres, ""]
    elif s.lots:
        res += ["### " + trad("Lots, dans leur ordre d'exécution"), ""]
        autres = []
        for lot in s.lots:
            titre = f"{lot.entree.id} — {lot.entree.titre}"
            if lot in suivis:
                marque = "▶ " if lot.en_cours else ""
                res += [f"#### {marque}{titre}" + (trad(" — en cours") if lot.en_cours else ""), "",
                        _avancement_lot(lot, demandes=True), ""]
                res += [_ligne_tache(t, avec_lot=False) for t in lot.taches] + [""] if lot.taches else []
            else:
                autres.append("- " + _ligne_lot(lot, court=False))
        if autres:
            res += ["#### " + trad("Les lots suivants"), "", *autres, ""]
    if not (s.jalons or s.lots):
        res += [trad("Ni jalon ni lot au backlog."), ""]

    def nomme(e: memoire.Entree) -> str:
        lien = liens.get(e.id)
        return f"- [{e.id} — {e.titre}]({lien})" if lien else f"- {e.id} — {e.titre}"

    hors = (_liste(trad("Tâches dans aucun lot"), [_ligne_tache(t, avec_lot=False) for t in s.hors_lot])
            + _liste(trad("Besoins à découper en tâches"), [f"- {e.id} — {e.titre}" for e in s.a_decouper])
            + _liste(trad("Besoins à fermer, leurs tâches closes"), [f"- {e.id} — {e.titre}" for e in s.a_fermer])
            + _liste(trad("Bloqués"), [f"- {e.id} — {e.titre}" for e in s.bloques])
            + _liste(trad("Pour l'humain"), [nomme(e) for e in s.pour_l_humain])
            + _liste(trad("Demandes en attente"), [nomme(e) for e in s.demandes]))
    if s.sans_jalon:
        ids = [e.id for e in s.sans_jalon]
        montres = ids if tout else ids[:SANS_JALON_NOMMES]
        suite = trad(" … et {n} autre(s) : `--all`", n=len(ids) - len(montres)) if len(montres) < len(ids) else ""
        hors.append(trad("- **Après les jalons**, dans aucun jalon : {ids}{suite}", ids=", ".join(montres),
                         suite=suite))
    if hors:
        res += ["### " + trad("Hors des lots"), "", *hors, ""]
    res += [f"> **!!** {_alerte(*a)}" for a in s.alertes]
    return "\n".join(res).rstrip() + "\n"


def liens_pour_l_humain(projet: config.Projet, s: Suite) -> dict[str, str]:
    """Le permalien de chaque demande en attente et de chaque entrée pour
    l'humain, qu'il ouvre d'un clic ; aucun quand rien n'est poussé."""
    from socle import links

    res = {}
    for e in [*s.pour_l_humain, *s.demandes]:
        try:
            lien = links.lien(projet, e.fichier)[0]
        except Exception:  # la suite se donne même sans ses liens
            lien = None
        if lien:
            res[e.id] = lien
    return res


def rendre(projet: config.Projet, format_: str = "text", par: str = "batch", tout: bool = False) -> str:
    """La suite du projet, dans le format demandé."""
    s = calculer(memoire.Memoire.charger(projet.racine))
    if format_ == "markdown":
        return markdown(s, par, tout, liens_pour_l_humain(projet, s))
    return texte(s, par)
