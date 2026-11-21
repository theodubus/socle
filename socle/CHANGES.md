# Notes de version du socle

Ce que chaque changement du socle change pour un projet installé, et ce que
l'agent du projet doit en faire. Une entrée par changement, la plus récente
d'abord, sous un identifiant qui ne change jamais : la date du changement et
une lettre. À la mise à jour, l'installeur donne les entrées que la copie du
moteur du projet n'avait pas, et le message de commit qu'il propose nomme
leurs identifiants.

## 2026-11-21-d — L'installeur nomme le hook de fin de tour que le projet a déjà

L'installeur garde les hooks que le projet déclare lui-même dans
`.claude/settings.json`, à côté de ceux du socle, et signalait déjà un
état au démarrage propre au projet. Il ne disait rien d'un hook `Stop`
propre au projet : celui-ci tire à chaque fin de tour à côté de celui du
socle, et, s'il lance les mêmes vérifications, chaque fin de tour les
paie deux fois. À l'installation comme à la mise à jour, l'installeur le
nomme désormais, d'une ligne qui dit qu'il peut doubler celui du socle.

À faire : si l'installeur nomme un hook de fin de tour du projet, le
dire à l'humain : lui seul le retire de `.claude/settings.json`, ou n'y
laisse que ce qui est propre au projet, si le hook du socle fait déjà
le reste.

## 2026-11-21-c — « Et maintenant » ne fait plus commiter les fichiers protégés d'une mise à jour avant sa demande

En session cloud, une mise à jour qui change des fichiers protégés
disait à la session qui a dû ajouter le dépôt du socle d'y commiter,
pousser la branche et ouvrir la pull request, la demande se posant
ensuite dans une session neuve. Le hook avant commit refuse pourtant un
fichier protégé changé qu'aucune demande en attente ne couvre : cette
session ne pouvait pas faire ce qu'on lui disait. Elle n'y commite
désormais les fichiers protégés qu'après y avoir posé la demande, en
deux temps comme toute session, quand la branche par défaut exige la CI
du socle ; sinon, elle n'y commite rien, et la mise à jour se refait
dans une session neuve sur le seul dépôt du projet, le dépôt du socle
cloné sans y être ajouté.

À faire : rien.

## 2026-11-21-b — Une mise à jour ne pose plus un second adaptateur du langage d'une copie déjà là

Un projet dont Python est un langage de plus que le principal a sa copie
`.socle/adapters/python.toml`. Quand un `conftest.py` y apparaissait,
une mise à jour avec `--adapter auto` détectait `python-pytest` et en
posait la copie à côté : deux adaptateurs du même langage, dont les
motifs se recouvrent, que le contrôle `adaptateur.recouvrement` refusait
ensuite. L'installeur ne comparait le langage d'un adaptateur détecté ou
nommé qu'à celui de l'adaptateur principal ; il le compare désormais
aussi à celui de chaque copie déjà posée, et un adaptateur de ce langage
est cette copie, qu'il rafraîchit ou garde comme avant.

À faire : rien, sauf si une mise à jour précédente a posé dans
`.socle/adapters/` un second adaptateur du langage d'une copie déjà là
(`adaptateur.recouvrement` en échec) : proposer alors à l'humain, par une
demande, de retirer celle des deux que le projet n'a pas choisie.

## 2026-11-21-a — Relancé avant le commit d'une mise à jour, l'installeur nomme encore ses notes de version

L'installeur lisait les notes de version déjà vues dans la copie du
moteur de l'arbre. Relancé avant le commit de la mise à jour (après
`git fetch --unshallow`, ou pour corriger `--adapter`), il y trouvait
déjà la copie nouvelle et ne voyait plus de notes nouvelles : le message
de commit qu'il propose, comme l'étape qui ouvre l'agent, ne les
nommait plus. Il les lit désormais dans la copie du moteur du dernier
commit ; dans l'arbre seulement quand le dépôt n'a pas de commit, ou que
le dernier n'a pas de copie du moteur.

À faire : rien.

## 2026-11-20-r — Le skill `socle-batch` fait attendre, après une fusion par l'agent, les workflows qu'elle lance

Une fusion sur la branche par défaut peut lancer un déploiement ou une
publication ; s'il échouait, rien ne le disait, et l'agent passait au lot
suivant. L'étape de la fusion du skill `socle-batch` le dit désormais :
l'agent qui fusionne lui-même sa pull request, quand la politique le
permet, attend ensuite les workflows que la fusion lance sur la branche
par défaut, comme il attend la CI, et son récap dit s'ils ont réussi.
Qui fusionne, l'étape le lit dans la politique, et non plus dans les
instructions du projet.

À faire : rien ; le skill `socle-batch` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-20-q — La fusion de sa pull request par l'agent, une option de la politique que l'humain active

Le hook refuse à l'agent la fusion d'une pull request, comme les autres
actions externes. La politique que pose l'installeur porte désormais en
commentaire, dans sa section `[irreversible]`, la ligne `tools` qui la
lui laisse : la liste des outils externes du moteur, moins la fusion.
L'humain seul l'active, en la décommentant ; le guide (« La fusion par
l'agent ») dit à quelles conditions l'agent fusionne alors sa propre
pull request, et ce qu'il vérifie ensuite. Le hook ne change pas : sans
la ligne, la fusion reste refusée. La politique d'un projet installé ne
se réécrit pas ; à cette mise à jour, le diff de la politique montre la
ligne.

À faire : rien, sauf si l'humain veut que l'agent fusionne lui-même sa
pull request. Il écrit alors lui-même cette ligne dans la section
`[irreversible]` de `.socle/policy.toml`, et l'approuve comme tout
changement protégé ; l'agent ne l'écrit pas, il peut la lui donner :

```toml
tools = ['mcp__github__(delete_file|create_repository|fork_repository|create_release|push_files|create_or_update_file|enable_pr_auto_merge)']
```

Un projet qui a déjà écrit cette ligne n'a rien à faire.

## 2026-11-20-p — Supprimer la branche distante ne remet plus à neuf la plage d'un push

Le hook avant push juge la plage qui part depuis le commit distant ; une
branche absente en face se jugeait contre la branche par défaut, où un
test que seule la branche a ajouté n'a pas de valeur antérieure. Supprimer
la branche distante laissait donc réécrire ce qui y avait été poussé. Le
hook garde désormais, quand il laisse passer un push, le commit poussé
vers chaque référence distante, dans `.git/socle/pushed.json` (le
répertoire git commun des worktrees, non versionné) ; une branche
distante disparue dont ce commit n'est pas dans la branche par défaut se
juge depuis lui, et le refus dit que supprimer la branche n'est pas une
issue. Une branche fusionnée par un commit de fusion, repartie de la
branche par défaut sous le même nom, se juge comme une branche neuve ;
après une fusion par écrasement (squash) ou par rebase, le commit gardé
reste hors de la branche par défaut, et la branche repartie sous le même
nom se juge depuis lui : plus strict, jamais moins ; la sortie est un
autre nom de branche. Un clone qui n'a rien poussé depuis la mise à jour
se juge comme avant.

À faire : rien.

## 2026-11-20-o — Le dossier de la revue d'une branche qui a fusionné la branche par défaut ne montre que le lot

Une branche déjà poussée qui fusionnait la branche par défaut en cours
de lot donnait au relecteur, avec le lot, le code et les entrées closes
que la fusion apportait. `socle review` mesure désormais le diff et les
sujets du lot depuis la fusion refaite sur son début (`git merge-tree
--write-tree`, git 2.38), et une note le dit ; le diff d'une seconde
revue (`--since`) aussi, et ses messages ne gardent que les commits de
la branche. Une fusion qui ne se
refait pas sans conflit, ou un git plus ancien, laisse le dossier
d'avant, et la note dit qu'il montre aussi ce que la fusion a apporté.

À faire : rien.

## 2026-11-20-n — Le résumé de la CI d'une pull request donne le lien d'une demande posée sur sa branche

Sur une pull request, la CI tourne sur une HEAD détachée, le commit de
fusion que GitHub prépare ; le lien d'une demande y visait la branche
par défaut, où une demande posée sur la branche n'est pas encore : le
résumé de l'exécution (`socle roadmap --format markdown`) la donnait sans
lien. Quand `GITHUB_HEAD_REF` est là, le lien vise désormais, pour le dépôt
que la CI a extrait (`GITHUB_WORKSPACE`), la tête de la pull request, le second parent du commit de fusion.

À faire : rien.

## 2026-11-20-m — `socle renumber` répare une collision née d'un rebase

Après un rebase ou un cherry-pick, deux entrées portaient le même
identifiant : `socle renumber` refusait (« existait avant la branche »),
ou renumérotait les deux, avec les mentions de celle qui était déjà là.
Il renumérote désormais celle qu'ajoute la branche, celle qui manque à
la base ou au dernier commit poussé, et ne change que les lignes que la
branche a ajoutées : l'autre entrée et ses mentions restent telles
quelles.

À faire : rien.

## 2026-11-20-l — `socle new` ne reprend pas un identifiant qu'un correctif suivi du dépôt crée

Une passation range en correctifs (`git format-patch`) les commits pas
encore relus ; une entrée écrite avant leur application prenait le
numéro d'une entrée qu'ils créent, et le correctif appliqué en
définissait deux. Le calcul d'un identifiant (`socle new`, une
demande, `socle renumber`) saute désormais les titres
d'entrée qu'un correctif suivi du dépôt (`*.patch`, `*.diff`) ajoute à
un fichier de la mémoire.

