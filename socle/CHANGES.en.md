# Socle release notes

What each change to the socle changes for an installed project, and what the
project's agent must do about it. One entry per change, the most recent
first, under an identifier that never changes: the date of the change and a
letter. On an update, the installer gives the entries that the project's
engine copy did not have, and the commit message it proposes names their
identifiers.

Each entry says, in a paragraph that starts with “To do:”, what the
project's agent must do. When it has nothing to do, that paragraph is
written “To do: nothing.”, or “To do: nothing;” followed by a detail that
asks nothing: of such an entry, the installer prints only the title,
under a line that names this file. Any other form (“nothing, unless …”,
“nothing in the project …”, an action) is printed in full, before them.

## 2026-11-23-a — Without list_events, the resumption reads in the local transcript whether a limit cut the session off

The `socle-resume` skill gives the wake-up one more source when the
session lacks the `list_events` tool: the transcript Claude Code keeps
for the project, the most recent `.jsonl` of its folder under
`~/.claude/projects/`. The previous turn ended on a limit if a record
carrying `quotaLimits`, the refusal, closes it; its timestamp is the time
of the cut, which the recap gives instead of "an unknown time", and the
messages the human typed since are the ones that follow it. Without a
transcript, the conversation alone decides, as before.

To do: nothing; the `socle-resume` skill is a protected copy, in the
installer's request.

## 2026-11-22-j — The cold reader of a request answers in a single message, with no tool

The `socle-request` skill bounds what the cold reader of a request does:
its only message is still the brief of `socle review --request`, and it
returns its reading in a single message, launching no tool. Measured
this way, a reading reads nothing of the project outside its brief and
costs only the fixed price of a subagent, its brief and its answer,
about a third of a batch reviewer. A subagent report that counts a tool
launched means a reading that was not cold, and the recap says so.

To do: nothing; the `socle-request` skill is a protected copy, in the
installer's request.

## 2026-11-22-i — A command says what a Claude Code session cost, and what made it cost

`python3 .socle/socle consumption` reads the transcripts Claude Code
keeps for the project, or those of a folder given as an argument, and
prints in Markdown what the session cost, by day and by model, the main
conversation and the subagents apart, and what made it cost: the size of
the context read again at each call, the resumptions after a pause, the
compactions, and what the socle injects into the conversation. The cost
is weighted at the public price, an assumption that options change;
readings of the five-hour window (`--point`) say what a point of the
usage limit is worth. The report carries only aggregates, never a text
of the conversation. The guide says when to use it.

To do: nothing, except when the human asks what a session cost, or why a
usage limit fell so early: run `python3 .socle/socle consumption` and
give them its output.

## 2026-11-22-h — In a cloud session, a failed fetch of the clone's history is no longer paid again on each resume

In a cloud session, the startup hook completes a shallow clone
(`git fetch --unshallow`) in 120 seconds at most. A fetch that hung took
them again at each start of the same container, a resume or a
compaction. A failure, timed out or a non-zero code, is now marked next
to the hooks' trace: the next start of the same container retries the
history for 15 seconds only, and the `!!` line gives, as before, the
command to run again by hand before committing. The adapter's tools get
the rest of the startup delay, 270 seconds in all: at least 140 on the
first start, 245 on a resume.

To do: nothing.

## 2026-11-22-g — The guide says how to import a journal numbered like the socle's

A project that already kept a journal whose entries have the form of
the socle's (`J-`, a date and a letter) knew neither which letters its
imported entries take, nor how to cite the old ones before their
migration, which the references check says do not exist. The guide now
says so, in its reference, after the adopted project: an imported entry
keeps its identifier, except on a day the socle's journal already has,
where it takes the letters that follow the socle's own, its citations
rewritten in the same commit, except in the journal, the decisions and
the requests, where the migration's entry gives the mapping; before the
migration, a new citation names the entry by its file, its date and its
letter: on a day that clashes, its identifier would silently designate
the socle's entry.

To do: nothing, unless the project kept such a journal: propose its
migration to the human, following the guide (“A journal from before the
socle”).

## 2026-11-22-f — The guide says that a box delivering a request, a report or a memory entry is checked by what it produces

The memory format and the reviewer's instructions already said so: a
box of a task's “Done when” whose deliverable is a request posed, a
report written or a memory entry rewritten is checked by what it
produces, which the box names, not by a test. The human's guide still
said that every “Done when” is checked by a test; it now states the
exception.

To do: nothing.

## 2026-11-22-e — The installer no longer shows again in full a policy difference already shown

On every update, the installer showed in full what separates the
project's policy from the template of this version, even when the
difference was made only of lines the human wrote there on purpose,
already shown at the previous update. It now also compares the policy
with the template of the engine copy of the last commit: if each
changed line of the difference was already there, a single line says
so, with their number and the command that shows it in full; otherwise,
or without a committed copy, the difference is shown in full, as before.

To do: a difference shown in full holds at least one line that the
template of this version changes: show it to the human, who alone writes
the policy.

## 2026-11-22-d — The installer says in one line that an empty adoption has nothing to enter

An adoption that found no failing check, or an update of an adopted
project whose `[adoption] warn_only` list was empty, said nothing of the
adoption: knowing there was nothing to enter took a dry run. The
installer now says so in one line: “adoption: no check in `[adoption]
warn_only`, no finding to tolerate: nothing to enter”. A project never
adopted gets none.

To do: nothing.

## 2026-11-22-c — The settings merge keeps the project's command placed in a block of the socle

