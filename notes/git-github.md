# Git & GitHub

## Concepts
- **Four places:** working tree (files on disk) → staging area (`git add`) → history (`git commit`) → remote (GitHub, `git push`).
- **Branch** = a movable label on a commit. `main` stays clean; all work happens on feature branches.
- **GitHub flow:** branch → small commits → push → pull request → merge → delete branch.
- **Branch = a unit of work that gets merged** (e.g. a whole module). **Commit = one step** inside it.
- **Upstream:** `git push -u origin <branch>` links the local branch to the remote one; afterwards plain `git push` works.
- **Squash merge:** all commits of a PR become one commit on `main`. Tidy history; you lose the step-by-step commits on `main` (they stay in the PR).
- `.gitignore` works per folder: Git reads `.gitignore` files in every directory (uv puts one with `*` inside `.venv/`).
- In `.gitignore`, **a leading space is part of the pattern**: ` .env` does NOT ignore `.env`.

## Commands
```bash
git switch main && git pull              # start from latest main
git switch -c m01-fastapi                # create + switch to a branch
git status / git diff / git log --oneline
git add <files> && git commit -m "Add X"
git push -u origin <branch>              # first push; later just `git push`
gh pr create --fill                      # open a PR
gh pr merge --squash --delete-branch     # merge it
git check-ignore -v .env                 # which .gitignore rule ignores this path?
git commit --amend                       # rewrite last commit (needs force push if already pushed)
git reset --hard HEAD~1                  # drop last local commit (destructive!)
```

## Divergent branches
- `git pull` = `git fetch` + combine. If local and remote **both** have commits the other lacks, they've *diverged*; Git asks: merge or rebase?
- My case: an empty `test protection` commit left on local `main` + the squash-merged PR on GitHub.
- Fix when the local commits are junk: check `git log origin/main..main` (local-only commits), then `git reset --hard origin/main`.
- Prevent: `git config --global pull.ff only` → pull only fast-forwards, fails loudly on divergence. Fits "never commit to main".
- `git fetch --prune` removes stale refs to remote branches that were deleted (e.g. after `--delete-branch`).

## Commit messages
- Imperative, short (~50 chars), no period: `Configure ruff and pytest`, not `Added stuff` or a list of the diff.
- Blank line + body if the *why* isn't obvious.

## Branch protection (Ruleset `protect-main`)
- Settings → Rules → Rulesets → target default branch.
- Restrict deletions, block force pushes, require PR (0 approvals when solo: you can't approve your own PR).
- Bypass list empty, otherwise the rule doesn't apply to me.
- From M5: require status checks (CI) to pass.
- Direct push to main is rejected with `GH013: Repository rule violations`.

## Interview questions

**What's the difference between `git add` and `git commit`?**
<details><summary>Answer</summary>
`add` moves changes into the staging area (choosing what goes into the next snapshot); `commit` saves the staged snapshot into history. This lets you commit only part of your changes.
</details>

**Why use feature branches and pull requests, even alone?**
<details><summary>Answer</summary>
`main` stays always-working and deployable; each change is reviewed as one unit; CI can check a PR before it merges; easy to revert a whole feature. Same workflow as in a team.
</details>

**Squash merge vs merge commit vs rebase: why squash?**
<details><summary>Answer</summary>
Squash: one clean commit per feature on main, easy to read and revert; you lose the individual commits on main. Merge commit keeps all commits plus a merge node (full history, noisier). Rebase replays commits on top of main for linear history but rewrites commit IDs.
</details>

**Why is force-pushing to main dangerous?**
<details><summary>Answer</summary>
It rewrites shared history: commits others already pulled disappear, work can be lost, and deployed commits may no longer exist. Block it with branch protection.
</details>

**`git pull` says "divergent branches". What does it mean and what do you do?**
<details><summary>Answer</summary>
Local and remote each have commits the other doesn't. Look at both sides (`git log origin/main..main` and `main..origin/main`). If local commits matter: rebase them onto the remote (or merge). If they're junk: `git reset --hard origin/main`. On main, use `pull.ff only` so this never silently creates merge commits.
</details>

**Why is branch protection a server-side rule and not a local hook?**
<details><summary>Answer</summary>
Local hooks are optional and skippable; the server is the only place that can enforce rules for everyone.
</details>
