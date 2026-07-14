# skills

Agent skills following the open [Agent Skills](https://agentskills.io) specification — one directory per skill, a `SKILL.md` carrying metadata and instructions. Not tied to any single agent: they work with Claude Code, Codex, Gemini CLI, OpenCode, and any other host that supports the spec. Skills are written in English but respond in whatever language the user speaks.

## Where this comes from

The ideas are from Thariq's ([@trq212](https://x.com/trq212)) article *A Field Guide to Fable: Finding Your Unknowns*: the quality of AI-assisted work is bottlenecked by your ability to clarify your own unknowns. Your prompt is the map, the codebase is the territory, and the gap between them is the four quadrants of (un)known (un)knowns. The article collects eight practices — blind-spot passes, brainstorms and prototypes, interviews, references, and implementation plans before the work; deviation notes during; explainers and quizzes after.

This repo's stance is restraint. Most of those eight are one-line prompt vocabulary — typing them is enough, and wrapping them in skills would add drag, not leverage. Only workflows where a fixed procedure carries real value over a hand-typed prompt get turned into skills, and a skill gets deleted the moment it turns into ritual.

## Skills

| Skill | What it does |
|---|---|
| [debrief](debrief/SKILL.md) | Post-implementation learning loop: the agent explains its key decisions (why this path, which existing code the change depends on, deviations from plan, what it decided on your behalf), then quizzes you one question at a time until you actually understand what was done |

## Suggested pairing

- **Before implementation**: an interview-style grilling to surface your unknowns — a grill-me-style skill, or simply prompt the agent to interview you one question at a time, prioritizing questions whose answers would change the architecture.
- **After implementation**: `debrief` to verify your understanding. Wrong quiz answers are your verified blind spots — exactly the things worth recording into long-term memory.

## Install

- **Claude Code**: copy a skill directory into `~/.claude/skills/` (global) or `.claude/skills/` (per project).
- **Other hosts**: see [agentskills.io](https://agentskills.io) for your client's skills directory convention.

## License

[MIT](LICENSE)
