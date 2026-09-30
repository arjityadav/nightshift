# M0 · Engineering setup

**Time:** 3–4 sessions · **Tests:** `make check M=00` · **You'll have:** a professional Python repository on GitHub and your first test-driven module.

Most tutorials skip this part. Companies don't: every repository you'll work in has a dependency manager, a lock file, a linter, tests, pre-commit hooks and a Makefile. Setting them up yourself, once, is how you understand them.

---

## Concepts

**The terminal.** Everything in DevOps happens in a terminal: Docker, kubectl, Git, CI logs. You need about ten commands:

| Command | Does | Example |
|---|---|---|
| `pwd` | print the folder you're in | `pwd` |
| `ls -la` | list files, including hidden ones (`.gitignore`, `.env`) | `ls -la` |
| `cd` | change folder (`..` = up one, `~` = home) | `cd ~/code/nightshift` |
| `mkdir -p` | create folders | `mkdir -p tinyshop` |
| `cat` | print a file | `cat pyproject.toml` |
| `echo $VAR` | print an environment variable | `echo $PATH` |
| `export VAR=x` | set an environment variable for this terminal | `export DATABASE_URL=...` |
| `which` | where is this program? | `which python` |
| `Ctrl+C` | stop the running program | |
| `↑` / `Ctrl+R` | previous commands / search history | |

**Environment variables** are how every tool in this course gets configuration: `DATABASE_URL`, `OLLAMA_HOST`, `KUBECONFIG`. `PATH` is the list of folders the shell searches for programs; "command not found" usually means a folder is missing from `PATH`.

**Git** records snapshots of your project. Four places matter: your *working tree* (files on disk), the *staging area* (`git add` puts changes there), the *history* (`git commit` saves a snapshot) and the *remote* (GitHub; `git push` uploads). Branches are movable labels on commits; later you'll work on a branch, open a pull request and let CI check it before merging.

**uv** manages Python itself, your virtual environment (`.venv/`, a private copy of Python with your packages) and your dependencies. `pyproject.toml` lists what you *want* ("fastapi, version 0.115 or newer"); `uv.lock` records exactly what you *got* (one exact fastapi version and every sub-dependency, with hashes). Commit both. The lock file is why your laptop, CI and the Docker image all run identical versions.

**Tests and TDD.** pytest finds files named `test_*.py` and runs functions named `test_*`; a test passes if no `assert` fails. In test-driven development you write (or here: are given) the test first, watch it fail (red), write the simplest code that passes (green), then clean up (refactor).

**Linting and formatting.** ruff checks for bugs and bad patterns (unused imports, undefined names, mutable default arguments) and formats code consistently, so code reviews are about logic, not spaces.

**pre-commit** runs checks automatically every time you `git commit`, so bad code never reaches GitHub.

**Make** gives every project the same short commands (`make test`, `make lint`). Nobody remembers `uv run pytest -q tests/test_m01_*.py`; everybody remembers `make check M=01`.

---

## Step 1 · Install the tools

