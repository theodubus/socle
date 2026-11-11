---
name: socle-resume
description: Faire reprendre seul l'agent qu'une limite d'usage coupe, par deux réveils programmés sur sa propre session, armés une fois par tour, sans jamais relancer un agent que rien n'a coupé. À utiliser dans une session cloud de Claude Code, au début et à la fin de chaque tour où l'agent agit, au lancement d'un sous-agent, et quand un message commence par « Reprise après limite ».
---

# La reprise après une limite d'usage

Une limite d'usage du compte, sur cinq heures ou sur sept jours, coupe la
session ; coupé, l'agent ne reprend qu'au message suivant de l'humain. Deux
réveils, des messages que l'agent programme pour sa propre session, le
font reprendre dès que la limite se lève. Ils ne vivent que pendant un
tour qui travaille : un tour qui finit, pour toute autre raison qu'une
limite (en attendant l'humain, par exemple), ne relance jamais l'agent.
Chaque appel coûte de l'usage : la procédure en fait le moins possible,
quatre ou cinq par tour.

## Quand

Dans une session cloud de Claude Code seulement, où existent les outils
`send_later`, `update_trigger`, `delete_trigger`, `list_triggers`,
`list_events` et `get_session` (serveur `claude-code-remote`). Ailleurs, ce
skill ne s'applique pas. Une réponse en texte seul n'arme rien ; un tour où
l'agent lance une commande, écrit un fichier ou lance un sous-agent arme.
Un sous-agent ne touche à aucun réveil : ni armer, ni déplacer, ni retirer.

## Les deux réveils

Un par fenêtre, nommés « Reprise après limite (cinq heures) — <dépôt> » et
« Reprise après limite (semaine) — <dépôt> », chacun cinq minutes après la
remise à zéro de sa fenêtre, de jour comme de nuit, quel que soit son
remplissage.

L'heure de la remise à zéro : `list_events` avec
`kinds: ["rate_limit_event"]` et `limit: 100` (l'identifiant de la session
est dans son lien, `…/code/session_…`, sinon `get_session` sans argument
le donne), en remontant par `before_id` tant que rien n'est trouvé ; dans
le plus récent, `rate_limit_info.unifiedWindows.five_hour.resetsAt` et
`….seven_day.resetsAt`, en secondes depuis 1970, UTC. Une heure lue plus
tôt dans la conversation, encore à venir, vaut toujours : une fenêtre ne
se remet pas à zéro avant son heure, et on ne la relit pas.

**Jamais dans le passé.** Un réveil armé à une heure passée se déclenche
aussitôt. L'heure courante se lit par `date -u` (dans la première commande
du tour) ; `send_later` la rend aussi (`now`). Une remise à zéro lue qui
n'est pas à plus d'une minute dans l'avenir date d'une fenêtre close : le
réveil s'arme alors à la borne, maintenant plus cinq heures et cinq
minutes pour la fenêtre de cinq heures, plus sept jours et cinq minutes
pour la semaine, tard mais jamais à tort. Un résultat de `send_later` dont
l'heure armée précède `now` : retirer ce réveil et le réarmer à la borne.

Leur texte porte ce que l'agent ne retrouve pas ailleurs : le lot, et les
sous-agents en cours. L'étape, il la retrouve dans sa conversation, dans
git, dans le chantier actif et dans la liste des worktrees.

```text
Reprise après limite (<fenêtre>) — <dépôt>, branche <branche>.
Avant tout : la vérification du skill socle-resume.
Lot : <les sujets>.
Sous-agents en cours : <chacun : son identifiant, sa tâche, ce qu'il doit rendre> | aucun.
```

## Au début de chaque tour où l'agent agit

Une fois, avant ou avec sa première action :

1. Les réveils laissés par un tour d'avant, sa conversation les lui
   montre, avec leur `trigger_id` (après un compactage qui les a perdus :
   `list_triggers` avec `enabled: true` et `limit: 100`, ceux de ces deux
   noms dont `persistent_session_id` est cette session). S'il en reste,
   le tour qui s'ouvre, sur un message de l'humain comme sur un réveil,
   les fait siens : la coupure qu'ils gardaient est finie, et un réveil
   d'une fenêtre écoulée, laissé tel quel, relancerait l'agent pour rien.
   Un réveil laissé garde aussi le texte du lot d'avant, qui ferait
   reprendre l'ancien lot si ce tour était coupé : celui qu'il faut
   déplacer reçoit, dans le même appel, l'heure de ce tour et le texte
   de son lot (`update_trigger`, avec `run_once_at` et `prompt`) ; celui
   dont l'heure est encore la bonne ne le reçoit, par le même appel, que
   si le lot a changé, et reste sinon sans appel.
2. Le réveil qui manque s'arme : `send_later`, avec `at` (la remise à
   zéro plus cinq minutes, jamais dans le passé), `name` et `message`.
   Jamais deux réveils de la même fenêtre.

Ensuite, rien à chaque étape : ni récrire leur texte, ni relire l'heure.

## Au lancement d'un sous-agent

Récrire le texte des deux réveils (`update_trigger`, avec `prompt`), une
fois pour les sous-agents lancés ensemble, quand leurs identifiants sont
connus. Un sous-agent qui rend ne demande rien : sa conversation dit à
l'agent que son résultat est arrivé.

## À la fin de chaque tour

Avant la réponse finale, si aucun sous-agent ne tourne encore, retirer les
deux réveils (`delete_trigger`). Si un sous-agent tourne, les laisser :
ils restent jusqu'au tour qui reçoit son résultat. Un tour coupé ou
refusé ne retire rien : c'est ce qui le fait reprendre. Si le tour
continue après les avoir retirés (un hook de fin de tour refuse de
conclure, par exemple), les réarmer. Un tour en texte seul qui trouve des
réveils laissés par un tour d'avant les retire de même.

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
   (« Reprise après limite : coupé à <heure>, repris à <heure> »), et une
   entrée au journal aussi.

## Ce que l'agent ne fait jamais

Armer un réveil récurrent, dans le passé, ou hors d'un tour où il agit ;
le récrire à chaque étape ; reprendre sans la vérification ; garder un
réveil à la fin d'un tour sans sous-agent en cours ; toucher au réveil
d'une autre session. L'humain arrête tout en écrivant « arrête » dans la
session ; les réveils figurent aussi dans la liste des tâches programmées
de son compte, où ils se suppriment.
