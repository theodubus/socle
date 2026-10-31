"""Les liens que l'humain peut suivre.

L'humain lit les messages de l'agent dans la conversation ou sur GitHub, pas
dans le conteneur de l'agent : un lien relatif, un chemin qui n'existe pas,
ou un fichier qui n'est pas encore poussé y mènent à un 404. Ce module
calcule le permalien d'un fichier ou d'une entrée de mémoire — au commit
poussé, et non à une branche qui disparaîtra à la fusion — et repère, dans
un message, les liens que l'humain ne pourra pas suivre.

Les URL ont la forme de GitHub : `<dépôt>/blob/<commit>/<chemin>`.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit

from socle import config, requests as demandes, memory as memoire, utils as outils
from socle.messages import trad

# Un lien markdown, une URL nue, un passage entre accents graves.
LIEN_MD = re.compile(r"\[[^\]\n]*\]\((?P<cible>[^)\s]+)[^)\n]*\)")
URL = re.compile(r"https?://[^\s)>\]`\"'<]+")
CODE = re.compile(r"(?<!`)`(?P<code>[^`\n]+)`(?!`)")
SCHEMA = re.compile(r"^[A-Za-z][\w+.-]*:")
CHEMIN = re.compile(r"^[\w.@-]+(?:/[\w.@-]+)*/?$")
LIGNE = re.compile(r":\d+(?:-\d+)?$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")

# Un nom seul, sans répertoire, n'est pris pour un fichier que s'il en a
# l'extension : `outils.git` est un appel, `AGENTS.md` un fichier.
EXTENSIONS = {
    "md", "toml", "py", "rs", "json", "yml", "yaml", "txt", "sh", "lock",
    "log", "cfg", "ini", "js", "ts", "html", "css", "csv",
}


def url_depot(projet: config.Projet) -> str | None:
    """L'adresse web du dépôt : `[human] repo_url` de la politique, sinon
    celle du dépôt `origin`. `None` si elle ne se déduit pas — un relais
    local, par exemple, ne dit pas où l'humain lira."""
    explicite = projet.pol("human", "repo_url")
    if explicite:
        return str(explicite).rstrip("/")
    distant = outils.git(projet.racine, "remote", "get-url", "origin", check=False).strip()
    return depuis_distant(distant)


def depuis_distant(distant: str) -> str | None:
    if not distant:
        return None
    m = re.match(r"^[\w.-]+@(?P<hote>[\w.-]+):(?P<chemin>[^/].*)$", distant)  # git@hote:o/r.git
    if m:
        hote, chemin = m["hote"], m["chemin"]
    else:
        u = urlsplit(distant)
        if u.scheme not in ("http", "https", "ssh", "git") or not u.hostname:
            return None
        hote, chemin = u.hostname, u.path
    chemin = chemin.strip("/").removesuffix(".git")
    if "." not in hote or re.fullmatch(r"[\d.]+", hote) or chemin.count("/") != 1:
        return None
    return f"https://{hote}/{chemin}"


def ancre(titre: str) -> str:
    """L'ancre que GitHub donne à un titre : son texte rendu (sans accents
    graves ni marques de gras), en minuscules, sans ponctuation, les espaces
    changés en tirets (« B-0014 — Exiger » donne `b-0014--exiger`). Seule
    copie : les liens de la mémoire se vérifient avec elle."""
    t = re.sub(r"`|\*\*|__", "", titre.strip().lower())
    t = "".join(c for c in t if c in " -_" or unicodedata.category(c)[0] in "LNM")
    return t.replace(" ", "-")


def commit_pousse(racine) -> str | None:
    """Le dernier commit poussé de la branche courante, sinon celui de la
    branche par défaut distante."""
    defaut = outils.branche_par_defaut(racine)
    for ref in ("@{upstream}", defaut if defaut and defaut.startswith("origin/") else None):
        if ref and outils.rev_existe(racine, ref):
            return outils.resoudre(racine, ref)
    return None


