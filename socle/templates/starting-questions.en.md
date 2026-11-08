<!-- socle: layer=requests zone=public -->
# {id} — The project's starting questions

> date : {date} · origin : `socle init`

## Decision requested

Answer the {n} starting questions below, or accept all their defaults in one
word.

## Context

**The project.** This repository, {nom}, has just been equipped with the
socle: a tool that keeps the project's memory in the repository, checks
what the coding agent produces there, and asks the human, in requests like
this one, the decisions that belong to them. What the project itself does,
the agent does not guess: it is one of the questions below.

**The work.** The socle's initialization: describing the project in its
memory, starting from {entrees}, so that the agent then works without
guessing. Nothing else is done yet.

**The question.** The agent invents nothing: it does not ask what it can
read in the repository (the language, the test tools), only what it cannot
guess, such as the project's goal, confidentiality or the level of autonomy.
The questions are grouped here, at the start, and capped at {plafond}; the
less urgent ones go to the backlog. Each one has a default, and says what
that default changes.

## Questions

{questions}

## Cited elements

{elements}

## Where to look

{lien}

What to check: that each default suits you, or the answer to put in its
place.

## Options

- **Accept all the defaults**: no effort; low risk, each default stays
  "assumed" and can be corrected later; reversible.
- **Answer question by question**: a few minutes; the start follows what you
  want; reversible.
- **Reject the defaults**: no effort now; risk, the start waits for these
  answers, each question staying open; reversible.

## Consequences

If you approve the defaults, the agent applies them, marked "assumed". If you
answer otherwise, the agent records your exact text and applies it. If you
reject the defaults (`reject`), each question stays open, in the backlog.
If the questions cannot be understood (`insufficient-context`), the agent
rewrites them. With no answer, the defaults apply, marked "assumed", and the
request stays in the queue for you to come back to.

## Recommendation

Read the defaults and only answer what does not suit you. Verified: what the
repository audit read, if there was one. Assumed: everything else.

## Possible answers

- `approve` — all the defaults apply, marked "assumed".
- `answers` — the text of your answer gives the answers, question by question; the agent records it as is.
- `reject` — no default applies: each question stays open, in the backlog.
- `insufficient-context` — the request goes back to the agent, who rewrites it as a request that replaces it.
