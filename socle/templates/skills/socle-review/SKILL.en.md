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
`## Threat model` section: what the guardrail stops, what it lets
through; a topic whose design is not settled, its specification.

## How

1. Commit the batch: the review only sees what is committed, or changed
   in a file already tracked.
2. Prepare the reviewer's brief:

```sh
python3 .socle/socle review
```

   It gives the instruction, the batch's diff since the remote branch
   (otherwise the default branch), the topics the batch touches, in
   full, those it opens by their title, and the decisions they cite.
   `--base <ref>` changes the batch's base; for a second review,
   `--since <reviewed commit>` shows only the diff since the first
   review's commit, with the messages of the commits that fix it.
3. Hand it to a reviewer who does not have the conversation. Under
   Claude Code: a subagent (the `Agent` tool), of the session's model,
   whose only message is this brief, as is: nothing is added to it,
   nothing removed. It also receives the project's instructions and can
   read the repository, but neither the conversation nor the agent's
   reasoning, and the brief tells it to change nothing: to try a
   command, it creates a temporary directory outside the repository and
   writes only there, through the path `mktemp -d` returned, written out
   in full in each command: a variable does not survive from one call to
   the next. The agent's hook refuses the installer aimed at the
   project in another mode than its lock's, or at a target written
   through a variable, but not every write of the
   reviewer in the repository. An agent without
   subagents skips the review, and its recap says so.

## The findings

The reviewer classifies them; the agent checks each classification.

- **Blocking** (it contradicts a ticked criterion or a cited decision,
  breaks what worked, loses data, or bypasses a guardrail within its
  threat model): fixed in the batch, before the push.
- **For the backlog** (the rest: a bypass outside the threat model, a
  criterion the batch does not tick, a neighbouring defect): not fixed
  in the batch; it goes to the backlog, one topic per finding or one for
  several of the same kind.
- **Unfounded**: dismissed, in one line that says why.

Post nothing on GitHub: the human reads the recap, not the review. The
recap says it in one line: `Review: <b> blocking, fixed; <n> to the
backlog (<topics>); dismissed: <reason for each>`, or `Review: no
finding`.
