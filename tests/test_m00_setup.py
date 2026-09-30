"""M0 · Project setup.   make check M=00"""

import tomllib


def _pyproject(root):
    path = root / "pyproject.toml"
    assert path.exists(), "create pyproject.toml with `uv init` (see lesson M0, step 3)"
    return tomllib.loads(path.read_text())


def test_pyproject_basics(root):
    data = _pyproject(root)
    assert data["project"]["name"] == "nightshift"
    assert data["project"]["requires-python"].startswith(">=3.12")


def test_dev_tools_are_dev_dependencies(root):
    dev = " ".join(_pyproject(root).get("dependency-groups", {}).get("dev", []))
    for tool in ("pytest", "ruff", "pre-commit"):
        assert tool in dev, f"add {tool} with: uv add --dev {tool}"


def test_ruff_is_configured(root):
    ruff = _pyproject(root).get("tool", {}).get("ruff", {})
    assert "line-length" in ruff, "add a [tool.ruff] section with line-length"
    assert "select" in ruff.get("lint", {}), "add [tool.ruff.lint] select = [...]"


def test_gitignore_keeps_secrets_and_junk_out(root):
    path = root / ".gitignore"
    assert path.exists(), "create .gitignore"
    text = path.read_text()
    for entry in (".env", ".venv", "__pycache__"):
        assert entry in text, f"{entry} must be in .gitignore"


def test_pre_commit_runs_ruff(root):
    path = root / ".pre-commit-config.yaml"
    assert path.exists(), "create .pre-commit-config.yaml"
    assert "ruff" in path.read_text()


def test_makefile_targets(root):
    path = root / "Makefile"
    assert path.exists(), "create a Makefile"
    text = path.read_text()
    for target in ("install:", "test:", "lint:", "check:"):
        assert f"\n{target}" in "\n" + text, f"Makefile needs a `{target}` target"
    assert "\n\t" in text, "Makefile recipe lines must start with a TAB, not spaces"


def test_package_exists():
    import tinyshop

    assert isinstance(tinyshop.__version__, str) and tinyshop.__version__.count(".") == 2
