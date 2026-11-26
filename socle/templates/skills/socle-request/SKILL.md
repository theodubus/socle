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
3. Une demande qui passe la moitié de son budget (`new request` le donne)
   se fait relire à froid avant d'être poussée ; une demande plus courte,
   ou qui ne fait qu'approuver des fichiers protégés par leurs empreintes,
   part sans elle. Le relecteur : un sous-agent (outil `Agent`), dont le
   seul message est le dossier de `python3 .socle/socle
   review --request D-NNNN`, tel quel. Il reçoit explicitement à son
   lancement (`model`) le modèle le plus capable disponible jusqu'à Opus,
   quel que soit celui de la session, sur la dernière version de sa
   famille (un alias qui en désigne une plus ancienne : sans `model`, il
   hérite de la session) ; Fable, s'il est disponible, seulement si
   l'humain le demande. Il lit la demande dans le rôle de l'humain qui n'a pas ouvert le projet depuis
   trois semaines, et rend en un seul message, sans lancer d'outil, ce
   qu'il en a compris et ce qui lui manque pour décider. Un
   compte rendu qui compte un outil lancé dit une lecture qui n'était pas
   à froid : le récap le dit. Réécrire ce que l'humain ne
   comprendrait pas davantage ; écarter, d'une raison, ce qui n'aide pas à
   décider ou qu'un document lié donne déjà. Le récap le dit : `Relecture
   à froid (<modèle>) : <n> points, <k> corrigés ; écartés : …`. Un agent sans
   sous-agents saute cette étape, et son récap le dit.
4. Commiter et pousser la demande telle quelle, puis donner son lien
   (`python3 .socle/socle url D-NNNN`) dans la conversation. Travailler sur
   autre chose en attendant la réponse (politique, point 8).

## Relayer une réponse

1. Écrire le texte exact de l'humain dans un fichier.
2. Consigner la réponse :

```sh
python3 .socle/socle answer D-NNNN <réponse> --relayed --by <nom> --quote-file <fichier>
```

3. Recopier la réponse au journal, avec son texte exact.

La réponse se consigne dès qu'elle est donnée, se commite et se pousse
aussitôt : l'humain ne la voit plus en attente. Elle couvre le changement
qu'elle autorise (une valeur attendue, une clé des garde-fous, un fichier
protégé) dans sa pull request, ou plus tard, fusionnée, tant qu'une tâche
ouverte la cite et que ce qu'elle nomme n'a pas bougé depuis la demande :
la tâche qui fait le changement la cite, et se clôt avec lui.

Une réponse ne se relaie qu'à une demande poussée telle quelle : l'humain
doit avoir pu la lire. Une demande répondue est gelée. La réponse
`contexte-insuffisant` renvoie la demande : la réécrire en une demande
nouvelle, qui la remplace et la cite dans ses éléments cités ; l'état ne
la dit plus alors à réécrire.

Un test dont la valeur attendue change en attendant une demande qui le
nomme peut rester changé dans l'arbre à la fin du tour ; il ne se commite
qu'après la réponse.

## Une conception à trancher

Un besoin dont la conception n'est pas tranchée pose d'abord sa question
d'intention, dans la conversation, en quelques lignes : le besoin tel que
l'agent le comprend, le choix qui reste, sa recommandation ; la réponse
se consigne en séance (plus bas). Puis sa spécification et son code se
font dans le même lot, la spécification d'abord. Ce qui reste coûteux à
défaire va ensuite en demande, courte ; le reste, l'agent le décide et
l'écrit en décision.

## Consigner une décision prise en séance

Ce que l'humain tranche dans la conversation, de lui-même ou sur une question
courte posée dans le texte de la réponse, se consigne aussitôt, avec sa
réponse mot pour mot ; `--about <chemin>` désigne ce qu'elle approuve :

```sh
python3 .socle/socle decision "<question>" <réponse> --relayed --by <nom> --quote-file <fichier>
```

Une décision que l'humain donne de lui-même, sans qu'on la lui ait
demandée (une règle, une interdiction, « supprime ce test »), se consigne
sans question inventée ni réponse à choisir : son texte exact, sous un
titre qui la dit en une phrase sans rien nommer qu'il ne nomme. Elle est
validée, et autorise ce qu'elle nomme comme une demande validée :

```sh
python3 .socle/socle decision "<la décision en une phrase>" --unprompted --relayed --by <nom> --quote-file <fichier>
```

Une consigne de l'humain ne se lève que par sa parole : elle se consigne
ainsi, en séance, puis la consigne passe `levée`, avec
`levée-par : D-NNNN`, cette décision.

Un contenu montré dans la conversation que l'humain valide (un format, un
exemple, un texte) s'écrit d'abord tel quel dans le dépôt, puis la
décision le désigne (`--about <chemin>`), et les tâches qui en découlent
citent ce chemin : sans lui, la décision ne garde que la question et la
réponse, et le contenu se perd.

**La variante légère**, pour des valeurs attendues changées
mécaniquement, des tests qui lisent un format que l'humain vient de
valider : une question dans la conversation qui nomme chaque test, avec
sa valeur avant et après ; sa réponse se consigne mot pour mot en
décision de séance, dont le texte (`--question-file`) nomme les tests, et
se commite avec eux. Tout autre changement de valeur attendue, ou
suppression d'un test, garde la demande écrite.

## Ce que l'agent ne fait jamais

Répondre à la place de l'humain (`socle answer` sans `--relayed` ni
citation), ni lancer `socle approve`, réservé à l'humain.
