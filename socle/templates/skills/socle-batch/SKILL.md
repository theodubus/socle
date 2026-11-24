---
name: socle-batch
description: Mener un lot de tâches du backlog, de son annonce à sa livraison. À utiliser quand l'agent forme ou annonce un lot, à chacune de ses étapes, et à sa reprise.
---

# Mener un lot

Un lot réunit les tâches prêtes qu'une seule revue juge : celles qui
touchent les mêmes fichiers, le même garde-fou ou les mêmes tests.
L'agent qui le mène orchestre ; il n'implémente lui-même qu'une petite
tâche.

## Former et annoncer

1. Le prochain lot est dans l'état (`prochain lot`). Sinon, le former
   sur tout le backlog ouvert, sans le demander : les tâches prêtes
   auxquelles sa règle s'applique, du prochain jalon et de priorité haute
   d'abord ; un besoin à découper reçoit d'abord ses tâches ; une tâche
   qui change un comportement nomme le test qui affirme le contraire, sa
   demande posée aussitôt, avant le lot ; le reste va
   au prochain lot pas en cours dont la règle s'applique, et le récap dit
   chaque placement. Il se garde au backlog : `python3 .socle/socle new
   batch "Lot …"`, puis `après :` le lot d'avant et ses tâches ; son corps
   dit ce qui les réunit. Un ensemble qu'une session ne mène pas se forme
   en jalon, ses lots dessous.
2. Lire chaque tâche (`python3 .socle/socle show <ID>`) et estimer le
   coût du lot : s'il ne tient pas dans ce qui reste de la fenêtre, le
   découper, commencer par un lot plus petit ou attendre la remise à zéro.
   Annoncer le lot à l'humain (les tâches, leur taille, le jalon servi, le
   coût estimé), et le passer `en cours`.
3. En session cloud, armer les réveils (skill `socle-resume`).
4. Partir d'une branche de travail propre et poussée.

## Un sous-agent par tâche

Sous Claude Code : outil `Agent`, dans une copie isolée
(`isolation: "worktree"`), en arrière-plan ; deux à la fois au plus.
Sa consigne se lit sans la conversation.

```text
Tu implémentes une tâche de ce dépôt dans ta copie isolée. Les instructions
du projet s'appliquent. Commence par : git merge --ff-only <branche de travail>
Tâche : python3 .socle/socle show <ID>, puis <le choix déjà fait, où regarder, les pièges connus>.
À livrer, en un commit, sans push : le modèle de menace d'un garde-fou ou
la spécification d'une conception pas tranchée, d'abord ; le code et ses
tests ; la documentation touchée ; une entrée de journal ; la tâche cochée
et close si ses critères sont tenus ; python3 .socle/socle verify --fast.
Interdits : pousser, toucher un réveil, écrire un fichier protégé, changer
une valeur attendue ou supprimer un test (le signaler), corriger un défaut
voisin (un besoin au backlog).
Économie : lire ce qui sert, pas les fichiers entiers ; pas de suite complète relancée sans raison.
Compte rendu : ton modèle, le commit, ce que les tests prouvent, les choix, ce qui reste.
```

**Une petite tâche**, moins de 150 lignes de code et de tests (seuil
provisoire, à mesurer), s'implémente dans la session qui orchestre, sauf
si elle touche un garde-fou ou un format que d'autres parties du projet
lisent. **Sans sous-agents**, l'agent mène le lot seul : une tâche après
l'autre, un commit chacune, la revue sur le lot entier.

## La revue, avant tout push

Skill `socle-review`, sur le lot commité, et son tri des constats. Un
bloquant retourne à qui a implémenté, s'il répond encore, sinon à un
sous-agent neuf, avec la consigne et le constat : un sous-agent arrêté
depuis plus de cinq minutes ne se reprend pas. Un lot ne part qu'après
la correction de ses bloquants : une fois poussés, une décision, une
entrée de journal et une valeur attendue ne se réécrivent plus.

## Intégrer, pousser, livrer

1. Sur la branche de travail : `git merge --ff-only` de la branche du
   sous-agent si son commit suit la tête, sinon `git merge --squash`, puis
   un commit qui reprend son message. Un identifiant pris deux fois :
   `python3 .socle/socle renumber <ID>` sur le second.
