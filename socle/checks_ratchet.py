"""Rien ne s'affaiblit en silence (principe 5).

- `cliquet.garde-fous` : tout assouplissement des garde-fous (`.socle/guardrails.toml`)
  par rapport à la base exige une demande validée dans la plage, qui cite la
  clé assouplie. Durcir est libre.
- `protege.fichiers` : un fichier protégé par la politique ne change qu'avec
  une demande validée qui cite son empreinte nouvelle.
- `moteur.empreinte` : le moteur copié dans le projet est celui que l'installeur
  a posé.
- `hooks.configuration` et `hooks.trace` : les hooks de l'agent sont déclarés,
  et ils ont réellement tiré pendant la session qui a produit chaque commit.
"""

from __future__ import annotations

import json
import re

from socle import config, fingerprint as empreinte, language as langue, memory as memoire, utils as outils
from socle.messages import a_traduire, trad
from socle.context import controle

ABSENT = object()

# (motif de clé, sens) — `bas` : plus petit est plus strict ; `vrai` : vrai
# est plus strict ; `faux` : faux ou absent est plus strict (un module « à
# mesurer » qui reçoit son plafond) ; `inclus` : une liste plus courte est
# plus stricte (des exclusions) ; `couvre` : une liste plus longue est plus
# stricte (une couverture) ; `tolere` : les constats que l'adoption tolère,
# comptés, ne peuvent que se réduire (B-0180).
REGLES = [
    (("budgets", "*", "max_bytes|max_lines"), "bas"),
    (("staleness", "active_days"), "bas"),
    (("mutation", "caps", "*", "max"), "bas"),
    (("mutation", "caps", "*", "reason"), "libre"),
    (("mutation", "caps", "*", "pending"), "faux"),
    (("nocopy", "min_chars"), "bas"),
    (("nocopy", "exclude"), "inclus"),
    (("references", "exclude"), "inclus"),
    (("references", "repos"), "inclus"),
    (("references", "scan"), "couvre"),
    (("tooling", "paths"), "couvre"),
    (("memory", "code"), "couvre"),
    (("memory", "require_update_on_code_change"), "vrai"),
    (("requests", "internal_id_patterns"), "couvre"),
    (("tests", "spec_paths"), "inclus"),
    (("tests", "case_paths"), "couvre"),
    (("specs", "paths"), "couvre"),
    (("adoption", "warn_only"), "inclus"),
    (("adoption", "tolerated", "*"), "tolere"),
    (("thirdparty", "paths"), "inclus"),
    (("branches", "disposable"), "inclus"),
]

# Une clé qui a une valeur par défaut : absente, elle la vaut, et l'écrire
# telle quelle ne change rien (D-0087).
DEFAUTS = {("branches", "disposable"): list(config.BRANCHES_JETABLES)}


def _cle(chemin: tuple[str, ...]) -> str:
    morceaux = []
    for c in chemin:
        morceaux.append(c if re.fullmatch(r"[A-Za-z0-9_-]+", c) else json.dumps(c, ensure_ascii=False))
    return ".".join(morceaux)


def aplatir(d, prefixe=()) -> dict[tuple[str, ...], object]:
    res = {}
    for k, v in d.items():
        if k in ("docmap", "values") and not prefixe:
            continue  # comparés à part
        if isinstance(v, dict):
            res.update(aplatir(v, prefixe + (k,)))
        else:
            res[prefixe + (k,)] = v
    return res


def _regle(chemin: tuple[str, ...]) -> str | None:
    """Les règles se comparent composante par composante : une clé de budget
    est un motif de chemin, qui porte lui-même des points."""
    for motif, sens in REGLES:
        if len(motif) == len(chemin) and all(
            m == "*" or re.fullmatch(m, c) for m, c in zip(motif, chemin)
        ):
            return sens
    return None


# La raison d'un plafond mesuré, écrite dans la langue du projet et lue
# dans les deux.
MESURE = re.compile(r"(?:mesuré le \d{4}-\d{2}-\d{2} : |measured on \d{4}-\d{2}-\d{2}: )(\d+) surviv")


def _mesure(apres: dict, chemin: tuple[str, ...], plafond) -> bool:
    """Un plafond qui apparaît vient de la mesure : nul (le plus strict), ou
    avec la raison qu'écrit `mutation-verdict --record`, au même compte."""
    if plafond == 0:
        return True
    m = MESURE.search(str(apres.get(chemin[:-1] + ("reason",), "")))
    return bool(m) and int(m.group(1)) == plafond


