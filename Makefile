.PHONY: install test lint fmt check run up down db test-db

install:            ## install dependencies and git hooks
	uv sync
	uv run pre-commit install

test:               ## all tests
	uv run pytest -q

lint:               ## check style and bugs
	uv run ruff check .
	uv run ruff format --check .

fmt:                ## fix what can be fixed automatically
	uv run ruff format .
	uv run ruff check --fix .

check:              ## one module's tests: make check M=01
	uv run pytest -q tests/test_m$(M)_*.py

run:                ## start TinyShop with auto-reload (from M1)
	uv run uvicorn tinyshop.main:app --reload

up:                 ## start the stack in the background
	docker compose up -d --build

down:               ## stop the stack (keeps data)
	docker compose down

db:                 ## start only the database
	docker compose up -d db

test-db:            ## PostgreSQL tests against the tinyshop_test database (make db first)
	TEST_DATABASE_URL=postgresql://tinyshop:tinyshop@localhost:5432/tinyshop_test uv run pytest -q -m postgres
