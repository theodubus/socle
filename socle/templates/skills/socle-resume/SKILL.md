---
name: socle-resume
description: Faire reprendre seul l'agent qu'une limite d'usage coupe, par deux réveils programmés sur sa propre session, armés une fois par tour, sans jamais relancer un agent que rien n'a coupé. À utiliser dans une session cloud de Claude Code, au début et à la fin de chaque tour où l'agent agit, au lancement d'un sous-agent, et quand un message commence par « Reprise après limite ».
---

# La reprise après une limite d'usage

Une limite d'usage du compte, sur cinq heures ou sept jours, coupe la
session ; l'agent ne reprend alors qu'au message suivant de l'humain. Deux
réveils, messages que l'agent programme pour sa propre session, le font
reprendre à la levée. Ils ne vivent que pendant un tour qui travaille :
un tour qui finit autrement que sur une limite ne relance jamais l'agent.
Chaque appel coûte de l'usage : quatre ou cinq par tour.

## Quand

Dans une session cloud de Claude Code seulement, où existent les outils
`send_later`, `update_trigger`, `delete_trigger`, `list_triggers` et
`get_session` (serveur `claude-code-remote`). Ailleurs, ce skill ne
s'applique pas. Une réponse en texte seul n'arme rien ; un tour où l'agent
lance une commande, écrit un fichier ou lance un sous-agent arme.
Un sous-agent ne touche à aucun réveil : ni armer, ni déplacer, ni retirer.

## Les deux réveils

Un par fenêtre, nommés « Reprise après limite (cinq heures) — <dépôt> » et
« Reprise après limite (semaine) — <dépôt> », chacun cinq minutes après la
remise à zéro de sa fenêtre, de jour comme de nuit, quel que soit son
remplissage.

L'heure de la remise à zéro : `list_events` avec
`kinds: ["rate_limit_event"]` et `limit: 100` (l'identifiant de la
session : son lien, `…/code/session_…`, ou `get_session` sans argument),
en remontant par `before_id` tant que rien n'est trouvé ; dans le plus
récent, `rate_limit_info.unifiedWindows.five_hour.resetsAt` et
`….seven_day.resetsAt`, en secondes depuis 1970, UTC. Une heure lue plus
tôt, encore à venir, vaut toujours : on ne la relit pas.

**Jamais dans le passé.** Un réveil armé à une heure passée se déclenche
aussitôt. L'heure courante se lit par `date -u` (dans la première commande
du tour) ; `send_later` la rend aussi (`now`). Une remise à zéro lue qui
n'est pas à plus d'une minute dans l'avenir date d'une fenêtre close : le
réveil s'arme alors à la borne, maintenant plus cinq heures et cinq
minutes pour la fenêtre de cinq heures, plus sept jours et cinq minutes
pour la semaine, tard mais jamais à tort. Un résultat de `send_later` dont
l'heure armée précède `now` : retirer ce réveil et le réarmer à la borne.

**Sans l'outil `list_events`**, chaque réveil s'arme à la borne, et
celui de cinq heures, dont la fenêtre a commencé on ne sait quand, s'y
repousse au début de chaque tour qui agit et au lancement d'un sous-agent
(`run_once_at`, dans l'appel prévu). Il tombe après la levée tant
qu'aucune fenêtre n'a recommencé entre ce report et la coupure ; sinon
il tire trop tôt et se perd. `list_triggers` retrouve les réveils.

Leur texte porte ce que l'agent ne retrouve pas ailleurs : le lot, et les
sous-agents en cours. L'étape, il la retrouve dans sa conversation, git,
le chantier actif et les worktrees.

```text
Reprise après limite (<fenêtre>) — <dépôt>, branche <branche>.
Avant tout : la vérification du skill socle-resume.
Lot : <les sujets>.
Sous-agents en cours : <chacun : son identifiant, sa tâche, ce qu'il doit rendre> | aucun.
```

## Au début de chaque tour où l'agent agit

Une fois, avant ou avec sa première action :

1. Les réveils laissés par un tour d'avant, sa conversation les montre,
   avec leur `trigger_id` (perdus par un compactage : `list_triggers`
   avec `enabled: true` et `limit: 100`, ceux de ces deux noms dont
   `persistent_session_id` est cette session). Le tour qui s'ouvre,
   sur un message de l'humain comme sur un réveil, les fait siens : la
   coupure qu'ils gardaient est finie, et un réveil d'une fenêtre écoulée
   relancerait l'agent pour rien ; son texte, celui du lot d'avant, ferait
   reprendre l'ancien lot. Celui qu'il faut déplacer reçoit, dans un seul
   appel, l'heure de ce tour et le texte de son lot (`update_trigger`,
   avec `run_once_at` et `prompt`) ; celui dont l'heure est bonne ne
   reçoit le texte, du même appel, que si le lot a changé.
