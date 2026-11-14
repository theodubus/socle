# Notes de version du socle

Ce que chaque changement du socle change pour un projet installé, et ce que
l'agent du projet doit en faire. Une entrée par changement, la plus récente
d'abord, sous un identifiant qui ne change jamais : la date du changement et
une lettre. À la mise à jour, l'installeur donne les entrées que la copie du
moteur du projet n'avait pas, et le message de commit qu'il propose nomme
leurs identifiants.

## 2026-11-14-d — Un lot se garde au backlog

Un lot, les sujets qu'on mène ensemble parce qu'ils touchent les mêmes
fichiers, le même garde-fou ou les mêmes tests et qu'une seule revue les
juge, se garde désormais au backlog : un sujet marqué `forme : lot`, dont
`après` nomme ses sujets et le lot d'avant. L'état montre le prochain lot à
côté du prochain jalon, avec ce qui en reste et où en est chacun de ses
sujets. Un lot n'est jamais un sujet prêt, et il ne se clôt pas avant ses
sujets.

À faire : poser en lot les sujets qu'on prévoit de mener ensemble, au lieu
de ne les écrire que dans le chantier actif ; clore le lot quand ses sujets
le sont.

## 2026-11-14-c — Les notes de version

Ce fichier existe. Une mise à jour qui recopie le moteur imprime, entre ce
qu'elle a posé et l'audit, les entrées que la copie remplacée n'avait pas ;
une copie qui n'en avait aucune les reçoit toutes, dont celles qui décrivent
ce que le projet a déjà. Le message de commit que propose « Et maintenant »
nomme leurs identifiants dans un second paragraphe, pour la session suivante.

À faire : lire chaque entrée donnée et faire ce qu'elle demande ; garder ce
second paragraphe dans le commit de la mise à jour. Une session qui trouve
une mise à jour qu'elle n'a pas lancée lit les entrées que ce commit nomme.

## 2026-11-14-b — La fin de tour dit la mise à jour en une ligne

Entre l'installation et le push de sa demande, la fin de tour ne liste plus
chaque fichier protégé que la mise à jour a posés, avec sa commande de
remise : une seule ligne, « une mise à jour du socle attend sa demande : la
poser », avec leur nombre et la commande qui les liste avec leurs empreintes
(`python3 .socle/socle check --stage agent --only protege.fichiers`). Le
verrou du moteur nomme désormais, sous `[installed]`, ceux que l'installeur
a posés hors du moteur, avec leur empreinte : c'est ainsi qu'elle les
reconnaît.

À faire : ne pas remettre ces fichiers, poser la demande. Un fichier protégé
changé avant ou après le passage de l'installeur garde sa ligne et sa
commande de remise.

## 2026-11-14-a — Une réponse de l'humain se consigne aussitôt, et part avec ce qu'elle autorise

Une réponse donnée dans la conversation se consigne tout de suite dans
l'arbre (`python3 .socle/socle answer D-NNNN valider --relayed …`) : l'état
lit l'arbre et ne la dit plus en attente. Elle se commite et se pousse avec
le changement qu'elle autorise (une valeur attendue, une clé des garde-fous,
un fichier protégé), dans le même push, jamais avant : la CI d'un push ne
compte que les validations de sa plage. Seul un fichier protégé peut la
précéder, poussé sous la demande en attente. Un contrôle nouveau,
`demandes.reponse-seule`, avertit quand la réponse partirait seule : dans
`verify --fast`, au commit et avant le push. Le skill `socle-request`, une
copie protégée, le dit.

À faire : consigner chaque réponse dès qu'elle est donnée, et la pousser
avec ce qu'elle autorise. Poussée seule, elle ne couvre pas le changement qui
la suit : la consigner alors une seconde fois.

## 2026-11-13-c — La revue juge un lot contre ses sujets

Le dossier de `python3 .socle/socle review` donne au relecteur le « Fait
quand » de chaque sujet que le lot touche, même ouvert, et les titres de
ceux qu'il ouvre ; le relecteur classe chaque constat, bloquant (un critère
coché ou une décision contredits, une régression, une perte de données, un
contournement d'un garde-fou dans son modèle de menace) ou pour le backlog.
Le skill `socle-review`, une copie protégée, change.

À faire : corriger les bloquants dans le lot et mettre les autres au backlog ;
une seconde revue seulement si la correction est lourde, sur elle seule
(`python3 .socle/socle review --since <commit relu>`). Un sujet qui pose ou
change un garde-fou écrit avant son code une section « ## Modèle de menace »
(ce qu'il arrête, ce qu'il laisse passer) ; un sujet dont la conception
n'est pas tranchée, sa spécification.

## 2026-11-13-b — Le hook de l'agent développe les chemins comme le shell

Le hook juge un chemin qu'une commande shell écrit tel que le shell le
développerait : variables, motifs (`*`, `?`), accolades, `~`, `cd` et
`pushd` suivis, chemins relatifs au dossier courant. Ce qu'il ne sait pas
développer (une variable inconnue, `$(…)`, un `cd` vers un tel chemin) est
refusé s'il peut tomber dans le projet. Les faux refus connus : `$(mktemp -d)`
ou `$(git rev-parse --show-toplevel)` gardés dans une variable ou pris pour
cible d'un `cd`, une boucle `for` sur une liste écrite.

