# M2 · Docker

**Time:** ~1 week · **Tests:** `make check M=02` · **You'll have:** TinyShop as a small, secure container image, plus a Compose stack with the API and a PostgreSQL database (which the app starts using in M3).

"It works on my machine" stops being an excuse with containers: the image contains the exact Python, packages and code, and runs the same on your laptop, in CI and in Kubernetes. Every later module builds on this one.

---

## Concepts

| Term | Meaning | Analogy |
|---|---|---|
| **Image** | a read-only template: filesystem + metadata (what to run, which port) | a class |
| **Container** | a running (or stopped) instance of an image, with its own writable layer | an object |
| **Dockerfile** | the recipe that builds an image, one instruction per line | source code |
| **Layer** | each instruction adds a layer; layers are cached and shared | git commits |
| **Registry** | where images are stored: Docker Hub, GHCR (M5) | GitHub for images |
| **Tag** | a name for a version: `python:3.12-slim`, `tinyshop:0.1.0` | a git tag |
| **Volume** | storage that outlives containers (database files) | an external drive |

**A container is not a virtual machine.** It's a normal Linux process that the kernel isolates (namespaces: its own filesystem view, network, process list) and limits (cgroups: CPU and memory). That's why containers start in milliseconds, and why Kubernetes can run many of them per machine. On Mac and Windows, Docker Desktop runs a small Linux VM in the background for you.

**Layer caching** is the most important performance idea. Docker reuses a cached layer if the instruction *and everything before it* are unchanged. So you order instructions from "changes rarely" to "changes often": base image → dependencies → your code. Then editing `api.py` rebuilds in seconds instead of reinstalling every package.

**Multi-stage builds** use one stage with build tools to prepare the app and a second, clean stage that only copies the result. The final image doesn't contain the build tools, so it's smaller and has less to attack.

**Never run as root.** By default, a process in a container runs as root. If someone exploits your app, a root process makes escaping the container or damaging mounted files much easier. Create a user and switch to it. Kubernetes can enforce this (M13).

**Configuration comes from the environment**, not from the image: the same image runs in dev, staging and prod with different environment variables (the *Twelve-Factor App* principle). Secrets are never baked into an image: anyone who can pull the image can read every layer.

**Compose** describes several containers that belong together (API + database), their network, volumes and start order, in one YAML file. On the Compose network, containers reach each other **by service name**: from the `api` container, the database host is `db`, not `localhost`. Inside a container, `localhost` is the container itself.

**YAML in 30 seconds.** Indentation (spaces only, never tabs) means nesting; `key: value` is a mapping; `- item` is a list entry. Quote strings that contain `:` or start with special characters. You'll write a lot of YAML: Compose, GitHub Actions, Kubernetes, Helm.

---

## Step 1 · Install and warm up

Install **Docker Desktop** (Windows: enable "Use WSL 2 based engine" and WSL integration for your Ubuntu; Mac: the Apple-silicon or Intel build) or **Docker Engine** on Linux. Check: `docker version` and `docker compose version`.

Warm up, and read what each command prints:
```bash
docker run hello-world                        # pull an image, run it, exit
docker run -it --rm python:3.12-slim python   # an interactive Python in a container; exit()
docker run -d --name web -p 8080:80 nginx:1.27  # -d background, -p host:container port
curl -s localhost:8080 | head -5
docker ps                                     # running containers
docker logs web                               # its output
docker exec -it web sh                        # a shell INSIDE the container; try ls /, whoami, exit
docker stop web && docker rm web
docker images                                 # images on your machine and their sizes
```

## Step 2 · A naive Dockerfile first (to see the problems)

