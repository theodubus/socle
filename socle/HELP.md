# Le socle, côté humain : guide d'utilisation

Ce guide suit le parcours de l'humain dans un projet équipé du socle, de la
fin de l'installation à l'usage courant. Les commandes se lancent à la
racine du projet : `python3 .socle/socle <commande>` ; ce guide s'affiche
par `python3 .socle/socle help`. Sans terminal, en session cloud, l'agent
les lance : il suffit de les lui demander.

Le parcours en bref :

1. **Démarrer**, une fois : décrire le projet, donner ses outils à
   l'agent, pousser, protéger la branche.
2. **Travailler avec l'agent** : lui confier des tâches, lire ses
   récapitulatifs.
3. **Répondre à l'agent** quand une décision revient à l'humain.
4. **Les gestes occasionnels** : approuver ses propres changements, mettre
   à jour, agir là où l'agent ne peut pas.

## 1. Démarrer

En session cloud, l'agent installe le socle depuis son dépôt public, qui se
clone sans être ajouté à la session. La session qui installe a démarré
avant le socle, donc sans ses hooks : elle pousse sa branche et ouvre une
pull request. Une fois celle-ci fusionnée, le travail continue dans une
session neuve, qui part de la branche par défaut et reçoit l'état dès son
démarrage. Une session qui ajoute un second dépôt ne se reprend pas : à
deux dépôts, elle redémarre hors de la racine du projet, sans les hooks de
l'agent.

Juste après l'installation :

1. Décrire le projet :
   `python3 .socle/socle init --brief <document> --repo`. Le document de
   cadrage est archivé ; `--repo` relève ce que le dépôt contient déjà. Sans
   document, `--repo` seul ; dans un dépôt vide, sans option.
2. Donner à l'agent les outils que la CI installe pour l'adaptateur
   (pytest, par exemple), que l'installeur cite avec leurs commandes. En
   session cloud, le conteneur repart de zéro à chaque session : le hook de
   démarrage du socle les installe dans chaque session neuve ; seule la
   session qui installe le socle les installe elle-même. Tant que le projet
   n'a aucun fichier source, `verify` ne lance ni compilation ni tests, et
   le dit.
3. Commiter et pousser.
4. Protéger la branche par défaut sur GitHub (réglages du dépôt,
   « Rules ») : exiger la CI « Socle — verify, contrôles, auto-test » avant
   toute fusion. Sans cela, une CI rouge n'empêche pas de fusionner. La
   revue des propriétaires du code ne s'y ajoute que si un autre humain
   relit : l'auteur d'une pull request ne peut pas l'approuver, et l'agent
   ouvre les siennes au nom de l'humain. Dans les réglages généraux, cocher
   « Automatically delete head branches » : une branche fusionnée s'efface
   alors seule. L'état signale les autres : celles que la branche par
   défaut contient déjà, à supprimer, et celles qui ne bougent plus depuis
   une semaine sans avoir été fusionnées, à livrer ou à supprimer. Si une
   telle branche garde seule un commit que la mémoire cite, l'état donne
   d'abord la commande qui l'étiquette : sans elle, la CI ne le
   retrouverait plus.
5. Ouvrir l'agent dans le projet. Il lit l'état au démarrage, puis donne le
   lien des questions de départ, une demande que `socle init` a posée : y
   répondre dans la conversation, `valider` pour appliquer tous les
   défauts, ou une réponse par question.

Si le projet avait déjà son propre hook `SessionStart`, l'installeur le
signale : le retirer de `.claude/settings.json`, sans quoi chaque session
reçoit deux états.

## 2. Travailler avec l'agent

Les tâches se confient à l'agent comme d'habitude. Au démarrage de chaque
session, il reçoit l'état du projet ; il travaille, et les contrôles le
vérifient à chaque étape.

**Planifier.** Depuis le cadrage, l'agent écrit une spécification et une
architecture courtes dans la documentation du projet : chaque choix en
ADR, chaque question ouverte en demande (en questions de cadrage quand
votre intention manque, section 3), chaque tâche en sujet du backlog,
avec ce qu'elle attend (`après` : un autre sujet, ou une demande jusqu'à
sa réponse) et ce qui la rend faite (une section « Fait quand », en cases
à cocher, toutes cochées avant de la clore), groupée en jalons. Il soumet
chaque document en demande. Il suffit de le lui demander ; l'état donne
ensuite le prochain jalon et les sujets prêts.

**Spécifications et cas d'essai.** Le projet déclare où vivent ses
spécifications (`[specs] paths` des garde-fous) : l'état vous signale
celle qu'aucune demande ne vous a soumise. Il déclare aussi ses fichiers
de cas (`[tests] case_paths`), des données où ses tests lisent leurs
résultats attendus : y ajouter un cas est libre, mais changer ou retirer
un cas existant exige votre validation, comme une valeur attendue écrite
dans un test.

**Prioriser.** Un sujet peut porter `priorité : haute` ou
`priorité : basse` ; la normale ne s'écrit pas. Le dire à l'agent suffit,
et il ne change pas une priorité que l'humain a donnée. Les sujets prêts
se rangent par priorité, et ceux de priorité basse restent à part :
l'agent ne les prend que s'ils sont commodes, et le dit en annonçant le
lot.

**Enchaîner.** Tant que rien ne revient à l'humain, l'agent enchaîne les
sujets prêts sans attendre de message. Avant de s'y lancer, il annonce le
lot qu'il va traiter : l'arrêter ou le réorienter se fait d'un message.
Il s'arrête à la fin du lot, ou dès qu'une décision revient à l'humain.

