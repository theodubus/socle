# Le socle, côté humain : guide d'utilisation

Ce guide suit le parcours de l'humain dans un projet équipé du socle, de la
fin de l'installation à l'usage courant. Les commandes se lancent à la
racine du projet : `python3 .socle/socle <commande>` ; ce guide s'affiche
par `python3 .socle/socle help`. Sans terminal, en session cloud, l'agent
les lance : il suffit de les lui demander.

Le parcours en bref :

1. **Démarrer**, une fois : décrire le projet, donner ses outils à
   l'agent, pousser, protéger la branche.
2. **Travailler avec l'agent** : lui confier du travail, lire ses
   récapitulatifs.
3. **Répondre à l'agent** quand une décision revient à l'humain.
4. **Les gestes occasionnels** : approuver ses propres changements, mettre
   à jour, agir là où l'agent ne peut pas.

## 1. Démarrer

En session cloud, l'agent installe le socle depuis son dépôt public, qui se
clone sans être ajouté à la session. Les hooks de l'agent se chargent
dans la session qui installe, dès l'appel d'outil qui suit l'écriture de
ses réglages par l'installeur : ensuite, un fichier protégé (l'adaptateur,
la CI, la politique) ne se corrige plus à la main. Ce qui ne va pas se
corrige en relançant l'installeur avec les bonnes options, un adaptateur
propre au projet se donnant par `--adapter <fichier.toml>` ; un essai se
défait en le commitant sur sa branche, puis en revenant à la branche de
départ par `git switch`, jamais fichier par fichier, que le hook refuse :
non commités, ses fichiers suivraient, et l'installeur relancé y verrait
une mise à jour. Avant le premier commit,
`python3 .socle/socle verify --fast` lance la compilation et les tests de
l'adaptateur, que l'audit de l'installeur ne lance pas. La session qui
installe pousse sa branche et ouvre une pull request. Une fois celle-ci
fusionnée, le travail continue dans une
session neuve, qui part de la branche par défaut et reçoit l'état dès son
démarrage. Une session qui ajoute un second dépôt ne se reprend pas : à
deux dépôts, elle redémarre hors de la racine du projet, sans les hooks de
l'agent.

Un agent qui travaille dans un worktree du dépôt (un sous-agent, par
exemple) y cite les entrées qu'il vient d'y créer : le hook avant outil
lit une référence dans le worktree du fichier écrit ou du dossier
courant, ou dans la copie principale où la session a démarré. Ses refus
valent pour les deux arbres : refusée dans l'un, une action est refusée.
Les hooks de fin de tour et de démarrage jugent la copie principale.

Un projet écrit en plusieurs langages a un adaptateur par langage :
l'installeur en pose un par langage qu'il reconnaît, ou ceux qu'on lui
nomme (`--adapter python-pytest --adapter kotlin`, le premier étant le
principal), et chaque fichier est jugé par celui de son langage (la
[spécification des adaptateurs](adapters/README.md)). Un langage dont le
manifeste n'est que dans un sous-dossier ne reçoit pas d'adaptateur en
automatique. En automatique comme avec `--adapter`, tant qu'aucun
adaptateur ne le couvre et que son manifeste n'est pas sous un chemin
tiers déclaré, l'installeur le dit, avec ses deux issues : un adaptateur
propre au projet dont les commandes entrent dans le sous-dossier, ou le
sous-dossier déclaré tiers.
Un adaptateur peut se poser avant le premier fichier de son langage : la
CI ne prépare ses outils qu'une fois son fichier de build là (le cache de
Gradle attend un fichier Gradle), et ses capacités attendent le premier
fichier source, ce que `verify` dit en avertissement.

Juste après l'installation :

1. Décrire le projet :
   `python3 .socle/socle init --brief <document> --repo`. Le document de
   cadrage est archivé ; `--repo` relève ce que le dépôt contient déjà. Sans
   document, `--repo` seul ; dans un dépôt vide, sans option.
2. Donner à l'agent les outils que la CI installe pour l'adaptateur
   (pytest, par exemple), que l'installeur cite avec leurs commandes. En
   session cloud, le conteneur repart de zéro à chaque session : le hook de
   démarrage du socle les installe dans chaque session neuve, et complète
   l'historique d'un clone superficiel, dont les commits que la mémoire cite
   manqueraient ; seule la session qui installe le socle les installe
   elle-même. Tant que le projet
   n'a aucun fichier source, `verify` ne lance ni compilation ni tests, et
   le dit.
3. Commiter et pousser.
4. Protéger la branche par défaut sur GitHub (réglages du dépôt,
   « Rules ») : exiger la CI « Socle — verify, contrôles, auto-test » avant
   toute fusion. Sans cela, une CI rouge n'empêche pas de fusionner. Dans
   le même ensemble de règles, cocher « Block force pushes » et « Restrict
   deletions » : hors du hook de l'agent, seul GitHub refuse un push forcé
   sur la branche par défaut, ou sa suppression ; l'état dit s'ils sont
   refusés, et sinon vous demande de les faire refuser. La
   revue des propriétaires du code ne s'y ajoute que si un autre humain
   relit : l'auteur d'une pull request ne peut pas l'approuver, et l'agent
   ouvre les siennes au nom de l'humain. Dans les réglages généraux, cocher
   « Automatically delete head branches » : une branche fusionnée s'efface
   alors seule. L'état signale les autres : celles que la branche par
   défaut ou la branche de travail poussée contiennent déjà, à supprimer,
   et celles qui ne bougent plus depuis
   une semaine sans avoir été fusionnées, à livrer ou à supprimer. Si une
   telle branche garde seule un commit que la mémoire cite, l'état donne
   d'abord la commande qui l'étiquette : sans elle, la CI ne le
   retrouverait plus. Il ne propose qu'une branche que l'origine a
   encore, et ne dit une branche gardée par la branche de travail que si
   l'origine a encore celle-ci ; quand l'origine ne répond pas, il dit que sa liste vient du
   dernier fetch, et que `git fetch --prune origin` la rafraîchit.
