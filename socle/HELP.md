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
   défaut ou la branche de travail poussée contiennent déjà, à supprimer,
   et celles qui ne bougent plus depuis
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

**Faire relire.** Avant de livrer un lot qui change du code, une
spécification ou un test, l'agent le fait relire par un relecteur sans
contexte, qui cherche à le prendre en défaut : ce qui casse, ce qu'aucun
test ne prouve, ce qui contredit une décision. L'agent corrige chaque
constat fondé et écarte les autres ; son récap dit combien.

**Livrer.** Par défaut, l'agent fait tout sur une branche de
développement et garde une seule pull request ouverte, à laquelle chaque
lot fini s'ajoute : la fusionner quand on veut, une fois sa CI verte. Une
pull request par sujet, chacune à fusionner, se choisit aux questions de
départ, ou plus tard en le disant à l'agent, qui l'écrit en fait de la
mémoire.

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
seule, même après des semaines loin du projet : son contexte commence par
le projet, le chantier en cours et la question. L'agent qui a des
sous-agents la fait relire à froid, par l'un d'eux qui n'a que son texte,
avant de vous la poser, et son récap en donne le bilan. Elle se termine par
la liste des réponses possibles. Répondre dans la
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
commande est réservée à l'humain. L'agent, lui, n'écrit jamais dans un
fichier protégé, sauf pour le remettre à son état du dernier commit quand
il l'a changé par erreur (D-0098), hors des réglages de Claude Code, que
l'humain garde pour lui : `git restore --source=HEAD --staged
--worktree -- <chemin>` ou `git checkout HEAD -- <chemin>`, chaque chemin
écrit en toutes lettres, ou `rm <chemin>` pour un fichier apparu sous un
chemin protégé que git ne suit pas. Le reste lui est refusé : un autre
commit, avec ou sans `--`, un dossier entier, un motif ou une variable du
shell, des chemins lus dans un fichier, une variable ou un préfixe devant
`git`, une redirection vers un autre fichier protégé, et un fichier que
cite, lui ou son dossier, une demande en attente ou validée dont ce
qu'elle approuve n'est pas commité. Le risque accepté : effacer une
modification de l'humain dans l'arbre de travail qu'il n'a ni commitée ni
soumise par une demande.

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
diff de la politique est montré. Le hook de l'agent refuse l'installeur visé
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
4. Suis les étapes « Et maintenant » de l'installeur, dont la demande qui cite les fichiers protégés changés, puis pousse et ouvre la pull request.
5. Dis-moi ce qui me revient.
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
