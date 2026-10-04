---
name: github-mcp-git
description: Work with Git and GitHub in this repo using local git plus the GitHub MCP (mcp__github__*) — commit, push, branches, PRs, issues, and pushing when local `git push` has no credentials. Use for any commit/push/PR/issue task.
---

# github-mcp-git

Repo: `BeJIuaHT/Ai_agregator` (remote `origin`, HTTPS, default branch `main`).
GitHub MCP tools are deferred: load schemas first with
`ToolSearch("select:mcp__github__get_me,mcp__github__push_files,...")`, then call them.

## Division of labour
- **Local git (Bash)**: status, diff, add, commit, log, local branches. Always works offline.
- **GitHub MCP**: everything on github.com — remote branches, PRs, issues, reviews, reading remote files, and pushing when the shell has no credentials.
- Commit/push only when the user asks. Never commit directly to `main` if the user wants a PR; branch first.

## Before every commit
1. `git status --short` and `git add -n .` — review the file list.
2. Never stage secrets: `.env`, `workspace/keys/*`, `*.pem`, tokens. They are git-ignored; if one shows up, stop and fix `.gitignore`.
3. Commit message: short imperative subject, body for the why. End with the attribution line from the session reminder.

## Pushing
1. Try `git push origin <branch>`.
2. If it fails with `could not read Username` (no credentials), either ask the user to run `gh auth login && gh auth setup-git`, or push through MCP (below).

### Push via MCP (fallback)
- `mcp__github__get_me` first to confirm the token works and who it acts as.
- `mcp__github__push_files` (owner, repo, branch, files[{path, content}], message) creates ONE commit with many files. Use `create_or_update_file` for a single file (needs the current blob `sha` when updating).
- Read file contents from disk and pass them verbatim; send text files only. Skip ignored files.
- **Caveat**: the commit is created on GitHub with a different SHA than the local one. Afterwards sync local history:
  `git fetch origin && git reset --hard origin/<branch>` — only after confirming the working tree has no uncommitted changes (the pushed content matches local).
- Ask the user before doing this; it rewrites local history.

## Branches and PRs
1. `mcp__github__create_branch` (from `main`) or `git switch -c <name>`.
2. Push commits (above).
3. Look for a PR template first: `get_file_contents` on `.github/pull_request_template.md` (and `.github/PULL_REQUEST_TEMPLATE/`). Follow it if present.
4. `mcp__github__create_pull_request` (title, body, head, base=`main`). End the body with the PR attribution line from the session reminder.
5. Review flow: `pull_request_review_write` (method `create`) -> `add_comment_to_pending_review` -> `pull_request_review_write` (method `submit_pending`).
6. `merge_pull_request` only on explicit user request.

## Issues
- `search_issues` before `issue_write` to avoid duplicates.
- Set `state_reason` when closing.

## Reading remote state
- `list_branches`, `list_commits`, `get_commit`, `get_file_contents`, `search_code`, `pull_request_read`, `issue_read`.
- Use pagination (5-10 items) and `minimal_output` where available.

## Safety
- Outward-facing actions (push, PR, issue, comment, merge, delete repo/file) need the user's explicit request; approval for one does not cover the next.
- Never use `delete_repository` / `delete_file` unless asked by name.
- Never print tokens. If the MCP returns 401/403, report it; do not hunt for credentials.
- Run `run_secret_scanning` before pushing anything that touched config or scripts if unsure about leaked keys.
