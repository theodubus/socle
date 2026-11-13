"""L'installeur : pose tout le dispositif en une commande, se relance pour
les mises à jour.

Ce qu'il copie et ce qu'il référence décide de tout :
- le moteur est remplacé en bloc et son empreinte enregistrée — aucun merge ;
- la mémoire, la politique et les garde-fous appartiennent au projet :
  posés s'ils manquent, jamais écrasés ; une copie d'un adaptateur maintenu
  se rafraîchit à la mise à jour tant que le projet ne l'a pas adaptée
  (ADR-0052) ;
- les hooks, la CI et CODEOWNERS sont régénérés ; leur diff passe par la
  revue humaine (fichiers protégés).

Mode adoption (projet existant) : les budgets sont fixés au niveau actuel,
et les contrôles qui échouent sur l'existant passent en avertissement
(`[adoption] warn_only`), d'où on ne les retire que pour durcir ; seuls les
constats présents à l'adoption y sont tolérés (`[adoption.tolerated]`), tout
autre échoue (B-0180).
"""

from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import date
from pathlib import Path
from typing import NamedTuple

from socle import VERSION, config, fingerprint as empreinte, language as langue, messages, mutation, utils as outils
from socle import verification
from socle.messages import a_traduire, trad
from socle.report import en_echec_dans
from socle.templates import DOSSIER as MODELES, gabarit

ADAPTATEURS = Path(__file__).resolve().parent / "adapters"
DEBUT_SOCLE = config.DEBUT_SOCLE
FIN_SOCLE = "<!-- socle:fin -->"


def est_un_fichier(nom: str) -> bool:
    """Ce que `--adapter` reçoit désigne un fichier d'adaptateur, un `.toml`,
    et non un adaptateur maintenu."""
    return Path(nom).suffix == ".toml"


def charger_adaptateur(nom: str) -> tuple[str, str]:
    """(texte, nom) d'un adaptateur maintenu ou d'un fichier."""
    p = Path(nom)
    if est_un_fichier(nom):
        if not p.is_file():
            raise SystemExit(trad("fichier d'adaptateur introuvable : {nom}", nom=nom))
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
    (("build.gradle.kts", "settings.gradle.kts"), "kotlin"),
    (("Gemfile",), "ruby"),
    (("composer.json",), "php"),
    (("*.sln", "*.slnx", "*.csproj"), "csharp"),
    (("package.json",), "javascript"),
)


# Un langage dont le marqueur ne suffit pas : son build Gradle écrit en
# Kotlin, un projet Java sous Gradle le porte aussi ; il faut encore une
# source du langage, hors des greffons de construction (`buildSrc/`), qu'un
# projet Java écrit souvent en Kotlin.
SOURCE_EXIGEE = {"kotlin": ".kt"}
HORS_SOURCES = ("buildSrc",)


def _source_du_langage(chemin: str, extension: str) -> bool:
    return chemin.endswith(extension) and not set(HORS_SOURCES) & set(chemin.split("/")[:-1])


def langages_presents(fichiers: list[str]) -> dict[str, list[str]]:
    """Chaque langage dont le dépôt porte un fichier marqueur, à la racine ou
    plus bas, et où : l'audit de l'adaptateur les compare à celui
    qu'il couvre."""
    res: dict[str, list[str]] = {}
    for marqueurs, langage in MARQUEURS_LANGAGE:
        if langage in SOURCE_EXIGEE and not any(_source_du_langage(f, SOURCE_EXIGEE[langage]) for f in fichiers):
            continue
        for f in fichiers:
            nom = f.rsplit("/", 1)[-1]
            if any(fnmatch.fnmatchcase(nom, m) for m in marqueurs) and not f.startswith(config.DOSSIER + "/"):
                res.setdefault(langage, []).append(f)
    return res


def detecter_langage(cible: Path) -> str | None:
    for fichiers, langage in MARQUEURS_LANGAGE:
        if any(p.is_file() for f in fichiers for p in cible.glob(f)):
            if langage in SOURCE_EXIGEE and not any(
                    _source_du_langage(p.relative_to(cible).as_posix(), SOURCE_EXIGEE[langage])
                    for p in cible.rglob(f"*{SOURCE_EXIGEE[langage]}")):
                continue
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
    return _python_ou_pytest(cible, fichiers)


def _python_ou_pytest(cible: Path, fichiers: list[str], partout: bool = False) -> str:
    """`python-pytest` quand le dépôt dit pytest, `python` sinon. Ses fichiers
    de configuration se lisent à la racine ; `partout`, dans tout dossier :
    pour un Python qui n'est pas le premier langage, ses outils vivent souvent
    dans un sous-dossier (revue du lot de B-0095, constat 7)."""
    def nom(f):
        return f.rsplit("/", 1)[-1] if partout else f

    indices = [f for f in fichiers if f.endswith("conftest.py") or nom(f) in ("pytest.ini", "tox.ini")]
    for f in [f for f in fichiers if nom(f) in ("pyproject.toml", "setup.cfg") or nom(f).startswith("requirements")]:
        if "pytest" in (cible / f).read_text(encoding="utf-8", errors="replace"):
            indices.append(f)
    return "python-pytest" if indices else "python"


def detecter_adaptateurs(cible: Path) -> list[str]:
    """Un adaptateur maintenu par langage que le dépôt porte, celui de
    `detecter_adaptateur` d'abord : il prend `.socle/adapter.toml`
    (ADR-0051, point 6). Un dépôt à un seul langage n'en a qu'un."""
    premier = detecter_adaptateur(cible)
    if premier is None:
        return []
    res = [premier]
    vus = {_langage_de(premier)}
    fichiers = _fichiers_du_projet(cible)
    presents = langages_presents(fichiers)
    # Un langage dont le manifeste n'est que dans un sous-dossier n'en reçoit
    # pas : ses commandes se lancent à la racine, où elles échoueraient ;
    # l'installeur le dit (B-0168).
    en_sous_dossier = langages_en_sous_dossier(cible)
    for _, langage in MARQUEURS_LANGAGE:
        if langage not in presents or langage in vus or langage in en_sous_dossier:
            continue
        nom = _python_ou_pytest(cible, fichiers, partout=True) if langage == "python" else langage
        if (ADAPTATEURS / f"{nom}.toml").is_file():
            vus.add(langage)
            res.append(nom)
    return res


# Ce qui, à la racine, permet de lancer de là les commandes d'un langage
# dont le manifeste est plus bas : Gradle se lance de la racine dès qu'il y a
# son wrapper ou un fichier de build, Groovy compris (revue de B-0168).
LANCEURS_A_LA_RACINE = {"kotlin": ("settings.gradle", "build.gradle", "gradlew")}


def lancable_de_la_racine(cible: Path, langage: str, chemins: list[str], fichiers: list[str]) -> bool:
    """Les commandes de l'adaptateur maintenu d'un langage, dont `chemins`
    sont les manifestes, peuvent tourner de la racine : un manifeste y est,
    ou ce qui y lance l'outil (`LANCEURS_A_LA_RACINE`). Python sans
    manifeste à la racine : pytest, qui parcourt les sous-dossiers depuis la
    racine, ou un dossier `tests/` à la racine, que lit `unittest discover
    -s tests` (B-0168)."""
    if any("/" not in c for c in chemins) or set(LANCEURS_A_LA_RACINE.get(langage, ())) & set(fichiers):
        return True
    if langage == "python":
        return (_python_ou_pytest(cible, fichiers, partout=True) == "python-pytest"
                or any(f.startswith("tests/") and f.endswith(".py") for f in fichiers))
    return False


