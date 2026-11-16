# Socle release notes

What each change to the socle changes for an installed project, and what the
project's agent must do about it. One entry per change, the most recent
first, under an identifier that never changes: the date of the change and a
letter. On an update, the installer gives the entries that the project's
engine copy did not have, and the commit message it proposes names their
identifiers.

## 2026-11-15-e — The agent's hook refuses deleting the project through rsync --delete, git worktree remove and python -c

The agent's hook refuses deleting the project, or a directory that
contains it, through programs other than `rm`, `mv`, `git clean` and
`find`: the destination of an `rsync --delete` (and its variants,
`--del`, `--delete-after`…), the sources of an `rsync
--remove-source-files`, the path of a `git worktree remove` or a `git
worktree move`, also read the way git looks it up first, by the end of
the path of one of its worktrees (`git worktree remove agent-x`, run in
`.claude/worktrees/agent-x`), and the paths a `python -c` writes out in
full for `shutil.rmtree`, `shutil.move`, `os.rename` or `os.replace`. A
`find -exec` of one of them counts as a `find -exec rm`. Until now,
`rsync -a --delete empty/ ..`, `git worktree remove .` run by a subagent
in its worktree and `python3 -c "import shutil; shutil.rmtree('..')"`
passed.
The orchestrator, at the project root, still removes a subagent's
worktree (`git worktree remove -f -f .claude/worktrees/agent-x`, or
`agent-x`), a subagent another one's, and a directory of the project or
next to it stays free.

To do: nothing. To empty a directory, target a directory of the project,
or outside it a directory that does not contain it, its path written out
in full.

## 2026-11-15-d — The agent's hook judges the body of a function written without parentheses

The agent's hook reads `function name { …; }`, without parentheses, like
`name() { …; }`: each command of its body is judged, whether the body
follows the name on the same line or on the next one, and what it changes
does not carry over to what follows. Until now, the command read had
`function` for its program, and nothing in its body was judged: `function
f { git push --force origin main; }; f` and `function f { rm -rf ..; };
f` passed. Another body that bash accepts (`if`, `while`, `for`, a
subshell) is judged as if it ran where it is written: a directory it
changes becomes unknown after it, and a write into the project that
follows it is refused, as after `name() if …`. A group written at the head
of the subshell that serves as a function's body (`f() ( { cd x; }; … )`)
is no longer read as the body of that function.

Two regressions of this reading are closed in turn. On a call to a
function whose body `{ …; }` changes the directory or a variable, the
hook makes what it changes unknown and judges what follows as an unknown
state: a deletion of the project from the directory such a call leaves
behind (`function f { cd memory; }; f; rm -rf ../../<root>`) is refused,
normal use (`f() { ls; }; f; rm -rf build`) stays free. The call is
resolved when it happens, with what the functions the function calls
change, step by step, including a function defined after it or inside it
(`g() { f; }; f() { cd memory; }; g`); it counts behind `time` and `time
-p`, and in an `eval` or a substitution (`eval f`, `x=$(f; …)`), which
know the command's functions; a `bash -c`, another process, does not
know them. A quoted or escaped reserved word (`"function"`, `\function`,
`$'function'`, and a `}` that closed a body too early) is no longer read
as reserved: bash runs it as a command, and the group or body that
follows is judged as bash runs it in place.

To do: nothing. A force push or a deletion of the project written in such
a function, or let through by its call or by a quoted reserved word,
which the hook let through, is refused. A new refusal, harmless this
time: a write or a deletion through a relative path that follows a call
to a function whose body changes directory (`f() { cd memory; }; f; rm
-rf build`) is refused, as the hook no longer knows where it starts. To
run it, write its absolute path in full, or do the `cd` outside the
function (`cd memory; rm -rf build`).

## 2026-11-15-c — The review sorts out exotic findings, and its reviewer receives the most capable model

