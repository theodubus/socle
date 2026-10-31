"""L'installeur : pose tout le dispositif en une commande, se relance pour
les mises à jour.

Ce qu'il copie et ce qu'il référence décide de tout :
- le moteur est remplacé en bloc et son empreinte enregistrée — aucun merge ;
- la mémoire, la politique, l'adaptateur et les garde-fous appartiennent au
  projet : posés s'ils manquent, jamais écrasés ;
- les hooks, la CI et CODEOWNERS sont régénérés ; leur diff passe par la
  revue humaine (fichiers protégés).

Mode adoption (projet existant) : les budgets sont fixés au niveau actuel,
et les contrôles qui échouent sur l'existant passent en avertissement
(`[adoption] warn_only`), d'où on ne les retire que pour durcir.
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

from socle import VERSION, config, fingerprint as empreinte, language as langue, messages, mutation, utils as outils
from socle import verification
from socle.messages import a_traduire, trad
from socle.report import en_echec_dans
from socle.templates import DOSSIER as MODELES, gabarit

ADAPTATEURS = Path(__file__).resolve().parent / "adapters"
DEBUT_SOCLE = config.DEBUT_SOCLE
FIN_SOCLE = "<!-- socle:fin -->"


def charger_adaptateur(nom: str) -> tuple[str, str]:
    """(texte, nom) d'un adaptateur maintenu ou d'un fichier."""
    p = Path(nom)
    if p.suffix == ".toml" and p.is_file():
        return p.read_text(encoding="utf-8"), p.stem
    q = ADAPTATEURS / f"{nom}.toml"
    if not q.is_file():
        connus = ", ".join(sorted(x.stem for x in ADAPTATEURS.glob("*.toml")))
        raise SystemExit(trad("adaptateur inconnu : {nom} (maintenus : {connus} ; sinon un chemin vers un "
                              ".toml)", nom=nom, connus=connus))
    return q.read_text(encoding="utf-8"), nom


# Le message du lanceur, tel qu'il est écrit dans son gabarit.
PYTHON_ANCIEN = a_traduire("le socle exige Python 3.11 ou plus récent (tomllib) ; trouvé : ")


def noms_d_etapes_traduits(etapes: str) -> str:
    """Les étapes de CI d'un adaptateur, le nom de chacune dans la langue des
    messages ; le reste tel quel."""
    return re.sub(r"(?m)^(\s*- name: )(.+?)\s*$", lambda m: m.group(1) + trad(m.group(2)), etapes)


# Le fichier qui dit le langage d'un dépôt, son nom ou son motif, et
# l'adaptateur maintenu qui va avec ; le premier trouvé l'emporte. Une
# solution ou un projet .NET passe avant `package.json`, qu'un projet web en
# C# porte souvent pour ses ressources.
MARQUEURS_LANGAGE = (
    (("Cargo.toml",), "rust"),
    (("pyproject.toml", "setup.py", "setup.cfg"), "python"),
    (("go.mod",), "go"),
    (("pom.xml",), "java"),
    (("Gemfile",), "ruby"),
    (("composer.json",), "php"),
    (("*.sln", "*.slnx", "*.csproj"), "csharp"),
    (("package.json",), "javascript"),
)


def langages_presents(fichiers: list[str]) -> dict[str, list[str]]:
    """Chaque langage dont le dépôt porte un fichier marqueur, à la racine ou
    plus bas, et où : l'audit de l'adaptateur les compare à celui
    qu'il couvre."""
    res: dict[str, list[str]] = {}
    for marqueurs, langage in MARQUEURS_LANGAGE:
        for f in fichiers:
            nom = f.rsplit("/", 1)[-1]
            if any(fnmatch.fnmatchcase(nom, m) for m in marqueurs) and not f.startswith(config.DOSSIER + "/"):
                res.setdefault(langage, []).append(f)
    return res


def detecter_langage(cible: Path) -> str | None:
    for fichiers, langage in MARQUEURS_LANGAGE:
        if any(p.is_file() for f in fichiers for p in cible.glob(f)):
            return langage
    return None


def detecter_adaptateur(cible: Path) -> str | None:
    """L'adaptateur maintenu qui convient au dépôt, déduit de ses fichiers ;
    `None` si rien ne le dit : la question revient alors à l'humain."""
    langage = detecter_langage(cible)
    fichiers = outils.fichiers_courants(cible)
    if langage is None and any(f.endswith(".py") for f in fichiers):
        langage = "python"
    if langage != "python":
        return langage
    indices = [f for f in fichiers if f.endswith("conftest.py") or f in ("pytest.ini", "tox.ini")]
    for f in [f for f in fichiers if f in ("pyproject.toml", "setup.cfg") or f.startswith("requirements")]:
        if "pytest" in (cible / f).read_text(encoding="utf-8", errors="replace"):
            indices.append(f)
    return "python-pytest" if indices else "python"


def politique_privee(texte: str, mode: str, relecture: str | None, demandes: bool) -> str:
    """La politique du gabarit, avec la mémoire privée choisie à
    l'installation au lieu de son exemple en commentaire."""
    bloc = f'[private]\nmode = "{mode}"\n'
    if relecture:
        bloc += f'review = "{relecture}"\n'
    bloc += f"requests = {'true' if demandes else 'false'}\n"
    debut = texte.index("# [private]\n")
    fin = texte.find("\n\n", debut)
    fin = len(texte) if fin == -1 else fin + 1
    return texte[:debut] + bloc + texte[fin:]


def _balayage_planifie(cible: Path, texte_adaptateur: str) -> tuple[bool, str]:
    """(poser, ce qu'en dit le journal) : le workflow de mutation se pose
    quand l'adaptateur déclare un balayage, sauf si un workflow du projet
    le lance déjà ; celui du socle, déjà posé, se met à jour."""
    cap = tomllib.loads(texte_adaptateur).get("capabilities", {}).get("mutation", {})
    if "command" not in cap:
        return False, ""
    flux = sorted(str(p.relative_to(cible)).replace(os.sep, "/") for p in (cible / ".github/workflows").glob("*")
                  if p.is_file()) if (cible / ".github/workflows").is_dir() else []
    if mutation.WORKFLOW in flux:
        return True, ""
    autre = mutation.workflow_de_balayage(cap, flux, lambda f: outils.lire_a(cible, None, f), sauf_le_sien=True)
    if autre:
        return False, (trad("balayage de mutation : `{autre}` le lance déjà, le socle n'en pose pas un second "
                            "; la CI vérifie qu'il tourne encore", autre=autre))
    return True, trad("balayage de mutation hebdomadaire posé : {workflow}", workflow=mutation.WORKFLOW)