def _fichiers_du_projet(cible: Path) -> list[str]:
    """Les fichiers courants du dépôt, hors ceux du socle et d'un outil
    tiers : ceux-là n'appellent pas d'adaptateur, et l'état ne signale pas
    leur langage non plus."""
    return config.Projet.charger(cible).hors_tiers(
        [f for f in outils.fichiers_courants(cible) if not f.startswith((config.DOSSIER + "/", ".claude/"))])


def langages_en_sous_dossier(cible: Path) -> dict[str, list[str]]:
    """Chaque langage dont le dépôt ne porte de manifeste que dans des
    sous-dossiers, avec ces manifestes : un adaptateur y lancerait ses
    commandes à la racine, où elles échoueraient. En automatique,
    l'installeur ne lui en pose pas, et le dit (B-0168), sauf si ses
    commandes peuvent tourner de la racine (`lancable_de_la_racine`)."""
    fichiers = _fichiers_du_projet(cible)
    return {langage: chemins for langage, chemins in langages_presents(fichiers).items()
            if not lancable_de_la_racine(cible, langage, chemins, fichiers)}


def langages_en_place(cible: Path, ch: config.Chemins) -> set[str]:
    """Les langages des adaptateurs que le projet a déjà, le principal
    compris : sa clé `language`, le nom du fichier à défaut."""
    res = set()
    for c in [ch.adaptateur, *config.fichiers_adaptateurs(cible, ch.adaptateurs)]:
        p = cible / c
        if not p.is_file():
            continue
        try:
            res.add(str(config.lire_toml(p.read_text(encoding="utf-8")).get("language") or Path(c).stem))
        except (tomllib.TOMLDecodeError, OSError):
            res.add(Path(c).stem)
    return res


def adaptateurs_sans_langage(cible: Path, ch: config.Chemins) -> list[str]:
    """Les adaptateurs que le projet a déjà et qui ne déclarent pas
    `language` : le nom de leur fichier en tient lieu, et ne dit pas quel
    langage ils couvrent."""
    res = []
    for c in [ch.adaptateur, *config.fichiers_adaptateurs(cible, ch.adaptateurs)]:
        p = cible / c
        try:
            if p.is_file() and not config.lire_toml(p.read_text(encoding="utf-8")).get("language"):
                res.append(c)
        except (tomllib.TOMLDecodeError, OSError):
            continue
    return res


def sous_dossiers_sans_adaptateur(cible: Path, couverts: set[str], sans_langage: list[str] | tuple = ()) -> list[str]:
    """Ce que l'installeur dit, en automatique comme avec `--adapter`
    (B-0178), de chaque langage qu'aucun adaptateur ne couvre parce que son
    manifeste n'est que dans un sous-dossier : où, et les deux issues
    (B-0168). Un manifeste sous un chemin tiers déclaré ne compte pas (les
    fichiers tiers sont hors du projet). Si des adaptateurs posés ne
    déclarent pas leur langage (`sans_langage`), l'installeur les nomme au
    lieu d'affirmer qu'aucun ne couvre ce langage."""
    res = []
    for langage, chemins in langages_en_sous_dossier(cible).items():
        if langage in couverts:
            continue
        dossiers = sorted({c.rsplit("/", 1)[0] for c in chemins})
        issues = trad("Deux issues : lui donner un adaptateur propre au projet, dont les commandes entrent dans "
                      "{dossiers}, en relançant l'installeur avec `--adapter <principal> --adapter <fichier.toml>` ; "
                      "ou déclarer le sous-dossier tiers, qu'aucun contrôle ne juge alors, par `[thirdparty] paths "
                      "= [{motifs}]` des garde-fous, une décision de l'humain",
                      dossiers=", ".join(f"{d}/" for d in dossiers), motifs=", ".join(f'"{d}/**"' for d in dossiers))
        if sans_langage:
            res.append(trad("!! {langage} : son manifeste n'est que dans un sous-dossier ({manifestes}), et {liste} "
                            "ne déclare pas `language` : si cet adaptateur couvre {langage}, ajouter "
                            "`language = \"{langage}\"` à ce fichier et relancer l'installeur. Sinon : {issues}",
                            langage=langage, manifestes=", ".join(chemins), liste=", ".join(sans_langage),
                            issues=issues))
            continue
        res.append(trad("!! {langage} : son manifeste n'est que dans un sous-dossier ({manifestes}) ; aucun adaptateur "
                        "ne lui est posé, ses commandes se lanceraient à la racine. {issues}",
                        langage=langage, manifestes=", ".join(chemins), issues=issues))
    return res


def _langage_de(nom: str) -> str:
    """Le langage qu'un adaptateur couvre : sa clé `language`, son nom à
    défaut."""
    try:
        return str(tomllib.loads(charger_adaptateur(nom)[0]).get("language") or nom)
    except (SystemExit, tomllib.TOMLDecodeError):
        return nom


class AdaptateursConnus(NamedTuple):
    """Ce que le projet a porté des adaptateurs maintenus, lu avant que le
    moteur ne soit remplacé (ADR-0052)."""
    installes: dict[str, str]  # nom → texte, dans le moteur installé
    versions: dict[str, set[str]]  # nom → chaque texte que le moteur du projet en a porté
    moteur: str  # le dossier du moteur installé
    commit: str = ""  # le dernier commit avant la mise à jour : ce qui a changé se lit depuis lui
    superficiel: bool = False  # un clone superficiel : l'historique, et ses versions, sont incomplets