A review finding that does not block goes to the backlog if it can occur
in the project's normal use, or if nothing catches its effect afterwards;
an exotic finding whose effect is caught (by a check, the CI or an error
the agent sees at once), or an unfounded finding, is dismissed, and the
recap says why. The reviewer's instruction
(`python3 .socle/socle review`) says so, and has it return three lists,
"Blocking", "For the backlog" then "Dismissed". Under Claude Code, the reviewer receives
explicitly, at launch, the most capable model available up to Opus, never
a lesser one than the one that implemented the batch, whatever the
session's; Fable only if the human asks for it. A guardrail's threat
model is written in the topic's section or in the decision it cites. The
socle section of AGENTS.md changes (the sorting rule, a tightened text),
as do the `socle-review` skill, a protected copy, and the `HELP.md` guide.

To do: nothing, except following the sorting at the next review.

## 2026-11-15-b — The review brief measures the batch since the common ancestor, and refuses an unknown reference

`python3 .socle/socle review` measures the batch since the common
ancestor of HEAD and its base: the default branch that moved on, or a
commit pushed from elsewhere to the remote branch, no longer enter the
diff or the topics. Only the topics whose status or "Done when" the batch
changes make the reviewer's bar; a changed `after`, an added finding or a
closed topic filed away by `socle archive` are no longer there. An
unknown `--base` or `--since`, a `--since` that is not an ancestor of
HEAD, a base with no common ancestor with HEAD are refused (code 2),
instead of an empty brief. The brief says what the remote branch already
carries of the batch, over how many commits it measures a batch already
pushed, and the real reason for an empty brief (default branch guessed,
shallow clone); under `--since`, the command it proposes keeps `--since`.
After a squash merge, a branch restarted from the default branch no
longer brings the merged batch back into the review of the next one.
The `socle-review` skill, a protected copy, changes.

To do: a batch already pushed in whole or in part, or on a branch that
carries batches already reviewed, is reviewed with `python3 .socle/socle
review --base <the commit before the batch>`.

## 2026-11-15-a — The socle-batch skill says when to compact and which model for which work

The "Consumption" section of the `socle-batch` skill has two more rules.
The agent does not compact by itself: it writes the memory (active work,
journal), then asks the human to compact, at the end of a batch if the
human keeps the session beyond it, and before any wait that may exceed an
hour without changing sessions; near a limit, the threshold that changes
sessions prevails; after the pause, compacting rereads the whole
conversation at full price. The model is the one the quality of the work
calls for, never a lesser one to stay within a limit: a limit delays a
batch, it does not lighten it. Among those that do it equally well, the
one that uses the least of the limit per token, above all for the
orchestrating conversation; the human chooses the session's, on the
agent's advice; the model set by the project's instructions prevails, and
a subagent receives its own explicitly at launch.

To do: the skill is in the request for the update's protected files; once
it is in place, ask for compaction at the moments it gives, advise the
human on the session's model, and name the model of each subagent at
launch.

## 2026-11-14-k — The agent's hook sees what cp -t, find -delete, xargs, bash -ec, sort -o and python -c write

The agent's hook now judges these writes to a protected file: `cp`, `ln`,
`install` and `mv` write the directory of `-t`, `sort` the file of `-o`;
`bash -ec '…'`, `bash -lc '…'` and `bash -c -- '…'` open their command;
`find -delete`, or `find -exec rm {} +`, is judged by its starting points
and the name or path filters that guard its action, at any depth: `find .
-name '*.pyc' -delete` passes, `find . -name '*.toml' -delete` is refused.
A filter guards only the action that follows it, outside a `!` and the
other branch of a `-o`; the `*` of a `-path` crosses directories, as in
`find`. `python -c` and `xargs` of a writer, which the hook cannot read,
are judged by the protected paths they cite in full: `echo <protected
file> | xargs rm` is refused, as is a `python -c` that cites a protected
file, even to read it.

To do: read a protected file with `cat` or the file-reading tool, rather
than with a `python -c` that cites it, which the hook now refuses; it also
refuses a `python -c` that cites a directory containing a protected file,
even to list it (`os.listdir('.socle')`): list it with `ls`. The hook
likewise refuses a `find` that deletes or writes what it finds from the
root without a name or path filter, even with `-type` or `-empty` (`find .
-type d -empty -delete`, `find . -type f -exec sed -i … {} +`): give it a
name or path filter, or start it from a directory of the project.

