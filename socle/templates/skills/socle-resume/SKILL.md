---
name: socle-resume
description: Faire reprendre seul l'agent qu'une limite d'usage coupe, par deux réveils programmés sur sa propre session, sans jamais relancer un agent que rien n'a coupé. À utiliser dans une session cloud de Claude Code, au début et à la fin de chaque tour où l'agent agit, à chaque étape, et quand un message commence par « Reprise après limite ».
---

# La reprise après une limite d'usage

Une limite d'usage du compte, sur cinq heures ou sur sept jours, coupe la
session ; coupé, l'agent ne reprend qu'au message suivant de l'humain. Deux
réveils, des messages que l'agent programme pour sa propre session, le
font reprendre dès que la limite se lève. Ils ne vivent que pendant un
tour qui travaille : un tour qui finit, pour toute autre raison qu'une
limite (en attendant l'humain, par exemple), ne relance jamais l'agent.

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
remplissage. L'heure : `get_session` sans argument donne l'identifiant de
la session ; `list_events` avec `kinds: ["rate_limit_event"]` et
`limit: 100`, en remontant par `before_id` tant que rien n'est trouvé ;
dans le plus récent, `rate_limit_info.unifiedWindows.five_hour.resetsAt`
et `….seven_day.resetsAt`, en secondes depuis 1970, UTC.

Leur texte, récrit à chaque fois :

```text
Reprise après limite (<fenêtre>) — <dépôt>, branche <branche>.
Avant tout : la vérification du skill socle-resume.
Lot : <les sujets>. Étape : <ce qui était en cours, ce qui reste>.
Sous-agents en cours : <chacun : son identifiant, sa tâche, ce qu'il doit rendre> | aucun.
```

## Au début de chaque tour où l'agent agit

1. Lire l'heure des deux remises à zéro.
2. Chercher ses réveils : `list_triggers` avec `enabled: true` et
   `limit: 100`, en suivant `next_cursor`, ceux de ces deux noms dont
   `persistent_session_id` est cette session.
3. Présent, le déplacer et récrire son texte : `update_trigger`, avec
   `run_once_at` et `prompt`. Absent, l'armer : `send_later`, avec `at`
   (la remise à zéro plus cinq minutes), `name` et `message`. Jamais deux
   réveils de la même fenêtre.

## À chaque étape, et à chaque sous-agent lancé ou rendu

Récrire le texte des deux réveils (`update_trigger`), et recaler leur
heure si une fenêtre s'est remise à zéro pendant le tour.

## À la fin de chaque tour

Avant la réponse finale, si aucun sous-agent ne tourne encore, retirer les
deux réveils (`delete_trigger`). Si un sous-agent tourne, les laisser, leur
texte à jour : ils restent jusqu'au tour qui reçoit son résultat. Un tour
coupé ou refusé ne retire rien : c'est ce qui le fait reprendre. Si le
tour continue après les avoir retirés (un hook de fin de tour refuse de
conclure, par exemple), les réarmer.

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
   exige, et retirer ses réveils, ou les recaler si un sous-agent tourne.
3. Sinon, reprendre l'étape notée. Chaque sous-agent noté dont le résultat
   n'est pas arrivé : le poursuivre par un message (`SendMessage`, à son
   identifiant) s'il répond encore, sinon le relancer avec son message tel
   quel. Réarmer les réveils, et continuer comme sur « reprends ». Le récap le dit
   (« Reprise après limite : coupé à <heure>, repris à <heure> »), et une
   entrée au journal aussi.

## Ce que l'agent ne fait jamais

Armer un réveil récurrent, ou hors d'un tour où il agit ; reprendre sans la
vérification ; garder un réveil à la fin d'un tour sans sous-agent en
cours ; toucher au réveil d'une autre session. L'humain arrête tout en
écrivant « arrête » dans la session ; les réveils figurent aussi dans la
liste des tâches programmées de son compte, où ils se suppriment.
