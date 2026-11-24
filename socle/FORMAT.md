# Format de la mémoire

La mémoire est un ensemble de fichiers markdown en cinq couches, plus la file
des demandes humaines. Un script sait la lire : sans cela, aucun contrôle
automatique ne serait possible. Ce document fait foi pour le format ; le code
qui le lit est `socle/memory.py`, les contrôles sont listés par
`python3 .socle/socle checks`.

## Emplacements

```text
memory/
  canonical.md            faits vérifiés, avec statut et preuve
  active.md               chantier en cours, prochaines étapes
  backlog/B-0001-*.md     une entrée par fichier : besoin, tâche (T-), lot (L-), jalon (JA-)
  decisions/ADR-0001-*.md une décision par fichier
  journal/2026-10.md      un fichier par mois, une entrée par événement
  requests/D-0001-*.md    une demande de décision humaine par fichier
  requests/D-0001-*.answer.toml   la réponse de l'humain, et elle seule
  archives/               documents archivés tels quels (cadrage…), non lus par les contrôles
  private/                zone privée, même arborescence (voir « La zone privée »)
```

Les noms sont en anglais pour tous les projets, quelle que soit la langue de
la mémoire ; la configuration du socle suit (`.socle/policy.toml`,
`.socle/guardrails.toml`, `.socle/adapter.toml`, `.socle/engine.lock`,
`.socle/private.lock`, le moteur sous `.socle/engine/`). Le verrou note le
format de la mémoire (`format = 3`).
Les couches gardent leurs noms internes (`canonique`, `actif`, `demandes`…)
dans l'en-tête des fichiers : c'est le vocabulaire du format, pas un chemin.

## En-tête

La première ligne non vide de chaque fichier déclare sa couche et sa zone.
L'emplacement impose la couche ; la zone est celle de l'emplacement
(`publique` sous `memory/`, `privee` sous `memory/private/`).

```markdown
<!-- socle: couche=canonique zone=publique -->
```

## Entrées

Une entrée est un titre qui commence par son identifiant, suivi d'une ligne
de métadonnées (une ou plusieurs lignes `>` consécutives), puis d'un corps
libre qui court jusqu'au titre suivant de même niveau ou de niveau supérieur.
Comme en Markdown, les dièses qui ferment un titre, précédés d'une espace,
n'en font pas partie ; un dièse collé à un mot (« C# ») en fait partie.

```markdown
## F-0007 — La suite de tests complète tourne en moins de 40 secondes

> statut : mesuré · preuve : cmd:`cargo test --release` · date : 2026-10-10

Mesuré sur la machine de CI ; le chiffre change avec le nombre de tests.
```

Les métadonnées sont des paires `clé : valeur` séparées par un point médian
(`·`). Les clés s'écrivent sans souci des accents ni des majuscules
(`Réfutation` et `refutation` se valent).

### Identifiants

| Couche | Forme | Exemple |
| --- | --- | --- |
| Canonique | `F-` et quatre chiffres | `F-0007` |
| Backlog, besoin | `B-` et quatre chiffres | `B-0012` |
| Backlog, tâche | `T-` et quatre chiffres | `T-0031` |
| Backlog, lot | `L-` et quatre chiffres | `L-0005` |
| Backlog, jalon | `JA-` et quatre chiffres | `JA-0002` |
| Décisions | `ADR-` et quatre chiffres | `ADR-0003` |
| Demandes | `D-` et quatre chiffres | `D-0004` |
| Journal | `J-` date et lettre | `J-2026-10-10-A` |

Dans la zone privée, l'identifiant prend un `P` devant (`PF-0001`,
`PJ-2026-10-10-A`) : un fichier public qui en cite un est une fuite, et le
contrôle la voit même sans accès à la zone privée. Un identifiant se calcule
(`socle next-id`, `socle new`), il ne se devine pas ; `socle new` saute
ceux que prennent les branches distantes et les correctifs suivis du dépôt
(`*.patch`, `*.diff`), ceux d'une passation. Il est défini une seule
fois ; toute mention ailleurs doit mener à une définition. Un identifiant
que deux branches ont pris se répare par `socle renumber <ID>` : l'entrée
qu'ajoute la branche prend le suivant libre, avec ses mentions et ses
empreintes ; après un rebase ou un cherry-pick qui les réunit, c'est celle
qui manque à la base ou au dernier commit poussé, et seules les lignes que
la branche a ajoutées changent.

### Références

Une valeur de métadonnée, ou le texte, peut citer :

| Forme | Vérifiée en CI |
| --- | --- |
| `commit:3f2a9c1` | l'objet existe dans le dépôt (historique complet), ou dans une de ses pull requests, que le contrôle récupère de l'origine avant de le dire absent : de GitHub, ou d'un clone qui les a récupérées |
| `fichier:src/x.rs`, `fichier:src/x.rs:12`, `fichier:doc.md#ancre` | le chemin existe |
| ``cmd:`cargo test, puis cargo bench` `` ou `cmd:scripts/verify.sh` | le script existe s'il est un chemin du dépôt |
| `url:https://…` | jamais suivie : aucun service externe |
| `F-0007`, `J-2026-10-10-A`… | l'entrée existe |

