# Spécification des adaptateurs

Ce document spécifie les adaptateurs : ce qu'ils sont, les champs qu'ils
déclarent, et ce que chaque adaptateur maintenu emploie. Il s'adresse à qui
choisit un adaptateur ou en écrit un pour un autre langage.

## Définition

Un adaptateur est un petit fichier de réglages, en TOML, qui apprend au socle
à faire **dans un langage donné** les quelques gestes qu'il ne peut pas
deviner : lancer les tests, reconnaître un test et une assertion dans un
fichier, rejouer un test seul, lancer la mutation.

## Pourquoi il en faut un

Le socle surveille trois choses : la mémoire, la documentation et les tests.
La mémoire et la documentation sont du markdown, que le moteur lit de la même
façon dans n'importe quel projet. Les tests, non : chaque langage les écrit
et les lance à sa manière.

Soit une règle du socle : **un correctif livre un test qui échoue sur le
commit d'avant**, preuve qu'il attrape le bogue corrigé. Pour l'appliquer, le
moteur doit :

1. trouver le test que le correctif ajoute : en Rust, une fonction précédée
   de `#[test]` ; en Python, une méthode dont le nom commence par `test` ;
2. lancer ce test seul sur le commit d'avant : `cargo test <nom>` en Rust,
   `python3 -m unittest <module>` en Python ;
3. constater qu'il échoue.

Le troisième geste est le même partout : le moteur le fait. Les deux premiers
dépendent du langage : l'adaptateur les lui dit. C'est comme un adaptateur de
prise électrique : l'appareil (le moteur) ne change pas, seule la prise (le
langage) change.

Sans adaptateur, le socle vérifierait encore la mémoire et la documentation,
mais il ne verrait rien des tests.

## Ce qu'il contient

Dix adaptateurs sont maintenus. Le tableau ci-dessous compare les trois
premiers ; celui de la section « Cinq langages de plus » compare les cinq
suivants, et les sections « C# » et « Kotlin » les deux derniers.
Ce sont des extraits : les fichiers font foi, [rust.toml](rust.toml),
[python.toml](python.toml), [python-pytest.toml](python-pytest.toml),
[javascript.toml](javascript.toml), [go.toml](go.toml),
[java.toml](java.toml), [ruby.toml](ruby.toml), [php.toml](php.toml),
[csharp.toml](csharp.toml) et [kotlin.toml](kotlin.toml). Les
deux adaptateurs Python ne diffèrent que par le lanceur de tests et la
mutation : `python` s'en tient à la bibliothèque standard (`unittest`), sans
mutation ; `python-pytest` prend pytest et mutmut, qui exige pytest.

| Ce que le moteur demande | Rust | Python (`unittest`) | Python (`pytest`) | Qui s'en sert |
| --- | --- | --- | --- | --- |
| Lancer les tests | `cargo test` | `unittest` | `pytest` | `socle verify`, hook de fin de tour, CI |
| Vérifier le code | `clippy` | compilation de chaque fichier | idem | idem |
| Vérifier le formatage | `cargo fmt` | absent : relecture du diff | idem | idem |
| Reconnaître une fonction de test | `fn` sous `#[test]` | `def test…` | idem | `tests.creux`, `tests.attendus` |
| Reconnaître une assertion | `assert!`, `assert_eq!`… | `assert`, `self.assert…` | `assert`, `pytest.raises` | `tests.creux` : un test sans assertion est refusé |
| Reconnaître un test désactivé | `#[ignore]` | `@unittest.skip` | `@pytest.mark.skip`, `xfail` | `tests.creux` : désactivé sans raison écrite, refusé |
| Rejouer un test sur le commit d'avant | `cargo test` d'un fichier de `tests/`, ou d'un test de son module par son nom | `unittest` d'un module | `pytest` d'un fichier | `tests.regression` |
| Mesurer la mutation | `cargo-mutants` | absente | `mutmut` | `mutation.couverture`, `socle mutation-run`, `socle mutation-verdict` |
| Dire quel code doit être testé, et quelles fonctions sont privées | `src/`, `fn` sans `pub` | hors `tests/`, `def _…` | idem | `tests.code-teste` : une fonction publique ajoutée ou modifiée est nommée par un test |