1. **A Unix terminal.**
   - Windows: install WSL2 with Ubuntu (`wsl --install` in PowerShell as administrator, then restart). Do **everything** in this course inside Ubuntu, and keep your code in the Linux home folder (`~/code`), not under `/mnt/c`, which is much slower.
   - Mac: the built-in Terminal. Install Homebrew (https://brew.sh) for the other tools.
   - Linux: you're set.
2. **Git:** `sudo apt install git make` (Ubuntu/WSL) or `brew install git` (Mac; `make` is included with the Xcode command-line tools: `xcode-select --install`).
3. **uv:** follow https://docs.astral.sh/uv/getting-started/installation/ (a one-line installer). Then `uv --version`.
4. **VS Code** with the extensions *Python*, *Ruff*, and on Windows *WSL*. On Windows, open the project with `code .` from the Ubuntu terminal.
5. **A GitHub account** and the GitHub CLI (`sudo apt install gh` or `brew install gh`), then `gh auth login`.

Tell Git who you are (this appears on every commit):
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

## Step 2 · Create the repository

Unzip the starter (it only contains `docs/`, `tests/`, a README and a `CLAUDE.md` with instructions for Claude Code), then:
```bash
mkdir -p ~/code && cd ~/code
unzip ~/Downloads/nightshift.zip        # adjust the path
cd nightshift
git init
git add . && git commit -m "Starter: docs and tests"
```

## Step 3 · The Python project

```bash
uv init --bare --name nightshift --python 3.12
uv add --dev pytest httpx ruff pre-commit pyyaml
```
- `uv init --bare` creates only `pyproject.toml`. Open it and read it.
- `uv add --dev ...` adds *development* tools: needed to test and lint, but not in production. uv writes them under `[dependency-groups]`, creates `.venv/`, installs everything, and writes `uv.lock`.
- Look at what happened: `cat pyproject.toml`, `ls -la`, `head -30 uv.lock`.

Now the package that will hold TinyShop:
```bash
mkdir tinyshop
```
Create `tinyshop/__init__.py`:
```python
"""TinyShop: the small online shop that Nightshift will operate."""

__version__ = "0.1.0"
```
A folder with an `__init__.py` is a Python *package*: `import tinyshop` now works. `__version__` follows *semantic versioning*: MAJOR.MINOR.PATCH.

## Step 4 · Configure ruff and pytest

Add to the end of `pyproject.toml`:
```toml
[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]   # pycodestyle, pyflakes, import sorting, bugbear, pyupgrade

[tool.ruff.lint.isort]
known-first-party = ["tinyshop", "tests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["postgres: needs a running PostgreSQL (TEST_DATABASE_URL)"]
```

## Step 5 · `.gitignore`

Create `.gitignore`:
```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
```
`.env` will hold passwords later. Ignoring it **before** it exists is how you make sure a secret never lands in Git history, where deleting the file doesn't remove it.

## Step 6 · Makefile

Create `Makefile`. **Recipe lines must start with a TAB character, not spaces.** VS Code shows the difference in the bottom-right corner ("Spaces: 4" vs "Tab Size: 4"); if `make` says `missing separator`, that's the cause.

```makefile
.PHONY: install test lint fmt check run

install:            ## install dependencies and git hooks
	uv sync
	uv run pre-commit install

test:               ## all tests
	uv run pytest -q

lint:               ## check style and bugs
	uv run ruff check .
	uv run ruff format --check .

fmt:                ## fix what can be fixed automatically
	uv run ruff check --fix .
	uv run ruff format .

check:              ## one module's tests: make check M=01
	uv run pytest -q tests/test_m$(M)_*.py

run:                ## start TinyShop with auto-reload (from M1)
	uv run uvicorn tinyshop.main:app --reload
```
- A *target* (`test:`) is a name; the indented lines below it are shell commands.
- `$(M)` is a variable you pass on the command line: `make check M=00`.
- `.PHONY` says these targets are commands, not files.
- `uv run X` runs X inside your project's virtual environment, so you never need to "activate" it.

## Step 7 · pre-commit

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: detect-private-key
```
Then:
```bash
make install                        # installs the git hook
uv run pre-commit autoupdate        # bumps `rev:` to the newest versions
uv run pre-commit run --all-files   # run all hooks once on everything
```
From now on, `git commit` runs these hooks first. If a hook changes a file, the commit stops: look at the change, `git add` it, and commit again. `detect-private-key` blocks commits that contain private keys, a small but real safety net.

Run the setup checks:
```bash
make check M=00
```
`test_m00_setup.py` should now pass; `test_m00_money.py` fails because `tinyshop/money.py` doesn't exist yet. That's your next step.

## Step 8 · Your first TDD module: money

**Why integer cents?** Try this in `uv run python`:
```python
>>> 0.1 + 0.2
0.30000000000000004
>>> 0.1 + 0.2 == 0.3
False
```
Floats are binary fractions and can't represent most decimal amounts exactly. Small errors add up across thousands of orders, and totals stop matching. Every serious payment system stores money as integers in the smallest unit (cents), or as `Decimal`. TinyShop uses cents everywhere: `price_cents = 1299` means €12.99.

Open `tests/test_m00_money.py` and read it: the tests are the specification. Then create `tinyshop/money.py` with these three functions:

```python
def to_cents(amount: str) -> int:
    """Convert a text amount in euros to integer cents.

    "19.99" -> 1999, "19,99" -> 1999 (German comma), "5" -> 500, "0.5" -> 50, " 7.10 " -> 710.
    Surrounding spaces are allowed. At most 2 decimals. Raise ValueError for anything else:
    "", "abc", "1.999", "-5", "1.2.3", "€5".
    Never convert through float.
    """


def format_eur(cents: int) -> str:
    """1999 -> "19.99 EUR", 5 -> "0.05 EUR", 0 -> "0.00 EUR". Negative -> ValueError."""


def split_evenly(cents: int, parts: int) -> list[int]:
    """Split an amount into `parts` shares that differ by at most 1 cent and sum EXACTLY to `cents`.
    The first shares get the extra cents: split_evenly(1000, 3) -> [334, 333, 333].
    parts <= 0 -> ValueError."""
```

Work in the TDD loop: run `make check M=00`, read the first failure, make it pass, repeat.

<details>
<summary>Hints (open only if stuck)</summary>

- `to_cents`: strip, then either a regular expression like `^(\d+)(?:[.,](\d{1,2}))?$` (Python's `re` module), or split on `.`/`,` and check each part with `str.isdigit()`. Watch out for "0.5": the fraction "5" means 50 cents, not 5. `str.ljust(2, "0")` pads "5" to "50".
- `format_eur`: `cents // 100` and `cents % 100`, and an f-string with `:02d` to pad to two digits.
- `split_evenly`: `divmod(cents, parts)` gives the base share and the remainder; the first `remainder` shares get one extra cent.
</details>

## Step 9 · Push to GitHub

```bash
make lint           # fix anything it reports (make fmt fixes most)
make test           # M0 tests green; M1+ tests fail for now, which is expected
git add .
git commit -m "M0: project setup and money helpers"
gh repo create nightshift --public --source . --push
```
A **public** repository gives you free CI minutes (M5) and free image hosting (GHCR) later, and recruiters can see it. That's also why secrets never go into it.

---

## Definition of done

- [ ] `make check M=00` is green.
- [ ] `make lint` is clean, and `git commit` runs the pre-commit hooks.
- [ ] The repository is on GitHub with `pyproject.toml`, `uv.lock`, `.gitignore`, `Makefile`, `.pre-commit-config.yaml` and `tinyshop/`.
- [ ] `git log --oneline` shows small, meaningful commits.

## Interview questions

1. **What's the difference between `pyproject.toml` and `uv.lock`?** The first declares the dependencies you want, with version ranges; the lock file pins the exact resolved versions of everything (including sub-dependencies), so every environment installs identical packages. Commit both.
2. **Why is floating point wrong for money? What do you use instead?** Binary floats can't represent most decimals exactly, so rounding errors accumulate. Use integer minor units (cents) or `Decimal`.
3. **What happens if you commit a password and delete it in the next commit?** It stays in Git history and anyone with the repository can read it. Rotate the secret immediately; rewriting history is a clean-up step, not a fix. Prevent it with `.gitignore` and hooks like `detect-private-key`.
4. **What is TDD, and when is it most useful?** Write a failing test, make it pass, refactor. Most useful when the behaviour is clear and edge cases matter, like money, parsing or permissions.
5. **What's a virtual environment, and why use one?** A per-project Python environment with its own packages, so projects don't break each other and you can reproduce the exact setup.

**Next:** [M1 · HTTP APIs with FastAPI](M01-fastapi.md)