def declarer_tiers(texte: str, chemins: list[str]) -> str:
    """Les garde-fous, avec ces chemins tiers ajoutés à leur liste."""
    actuels = (tomllib.loads(texte).get("thirdparty") or {}).get("paths", [])
    manquants = [c for c in chemins if c not in actuels]
    if not manquants:
        return texte
    liste = json.dumps(list(actuels) + manquants)
    if re.search(r"(?m)^\[thirdparty\]\s*$", texte):
        return re.sub(r"(?ms)^(\[thirdparty\]\s*$.*?^paths\s*=\s*)\[[^\]]*\]", lambda m: m.group(1) + liste,
                      texte, count=1)
    return texte.rstrip("\n") + "\n\n[thirdparty]\n" + f"paths = {liste}\n"


def lire_plafonds(fichier: Path) -> dict[str, dict]:
    """Des plafonds de mutation déjà mesurés, à reprendre à l'installation :
    la table `[mutation.caps]` d'un fichier TOML, chaque module avec son
    `max` entier et, s'il en a une, sa raison (B-0009). Une erreur dit ce qui
    ne va pas, avant que rien ne s'écrive."""
    try:
        caps = tomllib.loads(fichier.read_text(encoding="utf-8")).get("mutation", {}).get("caps", {})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise ValueError(trad("{fichier} illisible : {erreur}", fichier=fichier, erreur=e)) from e
    if not caps:
        raise ValueError(trad("{fichier} n'a aucune table `[mutation.caps]`", fichier=fichier))
    res = {}
    for module, c in caps.items():
        maxi = c.get("max") if isinstance(c, dict) else None
        if not isinstance(maxi, int) or isinstance(maxi, bool) or maxi < 0:
            raise ValueError(trad("{fichier} : le plafond de « {module} » n'est pas un `max` entier positif ou nul",
                                  fichier=fichier, module=module))
        res[module] = {"max": maxi, "reason": str(c.get("reason", "")).strip()}
    return res


def garde_fous_initiaux(cible: Path, texte_adaptateur: str, ch: config.Chemins = config.FORMAT_ACTUEL,
                        lg: str = "fr", plafonds: dict[str, dict] | None = None, source: str = "") -> str:
    """Les garde-fous du gabarit, avec chaque module qui porte déjà du code
    posé « à mesurer » au cliquet de mutation : une installation sur un
    projet existant finit verte, et le premier balayage pose les plafonds
    mesurés. Un module dont `plafonds` donne la mesure, faite ailleurs, la
    reprend au lieu d'attendre ce balayage (B-0009)."""
    texte = gabarit("guardrails.toml", lg)
    cap = tomllib.loads(texte_adaptateur).get("capabilities", {}).get("mutation", {})
    if "command" not in cap:
        return texte
    porte = re.compile(cap.get("has_code", r"."))
    fichiers = [f for f in outils.fichiers_courants(cible) if not f.startswith(config.DOSSIER + "/")]
    modules = [m for m in outils.filtrer(fichiers, cap.get("modules", []), cap.get("modules_exclude", []))
               if porte.search(outils.lire_a(cible, None, m) or "")]
    if not modules:
        return texte
    plafonds = plafonds or {}

    def entree(m: str) -> str:
        cle = json.dumps(m, ensure_ascii=False)
        if m not in plafonds:
            return f"{cle} = {{ pending = true }}\n"
        raison = plafonds[m]["reason"] or trad("repris de {source} à l'installation", source=source)
        return f"{cle} = {{ max = {plafonds[m]['max']}, reason = {json.dumps(raison, ensure_ascii=False)} }}\n"

    exemple = '# "src/lib.rs" = { max = 0 }\n'
    return texte.replace(exemple, exemple + "".join(entree(m) for m in sorted(modules)), 1)


def nom_de_l_humain(cible: Path, donne: str = "") -> str:
    """Le nom qui signe les réponses que l'agent relaie : celui que l'humain
    donne (`--human`), sinon son nom git. En session cloud, l'identité git du
    conteneur est celle de l'agent (« Claude »), pas celle de l'humain : elle
    ne se prend pas (B-0094)."""
    from socle import hooks

    if donne.strip():
        return donne.strip()
    if os.environ.get(hooks.SESSION_CLOUD) == "true":
        return ""
    return outils.git(cible, "config", "user.name", check=False).strip()


def politique_nom(texte: str, nom: str) -> str:
    """La politique d'un projet neuf, avec le nom de l'humain qui l'installe :
    il signe les réponses que l'agent relaie. Sans nom, la ligne
    reste en commentaire."""
    if not nom:
        return texte
    return re.sub(r'(?m)^# name = "[^"\n]*"$', lambda m: f"name = {json.dumps(nom, ensure_ascii=False)}", texte,
                  count=1)


def politique_langue(texte: str, lg: str) -> str:
    """La politique du gabarit, avec la langue de la mémoire choisie à
    l'installation au lieu de son exemple en commentaire."""
    return texte.replace('# [memory]\n# language = "fr"\n', f'[memory]\nlanguage = "{lg}"\n', 1)


def diff_politique(cible: Path) -> list[str]:
    """Ce qui sépare la politique du projet de celle du gabarit de cette
    version : affiché à la mise à jour, jamais appliqué. La politique est à
    l'humain."""
    import difflib

    p = cible / config.FORMAT_ACTUEL.politique
    if not p.is_file():
        return []
    # Le gabarit tel que l'installeur le poserait pour ce projet : dans sa
    # langue, qu'il écrit dans la politique.
    lg = langue.du_projet(config.Projet.charger(cible))
    gab = gabarit("policy.toml", lg)
    gab = politique_langue(gab, lg) if lg != "fr" else gab
    # Le nom de l'humain, que l'installeur y a écrit, n'est pas un écart.
    gab = politique_nom(gab, str(config.Projet.charger(cible).pol("human", "name", defaut="") or ""))
    projet, gab = p.read_text(encoding="utf-8").splitlines(), gab.splitlines()
    return list(difflib.unified_diff(projet, gab, trad("politique du projet"), trad("gabarit de cette version"),
                                     lineterm=""))


def _refus_cible(cible: Path) -> str | None:
    """Pourquoi le socle ne s'installe pas là, ou `None`."""
    if not outils.est_depot(cible):
        return trad("{cible} n'est pas un dépôt git", cible=cible)
    haut = outils.git(cible, "rev-parse", "--show-toplevel", check=False).strip()
    if haut and Path(haut).resolve() != cible.resolve():
        # Les hooks git (core.hooksPath) et le workflow de CI ne se lisent
        # qu'à la racine du dépôt : posés plus bas, ils ne tireraient pas.
        return trad("{cible} n'est pas la racine du dépôt git ({haut}) ; le socle s'installe à la racine",
                    cible=cible, haut=haut)
    return None


