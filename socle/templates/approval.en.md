<!-- socle: layer=requests zone=public -->
# {id} — Approve a change made by the human themselves

> date : {date} · origin : `socle approve`

## Decision requested

The human approves a change they made themselves to a guardrail or a protected file.

## Context

Written and approved in a single step by `socle approve`, a command the agent's hook refuses: it is for the human only, so that their own protected changes stay visible and traced. Reason given: {raison}

## Cited elements

{elements}

## Where to look

The diff of the commit that carries this request; the files and keys cited above, see [the request format](../../{moteur}/socle/FORMAT.md).

## Options

Approving keeps the change: no effort, the risk is the human's, reversible by a new approved change. Not approving lets the CI reject the change, which is reversible and takes no effort.

## Consequences

If the human approves, the CI accepts the cited change. If they reject it, the CI rejects it. With no answer, nothing goes through: this request is born with its answer.

## Recommendation

Verified: the fingerprints and keys cited above are those of the tree at the time of approval. Assumed: nothing, the human decides alone.

## Possible answers

- `approve` — the CI accepts the cited change.
- `insufficient-context` — not applicable here; present because every request offers it.
