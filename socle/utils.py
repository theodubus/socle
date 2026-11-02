"""Outils communs : git, motifs de chemins, texte.

Tout passe par git plutôt que par le système de fichiers quand une question
porte sur l'historique : l'état dérivé et les contrôles « ajout seul » n'ont
de sens que comparés à une révision, jamais à un souvenir.
"""

from __future__ import annotations

import codecs
import difflib
import hashlib
import os
import re
import stat
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

# L'arbre vide de git : sert de base quand il n'y en a pas (premier commit,
# dépôt neuf), pour que « tout est ajouté » se calcule comme un diff ordinaire.
ARBRE_VIDE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class ErreurGit(RuntimeError):
    pass


def git(racine: Path, *args: str, check: bool = True, entree: str | None = None) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=racine,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=entree,
    )
    if check and r.returncode != 0:
        raise ErreurGit(f"git {' '.join(args)} : {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


# Ce par quoi git désigne un dépôt à ses commandes. Git le passe à ses hooks,
# en chemin absolu depuis un worktree secondaire : hérité par les tests du
# projet ou par git dans un autre dépôt (un dépôt jetable, le clone de la
# mémoire privée), il les faisait viser le dépôt du projet.
VARIABLES_DE_DEPOT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX",
                      "GIT_QUARANTINE_PATH")
# L'index que juge le hook avant commit, seul usage légitime de ces
# variables : un `git commit -a` en passe un temporaire.
_index_du_hook: str | None = None


def isoler_du_hook(racine: Path) -> None:
    """Au début d'un hook git : retient en chemin absolu l'index que git
    juge, puis retire de l'environnement ce qui désigne un dépôt. Chaque
    commande retrouve alors son dépôt par son dossier, le projet comme un
    autre."""
    global _index_du_hook
    index = os.environ.get("GIT_INDEX_FILE")
    _index_du_hook = str(Path(racine, index).resolve()) if index else None
    for v in VARIABLES_DE_DEPOT:
        os.environ.pop(v, None)


def arbre_de_l_index(racine: Path) -> str | None:
    """L'index figé en arbre (`write-tree`) : celui que le hook avant commit
    juge, ou celui du dépôt."""
    env = dict(os.environ, GIT_INDEX_FILE=_index_du_hook) if _index_du_hook else None
    r = subprocess.run(["git", "write-tree"], cwd=racine, capture_output=True, text=True, env=env)
    return r.stdout.strip() or None if r.returncode == 0 else None


def git_reussit(racine: Path, *args: str) -> bool:
    r = subprocess.run(["git", *args], cwd=racine, capture_output=True)
    return r.returncode == 0


def trouver_racine(depart: Path | None = None) -> Path:
    """La racine du projet : celle du dépôt git, sinon le premier parent qui
    porte un `.socle/`."""
    depart = (depart or Path.cwd()).resolve()
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=depart, capture_output=True, text=True
    )
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    for p in [depart, *depart.parents]:
        if (p / ".socle").is_dir():
            return p
    return depart


def est_depot(racine: Path) -> bool:
    return git_reussit(racine, "rev-parse", "--git-dir")


