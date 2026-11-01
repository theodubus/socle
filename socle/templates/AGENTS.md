@@SECTION_PROJET@@

## Socle : mémoire, documentation et tests

Ce dépôt utilise le socle (version et empreinte : `.socle/engine.lock`).
Ce fichier dit **comment** travailler ;
**où en est le projet** se calcule, et ne s'écrit jamais à la main.

### Au démarrage, et après chaque compactage

`python3 .socle/socle state` imprime l'état dérivé — commit, base, CI,
backlog, demandes humaines en attente —, puis le chantier actif et la mémoire
canonique. Sous Claude Code, le hook `SessionStart` le fait seul ; sous un
autre agent, le lancer d'abord. Rien de ce qui n'y figure pas n'est acquis.
Ce que l'humain a écrit lui-même depuis le dernier commit de l'agent (une
approbation, une réponse dans son terminal), l'état le liste : le lui citer
dans la réponse suivante, par son identifiant et son lien, puisque la
commande lui a donné un numéro qu'il ne retrouve pas dans la conversation.

Si l'état n'a pas été injecté au démarrage d'une session de Claude Code, les
hooks de l'agent ne sont pas chargés : la session a démarré hors de la racine
du projet. Le dire à l'humain avant tout travail, et ne rien pousser ;
`socle state` l'affiche aussi en tête, et le hook avant commit refuse alors
le commit. Ne jamais écrire soi-même un réglage de Claude Code pour rétablir
les hooks.

Une consigne de l'humain donnée dans la conversation, qui vaut au-delà du tour
(une règle, une préférence, une interdiction), s'écrit dans la mémoire avant de
continuer : au chantier actif si elle touche le travail en cours, sinon au
journal, avec son texte exact. Le résumé d'un compactage ne la garde pas
toujours, et une session neuve n'a que la mémoire.

### La mémoire, dans `memory/`

