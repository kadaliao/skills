# Routing Policy

Use `balanced` when no stronger signal clearly applies. Route according to the
shape and consequence of the work, not keywords or the user's apparent urgency.

## Tier Matrix

| Tier | Choose when | Avoid when |
| --- | --- | --- |
| passthrough | Simple factual reply, explicit dedicated skill, one-step status/tool operation, or dedicated image/artifact workflow | Repository analysis or multi-step work is required |
| fast | Goal and implementation are clear, scope is small but still substantive, change is reversible, and verification is deterministic | The root can finish in one bounded operation, or investigation is required |
| balanced | Routine research, diagnosis, review, configuration, or implementation with bounded uncertainty, including multi-module work inside one known ownership boundary | Work crosses ownership boundaries, the root cause is ambiguous, or verification is unusually difficult |
| deep | A strong signal exists: ambiguous root cause, cross-system ownership, concurrency/performance behavior, unfamiliar API semantics, or a long verification chain; alternatively, multi-module scope combines with another material complexity signal | Multi-module scope is the only complexity signal, or failure could cause severe and hard-to-reverse harm |
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

Treat `multi-module` as a scope description, not a sufficient reason for
`deep`. Keep same-repository, known-path work at `balanced` unless another
material signal applies. Choose `deep` when at least one strong signal applies:

- `cross-system`
- `ambiguous-root-cause`
- `concurrency-performance`
- `unfamiliar-api`
- `long-verification`
- `independent-review`
- `model-unavailable`
- `verification-failed`

Also choose `deep` when `multi-module` combines with one of `multi-source`,
`evidence-needed` or `high-impact`.

Choose `fast` only when `bounded`, `low-risk`, and
`deterministic-verification` all apply. Otherwise use `balanced` by default.

Do not choose `critical` from consequence alone. Require both meaningful
consequence and difficult reversibility or verification.

## Escalation Signals

- Escalate `fast -> balanced` when investigation or more than a tiny local
  change becomes necessary.
- Escalate `balanced -> deep` when the real path crosses ownership boundaries,
  assumptions conflict with evidence, concurrency or unfamiliar API semantics
  emerge, or two representative attempts fail.
- Propose `deep -> critical` when newly discovered impact includes data loss,
  authorization, security, financial correctness, or risky production state.
- Do not downgrade within the same task. Start a new routing decision only for
  a genuinely new goal.

## Examples

- Answer a unit conversion: passthrough.
- Run an explicitly named PDF skill: passthrough.
- Correct a typo and run a focused check: fast.
- Add a small, documented CLI option with deterministic tests: fast.
- Diagnose a dependency path broken by a package-manager upgrade: balanced.
- Research an external API from official sources and recommend an integration:
  balanced.
- Update several known modules in one repository with focused tests: balanced.
- Trace and fix a bug spanning a client and backend: deep.
- Review a broad application and implement verified fixes: deep.
- Design a destructive production migration with incomplete rollback: critical.
- Commit and push a verified documentation edit: keep its existing tier; the
  external write is an authorization concern, not a reasoning-tier signal.
