"""Le contrat des demandes de décision humaine.

Une demande en file est lue quand le contexte est perdu : elle doit se suffire
à elle-même. Le lint vérifie ce qu'un script peut vérifier — les huit champs,
et qu'aucun identifiant interne n'y paraisse sans description. La qualité de
l'explication, elle, ne se contrôle pas : la réponse `contexte-insuffisant`
renvoie la demande à l'agent, et ce renvoi reste consigné dans la réponse.

Une réponse vit à côté de la demande, dans `<demande>.answer.toml`, et
seul l'humain l'écrit (`socle answer`). Elle porte l'empreinte du texte
exact auquel l'humain a répondu : la demande est gelée dès qu'elle a une
réponse.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from socle import config, fingerprint as empreinte, language as langue, memory as memoire, utils as outils
from socle.messages import a_traduire, langue as langue_des_messages, trad

# Les sections et les réponses, sous leurs clés internes ; elles s'écrivent
# dans la langue de la mémoire du projet.
SECTIONS = {k: v["fr"] for k, v in langue.SECTIONS.items()}
REPONSE_POSITIVE = "valider"
RENVOI = "contexte-insuffisant"

# Identifiants internes qui ne disent rien à qui n'a pas le projet en tête :
# ceux de la mémoire, un SHA, un numéro de PR ou d'issue. Le projet en ajoute
# d'autres (`requests.internal_id_patterns`), comme les codes de chantier.
MOTIFS_INTERNES = [
    memoire.ID_RE.pattern,
    r"(?<![\w/.@-])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}(?![\w-])",  # pas une empreinte `ID@…`
    r"(?<![\w&])#\d+\b",
]
MOTS_DESCRIPTION_MIN = 5
# Une ligne d'empreinte (ADR-0058) : un fichier protégé et son empreinte
# nouvelle, rien d'autre, dans les mises en liste que `ligne_d_empreinte`
# énumère. C'est ce que
# `protege.fichiers` lit dans la demande qui approuve une mise à jour ;
# l'humain, lui, lit les fichiers dans la pull request.
EMPREINTE_DE_FICHIER = re.compile(r"sha256:[0-9a-f]{16}")
FICHIER_SUPPRIME = tuple(empreinte.SUPPRIME.values())
DECOR_DE_LISTE = {"-", "+", "—", "–", "|", "·", "→", "->", "=>"}
_PUCE_NUMEROTEE = re.compile(r"\d+[.)]")
# Ce qu'un chemin de fichier ne porte pas : un motif, un lien Markdown.
_PAS_UN_FICHIER = re.compile(r"[*?\[\]()<>]")
SECTION_MIN = 15
# Une demande lue une semaine plus tard, sans le projet en tête : le contexte
# raconte, il ne résume pas en une ligne.
MOTS_CONTEXTE_MIN = 60
# Chacun des trois paragraphes qui ouvrent le contexte (ADR-0046) dit
# quelque chose : un nom en gras suivi d'une demi-phrase ne remet personne
# en contexte. Une demande posée avant le moteur qui apporte la règle, ou
# datée d'avant elle, garde l'ancien contrat.
MOTS_PARAGRAPHE_MIN = 15
DATE_PARAGRAPHES = "2026-11-08"
LIEN = re.compile(r"\]\([^)\s]+\)|https?://\S+")
# Un trou du gabarit : `<texte avec des espaces>`, hors commentaire HTML ;
# collé à ses chevrons, pour qu'une comparaison (« < 5 », « a <= b ») n'en
# soit pas un. Le code cité, entre accents graves, est un exemple.
TROU = re.compile(r"<(?!!--)[^\s<>=][^<>\n]*\s[^<>\n]*[^\s<>=-]>")
CODE_CITE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


@dataclass
class Demande:
    chemin: str
    texte: str
    entree: memoire.Entree | None
    sections: dict[str, str] = field(default_factory=dict)
    reponse: dict | None = None
    chemin_reponse: str | None = None
    erreur_reponse: str | None = None

    @property
    def id(self) -> str | None:
        return self.entree.id if self.entree else None

    @property
    def statut(self) -> str:
        if self.reponse is None:
            if self.entree and "retiree" in self.entree.meta:
                return "retirée"
            return "en attente"
        r = str(self.reponse.get("reponse", ""))
        return "renvoyée" if langue.reponse(r) == RENVOI else f"répondue : {r}"

    @property
    def statut_affiche(self) -> str:
        """Le statut dit dans la langue des messages ; `statut` reste la valeur
        que le moteur compare."""
        if self.reponse is None:
            return trad("retirée") if self.entree and "retiree" in self.entree.meta else trad("en attente")
        r = str(self.reponse.get("reponse", ""))
        return trad("renvoyée") if langue.reponse(r) == RENVOI else trad("répondue : {reponse}", reponse=r)

    @property
    def seance(self) -> bool:
        """Une décision prise en séance : l'humain a lu la question
        dans la conversation et y a répondu ; elle s'écrit avec sa réponse."""
        return bool(self.entree) and langue.valeur(self.entree.meta.get("forme", "")) == "seance"

    @property
    def sujet(self) -> tuple[str, str] | None:
        """Ce que la décision approuve : un chemin, et l'empreinte de la
        version approuvée (`chemin@empreinte`) quand il y en a une."""
        brut = (self.entree.meta.get("sujet", "") if self.entree else "").strip()
        if not brut:
            return None
        chemin, _, empreinte = brut.partition("@")
        return chemin.strip(), empreinte.strip()

    @property
    def validee(self) -> bool:
        return self.reponse is not None and langue.reponse(str(self.reponse.get("reponse", ""))) == REPONSE_POSITIVE

    def reponses_possibles(self) -> list[str]:
        bloc = self.sections.get("reponses-possibles", "")
        return re.findall(r"^\s*[-*]\s+`([^`]+)`", bloc, flags=re.M)

    def accepte(self, reponse: str) -> bool:
        """Une réponse possible, telle qu'écrite ou dans une autre langue
        (`approve` pour `valider`). En séance, la question n'a pas de liste
        écrite : toute réponse se consigne."""
        if self.seance:
            return bool(reponse.strip())
        return langue.reponse(reponse) in {langue.reponse(p) for p in self.reponses_possibles()}


