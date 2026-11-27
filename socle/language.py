"""La langue de la mémoire : les mots-clés du format (champs des
entrées, statuts, couches, sections des demandes, réponses) et les gabarits
dans la langue choisie par le projet (`[memory] language` de la politique).

Le moteur raisonne sur des clés internes, celles du format d'origine, sans
accents. La lecture accepte les mots de toutes les langues, quelle que soit
celle du projet : une mémoire en ajout seul garde les mots avec lesquels
elle a été écrite, et un projet qui change de langue n'a rien à réécrire.
L'écriture (`socle new`, les gabarits, l'installeur) suit la langue du
projet. Les messages du moteur restent en français.
"""

from __future__ import annotations

from socle import utils as outils

LANGUES = ("fr", "en")
DEFAUT = "fr"

# Champs des entrées : clé interne → mot écrit, par langue.
CHAMPS = {
    "statut": {"fr": "statut", "en": "status"},
    "preuve": {"fr": "preuve", "en": "proof"},
    "source": {"fr": "source", "en": "source"},
    "refutation": {"fr": "réfutation", "en": "refutation"},
    "validation": {"fr": "validation", "en": "validation"},
    "origine": {"fr": "origine", "en": "origin"},
    "ref": {"fr": "ref", "en": "ref"},
    "lu": {"fr": "lu", "en": "read"},
    "pour": {"fr": "pour", "en": "for"},
    "date": {"fr": "date", "en": "date"},
    "type": {"fr": "type", "en": "type"},
    "remplacee-par": {"fr": "remplacée-par", "en": "superseded-by"},
    # La demande validée qui lève une consigne de l'humain.
    "levee-par": {"fr": "levée-par", "en": "lifted-by"},
    "bloque": {"fr": "bloque", "en": "blocks"},
    "retiree": {"fr": "retirée", "en": "withdrawn"},
    "reformulee": {"fr": "reformulée", "en": "reworded"},
    "basculee": {"fr": "basculée", "en": "made-private"},
    "depuis": {"fr": "depuis", "en": "from"},
    "report": {"fr": "report", "en": "deferred"},
    "forme": {"fr": "forme", "en": "form"},
    "sujet": {"fr": "sujet", "en": "about"},
    "apres": {"fr": "après", "en": "after"},
    "priorite": {"fr": "priorité", "en": "priority"},
    "besoin": {"fr": "besoin", "en": "need"},
    "ancien": {"fr": "ancien", "en": "former"},
    # Un besoin en réserve, d'aucun jalon ouvert (ADR-0118) : pourquoi il
    # attend, et le plus haut lot du backlog à son dernier tri.
    "reserve": {"fr": "réserve", "en": "reserve"},
    "trie": {"fr": "trié", "en": "sorted"},
    # L'estampille de la passation (`memory/handoff.md`).
    "ecrite": {"fr": "écrite", "en": "written"},
    "branche": {"fr": "branche", "en": "branch"},
    "chaine": {"fr": "chaîne", "en": "chain"},
}

# Statuts, par type d'entrée : « abandoned » est une entrée du backlog
# abandonnée ou une décision abandonnée selon le type. Les quatre formes du
# backlog (ADR-0083) ont les mêmes.
_STATUTS_BACKLOG = {"ouvert": {"fr": "ouvert", "en": "open"}, "en-cours": {"fr": "en cours", "en": "in progress"},
                    "bloque": {"fr": "bloqué", "en": "blocked"}, "fait": {"fr": "fait", "en": "done"},
                    "abandonne": {"fr": "abandonné", "en": "abandoned"}}