def versions_maintenues(cible: Path, dossier_moteur: str) -> AdaptateursConnus:
    """Les adaptateurs maintenus du moteur installé, et chaque version que
    l'historique git du projet en a eue sous `**/socle/adapters/` : une copie
    identique à l'une d'elles n'est pas adaptée (ADR-0052, point 2). Le
    moteur installé est celui du dernier commit, sinon celui de l'arbre :
    l'installeur relancé avant ce commit trouve déjà le nouveau dans l'arbre
    (revue du lot d'ADR-0052, constat 1)."""
    d = cible / dossier_moteur / "socle/adapters"
    arbre = {p.stem: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.toml"))} if d.is_dir() else {}
    installes = dict(arbre)
    commit = outils.git(cible, "rev-parse", "--verify", "-q", "HEAD", check=False).strip()
    if commit:
        for chemin in outils.git(cible, "ls-tree", "-z", "--name-only", commit, "--",
                                 f"{dossier_moteur}/socle/adapters/", check=False).split("\0"):
            if chemin.endswith(".toml"):
                installes[Path(chemin).stem] = outils.git(cible, "show", f"{commit}:{chemin}", check=False)
    versions: dict[str, set[str]] = {}
    for textes in (arbre, installes):
        for nom, texte in textes.items():
            versions.setdefault(nom, set()).add(texte)
    sortie = outils.git(cible, "log", "--raw", "--no-abbrev", "--format=", "--",
                        ":(glob)**/socle/adapters/*.toml", check=False)
    blobs: dict[str, str] = {}
    for ligne in sortie.splitlines():
        champs, _, chemins = ligne.partition("\t")
        champs = champs.split()
        if len(champs) < 4 or not chemins or set(champs[3]) == {"0"}:
            continue
        blobs.setdefault(champs[3], Path(chemins.split("\t")[-1]).stem)
    for blob, nom in blobs.items():
        texte = outils.git(cible, "cat-file", "blob", blob, check=False)
        if texte:
            versions.setdefault(nom, set()).add(texte)
    superficiel = outils.git(cible, "rev-parse", "--is-shallow-repository", check=False).strip() == "true"
    return AdaptateursConnus(installes, versions, dossier_moteur, commit[:12], superficiel)


def adaptateur_de_base(texte: str, versions: dict[str, set[str]]) -> str | None:
    """L'adaptateur maintenu d'où vient la copie principale : celui dont elle
    porte une version ; adaptée, celui de son langage dont le texte est le
    plus proche du sien ; `None` si aucun maintenu n'a son langage (ADR-0052,
    point 3)."""
    for nom in sorted(versions):
        if texte in versions[nom]:
            return nom
    try:
        langage = str(config.lire_toml(texte).get("language") or "")
    except tomllib.TOMLDecodeError:
        return None
    candidats = {}
    for p in sorted(ADAPTATEURS.glob("*.toml")):
        maintenu = p.read_text(encoding="utf-8")
        if langage and str(tomllib.loads(maintenu).get("language") or "") == langage:
            candidats[p.stem] = maintenu
    if not candidats:
        return None
    lignes = texte.splitlines()
    return max(candidats, key=lambda nom: difflib.SequenceMatcher(None, lignes, candidats[nom].splitlines()).ratio())


def rafraichir_copie(cible: Path, chemin: str, base: str | None, connus: AdaptateursConnus) -> list[str]:
    """Une copie d'adaptateur que le projet a déjà, à la mise à jour : non
    adaptée, elle prend l'adaptateur maintenu de cette version ; adaptée, elle
    se garde, et l'installeur dit quand son adaptateur maintenu a changé
    depuis le moteur installé (ADR-0052)."""
    p = cible / chemin
    maintenu = ADAPTATEURS / f"{base}.toml" if base else None
    if maintenu is None or not maintenu.is_file():
        return [trad("{nom} existe : conservé (comparer au gabarit à la main si besoin)", nom=chemin)]
    texte, nouveau = p.read_text(encoding="utf-8"), maintenu.read_text(encoding="utf-8")
    if texte == nouveau:
        return []
    if texte in connus.versions.get(base, ()):
        outils.ecrire(p, nouveau)
        return [trad("{nom} rafraîchi depuis l'adaptateur maintenu {base}, que le projet n'avait pas adapté : un "
                     "changement protégé, à approuver", nom=chemin, base=base)]
    source = f"{connus.moteur}/socle/adapters/{base}.toml"
    if base not in connus.installes:
        # Un `git diff` ne montrerait rien d'un fichier que le moteur installé
        # n'avait pas (revue du lot d'ADR-0052, constat 4).
        return [trad("!! {nom} : conservé ; l'adaptateur maintenu {base} n'était pas dans le moteur installé : le "
                     "comparer à la copie (`diff {nom} {source}`), et proposer à l'humain, par une demande, ce "
                     "qu'il faut en reprendre", nom=chemin, base=base, source=source)]
    if connus.installes[base] != nouveau:
        # Depuis le commit d'avant la mise à jour : la commande montre encore
        # ce qui a changé une fois la mise à jour commitée.
        voir = f"git diff {connus.commit} -- {source}" if connus.commit else f"diff {chemin} {source}"
        return [trad("!! {nom} adapté par le projet : conservé ; l'adaptateur maintenu {base} a changé depuis le "
                     "moteur installé : proposer à l'humain, par une demande, d'y reporter ses corrections (ce qui "
                     "a changé : `{voir}`)", nom=chemin, base=base, voir=voir)]
    return [trad("{nom} adapté par le projet : conservé ; l'adaptateur maintenu {base} n'a pas changé",
                 nom=chemin, base=base)]


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


def _balayage_planifie(cible: Path, texte_adaptateur: str, autres: list[str] = ()) -> tuple[bool, str]:
    """(poser, ce qu'en dit le journal) : le workflow de mutation se pose
    quand un adaptateur déclare un balayage, sauf si un workflow du projet
    le lance déjà ; celui du socle, déjà posé, se met à jour."""
    caps = [c for x in (texte_adaptateur, *autres)
            if "command" in (c := tomllib.loads(x).get("capabilities", {}).get("mutation", {}))]
    if not caps:
        return False, ""
    flux = sorted(str(p.relative_to(cible)).replace(os.sep, "/") for p in (cible / ".github/workflows").glob("*")
                  if p.is_file()) if (cible / ".github/workflows").is_dir() else []
    if mutation.WORKFLOW in flux:
        return True, ""
    # Un workflow du projet qui lance l'outil d'un seul langage ne balaie pas
    # les autres : celui du socle se pose tant qu'un outil n'a pas le sien.
    autres = [mutation.workflow_de_balayage(c, flux, lambda f: outils.lire_a(cible, None, f), sauf_le_sien=True)
              for c in caps]
    autre = autres[0] if all(autres) else None
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
                        lg: str = "fr", plafonds: dict[str, dict] | None = None, source: str = "",
                        autres: list[str] = ()) -> str:
    """Les garde-fous du gabarit, avec chaque module qui porte déjà du code
    posé « à mesurer » au cliquet de mutation : une installation sur un
    projet existant finit verte, et le premier balayage pose les plafonds
    mesurés. Un module dont `plafonds` donne la mesure, faite ailleurs, la
    reprend au lieu d'attendre ce balayage (B-0009)."""
    texte = gabarit("guardrails.toml", lg)
    # Chaque adaptateur pose les modules de son langage (ADR-0051, point 5).
    modules = modules_a_mesurer(cible, [texte_adaptateur, *autres])
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


_ENTETE = re.compile(r"^#?\s*\[\[?([\w.]+)\]\]?\s*$")
_CLE = re.compile(r"^(#\s*)?([A-Za-z_][\w-]*)\s*=\s*\S")


def _reglages(texte: str) -> list[tuple[str, str, str]]:
    """Les réglages d'un fichier de garde-fous, écrits ou en commentaire :
    (section, clé, explication), l'explication étant le commentaire qui les
    précède. Les clés entre guillemets (motifs de budget, modules d'un
    plafond) sont des données du projet, pas des réglages."""
    reglages, section, avant_section, courant = [], "", "", []
    for ligne in texte.splitlines():
        brute = ligne.strip()
        entete = _ENTETE.match(brute)
        cle = _CLE.match(brute)
        if entete:
            section, avant_section, courant = entete[1], " ".join(courant), []
        elif cle:
            reglages.append((section, cle[2], " ".join(courant) or avant_section))
            courant = []
        elif brute.startswith("#"):
            courant.append(brute.lstrip("#").strip())
        else:
            courant = []
    return reglages