def chemin_reponse(chemin_demande: str) -> str:
    return chemin_demande[: -len(".md")] + memoire.SUFFIXE_REPONSE


def decouper_sections(texte: str) -> dict[str, str]:
    res: dict[str, list[str]] = {}
    courante = None
    for _, ligne, code in memoire.lignes_hors_code(texte):
        m = None if code else re.match(r"^##\s+(.*?)\s*#*\s*$", ligne)
        if m and not ligne.startswith("###"):
            courante = langue.section(m[1])
            res.setdefault(courante, [])
            continue
        if courante is not None:
            res[courante].append(ligne)
    return {k: "\n".join(v).strip() for k, v in res.items()}


def charger(racine: Path, rev: str | None, chemin: str, texte: str) -> Demande:
    f = memoire.analyser(chemin, texte)
    entrees = [e for e in f.entrees if e.type == "D"]
    d = Demande(chemin=chemin, texte=texte, entree=entrees[0] if entrees else None)
    d.sections = decouper_sections(texte)
    cr = chemin_reponse(chemin)
    brut = outils.lire_a(racine, rev, cr)
    if brut is not None:
        d.chemin_reponse = cr
        try:
            d.reponse = tomllib.loads(brut)
        except tomllib.TOMLDecodeError as e:
            d.reponse = {}
            d.erreur_reponse = trad("réponse illisible : {erreur}", erreur=e)
    return d


def toutes(racine: Path, rev: str | None = None) -> list[Demande]:
    """Les demandes, privées comprises quand elles se lisent : celles du clone
    du dépôt privé, ou déchiffrées ; une demande privée chiffrée ici n'est
    pas lue."""
    if rev is None:
        chemins = set(outils.fichiers_courants(racine)) | set(memoire.fichiers_compagnon(racine))
    else:
        chemins = outils.fichiers_a(racine, rev)
    res = []
    for c in sorted(chemins):
        if memoire.couche_attendue(c) == "demandes":
            texte = outils.lire_a(racine, rev, c)
            if texte is not None and not (memoire.est_prive(c) and not memoire.lisible(texte)):
                res.append(charger(racine, rev, c, texte))
    return res


def motifs_internes(projet: config.Projet) -> list[re.Pattern]:
    supp = projet.gf("requests", "internal_id_patterns", defaut=[])
    return [re.compile(m) for m in MOTIFS_INTERNES + list(supp)]