| Couche | Où | Règle |
| --- | --- | --- |
| Canonique | `memory/canonical.md` | faits avec statut et preuve ; ne change qu'avec une preuve nouvelle |
| Actif | `memory/active.md` | chantier en cours, prochaines étapes ; réécrit, borné |
| Décisions | `memory/decisions/` | une ADR par fichier, le seul registre des décisions du projet ; seul son statut change ensuite |
| Journal | `memory/journal/` | une entrée datée par événement ; ajout seul |
| Backlog | `@@BACKLOG@@` | sujets avec statut et origine, ordonnés par `après` (sujets ou demandes), leurs jalons et leur priorité (l'état en calcule les prêts) ; faits quand leur « Fait quand » est coché, clos avec une référence, puis rangés par `socle archive` |
| Demandes | `memory/requests/` | décisions humaines en file, au contrat du skill `socle-request` |

Une entrée : `## F-NNNN — titre`, puis une ligne `> statut : mesuré · preuve : commit:<sha>`.
Statuts d'un fait : `mesuré` (avec `preuve`), `supposé`, `réfuté` (titre barré,
avec `refutation`), `validé` (avec `validation : D-NNNN`, écrit après la
réponse de l'humain). Format complet : `@@MOTEUR@@/socle/FORMAT.md`.
Un identifiant se calcule (`python3 .socle/socle new <type> "titre"`), il ne
se devine pas. En cas de conflit, l'ordre d'autorité est : le code et les
tests, puis la mémoire canonique, puis le journal.

**Mémoire privée**, si la politique en choisit une (`[private] mode`) : rien de privé ne se recopie en public, ni un identifiant `P…`, ni son contenu, ni dans un message de commit, une pull request ou un commentaire ; indisponible (l'état le dit), on ne conclut pas sur ce qui en dépend. Où écrire, basculer une entrée, commiter en mode compagnon, faire relire avant publication : le skill `socle-private-memory`.

### Politique d'autonomie (`.socle/policy.toml`, modifiée par l'humain seul)

1. **Assouplir un garde-fou** (`.socle/guardrails.toml`) exige une demande validée ; durcir est libre. Déclarer des fichiers tiers, qu'aucun contrôle ne juge (`[thirdparty] paths`), assouplit.
2. **Supprimer un test ou changer une valeur attendue** exige une demande validée, ou une spécification que l'humain a lui-même changée et qui nomme le test ; une ADR écrite par l'agent ne suffit pas.
3. **Décision de conception** : réversible et mesurable, l'agent décide et écrit une ADR ; coûteuse à défaire, demande.
4. **Action irréversible ou externe** (force-push, push sur la branche par défaut, publication, suppression distante, dépense) : toujours une demande. Le hook la refuse.
5. **Mémoire** : ajout seul ; « réfuté » exige une référence de mesure ; « validé » ne s'écrit qu'après la réponse de l'humain.
6. **Débordement de périmètre** : un bug voisin va au backlog, il ne se corrige pas, sauf s'il bloque.
7. **Échec répété** : contrôles rouges après trois tentatives, arrêt et escalade par une demande qui résume.
8. **Validation requise** : mettre la demande en file, travailler sur autre chose, ne jamais deviner.

### Demandes de décision humaine

Une décision qui revient à l'humain se pose en demande, qui se lit seule
quand le contexte est perdu, et dont le lien se donne dans la conversation.
L'humain répond dans la conversation ; l'agent consigne sa réponse mot pour
mot, sans jamais la choisir, et la recopie au journal. Une décision qui
demande du contexte, approuver un document compris, s'écrit toujours en
demande ; jamais dans le widget de questions de l'agent, où l'humain lit un
texte brut sans liens à suivre (le hook le refuse). Ce que l'humain tranche
dans la conversation, de lui-même ou sur une question courte posée dans le
texte de la réponse, se consigne aussitôt de même, en séance. Comment : le
skill `socle-request`.

### Lire la mémoire à la demande

Le démarrage n'injecte que l'état, le chantier actif et les faits. Le reste
se lit quand il sert, sans attendre qu'on le demande :

- un identifiant cité (`F-`, `B-`, `ADR-`, `D-`, `J-`) se lit avant de
  s'appuyer dessus : `python3 .socle/socle show <ID>`, qui donne aussi son
  empreinte ;
- avant une décision de conception, l'index des décisions de l'état dit si
  elle est déjà prise : on ne la rouvre pas sans fait nouveau ;
- avant d'ouvrir un sujet, le backlog (`socle show --index backlog`) dit
  s'il existe déjà ;
- pour savoir pourquoi une chose est ainsi, chercher dans le journal
  (`grep -rn "<mot>" memory/journal/`).

La lecture se prouve : une décision, une demande ou un sujet de backlog
nouveaux citent ce qu'ils ont lu avec son empreinte (`ADR-NNNN@xxxxxxxx`,
`lu : decisions@…`, `lu : backlog@…`). Une empreinte périmée ou inventée est
refusée ; il faut relire l'entrée. `socle new` pose l'empreinte de l'index.

### Les skills

Une procédure rare se lit dans son skill, que l'agent charge sur sa
description : `socle-request` (poser une demande, relayer une réponse,
consigner une décision en séance) et `socle-private-memory` (la mémoire
privée), dans `.claude/skills/`, posés par l'installeur et protégés ; un
autre agent lit leur `SKILL.md` à ce chemin.

Une procédure du projet qui se refait (le journal montre la première fois)
s'écrit en skill à la deuxième, dans `.claude/skills/<nom>/SKILL.md` : un
nom sans le préfixe `socle-`, un en-tête `name` (le nom du
dossier) et `description` (ce qu'il fait, et quand s'en servir), et une
entrée au journal qui le dit. Un skill dit comment faire, la mémoire ce qui
est et pourquoi : il n'en recopie rien. Ses commandes, dans des blocs de
code, sont jugées comme le hook les jugerait ; une commande à ne pas lancer
se cite dans le texte.

### Livrer le travail

Tant que rien ne revient à l'humain, l'agent enchaîne les sujets prêts
sans attendre de message. Il annonce d'abord le lot, pas forcément tout ce
qui est prêt (les sujets, leur taille, le jalon qu'ils servent ; un sujet de
priorité basse s'il est commode), puis s'y met ; il s'arrête à la fin du
lot, ou dès qu'une décision revient à l'humain. Il ne change pas une
priorité que l'humain a donnée.

Par défaut, tout se fait sur une branche de développement, avec une seule
pull request ouverte à la fois : chaque lot fini s'y ajoute, l'humain la
fusionne quand il veut, et la branche repart alors de la branche par
défaut. Une pull request par sujet, seulement si l'humain l'a choisi (un
fait de la mémoire le dit). Une session neuve qui trouve ouverte la pull
request d'une autre demande à l'humain de la fusionner d'abord, ou de
l'autoriser à y continuer.

### Avant de conclure

- `python3 .socle/socle verify --fast` passe (le hook `Stop` le vérifie) ; `verify` exécute tout.
- Si du code a changé, la mémoire aussi : chantier actif, journal, backlog.
- Si du code associé à une doc a changé (`[[docmap]]` des garde-fous), la doc change dans le même travail, ou le commit qui change ce code porte le trailer `Dispense-doc: <raison>`, qui ne vaut que pour lui.
- Un correctif (sujet `fix:` ou trailer `Corrige: B-NNNN`) livre un test qui échoue sur le commit parent.
- Une fonction publique ajoutée ou modifiée est nommée par au moins un test, ou un commit la dispense nommément avec sa raison (`Dispense-test: f, g — <raison>`). Du code existant découvert sans test : le test s'écrit tout de suite s'il est dans le périmètre du travail, sinon un sujet va au backlog.
- Une action que seul l'humain peut faire (refusée par le hook, réglage d'un service, fichier qu'il détient) va au backlog avec `pour : humain`.
- **Toute intervention qui a agi se termine par un récap, puis deux lignes** : `Pour toi :` — ce qui revient à l'humain, décisions en attente et actions à faire, ou « rien » —, chaque point compréhensible sans le raisonnement de l'agent (ce que c'est, pourquoi, ce que change sa réponse), et `Ensuite :` — la suite proposée (prochain jalon, ce qu'il reste à faire avant), et ce que l'agent attend s'il attend quelque chose (une CI, un match : quoi, et jusqu'à quand). L'état calcule ce qui revient à l'humain ; le hook `Stop` refuse de conclure sans les deux lignes.
- **Un fichier à lire, ou une pull request, se donne par son lien** : l'humain lit dans la conversation ou sur GitHub, pas dans le conteneur de l'agent. `python3 .socle/socle url <chemin|ID>` donne le permalien, une fois le fichier poussé ; une demande en attente citée sans son lien, un lien relatif, ou un chemin entre accents graves qui n'existe pas dans le dépôt font refuser la fin du tour. Un chemin d'un autre dépôt s'écrit `depot:chemin`, le dépôt lié quelque part dans le projet par son adresse (à défaut, déclaré dans `[references] repos` des garde-fous) ; un dépôt inconnu est signalé.

### Ne jamais

- compléter un SHA de tête, inventer un identifiant ou une référence : le hook les refuse ;
- écrire dans un fichier protégé (politique, adaptateur, verrou du moteur, hooks, CI, réponses humaines) ;
- répondre à la place de l'humain (`socle answer` sans `--relayed` ni citation), ou lancer `socle approve` ou `socle private install`, réservés à l'humain ;
- contourner un hook (`--no-verify`) : le hook de l'agent le refuse sur le dépôt du projet, et la CI exécute tout ;
- poser une question à l'humain dans le widget de questions de l'agent : le hook le refuse.

### Ce qui tourne tout seul

| Où | Quoi |
| --- | --- |
| `.claude/settings.json` | hooks de Claude Code : `SessionStart` (état dérivé ; en session cloud, les outils de l'adaptateur), `PreToolUse` (refus), `Stop` (contrôles de fin de tour) |
| `.socle/git-hooks/` | hooks git : `pre-commit` (contrôles rapides), `prepare-commit-msg` (trailers `Socle-Hooks`, `Socle-Hooks-Since-Commit`), `commit-msg` (fuites de la mémoire privée ; une fonction sans test ni dispense, un correctif sans test, un commit d'agent sans hook de l'agent, en avertissement), `pre-push` (`verify --fast` sur le dernier commit, la plage qui part jugée comme la CI la jugera, relecture avant publication) |
| `.github/workflows/socle.yml` | CI : capacités de l'adaptateur, tous les contrôles contre la base, auto-test du socle |
@@LIGNE_MUTATION@@
| `.git/socle/hooks.log` | trace locale de chaque hook qui tire, non versionnée, commune à tous les worktrees du dépôt |

Liste des contrôles : `python3 .socle/socle checks`.
