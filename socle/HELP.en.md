# The socle, on the human's side: user guide

This guide follows the human's path in a project equipped with the socle,
from the end of the installation to everyday use. Commands run at the
project root: `python3 .socle/socle <command>`; this guide is shown by
`python3 .socle/socle help`. Without a terminal, in a cloud session, the
agent runs them: just ask it to.

The path in short:

1. **Getting started**, once: describe the project, give the agent its
   tools, push, protect the branch.
2. **Working with the agent**: give it work, read its recaps.
3. **Answering the agent** when a decision belongs to the human.
4. **Occasional actions**: approve one's own changes, update, act where the
   agent cannot.

## 1. Getting started

In a cloud session, the agent installs the socle from its public
repository, which is cloned without being added to the session. The
agent's hooks load in the session that installs, from the tool call that
follows the installer writing their settings: from then on, a protected
file (the adapter, the CI, the policy) can no longer be fixed by hand.
What is wrong is fixed by running the installer again with the right
options, an adapter of the project's own being given by `--adapter
<file.toml>`; a trial is undone by committing it on its branch, then going
back to the starting branch with `git switch`, never file by file, which
the hook refuses: uncommitted, its files would follow, and the installer
run again would see an update. Before the first
commit, `python3 .socle/socle verify --fast` runs the adapter's build and
tests, which the installer's audit does not run. The session that installs
pushes its branch and opens a pull request. Once that is merged, the
work continues in a new session, which starts from the default branch and
receives the state as soon as it starts. A session that adds a second
repository is not resumed: with two repositories, it restarts outside the
project root, without the agent's hooks.

An agent working in a worktree of the repository (a subagent, for
instance) cites there the entries it has just created: the pre-tool hook
reads a reference in the worktree of the file written or of the current
directory, or in the main copy where the session started. Its refusals
hold for both trees: refused in either, an action is refused. The
end-of-turn and start hooks judge the main copy.

A project written in several languages has one adapter per language: the
installer sets one per language it recognises, or those it is given
(`--adapter python-pytest --adapter kotlin`, the first being the main
one), and each file is judged by the one of its language (the
[adapters specification](adapters/README.md)). A language whose manifest
is only in a subdirectory gets no adapter automatically. Automatically
as with `--adapter`, while no adapter covers it and its manifest is not
under a declared third-party path, the installer says so, with its two ways out: an adapter of the project's
own whose commands enter the subdirectory, or the subdirectory declared
third-party.
An adapter can be set before the first file of its language: the CI
prepares its tools only once its build file is there (the Gradle cache
waits for a Gradle file), and its capabilities wait for the first source
file, which `verify` reports as a warning.

Right after the installation:

1. Describe the project:
   `python3 .socle/socle init --brief <document> --repo`. The brief is
   archived; `--repo` surveys what the repository already holds. Without a
   document, `--repo` alone; in an empty repository, no option.
2. Give the agent the tools the CI installs for the adapter (pytest, for
   instance), which the installer quotes with their commands. In a cloud
   session, the container starts from scratch at every session: the
   socle's start-up hook installs them in every new session, and completes
   the history of a shallow clone, which would lack the commits the memory
   cites; only the session that installs the socle installs them itself. As long as the
   project has no source file, `verify` runs neither build nor tests, and
   says so.
3. Commit and push.
4. Protect the default branch on GitHub (repository settings, "Rules"):
   require the CI "Socle — verify, checks, self-test" before any merge.
   Without it, a red CI does not prevent merging. In the same ruleset, tick
   "Block force pushes" and "Restrict deletions": outside the agent's hook,
   only GitHub refuses a force push to the default branch, or its
   deletion; the state says whether they are refused, and otherwise asks
   you to have them refused. The code owners' review
   is added only if another human reviews: the author of a pull request
   cannot approve it, and the agent opens its own under the human's name.
   In the general settings, tick "Automatically delete head branches": a
   merged branch then deletes itself. The agent's branches that the
   default branch or its pushed working branch already contains, the agent
   deletes itself (`socle prune-branches`), after checking on the origin,
   at that very moment, that they have not moved; a line of the policy
   takes this from it (`prune_branches = false`, section
   `[irreversible]`). The state reports the others to you: yours those
   branches already contain, and those the origin refused to let the agent
   delete, to delete, and those that have not
   moved for a week without being merged, to deliver or to delete. If such a
   branch alone keeps a commit the memory cites, the state first gives the
   command that tags it: without it, CI would no longer find it. It only
   proposes a branch the origin still has, and reports a branch as kept by
   the working branch only if the origin still has the latter; when the
   origin does not answer,
   it says its list comes from the last fetch, and that `git fetch --prune
   origin` refreshes it.
5. Open the agent in the project. It reads the state at start-up, then
   gives the link of the starting questions, a request that `socle init`
   put: answer it in the conversation, `approve` to apply all the defaults,
   or one answer per question.

If the project already had its own `SessionStart` hook, the installer
points it out: remove it from `.claude/settings.json`, otherwise each
session receives two states. It names likewise a `Stop` hook of the
project, which fires at every end of turn next to the socle's and may
duplicate it. A command of the project placed in the same block as a hook
of the socle is kept and named likewise: the installer removes from the
block only the socle's.

## 2. Working with the agent

Work is given to the agent as usual. At the start of each session, it
receives the project's state, the active work, the titles of the facts and
the last ten decisions; it works, and the checks verify it at each step.
This start-up stays under `[startup] max_bytes` of the guardrails, a cap
set below what Claude Code hands over whole to the agent, of which each
part has its share: a part beyond its own loses whole lines (the state
first what can be read elsewhere, never what calls for action before it;
the others from their end), and the last line says which, by how much,
and how to read the rest. The active work's budget, public and private
together, fits in its share: at its allowed size, it is never cut.

**Planning.** From the brief, the agent writes a short specification and a
short architecture in the project's documentation: each choice as an ADR,
each open question as a request (as framing questions when your
intention is missing, section 3). The backlog has four forms of entry,
each with its prefix: a **need** (`B-`), a defect to fix or a feature to
add, with what satisfies it (“Satisfied when”, a result); a **task**
(`T-`), a deliverable that serves a need, with what makes it done (“Done
when”, which a test checks; a box that delivers a request posed, a report
written or a memory entry rewritten is checked by what it produces, which
the box names: the request and your answer, the report's file, what
`socle show` shows of it); a **batch** (`L-`), the tasks that touch the
same files, carried out and reviewed together; a **milestone** (`JA-`),
the needs that serve one goal. Each says what it waits on (`after`:
another entry, or a request until it is answered), and its boxes are all
checked before closing it; the agent then closes it in one step, `socle
close`, which sets its status, its reference (by default, the commit that
closes it) and its filing. A need is born placed, in a milestone (`socle
new need "…" --milestone JA-NNNN`) or in the reserve, outside the
milestones, with its reason and the batch of its sorting (`--reserve
"<reason>"`): at the closing of a batch, the agent sorts those the state
calls to place, without a reason or unsorted for fifteen closed batches,
and sorts the whole reserve again before closing a milestone, each need
joining a milestone to come, kept with its reason, or proposed for
abandonment in a request. It submits each document as a request. Just
ask it to; the state then gives the next milestone, the next batch and
the progress of its tasks, the ready tasks, and the needs to split into
tasks or to close. The whole roadmap, at a glance, reads in a terminal with
`python3 .socle/socle roadmap`, on the page of each CI run, and in the
conversation: ask the agent for “the roadmap”.

It has a single form, in four parts. **Now**: each batch in progress,
marked ▶, then each need it carries, with its first open tasks; with no
batch in progress, the first ready task. **Next**: the open milestones, in their order of execution,
numbered, each with its needs closed out of their total, between
brackets of equal width that align the titles; only the first, the next
step, is unfolded into its needs: the closed ones counted on one ✓
line, then ▶ served by a batch in progress, · other (`--all` unfolds them all). **For you**: what is up to
you, the actions to take and the pending requests. **In
reserve**: the needs in no milestone, counted, and how many are to place. A “Warning:” line tells of
a blocked entry, or of two batches whose order is not deduced. A title
reads up to its first colon. In the terminal, each title is followed by
its identifier, a line wraps under its own column, at the width of a
phone, and no request is named by its own. For example, the identifiers
written here `X-NNNN`:

```text
The roadmap of Fou — 27 November