def _poser_moteur(cible: Path, mode: str, source: Path, ch: config.Chemins) -> tuple[str, list[str]]:
    """Le moteur, remplacé en bloc, et son verrou ; rend le dossier du moteur."""
    journal = []
    # 1. Le moteur, remplacé en bloc.
    if mode == config.MODE_AMONT:
        dossier_moteur = str(source.relative_to(cible)) if source.is_relative_to(cible) else "engine"
    else:
        dossier_moteur = ch.moteur
        dest = cible / dossier_moteur / "socle"
        if dest.exists() and dest.resolve() == (source / "socle").resolve():
            # Lancé depuis le projet lui-même : la source est la destination,
            # et la supprimer avant la copie effaçait le moteur.
            journal.append(trad("moteur déjà en place dans {dossier_moteur}/socle (installeur lancé depuis le "
                                "projet) : conservé ; pour une autre version, lancer l'installeur depuis le "
                                "clone du socle", dossier_moteur=dossier_moteur))
        else:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source / "socle", dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".*"))
            journal.append(trad("moteur {version} copié dans {dossier_moteur}/socle", version=VERSION,
                                dossier_moteur=dossier_moteur))
    # Le message du lanceur sous un Python trop ancien s'écrit avant que le
    # moteur ne se charge : il prend la langue du projet ici.
    outils.ecrire(cible / config.LANCEUR, gabarit("launcher.py").replace(PYTHON_ANCIEN, trad(PYTHON_ANCIEN)),
                  executable=True)

    # 2. Le verrou et son empreinte. En mode amont, le moteur est la source :
    # une empreinte figée y changerait à chaque modification du moteur, et
    # ferait de chacune un changement de fichier protégé.
    if mode == config.MODE_AMONT:
        outils.ecrire(cible / ch.lock, (
            trad("# Verrou du moteur — écrit par l'installeur, jamais à la main.\n"
                 "# Mode amont : ce dépôt fabrique le moteur, dont l'empreinte n'est pas figée ici.\n")
            + f'mode = "{mode}"\n'
            f'engine_dir = "{dossier_moteur}"\n'
            f"format = {config.FORMAT}\n"
        ))
        journal.append(trad("verrou en mode amont : le moteur est la source, sous {dossier_moteur}/socle",
                            dossier_moteur=dossier_moteur))
    else:
        calculee, n = empreinte.calculer(cible, dossier_moteur)
        outils.ecrire(cible / ch.lock, (
            trad("# Verrou du moteur — écrit par l'installeur, jamais à la main.\n"
                 "# La CI recalcule l'empreinte ; un moteur altéré dans le projet fait échouer "
                 "`moteur.empreinte`.\n")
            + f'version = "{VERSION}"\n'
            f'mode = "{mode}"\n'
            f'engine_dir = "{dossier_moteur}"\n'
            f'fingerprint = "{calculee}"\n'
            f"files = {n}\n"
            f"format = {config.FORMAT}\n"
        ))
        journal.append(trad("verrou : {empreinte} sur {n} fichiers", empreinte=empreinte.courte(calculee), n=n))

    return dossier_moteur, journal


def _poser_configuration(cible: Path, texte_adaptateur: str, ancien: dict, prive: str | None,
                         relecture: str | None, demandes_privees: bool,
                         langue_memoire: str | None, ch: config.Chemins,
                         plafonds: dict[str, dict] | None = None, source: str = "",
                         humain: str = "") -> tuple[str, list[str]]:
    """La politique, l'adaptateur et les garde-fous, posés s'ils manquent ;
    rend la langue de la mémoire."""
    journal = []
    neuf = not (cible / ch.politique).is_file()
    politique = gabarit("policy.toml", langue_memoire if langue_memoire and neuf else "fr")
    if prive:
        politique = politique_privee(politique, prive, relecture, demandes_privees)
    if langue_memoire and not (cible / ch.politique).is_file():
        politique = politique_langue(politique, langue_memoire)
    if neuf:
        politique = politique_nom(politique, nom_de_l_humain(cible, humain))
    # La langue de la mémoire : celle choisie ici pour un projet neuf, sinon
    # celle que sa politique dit déjà.
    lg = langue_memoire if langue_memoire and not (cible / ch.politique).is_file() else (
        langue.du_projet(config.Projet.charger(cible)) if (cible / ch.politique).is_file() else "fr")
    # Une mémoire privée demandée sur un projet déjà installé : la politique
    # existe et se garde, mais c'est l'humain qui lance la commande, et sans
    # sa section la mémoire privée resterait « non configurée ».
    # Une section déjà là est un choix fait : elle ne se réécrit pas.
    p_pol = cible / ch.politique
    if prive and p_pol.is_file():
        texte_pol = p_pol.read_text(encoding="utf-8")
        if not re.search(r"(?m)^\[private\]\s*$", texte_pol):
            if "# [private]\n" in texte_pol:
                texte_pol = politique_privee(texte_pol, prive, relecture, demandes_privees)
            else:
                texte_pol = politique_privee(texte_pol.rstrip("\n") + "\n\n# [private]\n", prive, relecture,
                                             demandes_privees)
            p_pol.write_text(texte_pol, encoding="utf-8")
            journal.append(trad("mémoire privée ajoutée à la politique ({prive}) : un changement protégé, à "
                                "approuver", prive=prive))
    if ancien and (cible / ch.politique).is_file():
        ecart = diff_politique(cible)
        if ecart:
            journal.append(trad("la politique du projet diffère du gabarit de cette version ; rien n'est écrit, "
                                "elle est à l'humain — à relire :\n      {ecart}", ecart="\n      ".join(ecart)))
    for nom, contenu in (
        (ch.politique, politique),
        (ch.adaptateur, texte_adaptateur),
        (ch.garde_fous, garde_fous_initiaux(cible, texte_adaptateur, ch, lg, plafonds, source)),
    ):
        p = cible / nom
        if p.is_file():
            journal.append(trad("{nom} existe : conservé (comparer au gabarit à la main si besoin)", nom=nom))
            if nom == ch.garde_fous and plafonds:
                journal.append(trad("!! plafonds de {source} non repris : les garde-fous existent déjà",
                                    source=source))
        else:
            outils.ecrire(p, contenu)
            journal.append(trad("{nom} posé", nom=nom))
            if nom == ch.garde_fous and plafonds:
                poses = tomllib.loads(contenu).get("mutation", {}).get("caps", {})
                repris = [m for m in plafonds if "max" in poses.get(m, {})]
                journal.append(trad("plafonds de mutation repris de {source} : {n}", source=source, n=len(repris)))
                ecartes = sorted(set(plafonds) - set(repris))
                if ecartes:
                    journal.append(trad("!! plafonds de {source} écartés, faute d'un module de ce nom qui porte du "
                                        "code : {liste}", source=source, liste=", ".join(ecartes)))
    return lg, journal