STATUTS = {
    "F": {"mesure": {"fr": "mesuré", "en": "measured"}, "suppose": {"fr": "supposé", "en": "assumed"},
          "refute": {"fr": "réfuté", "en": "refuted"}, "valide": {"fr": "validé", "en": "validated"}},
    **{t: _STATUTS_BACKLOG for t in ("B", "T", "L", "JA")},
    "ADR": {"proposee": {"fr": "proposée", "en": "proposed"}, "acceptee": {"fr": "acceptée", "en": "accepted"},
            "remplacee": {"fr": "remplacée", "en": "superseded"}, "rejetee": {"fr": "rejetée", "en": "rejected"},
            "abandonnee": {"fr": "abandonnée", "en": "abandoned"}},
    # Une consigne de l'humain : en vigueur, ou levée par sa parole.
    "C": {"en-vigueur": {"fr": "en vigueur", "en": "in force"}, "levee": {"fr": "levée", "en": "lifted"}},
}

# Valeurs d'un champ qui se comparent : `pour : humain`.
VALEURS = {"humain": {"fr": "humain", "en": "human"}, "seance": {"fr": "séance", "en": "session"},
           "jalon": {"fr": "jalon", "en": "milestone"}, "lot": {"fr": "lot", "en": "batch"},
           "haute": {"fr": "haute", "en": "high"}, "basse": {"fr": "basse", "en": "low"},
           # Dans `ref` : le commit qui clôt l'entrée (ADR-0117).
           "ce-commit": {"fr": "ce commit", "en": "this commit"}}

# La section d'une tâche (et d'un lot ou d'un jalon qui en a une) qui dit ce
# qui la rend faite (D-0064) : des cases à cocher, toutes cochées avant de la
# clore « fait ». Celle d'un besoin dit le résultat qui le satisfait
# (ADR-0083).
FAIT_QUAND = {"fr": "Fait quand", "en": "Done when"}
SATISFAIT_QUAND = {"fr": "Satisfait quand", "en": "Satisfied when"}

# La section « Revues » d'un lot (ADR-0084, ADR-0100) : ses passes de revue
# et leurs bloquants. `socle review` en écrit une part, l'agent le reste ; le
# moteur relit les deux.
REVUES = {
    "revues": {"fr": "Revues", "en": "Reviews"},
    "passe": {"fr": "Passe", "en": "Pass"},
    "commits": {"fr": "Commits", "en": "Commits"},
    "arbre": {"fr": "arbre de travail", "en": "working tree"},
    "bloquant": {"fr": "Bloquant", "en": "Blocker"},
    "ouvre": {"fr": "Ouvre", "en": "Opens"},
}

# L'en-tête d'un fichier : `<!-- socle: couche=canonique zone=publique -->`.
ENTETE = {"couche": {"fr": "couche", "en": "layer"}, "zone": {"fr": "zone", "en": "zone"}}
COUCHES = {
    "canonique": {"fr": "canonique", "en": "canonical"}, "actif": {"fr": "actif", "en": "active"},
    "decisions": {"fr": "decisions", "en": "decisions"}, "journal": {"fr": "journal", "en": "journal"},
    "backlog": {"fr": "backlog", "en": "backlog"}, "demandes": {"fr": "demandes", "en": "requests"},
    "passation": {"fr": "passation", "en": "handoff"},
    "consignes": {"fr": "consignes", "en": "directives"},
}
ZONES = {"publique": {"fr": "publique", "en": "public"}, "privee": {"fr": "privee", "en": "private"}}

# Les références typées : `fichier:chemin` s'écrit `file:chemin` en anglais.
REFERENCES = {"commit": {"fr": "commit", "en": "commit"}, "fichier": {"fr": "fichier", "en": "file"},
              "cmd": {"fr": "cmd", "en": "cmd"}, "url": {"fr": "url", "en": "url"}}

