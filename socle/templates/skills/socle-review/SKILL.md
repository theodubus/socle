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
menace` : ce que le garde-fou arrête, ce qu'il laisse passer ; un sujet
dont la conception n'est pas tranchée, sa spécification.

## Comment

1. Commiter le lot : la revue ne voit que ce qui est commité, ou changé
   dans un fichier déjà suivi.
2. Préparer le dossier du relecteur :

```sh
python3 .socle/socle review
```

   Il donne la consigne, le diff du lot depuis la branche distante (sinon
   la branche par défaut), les sujets que le lot touche, en entier, ceux
   qu'il ouvre par leur titre, et les décisions qu'ils citent.
   `--base <ref>` change la base du lot ; pour une seconde revue,
   `--since <commit relu>` ne montre que le diff depuis le commit de la
   première, avec les messages des commits qui le corrigent.
3. Le confier à un relecteur qui n'a pas la conversation. Sous Claude
   Code : un sous-agent (outil `Agent`), du modèle de la session, dont le
   seul message est ce dossier, tel quel : rien ne s'y ajoute, rien ne s'en
   retire. Il reçoit aussi les instructions du projet et peut lire le
   dépôt, mais ni la conversation ni le raisonnement de l'agent, et le
   dossier lui dit de ne rien modifier : pour éprouver une commande, il
   crée un dossier temporaire hors du dépôt et n'écrit que là, par le
   chemin que `mktemp -d` a rendu, écrit en toutes lettres dans chaque
   commande : une variable ne survit pas d'un appel à l'autre. Le hook de
   l'agent refuse l'installeur visé sur le projet dans un autre mode que
   celui de son verrou, ou sur une cible écrite par une variable, mais pas
   toute écriture du relecteur
   dans le dépôt. Un agent sans sous-agents saute la
   revue, et son récap le dit.

## Les constats

Le relecteur les classe ; l'agent vérifie chaque classement.

- **Bloquant** (il contredit un critère coché ou une décision citée, fait
  régresser ce qui marchait, perd des données, ou contourne un garde-fou
  dans son modèle de menace) : corrigé dans le lot, avant le push.
- **Pour le backlog** (le reste : un contournement hors du modèle de
  menace, un critère que le lot ne coche pas, un défaut voisin) : pas
  corrigé dans le lot ; il va au backlog, un sujet par constat ou un pour
  plusieurs de même nature.
- **Infondé** : écarté, en une ligne qui dit pourquoi.

Ne rien poster sur GitHub : l'humain lit le récap, pas la revue. Le récap
le dit en une ligne : `Revue : <b> bloquants, corrigés ; <n> au backlog
(<sujets>) ; écartés : <raison de chacun>`, ou `Revue : aucun constat`.