def identifiants_cites(texte: str, motifs: list[re.Pattern]) -> set[str]:
    res = set()
    for _, ligne, code in memoire.lignes_hors_code(texte):
        if code:
            continue
        for m in motifs:
            for x in m.finditer(ligne):
                res.add(x.group(0))
    return res


def ligne_d_empreinte(ligne: str, proteges: list[str], racine: Path | None = None) -> bool:
    """ADR-0058 : la ligne ne dit qu'un fichier protégé et son empreinte
    nouvelle (`sha256:` et seize caractères, ou « supprimé » / `deleted`),
    dans un ordre ou dans l'autre. Sont acceptés autour : une puce (`-`,
    `*`, `+`) ou un numéro (`1.`, `1)`), une cellule de tableau (`|`), des
    accents graves ou du gras (`**`) sur l'un ou l'autre, un deux-points
    collé ou séparé, un tiret, un point médian, une flèche (`→`, `->`,
    `=>`), une ponctuation finale (`.`, `,`, `;`). Ne l'est pas : un mot de
    plus, un chemin que la politique ne protège pas, un répertoire (finissant
    par `/`, ou qui en est un sous `racine`), un motif (`*`, `?`, `[`), un
    lien Markdown. Ce n'est alors pas une ligne d'empreinte, mais de la
    prose."""
    jetons = ligne.replace("`", " ").replace("→", " → ").split()
    if jetons and _PUCE_NUMEROTEE.fullmatch(jetons[0]):
        jetons = jetons[1:]
    # Le gras et la ponctuation qui collent au jeton, pas les `_` d'un nom.
    jetons = [re.sub(r"^\*+|[*.,;:]+$", "", j) for j in jetons]
    jetons = [j for j in jetons if j and j not in DECOR_DE_LISTE]
    if len(jetons) != 2:
        return False
    empreintes = [j for j in jetons if EMPREINTE_DE_FICHIER.fullmatch(j) or j in FICHIER_SUPPRIME]
    chemins = [j for j in jetons if j not in empreintes]
    if len(empreintes) != 1 or len(chemins) != 1:
        return False
    chemin = chemins[0]
    if chemin.endswith("/") or _PAS_UN_FICHIER.search(chemin) or (racine is not None and (racine / chemin).is_dir()):
        return False
    return outils.correspond(chemin, proteges)


def hors_empreintes(texte: str, projet: config.Projet) -> str:
    """ADR-0058 : le texte d'une demande sans ses lignes d'empreinte, ce que
    son budget compte et ce que son lint lit comme de la prose. La liste des
    fichiers protégés d'une mise à jour n'y pèse donc rien, et ses
    empreintes n'ont pas à être décrites une à une."""
    proteges = projet.chemins_proteges()
    return "".join(ligne for ligne in texte.splitlines(keepends=True)
                   if not ligne_d_empreinte(ligne, proteges, projet.racine))


def contrat(projet: config.Projet, chemin: str, questions: bool = False) -> str:
    """ADR-0058 : le contrat d'une demande, dit par la commande qui la pose,
    avant qu'elle soit écrite, avec les seuils du lint et le budget du
    projet. Le lint reste le juge ; ceci évite de l'apprendre à son refus.
    Avec `questions`, celui du gabarit des questions de cadrage (D-0067),
    qui a sa section « Questions » et une réponse libre de plus."""
    lg = langue.du_projet(projet)
    noms = [v.get(langue_des_messages(), v["fr"]) for v in langue.PARAGRAPHES_CONTEXTE.values()]
    lignes = [trad("Son contrat, que le lint juge dès l'écriture (le skill `socle-request` le détaille) :"),
              trad("- chaque section du squelette remplie, sans texte du gabarit laissé entre chevrons ;"),
              trad("- « Contexte » commence par trois paragraphes, chacun ouvert par son nom en gras et long d'au "
                   "moins {n} mots : {noms} ; puis le détail, {total} mots au moins en tout ;",
                   n=MOTS_PARAGRAPHE_MIN, noms=", ".join(f"**{n}.**" for n in noms), total=MOTS_CONTEXTE_MIN),
              trad("- « Éléments cités » décrit en clair, en au moins {n} mots, chaque identifiant interne "
                   "(identifiant de mémoire, SHA, numéro de pull request) ; un fichier protégé à faire approuver "
                   "s'y écrit sur sa ligne, son chemin et son empreinte nouvelle, rien d'autre (`- "
                   ".socle/policy.toml sha256:0123456789abcdef`) : ces lignes n'ont pas à être décrites et ne "
                   "comptent pas dans le budget ;", n=MOTS_DESCRIPTION_MIN),
              trad("- « Où regarder » donne un lien ; « Options » dit l'effort, le risque et la réversibilité de "
                   "chacune ; « Conséquences », ce qui se passe si l'humain valide, s'il refuse, sans réponse ; « "
                   "Recommandation » sépare le vérifié du supposé ;"),
              trad("- « Réponses possibles » propose les réponses de base : {reponses}.",
                   reponses=", ".join(f"`{langue.mot(langue.REPONSES, r, lg)}`" for r in langue.REPONSES))]
    if questions:
        lignes.insert(3, trad("- « Questions » pose chaque question ouverte, en gras et numérotée, suivie de "
                              "l'hypothèse de l'agent (« aucune » s'il n'en a pas) ; « Réponses possibles » garde la "
                              "réponse libre du gabarit, `reponses`, en plus des réponses de base ;"))
    budget = projet.budget_octets(chemin)
    if budget:
        lignes.append(trad("Son budget : {budget} octets, les lignes d'empreinte mises à part.", budget=budget))
    return "\n".join(lignes)