Now
 ▶ Finish adopting the socle (L-NNNN)
   need: Adopting the socle (B-NNNN)
     left: Move CLAUDE.md into
           AGENTS.md (T-NNNN)

Next
1. [1/4] Ship the N10 network (JA-NNNN)
         ✓ 1 need closed
         · Measure N10 against N8 (B-NNNN)
         · Ship N10 in the binary (B-NNNN)
         · Place the engine on the CCRL
           list (B-NNNN)
2. [0/3] Tune the search with SPSA (JA-NNNN)
3. [0/2] Speed up the search (JA-NNNN)
4. [0/3] New network architecture (JA-NNNN)

For you: Copy the training data to a hard
         drive (B-NNNN)
In reserve: 12 needs, 2 of them high priority
```

With `--format markdown`, the same text comes in a code block: this is
how the conversation and the summary of each CI run give it, aligned, on
a phone as elsewhere.

**Specifications and test cases.** The project declares where its
specifications live (`[specs] paths` in the guardrails): the state tells
you about any that no request has submitted to you. It also declares its
case files (`[tests] case_paths`), data where its tests read their
expected results: adding a case is free, but changing or removing an
existing case requires your approval, like an expected value written in a
test.

**Prioritising.** A need or a task can carry `priority: high` or
`priority: low`; the normal one is not written, and a task takes its
need's. Telling the agent is enough, and it does not change a priority
the human gave. The ready tasks are sorted by priority, and the
low-priority ones stay apart: the agent takes them only
when convenient, and says so when announcing the batch.

**Chaining.** As long as nothing is up to the human, the agent chains the
ready tasks without waiting for a message. Before starting, it announces
the batch it will work on: stopping or redirecting it takes one message.
At the end of the batch, it chains the next one if the session allows
it (below, “Chaining sessions”), and stops as soon as a decision is up to
the human. An open batch that still waits for more tasks than one session
carries, `[batches] max_tasks` of the guardrails (9 by default), the state
and the end-of-turn reminder say so, without refusing anything: cut it
into batches, or make it a milestone with its batches under it. Lowering
the threshold is free; raising it requires a validated request.

**Having it reviewed.** Before delivering a batch that adds or changes a
guardrail (a check, a refusal, a hook), a format other parts of the
project read, or more than 150 lines of code and tests, the agent has it
reviewed by a reviewer without context, who gets the full brief
(`python3 .socle/socle review`) and tries to find fault with it against
the “Done when” criterion of the batch's tasks and, for a guardrail, its
threat model, written before the code: what the guardrail stops, what it
lets through. Another batch that changes code or a test, the agent
rereads itself, its diff and the files touched, against its tasks'
criteria (`python3 .socle/socle review --short`, which refuses a batch
that touches a guardrail), and its recap says so. A specification,
documentation or memory alone get no review: you judge their intent.
The agent fixes the blocking findings in the batch (a contradicted
criterion, a regression, a data loss, a bypass within the threat model);
it sends to the backlog, where you see them, those that matter and have
been seen in real use, or whose effect would be irreversible, as a task
if its fix is clear, as a need otherwise, and dismisses all the others,
including a case imagined and never seen, a slight nuisance or an
unfounded finding; a dismissed one comes back if it is seen. Its recap says how many, and why each is
dismissed.

**The review history.** The agent keeps, in each batch's entry, its
review passes and their blockers: a new session that resumes the batch
reads there where its review stands.

**Delivering.** By default, the agent does everything on one development
branch and keeps only one pull request open, to which each finished batch
is added: merge it whenever you want, once its CI is green. One pull
request per task, each to merge, is chosen in the starting questions, or
later by telling the agent, which writes it as a fact of the memory.

**Merging by the agent.** By default, you merge the agent's pull request
yourself: the hook refuses it the merge, like the other external actions.
For it to merge its own itself, uncomment the `tools` line that the
`[irreversible]` section of the policy (`.socle/policy.toml`) carries as a
comment: the list of external tools the engine refuses, minus the merge. A
policy laid down before this option does not have it; the diff of the
policy, shown on the update that brings it, gives it. Only the human writes the policy, and
approves this change like any protected change: the agent does not grant
itself the right. It then merges only under four conditions: its own pull
request only, never another session's; the CI green on its head commit,
which it gives; the review of the last batch done and its findings
handled; no request pending on its content. After the merge, it checks the
workflows the merge starts on the default branch (a deployment, a
publication…), and its recap says whether they succeeded. It merges
through its session's GitHub tool: `gh pr merge`, force push and push to
the default branch stay refused. The line freezes the list: a tool the
engine later adds to its own is not refused in the project until you have
copied it into the line, which the release note that adds it will say.
Removing the line gives the merge back to the human.

**Chaining sessions.** The session is the budget unit: at the end of a
batch, the agent chains the next one if its estimated cost fits in what
remains of the five-hour window and of the week, and if the conversation
stays under 150,000 tokens of context, beyond which running a batch
costs more than changing sessions; two batches at most without a message from you.
Otherwise, as near a usage limit or before a long wait, it tidies up,
then hands over to a new session, in one of two modes. By default, in a Claude Code
cloud session, the **scheduled session**: it creates the next session
itself, which appears at once in your list of sessions with its title and
start time, and schedules its prompt; never if its batch's cost does not
fit in what remains of the five-hour window, nor on a week at 75%: it
then waits for the reset. The chain
stops without you, and the recap tells you to ask for the resumption, when the
next batch has no ready task (a decision is up to you, for example),
after two batches run without a message from you, or if Claude Code
refuses to create the session. The **prompt to copy**: you open a new
session whenever you want, from one account or another, and ask there
for the resumption: "resume", "continue", or any other message that says
so; it is the mode of whoever has several accounts or wants to keep
control. To change the mode, tell the agent (“switch to the
prompt to copy”, “go back to the scheduled session”): it writes it in the
active work, and switching to the prompt to copy cancels what is
scheduled, giving you the link of each cancelled session. To stop a
scheduled session without changing the mode: write "stop" in the session
that scheduled it, or delete its task from the list of scheduled tasks
of your account and archive the session. In both modes, the agent
writes its handoff in the memory (`python3 .socle/socle handoff write`),
commits and pushes it, before any merge: when it merges its pull request
itself, the handoff is its last commit, and nothing is pushed afterwards,
so that no session branch is left for you to delete; the new session
finds it and judges its guard
(`python3 .socle/socle handoff check`): it does not work if someone pushed
to its branch since, if another session wrote the project's memory
since, or if another one already resumed it, and says so; without a
handoff, it says so too. Accepted, it continues
the open pull request of its branch, which becomes its own: it merges it
if the policy allows the agent to; otherwise, you merge it.

A prototype not meant to be merged is done on a disposable branch, named
`proto/…` (or with another prefix declared in `[branches] disposable` of the
guardrails). The socle's CI does not judge it on push, and the dead
references (links, identifiers, cited paths) of a file it adds are only a
warning there; the other checks before commit and those of the agent's
session remain, and the private memory is still judged whole. Thrown away,
it leaves nothing in the default branch; once pushed, deleting it on GitHub
is up to you, and the state lists it among the branches to examine after a
week without activity. Merged, it goes through a pull request, whose CI
judges it whole.

Each intervention of the agent that acted ends with two lines:

- **"For you:"** — what is up to the human: a request to read, an action
  to take, or nothing;
- **"Next:"** — what comes next, and what the agent is waiting for.

Each item of "For you" can be understood on its own: what it is, why,
and what your answer changes. The agent writes its two lines as text: a
line in a code block does not count, and an output it pastes there, like
the project's roadmap and its own "For you:" line, does not stand for
a recap.

At any time, `python3 .socle/socle state` gives the project's state: the
commit, the CI, the backlog and what comes next (the next milestone, the
next batch, the ready tasks), the pending requests, what is up to the human.
The memory is read in `memory/`.

A project procedure that comes back, the agent writes as a skill in
`.claude/skills/`, with a journal entry: it then loads it on demand instead
of rebuilding it. Its skills are checked like the rest; the socle's, laid by
the installer, are protected.

## 3. Answering the agent

**A request.** When a decision belongs to the human (loosening a
threshold, deleting a test, a decision costly to undo, an irreversible
action), the agent writes a request and gives its link. It reads on its
own, even after weeks away from the project: its context opens with the
project, the work in progress and the question. A long request, beyond
half its budget, an agent that has subagents has read cold, by one of
them that only has its text, before asking you, and its recap gives the
outcome. It ends with the list of
possible answers. Answer in the conversation; the agent records the answer
word for word.

- The base answers are the same in every request: `approve` (the
  recommendation), `reject`, `insufficient-context`; a choice request adds
  its options.
- `approve` is the only answer that authorises an action reserved to the
  human.
- A test it names, deleted or whose expected value changes, or a protected
  file it cites, may come before your answer: if the default branch
  requires the socle's CI, it is committed and pushed under the request
  pushed as is, the CI refusing it until your answer, and you read it in
  the pull request; otherwise, it waits in the agent's working tree.
- `insufficient-context` sends the request back to the agent, which
  rewrites it.
- From a terminal:
  `python3 .socle/socle answer D-NNNN <answer> --text "<text>"`.

**A question in session.** A short question, which the agent asks in the
text of its answer, is answered in the conversation; the agent records it
at once, word for word, like a request. What needs context, approving a
document included, comes as a request, with its link; never in the
agent's question widget, which the hook refuses. What you decide of your
own accord, without being asked (a rule, a prohibition, "delete this
test"), it records the same way, your exact text, with no question and no
answer to choose (`socle decision --unprompted`): the decision counts as
approved for what it names.

**A lasting directive.** A rule, a preference or a prohibition that holds
beyond the turn, the agent writes at once into the directives
(`memory/directives.md`, with `socle new directive`): a summary line, which
every session receives at startup, your exact text, which never changes,
and its source in the journal. Before relying on a directive, it reads its
exact text again (`socle show C-NNNN`), and any citation of a directive in
the memory proves it by its fingerprint. To lift one, say so: the agent
records your word in session, then marks the directive "lifted", with the
decision that lifts it (`lifted-by`); only your word lifts it, and
`socle archive` then moves it to the journal. A directive you change
becomes a new one, and your word lifts the old one. A decision about the
project is written as a decision, an expectation as a `blocked` need
(`socle-request` skill): filed as a directive, it would weigh on every
start, and would only be lifted by one more word.

**The question of intent.** When a need's design is not settled, the
agent first asks you, in the conversation, in a few lines, the need as it
understands it, the choice that remains and its recommendation. It
records your answer, then writes the specification and the code in the
same batch, the specification first; what remains costly to undo then
comes to you as a request, a short one.

**Framing questions.** When your intention is missing on several points,
the agent asks open questions, each with its assumption, in a request
whose link it gives. Answer them freely, in one or several messages
(`answers`), or `approve` its assumptions: it records the text as is,
then writes the specification that follows from it. Telling it "ask me your questions about this
need" is enough to request them.

**A review before publication**, if the policy requires it: the agent
shows what goes out to the public repository, the human gives their
agreement in the conversation. From a terminal:
`python3 .socle/socle reviewed --by <name>`.

## 4. Occasional actions

**Approving one's own protected changes.** The policy, the thresholds, the
adapter, the hooks and the CI are protected: a commit that changes them
without approval is refused. When the change comes from the human:
`python3 .socle/socle approve --text "<reason>"`, then commit. This
command is reserved to the human. The agent never writes to a protected
file, except to put it back as it was at the last commit when it changed
it by mistake, Claude Code's settings excepted, which the human
keeps for themselves: `git restore --source=HEAD --staged --worktree --
<path>` or `git checkout HEAD -- <path>`, each path written out in full,
or `rm <path>` for a file that appeared under a protected path and that
git does not track. Anything else is refused to it: another commit, with
or without `--`, a whole folder, a shell pattern or variable, paths read
from a file, a variable or a prefix before `git`, a redirection to another
protected file, and a file that is cited, itself or its folder, by a
request pending or approved whose approved change is not committed yet; a
folder that is only one word of a text copied between backticks, an
expected value or an output, is not cited there. The accepted risk: erasing a change of the human in the working tree that
they neither committed nor submitted in a request. A path the shell
writes, the hook expands, as best it can, as the shell would (variables,
patterns, braces, `~`, `cd`, `pushd`), from the agent's current directory,
assuming a subshell, a substitution or a pipeline passes nothing on to
what follows. A path it cannot expand (a variable it does not know,
`$(…)`) is refused if the directory that the part written out in full
before it names, moved up by the `..` that follow it, is in the project or
contains it: write it out in full, or under a directory outside the
project (`/tmp/…`). A command it cannot judge (more than 10,000 characters
outside the bodies of its heredocs, more than 32 parentheses or braces
open at once, a judgment that crashes or takes over 5 seconds) is refused
if it can write: split it. The script of a `python3 -c`, and the one a
heredoc gives to python (`python3 - <<'EOF'`), are judged by the protected
files they cite written out in full or that the arguments following them
name, if they read them (`sys.argv`), and such an argument it cannot
expand (`"$X"`), as a written path; a script python reads from a file is
not judged. It also refuses deleting a directory that
contains the project (`rm -rf ..`, an `mv`, a `git clean` or a `find` that
deletes from such a directory, or gives its list to `xargs rm` (`find ..
-maxdepth 0 | xargs rm -rf`), the destination of an `rsync --delete`,
the sources of an `rsync --remove-source-files`, the path of a `git
worktree remove`, a `python3 -c` or a heredoc's script that passes it
written out in full to `shutil.rmtree`), deleting the project itself by these other programs (a
subagent removing its own worktree, `git worktree remove .`, or by the
end of its path, which git looks up first among its worktrees: `git
worktree remove agent-x`), and
deleting the project by a `find` that starts from its root with no name
or path filter guarding what it deletes (`find . -delete`, `find . -type
f -delete`, `find . -delete -name '*.pyc'`, whose filter comes after the
action); a directory next to the project, and a directory of the
project, stay free (the orchestrator, at the root, removes a subagent's
worktree). A `git push` is judged likewise on its expanded arguments:
`F=--force; git push $F origin x` is a force push, and an argument it
cannot expand (a variable it does not know, a substitution, a function's
arguments) is refused: write the branch out in full. Three substitutions
are the exception, `$(git branch --show-current)`, `$(git rev-parse
--abbrev-ref HEAD)` and `$(git symbolic-ref --short HEAD)`, bare, quoted,
in backticks or through a variable: they stand for the current branch,
which the push then targets (`git push -u origin "$(git branch
--show-current)"` passes from a working branch, and is refused from the
default branch), unless the same command changes directory, repository
or branch before the push (`cd`, `git -C`, `git checkout`, `git
switch`).

