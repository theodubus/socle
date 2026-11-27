"""La passation d'une session à la suivante (`socle handoff`) : écrite dans
la mémoire (`memory/handoff.md`), que la session neuve trouve sur les
branches distantes, juge et retire.

Le moteur ne connaît que git et la mémoire, et ne lance pas `git fetch`.
Programmer la session suivante revient à la plateforme de l'agent, selon le
skill `socle-handoff` ; la session neuve part sur une demande de reprendre,
quelle qu'en soit la forme, que l'agent reconnaît : aucun contrôle ne lit le
message de l'humain.

- `write` : la passation, son estampille (l'heure `écrite` et la branche,
  qui l'identifient, et la chaîne) et ce qui attend ; l'agent la commite en
  dernier et pousse. Pour une session programmée (`--scheduled`), les bornes
  d'une chaîne sans l'humain : deux lots menés sans message de lui, ou un
  prochain lot sans tâche prête, et rien ne se programme.
- `check`, sans argument : parmi les passations que l'origine connaît (à la
  tête d'une branche distante, ou qu'un commit d'une branche distante a
  retirées), la plus récente. Reprise par une session dont le retrait n'est
  pas encore dans la branche par défaut, elle est refusée ; reprise et
  fusionnée, aucune n'attend ; sinon, sa garde, ses trois arguments tirés du
  dépôt. La passation de ce clone que l'origine n'a pas, ou un changement
  non commité, la fait refuser : c'est la vérification de la session qui
  part, après son push.
- `check --ref --head [--since]` : la garde seule, comme la reprise après
  une limite d'usage la donne. La session neuve ne travaille pas si
  quelqu'un a poussé sur sa branche depuis la passation, ou si une autre
  branche distante porte un commit daté d'après elle qui touche la mémoire
  sans être un ancêtre de la tête passée : une autre session travaille sur
  le projet, puisqu'un agent sous le socle écrit toujours sa mémoire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from socle import config, language as langue, memory as memoire, utils as outils
from socle.messages import trad

DISTANT = "origin"
# Deux lots menés sans message de l'humain, le lot en cours compris : la
# chaîne s'arrête là, et l'humain fait reprendre.
BORNE_DE_LA_CHAINE = 2
FORMAT_HEURE = memoire.FORMAT_HEURE
# Ce qui, dans un lot, se reprend : une tâche prête, ou en cours quand la
# passation coupe le lot près d'une limite.
A_REPRENDRE = ("pret", "en-cours")
# Les commits d'une branche qui touchent la passation, lus au plus pour y
# trouver celui qui a écrit une estampille.
LUS_AU_PLUS = 200

heure = memoire.heure_utc


class PassationRefusee(Exception):
    """La passation ne s'écrit pas : la raison dit quoi faire d'abord."""


@dataclass
class Verdict:
    """Le jugement de la garde : ses raisons de refuser, ou la référence où
    la session neuve se place, et sa tête."""

    refus: list[str] = field(default_factory=list)
    place: str | None = None
    sha: str | None = None


@dataclass
class Connue:
    """Une passation que l'origine connaît : les branches distantes qui la
    portent à leur tête, et les commits qui l'ont retirée, avec leur date."""

    passation: memoire.Passation
    tetes: list[str] = field(default_factory=list)
    retraits: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class Trouvee:
    """Ce que `check` sans argument trouve : la passation la plus récente,
    `None` quand aucune n'attend, et le verdict de sa garde."""

    passation: memoire.Passation | None
    verdict: Verdict


def lot_de_l_etat(racine: Path) -> tuple[str | None, list[str], bool]:
    """Le prochain lot que l'état donne, ce qui lui reste dans l'ordre de son
    `après`, et s'il a une tâche à reprendre (prête, ou en cours) ; sans
    lot, aucun identifiant, et s'il reste une tâche prête au backlog."""
    o = memoire.ordre(memoire.Memoire.charger(racine))
    if o is None:
        return None, [], False
    if o.lot is None:
        return None, [], bool(o.prets or o.basses)
    reste = [(i, a) for i, a in o.avancement if a not in memoire.CLOS_DANS_UN_LOT]
    return o.lot.id, [i for i, _ in reste], any(a in A_REPRENDRE for _, a in reste)


