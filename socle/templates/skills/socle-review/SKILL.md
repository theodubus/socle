---
name: socle-review
description: Faire relire un lot par un relecteur sans contexte avant de le livrer, la revue adversariale, puis traiter ses constats. À utiliser avant le push qui livre un lot qui change du code, une spécification ou un test.
---

# La revue adversariale d'un lot

Les contrôles du socle jugent la forme du travail ; la revue en juge le
fond, par un relecteur qui ne partage pas les angles morts de l'agent qui
a écrit le lot, et qui cherche à le prendre en défaut.

## Quand

Avant le push qui livre un lot qui change du code, une spécification ou un
test ; jamais pour un lot qui ne touche que la mémoire. Une passe par lot ;
une seconde seulement si la correction des constats bloquants est lourde
(elle change la conception d'une partie, pas quelques lignes), et sur elle
seule.

Le relecteur juge le lot contre ses sujets : leur critère « Fait quand »,
et, pour un garde-fou, son modèle de menace. Un sujet qui pose ou change un
garde-fou l'écrit donc avant son code, dans sa section `## Modèle de
menace` ou dans la décision qu'il cite : ce que le garde-fou arrête, ce
qu'il laisse passer ; un sujet dont la conception n'est pas tranchée, sa
spécification.

## Comment

1. Commiter le lot : la revue ne voit que ce qui est commité, ou changé
   dans un fichier déjà suivi.
2. Préparer le dossier du relecteur :

```sh
python3 .socle/socle review
```

   Il donne la consigne, le diff du lot depuis l'ancêtre commun de HEAD
   et de sa base, la branche distante (sinon la branche par défaut ; si
   la branche distante contient déjà le lot, poussé avant sa revue, ou
   est restée en arrière de la branche par défaut après une fusion par
   écrasement, l'ancêtre commun avec la branche par défaut, et il le dit), les sujets
   dont le lot change le statut ou le « Fait quand », en entier, ceux
   qu'il ouvre par leur titre, les décisions et les demandes que le lot
   écrit, puis celles que ses sujets citent.
   `--base <ref>` change la base du lot ; pour une seconde revue,
   `--since <commit relu>` ne montre que le diff depuis le commit de la
   première, avec les messages des commits qui le corrigent. Une
   référence inconnue, ou un `--since` qui n'est pas un ancêtre de HEAD,
   est refusée. Un lot déjà poussé en tout ou en partie (une session
   cloud pousse à chaque fin de tour), ou une branche qui porte des lots
   déjà relus, que la note du dossier signale : `--base <le commit d'avant
   le lot>`, la tête d'où le lot est parti.
3. Le confier à un relecteur qui n'a pas la conversation. Sous Claude Code
   : un sous-agent (outil `Agent`), dont le seul message est ce dossier,
   tel quel : rien ne s'y ajoute, rien ne s'en retire. Il reçoit
   explicitement à son lancement (`model`) le modèle le plus capable
   disponible jusqu'à Opus, jamais un moindre que celui qui a implémenté
   le lot, quel que soit celui de la session, que la règle du modèle de
   `socle-batch` peut faire moins coûteux, sur la dernière version de sa
   famille : si l'alias en désigne une plus ancienne, il hérite de la
   session, sans `model`, comme cette règle le dit, et son compte rendu
   nomme le modèle qui l'a servi ; Fable, s'il est disponible,
   seulement si l'humain le demande. Il reçoit aussi les instructions du
   projet et peut lire le dépôt, mais ni la conversation ni le
   raisonnement de l'agent, et le dossier lui dit de ne rien modifier :
   pour éprouver une commande, il crée un dossier temporaire hors du dépôt
   et n'écrit que là, par le chemin que `mktemp -d` a rendu, écrit en
   toutes lettres dans chaque commande : une variable ne survit pas d'un
   appel à l'autre. Le hook de l'agent refuse l'installeur visé sur le
   projet dans un autre mode que celui de son verrou, ou sur une cible
   écrite par une variable, mais pas toute écriture du relecteur dans le
   dépôt. Un agent sans sous-agents saute la revue, et son récap le dit.

## Les constats

Le relecteur les classe ; l'agent vérifie chaque classement.

- **Bloquant** (il contredit un critère coché ou une décision citée, fait
  régresser ce qui marchait, perd des données, ou contourne un garde-fou
  dans son modèle de menace) : corrigé dans le lot, avant le push.
- **Pour le backlog** : un constat qui ne bloque pas va au backlog s'il
  peut se produire dans l'usage normal du projet, ou si rien ne rattrape
  ensuite son effet ; un sujet par constat, ou un pour plusieurs de même
  nature.
- **Écarté** : un constat exotique (un geste rare, une forme qu'on
  n'écrit que pour contourner, un cas jamais reproduit) dont l'effet est
  rattrapé, par un contrôle, la CI ou une erreur que l'agent voit
  aussitôt ; et un constat infondé. Une ligne du récap dit pourquoi
  chacun est écarté.
- **Une forme du shell qu'un agent n'écrit pas** dans son travail (ni
  vue dans une session d'agent, ni dans un skill, ni dans une
  documentation courante), et qui échappe au hook de l'agent : elle ne se
  classe pas bloquante, même refusée avant le lot par accident, ni pour
  le backlog, quel qu'en soit l'effet. Elle s'écarte, et va d'une ligne à
  la liste des formes connues que le hook ne juge pas, que tient le guide
  du socle (`python3 .socle/socle help`).

Ne rien poster sur GitHub : l'humain lit le récap, pas la revue. Le récap
le dit en une ligne : `Revue : <b> bloquants, corrigés ; <n> au backlog
(<sujets>) ; écartés : <raison de chacun>`, ou `Revue : aucun constat`.
