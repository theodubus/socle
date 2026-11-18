@@SECTION_PROJET@@

## Socle: memory, documentation and tests

This repository uses the socle (version and fingerprint: `.socle/engine.lock`).
This file says **how** to work;
**where the project stands** is computed, and is never written by hand.

### At startup, and after every compaction

`python3 .socle/socle state` prints the derived state — commit, base, CI,
backlog, pending human requests —, then the essentials of the
memory. Under Claude Code, the `SessionStart` hook does it on its own; under
another agent, run it first. Nothing that is not in it is established.
What the human wrote themselves since the agent's last commit (an approval,
an answer in their terminal), the state lists: cite it to them in the next
reply, by its identifier and its link, which the conversation did not give
them.

If the state was not injected when a Claude Code session started, its
hooks are not loaded (the session started outside the project root;
`socle state` says so at the top, and the pre-commit hook then refuses the
commit): tell the human before any work, push nothing, and never write a
Claude Code setting yourself to restore them.

An instruction from the human given in the conversation, that holds beyond
the turn (a rule, a preference, a prohibition), is written into the memory
before going on: in the active work if it concerns the work in progress,
otherwise in the journal, with its exact text: a compaction may lose it,
and a new session only has the memory.

### The memory, in `memory/`

| Layer | Where | Rule |
| --- | --- | --- |
| Canonical | `memory/canonical.md` | facts with status and proof; only changes with a new proof |
| Active | `memory/active.md` | work in progress, next steps; rewritten, kept short |
| Decisions | `memory/decisions/` | one ADR per file, the project's only decision register; only its status changes afterwards |
| Journal | `memory/journal/` | one dated entry per event; append only |
| Backlog | `@@BACKLOG@@` | four forms, each with its prefix: need `B-` (“Satisfied when”), task `T-` that names its need (“Done when”), batch `L-` of tasks, milestone `JA-` of needs; ordered by `after`, with their priority (the state computes the ready tasks); closed with a reference, then filed by `socle archive` |
| Requests | `memory/requests/` | human decisions in a queue, under the contract of the skill `socle-request` |

