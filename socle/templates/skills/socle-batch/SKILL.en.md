---
name: socle-batch
description: Run a batch of backlog tasks, from its announcement to its delivery. Use when the agent forms or announces a batch, at each of its steps, and when resuming it.
---

# Running a batch

A batch gathers ready tasks that one review judges: those that touch
the same files, the same guardrail or the same tests. The agent running
it orchestrates; it implements itself only a small task.

## Forming and announcing

1. The next batch is in the state (`next batch`). Otherwise, form it
   over the whole open backlog, without asking: the ready tasks its rule
   applies to, those of the next milestone and of high priority first; a
   need to split gets its tasks first; a task that changes a behaviour
   names the test that asserts the opposite, its request made at once,
   before the batch; the rest goes to the next batch
   not in progress whose rule applies, and the recap states each
   placement. It is kept in the backlog: `python3 .socle/socle new batch
   "Batch …"`, then `after:` the previous batch and its tasks; its body
   says what brings them together. A whole that one session does not
   carry through is formed as a milestone, its batches under it.
2. Read each task (`python3 .socle/socle show <ID>`) and estimate the
   batch's cost: if it does not fit in what remains of the window, split
   it, start with a smaller batch or wait for the reset. Announce the
   batch to the human (the tasks, their size, the milestone served, the
   estimated cost), and set it `in progress`.
3. In a cloud session, arm the wake-ups (skill `socle-resume`).
4. Start from a clean, pushed work branch.

## One subagent per task

Under Claude Code: the `Agent` tool, in an isolated copy of the repository
(`isolation: "worktree"`), in the background; two at a time at most.
Without the conversation, its instructions read on their own.

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
Economy: read what serves, not whole files; no full suite rerun without reason.
Report: your model, the commit, what the tests prove, the choices, what remains.
```

**A small task**, under 150 lines of code and tests (a provisional
threshold, to be measured), is implemented in the
orchestrating session, unless it touches a guardrail or a format that
other parts of the project read.
**Without subagents**, the agent runs the batch alone: one task after
the other, one commit each, the review on the whole batch.

## The review, before any push

Skill `socle-review`, on the committed batch, and its sorting of the
findings. A blocking finding goes back to whoever implemented, if it
still answers, otherwise to a new subagent, with the instructions and the
finding: a subagent stopped for more than five minutes is not resumed. A
batch leaves only once its blocking findings are fixed: once pushed, a
decision, a journal entry and an expected value are no longer rewritten.

## Integrating, pushing, delivering

1. On the work branch: `git merge --ff-only` of the subagent's branch if
   its commit follows the head, otherwise `git merge --squash`, then a
   commit that reuses its message. An identifier taken twice:
   `python3 .socle/socle renumber <ID>` on the second.
2. Remove the isolated copy and its branch;
   `python3 .socle/socle verify --fast`.
3. Push; open the pull request if there is none, only one open. Wait for
   the CI of the head commit: the "CI" line of `python3 .socle/socle state`
   says `success` (or `failure`) on its short SHA. An announced wait has
   its wake-up in a cloud session (`send_later`); elsewhere, `Next:` says
   so, and the human restarts the agent.
4. Who merges: by default the human, and the next batch is added to the
   same pull request; the agent, its own, if the policy allows it: green
   CI on the head commit, which it gives, review done, no pending request
   on its content. It then waits likewise for the workflows the merge
   starts on the default branch; the recap says whether they succeeded.
5. The active work and the journal are written before the merge, in the
   last commit of the pull request, with the batch's closure: its tasks
   closed, it becomes `done`, then `python3 .socle/socle archive`; a task
   its review opens joins the next batch whose rule applies, otherwise a
   new batch in its need's milestone; the closing recap pastes the output of `python3
   .socle/socle roadmap` in a code block. After the merge, the local
   branch restarts from the default branch and is pushed only with the
   first commit of the next batch: pushed alone, it would recreate the
   deleted remote branch.

## Consumption

- One batch per session: the orchestrating conversation stays short.
- Costs are measured: the use of each window, before each launch and at
  each report (skill `socle-resume`). The closure notes in the journal the cost of each
  subagent, of the reviewer, of each request and of the tidying up: a
  batch's cost is estimated on these measures.
- Only one subagent beyond 75% of the week. A subagent is launched if
  what remains of each window covers its measured cost and that of the
  tidying up; without a measure, none beyond 85% of the week or 60% of
  the five-hour window. The tidying up starts at the latest ten points
  from a limit: finish the step in progress, then change sessions.
- The agent does not compact by itself: it writes the memory (active
  work, journal), then asks the human to (`/compact`), at the end of a
  batch if the human keeps the session, and before any wait
  that may exceed an hour without changing sessions. Near a limit, the
  threshold above prevails: change sessions. After the pause, it is too
  late. Without the human to compact, the agent does not wait for them: it
  changes sessions.
- A nearby limit changes the order of tasks, never the depth of the work
  (a task that needs more thought is started anyway) nor the model: the one the quality of the work calls for, never a
  lesser one to stay within a limit: a limit delays a batch, it does not
  lighten it. Among those that do it equally well, the one that uses the
  least of the limit per token; the human chooses the session's, on the
  agent's advice. The one set by the project's instructions prevails. A
  subagent receives its own explicitly at launch (`model`), never Fable
  unless the human wants it, the latest version of its family (an alias that designates an older one: without
  `model`, it inherits the session's; otherwise, tell the human), named
  in the recap.

## Changing sessions

At the end of the batch, near a limit or before a wait of more than an
hour (the moment: the `socle-handoff` skill). Tidy up first:

1. the active work gives the batch and what is waiting, the journal the
   handoff;
2. the isolated copies, their branches and, in a cloud session, the
   wake-ups removed;
3. everything is pushed; a commit not reviewed leaves as a patch
   (`git format-patch`) in a handover folder of the repository, removed
   at its integration. Nothing is pushed afterwards.

Then the `socle-handoff` skill: depending on the mode, it schedules the
next session, or gives the prompt of the next one to copy.