La mutation consiste à modifier le code exprès (changer un `+` en `-`, un
`<` en `<=`) et à vérifier qu'un test au moins échoue. Un « mutant » qui
survit montre du code qu'aucun test ne vérifie vraiment.

Sans section `[code]`, le code à tester est celui des sources, hors
fichiers de test, et toute fonction compte comme publique.

Une étape marquée `fast = true` tourne à la fin de chaque tour, avant
chaque push et quand l'agent lance `verify --fast` ; la CI les lance
toutes. Pendant les étapes rapides, le moteur pose la variable
`SOCLE_RAPIDE` : un test trop long pour une fin de tour s'y met de côté,
avec sa raison écrite, et la CI le joue toujours. Sous `unittest` :
`@unittest.skipIf(os.environ.get("SOCLE_RAPIDE"), "…")`.

Un projet qui commence n'a pas encore de test, et plusieurs outils le
disent par un échec (`unittest` : « NO TESTS RAN », ou un dossier `tests/`
absent ; pytest : « no tests ran »). La clé `no_tests` de la capacité
`tests` reconnaît ce cas dans la sortie : `verify` en fait un
avertissement, pas un échec. Les deux adaptateurs Python la déclarent ; un
autre l'ajoute quand son outil se comporte ainsi. Avant même son premier
fichier source (aucun fichier `sources`, hors du dossier du socle et des
fichiers tiers), un projet neuf n'a rien à compiler ni à tester : `verify`
ne lance pas les capacités, et le dit en avertissement.

Les étapes `ci_setup` installent les outils de l'adaptateur dans la CI,
avant le socle. L'agent en a besoin aussi, là où il travaille :
l'installeur cite leurs commandes parmi les étapes qui suivent, et un
`verify` qui échoue faute d'outil les rappelle.

Un adaptateur se pose souvent avant le premier fichier de son langage. Une
étape de `ci_setup` qui exige un fichier de build (un cache de dépendances,
`npm ci`, `composer install`, `dotnet restore`) attend ce fichier, par une
condition sur sa présence, dont les motifs sont une part de ceux que l'outil
lit (B-0179) : tant qu'il manque, l'étape est sautée, et elle ne peut donc
pas échouer faute de lui. La règle ne garantit rien de plus : un fichier de
build présent mais incomplet (un `package.json` sans verrou) fait échouer
l'étape, nettement. Ainsi, sous Kotlin :

```yaml
      - uses: actions/setup-java@v5
        if: hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') != ''
        with:
          cache: gradle
```

Le cache sert dès le premier fichier, sans réinstaller le socle. La
condition saute toute l'étape, l'installation de l'outil comprise (le JDK
sous Kotlin et Java) : c'est la seule forme sûre sans pouvoir l'essayer. Le
moteur lit la même condition sur les fichiers du projet : une commande qui
attend son fichier de build, l'installeur ne la donne pas à l'agent, et le
hook de démarrage d'une session cloud ne la lance pas ; tous deux disent
qu'elle attend. Une étape dont l'outil se passe lui-même du fichier absent
n'a pas de condition : `ruby/setup-ruby` saute `bundle install` et son cache
sans `Gemfile`, et le cache d'`actions/setup-go` se dit en avertissement
sans `go.sum`. Les capacités, elles, ne tournent pas avant le premier
fichier `sources`, comme dit plus haut. Le texte du workflow est jugé par
les tests ; son exécution, seulement sur GitHub.

## Une capacité absente se déclare