5. Ouvrir l'agent dans le projet. Il lit l'état au démarrage, puis donne le
   lien des questions de départ, une demande que `socle init` a posée : y
   répondre dans la conversation, `valider` pour appliquer tous les
   défauts, ou une réponse par question.

Si le projet avait déjà son propre hook `SessionStart`, l'installeur le
signale : le retirer de `.claude/settings.json`, sans quoi chaque session
reçoit deux états. Il nomme de même un hook `Stop` du projet, qui tire à
chaque fin de tour à côté de celui du socle et peut le doubler. Une
commande du projet placée dans le même bloc qu'un hook du socle est gardée
et nommée de même : l'installeur ne retire du bloc que celle du socle.

## 2. Travailler avec l'agent

Le travail se confie à l'agent comme d'habitude. Au démarrage de chaque
session, il reçoit l'état du projet, le chantier actif, les titres des faits
et les dix dernières décisions ; il travaille, et les contrôles le vérifient
à chaque étape. Ce démarrage tient sous `[startup] max_bytes` des
garde-fous, borne posée sous ce que Claude Code remet entier à l'agent,
dont chaque partie a sa part : une partie qui dépasse la sienne perd des
lignes entières (l'état, d'abord ce qui se relit ailleurs, jamais ce qui
demande d'agir avant ; les autres, depuis leur fin), et la dernière ligne
dit laquelle, de combien, et comment lire le reste. Le budget du chantier
actif, public et privé ensemble, tient dans sa part : à sa taille
permise, il n'est jamais coupé.

**Planifier.** Depuis le cadrage, l'agent écrit une spécification et une
architecture courtes dans la documentation du projet : chaque choix en
ADR, chaque question ouverte en demande (en questions de cadrage quand
votre intention manque, section 3). Le backlog a quatre formes d'entrée,
chacune son préfixe : un **besoin** (`B-`), un défaut à corriger ou une
fonction à ajouter, avec ce qui le satisfait (« Satisfait quand », un
résultat) ; une **tâche** (`T-`), un livrable qui sert un besoin, avec ce
qui la rend faite (« Fait quand », qu'un test vérifie ; une case qui
livre une demande posée, un relevé écrit ou une entrée de la mémoire
récrite se vérifie par ce qu'elle produit, que la case nomme : la
demande et votre réponse, le fichier du relevé, ce qu'en montre
`socle show`) ; un **lot**
(`L-`), les tâches qui touchent les mêmes fichiers, menées et relues
ensemble ; un **jalon** (`JA-`), les besoins qui servent un même but.
Chacune dit ce qu'elle attend (`après` : une autre entrée, ou une demande
jusqu'à sa réponse), et ses cases sont toutes cochées avant de la clore.
Il soumet chaque document en demande. Il suffit de le lui demander ;
l'état donne ensuite le prochain jalon, le prochain lot et l'avancement
de ses tâches, les tâches prêtes, et les besoins à découper en tâches ou
à fermer. La suite entière, d'un coup d'œil, se lit dans un terminal par
`python3 .socle/socle roadmap` (une ligne par jalon et par lot ;
`--format markdown` détaille le lot en cours et les deux suivants,
`--by need` lit par besoin, `--by batch`, le défaut, par lot), sur la page de chaque exécution de la CI, et
dans la conversation : demandez « la suite » à l'agent.

Le format compact aligne en colonnes les lots, strictement dans leur
ordre d'exécution, chacun avec ses tâches closes sur le total, le lot en
cours marqué ▶. L'en-tête d'un jalon, avec ses besoins clos sur le
total, s'écrit chaque fois que le jalon change d'un lot au suivant : un
jalon dont les lots alternent avec ceux d'un autre revient, et les lots
qui ne servent aucun jalon ont l'en-tête « Hors des jalons » à leur
place. Le lot en cours et les deux suivants, quel que soit leur jalon,
ont chacun leur ligne ; hors de cette fenêtre, une suite de lots d'un
même jalon tient en une ligne, et un lot seul garde la sienne (`--all`
les montre tous). Il finit par ce qui est hors des lots, compté, et par
ce qui vient ensuite : les jalons sans lot, avec leurs premiers besoins
ouverts, puis les besoins d'aucun jalon. Il ne nomme aucune demande. Par
exemple, les identifiants écrits ici `X-NNNN` :

```text
JA-NNNN  Fini avant les nouvelles fonctions        1/11 besoins clos
 ▶ L-NNNN  Structure du backlog, chantier en rond  2/3   en cours
   L-NNNN  Durée de la vérification                0/2
   L-NNNN  Suite de la structure du backlog        1/5
   …  L-NNNN à L-NNNN                              0/10
Hors lot : 4 besoins sans tâche · 1 bloqué (B-NNNN)
Ensuite : JA-NNNN Le pilote équipé (B-NNNN) · puis B-NNNN, B-NNNN
```

Le format détaillé, en Markdown, suit le même ordre sous les mêmes
en-têtes, et donne le lot en cours et les deux suivants, chacun avec le
tableau de ses tâches : leur état en symbole, que sa légende explique,
leur identifiant, leur besoin suivi de leur priorité, leur titre jusqu'à
son premier deux-points, et ce qu'attend une tâche qui attend ; les
autres lots, une ligne chacun, numérotés dans l'ordre d'exécution. Lu
par besoin, chaque besoin, dans l'ordre de ses lots, a le tableau de ses
tâches, avec le lot de chacune. Ce qui est hors des lots
suit, en tableaux de même forme, chaque demande en attente avec son lien.
Le début du même backlog :

```markdown
Légende : ✓ faite · ▶ en cours · ○ prête · ⏳ attend · ✗ bloquée · ⊘ abandonnée · ↑ priorité haute · ↓ priorité basse

### JA-NNNN — Fini avant les nouvelles fonctions · 1/11 besoins clos

**1. L-NNNN — Structure du backlog, chantier en rond** · en cours · 2/3

| | Tâche | Besoin | |
| --- | --- | --- | --- |
| ✓ | T-NNNN | B-NNNN | La structure en quatre formes |
| ✓ | T-NNNN | B-NNNN | Le format de la mémoire |
| ○ | T-NNNN | B-NNNN | La forme exotique dans la liste du guide |

**2. L-NNNN — Durée de la vérification** · 0/2

| | Tâche | Besoin | |
| --- | --- | --- | --- |
| ○ | T-NNNN | B-NNNN ↑ | Mesurer la durée de chaque étape |
| ⏳ | T-NNNN | B-NNNN ↑ | La suite sur plusieurs cœurs · attend T-NNNN |

…
```

**Spécifications et cas d'essai.** Le projet déclare où vivent ses
spécifications (`[specs] paths` des garde-fous) : l'état vous signale
celle qu'aucune demande ne vous a soumise. Il déclare aussi ses fichiers
de cas (`[tests] case_paths`), des données où ses tests lisent leurs
résultats attendus : y ajouter un cas est libre, mais changer ou retirer
un cas existant exige votre validation, comme une valeur attendue écrite
dans un test.

**Prioriser.** Un besoin ou une tâche peut porter `priorité : haute` ou
`priorité : basse` ; la normale ne s'écrit pas, et une tâche prend celle
de son besoin. Le dire à l'agent suffit, et il ne change pas une priorité
que l'humain a donnée. Les tâches prêtes se rangent par priorité, et
celles de priorité basse restent à part :
l'agent ne les prend que s'ils sont commodes, et le dit en annonçant le
lot.

**Enchaîner.** Tant que rien ne revient à l'humain, l'agent enchaîne les
tâches prêtes sans attendre de message. Avant de s'y lancer, il annonce le
lot qu'il va traiter : l'arrêter ou le réorienter se fait d'un message.
À la fin du lot, il enchaîne le suivant si la session le permet (plus
bas, « L'enchaînement des sessions »), et s'arrête dès qu'une décision
revient à l'humain.
Un lot ouvert qui attend encore plus de tâches qu'une session n'en mène,
`[batches] max_tasks` des garde-fous (9 par défaut), l'état et le rappel
de fin de tour le disent, sans rien refuser : le couper en lots, ou en
faire un jalon, ses lots dessous. Baisser le seuil est libre ; le relever
exige une demande validée.

**Faire relire.** Avant de livrer un lot qui pose ou change un garde-fou
(un contrôle, un refus, un hook), un format que d'autres parties du
projet lisent, ou plus de 150 lignes de code et de tests, l'agent le fait
relire par un relecteur sans contexte, qui reçoit le dossier complet
(`python3 .socle/socle review`) et cherche à le prendre en défaut contre
le critère « Fait quand » des tâches du lot et, pour un garde-fou, son
modèle de menace, écrit avant le code : ce que le garde-fou arrête, ce
qu'il laisse passer. Un autre lot qui change du code ou un test, l'agent
le relit lui-même, son diff et les fichiers touchés, contre les critères
de ses tâches (`python3 .socle/socle review --short`, qui refuse un lot
qui touche un garde-fou), et son récap le dit. Une spécification, de la
documentation ou de la mémoire seules n'ont pas de revue : c'est vous
qui en jugez l'intention.
L'agent corrige dans le lot les constats bloquants (un critère contredit,
une régression, une perte de données, un contournement dans le modèle de
menace) ; il envoie au backlog, où vous les voyez, ceux qui sont
importants et ont été vus en usage réel, ou dont l'effet serait
irréversible, en tâche si leur correction est claire, en besoin sinon,
et écarte tous les autres, dont un cas imaginé et jamais vu, une légère
gêne ou un constat infondé ; un écarté revient s'il se voit. Son récap dit combien, et
pourquoi chacun est écarté.

**L'historique des revues.** L'agent garde, dans l'entrée de chaque lot,
ses passes de revue et leurs bloquants : une session neuve qui reprend le
lot y lit où en est sa revue.

**Livrer.** Par défaut, l'agent fait tout sur une branche de
développement et garde une seule pull request ouverte, à laquelle chaque
lot fini s'ajoute : la fusionner quand on veut, une fois sa CI verte. Une
pull request par tâche, chacune à fusionner, se choisit aux questions de
départ, ou plus tard en le disant à l'agent, qui l'écrit en fait de la
mémoire.

**La fusion par l'agent.** Par défaut, c'est vous qui fusionnez la pull
request de l'agent : le hook lui refuse la fusion, comme les autres
actions externes. Pour qu'il fusionne lui-même la sienne, décommentez la
ligne `tools` que la section `[irreversible]` de la politique
(`.socle/policy.toml`) porte en commentaire : la liste des outils externes
que le moteur refuse, moins la fusion. Une politique posée avant cette
option ne l'a pas ; le diff de la politique, montré à la mise à jour qui
l'apporte, la donne. Seul l'humain écrit la politique, et approuve ce changement comme
tout changement protégé : l'agent ne s'en donne pas le droit. Il ne
fusionne alors qu'à quatre conditions : sa propre pull request
seulement, jamais celle d'une autre session ; la CI verte sur son commit
de tête, qu'il donne ; la revue du dernier lot faite et ses constats
traités ; aucune demande en attente sur son contenu. Après la fusion, il
vérifie les workflows qu'elle lance sur la branche par défaut (un
déploiement, une publication…), et son récap dit s'ils ont réussi. Il
fusionne par l'outil GitHub de sa session : `gh pr merge`, le push forcé
et le push sur la branche par défaut restent refusés. La ligne fige la
liste : un outil que le moteur ajoutera à la sienne n'est pas refusé au
projet tant que vous ne l'avez pas recopié dans la ligne, ce que dira la
note de version qui l'ajoute. Retirer la ligne rend la fusion à
l'humain.

