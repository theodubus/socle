# Notes de version du socle

Ce que chaque changement du socle change pour un projet installé, et ce que
l'agent du projet doit en faire. Une entrée par changement, la plus récente
d'abord, sous un identifiant qui ne change jamais : la date du changement et
une lettre. À la mise à jour, l'installeur donne les entrées que la copie du
moteur du projet n'avait pas, et le message de commit qu'il propose nomme
leurs identifiants.

## 2026-11-15-a — Le skill socle-batch dit quand compacter et quel modèle pour quel travail

La section « La consommation » du skill `socle-batch` a deux règles de
plus. L'agent ne compacte pas lui-même : il écrit la mémoire (chantier
actif, journal), puis demande le compactage à l'humain, à la fin d'un lot
si l'humain garde la session au-delà, et avant toute attente qui peut
passer l'heure sans changer de session ; près d'une limite, le seuil qui
fait changer de session prime ; après la pause, compacter relit toute la
conversation au prix fort. Le modèle est celui que demande la qualité du
travail, jamais un moindre pour tenir une limite : une limite retarde un
lot, elle ne l'allège pas. Entre ceux qui le font aussi bien, celui qui
consomme le moins de la limite par jeton, surtout pour la conversation
qui orchestre ; l'humain choisit celui de la session, sur le conseil de
l'agent ; le modèle que fixent les instructions du projet prime, et un
sous-agent reçoit le sien explicitement à son lancement.

À faire : le skill est dans la demande des fichiers protégés de la mise à
jour ; une fois posé, demander le compactage aux moments qu'il dit,
conseiller à l'humain le modèle de la session, et nommer le modèle de
chaque sous-agent à son lancement.

## 2026-11-14-k — Le hook de l'agent voit ce qu'écrivent cp -t, find -delete, xargs, bash -ec, sort -o et python -c

Le hook de l'agent juge désormais ces écritures d'un fichier protégé :
`cp`, `ln`, `install` et `mv` écrivent le dossier de `-t`, `sort` le
fichier de `-o` ; `bash -ec '…'`, `bash -lc '…'` et `bash -c -- '…'`
ouvrent leur commande ; `find -delete`, ou `find -exec rm {} +`, se juge
par ses points de départ et les filtres de nom ou de chemin qui gardent
son action, à toute profondeur : `find . -name '*.pyc' -delete` passe,
`find . -name '*.toml' -delete` est refusé. Un filtre ne garde que
l'action qui le suit, hors d'un `!` et de l'autre branche d'un `-o` ;
le `*` d'un `-path` traverse les dossiers, comme dans `find`. `python -c`
et `xargs` d'un écrivain, que le hook ne sait pas lire, se jugent par les
chemins protégés qu'ils citent en toutes lettres : `echo <fichier
protégé> | xargs rm` est refusé, comme un `python -c` qui cite un
fichier protégé, même pour le lire.

À faire : lire un fichier protégé par `cat` ou par l'outil de lecture,
plutôt que par un `python -c` qui le cite, que le hook refuse désormais ;
il refuse aussi un `python -c` qui cite un dossier contenant un fichier
protégé, même pour le lister (`os.listdir('.socle')`) : le lister par
`ls`. Le hook refuse de même un `find` qui supprime ou écrit ce qu'il
trouve depuis la racine sans filtre de nom ou de chemin, même avec
`-type` ou `-empty` (`find . -type d -empty -delete`, `find . -type f
-exec sed -i … {} +`) : lui donner un filtre de nom ou de chemin, ou le
faire partir d'un dossier du projet.

## 2026-11-14-j — Le hook de l'agent ne perd plus la commande qui suit un dièse ou des guillemets imbriqués

Le hook de l'agent lit un `#` comme le shell : il n'ouvre un commentaire
qu'en tête d'un mot, et le commentaire s'arrête à la fin de sa ligne. Un
`#` au milieu d'un mot (`x#`, `$#`, une adresse) ne fait plus perdre la
commande qui suit, ni un commentaire en fin de ligne celle de la ligne
suivante. Une substitution entre guillemets dont l'argument a ses propres
guillemets (`"$(cmd "arg")"`) se lit aussi comme le shell la lit : la
commande qui la suit se juge. Ce que lance la substitution elle-même ne se
juge toujours pas.

