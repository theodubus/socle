"""La migration du backlog en quatre formes (ADR-0083), à la mise à jour du
socle : mécanique, et idempotente sur le contenu.

- un lot (`forme : lot`) devient `L-`, un jalon (`forme : jalon`) `JA-`,
  clos compris, par ordre de leur ancien numéro, que chacun garde
  (`ancien : B-NNNN`) ; leur champ `forme` disparaît, et leur priorité,
  que `memoire.formes` refuse : un lot ni un jalon n'étaient déjà jamais
  prêts, elle ne changeait aucun ordre (le bilan nomme chacun) ;
- toute autre entrée reste un besoin ; sa section « Fait quand » devient
  « Satisfait quand », une fois, tant que le backlog n'a ni tâche, ni lot,
  ni jalon à leur préfixe ;
- chaque besoin qu'attend un lot ouvert reçoit une tâche qui reprend ses
  critères, chacun entier, et ses mentions récrites, vers laquelle sa
  section renvoie (`docs.copie` refuse une copie), et le lot l'attend à sa
  place ; un jalon attend les besoins de ses lots ; un besoin qui
  attendait un lot ou un jalon attend ses besoins et ses demandes encore
  ouverts ; une entrée close, jamais rien d'ouvert ;
- les mentions d'un numéro changé se récrivent dans le backlog et le
  chantier actif, une citation `B-NNNN@…` en simple mention (l'empreinte
  d'une version qui n'existe plus sous ce numéro) ; ailleurs, le journal,
  les décisions et les demandes gardent l'ancien numéro, qui se résout.

Elle n'écrit que l'arbre de travail, jamais l'index (T-0200) : le commit
de la demande seule qui suit une mise à jour n'emporte aucun renommage, et
`git add -A`, au commit des fichiers de la mise à jour, les prend avec le
reste ; git reconnaît les renommages à la lecture du diff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from socle import config, language as langue, memory as memoire, utils as outils

# L'empreinte que porte une tâche posée avant que l'index final ne se
# calcule ; jamais écrite pour de bon.
PROVISOIRE = "00000000"


@dataclass
class Bilan:
    """Ce que la migration a fait : (ancien, nouveau) des renumérotées, les
    tâches posées, les sections renommées, les lots et les jalons dont la
    priorité est retirée, par leur nouveau numéro."""

    renumerotees: list[tuple[str, str]] = field(default_factory=list)
    taches: list[str] = field(default_factory=list)
    sections: int = 0
    priorites: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.renumerotees or self.taches or self.sections or self.priorites)


def forme_ecrite(e: memoire.Entree) -> str:
    """La forme qu'un champ `forme` donnait à une entrée, avant ADR-0083."""
    return langue.valeur(memoire.nettoyer(e.meta.get("forme", "")))


def _morceaux_meta(texte: str) -> tuple[int, int, list[str]]:
    """Les lignes de métadonnées qui suivent le titre : (début, fin, morceaux
    `clé : valeur`)."""
    lignes = texte.split("\n")
    i = next((k for k, l in enumerate(lignes) if memoire.TITRE_RE.match(l)
              and memoire.ENTETE_ENTREE.match(memoire.TITRE_RE.match(l)["reste"])), None)
    if i is None:
        return 0, 0, []
    j = i + 1
    while j < len(lignes) and not lignes[j].strip():
        j += 1
    k = j
    while k < len(lignes) and lignes[k].lstrip().startswith(">"):
        k += 1
    brut = " · ".join(l.lstrip().removeprefix(">").strip() for l in lignes[j:k])
    return j, k, [m for m in re.split(r"\s+·\s+", brut) if m.strip()] if k > j else []


def _cle(morceau: str) -> str:
    return langue.champ(morceau.split(":", 1)[0]) if ":" in morceau else ""


def _remeta(texte: str, retirer: set[str] = frozenset(), remplacer: dict[str, str | None] | None = None,
            ajouter: list[str] = ()) -> str:
    """Le texte d'une entrée, sa ligne de métadonnées récrite : des champs
    retirés, la valeur d'autres remplacée (`None` : retiré), des morceaux
    ajoutés à la fin."""
    remplacer = remplacer or {}
    j, k, morceaux = _morceaux_meta(texte)
    if k == j:
        return texte
    res = []
    for m in morceaux:
        c = _cle(m)
        if c in retirer:
            continue
        if c in remplacer:
            if remplacer[c] is None:
                continue
            m = f"{m.split(':', 1)[0].rstrip()} : {remplacer[c]}"
        res.append(m)
    res += list(ajouter)
    lignes = texte.split("\n")
    return "\n".join(lignes[:j] + ["> " + " · ".join(res)] + lignes[k:])


