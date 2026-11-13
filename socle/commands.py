"""Une commande shell, découpée en commandes simples, pour que les hooks
jugent ce qu'elle fait et non le texte qu'elle cite.

Un heredoc, une chaîne entre guillemets ou un message de commit qui
nomment une commande dangereuse ne la lancent pas ; un lanceur entre
guillemets, un `git -C .`, des drapeaux groupés (`-fu`) ou un `cd` la
lancent bien. Le découpage suit les guillemets, les séparateurs (`;`, `&&`,
`||`, `|`, fin de ligne), les redirections, les `cd`, les préfixes (`env`,
`sudo`, `nohup`…) et les `bash -c`.

Les variables affectées dans la commande (`F=x`, `export F=x`, `F+=y`) et
les dossiers où elle passe (`cd`, `pushd`, `popd`) se suivent, la cible
d'un `cd` développée au moment du `cd` ; le découpage suppose qu'un
sous-shell `( … )`, une substitution (`$(…)`, accents graves, `<(…)`),
chaque élément d'un pipeline et une tâche de fond (`&`) ne les transmettent
pas à la suite. `developper` rend un mot comme le shell le développerait,
de son `~` et de ses variables, et marque ce qu'il ne sait pas développer ;
`accolades` et `se_croisent` disent ce qu'une accolade et un motif du shell
nomment ; `demesure`, qu'une commande est trop longue ou trop imbriquée
pour être découpée sans risque (B-0171, ADR-0072).

Heuristique, comme tout ce qui lit du shell sans l'exécuter : les mots
réservés (`if`, `then`, `{`, B-0204), les alias, les fonctions, `source`,
l'état qu'un `eval` laisse et ce que lance une substitution entre
guillemets (`"$(…)"`) ne sont pas suivis. Le hook n'est qu'un étage ; la CI
juge ce qui est commité.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from collections import ChainMap
from dataclasses import dataclass, field

# Les préfixes qui lancent la commande qui les suit.
PREFIXES = {"sudo", "command", "exec", "nohup", "time", "builtin", "nice", "stdbuf", "timeout", "xargs", "env"}
# Les options de ces préfixes qui prennent une valeur.
VALEURS = {"sudo": ("-u", "-g", "-C"), "nice": ("-n",), "env": ("-u", "-C"), "timeout": ("-s", "-k"),
           "xargs": ("-I", "-L", "-P", "-n", "-s", "-E", "-d")}
HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([\w.-]+)\2")
# Une affectation : son nom, l'indice d'un élément de tableau (`T[0]=x`),
# un `+` qui ajoute à la valeur (`F+=x`), la valeur.
AFFECTATION = re.compile(r"([A-Za-z_]\w*)(\[[^\]]*\])?(\+?)=(.*)", re.S)
# Ce qui affecte une variable du shell courant par ses arguments `NOM=valeur`.
DECLARATIONS = {"export", "declare", "typeset", "local", "readonly"}
# Les drapeaux d'une déclaration après lesquels le hook ne connaît plus la
# valeur : un tableau (`-a`, `-A`), une référence à une autre variable
# (`-n`), une valeur convertie (`-i`, `-l`, `-u`, `-c`).
DRAPEAUX_INCONNUS = {"declare": "naAiluc", "typeset": "naAiluc", "local": "naAiluc", "readonly": "aA"}
# `${NOM:=valeur}` et `${NOM=valeur}` affectent `NOM` en se développant.
DEFAUT_AFFECTE = re.compile(r"\$\{([A-Za-z_]\w*):?=")
# Les options de `read` qui prennent une valeur.
VALEURS_READ = ("-p", "-d", "-n", "-N", "-t", "-u", "-a")
# Une part d'un mot que le hook ne sait pas développer : une variable
# inconnue, une substitution de commande.
INCONNU = "\0"
# Les variables que le shell tient lui-même : leur valeur dans
# l'environnement du hook n'est pas celle du shell de l'agent (`_`, le
# chemin de python3 ; `OLDPWD`, le dossier d'un autre shell). Un shell neuf
# ne prend pas non plus `IFS` dans son environnement.
SPECIALES = frozenset({
    "_", "PWD", "OLDPWD", "IFS", "RANDOM", "SRANDOM", "SECONDS", "LINENO", "BASHPID", "PPID", "EPOCHSECONDS",
    "EPOCHREALTIME", "BASH_COMMAND", "BASH_SUBSHELL", "BASH_ARGV", "BASH_ARGC", "BASH_SOURCE", "BASH_LINENO",
    "BASH_REMATCH", "DIRSTACK", "FUNCNAME", "PIPESTATUS", "GROUPS", "HISTCMD", "REPLY", "MAPFILE", "OPTARG",
    "OPTIND", "COPROC"})
# Le repère, dans le texte que lit `shlex`, d'une part mise de côté
# (`_preparer`).
REPERE = re.compile("\x01(\\d+)\x01")
# Les opérateurs du shell, les plus longs d'abord : `shlex` rend d'un bloc
# une suite de ponctuations (`);`, `)>`).
OPERATEURS = (";;&", "&>>", "<<<", ";;", ";&", "&&", "||", "|&", "&>", ">>", ">|", ">&", "<&", "<<", "<>",
              ";", "&", "|", "(", ")", "<", ">", "\n")
# Ce que `developper` développe, hors du `~` de tête : une variable, une
# substitution, un motif étendu.
A_DEVELOPPER = re.compile(r"[$`]|[?*+@!]\(")
# Le nom d'une variable, ou un paramètre spécial, après un `$`.
NOM_APRES_DOLLAR = re.compile(r"[A-Za-z_]\w*|[\d@*#?$!-]")
# Au-delà, le hook ne découpe pas une commande (`demesure`) : plus de
# `LONGUEUR_MAX` caractères hors du corps de ses heredocs, le découpage
# risquerait de dépasser le délai du hook ; plus de `PROFONDEUR_MAX`
# parenthèses ou accolades ouvertes à la fois, d'épuiser la pile de python.
# Une valeur développée plus longue que `LONGUEUR_MAX`, que seule une
# variable dupliquée rend (`F=$F$F`), est inconnue (seconde revue de
# B-0171, constat 4, ADR-0072).
LONGUEUR_MAX = 10_000
PROFONDEUR_MAX = 32
# Les échappements d'une chaîne `$'…'`.
ECHAPPEMENTS = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}


@dataclass
class Commande:
    argv: list[str]
    # Les fichiers que ses redirections écrivent (`>`, `>>`, `>|`, `&>`).
    redirige: list[str] = field(default_factory=list)
    # Le dossier où elle s'exécute, relatif au dossier de départ (`""` : le
    # même), ou absolu après un `cd` absolu.
    dossier: str = ""
    # Ce qui la précède et que `_sans_prefixes` retire : affectations de
    # variables (`GIT_DIR=…`), `env`, `sudo`… et leurs options.
    prefixe: list[str] = field(default_factory=list)
    # Les variables affectées avant elle dans le même texte, dans l'ordre :
    # (nom, valeur telle qu'écrite), la valeur `None` quand elle vient
    # d'ailleurs (`read`, `for`) ; un `cd` y pose `PWD` et `OLDPWD`.
    affectations: list[tuple[str, str | None]] = field(default_factory=list)
    # Le dossier où elle s'exécute, développé avec les variables connues au
    # moment de chaque `cd` : absolu si l'environnement d'`analyser` donne
    # `PWD`, `INCONNU` à la place de ce qui ne se développe pas (B-0171).
    lieu: str = ""
    # Les variables de `affectations`, déjà développées avec l'environnement
    # d'`analyser`, que `variables_de` reprend sans les redévelopper.
    connues: dict[str, str] | None = field(default=None, repr=False, compare=False)
    environnement: dict[str, str] | None = field(default=None, repr=False, compare=False)

    @property
    def programme(self) -> str:
        return self.argv[0].rsplit("/", 1)[-1] if self.argv else ""

    def chemin(self, nom: str) -> str:
        """Un chemin de la commande, rapporté au dossier de départ."""
        if nom.startswith(("/", "~")) or not self.dossier:
            return nom
        return posixpath.normpath(posixpath.join(self.dossier, nom))


def sans_heredocs(texte: str) -> str:
    """Le texte sans le corps de ses heredocs : un document, pas une commande."""
    res, attendus = [], []
    for ligne in texte.split("\n"):
        if attendus:
            fin, tabs = attendus[0]
            if (ligne.lstrip("\t") if tabs else ligne) == fin:
                attendus.pop(0)
            continue
        res.append(ligne)
        attendus += [(m.group(3), m.group(1) == "-") for m in HEREDOC.finditer(ligne)]
    return "\n".join(res)


def _fin_guillemets(texte: str, i: int) -> int:
    """L'index après la chaîne `"…"` ouverte en `i`, comme `shlex` la lit."""
    j, n = i + 1, len(texte)
    while j < n and texte[j] != '"':
        j += 2 if texte[j] == "\\" else 1
    return min(j + 1, n)