def assouplissements(avant: dict, apres: dict, modules_existants: set[str] | None = None,
                     renommes: dict[str, str] | None = None,
                     fichiers_avant: list[str] | None = None,
                     renommes_toleres: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """[(clé citable, explication)] des assouplissements de `avant` à `apres`.
    `modules_existants` : les fichiers de l'arbre jugé ; le seuil d'un fichier
    disparu se retire avec lui. `renommes` et `fichiers_avant` : les fichiers
    que la plage renomme, et ceux de la base ; une correspondance ou une
    valeur liée qui suit ses fichiers sous leur nouveau nom n'assouplit rien.
    `renommes_toleres` : ceux que suivent les clés de l'adoption, lus depuis
    la branche par défaut (B-0189) ; à défaut, `renommes`."""
    renommes = renommes or {}
    renommes_toleres = renommes if renommes_toleres is None else renommes_toleres
    res = []
    a, b = aplatir(avant), aplatir(apres)
    for chemin, defaut in DEFAUTS.items():
        a.setdefault(chemin, defaut)
        b.setdefault(chemin, defaut)
    for chemin in sorted(set(a) | set(b)):
        va, vb = a.get(chemin, ABSENT), b.get(chemin, ABSENT)
        if va == vb:
            continue
        cle = _cle(chemin)
        sens = _regle(chemin)
        if sens == "libre":
            continue
        if sens == "tolere":
            res += _toleres(cle, chemin[-1], va, vb, apres, renommes_toleres)
            continue
        if va is ABSENT:
            if chemin[:2] == ("mutation", "caps") and chemin[-1] == "max" and not _mesure(b, chemin, vb):
                res.append((cle, trad("plafond {vb} écrit sans la mesure que pose `mutation-verdict --record`",
                                      vb=repr(vb))))
                continue
            if sens in ("bas", "vrai", "couvre", "faux") or (sens == "inclus" and not vb):
                continue  # un seuil ou une couverture qui apparaît durcit
            res.append((cle, trad("clé ajoutée : {vb}", vb=repr(vb))))
            continue
        if vb is ABSENT:
            if chemin[:2] == ("mutation", "caps") and modules_existants is not None and chemin[2] not in modules_existants:
                continue  # le module a disparu : son plafond avec lui
            if chemin[0] == "budgets" and modules_existants is not None \
                    and not outils.filtrer(modules_existants, [chemin[1]]):
                continue  # plus aucun fichier sous ce motif : son budget ne couvrait plus rien
            if sens == "faux":
                continue  # « à mesurer » qui disparaît : le plafond mesuré le remplace
            res.append((cle, trad("seuil retiré (valait {va})", va=repr(va))))
            continue
        if sens == "bas" and isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if vb > va:
                res.append((cle, f"{va} → {vb}"))
        elif sens == "vrai":
            if va and not vb:
                res.append((cle, f"{va} → {vb}"))
        elif sens == "faux":
            if vb and not va:
                res.append((cle, f"{va} → {vb}"))
        elif sens == "couvre":
            retires = set(va or []) - set(vb or [])
            if retires:
                res.append((cle, trad("couverture retirée : {retires}", retires=sorted(retires))))
        elif sens == "inclus":
            ajoutes = set(vb or []) - set(va or [])
            if ajoutes:
                res.append((cle, trad("exclusion ajoutée : {ajoutes}", ajoutes=sorted(ajoutes))))
        else:
            res.append((cle, trad("changement non classé : {va} → {vb}", va=repr(va), vb=repr(vb))))

    # Chaque correspondance exige, quand son code change, l'une de ses docs :
    # une doc de plus à la liste rend l'exigence plus facile à satisfaire.
    apres_docmap = [(set(l.get("code", [])), set(l.get("docs", []))) for l in apres.get("docmap", [])]
    vus = set()
    for ligne in avant.get("docmap", []):
        docs = set(ligne.get("docs", []))
        for g in ligne.get("code", []):
            candidates = [d for c, d in apres_docmap if g in c]
            cle = f"docmap {json.dumps(g, ensure_ascii=False)}"
            if cle in vus or any(d <= docs for d in candidates) or _suivie(g, docs, apres_docmap, renommes,
                                                                          fichiers_avant):
                continue
            vus.add(cle)
            if not candidates:
                res.append((cle, trad("correspondance code ↔ doc retirée")))
            else:
                ajoutees = min((d - docs for d in candidates), key=len)
                res.append((cle, trad("docs ajoutées à la correspondance : {docs}", docs=sorted(ajoutees))))
    vals_avant = {v.get("name"): v for v in avant.get("values", [])}
    vals_apres = {v.get("name"): v for v in apres.get("values", [])}
    for nom, decl in vals_avant.items():
        if nom not in vals_apres:
            res.append((f"values {json.dumps(nom, ensure_ascii=False)}", trad("valeur liée retirée")))
        elif vals_apres[nom] != {**decl, "file": renommes.get(decl.get("file"), decl.get("file"))}:
            res.append((f"values {json.dumps(nom, ensure_ascii=False)}", trad("source de la valeur changée")))
    return res


def _toleres(cle: str, controle: str, va, vb, apres: dict,
             renommes: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """La liste des constats qu'un contrôle sous adoption tolère : qui
    apparaît, elle durcit (absente, le contrôle entier l'était) ; qui
    disparaît alors que le contrôle reste sous l'adoption, elle le désarme ;
    qui compte un constat de plus, elle assouplit, et chaque constat ajouté
    se cite à part : une demande validée n'autorise que ceux qu'elle nomme.
    Un constat dont la plage renomme le fichier, suivi sous son nouveau nom,
    n'est pas ajouté."""
    from collections import Counter

    from socle.context import cle_renommee

    if va is ABSENT:
        return []
    if vb is ABSENT or not isinstance(vb, list):
        if controle in ((apres.get("adoption") or {}).get("warn_only") or []):
            return [(cle, trad("liste des constats tolérés retirée : le contrôle entier est désarmé"))]
        return []
    avant = Counter(cle_renommee(str(k), renommes or {}) for k in (va if isinstance(va, list) else []))
    ajoutes = Counter(map(str, vb)) - avant
    return [(f"{cle} {json.dumps(k, ensure_ascii=False)}", trad("constat toléré ajouté ({n} fois)", n=n))
            for k, n in sorted(ajoutes.items())]


def _suivie(motif: str, docs: set[str], apres_docmap: list[tuple[set[str], set[str]]], renommes: dict[str, str],
            fichiers_avant: list[str] | None) -> bool:
    """Le motif d'une correspondance dont les fichiers, ou les docs, ont été
    renommés : chacun, sous son nouveau nom, reste couvert par une
    correspondance qui n'exige pas d'autre doc que les siennes, renommées
    elles aussi. Un motif qui ne couvrait rien, ou dont ni les fichiers ni
    les docs n'ont changé de nom, ne se suit pas : le retirer reste un
    assouplissement."""
    if not renommes or not fichiers_avant:
        return False
    couverts = [f for f in fichiers_avant if outils.correspond(f, [motif])]
    if not couverts or not any(f in renommes for f in couverts) and not any(d in renommes for d in docs):
        return False
    docs_suivies = {renommes.get(d, d) for d in docs}
    return all(any(outils.correspond(renommes.get(f, f), sorted(c)) and d <= docs_suivies for c, d in apres_docmap)
               for f in couverts)


def _valide_par(ctx, *citations: str):
    for d in ctx.validations:
        if all(c in d.texte for c in citations):
            return d
    return None


@controle("cliquet.garde-fous", base=True)
def cliquet(ctx, r):
    """Durcir un garde-fou est libre ; l'assouplir exige une demande validée
    qui cite la clé (politique, point 1)."""
    avant = ctx.projet_base.garde_fous if ctx.projet_base else {}
    if not avant:
        return  # installation : rien à comparer
    for cle, pourquoi in assouplissements(avant, ctx.projet.garde_fous, set(ctx.fichiers), ctx.renommes,
                                          ctx.fichiers_base, ctx.renommes_adoption):
        d = _valide_par(ctx, cle)
        if d:
            r.avertir("cliquet.garde-fous", trad("assouplissement validé par {id} : {cle} — {pourquoi}",
                                                 id=d.id, cle=cle, pourquoi=pourquoi),
                      ctx.projet.chemins.garde_fous)
        else:
            r.erreur("cliquet.garde-fous", trad("assouplissement sans validation humaine : {cle} — {pourquoi}. "
                                                "Émettre une demande qui cite `{cle}` ; elle couvrira ce "
                                                "changement une fois validée", cle=cle, pourquoi=pourquoi),
                     ctx.projet.chemins.garde_fous)


_FUSION_GARDEE: dict[str, bool] = {}


def fusion_gardee(projet: config.Projet) -> bool:
    """La branche par défaut exige la CI du socle avant toute fusion : une
    pull request rouge ne s'y fusionne pas. Demandé à GitHub une fois par
    processus ; inconnu, c'est non."""
    cle = str(projet.racine)
    if cle not in _FUSION_GARDEE:
        from socle import state as etat

        _FUSION_GARDEE[cle] = etat.ci_exigee(projet)[0] is True
    return _FUSION_GARDEE[cle]


def _en_attente(ctx, *citations: str, au_commit: bool = False):
    """Une demande en attente, poussée telle quelle, qui cite le changement
    (un fichier protégé et son empreinte nouvelle, un test) : à la fin du
    tour (étage agent), il peut rester dans l'arbre en attendant la réponse
    de l'humain, comme une mise à jour du socle en session cloud (B-0115).
    Avec `au_commit`, il se commite et se pousse aussi (étage git), si la
    branche par défaut exige la CI du socle, qui le refuse jusqu'à la
    réponse : l'humain lit les fichiers dans la pull request au lieu de
    valider des empreintes (D-0071). Le hook avant push, qui juge la plage
    comme la CI, le laisse partir lui aussi. La CI le refuse toujours."""
    from socle import requests as demandes

    pousse = au_commit and (ctx.etage == "git" or ctx.avant_push)
    if ctx.etage != "agent" and not pousse:
        return None
    for d in ctx.demandes:
        if (d.id and d.reponse is None and d.entree is not None and "retiree" not in d.entree.meta
                and all(c in d.texte for c in citations) and demandes.illisible(ctx.projet, d) is None):
            if ctx.etage != "agent" and not fusion_gardee(ctx.projet):
                return None
            return d
    return None


def installation_en_cours(racine) -> bool:
    """La branche par défaut n'a pas encore le socle : la plage, même jugée
    depuis un push qui l'a déjà posé, appartient à la pull request qui
    l'installe, et la CI de celle-ci la juge depuis la branche par défaut
    (B-0096). Une branche par défaut introuvable ou devinée ne dit rien."""
    ref = outils.branche_par_defaut(racine)
    if not ref or outils.branche_par_defaut_devinee(racine):
        return False
    return outils.lire_a(racine, ref, config.FORMAT_ACTUEL.lock) is None


@controle("protege.fichiers", base=True)
def proteges(ctx, r):
    """Un fichier protégé ne change qu'avec une demande validée qui cite son
    empreinte nouvelle (hooks, CI, politique, adaptateur, moteur)."""
    if not ctx.projet_base or not ctx.projet_base.installe:
        installes = outils.filtrer(ctx.changes, ctx.projet.chemins_proteges())
        if installes:
            r.avertir("protege.fichiers", trad("installation du socle : {n} fichier(s) protégé(s) posé(s) — la "
                                               "politique par défaut est celle du cadrage", n=len(installes)))
        return
    if installation_en_cours(ctx.racine):
        changes = outils.filtrer(ctx.changes, ctx.projet.chemins_proteges())
        if changes:
            r.avertir("protege.fichiers", trad("installation en cours : la branche par défaut n'a pas encore le "
                                               "socle, et {n} fichier(s) protégé(s) changent avant sa fusion "
                                               "({liste})", n=len(changes), liste=", ".join(changes[:5])))
        return
    motifs = sorted(set(ctx.projet.chemins_proteges()) | set(ctx.projet_base.chemins_proteges()))

    def existe(chemin: str) -> bool:
        return (ctx.racine / chemin).is_file() if ctx.tete is None else ctx.lire(chemin) is not None

    for c in outils.filtrer(ctx.changes, motifs):
        if memoire.est_reponse(c):
            continue  # les réponses sont le mécanisme de validation lui-même
        if ctx.projet.mode == config.MODE_AMONT and c.startswith(ctx.projet.dossier_moteur + "/socle/"):
            continue
        present = existe(c)
        if present and ctx.tete is None:
            cites = [empreinte.courte(empreinte.fichier(ctx.racine / c))]
        elif present:
            cites = ["sha256:" + outils.sha256(ctx.lire(c))[:16]]
        else:
            # Supprimé : le mot de l'une ou l'autre langue, celui du projet
            # d'abord, que le refus cite (B-0163).
            premier = empreinte.supprime(langue.du_projet(ctx.projet))
            cites = [premier, *(m for m in empreinte.SUPPRIME.values() if m != premier)]
        cite = cites[0]
        d = next((v for v in (_valide_par(ctx, c, x) for x in cites) if v), None)
        attente = None if d else next((a for a in (_en_attente(ctx, c, x, au_commit=True) for x in cites) if a), None)
        if d:
            r.avertir("protege.fichiers", trad("modification validée par {id}", id=d.id), c)
        elif attente and fusion_gardee(ctx.projet):
            r.avertir("protege.fichiers", trad("modification en attente de {id} : elle se commite et se pousse, "
                                               "la CI la refuse jusqu'à la réponse de l'humain, qui la lit dans "
                                               "la pull request", id=attente.id), c)
        elif attente:
            r.avertir("protege.fichiers", trad("modification en attente de {id} : le tour peut finir, le commit "
                                               "et la CI attendent la réponse de l'humain", id=attente.id), c)
        elif re.search(r"(^|/)\.claude/settings(\.local)?\.json$", c):
            # Les réglages de Claude Code restent à l'humain, remise comprise.
            r.erreur("protege.fichiers", trad("fichier protégé modifié sans validation humaine. Une demande "
                                              "validée doit citer `{fichier}` et `{cite}`", fichier=c, cite=cite), c)
        else:
            r.erreur("protege.fichiers", trad("fichier protégé modifié sans validation humaine. Une demande "
                                              "validée doit citer `{fichier}` et `{cite}`. Changé par erreur dans "
                                              "l'arbre de travail, l'agent le remet à son état du dernier commit : "
                                              "`git restore --source=HEAD --staged --worktree -- {fichier}`, ou "
                                              "`rm {fichier}` s'il est apparu sans être suivi par git (D-0098)",
                                              fichier=c, cite=cite), c)


@controle("moteur.empreinte")
def moteur(ctx, r):
    """Le moteur du projet est celui que l'installeur a posé."""
    if not ctx.projet.installe:
        r.erreur("moteur.empreinte", trad("socle non installé : `{lock}` absent (commité ? un .gitignore du "
                                          "projet peut l'écarter)", lock=ctx.projet.chemins.lock))
        return
    if ctx.projet.mode == config.MODE_AMONT:
        r.indisponible("moteur.empreinte", trad("mode amont : ce dépôt fabrique le moteur, son empreinte n'est "
                                                "pas figée"))
        return
    attendue = ctx.projet.lock.get("fingerprint")
    calculee, n = empreinte.calculer(ctx.racine, ctx.projet.dossier_moteur)
    if n == 0:
        r.erreur("moteur.empreinte", trad("moteur introuvable dans {dossier_moteur}",
                                          dossier_moteur=ctx.projet.dossier_moteur))
    elif calculee != attendue:
        r.erreur("moteur.empreinte", trad("moteur altéré : empreinte {calculee}, le verrou attend {attendue}. "
                                          "Relancer l'installeur, jamais réparer à la main",
                                          calculee=empreinte.courte(calculee), attendue=empreinte.courte(str(attendue))),
                 ctx.projet.chemins.lock)


HOOKS_REQUIS = ("SessionStart", "PreToolUse", "Stop")


@controle("hooks.configuration")
def configuration(ctx, r):
    """Les hooks de l'agent sont déclarés et appellent le moteur."""
    if not ctx.projet.pol("agents", "claude_code", defaut=True):
        return
    texte = ctx.lire(".claude/settings.json")
    if texte is None:
        r.erreur("hooks.configuration", trad("`.claude/settings.json` absent : les hooks de Claude Code ne "
                                             "sont pas déclarés"))
        return
    try:
        conf = json.loads(texte)
    except json.JSONDecodeError as e:
        r.erreur("hooks.configuration", trad("JSON illisible : {erreur}", erreur=e), ".claude/settings.json")
        return
    for evt in HOOKS_REQUIS:
        commandes = [h.get("command", "") for bloc in conf.get("hooks", {}).get(evt, []) for h in bloc.get("hooks", [])]
        if not any(".socle/socle" in c and "hook" in c for c in commandes):
            r.erreur("hooks.configuration", trad("aucun hook {evt} n'appelle `.socle/socle hook`", evt=evt), ".claude/settings.json")


def lire_trailer_hooks(valeur: str) -> dict[str, str]:
    res = {}
    for morceau in valeur.replace(",", " ").split():
        if "=" in morceau:
            k, v = morceau.split("=", 1)
            res[k] = v
    return res


# Le remède quand les hooks de l'agent ne sont pas chargés : Claude Code ne
# les lit que dans le dossier où la session démarre. L'agent ne
# pose jamais lui-même un réglage pour les rétablir.
REMEDE_HOOKS = a_traduire(
    "Claude Code ne lit ses hooks que dans le dossier où la session démarre : relancer la session depuis la "
    "racine du projet ; dans une session à plusieurs dépôts, ouvrir une session sur ce dépôt seul. L'agent "
    "n'écrit jamais lui-même un réglage de Claude Code pour les rétablir : il le dit à l'humain, et ne pousse "
    "rien. Le travail en cours, qui ne peut plus se commiter, il le montre dans la conversation (`git diff`, "
    "`git stash show -p --include-untracked`, ou le texte des fichiers nouveaux), pour que l'humain le donne à "
    "la session neuve : le conteneur peut disparaître avec lui.")


def est_agent(projet, message: str) -> bool:
    marqueurs = projet.pol("agents", "markers", defaut=[r"(?im)^co-authored-by:.*\bclaude\b", r"(?im)^socle-agent:"])
    return any(re.search(m, message) for m in marqueurs)


@controle("hooks.trace", etages=("ci",), base=True)
def trace(ctx, r):
    """Chaque commit d'agent porte la trace des hooks qui ont tiré pendant sa
    session (`Socle-Hooks:`, ajouté par le hook git). Absente, ou sans
    PreToolUse : les hooks n'ont jamais été chargés. Et depuis le commit
    précédent (`Socle-Hooks-Since-Commit:`) : sans PreToolUse, ils ont cessé
    de tirer en cours de session. Un commit qui ne touche que des chemins
    déclarés tiers n'est pas un commit du projet : l'agent d'une autre
    session, qui n'a pas les hooks du socle, l'a écrit (ADR-0031)."""
    for c in ctx.commits_du_projet:
        if len(c["parents"]) != 1 or not est_agent(ctx.projet, c["message"]):
            continue
        if outils.lire_a(ctx.racine, c["parents"][0], ctx.projet.chemins.lock) is None:
            continue  # le socle n'était pas encore installé
        sujet = c["message"].strip().splitlines()[0]
        valeurs = outils.trailers(c["message"]).get("socle-hooks")
        if not valeurs:
            r.erreur("hooks.trace", trad("{sha} « {sujet} » : commit d'agent sans trailer `Socle-Hooks` — les "
                                         "hooks git n'ont pas tourné (`git config core.hooksPath "
                                         ".socle/git-hooks`)", sha=c['sha'][:10], sujet=sujet))
            continue
        t = lire_trailer_hooks(valeurs[-1])
        depuis = outils.trailers(c["message"]).get("socle-hooks-since-commit")
        n = lire_trailer_hooks(depuis[-1]).get("PreToolUse", "0") if depuis else "1"
        if not t.get("PreToolUse", "0").isdigit() or int(t.get("PreToolUse", "0")) < 1:
            r.erreur("hooks.trace", trad("{sha} « {sujet} » : aucun PreToolUse n'a tiré pendant la session — "
                                         "les hooks de l'agent n'étaient pas chargés. {remede}",
                                         sha=c['sha'][:10], sujet=sujet, remede=trad(REMEDE_HOOKS)))
        elif not n.isdigit() or int(n) < 1:
            # Le compte de la session garde les tirs d'avant l'arrêt.
            r.erreur("hooks.trace", trad("{sha} « {sujet} » : aucun PreToolUse n'a tiré depuis le commit "
                                         "précédent — les hooks de l'agent ont cessé d'être chargés en cours "
                                         "de session. {remede}", sha=c['sha'][:10], sujet=sujet,
                                         remede=trad(REMEDE_HOOKS)))
        if t.get("SessionStart") == "0":
            r.erreur("hooks.trace", trad("{sha} « {sujet} » : le hook SessionStart n'a jamais tiré pendant la "
                                         "session", sha=c['sha'][:10], sujet=sujet))