À faire : rien.

## 2026-11-20-k — Un titre qui finit par un dièse collé à un mot le garde

Le lecteur de la mémoire retirait tout dièse en fin de titre : une
entrée intitulée « … dans un projet C# » se lisait « … dans un projet
C ». Seule une fermeture précédée d'une espace (`## Titre ##`) se
retire désormais, comme en Markdown. Les empreintes des entrées ne
changent pas : elles se calculent sur le texte brut ; celle d'un index
change si l'un de ses titres finit ainsi.

À faire : rien ; une citation d'index que ce changement périme se
refuse avec la commande qui la relit.

## 2026-11-20-j — Une forme du shell que le hook ne juge pas ne se liste ni ne se signale plus : le guide garde le modèle de menace du hook

Le skill `socle-review`, la consigne du relecteur de `socle review` et
la section du socle d'`AGENTS.md` ne disent plus la forme du shell qu'un
agent n'écrit pas : la revue ne la cherche pas, et une forme trouvée
s'écarte comme tout constat exotique, sans ligne qui la nomme au récap ni
signalement au dépôt du socle. Le guide (`python3 .socle/socle help`)
perd la liste des formes connues que le hook ne juge pas et les phrases
qui disaient quand un trou du hook ouvre une entrée du backlog ; il garde
ce que juge le hook, ce qu'il refuse de ne pas savoir lire, et ce qu'il
ne modélise pas, que rattrape le contrôle des fichiers protégés.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur, et la section du socle d'`AGENTS.md` se
régénère avec la mise à jour. Une forme déjà nommée dans un récap ne se
signale pas.

## 2026-11-20-i — Le skill `socle-review` fait demander à l'humain s'il veut Fable pour le relecteur d'un lot implémenté sur Fable

Un lot que l'humain a fait implémenter sur Fable (le lot, pas la session
qui orchestre) : l'agent lui demande, avant la revue, s'il veut aussi
Fable pour le relecteur. Hors de ce cas, la règle ne change pas : le
modèle le plus capable jusqu'à Opus, jamais un moindre que celui qui a
implémenté, et Fable seulement si l'humain le demande.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-20-h — Le skill `socle-batch` situe le réveil en session cloud, forme en jalon ce qu'une session ne mène pas, renvoie au tri de `socle-review` et donne aux sous-agents la ligne « Économie »

Le skill `socle-batch` change en cinq points :

- une attente annoncée a son réveil en session cloud (`send_later`), le
  seul lieu où l'outil existe ; ailleurs, la ligne `Ensuite :` du récap
  la dit, et l'humain relance l'agent ;
- un ensemble qu'une session ne mène pas se forme en jalon, ses lots
  dessous ;
- les constats de la revue qui ne bloquent pas suivent le tri de
  `socle-review`, au backlog ou écartés, au lieu d'aller tous au
  backlog ;
- la consigne des sous-agents porte la ligne « Économie : lire ce qui
  sert, pas les fichiers entiers ; pas de suite complète relancée sans
  raison » ;
- un sous-agent ne reçoit jamais Fable, sauf si l'humain le veut.

À faire : rien ; le skill `socle-batch` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-20-g — Un test changé sous sa demande en attente se commite et se pousse, la CI du socle exigée

Un test supprimé, ou dont la valeur attendue change, ou un cas d'un
fichier de cas déclaré, qu'une demande en attente nomme ne quittait pas
l'arbre de l'agent : `tests.attendus` ne le tolérait qu'à la fin du tour.
Il se tolère désormais comme un fichier protégé sous sa demande en
attente : si la branche par défaut exige la CI du socle avant toute
fusion, il se commite et se pousse dès que la demande qui le nomme est
poussée telle quelle, et la CI le refuse jusqu'à la réponse de l'humain,
qui le lit dans la pull request. Sans cette protection, rien ne change :
le commit et la CI attendent la réponse. Un commit sans demande poussée
reste refusé.

À faire : rien.

## 2026-11-20-f — Le relecteur à froid d'une demande reçoit le modèle le plus capable jusqu'à Opus, à son lancement

Le skill `socle-request` faisait relire une demande à froid par un
sous-agent du modèle de la session, que la règle du modèle de
`socle-batch` peut faire moins coûteux. Comme le relecteur d'un lot, il
reçoit désormais explicitement à son lancement (`model`) le modèle le
plus capable disponible jusqu'à Opus, quel que soit celui de la session,
sur la dernière version de sa famille ; Fable seulement si l'humain le
demande. Le récap nomme le modèle : `Relecture à froid (<modèle>) : …`.

À faire : rien ; le skill `socle-request` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-20-e — `socle decision --unprompted` consigne une décision que l'humain donne sans qu'on la lui ait demandée

`socle decision` exigeait une réponse de base ou une option nommée par la
question : une décision que l'humain donnait de lui-même se consignait
sous `valider`, avec une « question posée » inventée. `socle decision "<la
décision en une phrase>" --unprompted --relayed --by <nom> --quote-file
<fichier>` l'écrit sans question ni réponse à choisir : son texte exact
sous la section `Décision donnée`, et la réponse `valider` que le moteur
pose, son texte cité. Elle autorise ce qu'elle nomme comme une demande
validée. Le titre ne cite pas seul un identifiant que le texte de
l'humain ne cite pas. Le skill `socle-request` et le guide le disent.

À faire : rien ; le skill `socle-request` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-20-d — L'état et le rappel de fin de tour avertissent d'un lot ouvert qui attend plus de tâches qu'une session n'en mène

Un lot ouvert qui attend encore plus de tâches ouvertes, en cours ou
bloquées que `[batches] max_tasks` des garde-fous, 9 par défaut, se dit
dans l'état, avec ce qui demande d'agir, et dans le rappel de fin de
tour, sous l'ordre du backlog : une ligne nomme chaque lot et son
compte, et dit de le couper en lots, ou d'en faire un jalon et de
former ses lots dessous. Un avertissement, jamais un échec. Le seuil se
règle comme `[verify] fast_max_seconds` : le baisser est libre, le
relever exige une demande validée.

À faire : rien ; la clé, que l'installeur nomme à la mise à jour, se
déclare au besoin dans `.socle/guardrails.toml`. Un lot que l'état
signale se coupe à sa prochaine annonce.
## 2026-11-20-c — Le recul n'est plus exigé : `socle review` écrit les passes d'un lot et le contrôle du backlog le laisse se clore sans lui

`socle review` écrit chaque passe d'un lot dans sa section « Revues »
sans exiger le recul de la précédente : ni paragraphe « Recul : », ni
regard du relecteur sur les bloquants (`· même cause`, `· cause
nouvelle`), ni arrêt sur une demande qui cite le lot. Le contrôle
`memoire.backlog` laisse se clore `fait` un lot relu sans recul. Le
dossier d'une passe au-delà de la première est celui de toute passe : il
ne donne plus au relecteur les causes des passes d'avant. La section
« Revues » garde ses passes, leurs commits et leurs lignes `- Bloquant :`
et `- Ouvre :` ; une ligne de bloquant écrite sous une autre forme reste
refusée. Un recul et des marques de cause déjà écrits restent dans le
lot, lus comme du texte. Les skills `socle-review` et `socle-batch` et le
guide ne disent plus le recul.

