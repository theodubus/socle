"""Une commande shell, découpée en commandes simples, pour que les hooks
jugent ce qu'elle fait et non le texte qu'elle cite.

Un heredoc, une chaîne entre guillemets ou un message de commit qui
nomment une commande dangereuse ne la lancent pas ; un lanceur entre
guillemets, un `git -C .`, des drapeaux groupés (`-fu`) ou un `cd` la
lancent bien. Le découpage suit les guillemets, les séparateurs (`;`, `&&`,
`||`, `|`, fin de ligne), les redirections, les `cd`, les préfixes (`env`,
`sudo`, `nohup`…) et les `bash -c`.

Heuristique, comme tout ce qui lit du shell sans l'exécuter : les
substitutions (`$(…)`, accents graves), les alias et les fonctions ne sont
pas suivis. Le hook n'est qu'un étage ; la CI juge ce qui est commité.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import dataclass, field

# Les préfixes qui lancent la commande qui les suit.
PREFIXES = {"sudo", "command", "exec", "nohup", "time", "builtin", "nice", "stdbuf", "timeout", "xargs", "env"}
# Les options de ces préfixes qui prennent une valeur.
VALEURS = {"sudo": ("-u", "-g", "-C"), "nice": ("-n",), "env": ("-u", "-C"), "timeout": ("-s", "-k"),
           "xargs": ("-I", "-L", "-P", "-n", "-s", "-E", "-d")}
HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([\w.-]+)\2")


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


def jetons(texte: str) -> list[str]:
    """Les mots et les opérateurs de la commande, guillemets retirés."""
    texte = sans_heredocs(texte.replace("\\\n", " "))
    lex = shlex.shlex(texte, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError:  # guillemets non fermés : on juge chaque mot tel quel
        return texte.split()


def _operateur(jeton: str) -> bool:
    return bool(jeton) and all(c in ";&|()<>\n" for c in jeton)


def _sans_prefixes(argv: list[str]) -> list[str]:
    """La commande lancée derrière ses affectations et ses préfixes."""
    while argv:
        if re.fullmatch(r"[A-Za-z_]\w*=.*", argv[0], re.S):
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


def analyser(texte: str, dossier: str = "") -> list[Commande]:
    """Les commandes simples d'un texte de shell, dans l'ordre."""
    res: list[Commande] = []
    mots: list[str] = []
    redir: list[str] = []
    jets = jetons(texte)

    def clore():
        nonlocal mots, redir, dossier
        argv = _sans_prefixes(mots)
        if argv or redir:
            c = Commande(argv, redir, dossier, mots[:len(mots) - len(argv)])
            nom = c.programme
            if nom == "cd":
                cible = argv[1] if len(argv) > 1 else "~"
                dossier = cible if cible.startswith(("/", "~")) else c.chemin(cible)
            elif nom in ("bash", "sh", "zsh", "dash") and "-c" in argv[1:-1]:
                res.extend(analyser(argv[argv.index("-c") + 1], dossier))
            elif nom == "eval":
                res.extend(analyser(" ".join(argv[1:]), dossier))
            res.append(c)
        mots, redir = [], []

    i = 0
    while i < len(jets):
        j = jets[i]
        if _operateur(j):
            if ">" in j:
                if mots and mots[-1].isdigit():
                    mots.pop()  # le descripteur de `2>`
                cible = jets[i + 1] if i + 1 < len(jets) else ""
                if not (j.endswith("&") and (cible.isdigit() or cible == "-")) and not _operateur(cible):
                    redir.append(cible)
                i += 2 if not _operateur(cible) else 1
                continue
            if "<" in j:
                i += 2
                continue
            clore()
            i += 1
            continue
        mots.append(j)
        i += 1
    clore()
    return res


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