def lien(projet: config.Projet, cible: str) -> tuple[str | None, str]:
    """Le permalien d'un chemin du dépôt ou d'une entrée de mémoire, et un
    avertissement : ce qui manque, ou que la version poussée n'est pas la
    version locale."""
    racine = projet.racine
    depot = url_depot(projet)
    if not depot:
        return None, trad("adresse du dépôt inconnue : l'humain la règle dans la politique (`[human] repo_url`)")
    chemin, suffixe = cible.strip().rstrip("/"), ""
    if memoire.decouper_id(chemin):
        e = memoire.Memoire.charger(racine).entree(chemin)
        if e is None:
            return None, trad("{cible} : aucune entrée de ce nom dans la mémoire", cible=cible)
        chemin = e.fichier
        if e.niveau > 1:  # une entrée parmi d'autres : son ancre
            m = memoire.TITRE_RE.match(e.texte.splitlines()[0])
            suffixe = "#" + quote(ancre(m["reste"] if m else e.titre), safe="-_")
    if memoire.est_prive(chemin):
        return _lien_prive(projet, chemin, suffixe)
    sha = commit_pousse(racine)
    if not sha:
        return None, trad("rien n'est poussé : pousser d'abord")
    sorte = outils.git(racine, "cat-file", "-t", f"{sha}:{chemin}", check=False).strip()
    if sorte not in ("blob", "tree"):
        return None, trad("{chemin} n'est pas dans la version poussée ({sha}) : pousser d'abord",
                          chemin=chemin, sha=sha[:7])
    url = f"{depot}/{sorte}/{sha}/{quote(chemin)}{suffixe}"
    avertissement = ""
    local = racine / chemin
    if sorte == "blob" and local.is_file():
        pousse = outils.git(racine, "rev-parse", f"{sha}:{chemin}", check=False).strip()
        if outils.git(racine, "hash-object", "--", chemin, check=False).strip() != pousse:
            avertissement = trad("{chemin} : la version locale n'est pas poussée, le lien montre la version "
                                 "poussée", chemin=chemin)
    return url, avertissement


def _lien_prive(projet: config.Projet, chemin: str, suffixe: str) -> tuple[str | None, str]:
    """Mode compagnon : le permalien dans le dépôt privé, que l'humain lit sur
    GitHub. Mode chiffré : aucun, GitHub n'en montre que le chiffré."""
    from socle import private as prive

    if prive.mode(projet) != "compagnon":
        return None, (trad("{chemin} est chiffré sur GitHub, où l'humain ne peut pas le lire : le lui donner "
                           "en entier dans la conversation", chemin=chemin))
    depot = prive.depot_compagnon(projet.racine)
    web = depuis_distant(outils.git(depot, "remote", "get-url", "origin", check=False).strip()) if depot else None
    sha = commit_pousse(depot) if depot else None
    if not web or not sha:
        return None, trad("dépôt privé non cloné, sans adresse web, ou rien n'y est poussé")
    interne = memoire.hors_zone_privee(chemin)
    if not outils.git(depot, "cat-file", "-t", f"{sha}:{interne}", check=False).strip():
        return None, trad("{chemin} n'est pas dans la version poussée du dépôt privé : y pousser d'abord",
                          chemin=chemin)
    return f"{web}/blob/{sha}/{quote(interne)}{suffixe}", ""


# --------------------------------------------------------------------------
# Les liens d'un message
# --------------------------------------------------------------------------


def _hors_code(message: str) -> str:
    """Le message sans ses blocs de code clôturés : des exemples, pas des
    liens donnés à suivre."""
    return "\n".join(l for _, l, code in memoire.lignes_hors_code(message) if not code)


def ressemble_a_un_chemin(texte: str) -> str | None:
    """Le chemin qu'un passage entre accents graves désigne, si c'en est
    un : le client de l'humain en fait un lien."""
    t = LIGNE.sub("", texte.strip())
    if not CHEMIN.match(t) or t.startswith(("/", "../", "~")):
        return None
    dernier = t.rstrip("/").rsplit("/", 1)[-1]
    ext = dernier.rsplit(".", 1)[1].lower() if "." in dernier[1:] else ""
    if t.endswith("/"):
        return t
    if "/" in t:
        return t if ext[:1].isalpha() else None
    return t if ext in EXTENSIONS else None


