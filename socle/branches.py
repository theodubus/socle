"""Les branches de l'agent que l'agent supprime lui-même (`socle
prune-branches`, ADR-0114).

L'état calcule les branches distantes que la branche par défaut, ou la
branche de travail poussée, contient en entier (`human`). Parmi elles, celles
de l'agent, dont le dernier commit porte l'un des motifs de `[agents]
markers` de la politique, se suppriment sans geste de l'humain : la commande
vérifie sur l'origine, au moment même, que chacune y est encore à la tête
que le fetch connaît et que sa branche de garde la contient, puis la
supprime sous bail (`--force-with-lease`), qui échoue si elle a bougé entre
la vérification et le push. Les autres restent à l'humain, comme avant.

La suppression vaut par défaut ; `prune_branches = false`, dans
`[irreversible]` de la politique, la coupe. Un refus de l'origine (un proxy,
des droits, une règle de protection) se garde dans le dossier local du socle :
la branche revient à l'humain tant qu'un fetch ne la montre pas changée.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from socle import config, utils as outils
from socle.messages import trad

DISTANT = "origin"
# Le délai de chaque question que la commande pose à l'origine : plus long
# que celui de l'état, qui ne doit pas retarder le démarrage.
DELAI = 60
COMMANDE = "python3 .socle/socle prune-branches"


class SuppressionRefusee(RuntimeError):
    """La commande ne peut rien supprimer : coupée par la politique, ou
    l'origine injoignable."""


def active(projet: config.Projet) -> bool:
    """La suppression par l'agent vaut par défaut ; `prune_branches = false`,
    dans `[irreversible]` de la politique, la coupe. Toute autre valeur
    qu'un vrai booléen la coupe aussi : dans le doute, la branche reste à
    l'humain."""
    return projet.pol("irreversible", "prune_branches", defaut=True) is True


def de_l_agent(projet: config.Projet, sha: str) -> bool:
    """Le commit `sha` porte-t-il la marque d'un agent (`[agents] markers`) ?
    Un commit de fusion fait par GitHub, ou un commit de l'humain, ne la
    porte pas."""
    from socle.checks_ratchet import est_agent

    message = outils.git(projet.racine, "log", "-1", "--format=%B", sha, "--", check=False)
    return bool(message.strip()) and est_agent(projet, message)


def tete_connue(projet: config.Projet, nom: str) -> str:
    """La tête de la branche distante `nom` selon le dernier fetch, ou ``."""
    return outils.git(projet.racine, "rev-parse", "--verify", "--quiet", f"refs/remotes/{DISTANT}/{nom}^{{commit}}",
                      check=False).strip()


def tetes_de_l_origine(projet: config.Projet, delai: float = DELAI) -> dict[str, str] | None:
    """Les branches que l'origine a vraiment, avec leur tête (`git ls-remote
    --heads origin`) ; `None` sans sa réponse."""
    from socle import human as humain

    return humain.tetes_de_l_origine(projet, delai)


# --------------------------------------------------------------------------
# Les refus de l'origine, gardés dans le dossier local du socle
# --------------------------------------------------------------------------


def chemin_des_refus(racine: Path) -> Path:
    """Les refus de l'origine, à côté de la trace des hooks, dans le
    répertoire git commun que partagent les worktrees du clone."""
    return config.chemin_trace(racine).with_name("prune-refused.json")