On install as on every update, the installer replaces the socle's hooks
in `.claude/settings.json` and keeps the project's. Yet it removed any
hooks block that carried a command of the socle, and with it a command
of the project placed in the same block (a `bash tools/lint.sh` next to
the socle's `Stop` hook, for instance), without saying so. It now
removes from a block only the socle's commands, keeps the block if any
are left, and names the kept command like a hook of the project in its
own block. Run again, it duplicates nothing.

To do: if a command of the project has vanished from
`.claude/settings.json` at a previous update, tell the human: only they
put it back, the file being protected.

## 2026-11-22-b — The installer names the named adapter that the copy of its language replaces

An adapter named by `--adapter`, a file or a maintained adapter, of the
language of a copy already in `.socle/adapters/` becomes that copy,
which the update refreshes or keeps: it is not set. The installer did
not say so, and its log named only the copy. It now says so with a `!!`
line, of the form of the main copy's: the adapter set aside, the copy
kept, and how to replace it. An adapter detected automatically becomes
the copy without the installer saying more.

To do: if the installer says that a named adapter is not set, tell the
human: the copy kept remains the project's, and replacing it is done as
the line says, through a request on an equipped project.

## 2026-11-22-a — On an update, the installer prints in full only the release notes that ask something

On every update, the installer printed in full each release note that
the project's engine copy did not have, even those that ask nothing:
often more than half of what it printed. It now prints in full, first,
only those whose “To do” asks something; of the others, whose “To do”
is “nothing.”, or “nothing;” followed by a detail, one line each, their
title, under a line that says how many they are and the file to read
them in. Any other form, “nothing, unless …” included, is printed in
full. The commit message it proposes still names all the entries.

To do: read the notes the installer prints in full, and do what each
one asks; a note it names only by its title asks nothing, and is read
in the file it names when it matters.

## 2026-11-21-d — The installer names the end-of-turn hook the project already has

The installer keeps the hooks the project declares itself in
`.claude/settings.json`, next to the socle's, and already pointed out a
start-up state of the project's own. It said nothing of a `Stop` hook of
the project's own: that hook fires at every end of turn next to the
socle's, and, if it runs the same checks, every end of turn pays for
them twice. On install as on update, the installer now names it, with a
line that says it may duplicate the socle's.

To do: if the installer names an end-of-turn hook of the project, tell
the human: only they remove it from `.claude/settings.json`, or leave in
it only what is the project's own, if the socle's hook already does the
rest.

## 2026-11-21-c — “What now” no longer has an update's protected files committed before its request

In a cloud session, an update that changes protected files told the
session that had to add the socle's repository to commit there, push
the branch and open the pull request, the request being put afterwards
in a new session. Yet the pre-commit hook refuses a changed protected
file that no pending request covers: that session could not do what it
was told. It now commits the protected files there only after putting
the request there, in two steps like any session, when the default
branch requires the socle CI; otherwise, it commits nothing there, and
the update is redone in a new session on the project's repository
alone, the socle's repository cloned without being added to it.

To do: nothing.

## 2026-11-21-b — An update no longer lays down a second adapter for the language of a copy already there

A project in which Python is a language besides the main one has its
copy `.socle/adapters/python.toml`. When a `conftest.py` appeared in
it, an update with `--adapter auto` detected `python-pytest` and laid
down its copy next to it: two adapters for the same language, whose
patterns overlap, which the `adaptateur.recouvrement` check then
refused. The installer compared the language of a detected or named
adapter with that of the main adapter only; it now also compares it
with that of each copy already laid down, and an adapter for that
language is that copy, which it refreshes or keeps as before.

To do: nothing, unless an earlier update laid down in
`.socle/adapters/` a second adapter for the language of a copy already
there (`adaptateur.recouvrement` failing): then propose to the human,
through a request, to remove whichever of the two the project did not
choose.

## 2026-11-21-a — Run again before an update is committed, the installer still names its release notes

The installer read the release notes already seen in the engine copy of
the working tree. Run again before the update was committed (after
`git fetch --unshallow`, or to correct `--adapter`), it found the new
copy there already and saw no new notes: the commit message it
proposes, like the step that opens the agent, no longer named them. It
now reads them in the engine copy of the last commit; in the working
tree only when the repository has no commit, or the last one has no
engine copy.

To do: nothing.

## 2026-11-20-r — The `socle-batch` skill has the agent wait, after a merge by the agent, for the workflows it starts

A merge into the default branch may start a deployment or a release; if
it failed, nothing said so, and the agent moved on to the next batch.
The merge step of the `socle-batch` skill now says it: the agent that
merges its own pull request, when the policy allows it, then waits for
the workflows the merge starts on the default branch, as it waits for
the CI, and its recap says whether they succeeded. Who merges, the step
reads in the policy, no longer in the project's instructions.

To do: nothing; the `socle-batch` skill is a protected copy, in the
installer's request.

## 2026-11-20-q — Merging its own pull request by the agent, a policy option the human enables

The hook refuses the agent the merge of a pull request, like the other
external actions. The policy the installer lays down now carries as a
comment, in its `[irreversible]` section, the `tools` line that allows
it: the engine's list of external tools, minus the merge. Only the human
enables it, by uncommenting it; the guide (“Merging by the agent”) gives
the conditions under which the agent then merges its own pull request,
and what it checks afterwards. The hook does not change: without the
line, the merge stays refused. An installed project's policy is not
rewritten; on this update, the diff of the policy shows the line.

To do: nothing, unless the human wants the agent to merge its own pull
request. They then write this line themselves in the `[irreversible]`
section of `.socle/policy.toml`, and approve it like any protected
change; the agent does not write it, it can give it to them:

```toml
tools = ['mcp__github__(delete_file|create_repository|fork_repository|create_release|push_files|create_or_update_file|enable_pr_auto_merge)']
```

A project that has already written this line has nothing to do.

## 2026-11-20-p — Deleting the remote branch no longer resets the range of a push

The pre-push hook judges the outgoing range from the remote commit; a
branch absent on the remote was judged against the default branch, where
a test that only the branch added has no earlier value. Deleting the
remote branch thus let what had been pushed to it be rewritten. When it
lets a push through, the hook now keeps the commit pushed to each remote
reference, in `.git/socle/pushed.json` (the git common directory of the
worktrees, not versioned); a vanished remote branch whose commit is not
in the default branch is judged from it, and the refusal says that
deleting the branch is not a way out. A branch merged by a merge commit,
restarted from the default branch under the same name, is judged as a new
branch; after a squash or rebase merge, the kept commit stays outside the
default branch, and the branch restarted under the same name is judged
from it: stricter, never looser; the way out is another branch name. A
clone that has pushed nothing since the update is judged as before.

To do: nothing.

## 2026-11-20-o — The review folder of a branch that merged the default branch shows only the batch

An already pushed branch that merged the default branch during a batch
gave the reviewer, along with the batch, the code and the closed entries
the merge brought. `socle review` now measures the batch's diff and
subjects from the merge redone on its start (`git merge-tree
--write-tree`, git 2.38), and a note says so; so does the diff of a
second review (`--since`), whose messages keep only the branch's
commits. A merge that cannot be
redone without conflict, or an older git, leaves the folder as before,
and the note says it also shows what the merge brought.

To do: nothing.

## 2026-11-20-n — The CI summary of a pull request links a request posed on its branch

On a pull request, the CI runs on a detached HEAD, the merge commit
GitHub prepares; a request's link pointed there to the default branch,
which does not have a request posed on the branch yet: the run summary
(`socle roadmap --format markdown`) gave it without a link. When
`GITHUB_HEAD_REF` is set, the link now points, for the repository the
CI checked out (`GITHUB_WORKSPACE`), to the head of the pull request, the second parent of the merge commit.

To do: nothing.

## 2026-11-20-m — `socle renumber` repairs a collision born of a rebase

After a rebase or a cherry-pick, two entries carried the same
identifier: `socle renumber` refused ("existed before the branch"), or
renumbered both, along with the mentions of the one already there. It
now renumbers the one the branch adds, the one missing from the base or
from the last pushed commit, and changes only the lines the branch
added: the other entry and its mentions stay as they are.

To do: nothing.

## 2026-11-20-l — `socle new` does not reuse an identifier that a tracked patch of the repository creates

A handover stores the commits not yet reviewed as patches (`git
format-patch`); an entry written before they were applied took the
number of an entry they create, and the applied patch defined it twice.
Computing an identifier (`socle new`, a request, `socle
renumber`) now skips the entry titles that a tracked patch of the
repository (`*.patch`, `*.diff`) adds to a memory file.

To do: nothing.

## 2026-11-20-k — A title that ends with a hash attached to a word keeps it

The memory reader stripped every trailing hash from a title: an entry
titled "… in a C# project" ended "… in a C" once read. Only a closing
sequence preceded by a space (`## Title ##`) is now stripped, as in
Markdown. Entry fingerprints do not change: they are computed on the raw
text; an index fingerprint changes if one of its titles ends that way.

To do: nothing; an index citation this change makes stale is refused
with the command that rereads it.

## 2026-11-20-j — A shell form the hook does not judge is no longer listed or reported: the guide keeps the hook's threat model

The `socle-review` skill, the reviewer's instructions of `socle review`
and the socle section of `AGENTS.md` no longer mention the shell form an
agent does not write: the review does not look for one, and a form found
is dismissed like any exotic finding, with no recap line naming it and
no report to the socle's repository. The guide (`python3 .socle/socle
help`) loses the list of known forms the hook does not judge and the
sentences that said when a hole in the hook opens a backlog entry; it
keeps what the hook judges, what it refuses for not being able to read
it, and what it does not model, which the protected-files check catches.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request, and the socle section of `AGENTS.md` is regenerated
with the update. A form already named in a recap is not reported.

## 2026-11-20-i — The `socle-review` skill has the human asked whether they want Fable for the reviewer of a batch implemented on Fable

A batch the human had implemented on Fable (the batch, not the
orchestrating session): the agent asks them, before the review, whether
they also want Fable for the reviewer. Outside this case, the rule does
not change: the most capable model up to Opus, never a lesser one than
the one that implemented, and Fable only if the human asks for it.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-20-h — The `socle-batch` skill places the wake-up in a cloud session, forms as a milestone what one session does not carry through, refers to the sorting of `socle-review` and gives subagents the “Economy” line

The `socle-batch` skill changes in five points:

- an announced wait has its wake-up in a cloud session (`send_later`),
  the only place where the tool exists; elsewhere, the recap's `Next:`
  line says it, and the human restarts the agent;
- a whole that one session does not carry through is formed as a
  milestone, its batches under it;
- the review's findings that do not block follow the sorting of
  `socle-review`, to the backlog or set aside, instead of all going to
  the backlog;
- the subagents' instructions carry the line “Economy: read what serves,
  not whole files; no full suite rerun without reason”;
- a subagent never receives Fable, unless the human wants it.

To do: nothing; the `socle-batch` skill is a protected copy, in the
installer's request.

## 2026-11-20-g — A test changed under its pending request is committed and pushed, the socle's CI required

A deleted test, or one whose expected value changes, or a case of a
declared case file, that a pending request names did not leave the
agent's working tree: `tests.attendus` tolerated it only at the end of
the turn. It is now tolerated like a protected file under its pending
request: if the default branch requires the socle's CI before any merge,
it is committed and pushed as soon as the request that names it is
pushed as is, and the CI refuses it until the human's answer, who reads
it in the pull request. Without that protection, nothing changes: the
commit and the CI wait for the answer. A commit without a pushed request
is still refused.

To do: nothing.

## 2026-11-20-f — A request's cold reader receives the most capable model up to Opus, at launch

The `socle-request` skill had a request read cold by a subagent of the
session's model, which the model rule of `socle-batch` may make cheaper.
Like a batch's reviewer, it now receives explicitly at launch (`model`)
the most capable model available up to Opus, whatever the session's, on
the latest version of its family; Fable only if the human asks for it.
The recap names the model: `Cold reading (<model>): …`.

To do: nothing; the `socle-request` skill is a protected copy, in the
installer's request.

## 2026-11-20-e — `socle decision --unprompted` records a decision the human gives without being asked

`socle decision` required a base answer or an option named by the
question: a decision the human gave of their own accord was recorded
under `approve`, with an invented "question asked". `socle decision "<the
decision in one sentence>" --unprompted --relayed --by <name> --quote-file
<file>` writes it with no question and no answer to choose: their exact
text under the `Decision given` section, and the `approve` answer that the
engine sets, their text quoted. It authorizes what it names as an approved
request does. The title does not cite on its own an identifier the
human's text does not cite. The `socle-request` skill and the guide say
so.

To do: nothing; the `socle-request` skill is a protected copy, in the
installer's request.

## 2026-11-20-d — The state and the end-of-turn reminder warn about an open batch that waits for more tasks than one session carries

An open batch that still waits for more open, in-progress or blocked
tasks than `[batches] max_tasks` of the guardrails, 9 by default, is
reported in the state, with what calls for action, and in the
end-of-turn reminder, under the backlog order: one line names each
batch and its count, and says to cut it into batches, or to make it a
milestone with its batches under it. A warning, never a failure. The
threshold is set like `[verify] fast_max_seconds`: lowering it is free,
raising it requires a validated request.

To do: nothing, unless the state reports a batch: cut it at its next
announcement. The key, which the installer names on update, can be
declared in `.socle/guardrails.toml` if needed.
## 2026-11-20-c — The step back is no longer required: `socle review` writes a batch's passes and the backlog check lets it close without one

`socle review` writes each pass of a batch in its “Reviews” section
without requiring the previous one's step back: no “Step back:”
paragraph, no reviewer's view on the blockers (`· same cause`, `· new
cause`), no stop on a request that cites the batch. The
`memoire.backlog` check lets a reviewed batch close `done` without a
step back. The brief of a pass beyond the first is that of any pass: it
no longer gives the reviewer the causes of the earlier passes. The
“Reviews” section keeps its passes, their commits and their `- Blocker:`
and `- Opens:` lines; a blocker line written in another form is still
refused. A step back and cause marks already written stay in the batch,
read as text. The `socle-review` and `socle-batch` skills and the guide
no longer mention the step back.

To do: nothing; the `socle-review` and `socle-batch` skills are
protected copies, in the installer's request. A batch stopped on a
request only waits for it if its `after` names it.

## 2026-11-20-b — The installer has git ignore the subagents' worktrees

The `socle-batch` skill launches its subagents in worktrees, which Claude
Code lays down under `.claude/worktrees/`; not ignored, they show in `git
status` as files to commit. The installer adds `/.claude/worktrees/` to
the project's `.gitignore`, under a comment that says so, unless a line
already ignores it, or `.claude/`.

To do: nothing; the line comes with the update, to commit with it.

## 2026-11-20-a — The agent's hook lets a protected file be restored when a request cites its folder only in a copied text

The agent's hook refused to put back as it was at the last commit a
protected file that no request approves, when a pending request, or an
approved one whose answer is not committed, cited its folder in a text
copied between backticks: an expected value of a test, an output line
(`skills du socle posés dans .claude/skills : …`). A folder that is only
one word of such a text, between backticks or in a code block, is no
longer a citation there. The file named in full, and its folder cited in
the prose or alone between its backticks (`.claude/skills/`), still
spare it.

To do: nothing.

## 2026-11-19-t — The agent's hook reads the current branch in `git push origin "$(git branch --show-current)"`

The agent's hook expands three substitutions of a `git push` into the
current branch, `$(git branch --show-current)`, `$(git rev-parse
--abbrev-ref HEAD)` and `$(git symbolic-ref --short HEAD)`, bare, quoted,
in backticks or through a variable (`B=$(git branch --show-current); git
push -u origin "$B"`), and judges the push as if the branch were written
out in full: it passes from a working branch, and it is refused from the
default branch. They were refused, like any argument it cannot expand.
When the same command changes directory, repository or branch before the
push (`cd` elsewhere, `git -C`, `git checkout`, `git switch`), or for any
other substitution (`$(echo main)`), the push stays refused.

To do: nothing.

## 2026-11-19-s — The agent's hook judges the filters of a `find` by their conjunction, and its `-path` under its starting points

The agent's hook judges the expression of a `find` that deletes or
writes what it finds by the conjunction of its filters: a protected file
is targeted only if it answers each filter of one conjunction, and the
pattern of a `-path` targets only what lies under the `find`'s starting
points. `find . -name '*.json' -path './build/*' -delete` and `find
build -path '*.toml' -delete` pass; they were refused, each filter
judged alone, and the leading star of a `-path` read from the project's
root. What a conjunction reaches stays refused (`find . -name '*.json'
-path './.claude/*' -delete`, `find . -path '*.toml' -delete`).

To do: nothing.

## 2026-11-19-r — The agent's hook judges `find … | xargs rm` as a `find` that deletes from its starting points

The agent's hook judges an `xargs` of a program that deletes what it
reads (`rm`, `mv`, `git worktree remove`…), behind a `find` that gives
it its list, as a `find` that deletes from its starting points: `find
.. -maxdepth 0 | xargs rm -rf` is refused as deleting a directory that
contains the project, and `find . -type f | xargs rm -f` as deleting the
project. They passed: `xargs` was judged only by the protected paths the
command cites. What the `find` writes on its output is guarded by its
`-print` or `-print0`, or failing those by its whole expression. A
cleanup under the project (`find . -name '*.pyc' | xargs rm -f`, `find
build -type f | xargs rm -f`) still passes. The guide no longer says
this deletion escapes the hook, and the line of `xargs git worktree
remove` in the list of known forms states its exception, behind a
`find`.

To do: nothing.

## 2026-11-19-q — The agent's hook judges the arguments that follow the script of a `python -c`

The agent's hook judges the arguments that follow the script of a
`python -c`, and those that follow the `-` of a script python reads on
its input, as the paths the script cites written out in full: `python3
-c "import sys; open(sys.argv[1], 'w')" .socle/policy.toml` is refused.
It passed: only the script was judged, and the path it reads in
`sys.argv` escaped the hook, down to Claude Code's local settings file,
which git does not track. An argument is expanded with the command's
known variables (`F=…; python3 -c "…" "$F"`); one it cannot expand
(`"$X"`, `$(…)`) is judged as the unknown path the shell would write,
refused if it can fall inside the project, free under a directory
outside it (`/tmp/$X`). A `python -c` whose arguments name no protected
file passes, as does a script that does not read its arguments (neither
`argv` nor `argparse`, `fileinput`, `optparse` or `getopt`), which does
not touch them; the list of known forms the hook does not judge enters
one that would read them otherwise (`runpy`, the `exec` of another
script).

To do: nothing.

## 2026-11-19-p — The agent's hook judges the script a heredoc gives to python

The agent's hook judges the body of a heredoc read on its input by a
`python` or `python3` launched without `-c`, without `-m` and without a
script, or with `-` as its script, as the script of a `python -c`:
`python3 - <<'EOF'` whose body writes `.socle/policy.toml`, or passes
`..` to `shutil.rmtree`, is refused. It passed: the body of a heredoc
was only text to the splitting. The body is read as written, without
expanding its variables, its leading tabs removed for `<<-`, and the
last redirection of the input wins. A script that cites no protected
file and deletes nothing of the project passes; a heredoc given to
another program (`cat > notes.txt <<'EOF'`) and a script python reads
from a file (`python3 script.py`, `python3 - < script.py`) are judged as
before. Two neighbouring forms, which no agent writes in its work, are
entered in the list of known forms the hook does not judge: the heredoc
of a substitution, and the body of a heredoc given to an interpreter
other than python.

To do: nothing.

## 2026-11-19-o — The agent's hook refuses a former number repeated in a new line, even in a file that already cites it

The agent's hook refuses the former number of a renumbered entry in a
new text; it skipped every mention the file already held before the
write. In the journal of the migration's month, which cites almost all
former numbers, a new entry that repeated one passed. It now judges the
lines the write adds or changes: a new line that repeats the former
number without the current identifier is refused, even if the file
already cites it, and an earlier line kept as is passes, even if the
write changes what surrounds it. The line that also names the current
identifier ("former → current") still passes, as does, on a metadata
line, the former number it already held: the `former` field of a
renumbered entry being closed, the source of a decision whose status
changes.

To do: if the hook refuses a former number in a new journal entry, cite
the current identifier it names.

## 2026-11-19-n — The agent's hook judges the command that a quoted substitution launches

The agent's hook judges the command that a substitution in double
quotes, `"$(…)"` or backquotes, launches as it judges that of a bare
substitution, with the functions the command defined:
`x="$(cd memory && rm -rf ../..)"`, `echo "$(rm -rf ..)"` or
`echo "$(git push --force origin main)"` are refused as without quotes.
They passed: the text of a quoted substitution was never judged. An
ordinary substitution (`x="$(git rev-parse HEAD)"`), a `"$((…))"`
computation and a commit message written by `"$(cat <<'EOF' … EOF)"`,
whose body is only text, still pass.

To do: nothing.

## 2026-11-19-m — The agent's hook judges a `git push` on its expanded arguments, and refuses an argument it cannot expand

The agent's hook read the argv of a `git push` as written: a force push
or a push to the default branch passed when its option or branch came
from a variable (`F=--force; git push $F origin x`, `B=main; git push
origin "$B"`), from a function's arguments (`f() { git push "$@"; }; f
--force origin x`) or from a substitution. It now judges the argv of a
`git` expanded with the known variables, as it judges a path, and
refuses a `git push` one of whose arguments does not expand: a variable
it does not know, a substitution (`git push origin "$(git branch
--show-current)"`), a function's arguments. A branch written out in
full, or in a variable assigned earlier in the same command, passes as
before. A global git option whose quoted value holds a variable and a
space (`git -c http.extraheader="AUTHORIZATION: bearer $TOKEN" push …`)
does not hide the push: it is judged on the argv split into words and
on the whole argv.

