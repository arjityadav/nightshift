# Testing (pytest, TDD)

## Concepts
- pytest finds `test_*.py` files and `test_*` functions; a test passes if no `assert` fails.
- `assert cond, "message"`: the message is the hint shown when it fails.
- **TDD:** red (failing test) → green (simplest code that passes) → refactor. Tests are the specification.
- **Two phases:** *collection* (import every test file) then *running*. An import error in one file = collection error → pytest **interrupts the whole run**, even unrelated tests don't run.
- Output symbols: `.` pass, `F` fail, `E` error, `s` skipped.
- **Exit codes:** 0 all passed, 1 some failed, 2 interrupted/collection error. Make and CI treat any non-zero as failure.
- `testpaths = ["tests"]` → plain `pytest` only searches `tests/`.
- **Markers:** `@pytest.mark.postgres` labels tests (e.g. need a database) so they can be selected/skipped; registering them in config avoids warnings.

## Commands
```bash
uv run pytest -q                          # all tests, quiet
uv run pytest -q tests/test_m00_setup.py  # one file
make check M=00                           # one module
uv run pytest -k split                    # tests whose name matches
uv run pytest -x                          # stop at first failure
```

## Interview questions

**What is TDD and when is it most useful?**
<details><summary>Answer</summary>
Write a failing test, make it pass, refactor. Most useful when behaviour is clear and edge cases matter: money, parsing, permissions.
</details>

**A test file has an ImportError. What happens to the other tests?**
<details><summary>Answer</summary>
It's a collection error; pytest interrupts the run (exit code 2) and no tests run. Run a subset of files, or fix the import.
</details>

**Why do exit codes matter?**
<details><summary>Answer</summary>
Make, CI and scripts decide success/failure by the exit code (0 = success). That's how a failing test turns a CI build red.
</details>