À faire : rien ; les skills `socle-review` et `socle-batch` sont des
copies protégées, dans la demande de l'installeur. Un lot arrêté sur une
demande ne l'attend plus que si son `après` la nomme.

## 2026-11-20-b — L'installeur fait ignorer par git les worktrees des sous-agents

Le skill `socle-batch` lance ses sous-agents dans des worktrees, que
Claude Code pose sous `.claude/worktrees/` ; non ignorés, ils paraissent
dans `git status` comme des fichiers à commiter. L'installeur ajoute
`/.claude/worktrees/` au `.gitignore` du projet, sous un commentaire qui
le dit, sauf si une ligne l'y ignore déjà, lui ou `.claude/`.

À faire : rien ; la ligne arrive avec la mise à jour, à commiter avec
elle.

## 2026-11-20-a — Le hook de l'agent laisse remettre un fichier protégé dont une demande ne cite le dossier que dans un texte recopié

Le hook de l'agent refusait de remettre à son état du dernier commit un
fichier protégé qu'aucune demande n'approuve, quand une demande en
attente, ou validée sans sa réponse commitée, citait son dossier dans un
texte recopié entre accents graves : une valeur attendue d'un test, une
ligne de sortie (`skills du socle posés dans .claude/skills : …`). Un
dossier qui n'est qu'un mot d'un tel texte, entre accents graves ou dans
un bloc de code, n'y est plus une citation. Le fichier nommé en toutes
lettres, et son dossier cité dans la prose ou seul entre ses accents
graves (`.claude/skills/`), l'épargnent toujours.

À faire : rien.

## 2026-11-19-t — Le hook de l'agent lit la branche courante dans `git push origin "$(git branch --show-current)"`

Le hook de l'agent développe en la branche courante trois substitutions
d'un `git push`, `$(git branch --show-current)`, `$(git rev-parse
--abbrev-ref HEAD)` et `$(git symbolic-ref --short HEAD)`, nues, entre
guillemets, entre accents graves ou passées par une variable (`B=$(git
branch --show-current); git push -u origin "$B"`), et juge le push
comme si la branche était écrite en toutes lettres : il passe depuis une
branche de travail, et il est refusé depuis la branche par défaut. Elles
étaient refusées, comme tout argument qu'il ne sait pas développer.
Quand la même commande change de dossier, de dépôt ou de branche avant
le push (`cd` ailleurs, `git -C`, `git checkout`, `git switch`), ou pour
toute autre substitution (`$(echo main)`), le push reste refusé.

À faire : rien.

## 2026-11-19-s — Le hook de l'agent juge les filtres d'un `find` par leur conjonction, et le `-path` sous ses départs

Le hook de l'agent juge l'expression d'un `find` qui supprime ou écrit
ce qu'il trouve par la conjonction de ses filtres : un fichier protégé
n'est visé que s'il répond à chaque filtre d'une même conjonction, et
le motif d'un `-path` ne vise que ce qui est sous les départs du `find`.
`find . -name '*.json' -path './build/*' -delete` et `find build -path
'*.toml' -delete` passent ; ils étaient refusés, chaque filtre jugé seul,
et l'étoile de tête d'un `-path` lue depuis la racine du projet. Ce
qu'une conjonction atteint reste refusé (`find . -name '*.json' -path
'./.claude/*' -delete`, `find . -path '*.toml' -delete`).

À faire : rien.

## 2026-11-19-r — Le hook de l'agent juge `find … | xargs rm` comme un `find` qui supprime depuis ses départs

Le hook de l'agent juge un `xargs` d'un programme qui supprime ce qu'il
lit (`rm`, `mv`, `git worktree remove`…), derrière un `find` qui lui
donne sa liste, comme un `find` qui supprime depuis ses départs : `find
.. -maxdepth 0 | xargs rm -rf` est refusé comme la suppression d'un
dossier qui contient le projet, et `find . -type f | xargs rm -f` comme
celle du projet. Ils passaient : `xargs` ne se jugeait que par les
chemins protégés que la commande cite. Ce que le `find` écrit sur sa
sortie se garde par ses `-print` ou `-print0`, ou à défaut par son
expression entière. Un nettoyage sous le projet (`find . -name '*.pyc'
| xargs rm -f`, `find build -type f | xargs rm -f`) passe toujours. Le
guide ne dit plus que cette suppression échappe au hook, et la ligne de
`xargs git worktree remove` de la liste des formes connues dit son
exception, derrière un `find`.

À faire : rien.

## 2026-11-19-q — Le hook de l'agent juge les arguments qui suivent le script d'un `python -c`

Le hook de l'agent juge les arguments qui suivent le script d'un `python
-c`, et ceux qui suivent le `-` d'un script que python lit sur son
entrée, comme les chemins que le script cite en toutes lettres :
`python3 -c "import sys; open(sys.argv[1], 'w')" .socle/policy.toml` est
refusé. Il passait : seul le script se jugeait, et le chemin qu'il lit
dans `sys.argv` échappait au hook, jusqu'au fichier de réglages local de
Claude Code, que git ne suit pas. Un argument se développe avec les
variables connues de la commande (`F=…; python3 -c "…" "$F"`) ; celui
qu'il ne sait pas développer (`"$X"`, `$(…)`) se juge comme le chemin
inconnu qu'écrirait le shell, refusé s'il peut tomber dans le projet,
libre sous un dossier qui en est hors (`/tmp/$X`). Un `python -c` dont
les arguments ne nomment aucun fichier protégé passe, comme un script
qui ne lit pas ses arguments (ni `argv`, ni `argparse`, `fileinput`,
`optparse` ou `getopt`), qui ne les touche pas ; la liste des formes
connues que le hook ne juge pas inscrit celui qui les lirait autrement
(`runpy`, l'`exec` d'un autre script).

À faire : rien.

## 2026-11-19-p — Le hook de l'agent juge le script qu'un heredoc donne à python

Le hook de l'agent juge le corps d'un heredoc que lit sur son entrée un
`python` ou un `python3` lancé sans `-c`, sans `-m` et sans script, ou
avec `-` pour script, comme le script d'un `python -c` : `python3 -
<<'EOF'` dont le corps écrit `.socle/policy.toml`, ou passe `..` à
`shutil.rmtree`, est refusé. Il passait : le corps d'un heredoc n'était
que du texte pour le découpage. Le corps se lit tel qu'écrit, sans
développer ses variables, ses tabulations de tête retirées pour `<<-`,
et la dernière redirection de l'entrée l'emporte. Un script qui ne cite
aucun fichier protégé et ne supprime rien du projet passe ; un heredoc
donné à un autre programme (`cat > notes.txt <<'EOF'`) et un script que
python lit d'un fichier (`python3 script.py`, `python3 - < script.py`)
ne changent pas de jugement. Deux formes voisines, qu'aucun agent
n'écrit dans son travail, s'inscrivent dans la liste des formes connues
que le hook ne juge pas : le heredoc d'une substitution, et le corps
d'un heredoc donné à un autre interpréteur que python.

À faire : rien.

## 2026-11-19-o — Le hook de l'agent refuse un ancien numéro repris dans une ligne neuve, même d'un fichier qui le cite déjà

Le hook de l'agent refuse l'ancien numéro d'une entrée renumérotée dans
un texte neuf ; il sautait toute mention que le fichier portait déjà
avant l'écriture. Dans le journal du mois de la migration, qui cite
presque tous les anciens numéros, une entrée neuve qui en reprenait un
passait. Il juge désormais les lignes que l'écriture ajoute ou change :
une ligne neuve qui reprend l'ancien numéro sans l'identifiant actuel
est refusée, même si le fichier le cite déjà, et une ligne d'avant
gardée telle quelle passe, même si l'écriture change ce qui l'entoure.
La ligne qui nomme aussi l'identifiant actuel (« ancien → actuel ») passe
toujours, comme, sur une ligne de métadonnées, l'ancien numéro qu'elle
portait déjà : le champ `ancien` d'une entrée renumérotée qu'on clôt, la
source d'une décision dont le statut change.

À faire : si le hook refuse un ancien numéro dans une entrée neuve du
journal, citer l'identifiant actuel qu'il nomme.

## 2026-11-19-n — Le hook de l'agent juge la commande que lance une substitution entre guillemets

Le hook de l'agent juge la commande que lance une substitution entre
guillemets, `"$(…)"` ou des accents graves, comme celle d'une
substitution nue, avec les fonctions que la commande a définies :
`x="$(cd memory && rm -rf ../..)"`, `echo "$(rm -rf ..)"` ou
`echo "$(git push --force origin main)"` sont refusés comme sans
guillemets. Ils passaient : le texte d'une substitution entre guillemets
ne se jugeait jamais. Une substitution ordinaire (`x="$(git rev-parse
HEAD)"`), un calcul `"$((…))"` et un message de commit écrit par
`"$(cat <<'EOF' … EOF)"`, dont le corps n'est que du texte, passent
toujours.

