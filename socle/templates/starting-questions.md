<!-- socle: couche=demandes zone=publique -->
# {id} — Les questions de départ du projet

> date : {date} · origine : `socle init`

## Décision demandée

Répondre aux {n} questions de départ ci-dessous, ou accepter tous leurs
défauts d'un mot.

## Contexte

Le socle vient d'être posé sur ce projet, et son initialisation part de
{entrees}. L'agent n'invente rien : il ne demande pas ce qu'il peut lire dans
le dépôt (le langage, les outils de test), seulement ce qu'il ne peut pas
deviner, comme le but du projet, la confidentialité ou le niveau
d'autonomie. Les questions sont groupées ici, au début, et plafonnées à
{plafond} ; les moins urgentes vont au backlog. Chacune a un défaut, et dit
ce que ce défaut change.

## Questions

{questions}

## Éléments cités

{elements}

## Où regarder

{lien}

Ce qu'il faut vérifier : que chaque défaut te convient, ou la réponse à
mettre à sa place.

## Options

- **Accepter tous les défauts** : effort nul ; risque faible, chaque défaut
  reste « supposé » et se corrige plus tard ; réversible.
- **Répondre question par question** : quelques minutes ; le départ suit ce
  que tu veux ; réversible.
- **Refuser les défauts** : effort nul maintenant ; risque, le départ attend
  ces réponses, chaque question restant ouverte ; réversible.

## Conséquences

Si tu valides les défauts, l'agent les applique, marqués « supposés ». Si tu
réponds autrement, l'agent consigne ton texte exact et l'applique. Si tu
refuses les défauts (`refuser`), chaque question reste ouverte, au backlog.
Si les questions ne se comprennent pas (`contexte-insuffisant`), l'agent
les réécrit. Sans réponse, les défauts s'appliquent, marqués
« supposés », et la demande reste en file pour que tu y reviennes.

## Recommandation

Lire les défauts et ne répondre qu'à ce qui ne te convient pas. Vérifié : ce
que l'audit du dépôt a lu, s'il y en avait un. Supposé : tout le reste.

## Réponses possibles

- `valider` — tous les défauts s'appliquent, marqués « supposés ».
- `reponses` — le texte de ta réponse donne les réponses, question par question ; l'agent le consigne tel quel.
- `refuser` — aucun défaut ne s'applique : chaque question reste ouverte, au backlog.
- `contexte-insuffisant` — la demande revient à l'agent, qui la réécrit en une demande qui la remplace.