2. Retirer la copie isolée et sa branche ;
   `python3 .socle/socle verify --fast`.
3. Pousser ; ouvrir la pull request s'il n'y en a pas, une seule ouverte.
   Attendre `success` sur le SHA court du commit de tête, ligne « CI » de
   `python3 .socle/socle state`. Une attente annoncée a son réveil en
   session cloud (`send_later`) ; ailleurs, `Ensuite :` le dit, et
   l'humain relance l'agent.
4. Qui fusionne : par défaut l'humain, et le lot suivant s'ajoute à la
   même pull request ; l'agent, la sienne, si la politique le permet : CI
   verte sur le commit de tête, qu'il donne, revue faite, aucune demande
   en attente sur son contenu. Il attend de même les workflows que la
   fusion lance sur la branche par défaut ; le récap dit s'ils ont réussi.
5. Le chantier actif et le journal s'écrivent avant la fusion, dans le
   dernier commit de la pull request, avec la clôture du lot : ses tâches
   closes, il passe `fait`, puis `python3 .socle/socle archive` ; une tâche
   que sa revue ouvre rejoint le prochain lot dont la règle s'applique,
   sinon un lot neuf dans le jalon de son besoin ; le récap
   de la clôture colle la sortie de `python3 .socle/socle roadmap` dans un
   bloc de code. Après la fusion, la branche locale repart de la branche
   par défaut et ne se pousse qu'avec le premier commit du lot suivant :
   seule, elle recréerait la branche distante.

## La consommation

- Un lot par session : la conversation qui orchestre reste courte.
- Les coûts se mesurent : l'utilisation de chaque fenêtre, avant chaque
  lancement et à chaque compte rendu (skill `socle-resume`). La clôture note au journal le coût de chaque
  sous-agent, du relecteur, de chaque demande et du rangement : celui
  d'un lot s'estime sur ces mesures.
- Un seul sous-agent au-delà de 75 % de la semaine. Un sous-agent se
  lance si ce qui reste de chaque fenêtre couvre son coût mesuré et celui
  du rangement ; sans mesure, aucun au-delà de 85 % de la semaine ou de
  60 % de la fenêtre de cinq heures. Le rangement commence au plus tard à
  dix points d'une limite : finir le pas en cours, puis changer de session.
- L'agent ne compacte pas lui-même : il écrit la mémoire (chantier actif,
  journal), puis le demande à l'humain (`/compact`), à la fin d'un lot
  si l'humain garde la session, et avant toute attente qui peut passer
  l'heure sans changer de session. Près d'une limite, le seuil plus haut
  prime : changer de session. Après la pause, il est trop tard. Sans
  l'humain pour compacter, l'agent ne l'attend pas : il change de session.
- Une limite proche change l'ordre des tâches, jamais la profondeur du
  travail (une tâche qui demande plus de réflexion se commence quand
  même) ni le modèle : celui que demande la qualité du travail, jamais
  un moindre pour tenir une limite : une limite retarde un lot, elle ne
  l'allège pas. Entre ceux qui le font aussi bien, celui qui consomme le
  moins de la limite par jeton ; l'humain choisit celui de la session,
  sur le conseil de l'agent. Celui que fixent les instructions du projet
  prime. Un sous-agent reçoit le sien explicitement à son lancement
  (`model`), jamais Fable sauf si l'humain le veut, la dernière version
  de sa famille (un alias qui en désigne une plus ancienne : sans
  `model`, il hérite de la session ; sinon, le dire à l'humain), nommé au
  récap.

## Changer de session

À la fin du lot, près d'une limite ou avant une attente de plus d'une
heure (le moment : skill `socle-handoff`). Ranger d'abord :

1. le chantier actif dit le lot et ce qui attend, le journal la
   passation ;
2. les copies isolées, leurs branches et, en session cloud, les réveils
   retirés ;
3. tout est poussé ; un commit non relu part en correctif
   (`git format-patch`) dans un dossier de passation du dépôt, retiré à son
   intégration. Plus rien ne se pousse ensuite.

Puis le skill `socle-handoff` : selon le mode, il programme la session
suivante, ou donne le prompt de la suivante à copier.
