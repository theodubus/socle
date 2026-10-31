What now falls to the agent (brief, "Initialization" section):

1. **The starting questions**: read them again, add some if the input calls
   for it (a gap or a contradiction in the document), without exceeding the
   cap, then give them to the human in the conversation, with their link.
   Their answer is recorded with its exact text (`socle answer … --relayed`).
2. **A brief**: draw from it the goals, the constraints and the decisions,
   without rewriting it. Each fact drawn from the document is "assumed",
   with the document as its source
   (`source : file:memory/archives/<document>#<section>`); each goal becomes
   a backlog topic, with the same origin.
3. **An existing repository**: the facts measured by the audit are laid
   down; only add what a command or a file proves, the rest is "assumed" or
   becomes a question.
4. **Both together**: the repository is authoritative for what exists (code,
   tests, tools, CI), the document for what is wanted; any divergence becomes
   a question, never a silent correction.
5. **Nothing**: the memory stays empty; the checks are already active, the
   rest is discovered while working.

No fact without a source, except "assumed": `socle verify` checks it.