def _poser_memoire(cible: Path, lg: str, nom_adaptateur: str, adoption: bool, ch: config.Chemins) -> list[str]:
    """La mémoire initiale : chaque couche absente, et le journal ouvert."""
    journal = []
    jour = date.today().isoformat()
    for nom, lieu in (("canonical.md", ch.canonique), ("active.md", ch.actif)):
        p = cible / lieu
        if not p.is_file():
            outils.ecrire(p, gabarit(f"memory/{nom}", lg))
    # Le backlog est un dossier, un fichier par sujet.
    for lieu in (ch.decisions, ch.demandes, ch.backlog):
        d = cible / lieu
        d.mkdir(parents=True, exist_ok=True)
        if not any(d.iterdir()):
            outils.ecrire(d / ".gitkeep", "")
    jdir = cible / ch.journal
    if not jdir.is_dir() or not any(jdir.glob("*.md")):
        from socle import memory as memoire

        ident = memoire.Memoire.charger(cible).prochain_id("J", date=jour)
        outils.ecrire(jdir / f"{jour[:7]}.md", gabarit("memory/journal.md", lg)
                .replace("@@MOIS@@", jour[:7]).replace("@@ID@@", ident).replace("@@VERSION@@", VERSION)
                .replace("@@ADAPTATEUR@@", nom_adaptateur)
                .replace("@@ADOPTION@@", ("" if not adoption else ", in adoption mode" if lg == "en"
                                          else ", en mode adoption")))
        journal.append(trad("mémoire initiale posée, journal ouvert par {ident}", ident=ident))

    return journal


# Le dossier des skills de Claude Code ; un autre agent les lit à ces
# chemins, que les instructions donnent.
SKILLS = ".claude/skills"


def poser_skills(cible: Path, lg: str = "fr") -> list[str]:
    """Les skills du socle, dans la langue de la mémoire : ses procédures
    rares, que l'agent charge sur leur description au lieu de les relire à
    chaque session (ADR-0034). Posés par l'installeur comme les hooks, et
    remplacés à chaque mise à jour."""
    noms = []
    for dossier in sorted(p for p in (MODELES / "skills").iterdir() if p.is_dir()):
        outils.ecrire(cible / SKILLS / dossier.name / "SKILL.md", gabarit(f"skills/{dossier.name}/SKILL.md", lg))
        noms.append(dossier.name)
    return [trad("skills du socle posés dans {dossier} : {noms}", dossier=SKILLS, noms=", ".join(noms))]


def _poser_etages(cible: Path, texte_adaptateur: str, dossier_moteur: str, proprietaire: str,
                  balayage: bool, motif: str, ch: config.Chemins, lg: str = "fr") -> list[str]:
    """Les étages d'application : hooks de l'agent, hooks git, CI, balayage
    de mutation, CODEOWNERS, .gitignore. Les workflows sont dans la langue de
    la mémoire."""
    journal = []
    journal += _settings(cible)
    journal += poser_skills(cible, lg)
    for h in (MODELES / "git-hooks").iterdir():
        outils.ecrire(cible / config.GIT_HOOKS / h.name, h.read_text(encoding="utf-8"), executable=True)
    if outils.git(cible, "config", "--get", "core.hooksPath", check=False).strip() in ("", config.GIT_HOOKS):
        outils.git(cible, "config", "core.hooksPath", config.GIT_HOOKS)
        journal.append(trad("hooks git branchés (core.hooksPath)"))
    else:
        journal.append(trad("!! core.hooksPath pointe ailleurs : hooks git NON branchés"))
    setup = noms_d_etapes_traduits(tomllib.loads(texte_adaptateur).get("ci_setup", ""))
    etapes = setup.strip("\n") + "\n" if setup.strip() else ""
    workflow = gabarit("socle.yml", lg).replace("@@ETAPES_ADAPTATEUR@@\n", etapes)
    # Le nom du travail est celui qu'une protection de branche exige : une
    # mise à jour garde celui qui est en place, quelle que soit la langue.
    existant = cible / ".github/workflows/socle.yml"
    avant = outils.nom_du_travail(existant.read_text(encoding="utf-8")) if existant.is_file() else None
    nouveau = outils.nom_du_travail(workflow)
    if avant and nouveau and avant != nouveau:
        workflow = workflow.replace(f"    name: {nouveau}\n", f"    name: {avant}\n", 1)
        journal.append(trad("nom du travail de CI gardé : « {nom} », celui qu'une protection de branche exige "
                            "peut-être", nom=avant))
    outils.ecrire(cible / ".github/workflows/socle.yml", workflow)
    if balayage:
        installation = tomllib.loads(texte_adaptateur).get("capabilities", {}).get("mutation", {}).get("install", "")
        # En bloc littéral : la commande peut porter ce que YAML lirait autrement.
        etape = (f"      - name: {trad('Outil de mutation')}\n        run: |\n          {installation}\n"
                 if installation else "")
        outils.ecrire(cible / mutation.WORKFLOW, gabarit("mutation.yml", lg).replace("@@ETAPES_ADAPTATEUR@@\n", etapes)
                .replace("@@INSTALLATION@@\n", etape))
    if motif:
        journal.append(motif)
    journal += _codeowners(cible, proprietaire)
    journal += _gitignore(cible)
    journal += _non_ignores(cible, [config.LANCEUR, ch.lock, ch.politique, ch.adaptateur, ch.garde_fous,
                                    f"{config.GIT_HOOKS}/pre-commit", ".github/workflows/socle.yml", mutation.WORKFLOW,
                                    ".claude/settings.json", f"{SKILLS}/socle-request/SKILL.md", config.INSTRUCTIONS,
                                    "CLAUDE.md", ch.canonique,
                                    f"{dossier_moteur}/socle/cli.py"])
    return journal