Two neighbouring forms, which no agent writes, join the list of known
forms the hook does not judge: the option that skips the hooks passed
through a variable, which the CI catches, and a git subcommand that
comes from a variable.

To do: if the hook refuses a push of the working branch, write its
branch out in full.

## 2026-11-19-l — The agent's hook judges the command that `uv run` and `poetry run` launch

The agent's hook removes `uv run` and `poetry run`, with their options
before `run` as after it (`uv run --with x -p 3.12 --`, `poetry -C . run
-n`), as it removes `env` or `sudo`, and judges the command they launch
as without them: `uv run rm -rf ..`, `poetry run git push --force origin
main` and a `uv run python -c` that writes a protected file are refused
as without that prefix. They passed: the hook read the program `uv` or
`poetry`. The ordinary commands they launch (`uv run pytest`, `uv run -m
pytest`, `poetry run pytest`) still pass. The guide lists two known forms
the hook does not judge: the command that `uv run --directory` or
`poetry -C` launches is read in the current directory, not in the one
they name, and the value of an option it does not know (`uv run
--python-preference managed …`) is read as the launched command.

To do: nothing.

## 2026-11-19-k — The review pass is committed, and the refusal of a reviewed batch's closing shows the history, what git gives and the three questions

The `socle-review` skill says to commit the pass that `socle review`
writes in the batch's “Reviews” section, with what the agent records in
it: written without a commit where the command ran, it was lost, and the
next pass rewrote “Pass 1” without a step back required. And when the
backlog check refuses the “done” closing of a reviewed batch, its
refusal now shows, under the reason, what the refusal of a pass shows:
the batch's history, the entries opened and closed since the start of
its first pass and the closed batches that touched the same files, then
the three questions of the step back and what to write. A check's report
prints that detail indented; the end of turn keeps only the reason.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-19-j — The same review pass is recognized on a dirty tree, and a badly written blocker line is refused