À faire : rien.

## 2026-11-14-i — Le hook de l'agent lit les conditions et les boucles

Le hook de l'agent juge désormais une commande écrite derrière un mot
réservé du shell (`then`, `else`, `elif`, `do`, `!`, `{`, `if`, `while`,
`until`) : une écriture d'un fichier protégé, une action irréversible ou une
commande réservée à l'humain dans le corps d'une condition ou d'une boucle
ne passe plus, comme hors d'elle. Ce qu'une condition ou une boucle change,
son dossier et ses variables, devient inconnu après elle, sauf un dossier
où elle revient (`for d in */; do cd "$d"; …; cd ..; done`) sans qu'un
`break` ou un `continue` l'ait quittée ailleurs ; le corps d'un `for` se
juge une fois par mot de sa liste, sa variable liée à ce mot, si bien que
`for d in .socle memory; do cd $d; …; done` se juge dans chacun des deux
dossiers, et `for f in *.md; do sed -i … "$f"; done` par son motif. Le corps d'une
fonction (`f() { …; }`) se juge, mais ce qu'il change ne vaut pas pour la
suite : il ne s'exécute pas là où il s'écrit.

À faire : rien, sauf si le hook refuse désormais une boucle qui écrit vers
une variable qu'il ne connaît pas (`while read f; do sed -i … "$f"; done`) :
écrire la liste des fichiers en toutes lettres, dans un `for`, ou les
traiter par l'outil d'écriture de fichiers. Des `for` imbriqués de
plusieurs milliers de tours, qu'il ne déplie pas, ont la même variable
inconnue : les découper en commandes plus courtes.

## 2026-11-14-h — Le hook de l'agent lit depuis son dossier courant le fichier qu'une commande publie