**L'enchaînement des sessions.** La session est l'unité de budget : à la
fin d'un lot, l'agent enchaîne le suivant si son coût estimé tient dans
ce qui reste de la fenêtre de cinq heures et de la semaine, et si la
conversation reste sous 300 000 jetons de contexte, au-delà desquels
chaque échange coûte de plus en plus ; deux lots au plus sans message de
votre part. Sinon, comme près d'une limite d'usage ou avant une longue
attente, il range, puis passe la main à une session neuve, selon l'un de
deux modes. Par
défaut, en session cloud de Claude Code, la **session programmée** : il
crée lui-même la session suivante, qui paraît aussitôt dans votre liste
de sessions avec son titre et son heure de départ, et programme son
prompt ; jamais si le coût de son lot ne tient pas dans ce qui reste de
la fenêtre de cinq heures, ni sur une semaine à 75 % : elle attend alors
la remise à zéro. La chaîne s'arrête sans
vous, et le récap vous dit de demander la reprise, quand le lot suivant
n'a aucune tâche prête (une décision vous revient, par exemple), après
deux lots menés sans message de votre part, ou si Claude Code refuse de
créer la session. Le **prompt à copier** : vous ouvrez une session neuve
quand vous voulez, d'un compte comme d'un autre, et y demandez la
reprise : « reprends », « continue », ou tout autre message qui le dise ;
c'est le mode de qui a plusieurs comptes ou veut garder la main. Pour changer de mode, dites-le à l'agent (« passe au prompt à
copier », « reprends la session programmée ») : il l'écrit au chantier
actif, et passer au prompt à copier annule ce qui est programmé, en vous
donnant le lien de chaque session annulée. Pour arrêter une session
programmée sans changer de mode : écrire « arrête » dans la session qui
l'a programmée, ou supprimer sa tâche de la liste des tâches programmées
de votre compte et archiver la session. Dans les deux modes, l'agent
écrit sa passation dans la mémoire (`python3 .socle/socle handoff write`),
la commite et la pousse ; la session neuve la trouve et juge sa garde
(`python3 .socle/socle handoff check`) : elle ne travaille pas si
quelqu'un a poussé sur sa branche depuis, si une autre session a écrit la
mémoire du projet depuis, ou si une autre l'a déjà reprise, et le dit ;
sans passation, elle le dit aussi. Acceptée, elle continue la pull request ouverte de sa branche, qui
devient la sienne : elle la fusionne si la politique le permet à
l'agent ; sinon, vous la fusionnez.