def posee_avant_le_moteur(projet: config.Projet, chemin: str, texte: str) -> bool:
    """ADR-0046 : la demande était déjà là, telle quelle, avant la mise à
    jour du moteur, au dernier commit qui précède celui qui a changé son
    verrou, ou à `HEAD` tant que la mise à jour n'est pas commitée. Elle a
    été écrite sous l'ancien contrat. Sans historique lisible, non."""
    racine, verrou = projet.racine, projet.chemins.lock
    if outils.git(racine, "status", "--porcelain", "--", verrou, check=False).strip():
        avant = "HEAD"
    else:
        dernier = outils.git(racine, "log", "-1", "--format=%H", "--", verrou, check=False).strip()
        if not dernier:
            return False
        avant = f"{dernier}^"
    return outils.lire_a(racine, avant, chemin) == texte


def paragraphes_du_contexte(contexte: str) -> list[str]:
    """ADR-0046 : le contexte commence par « Le projet », « Le chantier » et
    « La question », ses trois premiers paragraphes, dans cet ordre, chacun
    ouvert par son nom en gras et long d'au moins quinze mots. Les noms se
    lisent dans les deux langues, et se disent dans celle des messages.
    Vide : le contexte part du projet."""
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n", contexte.strip()) if p.strip()]

    def cle(p: str) -> str | None:
        for k, noms in langue.PARAGRAPHES_CONTEXTE.items():
            if any(re.match(rf"\*\*\s*{re.escape(n)}\s*[.:]?\s*\*\*", p, re.I) for n in noms.values()):
                return k
        return None

    trouves = [(cle(p), p) for p in paragraphes]
    trouves = [(k, p) for k, p in trouves if k]
    ordre = list(langue.PARAGRAPHES_CONTEXTE)
    noms = {k: v.get(langue_des_messages(), v["fr"]) for k, v in langue.PARAGRAPHES_CONTEXTE.items()}
    manque = [noms[k] for k in ordre if k not in {k for k, _ in trouves}]
    if manque:
        return [trad("« Contexte » : il commence par trois paragraphes, chacun ouvert par son nom en gras, pour "
                     "qui revient sur le projet après des semaines : **Le projet.** (ce que fait le projet), **Le "
                     "chantier.** (le but du travail en cours, ce qui est fait et ce qui reste), **La question.** "
                     "(ce qui la pose maintenant) ; il manque : {manque}", manque=", ".join(manque))]
    fautes = []
    if [cle(p) for p in paragraphes[:3]] != ordre:
        fautes.append(trad("« Contexte » : il commence par « Le projet », puis « Le chantier », puis « La "
                           "question », dans cet ordre"))
    for k, p in trouves:
        if len(re.findall(r"[^\W\d_]{2,}", p)) - len(noms[k].split()) < MOTS_PARAGRAPHE_MIN:
            fautes.append(trad("« Contexte » : le paragraphe « {nom} » fait moins de {n} mots", nom=noms[k],
                               n=MOTS_PARAGRAPHE_MIN))
    return fautes


