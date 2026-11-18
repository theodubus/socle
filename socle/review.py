"""Le dossier de la revue adversariale d'un lot (ADR-0042).

Avant le push qui livre un lot qui change du code, une spécification ou un
test, l'agent le fait relire par un relecteur qui n'a pas son contexte, et
qui cherche à le prendre en défaut. Le moteur ne connaît aucun agent : il
ne lance pas le relecteur, il prépare ce que celui-ci reçoit, et rien
d'autre. La procédure vit côté agent, dans le skill `socle-review`.

La relecture à froid d'une demande (ADR-0046) procède de même : un lecteur
qui n'a que son texte, dans le rôle de l'humain qui revient sur le projet
après des semaines ; le skill `socle-request` dit quand.

Un lot en cours garde l'historique de ses passes dans sa section
« Revues » (ADR-0084) : `socle review` y écrit chaque passe, refuse la
suivante tant que la précédente n'a pas son recul, refuse « continuer »
après deux passes de suite où une même cause revient, et toute passe tant
que la demande d'un arrêt attend sa réponse.
"""

from __future__ import annotations

import re
from datetime import date

from socle import config, language as langue, memory as memoire, utils as outils
from socle.messages import a_traduire, trad

# Au-delà, le diff se tronque, et le dossier le dit : un relecteur qui reçoit
# un diff énorme le survole.
PLAFOND_DIFF = 60_000


def _amont(racine) -> str:
    """La branche distante de la branche courante, `""` sans elle."""
    return outils.git(racine, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                      check=False).strip()


def base_du_lot(racine) -> str | None:
    """Ce que le lot change se mesure depuis la branche distante de la
    branche courante, ce qu'elle n'a pas encore poussé ; sans branche
    distante, depuis la branche par défaut."""
    return _amont(racine) or outils.branche_par_defaut(racine)


class ReferenceRefusee(ValueError):
    """Une base ou un `--since` qui ne mesure pas le lot (ADR-0081) : le
    dossier ne se fait pas, au lieu d'un dossier vide ou étranger."""


class PasseRefusee(ValueError):
    """Une passe de revue que l'historique du lot refuse (ADR-0084) : la
    précédente sans son recul, un « continuer » après deux passes où une
    même cause revient, un lot arrêté dont la demande attend sa réponse ;
    ou un lot qu'on ne sait pas désigner. Rien ne s'écrit ni ne se relit."""


def debut_du_lot(racine, base: str) -> str | None:
    """Le commit d'où se mesure le lot : l'ancêtre commun de `base` et de
    HEAD (ADR-0081). Une base qui a avancé sans la branche n'apporte ainsi
    au lot ni ses changements ni ses sujets. `None` sans ancêtre commun."""
    return outils.git(racine, "merge-base", base, "HEAD", check=False).strip() or None


def _debut(racine, base: str) -> str:
    return debut_du_lot(racine, base) or base


def _hors_memoire(projet: config.Projet) -> list[str]:
    return ["--", ".", f":(exclude){projet.chemins.memoire}"]


def _commits_hors_memoire(projet: config.Projet, depuis: str, jusqua: str) -> int:
    """Les commits de `depuis..jusqua` qui changent autre chose que la mémoire."""
    sortie = outils.git(projet.racine, "rev-list", "--count", f"{depuis}..{jusqua}", *_hors_memoire(projet),
                        check=False).strip()
    return int(sortie) if sortie.isdigit() else 0


def refus_des_references(projet: config.Projet, base: str | None, depuis: str | None) -> str | None:
    """Pourquoi `--base` ou `--since` ne mesurent pas le lot, `None` s'ils
    le mesurent (ADR-0081) : une référence inconnue, un `--since` qui n'est
    pas un ancêtre de HEAD."""
    for option, ref in (("--base", base), ("--since", depuis)):
        if ref and not outils.rev_existe(projet.racine, ref):
            return trad("{option} {ref} : aucune branche, étiquette ni commit de ce nom dans ce dépôt ; rien "
                        "n'est relu", option=option, ref=ref)
    if depuis and not outils.git_reussit(projet.racine, "merge-base", "--is-ancestor", depuis, "HEAD"):
        return trad("--since {ref} n'est pas un ancêtre de HEAD : une seconde revue se mesure depuis le commit relu "
                    "par la première, que la branche contient ; rien n'est relu", ref=depuis)
    return None


