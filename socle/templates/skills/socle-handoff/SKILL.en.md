---
name: socle-handoff
description: Hand over to a new session, at the end of a batch, near a usage limit or before a long wait — schedule it yourself or give the prompt to copy, depending on the mode, with the guard against duplicated work. Use it after the tidying up of socle-batch, when the human changes the mode, and when a session starts from a handoff prompt.
---

# Handing over to a new session

A session runs only one batch. When it stops, the next one restarts from
the repository alone, on a handoff prompt that `python3 .socle/socle
handoff prompt` writes with its guard. The prompt's times are in UTC;
those the human reads, in their own time.

## The two modes

- **Scheduled session**, by default: the agent creates the next session
  and schedules its prompt.
- **Prompt to copy**: the agent gives the prompt in its recap, and the
  human opens the session themselves; the mode of whoever has several
  accounts or wants to keep control.

The mode is the one an instruction in the active work states; without
one, the scheduled session. The human changes it by saying so: the agent
writes the instruction in the active work, and its exact text in the
journal. Switching to the prompt to copy cancels what is scheduled, the
task deleted (`delete_trigger`) and the created session archived
(`archive_session`), and says so, with the link of each cancelled
session.

The prompt to copy also applies, the recap saying why, outside a Claude
Code cloud session (without `create_session` or `create_trigger`), and
at a bound.

## The moment

| The moment | The time of the next session |
| --- | --- |
| Batch delivered | right away: the next minute |
| Tidying up ten points from a limit (`socle-batch`) | the reset of that window, plus five minutes |
| Before a wait of more than an hour (a long CI, a given time) | the end of the wait |

A session never starts on a window beyond its threshold, 15% of the
five-hour window and 75% of the week: its time then moves back to the
reset of that window, plus five minutes. A batch costs a good share of
the window: started on a window already used, it would be cut off along
the way. The use and the resets are read as for the wake-ups (the
`socle-resume` skill).

## The bounds

Nothing is scheduled, and the recap gives the prompt to copy:

- when the next batch has no ready task in the state, because a
  decision is up to the human or nothing is ready; a pending request
  that does not block it does not stop it;
- after two batches run without a message from the human, the current
  batch included;
- when the platform refuses to create the session.

The chain (`--chain`) counts these batches: 0 if the human wrote in the
session; otherwise, that of its handoff prompt, plus one. The prompt to
copy carries 0. With `--scheduled`, the command refuses the prompt at
the first two bounds, saying so.

## Scheduling

First the tidying up (the `socle-batch` skill, "Changing sessions"): the
journal entry that tells the handoff, without the links only the recap
will give; the session's wake-ups removed; everything pushed. Nothing is
pushed afterwards: the guard names the remote head, and the scheduled
prompt is no longer rewritten. A commit needed later cancels the handoff
(the task deleted, the session archived), which is done again.

1. The prompt, with the link of this session (the one its commits carry)
   and what is waiting:

```sh
python3 .socle/socle handoff prompt --scheduled --chain <n> --session <link> --waiting "<what is waiting>"
```

2. `create_session`, without `prompt`: `source_url` the repository's
   address; `source_revision` the branch the guard names (`--ref`,
   without `origin/`); `outcome_branch` the work branch, without which
   the new session has nowhere to push; `model` this session's; `effort`
   its own, which is not inherited (refused, the call is made again
   without it); `title` "Handoff — <batch> — starts on <day> at <the
   human's time>"; `tags` `["handoff"]`.
3. `create_trigger`: `name` "Handoff — <repository>";
   `persistent_session_id` the created session; `run_once_at` the time
   of the moment; `prompt` the text of step 1; `initiation`
   `own_followup`.
4. The recap gives the link of the created session, its time and how to
   stop it; `Next:` says so.

If a call fails, the created session is archived, and the prompt to copy
replaces the handoff, the recap saying why.

## The prompt to copy

In a block to copy in the recap, with the reason for changing sessions:

```sh
python3 .socle/socle handoff prompt --session <link> --waiting "<what is waiting>"
```

Pasted late, its guard judges it all the same.

## The new session

Its prompt starts with `git fetch` and the guard (`socle handoff
check`). Refused, it does nothing else but say so, with its reason, in
its last message. Accepted, it moves to the reference the guard names:
its clone dates from its creation, not from its prompt.

## The open pull request

A session started from a handoff prompt that the guard accepts,
scheduled or pasted by the human, continues the open pull request of its
branch without asking: it becomes its own. It merges it if the policy
allows the agent to, under the conditions of `socle-batch`; otherwise
the human merges it.

## Seeing and stopping

The created session appears at once in the human's list of sessions,
under its title, ready for review while it waits for its prompt. Its
last message says what it did, why the chain stops or what the guard
refused, and what is up to the human.

The human stops it by writing "stop" in the session that scheduled it,
while it runs; afterwards, by changing the mode in a session of the
project, or by deleting its task from the list of scheduled tasks of
their account and archiving the session. A session they open while a
handoff is waiting tells them at the first turn (the `socle-resume`
skill), and cancels it only at their request.

## The old session woken up

A failed turn or a restarted container in the created session may give a
turn back to the one that scheduled it. It says so in one line and does
nothing else.

The wake-ups of `socle-resume` remain, in both modes: a session cut off
before tidying up resumes when the limit lifts.
