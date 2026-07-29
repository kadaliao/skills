---
name: model-router
description: Routes substantive Codex CLI and Codex App tasks to personal custom agents with pinned OpenAI models and reasoning efforts, keeps routing sticky for the task, escalates when complexity or risk rises, and records and reviews privacy-safe local routing metadata. Use automatically before analytical or execution work, and explicitly when the user invokes $model-router, asks to choose, switch, or override a model, reasoning effort, or agent tier, or asks for routing history, usage statistics, or a model-routing retrospective. Bypass simple factual replies, explicit dedicated-skill requests, single-step tool operations, and image or artifact generation handled by another skill.
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

When the user explicitly invokes `$model-router`, record a `passthrough`
selection and completion even when this bypass applies. Use the matching reason
such as `simple`, `explicit-skill`, or `single-step`. This keeps explicit router
usage visible without adding logging overhead to every implicit trivial reply.

## Route The Task

1. Read the current request and the minimum available workspace context needed
   to judge scope. Do not inspect old tasks or unrelated history for routing.
2. Classify the request into the fixed, privacy-safe reasons accepted by
   `scripts/route_log.py decide`. Use
   [routing-policy.md](references/routing-policy.md) when the choice is not
   obvious. Do not treat `multi-module` alone as a `deep` signal.
3. Run `decide --dry-run` with the task type and every applicable reason. Use
   its deterministic result rather than choosing a different tier ad hoc.
4. Choose exactly one initial tier:
   - `fast` -> `router_fast` -> `gpt-5.6-luna/low`
   - `balanced` -> `router_balanced` -> `gpt-5.6-terra/medium`
   - `deep` -> `router_deep` -> `gpt-5.6-sol/high`
   - `critical` -> `router_critical` -> `gpt-5.6-sol/max`
   - independent critical review -> `router_reviewer` ->
     `gpt-5.6-sol/high`
5. Show one concise line in the user's language before delegation:
   `Route: <tier> - <model>/<effort> - <short reason>.`
6. For `critical`, ask for confirmation before recording or spawning unless the user
   explicitly invoked `$model-router critical`. Explain that it uses
   `gpt-5.6-sol/max` plus an independent reviewer.
7. Repeat `decide` without `--dry-run` to append the selection and retain the
   returned route ID. For an explicit override, also pass `--tier <tier>`.
8. Start one write-capable custom agent. Pass the full task, current working
   directory, applicable constraints and skills, requested delivery actions,
   and success criteria. Preserve the current task context when spawning.
9. Keep follow-ups on that agent. Re-evaluate at a material phase transition,
   such as analysis to implementation or implementation to production action,
   but do not downgrade within the task.
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