def contient_le_lot(projet: config.Projet, base: str, depuis: str | None = None) -> bool:
    """`base` contient déjà le lot (ADR-0075) : avec `depuis`, le commit relu
    par la première revue y est déjà ; sans, rien n'en diffère hors de la
    mémoire depuis leur ancêtre commun (ADR-0081), ni un commit, ni
    l'arbre : un commit que `base` a reçu d'ailleurs n'y change rien."""
    if depuis:
        return outils.git_reussit(projet.racine, "merge-base", "--is-ancestor", depuis, base)
    return outils.git_reussit(projet.racine, "diff", "--quiet", _debut(projet.racine, base), *_hors_memoire(projet))


def base_par_defaut(projet: config.Projet, depuis: str | None = None) -> tuple[str | None, str | None]:
    """La base du lot sans `--base`, et ce que le dossier en dit (ADR-0075,
    ADR-0081). Une branche distante qui contient déjà le lot, poussé avant
    sa revue, n'y laisse rien : il se mesure alors depuis l'ancêtre commun
    de HEAD et de la branche par défaut. Si celui-ci le contient aussi, ou
    qu'il n'y en a pas, la base reste, et la note dit pourquoi le dossier
    est vide, et quoi lancer. Une branche distante qui porte déjà des
    commits du lot, ou d'un lot d'avant, le dit aussi."""
    racine = projet.racine
    base = base_du_lot(racine)
    amont = _amont(racine)
    if not base or base != amont:
        return base, None
    defaut = outils.branche_par_defaut(racine) or base
    devinee = outils.branche_par_defaut_devinee(racine)
    commun = None if devinee else outils.base_de_travail(racine)
    seconde = f" --since {depuis}" if depuis else ""
    # Une branche distante restée en arrière de la branche par défaut, que
    # la branche a reprise depuis son dernier push (une fusion par
    # écrasement, son image locale gardée) : son ancêtre commun avec HEAD
    # précède celui de la branche par défaut, et ramènerait le lot fusionné.
    debut_amont = debut_du_lot(racine, base)
    if commun and debut_amont and debut_amont != commun and outils.git_reussit(
            racine, "merge-base", "--is-ancestor", debut_amont, commun):
        return commun, trad("(la branche distante {amont} est restée en arrière de {defaut}, que la branche a reprise "
                            "depuis son dernier push, après une fusion par écrasement peut-être : le lot se mesure "
                            "depuis {commun}, l'ancêtre commun de HEAD et de {defaut} ; s'il commence plus tard, "
                            "`socle review --base <le commit d'avant le lot>{seconde}`)",
                            amont=base, defaut=defaut, commun=commun, seconde=seconde)
    if not contient_le_lot(projet, base, depuis):
        n = _commits_hors_memoire(projet, commun, _debut(racine, base)) if commun else 0
        if not n:
            return base, None
        return base, trad("(la branche distante {amont} porte déjà {n} commit(s) hors de la mémoire depuis {commun}, "
                          "l'ancêtre commun de HEAD et de {defaut}, que ce dossier ne montre pas : si le lot en "
                          "comprend, `socle review --base <le commit d'avant le lot>{seconde}`)",
                          amont=base, n=n, commun=commun, defaut=defaut, seconde=seconde)
    if devinee:
        return base, trad("(la branche distante {amont} contient déjà le lot, et ce clone ne connaît pas la branche "
                          "par défaut : ni `origin/HEAD`, ni `main`, ni `master`. Un lot déjà poussé se relit depuis "
                          "le commit d'avant lui : `socle review --base <ce commit>{seconde}`)",
                          amont=base, seconde=seconde)
    if not commun:
        return base, trad("(la branche distante {amont} contient déjà le lot, et HEAD n'a pas d'ancêtre commun avec la "
                          "branche par défaut {defaut} dans ce clone, superficiel peut-être (`git fetch --unshallow`). "
                          "Un lot déjà poussé se relit depuis le commit d'avant lui : `socle review --base <ce "
                          "commit>{seconde}`)", amont=base, defaut=defaut, seconde=seconde)
    if not contient_le_lot(projet, commun, depuis):
        return commun, trad("(la branche distante {amont} contient déjà le lot : il se mesure depuis {commun}, "
                            "l'ancêtre commun de HEAD et de {defaut}, sur {n} commit(s) hors de la mémoire ; s'il "
                            "commence plus tard, `socle review --base <le commit d'avant le lot>{seconde}`)",
                            amont=base, commun=commun, defaut=defaut, seconde=seconde,
                            n=_commits_hors_memoire(projet, commun, "HEAD"))
    return base, trad("(la branche distante {amont} contient déjà le lot, et la branche par défaut {defaut} aussi : "
                      "rien à relire depuis elles. Un lot déjà poussé se relit depuis le commit d'avant lui : "
                      "`socle review --base <ce commit>{seconde}`)", amont=base, defaut=defaut, seconde=seconde)


