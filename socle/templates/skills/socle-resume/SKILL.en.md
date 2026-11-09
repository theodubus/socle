---
name: socle-resume
description: Have the agent that a usage limit cuts off resume on its own, through two wake-ups scheduled on its own session, without ever restarting an agent that nothing cut off. Use in a Claude Code cloud session, at the start and the end of every turn where the agent acts, at every step, and when a message starts with "Resume after limit".
---

# Resuming after a usage limit

A usage limit of the account, over five hours or over seven days, cuts the
session off; cut off, the agent resumes only at the human's next message.
Two wake-ups, messages the agent schedules for its own session, make it
resume as soon as the limit lifts. They live only during a turn that
works: a turn that ends for any reason other than a limit (waiting for the
human, for instance) never restarts the agent.

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
reset of its window, day or night, however full it is. The time:
`get_session` without argument gives the session's id; `list_events` with
`kinds: ["rate_limit_event"]` and `limit: 100`, going back with
`before_id` while nothing is found; in the most recent,
`rate_limit_info.unifiedWindows.five_hour.resetsAt` and
`….seven_day.resetsAt`, in seconds since 1970, UTC.

Their text, rewritten every time:

```text
Resume after limit (<window>) — <repository>, branch <branch>.
First of all: the check of the skill socle-resume.
Batch: <the topics>. Step: <what was under way, what remains>.
Subagents under way: <each: its id, its task, what it must return> | none.
```

## At the start of every turn where the agent acts

1. Read the time of the two resets.
2. Look for its wake-ups: `list_triggers` with `enabled: true` and
   `limit: 100`, following `next_cursor`, those with these two names whose
   `persistent_session_id` is this session.
3. Present, move it and rewrite its text: `update_trigger`, with
   `run_once_at` and `prompt`. Absent, arm it: `send_later`, with `at`
   (the reset plus five minutes), `name` and `message`. Never two wake-ups
   for the same window.

## At every step, and at every subagent launched or returned

Rewrite the text of both wake-ups (`update_trigger`), and move their time
if a window was reset during the turn.

## At the end of every turn

Before the final answer, if no subagent is still running, remove both
wake-ups (`delete_trigger`). If a subagent is running, leave them, their
text up to date: they stay until the turn that receives its result. A turn
cut off or refused removes nothing: that is what makes it resume. If the
turn goes on after removing them (an end-of-turn hook refuses to conclude,
for instance), re-arm them.

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
   and remove the wake-ups, or move them if a subagent is running.
3. Otherwise, resume the noted step. Every noted subagent whose result did
   not arrive: continue it with a message (`SendMessage`, to its id) if it
   still answers, otherwise relaunch it with its message as is. Re-arm the
   wake-ups, and go on as on "resume". The recap says so ("Resume after limit: cut off
   at <time>, resumed at <time>"), and so does a journal entry.

## What the agent never does

Arm a recurring wake-up, or outside a turn where it acts; resume without
the check; keep a wake-up at the end of a turn with no subagent running;
touch another session's wake-up. The human stops everything by writing
"stop" in the session; the wake-ups also appear in the list of scheduled
tasks of their account, where they can be deleted.
