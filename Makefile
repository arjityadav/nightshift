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