`socle review` judges the working tree, modified tracked files included,
but the pass it writes in the batch's “Reviews” section kept only its
commits: run again on an unchanged dirty tree, it took the same pass for
a new one, refused without a step back, and its line said `Commits:
X..X` when nothing was committed. The pass now keeps, at the end of that
line, the fingerprint of the tree's changes it reviewed (`Commits:
<start>..<head> + working tree <fingerprint>`), and the same pass is
given again as long as neither the head nor those changes move,
committed afterwards or not. And a line of the “Reviews” section that
presents itself as a blocker in another form than `- Blocker: <its
cause>` (`- **Blocker**: …`, `- Blocker 1: …`, `1. Blocker: …`,
`- Blockers: …`, or without a bullet, `Blocker: …`, `Blocker 2 — …`), which nothing read, is refused by the backlog check,
whatever the batch's status.

To do: if the `memoire.backlog` check refuses such a line in a batch,
rewrite it `- Blocker: <its cause>`, one line per blocker.

## 2026-11-19-i — The review brief also gives the decisions and requests cited by those the batch writes

The brief of `socle review` gave the decisions and requests the batch
writes, then those its backlog entries cite. It now also gives, once
each, those cited by the decisions the batch writes: the validated
specification that a decision of the batch applies reaches the
reviewer, who judged without it. The `socle-review` skill says so.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-19-h — A private file approved by an in-session decision is never given in the review brief, however its path is written

The review brief judged the file approved by an in-session decision
private by the path written in its `sujet` field: written
`./memory/private/…`, or through a `..` detour, a file of the private
memory passed for public and was given to the reviewer. It is now judged
by its normalized path in the repository.

To do: nothing.

## 2026-11-19-g — A box of a task that delivers a request, a report or a memory entry is checked by what it produces

The memory format said that a task's “Done when” is checked by tests,
except an action only the human can do. It now states, box by box,
another exception: a box whose deliverable is a request posed, a report
written (the account of a measurement or a trial) or a memory entry
rewritten is checked by what it produces, which the box names: the
request and the human's answer recorded in the journal, the report's
file, what `socle show` or `socle roadmap` shows of it. Any other
deliverable keeps its test. The reviewer's instruction, in the full
brief as in the short one, says to judge such a box by that product,
not by the lack of a test.

To do: nothing; a task of this form may name that product in its box.

## 2026-11-19-f — The reviewer of a review receives the brief's path, not its text

The `socle-review` skill has the output of `socle review` written to a
file outside the repository, and gives the reviewer only its path, with
the instruction to read it in full and follow it as is. Copied as the
reviewer's message, the brief stayed in the orchestrating conversation,
reread at each step: tens of thousands of bytes per pass. What the
reviewer reads does not change.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-19-e — The review brief gives the file an in-session decision cited by the batch's tasks approves

An in-session decision can designate what it approves, a file of the
repository (`socle decision --about <path>`, its `about` field). When
the entries a batch serves cite such a decision, `socle review` now
gives the reviewer the text of that file as it was at the start of the
batch, and says whether the batch changes it, after the cited decisions; the
short brief (`--short`) gives it too, after the criteria. Beyond 20,000
bytes, the brief gives only its path, which the reviewer reads in the
repository. A private file, or one outside the repository, is not
given.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-19-d — `socle review --short`, the short brief of a small batch; the review skill says when to give it

`socle review --short` gives the reviewer of a small batch a short
brief: the instruction to judge the diff and the files it touches,
without exploring beyond, the batch's diff and the criteria of the tasks
it serves, without the rest of their entries or the decisions they
cite. It refuses, saying so, a batch that touches a guardrail: the
policy or the guardrails themselves, a path the policy protects, or a
path the guardrails declare as tooling (`[tooling] paths`); `socle
review` without the option then gives the full brief. The
`socle-review` skill says when to give the short brief: a batch of under
150 lines of code and tests that touches neither a guardrail nor a
format other parts of the project read; any other batch gets the full
brief. The skill is tightened elsewhere, with no rule less, to fit its
budget.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-19-c — A failing end of turn no longer copies the test output: the name of each check, the line of each failing test and the command that shows everything

When checks failed at the end of a turn, the hook copied the whole
report, passing checks and tool output included: thousands of tokens,
reread at every later step of the conversation. It now gives only the
essentials: each check that fails or warns, with the first useful line
of each of its findings (neither empty nor decoration); for an adapter
step, its command, its code and the line of each failing test, those
where a failure word (`FAIL`, `FAILED`, `ERROR`, `échec`…) opens or
closes the line, ten at most, or failing that the last useful line of
the output; the unavailable checks, named on one line. It ends with the
command that shows everything: `python3 .socle/socle check --stage
agent` for the socle's checks, `python3 .socle/socle verify --fast` for
the adapter's steps. The block, the counter, the escalation and the
rerun on an unchanged failure do not change.

To do: nothing in the project; for the detail of a failure, run the
command the message gives.

## 2026-11-19-b — The socle-request skill: content approved in session is first written in the repository; the light variant for mechanical expected values

Content shown in the conversation that the human approves (a format, an
example, a text) is now written as is in the repository before the
decision taken in session is recorded: it designates it (`socle decision
--about <path>`), and the tasks that follow from it cite that path.
Without it, the decision kept only the question and the answer, and a
batch could build on a memory of the content.

Expected values changed mechanically, tests that read a format the human
has just approved, are validated by a question in the conversation that
names each test, with its value before and after; the answer is recorded
word for word as a decision taken in session, whose text names the
tests, and is committed with them. Any other change of an expected
value, or deletion of a test, keeps the written request.

To do: nothing; the `socle-request` skill is a protected copy, in the
installer's request.

## 2026-11-19-a — The socle-batch skill: a small task is done without a subagent, and a batch's cost is estimated on measures

A small task, under 150 lines of code and tests (a provisional
threshold, revised on the measured costs), is implemented in the
orchestrating session, unless it touches a guardrail or a format that
other parts of the project read: the fixed cost of a subagent, which
rereads instructions and code before writing, exceeded what it saves.

The fixed consumption thresholds become a rule on measured costs. A
batch's closure notes in the journal the cost of each subagent, of the
reviewer, of each request and of the tidying up. A subagent is launched
if what remains of each window covers its measured cost and that of the
tidying up; without a measure, the former thresholds hold (none beyond
85% of the week or 60% of the five-hour window). The tidying up starts
at the latest ten points from a limit. At the announcement, the batch's
cost is estimated on these measures: if it does not fit in what remains
of the window, the batch is split, starts smaller or waits for the
reset.

To do: nothing; the `socle-batch` skill is a protected copy, in the
installer's request.

## 2026-11-18-d — The state no longer gives to delete a branch the origin no longer has

The clone keeps the reference of a branch deleted on the origin until a
fetch prunes it, and the state gave it to the human to delete, or to
examine, when they had already deleted it. When it has a remote branch to
propose, the state now asks the origin which ones it still has (`git
ls-remote --heads origin`, within five seconds) and proposes only those.
When the origin does not answer, it proposes them as before, saying that
its list comes from the last fetch and that `git fetch --prune origin`
refreshes it.

To do: nothing in the project.

## 2026-11-18-c — The project's roadmap in the approved formats: the compact one in columns, the detailed one in tables, in the order of execution; the recap is no longer read in a code block

`socle roadmap` changes its rendering, not its content nor its options.
The compact format aligns in columns, counted in characters, the batches
strictly in their order of execution, each with its tasks closed out of
the total, the batch in progress marked ▶. The heading of a milestone and
its needs closed out of the total comes back each time the milestone
changes from one batch to the next; “Outside the milestones” likewise
heads, in their place, the batches that serve none. The batch in
progress and the next two, whatever their milestone, have a line each;
beyond them, each run of batches of the same milestone fits on one line,
a single batch keeps its own, and `--all` unfolds everything. It no
longer has a header line, and ends with two lines: “Outside the
batches:”, the non-zero counts and the blocked entries named, and
“Next:”, the milestones with no batch with their first open needs, then
the needs in no milestone. It still names no request. The detailed format
(`--format markdown`) keeps its title and its sentence, then gives a key
to the symbols; in the same order, under the same headings, each batch of
the window has its line (its rank in the order of execution, its title,
its state if it is in progress or stopped, the requests it waits on, its
tasks closed out of the total) and a table with one row per task: its
state and its priority as symbols (✓ done, ▶ in progress, ○ ready,
⏳ waiting, ✗ blocked, ⊘ abandoned; ↑ high, ↓ low), its identifier, its
need, its title up to its first colon, and what it waits on; each other
batch, one numbered line. Read by need (`--by need`), the needs come in
the order of their batches, each with the table of its tasks and the
batch of each. What is outside the batches keeps its sections, each as a
table. The guide shows both formats.

The end-of-turn hook no longer looks for the recap's two lines, “For
you:” and “Next:”, nor for the patterns the policy gives in their place
(`[human] recap_markers`), in a code block fenced by three backticks or
three tildes; a block never closed runs to the end of the message. An
output pasted in a block, like this compact one, which ends with its own
“Next:” line, no longer stands for a recap; the `socle-batch` skill now
says to paste the compact one in a code block into the recap of a
batch's closing.

To do: nothing in the project. The agent writes its two lines as text,
never in a code block; the hook's refusal reminds it. The CI summary and
the recap of a batch's closing take the new rendering by themselves; a
project text that quoted the old one word for word is to be reviewed.

## 2026-11-18-b — The review dossier, its skill and the questions say task, need or entry, never “topic”

The product's last texts that called a backlog entry a “topic”, and that
tests read word for word, follow the backlog's four forms. The dossier of
`socle review` gives the reviewer “the backlog entries the batch serves”,
whose criteria (a task's “Done when”, a need's “Satisfied when”) are its
bar, “the entries the batch opens”, and the decisions “they cite”; the
`socle-review` skill describes it so. The starting question on delivery
offers “one pull request per task”. The template of the framing questions
(`socle new request --questions`) speaks of the need to specify. The guide
says a hole of the hook opens “a backlog entry”.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-18-a — The duration of the steps is told, and that of the fast steps has a threshold

`verify`, `verify --fast` and `socle ci` now print the duration of each
adapter step they run, at the end of its line, then their total. A new
guardrails key, `[verify] fast_max_seconds`, bounds the total of the fast
steps: 300 seconds when the project does not write it, the value the
template sets for a new project. Beyond it, the run that runs them all
warns without failing, naming the longest step: `verify --fast` at the end
of its output; the pre-push hook on its error output, without refusing the
push; the end of turn, without blocking, in its message to the human, and
in its reason to the agent when it already blocks for another one. The
warning comes back on the line that says the steps already passed, and in
`socle state` at the start of each session, as long as the last run where
they all passed exceeds the threshold. Its trace is a local file,
`.socle/trace/duree-des-etapes-rapides`, which git already ignores. The CI
prints the durations without a threshold. The ratchet knows the key:
raising it requires an approved request that cites it; lowering it is
free. For any guardrails key, it no longer takes `nan`, which no order
compares, for a tightening: writing it in place of a value, or replacing
it, requires an approved request.

To do: nothing mandatory. The duration of the project's fast steps is not
measured on its machine: `verify --fast --redo` measures it; if it exceeds
five minutes, the state will say so at each session, until it gets shorter
or the human raises the threshold. Writing the key at 300 in
`.socle/guardrails.toml` is free and changes nothing.

## 2026-11-17-f — The project's roadmap in the state, the instructions, a batch's closure and the CI

The roadmap (`socle roadmap`) shows up where one looks for it. The state
has a line that points to the command. The socle's instructions, in
`AGENTS.md`, tell the agent to paste the detailed format
(`--format markdown`) into its reply when the human asks for the
roadmap. The `socle-batch` skill has the compact format pasted into the
recap of a batch's closure. The installed CI writes the detailed format
into the summary of each run, readable on GitHub without an agent: a
"Project roadmap" step, before the private memory, none of which goes
into it, and which does not fail the CI if it fails. The guide says so in
one sentence.

To do: nothing; the `.github/workflows/socle.yml` workflow and the
`socle-batch` skill are protected copies, in the installer's request, and
the socle's section of `AGENTS.md` is regenerated by the update.

## 2026-11-17-e — The project's roadmap at a glance: `socle roadmap`

A new command, for the human as for the agent:
`python3 .socle/socle roadmap` gives the project's roadmap, computed from
the backlog like the state, nothing written by hand. Compact (the
default), one line per milestone, with its needs closed out of the total,
and one line per batch, in their order of execution deduced from their
`after`, the batch in progress marked with the progress of its tasks;
then what is outside the batches, counted. `--format markdown` gives the
detailed format: the batch in progress and the next two task by task
(each task with its need, its priority and where it stands), the others
on one line (`--all` details them all), and, named, the tasks in no
batch, the needs to split and to close, the blocked entries, those
`for: human` and the pending requests with their link. `--by need` reads
by need, each with its tasks and the batch of each; `--by batch`, the default,
by batch. Two batches that wait
on the same batch, neither waiting on the other, are flagged: their order
is not deduced, it is chosen by an `after` from one to the other.

To do: nothing.

## 2026-11-17-d — The last engine texts that called a backlog entry a “topic”

The description of `memoire.lectures`, which `socle checks` shows, says “a
backlog entry”; the help of `socle review --since`, “the tasks of the whole
batch”; the selftest labels (`socle selftest --verbose`), “need”.

To do: nothing.

## 2026-11-17-c — The migration of the backlog into four forms no longer loses or moves content

The backlog migration, which the update runs once, fixes three cases. A
closed entry that waited for an abandoned batch or milestone started
waiting for that batch's needs still open, which `memoire.ordre` then
refused: it now only waits for what is closed. A criterion written over
several lines goes whole into the task set, instead of its first line
alone, the rest staying in the need. The title, fields and criteria of a
task set cite the current identifiers, no longer the former number of a
batch or milestone.

To do: nothing in a project whose backlog has not migrated yet. In a
project already migrated, reread the tasks set by the migration: a
mention of a former number is replaced by the current identifier that
`socle show` gives, and a cut criterion is completed from the need.

## 2026-11-17-b — The former number of a renumbered entry: the hook names the current identifier, and `socle url` resolves it

The agent hook refused the former number of a renumbered entry
(`former: B-NNNN`), written in a new text, calling it invented, while the
checks resolve it; `socle url` answered “no entry”. The hook now refuses
it by naming the entry's current identifier, which the new text cites
instead, alone or on the former number's line (the update's summary,
“former → current”); the journal that already cites it is extended
without refusal;
`socle url` gives the link of the entry that carries it, and says its
current identifier.

To do: nothing; a number taken from the journal from before the migration
is cited by the identifier the refusal names.

## 2026-11-17-a — A shell form the hook does not judge is reported to the socle's repository

The `socle-review` skill said to enter a shell form an agent does not
write, dismissed by the review of a batch, in the guide's list of known
forms. In an equipped project, the guide sits under the installed engine,
protected: the agent cannot write it. The skill now says that the recap
names the form, and that “For you” suggests the human report it to the
socle's repository (https://github.com/theodubus/socle), which keeps the
list.

To do: nothing; the `socle-review` skill is a protected copy, in the
installer's request.

## 2026-11-16-g — A batch keeps the history of its reviews, and stops on a written step back

`socle review` now writes each review pass of the batch in progress (or
of the one `--batch L-NNNN` names) in the `## Reviews` section of its
entry: its date and the reviewed commits. The agent records there the
cause of each blocker, and the entries the pass opens; a new session
reads this history as it is. From the second pass on, the brief gives
the reviewer the causes of the earlier blockers, and has it say, for
each new blocker, whether it has the same cause as one of them. Before
any pass beyond the first, `socle review` requires the step back of the
previous one: a paragraph that starts with “Step back:”, answers three
questions of nature in at least sixty words, and ends with “continue” or
“stop”. Otherwise it refuses, showing the history, the entries opened
and closed since the start of the batch, the closed batches that touched
the same files and the three questions. It refuses “continue” after two
passes in a row where the reviewer sees a same cause come back, and any
pass while the stop is not lifted: only the human's answer to a request
that the step back names and that cites the batch lifts it, never a
withdrawn request, nor an old one, even answered, that does not cite it.
The `memoire.backlog` check applies the same rules to the last pass of a
reviewed batch closed `done`: it refuses it without its step back,
without the reviewer's view on a blocker, on a “continue” after two
causes that came back, or on a stop that nothing has lifted.