**What the agent's hook judges.** The agent's hook stops the mistakes of
a cooperative agent before they take effect. It judges the shell forms an
agent writes in its work, for every effect; for what nothing catches
afterwards (deleting the project or a directory that contains it, an
irreversible external action, a leak of the private memory, the part of
the memory that is not published), it also refuses what it cannot read.
A cooperative agent does not try to get around its guardrails.

The hook does not model all of bash: a write to a protected file in a
form one writes only to get around it (an `eval`, `IFS`, a path built on
the fly in another language) is outside its model, as are forms that
escape it (an unknown part that is itself `..`, an option set by the
shell's profile, a variable Claude Code sets only for its hooks…); the
guarantee is then the protected-files check, at the end of the turn, at
commit and in CI.

**Doing what the agent cannot do.** Pushing to the default branch,
publishing, setting up a service, deleting a remote branch, setting a tag
(in a cloud session, the agent only pushes its own branch): the agent records it in the backlog with
how to do it, and the state lists it under what is up to the human.
Deleting the remote branch of unmerged work does not reset its range:
the pre-push hook of the clone that pushed it judges what follows from
the last commit it pushed there.

**Committing oneself.** The same checks apply: a public function added is
named by a test, or waived in the commit message
(`Waive-test: f — <reason>`); a fix brings a test that fails on the
previous commit.

**Measuring what a session cost.** When a Claude Code session used up
its usage limits faster than expected, or before changing the way a
batch is run: `python3 .socle/socle consumption` reads the transcripts
Claude Code keeps for the project (under ~/.claude/projects/, one
folder per project; another folder is given as an argument), and says
what the session cost, by day and by model, the main conversation and
the subagents apart, and what made it cost: the size of the context
read again at each call, the resumptions after a pause, the
compactions, and what the socle injects into it. `--session <id>`
keeps one session (the name of its `.jsonl` file), `--day YYYY-MM-DD`
one day. The cost is weighted at the public price, an assumption that
options change; readings of the five-hour window, given by
`--point INSTANT,SHARE`, say what a point of the limit is worth. The
report carries only aggregates, never a text of the conversation.
Under another agent than Claude Code, the command finds nothing to
read.

**Updating the socle.** Run the installation command again from an
up-to-date clone of the engine (`git clone --depth 1
https://github.com/theodubus/socle /tmp/socle`). The project's files are never overwritten;
the diff of the policy is shown, in one line when each of its lines was
already in its diff to the template of the replaced copy, shown at the
previous update (the lines the human wrote on purpose). Between what it put in place and the
audit, the installer prints the [release notes](CHANGES.en.md) that the
project's engine copy did not have, all of them if it had none: what each
change does to the project, and what the agent must do. It prints in full
only those that ask something; of those whose “To do” is “nothing”, the
title alone, their text staying in the file it names. The commit message
it proposes names their identifiers, for the agent that did not see the
update go by. The agent's hook refuses the installer aimed
at an equipped project in another mode than its lock's, or at a target
written through a variable: the update keeps the mode, and its target is
written out in full. The one exception: a copy of a maintained
adapter that the project has not adapted is refreshed; an adapted copy is
kept, and the installer says when its maintained adapter has changed: the
agent then proposes to carry the corrections over, through a request. Then approve the changed protected files
(`socle approve`), and commit. In a cloud session, with no terminal, the
agent puts a request that cites each changed protected file with its
fingerprint, and the human approves it in the conversation; each file takes
one line there, its path and its fingerprint with nothing else, which the
request's budget does not count. Pushed alone first, the request is judged
by the CI with the previous engine, which may still count these lines and
refuse it: that refusal stops once the protected files are committed, with
the new engine. If the default
branch requires the socle CI, the agent commits and pushes these files as
soon as the request is pushed: the CI stays red until the approval, and the
human reads them in the pull request before answering. The engine's
public repository is cloned without being added to the session. An update
keeps the project's guardrails as they are, and names the settings that
have appeared in the template since: the agent declares there the ones the
project needs, such as its specifications and case files (section 2),
once the new engine is committed. Before that, CI judges with the old
engine, which does not know them and counts them as loosening. If the
socle's section, which is regenerated, makes `AGENTS.md` exceed its budget,
the installer says so: tighten the project's own part, or raise the budget
through a validated request, since raising it loosens a guardrail.

In a cloud session, the prompt to give the agent:

```text
Update the socle of this repository from its public repository, without adding that repository to the session:
1. If the clone is shallow (git rev-parse --is-shallow-repository answers true), complete its history: git fetch --unshallow.
2. git clone --depth 1 https://github.com/theodubus/socle /tmp/socle
3. On your working branch, from the root of the repository: PYTHONPATH=/tmp/socle python3 -m socle install --target . ; if the project has several adapters (copies in .socle/adapters/), name them all with --adapter, the main one first, as at installation.
4. Read the release notes the installer prints, and do what each one asks.
5. Follow the installer's "What now" steps, including the request that cites the changed protected files, then push and open the pull request.
6. Tell me what is up to me.
```

**Setting up the private memory** (companion mode). Create an empty private
repository on GitHub, then
`python3 .socle/socle private install --repo <address>`. The command ends
with the two settings to make on GitHub, with their links.

## When a check refuses

Each refusal says what it saw and how to get out of it. Most are for the
agent, which fixes them alone. Those that concern the human:

| Refusal | Meaning | What to do |
| --- | --- | --- |
| `protege.fichiers` | a protected file changed without approval | change by the human: `socle approve`; by the agent: it must ask |
| `cliquet.garde-fous` | a threshold was loosened | restore it, or approve a request that cites it |
| `tests.attendus` | an expected value changed, in a test or a case file, or a test disappeared | approve a request that names the test or cites the case file, or restore it |
| `tests.code-teste` | a public function without a test | write the test, or `Waive-test:` in the commit |
| `tests.regression` | a fix without a test that proves it | write that test; if its proof depends on the environment, or if the fix touches no file an adapter judges, approve a request that names the commit |
| `docs.correspondance` | code changed without its documentation | update the documentation, or `Waive-doc:` in the commit |
| `mutation.vivante` | the weekly sweep no longer runs | re-enable it in GitHub's Actions tab |
| push refused, review | the policy requires a review | review what goes out, give one's agreement |

## Reference

### The autonomy policy

`.socle/policy.toml`, modified by the human only:

1. Loosening a guardrail requires an approved request; tightening is free.
2. Deleting a test or changing an expected value, in a test or a case
   file, requires an approved request.
3. The agent takes reversible and measurable decisions; it asks for those
   that are costly to undo.
4. An irreversible or external action is always asked for, except
   merging its own pull request when the policy allows it (“Merging by
   the agent”).
5. The memory is append-only.
6. A defect next to the current work goes to the backlog.
7. After three failures in a row, the agent stops and writes a request.
8. The agent never guesses an approval: it waits for the answer.

### Commands

| For the human | |
| --- | --- |
| `help` | this guide |
| `install` | install or update the socle |
| `init` | describe the project |
| `state` | the project's state |
| `roadmap` | the project's roadmap: now, the steps that follow, what is up to you |
| `consumption` | what a Claude Code session cost, and what made it cost |
| `answer`, `decision`, `reviewed` | answer a request, record a decision in session, a review |
| `approve` | approve one's own protected changes |
| `private install` | set up the private memory |

The other commands serve the agent and the hooks; `python3 .socle/socle
--help` lists them all, and `python3 .socle/socle checks` lists the checks.

### Thresholds

`.socle/guardrails.toml` holds the checks' thresholds: memory size
budgets, mutation caps, correspondences between code and documentation,
third-party files (those of a tool installed in the project), the
project's case files and specifications. Tightening them is free;
loosening them requires an approved request.

**The duration of the steps.** Each verification that runs a step of the
adapter (`verify`, `verify --fast`, the CI) prints its duration at the end
of its line, then the total. The total of the fast steps has a threshold,
`[verify] fast_max_seconds`, 300 seconds by default: beyond five minutes
of waiting, a sub-agent loses the cache of its conversation. When a run
runs them all and they pass (`verify --fast`, the end of turn, the
pre-push hook), it keeps their total and the longest one in a local file,
under `.socle/trace/`. Beyond the threshold, a warning, never a failure,
gives the total, the threshold and the longest step with its duration: at
the end of that run, on the line of a verification that does not run the
steps again, and in the state, as long as the last complete run exceeds
the threshold. The pre-push hook lets the push go and says it on its error
output, which the agent reads in that of `git push`. The end of turn does
not block for it: it tells the human, and tells the agent only when it
already blocks for another reason; otherwise the agent reads it at its
next `verify --fast` and in the state. A run where a step fails does not
replace the previous one. The CI prints the durations, without a
threshold: it runs on another machine. Lowering the threshold is free;
raising it, or writing `nan` in it, which no order compares, requires an
approved request.

**An adopted project** (installed with `--adoption`). The checks that
failed on the existing code are named in `[adoption] warn_only`, and the
findings present at installation in `[adoption.tolerated]`, per check,
under a key that depends neither on the line number nor on the language:
the file and what the finding cites (`"README.md — missing.md"` for a dead
link). Those stay warnings; any new finding of these checks fails.
Renaming a file that carries some is settled in the pull request that
renames it: the check fails and says to rename the key in the list, from
the old one to the new one, which the ratchet allows in the same pull
request. Only a rename that git recognizes is followed: commit the rename
alone, before editing the file; failing that, fix the finding, or tolerate
it through an approved request. A finding the CI no longer sees is reported: removing
it from the list is free, adding one requires an approved request that
cites it. The
state says, per check, how many findings adoption still tolerates; at zero,
the check can leave `warn_only`. A project adopted before this rule gets its
list when the engine is updated, made of the default branch's findings
(those born on the branch are not tolerated, the installer names them);
while it is missing, the state says the
check is entirely disarmed.
When the adoption finds no failing check, or the `warn_only` list is
empty on update, the installer says so in one line: nothing to enter.

**A journal from before the socle.** A project that already kept a
journal whose entries have the form of the socle's (`J-`, a date and a
letter) migrates it into `memory/journal/`, each entry in the file of
its month, in the socle's format; from the installation on, a new entry
is written in the socle's journal only. An imported entry keeps its
identifier, except on a day for which the socle's journal already has
its own (the day of the installation, which opens it): the imported
entries of that day take, in their order, the letters that follow the
last one of the socle's journal, and their citations are rewritten in
the same commit, except in the journal, the decisions and the requests,
which are not rewritten: the journal entry that records the migration
gives there the mapping of that day's letters. The old journal is
removed in that commit, or keeps only a pointer to `memory/journal/`:
otherwise its headings for a renumbered day would designate other
entries. Until the migration, the references check refuses the
identifier of an old entry, except on a day that clashes, where it
silently designates the socle's entry with the same letter: the
citations the project already has are tolerated at adoption (previous
paragraph), and those the migration resolves are then removed from the
list; a new citation, whatever its day, names it without the form of an
identifier, by its file, its date and its letter (“entry B of 3 March
2026 in the old journal”).

