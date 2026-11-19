---
name: socle-review
description: Faire relire un lot par un relecteur sans contexte avant de le livrer, la revue adversariale, puis traiter ses constats. À utiliser avant le push qui livre un lot qui change du code, une spécification ou un test.
---

# La revue adversariale d'un lot

Les contrôles jugent la forme du travail ; la revue en juge le fond,
par un relecteur sans les angles morts de l'auteur, qui cherche à le
prendre en défaut.

## Quand

Avant le push qui livre un lot qui change du code, une spécification ou un
test ; jamais pour un lot qui ne touche que la mémoire. Une passe par lot ;
une seconde seulement si la correction des bloquants est lourde (elle
change la conception d'une partie, pas quelques lignes), et sur elle
seule ; chaque passe au-delà de la première suit le recul de la précédente.

Le relecteur juge le lot contre ses tâches : leur critère « Fait quand »,
et, pour un garde-fou, son modèle de menace. Un besoin qui pose ou change un
garde-fou l'écrit donc avant son code, dans sa section `## Modèle de
menace` ou dans la décision qu'il cite : ce que le garde-fou arrête, ce
qu'il laisse passer ; un besoin dont la conception n'est pas tranchée, sa
spécification.

## Comment

1. Commiter le lot : la revue ne voit que ce qui est commité, ou changé
   dans un fichier déjà suivi.
2. Préparer le dossier du relecteur :

```sh
python3 .socle/socle review
```

   Il donne la consigne, le diff du lot depuis l'ancêtre commun de HEAD
   et de sa base, la branche distante (sinon la branche par défaut, ou
   l'ancêtre commun avec elle, et il le dit, si la branche distante
   contient déjà le lot ou est restée en arrière après une fusion par
   écrasement), les entrées dont le lot change le statut ou les
   critères, en entier, celles qu'il ouvre par leur titre, les
   décisions et les demandes que le lot écrit, puis celles que ses
   entrées citent, et le fichier qu'approuve une décision de séance
   (son `sujet`).
   `--base <ref>` change la base ; pour une seconde revue, `--since
   <commit relu>` ne montre que le diff depuis la première, avec les
   messages des commits qui la corrigent. Une référence inconnue, ou un
   `--since` qui n'est pas un ancêtre de HEAD, est refusée. Un lot déjà
   poussé, même en partie (en session cloud, à chaque fin de tour), ou
   une branche qui porte des lots déjà relus, que la note du dossier
   signale : `--base <le commit d'où le lot est parti>`. Il écrit la
   passe dans le lot en cours du backlog, ou celui que `--batch L-NNNN`
   nomme, et refuse une passe que son historique refuse (plus bas).
   Un petit lot (moins de 150 lignes de code et de tests) qui ne touche
   ni un garde-fou ni un format que d'autres parties du projet lisent
   reçoit le dossier court, `--short` : le diff et les critères de ses
   tâches, à juger sans explorer au-delà des fichiers touchés ; tout
   autre lot, le dossier complet. `--short` refuse un lot qui touche un
   chemin que la politique protège ou que les garde-fous déclarent.
3. Le confier à un relecteur qui n'a pas la conversation. Sous Claude Code
   : un sous-agent (outil `Agent`), dont le seul message est ce dossier,
   tel quel, sans ajout ni retrait. Il reçoit explicitement à son
   lancement (`model`) le modèle le plus capable
   disponible jusqu'à Opus, jamais un moindre que celui qui a implémenté
   le lot, quel que soit celui de la session, que la règle du modèle de
   `socle-batch` peut faire moins coûteux, sur la dernière version de sa
   famille : si l'alias en désigne une plus ancienne, il hérite de la
   session, sans `model`, et son compte rendu nomme le modèle qui l'a
   servi ; Fable, s'il est disponible,
   seulement si l'humain le demande. Il reçoit aussi les instructions du
   projet et peut lire le dépôt ; le dossier lui dit de ne rien modifier
   hors d'un dossier temporaire (`mktemp -d`). Le hook de
   l'agent n'arrête pas toute écriture du relecteur dans le dépôt (il
   refuse l'installeur visé sur le projet hors du mode de son verrou, ou
   par une variable). Un agent sans sous-agents saute la revue, et son
   récap le dit.

## Les constats

Le relecteur les classe ; l'agent vérifie chaque classement.

- **Bloquant** (il contredit un critère coché ou une décision citée, fait
  régresser ce qui marchait, perd des données, ou contourne un garde-fou
  dans son modèle de menace) : corrigé dans le lot, avant le push.
- **Pour le backlog** : un constat qui ne bloque pas va au backlog s'il
  peut se produire dans l'usage normal du projet, ou si rien ne rattrape
  ensuite son effet : une tâche par constat si sa correction est claire,
  un besoin sinon, ou une entrée pour plusieurs de même nature.
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
  du socle (`python3 .socle/socle help`). Dans un projet équipé, ce guide
  est protégé : le récap nomme la forme, et « Pour toi » propose de la
  signaler au dépôt du socle (https://github.com/theodubus/socle), qui
  tient la liste.

Ne rien poster sur GitHub : l'humain lit le récap, pas la revue. Le récap
le dit en une ligne : `Revue : <b> bloquants, corrigés ; <n> au backlog
(<entrées>) ; écartés : <raison de chacun>`, ou `Revue : aucun constat`.

## L'historique du lot et le recul

Le lot garde ses passes dans la section `## Revues`, la dernière de son
entrée, lisible d'une session neuve : `socle review` y écrit chaque passe,
sa date et les commits relus, et redonne la même tant que rien ne change
hors de la mémoire.

1. Au retour du relecteur, écrire dans la passe une ligne `- Bloquant :
   <sa cause, en quelques mots>` par bloquant, et `- Ouvre : <les
   entrées que la passe ouvre>`, ou `rien`. À partir de la deuxième
   passe, le dossier donne au relecteur les causes des bloquants d'avant,
   et il dit, pour chaque bloquant nouveau, s'il a la même cause que l'un
   d'eux : sa ligne finit par `· même cause` ou `· cause nouvelle`, selon
   le relecteur, jamais selon l'agent.
2. Avant la passe suivante, et avant de clore le lot, écrire le recul de
   la passe, sous ses bloquants : un paragraphe qui commence par
   « Recul : », de soixante mots au moins, qui répond aux trois questions
   que `socle review` donne en refusant la passe, avec ce qu'il y
   montre : ses bloquants ont-ils la cause de ceux d'avant ? Ce que le
   lot ouvre est-il de la nature de ce qu'il ferme ? Les lots clos sur
   les mêmes fichiers ont-ils ouvert de telles entrées ? Son dernier mot est sa décision : « continuer », ce qui rendra la
   passe suivante différente écrit avant, ou « s'arrêter ».
3. S'arrêter : poser une demande à l'humain (skill `socle-request`) qui
   cite le lot et dit ce qui tourne, en clair, la règle qui le fait
   tourner, et une proposition qui la borne ; le recul la nomme
   (`D-NNNN`), et le lot l'attend par son `après`. `socle review` refuse
   une passe de plus jusqu'à sa réponse, seule à lever l'arrêt : avancer
   ailleurs. Après deux passes de suite où le relecteur voit une même
   cause revenir, il refuse « continuer » : le lot s'arrête.

Le contrôle du backlog refuse un lot relu clos `fait` dont la dernière
passe refuserait la suivante.
