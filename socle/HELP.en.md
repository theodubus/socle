# The socle, on the human's side: user guide

This guide follows the human's path in a project equipped with the socle,
from the end of the installation to everyday use. Commands run at the
project root: `python3 .socle/socle <command>`; this guide is shown by
`python3 .socle/socle help`. Without a terminal, in a cloud session, the
agent runs them: just ask it to.

The path in short:

1. **Getting started**, once: describe the project, give the agent its
   tools, push, protect the branch.
2. **Working with the agent**: give it tasks, read its recaps.
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
   Without it, a red CI does not prevent merging. The code owners' review
   is added only if another human reviews: the author of a pull request
   cannot approve it, and the agent opens its own under the human's name.
   In the general settings, tick "Automatically delete head branches": a
   merged branch then deletes itself. The state reports the others: those
   the default branch or the pushed working branch already contains, to
   delete, and those that have not
   moved for a week without being merged, to deliver or to delete. If such a
   branch alone keeps a commit the memory cites, the state first gives the
   command that tags it: without it, CI would no longer find it.
5. Open the agent in the project. It reads the state at start-up, then
   gives the link of the starting questions, a request that `socle init`
   put: answer it in the conversation, `approve` to apply all the defaults,
   or one answer per question.

If the project already had its own `SessionStart` hook, the installer
points it out: remove it from `.claude/settings.json`, otherwise each
session receives two states.

## 2. Working with the agent

Tasks are given to the agent as usual. At the start of each session, it
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
intention is missing, section 3), each task as a backlog topic, with its
what it waits on (`after`: another topic, or a request until it is
answered) and what makes it done (a “Done when” section, as checkboxes,
all checked before closing it), grouped in milestones. It submits each
document as a request. Just ask it to; the state then gives the next
milestone and the ready topics.

**Specifications and test cases.** The project declares where its
specifications live (`[specs] paths` in the guardrails): the state tells
you about any that no request has submitted to you. It also declares its
case files (`[tests] case_paths`), data where its tests read their
expected results: adding a case is free, but changing or removing an
existing case requires your approval, like an expected value written in a
test.

**Prioritising.** A topic can carry `priority: high` or `priority: low`;
the normal one is not written. Telling the agent is enough, and it does
not change a priority the human gave. The ready topics are sorted by
priority, and the low-priority ones stay apart: the agent takes them only
when convenient, and says so when announcing the batch.

**Chaining.** As long as nothing is up to the human, the agent chains the
ready topics without waiting for a message. Before starting, it announces
the batch it will work on: stopping or redirecting it takes one message.
It stops at the end of the batch, or as soon as a decision is up to the
human.

**Having it reviewed.** Before delivering a batch that changes code, a
specification or a test, the agent has it reviewed by a reviewer without
context, who tries to find fault with it against the “Done when”
criterion of the batch's topics and, for a guardrail, its threat model,
written before the code: what the guardrail stops, what it lets through.
The agent fixes the blocking findings in the batch (a contradicted
criterion, a regression, a data loss, a bypass within the threat model),
sends the others to the backlog, where you see them, and dismisses the
unfounded ones; its recap says how many.

**Delivering.** By default, the agent does everything on one development
branch and keeps only one pull request open, to which each finished batch
is added: merge it whenever you want, once its CI is green. One pull
request per topic, each to merge, is chosen in the starting questions, or
later by telling the agent, which writes it as a fact of the memory.

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
and what your answer changes.

At any time, `python3 .socle/socle state` gives the project's state: the
commit, the CI, the backlog and what comes next (the next milestone, the
ready topics), the pending requests, what is up to the human.
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
project, the work in progress and the question. An agent that has
subagents has it read cold, by one of them that only has its text, before
asking you, and its recap gives the outcome. It ends with the list of
possible answers. Answer in the conversation; the agent records the answer
word for word.

- The base answers are the same in every request: `approve` (the
  recommendation), `reject`, `insufficient-context`; a choice request adds
  its options.
- `approve` is the only answer that authorises an action reserved to the
  human.
- `insufficient-context` sends the request back to the agent, which
  rewrites it.
- From a terminal:
  `python3 .socle/socle answer D-NNNN <answer> --text "<text>"`.

**A question in session.** A short question, which the agent asks in the
text of its answer, is answered in the conversation; the agent records it
at once, word for word, like a request. What needs context, approving a
document included, comes as a request, with its link; never in the
agent's question widget, which the hook refuses.

**Framing questions.** When a topic's specification depends on an
intention the memory does not state, the agent asks open questions, each
with its assumption, in a request whose link it gives. Answer them
freely, in one or several messages (`answers`), or `approve` its
assumptions: it records the text as is, then submits the specification
that follows from it. Telling it "ask me your questions about this
topic" is enough to request them.

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
it by mistake (D-0098), Claude Code's settings excepted, which the human
keeps for themselves: `git restore --source=HEAD --staged --worktree --
<path>` or `git checkout HEAD -- <path>`, each path written out in full,
or `rm <path>` for a file that appeared under a protected path and that
git does not track. Anything else is refused to it: another commit, with
or without `--`, a whole folder, a shell pattern or variable, paths read
from a file, a variable or a prefix before `git`, a redirection to another
protected file, and a file that is cited, itself or its folder, by a
request pending or approved whose approved change is not committed yet.
The accepted risk: erasing a change of the human in the working tree that
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
if it can write: split it. This hook is only a first barrier against the
agent's mistakes: it does not model all of bash, some shell forms escape
it (an unknown part that is itself `..`, an option set by the shell's
profile, a variable Claude Code sets only for its hooks…), and the
guarantee is the protected-files check, at the end of the turn, at commit
and in CI.

**Doing what the agent cannot do.** Pushing to the default branch,
publishing, setting up a service, deleting a remote branch, setting a tag
(in a cloud session, the agent only pushes its own branch): the agent records it in the backlog with
how to do it, and the state lists it under what is up to the human.

**Committing oneself.** The same checks apply: a public function added is
named by a test, or waived in the commit message
(`Waive-test: f — <reason>`); a fix brings a test that fails on the
previous commit.

**Updating the socle.** Run the installation command again from an
up-to-date clone of the engine (`git clone --depth 1
https://github.com/theodubus/socle /tmp/socle`). The project's files are never overwritten;
the diff of the policy is shown. The agent's hook refuses the installer aimed
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
4. Follow the installer's "What now" steps, including the request that cites the changed protected files, then push and open the pull request.
5. Tell me what is up to me.
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
4. An irreversible or external action is always asked for.
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