Une référence nue s'arrête avant la ponctuation qui la suit : le point
final, la parenthèse qui la referme. Les liens markdown relatifs et leurs
ancres, décodés (`%20`), et les chemins du dépôt cités entre accents graves,
sont vérifiés aussi ; un chemin d'un autre dépôt s'écrit `depot:chemin`, le
dépôt lié quelque part dans le projet par son adresse, ou, à défaut, déclaré
dans `[references] repos` des garde-fous. Un texte barré (`~~…~~`,
`<s>…</s>`, `<del>…</del>`) dit ce qui n'est plus : ses chemins et ses liens
ne se vérifient pas. Un chemin vaut s'il est suivi par git, l'index
compris, comme un clone neuf le verra : un fichier neuf pas encore ajouté
(`git add`) est averti sur l'arbre de travail, et le commit qui ne l'ajoute
pas le refuse ; un chemin ignoré ne vaut que par une règle d'un
`.gitignore` que l'index ou le commit jugé contient, pas par une règle
locale (`.git/info/exclude`) ; un dossier ignoré se cite avec sa barre
finale. Dans une couche qui ne se
réécrit pas (canonique, décisions, journal, demandes), un chemin qui a
existé dans l'historique du dépôt vaut, un lien relatif se lit aussi depuis
les anciens emplacements de son fichier, et l'ancre d'un lien n'est pas
vérifiée : le titre qu'elle visait a pu changer depuis. Un bloc de code
clôturé porte des exemples : rien n'y est vérifié.

## Couches

### Canonique — `F-`

| Statut | Exigence |
| --- | --- |
| `mesuré` | `preuve` : commit, fichier, commande ou entrée qui la porte |
| `supposé` | rien ; `source` dit d'où vient le fait |
| `réfuté` | titre barré `~~…~~`, corps conservé, `refutation` vers la mesure |
| `validé` | `validation : D-NNNN`, une demande à laquelle l'humain a répondu `valider` |

Un fait ne s'efface pas : il se barre, ou s'archive dans le journal (voir
plus bas). Modifié, il porte une référence de preuve qu'il n'avait pas.

### Actif

Réécrit librement, borné par son budget. Il ne définit aucun identifiant :
un identifiant est stable, l'actif ne l'est pas. Il renvoie aux entrées du
backlog et du journal. L'ordre du travail ne s'y recopie pas : il se tient
au backlog, d'où l'état le calcule.

### Décisions — `ADR-`

Un fichier par décision, nommé d'après son identifiant. Statuts : `proposée`,
`acceptée`, `rejetée`, `abandonnée`, `remplacée` (avec
`remplacée-par : ADR-NNNN`). Ajout seul : seuls le statut et sa ligne de métadonnées
changent ensuite (une citation du corps en fait partie, et ne se réécrit pas), selon les passages proposée → acceptée, rejetée ou
abandonnée, et acceptée → remplacée ou abandonnée.

### Journal — `J-`

Un fichier par mois (`AAAA-MM.md`), une entrée par événement, datée par son
identifiant. Un titre qui commence comme une entrée sans en être une
lisible (`## J-2026-10-10 sans sa lettre`) est refusé : l'entrée ne serait lue
nulle part. Ajout seul : une entrée publiée ne change plus, sauf pour
recevoir à sa suite, sur une ligne nouvelle, une archive. Un mois dont le fichier atteindrait son
budget continue dans `AAAA-MM-2.md`, puis `AAAA-MM-3.md`.

### Backlog — `B-`, `T-`, `L-`, `JA-`

Une entrée du backlog a l'une de quatre formes, que son préfixe dit
(ADR-0083) :

- un **besoin**, `B-` : un défaut à corriger ou une fonction à ajouter ;
  ses constats ou sa motivation, sa spécification s'il n'est pas tranché,
  et sa section `## Satisfait quand`, un résultat, jamais une
  implémentation ;
- une **tâche**, `T-` : un livrable, en principe un commit, qui nomme le
  besoin qu'elle sert (`besoin : B-0012`) ; sa section `## Fait quand` se
  vérifie par des tests, ou, pour une action que seul l'humain peut faire,
  par ce qu'elle produit ; une case dont le livrable est une demande
  posée, un relevé écrit (le compte rendu d'une mesure ou d'un essai) ou
  une entrée de la mémoire récrite se vérifie aussi par ce qu'elle
  produit, que la case nomme : la demande, et la réponse de l'humain
  consignée au journal ; le fichier du relevé ; ce qu'en montre `socle
  show` ou `socle roadmap` ; tout autre livrable garde son test ; une
  tâche qui dit ce qu'un comportement doit devenir nomme, dès son
  écriture, le test qui affirme le contraire, et la demande qui
  autorise à le changer se pose aussitôt, avant le lancement du lot ;
- un **lot**, `L-` : des tâches qui touchent les mêmes fichiers, le même
  garde-fou ou les mêmes tests, menées et relues ensemble ; son corps dit
  ce qui les réunit ; une tâche est dans un lot au plus ;
- un **jalon**, `JA-` : des besoins qui servent un même but.

Statuts : `ouvert`, `en-cours`, `bloqué`, `fait`, `abandonné`. Toute entrée
a une `origine` (entrée de journal, commit, demande) ; une entrée close
(`fait`, `abandonné`) a une `ref` vers ce qui l'a close. Une action que seul
l'humain peut faire porte `pour : humain` : elle figure dans « ce qui revient
à l'humain », dans l'état et dans le récap de fin d'intervention, avec le
lien de son entrée, où vit son mode d'emploi (commandes, résultats attendus),
jusqu'à ce qu'elle soit close.

Une entrée par fichier, nommé comme une décision
(`B-0001-<titre court>.md`), sous un titre de niveau un ; `socle new need`,
`socle new task "…" --need B-NNNN`, `socle new batch` et `socle new
milestone` la posent, et `socle new need "…" --task "…"` le besoin et sa
tâche quand la correction est évidente :

```markdown
<!-- socle: couche=backlog zone=publique -->
# B-0001 — Un besoin détaillé

