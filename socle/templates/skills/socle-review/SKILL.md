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
seule.

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
   et de sa base, la branche distante (sinon la branche par défaut, et
   il dit pourquoi), les entrées dont le lot change le statut ou les
   critères, en entier, celles qu'il ouvre par leur titre, les
   décisions et les demandes que le lot écrit, puis celles que ses
   entrées citent et ces décisions, et le fichier qu'approuve une
   décision de séance (son `sujet`).
   `--base <ref>` change la base ; pour une seconde revue, `--since
   <commit relu>` ne montre que le diff depuis la première, avec les
   messages des commits qui la corrigent. Un lot déjà poussé, même en
   partie (en session cloud, à chaque fin de tour), ou une branche qui
   porte des lots déjà relus, que la note du dossier signale : `--base
   <le commit d'où le lot est parti>`. Il écrit la
   passe dans le lot en cours du backlog, ou celui que `--batch L-NNNN`
   nomme, et refuse une passe que son historique refuse (plus bas).
   Un petit lot (moins de 150 lignes de code et de tests) qui ne touche
   ni un garde-fou ni un format que d'autres parties du projet lisent
   reçoit le dossier court, `--short` : le diff et les critères de ses
   tâches, à juger sans explorer au-delà des fichiers touchés ; tout
   autre lot, le dossier complet. `--short` refuse un lot qui touche un
   chemin que la politique protège ou que les garde-fous déclarent.
3. Le confier à un relecteur qui n'a pas la conversation. Le dossier n'y
   entre pas, qui la relirait à chaque pas : la sortie de `socle review`
   s'écrit dans un fichier hors du dépôt, et le seul message du relecteur
   (sous Claude Code, un sous-agent, outil `Agent`) donne son chemin, avec
   la consigne de le lire en entier et de le suivre tel quel. Il reçoit
   explicitement à son lancement (`model`) le modèle le plus capable
   disponible jusqu'à Opus, jamais un moindre que celui qui a implémenté
   le lot, quel que soit celui de la session, que la règle du modèle de
   `socle-batch` peut faire moins coûteux, sur la dernière version de sa
   famille : si l'alias en désigne une plus ancienne, il hérite de la
   session, sans `model`, et son compte rendu nomme le modèle qui l'a
   servi ; Fable, s'il est disponible,
   seulement si l'humain le demande. Un lot implémenté sur Fable (le
   lot, pas la session qui orchestre) fait demander à l'humain, avant la
   revue, s'il veut aussi Fable pour le relecteur. Le relecteur reçoit
   aussi les instructions du projet et peut lire le dépôt ; le dossier
   lui dit de ne rien modifier hors d'un dossier temporaire
   (`mktemp -d`), ce que le hook de l'agent n'impose pas. Un agent sans
   sous-agents saute la revue, et son récap le dit.

## Les constats

Le relecteur les classe ; l'agent vérifie chaque classement.

- **Bloquant** (il contredit un critère coché ou une décision citée, fait
  régresser ce qui marchait, perd des données, ou contourne un garde-fou
  dans son modèle de menace) : corrigé dans le lot, avant le push.
- **Pour le backlog** : un constat qui ne bloque pas va au backlog
  seulement s'il est important et a été vu en usage réel (une session,
  une CI, un message de l'humain le montre), ou si son effet serait
  irréversible (une perte de données, un push sur la branche par défaut,
  une suppression) : une tâche par constat si sa correction est claire,
  un besoin sinon, ou une entrée pour plusieurs de même nature.
- **Écarté** : tout autre constat, dont un cas imaginé et jamais vu,
  une légère gêne que l'agent règle lui-même (ce que rattrape un
  contrôle, la CI ou une erreur qu'il voit aussitôt), un contournement
  hors du modèle de menace, et un constat infondé. En cas de doute, il
  s'écarte. Une ligne du récap dit pourquoi
  chacun est écarté ; il revient s'il est vu en usage réel.

Ne rien poster sur GitHub : l'humain lit le récap, pas la revue. Le récap
le dit en une ligne : `Revue : <b> bloquants, corrigés ; <n> au backlog
(<entrées>) ; écartés : <raison de chacun>`, ou `Revue : aucun constat`.

## L'historique du lot

Le lot garde ses passes dans la section `## Revues`, la dernière de son
entrée, lisible d'une session neuve qui reprend le lot : `socle review` y
écrit chaque passe, sa date et les commits relus, et redonne la même tant
que rien ne change hors de la mémoire. Commiter la passe écrite, et ce
qu'on y consigne : sinon, elle se perd là où `socle review` a tourné.

Au retour du relecteur, écrire dans la passe une ligne `- Bloquant : <sa
cause, en quelques mots>` par bloquant, et `- Ouvre : <les entrées que la
passe ouvre>`, ou `rien`. Rien d'autre n'est exigé, ni avant la passe
suivante, ni à la clôture du lot.
