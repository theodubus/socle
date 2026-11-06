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
batch: no second review after the fixes.

## How

1. Commit the batch: the review only sees what is committed, or changed
   in a file already tracked.
2. Prepare the reviewer's brief:

```sh
python3 .socle/socle review
```

   It gives the instruction, the batch's diff since the remote branch
   (otherwise the default branch), the topics the batch closes and the
   decisions they cite. `--base <ref>` changes the batch's base.
3. Hand it to a reviewer who does not have the conversation. Under
   Claude Code: a subagent (the `Agent` tool), of the session's model,
   whose only message is this brief, as is: nothing is added to it,
   nothing removed. It also receives the project's instructions and can
   read the repository, but neither the conversation nor the agent's
   reasoning, and the brief tells it to change nothing. An agent without
   subagents skips the review, and its recap says so.

## The findings

None blocks on its own. Fix each founded finding, in the batch, before the
push; answer the others in one line: why it does not hold. Post nothing on
GitHub: the human reads the recap, not the review.

The recap says it in one line: `Review: <n> findings, <k> fixed;
dismissed: <reason for each>`, or `Review: no finding`.