def refus(racine: Path) -> dict[str, dict[str, str]]:
    """Les refus gardés : pour chaque branche, la tête refusée (`sha`), la
    raison et l'heure."""
    try:
        donnees = json.loads(chemin_des_refus(racine).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(donnees, dict):
        return {}
    return {k: v for k, v in donnees.items()
            if isinstance(k, str) and isinstance(v, dict) and isinstance(v.get("sha"), str)}


def _garder_refus(racine: Path, refuses: dict[str, dict[str, str]]) -> None:
    try:
        p = chemin_des_refus(racine)
        p.parent.mkdir(parents=True, exist_ok=True)
        provisoire = p.with_name(f"{p.name}.{os.getpid()}")
        provisoire.write_text(json.dumps(refuses, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                              encoding="utf-8")
        os.replace(provisoire, p)
    except OSError:
        pass  # sans repère, la commande retentera : l'origine refusera de nouveau, sans rien perdre


def refus_actuel(projet: config.Projet, nom: str, tete: str | None = None) -> dict[str, str] | None:
    """Le refus gardé pour `nom`, s'il vaut encore : à la tête que le dernier
    fetch connaît. Une branche qui a changé depuis se retente."""
    r = refus(projet.racine).get(nom)
    tete = tete_connue(projet, nom) if tete is None else tete
    return r if r and tete and r.get("sha") == tete else None


# --------------------------------------------------------------------------
# Ce que l'état en dit
# --------------------------------------------------------------------------


def pour_l_agent(projet: config.Projet, noms: list[str]) -> list[str]:
    """Parmi les branches distantes `noms`, que l'état donnerait à l'humain
    à supprimer, celles que l'agent supprime lui-même : la suppression
    active, leur dernier commit marqué d'un agent, et aucun refus de
    l'origine à leur tête actuelle."""
    if not noms or not active(projet):
        return []
    res = []
    for nom in noms:
        tete = tete_connue(projet, nom)
        if tete and de_l_agent(projet, tete) and not refus_actuel(projet, nom, tete):
            res.append(nom)
    return sorted(set(res))


# --------------------------------------------------------------------------
# La commande
# --------------------------------------------------------------------------


@dataclass
class Bilan:
    supprimees: list[tuple[str, str]] = field(default_factory=list)  # (branche, tête)
    a_supprimer: list[tuple[str, str]] = field(default_factory=list)  # avec `--dry-run`
    laissees: list[tuple[str, str]] = field(default_factory=list)  # (branche, raison)
    refusees: list[tuple[str, str]] = field(default_factory=list)  # (branche, raison de l'origine)


def candidates(projet: config.Projet) -> list[tuple[str, str]]:
    """(branche, sa garde) : les branches distantes que l'état calcule à
    supprimer, chacune avec la branche distante qui la contient, la branche
    par défaut ou la branche de travail poussée. Ni la branche par défaut,
    ni la branche courante, ni une branche que `[human] keep_branches`
    garde."""
    from socle import human as humain

    defaut = outils.branche_par_defaut(projet.racine) or ""
    res = {b: defaut for b in humain.branches_a_supprimer(projet)}
    for b, poussee in humain.branches_contenues_dans_le_travail(projet):
        res.setdefault(b, poussee)
    return sorted(res.items())


def _fetch(projet: config.Projet) -> None:
    """Un fetch sans `--prune` : élaguer la référence d'une branche que
    l'origine n'a plus perdrait un commit qu'elle seule garde, que la
    mémoire cite peut-être, et que l'état dit alors d'étiqueter d'abord
    (ADR-0114). La question à l'origine (`ls-remote`) écarte déjà ces
    branches."""
    try:
        r = subprocess.run(["git", "fetch", "--quiet", DISTANT], cwd=projet.racine, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                           timeout=DELAI * 5, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except (subprocess.TimeoutExpired, OSError) as e:
        raise SuppressionRefusee(trad("`git fetch origin` n'a pas abouti ({erreur}) : rien n'est supprimé",
                                      erreur=type(e).__name__))
    if r.returncode != 0:
        raise SuppressionRefusee(trad("`git fetch origin` a échoué ({erreur}) : rien n'est supprimé",
                                      erreur=(r.stderr or r.stdout).strip()[-300:]))


def _supprimer(projet: config.Projet, nom: str, tete: str) -> tuple[bool, str]:
    """Le push de suppression, sous le bail de la tête vérifiée : il échoue
    si la branche a bougé sur l'origine depuis. (réussi, sortie de git)."""
    try:
        r = subprocess.run(["git", "push", "--porcelain", f"--force-with-lease=refs/heads/{nom}:{tete}", DISTANT,
                            f":refs/heads/{nom}"], cwd=projet.racine, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=DELAI * 5,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, type(e).__name__
    sortie = "\n".join(x.strip() for x in (r.stderr, r.stdout) if x.strip())
    return r.returncode == 0, sortie


# Les lignes de la sortie de git qui disent pourquoi un push a échoué.
LIGNE_D_ERREUR = re.compile(r"^(?:error|fatal|remote):|\[(?:remote )?rejected\]")


def raison_du_refus(sortie: str) -> str:
    """La raison d'un refus, lisible : les lignes d'erreur de git, sans le
    bruit qui les entoure (une négociation, `Done`) ; toute la sortie, sur
    une ligne, si aucune ne l'est. 300 caractères au plus."""
    lignes = [" ".join(l.split()) for l in sortie.splitlines() if LIGNE_D_ERREUR.search(l.strip())]
    return (" ; ".join(lignes) or " ".join(sortie.split()))[-300:]


def _contenue(projet: config.Projet, tete: str, garde: str | None) -> bool:
    return bool(garde) and outils.rev_existe(projet.racine, garde) and outils.git_reussit(
        projet.racine, "merge-base", "--is-ancestor", tete, garde)


def elaguer(projet: config.Projet, essai: bool = False) -> Bilan:
    """Supprime sur l'origine les branches de l'agent déjà contenues
    ailleurs, après les avoir vérifiées sur elle au moment même ; avec
    `essai`, dit seulement ce qu'elle supprimerait."""
    if not active(projet):
        raise SuppressionRefusee(trad(
            "la politique coupe la suppression des branches par l'agent (`prune_branches = false`, section "
            "`[irreversible]`) : les branches à supprimer reviennent à l'humain, que l'état les lui donne"))
    if not outils.branche_par_defaut(projet.racine):
        raise SuppressionRefusee(trad("ce clone ne connaît pas la branche par défaut de l'origine : rien n'est "
                                      "supprimé"))
    _fetch(projet)
    tetes = tetes_de_l_origine(projet)
    if tetes is None:
        raise SuppressionRefusee(trad("l'origine ne dit pas ses branches (`git ls-remote --heads origin`) : rien "
                                      "n'est supprimé"))
    bilan = Bilan()
    refuses = refus(projet.racine)
    change = False
    for nom, garde in candidates(projet):
        tete = tete_connue(projet, nom)
        if nom not in tetes:
            # L'origine ne l'a plus : rien à supprimer, et sa référence
            # locale reste, que l'état juge (un commit cité qu'elle seule
            # garde se dit à étiqueter).
            continue
        if not tete or tetes[nom] != tete:
            bilan.laissees.append((nom, trad("l'origine ne l'a plus à la tête que le fetch connaît")))
            continue
        if not de_l_agent(projet, tete):
            bilan.laissees.append((nom, trad("son dernier commit ne porte pas la marque d'un agent : elle revient "
                                             "à l'humain")))
            continue
        ancien = refus_actuel(projet, nom, tete)
        if ancien:
            bilan.laissees.append((nom, trad("l'origine a refusé de la supprimer ({raison}) : elle revient à "
                                             "l'humain, tant qu'un fetch ne la montre pas changée",
                                             raison=ancien.get("raison", ""))))
            continue
        nom_garde = garde.removeprefix(f"{DISTANT}/")
        if not _contenue(projet, tete, tetes.get(nom_garde)):
            bilan.laissees.append((nom, trad("`{garde}` ne la contient plus sur l'origine", garde=garde)))
            continue
        if essai:
            bilan.a_supprimer.append((nom, tete))
            continue
        reussi, sortie = _supprimer(projet, nom, tete)
        if reussi:
            bilan.supprimees.append((nom, tete))
            change = refuses.pop(nom, None) is not None or change
        elif "stale info" in sortie or "(stale" in sortie:
            bilan.laissees.append((nom, trad("elle a bougé sur l'origine depuis la vérification : laissée")))
        else:
            raison = raison_du_refus(sortie) or trad("sans raison dite")
            bilan.refusees.append((nom, raison))
            refuses[nom] = {"sha": tete, "raison": raison, "heure": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            change = True
    if change:
        _garder_refus(projet.racine, refuses)
    return bilan


def lignes(bilan: Bilan, essai: bool = False) -> list[str]:
    """Ce que la commande imprime : chaque branche supprimée avec la commande
    qui la recrée, chaque refus avec sa raison."""
    res = []
    for nom, tete in bilan.a_supprimer:
        res.append(trad("à supprimer : `{branche}` ({sha})", branche=nom, sha=tete[:10]))
    for nom, tete in bilan.supprimees:
        res.append(trad("supprimée : `{branche}` ({sha}) — la recréer : `git push origin {tete}:refs/heads/{branche}`",
                        branche=nom, sha=tete[:10], tete=tete))
    for nom, raison in bilan.refusees:
        res.append(trad("refusée par l'origine : `{branche}` — {raison} ; elle revient à l'humain", branche=nom,
                        raison=raison))
    for nom, raison in bilan.laissees:
        res.append(trad("laissée : `{branche}` — {raison}", branche=nom, raison=raison))
    if not res:
        res.append(trad("aucune branche de l'agent à supprimer"))
    elif essai:
        res.append(trad("(--dry-run : rien n'est supprimé)"))
    return res