def linter(d: Demande, projet: config.Projet) -> list[str]:
    """Les manquements au contrat, en clair. Vide : la demande est conforme."""
    fautes = []
    f = memoire.analyser(d.chemin, d.texte)
    if f.couche != "demandes":
        fautes.append(trad("en-tête `<!-- socle: couche=demandes zone=… -->` absent ou faux"))
    if d.entree is None:
        fautes.append(trad("pas de titre `# D-NNNN — <décision en une phrase>`"))
        return fautes
    if len(d.entree.titre) < 10:
        fautes.append(trad("le titre doit énoncer la décision demandée en une phrase"))
    if d.seance:
        # Une décision en séance n'attend rien : elle s'écrit avec la réponse
        # que l'humain vient de donner.
        fautes.append(trad("décision en séance sans la réponse de l'humain : la consigner avec elle, mot pour mot "
                           "(`socle decision`)"))
        return fautes
    nom = Path(d.chemin).name
    if not nom.startswith(d.entree.id):
        fautes.append(trad("le nom du fichier doit commencer par {id}", id=d.entree.id))

    for k, titre in SECTIONS.items():
        contenu = d.sections.get(k)
        if contenu is None:
            fautes.append(trad("section « {titre} » absente", titre=titre))
        elif len(re.sub(r"\s+", " ", contenu)) < SECTION_MIN:
            fautes.append(trad("section « {titre} » vide ou trop courte", titre=titre))
        elif TROU.search(CODE_CITE.sub(" ", contenu)):
            # Le gabarit porte les mots que le lint cherche : un trou laissé
            # tel quel passerait pour une section remplie.
            trou = TROU.search(CODE_CITE.sub(" ", contenu)).group(0)
            fautes.append(trad("section « {titre} » : texte du gabarit laissé tel quel ({trou}…)",
                               titre=titre, trou=trou[:40]))

    contexte = d.sections.get("contexte", "")
    date_ = d.entree.meta.get("date", "")
    if contexte and not (date_ and date_ < DATE_PARAGRAPHES) and not posee_avant_le_moteur(projet, d.chemin, d.texte):
        fautes += paragraphes_du_contexte(contexte)
    if contexte and len(re.findall(r"[^\W\d_]{2,}", contexte)) < MOTS_CONTEXTE_MIN:
        fautes.append(trad("« Contexte » trop court : moins de {n} mots ne suffisent pas à "
                           "quelqu'un qui n'a pas ouvert le projet depuis une semaine",
                           n=MOTS_CONTEXTE_MIN))
    regarder = d.sections.get("ou-regarder", "")
    if "ou-regarder" in d.sections and not LIEN.search(regarder):
        fautes.append(trad("« Où regarder » doit donner un lien vers chaque document ou passage à lire, et "
                           "dire ce qu'il faut y vérifier : le permalien de `socle url <chemin>` ; sans "
                           "adresse de dépôt connue, un lien relatif depuis la demande "
                           "(`[calc.py](../../calc.py)`)"))

    norm = {k: outils.cle(v).replace("-", " ") for k, v in d.sections.items()}
    opts = norm.get("options", "")
    for indice, faute in (("effort", a_traduire("« Options » doit dire l'effort de chaque option")),
                          ("risque", a_traduire("« Options » doit dire le risque de chaque option")),
                          ("reversibilite", a_traduire("« Options » doit dire la réversibilité de chaque option"))):
        if "options" in d.sections and not any(x in opts for x in langue.INDICES[indice]):
            fautes.append(trad(faute))
    cons = norm.get("consequences", "")
    if "consequences" in d.sections:
        if not any(x in cons for x in langue.INDICES["si-valide"]):
            fautes.append(trad("« Conséquences » doit dire ce qui se passe si l'humain valide"))
        if not any(x in cons for x in langue.INDICES["si-refuse"]):
            fautes.append(trad("« Conséquences » doit dire ce qui se passe si l'humain refuse"))
        if not any(x in cons for x in langue.INDICES["sans-reponse"]):
            fautes.append(trad("« Conséquences » doit dire ce qui se passe sans réponse"))
    rec = norm.get("recommandation", "")
    if "recommandation" in d.sections and not (any(x in rec for x in langue.INDICES["verifie"])
                                               and any(x in rec for x in langue.INDICES["suppose"])):
        fautes.append(trad("« Recommandation » doit séparer ce qui est vérifié de ce qui est supposé"))

    possibles = d.reponses_possibles()
    if "reponses-possibles" in d.sections:
        if len(possibles) < 2:
            fautes.append(trad("« Réponses possibles » : au moins deux réponses, en liste `- \\`valeur\\` — "
                               "sens`"))
        if RENVOI not in {langue.reponse(x) for x in possibles}:
            fautes.append(trad("« Réponses possibles » doit proposer `{renvoi}`", renvoi=RENVOI))
        lg = langue.du_projet(projet)
        proposees = {langue.reponse(x) for x in possibles}
        manquent = [r for r in langue.REPONSES if r not in proposees and r != RENVOI]
        nommes = gestes_nommes(d, projet) if REPONSE_POSITIVE in manquent else []
        if nommes:
            fautes.append(trad("« Réponses possibles » : la demande nomme {noms}, que seule une réponse "
                               "`{positive}` autorise à changer, mais ne propose pas `{positive}` ; la "
                               "proposer pour l'option qui y touche (une autre option mène à une demande "
                               "nouvelle)", noms=", ".join(f"`{n}`" for n in nommes[:5]),
                               positive=langue.mot(langue.REPONSES, REPONSE_POSITIVE, lg)))
        # Le geste nommé a son propre refus ; une demande retirée n'attend plus
        # de réponse, et les réponses de base (D-0053) ne la concernent pas.
        manquent = [] if "retiree" in d.entree.meta else [r for r in manquent
                                                          if not (nommes and r == REPONSE_POSITIVE)]
        if manquent:
            fautes.append(trad("« Réponses possibles » doit proposer les réponses de base, les mêmes dans toute "
                               "demande ({manquent}) : `{positive}` y prend la recommandation, et une demande de "
                               "choix ajoute ses options", manquent=", ".join(
                                   f"`{langue.mot(langue.REPONSES, r, lg)}`" for r in manquent),
                               positive=langue.mot(langue.REPONSES, REPONSE_POSITIVE, lg)))
        for x in possibles:
            base = langue.SYNONYMES.get(outils.cle(x))
            if base:
                fautes.append(trad("« Réponses possibles » : `{x}` double la réponse de base `{base}`, à employer "
                                   "à sa place", x=x, base=langue.mot(langue.REPONSES, base, lg)))

    # Aucun identifiant interne sans description, dans la même demande.
    decrits = descriptions(d.sections.get("elements-cites", ""), motifs_internes(projet))
    # Une ligne d'empreinte se suffit : son chemin dit ce qu'elle est (ADR-0058).
    cites = identifiants_cites(hors_empreintes(d.texte, projet), motifs_internes(projet)) - {d.entree.id}
    for ident in sorted(cites):
        if ident not in decrits:
            fautes.append(
                trad("identifiant `{ident}` cité sans description : le décrire en clair dans « Éléments cités "
                     "» (`- <identifiant> — ce que c'est, en une phrase`)", ident=ident)
            )
    return fautes


