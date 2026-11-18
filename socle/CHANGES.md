# Notes de version du socle

Ce que chaque changement du socle change pour un projet installé, et ce que
l'agent du projet doit en faire. Une entrée par changement, la plus récente
d'abord, sous un identifiant qui ne change jamais : la date du changement et
une lettre. À la mise à jour, l'installeur donne les entrées que la copie du
moteur du projet n'avait pas, et le message de commit qu'il propose nomme
leurs identifiants.

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
