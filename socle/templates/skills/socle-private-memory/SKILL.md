---
name: socle-private-memory
description: Travailler avec la mémoire privée du projet, quand la politique en choisit une : où écrire le contenu nouveau, basculer une entrée publique en privé, commiter en mode compagnon, ajouter un terme privé, faire relire avant publication. À utiliser avant d'écrire une entrée, de commiter ou de pousser dans un projet qui a une mémoire privée.
---

# La mémoire privée

Si la politique en choisit une (`[private] mode`, dans
`.socle/policy.toml`), une partie de la mémoire vit dans une zone privée,
sous memory/private/. L'état dit si elle est disponible ; indisponible, on
ne conclut pas sur ce qui en dépend.

## Écrire

- Le contenu nouveau va dans la zone privée pour les couches que la
  politique rend privées : `socle new` le fait par défaut.
- Une consigne de l'humain sur une entrée précise se suit par
  `socle new … --private` ou `--public`.
- Un nom privé nouveau (une idée, un client) s'ajoute à la liste des termes
  privés ; seul l'humain en retire :

```sh
python3 .socle/socle private term <terme>
```

## Basculer une entrée publique en privé

```sh
python3 .socle/socle private move <ID>
```

L'historique public garde l'ancien texte : le dire à l'humain.

## Ne rien recopier en public

Rien de privé ne se recopie en public : ni un identifiant `P…`, ni son
contenu, ni dans un message de commit, une pull request ou un commentaire.
Les hooks et la CI refusent une fuite.

## Commiter en mode compagnon

Un changement privé se commite dans le dépôt privé, puis le verrou avance
dans le dépôt public :

```sh
python3 .socle/socle private lock
```

## Faire relire avant publication

Si la politique exige une relecture (`[private] review`), montrer à
l'humain ce qui part, puis consigner son accord avec son texte exact, à
chaque push ou par lots :

```sh
python3 .socle/socle reviewed --relayed --by <nom> --quote-file <fichier>
```

## Une demande privée

Chiffrée, elle ne se lit pas sur GitHub : la donner en entier dans la
conversation.

Mettre en place la mémoire privée (`socle private install`) est réservé à
l'humain.