def gestes_nommes(d: Demande, projet: config.Projet) -> list[str]:
    """Les tests du projet et les clés des seuils que la demande nomme : ce
    que lisent, dans une demande validée, les deux contrôles qui acceptent une
    validation (`tests.attendus`, `cliquet.garde-fous`). Une demande qui en
    nomme sans proposer `valider` ne peut rien autoriser, quoi que l'humain
    réponde (D-0040)."""
    from socle import checks_ratchet as cliquet, checks_tests, tests_reader as tests_lecture

    nommes = []
    fichiers = outils.fichiers_courants(projet.racine)
    for a in projet.adaptateurs:
        cfg = checks_tests.cfg_tests(projet.pour(a))
        if cfg is None:
            continue
        for chemin in outils.filtrer(fichiers, cfg.get("paths", []), cfg.get("exclude", [])):
            try:
                texte = (projet.racine / chemin).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            nommes += [f.nom for f in tests_lecture.extraire(texte, chemin, cfg)
                       if f.est_test and f.nom not in nommes and checks_tests._nomme(d.texte, f.nom)]
    nommes += [c for c in map(cliquet._cle, cliquet.aplatir(projet.garde_fous)) if c in d.texte]
    return nommes


def descriptions(bloc: str, motifs: list[re.Pattern]) -> set[str]:
    """Les identifiants décrits : une puce qui les nomme et dit, en au moins
    cinq mots, ce qu'ils sont."""
    res = set()
    for ligne in bloc.splitlines():
        if not re.match(r"^\s*[-*]\s+", ligne):
            continue
        idents = identifiants_cites(ligne, motifs)
        reste = ligne
        for i in idents:
            reste = reste.replace(i, " ")
        mots = re.findall(r"[^\W\d_]{2,}", reste)
        if len(mots) >= MOTS_DESCRIPTION_MIN:
            res |= idents
    return res


