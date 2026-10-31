# Socle

**Mémoire et garde-fous pour les agents de code qui entretiennent un projet
dans la durée.**

Le socle s'installe dans un dépôt qu'un agent de code (Claude Code, ou un
autre) fait évoluer de session en session. Il garde la mémoire du projet
dans le dépôt, la remet à l'agent à chaque session, et vérifie
automatiquement ce que l'agent produit. L'humain ne tranche que ce
qu'aucun contrôle ne peut trancher.

Ce dépôt ne contient que le moteur, publié depuis son atelier à chaque
version. Le moteur est en Python 3.11+, sans dépendance.

## Installation

Prérequis : Python 3.11+ et git ; un projet en Rust, Python, JavaScript ou
TypeScript, Go, Java, Ruby, PHP ou C# ; les outils de son adaptateur là où
l'agent travaille (pytest, cargo…), que l'installeur cite ; Claude Code et
GitHub pour les trois étages de contrôles.

```sh
git clone --depth 1 https://github.com/theodubus/socle /tmp/socle
cd <projet>
PYTHONPATH=/tmp/socle python3 -m socle install --target . --owner @<propriétaire>
```

L'installeur termine par les étapes suivantes, chacune avec sa commande.
Une mise à jour relance les mêmes commandes depuis un clone à jour : les
fichiers du projet ne sont jamais écrasés.

En session cloud de Claude Code, l'agent fait tout, installation comprise :
ce dépôt, public, se clone sans être ajouté à la session, qui reste ainsi
sur le seul dépôt du projet. L'installation prend `--human <nom>`, l'identité
git du conteneur étant celle de l'agent.

## Documentation

| Document | Portée |
| --- | --- |
| [Le guide d'utilisation](socle/HELP.md) | l'usage d'un projet équipé, étape par étape, et la référence des commandes |
| [Le format de la mémoire](socle/FORMAT.md) | la spécification de la mémoire |
| [La spécification des adaptateurs](socle/adapters/README.md) | comment décrire un langage |

## Licence

MIT : voir le fichier `LICENSE` de ce dépôt.