À faire : sur un refus, écrire le chemin en toutes lettres, ou affecter la
variable plus tôt dans la même commande (`F=/tmp/x; echo y > "$F"`). Le hook
n'est qu'une première barrière : le contrôle `protege.fichiers` reste la
garantie.

## 2026-11-13-a — La sortie du démarrage est bornée

La sortie du hook de démarrage dépassait ce que Claude Code remet entier, et
l'agent n'en recevait qu'un aperçu. Elle tient désormais sous
`[startup] max_bytes` des garde-fous (9 500 octets) : d'abord ce qui demande
d'agir, puis l'état, le chantier actif en entier, les faits par leur titre
et les dix dernières décisions. Une partie qui dépasse sa part perd des
lignes entières, et une dernière ligne « !! coupé » dit ce qui manque et où
le lire. Le budget du chantier actif passe à 3 700 octets, public et privé
ensemble.

À faire : lire aussitôt ce qu'une ligne « !! coupé » dit manquer
(`python3 .socle/socle state --short` pour l'état entier,
`python3 .socle/socle show <ID>` pour une entrée). Si l'installeur dit que le
budget de `memory/active.md` est au-dessus de sa part, le baisser à la valeur
qu'il donne (durcir est libre), puis raccourcir le chantier actif, ce qui en
sort allant au journal.

## 2026-11-12-a — L'adoption ne tolère que les constats déjà présents

Dans un projet adopté, un contrôle sous `[adoption] warn_only` ne passe plus
en avertissement tout entier : seuls les constats consignés sous
`[adoption.tolerated]` des garde-fous le sont, et tout constat nouveau
échoue. À la mise à jour, l'installeur y consigne les constats de la base
encore présents, et le dit. Un fichier renommé garde ses constats si sa clé
est renommée dans la même pull request.

À faire : lire ce que l'installeur dit de la liste ; corriger un constat
nouveau au lieu de l'ajouter, puisqu'ajouter assouplit et attend une demande
validée ; retirer un constat résorbé, ce qui est libre ; renommer la clé d'un
fichier renommé dans la pull request qui le renomme.

## 2026-11-11-b — L'agent peut remettre un fichier protégé à son état du dernier commit

Le hook de l'agent laisse passer `git restore --source=HEAD -- <fichier>` et
`git checkout HEAD -- <fichier>`, chaque chemin écrit en toutes lettres, et
`rm <fichier>` pour un fichier apparu sous un chemin protégé que git ne suit
pas. Les réglages de Claude Code en restent exclus, et un fichier que cite
une demande dont l'approbation n'est pas commitée est épargné.

À faire : rien ; c'est la forme que donnent le refus d'écriture et l'erreur
de `protege.fichiers`, pour défaire un changement fait par erreur.

## 2026-11-11-a — Le hook refuse l'installeur hors du mode du verrou

Le hook de l'agent refuse `socle install` sur un projet équipé dans un autre
mode que celui de son verrou, et une cible qu'il ne sait pas résoudre (une
variable, `$(…)`, `~autre`, dans la cible ou dans le `cd` qui la précède).
La ligne de commande refuse les options abrégées.

À faire : lancer la mise à jour dans le mode du verrou, la cible écrite en
toutes lettres (`--target .`) ; changer le mode d'un projet revient à
l'humain.

## 2026-11-10-b — La mise à jour approuvée par une demande

L'installeur rend 0 quand l'installation a réussi et que seule
l'approbation des fichiers protégés attend. En session cloud, la demande qui
les approuve se pose par `python3 .socle/socle new request "<décision>"`, qui
en imprime le contrat ; chaque fichier protégé s'y écrit sur sa ligne, son
chemin et son empreinte sans rien d'autre, et ces lignes ne comptent pas
dans le budget de la demande. Le hook avant commit refuse une référence que
le commit ne contient pas.

À faire : suivre « Et maintenant » dans son ordre : la demande seule
d'abord, poussée, puis les fichiers protégés avec ce qui les cite (journal,
chantier actif).

## 2026-11-10-a — Les branches jetables

Une branche dont le nom commence par un préfixe de `[branches] disposable`
des garde-fous, `proto/` à défaut, n'est pas jugée par la CI à chaque envoi ;
sa pull request la juge en entier, et la protection de la branche par défaut
bloque la fusion tant que la CI est rouge. Le workflow de CI, un fichier
protégé, change à la mise à jour.

À faire : rien. Un essai qu'on ne veut pas faire juger à chaque push va sur
une branche `proto/…` ; ajouter un préfixe assouplit, et attend une demande
validée.

## 2026-11-09-a — L'empreinte de lecture ne couvre plus les métadonnées

L'empreinte d'une entrée de la mémoire (`ID@xxxxxxxx`, que
`python3 .socle/socle show` imprime) couvre son titre et son corps, sans les
lignes `>` qui suivent le titre : changer un statut ne périme plus une
citation. Toutes les empreintes changent donc avec cette version ; une
citation écrite avant reste acceptée tant qu'elle correspond. Une citation
ne prouve plus qu'un statut a été lu.

À faire : relire une entrée (`python3 .socle/socle show <ID>`) avant de la
citer de nouveau, pour en prendre l'empreinte ; ne pas récrire les
citations anciennes. Lire le statut dans l'index (`python3 .socle/socle show
--index decisions`, ou `backlog`).