def a_des_commits(racine: Path) -> bool:
    return git_reussit(racine, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")


def rev_existe(racine: Path, rev: str) -> bool:
    return git_reussit(racine, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")


def objet_existe(racine: Path, sha: str) -> bool:
    return git_reussit(racine, "cat-file", "-e", f"{sha}^{{commit}}")


# Les dépôts dont les pull requests ont déjà été récupérées par ce processus.
_PULL_REQUESTS_RECUPEREES: set[str] = set()


def recuperer_pull_requests(racine: Path) -> bool:
    """Les têtes des pull requests de l'origine, une fois par dépôt et par
    processus. GitHub garde le commit d'une pull request même quand sa
    branche est supprimée ou fusionnée par écrasement, mais un clone ne
    récupère que les branches et les étiquettes : un commit que la mémoire
    cite disparaissait ainsi de la CI (B-0117). Sans origine ou sans
    réseau, rien n'est récupéré, et rien n'échoue."""
    cle = str(Path(racine).resolve())
    if cle in _PULL_REQUESTS_RECUPEREES:
        return False
    _PULL_REQUESTS_RECUPEREES.add(cle)
    return git_reussit(racine, "fetch", "--quiet", "--no-tags", "origin", "+refs/pull/*/head:refs/socle/pull/*")


def etiqueter(commits: list[str]) -> str:
    """La commande qui garde des commits par une étiquette chacun, poussée :
    un clone ne récupère que les branches et les étiquettes (B-0116)."""
    etiquettes = [f"cite/{c}" for c in commits]
    return " && ".join([f"git tag {e} {c}" for e, c in zip(etiquettes, commits)]
                       + [f"git push origin {' '.join(etiquettes)}"])


def resoudre(racine: Path, rev: str) -> str:
    return git(racine, "rev-parse", f"{rev}^{{commit}}").strip()


def fichiers_courants(racine: Path) -> list[str]:
    """Fichiers suivis et non suivis non ignorés, tels qu'ils sont sur disque."""
    if not est_depot(racine):
        return sorted(
            str(p.relative_to(racine)).replace(os.sep, "/")
            for p in racine.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )
    sortie = git(racine, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    vus = []
    for nom in sortie.split("\0"):
        if nom and (racine / nom).is_file():
            vus.append(nom)
    return sorted(set(vus))


def fichiers_a(racine: Path, rev: str | None) -> list[str]:
    if rev is None or rev == ARBRE_VIDE:
        return []
    sortie = git(racine, "ls-tree", "-r", "-z", "--name-only", rev)
    return [n for n in sortie.split("\0") if n]


def lire_a(racine: Path, rev: str | None, chemin: str) -> str | None:
    """Le contenu d'un fichier à une révision ; `None` s'il n'y existe pas.
    `rev=None` veut dire « l'arbre de travail »."""
    if rev is None:
        p = racine / chemin
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    if rev == ARBRE_VIDE:
        return None
    r = subprocess.run(
        ["git", "show", f"{rev}:{chemin}"], cwd=racine, capture_output=True
    )
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def empreinte_arbre(racine: Path) -> str:
    """Ce qu'une vérification a vu : HEAD, le diff courant, et le contenu des
    fichiers non suivis, pas seulement leurs noms : un fichier nouveau
    modifié après une vérification réussie la rend caduque."""
    tete = git(racine, "rev-parse", "HEAD", check=False).strip()
    diff = git(racine, "diff", "HEAD", check=False)
    autres = git(racine, "ls-files", "--others", "--exclude-standard", check=False)
    contenus = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=racine, input=autres,
                              capture_output=True, text=True).stdout if autres.strip() else ""
    return sha256(tete + diff + autres + contenus)


def empreinte_contenu(racine: Path, hors: tuple[str, ...] = ()) -> str:
    """Le contenu de l'arbre de travail, fichiers non suivis compris, tel que
    git l'écrirait en arbre : un commit qui n'y change rien le garde, à la
    différence d'`empreinte_arbre`. Les chemins qui commencent par l'un de
    `hors` n'y entrent pas (B-0086)."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as dossier:
        index = Path(dossier) / "index"
        reel = git(racine, "rev-parse", "--git-path", "index", check=False).strip()
        if reel and (racine / reel).is_file():
            # Ses dates évitent de tout relire, la sienne comprise : git relit une
            # entrée datée de la seconde de l'index, et une copie datée du moment
            # lui ferait croire inchangé un fichier modifié dans cette seconde (B-0091).
            shutil.copy2(racine / reel, index)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        subprocess.run(["git", "add", "-A"], cwd=racine, env=env, capture_output=True)
        arbre = subprocess.run(["git", "write-tree"], cwd=racine, env=env, capture_output=True,
                               text=True).stdout.strip()
    lignes = git(racine, "ls-tree", "-r", "--full-tree", arbre, check=False).splitlines() if arbre else []
    return sha256("".join(l + "\n" for l in lignes if not l.split("\t", 1)[-1].startswith(hors)))


def lire_plusieurs(racine: Path, rev: str, chemins: list[str]) -> dict[str, str | None]:
    """Le contenu de plusieurs fichiers à une révision, en un seul processus
    git (`cat-file --batch`) au lieu d'un `git show` par fichier ; `None`
    pour un fichier absent."""
    if not chemins or rev == ARBRE_VIDE:
        return {c: None for c in chemins}
    entree = "".join(f"{rev}:{c}\n" for c in chemins).encode("utf-8")
    sortie = subprocess.run(["git", "cat-file", "--batch"], cwd=racine, input=entree, capture_output=True).stdout
    res, i = {}, 0
    for c in chemins:
        fin = sortie.index(b"\n", i)
        entete = sortie[i:fin].split()
        i = fin + 1
        if len(entete) != 3 or entete[1] != b"blob":
            res[c] = None
            if len(entete) == 3:
                i += int(entete[2]) + 1
            continue
        taille = int(entete[2])
        res[c] = sortie[i:i + taille].decode("utf-8", errors="replace")
        i += taille + 1
    return res


def fichiers_changes(racine: Path, base: str | None, tete: str | None = None) -> list[str]:
    """Chemins changés entre `base` et `tete`. `tete=None` : l'arbre de
    travail, non suivis compris."""
    base = base or ARBRE_VIDE
    if tete is None:
        if a_des_commits(racine):
            sortie = git(racine, "diff", "--name-only", "--no-renames", "-z", base)
        else:
            sortie = ""
        noms = {n for n in sortie.split("\0") if n}
        autres = git(racine, "ls-files", "-z", "--others", "--exclude-standard")
        noms |= {n for n in autres.split("\0") if n}
        if not a_des_commits(racine):
            indexes = git(racine, "ls-files", "-z", "--cached")
            noms |= {n for n in indexes.split("\0") if n}
        return sorted(noms)
    sortie = git(racine, "diff", "--name-only", "--no-renames", "-z", base, tete)
    return sorted(n for n in sortie.split("\0") if n)


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)


def renommes(racine: Path, base: str, tete: str | None = None) -> dict[str, str]:
    """{nom à la base: nom à la tête} : les renommages que git reconnaît,
    commit par commit de `base` à `tete`, puis jusqu'à l'arbre de travail
    (`tete` absent) ou à l'arbre jugé (l'index, au commit). Commit par commit
    et non d'un bloc : un fichier renommé et beaucoup modifié depuis la base
    ne ressemble plus assez à son ancien texte pour que git l'apparie. La
    fusion d'une pull request se parcourt par sa branche."""
    commit = bool(tete) and git(racine, "cat-file", "-t", tete, check=False).strip() == "commit"
    fin = tete if commit else "HEAD"
    # La fusion que GitHub fabrique pour la CI d'une pull request : son
    # premier parent est la base, le second la branche. En premier parent, la
    # plage ne serait que cette fusion, d'un bloc : on suit la branche, puis
    # le pas de la fusion elle-même.
    fusion = []
    parents = git(racine, "rev-list", "--parents", "-n", "1", fin, check=False).split()[1:]
    if len(parents) == 2 and git_reussit(racine, "merge-base", "--is-ancestor", parents[0], base):
        fusion = [_renommages(git(racine, "diff", "-M", "--name-status", "-z", parents[1], fin, check=False))]
        fin = parents[1]
    sortie = git(racine, "log", "--reverse", "--first-parent", "-M", "--name-status", "--format=%x01", "-z",
                 f"{base}..{fin}", check=False)
    etapes = [_renommages(bloc) for bloc in sortie.split("\x01")[1:]] + fusion
    if not commit:
        etapes.append(_renommages(git(racine, "diff", "-M", "--name-status", "-z", "HEAD", *([tete] if tete else []),
                                      check=False)))
    res: dict[str, str] = {}
    for etape in etapes:
        origine = {neuf: ancien for ancien, neuf in res.items()}
        for ancien, neuf in etape.items():
            res[origine.get(ancien, ancien)] = neuf
    return {a: b for a, b in res.items() if a != b}


def _renommages(sortie: str) -> dict[str, str]:
    """Les renommages d'une sortie `--name-status -z` de git."""
    jetons, res, i = sortie.split("\0"), {}, 0
    while i < len(jetons):
        statut = jetons[i].strip("\n")
        if not statut:
            i += 1
        elif statut[:1] in ("R", "C"):
            if statut[:1] == "R" and i + 2 < len(jetons):
                res[jetons[i + 1]] = jetons[i + 2]
            i += 3
        else:
            i += 2
    return res


def lignes_changees(racine: Path, base: str | None, tete: str | None, chemin: str,
                    ancien: str | None = None) -> set[int] | None:
    """Les lignes de `chemin`, dans la tête, ajoutées ou modifiées depuis
    `base`, où il s'appelait `ancien` s'il a été renommé ; une suppression
    marque la ligne qui la suit. `None` : le fichier n'existait pas dans la
    base, tout y est nouveau."""
    source = ancien or chemin
    avant = lire_a(racine, base, source) if base else None
    if avant is None:
        return None
    if source != chemin:
        # Renommé : les deux textes se comparent directement ; git, d'une
        # base lointaine, ne reconnaît plus le fichier sous son nouveau nom.
        res = set()
        a, b = avant.splitlines(), (lire_a(racine, tete, chemin) or "").splitlines()
        for quoi, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if quoi in ("replace", "insert"):
                res |= set(range(j1 + 1, j2 + 1))
            elif quoi == "delete":
                res.add(j1 + 1)
        return res
    args = ["diff", "-U0", "--no-color", "--no-ext-diff", base] + ([tete] if tete else []) + ["--", chemin]
    res = set()
    for m in HUNK.finditer(git(racine, *args, check=False)):
        debut, n = int(m.group(1)), int(m.group(2) or 1)
        res |= set(range(debut, debut + n)) if n else {debut + 1}
    return res


def branche_par_defaut(racine: Path) -> str | None:
    """`origin/main`, `origin/master`, ou ce que pointe `origin/HEAD`."""
    return _branche_par_defaut(racine)[0]


def branche_par_defaut_devinee(racine: Path) -> bool:
    """La branche par défaut n'est que devinée : ce clone n'a ni `origin/HEAD`
    ni `main` ni `master`, et la branche suivie de la branche courante en
    tient lieu. Un clone qui n'a récupéré que sa branche de travail prend
    ainsi celle-ci pour la branche par défaut."""
    return _branche_par_defaut(racine)[1]


def _branche_par_defaut(racine: Path) -> tuple[str | None, bool]:
    r = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        cwd=racine, capture_output=True, text=True,
    )
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().removeprefix("refs/remotes/"), False
    for nom in ("origin/main", "origin/master", "main", "master"):
        if rev_existe(racine, nom):
            return nom, False
    # Un dépôt neuf n'a parfois encore que sa branche de travail : ce qui est
    # déjà poussé sert alors de base, plutôt que pas de base du tout.
    r = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=racine, capture_output=True, text=True,
    )
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip(), True
    return None, False


