---
name: socle-private-memory
description: Work with the project's private memory, when the policy chooses one: where new content goes, moving a public entry to private, committing in companion mode, adding a private term, having a review before publication. Use before writing an entry, committing or pushing in a project that has a private memory.
---

# The private memory

If the policy chooses one (`[private] mode`, in `.socle/policy.toml`), part
of the memory lives in a private zone, under memory/private/. The state says
whether it is available; unavailable, nothing is concluded about what
depends on it.

## Writing

- New content goes into the private zone for the layers the policy makes
  private: `socle new` does it by default.
- An instruction from the human about a given entry is followed with
  `socle new … --private` or `--public`.
- A new private name (an idea, a client) is added to the list of private
  terms; only the human removes one:

```sh
python3 .socle/socle private term <term>
```

## Moving a public entry to private

```sh
python3 .socle/socle private move <ID>
```

The public history keeps the old text: tell the human.

## Copying nothing to public

Nothing private is copied to public: neither a `P…` identifier, nor its
content, nor in a commit message, a pull request or a comment. The hooks
and the CI refuse a leak.

## Committing in companion mode

A private change is committed in the private repository, then the lock
moves forward in the public repository:

```sh
python3 .socle/socle private lock
```

## Having a review before publication

If the policy requires a review (`[private] review`), show the human what
is leaving, then record their agreement with their exact text, at each push
or in batches:

```sh
python3 .socle/socle reviewed --relayed --by <name> --quote-file <file>
```

## A private request

Encrypted, it cannot be read on GitHub: give it in full in the
conversation.

Setting up the private memory (`socle private install`) is for the human
only.
