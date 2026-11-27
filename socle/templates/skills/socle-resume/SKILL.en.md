---
name: socle-resume
description: Have the agent that a usage limit cuts off resume on its own, through two wake-ups on its own session, without ever restarting an agent that nothing cut off. Use in a Claude Code cloud session, at the start of every turn where the agent acts, when launching a subagent, and when a message starts with "Resume after limit".
---

# Resuming after a usage limit

Two wake-ups, messages the agent schedules for its own session, make it
resume when a usage limit lifts. They remain from one turn to the next: a
wake-up that fires with nothing to resume, after a turn that ended for
another reason than a limit, is checked and told in one line; it
never restarts the agent.

## When

In a Claude Code cloud session only, where the tools `send_later`,
`update_trigger`, `delete_trigger`, `list_triggers` and `get_session`
exist. Elsewhere, this skill does not apply. A text-only answer touches
no wake-up; a turn where the agent runs a command, writes a file or
launches a subagent arms the missing one. A subagent
touches no wake-up: it neither arms, moves nor removes one.

## The two wake-ups

One per window, named "Resume after limit (five hours) — <repository>" and
"Resume after limit (week) — <repository>", each five minutes after the
reset of its window, day or night, however full it is.

The time of the reset: `list_events` with `kinds: ["rate_limit_event"]`
and `limit: 100` (the session's id: `get_session` without
argument), going back with `before_id` while nothing is found; in the most recent,
`rate_limit_info.unifiedWindows.five_hour.resetsAt` and
`….seven_day.resetsAt`, in seconds since 1970, UTC. A time read earlier,
still to come, holds: it is not read again.

**Never in the past.** The current time: `date -u`, in the turn's first command, or the `now` that
`send_later` returns. A reset read that is not more than a minute ahead:
the wake-up is then armed at the bound, now
plus five hours and five minutes, or seven days and five minutes for the
week. A `send_later` whose armed time precedes its `now`: remove that
wake-up and re-arm it at the bound.

**Without the `list_events` tool**, `get_session` without argument
gives, when it carries `rate_limit_info`, the time of the only window
that `rateLimitType` names (`resetsAt`); the other wake-up is armed at
the bound. A wake-up at the bound is not pushed back to it, neither at
the start of a turn nor when launching a subagent: fired with nothing to
resume, it costs one check. `list_triggers` finds the wake-ups again.

Their text carries the batch and the subagents under way:

```text
Resume after limit (<window>) — <repository>, branch <branch>.
First of all: the check of the skill socle-resume.
Batch: <its tasks>.
Subagents under way: <each: its id, its task, what it must return> | none.
```

## At the start of every turn where the agent acts

Once, before or with its first action:

1. The wake-ups left by an earlier turn, its conversation shows them,
   with their `trigger_id`. At the session's first turn, or lost to a
   compaction: `list_triggers` with `enabled: true` and `limit: 100`;
   those with these two names whose `persistent_session_id` is this
   session are its own. Those of an archived session (`get_session`:
   `SESSION_STATUS_ARCHIVED`) are told to the human with their times, and
   are disabled (`update_trigger`, `enabled: false`) only at their
   request. A handoff that is waiting ("Handoff — <repository>") likewise.
   The turn that opens, on a message from the human as on a
   wake-up, makes the wake-ups left its own; the one that fired, spent,
   is missing. A wake-up left at the right time, for the same batch, is
   not touched: the turn calls no wake-up tool. The one whose time
   changes gets, in a single call, its new time and the text of its batch
   (`update_trigger`, with `run_once_at` and `prompt`); the one whose
   time is right gets the text only if the batch changed.
2. The missing wake-up is armed: `send_later`, with `at` (the reset plus
   five minutes, never in the past), `name` and `message`. Never two
   wake-ups for the same window.

## When launching a subagent

Rewrite the text of both wake-ups (`update_trigger`, with `prompt`), once
for the subagents launched together, when their ids are known.

## At the end of every turn

The wake-ups remain: the end of a turn removes none. During a wait with
a bounded time (a reminder, a background command, a CI), until the
event's turn, each is pushed back after that time if it fell before. A
turn cut off or refused removes nothing. They are removed
(`delete_trigger`) only when a session that hands over tidies up, or
when the human says to stop.

## On waking: check first

A message that starts with "Resume after limit":

1. Read `list_events` with `kinds: ["result"]` and `limit: 100`: the
   last result before this wake-up closes the previous turn, whatever
   opened it; it ended on a limit if it is an error `usage_limit_reached`.
   Then, with `kinds: ["user", "assistant"]`, the messages that arrived
   since its last work, even refused: the human's are typed text, neither a tool result, nor a
   wake-up, nor a notification; a resume message from the application
   (`text_not_typed`) counts as "resume".
   **Without `list_events`**, the local transcript tells: the most recent
   `.jsonl` of the project under `~/.claude/projects/`, read from its end
   (`tail`). The cut is the first `quotaLimits` record that follows the
   model's last call, at its `timestamp`; every typed `user` record
   (`origin.kind` set to `human`) that follows it is the human's, even if
   another refusal follows, like the one that provoked it. Without a
   transcript, or without the previous turn in it (a replaced container),
   the conversation: the previous turn
   cut off short, with no recap nor interruption nor message from the
   human since, the agent resumes; otherwise, not. A message refused
   during the limit may be missing there: the first answer says so at its
   top, for the human to repeat it.
2. Do not resume:
   - if the previous turn did not end on a limit (the human interrupted
     it, or it ended normally);
   - if the human wrote during the limit: answer their message, which comes
     first; if it says to stop, stop, the wake-ups removed;
   - if the guard refuses: `git fetch`, then `python3 .socle/socle handoff
     check --ref origin/<branch> --head <its head before the fetch> --since
     <the cut, if known>`;
   - if the branch's pull request was merged or closed since.

   Then answer why in one line, then the project's closing lines,
   without resuming the work: the remaining wake-up stays, and this answer
   arms nothing.
   If the human had interrupted the work and the end-of-turn check
   refuses on failing checks, say so in one line, without touching it or
   re-arming.
3. Otherwise, resume the noted batch, at the step the conversation, git,
   the active work and the worktrees tell. Every noted subagent whose
   result did not arrive: continue it with a message (`SendMessage`, to
   its id) if it still answers, otherwise relaunch it with its message as
   is. The recap says so ("Resume after limit: cut
   off at <time>, resumed at <time>"; without `list_events`, the time from
   the transcript, else "cut off at an unknown time"), and so does the
   journal.

## What the agent never does

Arm a recurring wake-up; rewrite a wake-up at every step; touch another
session's wake-up without the human asking; the human finds the
wake-ups in the list of scheduled tasks of their account
(claude.ai/code/routines).