Un prototype qu'on ne compte pas fusionner se fait sur une branche
jetable, nommée `proto/…` (ou d'un autre préfixe déclaré dans
`[branches] disposable` des garde-fous). La CI du socle ne la juge pas aux
envois, et les références mortes (liens, identifiants, chemins cités) d'un
fichier qu'elle ajoute n'y sont qu'un avertissement ; les autres contrôles
avant commit et ceux de la session de l'agent restent, et la mémoire
privée reste jugée en entier. Jetée, elle ne laisse rien dans la branche
par défaut ; poussée, sa suppression sur GitHub vous revient, et l'état
la liste parmi les branches à examiner après une semaine sans activité.
Fusionnée, elle passe par une pull request, dont la CI la juge en entier.

Chaque intervention de l'agent qui a agi se termine par deux lignes :

- **« Pour toi : »** — ce qui revient à l'humain : une demande à lire, une
  action à faire, ou rien ;
- **« Ensuite : »** — la suite prévue, et ce que l'agent attend.

Chaque point de « Pour toi » se comprend seul : ce que c'est, pourquoi,
et ce que change votre réponse. L'agent écrit ses deux lignes en texte :
une ligne dans un bloc de code ne compte pas, et une sortie qu'il y
colle, comme le compact de la suite et sa propre ligne « Ensuite : », ne
tient pas lieu de récap.

À tout moment, `python3 .socle/socle state` donne l'état du projet : le
commit, la CI, le backlog et ce qui vient ensuite (le prochain jalon, le
prochain lot, les tâches prêtes), les demandes en attente, ce qui revient à l'humain. La mémoire se lit dans `memory/`.

Une procédure du projet qui revient, l'agent l'écrit en skill dans
`.claude/skills/`, avec une entrée au journal : il la charge ensuite à la
demande au lieu de la reconstituer. Ses skills sont contrôlés comme le
reste ; ceux du socle, posés par l'installeur, sont protégés.

## 3. Répondre à l'agent

**Une demande.** Quand une décision revient à l'humain (relâcher un seuil,
supprimer un test, une décision coûteuse à défaire, une action
irréversible), l'agent écrit une demande et en donne le lien. Elle se lit
seule, même après des semaines loin du projet : son contexte commence par
le projet, le chantier en cours et la question. Une demande longue, au-delà
de la moitié de son budget, l'agent qui a des sous-agents la fait relire
à froid, par l'un d'eux qui n'a que son texte, avant de vous la poser, et
son récap en donne le bilan. Elle se termine par
la liste des réponses possibles. Répondre dans la
conversation ; l'agent consigne la réponse mot pour mot.

- Les réponses de base sont les mêmes dans toute demande : `valider` (la
  recommandation), `refuser`, `contexte-insuffisant` ; une demande de choix
  y ajoute ses options.
- `valider` est la seule réponse qui autorise un geste réservé à l'humain.
- Un test qu'elle nomme, supprimé ou dont la valeur attendue change, ou un
  fichier protégé qu'elle cite, peut précéder votre réponse : si la
  branche par défaut exige la CI du socle, il se commite et se pousse sous
  la demande poussée telle quelle, la CI le refusant jusqu'à votre
  réponse, et vous le lisez dans la pull request ; sinon, il l'attend dans
  l'arbre de l'agent.
- `contexte-insuffisant` renvoie la demande à l'agent, qui la réécrit.
- Depuis un terminal :
  `python3 .socle/socle answer D-NNNN <réponse> --text "<texte>"`.