def migrer_backlog(racine: Path, lg: str | None = None) -> Bilan:
    """Migre le backlog du projet dans `racine` : voir le module. Rend ce
    qui a été fait ; rien la seconde fois."""
    projet = config.Projet.charger(racine)
    lg = lg or langue.du_projet(projet)
    mem = memoire.Memoire.charger(racine)
    entrees = {e.id: e for e in mem.entrees(memoire.BACKLOG)
               if not e.archivee and not e.basculee and memoire.couche_attendue(e.fichier) == "backlog"}
    demandes = {e.id: e for e in mem.entrees("D")}
    bilan = Bilan()
    deja = any(e.type != "B" for e in entrees.values())

    # 1. Les lots et les jalons, par ordre de leur ancien numéro.
    from socle import identifiers as identifiants

    pris = set(mem.definitions()) | set(mem.anciens())
    for t in ("T", "L", "JA"):
        pris |= identifiants.pris_ailleurs(racine, t)
    nouveaux: dict[str, str] = {}
    for e in sorted(entrees.values(), key=lambda x: x.id):
        f = forme_ecrite(e)
        if e.type == "B" and f in ("lot", "jalon"):
            n = memoire.prochain_libre("L" if f == "lot" else "JA", pris, prive=e.prive)
            pris.add(n)
            nouveaux[e.id] = n
            bilan.renumerotees.append((e.id, n))

    def forme(i: str) -> str | None:
        """La forme d'un identifiant après la migration."""
        return memoire.type_d_id(nouveaux.get(i, i))

    def ouvert(i: str) -> bool:
        if i in demandes:
            return not memoire.demande_close(mem, demandes[i])
        return i in entrees and entrees[i].statut not in memoire.BACKLOG_CLOS

    def attendable(e: memoire.Entree, x: str) -> bool:
        """Ce qu'un lot développé dans l'`après` d'un jalon `e` lui fait
        attendre : ouvert, tous ses besoins ; clos, ses besoins clos, jamais
        un besoin ou une demande encore ouverts, que `memoire.ordre`
        refuserait (T-0052)."""
        return e.statut not in memoire.BACKLOG_CLOS or not ouvert(x)

    def besoins_de(i: str, vus: set[str]) -> list[str]:
        """Ce que rassemble un lot ou un jalon renuméroté : ses besoins, de
        proche en proche, et ses demandes."""
        if i in vus or i not in entrees:
            return []
        vus.add(i)
        res = []
        for d in memoire.dependances(entrees[i]):
            if d in nouveaux:
                res += besoins_de(d, vus) if forme(i) == "JA" or forme(d) == "JA" else []
            elif d in demandes or forme(d) == "B":
                res.append(d)
        return list(dict.fromkeys(res))

    # 2. Les tâches des besoins qu'attend un lot ouvert, dans l'ordre des
    # lots puis de leur `après`.
    textes: dict[str, str] = {}      # chemin → texte récrit
    apres_nouveau: dict[str, list[str]] = {}
    poses: list[tuple[str, memoire.Entree, str]] = []   # (tâche, besoin, chemin)
    for ancien, nouvel in bilan.renumerotees:
        e = entrees[ancien]
        if forme(ancien) == "L":
            liste = []
            for d in memoire.dependances(e):
                if e.statut not in memoire.BACKLOG_CLOS and forme(d) == "B" and d in entrees:
                    t = memoire.prochain_libre("T", pris, prive=entrees[d].prive)
                    pris.add(t)
                    poses.append((t, entrees[d], nouvel))
                    liste.append(t)
                else:
                    liste.append(nouveaux.get(d, d))
            apres_nouveau[ancien] = liste
        else:
            liste = []
            for d in memoire.dependances(e):
                if forme(d) == "L":
                    liste += [x for x in besoins_de(d, set()) if attendable(e, x)]
                else:
                    liste.append(nouveaux.get(d, d))
            apres_nouveau[ancien] = list(dict.fromkeys(liste))

    # 3. Les fichiers des renumérotées : `forme` et la priorité retirés,
    # `après` récrit, `ancien` ajouté une fois les mentions récrites. Un lot
    # ni un jalon n'étaient prêts, avant ADR-0083 déjà : leur priorité ne
    # changeait aucun ordre, et `memoire.formes` la refuse désormais.
    champ_ancien = langue.mot(langue.CHAMPS, "ancien", lg)
    renommes: dict[str, str] = {}
    for ancien, nouvel in bilan.renumerotees:
        e = entrees[ancien]
        apres = apres_nouveau.get(ancien) or None
        if "priorite" in e.meta:
            bilan.priorites.append(nouvel)
        textes[e.fichier] = _remeta(textes.get(e.fichier, mem.fichiers[e.fichier].texte),
                                    retirer={"forme", "priorite"},
                                    remplacer={"apres": ", ".join(apres) if apres else None})
        dossier, nom = e.fichier.rsplit("/", 1)
        renommes[e.fichier] = f"{dossier}/{nouvel}{nom[len(ancien):]}"

    # 4. Un besoin qui attendait un lot ou un jalon attend ses besoins et ses
    # demandes encore ouverts ; la section des besoins, renommée une fois.
    for e in entrees.values():
        if e.id in nouveaux:
            continue
        deps = memoire.dependances(e)
        if any(d in nouveaux for d in deps):
            liste = []
            for d in deps:
                # Ouverte, l'entrée n'attend que ce qui reste ouvert ; close,
                # que ce qui est clos (T-0052).
                liste += [x for x in besoins_de(d, set()) if ouvert(x) != (e.statut in memoire.BACKLOG_CLOS)] \
                    if d in nouveaux else [d]
            liste = [x for x in dict.fromkeys(liste) if x != e.id]
            textes[e.fichier] = _remeta(textes.get(e.fichier, mem.fichiers[e.fichier].texte),
                                        remplacer={"apres": ", ".join(liste) if liste else None})
        if not deja and e.type == "B" and memoire.SECTION_FAIT_QUAND.search(e.corps) \
                and not memoire.SECTION_SATISFAIT_QUAND.search(e.corps):
            texte = textes.get(e.fichier, mem.fichiers[e.fichier].texte)
            textes[e.fichier] = re.sub(r"(?mi)^(#{2,4}\s+)(Fait quand|Done when)(\s*)$",
                                       lambda m: m[1] + langue.SATISFAIT_QUAND["en" if m[2].lower() == "done when"
                                                                               else "fr"] + m[3], texte, count=1)
            bilan.sections += 1

    # 5. Les mentions des numéros changés, dans le backlog et le chantier
    # actif.
    ch = projet.chemins
    motif = re.compile(r"(?<![\w-])(%s)(?:@[0-9a-f]{8})?(?![\w-])" % "|".join(map(re.escape, nouveaux))) \
        if nouveaux else None

    def recrire(texte: str) -> str:
        """Un texte, ses mentions des numéros changés récrites."""
        return motif.sub(lambda m: nouveaux[m[1]], texte) if motif else texte

    if nouveaux:
        cibles = [c for c in mem.fichiers if memoire.couche_attendue(c) == "backlog"]
        cibles += [c for c in (ch.actif, ch.dans_prive(ch.actif)) if (racine / c).is_file()]
        for c in cibles:
            avant = textes.get(c, mem.fichiers[c].texte if c in mem.fichiers else (racine / c).read_text("utf-8"))
            apres = recrire(avant)
            if apres != avant:
                textes[c] = apres
        for ancien, nouvel in bilan.renumerotees:
            f = entrees[ancien].fichier
            textes[f] = _remeta(textes[f], ajouter=[f"{champ_ancien} : {ancien}"])

    # 6. Les tâches, chacune dans son fichier, avec les critères de son
    # besoin, dont la section renvoie à elle : une copie divergerait, et
    # `docs.copie` la refuse. L'index qu'elles citent se calcule une fois
    # tout écrit.
    siennes: dict[str, list[str]] = {}
    for t, b, _ in poses:
        siennes.setdefault(b.id, []).append(t)
    # Le besoin est lu avant la réécriture de ses mentions : le titre, les
    # champs et les critères de sa tâche se récrivent à leur tour (T-0052).
    for i, ts in siennes.items():
        b = entrees[i]
        criteres = criteres_entiers(b)
        if criteres:
            coche = "x" if all(c for c, _ in criteres) else " "
            textes[b.fichier] = _renvoyer(textes.get(b.fichier, mem.fichiers[b.fichier].texte),
                                          f"- [{coche}] {_texte(lg, 'renvoi', taches=', '.join(ts))}")
    for t, b, lot in poses:
        cases = [f"- [{'x' if coche else ' '}] {recrire(texte)}" for coche, texte in criteres_entiers(b)] or \
            [f"- [ ] {_texte(lg, 'critere', besoin=b.id)}"]
        champs = {"statut": b.statut, "origine": recrire(b.meta.get("origine") or b.id), "besoin": b.id}
        if b.statut in memoire.BACKLOG_CLOS and b.meta.get("ref"):
            champs["ref"] = recrire(b.meta["ref"])
        champs["lu"] = f"backlog@{PROVISOIRE}"
        dossier = b.fichier.rsplit("/", 1)[0]
        titre = recrire(b.titre)
        chemin = f"{dossier}/{t}-{memoire.nom_de_fichier(titre)}.md"
        texte = (f"{langue.entete_fichier('backlog', 'privee' if b.prive else 'publique', lg)}\n"
                 f"# {t} — {titre}\n\n{langue.meta(lg, 'T', **champs)}\n\n"
                 f"{_texte(lg, 'corps', besoin=b.id, lot=lot)}\n\n## {langue.FAIT_QUAND[lg]}\n\n"
                 + "\n".join(cases) + "\n")
        textes[chemin] = texte
        bilan.taches.append(t)

    if not bilan:
        return bilan
    for c, texte in textes.items():
        outils.ecrire(racine / c, texte if texte.endswith("\n") else texte + "\n")
    for avant, apres in renommes.items():
        (racine / avant).rename(racine / apres)
    poser_lectures(racine, bilan.taches)
    return bilan