def reglages_nouveaux(projet: str, modele: str) -> list[tuple[str, str]]:
    """Les réglages du gabarit des garde-fous que le fichier du projet
    n'écrit pas, même en commentaire : (`[section] clé`, ce qu'il fait). Une
    mise à jour garde les garde-fous du projet ; sans ce relevé, l'agent ne
    saurait pas qu'un réglage nouveau existe."""
    connus = {(s, c) for s, c, _ in _reglages(projet)}
    try:
        donnees = tomllib.loads(projet)
    except tomllib.TOMLDecodeError:
        donnees = {}

    def parcourir(table: dict, chemin: str) -> None:
        for cle, valeur in table.items():
            if isinstance(valeur, dict):
                parcourir(valeur, f"{chemin}.{cle}" if chemin else cle)
            elif isinstance(valeur, list) and valeur and all(isinstance(v, dict) for v in valeur):
                for element in valeur:
                    parcourir(element, f"{chemin}.{cle}" if chemin else cle)
            else:
                connus.add((chemin, cle))

    parcourir(donnees, "")
    nouveaux, vus = [], set()
    for section, cle, explication in _reglages(modele):
        if (section, cle) in connus or (section, cle) in vus:
            continue
        vus.add((section, cle))
        nouveaux.append((f"[{section}] {cle}" if section else cle, explication))
    return nouveaux


def alerte_chantier_actif(cible: Path) -> list[str]:
    """Un budget du chantier actif que les garde-fous gardés d'un projet
    installé avant mettent au-dessus de sa part de la sortie du démarrage
    (ADR-0071) : à son budget, le chantier actif y serait coupé à chaque
    session. La mise à jour ne réécrit pas les garde-fous du projet ; elle le
    dit, avec la valeur qui tient, comme l'état à chaque démarrage."""
    from socle import state as etat

    return etat.alerte_budget_actif(config.Projet.charger(cible))


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
                         humain: str = "", autres: list[tuple[str, str]] = (),
                         connus: AdaptateursConnus | None = None) -> tuple[str, list[str]]:
    """La politique, les adaptateurs et les garde-fous, posés s'ils manquent ;
    rend la langue de la mémoire. `autres` : (nom, texte) des adaptateurs des
    autres langages, posés dans `.socle/adapters/` (ADR-0051). `connus` : à la
    mise à jour, ce que le projet a porté des adaptateurs maintenus ; une copie
    qu'il n'a pas adaptée s'en rafraîchit (ADR-0052)."""
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
        (ch.garde_fous, garde_fous_initiaux(cible, texte_adaptateur, ch, lg, plafonds, source,
                                            [x for _, x in autres])),
    ):
        p = cible / nom
        if p.is_file() and nom == ch.adaptateur and connus is not None:
            journal += rafraichir_copie(cible, nom, adaptateur_de_base(p.read_text(encoding="utf-8"),
                                                                       connus.versions), connus)
        elif p.is_file():
            journal.append(trad("{nom} existe : conservé (comparer au gabarit à la main si besoin)", nom=nom))
            if nom == ch.garde_fous and plafonds:
                journal.append(trad("!! plafonds de {source} non repris : les garde-fous existent déjà",
                                    source=source))
            # Le pilote les avait déclarés avant que son moteur nouveau soit commité :
            # l'ancien, qui jugeait la CI, les a pris pour un assouplissement.
            if nom == ch.garde_fous:
                nouveaux = reglages_nouveaux(p.read_text(encoding="utf-8"), gabarit("guardrails.toml", lg))
                if nouveaux:
                    journal.append(trad(
                        "!! réglages du gabarit absents de {nom} ({n}) : à déclarer s'ils servent au projet, une "
                        "fois ce moteur commité (la CI juge avec le moteur commité, et un réglage qu'il ne connaît "
                        "pas compte pour un assouplissement) ; ce qui durcit est libre, un assouplissement attend "
                        "une demande validée :\n      {liste}",
                        nom=nom, n=len(nouveaux),
                        liste="\n      ".join(f"`{cle}` — {quoi}" if quoi else f"`{cle}`"
                                              for cle, quoi in nouveaux)))
                journal += alerte_chantier_actif(cible)
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
    poses, sortie = _poser_autres_adaptateurs(cible, autres, ch, connus)
    journal += sortie
    gf = cible / ch.garde_fous
    if poses and gf.is_file():
        # Une mise à jour qui ajoute un langage : ses modules entrent « à
        # mesurer » au cliquet, comme ceux d'une installation neuve (revue du
        # lot de B-0095, constat 2). Ajouter un plafond durcit.
        texte = gf.read_text(encoding="utf-8")
        modules = [m for m in modules_a_mesurer(cible, poses)
                   if m not in (tomllib.loads(texte).get("mutation", {}).get("caps", {}) or {})]
        if modules:
            outils.ecrire(gf, ajouter_a_mesurer(texte, modules))
            journal.append(trad("plafonds de mutation : {n} module(s) des adaptateurs ajoutés posé(s) à mesurer",
                                n=len(modules)))
    return lg, journal


def modules_a_mesurer(cible: Path, textes: list[str]) -> list[str]:
    """Les modules qui portent du code, pour chaque adaptateur qui déclare un
    balayage de mutation."""
    fichiers = [f for f in outils.fichiers_courants(cible) if not f.startswith(config.DOSSIER + "/")]
    modules = []
    for x in textes:
        cap = tomllib.loads(x).get("capabilities", {}).get("mutation", {})
        if "command" not in cap:
            continue
        porte = re.compile(cap.get("has_code", r"."))
        modules += [m for m in outils.filtrer(fichiers, cap.get("modules", []), cap.get("modules_exclude", []))
                    if porte.search(outils.lire_a(cible, None, m) or "") and m not in modules]
    return sorted(modules)


def ajouter_a_mesurer(texte: str, modules: list[str]) -> str:
    """Les garde-fous, avec ces modules « à mesurer » sous `[mutation.caps]`,
    la table ajoutée si elle manque."""
    lignes = "".join(f"{json.dumps(m, ensure_ascii=False)} = {{ pending = true }}\n" for m in modules)
    m = re.search(r"(?m)^\[mutation\.caps\]\s*\n", texte)
    if m:
        return texte[:m.end()] + lignes + texte[m.end():]
    return texte.rstrip("\n") + "\n\n[mutation.caps]\n" + lignes