**Une question en séance.** Une question courte, que l'agent pose dans
le texte de sa réponse, se répond dans la conversation ; l'agent la
consigne aussitôt, mot pour mot, comme une demande. Ce qui demande du
contexte, approuver un document compris, arrive en demande, avec son
lien ; jamais dans le widget de questions de l'agent, que le hook refuse.
Ce que vous décidez de vous-même, sans qu'il l'ait demandé (une règle, une
interdiction, « supprime ce test »), il le consigne de même, votre texte
exact, sans question ni réponse à choisir (`socle decision --unprompted`) :
la décision vaut validée pour ce qu'elle nomme.

**Une consigne durable.** Une règle, une préférence ou une interdiction qui
vaut au-delà du tour, l'agent l'écrit aussitôt dans les consignes
(`memory/directives.md`, par `socle new directive`) : une ligne de résumé,
que chaque session reçoit au démarrage, votre texte exact, qui ne change
jamais, et sa source au journal. Avant de s'appuyer sur une consigne, il en
relit le texte exact (`socle show C-NNNN`), et toute citation d'une
consigne dans la mémoire le prouve par son empreinte. Pour en lever une,
dites-le : l'agent consigne votre parole en séance, puis note la consigne
« levée », avec la décision qui la lève (`levée-par`) ; seule votre parole
la lève, et `socle archive` la range ensuite dans le journal. Une consigne
que vous changez en devient une nouvelle, et votre parole lève l'ancienne.

**La question d'intention.** Quand la conception d'un besoin n'est pas
tranchée, l'agent vous pose d'abord, dans la conversation, en quelques
lignes, le besoin tel qu'il le comprend, le choix qui reste et sa
recommandation. Il consigne votre réponse, puis écrit la spécification et
le code dans le même lot, la spécification d'abord ; ce qui reste coûteux
à défaire vous arrive ensuite en demande, courte.

**Des questions de cadrage.** Quand votre intention manque sur plusieurs
points, l'agent pose des questions ouvertes, chacune avec son hypothèse,
dans une demande dont il donne le lien. Y répondre librement, en un ou
plusieurs messages (`reponses`), ou `valider` ses hypothèses : il
consigne le texte tel quel, puis écrit la spécification qui en découle. Lui dire « pose-moi tes questions sur ce
besoin » suffit à en demander.

**Une relecture avant publication**, si la politique l'exige : l'agent
montre ce qui part vers le dépôt public, l'humain donne son accord dans la
conversation. Depuis un terminal : `python3 .socle/socle reviewed --by <nom>`.

## 4. Les gestes occasionnels

**Approuver ses propres changements protégés.** La politique, les seuils,
l'adaptateur, les hooks et la CI sont protégés : un commit qui les change
sans validation est refusé. Quand le changement vient de l'humain :
`python3 .socle/socle approve --text "<raison>"`, puis commiter. Cette
commande est réservée à l'humain. L'agent, lui, n'écrit jamais dans un
fichier protégé, sauf pour le remettre à son état du dernier commit quand
il l'a changé par erreur, hors des réglages de Claude Code, que
l'humain garde pour lui : `git restore --source=HEAD --staged
--worktree -- <chemin>` ou `git checkout HEAD -- <chemin>`, chaque chemin
écrit en toutes lettres, ou `rm <chemin>` pour un fichier apparu sous un
chemin protégé que git ne suit pas. Le reste lui est refusé : un autre
commit, avec ou sans `--`, un dossier entier, un motif ou une variable du
shell, des chemins lus dans un fichier, une variable ou un préfixe devant
`git`, une redirection vers un autre fichier protégé, et un fichier que
cite, lui ou son dossier, une demande en attente ou validée dont ce
qu'elle approuve n'est pas commité ; un dossier qui n'est qu'un mot d'un
texte recopié entre accents graves, une valeur attendue ou une sortie,
n'y est pas cité. Le risque accepté : effacer une
modification de l'humain dans l'arbre de travail qu'il n'a ni commitée ni
soumise par une demande. Un chemin que le shell écrit, le hook le
développe, au mieux, comme le shell (variables, motifs, accolades, `~`,
`cd`, `pushd`), depuis le dossier courant de l'agent, en supposant qu'un
sous-shell, une substitution ou un pipeline ne transmettent rien à la
suite. Un chemin qu'il ne sait pas développer (une variable qu'il ne
connaît pas, `$(…)`) est refusé si le dossier qu'écrit en toutes lettres
la part qui le précède, remonté des `..` qui le suivent, est dans le
projet ou le contient : l'écrire en toutes lettres, ou sous un dossier
hors du projet (`/tmp/…`). Une commande qu'il ne sait pas juger (plus de
10 000 caractères hors du corps de ses heredocs, plus de 32 parenthèses
ou accolades ouvertes à la fois, un jugement qui plante ou passe
5 secondes) est refusée si elle peut écrire : la découper. Le script d'un
`python3 -c`, et celui qu'un heredoc donne à python (`python3 - <<'EOF'`),
se jugent par les fichiers protégés qu'ils citent en toutes lettres ou
que nomment les arguments qui les suivent, s'ils les lisent (`sys.argv`),
et un tel argument qu'il ne sait pas développer (`"$X"`), comme un chemin
écrit ; un script que python lit d'un fichier ne se juge pas. Il refuse
aussi la suppression d'un dossier qui contient le projet (`rm -rf ..`, un
`mv`, un `git clean` ou un `find` qui supprime depuis un tel dossier, ou
qui en donne la liste à `xargs rm` (`find .. -maxdepth 0 | xargs rm
-rf`), la
destination d'un `rsync --delete`, les sources d'un `rsync
--remove-source-files`, le chemin d'un `git worktree remove`, un `python3
-c` ou le script d'un heredoc qui le passent en toutes lettres à
`shutil.rmtree`), celle du projet
lui-même par ces autres programmes (un sous-agent qui retire son propre
worktree, `git worktree remove .`, ou par la fin de son chemin, que git
cherche d'abord parmi ses worktrees : `git worktree remove agent-x`), et
celle du projet par un `find` qui
part de sa racine sans qu'un filtre de nom ou de chemin garde ce qu'il
supprime (`find . -delete`, `find . -type f -delete`, `find . -delete
-name '*.pyc'`, dont le filtre vient après l'action) ; un dossier voisin
du projet, et un dossier du projet, restent libres (l'orchestrateur, à la
racine, retire le worktree d'un sous-agent). Un `git push` se juge de même
sur ses arguments développés : `F=--force; git push $F origin x` est un
push forcé, et un argument qu'il ne sait pas développer (une variable
qu'il ne connaît pas, une substitution, les arguments d'une fonction) est
refusé : écrire la branche en toutes lettres. Trois substitutions font
exception, `$(git branch --show-current)`, `$(git rev-parse --abbrev-ref
HEAD)` et `$(git symbolic-ref --short HEAD)`, nues, entre guillemets,
entre accents graves ou passées par une variable : elles valent la
branche courante, que le push vise alors (`git push -u origin "$(git
branch --show-current)"` passe depuis une branche de travail, et est
refusé depuis la branche par défaut), sauf si la même commande change de
dossier, de dépôt ou de branche avant le push (`cd`, `git -C`, `git
checkout`, `git switch`).

