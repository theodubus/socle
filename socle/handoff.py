"""La passation d'une session à la suivante (`socle handoff`) : le prompt de
la session neuve, précédé de sa garde, et le jugement de cette garde.

Le moteur ne connaît que git et la mémoire. Programmer la session suivante
revient à la plateforme de l'agent, selon le skill `socle-handoff`, qui
donne ce prompt à programmer, ou à copier : le même sert aux deux modes.

- `prompt` : refusé tant que la tête locale n'est pas poussée ; la garde y
  nomme la branche distante (`--ref`), sa tête (`--head`) et l'heure de la
  passation (`--since`), puis vient le prompt d'une session neuve, avec le
  lot que l'état donne. Pour une session programmée (`--scheduled`), les
  bornes d'une chaîne sans l'humain : deux lots menés sans message de lui,
  ou un prochain lot sans tâche prête, et rien ne se programme.
- `check` : la session neuve ne travaille pas si quelqu'un a poussé sur sa
  branche depuis la passation, ou si une autre branche distante porte un
  commit daté d'après elle qui touche la mémoire sans être un ancêtre de la
  tête passée : une autre session travaille sur le projet, puisqu'un agent
  sous le socle écrit toujours sa mémoire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from socle import config, links as liens, memory as memoire, utils as outils
from socle.messages import trad

DISTANT = "origin"
# Deux lots menés sans message de l'humain, le lot en cours compris : la
# chaîne s'arrête là, et le prompt se donne à copier.
BORNE_DE_LA_CHAINE = 2
FORMAT_HEURE = "%Y-%m-%dT%H:%M:%SZ"
# Ce qui, dans un lot, se reprend : une tâche prête, ou en cours quand la
# passation coupe le lot près d'une limite.
A_REPRENDRE = ("pret", "en-cours")


class PassationRefusee(Exception):
    """Le prompt ne s'écrit pas : la raison dit quoi faire d'abord."""


@dataclass
class Verdict:
    """Le jugement de la garde : ses raisons de refuser, ou la référence où
    la session neuve se place, et sa tête."""

    refus: list[str] = field(default_factory=list)
    place: str | None = None
    sha: str | None = None


def heure(texte: str) -> datetime:
    """Une heure ISO 8601 (`2026-11-24T10:05:00Z`), en UTC ; sans fuseau,
    elle est en UTC. `ValueError` sinon."""
    h = datetime.fromisoformat(texte.strip().replace("Z", "+00:00"))
    return h.replace(tzinfo=timezone.utc) if h.tzinfo is None else h.astimezone(timezone.utc)


def nom_du_depot(projet: config.Projet) -> str:
    """Le nom du dépôt, celui que portent les tâches programmées : le
    dernier segment de son adresse web, sinon le nom de sa racine."""
    url = liens.url_depot(projet)
    return url.rsplit("/", 1)[-1] if url else projet.racine.name


def tete_poussee(racine: Path) -> tuple[str, str]:
    """La branche distante qui porte la tête locale, et cette tête : la
    branche de travail poussée (son homonyme distante, ou celle qu'elle
    suit), ou la branche par défaut quand la pull request du lot vient
    d'être fusionnée et que la branche locale en est repartie. Refusé si la
    tête n'est sur aucune, ou qu'un fichier suivi a un changement non
    commité : la session neuve ne repart que du dépôt."""
    if not outils.a_des_commits(racine):
        raise PassationRefusee(trad("aucun commit : rien à passer"))
    if outils.git(racine, "status", "--porcelain", "--untracked-files=no", check=False).strip():
        raise PassationRefusee(trad("des changements de fichiers suivis ne sont pas commités : les commiter et les "
                                    "pousser d'abord, la session neuve ne repart que du dépôt"))
    tete = outils.resoudre(racine, "HEAD")
    branche = outils.branche_courante(racine)
    suivie = outils.git(racine, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                        check=False).strip()
    candidates = [f"{DISTANT}/{branche}" if branche else None, suivie, outils.branche_par_defaut(racine)]
    for ref in dict.fromkeys(c for c in candidates if c and c.startswith(f"{DISTANT}/")):
        if outils.rev_existe(racine, ref) and outils.resoudre(racine, ref) == tete:
            return ref, tete
    raise PassationRefusee(trad("la tête locale {sha} n'est pas poussée : pousser d'abord ; la garde nomme la tête "
                                "distante, et rien ne se pousse plus après la passation", sha=tete[:10]))


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


def prompt(projet: config.Projet, chaine: int = 0, attente: str | None = None, programmee: bool = False,
           maintenant: datetime | None = None) -> str:
    """Le prompt de la session neuve, précédé de la passation et de sa garde.
    `chaine` : les lots menés sans message de l'humain, le lot en cours
    compris ; le prompt à copier porte 0. `programmee` : pour une session
    programmée, refusé à la borne de la chaîne ou sans tâche prête au
    prochain lot, où le prompt se donne à copier."""
    racine = projet.racine
    if chaine < 0:
        raise PassationRefusee(trad("`--chain` compte des lots : 0 ou plus"))
    if chaine and not programmee:
        raise PassationRefusee(trad("le prompt à copier porte la chaîne 0, que l'humain remet à zéro en le collant : "
                                    "`--chain` va avec `--scheduled`"))
    if programmee and chaine >= BORNE_DE_LA_CHAINE:
        raise PassationRefusee(trad("chaîne : {n} lots menés sans message de l'humain, sa borne est {borne} : ne rien "
                                    "programmer, donner le prompt à copier (sans `--scheduled`)",
                                    n=chaine, borne=BORNE_DE_LA_CHAINE))
    ref, tete = tete_poussee(racine)
    lot, taches, a_reprendre = lot_de_l_etat(racine)
    if programmee and not a_reprendre:
        raise PassationRefusee(trad("le prochain lot n'a aucune tâche prête dans l'état (une décision revient à "
                                    "l'humain, ou rien n'est prêt) : ne rien programmer, donner le prompt à copier "
                                    "(sans `--scheduled`)"))
    quand = (maintenant or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(FORMAT_HEURE)
    depot = nom_du_depot(projet)
    if lot:
        texte_lot = f"{lot} ({', '.join(taches)})" if taches else lot
    else:
        texte_lot = trad("aucun dans l'état, à former")
    attente = (attente or "").strip().rstrip(".") or trad("rien")
    return "\n".join([
        trad("Passation — {depot}, à {heure}.", depot=depot, heure=quand),
        trad("Avant tout : git fetch {distant}, puis", distant=DISTANT),
        f"python3 .socle/socle handoff check --ref {ref} --head {tete} --since {quand}",
        trad("S'il refuse, ne fais rien d'autre que le dire ; s'il accepte, place-toi où il le dit, et la pull "
             "request ouverte de cette branche devient la tienne."),
        trad("Chaîne : {n} lot(s) mené(s) sans message de l'humain.", n=chaine),
        trad("Reprends le travail de ce dépôt, en session neuve."),
        trad("Puis : lis l'état que le démarrage injecte, et ce qu'une ligne « !! coupé » y dit manquer ; puis le "
             "chantier actif, et applique-les."),
        trad("Le lot : {lot}, selon le skill socle-batch.", lot=texte_lot),
        trad("Ce qui attend : {attente}.", attente=attente),
    ])


def _branches_distantes(racine: Path) -> list[str]:
    """Les branches distantes de l'origine, par leur nom court
    (`origin/main`), sans la référence symbolique `origin/HEAD`."""
    sortie = outils.git(racine, "for-each-ref", "--format=%(refname)%00%(symref)", f"refs/remotes/{DISTANT}/",
                        check=False)
    res = []
    for ligne in sortie.splitlines():
        nom, _, symbolique = ligne.partition("\0")
        if nom and not symbolique:
            res.append(nom.removeprefix("refs/remotes/"))
    return res


def _ancetre(racine: Path, a: str, b: str) -> bool:
    return outils.git_reussit(racine, "merge-base", "--is-ancestor", a, b)


def juger(projet: config.Projet, ref: str, tete: str, depuis: datetime | None = None) -> Verdict:
    """La garde d'une passation, dans la session neuve après `git fetch` :
    refusée si la tête de `ref` n'est plus `tete` (quelqu'un a poussé
    depuis), ou si une autre branche distante porte un commit, hors des
    fusions, daté d'après `depuis` (par défaut, la date de `tete`), qui
    touche la mémoire sans être un ancêtre de `tete` (une autre session
    travaille). Une pull request fusionnée par un commit de fusion pendant
    l'attente fait de `tete` un ancêtre de la branche par défaut : la
    session repart de celle-ci ; fusionnée par squash, son commit refuse."""
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
    for branche in _branches_distantes(racine):
        if branche == ref:
            continue
        sortie = outils.git(racine, "log", "--no-merges", "--full-history", f"--since={quand}",
                            "--format=%H%x00%ct%x00%s", branche, f"^{tete}", "--", f"{projet.chemins.memoire}/",
                            check=False)
        commits = [c.split("\0") for c in sortie.splitlines() if c.count("\0") == 2]
        commits = [(sha, sujet) for sha, date, sujet in commits if int(date) > seuil]
        if commits:
            refus.append(trad("{branche} porte {n} commit(s) daté(s) d'après {heure} qui touche(nt) {memoire}/ sans "
                              "être dans {tete} (le dernier : {sha} {sujet}) : une autre session travaille sur le "
                              "projet", branche=branche, n=len(commits), heure=quand, memoire=projet.chemins.memoire,
                              tete=tete[:10], sha=commits[0][0][:10], sujet=commits[0][1]))
    if refus:
        return Verdict(refus)
    place = defaut if fusionnee else ref
    return Verdict([], place, outils.resoudre(racine, place))