def _poser_autres_adaptateurs(cible: Path, autres: list[tuple[str, str]], ch: config.Chemins,
                              connus: AdaptateursConnus | None = None) -> tuple[list[str], list[str]]:
    """Les adaptateurs des autres langages, `.socle/adapters/<nom>.toml` :
    posés s'ils manquent. À la mise à jour, une copie d'un adaptateur maintenu
    que le projet n'a pas adaptée s'en rafraîchit, et l'humain l'approuve comme
    tout fichier protégé ; une copie adaptée, ou un adaptateur propre au
    projet, se garde (ADR-0052)."""
    journal, poses = [], []
    a_poser = dict(autres)
    for chemin in config.fichiers_adaptateurs(cible, ch.adaptateurs):
        nom = Path(chemin).stem
        if nom not in a_poser and (ADAPTATEURS / f"{nom}.toml").is_file():
            a_poser[nom] = (ADAPTATEURS / f"{nom}.toml").read_text(encoding="utf-8")
    for nom, texte in a_poser.items():
        p = cible / ch.adaptateurs / f"{nom}.toml"
        if not p.is_file():
            outils.ecrire(p, texte)
            poses.append(texte)
            journal.append(trad("{nom} posé", nom=f"{ch.adaptateurs}/{nom}.toml"))
        elif connus is not None:
            journal += rafraichir_copie(cible, f"{ch.adaptateurs}/{nom}.toml", nom, connus)
        else:
            journal.append(trad("{nom} existe : conservé (comparer au gabarit à la main si besoin)",
                                nom=f"{ch.adaptateurs}/{nom}.toml"))
    return poses, journal


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


def ignorer_aux_envois(projet: config.Projet) -> str:
    """Les lignes du workflow de CI qui écartent les branches jetables des
    envois ; une pull request qui en part la lance toujours (D-0087). Un
    préfixe n'a aucun caractère de motif (`Projet.branches_jetables`) : `**`
    le prolonge comme `startswith`. Les étiquettes se nomment, faute de quoi
    GitHub ne lancerait plus la CI pour elles."""
    motifs = [p + "**" for p in projet.branches_jetables()]
    if not motifs:
        return ""
    return f"    branches-ignore: [{', '.join(json.dumps(m) for m in motifs)}]\n    tags: [\"**\"]\n"


def etapes_de_ci(textes: list[str]) -> str:
    """Les étapes de CI des adaptateurs, l'une après l'autre ; une étape que
    deux adaptateurs déclarent à l'identique ne se répète pas (ADR-0051,
    point 4)."""
    res = []
    for x in textes:
        setup = tomllib.loads(x).get("ci_setup", "")
        for bloc in re.split(r"(?m)^(?=      - )", setup):
            if bloc.strip() and bloc not in res:
                res.append(bloc if bloc.endswith("\n") else bloc + "\n")
    return "".join(res)


def _poser_etages(cible: Path, texte_adaptateur: str, dossier_moteur: str, proprietaire: str,
                  balayage: bool, motif: str, ch: config.Chemins, lg: str = "fr",
                  autres: list[tuple[str, str]] = ()) -> list[str]:
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
    setup = noms_d_etapes_traduits(etapes_de_ci([texte_adaptateur, *(x for _, x in autres)]))
    etapes = setup.strip("\n") + "\n" if setup.strip() else ""
    workflow = gabarit("socle.yml", lg).replace("@@ETAPES_ADAPTATEUR@@\n", etapes)
    workflow = workflow.replace("@@BRANCHES_JETABLES@@", ignorer_aux_envois(config.Projet.charger(cible)))
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
        installations = [i for x in (texte_adaptateur, *(y for _, y in autres))
                         if (i := tomllib.loads(x).get("capabilities", {}).get("mutation", {}).get("install", ""))]
        # En bloc littéral : la commande peut porter ce que YAML lirait autrement.
        etape = "".join(f"      - name: {trad('Outil de mutation')}\n        run: |\n          {i}\n"
                        for i in dict.fromkeys(installations))
        outils.ecrire(cible / mutation.WORKFLOW, gabarit("mutation.yml", lg).replace("@@ETAPES_ADAPTATEUR@@\n", etapes)
                .replace("@@INSTALLATION@@\n", etape))
    if motif:
        journal.append(motif)
    journal += _codeowners(cible, proprietaire)
    journal += _gitignore(cible)
    journal += _non_ignores(cible, [config.LANCEUR, ch.lock, ch.politique, ch.adaptateur, ch.garde_fous,
                                    *config.fichiers_adaptateurs(cible, ch.adaptateurs),
                                    f"{config.GIT_HOOKS}/pre-commit", ".github/workflows/socle.yml", mutation.WORKFLOW,
                                    ".claude/settings.json", f"{SKILLS}/socle-request/SKILL.md", config.INSTRUCTIONS,
                                    "CLAUDE.md", ch.canonique,
                                    f"{dossier_moteur}/socle/cli.py"])
    return journal