def branche_de_travail(racine: Path) -> str:
    """La branche que la passation nomme, où elle se pousse : celle que la
    branche courante suit sur l'origine, sauf la branche par défaut, d'où
    une branche de travail part sans y pousser ; sinon le nom de la branche
    courante. Refusé hors de toute branche."""
    branche = outils.branche_courante(racine)
    if not branche:
        raise PassationRefusee(trad("la tête est détachée, sur aucune branche : se placer d'abord sur la branche de "
                                    "travail, que la passation nomme"))
    suivie = outils.git(racine, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                        check=False).strip()
    if suivie.startswith(f"{DISTANT}/") and suivie != outils.branche_par_defaut(racine):
        return suivie.removeprefix(f"{DISTANT}/")
    return branche


def ecrire(projet: config.Projet, chaine: int = 0, attente: str | None = None, programmee: bool = False,
           maintenant: datetime | None = None) -> memoire.Passation:
    """Écrit la passation (`memory/handoff.md`), dans la langue de la
    mémoire, et la rend. `chaine` : les lots menés sans message de
    l'humain, le lot en cours compris ; la passation que l'humain fait
    reprendre porte 0. `programmee` : refusé à la borne de la chaîne ou sans
    tâche prête au prochain lot. Réécrite, elle reçoit une heure nouvelle."""
    racine = projet.racine
    if chaine < 0:
        raise PassationRefusee(trad("`--chain` compte des lots : 0 ou plus"))
    if chaine and not programmee:
        raise PassationRefusee(trad("la passation que l'humain fait reprendre porte la chaîne 0, que sa demande remet "
                                    "à zéro : `--chain` va avec `--scheduled`"))
    if programmee and chaine >= BORNE_DE_LA_CHAINE:
        raise PassationRefusee(trad("chaîne : {n} lots menés sans message de l'humain, sa borne est {borne} : ne rien "
                                    "programmer ; écrire la passation sans `--scheduled`, et le récap dit à l'humain "
                                    "de demander la reprise dans une session neuve",
                                    n=chaine, borne=BORNE_DE_LA_CHAINE))
    if not outils.a_des_commits(racine):
        raise PassationRefusee(trad("aucun commit : rien à passer"))
    branche = branche_de_travail(racine)
    if programmee and not lot_de_l_etat(racine)[2]:
        raise PassationRefusee(trad("le prochain lot n'a aucune tâche prête dans l'état (une décision revient à "
                                    "l'humain, ou rien n'est prêt) : ne rien programmer ; écrire la passation sans "
                                    "`--scheduled`, et le récap dit à l'humain de demander la reprise dans une "
                                    "session neuve"))
    quand = (maintenant or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    chemin = racine / projet.chemins.passation
    avant = memoire.lire_passation(chemin.read_text(encoding="utf-8"))[0] if chemin.is_file() else None
    if avant and avant.ecrite >= quand:
        quand = avant.ecrite + timedelta(seconds=1)
    lg = langue.du_projet(projet)
    attente = (attente or "").strip().rstrip(".") or langue.mot(langue.TEXTES, "rien", lg)
    p = memoire.Passation(quand, branche, chaine,
                          langue.mot(langue.TEXTES, "attente-passation", lg).format(attente=attente))
    outils.ecrire(chemin, memoire.texte_passation(p, lg))
    return p


def _branches_distantes(racine: Path, contient: str | None = None) -> list[str]:
    """Les branches distantes de l'origine, par leur nom court
    (`origin/main`), sans la référence symbolique `origin/HEAD` ; avec
    `contient`, celles qui portent ce commit."""
    options = ["--contains", contient] if contient else []
    sortie = outils.git(racine, "for-each-ref", *options, "--format=%(refname)%00%(symref)",
                        f"refs/remotes/{DISTANT}/", check=False)
    res = []
    for ligne in sortie.splitlines():
        nom, _, symbolique = ligne.partition("\0")
        if nom and not symbolique:
            res.append(nom.removeprefix("refs/remotes/"))
    return res


def _ancetre(racine: Path, a: str, b: str) -> bool:
    return outils.git_reussit(racine, "merge-base", "--is-ancestor", a, b)


def _retraits(racine: Path, chemin: str) -> list[tuple[str, int, str]]:
    """Les commits des branches distantes qui retirent la passation : leur
    SHA, leur date et le texte retiré, lu dans leur diff (un appel git)."""
    sortie = outils.git(racine, "log", f"--remotes={DISTANT}", "--no-merges", "--full-history", "--diff-filter=D",
                        "--no-renames", "--no-color", "--no-ext-diff", "--format=%x01%H %ct", "-p", "--", chemin,
                        check=False)
    res, sha, date, lignes, hunk = [], None, 0, [], False
    for ligne in sortie.splitlines():
        if ligne.startswith("\x01"):
            if sha:
                res.append((sha, date, "\n".join(lignes)))
            sha, date = ligne[1:].split()[0], int(ligne[1:].split()[1])
            lignes, hunk = [], False
        elif ligne.startswith("diff --git"):
            hunk = False
        elif ligne.startswith("@@"):
            hunk = True
        elif hunk and ligne.startswith("-"):
            lignes.append(ligne[1:])
    if sha:
        res.append((sha, date, "\n".join(lignes)))
    return res


def connues(projet: config.Projet) -> dict[tuple[datetime, str], Connue]:
    """Les passations que le clone sait de l'origine, sans `git fetch`, par
    leur estampille : à la tête de chaque branche distante, la branche par
    défaut comprise, et celles qu'un commit d'une branche distante a
    retirées."""
    racine, chemin = projet.racine, projet.chemins.passation
    res: dict[tuple[datetime, str], Connue] = {}
    branches = _branches_distantes(racine)
    for branche in branches:
        texte = outils.lire_a(racine, branche, chemin)
        p = memoire.lire_passation(texte)[0] if texte else None
        if p:
            res.setdefault(p.estampille, Connue(p)).tetes.append(branche)
    for sha, date, texte in (_retraits(racine, chemin) if branches else []):
        p = memoire.lire_passation(texte)[0]
        if p:
            res.setdefault(p.estampille, Connue(p)).retraits.append((sha, date))
    return res


def _derniere(toutes: dict[tuple[datetime, str], Connue]) -> Connue | None:
    """La plus récente, par son heure `écrite` : la seule qui compte."""
    return max(toutes.values(), key=lambda c: c.passation.estampille) if toutes else None


def _ecrite_par(racine: Path, rev: str, p: memoire.Passation, chemin: str) -> str | None:
    """Le dernier commit de `rev`, hors des fusions, qui a écrit cette
    estampille : celui de la passation, ou le commit de squash ou de rebase
    qui l'a portée ; `None` s'il n'y en a pas."""
    shas = outils.git(racine, "log", "--no-merges", "--full-history", "--format=%H", rev, "--", chemin,
                      check=False).split()
    for sha in shas[:LUS_AU_PLUS]:
        texte = outils.lire_a(racine, sha, chemin)
        q = memoire.lire_passation(texte)[0] if texte else None
        if q and q.estampille == p.estampille:
            return sha
    return None


def _locale(projet: config.Projet, toutes: dict[tuple[datetime, str], Connue]) -> list[str]:
    """La vérification de la session qui part, après son push : la
    passation de ce clone, commitée, poussée, et rien après elle qui ne soit
    sur l'origine. Rien à dire sans passation dans ce clone."""
    racine, chemin = projet.racine, projet.chemins.passation
    texte = outils.lire_a(racine, None, chemin)
    if texte is None:
        return []
    sales = [l[3:] for l in outils.git(racine, "status", "--porcelain", "--untracked-files=no",
                                       check=False).splitlines() if l.strip()]
    if not outils.git_reussit(racine, "ls-files", "--error-unmatch", "--", chemin):
        sales.append(chemin)
    if sales:
        return [trad("des changements ne sont pas commités ({chemins}) : les commiter, la passation en dernier, puis "
                     "pousser ; la session neuve ne repart que du dépôt", chemins=", ".join(sorted(set(sales))))]
    p = memoire.lire_passation(texte)[0]
    if p is None:
        return []  # sa forme se juge par `memoire.format`
    if p.estampille not in toutes:
        return [trad("la passation de ce clone, écrite à {heure}, n'est pas poussée : aucune branche de {distant} ne "
                     "la porte ; pousser, puis relancer `socle handoff check`", heure=p.heure, distant=DISTANT)]
    porteur = _ecrite_par(racine, "HEAD", p, chemin)
    apres = outils.git(racine, "rev-list", "HEAD", f"^{porteur}", "--not", f"--remotes={DISTANT}",
                       check=False).split() if porteur else []
    if apres:
        return [trad("la tête locale {sha} n'est pas poussée : {n} commit(s) après la passation de ce clone ne sont "
                     "sur aucune branche de {distant} ; un commit nécessaire après la passation la réécrit, puis se "
                     "pousse", sha=apres[0][:10], n=len(apres), distant=DISTANT)]
    return []


def trouver(projet: config.Projet) -> Trouvee:
    """La passation qui attend, après `git fetch`, et le verdict de sa
    garde : la plus récente que l'origine connaît ; reprise, refusée tant
    que son retrait n'est pas dans la branche par défaut ; sinon, sa garde
    sur `origin/<sa branche>`, sa tête le dernier commit qui a écrit son
    estampille, son heure `écrite`. Sa branche supprimée, la tête est le
    commit de la branche par défaut qui l'y a portée, et la garde juge
    aussi les ancêtres de celui-ci."""
    racine, chemin = projet.racine, projet.chemins.passation
    toutes = connues(projet)
    refus = _locale(projet, toutes)
    c = _derniere(toutes)
    if c is None:
        return Trouvee(None, Verdict(refus))
    p, defaut = c.passation, outils.branche_par_defaut(racine)
    ref = f"{DISTANT}/{p.branche}"
    if c.retraits:
        if defaut and any(_ancetre(racine, sha, defaut) for sha, _ in c.retraits):
            return Trouvee(None, Verdict(refus))
        sha, date = max(c.retraits, key=lambda r: r[1])
        refus.append(trad("la passation écrite à {heure} sur {ref} est déjà reprise : {branches} porte son retrait "
                          "({sha}, {quand}), qui n'est pas encore dans {defaut} : une autre session y travaille",
                          heure=p.heure, ref=ref, branches=", ".join(_branches_distantes(racine, sha)), sha=sha[:10],
                          quand=datetime.fromtimestamp(date, timezone.utc).strftime(FORMAT_HEURE),
                          defaut=defaut or trad("la branche par défaut")))
        return Trouvee(p, Verdict(refus))
    tete = _ecrite_par(racine, ref, p, chemin) if outils.rev_existe(racine, ref) else None
    ancetres = tete is None
    if tete is None and defaut:
        tete = _ecrite_par(racine, defaut, p, chemin)
    if tete is None:
        refus.append(trad("la passation écrite à {heure} sur {ref} n'a été écrite par aucun commit de {ref} ni de "
                          "{defaut} : `git fetch {distant}` d'abord", heure=p.heure, ref=ref,
                          defaut=defaut or trad("la branche par défaut"), distant=DISTANT))
        return Trouvee(p, Verdict(refus))
    verdict = juger(projet, ref, tete, p.ecrite, ancetres=ancetres)
    if refus:
        verdict = Verdict(refus + verdict.refus)
    return Trouvee(p, verdict)


# Ce qu'une session charge à son démarrage, et qu'elle ne relit pas quand
# elle se place ensuite sur la passation : ses instructions, ses skills et
# ses hooks (B-0374).
LUS_AU_DEMARRAGE = (config.INSTRUCTIONS, "CLAUDE.md", ".claude/")
# Les fichiers changés que l'alerte nomme, au plus.
NOMMES_AU_PLUS = 10


def retard(projet: config.Projet, toutes: dict[tuple[datetime, str], Connue] | None = None
           ) -> tuple[str, str, list[str]] | None:
    """La tête locale en retard sur la passation qui attend, d'après le clone
    tel qu'il est (B-0374) : la branche distante qui la porte, la tête
    locale, et les fichiers d'instructions, de skills et de hooks qui
    changent entre les deux ; `None` quand aucune n'attend, ou que la tête
    locale n'est pas un ancêtre strict de cette branche."""
    c = _derniere(connues(projet) if toutes is None else toutes)
    if c is None or c.retraits or not c.tetes:
        return None
    racine = projet.racine
    voulue = f"{DISTANT}/{c.passation.branche}"
    ref = voulue if voulue in c.tetes else sorted(c.tetes)[0]
    tete = outils.git(racine, "rev-parse", "--verify", "-q", "HEAD^{commit}", check=False).strip()
    if not tete:
        return None
    cible = outils.resoudre(racine, ref)
    if tete == cible or not _ancetre(racine, tete, cible):
        return None
    changes = [f for f in outils.fichiers_changes(racine, tete, cible)
               if f in LUS_AU_DEMARRAGE or f.startswith(tuple(p for p in LUS_AU_DEMARRAGE if p.endswith("/")))]
    return ref, tete, changes


def alerte_retard(projet: config.Projet, toutes: dict[tuple[datetime, str], Connue] | None = None) -> str | None:
    """L'alerte que l'état met en tête quand la tête locale est en retard
    sur la passation qui attend ; `None` sinon."""
    r = retard(projet, toutes)
    if r is None:
        return None
    ref, tete, changes = r
    if changes:
        liste = ", ".join(f"`{f}`" for f in changes[:NOMMES_AU_PLUS]) + (" …" if len(changes) > NOMMES_AU_PLUS
                                                                           else "")
        lus = trad("les instructions, les skills et les hooks chargés au démarrage sont ceux d'avant, et changent "
                   "dans {liste} : avant tout travail, lire ce qui change (`git diff {tete} {ref} -- {chemins}`)",
                   liste=liste, tete=tete[:10], ref=ref, chemins=" ".join(LUS_AU_DEMARRAGE))
    else:
        lus = trad("aucun fichier d'instructions, de skills ni de hooks ne change entre les deux")
    return trad("!! LA TÊTE LOCALE ({tete}) EST EN RETARD SUR {ref}, qui porte la passation en attente : la "
                "mémoire lue ici est celle d'avant ; {lus}. La reprise se place sur la référence que la garde nomme "
                "(`socle handoff check`, après `git fetch`).", tete=tete[:10], ref=ref, lus=lus)


def ligne_etat(projet: config.Projet, toutes: dict[tuple[datetime, str], Connue] | None = None) -> str | None:
    """La ligne de l'état, d'après le clone tel qu'il est : la passation qui
    attend, la plus récente que l'origine connaît, sans retrait ; `None`
    quand aucune n'attend."""
    c = _derniere(connues(projet) if toutes is None else toutes)
    if c is None or c.retraits:
        return None
    return trad("passation : en attente sur {ref}, écrite à {heure} — une demande de reprendre (« reprends ») la "
                "reprend", ref=f"{DISTANT}/{c.passation.branche}", heure=c.passation.heure)


def juger(projet: config.Projet, ref: str, tete: str, depuis: datetime | None = None,
          ancetres: bool = False) -> Verdict:
    """La garde d'une passation, dans la session neuve après `git fetch` :
    refusée si la tête de `ref` n'est plus `tete` (quelqu'un a poussé
    depuis), ou si une autre branche distante porte un commit, hors des
    fusions, daté d'après `depuis` (par défaut, la date de `tete`), qui
    touche la mémoire sans être un ancêtre de `tete` (une autre session
    travaille). Une pull request fusionnée par un commit de fusion pendant
    l'attente fait de `tete` un ancêtre de la branche par défaut : la
    session repart de celle-ci ; fusionnée par squash, son commit refuse.
    Avec `ancetres`, quand `tete` est le commit de la branche par défaut qui
    a porté la passation, ses ancêtres qui touchent la mémoire, écrits (date
    d'auteur) après `depuis`, refusent aussi : la mémoire d'une autre
    session, fusionnée avant le squash ou le rebase."""
    racine = projet.racine
    ref = ref.removeprefix("refs/remotes/")
    if not outils.rev_existe(racine, tete):
        return Verdict([trad("--head {tete} est introuvable dans ce clone : `git fetch {distant}` d'abord ; sinon, "
                             "la branche a été réécrite depuis la passation", tete=tete, distant=DISTANT)])
    tete = outils.resoudre(racine, tete)
    defaut = outils.branche_par_defaut(racine)
    fusionnee = bool(defaut) and defaut != ref and _ancetre(racine, tete, defaut)
    refus = []
    if outils.rev_existe(racine, ref):
        actuelle = outils.resoudre(racine, ref)
        if actuelle != tete:
            refus.append(trad("la tête de {ref} est {actuelle}, plus {tete} : quelqu'un a poussé sur {ref} depuis la "
                              "passation", ref=ref, actuelle=actuelle[:10], tete=tete[:10]))
    elif not fusionnee:
        refus.append(trad("{ref} n'existe plus, et {tete} n'est pas dans {defaut} : la pull request a été fusionnée "
                          "par squash, ou la branche supprimée", ref=ref, tete=tete[:10],
                          defaut=defaut or trad("la branche par défaut")))
    seuil = int(depuis.timestamp()) if depuis else int(outils.git(racine, "log", "-1", "--format=%ct", tete).strip())
    quand = datetime.fromtimestamp(seuil, timezone.utc).strftime(FORMAT_HEURE)
    memoire_ = f"{projet.chemins.memoire}/"
    for branche in _branches_distantes(racine):
        if branche == ref:
            continue
        sortie = outils.git(racine, "log", "--no-merges", "--full-history", f"--since={quand}",
                            "--format=%H%x00%ct%x00%s", branche, f"^{tete}", "--", memoire_, check=False)
        commits = [c.split("\0") for c in sortie.splitlines() if c.count("\0") == 2]
        commits = [(sha, sujet) for sha, date, sujet in commits if int(date) > seuil]
        if commits:
            refus.append(trad("{branche} porte {n} commit(s) daté(s) d'après {heure} qui touche(nt) {memoire}/ sans "
                              "être dans {tete} (le dernier : {sha} {sujet}) : une autre session travaille sur le "
                              "projet", branche=branche, n=len(commits), heure=quand, memoire=projet.chemins.memoire,
                              tete=tete[:10], sha=commits[0][0][:10], sujet=commits[0][1]))
    if ancetres:
        sortie = outils.git(racine, "log", "--no-merges", "--full-history", f"--since={quand}",
                            "--format=%H%x00%at%x00%s", tete, "--", memoire_, check=False)
        commits = [c.split("\0") for c in sortie.splitlines() if c.count("\0") == 2]
        commits = [(sha, sujet) for sha, date, sujet in commits if sha != tete and int(date) > seuil]
        if commits:
            refus.append(trad("{tete} porte parmi ses ancêtres {n} commit(s) écrit(s) après {heure} qui touche(nt) "
                              "{memoire}/ (le dernier : {sha} {sujet}) : une autre session a travaillé sur le projet "
                              "depuis la passation", tete=tete[:10], n=len(commits), heure=quand,
                              memoire=projet.chemins.memoire, sha=commits[0][0][:10], sujet=commits[0][1]))
    if refus:
        return Verdict(refus)
    place = defaut if fusionnee else ref
    return Verdict([], place, outils.resoudre(racine, place))
