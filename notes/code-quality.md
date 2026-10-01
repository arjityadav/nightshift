# Code quality (ruff, pre-commit)

## ruff rule sets (`select = [...]`)
| Code | Origin | Catches | Example |
|---|---|---|---|
| E | pycodestyle | PEP 8 style | `x == None` → `x is None` |
| F | pyflakes | real bugs / dead code | unused import, undefined name |
| I | isort | import order | stdlib → third-party → first-party |
| B | bugbear | likely bugs | mutable default argument |
| UP | pyupgrade | old syntax | `List[int]` → `list[int]` |

- `line-length = 110`, `target-version = "py312"`, `known-first-party = ["tinyshop", "tests"]`.
- `ruff check` = lint, `ruff format` = formatter. `make lint` checks, `make fmt` fixes.

### Mutable default argument (B006)
```python
def add(item, items=[]):  # default created ONCE, at definition time
    items.append(item)
    return items


add(1)  # [1]
add(2)  # [1, 2]  ← shared list
# fix: items=None; if items is None: items = []
```

## pre-commit
- Git hooks = scripts Git runs at certain moments; pre-commit manages them from `.pre-commit-config.yaml`.
- `pre-commit install` writes `.git/hooks/pre-commit` (local, not cloned → every machine must install).
- On `git commit` the hooks run on staged files; any failure blocks the commit.
- A hook that **fixes** files (end-of-file-fixer, trailing-whitespace, ruff --fix) reports "Failed" → review `git diff`, `git add`, commit again.
- `pre-commit autoupdate` bumps `rev:` versions; `pre-commit run --all-files` runs everything once.
- YAML indents with **spaces** (Makefile needs **tabs**).
- Gotcha: `ruff format` also formats **Python code blocks inside Markdown**. Exclude folders you don't own (course docs) with `extend-exclude = ["docs"]` under `[tool.ruff]`; undo unwanted changes with `git restore <path>`.
- Hook id `ruff` is a legacy alias; the current id is `ruff-check`.

## Interview questions

**Why use a linter and formatter?**
<details><summary>Answer</summary>
Catch bugs early (undefined names, mutable defaults) and enforce one style automatically, so code reviews are about logic, not formatting.
</details>

**Explain the mutable default argument bug.**
<details><summary>Answer</summary>
Default values are evaluated once when the function is defined, so a list default is shared across calls. Use `None` and create the list inside.
</details>

**What are pre-commit hooks and their limits?**
<details><summary>Answer</summary>
Checks that run before each commit for fast feedback. Limits: installed per machine, skippable with `--no-verify`, don't run for web/bot commits. So re-run the same checks in CI.
</details>
