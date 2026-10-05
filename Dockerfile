# ---- build stage: install dependencies with uv ----
FROM python:3.12-slim AS builder
# copy the uv binary from uv's official image; use the version `uv --version` shows
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
# compile .pyc files now (faster start); copy files instead of hard-linking; use the image's Python
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# 1) only the dependency files: this layer is cached until pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
# 2) install EXACTLY the locked versions (--frozen), without pytest/ruff (--no-dev), into /app/.venv
RUN uv sync --frozen --no-dev --no-install-project
# 3) your code last: it changes most often
COPY tinyshop ./tinyshop

# ---- runtime stage: small image, non-root user ----
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /app /app
# use the virtual environment's python/uvicorn; print logs immediately (no buffering)
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# exec form (a JSON list): uvicorn runs as PID 1 and receives the stop signal directly
CMD ["uvicorn", "tinyshop.main:app", "--host", "0.0.0.0", "--port", "8000"]
