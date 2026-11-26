---
name: socle-handoff
description: Passer la main à une session neuve, à la fin d'un lot, près d'une limite d'usage ou avant une longue attente — écrire la passation dans la mémoire, puis programmer la session suivante ou dire à l'humain de demander la reprise, selon le mode, avec la garde contre le travail en double. À utiliser après le rangement de socle-batch, quand l'humain change de mode, et quand le premier message d'une session neuve demande de reprendre.
---

# Passer la main à une session neuve

Une session enchaîne les lots que son budget permet (skill
`socle-batch`). Quand elle s'arrête, elle écrit sa passation dans la
mémoire, la commite et la pousse ; la session suivante, d'un compte
comme d'un autre, la trouve et juge sa garde. Les heures de la passation
sont en UTC ; celles que lit l'humain, à son heure.

## Les deux modes

- **Session programmée**, par défaut : l'agent crée la session suivante
  et programme son réveil.
- **Prompt à copier** : le récap dit à l'humain d'ouvrir une session
  neuve et d'y demander la reprise ; le mode de qui a plusieurs comptes
  ou veut garder la main.

Le mode est celui que dit une consigne en vigueur ; sans elle, la
session programmée. L'humain en change en le disant : l'agent consigne sa
parole en séance, lève la consigne d'avant et écrit la nouvelle
(`socle new directive`), avec son texte exact (skill `socle-request`). Passer au
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

Une session ne part que si le coût estimé de son lot tient dans ce qui
reste de la fenêtre de cinq heures, la marge du rangement comprise, et
jamais sur une semaine au-delà de 75 % : sinon, son heure recule à la
remise à zéro de cette fenêtre, plus cinq minutes. L'utilisation et les
remises à zéro se lisent comme pour les réveils (skill `socle-resume`).

## Les bornes

Rien ne se programme, et le récap dit de demander la reprise :

- quand le prochain lot n'a aucune tâche prête dans l'état, parce
  qu'une décision revient à l'humain ou que rien n'est prêt ; une
  demande en attente qui ne le bloque pas ne l'arrête pas ;
- après deux lots menés sans message de l'humain, le lot en cours
  compris ;
- quand la plateforme refuse de créer la session.

La chaîne (`--chain`) compte ces lots : 0 si l'humain a écrit dans la
session ; sinon, celle de sa passation, plus un. Le prompt à copier
porte 0. Avec `--scheduled`, la commande refuse la passation aux deux
premières bornes, en le disant.

## Écrire la passation

D'abord le rangement (skill `socle-batch`, « Changer de session ») :
l'entrée du journal qui dit la passation, sans les liens que seul le récap
donnera ; les réveils de la session retirés. Puis, avec `--scheduled`
pour une session programmée :

```sh
python3 .socle/socle handoff write --chain <n> --waiting "<ce qui attend>"
```

La passation se commite en dernier et se pousse. Puis la garde, sans
argument, doit la trouver en attente (sa ligne « Premier commit » vaut
pour la session neuve) ; sinon, rien ne se programme, et le récap dit
pourquoi :

```sh
python3 .socle/socle handoff check
```

Plus rien ne se pousse ensuite ; un commit nécessaire après réécrit la
passation (`write`) dans ce même commit, et la garde se relance.

## Programmer

La passation écrite avec `--scheduled` (plus haut, `socle-batch` rangé) :

1. `create_session`, sans `prompt` : `source_url` l'adresse du dépôt ;
   `source_revision` la branche de travail ; `outcome_branch` la même,
   sans quoi la session neuve n'a pas où pousser ; `model` celui de
   cette session ; `effort` le sien, qui ne s'hérite pas (refusé, l'appel
   se refait sans lui) ; `title` « Passation — <lot> — part le <jour> à
   <heure de l'humain> » ; `tags` `["passation"]`.
2. `create_trigger` : `name` « Passation — <dépôt> » ;
   `persistent_session_id` la session créée ; `run_once_at` l'heure du
   moment ; `prompt` « reprends — session programmée » ; `initiation`
   `own_followup`.
3. Le récap donne le lien de la session créée, son heure et comment
   l'arrêter ; `Ensuite :` le dit.

Si un appel échoue, la session créée s'archive, et le prompt à copier
remplace la passation programmée, le récap disant pourquoi.

## Le prompt à copier

Le récap le dit, avec la raison du changement de session : « Dans une
session neuve, écrivez « reprends » » ; tout message qui demande de
reprendre ou de continuer convient.

## La session neuve

Sur un premier message qui demande de reprendre ou de continuer le
travail, quelle qu'en soit la forme (« reprends », « continue »,
« reprends les travaux »), ou sur celui de la tâche programmée, l'agent
lance `git fetch --prune origin`, puis la garde sans argument. Refusée,
la session ne fait rien d'autre que le dire, avec sa raison, dans son
dernier message. Acceptée, elle se place sur la référence que la garde
nomme, et son premier commit retire la passation, poussé aussitôt ; sa
chaîne est celle de la passation plus un, réveillée par la tâche
programmée, 0 si l'humain a demandé. Sans passation, elle fait ce que
fait une session neuve, et le dit dans son premier message.

## La pull request ouverte

Une session dont la garde accepte la passation, programmée ou demandée
par l'humain, continue la pull request ouverte de sa branche sans la
demander : elle devient la sienne. Elle la fusionne si la politique le
permet à l'agent, aux conditions de `socle-batch` ; sinon l'humain la
fusionne.

## Voir et arrêter

La session créée paraît aussitôt dans la liste des sessions de
l'humain, sous son titre, prête à relire tant qu'elle attend son réveil.
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