def installer(cible: Path, adaptateur: str | list[str], proprietaire: str = "", adoption: bool = False,
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


def _installer(cible: Path, adaptateur: str | list[str], proprietaire: str, adoption: bool, mode: str,
               source: Path | None,
               prive: str | None, relecture: str | None, demandes_privees: bool, filtre: str,
               langue_memoire: str | None, plafonds: dict[str, dict] | None = None, source_plafonds: str = "",
               humain: str = "") -> int:
    ch = config.FORMAT_ACTUEL

    refus = _refus_cible(cible)
    if refus:
        print(trad("refus : {refus}", refus=refus), file=sys.stderr)
        return 2
    source = source or Path(__file__).resolve().parent.parent
    # Plusieurs `--adapter` : un par langage, le premier nommé prend
    # `.socle/adapter.toml` ; `auto` en pose un par langage reconnu
    # (ADR-0051, point 6).
    demandes_ = [adaptateur] if isinstance(adaptateur, str) else list(adaptateur) or ["auto"]
    noms, detectes, nommes = [], False, set()
    for n in demandes_:
        if n != "auto":
            noms += [n] if n not in noms else []
            nommes.add(n)
            continue
        trouves = detecter_adaptateurs(cible)
        if not trouves and not noms and n == demandes_[-1]:
            connus = "|".join(sorted(x.stem for x in ADAPTATEURS.glob("*.toml")))
            print(trad("refus : langage non détecté (aucun de Cargo.toml, pyproject.toml, go.mod, pom.xml, "
                       "Gemfile, composer.json, *.sln, *.csproj, package.json, ni fichier Python) : le demander "
                       "à l'humain, puis `--adapter <{connus}>` ou le chemin d'un .toml", connus=connus), file=sys.stderr)
            return 2
        detectes = True
        noms += [x for x in trouves if x not in noms]
    from socle.checks_tests import ecarts_au_contrat

    charges, de_fichier, sans_cle = [], set(), {}
    for n in noms:
        texte, nom = charger_adaptateur(n)
        try:
            donnees = tomllib.loads(texte)
        except tomllib.TOMLDecodeError as e:
            print(trad("refus : adaptateur « {nom} » illisible : {erreur}", nom=nom, erreur=e), file=sys.stderr)
            return 2
        # Un adaptateur propre au projet se juge avant d'être posé : protégé
        # ensuite, il ne se corrigerait plus à la main (B-0168).
        ecarts = ecarts_au_contrat(donnees) if est_un_fichier(n) else []
        if ecarts:
            print(trad("refus : l'adaptateur {chemin} ne tient pas le contrat des adaptateurs :\n  - {ecarts}",
                       chemin=n, ecarts="\n  - ".join(ecarts)), file=sys.stderr)
            return 2
        charges.append((nom, texte, str(donnees.get("language") or nom), n in nommes))
        if not donnees.get("language"):
            sans_cle[nom] = n
        if est_un_fichier(n):
            de_fichier.add(nom)
    # Le principal : celui que le projet a déjà, sinon le premier nommé. Un
    # autre adaptateur du même langage que lui ne s'ajoute pas.
    principal = cible / ch.adaptateur
    texte_principal = principal.read_text(encoding="utf-8") if principal.is_file() else ""
    langage_principal = (str(config.lire_toml(texte_principal).get("language") or "") if principal.is_file()
                         else charges[0][2])
    texte_adaptateur, nom_adaptateur = charges[0][1], charges[0][0]
    langages, autres, sans_langage = {langage_principal}, [], []
    for nom, texte, langage, nomme in charges[1:] if not principal.is_file() else charges:
        if langage in langages:
            continue
        if principal.is_file() and not langage_principal and not nomme:
            # Un principal qui ne dit pas son langage : un adaptateur détecté
            # pourrait le doubler (revue du lot de B-0095, constat 9).
            sans_langage.append(nom)
            continue
        langages.add(langage)
        autres.append((nom, texte))
    if principal.is_file() and autres and charges[0][2] != langage_principal:
        # Le premier nommé n'est pas le principal du projet : la CI part du
        # principal, qui reste (constat 3).
        texte_adaptateur, nom_adaptateur = texte_principal, langage_principal or Path(ch.adaptateur).stem
    # Un fichier d'adaptateur donné pour le langage d'un principal déjà en
    # place n'est pas posé : le principal se garde. L'installeur le dit, au
    # lieu d'afficher son nom comme s'il l'était (revue de B-0168).
    ecartes = [nom for nom, texte, langage, _ in charges if nom in de_fichier and texte_principal
               and langage == langage_principal and texte != texte_principal]
    if nom_adaptateur in ecartes:
        texte_adaptateur, nom_adaptateur = texte_principal, langage_principal or Path(ch.adaptateur).stem
    ancien = config.Projet.charger(cible).lock if (cible / config.FORMAT_ACTUEL.lock).is_file() else {}
    journal = [trad("adaptateur : {nom}", nom=", ".join([nom_adaptateur, *(n for n, _ in autres)]))
               + (trad(" (détecté)") if detectes else "")]
    if sans_langage:
        journal.append(trad("!! {adaptateur} ne déclare pas `language` : aucun autre adaptateur ne s'ajoute en "
                            "automatique ({liste}) ; les nommer par `--adapter`, ou y déclarer son langage",
                            adaptateur=ch.adaptateur, liste=", ".join(sans_langage)))
    for nom in ecartes:
        journal.append(trad("!! {nom} non posé : {adaptateur} existe déjà pour {langage}, et se garde. Pour le "
                            "remplacer : sur un essai, le commiter sur sa branche, revenir à la branche de départ "
                            "par `git switch` et relancer l'installeur sur une branche neuve ; sur un projet "
                            "équipé, proposer le changement à l'humain par une demande, l'adaptateur étant protégé",
                            nom=nom, adaptateur=ch.adaptateur, langage=langage_principal))
    # Les langages couverts : ceux de cet appel, et ceux des copies déjà
    # posées (revue de B-0168), détectés ou nommés par `--adapter` (B-0178).
    poses_sans_cle = [sans_cle[n] for n in [nom_adaptateur, *(n for n, _ in autres)] if n in sans_cle]
    journal += sous_dossiers_sans_adaptateur(cible, langages | {c[2] for c in charges}
                                             | langages_en_place(cible, ch),
                                             sorted(set(poses_sans_cle) | set(adaptateurs_sans_langage(cible, ch))))
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

    # Ce que le projet a porté des adaptateurs maintenus se lit avant que le
    # moteur installé ne soit remplacé (ADR-0052).
    connus = versions_maintenues(cible, str(ancien.get("engine_dir") or ch.moteur)) if ancien else None
    if connus is not None and connus.superficiel:
        journal.append(trad("!! clone superficiel : l'historique du moteur y est incomplet, et une copie d'adaptateur "
                            "que le projet n'a pas adaptée peut y être prise pour adaptée, et gardée ; "
                            "`git fetch --unshallow`, puis relancer l'installeur"))

    # 1. Le moteur, remplacé en bloc, et son verrou.
    dossier_moteur, poses = _poser_moteur(cible, mode, source, ch)
    journal += poses

    # 2. Les fichiers du projet : posés s'ils manquent, jamais écrasés.
    lg, poses = _poser_configuration(cible, texte_adaptateur, ancien, prive, relecture, demandes_privees,
                                     langue_memoire, ch, plafonds, source_plafonds, humain, autres, connus)
    journal += poses

    # 3. La mémoire initiale.
    journal += _poser_memoire(cible, lg, ", ".join([nom_adaptateur, *(n for n, _ in autres)]), adoption, ch)

    # 4. Les instructions : AGENTS.md fait foi, CLAUDE.md l'importe. La CI et
    # le balayage partent des copies telles qu'elles sont désormais : une
    # copie adaptée, gardée, y garde ses adaptations. Nommer pour le langage
    # du principal un autre adaptateur maintenu que le sien en fait la CI,
    # comme avant ; détecté, il ne la fait pas (ADR-0052, point 5). Ceux
    # qu'il vient de nommer d'abord.
    if texte_principal and (texte_adaptateur == texte_principal or not charges[0][3] or (
            connus is not None and adaptateur_de_base(texte_principal, connus.versions) == nom_adaptateur)):
        texte_adaptateur = principal.read_text(encoding="utf-8")
    en_place = {Path(c).stem: (cible / c).read_text(encoding="utf-8")
                for c in config.fichiers_adaptateurs(cible, ch.adaptateurs)}
    tous_autres = [(nom, en_place[nom]) for nom in dict.fromkeys([*(n for n, _ in autres), *en_place])
                   if nom in en_place]
    balayage, motif = _balayage_planifie(cible, texte_adaptateur, [x for _, x in tous_autres])
    section_avant = sum(_taille_section((cible / nom).read_text(encoding="utf-8")) for nom in INSTRUCTIONS
                        if (cible / nom).is_file())
    journal += _instructions(cible, dossier_moteur, lg, balayage, ch)

    # 5. Les étages d'application.
    journal += _poser_etages(cible, texte_adaptateur, dossier_moteur, proprietaire, balayage, motif, ch, lg,
                             tous_autres)
    if prive:
        journal += _prive(cible, prive, filtre)

    # 6. La trace : l'installation se voit dans `Socle-Hooks` d'une session
    # en cours (SessionStart a tiré avant que le hook n'existe).
    from socle.hooks import tracer

    tracer(cible, "Install", "", VERSION)

    # 7. Adoption : budgets au niveau actuel, contrôles en échec en avertissement.
    if adoption:
        journal += _adopter(cible)
    if adoption or ancien:
        journal += consigner_tolerances(cible, mise_a_jour=not adoption)
    journal += _alerte_budget(cible, section_avant)

    print(trad("socle {version} installé dans {cible}", version=VERSION, cible=cible))
    for l in journal:
        print(f"  - {l}")
    print(trad("\nAudit :"))
    code, echecs = _audit(cible)
    print(note_d_audit())
    print(trad("\nEt maintenant :"))
    for i, etape in enumerate(et_maintenant(cible, bool(ancien), echecs), 1):
        print(f"  {i}. {etape}")
    return code_de_sortie(code, echecs, attentes_de_l_humain(cible))


def attentes_de_l_humain(cible: Path) -> set[str]:
    """Les contrôles qu'une installation réussie laisse en échec jusqu'à un
    geste de l'humain que « Et maintenant » lui dit, ni à corriger ni à
    passer en adoption : l'approbation des fichiers protégés qu'elle a
    changés, et le verrou d'un dépôt compagnon pas encore en place, que
    `socle private install`, réservé à l'humain, pose."""
    from socle import private as prive

    attentes = {"protege.fichiers"}
    if prive.mode(config.Projet.charger(cible)) == "compagnon" and not prive.commit_compagnon(cible):
        attentes.add("prive.verrou")
    return attentes


def code_de_sortie(code: int, echecs: list[str], attentes: set[str]) -> int:
    """Le code de l'installeur, d'après celui de son audit : 0 quand
    l'installation a réussi et que seuls attendent les gestes de l'humain,
    1 quand un autre contrôle échoue, à corriger (B-0150, ADR-0056)."""
    if code and echecs and set(echecs) <= attentes:
        return 0
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


# Les fichiers d'instructions qui peuvent porter la section du socle :
# AGENTS.md, ou CLAUDE.md tant qu'une adoption le garde comme source.
INSTRUCTIONS = (config.INSTRUCTIONS, "CLAUDE.md")


def _taille_section(texte: str) -> int:
    """La taille, en octets, de la section du socle d'un fichier
    d'instructions, ses marqueurs compris ; 0 sans elle."""
    if DEBUT_SOCLE not in texte or FIN_SOCLE not in texte:
        return 0
    debut = texte.index(DEBUT_SOCLE)
    return len(texte[debut:texte.index(FIN_SOCLE, debut) + len(FIN_SOCLE)].encode("utf-8"))


def _alerte_budget(cible: Path, section_avant: int) -> list[str]:
    """B-0129 : le fichier d'instructions que la section du socle, posée ou
    régénérée, fait passer au-delà de son budget : sans ce que la section a
    gagné, il tenait. Le cliquet ne laisse un budget que baisser :
    l'installeur dit ce que l'humain peut faire, au lieu que l'audit le dise
    seulement rouge. Le contenu repris d'un CLAUDE.md n'est pas la section."""
    budgets = config.Projet.charger(cible).gf("budgets", defaut={}) or {}
    res = []
    for nom in INSTRUCTIONS:
        f = cible / nom
        if not f.is_file():
            continue
        texte = f.read_text(encoding="utf-8")
        octets, ecart = len(texte.encode("utf-8")), _taille_section(texte) - section_avant
        # Le plus bas des budgets qui le couvrent : le contrôle les juge tous.
        budget = min((int(b["max_bytes"]) for motif, b in budgets.items()
                      if "max_bytes" in b and outils.correspond(nom, [motif])), default=None)
        if budget is not None and ecart > 0 and octets > budget >= octets - ecart:
            res.append(trad("!! {fichier} dépasse son budget : {octets} octets pour {budget}, la section du socle, "
                            "posée ou régénérée, ayant grossi de {ecart} ; resserrer la partie propre au projet, hors "
                            "de cette section, ou relever le budget par une demande validée, puisque le relever "
                            "assouplit un garde-fou", fichier=nom, octets=octets, budget=budget, ecart=ecart))
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


def budget_d_adoption(octets: int) -> int:
    """Le budget qu'une adoption fixe à un fichier de cette taille : la taille
    plus un dixième, arrondie au millier supérieur. Le cliquet ne le laisse
    ensuite que baisser : sans marge, la première ligne ajoutée le casserait
    (B-0168)."""
    return -(-octets * 11 // 10000) * 1000


def _adopter(cible: Path) -> list[str]:
    """Plafonds au niveau actuel ; les contrôles en échec passent en
    avertissement, liste d'où l'on ne retire que pour durcir."""
    from socle import context as contexte

    gf = cible / config.FORMAT_ACTUEL.garde_fous
    texte = gf.read_text(encoding="utf-8")
    res = []
    claude = cible / "CLAUDE.md"
    if claude.is_file() and claude.read_text(encoding="utf-8").strip() != "@AGENTS.md" and '"CLAUDE.md"' not in texte:
        # Gardé comme source le temps du renommage : il a son budget, au
        # niveau actuel avec sa marge.
        octets = len(claude.read_bytes())
        taille = budget_d_adoption(octets)
        texte = texte.replace("[budgets]\n", f'[budgets]\n"CLAUDE.md" = {{ max_bytes = {taille} }}\n', 1)
        res.append(trad("budget de CLAUDE.md, gardé comme source : {taille} octets pour {octets}, sa taille plus un "
                        "dixième, arrondie au millier supérieur (il ne pourra que baisser)", taille=taille,
                        octets=octets))
    gf.write_text(texte, encoding="utf-8")
    projet = config.Projet.charger(cible)
    for motif, b in (projet.gf("budgets", defaut={}) or {}).items():
        tailles = [len((cible / c).read_bytes()) for c in outils.filtrer(outils.fichiers_courants(cible), [motif])]
        if tailles and max(tailles) > b.get("max_bytes", 0):
            nouveau = budget_d_adoption(max(tailles))
            texte = re.sub(rf'^("{re.escape(motif)}"\s*=\s*\{{\s*max_bytes\s*=\s*)\d+', rf"\g<1>{nouveau}", texte, flags=re.M)
            res.append(trad("budget de {motif} fixé au niveau actuel avec sa marge : {nouveau} octets pour {octets}, "
                            "la taille plus un dixième, arrondie au millier supérieur (il ne pourra que baisser)",
                            motif=motif, nouveau=nouveau, octets=max(tailles)))
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


_TABLE_TOLERES = re.compile(r"(?ms)^\[adoption\.tolerated\][^\n]*\n.*?(?=^\[|\Z)")


def consigner_tolerances(cible: Path, mise_a_jour: bool = False) -> list[str]:
    """Chaque contrôle de `[adoption] warn_only` qui n'a pas encore sa liste
    de constats tolérés reçoit ceux présents maintenant : à l'adoption, et à
    la mise à jour d'un projet adopté avant B-0180, dont les constats anciens
    ne deviennent pas des erreurs. Dit ensuite, par contrôle, combien
    l'adoption en tolère. Une liste déjà là ne s'étend jamais : ce serait
    assouplir."""
    from socle import context as contexte

    projet = config.Projet.charger(cible)
    manquants = [c for c, liste in contexte.tolerances(projet).items() if liste is None]
    res = []
    if manquants:
        gf = cible / config.FORMAT_ACTUEL.garde_fous
        texte = gf.read_text(encoding="utf-8")
        existantes = projet.gf("adoption", "tolerated", defaut={}) or {}
        if existantes and not _TABLE_TOLERES.search(texte):
            # Écrite à la main sous une autre forme : on n'y touche pas.
            return res + contexte.bilan_adoption(projet)
        presents = contexte.constats_presents(projet, manquants)
        if mise_a_jour:
            # Un projet adopté avant B-0180 : ne sont d'avant l'installation
            # que les constats de la base, la branche par défaut ; un constat
            # né sur la branche de travail n'est pas toléré.
            base = outils.base_de_travail(cible)
            if base is None:
                res.append(trad("mise à jour : aucune base lisible (la branche par défaut distante) : les constats "
                                "présents dans l'arbre de travail sont consignés comme tolérés, y compris ceux "
                                "qu'une branche aurait ajoutés"))
            else:
                de_la_base = contexte.constats_presents(projet, manquants, tete=base)
                # Un fichier renommé sur la branche garde ses constats de la
                # base, sous son nouveau nom (B-0189).
                tiers = projet.chemins_tiers()
                renommes = {a: b for a, b in outils.renommes(cible, base).items()
                            if not outils.correspond(b, tiers)}
                deplacees: dict[str, Counter] = {}
                for c in manquants:
                    suivies = [contexte.cle_renommee(k, renommes) for k in de_la_base[c]]
                    deplacees[c] = Counter(n for k, n in zip(de_la_base[c], suivies) if n != k)
                    de_la_base[c] = suivies
                for c in manquants:
                    gardes = list((Counter(presents[c]) & Counter(de_la_base[c])).elements())
                    consignees = list((deplacees[c] & Counter(gardes)).elements())
                    if consignees:
                        res.append(trad("mise à jour : {controle} — {n} constat(s) d'un fichier renommé sur la "
                                        "branche, consigné(s) sous son nouveau nom : {cles}",
                                        controle=c, n=len(consignees), cles="; ".join(consignees)))
                    nes = list((Counter(presents[c]) - Counter(de_la_base[c])).elements())
                    if nes:
                        res.append(trad("mise à jour : {controle} — {n} constat(s) né(s) sur la branche, absent(s) "
                                        "de la branche par défaut, non toléré(s) : à corriger ({cles})",
                                        controle=c, n=len(nes), cles="; ".join(nes)))
                    presents[c] = gardes
        toutes = {**existantes, **presents}
        lignes = ["[adoption.tolerated]",
                  trad("# Les constats présents à l'adoption, que `warn_only` tolère : toute autre erreur de ces\n"
                       "# contrôles échoue. En retirer durcit (libre) ; en ajouter assouplit (demande validée).")]
        for c, cles in toutes.items():
            lignes.append(f"{json.dumps(c, ensure_ascii=False)} = [")
            lignes += [f"    {json.dumps(k, ensure_ascii=False)}," for k in cles]
            lignes.append("]")
        texte = _TABLE_TOLERES.sub("", texte).rstrip("\n") + "\n\n" + "\n".join(lignes) + "\n"
        gf.write_text(texte, encoding="utf-8")
        for c in manquants:
            if mise_a_jour:
                res.append(trad("mise à jour : {controle} était désarmé en entier par l'adoption ; ses {n} "
                                "constat(s) présent(s) sont consignés comme tolérés (`[adoption.tolerated]`), et "
                                "tout constat nouveau échouera désormais (B-0180)", controle=c, n=len(presents[c])))
        projet = config.Projet.charger(cible)
    return res + contexte.bilan_adoption(projet)


def _audit(cible: Path) -> tuple[int, list[str]]:
    """Les contrôles de la CI, en bref : ce qui échoue ou avertit. Rend le
    code de sortie et les contrôles en échec."""
    r = subprocess.run([sys.executable, str(cible / config.LANCEUR), "check", "--stage", "ci", "--short"],
                       cwd=cible, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr)
    return r.returncode, en_echec_dans(r.stdout)


def note_d_audit() -> str:
    """Ce que l'audit n'a pas lancé : il lance les contrôles, pas les
    capacités de l'adaptateur (B-0168)."""
    return trad("(l'audit lance les contrôles du socle, pas les capacités de l'adaptateur : la compilation et les "
                "tests du projet n'ont pas été lancés ; `python3 .socle/socle verify --fast` les lance)")


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
                           "l'humain valide dans la conversation. La poser par `python3 .socle/socle new request "
                           '"<décision>"`, qui en dit le contrat, celui du moteur nouveau ; chaque fichier s\'y '
                           "écrit sur sa ligne, son chemin et son empreinte sans rien d'autre : ces lignes ne "
                           "comptent pas dans le budget de la demande. Poussée seule d'abord, la demande est jugée par la CI "
                           "avec le moteur d'avant, qui peut encore compter ces lignes dans son budget et la refuser "
                           ": ce refus cesse une fois les fichiers protégés commités, avec le moteur nouveau. "
                           "Poussée, elle laisse commiter et pousser ces "
                           "fichiers si la branche par défaut exige la CI du socle, qui les refuse jusqu'à la réponse "
                           "et où l'humain les lit dans la pull request (D-0071) ; sinon, ils restent dans l'arbre "
                           "jusqu'à sa réponse, puis se commitent avec elle. Une session qui a dû ajouter le dépôt du socle "
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
    # met en place le règle, pas une correction ni l'adoption. Le code de
    # sortie lit la même liste (ADR-0056).
    attentes = attentes_de_l_humain(cible)
    autres = [c for c in echecs if c not in attentes]
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
    attente = verification.commandes_en_attente(projet)
    if attente and not mise_a_jour:
        etapes.append(trad("ne pas encore lancer les outils de la CI qui attendent leur fichier de build : {ligne}",
                           ligne=verification.attente_dite(attente)))
    # L'audit n'a lancé que les contrôles : la vérification rapide lance les
    # capacités de l'adaptateur, avant que rien ne parte (B-0168).
    verifier = trad(". Avant de commiter, lancer `python3 .socle/socle verify --fast` : il lance la compilation et "
                    "les tests de l'adaptateur, que l'audit n'a pas lancés")
    if not mise_a_jour:
        verifier += trad(". S'ils échouent pour une raison que l'adaptateur porte (ses commandes, lancées à la "
                         "racine) : l'adaptateur posé est protégé, et ne se corrige plus à la main. Laisser l'essai "
                         "sur sa branche, commité, revenir à la branche de départ par `git switch`, jamais fichier "
                         "par fichier, et relancer l'installeur sur une branche neuve avec `--adapter "
                         "<fichier.toml>`")
    message = (trad("Mettre à jour le socle {version}", version=VERSION) if mise_a_jour
               else trad("Installer le socle {version}", version=VERSION))
    if mise_a_jour and "protege.fichiers" in echecs and os.environ.get(hooks.SESSION_CLOUD) == "true":
        # Le hook avant commit juge ce que le commit contient : la note qui
        # cite un fichier protégé part avec lui, la demande avant eux (B-0148).
        etapes.append(trad('dans la session qui pose la demande, commiter en deux temps : d\'abord la demande '
                           'seule, qui ne cite que ce qui est déjà commité, hors les fichiers protégés qu\'elle '
                           'approuve, et la pousser ; puis, quand elle le permet, les fichiers protégés avec ce qui '
                           'les cite (journal, chantier actif) : `git add -A && git commit -m "{message}" && git '
                           'push`. Le hook avant commit refuse une référence, chemin ou identifiant, que le commit '
                           'ne contient pas', message=message) + verifier)
    else:
        etapes.append(trad('commiter puis pousser : `git add -A && git commit -m "{message}" && git push`',
                           message=message) + verifier)
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
