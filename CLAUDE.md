# Ai_agregator — RunPod ComfyUI video infrastructure

## Phase: PREPARATION ONLY
No billable RunPod resources may be created until the user explicitly says so.
`RUNPOD_ALLOW_SPEND` in `.env` must stay `no`; `runpod.sh` refuses create-* otherwise.
Read-only calls (list GPUs, list pods/volumes) are free and allowed.

## Orchestration
Sequence: model-selector-agent (cost plan, read-only) -> devops-agent -> provisioner-agent -> pipeline-agent -> qa-agent.
No provisioning starts without a `workspace/plan.md` approved by the user.
Use sequential-thinking before any multi-step infra action. Every agent reports
what it created (IDs) so the orchestrator can terminate everything on failure.
Always finish a failed/abandoned run by stopping or terminating pods (billing!).

## Secrets
Keys live only in `.env` / `workspace/keys/` (git-ignored). Never print RUNPOD_API_KEY.

## Tooling notes
- fetch MCP = GET only, no custom headers -> use it for public docs / unauthenticated ComfyUI GETs.
- Authenticated RunPod calls go through `.claude/skills/runpod-management/scripts/runpod.sh` (curl).
- Skills: runpod-management, comfyui-environment-setup, comfyui-api-workflow.
- Agents: model-selector-agent, devops-agent, provisioner-agent, pipeline-agent, qa-agent (.claude/agents/).
