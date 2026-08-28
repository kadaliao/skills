---
name: minimalist-coding
description: Use when the user asks for a focused implementation, bug fix, simplification, dependency reduction, or to avoid over-engineering. Chooses the smallest clear, compatible, and risk-proportionate change after checking whether the requested capability already exists.
license: MIT
metadata:
  author: kadaliao
  version: "1.0"
---

# Minimalist Coding

Deliver the requested behavior with the least new complexity that remains clear,
correct, and maintainable in the existing codebase. The goal is not the fewest
physical lines; it is the smallest justified change.

Always respond in the user's language.

## Decision Ladder

Before adding code, stop at the first option that satisfies the request:

1. **Do not add unrequested scope** - omit behavior the user did not ask for.
2. **Reuse local code** - find the existing helper, pattern, or API in the codebase.
3. **Use the standard library** - prefer it when it solves the problem clearly.
4. **Use the native platform** - rely on framework or platform functionality already in use.
5. **Use an installed dependency** - do not add a package when an existing dependency fits.
6. **Add minimal code** - write only the code needed to meet the defined behavior.

Prefer the smallest clear expression, not a forced one-liner. Split code when a
single expression obscures control flow, resource ownership, or failure handling.

## Rules

- Do not invent interfaces, base classes, configuration layers, or generic helpers
  for one known use case.
- Do not install a dependency for functionality the standard library, native
  platform, or existing dependency provides cleanly.
- Reuse the repository's established conventions before introducing a new pattern.
- Keep the diff within the requested ownership boundary. Do not combine unrelated
  refactors with a feature or bug fix.
- Ask a scope question only when the request is ambiguous or a simpler alternative
  materially reduces cost, risk, or ongoing maintenance. Otherwise implement the
  stated request.
- Do not hardcode secrets, environment-specific endpoints, operational limits, or
  business policy merely because they have one current caller.

## Reliability Is Proportionate To Risk

Minimalism does not mean omitting necessary safeguards.

- Validate untrusted input at its boundary.
- Preserve resource cleanup and existing error-propagation conventions.
- Handle failures from I/O, networks, persistence, authentication, or concurrency
  when the changed path can realistically encounter them.
- Add comments only for non-obvious decisions or constraints.
- Add logging only when it serves an existing operational or debugging need.
- Add focused verification for changed behavior, using the repository's existing
  test and validation conventions.

Do not add speculative retries, fallback systems, configuration, telemetry, or
defensive branches for unsupported or unreachable scenarios.

## Workflow

1. Read the request, relevant code, and local conventions before editing.
2. Apply the decision ladder and identify the smallest option that meets the
   requested behavior.
3. State a non-obvious decision concisely when it affects scope or tradeoffs.
4. Make the narrowest clear change; delete obsolete code rather than preserving it
   for hypothetical reuse.
5. Verify the behavior proportionately to its risk and blast radius.
6. Report what changed and the verification performed without padding the result.

## Anti-Patterns

| Anti-pattern | Preferred response |
| --- | --- |
| New package for a small utility | Use the standard library or an installed dependency. |
| Class or generic abstraction for one use | Keep the logic local; extract after demonstrated reuse. |
| Configuration for a stable local value | Keep it local, unless it is environment-, security-, or policy-sensitive. |
| One-line expression that hides control flow | Use a few clear lines. |
| Broad refactor attached to a narrow fix | Change only the affected path. |
| Omitting likely boundary failures for brevity | Add the smallest handling consistent with local conventions. |
