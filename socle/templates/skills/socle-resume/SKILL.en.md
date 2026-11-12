---
name: socle-resume
description: Have the agent that a usage limit cuts off resume on its own, through two wake-ups scheduled on its own session, armed once per turn, without ever restarting an agent that nothing cut off. Use in a Claude Code cloud session, at the start and the end of every turn where the agent acts, when launching a subagent, and when a message starts with "Resume after limit".
---

# Resuming after a usage limit

A usage limit of the account, over five hours or seven days, cuts the
session off; the agent then resumes only at the human's next message.
Two wake-ups, messages the agent schedules for its own session, make it
resume when the limit lifts. They live only during a turn that works: a
turn that ends for another reason than a limit never restarts the agent.
Every call costs usage: four or five per turn.

## When

In a Claude Code cloud session only, where the tools `send_later`,
`update_trigger`, `delete_trigger`, `list_triggers` and `get_session`
exist (server `claude-code-remote`). Elsewhere, this skill
does not apply. A text-only answer arms nothing; a turn where the agent
runs a command, writes a file or launches a subagent arms. A subagent
touches no wake-up: it neither arms, moves nor removes one.

## The two wake-ups

One per window, named "Resume after limit (five hours) — <repository>" and
"Resume after limit (week) — <repository>", each five minutes after the
reset of its window, day or night, however full it is.

The time of the reset: `list_events` with `kinds: ["rate_limit_event"]`
and `limit: 100` (the session's id: its link, `…/code/session_…`, or
`get_session` without argument), going back with
`before_id` while nothing is found; in the most recent,
`rate_limit_info.unifiedWindows.five_hour.resetsAt` and
`….seven_day.resetsAt`, in seconds since 1970, UTC. A time read earlier,
still to come, still holds: it is not read again.

**Never in the past.** A wake-up armed at a past time fires at once. The
current time is read by `date -u` (in the turn's first command);
`send_later` returns it too (`now`). A reset read that is not more than a
minute ahead belongs to a closed window: the wake-up is then armed at the
bound, now plus five hours and five minutes for the five-hour window,
plus seven days and five minutes for the week, late but never wrong. A
`send_later` result whose armed time precedes `now`: remove that wake-up
and re-arm it at the bound.

**Without the `list_events` tool**, every wake-up is armed at the bound,
and the five-hour one, whose window began no one knows when, is pushed
back to it at the start of every turn where the agent acts and when
launching a subagent (`run_once_at`, in the planned call). It falls after
the limit lifts as long as no window restarted between that push and the
cut; otherwise it fires too early and is lost. `list_triggers` finds the
wake-ups again.

Their text carries what the agent finds nowhere else: the batch, and the
subagents under way. The step it finds in its conversation, git, the
active work and the worktrees.

```text
Resume after limit (<window>) — <repository>, branch <branch>.
First of all: the check of the skill socle-resume.
Batch: <the topics>.
Subagents under way: <each: its id, its task, what it must return> | none.
```

## At the start of every turn where the agent acts

Once, before or with its first action:

1. The wake-ups left by an earlier turn, its conversation shows them,
   with their `trigger_id` (lost to a compaction: `list_triggers` with
   `enabled: true` and `limit: 100`, those with these two names whose
   `persistent_session_id` is this session). The turn that opens,
   on a message from the human as on a wake-up, makes them its own: the
   cut they guarded is over, and a wake-up of an elapsed window would
   restart the agent for nothing; its text, the earlier batch's, would
   resume the old batch. The one to move gets, in a single call, this
   turn's time and the text of its batch (`update_trigger`, with
   `run_once_at` and `prompt`); the one whose time is right gets the
   text, from the same call, only if the batch changed.
2. The missing wake-up is armed: `send_later`, with `at` (the reset plus
   five minutes, never in the past), `name` and `message`. Never two
   wake-ups for the same window.

## When launching a subagent

Rewrite the text of both wake-ups (`update_trigger`, with `prompt`), once
for the subagents launched together, when their ids are known. A subagent
that returns asks for nothing: the conversation says so.

## At the end of every turn

Before the final answer, if no subagent is running, remove both wake-ups
(`delete_trigger`); otherwise leave them until the turn that receives its
result. A turn cut off or refused removes nothing: that is what makes it
resume. If the turn goes on after (an end-of-turn hook refuses to
conclude), re-arm them. A text-only turn likewise removes the wake-ups
left by an earlier turn.

## On waking: check first

A message that starts with "Resume after limit":

1. Read `list_events` with `kinds: ["result"]` and `limit: 100`: the
   last result before this wake-up closes the previous turn, whatever
   opened it (a message from the human, a subagent's result, another
   wake-up); it ended on a limit if it is an error `usage_limit_reached`.
   Then, with `kinds: ["user"]`, the messages that arrived since the cut,
   even refused: the human's are typed text, neither a tool result, nor a
   wake-up, nor a notification; a resume message from the application
   (`text_not_typed`) counts as "resume".
   **Without `list_events`**, the conversation alone tells: the previous
   turn cut off short, with no closing recap nor interruption by the
   human, and no message from them since, the agent resumes; otherwise,
   it does not resume the old work. A message refused during the limit
   cannot be read there: the first answer says so at its top, so that the
   human repeats it.
2. Do not resume:
   - if the previous turn did not end on a limit (the human interrupted
     it, or it ended normally);
   - if the human wrote since the cut: answer their message, which comes
     first; if it says to stop, stop;
   - if another session pushed to the branch since the agent's last
     commit (`git fetch`, then compare);
   - if the branch's pull request was merged or closed since.

   Then answer briefly why, with the closing lines the project requires,
   and remove the remaining wake-up, or leave it if a subagent is running.
3. Otherwise, resume the noted batch, at the step the conversation, git,
   the active work and the worktrees tell. Every noted subagent whose
   result did not arrive: continue it with a message (`SendMessage`, to
   its id) if it still answers, otherwise relaunch it with its message as
   is. The wake-up that fired will not fire again: the start of the turn
   re-arms it, as on "resume". The recap says so ("Resume after limit: cut
   off at <time>, resumed at <time>"; without `list_events`, "cut off at an
   unknown time"), and so does the journal.

## What the agent never does

Arm a recurring wake-up, one in the past, or one outside a turn where it
acts; rewrite it at every step; resume without the check; keep a wake-up
at the end of a turn with no subagent running; touch another session's
wake-up. The human stops everything by writing "stop" in the session, or
deletes the wake-ups from the list of scheduled tasks of their account.