Pour juger une fuite de la mémoire privée, le hook de l'agent lit le
fichier qu'une commande publie (`git commit -F`, `gh … --body-file`, `gh
api -F champ=@x`). Il lisait un chemin relatif depuis la racine du projet,
quel que soit le dossier courant de l'agent : après un `cd docs`, `git
commit -F message.txt` lui faisait lire le `message.txt` de la racine, et
non celui que git publie. Il le lit désormais depuis le dossier courant de
l'agent, comme les chemins qu'une commande écrit.

À faire : rien.

## 2026-11-14-g — Le hook de l'agent refuse la suppression d'un dossier qui contient le projet

Le hook de l'agent laissait passer `rm -rf ..` lancé depuis la racine, et
la suppression d'un dossier qui la contient (le dossier de l'utilisateur,
celui des worktrees d'un sous-agent) : elle emporterait le code, la
mémoire, la politique et les hooks, et aucun contrôle ne la rattrape
ensuite. Il refuse désormais la suppression d'un tel dossier par les
arguments de `rm`, les sources d'un `mv`, ce que balaie `git clean` et les
points de départ d'un `find` qui supprime (`-delete`, `-exec rm`), son
chemin développé comme tout chemin que le hook juge ; et celle du projet
par un `find` qui part de sa racine sans qu'un filtre de nom ou de chemin
garde ce qu'il supprime (`find . -delete`, `find . -type f -delete`, `find
. -delete -name '*.pyc'`, dont le filtre vient après l'action, ou `find .
-path ./.git -prune -o -delete`). Un dossier voisin du projet, un dossier
du projet (`find build -delete`) et un `find` qui filtre ce qu'il
supprime sous la racine restent libres.

À faire : rien. Un tel refus se lève en visant un dossier du projet, ou
hors de lui un dossier qui ne le contient pas, écrit en toutes lettres.

## 2026-11-14-f — Le modèle de menace du hook de l'agent

Le guide dit désormais ce que le hook de l'agent arrête : les erreurs d'un
agent coopératif, avant qu'elles agissent. Il juge les formes du shell
qu'un agent écrit dans son travail, et, quelle qu'en soit la forme, ce que
rien ne rattrape ensuite : supprimer le projet ou un dossier qui le
contient, une action externe irréversible, une fuite de la mémoire privée
dans ce qui se publie. Une écriture d'un fichier protégé sous une forme
qu'on n'écrit que pour contourner (un `eval`, `IFS`, un chemin construit au
vol dans un autre langage) est hors de son modèle : le contrôle
`protege.fichiers` la refuse ensuite. Le hook lui-même ne change pas. La
suppression du projet lui échappe encore quand un autre programme que
`rm`, `mv`, `git clean` ou `find` la fait (`rsync --delete`, `git worktree
remove`, un `python3 -c` qui appelle `shutil.rmtree`, `xargs rm`) : rien
ne la rattrape.

À faire : un trou du hook de cette dernière sorte, qu'une revue trouve,
n'ouvre pas de sujet au backlog ; un trou par lequel passe ce que rien ne
rattrape en ouvre un, quelle qu'en soit la forme.

## 2026-11-14-e — Le skill socle-batch conduit un lot

Un skill nouveau du socle, `socle-batch`, posé et protégé comme les autres
sous `.claude/skills/`, dit comment mener un lot de sa formation à sa
livraison : l'annoncer, un sous-agent par sujet, la revue sans contexte
avant tout push, l'intégration, la CI et la fusion, une session par lot,
les seuils de consommation au-delà desquels on range, et le changement de
session avec le prompt de la suivante. Après la fusion, rien ne se pousse
sans travail neuf. Un agent sans sous-agents mène le lot seul.

À faire : le skill est dans la demande des fichiers protégés de la mise à
jour ; une procédure du projet qui menait déjà ses lots ne garde que ce qui
lui est propre.

## 2026-11-14-d — Un lot se garde au backlog

Un lot, les sujets qu'on mène ensemble parce qu'ils touchent les mêmes
fichiers, le même garde-fou ou les mêmes tests et qu'une seule revue les
juge, se garde désormais au backlog : un sujet marqué `forme : lot`, dont
`après` nomme ses sujets et le lot d'avant. L'état montre le prochain lot à
côté du prochain jalon, avec ce qui en reste et où en est chacun de ses
sujets. Un lot n'est jamais un sujet prêt, et il ne se clôt pas avant ses
sujets.

À faire : poser en lot les sujets qu'on prévoit de mener ensemble, au lieu
de ne les écrire que dans le chantier actif ; clore le lot quand ses sujets
le sont.

## 2026-11-14-c — Les notes de version

Ce fichier existe. Une mise à jour qui recopie le moteur imprime, entre ce
qu'elle a posé et l'audit, les entrées que la copie remplacée n'avait pas ;
une copie qui n'en avait aucune les reçoit toutes, dont celles qui décrivent
ce que le projet a déjà. Le message de commit que propose « Et maintenant »
nomme leurs identifiants dans un second paragraphe, pour la session suivante.

À faire : lire chaque entrée donnée et faire ce qu'elle demande ; garder ce
second paragraphe dans le commit de la mise à jour. Une session qui trouve
une mise à jour qu'elle n'a pas lancée lit les entrées que ce commit nomme.

## 2026-11-14-b — La fin de tour dit la mise à jour en une ligne

Entre l'installation et le push de sa demande, la fin de tour ne liste plus
chaque fichier protégé que la mise à jour a posés, avec sa commande de
remise : une seule ligne, « une mise à jour du socle attend sa demande : la
poser », avec leur nombre et la commande qui les liste avec leurs empreintes
(`python3 .socle/socle check --stage agent --only protege.fichiers`). Le
verrou du moteur nomme désormais, sous `[installed]`, ceux que l'installeur
a posés hors du moteur, avec leur empreinte : c'est ainsi qu'elle les
reconnaît.

À faire : ne pas remettre ces fichiers, poser la demande. Un fichier protégé
changé avant ou après le passage de l'installeur garde sa ligne et sa
commande de remise.

## 2026-11-14-a — Une réponse de l'humain se consigne aussitôt, et part avec ce qu'elle autorise

Une réponse donnée dans la conversation se consigne tout de suite dans
l'arbre (`python3 .socle/socle answer D-NNNN valider --relayed …`) : l'état
lit l'arbre et ne la dit plus en attente. Elle se commite et se pousse avec
le changement qu'elle autorise (une valeur attendue, une clé des garde-fous,
un fichier protégé), dans le même push, jamais avant : la CI d'un push ne
compte que les validations de sa plage. Seul un fichier protégé peut la
précéder, poussé sous la demande en attente. Un contrôle nouveau,
`demandes.reponse-seule`, avertit quand la réponse partirait seule : dans
`verify --fast`, au commit et avant le push. Le skill `socle-request`, une
copie protégée, le dit.

À faire : consigner chaque réponse dès qu'elle est donnée, et la pousser
avec ce qu'elle autorise. Poussée seule, elle ne couvre pas le changement qui
la suit : la consigner alors une seconde fois.

## 2026-11-13-c — La revue juge un lot contre ses sujets

Le dossier de `python3 .socle/socle review` donne au relecteur le « Fait
quand » de chaque sujet que le lot touche, même ouvert, et les titres de
ceux qu'il ouvre ; le relecteur classe chaque constat, bloquant (un critère
coché ou une décision contredits, une régression, une perte de données, un
contournement d'un garde-fou dans son modèle de menace) ou pour le backlog.
Le skill `socle-review`, une copie protégée, change.

À faire : corriger les bloquants dans le lot et mettre les autres au backlog ;
une seconde revue seulement si la correction est lourde, sur elle seule
(`python3 .socle/socle review --since <commit relu>`). Un sujet qui pose ou
change un garde-fou écrit avant son code une section « ## Modèle de menace »
(ce qu'il arrête, ce qu'il laisse passer) ; un sujet dont la conception
n'est pas tranchée, sa spécification.

## 2026-11-13-b — Le hook de l'agent développe les chemins comme le shell

Le hook juge un chemin qu'une commande shell écrit tel que le shell le
développerait : variables, motifs (`*`, `?`), accolades, `~`, `cd` et
`pushd` suivis, chemins relatifs au dossier courant. Ce qu'il ne sait pas
développer (une variable inconnue, `$(…)`, un `cd` vers un tel chemin) est
refusé s'il peut tomber dans le projet. Les faux refus connus : `$(mktemp -d)`
ou `$(git rev-parse --show-toplevel)` gardés dans une variable ou pris pour
cible d'un `cd`, une boucle `for` sur une liste écrite.

À faire : sur un refus, écrire le chemin en toutes lettres, ou affecter la
variable plus tôt dans la même commande (`F=/tmp/x; echo y > "$F"`). Le hook
n'est qu'une première barrière : le contrôle `protege.fichiers` reste la
garantie.

## 2026-11-13-a — La sortie du démarrage est bornée

La sortie du hook de démarrage dépassait ce que Claude Code remet entier, et
l'agent n'en recevait qu'un aperçu. Elle tient désormais sous
`[startup] max_bytes` des garde-fous (9 500 octets) : d'abord ce qui demande
d'agir, puis l'état, le chantier actif en entier, les faits par leur titre
et les dix dernières décisions. Une partie qui dépasse sa part perd des
lignes entières, et une dernière ligne « !! coupé » dit ce qui manque et où
le lire. Le budget du chantier actif passe à 3 700 octets, public et privé
ensemble.

À faire : lire aussitôt ce qu'une ligne « !! coupé » dit manquer
(`python3 .socle/socle state --short` pour l'état entier,
`python3 .socle/socle show <ID>` pour une entrée). Si l'installeur dit que le
budget de `memory/active.md` est au-dessus de sa part, le baisser à la valeur
qu'il donne (durcir est libre), puis raccourcir le chantier actif, ce qui en
sort allant au journal.

## 2026-11-12-a — L'adoption ne tolère que les constats déjà présents

Dans un projet adopté, un contrôle sous `[adoption] warn_only` ne passe plus
en avertissement tout entier : seuls les constats consignés sous
`[adoption.tolerated]` des garde-fous le sont, et tout constat nouveau
échoue. À la mise à jour, l'installeur y consigne les constats de la base
encore présents, et le dit. Un fichier renommé garde ses constats si sa clé
est renommée dans la même pull request.

À faire : lire ce que l'installeur dit de la liste ; corriger un constat
nouveau au lieu de l'ajouter, puisqu'ajouter assouplit et attend une demande
validée ; retirer un constat résorbé, ce qui est libre ; renommer la clé d'un
fichier renommé dans la pull request qui le renomme.

## 2026-11-11-b — L'agent peut remettre un fichier protégé à son état du dernier commit

Le hook de l'agent laisse passer `git restore --source=HEAD -- <fichier>` et
`git checkout HEAD -- <fichier>`, chaque chemin écrit en toutes lettres, et
`rm <fichier>` pour un fichier apparu sous un chemin protégé que git ne suit
pas. Les réglages de Claude Code en restent exclus, et un fichier que cite
une demande dont l'approbation n'est pas commitée est épargné.

À faire : rien ; c'est la forme que donnent le refus d'écriture et l'erreur
de `protege.fichiers`, pour défaire un changement fait par erreur.

## 2026-11-11-a — Le hook refuse l'installeur hors du mode du verrou

Le hook de l'agent refuse `socle install` sur un projet équipé dans un autre
mode que celui de son verrou, et une cible qu'il ne sait pas résoudre (une
variable, `$(…)`, `~autre`, dans la cible ou dans le `cd` qui la précède).
La ligne de commande refuse les options abrégées.

À faire : lancer la mise à jour dans le mode du verrou, la cible écrite en
toutes lettres (`--target .`) ; changer le mode d'un projet revient à
l'humain.

## 2026-11-10-b — La mise à jour approuvée par une demande

L'installeur rend 0 quand l'installation a réussi et que seule
l'approbation des fichiers protégés attend. En session cloud, la demande qui
les approuve se pose par `python3 .socle/socle new request "<décision>"`, qui
en imprime le contrat ; chaque fichier protégé s'y écrit sur sa ligne, son
chemin et son empreinte sans rien d'autre, et ces lignes ne comptent pas
dans le budget de la demande. Le hook avant commit refuse une référence que
le commit ne contient pas.

À faire : suivre « Et maintenant » dans son ordre : la demande seule
d'abord, poussée, puis les fichiers protégés avec ce qui les cite (journal,
chantier actif).

## 2026-11-10-a — Les branches jetables

Une branche dont le nom commence par un préfixe de `[branches] disposable`
des garde-fous, `proto/` à défaut, n'est pas jugée par la CI à chaque envoi ;
sa pull request la juge en entier, et la protection de la branche par défaut
bloque la fusion tant que la CI est rouge. Le workflow de CI, un fichier
protégé, change à la mise à jour.

À faire : rien. Un essai qu'on ne veut pas faire juger à chaque push va sur
une branche `proto/…` ; ajouter un préfixe assouplit, et attend une demande
validée.

## 2026-11-09-a — L'empreinte de lecture ne couvre plus les métadonnées

L'empreinte d'une entrée de la mémoire (`ID@xxxxxxxx`, que
`python3 .socle/socle show` imprime) couvre son titre et son corps, sans les
lignes `>` qui suivent le titre : changer un statut ne périme plus une
citation. Toutes les empreintes changent donc avec cette version ; une
citation écrite avant reste acceptée tant qu'elle correspond. Une citation
ne prouve plus qu'un statut a été lu.

À faire : relire une entrée (`python3 .socle/socle show <ID>`) avant de la
citer de nouveau, pour en prendre l'empreinte ; ne pas récrire les
citations anciennes. Lire le statut dans l'index (`python3 .socle/socle show
--index decisions`, ou `backlog`).