À faire : rien.

## 2026-11-19-m — Le hook de l'agent juge un `git push` sur ses arguments développés, et refuse un argument qu'il ne sait pas développer

Le hook de l'agent lisait l'argv d'un `git push` tel qu'il est écrit : un
push forcé ou vers la branche par défaut passait quand son option ou sa
branche venait d'une variable (`F=--force; git push $F origin x`,
`B=main; git push origin "$B"`), des arguments d'une fonction (`f() { git
push "$@"; }; f --force origin x`) ou d'une substitution. Il juge
désormais l'argv d'un `git` développé avec les variables connues, comme
il juge un chemin, et refuse un `git push` dont un argument ne se
développe pas : une variable qu'il ne connaît pas, une substitution
(`git push origin "$(git branch --show-current)"`), les arguments d'une
fonction. Une branche écrite en toutes lettres, ou dans une variable
affectée plus tôt dans la même commande, passe comme avant. Une option
globale de git dont la valeur entre guillemets porte une variable et une
espace (`git -c http.extraheader="AUTHORIZATION: bearer $TOKEN" push …`)
ne cache pas le push : il se juge sur l'argv coupé en mots et sur l'argv
entier.

Deux formes voisines, qu'aucun agent n'écrit, s'inscrivent dans la liste
des formes connues que le hook ne juge pas : l'option qui saute les hooks
passée par une variable, que la CI rattrape, et une sous-commande de git
venue d'une variable.

À faire : si le hook refuse un push de la branche de travail, écrire sa
branche en toutes lettres.

## 2026-11-19-l — Le hook de l'agent juge la commande que lancent `uv run` et `poetry run`

Le hook de l'agent retire `uv run` et `poetry run`, avec leurs options
avant `run` comme après (`uv run --with x -p 3.12 --`, `poetry -C . run
-n`), comme il retire `env` ou `sudo`, et juge la commande qu'ils
lancent comme sans eux : `uv run rm -rf ..`, `poetry run git push
--force origin main` et un `uv run python -c` qui écrit un fichier
protégé sont refusés comme sans ce préfixe. Ils passaient : le hook lisait
le programme `uv` ou `poetry`. Les commandes ordinaires qu'ils lancent
(`uv run pytest`, `uv run -m pytest`, `poetry run pytest`) passent
toujours. Le guide inscrit deux formes connues que le hook ne juge pas :
la commande que lance `uv run --directory` ou `poetry -C` se lit dans le
dossier courant, non dans celui qu'ils nomment, et la valeur d'une option
qu'il ne connaît pas (`uv run --python-preference managed …`) se lit
comme la commande lancée.

À faire : rien.

## 2026-11-19-k — La passe de revue se commite, et le refus de la clôture d'un lot relu montre l'historique, ce que git donne et les trois questions

Le skill `socle-review` dit de commiter la passe que `socle review` écrit
dans la section « Revues » du lot, avec ce que l'agent y consigne :
écrite sans commit là où la commande a tourné, elle se perdait, et la
passe suivante récrivait « Passe 1 » sans recul exigé. Et quand le
contrôle du backlog refuse la clôture « fait » d'un lot relu, son refus
montre désormais, sous la raison, ce que montre le refus d'une passe :
l'historique du lot, les entrées ouvertes et closes depuis le début de
sa première passe et les lots clos qui ont touché les mêmes fichiers,
puis les trois questions du recul et ce qu'il faut écrire. Le rapport
d'un contrôle imprime ce détail en retrait ; la fin de tour n'en garde
que la raison.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-j — La même passe de revue se reconnaît sur un arbre sale, et une ligne de bloquant mal écrite est refusée

`socle review` juge l'arbre de travail, fichiers suivis modifiés
compris, mais la passe qu'il écrit dans la section « Revues » du lot ne
gardait que ses commits : relancé sur un arbre sale inchangé, il prenait
la même passe pour une nouvelle, refusée sans recul, et sa ligne disait
`Commits : X..X` quand rien n'était commité. La passe garde désormais, au
bout de cette ligne, l'empreinte des changements de l'arbre qu'elle a
relus (`Commits : <début>..<tête> + arbre de travail <empreinte>`), et la
même passe se redonne tant que ni la tête ni ces changements ne bougent,
commités ensuite ou non. Et une ligne de la section « Revues » qui se
donne pour un bloquant sous une autre forme que `- Bloquant : <sa cause>`
(`- **Bloquant** : …`, `- Bloquant 1 : …`, `1. Bloquant : …`,
`- Bloquants : …`, ou sans puce, `Bloquant : …`, `Bloquant 2 — …`), que rien ne lisait, est refusée par le contrôle du
backlog, à tout statut du lot.

À faire : si le contrôle `memoire.backlog` refuse une telle ligne dans un
lot, la récrire `- Bloquant : <sa cause>`, une ligne par bloquant.

## 2026-11-19-i — Le dossier de la revue donne aussi les décisions et les demandes que citent celles que le lot écrit

Le dossier de `socle review` donnait les décisions et les demandes que le
lot écrit, puis celles que citent ses entrées du backlog. Il donne
désormais aussi, une fois chacune, celles que citent les décisions que
le lot écrit : la spécification validée qu'une décision du lot applique
arrive au relecteur, qui jugeait sans elle. Le skill `socle-review` le
dit.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-h — Un fichier privé qu'approuve une décision de séance ne se donne jamais au dossier de la revue, quelle que soit l'écriture de son chemin

Le dossier de la revue jugeait privé le fichier qu'approuve une décision
de séance sur le chemin écrit dans son champ `sujet` : écrit
`./memory/private/…`, ou par un détour en `..`, un fichier de la mémoire
privée passait pour public et se donnait au relecteur. Il se juge
désormais sur son chemin normalisé dans le dépôt.

À faire : rien.

## 2026-11-19-g — Une case d'une tâche qui livre une demande, un relevé ou une entrée de la mémoire se vérifie par ce qu'elle produit

Le format de la mémoire disait que le « Fait quand » d'une tâche se
vérifie par des tests, sauf une action que seul l'humain peut faire. Il
dit désormais, case par case, une autre exception : une case dont le
livrable est une demande posée, un relevé écrit (le compte rendu d'une
mesure ou d'un essai) ou une entrée de la mémoire récrite se vérifie par
ce qu'elle produit, que la case nomme : la demande et la réponse de
l'humain consignée au journal, le fichier du relevé, ce qu'en montre
`socle show` ou `socle roadmap`. Tout autre livrable garde son test. La
consigne du relecteur, dans le dossier complet comme dans le dossier
court, dit de juger une telle case par ce produit, et non par l'absence
d'un test.

À faire : rien ; une tâche de cette forme peut nommer ce produit dans sa
case.

## 2026-11-19-f — Le relecteur d'une revue reçoit le chemin du dossier, pas son texte

Le skill `socle-review` fait écrire la sortie de `socle review` dans un
fichier hors du dépôt, et ne donner au relecteur que son chemin, avec la
consigne de le lire en entier et de le suivre tel quel. Recopié comme
message du relecteur, le dossier restait dans la conversation qui
orchestre, relue à chaque pas : plusieurs dizaines de milliers d'octets
par passe. Ce que le relecteur lit ne change pas.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-e — Le dossier de la revue donne le fichier qu'approuve une décision de séance que citent les tâches du lot

Une décision prise en séance peut désigner ce qu'elle approuve, un
fichier du dépôt (`socle decision --about <chemin>`, son champ `sujet`).
Quand les entrées que sert un lot citent une telle décision, `socle
review` donne désormais au relecteur le texte de ce fichier tel qu'il
était au début du lot, et dit si le lot le change, à la suite
des décisions citées ; le dossier court (`--short`) le donne aussi,
après les critères. Au-delà de 20 000 octets, le dossier ne donne que
son chemin, que le relecteur lit dans le dépôt. Un fichier privé, ou
hors du dépôt, ne se donne pas.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-d — `socle review --short`, le dossier court d'un petit lot ; le skill de la revue dit quand le donner

`socle review --short` donne au relecteur d'un petit lot un dossier
court : la consigne de juger le diff et les fichiers qu'il touche, sans
explorer au-delà, le diff du lot et les critères des tâches qu'il sert,
sans le reste de leurs entrées ni les décisions qu'elles citent. Il
refuse, en le disant, un lot qui touche un garde-fou : la politique ou
les garde-fous eux-mêmes, un chemin que la politique protège, ou un
chemin que les garde-fous déclarent comme l'outillage (`[tooling]
paths`) ; `socle review` sans l'option donne alors le dossier complet.
Le skill `socle-review` dit quand donner le dossier court : un lot de
moins de 150 lignes de code et de tests qui ne touche ni un garde-fou ni
un format que d'autres parties du projet lisent ; tout autre lot reçoit
le dossier complet. Le skill est resserré ailleurs, sans règle en moins,
pour tenir dans son budget.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-c — La fin de tour en échec ne recopie plus la sortie des tests : le nom de chaque contrôle, la ligne de chaque test en échec et la commande qui montre tout

Quand des contrôles échouent en fin de tour, le hook recopiait le
rapport entier, contrôles qui passent et sortie des outils compris :
des milliers de jetons, relus à chaque étape suivante de la
conversation. Il ne donne plus que l'essentiel : chaque contrôle en
échec ou qui avertit, avec la première ligne utile de chacun de ses
constats (ni vide ni de décor) ; pour une étape de l'adaptateur, sa
commande, son code et la ligne de chaque test en échec, celles où un mot
d'échec (`FAIL`, `FAILED`, `ERROR`, `échec`…) ouvre ou ferme la ligne,
dix au plus, ou à défaut la dernière ligne utile de la sortie ; les
contrôles indisponibles, nommés sur une ligne. Il finit par la commande
qui montre tout : `python3 .socle/socle check --stage agent` pour les
contrôles du socle, `python3 .socle/socle verify --fast` pour les étapes
de l'adaptateur. Le blocage, le compteur, l'escalade et la relance sur un
échec inchangé ne changent pas.

À faire : rien dans le projet ; pour le détail d'un échec, lancer la
commande que le message donne.

## 2026-11-19-b — Le skill socle-request : un contenu validé en séance s'écrit d'abord dans le dépôt ; la variante légère des valeurs attendues mécaniques

Un contenu montré dans la conversation que l'humain valide (un format, un
exemple, un texte) s'écrit désormais tel quel dans le dépôt avant que la
décision de séance se consigne : elle le désigne (`socle decision
--about <chemin>`), et les tâches qui en découlent citent ce chemin. Sans
lui, la décision ne gardait que la question et la réponse, et un lot
pouvait construire sur un souvenir du contenu.

Des valeurs attendues changées mécaniquement, des tests qui lisent un
format que l'humain vient de valider, se valident par une question dans
la conversation qui nomme chaque test, avec sa valeur avant et après ; la
réponse se consigne mot pour mot en décision de séance, dont le texte
nomme les tests, et se commite avec eux. Tout autre changement de valeur
attendue, ou suppression d'un test, garde la demande écrite.

À faire : rien ; le skill `socle-request` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-19-a — Le skill socle-batch : une petite tâche se fait sans sous-agent, et le coût d'un lot s'estime sur des mesures

Une petite tâche, moins de 150 lignes de code et de tests (un seuil
provisoire, revu sur les coûts mesurés), s'implémente dans la session
qui orchestre, sauf si elle touche un garde-fou ou un format que
d'autres parties du projet lisent : le coût fixe d'un sous-agent, qui
relit instructions et code avant d'écrire, dépassait ce qu'il épargne.

Les seuils fixes de la consommation deviennent une règle sur des coûts
mesurés. La clôture d'un lot note au journal ce qu'ont coûté chaque
sous-agent, le relecteur, chaque demande et le rangement. Un sous-agent
se lance si ce qui reste de chaque fenêtre couvre son coût mesuré et
celui du rangement ; sans mesure, les anciens seuils valent (aucun
au-delà de 85 % de la semaine ou de 60 % de la fenêtre de cinq heures).
Le rangement commence au plus tard à dix points d'une limite. À
l'annonce, le coût du lot s'estime sur ces mesures : s'il ne tient pas
dans ce qui reste de la fenêtre, le lot se découpe, commence plus petit
ou attend la remise à zéro.

À faire : rien ; le skill `socle-batch` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-18-d — L'état ne donne plus à supprimer une branche que l'origine n'a plus

Le clone garde la référence d'une branche supprimée sur l'origine tant
qu'un fetch ne l'élague pas, et l'état la donnait à supprimer, ou à
examiner, à l'humain, qui l'avait déjà supprimée. Quand il a une branche
distante à proposer, l'état demande désormais à l'origine celles qu'elle
a encore (`git ls-remote --heads origin`, en cinq secondes au plus) et
ne propose que celles-là. Quand l'origine ne répond pas, il les propose
comme avant, en disant que sa liste vient du dernier fetch et que `git
fetch --prune origin` la rafraîchit.

À faire : rien dans le projet.

## 2026-11-18-c — La suite du projet aux formats validés : le compact en colonnes, le détaillé en tableaux, dans l'ordre d'exécution ; le récap ne se lit plus dans un bloc de code

`socle roadmap` change de rendu, pas de contenu ni d'options. Le format
compact aligne en colonnes, comptées en caractères, les lots strictement
dans leur ordre d'exécution, chacun avec ses tâches closes sur le total,
le lot en cours marqué ▶. L'en-tête d'un jalon et de ses besoins clos
sur le total revient chaque fois que le jalon change d'un lot au
suivant ; « Hors des jalons » coiffe de même, à leur place, les lots qui
n'en servent aucun. Le lot en cours et les deux suivants, de quelque
jalon qu'ils soient, ont chacun leur ligne ; au-delà, chaque suite de
lots d'un même jalon tient en une ligne, un lot seul garde la sienne, et
`--all` déplie tout. Il n'a plus de ligne d'en-tête, et finit par deux
lignes : « Hors lot : », les comptes non nuls et les bloqués nommés, et
« Ensuite : », les jalons sans lot avec leurs premiers besoins ouverts,
puis les besoins d'aucun jalon. Il ne nomme toujours aucune demande. Le
format détaillé (`--format markdown`) garde son titre et sa phrase, puis
donne une légende des symboles ; dans le même ordre, sous les mêmes
en-têtes, chaque lot de la fenêtre a sa ligne (son rang dans l'ordre
d'exécution, son titre, son état s'il est en cours ou arrêté, les
demandes qu'il attend, ses tâches closes sur le total) et un tableau
d'une ligne par tâche : son état et sa priorité en symboles (✓ faite,
▶ en cours, ○ prête, ⏳ attend, ✗ bloquée, ⊘ abandonnée ; ↑ haute,
↓ basse), son identifiant, son besoin, son titre jusqu'à son premier
deux-points, et ce qu'elle attend ; chaque autre lot, une ligne
numérotée. Lu par besoin (`--by need`), les besoins viennent dans
l'ordre de leurs lots, chacun avec le tableau de ses tâches et le lot de
chacune. Ce qui est hors des lots garde ses sections, chacune en tableau.
Le guide montre les deux formats.

Le hook de fin de tour ne cherche plus les deux lignes du récap,
« Pour toi : » et « Ensuite : », ni les motifs que la politique donne à
leur place (`[human] recap_markers`), dans un bloc de code délimité par
trois accents graves ou trois tildes ; un bloc jamais fermé court
jusqu'à la fin du message. Une sortie collée dans un bloc, comme ce
compact, qui finit par sa propre ligne « Ensuite : », ne tient plus lieu
de récap ; le skill `socle-batch` dit désormais de coller le compact
dans un bloc de code au récap de la clôture d'un lot.

À faire : rien dans le projet. L'agent écrit ses deux lignes en texte,
jamais dans un bloc de code ; le refus du hook le lui rappelle. Le résumé
de la CI et le récap de la clôture d'un lot prennent le nouveau rendu
d'eux-mêmes ; un texte du projet qui citait l'ancien mot pour mot est à
revoir.

## 2026-11-18-b — Le dossier de la revue, son skill et les questions disent tâche, besoin ou entrée, jamais « sujet »

Les derniers textes du produit qui disaient « sujet » d'une entrée du
backlog, et que des tests lisent mot pour mot, suivent les quatre formes
du backlog. Le dossier de `socle review` donne au relecteur « les entrées
du backlog que sert le lot », dont les critères (« Fait quand » d'une
tâche, « Satisfait quand » d'un besoin) sont sa barre, « les entrées que le
lot ouvre », et les décisions « qu'elles citent » ; le skill
`socle-review` le décrit ainsi. La question de départ sur la livraison
propose « une pull request par tâche ». Le gabarit des questions de
cadrage (`socle new request --questions`) parle du besoin à spécifier. Le
guide dit qu'un trou du hook ouvre « une entrée du backlog ».

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-18-a — La durée des étapes se dit, et celle des étapes rapides a un seuil

`verify`, `verify --fast` et `socle ci` impriment désormais la durée de
chaque étape de l'adaptateur qu'ils lancent, au bout de sa ligne, puis
leur total. Une clé nouvelle des garde-fous, `[verify] fast_max_seconds`,
borne le total des étapes rapides : 300 secondes quand le projet ne
l'écrit pas, la valeur que pose le gabarit d'un projet neuf. Au-delà, le
passage qui les lance toutes avertit sans échouer, en nommant l'étape la
plus longue : `verify --fast` au bout de sa sortie ; le hook avant envoi
sur sa sortie d'erreur, sans refuser le push ; la fin de tour, sans
bloquer, dans son message à l'humain, et dans sa raison à l'agent quand
elle bloque déjà pour une autre. L'avertissement revient sur la ligne qui
dit les étapes déjà passées, et dans `socle state` au démarrage de chaque
session, tant que le dernier passage où toutes ont passé dépasse le
seuil. Sa trace est un fichier local,
`.socle/trace/duree-des-etapes-rapides`, que git ignore déjà. La CI
imprime les durées sans seuil. Le cliquet connaît la clé : la relever
exige une demande validée qui la cite, la baisser est libre. Pour toute
clé des garde-fous, il ne prend plus `nan`, qu'aucun ordre ne compare,
pour un durcissement : l'écrire à la place d'une valeur, ou l'y
remplacer, exige une demande validée.

À faire : rien d'obligatoire. La durée des étapes rapides du projet n'est
pas mesurée sur sa machine : `verify --fast --redo` la mesure ; si elle
dépasse cinq minutes, l'état le dira à chaque session, jusqu'à ce qu'elle
raccourcisse ou que l'humain relève le seuil. Écrire la clé à 300 dans
`.socle/guardrails.toml` est libre et ne change rien.

## 2026-11-17-f — La suite du projet dans l'état, les instructions, la clôture d'un lot et la CI

La suite (`socle roadmap`) se montre là où on la cherche. L'état a une
ligne qui renvoie à la commande. Les instructions du socle, dans
`AGENTS.md`, disent à l'agent de coller le format détaillé
(`--format markdown`) dans sa réponse quand l'humain demande la suite. Le
skill `socle-batch` fait coller le format compact dans le récap de la
clôture d'un lot. La CI posée écrit le format détaillé dans le résumé de
chaque exécution, lisible sur GitHub sans agent : une étape « Suite du
projet », avant la mémoire privée, dont rien n'y entre, et qui ne fait
pas échouer la CI si elle échoue. Le guide le dit en une phrase.

À faire : rien ; le workflow `.github/workflows/socle.yml` et le skill
`socle-batch` sont des copies protégées, dans la demande de
l'installeur, et la section du socle d'`AGENTS.md` est régénérée par la
mise à jour.

## 2026-11-17-e — La suite du projet d'un coup d'œil : `socle roadmap`

Une commande nouvelle, pour l'humain comme pour l'agent :
`python3 .socle/socle roadmap` donne la suite du projet, calculée depuis le
backlog comme l'état, rien d'écrit à la main. En compact (par défaut),
une ligne par jalon, avec ses besoins clos sur le total, et une ligne par
lot, dans leur ordre d'exécution déduit de leurs `après`, le lot en cours
marqué et l'avancement de ses tâches ; puis ce qui est hors des lots,
compté. `--format markdown` donne le format détaillé : le lot en cours et
les deux suivants tâche par tâche (chaque tâche avec son besoin, sa
priorité et où elle en est), les autres en une ligne (`--all` les
détaille tous), et, nommés, les tâches dans aucun lot, les besoins à
découper et à fermer, les entrées bloquées, celles `pour : humain` et les
demandes en attente avec leur lien. `--by need` lit par besoin, chacun
avec ses tâches et le lot de chacune ; `--by batch`, le défaut, par lot. Deux lots qui attendent un même lot
sans que l'un attende l'autre sont signalés : leur ordre n'est pas
déduit, il se choisit par un `après` de l'un vers l'autre.

À faire : rien.

## 2026-11-17-d — Les derniers textes du moteur qui disaient « sujet » d'une entrée du backlog

La description de `memoire.lectures`, que `socle checks` affiche, dit « une
entrée du backlog » ; l'aide de `socle review --since`, « les tâches du lot
entier » ; les libellés de l'auto-test (`socle selftest --verbose`), « besoin »,
et « commande en arrière-plan » au lieu de « tâche de fond ».

À faire : rien.

## 2026-11-17-c — La migration du backlog en quatre formes ne perd ni ne déplace plus de contenu

La migration du backlog, que la mise à jour fait une fois, corrige trois
cas. Une entrée close qui attendait un lot ou un jalon abandonné se
mettait à attendre les besoins encore ouverts de ce lot, ce que
`memoire.ordre` refusait ensuite : elle n'attend plus que ce qui est clos.
Un critère écrit sur plusieurs lignes passe entier dans la tâche posée, au
lieu de sa seule première ligne, la suite restant dans le besoin. Le titre,
les champs et les critères d'une tâche posée citent les identifiants
actuels, et non plus l'ancien numéro d'un lot ou d'un jalon.

À faire : rien dans un projet dont le backlog n'a pas encore migré. Dans
un projet déjà migré, relire les tâches posées par la migration : une
mention d'un ancien numéro se remplace par l'identifiant actuel que
`socle show` donne, et un critère coupé se complète depuis le besoin.

## 2026-11-17-b — L'ancien numéro d'une entrée renumérotée : le hook nomme l'identifiant actuel, et `socle url` le résout

Le hook de l'agent refusait l'ancien numéro d'une entrée renumérotée
(`ancien : B-NNNN`), écrit dans un texte neuf, en le disant inventé, alors
que les contrôles le résolvent ; `socle url` répondait « aucune entrée ».
Le hook le refuse désormais en nommant l'identifiant actuel de l'entrée,
que le texte neuf cite à la place, seul ou sur la ligne de l'ancien
(le bilan de la mise à jour, « ancien → actuel ») ; le journal qui le cite
déjà se complète sans refus ; `socle url` donne le lien de l'entrée qui le porte, et dit
son identifiant actuel.

À faire : rien ; un numéro repris du journal d'avant la migration se cite
par l'identifiant que le refus nomme.

## 2026-11-17-a — Une forme du shell que le hook ne juge pas se signale au dépôt du socle

Le skill `socle-review` disait d'inscrire une forme du shell qu'un agent
n'écrit pas, écartée par la revue d'un lot, dans la liste des formes
connues du guide. Dans un projet équipé, le guide est sous le moteur
installé, protégé : l'agent ne peut pas l'écrire. Le skill dit désormais
que le récap nomme la forme, et que « Pour toi » propose à l'humain de la
signaler au dépôt du socle (https://github.com/theodubus/socle), qui
tient la liste.

À faire : rien ; le skill `socle-review` est une copie protégée, dans la
demande de l'installeur.

## 2026-11-16-g — Un lot garde l'historique de ses revues, et s'arrête sur un recul écrit

`socle review` écrit désormais chaque passe de revue du lot en cours (ou
de celui que `--batch L-NNNN` nomme) dans la section `## Revues` de son
entrée : sa date et les commits relus. L'agent y consigne la cause de
chaque bloquant, et les entrées que la passe ouvre ; une session neuve lit
cet historique tel quel. À partir de la deuxième passe, le dossier donne
au relecteur les causes des bloquants d'avant, et lui fait dire, pour
chaque bloquant nouveau, s'il a la même cause que l'un d'eux. Avant toute
passe au-delà de la première, `socle review` exige le recul de la
précédente : un paragraphe qui commence par « Recul : », répond en
soixante mots au moins à trois questions de nature, et finit par
« continuer » ou par « s'arrêter ». Il le refuse sinon, en montrant
l'historique, les entrées ouvertes et closes depuis le début du lot, les
lots clos qui ont touché les mêmes fichiers et les trois questions. Il
refuse « continuer » après deux passes de suite où le relecteur voit une
même cause revenir, et toute passe tant que l'arrêt n'est pas levé : seule
le lève la réponse de l'humain à une demande que le recul nomme et qui
cite le lot, jamais une demande retirée, ni une ancienne, même répondue,
qui ne le cite pas. Le contrôle `memoire.backlog` applique les mêmes
règles à la dernière passe d'un lot relu clos `fait` : il le refuse sans
son recul, sans le regard du relecteur sur un bloquant, sur un
« continuer » après deux causes revenues, ou sur un arrêt que rien n'a
levé.

