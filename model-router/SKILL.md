---
name: model-router
description: Routes substantive Codex CLI and Codex App tasks to personal custom agents with pinned OpenAI models and reasoning efforts, keeps routing sticky for the task, escalates when complexity or risk rises, and records privacy-safe local metadata. Use automatically before analytical or execution work, and explicitly when the user invokes $model-router or asks to choose, switch, or override a model, reasoning effort, or agent tier. Bypass simple factual replies, explicit dedicated-skill requests, single-step tool operations, and image or artifact generation handled by another skill.
---

# Model Router

Route a substantive task once, keep the selected agent for its follow-ups, and
escalate only when evidence shows the original tier is insufficient.

## Apply Overrides And Bypasses

Honor explicit overrides first:

- `$model-router off`: handle the current task in the root session.
- `$model-router fast|balanced|deep`: select that tier without confirmation.
- `$model-router critical`: treat the explicit invocation as confirmation for
  the critical tier.
- `do not upgrade`: keep the current tier unless continuing would be unsafe or
  impossible; explain the conflict instead of silently upgrading.

Do not spawn a custom agent for a simple factual answer, an explicit request
for another dedicated skill, a single-step tool or status operation, or image
and artifact work already owned by another skill. Handle those in the root
session and let the dedicated skill run normally.

## Route The Task

1. Read the current request and the minimum available workspace context needed
   to judge scope. Do not inspect old tasks or unrelated history for routing.
2. Classify task type, scope, uncertainty, consequence, reversibility, and
   verification difficulty. Use [routing-policy.md](references/routing-policy.md)
   when the choice is not obvious.
3. Choose exactly one initial tier:
   - `fast` -> `router_fast` -> `gpt-5.6-luna/low`
   - `balanced` -> `router_balanced` -> `gpt-5.6-terra/medium`
   - `deep` -> `router_deep` -> `gpt-5.6-sol/high`
   - `critical` -> `router_critical` -> `gpt-5.6-sol/max`
   - independent critical review -> `router_reviewer` ->
     `gpt-5.6-sol/high`
4. Show one concise line in the user's language before delegation:
   `Route: <tier> - <model>/<effort> - <short reason>.`
5. For `critical`, ask for confirmation before spawning unless the user
   explicitly invoked `$model-router critical`. Explain that it uses
   `gpt-5.6-sol/max` plus an independent reviewer.
6. Start one write-capable custom agent. Pass the full task, current working
   directory, applicable constraints and skills, requested delivery actions,
   and success criteria. Preserve the current task context when spawning.
7. Keep follow-ups on that agent. Re-evaluate at a material phase transition,
   such as analysis to implementation or implementation to production action,
   but do not downgrade within the task.
8. Wait for the agent, inspect its evidence and verification, then deliver one
   consolidated answer from the root session.

Do not run multiple write-capable agents concurrently in the same worktree.
For a confirmed critical task, run `router_critical` first and then run the
read-only `router_reviewer` against the resulting state. Return reviewer
findings to `router_critical` for correction when needed before final delivery.

Treat a task as passthrough instead of `fast` when the root can finish it with
one bounded tool operation or a short direct response. Reserve `router_fast`
for substantive low-risk work that still benefits from an isolated execution
context. This avoids paying subagent startup and context cost for trivial work.

## Escalate Deliberately

Escalate `fast -> balanced` or `balanced -> deep` automatically when the task
expands across modules, the root cause remains ambiguous, representative
verification fails twice, required evidence conflicts, or the selected agent
reports that its tier is insufficient.

Escalating to `critical` always requires confirmation unless already explicitly
selected. Never silently downgrade a critical task. If an agent or pinned model
is unavailable, use these fallbacks:

- `fast` -> `balanced`
- `balanced` -> `deep`
- `deep` -> request confirmation for `critical`
- `critical` or `reviewer` -> stop and report the configuration failure

Model tier is separate from action permission. A commit, push, install, or
release does not by itself make a task critical; follow the user's authorization
and the active approval policy for side effects.

## Record Privacy-Safe Metadata

Use `scripts/route_log.py` at selection and completion. Record only its fixed
enum fields; never pass prompts, code, paths, repository names, tool output,
user identifiers, or secrets.

```bash
ROUTER_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" select \
  --task-type implementation \
  --tier balanced \
  --reason multi-module \
  --confidence 0.82

python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" complete \
  --route-id ROUTE_ID \
  --outcome succeeded \
  --verification passed \
  --final-tier balanced \
  --duration-seconds 420
```

If `CODEX_HOME` is unset, use `$HOME/.codex`. Logging failure must not block the
task; report it briefly and continue.