def installer(cible: Path, adaptateur: str, proprietaire: str = "", adoption: bool = False,
              mode: str = config.MODE_PROJET, source: Path | None = None, prive: str | None = None,
              relecture: str | None = None, demandes_privees: bool = False, filtre: str = "git-crypt",
              langue_memoire: str | None = None, plafonds: Path | None = None, humain: str = "") -> int:
    """Installe ou met à jour le socle dans `cible`. Ses messages sont dans la
    langue de la mémoire du projet : celle qu'il a déjà, ou celle choisie pour
    un projet neuf."""
    existant = (cible / config.FORMAT_ACTUEL.politique).is_file()
    lg = langue.du_projet(config.Projet.charger(cible)) if existant else (langue_memoire or "fr")
    with messages.dans(lg):
        # Les plafonds déjà mesurés se lisent avant que rien ne s'écrive.
        try:
            caps = lire_plafonds(plafonds) if plafonds else None
        except ValueError as e:
            print(trad("refus : {erreur}", erreur=e), file=sys.stderr)
            return 2
        return _installer(cible, adaptateur, proprietaire, adoption, mode, source, prive, relecture,
                          demandes_privees, filtre, langue_memoire, caps, plafonds.name if plafonds else "",
                          humain)


def _installer(cible: Path, adaptateur: str, proprietaire: str, adoption: bool, mode: str, source: Path | None,
               prive: str | None, relecture: str | None, demandes_privees: bool, filtre: str,
               langue_memoire: str | None, plafonds: dict[str, dict] | None = None, source_plafonds: str = "",
               humain: str = "") -> int:
    ch = config.FORMAT_ACTUEL

    refus = _refus_cible(cible)
    if refus:
        print(trad("refus : {refus}", refus=refus), file=sys.stderr)
        return 2
    source = source or Path(__file__).resolve().parent.parent
    if adaptateur == "auto":
        detecte = detecter_adaptateur(cible)
        if detecte is None:
            connus = "|".join(sorted(x.stem for x in ADAPTATEURS.glob("*.toml")))
            print(trad("refus : langage non détecté (aucun de Cargo.toml, pyproject.toml, go.mod, pom.xml, "
                       "Gemfile, composer.json, *.sln, *.csproj, package.json, ni fichier Python) : le demander "
                       "à l'humain, puis `--adapter <{connus}>` ou le chemin d'un .toml", connus=connus), file=sys.stderr)
            return 2
        adaptateur = detecte
    texte_adaptateur, nom_adaptateur = charger_adaptateur(adaptateur)
    ancien = config.Projet.charger(cible).lock if (cible / config.FORMAT_ACTUEL.lock).is_file() else {}
    try:
        tomllib.loads(texte_adaptateur)
    except tomllib.TOMLDecodeError as e:
        print(trad("refus : adaptateur « {nom} » illisible : {erreur}", nom=nom_adaptateur, erreur=e),
              file=sys.stderr)
        return 2
    journal = [trad("adaptateur : {nom}", nom=nom_adaptateur)
               + (trad(" (détecté)") if adaptateur != nom_adaptateur else "")]
    if ancien:
        journal.append(trad("mise à jour : moteur {avant} → {version}", avant=ancien.get("version", "amont"),
                            version=VERSION))
        # Les sujets clos quittent les ouverts : une fois, à la
        # mise à jour, puis par `socle archive`.
        from socle import archive as archivage, memory as memoire

        ranges = archivage.ranger_backlog(cible)
        if ranges:
            journal.append(trad("backlog : {n} sujet(s) clos rangé(s) dans `{dossier}/`", n=len(ranges),
                                dossier=memoire.DOSSIER_CLOS))

    # 1. Le moteur, remplacé en bloc, et son verrou.
    dossier_moteur, poses = _poser_moteur(cible, mode, source, ch)
    journal += poses

    # 2. Les fichiers du projet : posés s'ils manquent, jamais écrasés.
    lg, poses = _poser_configuration(cible, texte_adaptateur, ancien, prive, relecture, demandes_privees,
                                     langue_memoire, ch, plafonds, source_plafonds, humain)
    journal += poses

    # 3. La mémoire initiale.
    journal += _poser_memoire(cible, lg, nom_adaptateur, adoption, ch)

    # 4. Les instructions : AGENTS.md fait foi, CLAUDE.md l'importe.
    balayage, motif = _balayage_planifie(cible, texte_adaptateur)
    journal += _instructions(cible, dossier_moteur, lg, balayage, ch)

    # 5. Les étages d'application.
    journal += _poser_etages(cible, texte_adaptateur, dossier_moteur, proprietaire, balayage, motif, ch, lg)
    if prive:
        journal += _prive(cible, prive, filtre)

    # 6. La trace : l'installation se voit dans `Socle-Hooks` d'une session
    # en cours (SessionStart a tiré avant que le hook n'existe).
    from socle.hooks import tracer

    tracer(cible, "Install", "", VERSION)

    # 7. Adoption : budgets au niveau actuel, contrôles en échec en avertissement.
    if adoption:
        journal += _adopter(cible)

    print(trad("socle {version} installé dans {cible}", version=VERSION, cible=cible))
    for l in journal:
        print(f"  - {l}")
    print(trad("\nAudit :"))
    code, echecs = _audit(cible)
    print(trad("\nEt maintenant :"))
    for i, etape in enumerate(et_maintenant(cible, bool(ancien), echecs), 1):
        print(f"  {i}. {etape}")
    return code


# La ligne qui nomme le balayage planifié, là où l'installeur le pose : un
# chemin cité qui n'existe pas serait refusé.
LIGNE_MUTATION = {
    "fr": "| `.github/workflows/socle-mutation.yml` | balayage de mutation, chaque semaine : les survivants de chaque "
          "module contre son plafond ; une issue s'ouvre quand le cliquet casse, et la CI dit quand il cesse de "
          "tourner |\n",
    "en": "| `.github/workflows/socle-mutation.yml` | weekly mutation sweep: each module's survivors against its cap; "
          "an issue opens when the ratchet breaks, and the CI says when it stops running |\n",
}


