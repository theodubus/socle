---
name: socle-review
description: Have a batch reviewed by a reviewer without context before delivering it, the adversarial review, then handle its findings. Use before the push that delivers a batch that changes code, a specification or a test.
---

# The adversarial review of a batch

The checks judge the form of the work; the review judges its
substance, through a reviewer without the blind spots of the author,
who tries to find fault with it.

## When

Before the push that delivers a batch that changes code, a specification
or a test; never for a batch that only touches the memory. One pass per
batch; a second one only if the fix of the blockers is heavy (it changes
the design of a part, not a few lines), and on that fix alone.

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
   branch, and it says why), the entries whose status or criteria the
   batch changes, in full, those it opens by their title, the decisions
   and requests the batch writes, then those its entries cite and
   these decisions, and the file an in-session decision approves (its
   `about`).
   `--base <ref>` changes the base; for a second review, `--since
   <reviewed commit>` shows only the diff since the first, with the
   messages of the commits that fix it. A batch already pushed, even in
   part (in a cloud session, at the end of each turn), or a branch that
   carries batches already reviewed, which the brief's note points out:
   `--base <the commit the batch started from>`. It writes the pass in the backlog's batch in progress, or the
   one `--batch L-NNNN` names, and refuses a pass its history refuses
   (below).
   A small batch (under 150 lines of code and tests) that touches
   neither a guardrail nor a format other parts of the project read
   gets the short brief, `--short`: the diff and its tasks' criteria, to
   judge without exploring beyond the files touched; any other batch,
   the full brief. `--short` refuses a batch that touches a path the
   policy protects or the guardrails declare.
3. Hand it to a reviewer who does not have the conversation. The brief
   does not enter it, which would reread it at each step: the output of
   `socle review` is written to a file outside the repository, and the
   reviewer's only message (under Claude Code, a subagent, the `Agent`
   tool) gives its path, with the instruction to read it in full and
   follow it as is. It receives explicitly at launch (`model`) the most capable model available up to Opus, never
   a lesser one than the one that implemented the batch, whatever the
   session's, which the model rule of `socle-batch` may make cheaper, on
   the latest version of its family: if the alias designates an older
   one, it inherits the session's, without `model`, and its report names
   the model that served it;
   Fable, if available, only if the human asks for it. A batch
   implemented on Fable (the batch, not the orchestrating session) has
   the human asked, before the review, whether they also want Fable for
   the reviewer. The reviewer also receives
   the project's instructions and can read the repository; the brief
   tells it to change nothing outside a temporary directory (`mktemp
   -d`), which the agent's hook does not enforce. An agent without
   subagents skips the review, and its recap says so.

## The findings

The reviewer classifies them; the agent checks each classification.

- **Blocking** (it contradicts a ticked criterion or a cited decision,
  breaks what worked, loses data, or bypasses a guardrail within its
  threat model): fixed in the batch, before the push.
- **For the backlog**: a finding that does not block goes to the
  backlog only if it matters and has been seen in real use (a session,
  a CI run, a message from the human shows it), or if its effect would
  be irreversible (lost data, a push to the default branch, a deletion):
  one task per finding if its fix is clear, a need otherwise, or one
  entry for several of the same kind.
- **Dismissed**: any other finding, including a case imagined and
  never seen, a slight nuisance the agent handles itself (what a check,
  the CI or an error it sees at once catches), a bypass outside the
  threat model, and an unfounded finding. When in doubt, it is
  dismissed. One line of the recap says why each is dismissed; it
  comes back if seen in real use.

Post nothing on GitHub: the human reads the recap, not the review. The
recap says it in one line: `Review: <b> blocking, fixed; <n> to the
backlog (<entries>); dismissed: <reason for each>`, or `Review: no
finding`.

## The batch's history

The batch keeps its passes in the `## Reviews` section, the last of its
entry, readable from a new session that resumes the batch: `socle review`
writes each pass there, its date and the reviewed commits, and gives the
same one again as long as nothing changes outside the memory. Commit the
written pass, and what is recorded in it: otherwise, it is lost where
`socle review` ran.

When the reviewer returns, write in the pass one line `- Blocker: <its
cause, in a few words>` per blocker, and `- Opens: <the entries the pass
opens>`, or `none`. Nothing else is required, neither before the next
pass, nor when the batch is closed.