À faire : marquer `en cours` le lot qu'on mène, pour que ses passes s'y
écrivent ; au retour du relecteur, y consigner les bloquants ; écrire le
recul avant la passe suivante et avant la clôture ; s'arrêter, c'est
poser une demande à l'humain, qui cite le lot et dit ce qui tourne, la
règle qui le fait tourner et une proposition qui la borne. Les skills `socle-review` et
`socle-batch` le disent ; ce sont des copies protégées, dans la demande de
l'installeur.

## 2026-11-16-f — Le backlog en quatre formes, chacune son préfixe : besoin, tâche, lot et jalon

Une entrée du backlog a désormais l'une de quatre formes, que son préfixe
dit : un besoin (`B-`), un défaut à corriger ou une fonction à ajouter,
avec sa section « Satisfait quand », un résultat ; une tâche (`T-`), un
livrable qui nomme son besoin (`besoin : B-NNNN`), avec sa section « Fait
quand », qu'un test vérifie ; un lot (`L-`), les tâches menées et relues
ensemble ; un jalon (`JA-`), les besoins qui servent un même but. Le champ
`forme` disparaît. Chaque forme n'attend que ce qui lui revient : un lot,
ses tâches et le lot d'avant ; un jalon, ses besoins et le jalon d'avant.
Seule une tâche est prête ; elle prend la priorité de son besoin et attend
ce qu'il attend. Un besoin se ferme quand ses tâches sont closes, l'une au
moins faite. L'état dit le prochain jalon et ses besoins ouverts, le
prochain lot et ses tâches, les tâches prêtes, les besoins à découper et
ceux à fermer. Les commandes `socle new need`, `socle new task "…" --need
B-NNNN`, `socle new batch` et `socle new milestone` remplacent `socle new
backlog`, qui disparaît ; `socle new need "…" --task "…"` pose le besoin et
sa tâche. Un contrôle nouveau, `memoire.formes`, refuse de remélanger les
formes.

