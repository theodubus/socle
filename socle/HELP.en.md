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
session that installs started before the socle, hence without its hooks:
it pushes its branch and opens a pull request. Once that is merged, the
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
[adapters specification](adapters/README.md)).

Right after the installation:

1. Describe the project:
   `python3 .socle/socle init --brief <document> --repo`. The brief is
   archived; `--repo` surveys what the repository already holds. Without a
   document, `--repo` alone; in an empty repository, no option.
2. Give the agent the tools the CI installs for the adapter (pytest, for
   instance), which the installer quotes with their commands. In a cloud
   session, the container starts from scratch at every session: the
   socle's start-up hook installs them in every new session; only the
   session that installs the socle installs them itself. As long as the
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
receives the project's state; it works, and the checks verify it at each
step.

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
context, who tries to find fault with it: what breaks, what no test
proves, what contradicts a decision. The agent fixes each founded finding
and dismisses the others; its recap says how many.

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
command is reserved to the human.

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