> statut : ouvert · origine : J-2026-10-12-A

Son corps, libre, avec ses sous-titres (`## Les commandes`…).

## Satisfait quand

- [ ] un résultat que l'utilisateur constate
```

Chaque entrée a son plafond (`"memory/backlog/*.md"` dans `[budgets]`).
Une entrée close garde son fichier, rangé à l'écart des ouvertes dans le
sous-dossier `closed` du backlog : `socle archive` y range
chaque entrée close, et remet parmi les ouvertes une entrée rouverte ; le
contrôle du backlog refuse une entrée mal rangée, et la mise à jour range un
projet existant. Une entrée rangée garde son identifiant et le plafond
d'une entrée. Une bascule en privé copie le fichier sous `private/backlog/`
(ou son sous-dossier des clos), et un fichier public garde l'identifiant,
comme pour une décision.

L'ordre du travail se tient au backlog. Une entrée attend d'autres
entrées par `après : B-0012, B-0014`, et une demande, `après : D-0007`,
jusqu'à sa réponse (D-0064) ; une condition hors de la mémoire devient une
tâche `pour : humain`, qu'elle attend. Chaque forme n'attend que ce qui
lui revient : un besoin, des besoins et des demandes ; une tâche, des
tâches, des besoins et des demandes ; un lot, ses tâches, des demandes et
le lot d'avant ; un jalon, ses besoins, des demandes et le jalon d'avant.
`après` et `besoin` nomment l'identifiant actuel. Un besoin, un lot ni un
jalon ne sont jamais prêts : seule une tâche se prend. Une priorité,
`priorité : haute` ou `priorité : basse` (D-0062), se donne à un besoin ou
à une tâche ; la normale ne s'écrit pas, et l'agent ne change pas celle
que l'humain a donnée. Une tâche sans priorité prend celle de son besoin,
et attend aussi ce qu'il attend.

L'état en calcule ce qui vient ensuite : le prochain jalon, ouvert,
qu'aucun jalon ouvert ne précède, avec ses besoins et ses demandes encore
ouverts ; le prochain lot, ouvert, qu'aucun lot ouvert ne précède, celui
qui est en cours d'abord, et où en est chacune de ses tâches et de ses
demandes ; les tâches prêtes, ouvertes et pas encore en cours, dont tout
ce qu'elles attendent est clos ou répondu, celles des besoins du prochain
jalon d'abord, puis par priorité ; à part, les prêtes de priorité basse,
que l'agent prend quand c'est commode ; les besoins à fermer, dont les
tâches sont closes, l'une au moins faite ; les besoins à découper, sans
tâche ouverte ni rien d'ouvert qu'ils attendent ; et le nombre d'entrées
qui attendent encore, selon ce qu'elles attendent : une entrée du backlog,
une demande sans réponse, ou les deux. Le rappel de fin de tour le redonne.
Un lot ouvert qui attend encore plus de tâches ouvertes, en cours ou
bloquées que `[batches] max_tasks` des garde-fous (9 par défaut), l'état
et le rappel le signalent, sans rien refuser : il ne se mène pas en une
session.

`socle roadmap` en tire la suite entière, par les mêmes règles : chaque
jalon et ses besoins clos sur le total ; les lots ouverts dans leur ordre
d'exécution, chacun après les lots qu'il attend de proche en proche, l'en
cours d'abord à choix égal, et où en est chacune de leurs tâches (faite,
en cours, prête, ce qu'elle attend encore, bloquée) ; hors des lots, les
tâches ouvertes qu'aucun lot n'attend, les besoins à découper et à
fermer, les entrées bloquées, celles `pour : humain`, les demandes en
attente, et les besoins ouverts qu'aucun jalon n'attend. Deux lots qui
attendent un même lot sans que l'un attende l'autre y sont signalés : leur
ordre n'est pas déduit, il est choisi par leur identifiant.

Une tâche est faite quand sa section `## Fait quand` est cochée ; un
besoin, quand ses tâches sont closes, l'une au moins faite, et sa section
`## Satisfait quand` cochée ; un lot, quand ses tâches sont closes ; un
jalon, quand ses besoins le sont. Abandonnée, une entrée laisse ses cases.
Une tâche qui se révèle un besoin s'abandonne, en renvoyant au besoin
ouvert. Un constat de revue devient une tâche si sa correction est claire,
un besoin sinon.

