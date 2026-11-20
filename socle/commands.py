"""Une commande shell, découpée en commandes simples, pour que les hooks
jugent ce qu'elle fait et non le texte qu'elle cite.

Un heredoc, une chaîne entre guillemets ou un message de commit qui
nomment une commande dangereuse ne la lancent pas ; un lanceur entre
guillemets, un `git -C .`, des drapeaux groupés (`-fu`) ou un `cd` la
lancent bien. Le découpage suit les guillemets, les séparateurs (`;`, `&&`,
`||`, `|`, fin de ligne), les redirections, les `cd`, les préfixes (`env`,
`sudo`, `nohup`…, `uv run` et `poetry run` avec leurs options) et les
`bash -c`.

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

Les mots réservés qui précèdent une commande (`if`, `then`, `do`, `!`,
`{`…) se retirent comme un préfixe ; ce qu'une condition ou une boucle
change, son dossier et ses variables, devient inconnu après elle, et le
corps d'un `for` se lit une fois par mot de sa liste, sa variable liée à ce
mot (B-0204).

Heuristique, comme tout ce qui lit du shell sans l'exécuter : les motifs
d'un `case`, les alias, les fonctions, `source` et l'état qu'un `eval`
laisse ne sont pas suivis ; ce que lance une substitution se juge, entre
guillemets (`"$(…)"`) comme nue (B-0260). Le hook n'est qu'un étage ; la
CI juge ce qui est commité.
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
# Les lanceurs d'un projet Python, `uv run` et `poetry run`, qui lancent la
# commande qui suit leurs options, comme `python -m` son module (B-0248) ;
# les options de chacun qui prennent une valeur, avant `run` comme après.
LANCEURS = {
    "uv": ("--extra", "--no-extra", "--group", "--no-group", "--only-group", "--no-editable-package",
           "--env-file", "-w", "--with", "--with-editable", "--with-requirements", "--package",
           "--python-platform", "--index", "--default-index", "-i", "--index-url", "--extra-index-url", "-f",
           "--find-links", "--index-strategy", "--keyring-provider", "-P", "--upgrade-package",
           "--upgrade-group", "--resolution", "--prerelease", "--fork-strategy", "--exclude-newer",
           "--exclude-newer-package", "--no-sources-package", "--reinstall-package", "--link-mode", "-C",
           "--config-setting", "--config-settings-package", "--no-build-isolation-package",
           "--no-build-package", "--no-binary-package", "--cache-dir", "--refresh-package", "-p", "--python",
           "--color", "--allow-insecure-host", "--directory", "--project", "--config-file"),
    "poetry": ("-C", "--directory", "-P", "--project"),
}
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
# Les mots réservés du shell qui précèdent une commande simple : le
# découpage les retire, comme un préfixe (B-0204).
RESERVES = ("if", "then", "else", "elif", "while", "until", "do", "!", "{")
# Ce qui ouvre une commande composée, et ce qui la ferme. Ce qu'une
# condition ou une boucle change devient inconnu après elle, et dans la
# branche `else` ou `elif` qui suit ; un groupe `{ …; }` s'exécute une fois,
# et le corps d'une fonction (`nom() { …; }`) pas là où il s'écrit.
OUVRANTS = ("if", "while", "until", "for", "select", "{")
FERMANTS = ("fi", "done", "}")
# Les mots que le découpage lit comme une structure (`function`, `{`, `}`,
# `if`, `then`, `do`, `done`, `!`…), et non comme le nom d'une commande. Un
# mot cité ou échappé dont le texte nu est l'un d'eux n'est pas réservé pour
# bash (`"function" f`, `\function`, `f() { "}"; … }`) : il se lance comme
# une commande, et le hook le lit comme un mot, jamais comme une structure
# (B-0232, la seconde revue du lot B-0234).
MOTS_STRUCTURE = frozenset(RESERVES + FERMANTS + OUVRANTS + ("function",))
# Ce que le dépliage des `for` d'une commande peut ajouter à ce que le
# découpage lit, en caractères, le texte des substitutions et des `bash -c`
# que chaque tour relit compris, pour toute la commande, ses sous-shells
# comme son texte : au-delà, la variable d'un `for` de plusieurs mots est
# inconnue dans son corps (la seconde revue du lot 3, J-2026-11-14-AL).
DEPLIAGE_MAX = 100_000
# Ce qui saute à la suite d'une boucle, ou à son tour d'après.
SAUTS = ("break", "continue")
# Le nom d'une fonction que définit `nom ( )`.
NOM_DE_FONCTION = re.compile(r"[\w.:+@-]+")
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
# Ce qui marque un mot dont une part est citée ou échappée : le découpage
# ne le lit ni comme un opérateur (`\(`, `';'` ; `find … \( … \) -exec … \;`,
# la revue du lot 3, J-2026-11-14-AH), ni comme un mot réservé (`"function"`,
# `\function`, `"}"` ; la seconde revue du lot B-0234, B-0232). `_preparer`
# le pose à chaque guillemet et chaque échappement ; `_jetons` ne le garde
# que devant un mot dont le texte nu est un opérateur ou un mot réservé.
CITE = "\x02"
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
    # Le corps du heredoc que reçoit son entrée (`<<`, `<<-` sans ses
    # tabulations de tête), tel qu'écrit, sans rien développer ; `None` sans
    # heredoc, ou quand une redirection qui le suit lui donne une autre
    # entrée (B-0229).
    entree: str | None = None
    # La commande qui la précède dans son pipeline (`a | b` : `a` pour `b`),
    # celle qui écrit ce que lit son entrée ; `None` en tête d'un pipeline
    # (B-0246).
    amont: Commande | None = field(default=None, repr=False, compare=False)

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
    return _heredocs(texte)[0]


def _heredocs(texte: str) -> tuple[str, list[tuple[str, str]]]:
    """Le texte sans le corps de ses heredocs, et ces corps dans l'ordre :
    (le mot qui le ferme, le corps), les tabulations de tête de ses lignes
    retirées pour `<<-`, comme le shell (B-0229)."""
    res, attendus, corps = [], [], []
    for ligne in texte.split("\n"):
        if attendus:
            fin, tabs, lignes = attendus[0]
            if (ligne.lstrip("\t") if tabs else ligne) == fin:
                corps.append((fin, "\n".join(lignes)))
                attendus.pop(0)
            else:
                lignes.append(ligne.lstrip("\t") if tabs else ligne)
            continue
        res.append(ligne)
        attendus += [(m.group(3), m.group(1) == "-", []) for m in HEREDOC.finditer(ligne)]
    # Un heredoc sans sa ligne de fin court jusqu'au bout du texte.
    corps += [(fin, "\n".join(lignes)) for fin, _, lignes in attendus]
    return "\n".join(res), corps


def _fin_guillemets(texte: str, i: int) -> int:
    """L'index après la chaîne `"…"` ouverte en `i`, comme le shell la lit :
    une substitution qu'elle contient (`$(…)`, accents graves) a ses propres
    guillemets (`"$(cmd "arg")"`, B-0207)."""
    j, n = i + 1, len(texte)
    while j < n and texte[j] != '"':
        if texte[j] == "\\":
            j += 2
        elif texte.startswith("$(", j):
            j = _fermante(texte, j + 1)
        elif texte[j] == "`":
            j = _fin_accents(texte, j)
        else:
            j += 1
    return min(j + 1, n)


def _fin_accents(texte: str, i: int) -> int:
    """L'index après la substitution entre accents graves ouverte en `i`."""
    j, n = i + 1, len(texte)
    while j < n and texte[j] != "`":
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
    guillemets seulement, sauf une substitution entre guillemets, mise de
    côté pour que `shlex` n'y lise pas d'autres guillemets, et dont la
    commande se rend comme celle d'une substitution nue (B-0260). Un `#` en tête
    d'un mot ouvre un commentaire, retiré jusqu'à la fin de la ligne, qui
    reste ; ailleurs (`x#`, `$#`), il fait partie du mot (B-0207). Des
    opérateurs échappés ou entre guillemets (`\\(`, `';'`, `"&"`, `$'('`)
    sont un mot, marqué de `CITE` : `shlex`, qui retire les guillemets, les
    rendrait comme des opérateurs (la revue du lot 3, J-2026-11-14-AH)."""
    texte = texte.replace("\x01", "").replace(CITE, "")
    res: list[str] = []
    parts: list[tuple[str, str | None]] = []
    i, n = 0, len(texte)

    def mettre(fin: int, interne: str | None = None):
        nonlocal i
        parts.append((texte[i:fin], interne))
        res.append(f"\x01{len(parts) - 1}\x01")
        i = fin

    def cite(fin: int, contenu: str):
        """Des opérateurs échappés ou entre guillemets : un mot."""
        nonlocal i
        parts.append((CITE + contenu, None))
        res.append(f"\x01{len(parts) - 1}\x01")
        i = fin

    while i < n:
        ch = texte[i]
        if ch == "\\" and texte[i + 1:i + 2] and texte[i + 1] in ";&|()<>":
            cite(i + 2, texte[i + 1])
        elif ch == "\\":
            # Un échappement : le mot porte `CITE`, pour que `_jetons` ne le
            # lise pas comme un mot réservé (`\function`, B-0232).
            res.append(CITE)
            res.append(texte[i:i + 2])
            i += 2
        elif ch == "'":
            fin = texte.find("'", i + 1)
            fin = n if fin < 0 else fin + 1
            if fin - i > 2 and texte[fin - 1] == "'" and _operateur(texte[i + 1:fin - 1]):
                cite(fin, texte[i + 1:fin - 1])
                continue
            res.append(CITE)
            res.append(texte[i:fin])
            i = fin
        elif ch == '"' and (fin := _fin_guillemets(texte, i)) - i > 2 and texte[fin - 1] == '"' \
                and _operateur(texte[i + 1:fin - 1]):
            cite(fin, texte[i + 1:fin - 1])
        elif ch == '"':
            fin = _fin_guillemets(texte, i)
            res.append('"')
            res.append(CITE)
            k = i + 1
            while k < fin:
                if texte[k] == "\\":
                    res.append(texte[k:k + 2])
                    k += 2
                elif texte.startswith("$(", k) or texte[k] == "`":
                    # Ce qu'elle lance se juge comme ce que lance une
                    # substitution nue, avec les fonctions connues (B-0260) ;
                    # ses guillemets ne se lisent plus comme ceux de la
                    # chaîne. Un calcul `$((…))` ne lance rien.
                    if texte[k] == "`":
                        bout = _fin_accents(texte, k)
                        fin_interne = bout - 1 if texte[bout - 1:bout] == "`" and bout - 1 > k else bout
                        interne = re.sub(r"\\([$`\\\"])", r"\1", texte[k + 1:fin_interne])
                    else:
                        bout = _fermante(texte, k + 1)
                        fin_interne = bout - 1 if texte[bout - 1:bout] == ")" else bout
                        interne = None if texte.startswith("$((", k) else texte[k + 2:fin_interne]
                    parts.append((texte[k:bout], interne))
                    res.append(f"\x01{len(parts) - 1}\x01")
                    k = bout
                else:
                    res.append(texte[k])
                    k += 1
            i = fin
        elif ch == "#" and (not res or res[-1][-1:] in (" ", "\t", "\n", ";", "&", "|", "(", ")", "<", ">")):
            fin = texte.find("\n", i)
            i = n if fin < 0 else fin
        elif texte.startswith("$'", i):
            fin, valeur = _ansi_c(texte, i + 2)
            if valeur is None:
                mettre(fin)
            elif _operateur(valeur):
                cite(fin, valeur)
            else:
                res.append(CITE)
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
    sans_corps, corps = _heredocs(texte.replace("\\\n", " "))
    prepare, parts = _preparer(sans_corps)

    def prendre(fin: str) -> str | None:
        """Le premier corps qui reste du heredoc que ferme `fin`, retiré."""
        k = next((k for k, (nom, _) in enumerate(corps) if nom == fin), None)
        return None if k is None else corps.pop(k)[1]

    lex = shlex.shlex(prepare, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    # `_preparer` a retiré les commentaires : un `#` qui reste est dans un
    # mot, et `shlex` en avalerait la fin de la ligne (B-0207).
    lex.commenters = ""
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
        mot = REPERE.sub(lambda m: parts[int(m.group(1))][0], j)
        if CITE in mot:
            # Un mot cité dont le texte nu est un opérateur ou un mot réservé
            # garde sa marque, que le découpage retire en le lisant comme un
            # mot (`"function"`, `"}"`, B-0232) ; un autre mot la perd.
            nu = mot.replace(CITE, "")
            mot = CITE + nu if _operateur(nu) or nu in MOTS_STRUCTURE else nu
        if res and res[-1][0] == "<<":
            # Le mot qui ferme un heredoc (`-EOF` pour `<<-EOF`) : il prend le
            # premier corps de ce nom qui reste, dans l'ordre du texte.
            mot, nom = _Heredoc(mot), mot.lstrip(CITE)
            mot.corps = prendre(nom) if any(fin == nom for fin, _ in corps) or nom[:1] != "-" else prendre(nom[1:])
        else:
            # Les heredocs d'une substitution ou d'une chaîne, que le découpage
            # a vus aussi : leurs corps ne sont pas ceux des suivants.
            for m in HEREDOC.finditer(mot.replace(CITE, "")):
                prendre(m.group(3))
        res.append((mot, internes))
    return res


def jetons(texte: str) -> list[str]:
    """Les mots et les opérateurs de la commande, guillemets retirés."""
    return [j.lstrip(CITE) for j, _ in _jetons(texte)]


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


def _script_du_shell(argv: list[str]) -> str | None:
    """La commande que lance un `bash -c`, quel que soit le groupe d'options
    qui porte le `c` (`-ec`, `-lc`, `-o pipefail -c`), `--` sauté : le
    premier argument après les options ; `None` sans `-c` (B-0206)."""
    vu, i = False, 1
    while i < len(argv):
        a = argv[i]
        if a in ("--", "-"):
            i += 1
            break
        if a in ("--rcfile", "--init-file"):
            i += 2
        elif a.startswith("--"):
            i += 1
        elif a[:1] in ("-", "+") and len(a) > 1:
            vu = vu or (a[0] == "-" and "c" in a[1:])
            # `-o pipefail`, `+O extglob` : la valeur suit.
            i += 2 if a[-1] in "oO" else 1
        else:
            break
    return argv[i] if vu and i < len(argv) else None


def _definition(mots: list[str]) -> int | None:
    """Les mots lus devant un `( )` définissent-ils une fonction : un nom,
    précédé ou non de `function` et de mots réservés (`then f() {`) ; le
    nombre de ces mots réservés, ou `None`."""
    if not mots or not NOM_DE_FONCTION.fullmatch(mots[-1]) or mots[-1] in RESERVES + FERMANTS + ("function",):
        return None
    k = len(mots) - 1 - (mots[-2:-1] == ["function"])
    return k if all(m in RESERVES for m in mots[:k]) else None


def _fonction_sans_parentheses(mots: list[str]) -> int | None:
    """Les mots lus devant le premier mot d'un corps, ou devant un saut de
    ligne, définissent-ils une fonction sans parenthèses, `function nom` :
    le mot réservé en tête de la commande, précédé ou non de mots réservés
    (`then function f {`), puis un nom, quel qu'il soit (bash admet
    `function f/x` et `function if`, et les appelle) ; le nombre de ces mots
    réservés, ou `None` (B-0232)."""
    if len(mots) < 2 or mots[-2] != "function":
        return None
    k = len(mots) - 2
    return k if all(m in RESERVES for m in mots[:k]) else None


def _cible_suivie(d: str) -> str:
    """La cible développée `d` d'un `cd`, ce que le hook ne sait pas suivre
    remplacé par `INCONNU` : un `**`, qui traverse peut-être plusieurs
    dossiers (`globstar`). Une variable faite de plusieurs mots se lit comme
    un seul nom, celui d'un dossier dont le chemin porte une espace : le
    découpage ne voit plus les guillemets qui la gardent entière, et la
    liste d'un `for` se lit mot par mot (la seconde revue du lot 3,
    J-2026-11-14-AL)."""
    return re.sub(r"[^/]*\*\*[^/]*", INCONNU, d)


def _mots_de_la_liste(liste: list[str], variables) -> list[str] | None:
    """Les mots que prend, un par tour, la variable d'un `for` dont la liste
    s'écrit `liste` : chaque accolade développée, et un mot qui porte une
    variable coupé comme le shell le couperait ; un motif reste un motif,
    que le jugement lit contre les fichiers. `None` si l'un ne se développe
    pas."""
    res: list[str] = []
    for mot in liste:
        for forme in accolades(mot):
            if not re.search(r"[$`]", forme):
                res.append(forme)
                continue
            d = developper(forme, variables)[0]
            if INCONNU in d:
                return None
            separateurs = variables.get("IFS")
            separateurs = " \t\n" if separateurs is None or INCONNU in separateurs else separateurs
            res += [x for x in re.split("[" + re.escape(separateurs) + "]+", d) if x] if separateurs else [d] * bool(d)
    return res


class _Heredoc(str):
    """Le mot qui suit un `<<` : il porte le corps du heredoc qu'il ferme
    (`corps`, `None` si le découpage ne l'a pas trouvé, B-0229)."""
    corps: str | None


class _Tour(str):
    """Le jeton que le dépliage d'un `for` pose devant chaque tour de son
    corps : sa variable y prend le mot de son rang. Aucun mot du texte n'en
    est un."""
    rang: int


def _tour(rang: int) -> _Tour:
    jeton = _Tour("")
    jeton.rang = rang
    return jeton


def _boucle() -> dict:
    """Ce que le découpage suit d'une boucle ouverte : sa variable (`nom`),
    ce qu'elle vaut dans un corps qui ne se déplie pas (`lien`), les mots de
    sa liste (`valeurs`), si son corps s'est déplié (`deplie`), et le
    dossier de chaque saut lu dans son corps (`sauts`)."""
    return {"nom": None, "lien": None, "valeurs": None, "deplie": False, "sauts": []}


def _fin_du_corps(jets: list[tuple[str, list[str]]], i: int) -> int | None:
    """L'indice du `done` qui ferme le corps de boucle que le `do` de
    `jets[i]` ouvre, les boucles qu'il contient sautées ; `None` s'il ne se
    ferme pas dans le texte."""
    profondeur, debut, k = 1, True, i + 1
    while k < len(jets):
        j = jets[k][0]
        if _operateur(j):
            if ">" in j or "<" in j:
                # Une redirection et sa cible, là où une commande peut commencer.
                k += 1 if "<" not in j and k + 1 < len(jets) and _operateur(jets[k + 1][0]) else 2
                continue
            debut = True
        elif debut and not isinstance(j, _Tour):
            if j == "do":
                profondeur += 1
            elif j == "done":
                profondeur -= 1
                if not profondeur:
                    return k
            debut = j in RESERVES
        k += 1
    return None


def _apres_le_lanceur(argv: list[str]) -> int | None:
    """Le rang, dans `argv`, de la commande que lance `uv run` ou `poetry
    run`, leurs options sautées, avant `run` comme après, avec la valeur de
    celles qui en prennent une ; `None` si `argv` ne lance pas ainsi une
    commande (`uv sync`, `uv run` seul). Le module de `uv run -m module` est
    le programme, comme celui de `python -m` (B-0248)."""
    valeurs = LANCEURS.get(argv[0].rsplit("/", 1)[-1]) if argv else None
    if valeurs is None:
        return None
    i, run = 1, False
    while i < len(argv):
        mot = argv[i]
        if run and mot == "--":
            return i + 1 if i + 1 < len(argv) else None
        if mot.startswith("-") and mot != "-":
            i += 2 if mot in valeurs else 1
        elif run:
            return i
        elif mot == "run":
            run, i = True, i + 1
        else:
            return None
    return None


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
        elif (rang := _apres_le_lanceur(argv)) is not None:
            argv = argv[rang:]
        else:
            break
    # `python3 -m module …` : le module est le programme.
    if argv and re.fullmatch(r"python[\d.]*", argv[0].rsplit("/", 1)[-1]) and argv[1:2] == ["-m"] and len(argv) > 2:
        argv = argv[2:]
    return argv


def _sur_place(prefixe: list[str]) -> bool:
    """Le préfixe retiré d'une commande la lance-t-il dans le shell courant,
    une fonction comprise : des affectations seules (`F=1 f`), derrière le
    mot réservé `time` en tête et ses options `-p` et `--` (`time -p f`,
    la seconde revue du lot B-0234, B-0232). Un préfixe programme (`command
    f`, `sudo f`, `env f`, `F=1 time f`) lance un programme externe, non
    la fonction."""
    i = 0
    if prefixe[:1] == ["time"]:
        i = 1
        while prefixe[i:i + 1] in (["-p"], ["--"]):
            i += 1
    return all(AFFECTATION.fullmatch(p) for p in prefixe[i:])


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
    return _analyser(texte, _Etat(dossier, lieu, list(affectations or []), [], dossier), env, [DEPLIAGE_MAX])


def _analyser(texte: str, etat: _Etat, env: dict, budget: list[int],
              fonctions: dict[str, tuple[bool, list[str], list[str]]] | None = None,
              appels: list[str] | None = None) -> list[Commande]:
    """Les commandes simples de `texte`, depuis `etat`. `fonctions`, celles
    que le shell connaît déjà (une copie, pour une substitution ou un
    `eval`, que bash lance avec les fonctions du shell) ; `appels` reçoit
    le nom de chaque fonction que le texte appelle hors des corps qu'il
    définit, qu'un `eval` résout à son tour (B-0250)."""
    res: list[Commande] = []
    mots: list[str] = []
    redir: list[str] = []
    # Le corps du heredoc que reçoit l'entrée de la commande en cours (B-0229),
    # et la commande qui la précède dans son pipeline (B-0246).
    entree: str | None = None
    amont: Commande | None = None
    jets = _jetons(texte)
    # Ce que retrouve la suite d'un pipeline (chaque élément tourne dans un
    # sous-shell), d'une tâche de fond (toute la liste `a && b &`) et d'un
    # sous-shell `( … )` : l'état d'avant eux.
    debut_liste, debut_tube, en_tube = etat.copie(), etat.copie(), False
    englobants: list[tuple[_Etat, _Etat, _Etat, bool]] = []
    # Les commandes composées ouvertes (B-0204) : le mot qui l'ouvre, l'état
    # d'avant elle, ceux du début de sa liste et de son pipeline, pour une
    # boucle ce que dit `_boucle`, et, pour le corps `{ … }` d'une fonction,
    # son nom et les noms qu'il appelle (B-0232).
    composes: list[tuple[str, _Etat, _Etat, _Etat, bool, dict | None, tuple[str, list[str]] | None]] = []
    # Les fonctions définies dans le texte, ou que le shell connaît déjà
    # (une substitution, un `eval`), par leur corps `{ … }` : s'il change le
    # dossier, les variables qu'il affecte, et les noms qu'il appelle. À
    # l'appel, le hook rend inconnu ce qu'elles changent (le dossier, puis
    # chaque variable), avec ce que changent les fonctions qu'elles
    # appellent, connues au moment de l'appel, de proche en proche ; ce qui
    # suit se juge comme ADR-0072 juge un état inconnu. Une suppression du
    # projet par le dossier qu'un corps de fonction laisse derrière lui
    # passait sinon (la seconde revue du lot B-0234, B-0232).
    fonctions = dict(fonctions or {})
    # Ce que change l'appel de chaque nom, résolu (`effets`) : vidé à chaque
    # fonction définie.
    resolues: dict[str, tuple[bool, list[str]]] = {}
    # Les tours d'un `for` déplié : sa boucle, et le mot que prend sa variable.
    tours: list[tuple[dict, str]] = []
    # La commande lue juste avant un `||` était un `cd` : sous l'hypothèse
    # du `cd` qui réussit (B-0204), ce qui suit le `||` ne s'exécute pas.
    ou_apres_cd = False
    # Les commandes composées ouvertes juste après un tel `||` (`cd "$d" ||
    # { echo …; continue; }`), par leur rang dans `composes` : leurs sauts ne
    # se lisent pas non plus.
    echecs: list[int] = []
    # Un `nom ( )` ou un `function nom` vient de se lire : le `{` qui suit,
    # sur la même ligne ou après des sauts de ligne, ouvre le corps d'une
    # fonction (la revue du lot 3, J-2026-11-14-AH ; B-0232). `nom_defini`
    # retient le nom de cette fonction, jusqu'à l'ouverture de son corps.
    definition = False
    nom_defini = ""

    def lieu_de(cible: str) -> str:
        d = _cible_suivie(developper(cible, _visibles(env, etat.variables(env)))[0])
        if d.startswith(("/", INCONNU)):
            return normaliser(d)
        return normaliser(posixpath.join(etat.lieu, d)) if d else etat.lieu

    def changer(dossier: str, lieu: str):
        etat.vues += [("OLDPWD", etat.lieu), ("PWD", lieu)]
        etat.dossier, etat.lieu = dossier, lieu

    def aller(cible: str, depuis: Commande) -> str:
        return cible if cible.startswith(("/", "~")) else depuis.chemin(cible)

    def sous_shells(internes: list[str]):
        # Une substitution hérite des fonctions du shell (B-0250).
        for interne in internes:
            res.extend(_analyser(interne, etat.copie(), env, budget, fonctions))

    def ouvrir(mot: str, boucle: dict | None = None, nom: str | None = None):
        composes.append((mot, etat.copie(), debut_liste, debut_tube, en_tube, boucle,
                         None if nom is None else (nom, [])))

    def effets(nom: str) -> tuple[bool, list[str]]:
        """Ce que change l'appel de `nom` : s'il change le dossier, et les
        variables qu'il affecte, avec ce que changent les fonctions qu'il
        appelle, connues maintenant, de proche en proche ; chacune ne se lit
        qu'une fois, ce qui garde des cycles et de la récursion (B-0232)."""
        if nom not in resolues:
            change_dir, change_var, vues, pile = False, [], set(), [nom]
            while pile:
                n = pile.pop()
                if n in vues or n not in fonctions:
                    continue
                vues.add(n)
                d, v, a = fonctions[n]
                change_dir = change_dir or d
                change_var.extend(v)
                pile.extend(a)
            resolues[nom] = (change_dir, list(dict.fromkeys(change_var)))
        return resolues[nom]

    def appeler(nom: str):
        """`nom` s'appelle dans le shell courant : le corps de fonction
        ouvert le retient, ou à défaut `appels`, pour le résoudre à son
        propre appel, une fonction définie plus loin comprise ; ce que
        change une fonction de ce nom devient inconnu (B-0232)."""
        corps = next((x[6] for x in reversed(composes) if x[0] == "()"), None)
        if corps is not None:
            corps[1].append(nom)
        elif appels is not None:
            appels.append(nom)
        change_dir, change_var = effets(nom)
        if change_dir:
            changer(f"$({nom})", INCONNU)
        etat.vues.extend((v, None) for v in change_var)

    def ailleurs(boucle: dict | None) -> bool:
        """Un `break` ou un `continue` de la boucle s'est lu dans un autre
        dossier que celui où le tour finit : le tour d'après, et la suite de
        la boucle, peuvent partir de l'un comme de l'autre."""
        return bool(boucle) and any(lieu != etat.lieu for lieu in boucle["sauts"])

    def tour(rang: int):
        """Un tour d'un `for` déplié commence : sa variable prend son mot ;
        un saut lu ailleurs qu'où le tour d'avant finit rend son dossier
        inconnu."""
        boucle, valeur = tours[rang]
        if ailleurs(boucle):
            changer("$(for …)", INCONNU)
        etat.vues.append((boucle["nom"], valeur))

    def deplier(i: int, boucle: dict):
        """Le corps du `for` qu'ouvre le `do` de `jets[i]`, dont la liste a
        plusieurs mots, se répète, un tour par mot, chacun précédé de
        son `_Tour` (la seconde passation du lot 3, J-2026-11-14-AJ). Sans son
        `done`, il se lit une fois, sa variable valant tous les mots ;
        au-delà de ce qui reste de `DEPLIAGE_MAX` (`budget`), une fois, sa
        variable inconnue."""
        boucle["deplie"] = True
        fin = _fin_du_corps(jets, i)
        if fin is None:
            return
        corps, valeurs = jets[i + 1:fin], boucle["valeurs"]
        # Ce que chaque tour ajoute : ses mots, et ce que relisent ses
        # substitutions et ses `bash -c`, que chaque copie relit.
        cout = len(valeurs) * (1 + sum(1 + len(j) + sum(map(len, internes)) for j, internes in corps))
        if cout > budget[0]:
            boucle["lien"] = (boucle["nom"], None)
            return
        budget[0] -= cout
        boucle["lien"] = None
        deplie = []
        for valeur in valeurs:
            tours.append((boucle, valeur))
            deplie += [(_tour(len(tours) - 1), [])] + corps
        jets[i + 1:fin] = deplie

    def incertain():
        """Ce que la commande composée ouverte a changé, son dossier et ses
        variables, devient inconnu : le hook ne sait pas quelle branche,
        ni combien de tours, le shell prendra (B-0204)."""
        mot, avant, boucle = composes[-1][0], composes[-1][1], composes[-1][5]
        suite = etat.vues[len(avant.vues):] if len(etat.vues) >= len(avant.vues) else etat.vues
        changees = dict.fromkeys(nom for nom, _ in suite)
        etat.vues.extend((nom, None) for nom in changees)
        if INCONNU in etat.lieu or INCONNU in avant.lieu:
            if (etat.dossier, etat.lieu) != (avant.dossier, avant.lieu) or ailleurs(boucle):
                changer(f"$({mot} …)", INCONNU)
        elif etat.lieu != avant.lieu or ailleurs(boucle):
            changer(f"$({mot} …)", INCONNU)
        else:
            # Revenue à son dossier, connu (`cd x; …; cd ..`) : un tour la
            # laisse où elle était, comme une branche ; le dossier se dit
            # comme avant elle (la revue du lot 3, J-2026-11-14-AH).
            etat.dossier = avant.dossier
            if "PWD" in changees:
                etat.vues.append(("PWD", etat.lieu))

    def definir(k: int):
        """Une définition de fonction vient de se lire : ses `k` mots
        réservés de tête se suivent, et la commande qui suit est son corps.
        Son nom (`mots[-1]`) attend l'ouverture de son corps (B-0232) : il ne
        se pose qu'après les mots réservés, dont le `{` qui ouvre le corps
        d'une fonction qui la contient, et qui garde son propre nom (`f() {
        g() { …; }; … }`, la seconde revue du lot B-0234)."""
        nonlocal mots, definition, nom_defini
        nom = mots[-1].lstrip(CITE) if mots else ""
        mots = mots[:k]
        reserves()
        mots, definition, nom_defini = [], True, nom

    def reserves():
        """Retire les mots réservés en tête de la commande, et suit les
        commandes composées qu'ils ouvrent ou ferment (B-0204). Le corps
        d'une fonction s'ouvre comme un groupe, et rend en se fermant
        l'état d'avant lui : il ne s'exécute pas là où il s'écrit."""
        nonlocal mots, debut_liste, debut_tube, en_tube, etat, definition
        fonction = definition and bool(mots)
        if mots:
            definition = False
        if fonction and mots[0] == "{":
            mots = mots[1:]
            ouvrir("()", nom=nom_defini)
        while mots and mots[0] in RESERVES:
            mot, mots = mots[0], mots[1:]
            if mot in OUVRANTS:
                ouvrir(mot, _boucle() if mot in ("while", "until") else None)
                if ou_apres_cd:
                    echecs.append(len(composes))
            elif mot in ("else", "elif") and composes:
                incertain()
            elif mot == "do" and composes and composes[-1][5] and composes[-1][5]["lien"]:
                # Le corps d'un `for` qui ne se déplie pas : sa variable prend
                # le seul mot de sa liste, ou tous, ou une valeur inconnue.
                etat.vues.append(composes[-1][5]["lien"])
        if mots[:1] in (["for"], ["select"]):
            nom, liste = (mots[1:2] or [""])[0], mots[2:]
            valeurs = None
            if liste[:1] == ["in"] and mots[0] == "for":
                valeurs = _mots_de_la_liste(liste[1:], _visibles(env, etat.variables(env)))
            boucle = _boucle()
            if re.fullmatch(r"[A-Za-z_]\w*", nom):
                # Un `select` ne se déplie pas : l'humain choisit ses tours.
                valeur = None if mots[0] == "select" or liste[:1] != ["in"] else " ".join(
                    valeurs if valeurs is not None else (f for w in liste[1:] for f in accolades(w)))
                boucle.update(nom=nom, lien=(nom, valeur), valeurs=valeurs)
            ouvrir(mots[0], boucle)
        if mots[:1] and mots[0] in FERMANTS and composes:
            if mots[0] != "}":
                incertain()
            if echecs and echecs[-1] == len(composes):
                echecs.pop()
            ouvert, avant, debut_liste, debut_tube, en_tube, _, corps = composes.pop()
            if ouvert == "()":
                # Le corps `{ … }` d'une fonction : s'il a changé le dossier
                # ou affecté des variables, et les noms qu'il appelle, que son
                # appel résoudra (B-0232). Une redéfinition s'ajoute à la
                # première, qu'elle ne remplace peut-être pas (`if …; then
                # f() { …; }; fi`). Son état rendu, comme un groupe non
                # exécuté là.
                if corps and corps[0]:
                    suite = etat.vues[len(avant.vues):] if len(etat.vues) >= len(avant.vues) else etat.vues
                    # Le lieu, normalisé et absolu, dit seul un changement de
                    # dossier : un corps `cd a; cd ..` y revient (`.` et `` le
                    # disent autrement, comme la revue du lot 3 l'a vu).
                    change_dir = etat.lieu != avant.lieu
                    change_var = [v for v, _ in suite if v not in ("PWD", "OLDPWD")]
                    d, v, a = fonctions.get(corps[0], (False, [], []))
                    fonctions[corps[0]] = (d or change_dir, list(dict.fromkeys(v + change_var)),
                                           list(dict.fromkeys(a + corps[1])))
                    resolues.clear()
                etat = avant.copie()
            return avant
        return None

    def clore():
        nonlocal mots, redir, entree, amont
        avant = reserves()
        if avant is not None:
            # Le mot qui ferme une commande composée : ses redirections
            # s'ouvrent dans le dossier d'avant elle.
            if redir:
                res.append(Commande(mots, redir, avant.dossier, [], list(avant.vues), avant.lieu,
                                    avant.variables(env), env))
            mots, redir, entree = [], [], None
            return
        # Les mots réservés cités ont servi : leur marque tombe pour l'`argv`
        # (`"function" f` lance la commande `function`, B-0232).
        mots = [m.lstrip(CITE) for m in mots]
        argv = _sans_prefixes(mots)
        if not argv and mots and all(AFFECTATION.fullmatch(m) for m in mots):
            # Une affectation seule vaut pour la suite ; devant une commande,
            # elle ne vaut que pour celle-ci.
            etat.vues.extend(_affectation(m) for m in mots)
        if argv or redir:
            c = Commande(argv, redir, etat.dossier, mots[:len(mots) - len(argv)], list(etat.vues), etat.lieu,
                         etat.variables(env), env, entree, amont)
            amont = None
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
            elif nom in ("bash", "sh", "zsh", "dash") and (script := _script_du_shell(argv)) is not None:
                res.extend(_analyser(script, etat.copie(), env, budget))
            elif nom == "eval":
                # `eval` lit son texte dans le shell courant, avec ses
                # fonctions ; celles qu'il appelle s'appellent ici, et ce
                # qu'elles changent vaut pour la suite (B-0250). Un `bash
                # -c`, un autre processus, ne les connaît pas.
                lus: list[str] = []
                res.extend(_analyser(" ".join(argv[1:]), etat.copie(), env, budget, fonctions, lus))
                for appelee in lus:
                    appeler(appelee)
            elif nom in SAUTS and not ou_apres_cd and not echecs:
                # Un saut, vers la suite d'une boucle ou son tour d'après :
                # son dossier se compare à celui où le tour finit. Il vaut
                # pour la boucle la plus intérieure, ou pour les `n` plus
                # intérieures (`break 2`), toutes si `n` ne se lit pas ; il
                # ne sort pas du corps d'une fonction, qui ne s'exécute pas
                # là où il s'écrit.
                n = (int(argv[1]) if argv[1].isdigit() else len(composes)) if len(argv) > 1 else 1
                for x in reversed(composes):
                    if x[0] == "()" or n <= 0:
                        break
                    if x[5] is not None:
                        x[5]["sauts"].append(etat.lieu)
                        n -= 1
            elif argv and _sur_place(c.prefixe):
                # L'appel, peut-être, d'une fonction, par son nom entier
                # (`function f/x` s'appelle `f/x`) : si son corps change le
                # dossier ou des variables, ou appelle une fonction qui les
                # change, ce qu'elle change devient inconnu, et ce qui suit se
                # juge comme un état inconnu (B-0232). Un préfixe programme
                # (`command f`, `sudo f`, `env f`) lance un programme externe,
                # non la fonction, et ne fuit rien ; une affectation devant
                # (`F=1 f`) ou `time` l'appellent.
                appeler(argv[0])
            etat.vues.extend(_affectations(argv))
            etat.vues.extend((m.group(1), None) for x in mots + redir for m in DEFAUT_AFFECTE.finditer(x))
            res.append(c)
        mots, redir, entree = [], [], None

    i = 0
    while i < len(jets):
        j, internes = jets[i]
        if isinstance(j, _Tour):
            tour(j.rang)
            i += 1
            continue
        if (j == "do" and not mots and composes and (b := composes[-1][5]) and b["valeurs"]
                and len(b["valeurs"]) > 1 and not b["deplie"]):
            deplier(i, b)
        if not _operateur(j):
            if not redir and (k := _fonction_sans_parentheses(mots)) is not None:
                # `function nom`, sans parenthèses : ce mot commence son
                # corps, comme après `nom ( )` (B-0232).
                definir(k)
            sous_shells(internes)
            # Un mot réservé cité garde sa marque dans `mots`, pour que les
            # mots réservés et les définitions ne le lisent pas comme une
            # structure ; `clore` la retire pour l'`argv` (B-0232).
            mots.append(j if j[:1] == CITE and j.lstrip(CITE) in MOTS_STRUCTURE else j.lstrip(CITE))
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
                redir.append(suivant.lstrip(CITE))
            i += 2
            continue
        if "<" in j:
            sous_shells(internes)
            if j in ("<", "<<", "<<<"):
                # La dernière redirection de l'entrée l'emporte : un heredoc
                # y donne son corps, un fichier ou une chaîne autre chose.
                entree = getattr(suivant, "corps", None) if j == "<<" else None
            i += 2
            continue
        if j == "(" and suivant == ")" and not redir and (k := _definition(mots)) is not None:
            # `nom ( )`, ou `function nom ( )` : les mots réservés qui le
            # précèdent se suivent, et le `{` qui suit ouvre son corps.
            definir(k)
            i += 2
            continue
        if j == "\n" and not redir and (k := _fonction_sans_parentheses(mots)) is not None:
            # `function nom`, son corps sur une ligne suivante (B-0232).
            definir(k)
            i += 1
            continue
        lues = len(res)
        clore()
        if j != "\n":
            # Le corps d'une fonction est la commande qui suit sa définition,
            # par-delà des sauts de ligne seulement : un sous-shell l'est, et
            # un groupe qu'il contient ne se lit plus comme lui (B-0232).
            definition = False
        ou_apres_cd = j == "||" and len(res) > lues and res[-1].programme in ("cd", "pushd", "popd")
        if j == "(":
            englobants.append((etat.copie(), debut_liste, debut_tube, en_tube))
            debut_liste, debut_tube, en_tube = etat.copie(), etat.copie(), False
        elif j == ")":
            if englobants:
                etat, debut_liste, debut_tube, en_tube = englobants.pop()
        elif j in ("|", "|&"):
            etat, en_tube = debut_tube.copie(), True
            # Ce qui écrit dans le tube : la dernière commande lue, celle
            # d'un groupe ou d'une boucle qui se ferme compris.
            amont = res[-1] if res else None
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


def se_croisent_tous(motifs_shell: list[str], motif_chemin: str, permissif: bool = False) -> bool:
    """Un même chemin peut-il répondre à chacun des motifs du shell et au
    motif de chemin, comme `se_croisent` pour un seul : les filtres d'une
    même conjonction d'un `find` (B-0231)."""
    shells = [_elements_shell(m, permissif) for m in motifs_shell]
    chemins = _elements_chemin(motif_chemin.lower() if permissif else motif_chemin)
    if len(shells) == 1:
        return any(_se_croisent(shells[0], b) for b in chemins)
    return any(_se_croisent_tous(*shells, b) for b in chemins)


# Les états que parcourt au plus le croisement de plus de deux motifs : au-delà,
# ils sont dits se croiser, un refus de trop plutôt qu'un hook trop lent.
ETATS_MAX = 200_000


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


def _se_croisent_tous(*suites: list) -> bool:
    """`_se_croisent` pour plus de deux suites : celles de motifs du shell,
    puis la dernière, d'un motif de chemin. Un parcours de leur produit :
    (la position dans chacune, au début d'un nom), chaque pas rendant un
    caractère que toutes admettent ; au-delà de `ETATS_MAX` états, elles
    sont dites se croiser (B-0231)."""
    fins = tuple(len(s) for s in suites)
    shells = range(len(suites) - 1)
    vus: set = set()
    pile = [((0,) * len(suites), True)]
    while pile:
        etat = pile.pop()
        if etat in vus:
            continue
        if len(vus) > ETATS_MAX:
            return True
        vus.add(etat)
        positions, debut = etat
        if positions == fins:
            return True
        for k, (i, s) in enumerate(zip(positions, suites)):
            if i < len(s) and s[i][1]:
                pile.append((positions[:k] + (i + 1,) + positions[k + 1:], debut))
        if any(i == n for i, n in zip(positions, fins)):
            continue
        elements = [s[i] for i, s in zip(positions, suites)]
        ensemble = elements[0][0]
        for e in elements[1:]:
            ensemble = _commun(ensemble, e[0])
        suivantes = tuple(i if e[1] else i + 1 for i, e in zip(positions, elements))
        # Le `.` qui ouvre un nom ne répond qu'à un `.` écrit.
        interdits = {"/", "."} if debut and any(elements[k][2] for k in shells) else {"/"}
        if _rend(ensemble, "/"):
            pile.append((suivantes, True))
        if ensemble[0] or ensemble[1] - interdits:
            pile.append((suivantes, False))
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