# Une ligne qui ouvre un élément de liste au premier niveau.
ELEMENT = re.compile(r"^(?:[-*+]|\d+[.)])\s")


def _suite(ligne: str) -> bool:
    """La ligne continue-t-elle la case qui la précède ? Oui si elle n'est ni
    vide, ni une case, ni un titre, ni un élément de liste au premier
    niveau : en retrait, ou une continuation paresseuse (T-0052)."""
    return bool(ligne.strip()) and not memoire.CASE.match(ligne) and not ligne.startswith("#") \
        and (ligne[0].isspace() or not ELEMENT.match(ligne))


def criteres_entiers(e: memoire.Entree) -> list[tuple[bool, str]]:
    """Les critères d'un besoin que reprend sa tâche, de sa section « Fait
    quand », ou à défaut de celle de sa forme : (coché, texte), le texte
    d'un critère écrit sur plusieurs lignes entier, ses lignes de suite
    telles qu'écrites ; `memoire.criteres` n'en lit que la première
    (T-0052)."""
    for section in (memoire.SECTION_FAIT_QUAND, memoire.section_de(e)):
        m = section.search(e.corps)
        res: list[tuple[bool, str]] = []
        suite = False
        for ligne in e.corps[m.end():].splitlines() if m else ():
            if ligne.startswith("#"):
                break
            c = memoire.CASE.match(ligne)
            if c:
                res.append((c[1] != " ", c[2]))
                suite = True
            elif suite and _suite(ligne):
                res[-1] = (res[-1][0], res[-1][1] + "\n" + ligne.rstrip())
            else:
                suite = False
        if res:
            return res
    return []