def _diff(projet: config.Projet, base: str) -> tuple[str, list[str]]:
    """Le diff du lot depuis l'ancêtre commun de `base` et de HEAD
    (ADR-0081), l'arbre compris, la mémoire mise à part : elle se donne par
    ses sujets, plus bas."""
    debut = _debut(projet.racine, base)
    diff = outils.git(projet.racine, "diff", debut, *_hors_memoire(projet), check=False)
    fichiers = outils.git(projet.racine, "diff", "--name-only", debut, *_hors_memoire(projet), check=False).split()
    return diff, fichiers


def sujets_du_lot(projet: config.Projet, base: str) -> tuple[list, list]:
    """Les sujets du backlog que le lot touche (ADR-0073), mesurés depuis
    l'ancêtre commun de `base` et de HEAD (ADR-0081) : ceux qu'il sert,
    dont le « Fait quand » est la barre du relecteur, qui existaient à son
    début et dont il change le statut ou le « Fait quand », ou qu'il ouvre
    et clôt ; puis ceux qu'il ouvre sans les clore, ce qu'il renvoie au
    backlog. Un sujet dont il ne change que le reste (un `après`, un
    constat ajouté, sa place parmi les clos) n'est ni l'un ni l'autre."""
    debut = _debut(projet.racine, base)
    touches = set(outils.git(projet.racine, "diff", "--name-only", debut, "--", projet.chemins.backlog,
                             check=False).split())
    avant = memoire.Memoire.charger(projet.racine, debut)
    mem = memoire.Memoire.charger(projet.racine)
    servis, ouverts = [], []
    for e in mem.entrees(memoire.BACKLOG):
        if e.fichier not in touches or memoire.est_prive(e.fichier):
            continue
        # Sous son numéro, ou sous l'ancien d'une entrée renumérotée (ADR-0083).
        ancien = next((avant.entree(i) for i in (e.id, *e.anciens) if avant.entree(i)), None)
        if ancien is None:
            (servis if e.statut in memoire.BACKLOG_CLOS else ouverts).append(e)
        elif e.statut != ancien.statut or _cases(e) != _cases(ancien):
            servis.append(e)
    return servis, ouverts


def _cases(e) -> list:
    """Les critères d'une entrée, dans ses deux sections possibles : « Fait
    quand » et « Satisfait quand » (ADR-0083) ; une section renommée ne
    change pas la barre."""
    return [x for s in (memoire.SECTION_FAIT_QUAND, memoire.SECTION_SATISFAIT_QUAND) for x in memoire.criteres(e, s)]


def messages_depuis(racine, depuis: str) -> list[str]:
    """Les messages des commits depuis `depuis`, du plus ancien au plus
    récent, sans leurs lignes de fin (`Co-Authored-By:`, `Socle-Hooks:`…) :
    ce que la correction dit corriger. Seul le dernier paragraphe se retire,
    s'il n'est fait que de lignes de fin, et jamais le titre : un titre
    `fix: …` ou `Corrige: B-NNNN` reste."""
    brut = outils.git(racine, "log", "--reverse", "--format=%x00%B", f"{depuis}..HEAD", check=False)
    res = []
    for message in brut.split("\0"):
        paragraphes = [p.strip("\n") for p in re.split(r"\n[ \t]*\n", message.strip()) if p.strip()]
        if len(paragraphes) > 1 and all(re.match(r"^[A-Za-z][\w-]*: \S", ligne)
                                        for ligne in paragraphes[-1].splitlines()):
            paragraphes.pop()
        if paragraphes:
            res.append("\n\n".join(paragraphes))
    return res


