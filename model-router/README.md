# model-router

> **Codex only.** This skill is built for the Codex CLI and Codex App and is not portable to other hosts. It routes work to Codex *custom agents* pinned to specific OpenAI models and reasoning efforts, its logging script keys off `CODEX_HOME`, and its tier names map directly to Codex agent definitions (`router_fast`, `router_balanced`, `router_deep`, `router_critical`, `router_reviewer`). Dropping it into Claude Code, Gemini CLI, or any non-Codex host will not work — the agents, model ids, and effort levels it references do not exist there.

Route a substantive task to one model tier once, keep that agent for the task's follow-ups, and escalate only when evidence shows the tier is insufficient. The point is to stop paying deep-model cost on shallow work and stop under-powering the risky work, without re-deciding the model on every turn.

## Tiers

| Tier | Agent | Model / effort | For |
|---|---|---|---|
| passthrough | — (root session) | — | Simple facts, one-step ops, work owned by another skill |
| fast | `router_fast` | `gpt-5.6-luna/low` | Bounded, low-risk work with deterministic verification |
| balanced | `router_balanced` | `gpt-5.6-terra/medium` | Default: bounded uncertainty, including known multi-module work inside one ownership boundary |
| deep | `router_deep` | `gpt-5.6-sol/high` | Ambiguous, cross-system, concurrency, unfamiliar-API, or long-verification work |
| critical | `router_critical` | `gpt-5.6-sol/max` | High-consequence, hard-to-reverse: migrations, auth, security, money |
| reviewer | `router_reviewer` | `gpt-5.6-sol/high` | Independent read-only review of critical work |

Model tier is separate from action permission — a commit, push, or release does not by itself make a task critical.

## Overrides

- `$model-router off` — handle in the root session, no agent.
- `$model-router fast|balanced|deep` — pick that tier, no confirmation.
- `$model-router critical` — explicit invocation counts as confirmation for the critical tier.
- `do not upgrade` — hold the current tier unless continuing would be unsafe or impossible.

The deterministic policy keeps `multi-module` work at `balanced` unless another material complexity signal applies. Escalation (`fast → balanced → deep`) is automatic when uncertainty grows, ownership boundaries are crossed, verification fails twice, evidence conflicts, or the agent reports its tier is insufficient. Reaching `critical` always needs confirmation unless already explicitly selected; the skill never silently downgrades a critical task.

## Layout

- [SKILL.md](SKILL.md) — routing procedure, overrides, escalation rules.
- [references/routing-policy.md](references/routing-policy.md) — tier matrix and decision signals for non-obvious calls.
- [references/eval-cases.json](references/eval-cases.json) — executable routing-policy eval fixtures.
- [agents/openai.yaml](agents/openai.yaml) — Codex agent interface metadata.
- [scripts/route_policy.py](scripts/route_policy.py) — deterministic tier selection from fixed, privacy-safe task signals.
- [scripts/route_log.py](scripts/route_log.py) — append-only routing lifecycle, automatic wall-time measurement, stale reconciliation, and history review (`decide` / `complete` / `report` / `summary` / `reconcile`). Fixed enum fields only; no prompts, code, paths, or identifiers. Uses `$CODEX_HOME` (default `$HOME/.codex`).
- [scripts/test_model_router.py](scripts/test_model_router.py) — behavior evals, lifecycle tests, reporting tests, and legacy-log compatibility checks.

## Install

Codex reads skills from `$CODEX_HOME/skills` (default `~/.codex/skills`):

```bash
npx degit kadaliao/skills/model-router ~/.codex/skills/model-router
```
