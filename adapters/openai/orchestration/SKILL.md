---
name: orchestration
description: Operate and verify a local Master plus registered execution fronts with a transactional, root-bound CLI. Use for read-only work-block openings, front selection, initialization preview/apply, structural sync, explicit reflection and registration, closeout, narrow panel repair, or durable journal recovery.
---

# Orchestration

Operate the already installed agent-agnostic runtime at
`<target>/.agent-harnesses/runtime/orchestration/0.2.2/`. Treat that runtime's
`operations.json` as the machine-readable command authority and its operator
guide as the user-facing contract. This optional adapter does not replace or
install the runtime. Pass the intended existing workspace with `--root`; never
infer a different root from historical context.

Use global flags before the command:

```text
python3 -B <target>/.agent-harnesses/runtime/orchestration/0.2.2/hq.py --root <workspace> --json <command>
```

## Open read-only

Run `bom-dia` first. Keep it read-only.

- If it reports `uninitialized`, preview `init --dry-run` with an explicit ID,
  name, relative path, and optional aliases. Apply only after reviewing the
  preview.
- If it reports `inconsistent`, run `hq-sync`. Do not mutate around an issue.
- If it reports `recovery-required`, inspect `recover --dry-run`.
- If it reports `focus-required`, run `foco <selector>` or pass `--front` to
  the lifecycle command.

## Operate one work block

1. Run `hq-sync`; require `clean: true`.
2. Select the intended front with `foco <selector>` when needed.
3. Run `digere --summary <text> --pending <text> [--front <selector>]`. Do not
   invent a digest.
4. Run `registra [--note <text>] [--front <selector>]`.
5. Run `encerra --summary <text> --next <text> [--front <selector>]`.
6. Run `bom-dia [selector]` again to verify the next opening.

Initialization uses:

```text
init --id <id> --name <name> --path <relative-path> [--alias <alias>] --dry-run
init --id <id> --name <name> --path <relative-path> [--alias <alias>] --apply
```

Never edit the manifest or generated pending files as a substitute for these
commands.

## Recover or repair

Preview recovery before apply. Break a stale lock only when the lock exactly
matches the durable journal and explicit authorization is appropriate.

Use `repair-panel` only for a missing or mismatched generated `FRONTS.md`.
Preview first. If any manifest, path, alias, front file, boundary, or symlink
issue exists, stop; repair deliberately refuses repoint, delete, merge, and
conflict resolution.

## Preserve evidence

Separate:

- automated package tests;
- the isolated structural check;
- a real CLI walkthrough in a disposable workspace.

Treat `hq-sync` and dry-run output as structural evidence, not proof of an
external review, test suite, commit, publication, or remote state.
