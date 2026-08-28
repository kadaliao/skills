---
name: high-signal-review
description: Use when reviewing a diff, pull request, patch, or implementation. Reports only concrete, change-induced, evidence-backed correctness, security, compatibility, or meaningful performance issues; suppresses speculative, stylistic, and out-of-scope feedback.
license: MIT
metadata:
  author: kadaliao
  version: "1.0"
---

# High-Signal Review

Review for defects and regression risk, not hypothetical perfection. Prefer no
findings over weak findings. Always respond in the user's language.

## Finding Gate

Report a finding only when every condition holds:

1. **Change-induced** - the diff introduced the problem, made it materially worse,
   or made a pre-existing issue newly reachable.
2. **Concrete impact** - it can cause incorrect behavior, data loss, a security
   issue, a supported compatibility break, or a meaningful performance regression.
3. **Realistic trigger** - identify the input, state, caller, or execution path
   that causes it.
4. **Evidence** - ground it in the changed code, a caller, a type, a test, or a
   documented contract.
5. **Actionable remedy** - the author can make a specific, local correction.

If a concern fails any part of this gate, do not present it as a finding.

## Do Not Report By Default

- Naming, formatting, style, or personal design preferences.
- Refactors or abstractions that are not needed to correct a defect in this diff.
- Hypothetical future scale, reuse, extensibility, or architecture concerns.
- Generic advice such as "could be cleaner," "might be safer," or "consider X."
- Missing error handling for failure modes not reachable from the changed path.
- Pre-existing issues unrelated to the diff.
- Missing tests without a concrete changed behavior and realistic untested
  regression path.

Only include architecture, maintainability, polish, or optional test suggestions
when the user explicitly asks for them. Label those as non-blocking suggestions,
never as defects.

## Severity

- **P0** - data loss, security compromise, or production outage.
- **P1** - definite incorrect behavior on a supported or common path.
- **P2** - definite edge-case regression with a concrete trigger.
- **P3** - do not use unless the user explicitly requests non-blocking feedback.

Do not raise severity because a scenario is merely possible. Merge multiple
symptoms with the same root cause into one finding.

## Review Workflow

1. Read the task and diff first. Treat stated behavior changes as intentional
   unless they conflict with an established contract.
2. Trace changed inputs, outputs, state transitions, error paths, and relevant
   callers or consumers.
3. Inspect tests only for changed behavior and realistic boundary conditions.
4. Apply the Finding Gate to each candidate concern.
5. Keep only the highest-signal independent findings. Do not pad the review.

## Output

List findings first, ordered by severity. Each finding must include:

- severity and file:line
- triggering scenario
- concrete impact
- concise remediation direction

After findings, include `Test gaps` only for a concrete changed behavior that
remains unverified and has a realistic regression path. Omit the section when
there are none.

When no concern passes the Finding Gate, state exactly:

`No actionable correctness or regression issues found.`