def _fermante(texte: str, i: int) -> int:
    """L'index après la parenthèse qui ferme celle de `i`, guillemets
    sautés ; la fin du texte si rien ne la ferme."""
    profondeur, j, n = 0, i, len(texte)
    while j < n:
        ch = texte[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "'":
            k = texte.find("'", j + 1)
            j = n if k < 0 else k + 1
            continue
        if ch == '"':
            j = _fin_guillemets(texte, j)
            continue
        profondeur += {"(": 1, ")": -1}.get(ch, 0)
        j += 1
        if profondeur == 0:
            return j
    return n


def _ansi_c(texte: str, i: int) -> tuple[int, str | None]:
    """L'index après une chaîne `$'…'` dont le corps commence en `i`, et la
    chaîne qu'elle nomme ; `None` si le hook ne sait pas la lire (`\\c`, un
    caractère nul, une chaîne non fermée)."""
    res, n, sure = [], len(texte), True
    while i < n:
        ch = texte[i]
        if ch == "'":
            valeur = "".join(res)
            return i + 1, valeur if sure and not {INCONNU, "\x01"} & set(valeur) else None
        if ch != "\\":
            res.append(ch)
            i += 1
            continue
        suite = texte[i + 1:i + 2]
        code = re.match(r"[0-7]{1,3}|x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}", texte[i + 1:])
        if suite in ECHAPPEMENTS:
            res.append(ECHAPPEMENTS[suite])
            i += 2
        elif code:
            g = code.group()
            valeur = int(g[1:], 16) if g[0] in "xuU" else int(g, 8)
            if 0 < valeur <= 0x10FFFF:
                res.append(chr(valeur))
            else:
                sure = False
            i += 1 + len(g)
        elif suite in ("c", ""):
            sure = False
            i += 2
        else:
            res.append("\\" + suite)
            i += 2
    return n, None


def _ouvre_des_valeurs(texte: str, i: int) -> bool:
    """Le `(` en `i` ouvre-t-il un motif étendu (`@(…)`, `*(…)`, `!(…)`…)
    ou les valeurs d'un tableau (`T=(…)`, `T+=(…)`), que le shell ne lit pas
    comme un sous-shell ?"""
    avant = texte[max(0, i - 200):i]
    if avant[-1:] in ("?", "*", "+", "@", "!") and avant[-2:-1] != "$":
        return True
    return bool(re.search(r"(?:^|[\s;&|(])[A-Za-z_]\w*(?:\[[^\]]*\])?\+?=\Z", avant))


def _preparer(texte: str) -> tuple[str, list[tuple[str, str | None]]]:
    """Le texte pour `shlex`, chaque part qu'il couperait à tort ou lirait
    tel quel remplacée par un repère (`REPERE`) : une substitution (`$(…)`,
    accents graves, `<(…)`, `>(…)`), une expression arithmétique, les
    valeurs d'un tableau, un motif étendu, une chaîne `$'…'` que le hook ne
    sait pas lire. Rend aussi ces parts : (texte d'origine, commande qu'elle
    lance dans un sous-shell, ou `None`). Une chaîne `$'…'` simple devient
    la chaîne qu'elle nomme, `$"…"` une chaîne entre guillemets. Hors des
    guillemets seulement, comme `shlex` les lit ; un `#` y ouvre, comme pour
    lui, un commentaire jusqu'à la fin de la ligne."""
    texte = texte.replace("\x01", "")
    res: list[str] = []
    parts: list[tuple[str, str | None]] = []
    i, n = 0, len(texte)

    def mettre(fin: int, interne: str | None = None):
        nonlocal i
        parts.append((texte[i:fin], interne))
        res.append(f"\x01{len(parts) - 1}\x01")
        i = fin

    while i < n:
        ch = texte[i]
        if ch == "\\":
            res.append(texte[i:i + 2])
            i += 2
        elif ch == "'":
            fin = texte.find("'", i + 1)
            fin = n if fin < 0 else fin + 1
            res.append(texte[i:fin])
            i = fin
        elif ch == '"':
            fin = _fin_guillemets(texte, i)
            res.append(texte[i:fin])
            i = fin
        elif ch == "#":
            fin = texte.find("\n", i)
            fin = n if fin < 0 else fin
            res.append(texte[i:fin])
            i = fin
        elif texte.startswith("$'", i):
            fin, valeur = _ansi_c(texte, i + 2)
            if valeur is None:
                mettre(fin)
            else:
                res.append("'" + valeur.replace("'", "'\\''") + "'")
                i = fin
        elif texte.startswith('$"', i):
            i += 1  # le `"` qui suit ouvre une chaîne ordinaire
        elif texte.startswith("$((", i):
            mettre(_fermante(texte, i + 1))
        elif texte.startswith(("$(", "<(", ">("), i):
            fin = _fermante(texte, i + 1)
            mettre(fin, texte[i + 2:fin - 1 if texte[fin - 1:fin] == ")" else fin])
        elif ch == "`":
            fin = i + 1
            while fin < n and texte[fin] != "`":
                fin += 2 if texte[fin] == "\\" else 1
            mettre(min(fin + 1, n), re.sub(r"\\([$`\\])", r"\1", texte[i + 1:fin]))
        elif ch == "(" and _ouvre_des_valeurs(texte, i):
            fin = _fermante(texte, i)
            # `!(…)` en tête d'une commande est une négation suivie d'un
            # sous-shell : ce qu'il contient se juge aussi comme commande.
            mettre(fin, texte[i + 1:fin - 1] if texte[i - 1] == "!" else None)
        else:
            res.append(ch)
            i += 1
    return "".join(res), parts


def _jetons(texte: str) -> list[tuple[str, list[str]]]:
    """Les mots et les opérateurs de la commande, guillemets retirés, chacun
    avec les commandes que ses substitutions lancent."""
    prepare, parts = _preparer(sans_heredocs(texte.replace("\\\n", " ")))
    lex = shlex.shlex(prepare, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        bruts = list(lex)
    except ValueError:  # guillemets non fermés : on juge chaque mot tel quel
        bruts = prepare.split()
    res: list[tuple[str, list[str]]] = []
    for j in bruts:
        if _operateur(j):
            res += [(o, []) for o in _operateurs(j)]
            continue
        internes = [interne for k in REPERE.findall(j) if (interne := parts[int(k)][1]) is not None]
        res.append((REPERE.sub(lambda m: parts[int(m.group(1))][0], j), internes))
    return res


def jetons(texte: str) -> list[str]:
    """Les mots et les opérateurs de la commande, guillemets retirés."""
    return [j for j, _ in _jetons(texte)]


def _operateur(jeton: str) -> bool:
    return bool(jeton) and all(c in ";&|()<>\n" for c in jeton)


def _operateurs(jeton: str) -> list[str]:
    """Les opérateurs d'une suite de ponctuations que `shlex` rend d'un bloc."""
    res, i = [], 0
    while i < len(jeton):
        o = next(o for o in OPERATEURS if jeton.startswith(o, i))
        res.append(o)
        i += len(o)
    return res


def _sans_prefixes(argv: list[str]) -> list[str]:
    """La commande lancée derrière ses affectations et ses préfixes."""
    while argv:
        if AFFECTATION.fullmatch(argv[0]):
            argv = argv[1:]
        elif argv[0].rsplit("/", 1)[-1] in PREFIXES:
            nom = argv[0].rsplit("/", 1)[-1]
            argv = argv[1:]
            # Leurs options, et la valeur de celles qui en prennent une.
            while argv and (argv[0].startswith("-") or (nom == "env" and "=" in argv[0])
                            or (nom == "timeout" and re.fullmatch(r"[\d.]+[smhd]?", argv[0]))):
                argv = argv[2:] if argv[0] in VALEURS.get(nom, ()) else argv[1:]
        else:
            break
    # `python3 -m module …` : le module est le programme.
    if argv and re.fullmatch(r"python[\d.]*", argv[0].rsplit("/", 1)[-1]) and argv[1:2] == ["-m"] and len(argv) > 2:
        argv = argv[2:]
    return argv


def _affectation(mot: str) -> tuple[str, str | None] | None:
    """La variable qu'un mot `NOM=valeur` affecte, et sa valeur telle
    qu'écrite : `F+=x` ajoute à la valeur de `F` ; un tableau (`T=(…)`,
    `T[0]=x`) a une valeur que le hook ne suit pas."""
    m = AFFECTATION.fullmatch(mot)
    if not m:
        return None
    nom, indice, plus, valeur = m.groups()
    if indice or valeur.startswith("("):
        return nom, None
    return nom, "${" + nom + "}" + valeur if plus else valeur


def _affectations(argv: list[str]) -> list[tuple[str, str | None]]:
    """Les variables qu'une commande simple affecte dans le shell courant :
    `export F=x`, `unset F` (pas `unset -f F`, une fonction), et, d'une
    valeur que le hook ignore, `read F`, `for F in …`, `printf -v F`,
    `mapfile T`, une déclaration de tableau ou de référence (`declare -n`)."""
    nom, args = (argv[0], argv[1:]) if argv else ("", [])
    if nom in DECLARATIONS:
        affectees = [x for a in args if (x := _affectation(a))]
        drapeaux = "".join(a[1:] for a in args if a.startswith("-") and not AFFECTATION.fullmatch(a))
        if set(drapeaux) & set(DRAPEAUX_INCONNUS.get(nom, "")):
            noms = [n for n, _ in affectees] + [a for a in args if re.fullmatch(r"[A-Za-z_]\w*", a)]
            return [(n, None) for n in noms]
        return affectees
    if nom == "unset":
        options, args = options_et_arguments(args)
        if drapeau(options, "f"):
            return []
        return [(m.group(1), None if m.group(2) else "") for a in args
                if (m := re.fullmatch(r"([A-Za-z_]\w*)(\[.*\])?", a, re.S))]
    if nom in ("mapfile", "readarray"):
        return [(a, None) for a in args if re.fullmatch(r"[A-Za-z_]\w*", a)] + [("MAPFILE", None)]
    if nom in ("for", "select") and args and re.fullmatch(r"[A-Za-z_]\w*", args[0]):
        return [(args[0], None)]
    if nom == "printf" and "-v" in args[:-1]:
        return [(args[args.index("-v") + 1], None)]
    if nom == "read":
        res, i = [], 0
        while i < len(args):
            if args[i] in VALEURS_READ:
                if args[i] == "-a" and i + 1 < len(args):
                    res.append((args[i + 1], None))
                i += 2
                continue
            if not args[i].startswith("-"):
                res.append((args[i], None))
            i += 1
        return res or [("REPLY", None)]
    return []


@dataclass
class _Etat:
    """Ce qu'une commande laisse au shell qui la suit : son dossier, tel
    qu'écrit et développé, la pile de `pushd` (chaque entrée sous ces deux
    formes), le dossier écrit d'avant le dernier `cd`, les variables
    affectées, et celles des `comptees` premières déjà développées
    (`connues`), chacune une seule fois : les redévelopper toutes à chaque
    `cd` rendait le découpage cubique (seconde revue de B-0171, constat 4)."""
    dossier: str
    lieu: str
    vues: list[tuple[str, str | None]]
    pile: list[tuple[str, str]] = field(default_factory=list)
    precedent: str = ""
    connues: dict[str, str] = field(default_factory=dict)
    comptees: int = 0

    def copie(self) -> _Etat:
        return _Etat(self.dossier, self.lieu, list(self.vues), list(self.pile), self.precedent, self.connues,
                     self.comptees)

    def variables(self, env: dict) -> dict[str, str]:
        """Les variables affectées, développées dans l'ordre sur `env`. Le
        dictionnaire rendu ne change plus : une commande le garde."""
        if self.comptees < len(self.vues):
            self.connues = _developpees(env, self.vues[self.comptees:], dict(self.connues))
            self.comptees = len(self.vues)
        return self.connues


def analyser(texte: str, dossier: str = "", affectations: list[tuple[str, str | None]] | None = None,
             environnement=None) -> list[Commande]:
    """Les commandes simples d'un texte de shell, dans l'ordre. Chacune porte
    le dossier où elle s'exécute (`cd`, `cd -`, `pushd`, `popd` suivis), tel
    qu'écrit et développé avec `environnement` (dont `PWD`, le dossier de
    départ) et les variables connues au moment de chaque `cd`, et les
    variables affectées avant elle (B-0171)."""
    env = dict(environnement or {})
    depart = env.get("PWD", "")
    lieu = normaliser(posixpath.join(depart, dossier)) if dossier else depart
    return _analyser(texte, _Etat(dossier, lieu, list(affectations or []), [], dossier), env)


def _analyser(texte: str, etat: _Etat, env: dict) -> list[Commande]:
    res: list[Commande] = []
    mots: list[str] = []
    redir: list[str] = []
    jets = _jetons(texte)
    # Ce que retrouve la suite d'un pipeline (chaque élément tourne dans un
    # sous-shell), d'une tâche de fond (toute la liste `a && b &`) et d'un
    # sous-shell `( … )` : l'état d'avant eux.
    debut_liste, debut_tube, en_tube = etat.copie(), etat.copie(), False
    englobants: list[tuple[_Etat, _Etat, _Etat, bool]] = []

    def lieu_de(cible: str) -> str:
        d = developper(cible, _visibles(env, etat.variables(env)))[0]
        if d.startswith(("/", INCONNU)):
            return normaliser(d)
        return normaliser(posixpath.join(etat.lieu, d)) if d else etat.lieu

    def changer(dossier: str, lieu: str):
        etat.vues += [("OLDPWD", etat.lieu), ("PWD", lieu)]
        etat.dossier, etat.lieu = dossier, lieu

    def aller(cible: str, depuis: Commande) -> str:
        return cible if cible.startswith(("/", "~")) else depuis.chemin(cible)

    def sous_shells(internes: list[str]):
        for interne in internes:
            res.extend(_analyser(interne, etat.copie(), env))

    def clore():
        nonlocal mots, redir
        argv = _sans_prefixes(mots)
        if not argv and mots and all(AFFECTATION.fullmatch(m) for m in mots):
            # Une affectation seule vaut pour la suite ; devant une commande,
            # elle ne vaut que pour celle-ci.
            etat.vues.extend(_affectation(m) for m in mots)
        if argv or redir:
            c = Commande(argv, redir, etat.dossier, mots[:len(mots) - len(argv)], list(etat.vues), etat.lieu,
                         etat.variables(env), env)
            nom = c.programme
            if nom == "cd":
                cible = (options_et_arguments(argv[1:])[1] or ["~"])[0]
                if cible == "-":
                    retour = etat.precedent
                    etat.precedent = etat.dossier
                    changer(retour, lieu_de("$OLDPWD"))
                else:
                    etat.precedent = etat.dossier
                    changer(aller(cible, c), lieu_de(cible))
            elif nom in ("pushd", "popd"):
                options, args = options_et_arguments(argv[1:])
                rang = next((x for x in argv[1:] if re.fullmatch(r"[+-]\d+", x)), None)
                if rang:
                    # Une rotation de la pile (`pushd +1`), ou une entrée
                    # retirée par son rang (`popd -1`) : le hook ne la suit pas.
                    etat.pile = []
                    changer(f"$(dirs {rang})", INCONNU)
                elif nom == "pushd" and args and "-n" in options:
                    etat.pile.append((aller(args[0], c), lieu_de(args[0])))
                elif nom == "pushd" and args:
                    etat.pile.append((etat.dossier, etat.lieu))
                    changer(aller(args[0], c), lieu_de(args[0]))
                elif nom == "pushd" and etat.pile:
                    haut, etat.pile[-1] = etat.pile[-1], (etat.dossier, etat.lieu)
                    changer(*haut)
                elif nom == "popd" and etat.pile and "-n" in options:
                    etat.pile.pop()
                elif nom == "popd" and etat.pile:
                    changer(*etat.pile.pop())
            elif nom in ("bash", "sh", "zsh", "dash") and "-c" in argv[1:-1]:
                res.extend(_analyser(argv[argv.index("-c") + 1], etat.copie(), env))
            elif nom == "eval":
                res.extend(_analyser(" ".join(argv[1:]), etat.copie(), env))
            etat.vues.extend(_affectations(argv))
            etat.vues.extend((m.group(1), None) for x in mots + redir for m in DEFAUT_AFFECTE.finditer(x))
            res.append(c)
        mots, redir = [], []

    i = 0
    while i < len(jets):
        j, internes = jets[i]
        if not _operateur(j):
            sous_shells(internes)
            mots.append(j)
            i += 1
            continue
        suivant, internes = jets[i + 1] if i + 1 < len(jets) else ("", [])
        if ">" in j:
            if mots and mots[-1].isdigit():
                mots.pop()  # le descripteur de `2>`
            if _operateur(suivant):
                i += 1
                continue
            sous_shells(internes)
            if not (j.endswith("&") and (suivant.isdigit() or suivant == "-")):
                redir.append(suivant)
            i += 2
            continue
        if "<" in j:
            sous_shells(internes)
            i += 2
            continue
        clore()
        if j == "(":
            englobants.append((etat.copie(), debut_liste, debut_tube, en_tube))
            debut_liste, debut_tube, en_tube = etat.copie(), etat.copie(), False
        elif j == ")":
            if englobants:
                etat, debut_liste, debut_tube, en_tube = englobants.pop()
        elif j in ("|", "|&"):
            etat, en_tube = debut_tube.copie(), True
        elif j == "&":
            etat = debut_liste.copie()
            debut_liste, debut_tube, en_tube = etat.copie(), etat.copie(), False
        else:
            if en_tube:
                etat, en_tube = debut_tube.copie(), False
            debut_tube = etat.copie()
            if j not in ("&&", "||"):
                debut_liste = etat.copie()
        i += 1
    clore()
    return res


class _Trop(Exception):
    """Plus de formes que le plafond."""


def accolades(mot: str, plafond: int = 256) -> list[str]:
    """Les mots qu'une accolade du shell rend : `a{b,c}` donne `ab` et `ac`,
    `x{1..3}` donne `x1`, `x2`, `x3` ; une accolade sans virgule ni suite,
    ou celle de `${…}`, reste telle quelle. Au-delà du plafond, le mot rend
    une forme seule : sa part d'avant la première accolade, puis une part
    inconnue (`INCONNU`) suivie d'autant de `..` que les points du reste en
    pourraient former, que le hook juge comme toute part inconnue."""
    try:
        return _accolades(mot, plafond)
    except _Trop:
        i = next((k for k, ch in enumerate(mot) if ch == "{" and mot[k - 1:k] != "$"), 0)
        reste = re.sub(r"\{(?:-?\d+\.\.-?\d+(?:\.\.-?\d+)?|[A-Za-z]\.\.[A-Za-z])\}", "", mot[i:])
        return [mot[:i] + INCONNU + "/.." * (reste.count(".") // 2)]


def _accolades(mot: str, plafond: int) -> list[str]:
    i = 0
    while i < len(mot):
        if mot[i] != "{":
            i += 1
            continue
        profondeur, j, virgules = 0, i, []
        while j < len(mot):
            if mot[j] == "{":
                profondeur += 1
            elif mot[j] == "}":
                profondeur -= 1
                if profondeur == 0:
                    break
            elif mot[j] == "," and profondeur == 1:
                virgules.append(j)
            j += 1
        if j >= len(mot):
            return [mot]
        if i > 0 and mot[i - 1] == "$":
            i = j + 1  # `${…}` : une variable, pas une accolade
            continue
        dedans = mot[i + 1:j]
        suite = re.fullmatch(r"(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?|([A-Za-z])\.\.([A-Za-z])", dedans)
        if virgules:
            bornes = [i] + virgules + [j]
            parts = [mot[a + 1:b] for a, b in zip(bornes, bornes[1:])]
        elif suite:
            a, b = (int(suite.group(1)), int(suite.group(2))) if suite.group(1) else (
                ord(suite.group(4)), ord(suite.group(5)))
            pas = abs(int(suite.group(3) or 1)) or 1
            if abs(b - a) // pas >= plafond:
                raise _Trop
            parts = [str(x) if suite.group(1) else chr(x) for x in range(a, b + (1 if b >= a else -1),
                                                                          pas if b >= a else -pas)]
        else:
            i += 1
            continue
        res: list[str] = []
        for p in parts:
            res += _accolades(mot[:i] + p + mot[j + 1:], plafond)
            if len(res) > plafond:
                raise _Trop
        return res
    return [mot]


def _accolade_fermante(mot: str, i: int) -> int:
    """L'index après l'accolade qui ferme celle de `i` ; la fin du mot si
    rien ne la ferme."""
    profondeur = 0
    for j in range(i, len(mot)):
        profondeur += {"{": 1, "}": -1}.get(mot[j], 0)
        if profondeur == 0:
            return j + 1
    return len(mot)


def _valeur(expression: str, variables) -> str | None:
    """La valeur de `$NOM`, `${NOM}`, ou `${NOM:-mot}` et ses voisins (`-`,
    `+`, `=`, `?`, avec ou sans `:`) ; `None` si le hook ne la connaît pas."""
    corps = expression[2:-1] if expression.startswith("${") else expression[1:]
    if re.fullmatch(r"[A-Za-z_]\w*", corps):
        return variables.get(corps)
    m = re.fullmatch(r"([A-Za-z_]\w*)(:?)([-+=?])(.*)", corps, re.S) if expression.startswith("${") else None
    if not m:
        return None
    nom, deux_points, operateur, mot = m.groups()
    actuelle = variables.get(nom)
    # Une variable vide, sans `:`, peut aussi bien n'être pas posée : le
    # hook ne les distingue pas (`unset F` la vide).
    if actuelle is None or INCONNU in actuelle or (not actuelle and not deux_points):
        return None
    if actuelle and operateur in "-=?":
        return actuelle
    if not actuelle and operateur in "+?":
        return None if operateur == "?" else ""
    return developper(mot, variables)[0]


def developper(mot: str, variables) -> tuple[str, list[str]]:
    """Le mot comme le shell le développerait de son `~` et de ses variables
    (`variables` : nom → valeur, la valeur pouvant porter `INCONNU`), et les
    parts qu'il ne sait pas développer, chacune remplacée par `INCONNU` :
    une variable que `variables` ne connaît pas, `${…}` avec un opérateur
    autre que `-`, `+`, `=` et `?`, une substitution `$(…)` ou entre accents
    graves, une expression arithmétique, un paramètre spécial (`$1`, `$$`),
    une chaîne `$'…'` que le découpage n'a pas su lire, un motif étendu
    (`@(…)`). Un `$` en fin de mot est celui d'une substitution coupée. Un
    `INCONNU` déjà dans le mot (`accolades`) y reste."""
    if not mot.startswith("~") and not A_DEVELOPPER.search(mot):
        return mot, []  # sans rien à développer : sans le parcourir, qu'un long chemin rendrait lent
    res: list[str] = []
    inconnus: list[str] = []
    taille = 0
    if mot.startswith("~"):
        tete, barre, reste = mot.partition("/")
        if tete in ("~", "~+", "~-"):
            valeur = variables.get({"~": "HOME", "~+": "PWD", "~-": "OLDPWD"}[tete])
        else:
            # `~nom` : le dossier de cet utilisateur, ou le mot tel quel.
            valeur = posixpath.expanduser(tete)
        if valeur is None or INCONNU in valeur:
            inconnus.append(tete)
        res.append(INCONNU if valeur is None else valeur)
        mot = barre + reste
    i = 0
    while i < len(mot):
        ch = mot[i]
        if ch in "?*+@!" and mot[i + 1:i + 2] == "(":
            j = _fermante(mot, i + 1)
            inconnus.append(mot[i:j])
            res.append(INCONNU)
            i = j
            continue
        if ch == "`":
            j = mot.find("`", i + 1)
            j = len(mot) if j < 0 else j + 1
        elif ch != "$":
            res.append(ch)
            i += 1
            continue
        elif mot[i + 1:i + 2] in ("", "("):
            j = _fermante(mot, i + 1) if mot[i + 1:i + 2] else i + 1
        elif mot[i + 1] == "'":
            j = _ansi_c(mot, i + 2)[0]
        elif mot[i + 1] == "{":
            j = _accolade_fermante(mot, i + 1)
        elif m := NOM_APRES_DOLLAR.match(mot, i + 1):
            j = m.end()
        else:
            res.append(ch)  # un `$` que rien de développable ne suit
            i += 1
            continue
        valeur = _valeur(mot[i:j], variables) if ch == "$" else None
        if valeur is None or INCONNU in valeur:
            inconnus.append(mot[i:j])
        res.append(INCONNU if valeur is None else valeur)
        taille += len(valeur or "")
        if taille > LONGUEUR_MAX:
            return INCONNU, [mot]  # une valeur dupliquée, qui ne fait pas un chemin
        i = j
    return "".join(res), inconnus


def demesure(texte: str) -> tuple[str, int] | None:
    """Ce qui rend une commande trop longue ou trop imbriquée pour que le
    hook la découpe sans risque (`LONGUEUR_MAX`, `PROFONDEUR_MAX`) :
    `("longueur", n)`, ses caractères hors du corps de ses heredocs, ou
    `("profondeur", n)`, le plus de parenthèses et d'accolades ouvertes à la
    fois, guillemets compris ; `None` si elle se découpe."""
    corps = sans_heredocs(texte)
    if len(corps) > LONGUEUR_MAX:
        return "longueur", len(corps)
    profondeur = pire = 0
    for ch in corps:
        if ch in "({":
            profondeur += 1
            pire = max(pire, profondeur)
        elif ch in ")}":
            profondeur = max(0, profondeur - 1)
    return ("profondeur", pire) if pire > PROFONDEUR_MAX else None


def _developpees(environnement, affectations: list[tuple[str, str | None]],
                 connues: dict[str, str]) -> dict[str, str]:
    """`connues`, complété des variables affectées, chaque valeur développée
    à son tour sur celles d'avant et sur l'environnement. Une valeur trop
    imbriquée pour se développer (`RecursionError`) est inconnue : un chemin
    qui la cite se juge comme toute part inconnue (seconde revue de B-0171,
    constat 4)."""
    vues = ChainMap(connues, environnement)
    for nom, brute in affectations:
        try:
            connues[nom] = INCONNU if brute is None else developper(brute, vues)[0]
        except RecursionError:
            connues[nom] = INCONNU
    return connues


def _visibles(environnement, connues: dict[str, str]):
    """Les variables de l'environnement et celles affectées, sans `$_` : le
    dernier argument de la commande d'avant, que le hook ne suit pas."""
    vues = ChainMap(connues, environnement)
    return {k: v for k, v in vues.items() if k != "_"} if "_" in vues else vues


def _variables(environnement, affectations: list[tuple[str, str | None]]) -> dict[str, str]:
    return dict(_visibles(environnement, _developpees(environnement, affectations, {})))


def variables_de(c: Commande, environnement) -> dict[str, str]:
    """Les variables que le shell connaît quand la commande s'exécute :
    l'environnement, puis ce que le même texte affecte avant elle, chaque
    valeur développée à son tour ; `INCONNU`, une valeur que le hook ignore.
    Sur l'environnement d'`analyser`, celles que le découpage a déjà
    développées."""
    if c.connues is not None and c.environnement == dict(environnement):
        return dict(_visibles(environnement, c.connues))
    return _variables(environnement, c.affectations)


def environnement_du_shell(environ, pwd: str) -> dict[str, str]:
    """Les variables d'un shell neuf lancé dans `pwd` avec l'environnement
    `environ` : ni ses variables spéciales (`SPECIALES`), sauf `PWD`, ni ce
    que le hook ne saurait lire."""
    env = {k: v for k, v in environ.items() if k not in SPECIALES and INCONNU not in v}
    env["PWD"] = pwd
    return env


def normaliser(chemin: str) -> str:
    """Le chemin sans `.` ni `..` superflus, comme `posixpath.normpath`, sauf
    qu'un `..` ne remonte pas une part que le hook ne sait pas développer :
    `/tmp/$X/..` n'est pas `/tmp`, `$X` pouvant valoir plusieurs dossiers.
    Un chemin relatif vide reste vide (le dossier de départ)."""
    if INCONNU not in chemin:
        # Le même, sans le parcourir en python : `normpath` garde `//` en tête.
        n = posixpath.normpath(chemin)
        return "" if n == "." else n[1:] if n.startswith("//") else n
    absolu = chemin.startswith("/")
    parts: list[str] = []
    for p in chemin.split("/"):
        if p in ("", "."):
            continue
        if p == ".." and parts and parts[-1] != ".." and INCONNU not in parts[-1]:
            parts.pop()
        elif not (p == ".." and absolu and not parts):
            parts.append(p)
    return ("/" if absolu else "") + "/".join(parts)


def lieu_sur(chemin: str) -> str | None:
    """Le dossier sous lequel tombe à coup sûr un chemin normalisé qui porte
    une part que le hook ne sait pas développer : celui que la part écrite
    en toutes lettres avant elle nomme, remonté d'autant de `..` qui la
    suivent (un `..` écrit, ou un nom de points que l'inconnu compléterait,
    `..$X`) ; `None` quand rien de connu ne la précède. L'inconnu lui-même
    peut valoir `..` (`$X`, qui vaudrait `../..`) : risque accepté
    (ADR-0072)."""
    if not chemin.startswith("/"):
        return None
    parts = chemin.split("/")[1:]
    k = next((i for i, p in enumerate(parts) if INCONNU in p), len(parts))

    def remonte(p: str) -> bool:
        points = p.replace(INCONNU, "")
        return p == ".." or (INCONNU in p and 0 < len(points) <= 2 and not points.strip("."))

    montees = sum(1 for p in parts[k:] if remonte(p))
    return "/" + "/".join(parts[:max(0, k - montees)])


# Les éléments d'un motif : l'ensemble des caractères qu'il rend
# (`(nié, caractères)`), s'il est étoilé (zéro fois ou plus) et s'il est un
# joker (`*`, `?`, `[…]`), qui ne rend pas le `.` qui ouvre un nom.
_SAUF_BARRE = (True, frozenset("/"))
_TOUT = (True, frozenset())
# Les classes POSIX d'un `[…]` (`[[:alpha:]]`), sur les caractères ASCII.
_ASCII = [chr(x) for x in range(128)]
CLASSES = {
    "alpha": str.isalpha, "digit": str.isdigit, "alnum": str.isalnum, "upper": str.isupper, "lower": str.islower,
    "space": str.isspace, "blank": lambda c: c in " \t", "print": str.isprintable,
    "graph": lambda c: c.isprintable() and c != " ", "cntrl": lambda c: not c.isprintable(),
    "punct": lambda c: c.isprintable() and not c.isalnum() and c != " ", "xdigit": lambda c: c in "0123456789abcdefABCDEF",
    "word": lambda c: c.isalnum() or c == "_"}


def _crochet(motif: str, i: int) -> tuple[tuple[bool, frozenset], int] | None:
    """L'ensemble que rend le `[…]` ouvert en `i`, et l'index après lui ;
    `None` s'il n'est pas fermé (le `[` est alors un caractère). Une classe
    POSIX inconnue, un `[=…=]` ou un `[.….]` le rendent à tout caractère."""
    k = i + 1
    nie = motif[k:k + 1] in ("!", "^")
    k += nie
    chars: set[str] = set()
    tout, premier = False, True
    while k < len(motif):
        ch = motif[k]
        if ch == "]" and not premier:
            if tout:
                return _SAUF_BARRE, k + 1
            return ((True, frozenset(chars | {"/"})) if nie else (False, frozenset(chars - {"/"}))), k + 1
        premier = False
        if motif.startswith(("[:", "[=", "[."), k):
            fin = motif.find(motif[k + 1] + "]", k + 2)
            if fin < 0:
                return None
            classe = CLASSES.get(motif[k + 2:fin]) if motif[k + 1] == ":" else None
            if classe is None:
                tout = True
            else:
                chars.update(c for c in _ASCII if classe(c))
            k = fin + 2
        elif k + 2 < len(motif) and motif[k + 1] == "-" and motif[k + 2] != "]":
            chars.update(chr(x) for x in range(ord(ch), ord(motif[k + 2]) + 1))
            k += 3
        else:
            chars.add(ch)
            k += 1
    return None


def _elements_shell(motif: str, permissif: bool = False) -> list[tuple[tuple[bool, frozenset], bool, bool]]:
    """Les éléments d'un motif du shell. Avec `permissif` (`dotglob`,
    `globstar` et `nocaseglob` peut-être actifs), un joker rend aussi le `.`
    qui ouvre un nom, `**` traverse les dossiers, et la casse ne compte pas
    (les caractères sont rendus en minuscules)."""
    res, i = [], 0
    while i < len(motif):
        ch = motif[i]
        crochet = _crochet(motif, i) if ch == "[" else None
        if permissif and motif.startswith("**", i):
            el, i = (_TOUT, True, False), i + 2
        elif ch in "*?":
            el, i = (_SAUF_BARRE, ch == "*", not permissif), i + 1
        elif crochet:
            ensemble, i = crochet
            el = (ensemble, False, not permissif)
        else:
            el, i = ((False, frozenset(ch)), False, False), i + 1
        if permissif:
            (nie, chars), etoile, joker = el
            el = ((nie, frozenset(c.lower() for c in chars)), etoile, joker)
        res.append(el)
    return res


def _elements_chemin(motif: str) -> list[list[tuple[tuple[bool, frozenset], bool, bool]]]:
    """Les variantes d'un motif de chemin à la gitignore (`utils.correspond`),
    `**/` (zéro dossier ou plus) déplié en ses deux formes."""
    variantes: list[list] = [[]]
    i = 0
    while i < len(motif):
        if motif.startswith("**/", i):
            dossiers = [(_TOUT, True, True), ((False, frozenset("/")), False, False)]
            variantes = [v + x for v in variantes for x in ([], dossiers)]
            i += 3
            continue
        if motif.startswith("**", i):
            el, i = (_TOUT, True, True), i + 2
        elif motif[i] in "*?":
            el, i = (_SAUF_BARRE, motif[i] == "*", True), i + 1
        else:
            el, i = ((False, frozenset(motif[i])), False, False), i + 1
        variantes = [v + [el] for v in variantes]
    return variantes


def _commun(a: tuple[bool, frozenset], b: tuple[bool, frozenset]) -> tuple[bool, frozenset]:
    (na, ca), (nb, cb) = a, b
    if na and nb:
        return True, ca | cb
    if not na and not nb:
        return False, ca & cb
    return (False, cb - ca) if na else (False, ca - cb)


def _rend(ensemble: tuple[bool, frozenset], ch: str) -> bool:
    return (ch not in ensemble[1]) if ensemble[0] else (ch in ensemble[1])


def se_croisent(motif_shell: str, motif_chemin: str, dessous: bool = False, permissif: bool = False) -> bool:
    """Un même chemin peut-il répondre au motif du shell (`*`, `?`, `[…]`,
    qui ne traversent pas `/` ni ne rendent le `.` qui ouvre un nom) et au
    motif de chemin (`utils.correspond`) ? Avec `dessous`, un chemin sous ce
    que nomme le motif du shell compte aussi : `rm -rf .so*` vise
    `.socle/policy.toml`. Avec `permissif`, le motif du shell se lit comme
    si `dotglob`, `globstar` et `nocaseglob` étaient actifs."""
    shell = _elements_shell(motif_shell, permissif)
    formes = [shell] + ([shell + [((False, frozenset("/")), False, False), (_TOUT, True, False)]] if dessous else [])
    chemins = _elements_chemin(motif_chemin.lower() if permissif else motif_chemin)
    return any(_se_croisent(a, b) for a in formes for b in chemins)


def _se_croisent(a: list, b: list) -> bool:
    """Un même chemin peut-il répondre aux deux suites d'éléments ? Un
    parcours du produit des deux : (position dans `a`, dans `b`, au début
    d'un nom), chaque pas rendant un caractère que les deux admettent ; sans
    récursion, qu'un long chemin épuiserait."""
    vus: set = set()
    pile = [(0, 0, True)]
    while pile:
        etat = pile.pop()
        if etat in vus:
            continue
        vus.add(etat)
        i, j, debut = etat
        if i == len(a) and j == len(b):
            return True
        if i < len(a) and a[i][1]:
            pile.append((i + 1, j, debut))
        if j < len(b) and b[j][1]:
            pile.append((i, j + 1, debut))
        if i == len(a) or j == len(b):
            continue
        ensemble = _commun(a[i][0], b[j][0])
        i2, j2 = (i if a[i][1] else i + 1), (j if b[j][1] else j + 1)
        # Le `.` qui ouvre un nom ne répond qu'à un `.` écrit.
        interdits = {"/", "."} if debut and a[i][2] else {"/"}
        if _rend(ensemble, "/"):
            pile.append((i2, j2, True))
        if ensemble[0] or ensemble[1] - interdits:
            pile.append((i2, j2, False))
    return False


def options_et_arguments(argv: list[str]) -> tuple[list[str], list[str]]:
    """Les options (`-x`, `--y`) et les arguments d'une commande ; après
    `--`, tout est argument."""
    options, args = [], []
    fin = False
    for a in argv:
        if not fin and a == "--":
            fin = True
        elif not fin and a.startswith("-") and a != "-":
            options.append(a)
        else:
            args.append(a)
    return options, args


def drapeau(options: list[str], court: str = "", long: tuple[str, ...] = ()) -> bool:
    """Une option présente, seule (`-f`), groupée (`-fu`) ou longue (`--force`)."""
    for o in options:
        if o.startswith("--"):
            if any(o == l or o.startswith(l + "=") for l in long):
                return True
        elif court and court in o[1:]:
            return True
    return False


def git_sous_commande(argv: list[str]) -> tuple[str, list[str]]:
    """La sous-commande de `git` et ses arguments, derrière ses options
    globales (`-C <dossier>`, `-c <clé=valeur>`, `--git-dir=…`)."""
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path") else 1
    return (argv[i], argv[i + 1:]) if i < len(argv) else ("", [])

