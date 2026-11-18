---
name: socle-batch
description: Run a batch of backlog tasks, from forming it to delivering it: one subagent per task, the review without context before any push, integration, CI, merge, one session per batch. Use when the agent forms or announces a batch, at each of its steps, and when resuming a batch in progress.
---

# Running a batch

A batch gathers ready tasks that are handled together: those that touch
the same files, the same guardrail or the same tests, which one review
judges. The agent running it orchestrates: it announces,
delegates, has the work reviewed, integrates and delivers; it implements
itself only a change of a few lines.

## Forming and announcing

1. The next batch is in the state (`next batch`). Otherwise, form it
   over the whole open backlog, without asking: the ready tasks its rule
   applies to, those of the next milestone and of high priority first,
   what fits in one session; a need to split gets its tasks first. The
   rest, like a task opened later, goes to the next batch not yet in
   progress whose rule applies; the recap states each placement. It is
   kept in the backlog: `python3 .socle/socle new batch "Batch …"`, then
   `after:` the previous batch and its tasks; its body says what brings
   them together.
2. Read each task (`python3 .socle/socle show <ID>`), announce the batch
   to the human (the tasks, their size, the milestone served), and set it
   `in progress`.
3. In a Claude Code cloud session, arm the wake-ups (skill
   `socle-resume`).
4. Start from a clean, pushed work branch.

## One subagent per task

Under Claude Code: the `Agent` tool, in an isolated copy of the repository
(`isolation: "worktree"`), in the background; two at a time at most.
It does not have the conversation: its instructions read on their own.

```text
You implement a task of this repository in your isolated copy. The
project's instructions apply. Start with: git merge --ff-only <work branch>
Task: python3 .socle/socle show <ID>, then <the choice already made, where to look, the known traps>.
Deliver, in one commit, without pushing: the threat model of a guardrail
or the specification of an undecided design, first; the code and its
tests; the documentation touched; a journal entry; the task checked and
closed if its criteria are met; python3 .socle/socle verify --fast.
Forbidden: pushing, touching a wake-up, writing a protected file, changing
an expected value or deleting a test (report it), fixing a neighbouring
defect (a need in the backlog).
Report: your model, the commit, what the tests prove, the choices, what remains.
```

**Without subagents**, the agent runs the batch alone: one task after
the other, one commit each, the review on the whole batch.

## The review, before any push

Skill `socle-review`, on the committed batch. A blocking finding goes back
to the subagent that implemented, if it still answers, otherwise to a new
one that receives the instructions and the finding; the rest goes to the
backlog. A batch leaves only once its blocking findings are fixed: once
pushed, a decision, a journal entry and an expected value are no longer
rewritten.

## Integrating, pushing, delivering

1. On the work branch: `git merge --ff-only` of the subagent's branch if
   its commit follows the head, otherwise `git merge --squash`, then a
   commit that reuses its message. Two tasks that took the same
   identifier: the second one integrated is renumbered; an identifier the
   default branch also took: `python3 .socle/socle renumber <ID>`.
2. Remove the isolated copy and its branch;
   `python3 .socle/socle verify --fast`.
3. Push; open the pull request if there is none, only one open. Wait for
   the CI of the head commit: the "CI" line of `python3 .socle/socle state`
   says `success` (or `failure`) on its short SHA. An announced wait has
   its wake-up (under Claude Code, `send_later`).
4. The merge is the one the project's instructions give: by default, the
   human merges, and the next batch is added to the same pull request. If
   they let the agent merge its own: green CI on the head commit, review
   done, no pending request on its content, giving the expected head
   commit.
5. The active work and the journal are written before the merge, in the
   last commit of the pull request, with the batch's closure: its tasks
   closed and its step back written, it becomes `done`, then `python3 .socle/socle archive`; the closing
   recap pastes the output of `python3 .socle/socle roadmap` in a code block. After
   the merge, the local branch restarts from the default branch and is
   pushed only with the first commit of the next batch: pushed alone, it would recreate the deleted remote branch.

## Consumption

Each step of the orchestration rereads the whole conversation.

- One batch per session: the orchestrating conversation stays short.
- Only one subagent beyond 75% of the week; none
  beyond 85% of the week or 60% of the five-hour window: finish the step
  in progress, then change sessions. In a Claude Code cloud
  session, `list_events` gives them (`kinds: ["rate_limit_event"]`,
  `utilization`), before each launch and at each report.
- A nearby limit changes the order of tasks, never the depth of the work:
  a task that needs more thought is started anyway.
- A subagent is not resumed after more than five minutes' pause: a new one
  receives the instructions and the findings.
- A wait of more than an hour (a long CI, an answer from the human, the
  night) is not done in a long conversation.
- The agent does not compact by itself: it writes the memory (active
  work, journal), then asks the human to (under Claude Code, `/compact`),
  at the end of a batch if the human keeps the session beyond it, and
  before any wait that may exceed an hour without changing sessions. Near
  a limit, the
  threshold above prevails: change sessions. After the pause, it is too
  late: compacting would reread it at full price.
- The model: the one the quality of the work calls for, never a lesser
  one to stay within a limit: a limit delays a batch, it does not lighten
  it. Among those that do it equally well, the one that uses the least of
  the limit per token, above all for the orchestrating conversation; the human chooses the session's, on the agent's
  advice. The one set by the project's
  instructions prevails. A subagent receives its own explicitly at launch
  (`Agent` tool: `model`), on the latest version of its family: if the
  alias (`opus`…) designates an older one, without `model`, it inherits
  the session's; otherwise, tell the human. Its report and the recap name
  its model.

## Changing sessions

When the batch is delivered and the five-hour window does not allow
running another one whole, or a wait of more than an hour is coming. Tidy
up first, so that a new session restarts from the repository alone:

1. nothing that lives only in the container: everything is pushed, and a
   commit not yet reviewed leaves as a patch (`git format-patch`) in a
   handover folder of the repository, removed at its integration;
2. the isolated copies and their branches removed;
3. the active work, written before the merge, gives the batch and what is
   waiting (a report, a CI, a request);
4. in a cloud session, the wake-ups removed.

Then tell the human that sessions must change, and why, with the prompt
of the next one in a block to copy:

```text
Resume the work of this repository, in a new session.
First: read the state the startup injects; a "!! cut" line says what is
missing from it and where to read it. Then the active work, and apply them.
The batch: <the state's batch, its tasks in order>, following the socle-batch skill.
What is waiting: <a report, a CI, a request> | nothing.
```
