"""Le catalogue anglais des messages du moteur : le texte français,
tel qu'il est écrit dans le code, vers sa traduction. Les variables `{nom}`
sont les mêmes des deux côtés ; `tests/test_messages.py` le vérifie, et
qu'aucun message enveloppé n'y manque."""

MESSAGES: dict[str, str] = {
    "socle — commit refusé : un second commit dans la même commande que le précédent. Le filtre de l'agent ne "
    "passe qu'une fois par commande, et chaque commit d'agent doit le passer : lancer ce commit dans une commande "
    "à part.":
        "socle — commit refused: a second commit in the same command as the previous one. The agent's filter only "
        "runs once per command, and each agent commit must go through it: run this commit in a separate command.",
    "push sur {protegee}, prise pour la branche par défaut faute de mieux : ce clone n'a ni `origin/HEAD`, ni "
    "`main`, ni `master`. Si la branche par défaut du dépôt distant est une autre, `git fetch origin <elle>` la fait "
    "connaître ; relancer ensuite le push":
        "push to {protegee}, taken for the default branch for want of better: this clone has no `origin/HEAD`, no "
        "`main`, no `master`. If the remote repository's default branch is another one, `git fetch origin <it>` "
        "makes it known; then run the push again",
    "  ^ devinée : ce clone n'a ni `origin/HEAD`, ni `main`, ni `master` ; si la branche par défaut du dépôt distant "
    "est une autre, `git fetch origin <elle>` la fait connaître":
        "  ^ guessed: this clone has no `origin/HEAD`, no `main`, no `master`; if the remote repository's default "
        "branch is another one, `git fetch origin <it>` makes it known",
    "sujet `{ident}` disparu du backlog : un sujet clos se range par `socle archive`, il ne s'efface pas":
        "topic `{ident}` gone from the backlog: a closed topic is filed by `socle archive`, it is not erased",
    "range les sujets clos du backlog à l'écart des ouverts":
        "files the closed backlog topics apart from the open ones",
    "\n!! hooks git non branchés : `git config core.hooksPath .socle/git-hooks`":
        "\n!! git hooks not wired: `git config core.hooksPath .socle/git-hooks`",
    "SHA fabriqué : {sha} n'est pas un objet de ce dépôt, alors que son préfixe {prefixe} en est un. Le SHA complet "
    "de {prefixe} est {reel}. Ne jamais compléter un SHA de tête : `git rev-parse`.":
        "Fabricated SHA: {sha} is not an object of this repository, while its prefix {prefixe} is. The full SHA of "
        "{prefixe} is {reel}. Never complete a SHA from memory: `git rev-parse`.",
    "`{ident}@{h}` (ligne {ligne}) n'est pas l'empreinte de la version actuelle de {ident} : la relire, `python3 "
    ".socle/socle show {ident}`":
        "`{ident}@{h}` (line {ligne}) is not the fingerprint of the current version of {ident}: read it again, "
        "`python3 .socle/socle show {ident}`",
    "`{index}@{h}` (ligne {ligne}) n'est l'empreinte d'aucune version récente de l'index : le relire, `python3 "
    ".socle/socle show --index {index}`":
        "`{index}@{h}` (line {ligne}) is not the fingerprint of any recent version of the index: read it again, "
        "`python3 .socle/socle show --index {index}`",
    "`{ident}` (ligne {ligne}) ne désigne aucune entrée de la mémoire — créer l'entrée d'abord, ou corriger "
    "l'identifiant ; ne jamais en inventer un":
        "`{ident}` (line {ligne}) names no entry of the memory — create the entry first, or fix the identifier; "
        "never invent one",
    "`commit:{cible}` n'existe pas dans ce dépôt — lire le SHA avec `git rev-parse`, jamais de tête":
        "`commit:{cible}` does not exist in this repository — read the SHA with `git rev-parse`, never from memory",
    "`{id}` passe à « validé » sans demande validée par l'humain : ce statut ne s'écrit que par l'humain (politique, "
    "point 5). Émettre une demande `D-NNNN`.":
        "`{id}` becomes “validated” without a request approved by the human: this status is only written by the "
        "human (policy, rule 5). Open a request `D-NNNN`.",
    "{chemin}/ (dont {touche})":
        "{chemin}/ (including {touche})",
    "push forcé":
        "force push",
    "suppression d'une branche distante":
        "deletion of a remote branch",
    "push de toutes les références":
        "push of all references",
    "push forcé (+)":
        "force push (+)",
    "push sur la branche par défaut ({protegee})":
        "push to the default branch ({protegee})",
    "action externe ou irréversible ({outil}) : validation humaine requise (politique, point 4), et une demande "
    "validée ne la débloque pas : l'action revient à l'humain. Émettre une demande, travailler sur autre "
    "chose en attendant.":
        "external or irreversible action ({outil}): human approval required (policy, rule 4), and an approved "
        "request does not unlock it: the action falls to the human. Open a request, work on something "
        "else meanwhile.",
    "commande irréversible ou externe ({action}) : « {commande} » — validation humaine requise (politique, point 4), "
    "et une demande validée ne la débloque pas : l'action revient à l'humain. Si c'est une décision, "
    "émettre une demande `D-NNNN` ; une fois l'action décidée, l'inscrire au backlog avec `pour : humain`, sa "
    "commande exacte, où la lancer et ce qu'elle doit produire. Puis continuer sur autre chose.":
        "irreversible or external command ({action}): “{commande}” — human approval required (policy, rule 4), and "
        "an approved request does not unlock it: the action falls to the human. If it is a decision, open "
        "a request `D-NNNN`; once the action is decided, add it to the backlog with `for : human`, its exact "
        "command, where to run it and what it must produce. Then go on with something else.",
    "`{saut}` contourne les hooks du projet : la CI exécute tout, et rien ne la contourne. Corriger ce que le hook "
    "refuse ; s'il refuse à tort, l'inscrire au backlog et le dire à l'humain.":
        "`{saut}` bypasses the project's hooks: the CI runs everything, and nothing bypasses it. Fix what the hook "
        "refuses; if it refuses wrongly, add it to the backlog and tell the human.",
    "`socle private install` est réservé à l'humain : il pousse vers le dépôt privé et crée une clé de déploiement "
    "(politique, point 4). L'inscrire au backlog avec `pour : humain`.":
        "`socle private install` is reserved for the human: it pushes to the private repository and creates a deploy "
        "key (policy, rule 4). Add it to the backlog with `for : human`.",
    "`socle approve` est réservé à l'humain : il valide ses propres changements protégés.":
        "`socle approve` is reserved for the human: it approves their own protected changes.",
    "l'agent ne répond jamais à la place de l'humain. Il ne peut que relayer une réponse donnée dans la conversation "
    ": `socle answer D-NNNN <réponse> --relayed --by <nom> --quote-file <texte exact>`, `socle decision "
    "\"<question>\" <réponse> --relayed --by <nom> --quote-file <texte exact>` pour une décision prise en séance"
    ", ou `socle reviewed --relayed --by <nom> --quote-file <texte exact>` pour une relecture avant "
    "publication.":
        "the agent never answers in the human's place. It can only relay an answer given in the conversation: `socle "
        "answer D-NNNN <answer> --relayed --by <name> --quote-file <exact text>`, `socle decision "
        "\"<question>\" <answer> --relayed --by <name> --quote-file <exact text>` for a decision taken in session"
        ", or `socle reviewed --relayed --by <name> --quote-file <exact text>` for a review before "
        "publication.",
    "`{reglage}` : les réglages de Claude Code commandent ses hooks, seul l'humain les modifie (un réglage local "
    "peut les couper tous).":
        "`{reglage}`: Claude Code's settings drive its hooks, only the human changes them (a local setting can turn "
        "them all off).",
    "écriture d'un fichier protégé ({cible}) par le shell : seul l'humain modifie la politique, les hooks, la CI et "
    "le moteur (relance de l'installeur).":
        "write to a protected file ({cible}) through the shell: only the human changes the policy, the hooks, the CI "
        "and the engine (by running the installer again).",
    "`{chemin}` : les réglages de Claude Code commandent ses hooks, seul l'humain les modifie (un réglage local peut "
    "les couper tous).":
        "`{chemin}`: Claude Code's settings drive its hooks, only the human changes them (a local setting can turn "
        "them all off).",
    "`{rel}` est protégé par la politique : seul l'humain le modifie (CODEOWNERS), ou l'installeur pour les hooks, "
    "la CI et le moteur. Proposer le changement par une demande.":
        "`{rel}` is protected by the policy: only the human changes it (CODEOWNERS), or the installer for the hooks, "
        "the CI and the engine. Propose the change in a request.",
    "référence inventée — {fautes}":
        "invented reference — {fautes}",
    "demande hors contrat (elle doit se lire sans le projet en tête) — {fautes} ; la procédure : le skill "
    "`socle-request`":
        "request out of contract (it must read without the project in mind) — {fautes}; the procedure: the skill "
        "`socle-request`",
    "fuite de la mémoire privée : {termes}. Une écriture publique ne cite ni identifiant privé ni terme de la liste "
    "privée : reformuler sans eux (politique, mémoire privée ; le skill `socle-private-memory`).":
        "private memory leak: {termes}. A public write cites neither a private identifier nor a term of the private "
        "list: rephrase without them (policy, private memory; the skill `socle-private-memory`).",
    "contrôles de fin de tour (`socle check --stage agent`)":
        "end-of-turn checks (`socle check --stage agent`)",
    "Les contrôles échouent encore après {essais} tentatives : ARRÊT ET ESCALADE (politique, point 7). Écrire une "
    "demande `D-NNNN` qui résume l'échec, ce qui a été tenté et ce qui est supposé, puis s'arrêter.\n\n{rapport}":
        "The checks still fail after {essais} attempts: STOP AND ESCALATE (policy, rule 7). Write a request `D-NNNN` "
        "that sums up the failure, what was tried and what is assumed, then stop.\n\n{rapport}",
    "Les contrôles échouent (tentative {essais}/{maximum}) : corriger avant de conclure.\n\n{rapport}":
        "The checks fail (attempt {essais}/{maximum}): fix them before concluding.\n\n{rapport}",
    "récap de fin d'intervention non vérifiable : transcript illisible":
        "end-of-intervention recap cannot be checked: unreadable transcript",
    "sans {manque}":
        "without {manque}",
    "{n} lien(s) que l'humain ne pourra pas suivre":
        "{n} link(s) the human will not be able to follow",
    "fin d'intervention {defauts}, malgré un rappel":
        "end of intervention {defauts}, despite a reminder",
    "(le chantier actif n'a pas de section « Prochaines étapes »)":
        "(the active work has no “Next steps” section)",
    "Tu as agi pendant ce tour, et ton dernier message n'a pas {manque}. Termine par un récap de ce qui a été fait, "
    "puis :\n- « Pour toi : » ce qui revient à l'humain — décisions, actions qu'il est seul à pouvoir faire — ou « "
    "rien » ;\n- « Ensuite : » la suite proposée (prochain jalon, ce qu'il reste à faire avant), et ce que tu "
    "attends, s'il y a lieu (une CI, un match : quoi, et jusqu'à quand).\n\nCe qui revient à l'humain, calculé "
    "maintenant :\n{liste}\n\nProchaines étapes, selon le chantier actif :\n{suite}":
        "You acted during this turn, and your last message lacks {manque}. End with a recap of what was done, "
        "then:\n- “For you:” what falls to the human — decisions, actions only they can do — or “nothing”;\n- "
        "“Next:” the proposed next step (next milestone, what remains to do before it), and what you are waiting "
        "for, if anything (a CI run, a match: what, and until when).\n\nWhat falls to the human, computed "
        "now:\n{liste}\n\nNext steps, according to the active work:\n{suite}",
    " ni ":
        " and ",
    "Ton dernier message contient des liens que l'humain ne pourra pas suivre : il lit dans la conversation ou sur "
    "GitHub, pas dans ton conteneur.\n{liens}\nDonne un fichier par son permalien (`socle url <chemin|ID>`, après le "
    "push) ; n'écris entre accents graves que des chemins qui existent dans ce dépôt, et ceux d'un autre dépôt sous "
    "la forme `depot:chemin`.":
        "Your last message contains links the human will not be able to follow: they read in the conversation or on "
        "GitHub, not in your container.\n{liens}\nGive a file by its permalink (`socle url <path|ID>`, after the "
        "push); only put between backticks paths that exist in this repository, and those of another repository as "
        "`repo:path`.",
    "Ton dernier message cite {demandes}, en attente de l'humain, sans son lien : il doit pouvoir l'ouvrir d'un "
    "clic. Ajoute la sortie de `socle url {ids}`.":
        "Your last message cites {demandes}, waiting for the human, without its link: they must be able to open it "
        "in one click. Add the output of `socle url {ids}`.",
    "socle — contrôles avant commit":
        "socle — checks before commit",
    "\nFichiers protégés : si c'est l'humain qui les a changés (une mise à jour du socle, sa politique), `python3 "
    ".socle/socle approve --text \"<raison>\"` les liste et les approuve — réservé à l'humain ; l'agent, lui, ouvre "
    "une demande.":
        "\nProtected files: if the human changed them (a socle update, their policy), `python3 .socle/socle approve "
        "--text \"<reason>\"` lists and approves them — reserved for the human; the agent opens a request instead.",
    "\nCommit refusé. `git commit --no-verify` contourne ce hook, jamais la CI.":
        "\nCommit refused. `git commit --no-verify` bypasses this hook, never the CI.",
    "refus : {geste} est réservé à l'humain, et cette commande tourne dans une session d'agent (CLAUDECODE) — "
    "l'humain la lance dans son propre terminal":
        "refused: {geste} is reserved for the human, and this command runs in an agent session (CLAUDECODE) — the "
        "human runs it in their own terminal",
    "socle — commit refusé : {faute}":
        "socle — commit refused: {faute}",
    "socle — avertissement : ce correctif n'ajoute ni ne change aucun test ({liste}) : la CI le refusera "
    "(`tests.regression`), faute d'un test qui échoue sur le commit d'avant. L'ajouter à ce commit (`git commit "
    "--amend`), tant qu'il n'est pas poussé.":
        "socle — warning: this fix adds or changes no test ({liste}): the CI will refuse it (`tests.regression`), "
        "for lack of a test that fails on the previous commit. Add it to this commit (`git commit --amend`), as long "
        "as it is not pushed.",
    "socle — avertissement : commit d'agent sans aucun hook de l'agent pendant sa session (`Socle-Hooks: {valeurs}`) "
    ": la CI le refusera (`hooks.trace`). ":
        "socle — warning: agent commit without any agent hook during its session (`Socle-Hooks: {valeurs}`): the CI "
        "will refuse it (`hooks.trace`). ",
    "socle — avertissement : commit d'agent sans aucun hook de l'agent depuis le commit précédent "
    "(`Socle-Hooks-Since-Commit: {depuis}`) : ses hooks ont cessé de tirer en cours de session, et la CI le refusera "
    "(`hooks.trace`). ":
        "socle — warning: agent commit without any agent hook since the previous commit (`Socle-Hooks-Since-Commit: "
        "{depuis}`): its hooks stopped firing during the session, and the CI will refuse it (`hooks.trace`). ",
    "socle — avertissement : la CI refusera ce commit (`tests.code-teste`) :\n":
        "socle — warning: the CI will refuse this commit (`tests.code-teste`):\n",
    "\nLe commit passe ici. Écrire le test dans un commit suivant, ou amender ce message (`git commit --amend`) avec "
    "la dispense.":
        "\nThe commit goes through here. Write the test in a following commit, or amend this message (`git commit "
        "--amend`) with the waiver.",
    "socle — push refusé : fuite de la mémoire privée dans le nom de la branche : {liste}":
        "socle — push refused: private memory leak in the branch name: {liste}",
    "socle — push refusé : {refus}":
        "socle — push refused: {refus}",
    "socle — vérification avant push":
        "socle — checks before push",
    "décision":
        "decision",
    "action":
        "action",
    "réponse":
        "answer",
    "(pas encore poussé : pas de lien)":
        "(not pushed yet: no link)",
    "supprimer la branche distante `{branche}`, déjà contenue dans la branche par défaut":
        "delete the remote branch `{branche}`, already contained in the default branch",
    "(pas encore poussée : pas de lien)":
        "(not pushed yet: no link)",
    "ce qui revient à l'humain : rien":
        "what falls to the human: nothing",
    "ce qui revient à l'humain : {n}":
        "what falls to the human: {n}",
    "Le projet se construit avec cargo (Rust)":
        "The project builds with cargo (Rust)",
    "Le projet est un paquet Python":
        "The project is a Python package",
    "Le dépôt a {n} fonction(s) de test, dans {fichiers} fichier(s), dont `{premier}`":
        "The repository has {n} test function(s), in {fichiers} file(s), including `{premier}`",
    "Une CI GitHub existe : `{nom}`":
        "A GitHub CI exists: `{nom}`",
    "Le dépôt a un README":
        "The repository has a README",
    "celui du document de cadrage, tel qu'il est écrit":
        "the brief's, as it is written",
    "celui que dit le README, s'il en a un ; sinon aucun, et le backlog reste vide":
        "the one the README states, if there is one; otherwise none, and the backlog stays empty",
    "aucun : le backlog reste vide jusqu'à ce que tu en donnes un":
        "none: the backlog stays empty until you give one",
    "Quel est le but du projet, en une phrase ?":
        "What is the project's goal, in one sentence?",
    "le but alimente le backlog ; en défaut, il est noté « supposé »":
        "the goal feeds the backlog; by default, it is marked “assumed”",
    "Dans quel langage, avec quels outils de test ?":
        "In which language, with which test tools?",
    "celui de l'adaptateur posé à l'installation":
        "the one of the adapter installed with the socle",
    "l'adaptateur décide comment le socle lance les tests ; le changer demande ton accord":
        "the adapter decides how the socle runs the tests; changing it requires your approval",
    "Une partie de la mémoire doit-elle rester privée ?":
        "Should part of the memory stay private?",
    "non : toute la mémoire est publique":
        "no: the whole memory is public",
    "une mémoire privée se pose par l'installeur, en dépôt privé à côté ou chiffrée":
        "a private memory is set up by the installer, in a private repository alongside or encrypted",
    "La politique d'autonomie par défaut (les huit points du cadrage) te convient-elle ?":
        "Does the default autonomy policy (the eight rules of the brief) suit you?",
    "oui, telle quelle":
        "yes, as it is",
    "la politique dit ce que l'agent décide seul et ce qu'il te demande ; toi seul la modifies":
        "the policy says what the agent decides alone and what it asks you; only you change it",
    "Le travail se livre-t-il par une branche de développement, une seule pull request ouverte à la fois, ou "
    "par une branche et une pull request par sujet ?":
        "Is the work delivered through one development branch, with only one pull request open at a time, or "
        "through one branch and one pull request per topic?",
    "une branche de développement : chaque lot fini s'ajoute à la pull request ouverte, que tu fusionnes quand "
    "tu veux":
        "one development branch: each finished batch is added to the open pull request, which you merge "
        "whenever you want",
    "une pull request par sujet se relit sujet par sujet, mais il y en a une à fusionner par sujet ; le choix "
    "devient un fait de la mémoire, que l'agent suit":
        "a pull request per topic is reviewed topic by topic, but there is one to merge per topic; the choice "
        "becomes a fact of the memory, which the agent follows",
    "Des contraintes à respecter (licence, dépendances, plateformes, délais) ?":
        "Any constraints to respect (licence, dependencies, platforms, deadlines)?",
    "aucune connue":
        "none known",
    "une contrainte devient un fait « supposé » jusqu'à ce que tu la valides":
        "a constraint becomes an “assumed” fact until you validate it",
    "{i}. **{question}** Défaut : {defaut}. Ce que ça change : {effet}.":
        "{i}. **{question}** Default: {defaut}. What it changes: {effet}.",
    "- Le document de cadrage, archivé tel quel sous `{cadrage}` : ce que le projet veut, d'où l'agent tire les "
    "faits « supposés » et le backlog de départ.":
        "- The brief, archived as is under `{cadrage}`: what the project wants, from which the agent draws the "
        "“assumed” facts and the starting backlog.",
    "- Le document de cadrage : [{nom}]({lien}).":
        "- The brief: [{nom}]({lien}).",
    "- Aucun élément de la mémoire : le projet commence, et ces questions en posent le départ.":
        "- No element of the memory: the project is starting, and these questions set its start.",
    "- Les instructions du projet : [{instr}]({lien}), section de la politique d'autonomie.":
        "- The project's instructions: [{instr}]({lien}), autonomy policy section.",
    "refus : le socle n'est pas installé ici (`socle install` d'abord)":
        "refused: the socle is not installed here (`socle install` first)",
    " et ":
        " and ",
    "un document de cadrage":
        "a brief",
    "un dépôt existant":
        "an existing repository",
    "rien du tout":
        "nothing at all",
    "initialisation depuis {entrees}":
        "initialization from {entrees}",
    "refus : avec une mémoire privée, le cadrage s'archive dans sa zone, indisponible ici ({raison}) ; la mettre en "
    "place d'abord":
        "refused: with a private memory, the brief is archived in its zone, unavailable here ({raison}); set it up "
        "first",
    "\n## {ident} — Document de cadrage archivé tel quel\n\n{meta} · empreinte : {emp}\n\nArchivé sans réécriture. "
    "Ce qu'il affirme entre dans la mémoire en « supposé », avec ce fichier pour source, jusqu'à validation "
    "humaine.\n":
        "\n## {ident} — Brief archived as is\n\n{meta} · fingerprint : {emp}\n\nArchived without rewriting. What it "
        "states enters the memory as “assumed”, with this file as its source, until a human validation.\n",
    "document archivé : {archive} ({empreinte}…), journal {ident}":
        "document archived: {archive} ({empreinte}…), journal {ident}",
    "audit d'initialisation":
        "initialization audit",
    "audit du dépôt en lecture seule : {n} fait(s) mesuré(s), chacun avec son fichier":
        "read-only audit of the repository: {n} measured fact(s), each with its file",
    "questions de départ : {ident}, {n} question(s), chacune avec son défaut":
        "starting questions: {ident}, {n} question(s), each with its default",
    "\nPour toi :":
        "\nFor you:",
    "commiter puis pousser : `git add -A && git commit -m \"Initialiser la mémoire\" && git push` (la demande "
    "{ident} doit être sur GitHub pour que tu puisses la lire)":
        "commit then push: `git add -A && git commit -m \"Initialize the memory\" && git push` (the request {ident} "
        "must be on GitHub for you to read it)",
    "ouvrir l'agent dans le projet : il relit les questions de départ et te les pose dans la conversation, avec leur "
    "lien":
        "open the agent in the project: it reads the starting questions again and asks them to you in the "
        "conversation, with their link",
    "y répondre dans la conversation, une ligne par question ou « défauts » : l'agent consigne ta réponse telle "
    "quelle":
        "answer them in the conversation, one line per question or “defaults”: the agent records your answer as is",
    "adaptateur inconnu : {nom} (maintenus : {connus} ; sinon un chemin vers un .toml)":
        "unknown adapter: {nom} (maintained: {connus}; otherwise a path to a .toml)",
    "balayage de mutation : `{autre}` le lance déjà, le socle n'en pose pas un second ; la CI vérifie qu'il tourne "
    "encore":
        "mutation sweep: `{autre}` already runs it, the socle does not add a second one; the CI checks that it still "
        "runs",
    "balayage de mutation hebdomadaire posé : {workflow}":
        "weekly mutation sweep installed: {workflow}",
    "politique du projet":
        "project policy",
    "gabarit de cette version":
        "template of this version",
    "{cible} n'est pas un dépôt git":
        "{cible} is not a git repository",
    "{cible} n'est pas la racine du dépôt git ({haut}) ; le socle s'installe à la racine":
        "{cible} is not the root of the git repository ({haut}); the socle is installed at the root",
    "moteur déjà en place dans {dossier_moteur}/socle (installeur lancé depuis le projet) : conservé ; pour une "
    "autre version, lancer l'installeur depuis le clone du socle":
        "engine already in place in {dossier_moteur}/socle (installer run from the project): kept; for another "
        "version, run the installer from the socle's clone",
    "moteur {version} copié dans {dossier_moteur}/socle":
        "engine {version} copied to {dossier_moteur}/socle",
    "# Verrou du moteur — écrit par l'installeur, jamais à la main.\n# Mode amont : ce dépôt fabrique le moteur, "
    "dont l'empreinte n'est pas figée ici.\n":
        "# Engine lock — written by the installer, never by hand.\n# Upstream mode: this repository builds the "
        "engine, whose fingerprint is not frozen here.\n",
    "verrou en mode amont : le moteur est la source, sous {dossier_moteur}/socle":
        "lock in upstream mode: the engine is the source, under {dossier_moteur}/socle",
    "# Verrou du moteur — écrit par l'installeur, jamais à la main.\n# La CI recalcule l'empreinte ; un moteur "
    "altéré dans le projet fait échouer `moteur.empreinte`.\n":
        "# Engine lock — written by the installer, never by hand.\n# The CI recomputes the fingerprint; an engine "
        "altered in the project fails `moteur.empreinte`.\n",
    "verrou : {empreinte} sur {n} fichiers":
        "lock: {empreinte} over {n} files",
    "mémoire privée ajoutée à la politique ({prive}) : un changement protégé, à approuver":
        "private memory added to the policy ({prive}): a protected change, to approve",
    "la politique du projet diffère du gabarit de cette version ; rien n'est écrit, elle est à l'humain — à relire "
    ":\n      {ecart}":
        "the project's policy differs from the template of this version; nothing is written, it belongs to the human "
        "— to review:\n      {ecart}",
    "{nom} existe : conservé (comparer au gabarit à la main si besoin)":
        "{nom} exists: kept (compare it with the template by hand if needed)",
    "{nom} posé":
        "{nom} installed",
    "mémoire initiale posée, journal ouvert par {ident}":
        "initial memory installed, journal opened by {ident}",
    "hooks git branchés (core.hooksPath)":
        "git hooks wired (core.hooksPath)",
    "!! core.hooksPath pointe ailleurs : hooks git NON branchés":
        "!! core.hooksPath points elsewhere: git hooks NOT wired",
    "refus : {refus}":
        "refused: {refus}",
    "refus : langage non détecté (aucun de Cargo.toml, pyproject.toml, go.mod, pom.xml, Gemfile, composer.json, "
    "*.sln, *.csproj, package.json, ni fichier Python) : le demander à l'humain, puis `--adapter <{connus}>` ou le "
    "chemin d'un .toml":
        "refused: language not detected (none of Cargo.toml, pyproject.toml, go.mod, pom.xml, Gemfile, "
        "composer.json, *.sln, *.csproj, package.json, nor a Python file): ask the human, then "
        "`--adapter <{connus}>` or the path of a .toml",
    "refus : adaptateur « {nom} » illisible : {erreur}":
        "refused: adapter “{nom}” unreadable: {erreur}",
    "adaptateur : {nom}":
        "adapter: {nom}",
    " (détecté)":
        " (detected)",
    "mise à jour : moteur {avant} → {version}":
        "update: engine {avant} → {version}",
    "socle {version} installé dans {cible}":
        "socle {version} installed in {cible}",
    "\nAudit :":
        "\nAudit:",
    "\nEt maintenant :":
        "\nWhat now:",
    "!! CLAUDE.md gardé : {n} fichier(s) du projet le nomment ({liste}) ; le renommer en AGENTS.md est une décision "
    "humaine — section du socle ajoutée à CLAUDE.md":
        "!! CLAUDE.md kept: {n} file(s) of the project name it ({liste}); renaming it to AGENTS.md is a human "
        "decision — socle section added to CLAUDE.md",
    "CLAUDE.md existant renommé en AGENTS.md (il fait foi désormais)":
        "existing CLAUDE.md renamed to AGENTS.md (it is now authoritative)",
    "# {nom}\n\nÀ compléter : ce que fait le projet, sa structure, ses commandes.\n\n":
        "# {nom}\n\nTo complete: what the project does, its structure, its commands.\n\n",
    "AGENTS.md posé":
        "AGENTS.md installed",
    "## Repris de CLAUDE.md\n\n{propre}\n\n":
        "## Taken from CLAUDE.md\n\n{propre}\n\n",
    "le contenu de CLAUDE.md, propre au projet, est repris dans AGENTS.md, qui fait foi ; CLAUDE.md n'importe plus "
    "qu'AGENTS.md":
        "the content of CLAUDE.md, specific to the project, is taken over into AGENTS.md, which is authoritative; "
        "CLAUDE.md now only imports AGENTS.md",
    "section du socle de {fichier} régénérée":
        "socle section of {fichier} regenerated",
    "section du socle ajoutée à {fichier}":
        "socle section added to {fichier}",
    "!! .claude/settings.json illisible : hooks NON déclarés":
        "!! .claude/settings.json unreadable: hooks NOT declared",
    "hooks de Claude Code déclarés dans .claude/settings.json":
        "Claude Code hooks declared in .claude/settings.json",
    "!! aucun propriétaire (--owner) : CODEOWNERS non posé — la politique n'est protégée que par la CI":
        "!! no owner (--owner): CODEOWNERS not installed — the policy is only protected by the CI",
    "CODEOWNERS : {proprietaire} sur la politique, les hooks et la CI":
        "CODEOWNERS: {proprietaire} on the policy, the hooks and the CI",
    "# Trace locale des hooks du socle":
        "# Local trace of the socle's hooks",
    "{commentaire} (voir {source})":
        "{commentaire} (see {source})",
    "# Le socle : ses fichiers se commitent":
        "# The socle: its files are committed",
    ".gitignore : {n} fichier(s) du socle n'y sont plus ignorés":
        ".gitignore: {n} socle file(s) no longer ignored there",
    "!! encore ignorés par le .gitignore du projet, un dossier parent sans doute : {liste} — à rendre à la main, "
    "sans quoi ils ne seront pas commités":
        "!! still ignored by the project's .gitignore, by a parent folder no doubt: {liste} — to restore by hand, "
        "otherwise they will not be committed",
    "# Le clone du dépôt privé (mémoire privée)":
        "# The clone of the private repository (private memory)",
    "mémoire privée (compagnon) : dépôt privé trouvé, verrou à {sha}":
        "private memory (compagnon): private repository found, lock at {sha}",
    "!! mémoire privée (compagnon) : dépôt privé absent — le mettre en place : `python3 .socle/socle private install "
    "--repo <adresse du dépôt privé>`":
        "!! private memory (compagnon): private repository missing — set it up: `python3 .socle/socle private "
        "install --repo <address of the private repository>`",
    "mémoire privée (chiffrée) : filtre « {filtre} » configuré":
        "private memory (encrypted): filter “{filtre}” configured",
    "!! mémoire privée (chiffrée) : filtre « {filtre} » non configuré ici — l'initialiser (`{filtre} init`, ou "
    "l'équivalent de l'outil) avant d'écrire du privé ; `prive.chiffre` refusera tout fichier privé commité en clair":
        "!! private memory (encrypted): filter “{filtre}” not configured here — initialize it (`{filtre} init`, or "
        "the tool's equivalent) before writing anything private; `prive.chiffre` will refuse any private file "
        "committed in clear",
    "budget de CLAUDE.md, gardé comme source : {taille} octets (il ne pourra que baisser)":
        "budget of CLAUDE.md, kept as a source: {taille} bytes (it can only go down)",
    "budget de {motif} fixé au niveau actuel : {nouveau} octets (il ne pourra que baisser)":
        "budget of {motif} set at the current level: {nouveau} bytes (it can only go down)",
    "# Contrôles en échec sur l'existant, passés en avertissement. En retirer un\n# durcit (libre) ; en ajouter un "
    "assouplit (demande validée).\n":
        "# Checks failing on the existing code, turned into warnings. Removing one\n# tightens (free); adding one "
        "loosens (approved request).\n",
    "adoption : {n} contrôle(s) en avertissement : {liste}":
        "adoption: {n} check(s) as warnings: {liste}",
    "approuver les fichiers protégés que la mise à jour a changés (la liste s'affiche, à confirmer) : `python3 "
    ".socle/socle approve --text \"Mise à jour du socle {version}\"`":
        "approve the protected files the update changed (the list is shown, to confirm): `python3 .socle/socle "
        "approve --text \"Socle update {version}\"`",
    "{n} contrôle(s) en échec ci-dessus ({liste}) : les corriger, ou relancer l'installation avec `--adoption`, qui "
    "les passe en avertissement sur l'existant":
        "{n} check(s) failing above ({liste}): fix them, or run the installation again with `--adoption`, which "
        "turns them into warnings on the existing code",
    "mettre en place le dépôt privé (créé vide sur GitHub, privé) : clone, premier commit, verrou (ce qui règle "
    "`prive.verrou`), clé de déploiement, puis les deux gestes sur GitHub, avec leurs liens : `python3 .socle/socle "
    "private install --repo <adresse du dépôt privé>`":
        "set up the private repository (created empty on GitHub, private): clone, first commit, lock (which settles "
        "`prive.verrou`), deploy key, then the two steps on GitHub, with their links: `python3 .socle/socle private "
        "install --repo <address of the private repository>`",
    "initialiser le filtre de chiffrement « {filtre} » (`{filtre} init`, ou l'équivalent de l'outil) avant d'écrire "
    "du privé":
        "initialize the encryption filter “{filtre}” (`{filtre} init`, or the tool's equivalent) before writing "
        "anything private",
    "décrire le projet à l'agent : `python3 .socle/socle init --brief <document> --repo` (sans document : `--repo` "
    "seul ; un dépôt vide : sans option)":
        "describe the project to the agent: `python3 .socle/socle init --brief <document> --repo` (without a "
        "document: `--repo` alone; an empty repository: no option)",
    "donner à l'agent les outils que la CI installe : {commandes}, là où il travaille ; en session cloud, dans le "
    "script d'installation de l'environnement ou par l'agent, pour cette session seulement : le hook de démarrage "
    "du socle les installe ensuite dans chaque session neuve":
        "give the agent the tools the CI installs: {commandes}, where it works; in a cloud session, in the "
        "environment's setup script or by the agent, for this session only: the socle's start-up hook then "
        "installs them in every new session",
    "Mettre à jour le socle {version}":
        "Update the socle {version}",
    "Installer le socle {version}":
        "Install the socle {version}",
    "commiter puis pousser : `git add -A && git commit -m \"{message}\" && git push`":
        "commit then push: `git add -A && git commit -m \"{message}\" && git push`",
    "ouvrir l'agent dans le projet : il lit l'état au démarrage":
        "open the agent in the project: it reads the state at startup",
    "ouvrir l'agent dans le projet : il lit l'état au démarrage, et te donne le lien des questions de départ, une "
    "demande à laquelle tu réponds dans la conversation":
        "open the agent in the project: it reads the state at startup, and gives you the link of the starting "
        "questions, a request you answer in the conversation",
    "après ce premier push, protéger la branche par défaut : un ensemble de règles qui y exige la CI « {ci} » "
    "({page}) ; sans lui, une CI rouge n'empêche pas de fusionner, et `socle state` le signale. La revue des "
    "propriétaires du code ne s'y ajoute que si un autre humain relit : l'auteur d'une pull request ne peut pas "
    "l'approuver, et l'agent ouvre les siennes au nom de l'humain. Dans les réglages généraux, cocher "
    "« Automatically delete head branches » : une branche fusionnée s'efface alors seule":
        "after this first push, protect the default branch: a ruleset that requires the CI “{ci}” there ({page}); "
        "without it, a red CI does not prevent merging, and `socle state` reports it. The code owners' review is "
        "added only if another human reviews: the author of a pull request cannot approve it, and the agent opens "
        "its own under the human's name. In the general settings, tick “Automatically delete head branches”: a "
        "merged branch then deletes itself",
    "examiner la branche distante `{branche}` : {n} commit(s) absents de la branche par défaut, sans activité "
    "depuis {jours} jours ; la livrer par une pull request si son travail sert, sinon la supprimer":
        "examine the remote branch `{branche}`: {n} commit(s) missing from the default branch, no activity for "
        "{jours} days; deliver it through a pull request if its work is useful, otherwise delete it",
    "écrire ton nom dans `{politique}` (`[human] name`) avant de fusionner l'installation : il signe les réponses "
    "que l'agent relaie. En session cloud, l'identité git est celle de l'agent, que l'installeur ne prend pas ; "
    "`--human <nom>` le donne à l'installation":
        "write your name in `{politique}` (`[human] name`) before merging the installation: it signs the answers "
        "the agent relays. In a cloud session, the git identity is the agent's, which the installer does not take; "
        "`--human <name>` gives it at installation",
    "réglages du dépôt":
        "repository settings",
    "ensuite, tes gestes, chacun avec sa commande : `python3 .socle/socle help`":
        "then, your steps, each with its command: `python3 .socle/socle help`",
    "ECHEC":
        "FAILED",
    "indisponible":
        "unavailable",
    "ok (avertissement)":
        "ok (warning)",
    "  … et {n} autre(s) contrôle(s) sans rien à signaler":
        "  … and {n} other check(s) with nothing to report",
    "TOUT PASSE":
        "ALL PASS",
    "ECHEC — {n} contrôle(s) : {controles}":
        "FAILED — {n} check(s): {controles}",
    "dispositif qu'aucun document ne nomme : `{nom}` — le nommer, avec ce qu'il fait et pourquoi":
        "a device no document names: `{nom}` — name it, with what it does and why",
    "déclaration sans `regex`":
        "declaration without `regex`",
    "source absente : {fichier}":
        "missing source: {fichier}",
    "la commande source a dépassé son délai : {commande}":
        "the source command timed out: {commande}",
    "la commande source a échoué ({code}) : {commande}":
        "the source command failed ({code}): {commande}",
    "déclaration sans `file` ni `command`":
        "declaration without `file` or `command`",
    "la regex `{regex}` ne trouve rien dans la source":
        "the regex `{regex}` finds nothing in the source",
    "valeur déclarée sans `name`":
        "value declared without `name`",
    "valeur `{nom}` citée sans source déclarée (`[[values]]`)":
        "value `{nom}` cited without a declared source (`[[values]]`)",
    "`{nom}` vaut « {attendu} » à la source, la doc dit « {doc} »":
        "`{nom}` is “{attendu}” at the source, the doc says “{doc}”",
    "« {extrait} » ressemble à la valeur `{nom}` sans marqueur : l'encadrer de `<!-- valeur:{nom} -->…<!-- /valeur "
    "-->`":
        "“{extrait}” looks like the value `{nom}` without a marker: wrap it in `<!-- value:{nom} -->…<!-- /value "
        "-->`",
    "{n} fichier(s) de code sans doc associée, dispensé : « {dispenses} »":
        "{n} code file(s) without their associated doc, waived: “{dispenses}”",
    "code changé sans sa doc associée : {code} → mettre à jour {docs}, ou motiver une dispense par un trailer de "
    "commit `Dispense-doc: <raison>`, dans le commit qui change ce code":
        "code changed without its associated doc: {code} → update {docs}, or give a reason for a waiver with a "
        "commit trailer `Waive-doc: <reason>`, in the commit that changes this code",
    " ou ":
        " or ",
    "paragraphe identique aussi présent en {autres} : garder une source, renvoyer vers elle":
        "identical paragraph also present in {autres}: keep one source, point to it",
    "fichier de mémoire requis absent":
        "required memory file missing",
    "fichier hors des couches connues de la mémoire":
        "file outside the known layers of the memory",
    "en-tête `<!-- socle: couche=… zone=… -->` absent":
        "header `<!-- socle: layer=… zone=… -->` missing",
    "couche déclarée « {couche} », l'emplacement impose « {attendue} »":
        "declared layer “{couche}”, the location requires “{attendue}”",
    "zone non déclarée (`zone=publique` ou `zone=privee`)":
        "zone not declared (`zone=public` or `zone=private`)",
    "zone déclarée « {zone} » dans un emplacement « {zone_lieu} »":
        "declared zone “{zone}” in a “{zone_lieu}” location",
    "titre d'entrée illisible : « {titre} » — l'entrée n'est pas lue ; forme attendue : `## J-AAAA-MM-JJ-X — titre`":
        "unreadable entry title: “{titre}” — the entry is not read; expected form: `## J-YYYY-MM-DD-X — title`",
    "`{ident}` est défini {n} fois ({lieux})":
        "`{ident}` is defined {n} times ({lieux})",
    "`{id}` défini dans le chantier actif, qui est réécrit : un identifiant stable vit dans une couche durable":
        "`{id}` defined in the active work, which is rewritten: a stable identifier lives in a durable layer",
    "un fichier de journal se nomme `AAAA-MM.md`, ou `AAAA-MM-N.md` quand le mois continue (N à partir de 2)":
        "a journal file is named `YYYY-MM.md`, or `YYYY-MM-N.md` when the month continues (N from 2)",
    "un fichier de {couche} porte exactement une entrée ({n} trouvée(s))":
        "a {couche} file holds exactly one entry ({n} found)",
    "le nom du fichier doit commencer par {id}":
        "the file name must start with {id}",
    "`{id}` : un identifiant privé commence par P":
        "`{id}`: a private identifier starts with P",
    "`{id}` : un identifiant public ne commence pas par P":
        "`{id}`: a public identifier does not start with P",
    "`{id}` imbriqué hors d'une archive de journal":
        "`{id}` nested outside a journal archive",
    "`{id}` n'a pas sa place dans la couche « {couche} »":
        "`{id}` does not belong in the “{couche}” layer",
    "`{id}` est daté hors du mois de son fichier":
        "`{id}` is dated outside its file's month",
    "`{id}` : seule une entrée publique se bascule":
        "`{id}`: only a public entry can be moved to private",
    "`{id}` basculée garde un titre ou un texte : seuls « {titre} » et « {texte} » restent en public":
        "`{id}` moved to private keeps a title or a text: only “{titre}” and “{texte}” stay in public",
    "`{id}` sans `statut` (attendu : {liste})":
        "`{id}` without `status` (expected: {liste})",
    "`{id}` : statut « {statut} » inconnu (attendu : {liste})":
        "`{id}`: unknown status “{statut}” (expected: {liste})",
    "`{id}` est barré sans être « réfuté »":
        "`{id}` is struck through without being “refuted”",
    "`{ident}` ne désigne aucune entrée de la mémoire":
        "`{ident}` names no entry of the memory",
    "`{jeton}` : dépôt « {depot} » non déclaré, {n} chemin(s) cité(s) que rien ne vérifie, et aucune adresse du "
    "projet ne le lie : un lien vers ce dépôt le fait connaître ; sinon ce n'est pas un dépôt, et la forme "
    "`x:chemin` ne lui convient pas":
        "`{jeton}`: repository “{depot}” not declared, {n} cited path(s) nothing checks, and no address of the "
        "project links it: a link to this repository makes it known; otherwise it is not a repository, and the form "
        "`x:path` does not suit it",
    "`commit:{cible}` n'est pas un SHA":
        "`commit:{cible}` is not a SHA",
    "`commit:{cible}` n'existe pas dans ce dépôt, ni dans ses pull requests (historique complet ? `fetch-depth: "
    "0`)":
        "`commit:{cible}` does not exist in this repository, nor in its pull requests (full history? `fetch-depth: "
        "0`)",
    "`fichier:{cible}` : {chemin} n'existe pas":
        "`file:{cible}`: {chemin} does not exist",
    "`cmd:{cible}` : {premier} n'existe pas":
        "`cmd:{cible}`: {premier} does not exist",
    "lien mort : {cible}":
        "dead link: {cible}",
    "ancre morte : {cible}":
        "dead anchor: {cible}",
    "chemin cité inexistant : `{jeton}`":
        "cited path does not exist: `{jeton}`",
    "identifiant privé `{ident}` dans un fichier public":
        "private identifier `{ident}` in a public file",
    "`{ident}@{h}` ne correspond pas à la version actuelle de {ident} (lue avant un changement, ou inventée) : la "
    "relire, `python3 .socle/socle show {ident}`, et citer l'empreinte affichée":
        "`{ident}@{h}` does not match the current version of {ident} (read before a change, or invented): read it "
        "again, `python3 .socle/socle show {ident}`, and cite the fingerprint shown",
    "`{index}@{h}` ne correspond à aucune version récente de l'index : le relire, `python3 .socle/socle show --index "
    "{index}`, et citer l'empreinte affichée":
        "`{index}@{h}` matches no recent version of the index: read it again, `python3 .socle/socle show --index "
        "{index}`, and cite the fingerprint shown",
    "décision nouvelle `{ident}` sans `lu : decisions@…` : consulter l'index des décisions avant d'en ajouter une "
    "(`socle show --index decisions`)":
        "new decision `{ident}` without `read : decisions@…`: look at the decision index before adding one (`socle "
        "show --index decisions`)",
    "sujet nouveau `{ident}` sans `lu : backlog@…` : consulter le backlog avant d'y ajouter, pour ne pas dupliquer "
    "(`socle show --index backlog`)":
        "new topic `{ident}` without `read : backlog@…`: look at the backlog before adding to it, so as not to "
        "duplicate (`socle show --index backlog`)",
    "`{ident}` s'appuie sur `{cite}` sans montrer l'avoir lu : citer `{cite}@<empreinte>`, l'empreinte que donne "
    "`socle show {cite}`":
        "`{ident}` relies on `{cite}` without showing it was read: cite `{cite}@<fingerprint>`, the fingerprint "
        "`socle show {cite}` gives",
    "`{id}` est « mesuré » sans `preuve` (commit:, fichier:, cmd: ou identifiant)":
        "`{id}` is “measured” without `proof` (commit:, file:, cmd: or identifier)",
    "`{id}` réfuté : son titre se barre (`~~…~~`), il ne s'efface pas":
        "`{id}` refuted: its title is struck through (`~~…~~`), it is not deleted",
    "`{id}` réfuté sans `refutation` qui pointe vers la mesure":
        "`{id}` refuted without a `refutation` pointing to the measurement",
    "`{id}` « validé » sans `validation : D-NNNN` — ce statut ne s'écrit que par l'humain, via une demande":
        "`{id}` “validated” without `validation : D-NNNN` — this status is only written by the human, through a "
        "request",
    "`{id}` cite `{demande}`, qui n'a pas de réponse « valider »":
        "`{id}` cites `{demande}`, which has no “approve” answer",
    "`{ident}` est pris aussi sur la branche par défaut, depuis que cette branche s'en est séparée, pour « {titre} » "
    ": à la fusion, il serait défini deux fois. `python3 .socle/socle renumber {ident}` lui donne le prochain libre "
    "et le reporte":
        "`{ident}` is also taken on the default branch, since this branch split from it, for “{titre}”: at the "
        "merge, it would be defined twice. `python3 .socle/socle renumber {ident}` gives it the next free one and "
        "carries it over",
    "`{id}` sans `origine` (entrée de journal, commit ou demande)":
        "`{id}` without `origin` (journal entry, commit or request)",
    "`{id}` est clos (« {statut} ») sans `ref` vers ce qui l'a clos":
        "`{id}` is closed (“{statut}”) without a `ref` to what closed it",
    "{octets} octets pour un budget de {budget} ({motif}) : archiver dans le journal":
        "{octets} bytes for a budget of {budget} ({motif}): archive into the journal",
    "{lignes} lignes pour un budget de {budget} ({motif}) : archiver dans le journal":
        "{lignes} lines for a budget of {budget} ({motif}): archive into the journal",
    "aucun budget ne couvre ce fichier (`[budgets]` des garde-fous)":
        "no budget covers this file (`[budgets]` of the guardrails)",
    "chantier actif inchangé depuis {age} jours (seuil : {jours})":
        "active work unchanged for {age} days (threshold: {jours})",
    "{n} fichier(s) de code changé(s) depuis la base et aucun de `{memoire}/` : mettre à jour le chantier actif ou "
    "le journal avant de conclure":
        "{n} code file(s) changed since the base and none of `{memoire}/`: update the active work or the journal "
        "before concluding",
    "mémoire privée illisible ici : son ajout seul n'est pas vérifié":
        "private memory unreadable here: its append-only rule is not checked",
    "réponse humaine modifiée ou supprimée : elle est définitive":
        "human answer changed or deleted: it is final",
    "`{ident}` basculée dans la mémoire privée : elle reste telle quelle":
        "`{ident}` moved to the private memory: it stays as it is",
    "entrée de journal `{ident}` supprimée (le journal est en ajout seul)":
        "journal entry `{ident}` deleted (the journal is append-only)",
    "entrée de journal `{ident}` modifiée (le journal est en ajout seul)":
        "journal entry `{ident}` changed (the journal is append-only)",
    "décision `{ident}` supprimée (une décision se remplace, elle ne s'efface pas)":
        "decision `{ident}` deleted (a decision is superseded, it is not deleted)",
    "décision `{ident}` réécrite : seul son statut peut changer, une décision nouvelle la remplace":
        "decision `{ident}` rewritten: only its status can change, a new decision supersedes it",
    "décision `{ident}` : passage « {statut} » → « {apres} » interdit":
        "decision `{ident}`: change “{statut}” → “{apres}” forbidden",
    "décision `{ident}` remplacée sans `remplacée-par : ADR-NNNN`":
        "decision `{ident}` superseded without `superseded-by : ADR-NNNN`",
    "fait `{ident}` effacé : un fait se barre (réfuté) ou s'archive dans le journal, jamais ne disparaît":
        "fact `{ident}` erased: a fact is struck through (refuted) or archived into the journal, it never disappears",
    "fait `{ident}` modifié sans référence de preuve nouvelle":
        "fact `{ident}` changed without a new proof reference",
    "fait `{ident}` réfuté : son texte se garde, barré ; il ne se réécrit pas":
        "fact `{ident}` refuted: its text is kept, struck through; it is not rewritten",
    "demande `{ident}` supprimée (la retirer : `retirée : <raison>` dans ses métadonnées)":
        "request `{ident}` deleted (to withdraw it: `withdrawn : <reason>` in its metadata)",
    "`{id}` basculée : sa copie privée ne se lit pas ici":
        "`{id}` moved to private: its private copy cannot be read here",
    "`{id}` basculée sans copie privée qui la reprenne (`depuis : {id}`) : son contenu serait perdu ; `socle private "
    "move` fait les deux":
        "`{id}` moved to private without a private copy that takes it over (`from : {id}`): its content would be "
        "lost; `socle private move` does both",
    "`{id}` basculée : sa copie privée n'en reprend ni le titre ni le texte":
        "`{id}` moved to private: its private copy takes over neither its title nor its text",
    "réponse sans demande":
        "answer without a request",
    "AGENTS.md absent, et CLAUDE.md ne porte pas la section du socle : aucun fichier d'instructions ne fait foi":
        "AGENTS.md missing, and CLAUDE.md does not carry the socle section: no instructions file is authoritative",
    "CLAUDE.md doit contenir la seule ligne `@AGENTS.md` (aucune copie à synchroniser)":
        "CLAUDE.md must contain the single line `@AGENTS.md` (no copy to keep in sync)",
    "plafond {vb} écrit sans la mesure que pose `mutation-verdict --record`":
        "cap {vb} written without the measurement `mutation-verdict --record` sets",
    "clé ajoutée : {vb}":
        "key added: {vb}",
    "seuil retiré (valait {va})":
        "threshold removed (was {va})",
    "couverture retirée : {retires}":
        "coverage removed: {retires}",
    "exclusion ajoutée : {ajoutes}":
        "exclusion added: {ajoutes}",
    "changement non classé : {va} → {vb}":
        "unclassified change: {va} → {vb}",
    "correspondance code ↔ doc retirée":
        "code ↔ doc mapping removed",
    "docs ajoutées à la correspondance : {docs}":
        "docs added to the mapping: {docs}",
    "valeur liée retirée":
        "tied value removed",
    "source de la valeur changée":
        "source of the value changed",
    "assouplissement validé par {id} : {cle} — {pourquoi}":
        "loosening approved by {id}: {cle} — {pourquoi}",
    "assouplissement sans validation humaine : {cle} — {pourquoi}. Émettre une demande qui cite `{cle}` ; elle "
    "couvrira ce changement une fois validée":
        "loosening without human approval: {cle} — {pourquoi}. Open a request that cites `{cle}`; it will cover this "
        "change once approved",
    "installation en cours : la branche par défaut n'a pas encore le socle, et {n} fichier(s) protégé(s) changent "
    "avant sa fusion ({liste})":
        "installation in progress: the default branch does not have the socle yet, and {n} protected file(s) change "
        "before it is merged ({liste})",
    "installation du socle : {n} fichier(s) protégé(s) posé(s) — la politique par défaut est celle du cadrage":
        "socle installation: {n} protected file(s) installed — the default policy is the brief's",
    "modification en attente de {id} : le tour peut finir, le commit et la CI attendent la réponse de "
    "l'humain":
        "change awaiting {id}: the turn may end, the commit and the CI wait for the human's answer",
    "modification validée par {id}":
        "change approved by {id}",
    "fichier protégé modifié sans validation humaine. Une demande validée doit citer `{fichier}` et `{cite}`":
        "protected file changed without human approval. An approved request must cite `{fichier}` and `{cite}`",
    "socle non installé : `{lock}` absent (commité ? un .gitignore du projet peut l'écarter)":
        "socle not installed: `{lock}` missing (committed? a .gitignore of the project can exclude it)",
    "mode amont : ce dépôt fabrique le moteur, son empreinte n'est pas figée":
        "upstream mode: this repository builds the engine, its fingerprint is not frozen",
    "moteur introuvable dans {dossier_moteur}":
        "engine not found in {dossier_moteur}",
    "moteur altéré : empreinte {calculee}, le verrou attend {attendue}. Relancer l'installeur, jamais réparer à la "
    "main":
        "altered engine: fingerprint {calculee}, the lock expects {attendue}. Run the installer again, never repair "
        "by hand",
    "`.claude/settings.json` absent : les hooks de Claude Code ne sont pas déclarés":
        "`.claude/settings.json` missing: Claude Code's hooks are not declared",
    "JSON illisible : {erreur}":
        "unreadable JSON: {erreur}",
    "aucun hook {evt} n'appelle `.socle/socle hook`":
        "no {evt} hook calls `.socle/socle hook`",
    "{sha} « {sujet} » : commit d'agent sans trailer `Socle-Hooks` — les hooks git n'ont pas tourné (`git config "
    "core.hooksPath .socle/git-hooks`)":
        "{sha} “{sujet}”: agent commit without a `Socle-Hooks` trailer — the git hooks did not run (`git config "
        "core.hooksPath .socle/git-hooks`)",
    "{sha} « {sujet} » : le hook SessionStart n'a jamais tiré pendant la session":
        "{sha} “{sujet}”: the SessionStart hook never fired during the session",
    "aucun adaptateur (`{adaptateur}`)":
        "no adapter (`{adaptateur}`)",
    "capacité « {nom} » non déclarée : une commande, ou `absent` + `replacement`":
        "capability “{nom}” not declared: a command, or `absent` + `replacement`",
    "capacité « {nom} » : ni `command`, ni `absent` avec `replacement`":
        "capability “{nom}”: neither `command`, nor `absent` with `replacement`",
    "section `[tests]` sans `function` : les tests creux ne peuvent pas être détectés":
        "section `[tests]` without `function`: hollow tests cannot be detected",
    "adaptateur sans `[tests]` : détection impossible":
        "adapter without `[tests]`: detection impossible",
    "test `{nom}` désactivé sans raison écrite":
        "test `{nom}` disabled without a written reason",
    "test `{nom}` sans assertion : il passe sans rien mesurer":
        "test `{nom}` without an assertion: it passes without measuring anything",
    "assertion tautologique dans `{nom}` : « {ligne} » — si elle est voulue (déterminisme), l'écrire : commentaire "
    "`socle: voulu — <raison>`":
        "tautological assertion in `{nom}`: “{ligne}” — if it is intended (determinism), say so: a comment `socle: "
        "intended — <reason>`",
    "groupe de tests désactivé sans raison écrite : « {ligne} »":
        "group of tests disabled without a written reason: “{ligne}”",
    "validé par {id}":
        "approved by {id}",
    "spécification changée par l'humain : {chemin}":
        "specification changed by the human: {chemin}",
    "adaptateur sans `[tests]`":
        "adapter without `[tests]`",
    "{quoi}, en attente de {attente} : le tour peut finir, le commit et la CI attendent la réponse de l'humain":
        "{quoi}, waiting for {attente}: the turn can end, the commit and the CI wait for the human's answer",
    "test `{nom}` supprimé":
        "test `{nom}` deleted",
    "test `{nom}` supprimé sans validation humaine ni changement de spécification qui le nomme":
        "test `{nom}` deleted without human approval or a change of specification that names it",
    "assertion changée dans `{nom}`":
        "assertion changed in `{nom}`",
    "assertion changée ou retirée dans `{nom}` : « {exemple} » — valeur attendue modifiée sans spécification ni "
    "validation humaine":
        "assertion changed or removed in `{nom}`: “{exemple}” — expected value changed without specification or "
        "human approval",
    "valeurs changées hors des assertions dans {n} test(s) — {tests} (« {valeur} ») : si l'une est une valeur "
    "attendue (une variable, une table, un paramètre, une constante), la changer exige une validation humaine "
    "(politique, point 2)":
        "values changed outside the assertions in {n} test(s) — {tests} (“{valeur}”): if one is an expected value (a "
        "variable, a table, a parameter, a constant), changing it requires human approval (policy, rule 2)",
    " ; la spécification {specs} le nomme, mais elle est écrite par l'agent : elle ne suffit pas (politique, point "
    "2). Poser une demande à l'humain, ou qu'il change lui-même la spécification":
        "; the specification {specs} names it, but it is written by the agent: it is not enough (policy, rule 2). "
        "Open a request to the human, or let them change the specification themselves",
    "dispense illisible dans le commit {sha} : « {dispense} » — forme attendue : `Dispense-test: f, g — <raison d'au "
    "moins dix caractères>`":
        "unreadable waiver in commit {sha}: “{dispense}” — expected form: `Waive-test: f, g — <reason of at least "
        "ten characters>`",
    "adaptateur sans `[tests]` : fonctions illisibles":
        "adapter without `[tests]`: functions unreadable",
    "fonction `{nom}` modifiée, qu'aucun test ne nomme : écrire le test qui l'appelle, ou la dispenser par un "
    "trailer de commit `Dispense-test: {nom} — <raison>`":
        "function `{nom}` changed, which no test names: write the test that calls it, or waive it with a commit "
        "trailer `Waive-test: {nom} — <reason>`",
    "fonction `{nom}` ajoutée, qu'aucun test ne nomme : écrire le test qui l'appelle, ou la dispenser par un trailer "
    "de commit `Dispense-test: {nom} — <raison>`":
        "function `{nom}` added, which no test names: write the test that calls it, or waive it with a commit "
        "trailer `Waive-test: {nom} — <reason>`",
    "capacité absente : {absent} — remplacement : {remplacement}":
        "capability absent: {absent} — replacement: {remplacement}",
    "non déclarée":
        "not declared",
    " ; ni test changé dans un module de code":
        "; nor a test changed in a code module",
    "correctif sans test de régression : {sha} « {sujet} » (aucun fichier de {liste} ajouté ou modifié{ailleurs})":
        "fix without a regression test: {sha} “{sujet}” (no file of {liste} added or changed{ailleurs})",
    "{sha} : impossible de préparer le commit parent":
        "{sha}: cannot prepare the parent commit",
    "{sha} « {sujet} » : son test passe déjà sur le parent — il ne prouve pas le correctif ; si sa preuve dépend "
    "de l'environnement, une demande validée qui nomme ce commit l'admet":
        "{sha} “{sujet}”: its test already passes on the parent — it does not prove the fix; if its proof depends "
        "on the environment, an approved request that names this commit admits it",
    "{sha} « {sujet} » : son test passe déjà sur le parent ; admis par {id}, une demande validée qui nomme ce "
    "commit":
        "{sha} “{sujet}”: its test already passes on the parent; admitted by {id}, an approved request that names "
        "this commit",
    "{sha} « {sujet} » : son test ne se charge pas sur le parent (« {erreur} ») : il y échoue pour une autre raison "
    "que le défaut. L'écrire contre ce qui existe déjà sur le parent":
        "{sha} “{sujet}”: its test does not load on the parent (“{erreur}”): it fails there for another reason than "
        "the defect. Write it against what already exists on the parent",
    "{sha} « {sujet} » : son test de régression échoue sur le correctif lui-même":
        "{sha} “{sujet}”: its regression test fails on the fix itself",
    "module hors du cliquet de mutation : l'y poser à mesurer (`\"{m}\" = { pending = true }` sous `[mutation.caps]` "
    "des garde-fous), puis le mesurer par un balayage (`socle mutation-run --record`)":
        "module outside the mutation ratchet: add it to measure (`\"{m}\" = { pending = true }` under "
        "`[mutation.caps]` of the guardrails), then measure it with a sweep (`socle mutation-run --record`)",
    "module à mesurer : lancer le balayage de mutation et poser son plafond (`socle mutation-run --record`), ou "
    "recopier celui du dernier balayage planifié":
        "module to measure: run the mutation sweep and set its cap (`socle mutation-run --record`), or copy the one "
        "of the last scheduled sweep",
    "le cliquet nomme `{m}`, qui n'existe pas":
        "the ratchet names `{m}`, which does not exist",
    "plafond non nul sans raison écrite pour `{m}`":
        "non-zero cap without a written reason for `{m}`",
    "Ajouter un terme à la liste privée est libre ; en retirer un exige une demande validée qui cite la liste et son "
    "empreinte nouvelle.":
        "Adding a term to the private list is free; removing one requires an approved request that cites the list "
        "and its new fingerprint.",
    "Aucun identifiant privé dans un fichier public : le public ne référence jamais le privé.":
        "No private identifier in a public file: the public never references the private.",
    "Aucun terme de la liste privée dans un fichier public modifié, et ni terme ni identifiant privé dans un message "
    "de commit.":
        "No term of the private list in a changed public file, and neither a term nor a private identifier in a "
        "commit message.",
    "Aucune capacité n'est omise en silence : déclarée, ou absente avec sa raison et son contrôle de remplacement.":
        "No capability is left out silently: declared, or absent with its reason and its replacement check.",
    "Chaque commit d'agent porte la trace des hooks qui ont tiré pendant sa session (`Socle-Hooks:`, ajouté par le "
    "hook git).":
        "Each agent commit carries the trace of the hooks that fired during its session (`Socle-Hooks:`, added by "
        "the git hook).",
    "Chaque couche et le fichier d'instructions ont un plafond de taille.":
        "Each layer and the instructions file have a size cap.",
    "Chaque sujet a une origine ; un sujet clos a une référence, et il est rangé avec les clos ; un sujet fait a "
    "coché tout ce que dit sa section « Fait quand ».":
        "Each topic has an origin; a closed topic has a reference, and it is filed with the closed ones; a done topic "
        "has checked everything its “Done when” section says.",
    "Un sujet n'attend (`après`) que des sujets du backlog ou des demandes, jamais lui-même de proche en proche, et "
    "ne se dit fait qu'une fois clos ce qu'il attend : un jalon ne se clôt pas sur des tâches ouvertes, ni un sujet "
    "sur une demande sans réponse.":
        "A topic waits (`after`) only on backlog topics or requests, never on itself step by step, and is done only "
        "once what it waits on is closed: a milestone does not close over open tasks, nor a topic over an unanswered "
        "request.",
    "`{id}` : `après` ne nomme que des sujets du backlog ou des demandes ({valeur})":
        "`{id}`: `after` names only backlog topics or requests ({valeur})",
    "`{id}` est fait avant `{dep}`, qu'il attend, encore « {statut} »":
        "`{id}` is done before `{dep}`, which it waits on, still “{statut}”",
    "`{id}` est fait avant `{dep}`, qu'il attend, encore sans réponse":
        "`{id}` is done before `{dep}`, which it waits on, still unanswered",
    "`{id}` : `priorité` vaut `haute` ou `basse`, la normale ne s'écrit pas ({valeur})":
        "`{id}`: `priority` is `high` or `low`, the normal one is not written ({valeur})",
    "`{id}` est clos « fait » avec un critère de « Fait quand » non coché : {criteres}":
        "`{id}` is closed “done” with an unchecked “Done when” criterion: {criteres}",
    "`{id}` s'attend lui-même : {cycle}":
        "`{id}` waits on itself: {cycle}",
    "décision posée à l'humain dans le widget de questions de l'agent":
        "decision put to the human in the agent's question widget",
    "une question à l'humain ne passe pas par le widget de questions de l'agent : son texte y est brut et ses liens "
    "ne s'y suivent pas. Une décision qui demande du contexte (approuver un document, choisir entre des options) "
    "s'écrit en demande (`socle new request`), dont le lien se donne dans la conversation ; une question courte se "
    "pose dans le texte de la réponse.":
        "a question to the human does not go through the agent's question widget: its text is raw there and its "
        "links cannot be followed. A decision that needs context (approving a document, choosing between options) is "
        "written as a request (`socle new request`), whose link is given in the conversation; a short question is "
        "asked in the text of the answer.",
    "une demande de choix qui propose les réponses de base et ses options passe, et une demande qui nomme un test "
    "passe avec `valider`":
        "a choice request that proposes the base answers and its options passes, and a request that names a test "
        "passes with `approve`",
    "demande qui propose « approuver » au lieu de la réponse de base `valider`":
        "request that proposes “approuver” instead of the base answer `approve`",
    "« Réponses possibles » doit proposer les réponses de base, les mêmes dans toute demande ({manquent}) : "
    "`{positive}` y prend la recommandation, et une demande de choix ajoute ses options":
        "“Possible answers” must propose the base answers, the same in every request ({manquent}): `{positive}` takes "
        "the recommendation, and a choice request adds its options",
    "« Réponses possibles » : `{x}` double la réponse de base `{base}`, à employer à sa place":
        "“Possible answers”: `{x}` duplicates the base answer `{base}`, to be used instead",
    "« {reponse} » : une décision en séance se consigne sous une réponse de base ({base}), ou sous une option que la "
    "question nomme entre accents graves ; le texte exact de l'humain va dans la citation":
        "“{reponse}”: a decision in session is recorded under a base answer ({base}), or under an option the question "
        "names in backticks; the human's exact text goes in the quote",
    "la pull request {numero} citée sans son lien : donner son adresse, que l'humain ouvre d'un clic":
        "pull request {numero} cited without its link: give its address, which the human opens in one click",
    "pull request à fusionner citée sans son lien":
        "pull request to merge cited without its link",
    "sujet du backlog qui s'attend lui-même (`après`)":
        "backlog topic that waits on itself (`after`)",
    "jalon fait alors que la tâche qu'il attend est ouverte":
        "milestone done while the task it waits on is open",
    "un jalon qui attend une tâche ouverte, dans l'ordre, passe le commit et la CI":
        "a milestone that waits on an open task, in order, passes the commit and the CI",
    "prochain jalon : {id} — {titre} ; reste : {restants}":
        "next milestone: {id} — {titre}; left: {restants}",
    "rien, il se clôt":
        "nothing, it can close",
    "Selon l'ordre du backlog :":
        "According to the backlog's order:",
    "prêt : {id} — {titre}":
        "ready: {id} — {titre}",
    "prêt : {id} — {titre} (priorité haute)":
        "ready: {id} — {titre} (high priority)",
    "prêts aussi, de priorité basse : {ids}":
        "also ready, low priority: {ids}",
    "… et {n} autre(s) prêt(s)":
        "… and {n} more ready",
    "{n} sujet(s) attendent un sujet ouvert":
        "{n} topic(s) wait on an open topic",
    "Du code a changé et la mémoire non : la fin de tour attend sa mise à jour.":
        "Code changed and the memory did not: the end of turn waits for its update.",
    "Durcir un garde-fou est libre ; l'assouplir exige une demande validée qui cite la clé (politique, point 1).":
        "Tightening a guardrail is free; loosening it requires an approved request that cites the key (policy, rule "
        "1).",
    "En-têtes, couches, identifiants, statuts : la mémoire se lit par script.":
        "Headers, layers, identifiers, statuses: the memory is read by script.",
    "Journal et décisions en ajout seul ; un fait ne disparaît pas, ne change qu'avec une nouvelle preuve, et se "
    "barre quand il est réfuté.":
        "Journal and decisions are append-only; a fact does not disappear, only changes with a new proof, and is "
        "struck through when refuted.",
    "La mémoire privée configurée est accessible, sinon c'est dit ; des fichiers privés sans mode configuré sont "
    "publics, donc refusés.":
        "The configured private memory is accessible, otherwise it is said; private files without a configured mode "
        "are public, hence refused.",
    "Le balayage de mutation planifié tourne encore.":
        "The scheduled mutation sweep still runs.",
    "Le moteur du projet est celui que l'installeur a posé.":
        "The project's engine is the one the installer laid down.",
    "Les hooks de l'agent sont déclarés et appellent le moteur.":
        "The agent's hooks are declared and call the engine.",
    "Mode chiffré : aucun fichier privé n'est commité en clair, et un filtre de chiffrement couvre la zone privée.":
        "Encrypted mode: no private file is committed in clear, and an encryption filter covers the private zone.",
    "Mode compagnon : rien de privé n'est commité dans le dépôt public, et le verrou désigne le commit du dépôt "
    "privé qui va avec ce commit.":
        "Companion mode: nothing private is committed in the public repository, and the lock names the private "
        "repository's commit that goes with this commit.",
    "Pas de test sans assertion, d'assertion tautologique, ni de test désactivé sans raison écrite.":
        "No test without an assertion, no tautological assertion, no test disabled without a written reason.",
    "Si du code change, la doc qui lui est associée change aussi — ou une dispense écrite et motivée l'accompagne "
    "(`Dispense-doc: <raison>`), qui ne vaut que pour le code de son propre commit.":
        "If code changes, its associated doc changes too — or a written, reasoned waiver comes with it (`Waive-doc: "
        "<reason>`), which only covers the code of its own commit.",
    "Supprimer un test ou changer une valeur attendue exige une validation humaine, ou un changement de "
    "spécification qui le nomme, fait par l'humain (politique, point 2).":
        "Deleting a test or changing an expected value requires human approval, or a change of specification that "
        "names it, made by the human (policy, rule 2).",
    "Tout correctif livre un test qui échoue sur le commit parent et passe sur le correctif, vérifié en l'exécutant.":
        "Every fix delivers a test that fails on the parent commit and passes on the fix, checked by running it.",
    "Tout dispositif du dépôt est nommé dans la documentation.":
        "Every device of the repository is named in the documentation.",
    "Tout identifiant, commit, fichier, lien ou chemin cité existe.":
        "Every cited identifier, commit, file, link or path exists.",
    "Tout module qui porte du code est dans le cliquet de mutation, et le cliquet ne nomme que des modules qui "
    "existent.":
        "Every module that holds code is in the mutation ratchet, and the ratchet only names modules that exist.",
    "Toute demande en attente est autonome : huit champs, aucun identifiant nu.":
        "Every pending request stands on its own: eight fields, no bare identifier.",
    "Toute valeur citée dans la doc est liée à sa source, et les deux concordent.":
        "Every value cited in the doc is tied to its source, and both agree.",
    "Un chantier actif qui ne bouge plus est signalé — un avertissement, pas un échec.":
        "An active work that no longer moves is reported — a warning, not a failure.",
    "Un fait mesuré pointe vers sa preuve ; un fait réfuté garde sa trace ; un fait validé cite la demande que "
    "l'humain a validée.":
        "A measured fact points to its proof; a refuted fact keeps its trace; a validated fact cites the request the "
        "human approved.",
    "Un fichier protégé ne change qu'avec une demande validée qui cite son empreinte nouvelle (hooks, CI, politique, "
    "adaptateur, moteur).":
        "A protected file only changes with an approved request that cites its new fingerprint (hooks, CI, policy, "
        "adapter, engine).",
    "Un identifiant que la branche définit et que la branche par défaut a pris aussi depuis leur divergence, pour "
    "une autre entrée, serait défini deux fois à la fusion : dit avant, avec la commande qui répare.":
        "An identifier the branch defines and the default branch also took since they diverged, for another entry, "
        "would be defined twice at the merge: said beforehand, with the command that repairs it.",
    "Un même contenu dans deux fichiers est une copie qui divergera : refusé.":
        "The same content in two files is a copy that will diverge: refused.",
    "Un seul fichier d'instructions fait foi : `AGENTS.md`, que `CLAUDE.md` importe en une ligne ; ou, sans "
    "`AGENTS.md`, `CLAUDE.md` qui porte la section du socle, quand l'installeur l'a gardé parce que le projet le "
    "nomme.":
        "A single instructions file is authoritative: `AGENTS.md`, which `CLAUDE.md` imports in one line; or, "
        "without `AGENTS.md`, `CLAUDE.md` carrying the socle section, when the installer kept it because the project "
        "names it.",
    "Une citation `ID@empreinte` ou `index@empreinte` ajoutée désigne une version que l'agent a pu lire "
    "(`socle.readings`) ; une décision, une demande ou un sujet de backlog nouveaux prouvent ce qu'ils ont "
    "lu avant d'être écrits.":
        "A citation `ID@fingerprint` or `index@fingerprint` that is added names a version the agent could read "
        " (`socle.readings`); a new decision, request or backlog topic proves what it read before being "
        "written.",
    "Une fonction publique ajoutée ou modifiée est nommée par au moins un test — ou une dispense motivée la nomme "
    "(`Dispense-test: f — <raison>`).":
        "A public function added or changed is named by at least one test — or a reasoned waiver names it "
        "(`Waive-test: f — <reason>`).",
    "Une réponse porte sur le texte exact de sa demande et en est une réponse possible.":
        "An answer is about the exact text of its request and is one of its possible answers.",
    "# Le commit du dépôt privé qui correspond à ce commit public (mode compagnon).\n# Écrit par `socle private "
    "lock`, jamais à la main.\n":
        "# The private repository's commit that matches this public commit (companion mode).\n# Written by `socle "
        "private lock`, never by hand.\n",
    "mémoire privée : indisponible ici, sans clé de déploiement (pull request d'un fork ?)":
        "private memory: unavailable here, without a deploy key (pull request from a fork?)",
    "mémoire privée : pas de verrou ({verrou})":
        "private memory: no lock ({verrou})",
    "mémoire privée : récupération impossible (étape `git {etape}`)":
        "private memory: retrieval impossible (step `git {etape}`)",
    "mémoire privée : récupérée au verrou {verrou}":
        "private memory: retrieved at lock {verrou}",
    "liste des termes privés illisible ici (`{fichier_termes}`) : le terme n'est pas ajouté à l'aveugle, la liste "
    "serait écrasée ({raison})":
        "list of private terms unreadable here (`{fichier_termes}`): the term is not added blindly, the list would "
        "be overwritten ({raison})",
    "identifiant privé `{i}`":
        "private identifier `{i}`",
    "terme privé n°{i} : expression régulière invalide":
        "private term no. {i}: invalid regular expression",
    "terme privé n°{i} de la liste":
        "private term no. {i} of the list",
    "relecture avant publication (politique : {relecture}) : {sha} n'a pas été relu. Montrer à l'humain ce qui part "
    "(diff, messages de commit), puis consigner son accord avec son texte exact : `socle reviewed --relayed --by "
    "<nom> --quote-file <fichier>`. ":
        "review before publication (policy: {relecture}): {sha} has not been reviewed. Show the human what is "
        "leaving (diff, commit messages), then record their agreement with their exact text: `socle reviewed "
        "--relayed --by <name> --quote-file <file>`. ",
    "Une relecture à chaque push.":
        "One review at each push.",
    "Une relecture par lot de commits.":
        "One review per batch of commits.",
    "le dépôt privé n'est pas cloné dans `{dossier}/`":
        "the private repository is not cloned in `{dossier}/`",
    "disponible, mais au commit {sha} et non au verrou {verrou} (`socle private extract` pour revenir au verrou, "
    "`socle private lock` pour l'avancer)":
        "available, but at commit {sha} and not at lock {verrou} (`socle private extract` to go back to the lock, "
        "`socle private lock` to move it forward)",
    "disponible, au commit {sha}":
        "available, at commit {sha}",
    "{n} fichier(s) privé(s) illisible(s) : chiffrés, la clé manque ici":
        "{n} private file(s) unreadable: encrypted, the key is missing here",
    "disponible, déchiffrée":
        "available, decrypted",
    "aucun mode de mémoire privée dans la politique":
        "no private memory mode in the policy",
    "mémoire privée : non configurée (mode public seul)":
        "private memory: not configured (public mode only)",
    "mémoire privée : mode « {m} » inconnu (attendu : {liste})":
        "private memory: unknown mode “{m}” (expected: {liste})",
    "mémoire privée : {raison} (mode {m})":
        "private memory: {raison} (mode {m})",
    "mémoire privée : INDISPONIBLE (mode {m}) — {raison} ; les contrôles qui l'exigent le signalent ; ne pas "
    "conclure sur ce qui en dépend":
        "private memory: UNAVAILABLE (mode {m}) — {raison}; the checks that require it report it; draw no conclusion "
        "on what depends on it",
    "{n} fichier(s) sous `{dossier}/` commité(s) sans mode de mémoire privée : ils sont publics. Choisir un mode "
    "(`[private] mode` de la politique) ou les déplacer":
        "{n} file(s) under `{dossier}/` committed without a private memory mode: they are public. Choose a mode "
        "(`[private] mode` of the policy) or move them",
    "mode de mémoire privée « {m} » inconnu (attendu : {liste})":
        "unknown private memory mode “{m}” (expected: {liste})",
    "mémoire privée indisponible : {raison}":
        "private memory unavailable: {raison}",
    "relecture avant publication non choisie (`[private] review` : {liste}) : aucune n'est exigée":
        "review before publication not chosen (`[private] review`: {liste}): none is required",
    "relecture « {rel} » inconnue (attendu : {liste})":
        "unknown review “{rel}” (expected: {liste})",
    "fichier privé commité dans le dépôt public : il appartient au dépôt privé, que `{dossier}/` clone (le retirer "
    "de l'index)":
        "private file committed in the public repository: it belongs to the private repository, which `{dossier}/` "
        "clones (remove it from the index)",
    "mode compagnon sans dépôt privé ni verrou : sa mise en place revient à l'humain, `private install --repo "
    "<adresse du dépôt privé>`":
        "companion mode without a private repository or a lock: setting it up falls to the human, `private install "
        "--repo <address of the private repository>`",
    "mode compagnon sans verrou : `socle private lock`":
        "companion mode without a lock: `socle private lock`",
    "dépôt privé non cloné : verrou non vérifiable":
        "private repository not cloned: lock cannot be checked",
    "{n} changement(s) de la mémoire privée hors de tout commit du dépôt privé : les y commiter, puis `socle private "
    "lock`":
        "{n} change(s) of the private memory outside any commit of the private repository: commit them there, then "
        "`socle private lock`",
    "le verrou désigne {verrou}, le dépôt privé est à {sha} : `socle private lock` pour l'avancer, ou `socle private "
    "extract` pour y revenir":
        "the lock names {verrou}, the private repository is at {sha}: `socle private lock` to move it forward, or "
        "`socle private extract` to go back to it",
    "fichier privé commité EN CLAIR : le filtre de chiffrement n'a pas tourné. Retirer le commit avant tout push ; "
    "si c'est poussé, l'historique public l'a gardé":
        "private file committed IN CLEAR: the encryption filter did not run. Remove the commit before any push; if "
        "it is pushed, the public history has kept it",
    "aucun filtre de chiffrement ne couvre `{zone}/` (`.gitattributes` : `{zone}/** filter=…`)":
        "no encryption filter covers `{zone}/` (`.gitattributes`: `{zone}/** filter=…`)",
    "liste des termes privés illisible ici : seuls les identifiants privés sont cherchés":
        "list of private terms unreadable here: only private identifiers are searched for",
    "fuite de la mémoire privée dans le nom du fichier : {fuite}":
        "private memory leak in the file name: {fuite}",
    "fuite de la mémoire privée : {fuite}":
        "private memory leak: {fuite}",
    "fuite de la mémoire privée dans le message du commit {sha} : {fuite}":
        "private memory leak in the message of commit {sha}: {fuite}",
    "fuite de la mémoire privée dans le nom de la branche : {fuite}":
        "private memory leak in the branch name: {fuite}",
    "liste des termes privés illisible ici : retraits non vérifiables":
        "list of private terms unreadable here: removals cannot be checked",
    "{n} terme(s) retiré(s), validé par {id}":
        "{n} term(s) removed, approved by {id}",
    "{n} terme(s) retiré(s) de la liste privée sans validation humaine : une demande validée doit citer "
    "`{termes_ici}` et `{cite}`":
        "{n} term(s) removed from the private list without human approval: an approved request must cite "
        "`{termes_ici}` and `{cite}`",
    "refus : la politique ne choisit pas le mode compagnon — relancer l'installation avec `--private compagnon`, qui "
    "l'écrit":
        "refused: the policy does not choose the companion mode — run the installation again with `--private "
        "compagnon`, which writes it",
    "refus : {rel}/ existe et n'est pas un clone : le déplacer, puis relancer":
        "refused: {rel}/ exists and is not a clone: move it, then run again",
    "refus : clone impossible ({erreur})":
        "refused: clone impossible ({erreur})",
    "git clone a échoué":
        "git clone failed",
    "dépôt privé cloné dans {rel}/":
        "private repository cloned into {rel}/",
    "dépôt privé déjà cloné dans {rel}/":
        "private repository already cloned into {rel}/",
    "{rel}/ ignoré par le dépôt public (.gitignore)":
        "{rel}/ ignored by the public repository (.gitignore)",
    "# Mémoire privée de {projet}\n\nLe socle y range la mémoire privée du projet, au même format que la mémoire "
    "publique. Ce dépôt reste privé.\n":
        "# Private memory of {projet}\n\nThe socle keeps the project's private memory here, in the same format as "
        "the public memory. This repository stays private.\n",
    "Mémoire privée : premier commit":
        "Private memory: first commit",
    "refus : premier commit du dépôt privé impossible ({erreur})":
        "refused: first commit of the private repository impossible ({erreur})",
    "premier commit du dépôt privé":
        "first commit of the private repository",
    "!! dépôt privé non poussé ({erreur}) : le pousser, sans quoi la CI ne trouvera pas le commit du verrou":
        "!! private repository not pushed ({erreur}): push it, otherwise the CI will not find the lock's commit",
    "dépôt privé poussé":
        "private repository pushed",
    "verrou : {sha} ({verrou})":
        "lock: {sha} ({verrou})",
    "!! clé de déploiement non créée ({erreur})":
        "!! deploy key not created ({erreur})",
    "!! ssh-keygen absent : créer la clé à la main, `ssh-keygen -t ed25519 -N \"\" -f {cle}`":
        "!! ssh-keygen missing: create the key by hand, `ssh-keygen -t ed25519 -N \"\" -f {cle}`",
    "clé de déploiement : {cle} (hors du dépôt, jamais commitée)":
        "deploy key: {cle} (outside the repository, never committed)",
    "Ensuite :":
        "Then:",
    "  - effacer la clé privée une fois le secret posé : rm {cle}":
        "  - delete the private key once the secret is set: rm {cle}",
    "  - commiter puis pousser : git add {verrou} .gitignore && git commit -m \"Mémoire privée : le dépôt "
    "compagnon\" && git push":
        "  - commit then push: git add {verrou} .gitignore && git commit -m \"Private memory: the companion "
        "repository\" && git push",
    "Sur GitHub, deux gestes :":
        "On GitHub, two steps:",
    "  1. la clé publique en clé de déploiement du dépôt privé, en lecture seule":
        "  1. the public key as a deploy key of the private repository, read-only",
    "     (le contenu de {cle}.pub)":
        "     (the content of {cle}.pub)",
    "  2. deux secrets du dépôt public":
        "  2. two secrets of the public repository",
    "     SOCLE_PRIVE_CLE   = le contenu de {cle}":
        "     SOCLE_PRIVE_CLE   = the content of {cle}",
    "  Ou, avec gh :":
        "  Or, with gh:",
    "non disponible localement (gh absent) — voir la pull request":
        "not available locally (gh missing) — see the pull request",
    "non disponible (gh ne répond pas)":
        "not available (gh does not answer)",
    "non disponible (gh non authentifié ou aucune exécution)":
        "not available (gh not authenticated or no run)",
    "non disponible (réponse illisible)":
        "not available (unreadable answer)",
    "{ci} : {etat} sur {sha}":
        "{ci}: {etat} on {sha}",
    "dépôt hors de GitHub":
        "repository outside GitHub",
    "aucune branche par défaut connue":
        "no known default branch",
    "gh absent":
        "gh missing",
    "gh non authentifié, ou réponse illisible":
        "gh not authenticated, or unreadable answer",
    " ; revue des propriétaires du code exigée":
        "; code owners' review required",
    " ; revue des propriétaires du code non exigée":
        "; code owners' review not required",
    "remettre en marche le balayage de mutation : {message}":
        "restart the mutation sweep: {message}",
    "mutation : {message}":
        "mutation : {message}",
    "== {nom} — état dérivé par `socle state`, rien de recopié ==":
        "== {nom} — state derived by `socle state`, nothing copied ==",
    "git : indisponible ({erreur})":
        "git      : unavailable ({erreur})",
    "mémoire : illisible ({erreur}) — lancer `python3 .socle/socle check`":
        "memory   : unreadable ({erreur}) — run `python3 .socle/socle check`",
    "demandes : illisibles ({erreur})":
        "requests : unreadable ({erreur})",
    "protéger la branche `{nom}` : y exiger la CI « {ci} » avant toute fusion":
        "protect the branch `{nom}`: require the CI “{ci}” there before any merge",
    "branche  : {nom} — CI du socle exigée avant fusion{revue}":
        "branch   : {nom} — socle CI required before merging{revue}",
    "branche  : {nom} — CI du socle NON exigée : une CI rouge n'empêche pas de fusionner":
        "branch   : {nom} — socle CI NOT required: a red CI does not prevent merging",
    "branche  : protection inconnue ({detail})":
        "branch   : protection unknown ({detail})",
    "ce qui revient à l'humain : incalculable ({erreur})":
        "what falls to the human: cannot be computed ({erreur})",
    "écrit par l'humain lui-même depuis le dernier commit de l'agent : {n} — à lui citer, avec le lien":
        "written by the human themselves since the agent's last commit: {n} — to cite to them, with the link",
    "ce que l'humain a écrit lui-même : incalculable ({erreur})":
        "what the human wrote themselves: cannot be computed ({erreur})",
    "vérifier : `python3 .socle/socle verify --fast` (tout : sans `--fast`)":
        "verify   : `python3 .socle/socle verify --fast` (everything: without `--fast`)",
    "commit   : aucun (dépôt neuf)":
        "commit   : none (new repository)",
    "arbre propre":
        "clean tree",
    "ATTENTION, {n} fichier(s) non commité(s)":
        "WARNING, {n} uncommitted file(s)",
    "commit   : {sha} sur {branche} ({propre})":
        "commit   : {sha} on {branche} ({propre})",
    "base     : {defaut} — non fusionné : {n} commit(s)":
        "base     : {defaut} — not merged: {n} commit(s)",
    "  … et {n} autre(s)":
        "  … and {n} more",
    "depuis la base : {code} fichier(s) de code, {docs} de doc, {memoire} de mémoire":
        "since the base: {code} code file(s), {docs} doc, {memoire} memory",
    "  ^ du code a changé et la mémoire non : la fin de tour le refusera":
        "  ^ code changed and the memory did not: the end of turn will refuse it",
    "base     : aucune branche par défaut connue":
        "base     : no known default branch",
    "CI       : {ci}":
        "CI       : {ci}",
    "mesuré(s)":
        "measured",
    "supposé(s)":
        "assumed",
    "réfuté(s)":
        "refuted",
    "validé(s)":
        "validated",
    "mémoire  : {faits} fait(s) ({detail}) · {adrs} décision(s) · journal : {journal} entrée(s), dernière {dernier}":
        "memory   : {faits} fact(s) ({detail}) · {adrs} decision(s) · journal: {journal} entry(ies), last {dernier}",
    "aucun":
        "none",
    "décisions, index decisions@{empreinte} (une en entier : `python3 .socle/socle show ADR-NNNN`) :":
        "decisions, index decisions@{empreinte} (one in full: `python3 .socle/socle show ADR-NNNN`):",
    "backlog  : {ouverts} ouvert(s), {en_cours} en cours, {bloques} bloqué(s), {clos} clos":
        "backlog  : {ouverts} open, {en_cours} in progress, {bloques} blocked, {clos} closed",
    "en cours":
        "in progress",
    "bloqué":
        "blocked",
    "péremption : chantier actif inchangé depuis {age} jours (seuil {jours})":
        "staleness: active work unchanged for {age} days (threshold {jours})",
    "demandes humaines en attente : {n}":
        "pending human requests: {n}",
    " (du {date})":
        " (of {date})",
    "  RENVOYÉE (contexte insuffisant) : {id} — à réécrire en une demande qui la remplace":
        "  SENT BACK (insufficient context): {id} — to rewrite as a request that replaces it",
    "hooks    : aucune trace — ils n'ont encore jamais tiré dans ce clone":
        "hooks    : no trace — they have never fired in this clone yet",
    "hooks    : {n} déclenchement(s) tracé(s), dernier : {dernier}":
        "hooks    : {n} firing(s) traced, last: {dernier}",
    "!! base « {valeur} » introuvable — repli sur la branche par défaut":
        "!! base “{valeur}” not found — falling back to the default branch",
    "socle {version} — contrôles, étage {etage}":
        "socle {version} — checks, stage {etage}",
    ", sans base":
        ", no base",
    "socle {version} — vérification rapide":
        "socle {version} — fast verification",
    "socle {version} — vérification complète":
        "socle {version} — full verification",
    "hook inconnu : {evt}":
        "unknown hook: {evt}",
    "`[private] layers` : « {nom} » n'est pas une couche ({liste})":
        "`[private] layers`: “{nom}” is not a layer ({liste})",
    "refus : mémoire privée indisponible ({raison}) ; une entrée privée ne s'écrit pas à l'aveugle. `--public` si "
    "elle peut être publique, sinon attendre l'accès.":
        "refused: private memory unavailable ({raison}); a private entry is not written blindly. `--public` if it "
        "can be public, otherwise wait for access.",
    "{ident} : aucune entrée de ce nom dans la mémoire":
        "{ident}: no entry of that name in the memory",
    ", archivée dans {parent}":
        ", archived in {parent}",
    "\n--- réponse ({chemin}) : {statut} ---":
        "\n--- answer ({chemin}): {statut} ---",
    "`socle private term <terme>` : une mémoire privée, et un terme":
        "`socle private term <term>`: a private memory, and a term",
    "terme ajouté à la liste privée":
        "term added to the private list",
    "terme déjà dans la liste privée":
        "term already in the private list",
    "`socle private move <ID>` : l'identifiant d'une entrée publique":
        "`socle private move <ID>`: the identifier of a public entry",
    "le verrou n'existe qu'en mode compagnon (`[private] mode` de la politique)":
        "the lock only exists in companion mode (`[private] mode` of the policy)",
    "dépôt privé absent de `{dossier}/` : le cloner d'abord":
        "private repository missing from `{dossier}/`: clone it first",
    "{n} changement(s) privé(s) sans commit : les commiter dans le dépôt privé d'abord":
        "{n} private change(s) without a commit: commit them in the private repository first",
    "verrou : {sha} — à commiter avec le reste (`{fichier_verrou}`)":
        "lock: {sha} — to commit with the rest (`{fichier_verrou}`)",
    "pas de verrou à extraire":
        "no lock to extract",
    "mémoire privée remise au verrou : {verrou}":
        "private memory set back to the lock: {verrou}",
    "dire relu sans --relayed":
        "say reviewed without --relayed",
    "refus : une relecture relayée nomme l'humain (--by) et cite son texte exact (--quote-file)":
        "refused: a relayed review names the human (--by) and cites their exact text (--quote-file)",
    "relu : {sha} peut partir vers le dépôt public":
        "reviewed: {sha} can leave for the public repository",
    "--- index {index}@{empreinte} — à citer `lu : {index}@…` ---":
        "--- index {index}@{empreinte} — to cite `read : {index}@…` ---",
    "(vide)":
        "(empty)",
    "demande introuvable : {demande}":
        "request not found: {demande}",
    "refus : une réponse relayée nomme l'humain qui l'a donnée (--by), à moins que la politique ne le nomme "
    "(`[human] name`)":
        "refused: a relayed answer names the human who gave it (--by), unless the policy names them "
        "(`[human] name`)",
    "note : --by « {by} » n'est pas le nom que la politique donne à l'humain (« {nom} »)":
        "note: --by “{by}” is not the name the policy gives the human (“{nom}”)",
    "répondre sans --relayed":
        "answer without --relayed",
    "refus : {id} n'a pas pu être lue par l'humain — {pourquoi}. Une réponse ne se relaie qu'à une demande qu'il a "
    "pu lire : la pousser, lui donner son lien (`socle url {id}`), puis consigner la réponse qu'il donne ensuite. Il "
    "peut aussi répondre lui-même, sans --relayed, dans son terminal.":
        "refused: {id} could not be read by the human — {pourquoi}. An answer is only relayed to a request they "
        "could read: push it, give them its link (`socle url {id}`), then record the answer they give afterwards. "
        "They can also answer themselves, without --relayed, in their terminal.",
    "réponse « {answer} » écrite dans {chemin} — à commiter avec la suite.":
        "answer “{answer}” written in {chemin} — to commit with what follows.",
    "rien à approuver : aucun fichier protégé changé depuis le dernier commit":
        "nothing to approve: no protected file changed since the last commit",
    "{n} fichier(s) protégé(s) changé(s) depuis le dernier commit :":
        "{n} protected file(s) changed since the last commit:",
    "refus : confirmer par `--yes`, ou nommer les fichiers par `--files`":
        "refused: confirm with `--yes`, or name the files with `--files`",
    "Les approuver ? [o/N] ":
        "Approve them? [y/N] ",
    "rien n'est approuvé":
        "nothing is approved",
    "refus : la raison cite {i}, qui n'existe pas dans cette mémoire":
        "refused: the reason cites {i}, which does not exist in this memory",
    "refus : {f} n'existe ni ici ni au dernier commit : rien à approuver":
        "refused: {f} exists neither here nor at the last commit: nothing to approve",
    "rien à approuver : --files ou --keys":
        "nothing to approve: --files or --keys",
    "{ident} écrite et validée : {chemin}":
        "{ident} written and approved: {chemin}",
    "socle {version} — auto-test par injection de défauts":
        "socle {version} — self-test by fault injection",
    "{calculee}  ({n} fichiers sous {dossier_moteur}/socle et le lanceur)":
        "{calculee}  ({n} files under {dossier_moteur}/socle and the launcher)",
    "supprimé":
        "deleted",
    "socle {version} — verdict de mutation":
        "socle {version} — mutation verdict",
    "socle {version} — balayage de mutation":
        "socle {version} — mutation sweep",
    "pour l'humain":
        "for the human",
    "pour l'agent":
        "for the agent",
    "internes (hooks, CI, moteur)":
        "internal (hooks, CI, engine)",
    "(humain seul) mettre en place le dépôt privé du mode compagnon : --repo <adresse>":
        "(human only) set up the companion mode's private repository: --repo <address>",
    "{groupe} :":
        "{groupe}:",
    "socle {version} — mémoire, documentation et tests fiables":
        "socle {version} — reliable memory, documentation and tests",
    "racine du projet (défaut : le dépôt git courant)":
        "project root (default: the current git repository)",
    "le guide de l'humain : ses gestes, chacun avec sa commande":
        "the human's guide: their steps, each with its command",
    "où en est le projet, calculé à chaque fois (injecté au démarrage de l'agent)":
        "where the project stands, computed every time (injected when the agent starts)",
    "sans le contenu de l'actif et du canonique":
        "without the content of the active work and the canonical memory",
    "contrôles du socle, un code de sortie":
        "the socle's checks, one exit code",
    "révision de base (défaut : divergence avec la branche par défaut)":
        "base revision (default: divergence from the default branch)",
    "révision contrôlée (défaut : l'arbre de travail)":
        "checked revision (default: the working tree)",
    "liste de contrôles, séparés par des virgules":
        "list of checks, separated by commas",
    "sans les contrôles lents":
        "without the slow checks",
    "ne montrer que ce qui échoue ou avertit":
        "only show what fails or warns",
    "le contrat verify : capacités de l'adaptateur puis contrôles":
        "the verify contract: the adapter's capabilities then the checks",
    "relancer les étapes rapides même si elles ont déjà passé sur cet arbre exact":
        "run the fast steps again even if they already passed on this exact tree",
    "tout : capacités, contrôles, auto-test":
        "everything: capabilities, checks, self-test",
    "point d'entrée des hooks de l'agent et de git":
        "entry point of the agent's and git's hooks",
    "prochain identifiant libre":
        "next free identifier",
    "ajoute une entrée squelette avec son identifiant":
        "adds a skeleton entry with its identifier",
    "dans la mémoire privée (défaut quand elle existe)":
        "in the private memory (default when it exists)",
    "dans la mémoire publique, même quand une mémoire privée existe":
        "in the public memory, even when a private memory exists",
    "afficher une entrée de mémoire, avec son empreinte, ou un index":
        "show a memory entry, with its fingerprint, or an index",
    "l'index des décisions ou du backlog ouvert":
        "the index of the decisions or of the open backlog",
    "mémoire privée : état, verrou du dépôt compagnon, termes, bascule ; `install` (humain seul) met en place le "
    "dépôt compagnon":
        "private memory: status, companion repository lock, terms, move; `install` (human only) sets up the "
        "companion repository",
    "avec `term` : le terme à ajouter à la liste privée ; avec `move` : l'identifiant de l'entrée publique à "
    "basculer dans la mémoire privée":
        "with `term`: the term to add to the private list; with `move`: the identifier of the public entry to move "
        "into the private memory",
    "avec `install` (humain seul) : l'adresse du dépôt privé, cloné et mis en place":
        "with `install` (human only): the address of the private repository, cloned and set up",
    "tu as relu ce qui part vers le dépôt public ; l'agent y relaie ton accord (--relayed)":
        "you reviewed what leaves for the public repository; the agent relays your agreement (--relayed)",
    "accord donné par l'humain dans la conversation":
        "agreement given by the human in the conversation",
    "le permalien d'un fichier ou d'une entrée, à donner à l'humain":
        "the permalink of a file or an entry, to give to the human",
    "répondre à une demande ; l'agent y relaie (--relayed) ta réponse donnée dans la conversation":
        "answer a request; the agent relays (--relayed) your answer given in the conversation",
    "réponse donnée par l'humain dans la conversation":
        "answer given by the human in the conversation",
    "texte exact de l'humain (avec --relayed)":
        "the human's exact text (with --relayed)",
    "fichier qui contient le texte exact de l'humain":
        "file that contains the human's exact text",
    "(humain seul) approuver tes changements protégés ; sans --files, ceux qui ont changé":
        "(human only) approve your protected changes; without --files, those that changed",
    "sans --files : approuver sans demander confirmation":
        "without --files: approve without asking for confirmation",
    "installer ou mettre à jour le socle dans un projet":
        "install or update the socle in a project",
    "`auto`, le défaut (déduit du dépôt), un adaptateur maintenu ({adaptateurs}) ou le chemin d'un .toml":
        "`auto`, the default (deduced from the repository), a maintained adapter ({adaptateurs}) or the path of a "
        ".toml",
    "ce que la décision approuve (le chemin du document)":
        "what the decision approves (the document's path)",
    "propriétaire pour CODEOWNERS, ex. @theodubus":
        "owner for CODEOWNERS, e.g. @theodubus",
    "le nom de l'humain, qui signe les réponses que l'agent relaie (défaut : son nom git, hors session cloud)":
        "the human's name, which signs the answers the agent relays (default: their git name, outside a cloud "
        "session)",
    "projet existant : plafonds au niveau actuel":
        "existing project: caps at the current level",
    "mémoire privée, et son mode":
        "private memory, and its mode",
    "relecture humaine avant publication":
        "human review before publication",
    "demandes et réponses dans la mémoire privée":
        "requests and answers in the private memory",
    "mode chiffré : le nom du filtre git de l'outil":
        "encrypted mode: the name of the tool's git filter",
    "langue de la mémoire d'un projet neuf : mots-clés, gabarits et messages du moteur (défaut : fr)":
        "language of a new project's memory: keywords, templates and the engine's messages (default: fr)",
    "initialiser la mémoire depuis un cadrage, rien, ou le dépôt existant":
        "initialize the memory from a brief, nothing, or the existing repository",
    "le document de cadrage, archivé tel quel":
        "the brief, archived as is",
    "auditer le dépôt existant, en lecture seule":
        "audit the existing repository, read-only",
    "injecte des défauts connus et vérifie qu'ils sont attrapés":
        "injects known faults and checks that they are caught",
    "empreinte du moteur et de fichiers":
        "fingerprint of the engine and of files",
    "survivants d'un balayage contre les plafonds":
        "survivors of a sweep against the caps",
    "écrire le plafond mesuré des modules « à mesurer » dans les garde-fous":
        "write the measured cap of the modules “to measure” into the guardrails",
    "lance le balayage de mutation de l'adaptateur, puis son verdict":
        "runs the adapter's mutation sweep, then its verdict",
    "donne le prochain identifiant libre à une entrée qu'une autre branche a prise aussi":
        "gives the next free identifier to an entry another branch also took",
    "liste des contrôles":
        "list of the checks",
    "socle {version} — mémoire, documentation et tests fiables\n":
        "socle {version} — reliable memory, documentation and tests\n",
    "\nLe guide : `python3 .socle/socle help` ; toutes les commandes : `python3 .socle/socle --help`.":
        "\nThe guide: `python3 .socle/socle help`; all the commands: `python3 .socle/socle --help`.",
    "adresse du dépôt inconnue : l'humain la règle dans la politique (`[human] repo_url`)":
        "unknown repository address: the human sets it in the policy (`[human] repo_url`)",
    "{cible} : aucune entrée de ce nom dans la mémoire":
        "{cible}: no entry of that name in the memory",
    "rien n'est poussé : pousser d'abord":
        "nothing is pushed: push first",
    "{chemin} n'est pas dans la version poussée ({sha}) : pousser d'abord":
        "{chemin} is not in the pushed version ({sha}): push first",
    "{chemin} : la version locale n'est pas poussée, le lien montre la version poussée":
        "{chemin}: the local version is not pushed, the link shows the pushed version",
    "{chemin} est chiffré sur GitHub, où l'humain ne peut pas le lire : le lui donner en entier dans la conversation":
        "{chemin} is encrypted on GitHub, where the human cannot read it: give it to them in full in the conversation",
    "dépôt privé non cloné, sans adresse web, ou rien n'y est poussé":
        "private repository not cloned, without a web address, or nothing pushed there",
    "{chemin} n'est pas dans la version poussée du dépôt privé : y pousser d'abord":
        "{chemin} is not in the pushed version of the private repository: push there first",
    "commit {version} inconnu ou pas poussé":
        "commit {version} unknown or not pushed",
    "{chemin} n'existe pas dans la version poussée « {ref} »":
        "{chemin} does not exist in the pushed version “{ref}”",
    "version « {version} » inconnue ou pas poussée":
        "version “{version}” unknown or not pushed",
    "lien relatif « {cible} » : hors du conteneur, il ne mène nulle part":
        "relative link “{cible}”: outside the container, it leads nowhere",
    "`{code}` : aucun chemin de ce nom dans le dépôt, le lien qu'en fait le client mène à un 404":
        "`{code}`: no path of that name in the repository, the link the client makes of it leads to a 404",
    "capacité absente : {absent}":
        "capability absent: {absent}",
    "lecteur de résultats inconnu : « {parser} » (connus : {liste})":
        "unknown results reader: “{parser}” (known: {liste})",
    "dossier de résultats introuvable : {dossier}":
        "results folder not found: {dossier}",
    "plafond vide : rien à comparer — un vert ici serait silencieux":
        "empty cap: nothing to compare — a green here would be silent",
    "{module} : à mesurer, et pas encore balayé":
        "{module}: to measure, and not swept yet",
    "{module} : à mesurer — {n} survivant(s) ; ":
        "{module}: to measure — {n} survivor(s); ",
    "plafond posé":
        "cap set",
    "`--record` l'écrit comme plafond":
        "`--record` writes it as the cap",
    "{module} : aucun résultat — le balayage n'a pas tourné sur ce module":
        "{module}: no result — the sweep did not run on this module",
    "{module} : {n} survivant(s) pour un plafond de {plafond} — du code a cessé d'être couvert. Corriger les tests, "
    "ou demander à relever le plafond (raison écrite).":
        "{module}: {n} survivor(s) for a cap of {plafond} — code stopped being covered. Fix the tests, or ask to "
        "raise the cap (written reason).",
    "{module} : {n} survivant(s) sous le plafond {plafond} — resserrer le plafond":
        "{module}: {n} survivor(s) under the cap {plafond} — tighten the cap",
    "{module} : plafond annoncé mais non écrit — la forme de sa clé dans `{fichier}` n'est pas reconnue ; l'écrire à "
    "la main":
        "{module}: cap announced but not written — the form of its key in `{fichier}` is not recognised; write it by "
        "hand",
    "la commande de l'adaptateur balaie module par module sans `{output}` : chaque balayage écraserait le précédent "
    "; y ajouter l'option de l'outil qui choisit son dossier de sortie, `{output}` en valeur":
        "the adapter's command sweeps module by module without `{output}`: each sweep would overwrite the previous "
        "one; add the tool's option that chooses its output folder, with `{output}` as value",
    "plafond vide : aucun module à balayer":
        "empty cap: no module to sweep",
    "le workflow est « {etat} » : GitHub endort les workflows planifiés d'un dépôt public après soixante jours sans "
    "activité, et plus rien ne mesure le cliquet. Le réactiver (Actions → le workflow → Enable workflow), puis le "
    "lancer à la main":
        "the workflow is “{etat}”: GitHub puts the scheduled workflows of a public repository to sleep after sixty "
        "days without activity, and nothing measures the ratchet any more. Re-enable it (Actions → the workflow → "
        "Enable workflow), then run it by hand",
    "aucun balayage en {age} jours d'existence du workflow : son cron ne part pas. Le lancer à la main, et chercher "
    "pourquoi":
        "no sweep in {age} days of the workflow's existence: its cron does not start. Run it by hand, and find out "
        "why",
    "pas encore de balayage : le premier part au prochain créneau du cron, ou à la main":
        "no sweep yet: the first one starts at the cron's next slot, or by hand",
    "dernier balayage il y a {age} jours ({derniere}) : le workflow est actif mais ne tourne plus. Le lancer à la "
    "main, et chercher pourquoi son cron ne part plus":
        "last sweep {age} days ago ({derniere}): the workflow is active but no longer runs. Run it by hand, and find "
        "out why its cron no longer starts",
    "dernier balayage il y a {age} jour(s)":
        "last sweep {age} day(s) ago",
    "gh a échoué":
        "gh failed",
    "réponse illisible":
        "unreadable answer",
    "aucun workflow ne lance le balayage de mutation : le cliquet ne se mesure jamais. Relancer l'installeur, qui "
    "pose `{workflow}`":
        "no workflow runs the mutation sweep: the ratchet is never measured. Run the installer again, which lays "
        "down `{workflow}`",
    "dépôt hors de GitHub : la vivacité du balayage ne s'y lit pas":
        "repository outside GitHub: the sweep's liveness cannot be read there",
    "gh absent : la vivacité du balayage ne se lit pas":
        "gh missing: the sweep's liveness cannot be read",
    "`{nom}` n'est pas encore sur la branche par défaut : GitHub ne le planifie qu'une fois fusionné":
        "`{nom}` is not on the default branch yet: GitHub only schedules it once merged",
    "API de GitHub injoignable ({faute}) : dans la CI, il faut `GH_TOKEN` et le droit `actions: read`":
        "GitHub API unreachable ({faute}): in the CI, it needs `GH_TOKEN` and the `actions: read` permission",
    "exécutions du balayage illisibles ({faute})":
        "sweep runs unreadable ({faute})",
    "réponse illisible : {erreur}":
        "unreadable answer: {erreur}",
    "en-tête `<!-- socle: couche=demandes zone=… -->` absent ou faux":
        "header `<!-- socle: layer=requests zone=… -->` missing or wrong",
    "pas de titre `# D-NNNN — <décision en une phrase>`":
        "no title `# D-NNNN — <decision in one sentence>`",
    "le titre doit énoncer la décision demandée en une phrase":
        "the title must state the requested decision in one sentence",
    "section « {titre} » absente":
        "section “{titre}” missing",
    "section « {titre} » vide ou trop courte":
        "section “{titre}” empty or too short",
    "section « {titre} » : texte du gabarit laissé tel quel ({trou}…)":
        "section “{titre}”: template text left as is ({trou}…)",
    "« Contexte » trop court : moins de {n} mots ne suffisent pas à quelqu'un qui n'a pas ouvert le projet depuis "
    "une semaine":
        "“Context” too short: fewer than {n} words are not enough for someone who has not opened the project for a "
        "week",
    "« Où regarder » doit donner un lien vers chaque document ou passage à lire, et dire ce qu'il faut y vérifier : "
    "le permalien de `socle url <chemin>` ; sans adresse de dépôt connue, un lien relatif depuis la demande "
    "(`[calc.py](../../calc.py)`)":
        "“Where to look” must give a link to each document or passage to read, and say what to check there: the "
        "permalink of `socle url <path>`; with no known repository address, a relative link from the request "
        "(`[calc.py](../../calc.py)`)",
    "« Options » doit dire l'effort de chaque option":
        "“Options” must give the effort of each option",
    "« Options » doit dire le risque de chaque option":
        "“Options” must give the risk of each option",
    "« Options » doit dire la réversibilité de chaque option":
        "“Options” must give the reversibility of each option",
    "« Conséquences » doit dire ce qui se passe si l'humain valide":
        "“Consequences” must say what happens if the human approves",
    "« Conséquences » doit dire ce qui se passe si l'humain refuse":
        "“Consequences” must say what happens if the human rejects",
    "« Conséquences » doit dire ce qui se passe sans réponse":
        "“Consequences” must say what happens with no answer",
    "« Recommandation » doit séparer ce qui est vérifié de ce qui est supposé":
        "“Recommendation” must keep what is verified apart from what is assumed",
    "« Réponses possibles » : au moins deux réponses, en liste `- \\`valeur\\` — sens`":
        "“Possible answers”: at least two answers, as a list `- \\`value\\` — meaning`",
    "« Réponses possibles » doit proposer `{renvoi}`":
        "“Possible answers” must offer `{renvoi}`",
    "« Réponses possibles » : la demande nomme {noms}, que seule une réponse `{positive}` autorise à changer, mais "
    "ne propose pas `{positive}` ; la proposer pour l'option qui y touche (une autre option mène à une demande "
    "nouvelle)":
        "“Possible answers”: the request names {noms}, which only an answer `{positive}` authorises to change, but "
        "does not offer `{positive}`; offer it for the option that touches them (another option leads to a new "
        "request)",
    "identifiant `{ident}` cité sans description : le décrire en clair dans « Éléments cités » (`- <identifiant> — "
    "ce que c'est, en une phrase`)":
        "identifier `{ident}` cited without a description: describe it in plain words in “Cited elements” (`- "
        "<identifier> — what it is, in one sentence`)",
    "réponse sans champ `reponse`":
        "answer without a `reponse` field",
    "réponse `{reponse}` absente des réponses possibles de la demande":
        "answer `{reponse}` not among the request's possible answers",
    "réponse relayée depuis la conversation sans la citation exacte de l'humain":
        "answer relayed from the conversation without the human's exact quote",
    "la demande a changé après la réponse : la réponse portait sur un autre texte (une demande répondue est gelée ; "
    "en écrire une nouvelle qui la remplace)":
        "the request changed after the answer: the answer was about another text (an answered request is frozen; "
        "write a new one that replaces it)",
    "`{reponse}` n'est pas une réponse possible : {liste}":
        "`{reponse}` is not a possible answer: {liste}",
    "{id} a déjà une réponse ({reponse})":
        "{id} already has an answer ({reponse})",
    "canal inconnu : {canal}":
        "unknown channel: {canal}",
    "une réponse relayée cite le texte exact de l'humain (--quote ou --quote-file)":
        "a relayed answer cites the human's exact text (--quote or --quote-file)",
    "# Réponse humaine donnée dans la conversation, consignée par l'agent avec\n# le texte exact de l'humain "
    "(`citation`). Relue avec le diff.\n":
        "# Human answer given in the conversation, recorded by the agent with\n# the human's exact text "
        "(`citation`). Reviewed with the diff.\n",
    "# Réponse humaine, écrite par l'humain lui-même (`socle answer`).\n":
        "# Human answer, written by the human themselves (`socle answer`).\n",
    "# Elle porte sur le texte exact de {demande}, dont l'empreinte suit.\n":
        "# It is about the exact text of {demande}, whose fingerprint follows.\n",
    "la version poussée diffère de la version locale":
        "the pushed version differs from the local version",
    "TOML illisible : {erreur}":
        "unreadable TOML: {erreur}",
    "aucune révision de base : contrôle non exécuté":
        "no base revision: check not run",
    "le contrôle a planté : {erreur}":
        "the check crashed: {erreur}",
    "constat masqué : zone privée (relancer les contrôles là où elle se lit)":
        "finding hidden: private zone (run the checks again where it can be read)",
    "`{ident}` existait avant la branche : ce n'est pas à elle de le renuméroter":
        "`{ident}` existed before the branch: it is not for the branch to renumber it",
    "`{ident}` a reçu sa réponse : une demande répondue est gelée":
        "`{ident}` has received its answer: an answered request is frozen",
    "reporté dans {n} fichier(s) : {liste}":
        "carried over in {n} file(s): {liste}",
    "un identifiant de journal exige une date":
        "a journal identifier requires a date",
    "aucune mémoire privée dans la politique (`[private] mode`) : rien où basculer":
        "no private memory in the policy (`[private] mode`): nowhere to move to",
    "`{ident}` est déjà privée":
        "`{ident}` is already private",
    "une demande se lit là où l'humain lit : la retirer (`retirée : <raison>` dans ses métadonnées) et en poser une "
    "privée (`socle new request \"…\" --private`)":
        "a request is read where the human reads: withdraw it (`withdrawn : <reason>` in its metadata) and open a "
        "private one (`socle new request \"…\" --private`)",
    "`{ident}` : seuls un fait, un sujet, une entrée de journal ou une décision se basculent":
        "`{ident}`: only a fact, a topic, a journal entry or a decision can be moved",
    "`{ident}` est archivée dans `{parent}` : c'est cette entrée de journal qui se bascule":
        "`{ident}` is archived in `{parent}`: it is that journal entry that is moved",
    "`{ident}` archive {liste}, que d'autres entrées citent peut-être : leurs renvois publics ne survivraient pas à "
    "la bascule":
        "`{ident}` archives {liste}, which other entries may cite: their public references would not survive the move",
    "`{ident}` : son texte ne se retrouve pas tel quel dans {fichier}":
        "`{ident}`: its text is not found as is in {fichier}",
    "{ident} → {nouvel} : son titre et son texte sont dans {prive_rel}":
        "{ident} → {nouvel}: its title and its text are in {prive_rel}",
    "en public, {public_rel} ne garde de {ident} que l'identifiant : les renvois restent valides":
        "in public, {public_rel} keeps only the identifier of {ident}: references stay valid",
    "l'historique public garde l'ancien texte : seule une réécriture de l'historique, publiée en écrasant la "
    "branche, l'efface ; c'est à l'humain de la faire : le lui dire":
        "the public history keeps the old text: only a rewrite of the history, published by overwriting the branch, "
        "erases it; that is for the human to do: tell them",
    "un nom qui doit rester privé partout s'ajoute à la liste des termes : `socle private term <terme>`":
        "a name that must stay private everywhere is added to the list of terms: `socle private term <term>`",
    "mode compagnon : commiter la copie dans le dépôt privé, puis `socle private lock`":
        "companion mode: commit the copy in the private repository, then `socle private lock`",
    "  … étapes rapides déjà passées sur cet arbre exact : non relancées (`--redo` pour les relancer)":
        "  … fast steps already passed on this exact tree: not run again (`--redo` to run them again)",
    "délai dépassé : {commande}":
        "timed out: {commande}",
    "aucun test trouvé (`{commande}`) : un projet qui commence n'en a pas encore ; le premier code s'écrit avec son "
    "test":
        "no test found (`{commande}`): a project that is starting has none yet; the first code is written with its "
        "test",
    "!! outils de l'adaptateur : `{commande}` dépasse le délai du démarrage ; la relancer avant de vérifier":
        "!! adapter tools: `{commande}` exceeds the start-up time limit; run it again before verifying",
    "outils de l'adaptateur installés (session cloud) : `{commande}`":
        "adapter tools installed (cloud session): `{commande}`",
    "!! outils de l'adaptateur : `{commande}` a rendu {code} ; la relancer avant de vérifier\n    {queue}":
        "!! adapter tools: `{commande}` returned {code}; run it again before verifying\n    {queue}",
    "pas encore de code (aucun fichier {sources}) : `{commande}` non lancée ; elle tournera dès le premier fichier":
        "no code yet (no {sources} file): `{commande}` not run; it will run from the first file",
    "l'outil manque à cet environnement ; la CI l'installe ainsi : {commandes} — l'installer ici ; en session "
    "cloud, le hook de démarrage du socle l'installe dans chaque session neuve":
        "the tool is missing from this environment; the CI installs it with: {commandes} — install it here; in a "
        "cloud session, the socle's start-up hook installs it in every new session",
    "l'outil manque à cet environnement : l'installer":
        "the tool is missing from this environment: install it",
    "`{commande}` a rendu {code}\n        {queue}":
        "`{commande}` returned {code}\n        {queue}",
    "projet d'essai impossible à préparer : {erreur}":
        "test project impossible to prepare: {erreur}",
    "le témoin a planté : {erreur}":
        "the witness crashed: {erreur}",
    "témoin en échec — {nom} : un contrôle crie sur un cas sain\n        {sortie}":
        "witness failing — {nom}: a check cries out on a healthy case\n        {sortie}",
    "  témoin ok : {nom}":
        "  witness ok: {nom}",
    "{defaut} : injection impossible — {erreur}":
        "{defaut}: injection impossible — {erreur}",
    "DÉFAUT NON ATTRAPÉ : {defaut} (attendu : {controle}, étage {etage})":
        "FAULT NOT CAUGHT: {defaut} (expected: {controle}, stage {etage})",
    "{defaut} : attrapé, mais pas par {controle}\n        {sortie}":
        "{defaut}: caught, but not by {controle}\n        {sortie}",
    "  attrapé : {defaut} — {controle}, étage {etage}":
        "  caught: {defaut} — {controle}, stage {etage}",
    "installation du projet d'essai : {stdout}{stderr}":
        "installation of the test project: {stdout}{stderr}",
    "le témoin de base ne passe pas le hook pre-commit :\n{stdout}{stderr}":
        "the base witness does not pass the pre-commit hook:\n{stdout}{stderr}",
    "injection impossible : « {avant} » absent de {rel}":
        "injection impossible: “{avant}” missing from {rel}",
    "pas d'empreinte pour {cible} : {sortie}":
        "no fingerprint for {cible}: {sortie}",
    "Claude Code ne lit ses hooks que dans le dossier où la session démarre : relancer la session depuis la racine "
    "du projet ; dans une session à plusieurs dépôts, ouvrir une session sur ce dépôt seul. L'agent n'écrit jamais "
    "lui-même un réglage de Claude Code pour les rétablir : il le dit à l'humain, et ne pousse rien. Le travail en "
    "cours, qui ne peut plus se commiter, il le montre dans la conversation (`git diff`, `git stash show -p "
    "--include-untracked`, ou le texte des fichiers nouveaux), pour que l'humain le donne à la session neuve : le "
    "conteneur peut disparaître avec lui.":
        "Claude Code only reads its hooks in the folder where the session starts: restart the session from the "
        "project root; in a session with several repositories, open a session on this repository alone. The agent "
        "never writes a Claude Code setting itself to restore them: it tells the human, and pushes nothing. The work "
        "in progress, which can no longer be committed, it shows in the conversation (`git diff`, `git stash show -p "
        "--include-untracked`, or the text of the new files), for the human to give to the new session: the "
        "container may disappear with it.",
    "approuver les fichiers protégés que la mise à jour a changés : en session cloud, l'humain n'a pas de terminal "
    "pour `socle approve` ; poser une demande qui cite chaque fichier protégé changé et son empreinte (`python3 "
    ".socle/socle check` les donne), que l'humain valide dans la conversation ; poussée, elle laisse finir le tour, "
    "les fichiers changés restant dans l'arbre jusqu'à sa réponse, puis se commitant avec elle. Une session qui a dû "
    "ajouter le dépôt du socle ne se reprend pas : y commiter, pousser la branche et ouvrir la pull request, d'une traite et sans rien "
    "attendre, et poser la demande dans une session neuve sur le seul dépôt du projet, sur cette branche":
        "approve the protected files the update changed: in a cloud session, the human has no terminal for `socle "
        "approve`; put a request that cites each changed protected file and its fingerprint (`python3 .socle/socle "
        "check` gives them), which the human approves in the conversation; once pushed, it lets the turn end, the "
        "changed files staying in the tree until the answer, then committed with it. A session that had to add the socle's "
        "repository is not resumed: commit there, push the branch and open the pull request, in one go and without "
        "waiting for anything, and put the request in a new session on the project's repository alone, on that "
        "branch",
    "{sha} « {sujet} » : aucun PreToolUse n'a tiré pendant la session — les hooks de l'agent n'étaient pas chargés. "
    "{remede}":
        "{sha} “{sujet}”: no PreToolUse fired during the session — the agent's hooks were not loaded. {remede}",
    "{sha} « {sujet} » : aucun PreToolUse n'a tiré depuis le commit précédent — les hooks de l'agent ont cessé "
    "d'être chargés en cours de session. {remede}":
        "{sha} “{sujet}”: no PreToolUse fired since the previous commit — the agent's hooks stopped being loaded "
        "during the session. {remede}",
    "socle — commit refusé : commit d'agent sans aucun passage du filtre de l'agent depuis le commit précédent "
    "(`{depuis}`) : ses hooks ne sont pas chargés. {remede}":
        "socle — commit refused: agent commit without any pass of the agent's filter since the previous commit "
        "(`{depuis}`): its hooks are not loaded. {remede}",
    "!! LES HOOKS DE L'AGENT NE SONT PAS CHARGÉS dans cette session : aucun n'a tiré pour elle récemment, ni au "
    "démarrage ni avant cette commande (une session reprise hors de la racine du projet garde ses traces d'avant). "
    "Ni le filtre des commandes, ni les contrôles de fin de tour, ni l'état au démarrage ne tournent. Le dire à "
    "l'humain avant tout travail. {remede}":
        "!! THE AGENT'S HOOKS ARE NOT LOADED in this session: none fired for it recently, neither at startup nor "
        "before this command (a session resumed outside the project root keeps its traces from before). Neither "
        "the command filter, nor the end-of-turn checks, nor the state at startup run. Tell the human before any "
        "work. {remede}",
    # Les textes des adaptateurs maintenus (`absent`, `replacement`), écrits
    # dans leurs fichiers et traduits à l'affichage.
    "signal secondaire, jamais un garde-fou":
        "secondary signal, never a guardrail",
    "capacité `mutation`":
        "capability `mutation`",
    "aucun formateur imposé ; un projet qui adopte spotless ou google-java-format le déclare ici":
        "no formatter imposed; a project that adopts spotless or google-java-format declares it here",
    "relecture du diff, et `build` (le compilateur refuse ce qui ne se lit pas)":
        "review of the diff, and `build` (the compiler refuses what does not parse)",
    "aucun linter imposé ; un projet qui adopte checkstyle ou spotbugs le déclare ici":
        "no linter imposed; a project that adopts checkstyle or spotbugs declares it here",
    "capacité `build` : `javac` avec ses avertissements":
        "capability `build`: `javac` with its warnings",
    "aucun formateur imposé ; un projet qui adopte prettier le déclare ici (`npx prettier --check .`)":
        "no formatter imposed; a project that adopts prettier declares it here (`npx prettier --check .`)",
    "relecture du diff, et la capacité `tests`, qui charge chaque module testé":
        "review of the diff, and the capability `tests`, which loads each tested module",
    "aucun linter imposé ; un projet qui adopte eslint ou tsc le déclare ici (`npx eslint .`, `npx tsc --noEmit`)":
        "no linter imposed; a project that adopts eslint or tsc declares it here (`npx eslint .`, `npx tsc --noEmit`)",
    "la capacité `tests` : vitest refuse un module qui ne se charge pas":
        "the capability `tests`: vitest refuses a module that does not load",
    "langage interprété ; TypeScript se transpile à la volée par vitest":
        "interpreted language; vitest transpiles TypeScript on the fly",
    "capacité `tests`":
        "capability `tests`",
    "aucun formateur imposé ; un projet qui adopte php-cs-fixer le déclare ici":
        "no formatter imposed; a project that adopts php-cs-fixer declares it here",
    "relecture du diff, et `lint` (`php -l` de chaque fichier)":
        "review of the diff, and `lint` (`php -l` of each file)",
    "langage interprété : pas de compilation séparée":
        "interpreted language: no separate compilation",
    "capacité `lint` (`php -l`)":
        "capability `lint` (`php -l`)",
    "aucun formateur dans la bibliothèque standard ; un projet qui adopte ruff ou black le déclare ici":
        "no formatter in the standard library; a project that adopts ruff or black declares it here",
    "relecture du diff, et `lint` (compilation de chaque fichier)":
        "review of the diff, and `lint` (compilation of each file)",
    "capacité `lint` (compileall)":
        "capability `lint` (compileall)",
    "capacité `mutation`, ou son remplacement":
        "capability `mutation`, or its replacement",
    "pas d'outil de mutation sous unittest : l'adaptateur python-pytest emploie mutmut":
        "no mutation tool under unittest: the python-pytest adapter uses mutmut",
    "l'auto-test du socle et des tests qui injectent un défaut connu dans chaque garde-fou":
        "the socle's self-test and tests that inject a known defect into each guardrail",
    "aucun formateur imposé ; un projet qui adopte rubocop le déclare ici (`bundle exec rubocop`)":
        "no formatter imposed; a project that adopts rubocop declares it here (`bundle exec rubocop`)",
    "relecture du diff, et `lint` (`ruby -wc` de chaque fichier)":
        "review of the diff, and `lint` (`ruby -wc` of each file)",
    "capacité `lint` (`ruby -wc`)":
        "capability `lint` (`ruby -wc`)",
    "aucun analyseur imposé ; un projet qui adopte ses règles de style le déclare ici (`dotnet format style "
    "--verify-no-changes`)":
        "no analyzer imposed; a project that adopts its style rules declares it here (`dotnet format style "
        "--verify-no-changes`)",
    "capacité `build` : le compilateur et ses analyseurs par défaut, avec leurs avertissements":
        "capability `build`: the compiler and its default analyzers, with their warnings",
    "couverte par `lint` : clippy compile toutes les cibles, tests compris":
        "covered by `lint`: clippy compiles every target, tests included",
    "capacité `lint`":
        "capability `lint`",
    "signal secondaire, jamais un garde-fou : la mutation mesure ce que la couverture prétend":
        "secondary signal, never a guardrail: mutation measures what coverage claims",
    # Les noms des étapes de CI des adaptateurs, et ce que l'installeur dit
    # des workflows qu'il pose dans la langue du projet.
    "Outil de mutation":
        "Mutation tool",
    "Dépendances":
        "Dependencies",
    "pytest et mutmut":
        "pytest and mutmut",
    "Toolchain Rust":
        "Rust toolchain",
    "nom du travail de CI gardé : « {nom} », celui qu'une protection de branche exige peut-être":
        "CI job name kept: “{nom}”, the one a branch protection may require",
    "mesuré le {date} : {n} survivant(s)":
        "measured on {date}: {n} survivor(s)",
    "en attente":
        "pending",
    "retirée":
        "withdrawn",
    "renvoyée":
        "sent back",
    "répondue : {reponse}":
        "answered: {reponse}",
    "le socle exige Python 3.11 ou plus récent (tomllib) ; trouvé : ":
        "the socle requires Python 3.11 or newer (tomllib); found: ",
    # Les défauts injectés et les témoins sains de l'auto-test, décrits en
    # français dans `selftest.py` et traduits à l'affichage.
    "valeur de la doc divergente de sa source":
        "doc value diverging from its source",
    "lien ou identifiant mort":
        "dead link or identifier",
    "code modifié sans doc associée":
        "code changed without its associated doc",
    "test sans assertion":
        "test without an assertion",
    "assertion tautologique":
        "tautological assertion",
    "test désactivé sans raison écrite":
        "test disabled without a written reason",
    "test dont la seule assertion est en commentaire":
        "test whose only assertion is commented out",
    "classe de tests entière désactivée sans raison écrite":
        "whole test class disabled without a written reason",
    "plafond de mutation relevé":
        "mutation cap raised",
    "plafond de mutation remis « à mesurer »":
        "mutation cap put back to “to measure”",
    "plafond de mutation écrit à la main, sans la mesure":
        "mutation cap written by hand, without the measure",
    "doc ajoutée à une correspondance code ↔ doc":
        "doc added to a code ↔ doc mapping",
    "autre dépôt déclaré sans validation, pour que ses chemins échappent au contrôle":
        "other repository declared without approval, so that its paths escape the check",
    "budget de mémoire relevé":
        "memory budget raised",
    "correctif sans test de régression":
        "fix without a regression test",
    "test de régression qui échoue sur le parent faute de s'y charger":
        "regression test that fails on the parent because it does not load there",
    "code sans sa doc, couvert par la dispense d'un autre commit":
        "code without its doc, covered by another commit's waiver",
    "hook de l'agent absent ou jamais tiré":
        "agent hook absent or never fired",
    "hooks de l'agent arrêtés depuis le commit précédent":
        "agent hooks stopped since the previous commit",
    "session d'agent démarrée hors de la racine : ses hooks ne sont pas chargés":
        "agent session started outside the root: its hooks are not loaded",
    "commit d'agent sans passage du filtre depuis le précédent":
        "agent commit without a pass of the filter since the previous one",
    "moteur altéré dans le projet":
        "engine altered in the project",
    "politique altérée sans validation":
        "policy altered without approval",
    "fichier de test renommé hors des chemins de test : ses tests disparaissent":
        "test file renamed outside the test paths: its tests disappear",
    "fichier protégé renommé : son ancien chemin disparaît":
        "protected file renamed: its old path disappears",
    "fichier protégé changé, commité sans validation":
        "protected file changed, committed without approval",
    "demande humaine avec identifiant nu":
        "human request with a bare identifier",
    "demande qui ne dit pas où regarder":
        "request that does not say where to look",
    "demande qui nomme un test sans proposer `valider` : aucune réponse ne l'autoriserait":
        "request that names a test without offering `approve`: no answer would authorise it",
    "couche de mémoire au-delà de son budget":
        "memory layer beyond its budget",
    "identifiant privé dans un fichier public":
        "private identifier in a public file",
    "mémoire privée non accessible":
        "private memory not accessible",
    "mémoire privée commitée sans avancer le verrou":
        "private memory committed without moving the lock forward",
    "terme de la liste privée écrit dans un fichier public":
        "term of the private list written in a public file",
    "terme privé écrit sous une variante (collé, souligné)":
        "private term written in a variant (joined, underscored)",
    "terme privé dans le nom d'un fichier public":
        "private term in the name of a public file",
    "document archivé en public qui cite un terme privé":
        "document archived in public that cites a private term",
    "terme privé dans le nom d'une branche créée":
        "private term in the name of a created branch",
    "corps de pull request passé par un fichier hors du dépôt":
        "pull request body passed through a file outside the repository",
    "identifiant privé dans un bloc de code d'un fichier public":
        "private identifier in a code block of a public file",
    "fait privé effacé de la mémoire privée":
        "private fact erased from the private memory",
    "liste des termes privés commitée en clair":
        "list of private terms committed in clear",
    "terme ajouté sans accès à la mémoire privée":
        "term added without access to the private memory",
    "entrée privée écrite sans accès à la mémoire privée":
        "private entry written without access to the private memory",
    "identifiant privé dans un message de commit":
        "private identifier in a commit message",
    "l'agent écrit un terme privé dans un fichier public":
        "the agent writes a private term in a public file",
    "description de pull request qui cite un identifiant privé":
        "pull request description that cites a private identifier",
    "terme retiré de la liste privée sans validation humaine":
        "term removed from the private list without human approval",
    "sujet « done » sans référence, écrit en anglais":
        "“done” subject without a reference, written in English",
    "entrée publique « basculée » sans copie privée qui la reprenne":
        "public entry “moved” without a private copy that takes it over",
    "push vers le dépôt public sans relecture humaine":
        "push to the public repository without human review",
    "fichier privé commité en clair, sans filtre de chiffrement":
        "private file committed in clear, without an encryption filter",
    "entrée de backlog close sans référence":
        "backlog entry closed without a reference",
    "entrée de journal au titre mal formé, que rien ne lit":
        "journal entry with a malformed title, which nothing reads",
    "entrée de journal réécrite":
        "journal entry rewritten",
    "fait canonique effacé":
        "canonical fact erased",
    "valeur attendue changée sans spécification":
        "expected value changed without a specification",
    "valeur attendue changée sous une ADR que l'agent écrit lui-même":
        "expected value changed under an ADR the agent writes itself",
    "valeur attendue changée sous une demande que l'humain n'a pas pu lire, faute d'être poussée":
        "expected value changed under a request the human could not read, as it was not pushed",
    "test supprimé sans validation":
        "test deleted without approval",
    "fait passé à « validé » par l'agent":
        "fact set to “validated” by the agent",
    "SHA complété de tête":
        "SHA completed from memory",
    "force-push sans validation humaine":
        "force-push without human approval",
    "push forcé caché dans des drapeaux groupés":
        "forced push hidden in grouped flags",
    "push vers la branche par défaut par une référence complète":
        "push to the default branch through a full reference",
    "branche distante supprimée par l'API de GitHub":
        "remote branch deleted through the GitHub API",
    "fichier protégé écrit par une redirection du shell":
        "protected file written by a shell redirection",
    "dossier qui contient des fichiers protégés déplacé par le shell":
        "folder containing protected files moved by the shell",
    "l'agent coupe ses hooks par un réglage local de Claude Code":
        "the agent cuts its hooks through a local Claude Code setting",
    "chaque forme d'action irréversible ou externe":
        "each form of irreversible or external action",
    "chaque outil externe d'écriture":
        "each external writing tool",
    "référence à une entrée qui n'existe pas":
        "reference to an entry that does not exist",
    "contrôles rouges trois tours de suite, sans escalade":
        "checks red three turns in a row, without escalation",
    "fait « validé » commité sans réponse de l'humain":
        "“validated” fact committed without the human's answer",
    "demande hors contrat commitée":
        "request out of contract committed",
    "capacité absente sans son remplacement":
        "capability absent without its replacement",
    "demande réécrite après sa réponse":
        "request rewritten after its answer",
    "hooks de l'agent retirés de ses réglages":
        "agent hooks removed from its settings",
    "CLAUDE.md qui recopie des instructions":
        "CLAUDE.md that copies instructions",
    "AGENTS.md supprimé, CLAUDE.md sans la section du socle":
        "AGENTS.md deleted, CLAUDE.md without the socle section",
    "fichier de mémoire sans son en-tête":
        "memory file without its header",
    "chantier actif qui ne bouge plus":
        "active work that no longer moves",
    "fichiers privés commités sans mode de mémoire privée":
        "private files committed without a private memory mode",
    "module de code hors du cliquet de mutation":
        "code module outside the mutation ratchet",
    "balayage de mutation planifié endormi par GitHub":
        "scheduled mutation sweep put to sleep by GitHub",
    "survivants de mutation au-delà du plafond":
        "mutation survivors beyond the cap",
    "l'agent écrit une réponse humaine":
        "the agent writes a human answer",
    "l'agent répond à la place de l'humain":
        "the agent answers in place of the human",
    "l'agent approuve lui-même un changement protégé":
        "the agent approves a protected change itself",
    "l'agent commite en sautant les hooks du projet":
        "the agent commits skipping the project's hooks",
    "l'agent pousse en sautant les hooks, par -C vers le projet":
        "the agent pushes skipping the hooks, through -C into the project",
    "l'agent répond à la place de l'humain, lanceur entre guillemets après un cd":
        "the agent answers in place of the human, launcher in quotes after a cd",
    "l'agent met en place le dépôt compagnon (pousse, crée une clé)":
        "the agent sets up the companion repository (pushes, creates a key)",
    "réponse relayée sans le texte exact de l'humain":
        "relayed answer without the human's exact text",
    "réponse relayée à une demande que l'humain n'a pas pu lire":
        "relayed answer to a request the human could not read",
    "paragraphe copié dans deux fichiers":
        "paragraph copied into two files",
    "dispositif qu'aucune doc ne nomme":
        "device no doc names",
    "fin d'intervention sans dire ce qui revient à l'humain":
        "end of intervention without saying what falls to the human",
    "fin d'intervention qui ne dit pas la suite":
        "end of intervention that does not say what comes next",
    "chemin donné à l'humain qui n'existe pas dans le dépôt":
        "path given to the human that does not exist in the repository",
    "lien relatif, que l'humain ne peut pas suivre hors du conteneur":
        "relative link, which the human cannot follow outside the container",
    "permalien vers un fichier absent de la version poussée":
        "permalink to a file absent from the pushed version",
    "demande en attente citée sans son lien":
        "pending request cited without its link",
    "fonction publique ajoutée sans test qui la nomme":
        "public function added without a test that names it",
    "fonction modifiée sans test, couverte seulement par une dispense déjà poussée":
        "function changed without a test, covered only by an already pushed waiver",
    "décision ajoutée sans avoir consulté l'index des décisions":
        "decision added without consulting the index of decisions",
    "entrée citée dans une version qu'elle n'a plus":
        "entry cited in a version it no longer has",
    "identifiant que la branche par défaut a pris aussi":
        "identifier the default branch took too",
    "sujet ajouté au backlog sans l'avoir consulté":
        "subject added to the backlog without consulting it",
    "défaut indexé, corrigé seulement sur disque":
        "defect in the index, fixed only on disk",
    "code changé sans mise à jour de la mémoire":
        "code changed without updating the memory",
    "un changement complet passe la fin de tour, le commit et la CI":
        "a complete change passes the end of turn, the commit and the CI",
    "un correctif avec son test de régression passe la CI":
        "a fix with its regression test passes the CI",
    "un commit sans hooks dans un dépôt jetable, hors du projet, passe le hook de l'agent":
        "a commit without hooks in a throwaway repository, outside the project, passes the agent's hook",
    "un commit d'agent qui porte la trace de ses hooks passe la CI":
        "an agent commit that carries the trace of its hooks passes the CI",
    "une valeur attendue changée sous une spécification que l'humain a commitée passe la CI":
        "an expected value changed under a specification the human committed passes the CI",
    "CLAUDE.md gardé comme seule source, avec la section du socle, passe la CI":
        "CLAUDE.md kept as the only source, with the socle section, passes the CI",
    "une assertion reformatée à valeur égale passe la CI (relevé de recul, E)":
        "an assertion reformatted with an equal value passes the CI (step-back review, E)",
    "un chemin d'un autre dépôt, non déclaré, est signalé sans refus":
        "a path from another repository, undeclared, is reported without refusal",
    "une référence de commit en fin de phrase passe la CI":
        "a commit reference at the end of a sentence passes the CI",
    "durcir un garde-fou est libre":
        "tightening a guardrail is free",
    "un module nouveau entre au cliquet de mutation « à mesurer » : la CI passe":
        "a new module enters the mutation ratchet “to measure”: the CI passes",
    "un plafond de mutation posé par la mesure passe la CI":
        "a mutation cap set by the measure passes the CI",
    "une commande qui ne fait que citer une action refusée passe le hook de l'agent":
        "a command that only cites a refused action passes the agent's hook",
    "un mot proche d'un terme privé, sans l'être, passe le commit":
        "a word close to a private term, without being one, passes the commit",
    "un balayage de mutation planifié qui tourne passe la CI":
        "a scheduled mutation sweep that runs passes the CI",
    "un balayage de mutation sous le plafond passe le verdict":
        "a mutation sweep under the cap passes the verdict",
    "un garde-fou assoupli par l'humain, qui l'approuve, passe la CI":
        "a guardrail loosened by the human, who approves it, passes the CI",
    "un fichier protégé changé par l'humain, qui l'approuve, passe la CI":
        "a protected file changed by the human, who approves it, passes the CI",
    "une valeur attendue changée sous une demande validée par l'humain passe la CI":
        "an expected value changed under a request approved by the human passes the CI",
    "une demande complète passe le hook de l'agent":
        "a complete request passes the agent's hook",
    "une réponse donnée dans la conversation, relayée avec sa citation, passe le hook et la CI":
        "an answer given in the conversation, relayed with its quote, passes the hook and the CI",
    "une fin d'intervention avec « Pour toi : » et « Ensuite : » passe le hook de fin de tour":
        "an end of intervention with “For you:” and “Next:” passes the end-of-turn hook",
    "des liens que l'humain peut suivre passent le hook de fin de tour":
        "links the human can follow pass the end-of-turn hook",
    "une fonction ajoutée avec le test qui la nomme passe la CI":
        "a function added with the test that names it passes the CI",
    "deux pushes sains de suite passent le hook avant push, qui juge la plage de chacun":
        "two sound pushes in a row pass the pre-push hook, which judges the range of each",
    "une fonction privée, ou publique et dispensée avec sa raison, passe la CI":
        "a private function, or a public one waived with its reason, passes the CI",
    "mode compagnon : une entrée privée commitée et verrouillée passe la fin de tour, le commit et la CI":
        "companion mode: a private entry committed and locked passes the end of turn, the commit and the CI",
    "mode chiffré : une entrée privée part chiffrée et passe le commit et la CI":
        "encrypted mode: a private entry leaves encrypted and passes the commit and the CI",
    "ajouter un terme à la liste privée est libre : le commit et la CI passent":
        "adding a term to the private list is free: the commit and the CI pass",
    "mode compagnon : un sujet public basculé dans la mémoire privée passe la fin de tour, le commit et la CI":
        "companion mode: a public subject moved into the private memory passes the end of turn, the commit and the CI",
    "une mémoire en anglais : ses entrées, écrites par `socle new`, passent le commit et la CI":
        "a memory in English: its entries, written by `socle new`, pass the commit and the CI",
    "une valeur attendue changée sous une demande en attente, poussée : le tour finit, le commit attend":
        "an expected value changed under a pending request, pushed: the turn ends, the commit waits",
    "sujet du backlog d'une priorité ni haute ni basse":
        "backlog topic with a priority neither high nor low",
    "sujet fait alors que la demande qu'il attend est sans réponse":
        "topic done while the request it waits on is unanswered",
    "sujet fait avec un critère de « Fait quand » non coché":
        "topic done with an unchecked “Done when” criterion",
    "un sujet de priorité haute fait après la réponse qu'il attendait, ses critères cochés, passe le commit et la CI":
        "a high-priority topic done after the answer it waited for, its criteria checked, passes the commit and the CI",
    "un fichier protégé changé sous une demande en attente, poussée : le tour finit, le commit attend":
        "a protected file changed under a pending request, pushed: the turn ends, the commit waits",
    "un push relu par l'humain, son accord relayé avec son texte exact, passe le hook de l'agent":
        "a push reviewed by the human, their agreement relayed with their exact text, passes the agent's hook",
    "sans la clé (une CI de fork), la mémoire privée est indisponible et rien n'échoue":
        "without the key (a fork's CI), the private memory is unavailable and nothing fails",
    "en CI, un constat de la zone privée échoue sans montrer son contenu":
        "in CI, a finding in the private zone fails without showing its content",
    "une fin de tour sans travail n'exige pas de récap":
        "an end of turn without work does not require a recap",
    "un identifiant renuméroté après une collision passe la CI":
        "an identifier renumbered after a collision passes the CI",
    "une décision qui prouve ses lectures passe le commit":
        "a decision that proves its readings passes the commit",
    "un commit d'agent fait dans un autre worktree porte la trace des hooks et passe la CI":
        "an agent commit made in another worktree carries the trace of the hooks and passes the CI",
    "une session d'agent dont le hook de démarrage a tiré : l'état n'avertit pas":
        "an agent session whose startup hook fired: the state does not warn",
    "un commit d'agent dont le filtre a tiré depuis le commit précédent passe le hook avant commit":
        "an agent commit whose filter fired since the previous commit passes the pre-commit hook",
    "un défaut sur disque mais pas dans l'index ne bloque pas le commit de ce qui est indexé":
        "a defect on disk but not in the index does not block the commit of what is indexed",
    "une tautologie voulue, raison écrite, passe le commit":
        "an intended tautology, reason written, passes the commit",
    "une commande qui CITE `socle answer` sans l'appeler passe":
        "a command that CITES `socle answer` without calling it passes",
    "l'agent verrouille la mémoire privée : seule sa mise en place est réservée à l'humain":
        "the agent locks the private memory: only its setup is reserved to the human",
    "une écriture ordinaire passe le hook de l'agent":
        "an ordinary write passes the agent's hook",
    "`{id}` est clos (« {statut} ») mais reste parmi les sujets ouverts : `python3 .socle/socle archive` le range "
    "dans `{dossier}/`":
        "`{id}` is closed (“{statut}”) but stays among the open topics: `python3 .socle/socle archive` files it in "
        "`{dossier}/`",
    "`{id}` est rangé parmi les sujets clos alors qu'il est « {statut} » : `python3 .socle/socle archive` le remet "
    "parmi les ouverts":
        "`{id}` is filed among the closed topics while it is “{statut}”: `python3 .socle/socle archive` puts it back "
        "among the open ones",
    "{n} sujet(s) rangé(s) : les clos dans `{dossier}/`, les ouverts hors de lui":
        "{n} topic(s) filed: the closed ones in `{dossier}/`, the open ones outside it",
    "le backlog est déjà rangé":
        "the backlog is already in order",
    "backlog : {n} sujet(s) clos rangé(s) dans `{dossier}/`":
        "backlog: {n} closed topic(s) filed in `{dossier}/`",
    "sujet clos, avec sa référence, laissé parmi les ouverts":
        "closed topic, with its reference, left among the open ones",
    "un sujet clos, rangé avec les clos par `socle archive`, passe la CI":
        "a closed topic, filed with the closed ones by `socle archive`, passes the CI",
    "Pousser un commit sur la branche par défaut qui modifie ce fichier (une ligne de commentaire suffit ; c'est "
    "un fichier protégé, que l'humain approuve) : GitHub n'enregistre un workflow qu'au push qui modifie son "
    "fichier, pas toujours au premier push qui le pose. Puis vérifier dans l'onglet Actions qu'il y apparaît":
        "Push a commit to the default branch that changes this file (a comment line is enough; it is a protected "
        "file, which the human approves): GitHub only registers a workflow at a push that changes its file, not "
        "always at the first push that adds it. Then check in the Actions tab that it appears",
    "`{nom}` est sur la branche par défaut depuis le {date}, mais GitHub ne le connaît pas : son cron ne part "
    "jamais, et plus rien ne mesure le cliquet. {remede}":
        "`{nom}` has been on the default branch since {date}, but GitHub does not know it: its cron never starts, "
        "and nothing measures the ratchet any more. {remede}",
    "`{nom}` est sur la branche par défaut depuis le {date}, mais GitHub ne le connaît pas encore. {remede}":
        "`{nom}` has been on the default branch since {date}, but GitHub does not know it yet. {remede}",
    "balayage de mutation fusionné depuis dix jours, que GitHub ne connaît pas":
        "mutation sweep merged ten days ago, which GitHub does not know",
    "un balayage de mutation fusionné aujourd'hui, que GitHub ne connaît pas encore, passe la CI":
        "a mutation sweep merged today, which GitHub does not know yet, passes the CI",
    "chemin tiers « {motif} » ignoré : il couvrirait un fichier du socle, de la mémoire ou de la politique, que les "
    "contrôles doivent juger":
        "third-party path “{motif}” ignored: it would cover a file of the socle, of the memory or of the policy, "
        "which the checks must judge",
    "chemin tiers déclaré sans validation, pour qu'un fichier du projet échappe aux contrôles":
        "third-party path declared without validation, so that a file of the project escapes the checks",
    "chemin tiers qui couvrirait la mémoire":
        "third-party path that would cover the memory",
    "les fichiers d'un outil tiers, déclaré par l'humain qui l'approuve, échappent aux contrôles : la CI passe":
        "the files of a third-party tool, declared by the human who approves it, escape the checks: the CI passes",
    "consigner une décision prise en séance, avec la réponse de l'humain ; l'agent y relaie (--relayed) ta réponse "
    "mot pour mot":
        "record a decision taken in session, with the human's answer; the agent relays (--relayed) your answer word "
        "for word",
    "consigner une décision sans --relayed":
        "recording a decision without --relayed",
    "décision en séance consignée : {chemin}, et sa réponse « {answer} » — à commiter avec la suite.":
        "decision taken in session recorded: {chemin}, with its answer “{answer}” — to commit with the rest.",
    "décision en séance sans la réponse de l'humain : la consigner avec elle, mot pour mot (`socle decision`)":
        "decision taken in session without the human's answer: record it with it, word for word (`socle decision`)",
    "fichier qui contient la question telle que l'humain l'a lue":
        "file holding the question as the human read it",
    "la question doit énoncer la décision en une phrase":
        "the question must state the decision in one sentence",
    "le titre cite {ids}, que la question posée ne cite pas : le citer avec son empreinte (`ID@…`, que donne "
    "`socle show`), ou le nommer dans la question":
        "the title cites {ids}, which the question asked does not cite: cite it with its fingerprint (`ID@…`, given "
        "by `socle show`), or name it in the question",
    "refus : {erreur}":
        "refused: {erreur}",
    "refus : « {chemin} » n'existe pas dans le dépôt":
        "refused: “{chemin}” does not exist in the repository",
    "décision en séance consignée par l'agent sans la citer":
        "decision taken in session recorded by the agent without quoting it",
    "!! le projet a déjà son propre état au démarrage ({commandes}) : chaque session reçoit aussi celui du socle, "
    "et les deux se recoupent (branche, commits, ce qui revient à l'humain). Pour n'en garder qu'un, l'humain retire "
    "le sien de .claude/settings.json, ou n'y laisse que ce qui est propre au projet":
        "!! the project already has its own state at startup ({commandes}): every session also receives the "
        "socle's, and the two overlap (branch, commits, what is the human's). To keep only one, the human removes "
        "theirs from .claude/settings.json, or leaves in it only what is the project's own",
    "un chemin qui n'existe que dans une rustine suivie du dépôt passe la CI":
        "a path that only exists in a patch tracked by the repository passes the CI",
    "adaptateur : audit impossible ({erreur})":
        "adapter  : audit impossible ({erreur})",
    "adaptateur : !! langage(s) que l'adaptateur ({couvert}) ne couvre pas : {liste} — leurs tests, leur compilation "
    "et leur mutation ne passent par aucune capacité ; le dire à l'humain par une demande (un autre adaptateur, ou "
    "ces fichiers déclarés tiers)":
        "adapter  : !! language(s) the adapter ({couvert}) does not cover: {liste} — their tests, build and mutation "
        "go through no capability; tell the human through a request (another adapter, or these files declared "
        "third-party)",
    # Les skills (ADR-0034).
    "Un skill se nomme comme son dossier et dit, dans sa description, ce qu'il fait et quand s'en servir ; "
    "`socle-` reste aux skills du socle.":
        "A skill is named after its folder and says, in its description, what it does and when to use it; "
        "`socle-` stays for the socle's skills.",
    "Une commande qu'un skill donne à lancer est jugée comme le hook de l'agent la jugerait : un skill ne fait "
    "pas lancer ce que le hook refuse.":
        "A command a skill gives to run is judged as the agent's hook would judge it: a skill does not make the "
        "agent run what the hook refuses.",
    "skill sans en-tête : le fichier commence par `---`, `name: {dossier}`, `description: <ce qu'il fait, et "
    "quand s'en servir>`, `---`":
        "skill without a header: the file starts with `---`, `name: {dossier}`, `description: <what it does, and "
        "when to use it>`, `---`",
    "le skill se nomme « {nom} » : son nom est celui de son dossier, « {dossier} »":
        "the skill is named “{nom}”: its name is its folder's, “{dossier}”",
    "description trop maigre : ce que fait le skill et quand s'en servir, en au moins {n} mots ; l'agent ne "
    "charge un skill que sur elle":
        "description too thin: what the skill does and when to use it, in at least {n} words; the agent only "
        "loads a skill on it",
    "le préfixe `{prefixe}` est réservé aux skills que pose l'installeur : nommer autrement un skill du projet":
        "the `{prefixe}` prefix is reserved for the skills the installer lays: name a project skill otherwise",
    "le skill donne à lancer une commande que le hook de l'agent refuse — {raison} ; une commande à ne pas "
    "lancer se cite dans le texte, pas dans un bloc de code":
        "the skill gives a command to run that the agent's hook refuses — {raison}; a command not to run is "
        "cited in the text, not in a code block",
    "skills du socle posés dans {dossier} : {noms}":
        "socle skills laid in {dossier}: {noms}",
    "skill dont la description ne dit pas quand s'en servir":
        "skill whose description does not say when to use it",
    "skill qui fait lancer une commande que le hook refuse":
        "skill that makes the agent run a command the hook refuses",
    "un skill du projet bien formé, qui cite dans son texte une commande à ne pas lancer, passe le commit et la CI":
        "a well-formed project skill, which cites in its text a command not to run, passes the commit and the CI",
    # Les plafonds de mutation repris à l'installation (B-0009).
    "des plafonds de mutation déjà mesurés, à reprendre au lieu de poser ces modules « à mesurer » : un fichier "
    "TOML de `[mutation.caps]`":
        "mutation caps already measured, to take over instead of laying these modules “to measure”: a TOML file "
        "of `[mutation.caps]`",
    "{fichier} illisible : {erreur}":
        "{fichier} unreadable: {erreur}",
    "{fichier} n'a aucune table `[mutation.caps]`":
        "{fichier} has no `[mutation.caps]` table",
    "{fichier} : le plafond de « {module} » n'est pas un `max` entier positif ou nul":
        "{fichier}: the cap of “{module}” is not a `max` integer, positive or zero",
    "repris de {source} à l'installation":
        "taken over from {source} at installation",
    "!! plafonds de {source} non repris : les garde-fous existent déjà":
        "!! caps from {source} not taken over: the guardrails already exist",
    "plafonds de mutation repris de {source} : {n}":
        "mutation caps taken over from {source}: {n}",
    "!! plafonds de {source} écartés, faute d'un module de ce nom qui porte du code : {liste}":
        "!! caps from {source} set aside, for want of a module of that name that carries code: {liste}",
    "un correctif dont le test passe sur le parent, admis par une demande validée qui nomme son commit, passe la "
    "CI":
        "a fix whose test passes on the parent, admitted by an approved request that names its commit, passes the CI",
}