La mise à jour migre le backlog : chaque lot devient `L-` et chaque jalon
`JA-`, clos compris, en gardant son ancien numéro (`ancien : B-NNNN`), que
`socle show` et les contrôles des références résolvent, et sans sa
priorité : un lot ou un jalon n'était déjà jamais pris, elle ne changeait
aucun ordre, et `memoire.formes` la refuse désormais ; la mise à jour
nomme chaque entrée dont elle l'a retirée. Toute autre entrée reste un
besoin, sa section « Fait quand » renommée « Satisfait quand » ; chaque
besoin qu'attend un lot ouvert reçoit une tâche qui reprend ses critères,
vers laquelle sa section renvoie, et que le lot attend à sa place ; un
jalon attend les besoins de ses lots. Les mentions se récrivent dans le
backlog et le chantier actif ; le journal, les décisions et les demandes
gardent l'ancien numéro. Une citation par l'ancien numéro (`B-NNNN@…`) se
juge contre l'entrée renumérotée, comme celle de son identifiant actuel :
une empreinte périmée ou inventée y est refusée.

À faire : relire ce que la mise à jour a migré (`python3 .socle/socle
state`, le backlog), et commiter la migration avec elle. Puis, en prenant
chaque besoin : le découper en tâches s'il demande plusieurs livrables, et
récrire ses critères en résultats, ceux de ses tâches en livrables qu'un
test vérifie. Un constat de revue devient une tâche si sa correction est
claire, un besoin sinon. Les skills `socle-batch` et `socle-review` le
disent ; ce sont des copies protégées, dans la demande de l'installeur.
Le guide, la page publique et les gabarits des questions de cadrage et
de l'initialisation disent « besoin » là où ils disaient « sujet ».