## 2026-11-14-j — The agent's hook no longer loses the command after a hash or nested quotes

The agent's hook reads a `#` as the shell does: it opens a comment only at
the start of a word, and the comment stops at the end of its line. A `#` in
the middle of a word (`x#`, `$#`, an address) no longer loses the command
that follows, nor does an end-of-line comment lose the one on the next line.
A substitution between quotes whose argument has its own quotes (`"$(cmd
"arg")"`) is also read as the shell reads it: the command that follows it is
judged. What the substitution itself runs is still not judged.

To do: nothing.

## 2026-11-14-i — The agent's hook reads conditions and loops

The agent's hook now judges a command written behind a shell reserved word
(`then`, `else`, `elif`, `do`, `!`, `{`, `if`, `while`, `until`): a write to
a protected file, an irreversible action or a command reserved for the human
in the body of a condition or a loop no longer passes, as outside it. What a
condition or a loop changes, its directory and its variables, becomes
unknown after it, except a directory it comes back to (`for d in */; do cd
"$d"; …; cd ..; done`) without a `break` or a `continue` having left it
elsewhere; the body of a `for` is judged once per word of its list, its
variable bound to that word, so that `for d in .socle memory; do cd $d; …;
done` is judged in each of the two directories, and `for f in *.md; do sed
-i … "$f"; done` by its pattern. The body of a function (`f() { …; }`) is judged, but what it
changes does not hold for what follows: it does not run where it is
written.

To do: nothing, unless the hook now refuses a loop that writes to a variable
it does not know (`while read f; do sed -i … "$f"; done`): write the list of
files out in full, in a `for`, or handle them with the file-writing tool.
Nested `for` loops of several thousand iterations, which it does not
unfold, have the same unknown variable: split them into shorter commands.

## 2026-11-14-h — The agent's hook reads the file a command publishes from its current directory

To judge a leak of the private memory, the agent's hook reads the file a
command publishes (`git commit -F`, `gh … --body-file`, `gh api -F
field=@x`). It read a relative path from the project's root, whatever the
agent's current directory: after a `cd docs`, `git commit -F message.txt`
made it read the root's `message.txt`, not the one git publishes. It now
reads it from the agent's current directory, like the paths a command
writes.

To do: nothing.

## 2026-11-14-g — The agent's hook refuses deleting a directory that contains the project