def base_de_travail(racine: Path) -> str | None:
    """La base contre laquelle l'agent et les hooks git comparent : le point
    de divergence avec la branche par défaut. `None` si rien ne s'y prête."""
    if not a_des_commits(racine):
        return None
    defaut = branche_par_defaut(racine)
    if defaut is None:
        return None
    r = subprocess.run(
        ["git", "merge-base", "HEAD", defaut], cwd=racine, capture_output=True, text=True
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    # Égale à HEAD (branche neuve, ou tout est déjà poussé), elle reste la
    # bonne base : le travail en cours est dans l'arbre, comparé à elle.
    return r.stdout.strip()


def commits(racine: Path, base: str | None, tete: str = "HEAD") -> list[dict]:
    """Les commits de `base..tete`, du plus ancien au plus récent."""
    plage = tete if base in (None, ARBRE_VIDE) else f"{base}..{tete}"
    sortie = git(racine, "log", "--reverse", "--format=%H%x00%P%x00%B%x1e", plage)
    res = []
    for bloc in sortie.split("\x1e"):
        bloc = bloc.strip("\n")
        if not bloc:
            continue
        sha, parents, message = bloc.split("\0", 2)
        res.append({"sha": sha, "parents": parents.split(), "message": message})
    return res


TRAILER = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*:\s*(.*\S)\s*$")


def trailers(message: str) -> dict[str, list[str]]:
    """Les trailers du dernier paragraphe d'un message de commit, clés en
    minuscules."""
    paragraphes = [p for p in re.split(r"\n\s*\n", message.strip()) if p.strip()]
    if len(paragraphes) < 2:
        return {}
    res: dict[str, list[str]] = {}
    for ligne in paragraphes[-1].splitlines():
        m = TRAILER.match(ligne)
        if m:
            res.setdefault(m.group(1).lower(), []).append(m.group(2))
    return res


@lru_cache(maxsize=512)
def motif_vers_regex(motif: str) -> re.Pattern:
    """Motif de chemin à la gitignore, relatif à la racine : `*` ne traverse pas
    `/`, `**/` traverse zéro ou plusieurs répertoires, `**` final prend tout."""
    i, n, res = 0, len(motif), []
    while i < n:
        c = motif[i]
        if motif.startswith("**/", i):
            res.append("(?:.*/)?")
            i += 3
        elif motif.startswith("**", i):
            res.append(".*")
            i += 2
        elif c == "*":
            res.append("[^/]*")
            i += 1
        elif c == "?":
            res.append("[^/]")
            i += 1
        else:
            res.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(res) + "$")


