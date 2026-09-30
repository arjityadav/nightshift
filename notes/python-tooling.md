# Python tooling (uv, pyproject, packages)

## Concepts
- **uv** manages the Python version, the virtual environment (`.venv/`) and dependencies.
- **`pyproject.toml`** = what I *want* (ranges like `pytest>=9.1.1`). **`uv.lock`** = what I *got* (exact versions of everything incl. sub-dependencies, with hashes). Commit both.
- **`[dependency-groups] dev`** = tools needed to develop/test (pytest, ruff, pre-commit), not to run the app. Production images install without them → smaller, fewer vulnerable packages.
- **`[tool.<name>]`** tables: one file configures many tools; each tool reads only its own table.
- **`uv run X`** runs X inside the project venv; no need to activate it.
- **Virtual environment:** per-project Python with its own packages, so projects don't break each other.

## Packages and `__init__.py`
- A folder with `__init__.py` is a **regular package** → `import tinyshop` works.
- `__init__.py` runs **once**, on first import (then cached in `sys.modules`).
- Names defined there become package attributes (`tinyshop.__version__`).
- It does **not** import submodules automatically: `tinyshop.money` loads only when imported.
- Without `__init__.py`, Python 3.3+ treats a folder as a *namespace package*; we still add one for explicitness and tooling.
- `__version__ = "0.1.0"` → semantic versioning MAJOR.MINOR.PATCH.

## Commands
```bash
uv init --bare --name nightshift --python 3.12
uv add --dev pytest ruff          # dev dependency
uv add fastapi                    # runtime dependency
uv sync                           # install exactly what uv.lock says
uv run python / uv run pytest
```

## Interview questions

**Difference between `pyproject.toml` and `uv.lock`?**
<details><summary>Answer</summary>
pyproject declares the dependencies you want with version ranges; the lock file pins the exact resolved versions of everything, so laptop, CI and Docker install identical packages. Commit both.
</details>

**What is a virtual environment and why use one?**
<details><summary>Answer</summary>
An isolated per-project Python with its own installed packages, so projects with different versions don't conflict and the setup is reproducible.
</details>

**What does `__init__.py` do?**
<details><summary>Answer</summary>
Makes a folder a regular package; runs once on first import and defines the package's top-level names; does not import submodules automatically.
</details>

**Why separate dev dependencies?**
<details><summary>Answer</summary>
Production doesn't need test/lint tools; leaving them out makes images smaller and reduces attack surface.
</details>
