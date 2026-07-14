# debrief

Post-implementation learning loop. After an AI agent finishes a piece of work, it explains the key decisions behind it — why this path and not the alternatives, which existing code the change depends on, where it deviated from the plan, and what it decided on your behalf — then quizzes you one question at a time until you actually understand what was done. Wrong answers get re-explained from a different angle and re-tested before moving on.

The deliverable is verified understanding, not a summary: reading a diff (or a report you can skip) tells you little, because most of the behavior rests on existing code paths the diff never shows.

## Where this comes from

The idea is from Thariq's ([@trq212](https://x.com/trq212)) article *A Field Guide to Fable: Finding Your Unknowns*: the quality of AI-assisted work is bottlenecked by your ability to clarify your own unknowns. Your prompt is the map, the codebase is the territory, and the gap between them is the four quadrants of (un)known (un)knowns. The article collects eight practices — blind-spot passes, brainstorms and prototypes, interviews, references, and implementation plans before the work; deviation notes during; explainers and quizzes after — and closes with "what you learn becomes the map for next time."

This skill implements only the post-implementation loop (explainers + quizzes). The other practices are one-line prompt vocabulary — typing them is enough, and wrapping them in skills would add drag, not leverage. The quiz is in-chat and question-by-question precisely so it cannot be skimmed: a skippable report gets skipped.

## Trigger

Explicit only — `/debrief`, "quiz me on this change", or saying yes when the agent offers a debrief at wrap-up. It never auto-runs, and it pushes back on small changes ("not worth a debrief").

## Suggested pairing

- **Before implementation**: an interview-style grilling to surface your unknowns — a grill-me-style skill, or simply prompt the agent to interview you one question at a time, prioritizing questions whose answers would change the architecture.
- **After implementation**: `debrief` to verify your understanding. Wrong quiz answers are your verified blind spots — exactly the things worth recording into long-term memory.
