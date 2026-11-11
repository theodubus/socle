---
name: socle-resume
description: Have the agent that a usage limit cuts off resume on its own, through two wake-ups scheduled on its own session, armed once per turn, without ever restarting an agent that nothing cut off. Use in a Claude Code cloud session, at the start and the end of every turn where the agent acts, when launching a subagent, and when a message starts with "Resume after limit".
---

# Resuming after a usage limit

A usage limit of the account, over five hours or over seven days, cuts the
session off; cut off, the agent resumes only at the human's next message.
Two wake-ups, messages the agent schedules for its own session, make it
resume as soon as the limit lifts. They live only during a turn that
works: a turn that ends for any reason other than a limit (waiting for the
human, for instance) never restarts the agent. Every call costs usage:
the procedure makes as few as it can, four or five per turn.

## When

In a Claude Code cloud session only, where the tools `send_later`,
`update_trigger`, `delete_trigger`, `list_triggers`, `list_events` and
`get_session` exist (server `claude-code-remote`). Elsewhere, this skill
does not apply. A text-only answer arms nothing; a turn where the agent
runs a command, writes a file or launches a subagent arms. A subagent
touches no wake-up: it neither arms, moves nor removes one.

## The two wake-ups

One per window, named "Resume after limit (five hours) — <repository>" and
"Resume after limit (week) — <repository>", each five minutes after the
reset of its window, day or night, however full it is.

The time of the reset: `list_events` with `kinds: ["rate_limit_event"]`
and `limit: 100` (the session's id is in its link, `…/code/session_…`,
otherwise `get_session` without argument gives it), going back with
`before_id` while nothing is found; in the most recent,
`rate_limit_info.unifiedWindows.five_hour.resetsAt` and
`….seven_day.resetsAt`, in seconds since 1970, UTC. A time read earlier in
the conversation, still to come, still holds: a window does not reset
before its time, and it is not read again.

**Never in the past.** A wake-up armed at a past time fires at once. The
current time is read by `date -u` (in the turn's first command);
`send_later` returns it too (`now`). A reset read that is not more than a
minute ahead belongs to a closed window: the wake-up is then armed at the
bound, now plus five hours and five minutes for the five-hour window,
plus seven days and five minutes for the week, late but never wrong. A
`send_later` result whose armed time precedes `now`: remove that wake-up
and re-arm it at the bound.

Their text carries what the agent finds nowhere else: the batch, and the
subagents under way. The step it finds in its conversation, in git, in
the active work and in the list of worktrees.

```text
Resume after limit (<window>) — <repository>, branch <branch>.
First of all: the check of the skill socle-resume.
Batch: <the topics>.
Subagents under way: <each: its id, its task, what it must return> | none.
```

## At the start of every turn where the agent acts

Once, before or with its first action:

1. The wake-ups left by an earlier turn, its conversation shows them,
   with their `trigger_id` (after a compaction that lost them:
   `list_triggers` with `enabled: true` and `limit: 100`, those with these
   two names whose `persistent_session_id` is this session). If some
   remain, the turn that opens, on a message from the human as on a
   wake-up, makes them its own: the cut they guarded is over, and a
   wake-up of an elapsed window, left as is, would restart the agent for
   nothing. A wake-up left behind also keeps the text of the earlier
   batch, which would resume the old batch if this turn were cut: the
   one to move gets, in the same call, this turn's time and the text of
   its batch (`update_trigger`, with `run_once_at` and `prompt`); the one
   whose time is still right gets it, through the same call, only if the
   batch changed, and otherwise stays without a call.
2. The missing wake-up is armed: `send_later`, with `at` (the reset plus
   five minutes, never in the past), `name` and `message`. Never two
   wake-ups for the same window.

Then, nothing at each step: neither rewriting their text nor reading the
time again.

## When launching a subagent

Rewrite the text of both wake-ups (`update_trigger`, with `prompt`), once
for the subagents launched together, when their ids are known. A subagent
that returns asks for nothing: the conversation tells the agent its result
arrived.

## At the end of every turn

Before the final answer, if no subagent is still running, remove both
wake-ups (`delete_trigger`). If a subagent is running, leave them: they
stay until the turn that receives its result. A turn cut off or refused
removes nothing: that is what makes it resume. If the turn goes on after
removing them (an end-of-turn hook refuses to conclude, for instance),
re-arm them. A text-only turn that finds wake-ups left by an earlier turn
removes them likewise.

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
   off at <time>, resumed at <time>"), and so does a journal entry.

## What the agent never does

Arm a recurring wake-up, one in the past, or one outside a turn where it
acts; rewrite it at every step; resume without the check; keep a wake-up
at the end of a turn with no subagent running; touch another session's
wake-up. The human stops everything by writing "stop" in the session; the
wake-ups also appear in the list of scheduled tasks of their account,
where they can be deleted.