Les contrôles le tiennent. Celui de l'ordre refuse un `après` qui nomme
autre chose qu'une entrée du backlog ou une demande, une entrée qui
s'attend elle-même de proche en proche, une entrée `fait` avant ce qu'elle
attend, et une priorité ni haute ni basse ; une entrée abandonnée peut
laisser ce qu'elle attendait, et une entrée close ne retient plus celles
qui l'attendent. Celui du backlog refuse une entrée `fait` dont une case
reste vide. Celui des formes refuse, sur une entrée ouverte, un champ
`forme`, `besoin` hors d'une tâche, une priorité sur un lot ou un jalon,
une tâche sans besoin ou dans deux lots, un `après` que sa forme n'attend
pas ou qui nomme un ancien numéro, « Fait quand » dans un besoin et
« Satisfait quand » dans une tâche ; sur une entrée nouvelle, un besoin ou
une tâche sans sa section ; sur une clôture nouvelle, un besoin clos avec
une tâche ouverte, ou fait sans tâche faite. Ce qui est clos avant la
migration reste tel quel.

Une entrée renumérotée garde son ancien numéro (`ancien : B-0235`) :
`socle show`, `socle url`, les contrôles des références et la lecture
prouvée le résolvent vers elle (une citation par l'ancien numéro se juge
contre sa version actuelle), le
journal, les décisions et les demandes le gardent, et il ne se réattribue
jamais. Un texte neuf cite l'identifiant actuel : le hook de l'agent
refuse d'écrire l'ancien numéro dans une ligne qu'une écriture ajoute ou
change, même dans un fichier qui le cite déjà, sauf sur une ligne qui
nomme aussi l'identifiant actuel (`B-0235 → L-0002`), et nomme
l'identifiant à citer ; une ligne d'avant gardée telle quelle passe.

La mise à jour migre un backlog d'avant ADR-0083 : un lot
(`forme : lot`) devient `L-` et un jalon (`forme : jalon`) `JA-`, clos
compris, sans sa priorité, qui ne changeait aucun ordre (l'installeur
nomme chacun) ; toute autre entrée reste un besoin, sa section « Fait quand »
renommée ; chaque besoin qu'attend un lot ouvert reçoit une tâche qui
reprend ses critères, chacun entier, vers laquelle sa section renvoie, et
que le lot attend à sa place ; un jalon attend les besoins de ses lots ;
une entrée close n'en vient à attendre rien d'ouvert ; les mentions se
récrivent dans le backlog, le chantier actif et les tâches posées.

Un besoin qui pose ou change un garde-fou écrit, avant son code, son
modèle de menace : ce que le garde-fou arrête, ce qu'il laisse passer, dans
une section `## Modèle de menace` (`## Threat model` en anglais) ou dans la
décision qu'il cite. La revue d'un lot juge contre lui et contre le
« Fait quand » de ses tâches.

Un lot relu garde l'historique de ses passes de revue dans sa section
`## Revues` (`## Reviews` en anglais), la dernière de son entrée
(ADR-0084, ADR-0100). `socle review` y écrit chaque passe du lot en
cours, ou de celui que `--batch` nomme : son titre (`### Passe 2 —
2026-11-17`) et les commits relus (`Commits : <début>..<tête>`), suivis,
quand l'arbre de travail changeait des fichiers suivis hors de la
mémoire, que la passe a relus aussi, de l'empreinte de ces changements
(`+ arbre de travail <empreinte>`). L'agent y consigne, au retour du
relecteur, une ligne `- Bloquant : <sa cause, en quelques mots>` par
bloquant : une ligne qui se donne pour un bloquant sous une autre forme
(`- **Bloquant** : …`, `- Bloquant 1 : …`, `1. Bloquant : …`,
`- Bloquants : …`, ou sans puce, `Bloquant : …`, `Bloquant 2 — …`) n'est
pas lue, et le contrôle du backlog la refuse, à tout statut du lot ; puis
une ligne `- Ouvre : <les entrées que la passe ouvre>`. Rien d'autre
n'est exigé, ni avant une passe ni à la clôture du lot : le paragraphe de
recul et les marques de cause qu'un lot a écrits avant ADR-0100 se lisent
comme du texte.

Tant que rien ne change hors de la mémoire, ni le commit de tête que la
passe a relu ni les changements de l'arbre de travail dont elle garde
l'empreinte, `socle review` redonne la même passe sans l'écrire de
nouveau ; sinon, il écrit la suivante. Un lot qui ne change ni code, ni
spécification, ni test n'a pas de passe.

```markdown
## Revues

### Passe 1 — 2026-11-16

Commits : 3ea6b92..8719a8f

- Bloquant : la correction change la lecture des commandes
- Ouvre : T-0052

### Passe 2 — 2026-11-17

Commits : 8719a8f..1a2b3c4

- Bloquant : un test qui ne prouve pas la correction
- Ouvre : rien
```

```markdown
# JA-0002 — La recherche par ingrédient livrée

> statut : ouvert · origine : D-0003 · après : JA-0001, B-0021, B-0022, D-0004

# T-0031 — L'index des ingrédients et son test

> statut : ouvert · origine : J-2026-10-14-B · besoin : B-0021 · priorité : haute

## Fait quand

- [x] une recette se trouve par un de ses ingrédients, un test le montre
- [ ] le guide le dit
```