# Les sections d'une demande, et les réponses.
SECTIONS = {
    "decision-demandee": {"fr": "Décision demandée", "en": "Decision requested"},
    "contexte": {"fr": "Contexte", "en": "Context"},
    "elements-cites": {"fr": "Éléments cités", "en": "Cited elements"},
    "ou-regarder": {"fr": "Où regarder", "en": "Where to look"},
    "options": {"fr": "Options", "en": "Options"},
    "consequences": {"fr": "Conséquences", "en": "Consequences"},
    "recommandation": {"fr": "Recommandation", "en": "Recommendation"},
    "reponses-possibles": {"fr": "Réponses possibles", "en": "Possible answers"},
}
# Les trois paragraphes qui ouvrent le contexte d'une demande, chacun par
# son nom en gras (ADR-0046) : l'humain qui revient sur le projet après des
# semaines y retrouve le projet, le chantier, puis la question.
PARAGRAPHES_CONTEXTE = {
    "projet": {"fr": "Le projet", "en": "The project"},
    "chantier": {"fr": "Le chantier", "en": "The work"},
    "question": {"fr": "La question", "en": "The question"},
}
# La section d'une décision prise en séance : la question telle
# que l'humain l'a lue dans la conversation ; ou, quand il l'a donnée de
# lui-même, sans question, son texte exact (B-0185).
SECTIONS_SEANCE = {"question-posee": {"fr": "Question posée", "en": "Question asked"},
                   "decision-donnee": {"fr": "Décision donnée", "en": "Decision given"}}
REPONSES = {
    "valider": {"fr": "valider", "en": "approve"},
    "refuser": {"fr": "refuser", "en": "reject"},
    "contexte-insuffisant": {"fr": "contexte-insuffisant", "en": "insufficient-context"},
}
# Ce qui doublerait une réponse de base, dans une langue ou l'autre : les
# réponses de base sont les mêmes dans toute demande (D-0053).
SYNONYMES = {
    "approuver": "valider", "accepter": "valider", "oui": "valider", "ok": "valider",
    "accept": "valider", "validate": "valider", "yes": "valider",
    "rejeter": "refuser", "non": "refuser", "refuse": "refuser", "decline": "refuser", "no": "refuser",
}

# Ce que le lint d'une demande cherche dans ses sections, toutes langues
# confondues (texte sans accents, en minuscules).
INDICES = {
    "effort": ("effort",),
    "risque": ("risque", "risk"),
    "reversibilite": ("reversib",),
    "si-valide": ("valid", "approv"),
    "si-refuse": ("refus", "reject"),
    "sans-reponse": ("sans reponse", "pas de reponse", "ne repond", "aucune reponse", "no answer", "without an answer",
                     "without answer", "unanswered", "no response", "does not answer", "doesn't answer"),
    "verifie": ("verifie", "verified"),
    "suppose": ("suppose", "assumed"),
}

# Les trailers de commit et le marqueur d'une tautologie voulue.
TRAILERS = {"dispense-test": ("dispense-test", "waive-test"), "dispense-doc": ("dispense-doc", "waive-doc"),
            "corrige": ("corrige", "fixes")}
VOULU = ("voulu", "intended")

# Les textes fixes que le moteur écrit dans la mémoire.
TEXTES = {
    "titre-basculee": {"fr": "Entrée basculée dans la mémoire privée", "en": "Entry moved to the private memory"},
    "texte-basculee": {"fr": "Son contenu est dans la mémoire privée.", "en": "Its content is in the private memory."},
    "titre-journal": {"fr": "Journal", "en": "Journal"},
    # La passation (`socle handoff write`) : son titre, ce qui attend.
    "titre-passation": {"fr": "Passation", "en": "Handoff"},
    "attente-passation": {"fr": "Ce qui attend : {attente}.", "en": "What is waiting: {attente}."},
    "rien": {"fr": "rien", "en": "nothing"},
    # L'entrée du journal où `socle archive` range les consignes levées.
    "titre-consignes-rangees": {"fr": "Consignes levées rangées dans le journal",
                                "en": "Lifted directives moved to the journal"},
    "texte-consignes-rangees": {"fr": "Rangées par `socle archive` : chacune levée par la parole de l'humain que "
                                      "cite sa ligne de métadonnées. Leur identifiant reste résolu.",
                                "en": "Moved by `socle archive`: each one lifted by the human's word that its "
                                      "metadata line cites. Their identifiers still resolve."},
}

