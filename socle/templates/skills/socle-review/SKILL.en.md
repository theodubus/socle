---
name: socle-review
description: Have a batch reviewed by a reviewer without context before delivering it, the adversarial review, then handle its findings. Use before the push that delivers a batch that changes code, a specification or a test.
---

# The adversarial review of a batch

The socle's checks judge the form of the work; the review judges its
substance, through a reviewer without the blind spots of the batch's
author, who tries to find fault with it.

## When

Before the push that delivers a batch that changes code, a specification
or a test; never for a batch that only touches the memory. One pass per
batch; a second one only if the fix of the blocking findings is heavy (it
changes the design of a part, not a few lines), and on that fix alone;
each pass beyond the first follows the step back of the previous one
(below).

The reviewer judges the batch against its tasks: their “Done when”
criterion and, for a guardrail, its threat model. A need that adds or
changes a guardrail therefore writes it before its code, in its
`## Threat model` section or in the decision it cites: what the
guardrail stops, what it lets through; a need whose design is not
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
   refused. A batch already pushed, even in part (in a cloud session, at
   the end of each turn), or a branch that carries batches
   already reviewed, which the brief's note points out: `--base <the
   commit before the batch>`, the head the batch started from. It writes
   the pass in the entry of the backlog's batch in progress, or of the one
   `--batch L-NNNN` names, and refuses a pass the batch's history refuses
   (below).
3. Hand it to a reviewer who does not have the conversation. Under Claude
   Code: a subagent (the `Agent` tool), whose only message is this brief,
   as is, with nothing added or removed. It receives explicitly
   at launch (`model`) the most capable model available up to Opus, never
   a lesser one than the one that implemented the batch, whatever the
   session's, which the model rule of `socle-batch` may make cheaper, on
   the latest version of its family: if the alias designates an older
   one, it inherits the session's, without `model`, and its report names
   the model that served it;
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
  catches its effect afterwards: one task per finding if its fix is
  clear, a need otherwise, or one entry for several of the same kind.
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
  (`python3 .socle/socle help`). In an equipped project, this guide
  is protected: the recap names the form, and “For you” suggests
  reporting it to the socle's repository
  (https://github.com/theodubus/socle), which keeps the list.

Post nothing on GitHub: the human reads the recap, not the review. The
recap says it in one line: `Review: <b> blocking, fixed; <n> to the
backlog (<entries>); dismissed: <reason for each>`, or `Review: no
finding`.

## The batch's history and the step back

The batch keeps its passes in the `## Reviews` section, the last of its
entry, readable from a new session: `socle review` writes each pass
there, its date and the reviewed commits, and gives the same one again
as long as nothing changes outside the memory.

1. When the reviewer returns, write in the pass one line `- Blocker:
   <its cause, in a few words>` per blocker, and `- Opens: <the entries
   the pass opens>`, or `none`. From the second pass on, the brief gives
   the reviewer the causes of the earlier blockers, and it says, for each
   new blocker, whether it has the same cause as one of them: its line
   ends with `· same cause` or `· new cause`, as the reviewer says, never
   as the agent does.
2. Before the next pass, and before closing the batch, write the pass's
   step back, under its blockers: a paragraph that starts with “Step
   back:”, of at least sixty words, which answers the three questions
   `socle review` gives when it refuses the pass, with what it shows
   there. Do this pass's blockers have the
   same cause as the previous pass's? Are the entries the batch opens of
   the same nature as those it closes? Have the closed batches that
   touched the same files already opened this kind of entries? Its last
   word is its decision: “continue”, with what will make the next pass
   different written before it, or “stop”.
3. Stopping: put a request to the human (skill `socle-request`) that
   cites the batch and says what goes round, in plain words, the rule
   that makes it go round, and a proposal that bounds it; the step back
   names it (`D-NNNN`), and the batch waits for it through its `after`.
   `socle review` refuses one more pass until its answer, the only thing
   that lifts the stop: move on elsewhere. After two passes in a row
   where the reviewer sees a same cause come back, it refuses “continue”:
   the batch stops.

The backlog check refuses a reviewed batch closed `done` whose last pass
would refuse the next one.