def correspond(chemin: str, motifs) -> bool:
    if isinstance(motifs, str):
        motifs = [motifs]
    return any(motif_vers_regex(m).match(chemin) for m in motifs)


def filtrer(chemins, motifs, exclus=()) -> list[str]:
    return [c for c in chemins if correspond(c, motifs) and not correspond(c, exclus)]


def nom_du_travail(workflow: str) -> str | None:
    """Le nom du premier travail d'un workflow GitHub, celui qu'une
    protection de branche exige."""
    m = re.search(r"(?m)^ {4}name:\s*(.+?)\s*$", workflow)
    return m.group(1).strip("'\"") if m else None


def sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )


def cle(texte: str) -> str:
    """Forme canonique d'un mot-clé : minuscules, sans accents, espaces en tirets."""
    return re.sub(r"\s+", "-", sans_accents(texte).strip().lower())


def sha256(donnees: bytes | str) -> str:
    if isinstance(donnees, str):
        donnees = donnees.encode("utf-8")
    return hashlib.sha256(donnees).hexdigest()


def ecrire(chemin: Path, texte: str, executable: bool = False):
    """Écrit un fichier en UTF-8, ses dossiers créés au besoin."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    if executable:
        chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ajouter_lignes(chemin: Path, lignes: list[str], commentaire: str = "") -> list[str]:
    """Ajoute à la fin d'un fichier de configuration (`.gitignore`…) les
    lignes qui n'y sont pas encore, sous un commentaire qui dit pourquoi,
    séparées de ce qui précède par une ligne vide ; rend celles qu'il a
    ajoutées. Rien ne change si toutes y sont."""
    texte = chemin.read_text(encoding="utf-8") if chemin.is_file() else ""
    presentes = set(texte.splitlines())
    manquantes = [l for l in lignes if l not in presentes]
    if manquantes:
        bloc = ([commentaire] if commentaire else []) + manquantes
        chemin.write_text(texte.rstrip("\n") + ("\n\n" if texte.strip() else "") + "\n".join(bloc) + "\n",
                          encoding="utf-8")
    return manquantes


def empreinte_fichier(chemin: Path) -> str:
    return sha256(chemin.read_bytes())


def est_texte(chemin: Path, limite: int = 2_000_000) -> bool:
    try:
        if chemin.stat().st_size > limite:
            return False
        with chemin.open("rb") as f:
            debut = f.read(4096)
        if b"\0" in debut:
            return False
        # Décodeur incrémental : 4096 octets peuvent couper un caractère en
        # deux, ce qui n'en fait pas un fichier binaire.
        codecs.getincrementaldecoder("utf-8")().decode(debut, final=False)
        return True
    except (OSError, UnicodeDecodeError):
        return False