Un fait archivé dans le journal reste défini, donc toute référence vers lui
reste vivante.

### Demandes — `D-`

Un fichier par demande, titre `# D-NNNN — <la décision, en une phrase>`, et
huit sections de niveau deux : `Décision demandée`, `Contexte`, `Éléments
cités`, `Où regarder`, `Options`, `Conséquences`, `Recommandation`,
`Réponses possibles`. Les sept champs du cadrage, plus « Où regarder »,
ajouté après qu'une première série de demandes, conformes au lint, s'est
révélée impossible à trancher pour l'humain.

- « Contexte » raconte, en au moins soixante mots, pour l'humain qui
  revient sur le projet après des semaines. Il commence par trois
  paragraphes, dans cet ordre, chacun ouvert par son nom en gras et long
  d'au moins quinze mots (ADR-0046) : `**Le projet.**` (ce que fait le
  projet), `**Le chantier.**` (le but du travail en cours, ce qui est fait
  et ce qui reste, les décisions passées dites par leur contenu et leur
  date) et `**La question.**` (ce qui la pose maintenant). Viennent ensuite
  le problème lui-même — un extrait de code, la règle en cause — et, si la
  décision porte sur un contenu (un inventaire, un format), son résumé sur
  place. Les trois noms se lisent dans les deux langues. En est dispensée
  une demande posée avant le moteur qui apporte la règle, telle quelle au
  commit qui précède la mise à jour de son verrou, ou datée d'avant le
  8 novembre 2026.
- « Où regarder » donne un lien vers chaque document ou passage à lire
  pour décider, et dit ce qu'il faut y vérifier : le permalien de
  `socle url`, ou, sans adresse de dépôt connue, un lien relatif depuis la
  demande.

- « Éléments cités » décrit en clair, en au moins cinq mots, chaque
  identifiant interne de la demande (identifiants de mémoire, SHA, numéros de
  PR, et les motifs que le projet déclare) : `- B-0012 — le lien mort du
  README signalé par la CI`. Un fichier protégé à faire approuver, comme
  chacun de ceux qu'une mise à jour change, s'y écrit sur une ligne
  d'empreinte (ADR-0058) : son chemin et son empreinte nouvelle (`sha256:`
  et seize caractères, ou `supprimé` comme `deleted`), rien d'autre
  (`- .socle/policy.toml sha256:0123456789abcdef`). Autour, sont admis :
  une puce (`-`, `*`, `+`) ou un numéro (`1.`, `1)`), une cellule de
  tableau, des accents graves ou du gras sur le chemin ou l'empreinte, un
  deux-points collé au chemin ou séparé, un tiret, un point médian, une
  flèche (`→`, `->`, `=>`) et une ponctuation finale. Une telle ligne n'a
  pas à être décrite et ne compte pas dans le budget de la demande :
  l'humain lit les fichiers dans la pull request, pas leurs empreintes. Un
  mot de plus sur la ligne, un chemin que la politique ne protège pas, un
  répertoire, un motif (`*`, `?`) ou un lien Markdown vers le fichier, et
  elle redevient de la prose, décrite et comptée.
- `socle new request` imprime ce contrat sous l'identifiant, avec les
  seuils du lint et le budget du projet : il se lit avant d'écrire la
  demande, pas au refus du lint. Avec `--questions`, il dit aussi la
  section « Questions » de ce gabarit et sa réponse libre.
- « Options » dit l'effort, le risque et la réversibilité ; « Conséquences »
  ce qui se passe si l'humain valide, refuse, ne répond pas ;
  « Recommandation » sépare le vérifié du supposé.