def _rev_poussee(racine, ref: str) -> str | None:
    if SHA.match(ref):
        if outils.objet_existe(racine, ref) and outils.git(
                racine, "for-each-ref", "--contains", ref, "refs/remotes", check=False).strip():
            return ref
        return None
    distante = f"refs/remotes/origin/{ref}"
    if outils.rev_existe(racine, distante):
        return distante
    # Une étiquette : publiée si une branche distante contient son commit.
    etiquette = f"refs/tags/{ref}"
    if outils.rev_existe(racine, etiquette) and outils.git(
            racine, "branch", "-r", "--contains", f"{etiquette}^{{commit}}", check=False).strip():
        return etiquette
    return None


def url_morte(racine, depot: str, url: str) -> str | None:
    """Pourquoi une URL du dépôt mène à un 404, ou `None`. Seules les URL de
    fichiers et de commits se vérifient ici ; les autres (pull requests…)
    passent."""
    if not url.lower().startswith(depot.lower() + "/"):
        return None
    reste = url[len(depot) + 1:].split("#", 1)[0].split("?", 1)[0]
    parties = [unquote(p) for p in reste.split("/") if p]
    if len(parties) >= 2 and parties[0] == "commit":
        return None if _rev_poussee(racine, parties[1]) else trad("commit {version} inconnu ou pas poussé",
                                                                  version=parties[1][:12])
    if len(parties) < 2 or parties[0] not in ("blob", "tree", "raw"):
        return None
    # Une branche peut contenir des `/` : on essaie chaque découpage.
    for i in range(2, len(parties) + 1):
        ref, chemin = "/".join(parties[1:i]), "/".join(parties[i:])
        rev = _rev_poussee(racine, ref)
        if rev:
            if not chemin or outils.git(racine, "cat-file", "-t", f"{rev}:{chemin}", check=False).strip():
                return None
            return trad("{chemin} n'existe pas dans la version poussée « {ref} »", chemin=chemin, ref=ref[:12])
    return trad("version « {version} » inconnue ou pas poussée", version=parties[1][:12])


def problemes(projet: config.Projet, message: str) -> tuple[list[str], list[str]]:
    """(liens morts, demandes sans lien) du message de l'agent."""
    racine = projet.racine
    texte = memoire.sans_barre(_hors_code(message))
    morts = []
    for m in LIEN_MD.finditer(texte):
        cible = m["cible"]
        if not SCHEMA.match(cible) and not cible.startswith("#"):
            morts.append(trad("lien relatif « {cible} » : hors du conteneur, il ne mène nulle part", cible=cible))
    for m in CODE.finditer(texte):
        chemin = ressemble_a_un_chemin(m["code"])
        if chemin and not (racine / chemin).exists():
            morts.append(trad("`{code}` : aucun chemin de ce nom dans le dépôt, le lien qu'en fait le client "
                              "mène à un 404", code=m['code']))
    depot = url_depot(projet)
    urls = URL.findall(texte)
    if depot:
        for u in urls:
            pourquoi = url_morte(racine, depot, u.rstrip(".,;:"))
            if pourquoi:
                morts.append(f"{u} : {pourquoi}")
    sans_lien = []
    if depot:
        cibles = [unquote(u) for u in urls]
        for d in demandes.toutes(racine):
            if d.reponse is not None or d.statut != "en attente" or not d.id:
                continue
            if memoire.est_prive(d.chemin) and lien(projet, d.chemin)[0] is None:
                continue  # chiffrée sur GitHub : donnée en entier dans la conversation
            # Une demande privée se lie dans le dépôt privé, sans le préfixe de la zone privée.
            chemin = memoire.hors_zone_privee(d.chemin)
            if re.search(rf"(?<![\w-]){re.escape(d.id)}(?![\w-])", texte) and not any(chemin in u for u in cibles):
                sans_lien.append(d.id)
    return morts, sans_lien