def decisions_ecrites(projet: config.Projet, base: str) -> list:
    """Les décisions et les demandes que le lot ajoute à la mémoire : la
    spécification ou le modèle de menace écrits avant son code, que ses
    sujets, plus anciens, ne citent pas (ADR-0073), depuis l'ancêtre commun
    de `base` et de HEAD (ADR-0081)."""
    ajoutes = set(outils.git(projet.racine, "diff", "--name-only", "--diff-filter=A", _debut(projet.racine, base),
                             "--", projet.chemins.memoire, check=False).split())
    mem = memoire.Memoire.charger(projet.racine)
    return [e for e in mem.entrees() if e.fichier in ajoutes and e.id.startswith(("ADR-", "D-"))
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


# La consigne du relecteur (ADR-0042, ADR-0044, ADR-0073), en trois parties :
# son rôle, sa barre, les classes de ses constats (D-0112, D-0116).
CONSIGNE_ROLE = a_traduire(
    "Tu relis le lot de travail d'un autre agent, sans sa conversation ni son raisonnement : tu as ce dossier, et "
    "tu peux lire le dépôt pour vérifier un constat, mais tu ne modifies rien. Pour éprouver une commande "
    "(l'installeur, un script), crée d'abord un dossier temporaire hors du dépôt (`mktemp -d`), et n'écris que "
    "là : chaque commande qui écrit y vise par son chemin absolu, jamais par le dossier courant, écrit en toutes "
    "lettres tel que `mktemp -d` l'a rendu, jamais par une variable, qui ne survit pas d'un appel à l'autre. Ton "
    "rôle est de le prendre en défaut.")
CONSIGNE_BARRE = a_traduire(
    "Ta barre est celle des entrées du backlog que sert le lot, plus bas : leurs critères (« Fait quand » d'une "
    "tâche, « Satisfait quand » d'un besoin), les décisions qu'elles citent, et, pour une entrée qui pose ou "
    "change un garde-fou, son modèle de menace, ce que le garde-fou arrête et ce qu'il laisse passer. Cherche ce qui casse (un cas limite, une erreur de logique, une régression), ce "
    "qu'aucun test ne prouve, et ce qui contredit un critère ou une décision. Ne juge ni le style, ni ce que les "
    "contrôles automatiques jugent déjà : la forme de la mémoire, les liens, la présence des tests.")
CONSIGNE_CLASSES = a_traduire(
    "Classe chaque constat. **Bloquant** : il contredit un critère coché ou une décision citée, fait régresser "
    "ce qui marchait avant le lot, perd des données, ou contourne un garde-fou dans son modèle de menace ; un "
    "garde-fou que le lot pose ou change sans modèle de menace écrit est lui-même un constat bloquant. **Pour le "
    "backlog** : un constat qui ne bloque pas, s'il peut se produire dans l'usage normal du projet, ou si rien "
    "ne rattrape ensuite son effet ; un contournement hors du modèle de menace, un critère que le lot ne coche "
    "pas, un défaut voisin, une amélioration, jugés de même. **Écarté** : un constat exotique (un geste rare, "
    "une forme qu'on n'écrit que pour contourner, un cas jamais reproduit) dont l'effet est rattrapé, par un "
    "contrôle, la CI ou une erreur que l'agent voit aussitôt ; et un constat infondé. Une forme du shell qu'un "
    "agent n'écrit pas dans son travail (ni vue dans une session d'agent, ni dans un skill, ni dans une "
    "documentation courante), et qui échappe au hook de l'agent, ne se classe pas bloquante, même refusée avant "
    "le lot par accident, ni pour le backlog, quel qu'en soit l'effet : écarte-la, d'une ligne, pour la liste "
    "des formes connues que le hook ne juge pas, dans le guide du socle (`python3 .socle/socle help`). Seuls "
    "les bloquants se corrigent dans le lot. Rends trois listes numérotées, « Bloquants », « Pour le backlog » "
    "puis « Écartés », chaque constat avec son fichier et sa ligne, ce qui casse et comment le vérifier, pour "
    "un bloquant ce qu'il contredit, pour un écarté pourquoi ; ou « aucun constat ».")
CONSIGNE_SECONDE = a_traduire(
    "Seconde revue : ce diff corrige des constats bloquants d'une première revue, que disent les messages de ses "
    "commits ci-dessous ; le reste du lot a déjà été relu. Ne juge que cette correction : un bloquant mal "
    "corrigé, ce qu'elle fait régresser, contre les mêmes entrées.")
# Le second regard (D-0124, point 5) : à partir de la deuxième passe, le
# relecteur reçoit les causes des bloquants d'avant, et dit pour chaque
# bloquant nouveau s'il a la même cause que l'un d'eux.
CONSIGNE_REGARD = a_traduire(
    "Ce lot a déjà eu des passes de revue : voici les causes de leurs bloquants, telles que l'agent les a "
    "consignées. Pour chaque bloquant que tu trouves, dis s'il a la même cause que l'un d'eux, « même cause : » "
    "suivi de celle-ci, ou une cause nouvelle, « cause nouvelle ».")


def _mesurer(projet: config.Projet, base: str | None, depuis: str | None) -> tuple[str | None, str | None,
                                                                                    str | None]:
    """La base du lot, la note qui en parle, et le commit d'où il se
    mesure (ADR-0075, ADR-0081) ; `(None, note, None)` sans base connue.
    Une référence qui ne mesure pas le lot lève `ReferenceRefusee`."""
    refus = refus_des_references(projet, base, depuis)
    if refus:
        raise ReferenceRefusee(refus)
    note = None
    if not base:
        base, note = base_par_defaut(projet, depuis)
    if not base:
        return None, note, None
    debut = debut_du_lot(projet.racine, base)
    if not debut:
        raise ReferenceRefusee(trad("aucun ancêtre commun entre HEAD et {base} dans ce clone : rien ne mesure le lot. "
                                    "Un clone superficiel s'approfondit par `git fetch --unshallow` ; sinon, `socle "
                                    "review --base <le commit d'avant le lot>`", base=base))
    return base, note, debut


def dossier(projet: config.Projet, base: str | None = None, plafond: int = PLAFOND_DIFF,
            depuis: str | None = None, avant: list | None = None) -> str:
    """Ce que reçoit le relecteur, en plus du dépôt qu'il peut lire : la
    consigne, le diff du lot, les sujets du lot, les décisions qu'il écrit
    et celles qu'ils citent (ADR-0073). Avec `depuis`, le dossier d'une seconde revue : le
    diff depuis ce commit, les messages de ses commits, et toujours les
    sujets du lot entier, depuis `base`. Sans `base`, celle de
    `base_par_defaut` (ADR-0075). Le lot se mesure depuis l'ancêtre commun
    de la base et de HEAD ; une référence qui ne le mesure pas lève
    `ReferenceRefusee` (ADR-0081). `avant` : les passes d'avant de ce lot,
    dont le second regard donne les causes (ADR-0084) ; sans elles, le
    dossier d'une première passe."""
    base, note, debut = _mesurer(projet, base, depuis)
    lignes = [trad("# Revue adversariale d'un lot"), "", trad(CONSIGNE_ROLE), "", trad(CONSIGNE_BARRE), "",
              trad(CONSIGNE_CLASSES), ""]
    if not base:
        lignes.append(trad("(aucune base connue : ni branche distante, ni branche par défaut ; rien à relire)"))
        return "\n".join(lignes) + "\n"
    # La base elle-même quand elle est l'ancêtre commun : son nom se lit
    # mieux que son SHA.
    tel_quel = outils.git(projet.racine, "rev-parse", "--verify", "-q", f"{base}^{{commit}}",
                          check=False).strip() == debut
    origine = base if tel_quel else debut
    if note:
        lignes += [note, ""]
    if avant:
        lignes += [trad("## Le second regard : les causes des passes d'avant"), "", trad(CONSIGNE_REGARD), ""]
        for p in avant:
            if not p.bloquants:
                lignes.append(trad("- passe {n} : aucun bloquant consigné", n=p.numero))
            lignes += [trad("- passe {n} : {cause}", n=p.numero, cause=cause) for cause, _ in p.bloquants]
        lignes.append("")
    if depuis:
        lignes += [trad("## Seconde revue"), "", trad(CONSIGNE_SECONDE), ""]
        for message in messages_depuis(projet.racine, depuis):
            lignes += ["```text", message, "```", ""]
        diff, fichiers = _diff(projet, depuis)
        lignes += [trad("## Le diff de la correction ({n} fichier(s), depuis {base})", n=len(fichiers),
                        base=depuis), ""]
    else:
        diff, fichiers = _diff(projet, debut)
        if tel_quel:
            lignes += [trad("## Le diff du lot ({n} fichier(s), depuis {base})", n=len(fichiers), base=base), ""]
        else:
            lignes += [trad("## Le diff du lot ({n} fichier(s), depuis {commun}, l'ancêtre commun de HEAD et de "
                            "{base})", n=len(fichiers), commun=debut, base=base), ""]
    if not diff.strip():
        lignes.append(trad("(aucun changement hors de la mémoire : rien à relire)"))
    else:
        montre = diff.encode("utf-8")[:plafond].decode("utf-8", errors="ignore")
        lignes += ["```diff", montre.rstrip("\n"), "```"]
        if len(montre) < len(diff):
            lignes.append(trad("(diff tronqué : {n} caractère(s) de plus non montrés ; `git diff {base}` les "
                               "donne)", n=len(diff) - len(montre), base=depuis or origine))
    servis, ouverts = sujets_du_lot(projet, debut)
    if servis:
        lignes += ["", trad("## Les entrées du backlog que sert le lot : leurs critères sont ta barre"), ""]
        for s in servis:
            lignes += [s.texte.strip(), ""]
    if ouverts:
        lignes += ["", trad("## Les entrées que le lot ouvre : ce qu'il renvoie au backlog"), ""]
        lignes += [f"- {s.id} — {s.titre}" for s in ouverts]
    ecrites = decisions_ecrites(projet, debut)
    if ecrites:
        lignes += ["", trad("## Les décisions et les demandes que le lot écrit"), ""]
        for e in ecrites:
            lignes += [e.texte.strip(), ""]
    decisions = [e for e in decisions_citees(projet, servis) if e.id not in {d.id for d in ecrites}]
    if decisions:
        lignes += ["", trad("## Les décisions et les demandes qu'elles citent"), ""]
        for e in decisions:
            lignes += [e.texte.strip(), ""]
    return "\n".join(lignes).rstrip() + "\n"


# --------------------------------------------------------------------------
# L'historique des passes d'un lot (D-0124, ADR-0084)
# --------------------------------------------------------------------------

# Les trois questions du recul : de nature, non de nombre (D-0124, point 2).
QUESTIONS_DU_RECUL = (
    a_traduire("Les bloquants de cette passe ont-ils la même cause que ceux de la précédente ?"),
    a_traduire("Les entrées que le lot ouvre sont-elles de même nature que celles qu'il ferme ?"),
    a_traduire("Les lots clos qui ont touché les mêmes fichiers ont-ils déjà ouvert ce genre d'entrées ?"),
)
CONSIGNE_RECUL = a_traduire(
    "Y répondre dans la passe {n}, d'un paragraphe qui commence par « Recul : », de soixante mots au moins, dont "
    "le dernier mot est « continuer », ce qui rendra la passe suivante différente écrit avant, ou « s'arrêter ». "
    "S'arrêter, c'est une demande à l'humain, qui cite le lot ({lot}), que le paragraphe nomme (`D-NNNN`) et que "
    "le lot attend par son `après` : ce qui tourne, en clair, la règle qui le fait tourner, et une proposition qui "
    "la borne. L'agent avance ailleurs jusqu'à sa réponse, seule à lever l'arrêt.")
CONSIGNE_ARRET = a_traduire(
    "Le recul de la passe {n} finit donc par « s'arrêter » : une demande à l'humain, qui cite le lot ({lot}), que "
    "le paragraphe nomme (`D-NNNN`) et que le lot attend par son `après` : ce qui tourne, en clair, la règle qui le "
    "fait tourner, et une proposition qui la borne. L'agent avance ailleurs jusqu'à sa réponse, seule à lever "
    "l'arrêt.")
# Au-delà, une liste du refus se coupe, et le dit.
PLAFOND_LISTE = 30
# Les fichiers et les commits que lit la recherche des lots voisins.
PLAFOND_FICHIERS = 200
PLAFOND_COMMITS = 500


def lot_de_la_revue(projet: config.Projet, nom: str | None = None) -> memoire.Entree | None:
    """Le lot dont `socle review` produit la passe (ADR-0084) : celui que
    `--batch` nomme, ouvert ; sinon le seul lot `en cours` du backlog
    public, `None` s'il n'y en a pas. Plusieurs, ou un nom qui ne désigne
    pas un lot ouvert, lèvent `PasseRefusee`."""
    mem = memoire.Memoire.charger(projet.racine)
    if nom:
        e = mem.resoudre(nom)
        if e is None or not memoire.est_lot(e) or e.basculee or memoire.est_prive(e.fichier):
            raise PasseRefusee(trad("--batch {nom} : aucun lot de ce nom au backlog public ; rien n'est relu",
                                    nom=nom))
        if e.statut in memoire.BACKLOG_CLOS:
            raise PasseRefusee(trad("--batch {nom} : le lot est clos (« {statut} ») ; une passe s'écrit dans un lot "
                                    "ouvert ; rien n'est relu", nom=nom, statut=e.statut))
        return e
    lots = sorted((e for e in mem.entrees("L") if e.statut == "en-cours" and not e.archivee and not e.basculee
                   and not memoire.est_prive(e.fichier)), key=lambda e: e.id)
    if len(lots) > 1:
        raise PasseRefusee(trad("{n} lots sont en cours ({lots}) : `socle review --batch L-NNNN` nomme celui de cette "
                                "revue ; rien n'est relu", n=len(lots), lots=", ".join(e.id for e in lots)))
    return lots[0] if lots else None


def meme_passe(projet: config.Projet, p: memoire.Passe) -> bool:
    """Rien n'a changé hors de la mémoire depuis le commit de tête que la
    passe a relu : c'est la même passe, dont le dossier se redonne."""
    return bool(p.tete) and outils.rev_existe(projet.racine, p.tete) and outils.git_reussit(
        projet.racine, "diff", "--quiet", p.tete, *_hors_memoire(projet))


def entrees_depuis(projet: config.Projet, debut: str) -> tuple[list, list]:
    """Les entrées du backlog public que le lot a ouvertes depuis `debut`,
    et celles qu'il a closes : ce que git donne au recul."""
    defs = memoire.Memoire.charger(projet.racine, debut).definitions()
    ouvertes, closes = [], []
    for e in memoire.Memoire.charger(projet.racine).entrees(memoire.BACKLOG):
        if e.archivee or e.basculee or memoire.est_prive(e.fichier):
            continue
        avant = next((defs[i][0] for i in (e.id, *e.anciens) if i in defs), None)
        if avant is None:
            ouvertes.append(e)
        if e.statut in memoire.BACKLOG_CLOS and (avant is None or avant.statut not in memoire.BACKLOG_CLOS):
            closes.append(e)
    return sorted(ouvertes, key=lambda e: e.id), sorted(closes, key=lambda e: e.id)


def lots_voisins(projet: config.Projet, debut: str, lot: memoire.Entree) -> list:
    """Les lots clos qui ont touché les fichiers que ce lot change : ceux
    dont un commit d'avant le lot, qui change l'un de ces fichiers, cite le
    lot, son ancien numéro, ou une tâche ou un besoin qu'il attend."""
    racine = projet.racine
    fichiers = outils.git(racine, "diff", "--name-only", debut, *_hors_memoire(projet),
                          check=False).splitlines()[:PLAFOND_FICHIERS]
    if not fichiers:
        return []
    messages = outils.git(racine, "log", "-n", str(PLAFOND_COMMITS), "--format=%x00%B", debut, "--", *fichiers,
                          check=False).split("\0")
    cites = {i for m in messages for i, _ in memoire.mentions(m)}
    mem = memoire.Memoire.charger(racine)
    entrees = {e.id: e for e in mem.entrees(memoire.BACKLOG)}
    anciens = mem.anciens()
    res = []
    for l in mem.entrees("L"):
        if l.id == lot.id or l.statut not in memoire.BACKLOG_CLOS or l.basculee or memoire.est_prive(l.fichier):
            continue
        cles = {l.id, *l.anciens}
        for d in memoire.dependances(l):
            if memoire.type_d_id(d) not in ("T", "B"):
                continue
            cles.add(d)
            e = entrees.get(d) or anciens.get(d)
            if e is not None:
                cles |= {e.id, *e.anciens}
                if memoire.besoin_de(e):
                    cles.add(memoire.besoin_de(e))
        if cles & cites:
            res.append(l)
    return sorted(res, key=lambda e: e.id)


def _court(projet: config.Projet, rev: str) -> str:
    return outils.git(projet.racine, "rev-parse", "--short", rev, check=False).strip() or rev


def _liste(titre: str, entrees: list) -> list[str]:
    lignes = [titre] + [f"- {e.id} — {e.titre}" for e in entrees[:PLAFOND_LISTE]]
    if not entrees:
        lignes.append(trad("- rien"))
    elif len(entrees) > PLAFOND_LISTE:
        lignes.append(trad("- … et {n} de plus", n=len(entrees) - PLAFOND_LISTE))
    return lignes + [""]


def _texte_du_refus(projet: config.Projet, lot: memoire.Entree, suivante: int, raison: str, debut: str,
                    consigne: str | None) -> str:
    """Ce que l'agent lit d'une passe refusée : la raison, l'historique du
    lot, et, pour écrire un recul, ce que git donne et les trois
    questions."""
    lignes = [trad("socle review : la passe {n} du lot {lot} est refusée — {raison}.", n=suivante, lot=lot.id,
                   raison=raison), "",
              trad("## L'historique du lot ({chemin})", chemin=lot.fichier), "",
              memoire.section_des_revues(lot) or "", ""]
    if consigne:
        ouvertes, closes = entrees_depuis(projet, debut)
        lignes += [trad("## Ce que git donne depuis le début du lot ({debut})", debut=_court(projet, debut)), ""]
        lignes += _liste(trad("Les entrées que le lot a ouvertes :"), ouvertes)
        lignes += _liste(trad("Les entrées qu'il a closes :"), closes)
        lignes += _liste(trad("Les lots clos qui ont touché les mêmes fichiers :"), lots_voisins(projet, debut, lot))
        lignes += [trad("## Trois questions, de nature et non de nombre"), ""]
        lignes += [f"{i}. {trad(q)}" for i, q in enumerate(QUESTIONS_DU_RECUL, start=1)]
        lignes += ["", consigne]
    return "\n".join(lignes).rstrip() + "\n"


def refus_de_la_passe(projet: config.Projet, lot: memoire.Entree, deja: list, debut: str) -> str | None:
    """Pourquoi la passe qui suit `deja` est refusée (D-0124, points 2, 5
    et 6), `None` si elle ne l'est pas : les règles que la clôture du lot
    applique aussi (`memoire.refus_de_la_suite`), et, pour écrire le recul
    ou l'arrêt, ce que git donne et les trois questions."""
    refus = memoire.refus_de_la_suite(memoire.Memoire.charger(projet.racine), lot, deja)
    if refus is None:
        return None
    nature, raison = refus
    n = deja[-1].numero
    consigne = {"regard": CONSIGNE_RECUL, "recul": CONSIGNE_RECUL, "arret": CONSIGNE_ARRET}.get(nature)
    return _texte_du_refus(projet, lot, n + 1, raison, debut, trad(consigne, n=n, lot=lot.id) if consigne else None)


def ecrire_passe(projet: config.Projet, lot: memoire.Entree, numero: int, debut: str, tete: str, jour: str) -> str:
    """Ajoute la passe `numero` à la section « Revues » du lot, posée à la
    fin de son entrée si elle n'y est pas : son titre, sa date et ses
    commits. Rend le fichier du lot."""
    lg = langue.du_projet(projet)
    mots = {cle: m[lg] for cle, m in langue.REVUES.items()}
    chemin = projet.racine / lot.fichier
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    passe = [f"### {mots['passe']} {numero} — {jour}", "",
             f"{mots['commits']}{' :' if lg == 'fr' else ':'} {debut}..{tete}"]
    premiere = lot.ligne - 1
    fin = premiere + len(lot.texte.split("\n"))
    section = next((i for i in range(premiere + 1, fin) if memoire.SECTION_REVUES.match(lignes[i])), None)
    if section is None:
        k, ajout = fin, ["", f"## {mots['revues']}", "", *passe]
    else:
        niveau = len(lignes[section]) - len(lignes[section].lstrip("#"))
        k = next((i for i in range(section + 1, fin) if re.match(r"#{1,%d}\s" % niveau, lignes[i])), fin)
        while k > section + 1 and not lignes[k - 1].strip():
            k -= 1
        ajout = ["", *passe]
    lignes[k:k] = ajout
    outils.ecrire(chemin, "\n".join(lignes))
    return lot.fichier


def relire(projet: config.Projet, base: str | None = None, plafond: int = PLAFOND_DIFF, depuis: str | None = None,
           nom_du_lot: str | None = None, jour: str | None = None) -> tuple[str, str | None]:
    """Ce que fait `socle review` (ADR-0084) : le dossier d'une passe, et
    la ligne que la sortie d'erreur en dit. Sans lot en cours, le dossier
    d'avant, sans rien écrire. Avec lui : la même passe se redonne tant que
    rien n'a changé hors de la mémoire depuis son commit de tête ; sinon,
    la suivante n'est produite que si l'historique ne la refuse pas
    (`PasseRefusee`), et s'écrit dans le lot, avec le second regard à
    partir de la deuxième. Un lot qui ne change rien hors de la mémoire n'a
    pas de passe."""
    lot = lot_de_la_revue(projet, nom_du_lot)
    if lot is None:
        return dossier(projet, base, plafond, depuis), trad(
            "(aucun lot en cours au backlog : cette passe ne s'écrit dans aucun lot ; `socle review --batch L-NNNN` "
            "nomme le sien)")
    _, _, debut = _mesurer(projet, base, depuis)
    if debut is None:
        return dossier(projet, base, plafond, depuis), None
    deja = memoire.passes(lot)
    if deja and meme_passe(projet, deja[-1]):
        return dossier(projet, base, plafond, depuis, deja[:-1]), trad(
            "(la passe {n} du lot {lot} : rien n'a changé hors de la mémoire depuis le commit qu'elle a relu ; son "
            "dossier se redonne, rien ne s'écrit)", n=deja[-1].numero, lot=lot.id)
    if deja:
        refus = refus_de_la_passe(projet, lot, deja, debut)
        if refus:
            raise PasseRefusee(refus)
    texte = dossier(projet, base, plafond, depuis, deja)
    depart = depuis or debut
    if outils.git_reussit(projet.racine, "diff", "--quiet", depart, *_hors_memoire(projet)):
        return texte, None
    numero = deja[-1].numero + 1 if deja else 1
    chemin = ecrire_passe(projet, lot, numero, _court(projet, depart), _court(projet, "HEAD"),
                          jour or date.today().isoformat())
    return texte, trad(
        "passe {n} du lot {lot} écrite dans {chemin} : au retour du relecteur, y écrire une ligne « - Bloquant : <sa "
        "cause, en quelques mots> » par bloquant, suivie à partir de la deuxième passe du regard du relecteur, « · "
        "même cause » ou « · cause nouvelle », et « - Ouvre : <les entrées que la passe ouvre> » ; puis, avant la "
        "passe suivante ou la clôture du lot, son recul, « Recul : … »", n=numero, lot=lot.id, chemin=chemin)