**A subfolder worked on by other agents.** When other agent sessions,
which have neither the socle's hooks nor its rules, work on a subfolder on
their own branches (a user interface, say), declare it third-party in the
guardrails (`[thirdparty] paths = ["ui/**"]`), then approve it: it is a
relaxation
(`python3 .socle/socle approve --keys thirdparty.paths --text "<reason>"`).
A commit that touches only third-party paths is then not a commit of the
project: declaring a third-party path also exempts from the hooks' trace
the commits that touch only it; a test exemption it carries is neither
judged nor read (it exempts no function of the project), and a fix there
is only warned about. Their pull requests pass the socle's CI job.
Nothing needs setting on GitHub, or in the pre-push hook, which those
sessions do not have: the socle's CI job, required before merging or not,
judges them this way. Two limits, each with its setting:

- a commit that also touches a file of the project (the memory, the
  documentation, a file at the root) is judged as a whole, and refused
  without the hooks' trace: those sessions stay in their subfolder;
- the adapter's capabilities (build, tests) run as it declares them: if
  they cover the subfolder, it must build and its tests pass, or the human
  excludes it from the adapter's sources, a protected file.

### Why these rules

The socle section of `AGENTS.md` and the socle's skills are loaded whole
at every use: they state the rule, and what justifies it is read here.