To do: mark `in progress` the batch being carried out, so that its
passes are written in it; when the reviewer returns, record the blockers
there; write the step back before the next pass and before the closing;
stopping means putting a request to the human, which cites the batch and
says what goes round, the rule that makes it go round and a proposal that
bounds it.
The `socle-review` and `socle-batch` skills say so; they are protected
copies, in the installer's request.

## 2026-11-16-f — The backlog in four forms, each with its prefix: need, task, batch and milestone

A backlog entry now has one of four forms, which its prefix states: a need
(`B-`), a defect to fix or a feature to add, with its “Satisfied when”
section, a result; a task (`T-`), a deliverable that names its need
(`need : B-NNNN`), with its “Done when” section, which a test checks; a
batch (`L-`), the tasks carried out and reviewed together; a milestone
(`JA-`), the needs that serve one goal. The `form` field goes away. Each
form waits only on what is its own: a batch, on its tasks and the previous
batch; a milestone, on its needs and the previous milestone. Only a task is
ready; it takes its need's priority and waits on what its need waits on. A
need closes when its tasks are closed, at least one of them done. The
state gives the next milestone and its open needs, the next batch and its
tasks, the ready tasks, the needs to split and those to close. The commands
`socle new need`, `socle new task "…" --need B-NNNN`, `socle new batch` and
`socle new milestone` replace `socle new backlog`, which goes away;
`socle new need "…" --task "…"` sets the need and its task. A new check,
`memoire.formes`, refuses mixing the forms again.