The agent's hook let through `rm -rf ..` run from the root, and deleting a
directory that contains it (the user's directory, the one that holds a
subagent's worktrees): it would take away the code, the memory, the policy
and the hooks, and no check catches it afterwards. It now refuses deleting
such a directory through the arguments of `rm`, the sources of an `mv`,
what `git clean` sweeps and the starting points of a `find` that deletes
(`-delete`, `-exec rm`), its path expanded like any path the hook judges;
and deleting the project by a `find` that starts from its root with no
name or path filter guarding what it deletes (`find . -delete`, `find .
-type f -delete`, `find . -delete -name '*.pyc'`, whose filter comes after
the action, or `find . -path ./.git -prune -o -delete`). A directory next
to the project, a directory of the project (`find build -delete`) and a
`find` that filters what it deletes under the root stay free.

To do: nothing. Such a refusal is lifted by targeting a directory of the
project, or outside it a directory that does not contain it, written out
in full.

## 2026-11-14-f — The threat model of the agent's hook

The guide now says what the agent's hook stops: the mistakes of a
cooperative agent, before they take effect. It judges the shell forms an
agent writes in its work, and, whatever its form, what nothing catches
afterwards: deleting the project or a directory that contains it, an
irreversible external action, a leak of the private memory into what gets
published. A write to a protected file in a form one writes only to get
around it (an `eval`, `IFS`, a path built on the fly in another language)
is outside its model: the `protege.fichiers` check refuses it afterwards.
The hook itself does not change. Deleting the project still escapes it
when a program other than `rm`, `mv`, `git clean` or `find` does it
(`rsync --delete`, `git worktree remove`, a `python3 -c` that calls
`shutil.rmtree`, `xargs rm`): nothing catches it.

To do: a hole of the hook of that last kind, found by a review, opens no
backlog subject; a hole through which passes what nothing catches opens
one, whatever its form.

## 2026-11-14-e — The socle-batch skill leads a batch

A new socle skill, `socle-batch`, put in place and protected like the others
under `.claude/skills/`, says how to lead a batch from forming it to
delivering it: announcing it, one subagent per subject, the context-free
review before any push, integration, CI and merge, one session per batch,
the consumption thresholds beyond which the session wraps up, and the change
of session with the next one's prompt. After the merge, nothing is pushed
without new work. An agent without subagents leads the batch alone.

To do: the skill is in the request for the update's protected files; a
project procedure that already led its batches keeps only what is its own.

## 2026-11-14-d — A batch is kept in the backlog

A batch, the subjects led together because they touch the same files, the
same guardrail or the same tests and one review judges them, is now kept in
the backlog: a subject marked `form: batch`, whose `after` names its
subjects and the batch before it. The state shows the next batch beside the
next milestone, with what remains of it and where each of its subjects
stands. A batch is never a ready subject, and it does not close before its
subjects.

To do: record as a batch the subjects planned to be led together, instead of
writing them only in the active work; close the batch when its subjects are
closed.

## 2026-11-14-c — The release notes

This file exists. An update that copies the engine prints, between what it
put in place and the audit, the entries that the replaced copy did not have;
a copy that had none receives them all, including those that describe what
the project already has. The commit message that "What now" proposes names
their identifiers in a second paragraph, for the next session.

To do: read each entry given and do what it asks; keep that second paragraph
in the update's commit. A session that finds an update it did not run reads
the entries that this commit names.

## 2026-11-14-b — The end of turn states the update in one line

Between the installation and the push of its request, the end of turn no
longer lists each protected file that the update put in place, with its
restore command: a single line, "a socle update is waiting for its request: open it",
with their number and the command that lists them with their fingerprints
(`python3 .socle/socle check --stage agent --only protege.fichiers`). The
engine lock now names, under `[installed]`, those that the installer put in
place outside the engine, with their fingerprint: that is how the end of
turn recognises them.

To do: do not restore these files, open the request. A protected file
changed before or after the installer's run keeps its line and its restore
command.

## 2026-11-14-a — A human answer is recorded at once, and leaves with what it authorises

An answer given in the conversation is recorded in the tree right away
(`python3 .socle/socle answer D-NNNN approve --relayed …`): the state reads
the tree and no longer says it is pending. It is committed and pushed with
the change it authorises (an expected value, a guardrails key, a protected
file), in the same push, never before: the CI of a push only counts the
validations in its range. Only a protected file may precede it, pushed under
the pending request. A new check, `demandes.reponse-seule`, warns when the
answer would leave alone: in `verify --fast`, at commit and before the push.
The `socle-request` skill, a protected copy, says so.

To do: record each answer as soon as it is given, and push it with what it
authorises. Pushed alone, it does not cover the change that follows it:
record it a second time then.

## 2026-11-13-c — The review judges a batch against its topics

The file of `python3 .socle/socle review` gives the reviewer the “Done
when” of each topic the batch touches, even open, and the titles of those it
opens; the reviewer classifies each finding, blocking (a ticked criterion or
a decision contradicted, a regression, a data loss, a bypass of a guardrail
within its threat model) or for the backlog. The `socle-review` skill, a
protected copy, changes.

To do: fix the blocking findings in the batch and put the others in the
backlog; a second review only if the fix is heavy, on it alone
(`python3 .socle/socle review --since <reviewed commit>`). A topic that sets
or changes a guardrail writes, before its code, a "## Threat model" section
(what it stops, what it lets through); a topic whose design is not settled,
its specification.

## 2026-11-13-b — The agent hook expands paths as the shell does

The hook judges a path that a shell command writes as the shell would
expand it: variables, patterns (`*`, `?`), braces, `~`, `cd` and `pushd`
followed, paths relative to the current directory. What it cannot expand (an
unknown variable, `$(…)`, a `cd` to such a path) is refused if it may land in
the project. Known false refusals: `$(mktemp -d)` or
`$(git rev-parse --show-toplevel)` kept in a variable or taken as the target
of a `cd`, a `for` loop over a written list.

To do: on a refusal, write the path out in full, or assign the variable
earlier in the same command (`F=/tmp/x; echo y > "$F"`). The hook is only a
first barrier: the `protege.fichiers` check remains the guarantee.

## 2026-11-13-a — The startup output is bounded

The startup hook's output went beyond what Claude Code hands over whole, and
the agent only received a preview of it. It now fits under
`[startup] max_bytes` of the guardrails (9,500 bytes): first what calls for
action, then the state, the active work in full, the facts by their title
and the last ten decisions. A part that exceeds its share loses whole lines,
and a last “!! cut” line says what is missing and where to read it. The
active work's budget goes down to 3,700 bytes, public and private together.

To do: read at once what a “!! cut” line says is missing
(`python3 .socle/socle state --short` for the whole state,
`python3 .socle/socle show <ID>` for an entry). If the installer says the
budget of `memory/active.md` is above its share, lower it to the value it
gives (tightening is free), then shorten the active work, what comes out of
it going to the journal.

## 2026-11-12-a — Adoption only tolerates the findings already present

In an adopted project, a check under `[adoption] warn_only` no longer turns
into a warning as a whole: only the findings recorded under
`[adoption.tolerated]` of the guardrails do, and any new finding fails. On
an update, the installer records there the base's findings still present,
and says so. A renamed file keeps its findings if its key is renamed in the
same pull request.

To do: read what the installer says about the list; fix a new finding
instead of adding it, since adding loosens and awaits a validated request;
remove a finding that has gone, which is free; rename a renamed file's key in
the pull request that renames it.

## 2026-11-11-b — The agent may restore a protected file to its last commit

The agent hook lets through `git restore --source=HEAD -- <file>` and
`git checkout HEAD -- <file>`, each path written out in full, and
`rm <file>` for a file that appeared under a protected path that git does
not track. Claude Code's settings remain excluded, and a file cited by a
request whose approval is not committed is spared.

To do: nothing; this is the form that the write refusal and the
`protege.fichiers` error give, to undo a change made by mistake.

## 2026-11-11-a — The hook refuses the installer outside the lock's mode

The agent hook refuses `socle install` on an equipped project in another
mode than its lock's, and a target it cannot resolve (a variable, `$(…)`,
`~other`, in the target or in the `cd` before it). The command line refuses
abbreviated options.