- « Réponses possibles » est une liste `` - `valeur` — sens `` qui propose
  les réponses de base, les mêmes dans toute demande : `valider` (la
  recommandation telle quelle, ou l'option recommandée), `refuser` et
  `contexte-insuffisant` ; une demande de choix y ajoute ses options, et le
  lint refuse un synonyme d'une réponse de base (`approuver`, `oui`…). Une
  demande qui nomme un test du projet ou une clé des seuils ne les change
  que sur `valider`, et les contrôles cherchent leur nom dans le texte de
  la demande validée ; un test du projet est celui de l'un de ses
  adaptateurs, quand il en a plusieurs (ADR-0051). Une décision en séance se consigne de même sous une
  réponse de base, ou sous une option que la question nomme entre accents
  graves. Les questions de départ que pose `socle init` suivent la règle
  (D-0054) : `valider` y applique tous les défauts. Les questions de cadrage
  d'un besoin (`socle new request --questions`, D-0067) aussi : `valider` y
  applique les hypothèses de l'agent, `reponses` porte le texte libre de
  l'humain.

La réponse vit dans `<demande>.answer.toml`. L'humain répond dans la
conversation, et l'agent consigne sa réponse avec le texte exact
(`socle answer D-NNNN <réponse> --relayed --by <nom> --quote-file <fichier>`,
`canal = "conversation"`) ; ou l'humain la lance lui-même au terminal
(`canal = "terminal"`). L'agent ne choisit jamais la réponse : il relaie
celle que l'humain a écrite, citation à l'appui.

```toml
reponse = "valider"
texte = "ok, mais garder l'ancien plafond une semaine"
par = "Théo"
date = "2026-10-11"
canal = "conversation"
citation = "ok pour 5, mais garde l'ancien plafond une semaine"   # texte exact de l'humain
empreinte = "sha256:…"   # le texte exact de la demande au moment de la réponse
```

L'état de la demande se dérive de la réponse : en attente, répondue, renvoyée
(`contexte-insuffisant` : l'agent la réécrit en une nouvelle demande),
retirée (métadonnée `retirée : <raison>`). Une demande répondue est gelée.

Une décision prise en séance est la forme courte d'une demande :
l'humain, présent, a tranché dans la conversation, de lui-même ou sur une
question courte posée dans le texte de la réponse, jamais dans le widget de
questions de l'agent. Ce qui demande du contexte, approuver un document
compris, est une demande. Elle s'écrit
avec sa réponse, d'un seul geste, par `socle decision "<question>"
<réponse> --relayed --by <nom> --quote-file <fichier>` : un titre, la
métadonnée `forme : séance`, une section `Question posée` qui garde la
question telle qu'il l'a lue, et sa réponse citée mot pour mot. `sujet :
<chemin>` nomme le document qu'elle approuve (`--about`). Elle ne passe pas
par le contrat des huit sections ; sans réponse, elle est hors contrat. Sa
question, transcription de la conversation, n'a pas à prouver ses lectures
par des empreintes, ni son titre ce que la question cite ; un identifiant
que seul le titre cite se prouve, et `socle decision` refuse de l'écrire
sans empreinte, la réponse écrite ne laissant plus corriger la décision.

Une décision que l'humain donne de lui-même, sans qu'on la lui ait
demandée, est une décision de séance sans question : `socle decision
"<la décision en une phrase>" --unprompted --relayed --by <nom>
--quote-file <fichier>` l'écrit avec la section `Décision donnée` à la
place de `Question posée`, qui garde son texte exact, et sa réponse, la
réponse de base `valider`, que le moteur pose sans qu'on la choisisse, son
texte cité. Elle autorise ce qu'elle nomme comme une demande validée. Ce
texte, comme une question posée, n'a pas à prouver ses lectures ; un
identifiant que seul le titre cite se prouve.

## La zone privée

Une mémoire privée est une option, choisie par l'humain dans la politique
(`[private] mode`). Elle vit sous `memory/private/`, avec la même
arborescence, les mêmes formats, statuts et contrôles, et les mêmes budgets
de taille que la zone publique ; ses identifiants prennent un `P` devant.
Le privé peut citer le public, jamais l'inverse.

| Mode | Où vit la mémoire privée | Ce que le moteur vérifie |
| --- | --- | --- |
| `compagnon` | le clone d'un dépôt privé dans `memory/private/`, que le dépôt public ignore | aucun fichier privé n'est commité dans le dépôt public ; le verrou `.socle/private.lock` désigne le commit du dépôt privé qui va avec chaque commit public ; rien de privé ne reste hors commit |
| `chiffre` | dans le dépôt public, chiffrée par un filtre git (git-crypt ou équivalent) | aucun fichier privé n'est commité en clair ; un filtre couvre `memory/private/` dans `.gitattributes` |

Le moteur ne connaît pas l'outil de chiffrement : un fichier privé est
lisible quand sa première ligne porte l'en-tête du socle (celui de la
mémoire, ou `# socle: termes privés` pour la liste des termes), chiffré
sinon. Sans accès à la mémoire privée, rien n'y est écrit : ni une entrée
(`socle new`), ni un terme.

**Indisponible.** Sans le clone du dépôt privé, ou sans la clé, la mémoire
privée est indisponible : l'état dérivé l'écrit au démarrage, et les
contrôles qui en dépendent le signalent, sans passer en silence. Un fichier
privé chiffré ici compte pour absent : il n'est ni lu ni jugé.

**Le verrou** (mode compagnon) s'écrit par `socle private lock`, une
fois les changements privés commités dans le dépôt privé ;
`socle private extract` remet la mémoire privée au commit du verrou, après un
retour à un ancien commit du code. En CI, `socle private recover` la clone au
verrou avec les secrets `SOCLE_PRIVE_DEPOT` et `SOCLE_PRIVE_CLE`.

**En CI**, le journal d'un dépôt public est public : un constat de la zone
privée n'y montre ni son texte ni son chemin.

**Le contenu nouveau est privé par défaut** quand une mémoire privée existe,
couche par couche : `[private] layers` nomme les couches dont `socle new`
écrit les entrées sous `memory/private/` (`canonique`, `backlog`,
`decisions`, `journal`, `demandes`). Sans ce réglage, toutes le sont sauf
les demandes, qui ne sont privées, réponses comprises, que si l'humain l'a
choisi (`[private] requests = true`), car il doit pouvoir les lire là où il
lit ; en mode chiffré, GitHub n'en montre que le chiffré, et l'agent les
donne en entier dans la conversation. Entrée par entrée, `--private` ou
`--public` l'emporte sur la couche : c'est ainsi qu'une consigne de
l'humain (« celle-ci en privé ») s'applique.

**Une entrée publique se bascule** dans la mémoire privée
(`socle private move <ID>`) : un fait, une entrée du backlog, une entrée de
journal ou une décision. Une copie privée, sous un identifiant privé, en reprend le
titre et le texte et cite `depuis : <ID>`. L'entrée publique garde son
identifiant, pour que les renvois restent valides, et rien d'autre :

```markdown
## B-0005 — Entrée basculée dans la mémoire privée

> basculée : 2026-10-12

Son contenu est dans la mémoire privée.
```

Le fichier d'une décision basculée prend le nom `ADR-NNNN-basculee.md` ;
les liens vers son ancien nom, et les ancres vers l'ancien titre d'une
entrée basculée, restent valides. Une entrée basculée ne change plus ;
une bascule sans copie privée qui reprenne son texte est un effacement, et
l'ajout seul la refuse. Une demande ne se bascule pas : elle se retire et se
pose à nouveau en privé ; une entrée de journal qui archive des faits non
plus. L'historique public garde l'ancien texte : seule une réécriture de
l'historique l'efface, et c'est à l'humain de la faire.

**La liste des termes privés** (`memory/private/terms.txt`) nomme ce qui ne
doit jamais paraître en public : un terme par ligne, `#` pour un
commentaire, `re:` devant une expression régulière ; la recherche ignore la
casse et les accents, trouve les mots d'un terme séparés par n'importe quels
séparateurs ou par rien (`acme corp`, `acme_corp`, `AcmeCorp`), et ne prend
que des mots entiers (une frontière : un séparateur, un passage
minuscule-majuscule ou lettre-chiffre). Sa première ligne
est `# socle: termes privés`. L'agent y ajoute librement
(`socle private term <terme>`) ; en retirer un exige une demande validée qui
cite la liste et son empreinte nouvelle. Un terme trouvé n'est jamais
réécrit, seulement désigné par son rang dans la liste.

**Les fuites** se cherchent à trois étages : le hook de l'agent (écritures
hors de la zone privée et noms des fichiers nouveaux, messages de commit,
pull requests et commentaires, y compris le texte qu'une commande publie
depuis un fichier, noms des branches créées ou poussées), les hooks git
(message de commit, nom de la branche poussée), et la CI (fichiers publics
modifiés et noms des nouveaux, archives comprises, messages des commits,
nom de la branche). Un identifiant privé se cherche aussi dans les blocs de
code d'un fichier public. Avec une mémoire privée, le document de cadrage
s'archive dans sa zone.

**La relecture avant publication** se règle par projet
(`[private] review`) : `aucune`, `chaque-push` ou `lots`. Avec les deux
dernières, un push vers le dépôt public attend que l'humain ait relu le
commit qui part : il le dit (`socle reviewed`), ou l'agent relaie son accord
donné dans la conversation, avec son texte exact
(`socle reviewed --relayed --by <nom> --quote-file <fichier>`).

## Langue de la mémoire

La mémoire s'écrit dans la langue du projet, `[memory] language` de la
politique : `fr` (le défaut) ou `en`, choisie à l'installation
(`socle install --language en`). Elle décide des mots-clés du format et des
gabarits que posent l'installeur et `socle new` : champs, statuts, en-têtes,
sections et réponses des demandes, section du socle d'`AGENTS.md`, lignes du
récap (`For you:` et `Next:` en anglais). Le contenu des entrées est écrit
par l'agent, dans la langue que les instructions du projet lui donnent.

**La lecture accepte toutes les langues**, quelle que soit celle du projet :
le moteur ramène chaque mot à sa clé interne. Une mémoire en ajout seul
garde les mots avec lesquels elle a été écrite ; un projet qui change de
langue n'a rien à réécrire, et ses entrées nouvelles prennent les mots de la
nouvelle. Les trailers de commit ont leurs deux noms (`Dispense-test` ou
`Waive-test`, `Dispense-doc` ou `Waive-doc`, `Corrige` ou `Fixes`), comme le
marqueur d'une tautologie voulue (`socle: voulu —` ou `socle: intended —`).
Les messages du moteur suivent la même langue, comme les
commentaires qu'il écrit dans les fichiers qu'il pose (le verrou du moteur,
l'en-tête d'une réponse `.answer.toml`, les workflows de CI), les textes des
adaptateurs maintenus et les descriptions de l'auto-test. Ce qu'il relit
lui-même s'écrit dans la langue du projet et se lit dans les deux : le
marqueur d'une valeur liée (`<!-- valeur:… -->` ou `<!-- value:… -->`), la
raison d'un plafond de mutation mesuré (`mesuré le … : N survivant(s)` ou
`measured on …: N survivor(s)`). Le statut d'une demande reste une valeur
interne, que `socle show` dit dans la langue du projet.

