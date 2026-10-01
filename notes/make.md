# Make

## Concepts
- Short, shared commands for a project: `make test`, `make lint`, `make check M=00`.
- **Target** (`test:`) + **recipe** (indented shell lines below it).
- Recipe lines must start with a **TAB**, otherwise `missing separator`. Check with `cat -et Makefile` → tabs show as `^I`.
- **Variables:** `make check M=00` → `$(M)` becomes `00`.
- Make prints each command before running it; the shell expands globs (`test_m00_*.py`) before the program starts.
- Stops at the first command with a non-zero exit code: `make: *** [check] Error 2`.

## `.PHONY`
Make was built to produce **files**: a target is a filename, and if that file exists and is up to date Make does nothing. If a file named `test` existed, `make test` would print "up to date" and **not run the tests**. `.PHONY: test lint ...` says these targets are commands, always run them.

## Error messages
- `No rule to make target 'check'` → Makefile found but no `check:` target (e.g. file empty/unsaved).
- `No targets specified and no makefile found` → no Makefile at all.
- `missing separator` → spaces instead of a TAB.

## Interview questions

**What does `.PHONY` do?**
<details><summary>Answer</summary>
Marks targets that are commands, not files, so Make always runs them even if a file with that name exists.
</details>

**Why have a Makefile in a Python project?**
<details><summary>Answer</summary>
One consistent, documented entry point for common tasks: same commands for every developer and for CI; nobody has to remember long tool invocations.
</details>