To do: run the update in the lock's mode, the target written out in full
(`--target .`); changing a project's mode is up to the human.

## 2026-11-10-b — The update approved by a request

The installer returns 0 when the installation succeeded and only the
approval of the protected files is pending. In a cloud session, the request
that approves them is opened with `python3 .socle/socle new request
"<decision>"`, which prints its contract; each protected file is written on
its own line, its path and its fingerprint and nothing else, and these lines
do not count in the request's budget. The pre-commit hook refuses a
reference that the commit does not contain.

To do: follow "What now" in its order: the request alone first, pushed, then
the protected files with what cites them (journal, active work).

## 2026-11-10-a — Disposable branches

A branch whose name starts with a prefix of `[branches] disposable` in the
guardrails, `proto/` by default, is not judged by the CI on each push; its
pull request judges it whole, and the default branch's protection blocks the
merge while the CI is red. The CI workflow, a protected file, changes on the
update.

To do: nothing. A trial that should not be judged on each push goes on a
`proto/…` branch; adding a prefix loosens, and awaits a validated request.

## 2026-11-09-a — The reading fingerprint no longer covers the metadata

The fingerprint of a memory entry (`ID@xxxxxxxx`, which
`python3 .socle/socle show` prints) covers its title and body, without the
`>` lines that follow the title: changing a status no longer outdates a
citation. All fingerprints therefore change with this version; a citation
written before remains accepted as long as it matches. A citation no longer
proves that a status was read.

To do: read an entry again (`python3 .socle/socle show <ID>`) before citing
it anew, to take its fingerprint; do not rewrite the old citations. Read the
status in the index (`python3 .socle/socle show --index decisions`, or
`backlog`).
