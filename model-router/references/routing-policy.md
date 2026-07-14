# Routing Policy

Use `balanced` when no stronger signal clearly applies. Route according to the
shape and consequence of the work, not keywords or the user's apparent urgency.

## Tier Matrix

| Tier | Choose when | Avoid when |
| --- | --- | --- |
| passthrough | Simple factual reply, explicit dedicated skill, one-step status/tool operation, or dedicated image/artifact workflow | Repository analysis or multi-step work is required |
| fast | Goal and implementation are clear, scope is small but still substantive, change is reversible, and verification is cheap | The root can finish in one bounded operation, or investigation is required |
| balanced | Routine research, diagnosis, review, configuration, or implementation with bounded uncertainty | Work crosses major ownership boundaries or failure consequences are severe |
| deep | Ambiguous root cause, broad review, cross-module or cross-system implementation, concurrency/performance issues, unfamiliar APIs, or long verification chain | Failure could cause severe and hard-to-reverse harm |
| critical | Consequence is high and the result is difficult to reverse or verify: destructive data migration, authentication/authorization, security-sensitive changes, financial correctness, or risky production infrastructure | The task is merely long, urgent, or includes a routine external write |

## Decision Signals

Consider these dimensions together:

- Scope: single operation, single file, multi-file, multi-module, cross-system.
- Uncertainty: known procedure, local diagnosis, ambiguous root cause, unknown
  runtime behavior.
- Consequence: cosmetic, routine correctness, user-visible outage, security,
  money, or data loss.
- Reversibility: trivial revert, normal rollback, difficult migration, or
  irreversible side effect.
- Verification: deterministic local check, integration test, environment smoke,
  or incomplete observability.

Do not choose `critical` from consequence alone. Require both meaningful
consequence and difficult reversibility or verification.

## Escalation Signals

- Escalate `fast -> balanced` when investigation or more than a tiny local
  change becomes necessary.
- Escalate `balanced -> deep` when the real path crosses modules or systems,
  assumptions conflict with evidence, or two representative attempts fail.
- Propose `deep -> critical` when newly discovered impact includes data loss,
  authorization, security, financial correctness, or risky production state.
- Do not downgrade within the same task. Start a new routing decision only for
  a genuinely new goal.

## Examples

- Answer a unit conversion: passthrough.
- Run an explicitly named PDF skill: passthrough.
- Correct a typo and run a focused check: fast.
- Diagnose a dependency path broken by a package-manager upgrade: balanced.
- Research an external API from official sources and recommend an integration:
  balanced.
- Trace and fix a bug spanning a client and backend: deep.
- Review a broad application and implement verified fixes: deep.
- Design a destructive production migration with incomplete rollback: critical.
- Commit and push a verified documentation edit: keep its existing tier; the
  external write is an authorization concern, not a reasoning-tier signal.