The update migrates the backlog: each batch becomes `L-` and each milestone
`JA-`, closed ones included, keeping its former number (`former : B-NNNN`),
which `socle show` and the reference checks resolve, and without its
priority: a batch or a milestone was already never taken, it changed no
order, and `memoire.formes` now refuses it; the update names each entry it
removed it from. Every other entry stays a need, its “Done when” section
renamed “Satisfied when”; each need an open batch waits on gets a task
that takes its criteria, to which its section refers, and that the batch
waits on in its place; a milestone waits on its batches' needs. Mentions
are rewritten in the backlog and the active work; the journal, the
decisions and the requests keep the former number. A citation by the
former number (`B-NNNN@…`) is judged against the renumbered entry, like
one by its current identifier: a stale or invented fingerprint is refused
there.

To do: review what the update migrated (`python3 .socle/socle state`, the
backlog), and commit the migration with it. Then, when taking each need:
split it into tasks if it calls for several deliverables, and rewrite its
criteria as results, its tasks' as deliverables a test checks. A review
finding becomes a task if its fix is clear, a need otherwise. The
`socle-batch` and `socle-review` skills say so; they are protected copies,
in the installer's request.
The guide, the public page and the framing-questions and initialization
templates say “need” where they said “topic”.

## 2026-11-16-e — The guide no longer cites an identifier of the socle repository's memory

