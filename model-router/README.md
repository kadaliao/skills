# model-router

> **Codex only.** This skill is built for the Codex CLI and Codex App and is not portable to other hosts. It can route work to Codex *custom agents* when isolation or independent review is useful, while leaving routine work in the current root session. Its logging script keys off `CODEX_HOME`, and its tier names map directly to Codex agent definitions (`router_fast`, `router_balanced`, `router_deep`, `router_critical`, `router_reviewer`).

Use the current root model by default. Route a task to one tier only when an isolated agent or independent review adds value, keep that agent for follow-ups, and adjust when evidence or an explicit constraint justifies it. The router must not silently lower the root session's model capability.

## Tiers

| Tier | Agent | Model / effort | For |
|---|---|---|---|
| passthrough | — (root session) | current host model | Default for routine work and work owned by another skill |
| fast | `router_fast` | `gpt-6-astra/low` | Bounded, low-risk work with deterministic verification |
| balanced | `router_balanced` | `gpt-6-astra/medium` | Bounded uncertainty, including known multi-module work inside one ownership boundary |
| deep | `router_deep` | `gpt-6-astra/high` | Ambiguous, cross-system, concurrency, unfamiliar-API, or long-verification tasks |
| critical | `router_critical` | `gpt-6-astra/max` | High-consequence, hard-to-reverse: migrations, auth, security, money |
| reviewer | `router_reviewer` | `gpt-6-astra/high` | Independent read-only review of critical work |

Model tier is separate from action permission — a commit, push, or release does not by itself make a task critical.

## Overrides

- `$model-router off` — handle in the root session, no agent.
- `$model-router fast|balanced|deep` — pick that tier, no confirmation.
- `$model-router critical` — choose the critical reasoning tier without treating model selection as action approval.
- `do not upgrade` — hold the current tier unless continuing would be unsafe or impossible.

The deterministic policy keeps `multi-module` work at `balanced` unless another material complexity signal applies. Escalation (`fast → balanced → deep`) is available when uncertainty grows, ownership boundaries are crossed, verification fails twice, evidence conflicts, or the agent reports its tier is insufficient. Model selection does not grant or remove action permission, and the skill never silently downgrades the capability floor.

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

The skill directory contains the policy and logger. Codex custom-agent
definitions live in the host configuration under `~/.codex/agents/`; update
the `router_*.toml` entries there when installing or changing the route targets.