An entry: `## F-NNNN — title`, then a line `> status : measured · proof : commit:<sha>`.
Statuses of a fact: `measured` (with `proof`), `assumed`, `refuted` (title struck
through, with `refutation`), `validated` (with `validation : D-NNNN`, written
after the human's answer). Full format: `@@MOTEUR@@/socle/FORMAT.md`.
An identifier is computed (`python3 .socle/socle new <type> "title"`), it is
never guessed. In case of conflict, the order of authority is: the code and
the tests, then the canonical memory, then the journal.

**Private memory**, if the policy chooses one (`[private] mode`): nothing private is copied to public, neither a `P…` identifier, nor its content, nor in a commit message, a pull request or a comment; unavailable (the state says so), nothing is concluded about what depends on it. How to work with it: the skill `socle-private-memory`.

### Autonomy policy (`.socle/policy.toml`, changed by the human only)

1. **Loosening a guardrail** (`.socle/guardrails.toml`) requires an approved request; tightening is free. Declaring third-party files, which no check judges (`[thirdparty] paths`), loosens.
2. **Deleting a test or changing an expected value**, in a test or a declared case file, requires an approved request, or a specification the human changed themselves and that names the test; an ADR written by the agent is not enough.
3. **Design decision**: reversible and measurable, the agent decides and writes an ADR; costly to undo, ask.
4. **Irreversible or external action** (force-push, push to the default branch, publication, remote deletion, spending): always a request. The hook refuses it.
5. **Memory**: append only; "refuted" requires a measurement reference; "validated" is only written after the human's answer.
6. **Scope creep**: a neighbouring bug goes to the backlog, it is not fixed, unless it blocks.
7. **Repeated failure**: checks red after three attempts, stop and escalate with a request that sums up.
8. **Approval required**: queue the request, work on something else, never guess.

### Human decision requests

A decision that belongs to the human is put as a request, which reads on its
own once the context is lost, and whose link is given in the conversation.
The human answers in the conversation; the agent records their answer word
for word, never choosing it, and copies it into the journal. A decision that
needs context, approving a document included, is always written as a
request; never in the agent's question widget, where the human reads raw
text with no links to follow (the hook refuses it). What the human settles
in the conversation, of their own accord or on a short question asked in
the text of the answer, is recorded at once in the same way, in session.
How: the skill `socle-request`. A need whose specification depends on an
intention the memory does not state is first framed by open questions
(`socle new request --questions`); a specification is submitted before its
code.

### Reading the memory on demand

Startup only injects the state, the active work, the titles of the facts
and the last ten decisions, under a cap; what a `!! cut` line says is
missing is read at once. The rest is read when it is needed, without
waiting to be asked:

- a cited identifier (`F-`, `B-`, `T-`, `L-`, `JA-`, `ADR-`, `D-`, `J-`) is read before relying
  on it: `python3 .socle/socle show <ID>`, which also gives its fingerprint;
- before a design decision, `socle show --index decisions` says whether it
  has already been made: it is not reopened without a new fact;
- before opening a backlog entry, its index (`socle show --index
  backlog`) says whether it already exists;
- to know why something is the way it is, search the journal
  (`grep -rn "<word>" memory/journal/`);
- the roadmap, when the human asks for it: paste into the reply the output
  of `python3 .socle/socle roadmap --format markdown`.

Reading is proven: a new decision, request or backlog entry cites what it
read with its fingerprint (`ADR-NNNN@xxxxxxxx`, `read : decisions@…`,
`read : backlog@…`). A stale or invented fingerprint is refused; the entry
must be read again. `socle new` puts in the index fingerprint.

### Skills

A rare procedure is read in its skill, which the agent loads on its
description: `socle-request` (requests, a decision taken in session),
`socle-private-memory` (the private memory), `socle-batch` (running a
batch), `socle-review` (the review of a batch, before its delivery) and
`socle-resume` (in a cloud session, at every turn that acts: resuming
after a usage limit), in `.claude/skills/`, laid by the installer and
protected; another agent reads their `SKILL.md` at that path.

A project procedure that comes back (the journal shows the first time) is
written as a skill the second time, in `.claude/skills/<name>/SKILL.md`: a
name without the `socle-` prefix, a header with `name` (the
folder's name) and `description` (what it does, and when to use it), and a
journal entry that says so. A skill says how to do something, the memory
what is and why: it copies nothing from it. Its commands, in code blocks,
are judged as the hook would judge them; a command not to run is cited in
the text.

### Delivering the work

As long as nothing is up to the human, the agent chains the ready tasks
without waiting for a message. It first announces the batch, not
necessarily everything that is ready (the tasks, their size, the
milestone they serve; a low-priority task if convenient), then gets
going; it stops at the end of the batch, or as soon as a decision is up
to the human. It does not change a priority the human gave. A need
without an open task is first split into tasks. The batch is formed by
sweeping the whole open backlog; a task opened later joins the next
batch whose rule applies to it, never the one in progress. It is kept in
the backlog (`socle new batch`) and run following the `socle-batch`
skill. Before the push of a batch that changes code, a specification or a
test, it has it reviewed by a reviewer without context, against the “Done
when” of its tasks (the `socle-review` skill). A need whose design is
not settled writes its specification before its code; a need that adds
or changes a guardrail, its threat model (its `## Threat model` section,
or the decision it cites). Only blocking findings are fixed in the batch;
another goes to the backlog if it can occur in the project's normal use,
or if nothing catches its effect afterwards; otherwise, exotic and
caught, or unfounded, it is dismissed. In the backlog, it becomes a task
if its fix is clear, a need otherwise. A shell form an agent does not
write in its work, and that escapes the hook, is dismissed whatever its
effect: the guide gives the list of known forms. The recap gives the findings, and
why each dismissed one is.

By default, everything happens on one development branch, with only one
pull request open at a time: each finished batch is added to it, the
human merges it whenever they want, and the branch then starts again from
the default branch. One pull request per task, only if the human chose
it (a fact of the memory says so). A new session that finds another
session's pull request open asks the human to merge it first, or to let
it continue on it. A prototype not meant to be merged is done on a
disposable branch, named with a prefix of `[branches] disposable` in the
guardrails (`proto/` by default): the CI does not judge it on push.

### Before concluding

- `python3 .socle/socle verify --fast` passes (the `Stop` hook checks it); `verify` runs everything.
- If code changed, the memory did too: active work, journal, backlog.
- If code tied to a doc changed (`[[docmap]]` in the guardrails), the doc changes in the same work, or the commit that changes this code carries the trailer `Waive-doc: <reason>`, which covers that commit only.
- A fix (title `fix:` or trailer `Fixes: T-NNNN`) delivers a test that fails on the parent commit.
- A public function added or changed is named by at least one test, or a commit waives it by name with its reason (`Waive-test: f, g — <reason>`). Existing code found without tests: the test is written right away if it is within the scope of the work, otherwise a need goes to the backlog.
- An action only the human can take (refused by the hook, a service setting, a file they hold) goes to the backlog with `for : human`.
- **Every intervention that acted ends with a recap, then two lines**: `For you:` — what is up to the human, pending decisions and actions to take, or "nothing" —, each item understandable without the agent's reasoning (what it is, why, what their answer changes), and `Next:` — the proposed next step (next milestone, what remains before it), and what the agent is waiting for if it is waiting for something (a CI run, a match: what, and until when). The state computes what is up to the human; the `Stop` hook refuses to conclude without the two lines.
- **A file to read, or a pull request, is given by its link**: the human reads in the conversation or on GitHub, not in the agent's container. `python3 .socle/socle url <path|ID>` gives the permalink, once the file is pushed; a pending request cited without its link, a relative link, or a path between backticks that does not exist in the repository make the end of turn refused. A path in another repository is written `repo:path`, the repository linked somewhere in the project by its address (failing that, declared in `[references] repos` of the guardrails); an unknown repository is reported.

### Never

- complete a head SHA, invent an identifier or a reference: the hook refuses them;
- write to a protected file (policy, adapter, engine lock, hooks, CI, human answers);
- answer on the human's behalf (`socle answer` without `--relayed` and a quote), or run `socle approve` or `socle private install`, which are for the human only;
- bypass a hook (`--no-verify`): the agent's hook refuses it on the project's repository, and the CI runs everything;
- ask the human a question in the agent's question widget: the hook refuses it.

### What runs on its own

| Where | What |
| --- | --- |
| `.claude/settings.json` | Claude Code hooks: `SessionStart` (derived state; in a cloud session, the adapter's tools), `PreToolUse` (refusals), `Stop` (end-of-turn checks) |
| `.socle/git-hooks/` | git hooks: `pre-commit` (fast checks), `prepare-commit-msg` (`Socle-Hooks`, `Socle-Hooks-Since-Commit` trailers), `commit-msg` (private memory leaks; as warnings, a function with neither test nor waiver, a fix without a test, an agent commit without its hooks), `pre-push` (`verify --fast` on the last commit, the pushed range judged as in CI, review before publication) |
| `.github/workflows/socle.yml` | CI: adapter capabilities, all checks against the base, socle self-test, the project's roadmap as summary |
@@LIGNE_MUTATION@@
| `.git/socle/hooks.log` | local trace of every hook that fires, not versioned, shared by all worktrees of the repository |

List of checks: `python3 .socle/socle checks`.