The guide (`python3 .socle/socle help`), under approving one's own
protected changes, cited an identifier of the memory of the repository
that makes the socle, which an equipped project does not know. It no
longer does; a test keeps the guide free of any identifier of that memory.

To do: nothing.

## 2026-11-16-d — Forming a batch sweeps the whole open backlog, and an opened topic joins its batch at once

The `socle-batch` skill now says that when forming a batch, the agent
sweeps the whole open backlog, not only the next milestone: every ready
topic to which the rule of a batch applies (the same files, the same
guardrail or the same tests) goes into it, without asking the human; that
a topic opened later joins at once the open batch whose rule applies to
it, if it is ready, in the next batch not yet in progress, never in the
batch in progress, where only the blocking findings of its review are
fixed; and that a batch that no longer fits in one session splits into two
batches, along their files. The recap states each placement; the priority
remains the human's.

To do: nothing beyond following the skill; it is a protected copy, in the
installer's request.

## 2026-11-16-c — Each requested model runs on the latest version of its family

The `socle-batch` skill now says that each requested model, for a
subagent as for the session, runs on the latest version of its family:
under Claude Code, the `opus` alias of the `Agent` tool designated an
older Opus than the session's, with nothing saying so. Each subagent's
report names the model that served it (`modelUsage` confirms it in a cloud
session, once the turn is over); the agent launches a subagent without
`model` so that it inherits the session's when the alias designates an
older version, or tells the human; the reviewer follows the same rule (the
`socle-review` skill); the batch recap states the version that served each
subagent.

