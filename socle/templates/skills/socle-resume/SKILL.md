---
name: socle-resume
description: Faire reprendre seul l'agent qu'une limite d'usage coupe, par deux réveils sur sa propre session, sans jamais relancer un agent que rien n'a coupé. À utiliser en session cloud de Claude Code, au début et à la fin de chaque tour où l'agent agit, au lancement d'un sous-agent, et quand un message commence par « Reprise après limite ».
---

# La reprise après une limite d'usage

Deux réveils, que l'agent programme pour sa propre session, le font
reprendre à la levée d'une limite d'usage, pendant un tour qui travaille ou
une attente à heure bornée : un tour qui finit autrement que sur une limite
ne relance jamais l'agent.

## Quand

Dans une session cloud de Claude Code seulement, où existent `send_later`,
`update_trigger`, `delete_trigger`, `list_triggers` et `get_session` ;
ailleurs, ce skill ne s'applique pas. Une réponse en texte seul n'arme
rien, et retire les réveils laissés ; un tour qui lance une commande,
écrit un fichier ou lance un sous-agent arme.
Un sous-agent ne touche à aucun réveil : ni armer, ni déplacer, ni retirer.

## Les deux réveils

Un par fenêtre, nommés « Reprise après limite (cinq heures) — <dépôt> » et
« Reprise après limite (semaine) — <dépôt> », chacun cinq minutes après la
remise à zéro de sa fenêtre, de jour comme de nuit, quel que soit son
remplissage.

L'heure de la remise à zéro : `list_events` avec
`kinds: ["rate_limit_event"]` et `limit: 100` (la session : `get_session`
sans argument), en remontant par `before_id` tant que rien n'est
trouvé ; dans le plus récent, `rate_limit_info.unifiedWindows.five_hour.resetsAt` et
`….seven_day.resetsAt`, en secondes depuis 1970, UTC. Une heure lue plus
tôt, encore à venir, vaut : on ne la relit pas.

**Jamais dans le passé.** L'heure courante :
`date -u`, dans la première commande du tour, ou le `now` que rend
`send_later`. Une remise à zéro lue à moins d'une minute dans l'avenir :
le réveil s'arme à la borne, maintenant plus
cinq heures et cinq minutes, ou sept jours et cinq minutes pour la
semaine. Un `send_later` armé avant son `now` : le retirer et le réarmer
à la borne.

**Sans l'outil `list_events`**, chaque réveil s'arme à la borne, et
celui de cinq heures s'y repousse au début de chaque tour qui agit et au
lancement d'un sous-agent (`run_once_at`, dans l'appel prévu).
`list_triggers` retrouve les réveils.

Leur texte porte le lot et les sous-agents en cours :

```text
Reprise après limite (<fenêtre>) — <dépôt>, branche <branche>.
Avant tout : la vérification du skill socle-resume.
Lot : <ses tâches>.
Sous-agents en cours : <chacun : son identifiant, sa tâche, ce qu'il doit rendre> | aucun.
```

## Au début de chaque tour où l'agent agit

Une fois, avant ou avec sa première action :

1. Les réveils laissés par un tour d'avant, sa conversation les montre,
   avec leur `trigger_id`. Au premier tour de la session, ou perdus par
   un compactage : `list_triggers` avec `enabled: true` et `limit: 100` ;
   ceux de ces deux noms dont `persistent_session_id` est cette session
   sont les siens. Ceux d'une session archivée (`get_session` :
   `SESSION_STATUS_ARCHIVED`) se disent à l'humain avec leurs heures, et
   ne se désactivent (`update_trigger`, `enabled: false`) qu'à sa
   demande. Une passation qui attend (« Passation — <dépôt> ») de même.
   Le tour qui s'ouvre, sur un message de l'humain comme sur un réveil,
   fait siens les réveils laissés ; celui qui a tiré, éteint,
   manque. Celui qu'il faut déplacer reçoit, dans un seul appel,
   l'heure de ce tour et le texte de son lot (`update_trigger`, avec
   `run_once_at` et `prompt`) ; celui dont l'heure est bonne ne reçoit le
   texte, du même appel, que si le lot a changé.
