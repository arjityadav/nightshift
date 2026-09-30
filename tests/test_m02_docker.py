"""M2 · Docker. These tests read your Dockerfile and compose.yaml; the real test is running them
(see "Definition of done" in the lesson).   make check M=02"""

import re

import pytest
import yaml


def _stages(root):
    path = root / "Dockerfile"
    assert path.exists(), "create a Dockerfile in the repository root"
    text = path.read_text()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    stages, current = [], None
    for ln in lines:
        if ln.upper().startswith("FROM "):
            current = [ln]
            stages.append(current)
        elif current is not None:
            current.append(ln)
    return stages


def test_multi_stage_build(root):
    stages = _stages(root)
    assert len(stages) >= 2, "use a multi-stage build: a builder stage and a small runtime stage"
    assert re.search(r"\bAS\s+\w+", stages[0][0], re.I), "name the first stage, e.g. FROM ... AS builder"


def test_base_image_is_pinned_and_slim(root):
    for stage in _stages(root):
        image = stage[0].split()[1]
        assert ":" in image and not image.endswith(":latest"), f"pin a version tag, not {image}"
    assert "slim" in _stages(root)[-1][0], "use a slim base image for the runtime stage"


def test_runtime_runs_as_non_root(root):
    final = _stages(root)[-1]
    users = [ln.split()[1] for ln in final if ln.upper().startswith("USER ")]
    assert users, "add a USER instruction to the final stage (never run as root)"
    assert users[-1] not in ("root", "0"), "the final USER must not be root"


def test_runtime_serves_on_all_interfaces(root):
    final = " ".join(_stages(root)[-1])
    assert "uvicorn" in final and "tinyshop.main:app" in final
    assert "0.0.0.0" in final, "inside a container, listen on 0.0.0.0, not 127.0.0.1"
    assert re.search(r"CMD\s+\[", final), 'use the exec form: CMD ["uvicorn", ...]'


def test_dependencies_are_installed_before_copying_code(root):
    builder = _stages(root)[0]
    text = "\n".join(builder)
    lock_copy = text.find("pyproject.toml")
    code_copy = text.find("COPY tinyshop")
    install = text.find("uv sync")
    assert -1 not in (lock_copy, code_copy, install), "builder: copy pyproject/uv.lock, uv sync, copy code"
    assert lock_copy < install < code_copy, "copy the lock file and install BEFORE copying code (caching)"
    assert "--frozen" in text and "--no-dev" in text, "install exactly the locked versions, without dev tools"


def test_no_secrets_in_image(root):
    text = (root / "Dockerfile").read_text().upper()
    for bad in ("PASSWORD=", "SECRET=", "API_KEY=", "COPY .ENV"):
        assert bad not in text, f"never bake secrets into an image ({bad})"


def test_dockerignore(root):
    path = root / ".dockerignore"
    assert path.exists(), "create .dockerignore"
    entries = {ln.strip().rstrip("/") for ln in path.read_text().splitlines()}
    for entry in (".venv", ".git", ".env"):
        assert entry in entries, f"{entry} must be in .dockerignore"


@pytest.fixture
def compose(root):
    path = root / "compose.yaml"
    assert path.exists(), "create compose.yaml"
    return yaml.safe_load(path.read_text())


def test_compose_api_service(compose):
    api = compose["services"]["api"]
    assert api.get("build") in (".", {"context": "."}) or "build" in api
    assert any(str(p).endswith(":8000") for p in api.get("ports", [])), "publish port 8000"


def test_compose_db_service(compose):
    db = compose["services"]["db"]
    assert db["image"].startswith("postgres:16"), "use the official postgres:16 image"
    assert "healthcheck" in db and "pg_isready" in str(db["healthcheck"]["test"])
    volumes = [str(v) for v in db.get("volumes", [])]
    assert any(v.startswith("pgdata:") for v in volumes), "keep data in a named volume `pgdata`"
    assert "pgdata" in (compose.get("volumes") or {}), "declare the named volume at the top level"
    env = db.get("environment", {})
    assert "${" in str(env.get("POSTGRES_PASSWORD", "")), (
        "read the password from an env variable: ${POSTGRES_PASSWORD:-...}"
    )