| Clé interne | Français | Anglais |
| --- | --- | --- |
| champ `statut` | statut | status |
| champ `preuve` | preuve | proof |
| champ `source` | source | source |
| champ `refutation` | réfutation | refutation |
| champ `validation` | validation | validation |
| champ `origine` | origine | origin |
| champ `ref` | ref | ref |
| champ `lu` | lu | read |
| champ `pour` | pour | for |
| champ `date` | date | date |
| champ `type` | type | type |
| champ `remplacee-par` | remplacée-par | superseded-by |
| champ `bloque` | bloque | blocks |
| champ `retiree` | retirée | withdrawn |
| champ `reformulee` | reformulée | reworded |
| champ `basculee` | basculée | made-private |
| champ `depuis` | depuis | from |
| champ `report` | report | deferred |
| champ `forme` | forme | form |
| champ `sujet` | sujet | about |
| champ `apres` | après | after |
| champ `priorite` | priorité | priority |
| champ `besoin` | besoin | need |
| champ `ancien` | ancien | former |
| valeur `seance` | séance | session |
| valeur `jalon` | jalon | milestone |
| valeur `lot` | lot | batch |
| valeur `haute` | haute | high |
| valeur `basse` | basse | low |
| section de tâche `fait-quand` | Fait quand | Done when |
| section de besoin `satisfait-quand` | Satisfait quand | Satisfied when |
| section de lot `revues` | Revues | Reviews |
| titre de passe `passe` | Passe | Pass |
| ligne de passe `commits` | Commits | Commits |
| ligne de passe `arbre` | arbre de travail | working tree |
| ligne de passe `bloquant` | Bloquant | Blocker |
| ligne de passe `ouvre` | Ouvre | Opens |
| statut F `mesure` | mesuré | measured |
| statut F `suppose` | supposé | assumed |
| statut F `refute` | réfuté | refuted |
| statut F `valide` | validé | validated |
| statut B, T, L, JA `ouvert` | ouvert | open |
| statut B, T, L, JA `en-cours` | en cours | in progress |
| statut B, T, L, JA `bloque` | bloqué | blocked |
| statut B, T, L, JA `fait` | fait | done |
| statut B, T, L, JA `abandonne` | abandonné | abandoned |
| statut ADR `proposee` | proposée | proposed |
| statut ADR `acceptee` | acceptée | accepted |
| statut ADR `remplacee` | remplacée | superseded |
| statut ADR `rejetee` | rejetée | rejected |
| statut ADR `abandonnee` | abandonnée | abandoned |
| valeur `humain` | humain | human |
| en-tête `couche` | couche | layer |
| en-tête `zone` | zone | zone |
| couche `canonique` | canonique | canonical |
| couche `actif` | actif | active |
| couche `decisions` | decisions | decisions |
| couche `journal` | journal | journal |
| couche `backlog` | backlog | backlog |
| couche `demandes` | demandes | requests |
| zone `publique` | publique | public |
| zone `privee` | privee | private |
| référence `commit` | commit | commit |
| référence `fichier` | fichier | file |
| référence `cmd` | cmd | cmd |
| référence `url` | url | url |
| section `decision-demandee` | Décision demandée | Decision requested |
| section `contexte` | Contexte | Context |
| section `elements-cites` | Éléments cités | Cited elements |
| section `ou-regarder` | Où regarder | Where to look |
| section `options` | Options | Options |
| section `consequences` | Conséquences | Consequences |
| section `recommandation` | Recommandation | Recommendation |
| section `reponses-possibles` | Réponses possibles | Possible answers |
| paragraphe `projet` du contexte | Le projet | The project |
| paragraphe `chantier` du contexte | Le chantier | The work |
| paragraphe `question` du contexte | La question | The question |
| réponse `valider` | valider | approve |
| réponse `refuser` | refuser | reject |
| réponse `contexte-insuffisant` | contexte-insuffisant | insufficient-context |