def _instructions(cible: Path, dossier_moteur: str, lg: str = "fr", balayage: bool = False,
                  ch: config.Chemins = config.FORMAT_ACTUEL) -> list[str]:
    res = []
    agents = cible / config.INSTRUCTIONS
    claude = cible / "CLAUDE.md"
    backlog = ch.backlog + "/"
    section = (gabarit("AGENTS.md", lg).replace("@@VERSION@@", VERSION).replace("@@MOTEUR@@", dossier_moteur)
               .replace("@@BACKLOG@@", backlog)
               .replace("@@LIGNE_MUTATION@@\n", LIGNE_MUTATION.get(lg, LIGNE_MUTATION["fr"]) if balayage else ""))
    socle = section.split("@@SECTION_PROJET@@", 1)[1].strip("\n")
    bloc = f"{DEBUT_SOCLE}\n\n{socle}\n\n{FIN_SOCLE}\n"
    if not agents.is_file() and claude.is_file() and claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
        dependants = _qui_nomme(cible, "CLAUDE.md")
        if dependants:
            # Le renommer casserait le projet : ses propres fichiers le lisent
            #. La section du socle va dans
            # CLAUDE.md, et le renommage devient une décision humaine.
            _section_dans(claude, bloc)
            res.append(trad("!! CLAUDE.md gardé : {n} fichier(s) du projet le nomment ({liste}) ; le renommer en "
                            "AGENTS.md est une décision humaine — section du socle ajoutée à CLAUDE.md",
                            n=len(dependants),
                            liste=", ".join(dependants[:5]) + (" …" if len(dependants) > 5 else "")))
            return res
    if not agents.is_file():
        if claude.is_file() and claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
            # Le CLAUDE.md existant devient AGENTS.md, historique compris.
            if not outils.git_reussit(cible, "mv", "CLAUDE.md", config.INSTRUCTIONS):
                shutil.move(str(claude), str(agents))
            res.append(trad("CLAUDE.md existant renommé en AGENTS.md (il fait foi désormais)"))
            texte = agents.read_text(encoding="utf-8").rstrip("\n") + "\n\n"
        else:
            texte = trad("# {nom}\n\nÀ compléter : ce que fait le projet, sa structure, ses commandes.\n\n",
                         nom=cible.name)
        agents.write_text(texte + bloc, encoding="utf-8")
        res.append(trad("AGENTS.md posé"))
    else:
        res.append(_section_dans(agents, bloc))
    # Un CLAUDE.md qui dit autre chose que l'import : son contenu, propre au
    # projet, passe dans AGENTS.md, qui fait foi, au lieu d'être écrasé.
    ancien = claude.read_text(encoding="utf-8") if claude.is_file() else ""
    propre = "\n".join(l for l in ancien.splitlines() if l.strip() != "@AGENTS.md").strip()
    if propre:
        texte = agents.read_text(encoding="utf-8")
        ajout = trad("## Repris de CLAUDE.md\n\n{propre}\n\n", propre=propre)
        texte = (texte.replace(DEBUT_SOCLE, ajout + DEBUT_SOCLE, 1) if DEBUT_SOCLE in texte
                 else texte.rstrip("\n") + "\n\n" + ajout)
        agents.write_text(texte, encoding="utf-8")
        res.append(trad("le contenu de CLAUDE.md, propre au projet, est repris dans AGENTS.md, qui fait foi ; "
                        "CLAUDE.md n'importe plus qu'AGENTS.md"))
    claude.write_text("@AGENTS.md\n", encoding="utf-8")
    return res


def _section_dans(fichier: Path, bloc: str) -> str:
    """Pose ou régénère la section du socle entre ses marqueurs."""
    texte = fichier.read_text(encoding="utf-8")
    if DEBUT_SOCLE in texte and FIN_SOCLE in texte:
        avant, reste = texte.split(DEBUT_SOCLE, 1)
        apres = reste.split(FIN_SOCLE, 1)[1]
        fichier.write_text(avant + bloc.rstrip("\n") + apres, encoding="utf-8")
        return trad("section du socle de {fichier} régénérée", fichier=fichier.name)
    fichier.write_text(texte.rstrip("\n") + "\n\n" + bloc, encoding="utf-8")
    return trad("section du socle ajoutée à {fichier}", fichier=fichier.name)


def _qui_nomme(cible: Path, nom: str) -> list[str]:
    """Les fichiers du projet, hors documentation et hors socle, qui citent `nom`."""
    res = []
    for c in outils.fichiers_courants(cible):
        if c.endswith(".md") or c.startswith((".socle/", ".git/")):
            continue
        p = cible / c
        if outils.est_texte(p) and nom in p.read_text(encoding="utf-8", errors="replace"):
            res.append(c)
    return res


def _settings(cible: Path) -> list[str]:
    p = cible / ".claude/settings.json"
    modele = json.loads(gabarit("settings.json"))
    if p.is_file():
        try:
            conf = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [trad("!! .claude/settings.json illisible : hooks NON déclarés")]
    else:
        conf = {"$schema": modele["$schema"]}
    hooks = conf.setdefault("hooks", {})
    for evt, blocs in modele["hooks"].items():
        existants = hooks.setdefault(evt, [])
        # Les blocs du socle sont remplacés, ceux du projet gardés.
        existants[:] = [b for b in existants
                        if not any(".socle/socle hook" in h.get("command", "") for h in b.get("hooks", []))]
        existants.extend(blocs)
    outils.ecrire(p, json.dumps(conf, ensure_ascii=False, indent=2) + "\n")
    res = [trad("hooks de Claude Code déclarés dans .claude/settings.json")]
    propres = etats_du_projet(conf)
    if propres:
        # Chaque session recevrait alors deux états, qui se recoupent.
        res.append(trad("!! le projet a déjà son propre état au démarrage ({commandes}) : chaque session reçoit "
                        "aussi celui du socle, et les deux se recoupent (branche, commits, ce qui revient à "
                        "l'humain). Pour n'en garder qu'un, l'humain retire le sien de .claude/settings.json, ou "
                        "n'y laisse que ce qui est propre au projet", commandes=", ".join(propres)))
    return res


def etats_du_projet(conf: dict) -> list[str]:
    """Les commandes `SessionStart` que le projet déclare lui-même, à côté de
    celle du socle."""
    return [h.get("command", "") for b in (conf.get("hooks") or {}).get("SessionStart", [])
            for h in b.get("hooks", []) if h.get("command") and ".socle/socle hook" not in h["command"]]


def _codeowners(cible: Path, proprietaire: str) -> list[str]:
    p = cible / ".github/CODEOWNERS"
    if not proprietaire:
        return [trad("!! aucun propriétaire (--owner) : CODEOWNERS non posé — la politique n'est protégée que "
                     "par la CI")]
    lignes = gabarit("CODEOWNERS").replace("@@OWNER@@", proprietaire).splitlines()
    existant = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    ajout = [l for l in lignes if l not in existant]
    outils.ecrire(p, "\n".join(existant + ajout).strip("\n") + "\n")
    return [trad("CODEOWNERS : {proprietaire} sur la politique, les hooks et la CI", proprietaire=proprietaire)]


def _gitignore(cible: Path) -> list[str]:
    p = cible / ".gitignore"
    existant = p.read_text(encoding="utf-8") if p.is_file() else ""
    # Le commentaire renvoie au fichier d'instructions qui fait foi : CLAUDE.md
    # quand l'installeur l'a gardé ; celui d'une installation
    # antérieure compte, quel que soit le fichier qu'il nomme.
    source = config.INSTRUCTIONS if (cible / config.INSTRUCTIONS).is_file() else "CLAUDE.md"
    commentaire = trad("# Trace locale des hooks du socle")
    # Le commentaire d'une installation dans une autre langue compte aussi.
    deja = any(l.startswith(("# Trace locale des hooks du socle", commentaire)) for l in existant.splitlines())
    outils.ajouter_lignes(p, ["/.socle/trace/", "__pycache__/"], "" if deja else trad("{commentaire} (voir {source})", commentaire=commentaire, source=source))
    return []


