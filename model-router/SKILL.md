---
name: model-router
description: Helps choose an isolated Codex agent and reasoning effort when routing adds value, while preserving the current root model as the default capability floor. Use when the user invokes $model-router, asks to choose or review routing, or a task clearly benefits from an isolated or independent agent. Do not auto-delegate routine work that the current session can complete directly.
---

# Model Router

Use the current root session by default. Route only when isolation, parallel
execution, or an independent review materially helps. When routing is used,
keep the selected agent for follow-ups and adjust only when evidence or an
explicit user request justifies it.

## Apply Overrides And Bypasses

Honor explicit overrides first:

- `$model-router off`: handle the current task in the root session.
- `$model-router fast|balanced|deep`: select that tier without confirmation.
- `$model-router critical`: treat the explicit invocation as confirmation for
  the critical tier.
- `do not upgrade`: keep the current tier unless continuing would be unsafe or
  impossible; explain the conflict instead of silently upgrading.

Do not spawn a custom agent for a simple factual answer, an explicit request
for another dedicated skill, a single-step tool or status operation, routine
work the root can finish directly, or image and artifact work already owned by
another skill. Handle those in the root session and let the dedicated skill run
normally.

When the user explicitly invokes `$model-router`, record a `passthrough`
selection and completion even when this bypass applies. Use the matching reason
such as `simple`, `explicit-skill`, or `single-step`. This keeps explicit router
usage visible without adding logging overhead to every implicit trivial reply.

## Route The Task

1. Read the current request and the minimum available workspace context needed
   to judge scope. Do not inspect old tasks or unrelated history for routing.
   If routing would not add value, stay in the root session and skip the
   remaining steps.
2. Classify the request into the fixed, privacy-safe reasons accepted by
   `scripts/route_log.py decide`. Use
   [routing-policy.md](references/routing-policy.md) when the choice is not
   obvious. Do not treat `multi-module` alone as a `deep` signal.
3. Run `decide --dry-run` with the task type and every applicable reason. Use
   its deterministic result rather than choosing a different tier ad hoc.
4. Choose exactly one initial tier. The default targets use the current GPT-6
   capability floor and vary reasoning effort, not model quality:
   - `fast` -> `router_fast` -> `gpt-6-astra/low`
   - `balanced` -> `router_balanced` -> `gpt-6-astra/medium`
   - `deep` -> `router_deep` -> `gpt-6-astra/high`
   - `critical` -> `router_critical` -> `gpt-6-astra/max`
   - independent review -> `router_reviewer` -> `gpt-6-astra/high`
   If a target is unavailable on the host, keep the work in the root session
   or use an explicitly selected compatible target; never silently downgrade
   the capability floor.
5. Show one concise line in the user's language only when routing is used:
   `Route: <tier> - <model>/<effort> - <short reason>.`
6. Do not ask for confirmation merely because a model tier is called
   `critical`. Handle approval for destructive or external actions separately
   from model selection.
7. Repeat `decide` without `--dry-run` to append the selection and retain the
   returned route ID when routing is used. For an explicit override, also pass
   `--tier <tier>`.
8. Start one write-capable custom agent only when the route is useful. Pass the full task, current working
   directory, applicable constraints and skills, requested delivery actions,
   and success criteria. Preserve the current task context when spawning.
9. Keep follow-ups on that agent by default. Re-evaluate at a material phase
   transition, such as analysis to implementation or implementation to
   production action. The task may return to the root session or change effort
   when evidence, host availability, or the user's explicit constraint calls
   for it.
10. Wait for the agent, inspect its evidence and verification, then record one
    completion immediately before delivering the consolidated answer. Omit
    `--duration-seconds` so the logger calculates wall time from timestamps.

Do not run multiple write-capable agents concurrently in the same worktree.
For a confirmed critical task, run `router_critical` first and then run the
read-only `router_reviewer` against the resulting state. Return reviewer
findings to `router_critical` for correction when needed before final delivery.

Treat a task as passthrough instead of `fast` when the root can finish it with
one bounded tool operation or a short direct response. Reserve `router_fast`
for substantive low-risk work that still benefits from an isolated execution
context. This avoids paying subagent startup and context cost for trivial work.

## Escalate Deliberately

Escalate `fast -> balanced` when investigation or meaningful uncertainty
appears. Escalate `balanced -> deep` when work crosses ownership boundaries,
the root cause remains ambiguous, concurrency or unfamiliar API behavior
appears, representative verification fails twice, required evidence conflicts,
or the selected agent reports that its tier is insufficient. Multi-module work
inside one known ownership boundary may remain `balanced`.

Escalating to `critical` is a routing decision, not an approval request. Ask
only when the action itself needs user approval or the scope is unclear. If an
agent or pinned model is unavailable, use these fallbacks:

- `fast` -> `balanced`
- `balanced` -> `deep`
- `deep` -> keep the work in the root session or report that routing is unavailable
- `critical` or `reviewer` -> keep the work in the root session and report the configuration failure

Model tier is separate from action permission. A commit, push, install, or
release does not by itself make a task critical; follow the user's authorization
and the active approval policy for side effects.

## Record Privacy-Safe Metadata

Use `scripts/route_log.py` at selection and completion. Record only its fixed
enum fields; never pass prompts, code, paths, repository names, tool output,
user identifiers, or secrets. `decide` is the preferred selection path;
`select` remains only for backward-compatible manual logging.

```bash
ROUTER_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" decide \
  --task-type implementation \
  --reason multi-module

python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" complete \
  --route-id ROUTE_ID \
  --outcome succeeded \
  --verification passed \
  --final-tier balanced \
  --tier-fit appropriate
```

Classify `tier-fit` from observed work, not from the outcome alone:

- `appropriate`: the selected tier matched the complexity encountered.
- `over`: a lower tier would clearly have handled the work.
- `under`: escalation was needed or the selected tier was insufficient.
- `unknown`: there is not enough evidence to judge.

Pass `--active-duration-seconds` only when a real execution duration is
available. Never estimate it. A second completion is rejected unless
`--revise` is explicit, which preserves append-only correction history.

If `CODEX_HOME` is unset, use `$HOME/.codex`. Logging failure must not block the
task; report it briefly and continue.

## Review Routing History

When the user asks how the router has been used, run the local report directly
in the root session. Do not delegate this single-step status operation.

```bash
ROUTER_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" report
python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" report --days 7
python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" summary --since 2026-07-01
python3 "$ROUTER_HOME/skills/model-router/scripts/route_log.py" reconcile --stale-hours 24
```

Use `report` for a readable retrospective and `summary` for structured JSON.
Both support `--days`, `--since`, `--until`, `--task-type`, and `--tier`;
both accept `--stale-hours`, and `report` also accepts `--limit` and
`--top-reasons`. Explain active versus stale routes, failed or partial
verification, tier fit, escalation patterns, reason quality, current-policy
`deep` mismatches, completion revisions, and unusual p50/p90/max duration.

Use `reconcile` without `--apply` to preview routes that exceeded the stale
threshold. Add `--apply` only when every candidate is known to be abandoned; it
closes them as `abandoned/not-applicable` without rewriting history or adding
their stale age to performance duration statistics. Do not use
stale age alone to claim that work failed.

Treat the reported model as the configured target inferred from the tier. The
report covers only events successfully written by this skill; the metadata does
not prove the provider-side model actually called and does not contain prompts,
code, paths, repository names, user identifiers, tokens, cost, or secrets. Do
not claim otherwise.