2. Le réveil qui manque s'arme : `send_later`, avec `at` (la remise à
   zéro plus cinq minutes, jamais dans le passé), `name` et `message`.
   Jamais deux réveils de la même fenêtre.

## Au lancement d'un sous-agent

Récrire le texte des deux réveils (`update_trigger`, avec `prompt`), une
fois pour les sous-agents lancés ensemble, quand leurs identifiants sont
connus. Un sous-agent qui rend ne demande rien : sa conversation le dit.

## À la fin de chaque tour

Avant la réponse finale, si aucun sous-agent ne tourne, retirer les deux
réveils (`delete_trigger`) ; sinon les laisser jusqu'au tour qui reçoit
son résultat. Un tour coupé ou refusé ne retire rien : c'est ce qui le
fait reprendre. Si le tour continue après (un hook de fin de tour refuse
de conclure), les réarmer. Un tour en texte seul retire de même les
réveils laissés par un tour d'avant.

## Au réveil : vérifier d'abord

Un message qui commence par « Reprise après limite » :

1. Lire `list_events` avec `kinds: ["result"]` et `limit: 100` : le
   dernier résultat avant ce réveil clôt le tour d'avant, quoi qui l'ait
   ouvert (un message de l'humain, le résultat d'un sous-agent, un autre
   réveil) ; il a fini sur une limite s'il est en erreur
   `usage_limit_reached`. Puis, avec `kinds: ["user"]`, les messages
   arrivés depuis la coupure, même refusés : ceux de l'humain sont un texte
   tapé, ni un résultat d'outil, ni un réveil, ni une notification ; un
   message de reprise de l'application (`text_not_typed`) vaut « reprends ».
   **Sans `list_events`**, la conversation seule le dit : le tour d'avant
   coupé net, sans récap de fin ni interruption de l'humain, et sans
   message de lui depuis, l'agent reprend ; sinon, il ne reprend pas
   l'ancien travail. Un message refusé pendant la limite ne s'y lit pas :
   la première réponse le dit en tête, pour que l'humain le répète.
2. Ne pas reprendre :
   - si le tour d'avant n'a pas fini sur une limite (l'humain l'a
     interrompu, ou il a fini normalement) ;
   - si l'humain a écrit depuis la coupure : répondre à son message, qui
     prime ; s'il dit d'arrêter, s'arrêter ;
   - si une autre session a poussé sur la branche depuis le dernier commit
     de l'agent (`git fetch`, puis comparer) ;
   - si la pull request de la branche a été fusionnée ou fermée depuis.

   Répondre alors brièvement pourquoi, avec les lignes de fin que le projet
   exige, et retirer le réveil restant, ou le laisser si un sous-agent
   tourne.
3. Sinon, reprendre le lot noté, à l'étape que disent la conversation,
   git, le chantier actif et les worktrees. Chaque sous-agent noté dont le
   résultat n'est pas arrivé : le poursuivre par un message
   (`SendMessage`, à son identifiant) s'il répond encore, sinon le relancer
   avec son message tel quel. Le réveil qui a tiré ne tirera plus : le
   début du tour le réarme, comme sur « reprends ». Le récap le dit
   (« Reprise après limite : coupé à <heure>, repris à <heure> » ; sans
   `list_events`, « coupé à une heure inconnue »), et le journal aussi.

## Ce que l'agent ne fait jamais

Armer un réveil récurrent, dans le passé, ou hors d'un tour où il agit ;
le récrire à chaque étape ; reprendre sans la vérification ; garder un
réveil à la fin d'un tour sans sous-agent en cours ; toucher au réveil
d'une autre session. L'humain arrête tout en écrivant « arrête » dans la
session, ou supprime les réveils de la liste des tâches programmées de
son compte.
