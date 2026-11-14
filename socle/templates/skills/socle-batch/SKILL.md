---
name: socle-batch
description: Mener un lot de sujets du backlog, de sa formation à sa livraison : un sous-agent par sujet, la revue sans contexte avant tout push, l'intégration, la CI, la fusion, une session par lot et le passage à la suivante. À utiliser quand l'agent forme ou annonce un lot, à chacune de ses étapes, et à la reprise d'un lot en cours.
---

# Mener un lot

Un lot réunit les sujets prêts qui se traitent ensemble : ceux qui
touchent les mêmes fichiers, le même garde-fou ou les mêmes tests, qu'une
seule revue jugera ensemble. L'agent qui le mène orchestre : il annonce,
délègue, fait relire, intègre et livre ; il n'implémente lui-même qu'un
changement de quelques lignes.

## Former et annoncer

1. Le prochain lot est dans l'état (`prochain lot`). Sinon, le former :
   les prêts du prochain jalon et de priorité haute d'abord, ce qui se
   mène en une session. Il se garde au backlog :
   `python3 .socle/socle new backlog "Lot …"`, puis `forme : lot` et
   `après :` ses sujets et le lot d'avant ; son corps dit ce qui les
   réunit et nomme ce qui n'est pas un sujet.
2. Lire chaque sujet (`python3 .socle/socle show <ID>`), annoncer le lot à
   l'humain (les sujets, leur taille, le jalon servi), et le passer
   `en cours`.
3. En session cloud de Claude Code, armer les réveils (skill
   `socle-resume`).
4. Partir d'une branche de travail propre et poussée.

## Un sous-agent par sujet

Sous Claude Code : outil `Agent`, dans une copie isolée du dépôt
(`isolation: "worktree"`), en arrière-plan ; deux à la fois au plus.
Il n'a pas la conversation : sa consigne se lit seule.

```text
Tu implémentes un sujet de ce dépôt dans ta copie isolée. Les instructions
du projet s'appliquent. Commence par : git merge --ff-only <branche de travail>
Sujet : python3 .socle/socle show <ID>, puis <le choix déjà fait, où regarder, les pièges connus>.
À livrer, en un commit, sans push : le modèle de menace d'un garde-fou ou
la spécification d'une conception pas tranchée, d'abord ; le code et ses
tests ; la documentation touchée ; une entrée de journal ; le sujet coché
et clos si ses critères sont tenus ; python3 .socle/socle verify --fast.
Interdits : pousser, toucher un réveil, écrire un fichier protégé, changer
une valeur attendue ou supprimer un test (le signaler), corriger un défaut
voisin (un sujet au backlog).
Compte rendu : le commit, ce que les tests prouvent, les choix, ce qui reste.
```

**Sans sous-agents**, l'agent mène le lot seul, dans le même ordre : un
sujet après l'autre, un commit chacun, la revue sur le lot entier.

## La revue, avant tout push

Skill `socle-review`, sur le lot commité. Un bloquant retourne au
sous-agent qui a implémenté, s'il répond encore, sinon à un neuf qui
reçoit la consigne et le constat ; le reste va au backlog. Un lot ne part
qu'après la correction de ses bloquants : une fois poussés, une décision,
une entrée de journal et une valeur attendue ne se réécrivent plus.

## Intégrer, pousser, livrer

1. Sur la branche de travail : `git merge --ff-only` de la branche du
   sous-agent si son commit suit la tête, sinon `git merge --squash`, puis
   un commit qui reprend son message. Deux sujets qui ont pris le même
   identifiant : le second intégré se renumérote ; un identifiant que la
   branche par défaut a pris aussi : `python3 .socle/socle renumber <ID>`.
2. Retirer la copie isolée et sa branche ;
   `python3 .socle/socle verify --fast`.
3. Pousser ; ouvrir la pull request s'il n'y en a pas, une seule ouverte.
   Attendre la CI du commit de tête : la ligne « CI » de
   `python3 .socle/socle state` dit `success` (ou `failure`) sur son SHA
   court, jamais sur un commit d'avant. Une attente annoncée a son réveil
   (sous Claude Code, `send_later`) pour y revenir.
4. La fusion est celle que disent les instructions du projet : par
   défaut, l'humain fusionne, et le lot suivant s'ajoute à la même pull
   request. Si elles laissent l'agent fusionner la sienne : CI verte sur
   le commit de tête, revue faite, aucune demande en attente sur son
   contenu, en donnant le commit de tête attendu.
5. Le chantier actif et le journal s'écrivent avant la fusion, dans le
   dernier commit de la pull request, avec la clôture du lot : ses sujets
   clos, il passe `fait`, puis `python3 .socle/socle archive`. Après la
   fusion, la branche locale repart de la branche par défaut et ne se
   pousse qu'avec le premier commit du lot suivant : poussée sans rien de
   plus, elle recréerait la branche distante que la fusion a supprimée.

## La consommation

Chaque pas de l'orchestration (lancer un sous-agent, recevoir son compte
rendu, intégrer, regarder la CI) relit toute la conversation, et une
reprise après plus d'une heure d'arrêt la relit au prix fort.

- Un lot par session : la conversation qui orchestre reste courte.
- Deux sous-agents à la fois au plus ; un seul au-delà de 75 % de la
  semaine ; aucun au-delà de 85 % de la semaine ou de 60 % de la fenêtre
  de cinq heures : finir le pas en cours, puis changer de session. Sous
  Claude Code en session cloud, les deux fenêtres se lisent dans
  `list_events` (`kinds: ["rate_limit_event"]`, `utilization` de
  `five_hour` et de `seven_day`), avant chaque lancement et à chaque
  compte rendu.
- Une limite proche change l'ordre des sujets, jamais la profondeur du
  travail sur l'un d'eux : un sujet qui demande plus de réflexion se
  commence quand même, et se finit après la levée.
- Un sous-agent ne se reprend pas après plus de cinq minutes d'arrêt : un
  neuf reçoit la consigne et les constats.
- Une attente de plus d'une heure (une CI longue, une réponse de
  l'humain, la nuit) ne se fait pas dans une conversation longue.

## Changer de session

Quand le lot est livré et que la fenêtre de cinq heures ne permet pas
d'en mener un autre entier, ou qu'une attente de plus d'une heure
s'annonce. Ranger d'abord, pour qu'une session neuve reparte du dépôt
seul :

1. rien qui ne vive que dans le conteneur : tout est poussé, et un commit
   pas encore relu part en correctif (`git format-patch`) dans un dossier
   de passation du dépôt, retiré quand le lot s'intègre ;
2. les copies isolées et leurs branches retirées ;
3. le chantier actif, écrit avant la fusion, dit le lot et ce qui attend
   (un compte rendu, une CI, une demande) ;
4. en session cloud, les réveils retirés.

Puis dire à l'humain qu'il faut changer de session, et pourquoi, avec le
prompt de la suivante dans un bloc à copier :

```text
Reprends le travail de ce dépôt, en session neuve.
Avant tout : lis l'état que le démarrage injecte ; une ligne « !! coupé »
dit ce qui y manque et où le lire. Puis le chantier actif, et applique-les.
Le lot : <le lot de l'état, ses sujets dans l'ordre>, selon le skill socle-batch.
Ce qui attend : <un compte rendu, une CI, une demande> | rien.
```
