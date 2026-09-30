# Nightshift

**An AI on-call engineer for Kubernetes**, built from scratch: a FastAPI + PostgreSQL shop service, Docker, Kubernetes, GitOps, observability, MLOps, RAG, multi-agent LLMs and LLMOps, all free and running on your laptop.

This starter contains only:

- `docs/BLUEPRINT.md`: what you'll build, the architecture, the free stack, the rules the project follows, all modules, and the results and resume bullets you'll fill in.
- `docs/modules/`: step-by-step lessons (M0–M3 now; the next ones are written when you reach them).
- `tests/`: one test file per module. They're the specification: when they're green, the step is done.

Everything else, you write.

## Start here

1. Read [docs/BLUEPRINT.md](docs/BLUEPRINT.md) (15 minutes).
2. Open [docs/modules/M00-setup.md](docs/modules/M00-setup.md) and follow it from the top.

| Module | Lesson | Check |
|---|---|---|
| M0 | [Engineering setup](docs/modules/M00-setup.md) | `make check M=00` |
| M1 | [HTTP APIs with FastAPI](docs/modules/M01-fastapi.md) | `make check M=01` |
| M2 | [Docker](docs/modules/M02-docker.md) | `make check M=02` |
| M3 | [PostgreSQL](docs/modules/M03-postgres.md) | `make check M=03`, `make test-db` |
| M4–M13 | observability, CI, Kubernetes, GitOps, MLOps, RAG, agents, multi-agents, LLMOps, production | see the blueprint |

*(Replace this README with your own project README in M13: what Nightshift does, a demo GIF, architecture, results table, how to run it.)*
