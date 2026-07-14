# model-router

> **Codex only.** This skill is built for the Codex CLI and Codex App and is not portable to other hosts. It routes work to Codex *custom agents* pinned to specific OpenAI models and reasoning efforts, its logging script keys off `CODEX_HOME`, and its tier names map directly to Codex agent definitions (`router_fast`, `router_balanced`, `router_deep`, `router_critical`, `router_reviewer`). Dropping it into Claude Code, Gemini CLI, or any non-Codex host will not work — the agents, model ids, and effort levels it references do not exist there.

Route a substantive task to one model tier once, keep that agent for the task's follow-ups, and escalate only when evidence shows the tier is insufficient. The point is to stop paying deep-model cost on shallow work and stop under-powering the risky work, without re-deciding the model on every turn.

## Tiers

| Tier | Agent | Model / effort | For |
|---|---|---|---|
| passthrough | — (root session) | — | Simple facts, one-step ops, work owned by another skill |
| fast | `router_fast` | `gpt-5.6-luna/low` | Small but substantive, reversible, cheap to verify |
| balanced | `router_balanced` | `gpt-5.6-terra/medium` | Default: routine research, diagnosis, review, bounded implementation |
| deep | `router_deep` | `gpt-5.6-sol/high` | Ambiguous root cause, cross-module work, long verification chains |
| critical | `router_critical` | `gpt-5.6-sol/max` | High-consequence, hard-to-reverse: migrations, auth, security, money |
| reviewer | `router_reviewer` | `gpt-5.6-sol/high` | Independent read-only review of critical work |

Model tier is separate from action permission — a commit, push, or release does not by itself make a task critical.

## Overrides

- `$model-router off` — handle in the root session, no agent.
- `$model-router fast|balanced|deep` — pick that tier, no confirmation.
- `$model-router critical` — explicit invocation counts as confirmation for the critical tier.
- `do not upgrade` — hold the current tier unless continuing would be unsafe or impossible.

Escalation (`fast → balanced → deep`) is automatic when scope expands, root cause stays ambiguous, verification fails twice, evidence conflicts, or the agent reports its tier is insufficient. Reaching `critical` always needs confirmation unless already explicitly selected; the skill never silently downgrades a critical task.

## Layout

- [SKILL.md](SKILL.md) — routing procedure, overrides, escalation rules.
- [references/routing-policy.md](references/routing-policy.md) — tier matrix and decision signals for non-obvious calls.
- [references/eval-cases.json](references/eval-cases.json) — routing eval fixtures.
- [agents/openai.yaml](agents/openai.yaml) — Codex agent interface metadata.
- [scripts/route_log.py](scripts/route_log.py) — privacy-safe local metadata logging (fixed enum fields only; no prompts, code, paths, or identifiers). Uses `$CODEX_HOME` (default `$HOME/.codex`).
- [scripts/test_model_router.py](scripts/test_model_router.py) — tests for the logger.

## Install

Codex reads skills from `$CODEX_HOME/skills` (default `~/.codex/skills`):

```bash
npx degit kadaliao/skills/model-router ~/.codex/skills/model-router
```