2. Le réveil qui manque s'arme : `send_later`, avec `at` (la remise à
   zéro plus cinq minutes, jamais dans le passé), `name` et `message`.
   Jamais deux réveils de la même fenêtre.

## Au lancement d'un sous-agent

Récrire le texte des deux réveils (`update_trigger`, avec `prompt`), une
fois pour les sous-agents lancés ensemble, quand leurs identifiants sont
connus.

## À la fin de chaque tour

Avant la réponse finale, retirer les deux réveils (`delete_trigger`),
sauf pendant un sous-agent, jusqu'au tour qui reçoit son résultat, ou une
attente à heure bornée (un rappel, une commande en arrière-plan, une
CI), jusqu'au tour de l'événement, chacun repoussé après cette heure
s'il tombait avant. Un tour coupé ou refusé ne retire rien. Si le
tour continue après (un hook de fin de tour refuse de conclure), les
réarmer.

## Au réveil : vérifier d'abord

Un message qui commence par « Reprise après limite » :

1. Lire `list_events` avec `kinds: ["result"]` et `limit: 100` : le
   dernier résultat avant ce réveil clôt le tour d'avant, quoi qui l'ait
   ouvert ; il a fini sur une limite s'il est en erreur
   `usage_limit_reached`. Puis, avec `kinds: ["user", "assistant"]`, les
   messages arrivés depuis son dernier travail, même refusés : ceux de
   l'humain sont un texte tapé, ni un résultat d'outil, ni un réveil, ni
   une notification ; un message de reprise de l'application
   (`text_not_typed`) vaut « reprends ».
   **Sans `list_events`**, la transcription locale le dit : le `.jsonl`
   le plus récent du projet sous `~/.claude/projects/`, lu par sa fin
   (`tail`). La coupure est le premier enregistrement `quotaLimits` qui
   suit le dernier appel du modèle, à son `timestamp` ; tout `user` tapé
   (`origin.kind` à `human`) qui la suit est de l'humain, même suivi d'un
   autre refus, comme celui qui l'a provoquée. Sans transcription, ou sans
   le tour d'avant (un conteneur remplacé), la conversation : le tour
   d'avant coupé net, sans récap ni interruption ni message de l'humain
   depuis, l'agent reprend ; sinon, non. Un message refusé pendant la
   limite peut y manquer : la première réponse le dit en tête, que
   l'humain le répète.
2. Ne pas reprendre :
   - si le tour d'avant n'a pas fini sur une limite (l'humain l'a
     interrompu, ou il a fini normalement) ;
   - si l'humain a écrit pendant la limite : répondre à son message, qui
     prime ; s'il dit d'arrêter, s'arrêter ;
   - si la garde refuse : `git fetch`, puis `python3 .socle/socle handoff
     check --ref origin/<branche> --head <sa tête avant le fetch> --since
     <la coupure, si connue>` ;
   - si la pull request de la branche a été fusionnée ou fermée depuis.

   Répondre alors brièvement pourquoi, avec les lignes de fin du projet,
   et retirer le réveil restant, ou le laisser si un sous-agent tourne.
   Si l'humain avait interrompu le travail et que le contrôle de fin de
   tour refuse sur des contrôles en échec, le dire en une ligne, sans y
   toucher ni réarmer.
3. Sinon, reprendre le lot noté, à l'étape que disent la conversation,
   git, le chantier actif et les worktrees. Chaque sous-agent noté dont le
   résultat n'est pas arrivé : le poursuivre par un message
   (`SendMessage`, à son identifiant) s'il répond encore, sinon le relancer
   avec son message tel quel. Le récap le dit
   (« Reprise après limite : coupé à <heure>, repris à <heure> » ; sans
   `list_events`, l'heure de la transcription, sinon « coupé à une heure
   inconnue »), et le journal aussi.

## Ce que l'agent ne fait jamais

Armer un réveil récurrent ; récrire un réveil à chaque étape ; toucher au
réveil d'une autre session sans que l'humain le demande ; l'humain
retrouve les réveils dans la liste des tâches programmées de son compte
(claude.ai/code/routines).