**The socle section of `AGENTS.md`.** If the state was not injected when a
Claude Code session started, its hooks are not loaded (the session started
outside the project root; `socle state` says so at the top, and the
pre-commit hook then refuses the commit). An instruction from the human is
also written in the journal: a compaction may lose it. A decision that
needs context is never put in the agent's question widget, where the human
reads raw text with no links to follow (the hook refuses it). A prototype
not meant to be merged is done on a disposable branch: the CI does not
judge it on push. Before concluding, `python3 .socle/socle verify --fast`
passes (the `Stop` hook checks it). The state computes what is up to the
human; the `Stop` hook refuses to conclude without the two lines. A file
to read, or a pull request, is given by its link: the human reads in the
conversation or on GitHub, not in the agent's container. What the agent
never does, hooks refuse: complete a head SHA, invent an identifier or a
reference: the hook refuses them; bypass a hook (`--no-verify`): the
agent's hook refuses it on the project's repository, and the CI runs
everything; ask the human a question in the agent's question widget: the
hook refuses it.

**The `socle-batch` skill.** A batch leaves only once its blocking
findings are fixed: once pushed, a decision and a journal entry are no
longer rewritten. The agent waits for the CI of the pushed commit
(`gh run list --commit <sha>`): the "CI" line of the state follows the
head.