Create `Dockerfile`:
```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install fastapi "uvicorn[standard]"
CMD ["uvicorn", "tinyshop.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
```bash
docker build -t tinyshop:naive .
docker run --rm -p 8000:8000 tinyshop:naive      # open http://localhost:8000/docs, then Ctrl+C
docker images tinyshop                            # note the SIZE
docker run --rm tinyshop:naive whoami             # root!
docker run --rm tinyshop:naive ls -a              # .venv, .git ... all copied in
```
Now change one line in `tinyshop/api.py` and build again: pip reinstalls everything, because `COPY . .` came before `pip install`. Problems to fix:
1. **Huge** (the full `python:3.12` image is around 1 GB).
2. **Runs as root.**
3. **Copies everything**, including `.venv`, `.git` and, one day, `.env` with passwords.
4. **No caching** of dependencies.
5. **Ignores `uv.lock`**, so versions can differ from what you tested.

## Step 3 · `.dockerignore`

The *build context* is everything Docker sends to the builder (the `.` in `docker build .`). Keep junk and secrets out of it. Create `.dockerignore`:
```text
.venv
.git
.env
__pycache__
.pytest_cache
.ruff_cache
tests
docs
```

## Step 4 · The production Dockerfile

Replace the `Dockerfile` with this. Read every comment; you'll be asked about these choices in interviews.

```dockerfile
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
```

Why `--host 0.0.0.0`? `127.0.0.1` means "only this container itself", so the port mapping from your laptop couldn't reach it. `0.0.0.0` means "every network interface of the container".

Why the exec form `CMD ["uvicorn", ...]` and not `CMD uvicorn ...`? The shell form starts `/bin/sh -c`, which doesn't forward `SIGTERM`, so `docker stop` (and Kubernetes) would wait 10 seconds and then kill your app instead of letting it shut down cleanly.

Build and compare:
```bash
docker build -t tinyshop:0.1.0 .
docker images tinyshop                       # compare with :naive
docker run --rm tinyshop:0.1.0 whoami        # app
docker run -d --name shop -p 8000:8000 tinyshop:0.1.0
sleep 15 && docker ps                         # STATUS shows (healthy)
curl -s localhost:8000/health
docker stop shop && docker rm shop
```
**Experiment:** change a string in `api.py` and rebuild. The output shows `CACHED` for the `uv sync` step; only the last `COPY` reruns. Then change `pyproject.toml` (add a comment) and watch the dependency layer rebuild.

**Experiment:** `docker history tinyshop:0.1.0` shows every layer and its size.

## Step 5 · Compose: API + PostgreSQL

TinyShop doesn't use a database yet (M3), but you'll set up the database container now so the stack is ready.

First, the init script that creates a second, empty database for tests. Create `deploy/postgres/init.sql`:
```sql
-- Runs once, when the database volume is first created.
CREATE DATABASE tinyshop_test;
```

Then `compose.yaml`:
```yaml
services:
  api:
    build: .                       # build the Dockerfile in this folder
    ports:
      - "8000:8000"                # host:container
    environment:
      # the host is `db`: the service name below. The app starts using this in M3.
      DATABASE_URL: postgresql://tinyshop:${POSTGRES_PASSWORD:-tinyshop}@db:5432/tinyshop
    depends_on:
      db:
        condition: service_healthy # wait until the db healthcheck passes, not just "started"
    restart: unless-stopped

  db:
    image: postgres:16             # official image, pinned major version
    environment:
      POSTGRES_USER: tinyshop
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-tinyshop}   # from .env or your shell; default for local dev
      POSTGRES_DB: tinyshop
    ports:
      - "5432:5432"                # so tools on your laptop (psql, tests) can connect
    volumes:
      - pgdata:/var/lib/postgresql/data                                  # named volume: data survives restarts
      - ./deploy/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro  # bind mount, read-only
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tinyshop -d tinyshop"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

`${POSTGRES_PASSWORD:-tinyshop}` means: use the variable `POSTGRES_PASSWORD` if it's set, otherwise `tinyshop`. Compose automatically reads a `.env` file next to `compose.yaml`, which is why `.env` is in `.gitignore`. The default is fine for a laptop; real environments set a real secret (M6, M13).

**Named volume vs bind mount:** `pgdata:` is managed by Docker and survives `docker compose down`; `./deploy/...:` maps a file from your repository into the container.

Add these targets to your `Makefile` (TABs!):
```makefile
up:                 ## start the stack in the background
	docker compose up -d --build

down:               ## stop the stack (keeps data)
	docker compose down

db:                 ## start only the database
	docker compose up -d db
```

Run it:
```bash
make up
docker compose ps                  # both running; db "healthy", api "healthy" after ~15 s
docker compose logs -f api         # follow the API logs; Ctrl+C to stop following
curl -s localhost:8000/health
docker compose exec db psql -U tinyshop -d tinyshop -c '\l'     # list databases: tinyshop_test exists
make down
```

**Experiment (volumes):** `docker compose down` and `make up` again: the database keeps its data. `docker compose down -v` deletes the volume too, and the init script runs again on the next start.

**Experiment (networking):** `docker compose exec api python -c "import socket; print(socket.gethostbyname('db'))"` shows the database's IP on the Compose network. Try `localhost` instead and see that it's the API container itself.

Run `make check M=02`.

---

## Definition of done

- [ ] `make check M=02` is green.
- [ ] `make up` starts both containers; `docker compose ps` shows them healthy; `/docs` works at localhost:8000.
- [ ] Your image is several times smaller than `tinyshop:naive`, and `whoami` prints `app`.
- [ ] You can explain every line of the Dockerfile.
- [ ] Clean up: `docker image rm tinyshop:naive`; commit and push (`git commit -m "M2: Docker and Compose"`).

## Interview questions

1. **Image vs container?** An image is a read-only template made of layers; a container is a running instance of it with its own writable layer.
2. **How do you make Docker builds fast?** Order instructions from least to most frequently changing, copy dependency files and install before copying code, use `.dockerignore`, and use BuildKit cache mounts in CI.
3. **Why multi-stage builds?** Build tools stay in the build stage; the runtime image is smaller, starts faster and has a smaller attack surface.
4. **Why not run as root in a container?** A compromised process as root has far more power to escape isolation or damage mounted data. Use a dedicated user; Kubernetes can enforce `runAsNonRoot`.
5. **Why can't the API reach the database at `localhost:5432` in Compose?** `localhost` is the API container itself. Containers on a Compose network reach each other by service name (`db`).
6. **How do you pass secrets to a container?** At runtime, through environment variables or mounted files from a secret store, never in the image. Anyone who can pull an image can read all its layers.
7. **What does `depends_on` with `service_healthy` guarantee, and what not?** Start order until the healthcheck passes. It doesn't protect against the database going away later, so the app still needs retries and a readiness check.
8. **Exec form vs shell form of CMD?** The exec form runs your process as PID 1 so it receives SIGTERM and can shut down gracefully; the shell form wraps it in `/bin/sh`, which doesn't forward the signal.

**Next:** [M3 · PostgreSQL](M03-postgres.md)
