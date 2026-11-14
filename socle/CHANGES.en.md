# Socle release notes

What each change to the socle changes for an installed project, and what the
project's agent must do about it. One entry per change, the most recent
first, under an identifier that never changes: the date of the change and a
letter. On an update, the installer gives the entries that the project's
engine copy did not have, and the commit message it proposes names their
identifiers.

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
