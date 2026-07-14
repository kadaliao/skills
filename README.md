# skills

General-purpose agent skills following the open [Agent Skills](https://agentskills.io) specification: one directory per skill, with a `SKILL.md` carrying metadata and instructions. Any host that implements the spec can use them — Claude Code, Codex, Gemini CLI, OpenCode, Cursor, and others. Skills are written in English but respond in the user's language.

The collection is deliberately small. Anything a one-line prompt can do stays a prompt; only workflows where a fixed procedure carries real value over hand-typing get turned into skills, and a skill gets deleted the moment it turns into ritual.

## Skills

| Skill | What it does |
|---|---|
| [debrief](debrief/) | Post-implementation learning loop: the agent explains its key decisions, then quizzes you one question at a time until you actually understand what was done — see its [README](debrief/README.md) |

## Install

Copy a skill directory into your agent's skills location — e.g. `~/.claude/skills/` (global) or `.claude/skills/` (per project) for Claude Code; see [agentskills.io](https://agentskills.io) for other clients' conventions.

## License

[MIT](LICENSE)
