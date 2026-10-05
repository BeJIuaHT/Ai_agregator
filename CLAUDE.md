# Ai_agregator — RunPod ComfyUI video infrastructure

## Spending rule
Billable RunPod resources are created only after the user explicitly says "запускай" (or equivalent) for THAT run; approval of one run does not cover the next.
`RUNPOD_ALLOW_SPEND` in `.env` stays `no` by default; it is switched to `yes` only for an approved run and set back to `no` right after. `runpod.sh` refuses create-* otherwise. Agents never edit it.
Each run has a budget and a max price per hour from the approved `workspace/plan.md` (test runs so far: up to $1, Community GPUs).
Read-only calls (list GPUs, list pods/volumes) are free and allowed.

## Orchestration
Prompts: prompt-engineer-agent runs before the pipeline (any time, no RunPod needed) and leaves ready prompts in `workspace/prompts/built/`.
Sequence: model-selector-agent (cost plan, read-only) -> devops-agent -> provisioner-agent -> pipeline-agent -> qa-agent.
No provisioning starts without a `workspace/plan.md` approved by the user.
Use sequential-thinking before any multi-step infra action. Every agent reports
what it created (IDs) so the orchestrator can terminate everything on failure.
Always finish a failed/abandoned run by terminating pods (billing!). `runpod.sh terminate-all` is the emergency cleanup; afterwards `pods` and `volumes` must be `[]` and `RUNPOD_ALLOW_SPEND=no`.

### Rules from real runs (details in the skills and agents)
- Prefer terminate over stop: a stopped Community pod often cannot restart, and its files are stuck on that host. Download outputs to the repo BEFORE terminating.
- Provisioning is time-boxed (15 min) and gated by a 100 MB/s download-speed test (`speed_test.sh`); a slow host is terminated and replaced, not endured.
- ComfyUI needs torch 2.7+ (the default image has 2.4.1; `setup_comfyui.sh` upgrades it).
- Do not assume a rejected/unclear subagent call did not run: check `~/.claude/projects/<proj>/<session>/subagents/*.jsonl`, and list pods, before re-launching.
- Build prompts from blocks with `assemble_prompt.py`, never retype them.
- `runpod.sh` caps GPU price with `RUNPOD_MAX_PRICE` (default 0.25 $/h); an unexpectedly expensive pod gets terminated at once.

### Calling billing-related agents (checklist for the prompt)
State in the prompt: the max $/h and total budget, the time limit (provisioner 15 min), the abort rule (slow host, price over limit), which IDs to report (pod id, price, elapsed time), and that the agent must not create, stop or terminate anything outside its role.

## Secrets
Keys live only in `.env` / `workspace/keys/` (git-ignored). Never print RUNPOD_API_KEY.

## Tooling notes
- fetch MCP = GET only, no custom headers -> use it for public docs / unauthenticated ComfyUI GETs.
- Authenticated RunPod calls go through `.claude/skills/runpod-management/scripts/runpod.sh` (curl).
- Skills: runpod-management, comfyui-environment-setup, comfyui-api-workflow, github-mcp-git.
- Agents: prompt-engineer-agent, model-selector-agent, devops-agent, provisioner-agent, pipeline-agent, qa-agent (.claude/agents/).