def verifier_reponse(d: Demande) -> list[str]:
    if d.reponse is None:
        return []
    fautes = []
    if d.erreur_reponse:
        return [d.erreur_reponse]
    r = d.reponse.get("reponse")
    if not r:
        fautes.append(trad("réponse sans champ `reponse`"))
    elif not d.accepte(str(r)):
        fautes.append(trad("réponse `{reponse}` absente des réponses possibles de la demande", reponse=r))
    if d.reponse.get("canal") == "conversation" and len(str(d.reponse.get("citation", "")).strip()) < 2:
        fautes.append(trad("réponse relayée depuis la conversation sans la citation exacte de l'humain"))
    attendue = d.reponse.get("empreinte", "")
    if attendue != "sha256:" + outils.sha256(d.texte):
        fautes.append(
            trad("la demande a changé après la réponse : la réponse portait sur un autre texte (une demande "
                 "répondue est gelée ; en écrire une nouvelle qui la remplace)")
        )
    return fautes


CANAUX = ("terminal", "conversation")


def ecrire_reponse(racine: Path, d: Demande, reponse: str, texte: str, par: str, date: str,
                   canal: str = "terminal", citation: str = "") -> str:
    """Écrit la réponse humaine. Refuse une réponse hors des réponses possibles.

    Deux canaux. `terminal` : l'humain lance lui-même
    `socle answer`. `conversation` : l'humain a répondu dans le chat, et
    l'agent consigne sa réponse ; il doit alors en citer le texte exact, qui
    reste dans le fichier, visible à la relecture du diff."""
    if not d.accepte(reponse):
        raise ValueError(
            trad("`{reponse}` n'est pas une réponse possible : {liste}",
                 reponse=reponse, liste=', '.join(d.reponses_possibles()))
        )
    if d.reponse is not None:
        raise ValueError(trad("{id} a déjà une réponse ({reponse})",
                              id=d.id, reponse=d.chemin_reponse))
    if canal not in CANAUX:
        raise ValueError(trad("canal inconnu : {canal}", canal=canal))
    if canal == "conversation" and len(citation.strip()) < 2:
        raise ValueError(trad("une réponse relayée cite le texte exact de l'humain (--quote ou --quote-file)"))
    cr = chemin_reponse(d.chemin)
    entete = (
        trad("# Réponse humaine donnée dans la conversation, consignée par l'agent avec\n"
             "# le texte exact de l'humain (`citation`). Relue avec le diff.\n")
        if canal == "conversation" else
        trad("# Réponse humaine, écrite par l'humain lui-même (`socle answer`).\n")
    )
    contenu = (
        entete
        + trad("# Elle porte sur le texte exact de {demande}, dont l'empreinte suit.\n", demande=Path(d.chemin).name)
        + f"reponse = {_toml_str(reponse)}\n"
        f"texte = {_toml_str(texte)}\n"
        f"par = {_toml_str(par)}\n"
        f"date = {_toml_str(date)}\n"
        f"canal = {_toml_str(canal)}\n"
        + (f"citation = {_toml_str(citation.strip())}\n" if canal == "conversation" else "")
        + f"empreinte = {_toml_str('sha256:' + outils.sha256(d.texte))}\n"
    )
    (racine / cr).write_text(contenu, encoding="utf-8")
    return cr


def reponse_de_seance(reponse: str, question: str) -> bool:
    """Une décision en séance se consigne sous une réponse de base, dans une
    langue ou l'autre, ou sous une option que la question nomme entre accents
    graves (D-0053) : le vocabulaire est celui de toute demande."""
    if langue.reponse(reponse) in langue.REPONSES:
        return True
    return outils.cle(reponse) in {outils.cle(o) for o in re.findall(r"`([^`]+)`", question)}


def titre_sans_preuve(question: str, texte: str = "") -> list[str]:
    """Les identifiants que le titre d'une décision en séance cite seul, sans
    empreinte : la question posée, recopie de la conversation, n'a pas à
    prouver ses lectures ; ce que le titre ajoute, si (B-0103). Sans texte,
    le titre est la question."""
    if not texte:
        return []
    cites = {i for i, _ in memoire.mentions(texte)} | {i for i, _, _ in memoire.citations(question)}
    return sorted({i for i, _ in memoire.mentions(question)} - cites)