Chaque capacité est soit une commande, soit déclarée absente avec ce qui la
remplace. Rien ne manque en silence : le contrôle `adaptateur.capacites`
refuse une capacité ni fournie ni déclarée. L'adaptateur Python déclare ainsi
le formatage absent (la bibliothèque standard n'a pas de formateur) et la
mutation absente (mutmut exige pytest : l'adaptateur `python-pytest` la
fournit).

## Où il vit

- Les adaptateurs maintenus sont dans ce dossier.
- L'installeur copie celui qu'on choisit (`socle install --adapter rust`)
  dans le projet, sous `.socle/adapter.toml`. Le projet y ajoute ses
  étapes propres, par exemple un banc de performance, et y nomme ce qui lui
  est propre : sous `python-pytest`, les modules soumis à la mutation, quand
  son paquet n'est pas sous `src/`.
- Ce fichier est **protégé** : seul l'humain le modifie. Un agent qui
  remplacerait la commande des tests par une commande qui réussit toujours
  rendrait tous les contrôles de tests aveugles.
- Ce dépôt est lui-même écrit en Python : son
  [adaptateur](../../../.socle/adapter.toml) est l'adaptateur Python.
  Le socle ne marche donc pas que pour Rust : il tourne en Python ici, à
  chaque commit.

## Un projet en plusieurs langages

Un projet peut en écrire plusieurs, une app et ses outils, un serveur et son
client : il a alors un adaptateur par langage (ADR-0051).

- **Où ils vivent.** Le principal reste `.socle/adapter.toml` ; les autres
  vont dans `.socle/adapters/<nom>.toml`, au même format. Tous sont
  protégés, et tous jugent de la même façon : aucun ne passe avant un autre.
  Chacun déclare son langage (`language`) : l'installeur n'en pose pas deux
  pour le même, et n'en ajoute aucun en automatique à un principal qui ne
  dit pas le sien.
- **Qui juge quel fichier.** Chaque fichier est jugé par l'adaptateur dont
  les motifs le désignent : ses sources, son code ou ses tests. Le contrôle
  `adaptateur.recouvrement` refuse un fichier que deux adaptateurs
  désignent, en les nommant. L'ambiguïté se règle en resserrant les motifs
  d'une copie, par une demande.
- **Les règles des tests.** Chaque contrôle qui lit l'adaptateur tourne une
  fois par adaptateur, avec ses seuls motifs, et ses constats nomment
  l'adaptateur (`kotlin : test … sans assertion`). Une fonction Kotlin se
  teste en Kotlin. Un correctif livre un test dans le langage du code qu'il
  corrige (sa section `[code]`), et dans chacun s'il en corrige plusieurs ;
  un test ajouté dans un autre langage ne fait pas de lui un langage du
  code corrigé. Un correctif qui ne touche le code d'aucun revient au
  langage de ses tests, sinon au principal. Un correctif qui ne touche
  aucun fichier qu'un adaptateur juge est refusé, en nommant ses fichiers :
  aucun test ne peut le prouver ; une demande que l'humain valide, qui
  nomme son commit dans son texte, l'admet sans test (D-0088, ADR-0054).
  Un correctif qui ne touche que des fichiers déclarés tiers n'est pas
  jugé.
- **La vérification.** `verify` lance les étapes de chaque adaptateur, l'un
  après l'autre et jusqu'au bout, chacune nommée `verify.<adaptateur>.<étape>`
  (`verify.kotlin.tests`). La CI installe les outils de tous.
- **La mutation.** Chaque adaptateur balaie ses modules avec son outil, et ne
  juge que leurs plafonds ; un plafond qu'aucun ne désigne revient au
  principal. Les plafonds restent tenus par module, dans les garde-fous.
  `socle mutation-verdict <dossier> --adapter <nom>` juge les résultats d'un
  seul outil. Le balayage planifié du socle se pose tant qu'un outil n'a
  pas son propre workflow dans le projet.
- **L'installation.** `socle install --adapter python-pytest --adapter
  kotlin` : le premier nommé prend `.socle/adapter.toml`. En automatique,
  l'installeur en pose un par langage qu'il reconnaît, hors des fichiers
  tiers ; un langage dont le manifeste n'est que dans un sous-dossier (un
  `ui/package.json` sans `package.json` à la racine) n'en reçoit pas, ses
  commandes se lançant à la racine, et l'installeur le dit. Sauf si ce
  qu'il lance tourne de la racine : Gradle, dès que la racine a son wrapper
  ou un fichier de build (`gradlew`, `settings.gradle`, `build.gradle`, ou
  leurs `.kts`) ; Python, sous pytest, qui parcourt les sous-dossiers, ou
  avec un dossier `tests/` à la racine, que lit `unittest discover -s
  tests`.
  `--adapter` prend aussi le chemin d'un adaptateur propre au projet (un
  `.toml`), jugé par ce contrat avant d'être posé, puis gardé aux mises à
  jour comme une copie adaptée. Un langage ajouté à un projet déjà équipé voit ses modules entrer
  « à mesurer » au cliquet de mutation.
- **La mise à jour.** Elle rafraîchit chaque copie d'un adaptateur
  maintenu, la principale comprise, que le projet n'a pas adaptée : celle
  dont le texte est une version de l'adaptateur que le moteur du projet a
  portée, dans le moteur installé ou dans l'historique git ; l'humain
  l'approuve comme tout fichier protégé. Une copie adaptée se garde, ses
  motifs resserrés comme ses commandes : l'installeur dit, en avertissement,
  quand son adaptateur maintenu a changé depuis le moteur installé, et
  l'agent propose à l'humain, par une demande, d'y reporter les
  corrections. La CI se génère des adaptateurs du projet tels qu'ils sont
  (ADR-0052).

Un projet à un seul langage ne change rien : il n'a que son adaptateur
principal.

## Pour un autre langage

On écrit un nouveau fichier, avec les mêmes clés ; le moteur ne change pas.
Une seule exception : si l'outil de mutation du langage est nouveau, le
moteur doit apprendre à lire ses résultats (`engine/socle/mutation.py`, une
fonction par outil ; il en connaît sept : `cargo-mutants`, `mutmut`,
`stryker` (Stryker pour JavaScript, Stryker.NET pour C#), `gremlins`, `pit`,
`mutant` et `infection`). Puis on l'éprouve sur un projet jetable, comme le
fait `bench/adapters.py` pour les six derniers.

Les clés qui décrivent un langage, toutes facultatives sauf `function` :

| Clé | Ce qu'elle dit | Exemple |
| --- | --- | --- |
| `function` | une fonction ou un test ; le premier groupe trouvé est son nom | `^\s*func\s+(\w+)` |
| `marker_attribute`, `marker_name`, `marker_line` | ce qui fait un test : un attribut au-dessus, son nom, ou sa ligne | `#[test]`, `^test`, `test("…", …)` |
| `block` | la forme d'un bloc : `braces`, `indent` ou `end` | `end` pour Ruby |
| `expression_body` | une fonction écrite en expression, sans bloc : son corps commence au premier groupe, et va jusqu'aux lignes suivantes plus indentées | `fun f(x: Int) = 2 * x` en Kotlin |
| `strings`, `line_comment` | les littéraux et le commentaire de fin de ligne, où une accolade ne compte pas | chaînes entre accents graves de JavaScript |
| `block_comment` | un commentaire de bloc, ou une docstring : un mot qui y figure n'affirme ni n'appelle rien | `/\*[\s\S]*?\*/` |
| `assertion` | ce qui affirme ; un test sans assertion est creux | `\bexpect\s*\(` |
| `expected` | les lignes qui portent une valeur attendue, si ce ne sont pas les assertions | en Go, `if got != 4 {` |
| `ignore`, `ignore_reason` | un test désactivé, et sa raison écrite ; lus sur ses attributs, sa ligne et son corps | `t.Skip()` |
| `shared`, `copied` (régression) | les dépendances installées que le worktree de la régression lie ou copie | `node_modules`, `vendor` |
| `modules_exclude` (mutation) | ce que l'outil ne mute pas | `**/*_test.go` |
| `command` (mutation) | le balayage ; avec `{module}`, il se lance une fois par module du plafond, et `{output}` lui donne son propre dossier de résultats, sans quoi chaque module écraserait le précédent | `cargo mutants --file {module} --output {output}` |
| `install` (mutation) | ce qui pose l'outil sur le runner du balayage hebdomadaire, quand rien d'autre ne le fait | `cargo install cargo-mutants --locked` |
| `test_arg` (régression) | un argument par test rejoué ; `{file}`, `{stem}`, `{module}` ou `{dir}` | `./{dir}` en Go |
| `test_arg_separator` (régression) | ce qui joint les arguments de plusieurs tests rejoués ; une espace sinon | `,` pour `-Dtest=` de Maven, `\|` pour le filtre de `dotnet test` |
| `load_error` (régression) | ce qui, dans la sortie, dit que le test ne s'est pas chargé sur le parent : il y échoue pour une autre raison que le défaut | `\[build failed\]` en Go |
| `module_command` (régression) | la commande qui lance, par leurs noms (`{names}`), des tests écrits dans le module qu'ils testent ; sur le parent, seules leurs lignes de test s'appliquent | `cargo test --workspace -- {names}` |
| `test_module` | ce qui ouvre un module de tests dans un fichier de code : ses aides suivent le test sur le parent | `#[cfg(test)]` |

## JavaScript, Go, Java, Ruby et PHP

Chaque adaptateur emploie l'outil de tests et l'outil de mutation les plus
courants de son langage :

| Ce que le moteur demande | JavaScript, TypeScript | Go | Java | Ruby | PHP |
| --- | --- | --- | --- | --- | --- |
| Lancer les tests | `vitest` | `go test` | Maven, JUnit 5 | RSpec | PHPUnit |
| Vérifier le code | absent : les tests chargent chaque module | `go vet`, `go build` | `javac` | `ruby -wc` | `php -l` |
| Vérifier le formatage | absent : relecture du diff | `gofmt` | absent | absent | absent |
| Reconnaître un test | `test("…")`, `it("…")` | `func TestX` | `@Test` | `it "…" do` | `function testX`, `#[Test]` |
| Reconnaître un test désactivé | `test.skip`, `xit` | `t.Skip` | `@Disabled` | `xit`, `skip` | `markTestSkipped` |
| Rejouer un test sur le commit d'avant | `vitest` d'un fichier | `go test` de son paquet | `-Dtest=` de sa classe | `rspec` d'un fichier | `phpunit` d'un fichier |
| Mesurer la mutation | Stryker | gremlins | PIT | mutant | Infection |
| Dire quelles fonctions sont privées | non exportées | nom en minuscule | sans `public` | `private def` | `private`, `protected` |

Chaque outil de mutation lit la configuration du projet : `stryker.config.json`,
la section PIT du `pom.xml`, `mutant.yml`, `infection.json5` ; gremlins n'en
demande pas. Infection exige un pilote de couverture (pcov ou xdebug).

## C#

| Ce que le moteur demande | C# |
| --- | --- |
| Lancer les tests | `dotnet test` (xUnit, NUnit ou MSTest) |
| Vérifier le code | `dotnet build`, le compilateur et ses analyseurs par défaut |
| Vérifier le formatage | `dotnet format whitespace`, en mode dossier : deux secondes, sans construire |
| Reconnaître un test | `[Fact]`, `[Theory]`, `[Test]`, `[TestCase]`, `[TestMethod]` |
| Reconnaître un test désactivé | `Skip = "…"`, `[Ignore]`, `[Explicit]`, `Assert.Inconclusive` ; la raison, en trois caractères au moins |
| Rejouer un test sur le commit d'avant | `dotnet test --filter` de sa classe, du nom de son fichier ; plusieurs, jointes par `\|` |
| Mesurer la mutation | Stryker.NET, épinglé dans le manifeste d'outils du projet |
| Dire quelles fonctions sont privées | sans `public` |

Le dépôt porte une solution, ou un projet, à sa racine : l'installeur le
reconnaît à son `*.sln`, `*.slnx` ou `*.csproj`, avant un `package.json`
qu'un projet web porte souvent pour ses ressources, et les commandes de .NET
l'y trouvent seules. Stryker.NET écrit le rapport du même schéma que
Stryker, sous un autre nom (`mutation-report.json`) et avec des chemins
absolus : le lecteur de Stryker lit les deux. Un fichier qui ne déclare que
des types (un `record` sans corps, une interface) n'a rien à muter ; il
n'entre pas au plafond. La version 5 de Stryker.NET exige un SDK plus récent
que .NET 8 : le manifeste d'outils épingle la 4.16.0, et la CI pose les
deux SDK de support long.

## Kotlin

| Ce que le moteur demande | Kotlin |
| --- | --- |
| Lancer les tests | `./gradlew test` (kotlin.test ou JUnit 5, sous `useJUnitPlatform()`) |
| Vérifier le code | `./gradlew testClasses`, le compilateur Kotlin et ses avertissements |
| Reconnaître un test | `@Test` de kotlin.test, de JUnit 4 ou de JUnit 5, au-dessus de `fun` ou sur sa ligne ; un nom entre accents graves compte ; une fonction en expression (`fun t() = …`) a son corps après le `=` |
| Reconnaître une assertion | kotlin.test et JUnit (`assert…`, `fail`), MockK et Mockito (`verify`, `coVerify`), kotest (`shouldBe`…) |
| Reconnaître un test désactivé | `@Ignore` (kotlin.test, JUnit 4), `@Disabled` (JUnit 5) ; la raison, dans `@Disabled("…")`, `@Ignore("…")`, ou un commentaire après l'`@Ignore` de kotlin.test, qui n'en prend pas |
| Rejouer un test sur le commit d'avant | `./gradlew test --tests '*<Classe>'`, du nom de son fichier |
| Mesurer la mutation | PIT, par le greffon Gradle `info.solidsoft.pitest`, en XML sans horodatage, dans chaque module où il est appliqué ; un fichier sans corps de fonction (une interface, des `expect`) n'entre pas au plafond |
| Dire quelles fonctions sont privées | `private` ou `internal` : tout le reste est public, `protected` compris |

L'installeur reconnaît Kotlin à son build Gradle écrit en Kotlin
(`build.gradle.kts` ou `settings.gradle.kts`), pourvu que le dépôt porte une
source `.kt` hors de `buildSrc/` : un projet Java sous Gradle porte le même
build, et souvent des greffons de construction en Kotlin. PIT ne connaît que
le paquet et le nom du fichier source : son lecteur retrouve le fichier dans
le dépôt, rangé sous son paquet, sinon le seul de ce nom qui déclare ce
paquet. Les sources se cherchent sous `src/*/kotlin` comme sous `src/*/java`,
la disposition d'Android Studio. Un projet à plusieurs modules déclare
`filter { isFailOnNoMatchingTests = false }` dans ses tâches de test : le
rejeu filtre par classe à la racine. Le rejeu nomme la classe d'après le
fichier du test : une classe de test nommée autrement que son fichier ne s'y
trouve pas, et le correctif est refusé, Gradle ne trouvant aucun test ; et
le filtre `*CalcTest` lance aussi `BigCalcTest`, sans fausser le verdict,
qui exige encore le succès sur le correctif. Un projet multiplateforme ou Android,
dont les tâches de Gradle ont d'autres noms (`testDebugUnitTest`) et dont la
mutation passe par un autre greffon, adapte les commandes dans sa copie,
qu'une mise à jour garde.
