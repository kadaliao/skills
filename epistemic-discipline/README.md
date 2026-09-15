# epistemic-discipline

Epistemic tagging mode: every claim carries its source and confidence, symbolic frames may not leak into real-world conclusions, citations may not be fabricated, and nothing is conceded without new evidence.

This is a discipline you switch on for a specific kind of work — checking a claim, weighing evidence, explaining why you believe something. It is deliberately off by default.

## Install

Drop the directory into your agent's skills location:

```bash
npx degit kadaliao/skills/epistemic-discipline ~/.agents/skills/epistemic-discipline
```

`SKILL.md` is the only entry point, and its frontmatter `name` must match the directory name. Adjust the destination for other clients (for Claude Code, `~/.claude/skills/`).

## Triggers

Explicit invocation only:

```
/tags            # enable full
/tags lite       # enable lite
/tags off        # disable
tag every claim / epistemic mode
严谨模式 / 打标签 / 标记论断 / 标记模式
```

It does **not** enable itself because you asked a factual question, asked it to verify something, or pushed back on an answer.

## Why this is not a resident custom instruction

A resident instruction applies to **every** task. This ruleset then contaminates code generation, file operations, simple lookups, and small talk: there are no epistemic claims there to label, the tags become noise, and the agent performs contrarianism in situations that do not call for an argument.

A skill trades that away in the other direction — it will not trigger itself. If you find yourself wanting these rules constantly in ordinary Q&A, the fix is not to move the whole ruleset back into resident instructions. Shrink the resident version to three lines (never fabricate citations; never use a frame's conclusion as real-world grounds; never concede without new evidence) and leave the tagging system in the skill.

## Interaction with other skills

- With `caveman`: compress style, not tags. `[KNOWN, HIGH]` does not become `K/H`.
- With `high-signal-review`: that skill's "report only reproducible problems" bar outranks this skill's requirement to tag everything.