# Les entrées que `socle new` pose, par langue.
SQUELETTES = {
    "fr": {
        "F": "> statut : supposé · source : <d'où vient ce fait>\n\n<le fait, et ce qui le prouverait>",
        "B": "> statut : ouvert · origine : <J-… ou commit:… où le besoin est apparu> · lu : backlog@{lu}\n\n"
             "<le défaut à corriger ou la fonction à ajouter : ses constats ou sa motivation, et sa spécification "
             "s'il n'est pas tranché>\n\n## Satisfait quand\n\n- [ ] <un résultat, jamais une implémentation>",
        "T": "> statut : ouvert · origine : <J-… ou commit:… où la tâche est apparue> · besoin : {besoin} · "
             "lu : backlog@{lu}\n\n<le livrable, en principe un commit>\n\n## Fait quand\n\n"
             "- [ ] <ce qu'un test vérifie>",
        "L": "> statut : ouvert · origine : <J-… ou commit:… où le lot est formé> · lu : backlog@{lu}\n\n"
             "<ce qui réunit ses tâches, les fichiers qu'elles touchent ; son `après` nomme le lot d'avant, puis "
             "ses tâches>",
        "JA": "> statut : ouvert · origine : <J-… ou commit:… où le jalon est posé> · lu : backlog@{lu}\n\n"
              "<le but que servent ses besoins ; son `après` nomme le jalon d'avant, puis ses besoins>",
        "J": "<ce qui s'est passé, avec ses références>",
        "C": "> statut : en vigueur · source : <J-… ou D-… où la parole de l'humain est consignée> · "
             "date : {date}\n\n> « <le texte exact de l'humain, mot pour mot> »",
        "ADR": "> statut : proposée · date : {date} · lu : decisions@{lu}\n\n## Contexte\n\n<ce qui oblige à décider>\n\n"
               "## Décision\n\n<ce qui est décidé>\n\n## Conséquences\n\n<ce que ça change, et comment le défaire>",
    },
    "en": {
        "F": "> status : assumed · source : <where this fact comes from>\n\n<the fact, and what would prove it>",
        "B": "> status : open · origin : <J-… or commit:… where the need came up> · read : backlog@{lu}\n\n"
             "<the defect to fix or the feature to add: its findings or its motivation, and its specification "
             "if it is not settled>\n\n## Satisfied when\n\n- [ ] <a result, never an implementation>",
        "T": "> status : open · origin : <J-… or commit:… where the task came up> · need : {besoin} · "
             "read : backlog@{lu}\n\n<the deliverable, as a rule one commit>\n\n## Done when\n\n"
             "- [ ] <what a test checks>",
        "L": "> status : open · origin : <J-… or commit:… where the batch is formed> · read : backlog@{lu}\n\n"
             "<what brings its tasks together, the files they touch; its `after` names the previous batch, then "
             "its tasks>",
        "JA": "> status : open · origin : <J-… or commit:… where the milestone is set> · read : backlog@{lu}\n\n"
              "<the goal its needs serve; its `after` names the previous milestone, then its needs>",
        "J": "<what happened, with its references>",
        "C": "> status : in force · source : <J-… or D-… where the human's words are recorded> · "
             "date : {date}\n\n> “<the human's exact text, word for word>”",
        "ADR": "> status : proposed · date : {date} · read : decisions@{lu}\n\n## Context\n\n<what forces a decision>\n\n"
               "## Decision\n\n<what is decided>\n\n## Consequences\n\n<what it changes, and how to undo it>",
    },
}


def _inverse(table: dict) -> dict[str, str]:
    """Tout mot écrit, dans toutes les langues, vers sa clé interne."""
    res = {}
    for cle, mots in table.items():
        res[outils.cle(cle)] = cle
        for mot in mots.values():
            res[outils.cle(mot)] = cle
    return res


_CHAMPS = _inverse(CHAMPS)
_STATUTS = {t: _inverse(s) for t, s in STATUTS.items()}
_VALEURS = _inverse(VALEURS)
_ENTETE = _inverse(ENTETE)
_COUCHES = _inverse(COUCHES)
_ZONES = _inverse(ZONES)
_REFERENCES = _inverse(REFERENCES)
_SECTIONS = _inverse({**SECTIONS, **SECTIONS_SEANCE})
_REPONSES = _inverse(REPONSES)
_TRAILERS = {outils.cle(m): cle for cle, mots in TRAILERS.items() for m in mots}


