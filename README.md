# skills

General-purpose agent skills following the open [Agent Skills](https://agentskills.io) specification: one directory per skill, with a `SKILL.md` carrying metadata and instructions. Any host that implements the spec can use them — Claude Code, Codex, Gemini CLI, OpenCode, Cursor, and others. Skills are written in English but respond in the user's language.

The collection is deliberately small. Anything a one-line prompt can do stays a prompt; only workflows where a fixed procedure carries real value over hand-typing get turned into skills, and a skill gets deleted the moment it turns into ritual.

## Skills

| Skill | What it does |
|---|---|
| [debrief](debrief/) | Post-implementation learning loop: the agent explains its key decisions, then quizzes you one question at a time until you actually understand what was done — see its [README](debrief/README.md) |
| [model-router](model-router/) | **Codex only.** Routes a task to one Codex custom-agent tier (pinned OpenAI model + reasoning effort), keeps it sticky for follow-ups, and escalates on evidence — see its [README](model-router/README.md) |

## Install

A skill is just a directory — install it by dropping that directory into your agent's skills location. For Claude Code that's `~/.claude/skills/` (global) or `.claude/skills/` (per project); see [agentskills.io](https://agentskills.io) for other clients' conventions.

One line to install a single skill, no git history, via [degit](https://github.com/Rich-Harris/degit) (needs Node.js):

```bash
npx degit kadaliao/skills/debrief ~/.claude/skills/debrief
```

Swap `debrief` for any skill name and the destination for your client's skills directory. Or clone the whole repo and copy the directories you want.

## License

[MIT](LICENSE)