def ecrire_seance(projet: config.Projet, question: str, texte: str, reponse: str, par: str, jour: str,
                  canal: str, citation: str = "", sujet: str = "") -> tuple[str, str]:
    """Une décision prise en séance : la question que l'humain a
    lue dans la conversation, avec sa réponse, d'un seul geste, dans le
    registre des demandes. Rend les chemins de la demande et de sa
    réponse."""
    from socle import identifiers as identifiants

    racine = projet.racine
    if len(question.strip()) < 10:
        raise ValueError(trad("la question doit énoncer la décision en une phrase"))
    if not reponse_de_seance(reponse, texte or question):
        lg = langue.du_projet(projet)
        raise ValueError(trad("« {reponse} » : une décision en séance se consigne sous une réponse de base ({base}), "
                              "ou sous une option que la question nomme entre accents graves ; le texte exact de "
                              "l'humain va dans la citation", reponse=reponse, base=", ".join(
                                  f"`{langue.mot(langue.REPONSES, r, lg)}`" for r in langue.REPONSES)))
    seuls = titre_sans_preuve(question, texte)
    if seuls:
        # Une fois la réponse écrite, protégée, la décision ne se corrige
        # plus : son titre se juge avant (B-0103).
        raise ValueError(trad("le titre cite {ids}, que la question posée ne cite pas : le citer avec son "
                              "empreinte (`ID@…`, que donne `socle show`), ou le nommer dans la question",
                              ids=", ".join(seuls)))
    mem = memoire.Memoire.charger(racine)
    ident = mem.prochain_id("D", date=jour, pris_ailleurs=identifiants.pris_ailleurs(racine, "D"))
    lg = langue.du_projet(projet)
    champs = {"date": jour, "forme": langue.mot(langue.VALEURS, "seance", lg)}
    if sujet:
        champs["sujet"] = sujet
    chemin = f"{projet.chemins.demandes}/{ident}-{memoire.nom_de_fichier(question)}.md"
    contenu = (f"{langue.entete_fichier('demandes', 'publique', lg)}\n# {ident} — {question.strip()}\n\n"
               f"{langue.meta(lg, **champs)}\n\n"
               f"## {langue.mot(langue.SECTIONS_SEANCE, 'question-posee', lg)}\n\n{(texte or question).strip()}\n")
    outils.ecrire(racine / chemin, contenu)
    d = charger(racine, None, chemin, contenu)
    try:
        cr = ecrire_reponse(racine, d, reponse, "", par, jour, canal=canal, citation=citation)
    except ValueError:
        (racine / chemin).unlink()
        raise
    return chemin, cr


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def validations_ajoutees(racine: Path, base: str | None, tete: str | None) -> list[Demande]:
    """Les demandes validées par une réponse AJOUTÉE dans la plage : une vieille
    validation ne couvre pas un assouplissement nouveau. Une demande se
    reconnaît à son identifiant, qui ne change pas quand un déplacement
    renomme son fichier et celui de sa réponse (relevé de la passe de
    recul, D)."""
    def cle(d: Demande) -> str:
        return d.id or d.chemin_reponse or d.chemin

    deja = {cle(d) for d in toutes(racine, base) if d.reponse is not None} if base else set()
    return [
        d for d in toutes(racine, tete)
        if d.validee and cle(d) not in deja and not verifier_reponse(d)
    ]


def illisible(projet: config.Projet, d: Demande) -> str | None:
    """Pourquoi l'humain n'a pas pu lire la demande telle qu'elle est,
    ou `None`. Au banc, un agent a écrit une demande puis y a relayé une phrase
    que l'humain avait dite avant qu'elle existe. Une demande chiffrée ne se
    lit pas sur GitHub : l'agent la donne en entier dans la conversation."""
    from socle import links as liens, private as prive

    if d.seance:
        return None  # l'humain a lu la question dans la conversation
    if memoire.est_prive(d.chemin) and prive.mode(projet) == "chiffre":
        return None
    url, avertissement = liens.lien(projet, d.chemin)
    if url is None:
        return avertissement
    if memoire.est_prive(d.chemin):
        return None  # le dépôt privé : `lien` a vérifié qu'elle y est poussée
    sha = liens.commit_pousse(projet.racine)
    if outils.lire_a(projet.racine, sha, d.chemin) != (projet.racine / d.chemin).read_text(encoding="utf-8"):
        return trad("la version poussée diffère de la version locale")
    return None