**The `socle-resume` skill.** A usage limit of the account, over five
hours or seven days, cuts the session off; the agent then resumes only at
the human's next message: two wake-ups make it resume when the limit
lifts. A wake-up is never armed in the past: it would fire at once. A
reset read that is not more than a minute ahead belongs to a closed
window: the wake-up is then armed at the bound. During a wait with a
bounded time, the wake-ups remain, each pushed back after that time if it
fell before: refused, that turn resumes when the limit lifts. A turn cut
off or refused removes nothing: that is what makes it resume. The
wake-ups remain from one turn to the next: arming them at the start of
every turn and removing them at its end cost about one tool call in ten
of a sitting; a wake-up that fires with nothing to resume costs less, one
check and one line, and the check on waking makes it harmless. On waking
from work the human had interrupted, the agent says in one line that the
end-of-turn check refuses on failing checks, without touching it or
re-arming: relaunched on the same tree, it lets the turn conclude. The
human stops everything by writing "stop" in the session, or deletes the
wake-ups from the list of scheduled tasks of their account
(claude.ai/code/routines).

**The `socle-request` skill.** A request is read once the context is
lost: it stands on its own. The lines of its cited elements that carry
only a protected file to have approved, its path and its new fingerprint,
need no description and do not count in the request's budget. The human's
answer is recorded, committed and pushed at once: the human no longer sees
it pending. An answer is only relayed to a request pushed as is: the human
must have been able to read it. A request that the answer
`insufficient-context` sends back is rewritten as a new request that cites
it; the state then no longer says to rewrite it. Content the human
approves in session is first written in the repository, and the decision
designates it: without it, the decision keeps only the question and the
answer, and the content is lost.

**The `socle-handoff` skill.** The handoff is committed and pushed; the
next session, from one account or another, finds it and judges its guard.
The prompt to copy is the mode of whoever has several accounts or wants to
keep control. The scheduled session gets the work branch for
`outcome_branch`, without which the new session has nowhere to push. The
created session appears at once in the human's list of sessions, under its
title, ready for review while it waits for its wake-up. The wake-ups of
`socle-resume` remain, in both modes: a session cut off before tidying up
resumes when the limit lifts.
