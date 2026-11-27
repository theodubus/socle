---
name: socle-handoff
description: Hand over to a new session, at the end of a batch, near a usage limit or before a long wait — write the handoff in the memory, then schedule the next session or tell the human to ask for the resumption, depending on the mode, with the guard against duplicated work. Use it after the tidying up of socle-batch, when the human changes the mode, and when the first message of a new session asks to resume.
---

# Handing over to a new session

A session chains the batches its budget allows (the `socle-batch`
skill). When it stops, it writes its handoff in the memory, commits and
pushes it; the next session finds it and judges its guard. The handoff's times are in UTC; those the human reads,
in their own time.

## The two modes

- **Scheduled session**, by default: the agent creates the next session
  and schedules its wake-up.
- **Prompt to copy**: the recap tells the human to open a new session
  and ask there for the resumption.

The mode is the one a directive in force states; without one, the
scheduled session. The human changes it by saying so: the agent records
their words in session, lifts the previous directive and writes the new
one (`socle new directive`), with its exact text (skill `socle-request`).
Switching to the prompt to copy cancels what is scheduled, the
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

A session starts only if its batch's estimated cost fits in what
remains of the five-hour window, the tidying-up margin included, and
never on a week beyond 75%: otherwise, its time moves back to the reset
of that window, plus five minutes. The use and the resets are read as
for the wake-ups (the `socle-resume` skill).

## The bounds

Nothing is scheduled, and the recap says to ask for the resumption:

- when the next batch has no ready task in the state, because a
  decision is up to the human or nothing is ready; a pending request
  that does not block it does not stop it;
- after two batches run without a message from the human, the current
  batch included;
- when the platform refuses to create the session.

The chain (`--chain`) counts these batches: 0 if the human wrote in the
session; otherwise, that of its handoff, plus one. The prompt to copy
carries 0. With `--scheduled`, the command refuses the handoff at the
first two bounds, saying so.

## Writing the handoff

First the tidying up (the `socle-batch` skill, "Changing sessions"): the
journal entry that states the handoff, without the links only the recap
will give; the session's wake-ups removed. Then, with `--scheduled` for
a scheduled session:

```sh
python3 .socle/socle handoff write --chain <n> --waiting "<what is waiting>"
```

The handoff is committed last and pushed, before any merge of the pull
request: when the agent merges it itself, the handoff is its last commit,
`--waiting` stating the merge to come. The merge carries it to the
default branch, and the branch, which the host deletes, is not pushed
again. Then the guard, without arguments, must find it waiting (its
"First commit" line is for the new session); otherwise, nothing is
scheduled, and the recap says why:

```sh
python3 .socle/socle handoff check
```

Nothing is pushed afterwards; a commit needed later, before the merge,
rewrites the handoff (`write`) in that same commit, and the guard runs
again.

## Scheduling

The handoff written with `--scheduled` (above, `socle-batch` tidied up):

1. `create_session`, without `prompt`: `source_url` the repository's
   address; `source_revision` the work branch, or the default branch
   when the merge deleted it; `outcome_branch` the work branch; `model` this
   session's; `effort` its own, which is not inherited (refused, the call
   is made again without it); `title` "Handoff — <batch> — leaves on
   <day> at <human's time>"; `tags` `["passation"]`.
2. `create_trigger`: `name` "Handoff — <repository>";
   `persistent_session_id` the created session; `run_once_at` the time of
   the moment; `prompt` "resume — scheduled session"; `initiation`
   `own_followup`.
3. The recap gives the link of the created session, its time and how to
   stop it; `Next:` says so.

If a call fails, the created session is archived, and the prompt to copy
replaces the scheduled handoff, the recap saying why.

## The prompt to copy

The recap says it, with the reason for changing sessions: "In a new
session, write "resume""; any message that asks to resume or continue
will do.

## The new session

On a first message that asks to resume or continue the work, whatever
its form ("resume", "continue", "pick the work back up"), or on the
scheduled task's, the agent runs `git fetch --prune origin`, then the
guard without arguments. Refused, the session does nothing else but say
so, with its reason, in its last message. Accepted, it places itself on
the reference the guard names, and its first commit removes the
handoff, pushed at once, then `python3 .socle/socle prune-branches`
deletes the previous session's branch, which its own now contains, if
it had another one; its chain is the handoff's plus one, woken by
the scheduled task, 0 if the human asked. Without a handoff, it does
what a new session does, and says so in its first message.

When the state says at its top that the local head is behind the
handoff, the session loaded the earlier instructions, skills and hooks:
once placed, it reads what changes in them, by the command the state
gives, before any other work, and keeps to it.

## The open pull request

A session whose guard accepts the handoff, scheduled or asked for by the
human, continues the open pull request of its branch without asking: it
becomes its own. It merges it if the policy allows the agent to, under
the conditions of `socle-batch`; otherwise the human merges it.

## Seeing and stopping

The last message of the created session says what it did, why the chain stops or what the guard
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

The wake-ups of `socle-resume` remain, in both modes.
