---
name: socle-review
description: Have a batch reviewed by a reviewer without context before delivering it, the adversarial review, then handle its findings. Use before the push that delivers a batch that changes code, a specification or a test.
---

# The adversarial review of a batch

The socle's checks judge the form of the work; the review judges its
substance, through a reviewer who does not share the blind spots of the
agent that wrote the batch, and who tries to find fault with it.

## When

Before the push that delivers a batch that changes code, a specification
or a test; never for a batch that only touches the memory. One pass per
batch; a second one only if the fix of the blocking findings is heavy (it
changes the design of a part, not a few lines), and on that fix alone.

The reviewer judges the batch against its topics: their “Done when”
criterion and, for a guardrail, its threat model. A topic that adds or
changes a guardrail therefore writes it before its code, in its
`## Threat model` section or in the decision it cites: what the
guardrail stops, what it lets through; a topic whose design is not
settled, its specification.

## How

1. Commit the batch: the review only sees what is committed, or changed
   in a file already tracked.
2. Prepare the reviewer's brief:

```sh
python3 .socle/socle review
```

   It gives the instruction, the batch's diff since the common ancestor
   of HEAD and its base, the remote branch (otherwise the default
   branch; if the remote branch already contains the batch, pushed before
   its review, or stayed behind the default branch after a squash merge,
   the common ancestor with the default branch, and it says so), the topics whose status or “Done when” the batch changes, in
   full, those it opens by their title, the decisions and requests the
   batch writes, then those its topics cite.
   `--base <ref>` changes the batch's base; for a second review,
   `--since <reviewed commit>` shows only the diff since the first
   review's commit, with the messages of the commits that fix it. An
   unknown reference, or a `--since` that is not an ancestor of HEAD, is
   refused. A batch already pushed in whole or in part (a cloud session
   pushes at the end of each turn), or a branch that carries batches
   already reviewed, which the brief's note points out: `--base <the
   commit before the batch>`, the head the batch started from.
3. Hand it to a reviewer who does not have the conversation. Under Claude
   Code: a subagent (the `Agent` tool), whose only message is this brief,
   as is: nothing is added to it, nothing removed. It receives explicitly
   at launch (`model`) the most capable model available up to Opus, never
   a lesser one than the one that implemented the batch, whatever the
   session's, which the model rule of `socle-batch` may make cheaper, on
   the latest version of its family: if the alias designates an older
   one, it inherits the session's, without `model`, as that rule says, and
   its report names the model that served it;
   Fable, if available, only if the human asks for it. It also receives
   the project's instructions and can read the repository, but neither the
   conversation nor the agent's reasoning, and the brief tells it to
   change nothing: to try a command, it creates a temporary directory
   outside the repository and writes only there, through the path
   `mktemp -d` returned, written out in full in each command: a variable
   does not survive from one call to the next. The agent's hook refuses
   the installer aimed at the project in another mode than its lock's, or
   at a target written through a variable, but not every write of the
   reviewer in the repository. An agent without subagents skips the
   review, and its recap says so.

## The findings

The reviewer classifies them; the agent checks each classification.

- **Blocking** (it contradicts a ticked criterion or a cited decision,
  breaks what worked, loses data, or bypasses a guardrail within its
  threat model): fixed in the batch, before the push.
- **For the backlog**: a finding that does not block goes to the
  backlog if it can occur in the project's normal use, or if nothing
  catches its effect afterwards; one topic per finding, or one for
  several of the same kind.
- **Dismissed**: an exotic finding (a rare gesture, a form one only
  writes to get around something, a case never reproduced) whose effect
  is caught, by a check, the CI or an error the agent sees at once; and
  an unfounded finding. One line of the recap says why each is
  dismissed.
- **A shell form an agent does not write** in its work (seen neither in
  an agent session, nor in a skill, nor in current documentation), and
  that escapes the agent's hook: it is not classed as blocking, even if
  refused before the batch by accident, nor for the backlog, whatever its
  effect. It is dismissed, and goes in one line to the list of known
  forms the hook does not judge, which the socle's guide keeps
  (`python3 .socle/socle help`).

Post nothing on GitHub: the human reads the recap, not the review. The
recap says it in one line: `Review: <b> blocking, fixed; <n> to the
backlog (<topics>); dismissed: <reason for each>`, or `Review: no
finding`.