## 2026-11-16-e — Le guide ne cite plus un identifiant de la mémoire du dépôt du socle

Le guide (`python3 .socle/socle help`), à « Approuver ses propres
changements protégés », citait un identifiant de la mémoire du dépôt qui
fabrique le socle, qu'un projet équipé ne connaît pas. Il ne le cite
plus ; un test garde le guide de tout identifiant de cette mémoire.

À faire : rien.

## 2026-11-16-d — Former un lot balaie tout le backlog ouvert, et un sujet ouvert rejoint aussitôt son lot

Le skill `socle-batch` dit désormais qu'en formant un lot, l'agent balaie
tout le backlog ouvert, pas seulement le prochain jalon : chaque sujet prêt
auquel la règle d'un lot s'applique (les mêmes fichiers, le même garde-fou
ou les mêmes tests) y entre, sans le demander à l'humain ; qu'un sujet
ouvert ensuite rejoint aussitôt le lot ouvert dont la règle s'applique à
lui, s'il est prêt, dans le prochain lot pas encore en cours, jamais dans
le lot en cours, où seuls les bloquants de sa revue se corrigent ; et qu'un
lot qui ne tient plus en une session se coupe en deux lots,
sur leurs fichiers. Le récap dit chaque placement ; la priorité reste à
l'humain.

À faire : rien de plus que de suivre le skill ; c'est une copie protégée,
dans la demande de l'installeur.

## 2026-11-16-c — Chaque modèle demandé tourne sur la dernière version de sa famille

Le skill `socle-batch` dit désormais que chaque modèle demandé, pour un
sous-agent comme pour la session, tourne sur la dernière version de sa
famille : sous Claude Code, l'alias `opus` de l'outil `Agent` a désigné un
Opus plus ancien que celui de la session, sans que rien le dise. Le
compte rendu de chaque sous-agent nomme le modèle qui l'a servi
(`modelUsage` le confirme en session cloud, une fois le tour fini) ;
l'agent lance un sous-agent sans `model` pour qu'il hérite de la session
quand l'alias désigne une version plus ancienne, ou le dit à l'humain ; le
relecteur suit la même règle (le skill `socle-review`) ; le récap du lot
dit la version qui a servi chaque sous-agent.

À faire : rien de plus que de suivre le skill ; c'est une copie protégée,
dans la demande de l'installeur.

## 2026-11-16-b — L'état dit ce qu'attendent les sujets en attente : un sujet ou une demande

La dernière ligne de l'ordre du backlog, dans l'état et dans le rappel de
fin de tour, disait « n sujet(s) attendent un sujet ouvert » de tout sujet
qui n'était pas prêt, y compris de celui qui n'attend qu'une demande sans
réponse. Elle se dédouble : « n sujet(s) attendent un sujet ouvert » compte
ceux qui attendent un sujet, « n sujet(s) attendent une demande sans
réponse » ceux qui attendent une demande ; un sujet qui attend les deux
compte dans les deux lignes.

À faire : rien.

## 2026-11-16-a — Le hook de l'agent borné aux formes qu'un agent écrit : le guide donne la règle et les formes connues qu'il ne juge pas