**Ce que juge le hook de l'agent.** Le hook de l'agent arrête les erreurs
d'un agent coopératif avant qu'elles agissent. Il juge les formes du shell
qu'un agent écrit dans son travail, pour tout effet ; pour ce que rien ne
rattrape ensuite (supprimer le projet ou un dossier qui le contient, une
action externe irréversible, une fuite de la mémoire privée, la part de la
mémoire qui ne se publie pas), il refuse aussi ce qu'il ne sait pas lire.
Un agent coopératif ne cherche pas à contourner ses garde-fous.

Le hook ne modélise pas tout bash : une écriture d'un fichier protégé
sous une forme qu'on n'écrit que pour contourner (un `eval`, `IFS`, un
chemin construit au vol dans un autre langage) est hors de son modèle,
comme des formes qui lui échappent (une part inconnue qui vaut elle-même
`..`, une option posée par le profil du shell, une variable que Claude
Code ne pose que pour ses hooks…) ; la garantie est alors le contrôle
des fichiers protégés, à la fin du tour, au commit et dans la CI.

**Faire ce que l'agent ne peut pas faire.** Pousser sur la branche par
défaut, publier, régler un service, supprimer une branche distante, poser
une étiquette (en session cloud, l'agent ne pousse que sa propre branche) : l'agent l'inscrit au backlog avec son
mode d'emploi, et l'état le liste dans « ce qui revient à l'humain ».
Supprimer la branche distante d'un travail non fusionné ne remet pas sa
plage à neuf : le hook avant envoi du clone qui l'a poussée juge la suite
depuis le dernier commit qu'il y a poussé.

**Commiter soi-même.** Les mêmes contrôles s'appliquent : une fonction
publique ajoutée est nommée par un test, ou dispensée dans le message du
commit (`Dispense-test: f — <raison>`) ; un correctif apporte un test qui
échoue sur le commit précédent.

**Mesurer ce qu'une session a coûté.** Quand une session de Claude Code
a vidé ses limites d'usage plus vite que prévu, ou avant de changer la
façon de mener un lot : `python3 .socle/socle consumption` lit les
transcriptions que Claude Code tient pour le projet (sous
~/.claude/projects/, un dossier par projet ; un autre dossier se donne
en argument), et dit ce que la session a coûté, par jour et par modèle,
la conversation principale et les sous-agents à part, et ce qui l'a
fait coûter : la taille du contexte relu à chaque appel, les reprises
après une pause, les compactages, et ce que le socle y injecte.
`--session <id>` garde une session (le nom de son fichier `.jsonl`),
`--day AAAA-MM-JJ` un jour. Le coût est pondéré au tarif public, une
hypothèse que des options changent ; des relevés de la fenêtre de cinq
heures, donnés par `--point INSTANT,PART`, disent ce que vaut un point
de la limite. Le rapport ne porte que des agrégats, jamais un texte de
la conversation. Sous un autre agent que Claude Code, la commande ne
trouve rien à lire.

**Mettre à jour le socle.** Relancer la commande d'installation depuis un
clone à jour du moteur (`git clone --depth 1
https://github.com/theodubus/socle /tmp/socle`). Les fichiers du projet ne sont jamais écrasés ; le
diff de la politique est montré, en une ligne quand chacune de ses lignes
était déjà dans son diff au gabarit de la copie remplacée, montré à la
mise à jour précédente (les lignes que l'humain a écrites exprès). Entre ce qu'il a posé et l'audit,
l'installeur imprime les [notes de version](CHANGES.md) que la copie du
moteur du projet n'avait pas, toutes si elle n'en avait aucune : ce que
chaque changement fait au projet, et ce que l'agent doit faire. Il
n'imprime en entier que celles qui demandent quelque chose ; de celles
dont « À faire » est « rien », le titre seul, leur texte restant dans le
fichier qu'il nomme. Le message
de commit qu'il propose nomme leurs identifiants, pour l'agent qui n'a pas
vu passer la mise à jour. Le hook de l'agent refuse l'installeur visé
sur un projet équipé dans un autre mode que celui de son verrou, ou sur
une cible écrite par une variable : la mise à jour garde le mode, et sa
cible s'écrit en toutes lettres. Seule exception, une copie d'un adaptateur
maintenu que le projet n'a pas adaptée se rafraîchit ; une copie adaptée se
garde, et l'installeur dit quand son adaptateur maintenu a changé : l'agent
propose alors d'y reporter les corrections, par une demande. Approuver ensuite les fichiers protégés
changés (`socle approve`), puis commiter. En session cloud, sans terminal,
l'agent pose une demande qui cite chaque fichier protégé changé avec son
empreinte, et l'humain la valide dans la conversation ; chaque fichier y
tient sur une ligne, son chemin et son empreinte sans rien d'autre, que le
budget de la demande ne compte pas. Poussée seule d'abord, la demande est
jugée par la CI avec le moteur d'avant, qui peut encore compter ces lignes
et la refuser : ce refus cesse une fois les fichiers protégés commités,
avec le moteur nouveau. Si la branche par
défaut exige la CI du socle, l'agent commite et pousse ces fichiers dès la
demande poussée : la CI reste rouge jusqu'à la validation, et l'humain les
lit dans la pull request avant de répondre. Le dépôt public du
moteur se clone sans être ajouté à la session. Une mise à jour garde les
garde-fous du projet tels quels, et nomme les réglages apparus depuis dans
le gabarit : l'agent y déclare ceux qui servent au projet, comme ses
spécifications et ses fichiers de cas (section 2), une fois le moteur
nouveau commité. Avant, la CI juge avec l'ancien moteur, qui ne les connaît
pas et les compte pour un assouplissement. Si la section du socle, qui se
régénère, fait dépasser à `AGENTS.md` son budget, l'installeur le dit :
resserrer la partie propre au projet, ou relever le budget par une demande
validée, puisque le relever assouplit un garde-fou.

En session cloud, le prompt à donner à l'agent :

```text
Mets à jour le socle de ce dépôt depuis son dépôt public, sans ajouter ce dépôt à la session :
1. Si le clone est superficiel (git rev-parse --is-shallow-repository répond true), complète son historique : git fetch --unshallow.
2. git clone --depth 1 https://github.com/theodubus/socle /tmp/socle
3. Sur ta branche de travail, depuis la racine du dépôt : PYTHONPATH=/tmp/socle python3 -m socle install --target . ; si le projet a plusieurs adaptateurs (des copies dans .socle/adapters/), nomme-les tous par --adapter, le principal d'abord, comme à l'installation.
4. Lis les notes de version que l'installeur imprime, et fais ce que chacune demande.
5. Suis les étapes « Et maintenant » de l'installeur, dont la demande qui cite les fichiers protégés changés, puis pousse et ouvre la pull request.
6. Dis-moi ce qui me revient.
```

**Mettre en place la mémoire privée** (mode compagnon). Créer un dépôt
privé vide sur GitHub, puis
`python3 .socle/socle private install --repo <adresse>`. La commande
termine par les deux réglages à faire sur GitHub, avec leurs liens.

## Quand un contrôle refuse

Chaque refus dit ce qu'il a vu et comment en sortir. La plupart s'adressent
à l'agent, qui corrige seul. Ceux qui concernent l'humain :

| Refus | Signification | Que faire |
| --- | --- | --- |
| `protege.fichiers` | un fichier protégé a changé sans validation | changement de l'humain : `socle approve` ; de l'agent : il doit le demander |
| `cliquet.garde-fous` | un seuil a été relâché | le rétablir, ou valider une demande qui le cite |
| `tests.attendus` | une valeur attendue a changé, dans un test ou un fichier de cas, ou un test a disparu | valider une demande qui nomme le test ou cite le fichier de cas, ou rétablir |
| `tests.code-teste` | une fonction publique sans test | écrire le test, ou `Dispense-test:` dans le commit |
| `tests.regression` | un correctif sans test qui le prouve | écrire ce test ; si sa preuve dépend de l'environnement, ou si le correctif ne touche aucun fichier qu'un adaptateur juge, valider une demande qui nomme le commit |
| `docs.correspondance` | du code a changé sans sa documentation | mettre la documentation à jour, ou `Dispense-doc:` dans le commit |
| `mutation.vivante` | le balayage hebdomadaire ne tourne plus | le réactiver dans l'onglet Actions de GitHub |
| push refusé, relecture | la politique exige une relecture | relire ce qui part, donner son accord |

## Référence

### La politique d'autonomie

`.socle/policy.toml`, modifiée par l'humain seul :

1. Assouplir un garde-fou exige une demande validée ; le durcir est libre.
2. Supprimer un test ou changer une valeur attendue, dans un test ou un
   fichier de cas, exige une demande validée.
3. L'agent prend les décisions réversibles et mesurables ; il demande
   celles qui sont coûteuses à défaire.
4. Une action irréversible ou externe est toujours demandée, hors la
   fusion de sa pull request quand la politique la permet (« La fusion
   par l'agent »).
5. La mémoire est en ajout seul.
6. Un défaut voisin du travail en cours va au backlog.
7. Après trois échecs de suite, l'agent s'arrête et écrit une demande.
8. L'agent ne devine jamais une validation : il attend la réponse.

### Les commandes

| Pour l'humain | |
| --- | --- |
| `help` | ce guide |
| `install` | installer ou mettre à jour le socle |
| `init` | décrire le projet |
| `state` | l'état du projet |
| `roadmap` | la suite du projet : jalons, lots, tâches et besoins |
| `consumption` | ce qu'une session de Claude Code a coûté, et ce qui l'a fait coûter |
| `answer`, `decision`, `reviewed` | répondre à une demande, consigner une décision en séance, une relecture |
| `approve` | approuver ses propres changements protégés |
| `private install` | mettre en place la mémoire privée |

Les autres commandes servent à l'agent et aux hooks ; `python3 .socle/socle
--help` les liste toutes, et `python3 .socle/socle checks` liste les
contrôles.

### Les seuils

`.socle/guardrails.toml` porte les seuils des contrôles : budgets de taille
de la mémoire, plafonds de mutation, correspondances entre code et
documentation, fichiers tiers (ceux d'un outil installé dans le projet),
fichiers de cas et spécifications du projet. Les durcir est
libre ; les relâcher exige une demande validée.

**La durée des étapes.** Chaque vérification qui lance une étape de
l'adaptateur (`verify`, `verify --fast`, la CI) imprime sa durée au bout
de sa ligne, puis le total. Celui des étapes rapides a un seuil,
`[verify] fast_max_seconds`, 300 secondes par défaut : au-delà de cinq
minutes d'attente, un sous-agent perd le cache de sa conversation. Quand
un passage les lance toutes et qu'elles passent (`verify --fast`, la fin
de tour, le hook avant envoi), il garde leur total et la plus longue dans
un fichier local, sous `.socle/trace/`. Au-delà du seuil, un
avertissement, jamais un échec, donne le total, le seuil et l'étape la
plus longue avec sa durée : au bout de ce passage, sur la ligne d'une
vérification qui ne relance pas les étapes, et dans l'état, tant que le
dernier passage complet dépasse le seuil. Le hook avant envoi laisse
partir le push et le dit sur sa sortie d'erreur, que l'agent lit dans
celle de `git push`. La fin de tour ne bloque pas pour lui : elle le dit
à l'humain, et à l'agent seulement quand elle bloque déjà pour une autre
raison ; l'agent le lit sinon au `verify --fast` suivant et dans l'état.
Un passage où une étape échoue ne remplace pas le précédent. La CI
imprime les durées, sans seuil : elle tourne sur une autre machine.
Baisser le seuil est libre ; le relever, ou y écrire `nan`, qu'aucun
ordre ne compare, exige une demande validée.

**Un projet adopté** (installé avec `--adoption`). Les contrôles qui
échouaient sur l'existant sont nommés dans `[adoption] warn_only`, et les
constats présents à l'installation dans `[adoption.tolerated]`, par
contrôle, sous une clé qui ne dépend ni du numéro de ligne ni de la
langue : le fichier et ce que le constat cite (`"LISEZMOI.md — absent.md"`
pour un lien mort). Ceux-là restent en avertissement ; tout constat
nouveau de ces contrôles échoue. Renommer un fichier qui en porte se règle
dans la pull request qui le renomme : le contrôle échoue et dit de renommer
la clé dans la liste, de l'ancienne à la nouvelle, ce que le cliquet laisse
faire dans la même pull request. Seul un renommage que git reconnaît se
suit : commiter le renommage seul, avant de modifier le fichier ; à défaut,
corriger le constat, ou le tolérer par une demande validée. Un constat que
la CI ne voit plus se signale : le retirer de la liste est libre, en
ajouter un exige une demande validée qui le cite. L'état dit, par contrôle, combien de constats
l'adoption tolère encore ; à zéro, le contrôle peut sortir de `warn_only`.
Un projet adopté avant cette règle reçoit sa liste à la mise à jour du
moteur, faite des constats de la branche par défaut (ceux nés sur la
branche ne sont pas tolérés, l'installeur les nomme) ; tant qu'elle manque, l'état dit le contrôle désarmé en entier.
Quand l'adoption ne trouve aucun contrôle en échec, ou que la liste
`warn_only` est vide à la mise à jour, l'installeur le dit d'une ligne :
rien à inscrire.

**Un journal d'avant le socle.** Un projet qui tenait déjà un journal
dont les entrées ont la forme de celles du socle (`J-`, une date et une
lettre) le migre dans `memory/journal/`, chaque entrée dans le fichier
de son mois, au format du socle ; dès l'installation, une entrée
nouvelle ne s'écrit qu'au journal du socle. Une entrée importée garde
son identifiant, sauf un jour où le journal du socle a déjà les siennes
(celui de l'installation, qui l'ouvre) : les entrées importées de ce
jour y prennent, dans leur ordre, les lettres qui suivent la dernière
du journal du socle, et leurs citations se récrivent dans le même
commit, sauf dans le journal, les décisions et les demandes, qui ne se
récrivent pas : l'entrée du journal qui consigne la migration y donne
la correspondance des lettres de ce jour. L'ancien journal se retire
dans ce commit, ou n'y garde qu'un renvoi vers `memory/journal/` : ses
titres d'un jour renuméroté désigneraient sinon d'autres entrées. En
attendant la migration, le contrôle des références refuse l'identifiant
d'une entrée ancienne, sauf un jour qui se heurte, où il désigne en
silence l'entrée du socle de même lettre : les citations que le projet
a déjà sont tolérées à l'adoption (paragraphe précédent), et celles que
la migration résout se retirent ensuite de la liste ; une citation
nouvelle, quel que soit son jour, la nomme sans la forme d'un
identifiant, par son fichier, sa date et sa lettre (« l'entrée B du
3 mars 2026 de l'ancien journal »).

**Un sous-dossier travaillé par d'autres agents.** Quand d'autres sessions
d'agents, qui n'ont ni les hooks ni les règles du socle, travaillent un
sous-dossier sur leurs propres branches (une interface, par exemple),
le déclarer tiers dans les garde-fous (`[thirdparty] paths = ["ui/**"]`),
puis l'approuver : c'est un assouplissement
(`python3 .socle/socle approve --keys thirdparty.paths --text "<raison>"`).
Un commit qui ne touche que des chemins tiers n'est alors pas un commit du
projet : déclarer un chemin tiers dispense aussi de la trace des hooks les
commits qui ne touchent que lui ; une dispense de test qu'il porte n'est ni
jugée ni lue (elle ne dispense aucune fonction du projet), et un correctif
n'y est qu'averti. Leurs pull requests passent le travail de CI du socle.
Rien n'est à régler côté GitHub, ni au hook avant push, que ces sessions
n'ont pas : le travail de CI du socle, exigé ou non avant fusion, les juge
ainsi. Deux limites, chacune avec son réglage :

- un commit qui touche aussi un fichier du projet (la mémoire, la
  documentation, un fichier à la racine) est jugé en entier, et refusé sans
  la trace des hooks : ces sessions restent dans leur sous-dossier ;
- les capacités de l'adaptateur (compilation, tests) tournent comme il les
  déclare : si elles couvrent le sous-dossier, il doit compiler et ses
  tests passer, ou l'humain l'exclut des sources de l'adaptateur, fichier
  protégé.