def champ(mot: str) -> str:
    """La clé interne d'un champ écrit dans une langue ou une autre."""
    k = outils.cle(mot)
    return _CHAMPS.get(k, k)


def statut(type_: str, mot: str) -> str:
    k = outils.cle(mot)
    return _STATUTS.get(type_, {}).get(k, k)


def valeur(mot: str) -> str:
    k = outils.cle(mot)
    return _VALEURS.get(k, k)


def entete(cle: str, valeur_: str) -> tuple[str, str]:
    """Une paire de l'en-tête d'un fichier, en clés internes."""
    k = _ENTETE.get(outils.cle(cle), outils.cle(cle))
    v = outils.cle(valeur_)
    if k == "couche":
        v = _COUCHES.get(v, v)
    elif k == "zone":
        v = _ZONES.get(v, v)
    return k, v


def reference(type_: str) -> str:
    return _REFERENCES.get(type_, type_)


def section(titre: str) -> str:
    k = outils.cle(titre)
    return _SECTIONS.get(k, k)


def reponse(mot: str) -> str:
    k = outils.cle(mot)
    return _REPONSES.get(k, k)


def trailer(nom: str) -> str:
    k = outils.cle(nom)
    return _TRAILERS.get(k, k)


def textes(cle: str) -> set[str]:
    """Un texte fixe, dans toutes les langues."""
    return set(TEXTES[cle].values())


def mot(table: dict, cle: str, langue: str) -> str:
    """Le mot d'une clé interne dans la langue du projet."""
    return table[cle].get(langue) or table[cle][DEFAUT]


def du_projet(projet) -> str:
    """La langue de la mémoire du projet : `[memory] language`, français à
    défaut ; une langue inconnue retombe sur le français."""
    l = str(projet.pol("memory", "language", defaut=DEFAUT) or DEFAUT).lower()
    return l if l in LANGUES else DEFAUT


def entete_fichier(couche: str, zone: str, langue: str) -> str:
    """`<!-- socle: couche=… zone=… -->` dans la langue du projet."""
    return (f"<!-- socle: {mot(ENTETE, 'couche', langue)}={mot(COUCHES, couche, langue)} "
            f"{mot(ENTETE, 'zone', langue)}={mot(ZONES, zone, langue)} -->")


def trailers(message: str) -> dict[str, list[str]]:
    """Les trailers d'un message de commit, sous leurs noms internes
    (`Waive-test` est `dispense-test`)."""
    res: dict[str, list[str]] = {}
    for k, v in outils.trailers(message).items():
        res.setdefault(trailer(k), []).extend(v)
    return res


def trailers_hors_bloc(message: str) -> dict[str, list[str]]:
    """Les lignes en forme de trailer écrites hors du dernier paragraphe d'un
    message de commit, que `trailers` ne lit pas, sous leurs noms internes :
    ce qu'un refus qui attend une dispense nomme, pour dire où l'écrire."""
    res: dict[str, list[str]] = {}
    for k, v in outils.trailers_hors_bloc(message).items():
        res.setdefault(trailer(k), []).extend(v)
    return res


def meta(lg: str, type_: str | None = None, **champs: str) -> str:
    """Une ligne de métadonnées dans la langue du projet :
    `meta("en", "F", statut="mesure", preuve="file:x")` →
    `> status : measured · proof : file:x`. Le statut se donne par sa clé
    interne ; les autres valeurs telles quelles."""
    morceaux = []
    for cle, valeur_ in champs.items():
        cle = cle.replace("_", "-")
        if cle == "statut" and type_:
            valeur_ = mot(STATUTS[type_], valeur_, lg)
        morceaux.append(f"{mot(CHAMPS, cle, lg)} : {valeur_}")
    return "> " + " · ".join(morceaux)


def ref_fichier(chemin: str, lg: str) -> str:
    """`fichier:chemin` dans la langue du projet."""
    return f"{mot(REFERENCES, 'fichier', lg)}:{chemin}"