def _renvoyer(texte: str, case: str) -> str:
    """Le texte d'un besoin, les cases de sa section remplacées par une
    seule, qui renvoie à ses tâches ; les lignes de suite d'une case partent
    avec elle (T-0052)."""
    lignes, res, dedans, posee, suite = texte.split("\n"), [], False, False, False
    for l in lignes:
        if re.match(r"^#{2,4}\s+(?:Fait quand|Done when|Satisfait quand|Satisfied when)\s*$", l, re.I):
            dedans = True
        elif l.startswith("#"):
            dedans = False
        if dedans and memoire.CASE.match(l):
            if not posee:
                res.append(case)
                posee = True
            suite = True
            continue
        if dedans and suite and _suite(l):
            continue
        suite = False
        res.append(l)
    return "\n".join(res)


def poser_lectures(racine: Path, taches: list[str]) -> str:
    """Les tâches posées citent l'index du backlog sans elles (`lu :
    backlog@…`) : celui que la lecture prouvée reconnaît, sans les entrées
    que la plage ajoute (ADR-0083). Rend l'empreinte posée."""
    mem = memoire.Memoire.charger(racine)
    h = memoire.empreinte_index(mem, "backlog", set(taches))
    for t in taches:
        e = mem.entree(t)
        if e is None:
            continue
        p = racine / e.fichier
        p.write_text(re.sub(r"(?<![\w-])backlog@[0-9a-f]{8}", f"backlog@{h}", p.read_text(encoding="utf-8"), count=1),
                     encoding="utf-8")
    return h


TEXTES = {
    "corps": {"fr": "La tâche de {besoin}, que la migration du backlog en quatre formes a posée dans le lot {lot} : "
                    "elle reprend ses critères, à récrire en livrable qu'un test vérifie.",
              "en": "The task of {besoin}, set by the migration of the backlog into four forms in the batch {lot}: "
                    "it takes its criteria, to be rewritten as a deliverable a test checks."},
    "critere": {"fr": "ce que demande {besoin} est livré, et un test le montre",
                "en": "what {besoin} asks for is delivered, and a test shows it"},
    "renvoi": {"fr": "le « Fait quand » de {taches} est tenu", "en": "the “Done when” of {taches} holds"},
}


def _texte(lg: str, cle: str, **valeurs) -> str:
    return TEXTES[cle].get(lg, TEXTES[cle]["fr"]).format(**valeurs)