To do: nothing beyond following the skill; it is a protected copy, in the
installer's request.

## 2026-11-16-b — The state says what waiting topics wait on: a topic or a request

The last line of the backlog order, in the state and in the end-of-turn
reminder, said "n topic(s) wait on an open topic" of every topic that was
not ready, including one that only waits on an unanswered request. It now
splits in two: "n topic(s) wait on an open topic" counts those waiting on a
topic, "n topic(s) wait on an unanswered request" those waiting on a
request; a topic waiting on both counts in both lines.

To do: nothing.

## 2026-11-16-a — The agent's hook bounded to the forms an agent writes: the guide gives the rule and the known forms it does not judge

The guide (`python3 .socle/socle help`) says what the agent's hook
judges: the shell forms an agent writes in its work, for every effect;
for what nothing catches afterwards (deleting the project or a directory
that contains it, an irreversible external action, a leak of the private
memory, the part of the memory that is not published), it also refuses
what it cannot read. A hole opens a topic only if its form is one an
agent writes (seen in an agent session, a skill or current
documentation); another form is entered in one line in the list of known
forms the hook does not judge, which the guide now gives: `time` before a
compound command, the patterns of a `case`, `find -exec sudo …`, a
`return` in a function, the indirect call of a function, a function
named like a command or defined by an `eval`, `eval -- f`, `git
--config-env`, what an `eval` changes other than a call, a function
called from another directory, `echo .. | xargs rm`, `xargs git worktree
remove`, what a `python3 -c` launches or builds, `coproc`. Until now, the
guide said the hook judged, whatever its form, what nothing catches.

The reviewer's brief (`python3 .socle/socle review`) and the
`socle-review` skill, a protected copy, say it too: a shell form an agent
does not write in its work, and that escapes the hook, is classed neither
as blocking, even if refused before the batch by accident, nor for the
backlog; it is dismissed, in one line, for the list. The sorting of other
findings does not change. The hook itself does not change.

To do: nothing. Deleting the project through `find … | xargs rm` still
escapes it: do not run it against the project or a directory that
contains it.

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
