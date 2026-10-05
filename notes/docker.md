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

**Why shouldn't a container run as root?**
<details><summary>Answer</summary>
If the app is exploited, a root process makes escaping the container or damaging mounted files much easier. Run as an unprivileged user (least privilege); Kubernetes can enforce it.
</details>
