"""La suite du projet d'un coup d'œil (`socle roadmap`) : les jalons et
leurs besoins clos, les lots dans leur ordre d'exécution avec leurs tâches,
les besoins, et ce qui n'est dans aucun lot. Elle se calcule depuis le
backlog comme l'état, par les mêmes fonctions (`memory.Graphe`,
`memory.ordre_de`) : rien n'y est écrit à la main.

Deux formats, qui suivent tous deux l'ordre d'exécution des lots :
compact (`text`), une ligne alignée en colonnes par jalon et par lot, ou
par besoin, pour le terminal et le récap de la clôture d'un lot ; détaillé
(`markdown`), le lot en cours et les deux suivants avec le tableau de
leurs tâches, l'état et la priorité en symboles, pour la conversation et
le résumé d'une exécution de la CI. Le compact ne nomme
aucune demande : collé dans une réponse, il ne citerait pas une demande en
attente sans son lien ; le détaillé donne le lien de chacune."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations

from socle import config, memory as memoire
from socle.messages import a_traduire, trad

FORMATS = ("text", "markdown")
LECTURES = ("batch", "need")
# Sans `--all`, la fenêtre, commune à tous les jalons : le lot en cours (ou
# le premier) et les deux suivants dans l'ordre d'exécution. Le format
# détaillé les suit tâche par tâche, le compact les montre chacun en sa
# ligne.
DETAILLES = 3
# La largeur d'un titre, en caractères : dans la colonne du format compact,
# dans la ligne « Ensuite », et dans le format détaillé.
TITRE_COMPACT = 46
TITRE_ENSUITE = 32
TITRE_DETAILLE = 72
# Un titre se lit jusqu'à son premier « : » suivi d'une espace : ce qui suit
# le précise.
DEUX_POINTS = re.compile(r"\s*:(?=\s|$)")
# Les besoins hors de tout jalon que le format détaillé nomme sans `--all`.
SANS_JALON_NOMMES = 15
# Les besoins ouverts que la ligne « Ensuite » nomme, par jalon et après les
# jalons.
ENSUITE_NOMMES = 3
COMMANDE = "python3 .socle/socle roadmap"

# Où en est une tâche, sous sa clé interne (son statut, ou, ouverte, `pret`
# ou `attend`), en symbole ; sa priorité, en flèche.
SYMBOLES = {"fait": "✓", "en-cours": "▶", "pret": "○", "attend": "⏳", "bloque": "✗", "abandonne": "⊘"}
FLECHES = {"haute": "↑", "basse": "↓"}
# Les comptes du format compact, au singulier et au pluriel.
TACHES_HORS_LOT = (a_traduire("{n} tâche dans aucun lot"), a_traduire("{n} tâches dans aucun lot"))
SANS_TACHE = (a_traduire("{n} besoin sans tâche"), a_traduire("{n} besoins sans tâche"))
A_FERMER = (a_traduire("{n} besoin à fermer"), a_traduire("{n} besoins à fermer"))
BLOQUES = (a_traduire("{n} bloqué ({ids})"), a_traduire("{n} bloqués ({ids})"))
POUR_L_HUMAIN = (a_traduire("{n} pour l'humain"), a_traduire("{n} pour l'humain"))
EN_ATTENTE = (a_traduire("{n} demande en attente"), a_traduire("{n} demandes en attente"))
DEMANDES_ATTENDUES = (a_traduire("attend {n} demande"), a_traduire("attend {n} demandes"))
ET_D_AUTRES = (a_traduire("{ids} et {n} autre"), a_traduire("{ids} et {n} autres"))


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
    """La fenêtre, commune à tous les jalons : le lot en cours et les deux
    suivants dans l'ordre d'exécution, et tout lot en cours ; tous avec
    `--all`. Le format détaillé les suit tâche par tâche, le compact les
    montre chacun en sa ligne."""
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


def court(titre: str, largeur: int) -> str:
    """Un titre dans sa colonne : sa partie avant le premier « : » (suivi
    d'une espace ou en fin), coupée à `largeur` caractères avec « … » ; un
    titre plus court reste entier."""
    tete = DEUX_POINTS.split(titre, maxsplit=1)[0].strip() or titre.strip()
    return tete if len(tete) <= largeur else tete[:max(largeur - 1, 0)].rstrip() + "…"


def besoins_du_jalon(j: Jalon) -> list[str]:
    return [d for d in dict.fromkeys(memoire.dependances(j.entree)) if memoire.type_d_id(d) == "B"]


def _ouverts_du_jalon(s: Suite, j: Jalon) -> list[str]:
    return [b for b in besoins_du_jalon(j) if b in s.besoins and s.besoins[b].statut not in memoire.BACKLOG_CLOS]


def groupes(s: Suite, par: str = "batch") -> list[tuple[Jalon | None, list]]:
    """Les lots strictement dans leur ordre d'exécution, ou par besoin les
    besoins qui ont des tâches dans l'ordre de leurs lots, coupés en suites
    qui servent un même jalon : le premier, dans l'ordre des jalons, qui
    tient le besoin d'une de leurs tâches. Une suite commence chaque fois
    que le jalon change d'un élément au suivant : un jalon dont les lots
    alternent avec ceux d'un autre revient. Une suite qui ne sert aucun
    jalon a `None`, à sa place dans l'ordre."""
    if par == "need":
        elements, besoins = besoins_dans_l_ordre(s), (lambda b: {b})
    else:
        elements, besoins = s.lots, (lambda lot: {t.besoin for t in lot.taches})
    tenus = [(j, set(besoins_du_jalon(j))) for j in s.jalons]
    rangs: list[tuple[Jalon | None, list]] = []
    for x in elements:
        j = next((j for j, bs in tenus if bs & besoins(x)), None)
        if rangs and rangs[-1][0] is j:
            rangs[-1][1].append(x)
        else:
            rangs.append((j, [x]))
    return rangs


def ensuite(s: Suite, rangs: list[tuple[Jalon | None, list]]) -> list[Jalon]:
    """Les jalons ouverts que rien ne montre plus haut : sans lot, ou, par
    besoin, sans besoin qui ait des tâches."""
    montres = {j.entree.id for j, _ in rangs if j}
    return [j for j in s.jalons if j.entree.id not in montres]


def _nombre(n: int, formes: tuple[str, str], **valeurs) -> str:
    """Un compte, au singulier ou au pluriel."""
    return trad(formes[0] if n == 1 else formes[1], n=n, **valeurs)


def _quelques(ids: list[str], nommes: int) -> str:
    """Les premiers identifiants nommés, le reste compté."""
    if len(ids) <= nommes:
        return ", ".join(ids)
    return _nombre(len(ids) - nommes, ET_D_AUTRES, ids=", ".join(ids[:nommes]))


def _etat_lot(lot: Lot, nommer: bool) -> list[str]:
    """Où en est un lot, s'il est en cours ou arrêté : bloqué, ou qui attend
    des demandes sans réponse, nommées en Markdown, comptées en compact."""
    res = [trad("en cours")] if lot.en_cours else [trad("bloqué")] if lot.entree.statut == "bloque" else []
    if lot.demandes:
        res.append(trad("attend {ids}", ids=", ".join(lot.demandes)) if nommer
                   else _nombre(len(lot.demandes), DEMANDES_ATTENDUES))
    return res


def _avancement(taches: list[Tache]) -> str:
    """Les tâches closes sur le total."""
    return f"{sum(t.close for t in taches)}/{len(taches)}"


def _besoins_clos(j: Jalon) -> str:
    return trad("{clos}/{total} besoins clos", clos=j.clos, total=j.total)


def _lots_du_besoin(s: Suite, b: str) -> str:
    lots = list(dict.fromkeys(t.lot for t in taches_du_besoin(s, b) if t.lot))
    return ", ".join(lots) if lots else trad("dans aucun lot")


def _colonnes(rangees: list[tuple[str, str | None, str]]) -> list[str]:
    """Des lignes (gauche, avancement, suite) alignées en colonnes, comptées
    en caractères : ce qui suit la partie gauche (l'avancement, ou la suite
    d'une ligne qui n'en a pas) commence à la même colonne pour toutes, et
    la suite d'un avancement aussi. Une ligne sans rien à droite reste
    seule."""
    largeur = max((len(a) for _, a, _ in rangees if a is not None), default=0)
    droites = [(g, (a.ljust(largeur) + "  " + r).rstrip() if a is not None else r) for g, a, r in rangees]
    colonne = max((len(g) for g, d in droites if d), default=0) + 2
    return [g.ljust(colonne) + d if d else g for g, d in droites]


def _hors_lot(s: Suite) -> str:
    """La ligne « Hors lot » du format compact : les comptes non nuls, les
    bloqués nommés ; aucune demande nommée."""
    comptes = [(s.hors_lot, TACHES_HORS_LOT), (s.a_decouper, SANS_TACHE), (s.a_fermer, A_FERMER),
               (s.bloques, BLOQUES), (s.pour_l_humain, POUR_L_HUMAIN), (s.demandes, EN_ATTENTE)]
    morceaux = [_nombre(len(xs), formes, **({"ids": ", ".join(e.id for e in xs)} if formes is BLOQUES else {}))
                for xs, formes in comptes if xs]
    return trad("Hors lot : {comptes}", comptes=" · ".join(morceaux) if morceaux else trad("rien"))


def _ensuite(s: Suite, jalons: list[Jalon]) -> str | None:
    """La ligne « Ensuite » du format compact : les jalons ouverts sans lot,
    chacun avec ses premiers besoins ouverts, puis les besoins ouverts
    d'aucun jalon, quelques-uns nommés et le reste compté."""
    morceaux = []
    for j in jalons:
        ouverts = _ouverts_du_jalon(s, j)
        nommes = ", ".join(ouverts[:ENSUITE_NOMMES]) + (", …" if len(ouverts) > ENSUITE_NOMMES else "")
        morceaux.append(f"{j.entree.id} {court(j.entree.titre, TITRE_ENSUITE)}" + (f" ({nommes})" if ouverts else ""))
    if s.sans_jalon:
        ids = _quelques([e.id for e in s.sans_jalon], ENSUITE_NOMMES)
        morceaux.append(trad("puis {ids}", ids=ids) if morceaux else ids)
    return trad("Ensuite : {suite}", suite=" · ".join(morceaux)) if morceaux else None


def _alerte(a: str, b: str, p: str) -> str:
    return trad("ordre ambigu : {a} et {b} attendent tous deux {p}, sans ordre entre eux — que l'un attende "
                "l'autre", a=a, b=b, p=p)


def texte(s: Suite, par: str = "batch", tout: bool = False) -> str:
    """Le format compact, aligné en colonnes : les lots dans leur ordre
    d'exécution, ou les besoins dans l'ordre de leurs lots, l'en-tête d'un
    jalon (ses besoins clos) chaque fois que le jalon change, « Hors des
    jalons » de même ; le lot en cours marqué ▶. Les lots de la fenêtre ont
    chacun leur ligne ; hors d'elle, une suite de lots d'un même jalon tient
    en une ligne, un lot seul garde la sienne ; tous avec `tout`. Puis les
    lignes « Hors lot » et « Ensuite », et les alertes. Il ne nomme aucune
    demande."""
    rangs = groupes(s, par)
    fenetre = {lot.entree.id for lot in detailles(s, tout)}
    largeur = max((len(x if par == "need" else x.entree.id) for _, xs in rangs for x in xs), default=0)
    largeur_j = max((len(j.entree.id) for j, _ in rangs if j), default=0)

    def lot_seul(lot: Lot) -> tuple[str, str, str]:
        return (f" {'▶' if lot.en_cours else ' '} {lot.entree.id:<{largeur}}  {court(lot.entree.titre, TITRE_COMPACT)}",
                _avancement(lot.taches), " · ".join(_etat_lot(lot, nommer=False)))

    rangees: list[tuple[str, str | None, str]] = []
    for j, elements in rangs:
        if j:
            rangees.append((f"{j.entree.id:<{largeur_j}}  {court(j.entree.titre, TITRE_COMPACT)}", None,
                            _besoins_clos(j)))
        elif s.jalons:
            rangees.append((trad("Hors des jalons"), None, ""))
        if par == "need":
            rangees += [(f"   {b:<{largeur}}  {court(s.besoins[b].titre, TITRE_COMPACT)}",
                         _avancement(taches_du_besoin(s, b)), _lots_du_besoin(s, b)) for b in elements]
            continue
        caches: list[Lot] = []
        for lot in [*elements, None]:
            if lot is not None and lot.entree.id not in fenetre:
                caches.append(lot)
                continue
            if len(caches) == 1:
                rangees.append(lot_seul(caches[0]))
            elif caches:
                rangees.append(("   " + trad("…  {premier} à {dernier}", premier=caches[0].entree.id,
                                             dernier=caches[-1].entree.id),
                                _avancement([t for c in caches for t in c.taches]), ""))
            caches = []
            if lot is not None:
                rangees.append(lot_seul(lot))
    res = [] if (s.jalons or s.lots) else [trad("ni jalon ni lot au backlog")]
    res += _colonnes(rangees)
    res.append(_hors_lot(s))
    suite = _ensuite(s, ensuite(s, rangs))
    if suite:
        res.append(suite)
    res += [f"!! {_alerte(*a)}" for a in s.alertes]
    return "\n".join(res)


def _cellule(texte_: str) -> str:
    """Un texte dans une cellule d'un tableau Markdown, sa barre échappée."""
    return texte_.replace("|", "\\|")


def _tableau(entete: list[str], rangees: list[list[str]]) -> list[str]:
    """Un tableau Markdown, sa ligne de séparation comprise : sans elle,
    GitHub ne le dessine pas."""
    def ligne(cellules: list[str]) -> str:
        return "|" + "|".join(f" {c} " if c else " " for c in cellules) + "|"

    return [ligne(entete), ligne(["---"] * len(entete)), *(ligne(r) for r in rangees)]


def _fleche(priorite: str | None) -> str:
    return f" {FLECHES[priorite]}" if priorite in FLECHES else ""


def _rangee_tache(t: Tache, avec_lot: bool) -> list[str]:
    """Une tâche en une ligne de tableau : son état en symbole, son
    identifiant, son besoin (ou son lot) suivi de sa priorité, son titre
    coupé, puis ce qu'elle attend."""
    titre = _cellule(court(t.entree.titre, TITRE_DETAILLE))
    if t.attend:
        titre += " · " + trad("attend {ids}", ids=", ".join(t.attend))
    milieu = (t.lot if avec_lot else t.besoin) or "—"
    return [SYMBOLES.get(t.avancement, "?"), t.entree.id, milieu + _fleche(t.priorite), titre]


def _tableau_de_taches(taches: list[Tache], avec_lot: bool) -> list[str]:
    entete = ["", trad("Tâche"), trad("Lot") if avec_lot else trad("Besoin"), ""]
    return _tableau(entete, [_rangee_tache(t, avec_lot) for t in taches]) if taches else []


def _titre_de_groupe(s: Suite, j: Jalon | None, par: str) -> str:
    if j:
        return f"### {j.entree.id} — {court(j.entree.titre, TITRE_DETAILLE)} · {_besoins_clos(j)}"
    if s.jalons:
        return "### " + trad("Hors des jalons")
    return "### " + (trad("Besoins, dans l'ordre des lots") if par == "need"
                     else trad("Lots, dans leur ordre d'exécution"))


def _ligne_de_lot(lot: Lot, rang: int, detaille: bool) -> str:
    """« **n. L-NNNN — titre** · état · closes/total », ou, non détaillé, la
    même en un point de liste ; l'état seulement s'il est en cours ou
    arrêté, les demandes qu'il attend nommées."""
    titre = f"{lot.entree.id} — {court(lot.entree.titre, TITRE_DETAILLE)}"
    tete = f"**{rang}. {titre}**" if detaille else f"- **{rang}.** {titre}"
    return " · ".join([tete, *_etat_lot(lot, nommer=True), _avancement(lot.taches)])


def _ligne_de_besoin(s: Suite, b: str, detaille: bool) -> str:
    """« **B-NNNN — titre** · closes/total · ses lots »."""
    titre = f"{b} — {court(s.besoins[b].titre, TITRE_DETAILLE)}"
    tete = f"**{titre}**" if detaille else f"- {titre}"
    return " · ".join([tete, _avancement(taches_du_besoin(s, b)), _lots_du_besoin(s, b)])


def _symbole(s: Suite, e: memoire.Entree) -> str:
    """L'état d'une entrée hors des lots, en symbole."""
    if e.id in s.taches:
        return SYMBOLES.get(s.taches[e.id].avancement, "?")
    return SYMBOLES.get(e.statut, SYMBOLES["pret"])


def markdown(s: Suite, par: str = "batch", tout: bool = False, liens: dict[str, str] | None = None) -> str:
    """Le format détaillé, en Markdown : la légende des symboles ; les lots
    dans leur ordre d'exécution, l'en-tête d'un jalon (ses besoins clos)
    chaque fois que le jalon change, « Hors des jalons » de même ; les lots
    de la fenêtre avec le tableau de leurs tâches, les autres en une ligne
    numérotée chacun (`tout` : tous détaillés) ; ou les besoins dans l'ordre
    de leurs lots, chacun avec le tableau de ses tâches et le lot de
    chacune ; les jalons sans lot ; ce qui est hors des lots, en tableaux ;
    les alertes. `liens` : le lien d'une demande ou d'une entrée pour
    l'humain, par identifiant."""
    liens = liens or {}
    blocs: list[list[str]] = [
        ["## " + trad("La suite du projet")],
        [trad("Calculée depuis le backlog par `{commande} --format markdown` : rien n'y est écrit à la main.",
              commande=COMMANDE)],
        [trad("Légende : ✓ faite · ▶ en cours · ○ prête · ⏳ attend · ✗ bloquée · ⊘ abandonnée · ↑ priorité haute "
              "· ↓ priorité basse")]]
    rangs = groupes(s, par)
    lots_suivis = {lot.entree.id for lot in detailles(s, tout)}
    rang = {lot.entree.id: k + 1 for k, lot in enumerate(s.lots)}
    abrege = False
    for j, elements in rangs:
        blocs.append([_titre_de_groupe(s, j, par)])
        resumes: list[str] = []
        for x in elements:
            if par == "need":
                siennes = taches_du_besoin(s, x)
                detaille = tout or any(t.lot in lots_suivis for t in siennes)
                ligne, tableau = _ligne_de_besoin(s, x, detaille), _tableau_de_taches(siennes, avec_lot=True)
            else:
                detaille = x.entree.id in lots_suivis
                ligne = _ligne_de_lot(x, rang[x.entree.id], detaille)
                tableau = _tableau_de_taches(x.taches, avec_lot=False)
            if not detaille:
                resumes.append(ligne)
                abrege = True
                continue
            if resumes:
                blocs.append(resumes)
                resumes = []
            blocs += [[ligne], tableau]
        blocs.append(resumes)
    if abrege:
        blocs.append([trad("(`--all` pour tout le détail)")])
    if not (s.jalons or s.lots):
        blocs.append([trad("Ni jalon ni lot au backlog.")])
    apres = ensuite(s, rangs)
    if apres:
        blocs += [["### " + trad("Ensuite")], [
            f"- {j.entree.id} — {court(j.entree.titre, TITRE_DETAILLE)} · {_besoins_clos(j)}"
            + (f" : {', '.join(_ouverts_du_jalon(s, j))}" if _ouverts_du_jalon(s, j) else "") for j in apres]]

    def section(titre: str, entete: str, entrees: list[memoire.Entree], symbole: str | None = None) -> list[list[str]]:
        """Une section hors des lots, en tableau : une demande et une entrée
        pour l'humain ont le lien de leur identifiant."""
        rangees = [[symbole or _symbole(s, e),
                    (f"[{e.id}]({liens[e.id]})" if e.id in liens else e.id) + _fleche(memoire.priorite(e)),
                    _cellule(court(e.titre, TITRE_DETAILLE))] for e in entrees]
        return [[f"**{titre}**"], _tableau(["", entete, ""], rangees)] if entrees else []

    hors = [[f"**{trad('Tâches dans aucun lot')}**"], _tableau_de_taches(s.hors_lot, avec_lot=False)] \
        if s.hors_lot else []
    hors += (section(trad("Besoins à découper en tâches"), trad("Besoin"), s.a_decouper)
             + section(trad("Besoins à fermer, leurs tâches closes"), trad("Besoin"), s.a_fermer)
             + section(trad("Bloqués"), trad("Entrée"), s.bloques)
             + section(trad("Pour l'humain"), trad("Entrée"), s.pour_l_humain)
             + section(trad("Demandes en attente"), trad("Demande"), s.demandes, symbole=SYMBOLES["attend"]))
    if s.sans_jalon:
        ids = [e.id for e in s.sans_jalon]
        montres = ids if tout else ids[:SANS_JALON_NOMMES]
        suite = trad(" … et {n} autre(s) : `--all`", n=len(ids) - len(montres)) if len(montres) < len(ids) else ""
        hors.append([trad("- **Après les jalons**, dans aucun jalon : {ids}{suite}", ids=", ".join(montres),
                          suite=suite)])
    if hors:
        blocs += [["### " + trad("Hors des lots")], *hors]
    blocs.append([f"> **!!** {_alerte(*a)}" for a in s.alertes])
    return "\n\n".join("\n".join(b) for b in blocs if b) + "\n"


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
    return texte(s, par, tout)
