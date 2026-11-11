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
test ; jamais pour un lot qui ne touche que la mémoire. Une seule passe par
lot : pas de seconde revue après les corrections.

## Comment

1. Commiter le lot : la revue ne voit que ce qui est commité, ou changé
   dans un fichier déjà suivi.
2. Préparer le dossier du relecteur :

```sh
python3 .socle/socle review
```

   Il donne la consigne, le diff du lot depuis la branche distante (sinon
   la branche par défaut), les sujets que le lot ferme et les décisions
   qu'ils citent. `--base <ref>` change la base du lot.
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

Aucun ne bloque seul. Corriger chaque constat fondé, dans le lot, avant le
push ; répondre aux autres en une ligne : pourquoi il ne tient pas. Ne rien
poster sur GitHub : l'humain lit le récap, pas la revue.

Le récap le dit en une ligne : `Revue : <n> constats, <k> corrigés ;
écartés : <raison de chacun>`, ou `Revue : aucun constat`.
