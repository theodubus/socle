---
name: socle-request
description: Poser une demande de décision humaine, relayer la réponse de l'humain, ou consigner une décision prise en séance. À utiliser quand une décision revient à l'humain (politique d'autonomie, points 1 à 4, 7 et 8), quand il répond à une demande, ou quand il tranche une question dans la conversation.
---

# Les demandes de décision humaine

Une demande est lue quand le contexte est perdu : elle se suffit à
elle-même. L'humain répond dans la conversation ; l'agent consigne sa
réponse mot pour mot, sans jamais la choisir.

## Poser une demande

1. `python3 .socle/socle new request "<décision>"` pose le squelette,
   donne l'identifiant, et imprime le contrat que le lint jugera.
2. Remplir les huit champs :
   - **Décision demandée** : en une phrase.
   - **Contexte** : pour l'humain qui revient sur le projet après des
     semaines, trois paragraphes d'abord, chacun ouvert par son nom en
     gras : **Le projet.** (ce qu'il fait, et pour qui, même si l'humain
     le sait), **Le chantier.** (le but du travail en cours, ce qui est
     fait et ce qui reste ; ses décisions passées dites par leur contenu et
     leur date, pas par leur numéro) et **La question.** (ce qui la pose
     maintenant). Puis le détail, sur place, pas un renvoi : soixante mots
     au moins en tout, et chaque terme propre au projet expliqué à sa
     première apparition.
   - **Éléments cités** : chaque identifiant décrit en clair, avec
     l'empreinte de la version lue (`- B-NNNN@xxxxxxxx — ce que c'est, en
     une phrase`) ; jamais un identifiant seul. Un fichier protégé à
     faire approuver, ceux d'une mise à jour, s'y écrit sur sa ligne, son
     chemin et son empreinte nouvelle, rien d'autre (`python3 .socle/socle
     check` les donne) : ces lignes n'ont pas à être décrites et ne
     comptent pas dans le budget de la demande.
   - **Où regarder** : un lien vers chaque document à lire
     (`python3 .socle/socle url <chemin>`), et ce qu'il faut y vérifier.
   - **Options** : pour chacune, l'effort, le risque, la réversibilité.
   - **Conséquences** : si l'humain valide, s'il refuse, sans réponse.
   - **Recommandation** : le vérifié séparé du supposé.
   - **Réponses possibles** : une liste `` - `valeur` — sens `` qui
     propose les réponses de base, les mêmes dans toute demande :
     `valider` (la recommandation), `refuser` et `contexte-insuffisant` ;
     une demande de choix y ajoute ses options, et aucun synonyme
     (`approuver`, `oui`…). Seule `valider` autorise à changer un test ou
     une clé des seuils que la demande nomme.
3. Le lint refuse une demande incomplète ; le hook de l'agent la refuse dès
   l'écriture.
4. La faire relire à froid avant de la pousser : un sous-agent (outil
   `Agent`), du modèle de la session, dont le seul message est le dossier
   de `python3 .socle/socle review --request D-NNNN`, tel quel. Il lit la
   demande dans le rôle de l'humain qui n'a pas ouvert le projet depuis
   trois semaines, sans lien ni fichier, et rend ce qu'il en a compris et
   ce qui lui manque pour décider. Réécrire ce que l'humain ne
   comprendrait pas davantage ; écarter, d'une raison, ce qui n'aide pas à
   décider ou qu'un document lié donne déjà. Le récap le dit : `Relecture
   à froid : <n> points, <k> corrigés ; écartés : …`. Un agent sans
   sous-agents saute cette étape, et son récap le dit.
5. Commiter et pousser la demande telle quelle, puis donner son lien
   (`python3 .socle/socle url D-NNNN`) dans la conversation. Travailler sur
   autre chose en attendant la réponse (politique, point 8).

## Relayer une réponse

1. Écrire le texte exact de l'humain dans un fichier.
2. Consigner la réponse :

```sh
python3 .socle/socle answer D-NNNN <réponse> --relayed --by <nom> --quote-file <fichier>
```

3. Recopier la réponse au journal, avec son texte exact.

La réponse se consigne dès qu'elle est donnée, dans l'arbre : l'état la
lit répondue avant son commit, et l'humain ne la voit plus en attente.
Elle se commite et se pousse avec le changement qu'elle autorise (une
valeur attendue, une clé des garde-fous, un fichier protégé), dans le
même push, jamais avant : la CI d'un push ne compte que les validations
de sa plage, et le push du changement, seul après elle, serait refusé.
Seul un fichier protégé peut la précéder, poussé sous la demande en
attente là où la CI du socle est exigée : la réponse part ensuite seule,
sans dommage. `demandes.reponse-seule` avertit avant qu'elle parte seule.

Une réponse ne se relaie qu'à une demande poussée telle quelle : l'humain
doit avoir pu la lire. Une demande répondue est gelée. La réponse
`contexte-insuffisant` renvoie la demande : la réécrire en une demande
nouvelle, qui la remplace.

Un test dont la valeur attendue change en attendant une demande qui le
nomme peut rester changé dans l'arbre à la fin du tour ; il ne se commite
qu'après la réponse.

## Consigner une décision prise en séance

Une décision qui demande du contexte, approuver un document compris, se
pose en demande (plus haut), jamais dans le widget de questions de
l'agent : l'humain y lit un texte brut, sans liens à suivre. Ce que
l'humain tranche dans la conversation, de lui-même ou sur une question
courte posée dans le texte de la réponse, se consigne aussitôt, avec sa
réponse mot pour mot ; `--about <chemin>` désigne ce qu'elle approuve :

```sh
python3 .socle/socle decision "<question>" <réponse> --relayed --by <nom> --quote-file <fichier>
```

## Ce que l'agent ne fait jamais

Répondre à la place de l'humain (`socle answer` sans `--relayed` ni
citation), ni lancer `socle approve`, réservé à l'humain.