def _non_ignores(cible: Path, chemins: list[str]) -> list[str]:
    """Ce que le socle pose ne doit pas être ignoré par le `.gitignore` du
    projet (un `*.lock` gardait le verrou hors des commits) : une exception
    s'ajoute pour chaque fichier ignoré, et ce qu'elle ne suffit pas à
    rendre (un dossier parent ignoré) se dit."""
    def ignores() -> list[str]:
        presents = [c for c in chemins if (cible / c).exists()]
        if not presents:
            return []
        r = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=cible, input="\n".join(presents),
                           capture_output=True, text=True)
        return [l for l in r.stdout.splitlines() if l.strip()]

    pris = ignores()
    if not pris:
        return []
    outils.ajouter_lignes(cible / ".gitignore", [f"!/{c}" for c in pris], trad("# Le socle : ses fichiers se commitent"))
    restes = ignores()
    res = [trad(".gitignore : {n} fichier(s) du socle n'y sont plus ignorés", n=len(pris) - len(restes))]
    if restes:
        res.append(trad("!! encore ignorés par le .gitignore du projet, un dossier parent sans doute : {liste} "
                        "— à rendre à la main, sans quoi ils ne seront pas commités", liste=', '.join(restes)))
    return res


def _prive(cible: Path, mode: str, filtre: str) -> list[str]:
    """La mémoire privée : le clone du dépôt privé et son verrou, ou le
    filtre de chiffrement ; puis l'accès, vérifié."""
    from socle import private as prive

    res = []
    zone = prive.dossier(cible)
    if mode == "compagnon":
        outils.ajouter_lignes(cible / ".gitignore", [f"{zone}/"], trad("# Le clone du dépôt privé (mémoire privée)"))
        sha = prive.commit_compagnon(cible)
        if sha:
            prive.ecrire_verrou(cible, sha)
            res.append(trad("mémoire privée (compagnon) : dépôt privé trouvé, verrou à {sha}", sha=sha[:10]))
        else:
            res.append(trad("!! mémoire privée (compagnon) : dépôt privé absent — le mettre en place : "
                            "`python3 .socle/socle private install --repo <adresse du dépôt privé>`"))
    else:
        p = cible / ".gitattributes"
        texte = p.read_text(encoding="utf-8") if p.is_file() else ""
        ligne = f"{zone}/** filter={filtre} diff={filtre}"
        if not any(l.startswith(f"{zone}/**") for l in texte.splitlines()):
            p.write_text(texte.rstrip("\n") + ("\n" if texte.strip() else "") + ligne + "\n", encoding="utf-8")
        if outils.git(cible, "config", "--get", f"filter.{filtre}.clean", check=False).strip():
            res.append(trad("mémoire privée (chiffrée) : filtre « {filtre} » configuré", filtre=filtre))
        else:
            res.append(trad("!! mémoire privée (chiffrée) : filtre « {filtre} » non configuré ici — "
                            "l'initialiser (`{filtre} init`, ou l'équivalent de l'outil) avant d'écrire du "
                            "privé ; `prive.chiffre` refusera tout fichier privé commité en clair",
                            filtre=filtre))
    return res


def _adopter(cible: Path) -> list[str]:
    """Plafonds au niveau actuel ; les contrôles en échec passent en
    avertissement, liste d'où l'on ne retire que pour durcir."""
    from socle import context as contexte

    gf = cible / config.FORMAT_ACTUEL.garde_fous
    texte = gf.read_text(encoding="utf-8")
    res = []
    claude = cible / "CLAUDE.md"
    if claude.is_file() and claude.read_text(encoding="utf-8").strip() != "@AGENTS.md" and '"CLAUDE.md"' not in texte:
        # Gardé comme source le temps du renommage : il a son budget, au niveau actuel.
        taille = int(math.ceil(len(claude.read_bytes()) / 1000.0) * 1000)
        texte = texte.replace("[budgets]\n", f'[budgets]\n"CLAUDE.md" = {{ max_bytes = {taille} }}\n', 1)
        res.append(trad("budget de CLAUDE.md, gardé comme source : {taille} octets (il ne pourra que baisser)",
                        taille=taille))
    gf.write_text(texte, encoding="utf-8")
    projet = config.Projet.charger(cible)
    for motif, b in (projet.gf("budgets", defaut={}) or {}).items():
        tailles = [len((cible / c).read_bytes()) for c in outils.filtrer(outils.fichiers_courants(cible), [motif])]
        if tailles and max(tailles) > b.get("max_bytes", 0):
            nouveau = int(math.ceil(max(tailles) / 1000.0) * 1000)
            texte = re.sub(rf'^("{re.escape(motif)}"\s*=\s*\{{\s*max_bytes\s*=\s*)\d+', rf"\g<1>{nouveau}", texte, flags=re.M)
            res.append(trad("budget de {motif} fixé au niveau actuel : {nouveau} octets (il ne pourra que "
                            "baisser)", motif=motif, nouveau=nouveau))
    gf.write_text(texte, encoding="utf-8")
    projet = config.Projet.charger(cible)
    rapport = contexte.executer(contexte.Contexte(projet, etage="ci", base=None))
    en_echec = [c for c in rapport.controles_en_echec() if c != "config"]
    if en_echec:
        texte = gf.read_text(encoding="utf-8").rstrip("\n")
        deja = projet.gf("adoption", "warn_only", defaut=None)
        if deja is not None:
            # Une adoption déjà faite : sa liste se complète à sa place, une
            # seconde table `[adoption]` rendrait le fichier illisible.
            liste = json.dumps(list(deja) + [c for c in en_echec if c not in deja])
            texte = re.sub(r"(?ms)^(warn_only\s*=\s*)\[[^\]]*\]", lambda m: m.group(1) + liste, texte, count=1)
        else:
            texte += ("\n\n[adoption]\n" + trad("# Contrôles en échec sur l'existant, passés en avertissement. En "
                                                "retirer un\n# durcit (libre) ; en ajouter un assouplit (demande "
                                                "validée).\n") + f"warn_only = {json.dumps(en_echec)}")
        gf.write_text(texte + "\n", encoding="utf-8")
        res.append(trad("adoption : {n} contrôle(s) en avertissement : {liste}",
                        n=len(en_echec), liste=', '.join(en_echec)))
    return res


