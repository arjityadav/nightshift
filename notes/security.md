# Security & secrets

## Concepts
- Secrets (passwords, API keys, tokens) never go in Git and never in Docker images. They come from environment variables / `.env` (ignored).
- Ignore `.env` **before** it exists: once committed, a secret stays in Git history even after deleting the file.
- Verify ignores with `git check-ignore -v .env`.
- Use the GitHub **noreply email** for commits to keep the real email out of public history.

## Defence in depth for secrets
| Layer | Where |
|---|---|
| Don't create the risk | `.gitignore`, secrets only in env vars |
| Local hook | pre-commit `detect-private-key` (fast feedback) |
| Server side | GitHub secret scanning + **push protection** (Settings → Code security) |
| CI | secret scanner (e.g. gitleaks) + pre-commit in GitHub Actions |
| Leak happened | **rotate the secret first**, then clean history |

Principle: **local checks give fast feedback, server-side checks enforce.**

## Interview questions

**You committed a password and deleted it in the next commit. Safe?**
<details><summary>Answer</summary>
No: it's still in history and anyone with the repo can read it. Rotate the secret immediately; rewriting history is clean-up, not a fix. Prevent with .gitignore, hooks and push protection.
</details>

**Why isn't a pre-commit hook enough to stop secret leaks?**
<details><summary>Answer</summary>
Hooks are client-side: not cloned (each machine must install them), skippable with `--no-verify`, only match known patterns (not every password), and don't run for web/bot commits. Enforce server-side with push protection and CI scanning.
</details>