## Lecture prouvée

Chaque entrée a une empreinte, les huit premiers caractères du SHA-256 de
son titre et de son corps, sans sa ligne de métadonnées : changer un
statut, ce qu'une entrée attend ou ce qu'elle a lu ne périme pas ses
citations, et deux entrées qui se citent dans leurs métadonnées ne se
périment pas l'une l'autre. Une citation à l'empreinte du texte entier,
métadonnées comprises, celle d'avant cette règle, reste acceptée tant
qu'elle correspond. Chaque index a aussi une empreinte (`decisions@…`
pour toutes les décisions, `backlog@…` pour le backlog ouvert).
`socle show <ID>` et
`socle show --index decisions|backlog` les impriment avec le texte.

Citer `ADR-NNNN@xxxxxxxx`, c'est montrer qu'on a lu cette version-là. Une
citation ajoutée doit désigner la version actuelle de l'entrée, ou celle du
commit où la citation a paru ; une citation d'index, une version de l'index
dans la plage du travail, de sa base à l'arbre. Sinon elle est
périmée ou inventée, et refusée ; recopiée d'une autre entrée, elle se juge
comme une lecture neuve. Elle est obligatoire :

- dans une décision nouvelle : `lu : decisions@…`, et chaque entrée citée
  avec son empreinte ;
- dans une demande nouvelle : chaque entrée citée avec son empreinte ;
- dans une entrée nouvelle du backlog : `lu : backlog@…`, qui vaut aussi
  pour l'index sans les entrées que le même travail ajoute dans d'autres
  formes (un besoin, sa tâche et leur lot s'écrivent ensemble).

`socle new adr` et `socle new need|task|batch|milestone` affichent l'index
concerné et posent son empreinte dans le squelette. Une citation ancienne n'est pas revérifiée
quand l'entrée change ensuite : elle dit ce qui a été lu à l'époque.

## Ordre d'autorité

En cas de conflit : le code et les tests, puis la mémoire canonique, puis le
journal.