**Livrer.** Par défaut, l'agent fait tout sur une branche de
développement et garde une seule pull request ouverte, à laquelle chaque
lot fini s'ajoute : la fusionner quand on veut, une fois sa CI verte. Une
pull request par sujet, chacune à fusionner, se choisit aux questions de
départ, ou plus tard en le disant à l'agent, qui l'écrit en fait de la
mémoire.

Chaque intervention de l'agent qui a agi se termine par deux lignes :

- **« Pour toi : »** — ce qui revient à l'humain : une demande à lire, une
  action à faire, ou rien ;
- **« Ensuite : »** — la suite prévue, et ce que l'agent attend.

Chaque point de « Pour toi » se comprend seul : ce que c'est, pourquoi,
et ce que change votre réponse.

À tout moment, `python3 .socle/socle state` donne l'état du projet : le
commit, la CI, le backlog et ce qui vient ensuite (le prochain jalon, les
sujets prêts), les demandes en attente, ce qui revient à l'humain. La mémoire se lit dans `memory/`.

Une procédure du projet qui revient, l'agent l'écrit en skill dans
`.claude/skills/`, avec une entrée au journal : il la charge ensuite à la
demande au lieu de la reconstituer. Ses skills sont contrôlés comme le
reste ; ceux du socle, posés par l'installeur, sont protégés.

## 3. Répondre à l'agent

**Une demande.** Quand une décision revient à l'humain (relâcher un seuil,
supprimer un test, une décision coûteuse à défaire, une action
irréversible), l'agent écrit une demande et en donne le lien. Elle se lit
seule et se termine par la liste des réponses possibles. Répondre dans la
conversation ; l'agent consigne la réponse mot pour mot.

- Les réponses de base sont les mêmes dans toute demande : `valider` (la
  recommandation), `refuser`, `contexte-insuffisant` ; une demande de choix
  y ajoute ses options.
- `valider` est la seule réponse qui autorise un geste réservé à l'humain.
- `contexte-insuffisant` renvoie la demande à l'agent, qui la réécrit.
- Depuis un terminal :
  `python3 .socle/socle answer D-NNNN <réponse> --text "<texte>"`.

**Une question en séance.** Une question courte, que l'agent pose dans
le texte de sa réponse, se répond dans la conversation ; l'agent la
consigne aussitôt, mot pour mot, comme une demande. Ce qui demande du
contexte, approuver un document compris, arrive en demande, avec son
lien ; jamais dans le widget de questions de l'agent, que le hook refuse.

**Des questions de cadrage.** Quand la spécification d'un sujet dépend
d'une intention que la mémoire ne dit pas, l'agent pose des questions
ouvertes, chacune avec son hypothèse, dans une demande dont il donne le
lien. Y répondre librement, en un ou plusieurs messages (`reponses`), ou
`valider` ses hypothèses : il consigne le texte tel quel, puis soumet la
spécification qui en découle. Lui dire « pose-moi tes questions sur ce
sujet » suffit à en demander.

**Une relecture avant publication**, si la politique l'exige : l'agent
montre ce qui part vers le dépôt public, l'humain donne son accord dans la
conversation. Depuis un terminal : `python3 .socle/socle reviewed --by <nom>`.

## 4. Les gestes occasionnels

**Approuver ses propres changements protégés.** La politique, les seuils,
l'adaptateur, les hooks et la CI sont protégés : un commit qui les change
sans validation est refusé. Quand le changement vient de l'humain :
`python3 .socle/socle approve --text "<raison>"`, puis commiter. Cette
commande est réservée à l'humain.

**Faire ce que l'agent ne peut pas faire.** Pousser sur la branche par
défaut, publier, régler un service, supprimer une branche distante, poser
une étiquette (en session cloud, l'agent ne pousse que sa propre branche) : l'agent l'inscrit au backlog avec son
mode d'emploi, et l'état le liste dans « ce qui revient à l'humain ».

**Commiter soi-même.** Les mêmes contrôles s'appliquent : une fonction
publique ajoutée est nommée par un test, ou dispensée dans le message du
commit (`Dispense-test: f — <raison>`) ; un correctif apporte un test qui
échoue sur le commit précédent.

**Mettre à jour le socle.** Relancer la commande d'installation depuis un
clone à jour du moteur (`git clone --depth 1
https://github.com/theodubus/socle /tmp/socle`). Les fichiers du projet ne sont jamais écrasés ; le
diff de la politique est montré. Approuver ensuite les fichiers protégés
changés (`socle approve`), puis commiter. En session cloud, sans terminal,
l'agent pose une demande qui cite chaque fichier protégé changé avec son
empreinte, et l'humain la valide dans la conversation. Si la branche par
défaut exige la CI du socle, l'agent commite et pousse ces fichiers dès la
demande poussée : la CI reste rouge jusqu'à la validation, et l'humain les
lit dans la pull request avant de répondre. Le dépôt public du
moteur se clone sans être ajouté à la session. Une mise à jour garde les
garde-fous du projet tels quels, et nomme les réglages apparus depuis dans
le gabarit : l'agent y déclare ceux qui servent au projet, comme ses
spécifications et ses fichiers de cas (section 2), une fois le moteur
nouveau commité. Avant, la CI juge avec l'ancien moteur, qui ne les connaît
pas et les compte pour un assouplissement.

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
| `tests.regression` | un correctif sans test qui le prouve | écrire ce test ; si sa preuve dépend de l'environnement, valider une demande qui nomme le commit |
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
4. Une action irréversible ou externe est toujours demandée.
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
