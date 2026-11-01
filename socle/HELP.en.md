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
   the default branch already contains, to delete, and those that have not
   moved for a week without being merged, to deliver or to delete.
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
each open question as a request, each task as a backlog topic, with its
what it waits on (`after`: another topic, or a request until it is
answered) and what makes it done (a “Done when” section, as checkboxes,
all checked before closing it), grouped in milestones. It submits each
document as a request. Just ask it to; the state then gives the next
milestone and the ready topics.

**Prioritising.** A topic can carry `priority: high` or `priority: low`;
the normal one is not written. Telling the agent is enough, and it does
not change a priority the human gave. The ready topics are sorted by
priority, and the low-priority ones stay apart: the agent takes them only
when convenient, and says so when announcing the batch.

**Delivering.** By default, the agent does everything on one development
branch and keeps only one pull request open, to which each finished batch
is added: merge it whenever you want, once its CI is green. One pull
request per topic, each to merge, is chosen in the starting questions, or
later by telling the agent, which writes it as a fact of the memory.

**Chaining.** As long as nothing is up to the human, the agent chains the
ready topics without waiting for a message. Before starting, it announces
the batch it will work on: stopping or redirecting it takes one message.
It stops at the end of the batch, or as soon as a decision is up to the
human.

Each intervention of the agent that acted ends with two lines:

- **"For you:"** — what is up to the human: a request to read, an action
  to take, or nothing;
- **"Next:"** — what comes next, and what the agent is waiting for.

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
own and ends with the list of possible answers. Answer in the
conversation; the agent records the answer word for word.

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
publishing, setting up a service: the agent records it in the backlog with
how to do it, and the state lists it under what is up to the human.

**Committing oneself.** The same checks apply: a public function added is
named by a test, or waived in the commit message
(`Waive-test: f — <reason>`); a fix brings a test that fails on the
previous commit.

**Updating the socle.** Run the installation command again from an
up-to-date clone of the engine (`git clone --depth 1
https://github.com/theodubus/socle /tmp/socle`). The project's files are never overwritten;
the diff of the policy is shown. Then approve the changed protected files
(`socle approve`), and commit. In a cloud session, with no terminal, the
agent puts a request that cites each changed protected file with its
fingerprint, and the human approves it in the conversation. The engine's
public repository is cloned without being added to the session; a session
that had to add a second repository is not resumed: it installs, commits,
pushes and opens the pull request in one go, and the request is put in a
new session on the project's repository alone.

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
| `tests.attendus` | an expected value changed, or a test disappeared | approve a request that names the test, or restore the test |
| `tests.code-teste` | a public function without a test | write the test, or `Waive-test:` in the commit |
| `tests.regression` | a fix without a test that proves it | write that test; if its proof depends on the environment, approve a request that names the commit |
| `docs.correspondance` | code changed without its documentation | update the documentation, or `Waive-doc:` in the commit |
| `mutation.vivante` | the weekly sweep no longer runs | re-enable it in GitHub's Actions tab |
| push refused, review | the policy requires a review | review what goes out, give one's agreement |

## Reference

### The autonomy policy

`.socle/policy.toml`, modified by the human only:

1. Loosening a guardrail requires an approved request; tightening is free.
2. Deleting a test or changing an expected value requires an approved
   request.
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
third-party files (those of a tool installed in the project). Tightening them is free;
loosening them requires an approved request.
