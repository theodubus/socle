---
name: socle-batch
description: Run a batch of backlog topics, from forming it to delivering it: one subagent per topic, the review without context before any push, integration, CI, merge, one session per batch and the handover to the next. Use when the agent forms or announces a batch, at each of its steps, and when resuming a batch in progress.
---

# Running a batch

A batch gathers ready topics that are handled together: those that touch
the same files, the same guardrail or the same tests, which one review
will judge together. The agent running it orchestrates: it announces,
delegates, has the work reviewed, integrates and delivers; it implements
itself only a change of a few lines.

## Forming and announcing

1. The next batch is in the state (`next batch`). Otherwise, form it: the
   ready topics of the next milestone and of high priority first, what
   fits in one session. It is kept in the backlog:
   `python3 .socle/socle new backlog "Batch …"`, then `form: batch` and
   `after:` its topics and the previous batch; its body says what brings
   them together and names what is not a topic.
2. Read each topic (`python3 .socle/socle show <ID>`), announce the batch
   to the human (the topics, their size, the milestone served), and set it
   `in progress`.
3. In a Claude Code cloud session, arm the wake-ups (skill
   `socle-resume`).
4. Start from a clean, pushed work branch.

## One subagent per topic

Under Claude Code: the `Agent` tool, in an isolated copy of the repository
(`isolation: "worktree"`), in the background; two at a time at most.
It does not have the conversation: its instructions read on their own.

```text
You implement a topic of this repository in your isolated copy. The
project's instructions apply. Start with: git merge --ff-only <work branch>
Topic: python3 .socle/socle show <ID>, then <the choice already made, where to look, the known traps>.
Deliver, in one commit, without pushing: the threat model of a guardrail
or the specification of an undecided design, first; the code and its
tests; the documentation touched; a journal entry; the topic checked and
closed if its criteria are met; python3 .socle/socle verify --fast.
Forbidden: pushing, touching a wake-up, writing a protected file, changing
an expected value or deleting a test (report it), fixing a neighbouring
defect (a backlog topic).
Report: the commit, what the tests prove, the choices, what remains.
```

**Without subagents**, the agent runs the batch alone, in the same order:
one topic after the other, one commit each, the review on the whole batch.

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
   commit that reuses its message. Two topics that took the same
   identifier: the second one integrated is renumbered; an identifier the
   default branch also took: `python3 .socle/socle renumber <ID>`.
2. Remove the isolated copy and its branch;
   `python3 .socle/socle verify --fast`.
3. Push; open the pull request if there is none, only one open. Wait for
   the CI of the head commit: the "CI" line of `python3 .socle/socle state`
   says `success` (or `failure`) on its short SHA, never on an earlier
   commit. An announced wait has its wake-up (under Claude Code,
   `send_later`) to come back to it.
4. The merge is the one the project's instructions give: by default, the
   human merges, and the next batch is added to the same pull request. If
   they let the agent merge its own: green CI on the head commit, review
   done, no pending request on its content, giving the expected head
   commit.
5. The active work and the journal are written before the merge, in the
   last commit of the pull request, with the batch's closure: its topics
   closed, it becomes `done`, then `python3 .socle/socle archive`. After
   the merge, the local branch restarts from the default branch and is
   pushed only with the first commit of the next batch: pushed with
   nothing more, it would recreate the remote branch the merge deleted.

## Consumption

Each step of the orchestration (launching a subagent, receiving its
report, integrating, checking the CI) rereads the whole conversation, and
resuming after more than an hour's pause rereads it at full price.

- One batch per session: the orchestrating conversation stays short.
- Two subagents at a time at most; only one beyond 75% of the week; none
  beyond 85% of the week or 60% of the five-hour window: finish the step
  in progress, then change sessions. Under Claude Code in a cloud session,
  both windows are read in `list_events` (`kinds: ["rate_limit_event"]`,
  `utilization` of `five_hour` and of `seven_day`), before each launch and
  at each report.
- A nearby limit changes the order of topics, never the depth of the work
  on one of them: a topic that needs more thought is started anyway, and
  finished after the reset.
- A subagent is not resumed after more than five minutes' pause: a new one
  receives the instructions and the findings.
- A wait of more than an hour (a long CI, an answer from the human, the
  night) is not done in a long conversation.

## Changing sessions

When the batch is delivered and the five-hour window does not allow
running another one whole, or a wait of more than an hour is coming. Tidy
up first, so that a new session restarts from the repository alone:

1. nothing that lives only in the container: everything is pushed, and a
   commit not yet reviewed leaves as a patch (`git format-patch`) in a
   handover folder of the repository, removed when the batch is
   integrated;
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
The batch: <the state's batch, its topics in order>, following the socle-batch skill.
What is waiting: <a report, a CI, a request> | nothing.
```
