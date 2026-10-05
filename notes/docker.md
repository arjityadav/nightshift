# Docker

## Concepts
| Term | Meaning |
|---|---|
| Image | read-only template (filesystem + metadata), like a class |
| Container | running instance of an image, like an object |
| Dockerfile | recipe that builds an image |
| Layer | one per instruction; cached and shared |
| Registry | stores images (Docker Hub, GHCR) |
| Tag | version name: `python:3.12-slim` |
| Volume | storage that outlives containers |

- **A container is not a VM:** a normal Linux process, isolated by **namespaces** (own filesystem, network, process list) and limited by **cgroups** (CPU, memory). Starts in milliseconds.
- Inside a container the main app is **PID 1** and you only see its own processes.
- Images are minimal on purpose: tools like `ps` may be missing (`cat /proc/1/cmdline` instead).
- **Containers run as root by default** (`whoami` → `root` = root *user*, not root directory). Create a user and switch to it.

## The TinyShop Dockerfile, line by line
- **Layer caching:** a layer is reused only if its instruction and everything before it are unchanged. Order: rarely changing → often changing. Copy `pyproject.toml` + `uv.lock`, run `uv sync`, *then* copy the code → code edits rebuild in seconds.
- **Multi-stage build:** stage `builder` installs packages (uv, caches); the final stage starts fresh from `python:3.12-slim` and `COPY --from=builder /app /app` takes only code + `.venv`. Only the last stage becomes the image. My result: naive 1.25 GB → 193 MB.
- `uv sync --frozen --no-dev`: exact locked versions, no test/lint tools.
- `USER app` (created with `useradd`): non-root. Check: `docker compose exec api whoami` → `app`.
- **Exec form `CMD ["uvicorn", ...]`:** uvicorn is PID 1 and receives SIGTERM from `docker stop` / Kubernetes → graceful shutdown. Shell form `CMD uvicorn ...` makes `/bin/sh` PID 1, which doesn't forward the signal → hard kill after 10 s.
- `PYTHONUNBUFFERED=1`: logs appear immediately. `HEALTHCHECK`: Docker probes `/health`.
- `.dockerignore`: keeps `.venv`, `.git`, `.env`, tests, docs out of the build context (smaller, faster, no secrets).

## Compose
- Services share a network with DNS: **service name = hostname**. From `api`, the DB is `db:5432`. Inside a container, `localhost` is the container itself.
- From the Mac: `localhost:5432` through the published port.
- `depends_on: condition: service_healthy` waits for the DB healthcheck, not just "started".
- Named volume `pgdata` keeps data across `down`/`up`; `docker compose down -v` deletes it.
- `${POSTGRES_PASSWORD:-tinyshop}`: from env/.env, with a local-dev default.

## Commands
```bash
docker run -d --name web -p 8080:80 nginx:1.27   # -d background, -p HOST:CONTAINER
docker ps            # containers (running); -a includes stopped
docker images        # images and their sizes
docker logs web
docker exec -it web sh   # shell inside the container
docker stop web && docker rm web
docker run -it --rm python:3.12-slim python   # --rm deletes the container on exit
```

## Errors I hit
- **`Bind for 0.0.0.0:5432 failed: port is already allocated`** → another process (here another project's Postgres container) already listens on that **host** port. Only one process per host port; container ports never clash (each container has its own network).
  - Find it: `docker ps --format '{{.Names}}\t{{.Ports}}'` or `lsof -nP -iTCP:5432 -sTCP:LISTEN`.
  - Fix: stop the other container (`docker stop <name>`, data in volumes stays), or change only the host side (`"5433:5432"`).

## Interview questions

**What's the difference between an image and a container?**
<details><summary>Answer</summary>
An image is a read-only template (filesystem layers + metadata); a container is a running instance of it with its own writable layer. Many containers can run from one image.
</details>

**How is a container different from a virtual machine?**
<details><summary>Answer</summary>
A VM runs a full guest OS on virtualised hardware. A container is a host process isolated with namespaces and limited with cgroups, sharing the host kernel, so it's much lighter and starts in milliseconds.
</details>

**Why copy dependency files before the code in a Dockerfile?**
<details><summary>Answer</summary>
Layer caching: the dependency install layer is reused as long as pyproject/uv.lock don't change, so code changes rebuild in seconds instead of reinstalling all packages.
</details>

**What is a multi-stage build and why use it?**
<details><summary>Answer</summary>
One stage with build tools prepares the app; a clean final stage copies only the result. The final image has no build tools or caches: smaller and a smaller attack surface.
</details>

**Exec form vs shell form for CMD?**
<details><summary>Answer</summary>
Exec form (JSON list) makes the app PID 1 so it receives SIGTERM and shuts down gracefully; shell form makes a shell PID 1 that doesn't forward signals, so the app is killed hard after a timeout.
</details>

**Why can't the API container reach Postgres on `localhost`?**
<details><summary>Answer</summary>
Inside a container, localhost is the container itself. Compose provides DNS where each service name is a hostname, so the API connects to `db:5432`.
</details>

**Why shouldn't a container run as root?**
<details><summary>Answer</summary>
If the app is exploited, a root process makes escaping the container or damaging mounted files much easier. Run as an unprivileged user (least privilege); Kubernetes can enforce it.
</details>
