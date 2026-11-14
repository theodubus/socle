---
name: socle-request
description: Write a request for a human decision, relay the human's answer, or record a decision taken in session. Use when a decision belongs to the human (autonomy policy, points 1 to 4, 7 and 8), when they answer a request, or when they settle a question in the conversation.
---

# Requests for a human decision

A request is read once the context is lost: it stands on its own. The human
answers in the conversation; the agent records their answer word for word,
never choosing it.

## Writing a request

1. `python3 .socle/socle new request "<decision>"` lays out the skeleton,
   gives the identifier, and prints the contract the lint will judge.
2. Fill in the eight fields:
   - **Decision requested**: in one sentence.
   - **Context**: for the human who comes back to the project after
     weeks, three paragraphs first, each led by its name in bold: **The
     project.** (what it does, and for whom, even if the human knows it),
     **The work.** (the goal of the work in progress, what is done and
     what remains; their past decisions told by their content and date,
     not by their number) and **The question.** (what raises it now).
     Then the details, on the spot, not a pointer: at least sixty words in
     all, and each term proper to the project explained where it first
     appears.
   - **Cited elements**: each identifier described in plain words, with
     the fingerprint of the version read (`- B-NNNN@xxxxxxxx — what it is,
     in one sentence`); never an identifier alone. A protected file to
     have approved, those of an update, is written there on its own line,
     its path and its new fingerprint, nothing else (`python3 .socle/socle
     check` gives them): these lines need no description and do not count
     in the request's budget.
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
4. Have it read cold before pushing it: a subagent (the `Agent` tool), of
   the session's model, whose only message is the brief of
   `python3 .socle/socle review --request D-NNNN`, as is. It reads the
   request as the human who has not opened the project for three weeks,
   with no link and no file, and returns what it understood and what it
   lacks to decide. Rewrite what the human would not understand either;
   set aside, with a reason, what does not help to decide or what a linked
   document already gives. The recap says so: `Cold reading: <n> points,
   <k> fixed; set aside: …`. An agent without subagents skips this step,
   and its recap says so.
5. Commit and push the request as is, then give its link
   (`python3 .socle/socle url D-NNNN`) in the conversation. Work on
   something else while waiting for the answer (policy, point 8).

## Relaying an answer

1. Write the human's exact text into a file.
2. Record the answer:

```sh
python3 .socle/socle answer D-NNNN <answer> --relayed --by <name> --quote-file <file>
```

3. Copy the answer into the journal, with its exact text.

The answer is recorded as soon as it is given, in the tree: the state
reads it as answered before its commit, and the human no longer sees it
pending. It is committed and pushed with the change it authorizes (an
expected value, a guardrail key, a protected file), in the same push,
never before: the CI of a push only counts the approvals of its range,
and the push of the change, alone after it, would be refused. Only a
protected file can precede it, pushed under the pending request where
the socle's CI is required: the answer then leaves alone, harmlessly.
`demandes.reponse-seule` warns before it leaves alone.

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
