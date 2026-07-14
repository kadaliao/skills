---
name: debrief
description: Post-implementation learning loop that explains the key decisions behind completed work, then verifies the user's understanding with an interactive quiz. Trigger only when the user explicitly says /debrief, asks for a debrief, asks to be quizzed on a change, or accepts a wrap-up reminder; never auto-run otherwise. Always responds in the user's language.
license: MIT
metadata:
  author: kadaliao
  version: "1.0"
---

# Debrief: post-implementation learning loop

Purpose: after the AI finishes the work, the user learns how it was done. The deliverable is verified understanding, not a summary.

Always respond in the language the user is using.

## 1. Explain (one message, four sections, in order)

Do not restate the diff. Cover only what the diff cannot show:

1. **Why this path** — the rejected alternatives and why they lost.
2. **Existing code paths this change depends on** — which pre-existing code the correctness of this change rests on (give file:line). This is the biggest blind spot when reading diffs.
3. **Deviations from the plan** — where the work departed from the original plan or common practice, and why.
4. **Decisions made on the user's behalf** — choices the user never specified that the AI settled, listed one by one.

At most 5 lines per section; write "none" instead of padding.

## 2. Quiz (in-chat, one question at a time)

- 3–5 questions, all drawn from decision points in the four sections above. No syntax or naming trivia, and no recall questions answerable verbatim from the explanation.
- Good question shapes: "If condition X changed, where does this approach break first?" "Why not the more direct Y at point N?"
- Ask one question at a time. If the host has an interactive question tool (e.g. Claude Code's AskUserQuestion), use it and include one plausible-but-wrong option; otherwise ask in plain text. Wait for the answer — never answer for the user, never dump all questions at once.
- On a wrong answer: re-explain that point from a different angle, ask a variant question, and move on only after it is passed.

## 3. Wrap-up

- List the knowledge points behind any wrong answers.
- If there were wrong answers and the host has a long-term memory mechanism (a record-lesson-style skill, built-in agent memory), ask once whether to save them. Write only on an explicit yes, never automatically. Without a memory mechanism, hand the points to the user as a short list to record.
- All correct and no deviations: wrap up in one sentence, no elaboration.

## Boundaries

- For small changes (docs-only, few-line patches), push back: "not worth a debrief."
- The explanation and questions must come from what actually happened in this session; if context is thin, read the relevant diff/files first — never invent.