def _audit(cible: Path) -> tuple[int, list[str]]:
    """Les contrôles de la CI, en bref : ce qui échoue ou avertit. Rend le
    code de sortie et les contrôles en échec."""
    r = subprocess.run([sys.executable, str(cible / config.LANCEUR), "check", "--stage", "ci", "--short"],
                       cwd=cible, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr)
    return r.returncode, en_echec_dans(r.stdout)


def et_maintenant(cible: Path, mise_a_jour: bool, echecs: list[str]) -> list[str]:
    """Ce qui reste à l'humain après l'installation, dans l'ordre où le
    faire : chaque étape avec sa commande."""
    from socle import hooks, private as prive

    projet = config.Projet.charger(cible)
    etapes = []
    if "protege.fichiers" in echecs and os.environ.get(hooks.SESSION_CLOUD) == "true":
        # En session cloud, l'humain n'a pas de terminal, et la session qui a
        # ajouté le dépôt du socle ne se reprend pas (B-0107).
        etapes.append(trad("approuver les fichiers protégés que la mise à jour a changés : en session cloud, "
                           "l'humain n'a pas de terminal pour `socle approve` ; poser une demande qui cite chaque "
                           "fichier protégé changé et son empreinte (`python3 .socle/socle check` les donne), que "
                           "l'humain valide dans la conversation. Une session qui a dû ajouter le dépôt du socle "
                           "ne se reprend pas : y commiter, pousser la branche et ouvrir la pull request, d'une "
                           "traite et sans rien attendre, et poser la demande dans une session neuve sur le seul "
                           "dépôt du projet, sur cette branche"))
    elif "protege.fichiers" in echecs:
        etapes.append(trad("approuver les fichiers protégés que la mise à jour a changés (la liste s'affiche, "
                           'à confirmer) : `python3 .socle/socle approve --text "Mise à jour du socle '
                           '{version}"`', version=VERSION))
    mode = prive.mode(projet)
    sans_compagnon = mode == "compagnon" and not prive.commit_compagnon(cible)
    # Le verrou d'un dépôt compagnon pas encore en place : l'étape qui le
    # met en place le règle, pas une correction ni l'adoption.
    autres = [c for c in echecs if c != "protege.fichiers" and not (sans_compagnon and c == "prive.verrou")]
    if autres:
        etapes.append(trad("{n} contrôle(s) en échec ci-dessus ({liste}) : les corriger, ou relancer "
                           "l'installation avec `--adoption`, qui les passe en avertissement sur l'existant",
                           n=len(autres), liste=', '.join(autres)))
    if sans_compagnon:
        etapes.append(trad("mettre en place le dépôt privé (créé vide sur GitHub, privé) : clone, premier "
                           "commit, verrou (ce qui règle `prive.verrou`), clé de déploiement, puis les deux "
                           "gestes sur GitHub, avec leurs liens : `python3 .socle/socle private install --repo "
                           "<adresse du dépôt privé>`"))
    elif mode and mode != "compagnon":
        filtre = "git-crypt"
        attributs = cible / ".gitattributes"
        if attributs.is_file():
            m = re.search(rf"(?m)^{re.escape(prive.dossier(cible))}/\*\* filter=(\S+)", attributs.read_text(encoding="utf-8"))
            filtre = m.group(1) if m else filtre
        if not outils.git(cible, "config", "--get", f"filter.{filtre}.clean", check=False).strip():
            etapes.append(trad("initialiser le filtre de chiffrement « {filtre} » (`{filtre} init`, ou "
                               "l'équivalent de l'outil) avant d'écrire du privé", filtre=filtre))
    demandes = cible / projet.chemins.demandes
    if not mise_a_jour and not (demandes.is_dir() and any(demandes.glob("D-*.md"))):
        etapes.append(trad("décrire le projet à l'agent : `python3 .socle/socle init --brief <document> "
                           "--repo` (sans document : `--repo` seul ; un dépôt vide : sans option)"))
    ci = verification.commandes_ci(projet)
    if ci and not mise_a_jour:
        # La CI installe les outils de l'adaptateur ; l'environnement de
        # l'agent en a besoin aussi. En session cloud, le hook de démarrage
        # s'en charge ensuite (D-0048), pas dans la session qui installe.
        etapes.append(trad("donner à l'agent les outils que la CI installe : {commandes}, là où il travaille ; en "
                           "session cloud, dans le script d'installation de l'environnement ou par l'agent, pour "
                           "cette session seulement : le hook de démarrage du socle les installe ensuite dans "
                           "chaque session neuve", commandes=" ; ".join(f"`{x}`" for x in ci)))
    message = (trad("Mettre à jour le socle {version}", version=VERSION) if mise_a_jour
               else trad("Installer le socle {version}", version=VERSION))
    etapes.append(trad('commiter puis pousser : `git add -A && git commit -m "{message}" && git push`',
                       message=message))
    etapes.append(trad("ouvrir l'agent dans le projet : il lit l'état au démarrage") if mise_a_jour
                  else trad("ouvrir l'agent dans le projet : il lit l'état au démarrage, et te donne le lien des questions "
                          "de départ, une demande à laquelle tu réponds dans la conversation"))
    if not mise_a_jour and not str(projet.pol("human", "name", defaut="") or "").strip():
        # Sans lui, chaque réponse relayée doit nommer l'humain (`--by`).
        etapes.append(trad("écrire ton nom dans `{politique}` (`[human] name`) avant de fusionner l'installation : "
                           "il signe les réponses que l'agent relaie. En session cloud, l'identité git est celle "
                           "de l'agent, que l'installeur ne prend pas ; `--human <nom>` le donne à l'installation",
                           politique=projet.chemins.politique))
    if not mise_a_jour:
        from socle import state as etat

        page = etat.page_protection(projet)
        # L'auteur d'une pull request ne peut pas l'approuver, et l'agent ouvre
        # les siennes au nom de l'humain : seul, il ne fusionnerait plus (B-0093).
        etapes.append(trad("après ce premier push, protéger la branche par défaut : un ensemble de règles qui y "
                           "exige la CI « {ci} » ({page}) ; sans lui, une CI rouge n'empêche pas de fusionner, et "
                           "`socle state` le signale. La revue des propriétaires du code ne s'y ajoute que si un "
                           "autre humain relit : l'auteur d'une pull request ne peut pas l'approuver, et l'agent "
                           "ouvre les siennes au nom de l'humain. Dans les réglages généraux, cocher « Automatically "
                           "delete head branches » : une branche fusionnée s'efface alors seule",
                           ci=etat.nom_de_la_ci(projet), page=page or trad("réglages du dépôt")))
    etapes.append(trad("ensuite, tes gestes, chacun avec sa commande : `python3 .socle/socle help`"))
    return etapes