Le guide (`python3 .socle/socle help`) dit ce que juge le hook de
l'agent : les formes du shell qu'un agent écrit dans son travail, pour
tout effet ; pour ce que rien ne rattrape ensuite (supprimer le projet ou
un dossier qui le contient, une action externe irréversible, une fuite de
la mémoire privée, la part de la mémoire qui ne se publie pas), il refuse
aussi ce qu'il ne sait pas lire. Un trou n'ouvre un sujet que si sa forme
est de celles qu'un agent écrit (vue dans une session d'agent, un skill
ou une documentation courante) ; une autre forme s'inscrit d'une ligne
dans la liste des formes connues que le hook ne juge pas, que le guide
donne désormais : `time` devant une commande composée, les motifs d'un
`case`, `find -exec sudo …`, un `return` dans une fonction, l'appel
indirect d'une fonction, une fonction nommée comme une commande ou
définie par un `eval`, `eval -- f`, `git --config-env`, ce qu'un `eval`
change d'autre qu'un appel, une fonction appelée depuis un autre dossier,
`echo .. | xargs rm`, `xargs git worktree remove`, ce que lance ou
construit un `python3 -c`, `coproc`. Jusqu'ici, le guide disait que le
hook jugeait, quelle qu'en soit la forme, ce que rien ne rattrape.

La consigne du relecteur (`python3 .socle/socle review`) et le skill
`socle-review`, une copie protégée, le disent aussi : une forme du shell
qu'un agent n'écrit pas dans son travail, et qui échappe au hook, ne se
classe ni bloquante, même refusée avant le lot par accident, ni pour le
backlog ; elle s'écarte, d'une ligne, pour la liste. Le tri des autres
constats ne change pas. Le hook lui-même ne change pas.

À faire : rien. Une suppression du projet par `find … | xargs rm` lui
échappe encore : ne pas la lancer vers le projet ni vers un dossier qui
le contient.

## 2026-11-15-e — Le hook de l'agent refuse la suppression du projet par rsync --delete, git worktree remove et python -c

Le hook de l'agent refuse la suppression du projet, ou d'un dossier qui
le contient, par d'autres programmes que `rm`, `mv`, `git clean` et
`find` : la destination d'un `rsync --delete` (et ses variantes,
`--del`, `--delete-after`…), les sources d'un `rsync
--remove-source-files`, le chemin d'un `git worktree remove` ou d'un `git
worktree move`, lu aussi comme git le cherche d'abord, par la fin du
chemin d'un de ses worktrees (`git worktree remove agent-x`, lancé dans
`.claude/worktrees/agent-x`), et les chemins qu'un `python -c` écrit en
toutes lettres pour `shutil.rmtree`, `shutil.move`, `os.rename` ou
`os.replace`. Un `find -exec` de l'un d'eux compte comme un `find -exec
rm`. Jusqu'ici,
`rsync -a --delete vide/ ..`, `git worktree remove .` lancé par un
sous-agent dans son worktree et `python3 -c "import shutil;
shutil.rmtree('..')"` passaient. L'orchestrateur, à la racine du projet,
retire toujours le worktree d'un sous-agent (`git worktree remove -f -f
.claude/worktrees/agent-x`, ou `agent-x`), un sous-agent celui d'un autre,
et un dossier du projet ou voisin de lui reste libre.

À faire : rien. Pour vider un dossier, viser un dossier du projet, ou
hors de lui un dossier qui ne le contient pas, son chemin écrit en toutes
lettres.

## 2026-11-15-d — Le hook de l'agent juge le corps d'une fonction écrite sans parenthèses

Le hook de l'agent lit `function nom { …; }`, sans parenthèses, comme
`nom() { …; }` : chaque commande de son corps se juge, que le corps
suive le nom sur la même ligne ou sur la suivante, et ce qu'il change ne
vaut pas pour la suite. Jusqu'ici, la commande lue avait pour programme
`function`, et rien de son corps ne se jugeait : `function f { git push
--force origin main; }; f` et `function f { rm -rf ..; }; f` passaient.
Un autre corps que bash admet (`if`, `while`, `for`, un sous-shell) se
juge comme s'il s'exécutait là où il s'écrit : un dossier qu'il change
devient inconnu après lui, et une écriture dans le projet qui le suit est
refusée, comme après `nom() if …`. Un groupe écrit en tête du sous-shell
qui sert de corps à une fonction (`f() ( { cd x; }; … )`) ne se lit plus
comme le corps de cette fonction.

Deux régressions de cette lecture sont fermées à leur tour. À l'appel
d'une fonction dont le corps `{ …; }` change le dossier ou une variable,
le hook rend inconnu ce qu'elle change et juge la suite comme un état
inconnu : une suppression du projet depuis le dossier qu'un tel appel
laisse derrière lui (`function f { cd memory; }; f; rm -rf
../../<racine>`) est refusée, l'usage normal (`f() { ls; }; f; rm -rf
build`) reste libre. L'appel se résout au moment où il se fait, avec ce
que changent les fonctions que la fonction appelle, de proche en proche,
une fonction définie après elle ou dans elle comprise (`g() { f; }; f()
{ cd memory; }; g`) ; il vaut derrière `time` et `time -p`, et dans un
`eval` ou une substitution (`eval f`, `x=$(f; …)`), qui connaissent les
fonctions de la commande ; un `bash -c`, un autre processus, ne les
connaît pas. Un mot réservé cité ou échappé (`"function"`,
`\function`, `$'function'`, et un `}` qui fermait trop tôt un corps)
n'est plus lu comme réservé : bash le lance comme une commande, et le
groupe ou le corps qui suit se juge comme bash l'exécute sur place.

À faire : rien. Un push forcé ou une suppression du projet écrits dans
une telle fonction, ou passés par son appel ou par un mot réservé cité,
que le hook laissait passer, sont refusés. Un refus nouveau, sans danger
cette fois : une écriture ou une suppression par un chemin relatif qui
suit l'appel d'une fonction dont le corps change de dossier (`f() { cd
memory; }; f; rm -rf build`) est refusée, le hook ne sachant plus d'où
elle part. Pour la lancer, écrire son chemin absolu en toutes lettres, ou
faire le `cd` hors de la fonction (`cd memory; rm -rf build`).

## 2026-11-15-c — La revue trie les constats exotiques, et son relecteur reçoit le modèle le plus capable

Un constat de la revue qui ne bloque pas va au backlog s'il peut se
produire dans l'usage normal du projet, ou si rien ne rattrape ensuite son
effet ; un constat exotique dont l'effet est rattrapé (par un contrôle, la
CI ou une erreur que l'agent voit aussitôt), ou un constat infondé, est
écarté, et le récap dit pourquoi. La consigne du relecteur
(`python3 .socle/socle review`) le dit, et lui fait rendre trois listes,
« Bloquants », « Pour le backlog » puis « Écartés ». Sous Claude Code, le
relecteur reçoit explicitement, à son lancement, le modèle le plus capable
disponible jusqu'à Opus, jamais un moindre que celui qui a implémenté le
lot, quel que soit celui de la session ; Fable seulement si l'humain le
demande. Le modèle de menace d'un garde-fou s'écrit dans la section du
sujet ou dans la décision qu'il cite. La section du socle d'AGENTS.md
change (la règle du tri, un texte resserré), ainsi que le skill
`socle-review`, une copie protégée, et le guide `HELP.md`.

À faire : rien, sinon suivre le tri à la prochaine revue.

## 2026-11-15-b — Le dossier de la revue mesure le lot depuis l'ancêtre commun, et refuse une référence inconnue

`python3 .socle/socle review` mesure le lot depuis l'ancêtre commun de
HEAD et de sa base : la branche par défaut qui a avancé, ou un commit
poussé d'ailleurs sur la branche distante, n'entrent plus dans le diff ni
dans les sujets. Seuls les sujets dont le lot change le statut ou le
« Fait quand » font la barre du relecteur ; un `après` changé, un constat
ajouté ou un sujet clos rangé par `socle archive` n'y sont plus. Un
`--base` ou un `--since` inconnus, un `--since` qui n'est pas un ancêtre
de HEAD, une base sans ancêtre commun avec HEAD sont refusés (code 2), au
lieu d'un dossier vide. Le dossier dit ce que la branche distante porte
déjà du lot, sur combien de commits il mesure un lot déjà poussé, et la
vraie raison d'un dossier vide (branche par défaut devinée, clone
superficiel) ; sous `--since`, la commande qu'il propose garde `--since`.
Après une fusion par écrasement, une branche repartie de la branche par
défaut ne ramène plus le lot fusionné dans la revue du suivant.
Le skill `socle-review`, une copie protégée, change.

À faire : un lot déjà poussé en tout ou en partie, ou sur une branche qui
porte des lots déjà relus, se relit par `python3 .socle/socle review
--base <le commit d'avant le lot>`.

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
