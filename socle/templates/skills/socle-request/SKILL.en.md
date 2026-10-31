---
name: socle-request
description: Write a request for a human decision, relay the human's answer, or record a decision taken in session. Use when a decision belongs to the human (autonomy policy, points 1 to 4, 7 and 8), when they answer a request, or when they settle a question in the conversation.
---

# Requests for a human decision

A request is read once the context is lost: it stands on its own. The human
answers in the conversation; the agent records their answer word for word,
never choosing it.

## Writing a request

1. `python3 .socle/socle new request "<decision>"` lays out the skeleton
   and gives the identifier.
2. Fill in the eight fields:
   - **Decision requested**: in one sentence.
   - **Context**: the problem itself, summarised on the spot in at least
     sixty words, not a pointer.
   - **Cited elements**: each identifier described in plain words, with
     the fingerprint of the version read (`- B-NNNN@xxxxxxxx — what it is,
     in one sentence`); never an identifier alone.
   - **Where to look**: a link to each document to read
     (`python3 .socle/socle url <path>`), and what to check there.
   - **Options**: for each, the effort, the risk, the reversibility.
   - **Consequences**: if the human approves, if they reject, without an
     answer.
   - **Recommendation**: what is verified kept apart from what is assumed.
   - **Possible answers**: a list `` - `value` — meaning `` that offers
     the base answers, the same in every request: `approve` (the
     recommendation), `reject` and `insufficient-context`; a choice request
     adds its options, and no synonym (`accept`, `yes`…). Only `approve`
     authorises changing a test or a threshold key the request names.
3. The lint refuses an incomplete request; the agent's hook refuses it as
   soon as it is written.
4. Commit and push the request as is, then give its link
   (`python3 .socle/socle url D-NNNN`) in the conversation. Work on
   something else while waiting for the answer (policy, point 8).

## Relaying an answer

1. Write the human's exact text into a file.
2. Record the answer:

```sh
python3 .socle/socle answer D-NNNN <answer> --relayed --by <name> --quote-file <file>
```

3. Copy the answer into the journal, with its exact text.

An answer is only relayed to a request pushed as is: the human must have
been able to read it. An answered request is frozen. The answer
`insufficient-context` sends the request back: rewrite it as a new request
that replaces it.

A test whose expected value changes while waiting for a request that names
it may stay changed in the tree at the end of the turn; it is only
committed after the answer.

## Recording a decision taken in session

A decision that needs context, approving a document included, is put as a
request (above), never in the agent's question widget: the human reads raw
text there, with no links to follow. What the human settles in the
conversation, of their own accord or on a short question asked in the text
of the answer, is recorded at once, with their answer word for word;
`--about <path>` designates what it approves:

```sh
python3 .socle/socle decision "<question>" <answer> --relayed --by <name> --quote-file <file>
```

## What the agent never does

Answer on the human's behalf (`socle answer` without `--relayed` and a
quote), or run `socle approve`, which is for the human only.
