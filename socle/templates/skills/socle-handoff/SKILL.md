---
name: socle-handoff
description: Passer la main à une session neuve, à la fin d'un lot, près d'une limite d'usage ou avant une longue attente — la programmer soi-même ou donner le prompt à copier, selon le mode, avec la garde contre le travail en double. À utiliser après le rangement de socle-batch, quand l'humain change de mode, et quand une session part d'un prompt de passation.
---

# Passer la main à une session neuve

Une session ne mène qu'un lot. Quand elle s'arrête, la suivante repart du
dépôt seul, sur un prompt de passation que `python3 .socle/socle handoff
prompt` écrit avec sa garde. Les heures du prompt sont en UTC ; celles que
lit l'humain, à son heure.

## Les deux modes

- **Session programmée**, par défaut : l'agent crée la session suivante
  et programme son prompt.
- **Prompt à copier** : l'agent donne le prompt dans son récap, et
  l'humain ouvre la session lui-même ; le mode de qui a plusieurs comptes
  ou veut garder la main.

Le mode est celui que dit une consigne du chantier actif ; sans elle, la
session programmée. L'humain en change en le disant : l'agent écrit la
consigne au chantier actif, et son texte exact au journal. Passer au
prompt à copier annule ce qui est programmé, la tâche supprimée
(`delete_trigger`) et la session créée archivée (`archive_session`), et
le dit, avec le lien de chaque session annulée.

Le prompt à copier s'applique aussi, le récap disant pourquoi, hors d'une
session cloud de Claude Code (sans `create_session` ni `create_trigger`),
et à une borne.

## Le moment

| Le moment | L'heure de la session suivante |
| --- | --- |
| Lot livré | tout de suite : la minute qui suit |
| Rangement à dix points d'une limite (`socle-batch`) | la remise à zéro de cette fenêtre, plus cinq minutes |
| Avant une attente de plus d'une heure (une CI longue, une heure donnée) | la fin de l'attente |

Une session ne part jamais sur une fenêtre au-delà de son seuil, 15 % de
la fenêtre de cinq heures et 75 % de la semaine : son heure recule alors
à la remise à zéro de cette fenêtre, plus cinq minutes. Un lot coûte une
bonne part de la fenêtre : lancé sur une fenêtre entamée, il serait coupé
en route. L'utilisation et les remises à zéro se lisent comme pour les
réveils (skill `socle-resume`).

## Les bornes

Rien ne se programme, et le récap donne le prompt à copier :

- quand le prochain lot n'a aucune tâche prête dans l'état, parce
  qu'une décision revient à l'humain ou que rien n'est prêt ; une
  demande en attente qui ne le bloque pas ne l'arrête pas ;
- après deux lots menés sans message de l'humain, le lot en cours
  compris ;
- quand la plateforme refuse de créer la session.

La chaîne (`--chain`) compte ces lots : 0 si l'humain a écrit dans la
session ; sinon, celle de son prompt de passation, plus un. Le prompt à
copier porte 0. Avec `--scheduled`, la commande refuse le prompt aux deux
premières bornes, en le disant.

## Programmer

D'abord le rangement (skill `socle-batch`, « Changer de session ») :
l'entrée du journal qui dit la passation, sans les liens que seul le récap
donnera ; les réveils de la session retirés ; tout poussé. Plus rien ne
se pousse ensuite : la garde nomme la tête distante, et le prompt
programmé ne se récrit plus. Un commit nécessaire après annule la
passation (la tâche supprimée, la session archivée), qui se refait.

1. Le prompt, le lien de cette session (celui que portent ses commits)
   et ce qui attend donnés :

```sh
python3 .socle/socle handoff prompt --scheduled --chain <n> --session <lien> --waiting "<ce qui attend>"
```

2. `create_session`, sans `prompt` : `source_url` l'adresse du dépôt ;
   `source_revision` la branche que la garde nomme (`--ref`, sans
   `origin/`) ; `outcome_branch` la branche de travail, sans quoi la
   session neuve n'a pas où pousser ; `model` celui de cette session ;
   `effort` le sien, qui ne s'hérite pas (refusé, l'appel se refait sans
   lui) ; `title` « Passation — <lot> — part le <jour> à <heure de
   l'humain> » ; `tags` `["passation"]`.
3. `create_trigger` : `name` « Passation — <dépôt> » ;
   `persistent_session_id` la session créée ; `run_once_at` l'heure du
   moment ; `prompt` le texte de l'étape 1 ; `initiation` `own_followup`.
4. Le récap donne le lien de la session créée, son heure et comment
   l'arrêter ; `Ensuite :` le dit.

Si un appel échoue, la session créée s'archive, et le prompt à copier
remplace la passation, le récap disant pourquoi.

## Le prompt à copier

Dans un bloc à copier du récap, avec la raison du changement de session :

```sh
python3 .socle/socle handoff prompt --session <lien> --waiting "<ce qui attend>"
```

Collé tard, sa garde le juge de même.

## La session neuve

Son prompt commence par `git fetch` et la garde (`socle handoff check`).
Refusée, elle ne fait rien d'autre que le dire, avec sa raison, dans son
dernier message. Acceptée, elle se place sur la référence que la garde
nomme : son clone date de sa création, pas de son prompt.

## La pull request ouverte

Une session partie d'un prompt de passation que la garde accepte,
programmé ou collé par l'humain, continue la pull request ouverte de sa
branche sans la demander : elle devient la sienne. Elle la fusionne si
la politique le permet à l'agent, aux conditions de `socle-batch` ;
sinon l'humain la fusionne.

## Voir et arrêter

La session créée paraît aussitôt dans la liste des sessions de
l'humain, sous son titre, prête à relire tant qu'elle attend son prompt.
Son dernier message dit ce qu'elle a fait, pourquoi la chaîne s'arrête
ou ce que la garde a refusé, et ce qui revient à l'humain.

L'humain l'arrête en écrivant « arrête » dans la session qui l'a
programmée, tant qu'elle tourne ; ensuite, en changeant de mode dans une
session du projet, ou en supprimant sa tâche de la liste des tâches
programmées de son compte et en archivant la session. Une session qu'il
ouvre pendant qu'une passation attend la lui dit au premier tour (skill
`socle-resume`), et ne l'annule qu'à sa demande.

## L'ancienne session réveillée

Un tour en échec ou un conteneur redémarré dans la session créée peut
rendre un tour à celle qui l'a programmée. Elle le dit en une ligne et
ne fait rien d'autre.

Les réveils de `socle-resume` restent, dans les deux modes : une session
coupée avant d'avoir rangé reprend à la levée.
