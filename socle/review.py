"""Le dossier de la revue adversariale d'un lot (ADR-0042).

Avant le push qui livre un lot qui change du code, une spécification ou un
test, l'agent le fait relire par un relecteur qui n'a pas son contexte, et
qui cherche à le prendre en défaut. Le moteur ne connaît aucun agent : il
ne lance pas le relecteur, il prépare ce que celui-ci reçoit, et rien
d'autre. La procédure vit côté agent, dans le skill `socle-review`.

La relecture à froid d'une demande (ADR-0046) procède de même : un lecteur
qui n'a que son texte, dans le rôle de l'humain qui revient sur le projet
après des semaines ; le skill `socle-request` dit quand.
"""

from __future__ import annotations

from socle import config, memory as memoire, utils as outils
from socle.messages import trad

# Au-delà, le diff se tronque, et le dossier le dit : un relecteur qui reçoit
# un diff énorme le survole.
PLAFOND_DIFF = 60_000


def base_du_lot(racine) -> str | None:
    """Ce que le lot change se mesure depuis la branche distante de la
    branche courante, ce qu'elle n'a pas encore poussé ; sans branche
    distante, depuis la branche par défaut."""
    amont = outils.git(racine, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                       check=False).strip()
    return amont or outils.branche_par_defaut(racine)


def _diff(projet: config.Projet, base: str) -> tuple[str, list[str]]:
    """Le diff du lot contre `base`, l'arbre compris, la mémoire mise à part :
    elle se donne par ses sujets, plus bas."""
    exclure = f":(exclude){projet.chemins.memoire}"
    diff = outils.git(projet.racine, "diff", base, "--", ".", exclure, check=False)
    fichiers = outils.git(projet.racine, "diff", "--name-only", base, "--", ".", exclure, check=False).split()
    return diff, fichiers


def sujets_fermes(projet: config.Projet, base: str) -> list:
    """Les sujets du backlog que le lot touche et qui sont clos : ce qu'il
    prétend avoir fait, que le relecteur confronte au code."""
    touches = set(outils.git(projet.racine, "diff", "--name-only", base, "--", projet.chemins.backlog,
                             check=False).split())
    mem = memoire.Memoire.charger(projet.racine)
    return [e for e in mem.entrees("B") if e.fichier in touches and e.statut in memoire.BACKLOG_CLOS
            and not memoire.est_prive(e.fichier)]


def decisions_citees(projet: config.Projet, sujets: list) -> list:
    """Les décisions et les demandes que ces sujets citent, en entier."""
    mem = memoire.Memoire.charger(projet.racine)
    vus, res = set(), []
    for s in sujets:
        for ident, _ in memoire.mentions(s.texte):
            if ident in vus or not ident.startswith(("ADR-", "D-")):
                continue
            vus.add(ident)
            e = mem.entree(ident)
            if e is not None and not memoire.est_prive(e.fichier):
                res.append(e)
    return res


def dossier_demande(projet: config.Projet, ident: str) -> str | None:
    """Ce que reçoit le lecteur de la relecture à froid d'une demande
    (ADR-0046) : la consigne, puis le texte de la demande, rien d'autre.
    `None` si aucune demande ne porte cet identifiant."""
    from socle import requests as demandes

    trouvees = [d for d in demandes.toutes(projet.racine) if d.entree is not None and d.entree.id == ident]
    if not trouvees:
        return None
    consigne = trad(
        "Tu es l'humain à qui cette demande s'adresse. Tu n'as pas ouvert ce projet depuis trois semaines : tu ne "
        "te souviens ni de ce qu'il fait en détail, ni du travail en cours, ni de ce que tu as décidé avant. Tu "
        "n'as que le texte ci-dessous : n'ouvre aucun lien, ne lis aucun fichier, ne cherche rien. Lis la "
        "demande, puis rends, sans rien modifier nulle part :\n\n"
        "1. Le projet et le but du travail en cours, en tes mots, tels que la demande te les apprend ; « je ne "
        "sais pas » pour ce qu'elle ne dit pas.\n"
        "2. La décision qu'on te demande, et ce que change chacune des réponses possibles.\n"
        "3. Chaque mot, nom, sigle ou renvoi que le texte emploie sans te l'expliquer, avec la phrase où il "
        "apparaît.\n"
        "4. Ce qu'il te manquerait pour décider sans aller chercher ailleurs.\n\n"
        "Ne juge pas si la décision est bonne : seulement si le texte seul te permet de la prendre.")
    return "\n".join([trad("# Relecture à froid d'une demande"), "", consigne, "", trad("## La demande"), "",
                      trouvees[0].texte.strip(), ""])


def dossier(projet: config.Projet, base: str | None = None, plafond: int = PLAFOND_DIFF) -> str:
    """Ce que reçoit le relecteur, en plus du dépôt qu'il peut lire : la
    consigne, le diff du lot, les sujets qu'il ferme et les décisions
    qu'ils citent."""
    base = base or base_du_lot(projet.racine)
    lignes = [trad("# Revue adversariale d'un lot"), "", trad(
        "Tu relis le lot de travail d'un autre agent, sans sa conversation ni son raisonnement : tu as ce dossier, et tu peux lire le dépôt pour vérifier un constat, mais tu ne "
        "modifies rien. Pour éprouver une commande (l'installeur, un script), crée d'abord un dossier temporaire "
        "hors du dépôt (`mktemp -d`), et n'écris que là : chaque commande qui écrit y vise par son chemin absolu, "
        "jamais par le dossier courant, écrit en toutes lettres tel que `mktemp -d` l'a rendu, jamais par une "
        "variable, qui ne survit pas d'un appel à l'autre. Ton rôle est de le prendre en défaut. Cherche ce qui casse (un cas limite, une erreur "
        "de logique, une régression), ce qu'aucun test ne prouve (une branche du code, un message, un cas que "
        "rien n'exerce), et ce qui contredit un sujet, un critère « Fait quand » ou une décision cités plus "
        "bas. Ne juge ni le style, ni ce que les contrôles automatiques jugent déjà : la forme de la mémoire, "
        "les liens, la présence des tests. Rends des constats numérotés, chacun avec son fichier et sa ligne, "
        "ce qui casse et comment le vérifier ; ou « aucun constat »."), ""]
    if not base:
        lignes.append(trad("(aucune base connue : ni branche distante, ni branche par défaut ; rien à relire)"))
        return "\n".join(lignes) + "\n"
    diff, fichiers = _diff(projet, base)
    lignes += [trad("## Le diff du lot ({n} fichier(s), depuis {base})", n=len(fichiers), base=base), ""]
    if not diff.strip():
        lignes.append(trad("(aucun changement hors de la mémoire : rien à relire)"))
    else:
        montre = diff.encode("utf-8")[:plafond].decode("utf-8", errors="ignore")
        lignes += ["```diff", montre.rstrip("\n"), "```"]
        if len(montre) < len(diff):
            lignes.append(trad("(diff tronqué : {n} caractère(s) de plus non montrés ; `git diff {base}` les "
                               "donne)", n=len(diff) - len(montre), base=base))
    sujets = sujets_fermes(projet, base)
    if sujets:
        lignes += ["", trad("## Les sujets que le lot ferme"), ""]
        for s in sujets:
            lignes += [s.texte.strip(), ""]
    decisions = decisions_citees(projet, sujets)
    if decisions:
        lignes += ["", trad("## Les décisions et les demandes qu'ils citent"), ""]
        for e in decisions:
            lignes += [e.texte.strip(), ""]
    return "\n".join(lignes).rstrip() + "\n"
