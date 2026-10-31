"""Les skills : des procédures rangées chacune dans un dossier, que l'agent
charge à la demande sur leur description, au lieu de les relire à chaque
session (`.claude/skills/<nom>/SKILL.md` sous Claude Code). L'installeur pose
ceux du socle (`socle-*`) ; l'agent écrit ceux du projet (ADR-0034).

- `skills.contrat`  : un skill a un en-tête qui le nomme comme son dossier et
                      une description qui dit ce qu'il fait et quand s'en
                      servir : sans elle, l'agent ne le charge jamais ; le
                      préfixe `socle-` reste aux skills de l'installeur ;
- `skills.commandes` : une commande qu'un skill donne à lancer, dans un bloc
                      de code, est jugée comme le hook de l'agent la jugerait :
                      un skill ne fait pas lancer ce que le hook refuse.

Leur taille a son plafond dans les budgets des garde-fous, comme les couches
de la mémoire.
"""

from __future__ import annotations

import re

from socle import hooks
from socle.context import controle
from socle.messages import trad
from socle.templates import DOSSIER as DOSSIER_GABARITS

CHEMINS = ["**/skills/*/SKILL.md"]
# Les skills que pose l'installeur, un dossier par skill parmi ses gabarits :
# le préfixe leur est réservé.
DU_SOCLE = tuple(sorted(p.name for p in (DOSSIER_GABARITS / "skills").iterdir() if p.is_dir()))
PREFIXE_SOCLE = "socle-"
DESCRIPTION_MIN = 12  # mots
# Ce qui dit quand s'en servir, dans les deux langues de la mémoire.
QUAND = re.compile(r"\b(?:quand|lorsqu|à utiliser|avant d|après|si|when|use|before|after|if)\b", re.I)
BLOC = re.compile(r"^(```|~~~)[ \t]*([\w-]*)[^\n]*\n(.*?)^\1[ \t]*$", re.M | re.S)
SHELL = {"", "sh", "bash", "shell", "zsh", "console", "terminal"}
# Un argument à remplir (`<nom>`, `<texte exact>`) n'est pas une redirection.
A_REMPLIR = re.compile(r"<[^<>\n]+>")


def skills(ctx) -> dict[str, str]:
    return ctx.textes(CHEMINS)


def entete(texte: str) -> dict[str, str] | None:
    """L'en-tête d'un skill, entre ses deux lignes `---` : ses champs d'une
    ligne, et ceux en bloc (`>` ou `|`) mis bout à bout ; rien sans en-tête."""
    m = re.match(r"---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", texte, re.S)
    if not m:
        return None
    champs: dict[str, str] = {}
    cle = None
    for ligne in m.group(1).splitlines():
        c = re.match(r"([A-Za-z][\w-]*)\s*:\s*(.*)$", ligne)
        if c and not ligne[:1].isspace():
            cle, valeur = c.group(1), c.group(2).strip()
            champs[cle] = "" if valeur in (">", "|", ">-", "|-") else valeur.strip("\"'")
        elif cle and ligne.strip():
            champs[cle] = (champs[cle] + " " + ligne.strip()).strip()
    return champs


def commandes(texte: str) -> list[tuple[int, str]]:
    """Les blocs de code du shell d'un skill, avec leur ligne : ce qu'il donne
    à lancer. Une commande citée dans le texte n'en est pas une : c'est ainsi
    qu'un skill dit ce qu'il ne faut pas lancer."""
    res = []
    for m in BLOC.finditer(texte):
        if m.group(2).lower() not in SHELL:
            continue
        lignes = [re.sub(r"^\$\s+", "", l) for l in m.group(3).splitlines()]
        res.append((texte.count("\n", 0, m.start()) + 1, A_REMPLIR.sub("ARG", "\n".join(lignes))))
    return res


@controle("skills.contrat")
def contrat(ctx, r):
    """Un skill se nomme comme son dossier et dit, dans sa description, ce
    qu'il fait et quand s'en servir ; `socle-` reste aux skills du socle."""
    for chemin, texte in sorted(skills(ctx).items()):
        dossier = chemin.rsplit("/", 2)[-2]
        champs = entete(texte)
        if champs is None:
            r.erreur("skills.contrat", trad("skill sans en-tête : le fichier commence par `---`, `name: {dossier}`, "
                                            "`description: <ce qu'il fait, et quand s'en servir>`, `---`",
                                            dossier=dossier), chemin, 1)
            continue
        if champs.get("name") != dossier:
            r.erreur("skills.contrat", trad("le skill se nomme « {nom} » : son nom est celui de son dossier, "
                                            "« {dossier} »", nom=champs.get("name", ""), dossier=dossier), chemin, 1)
        description = champs.get("description", "")
        if len(re.findall(r"[^\W\d_]{2,}", description)) < DESCRIPTION_MIN or not QUAND.search(description):
            r.erreur("skills.contrat", trad("description trop maigre : ce que fait le skill et quand s'en servir, "
                                            "en au moins {n} mots ; l'agent ne charge un skill que sur elle",
                                            n=DESCRIPTION_MIN), chemin, 1)
        if dossier.startswith(PREFIXE_SOCLE) and dossier not in DU_SOCLE:
            r.erreur("skills.contrat", trad("le préfixe `{prefixe}` est réservé aux skills que pose l'installeur : "
                                            "nommer autrement un skill du projet", prefixe=PREFIXE_SOCLE), chemin, 1)


@controle("skills.commandes")
def commandes_lancees(ctx, r):
    """Une commande qu'un skill donne à lancer est jugée comme le hook de
    l'agent la jugerait : un skill ne fait pas lancer ce que le hook refuse."""
    for chemin, texte in sorted(skills(ctx).items()):
        for ligne, bloc in commandes(texte):
            raison = hooks.refus_bash(ctx.projet, bloc)
            if raison:
                r.erreur("skills.commandes", trad("le skill donne à lancer une commande que le hook de l'agent "
                                                  "refuse — {raison} ; une commande à ne pas lancer se cite dans "
                                                  "le texte, pas dans un bloc de code", raison=raison[:300]),
                         chemin, ligne)

