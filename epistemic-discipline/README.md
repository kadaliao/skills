# epistemic-discipline

严谨标记模式：给每条论断打来源标签和置信度，禁止框架越界到现实结论，禁止编造引用，禁止无证据投降。

## 安装

已在 `~/.agents/skills/epistemic-discipline/`。`SKILL.md` 的 frontmatter 是唯一入口，`name` 必须与目录名一致。

## 触发

明确调用才启用，默认关闭：

```
/tags            # 开启 full 档
/tags lite       # 开启 lite 档（只标承重论断）
/tags off        # 关闭
严谨模式 / 打标签 / 标记论断 / tag every claim / epistemic mode
```

**不会**因为用户问事实、要求核实或质疑答案而自动启用。

## 为什么不做成常驻 custom instructions

常驻指令的代价是它对**所有**任务生效。这套规则会污染代码生成、文件操作、简单查询和闲聊：那里没有需要标注的认识论论断，标签只会变成噪音，而且会让 agent 在不需要辩论的场合表演唱反调。

做成显式 skill 的取舍是反过来的：它不会自己触发。如果你发现自己在普通问答里频繁想要这套规则，正确的修法不是把它塞回常驻指令，而是缩小常驻版本的范围——只保留三行（不许编造引用；框架结论不许当现实依据；未经新证据不投降），把标签体系留在 skill 里。

## 与其它 skill 的关系

- 和 `caveman` 叠加时：压缩风格，不压缩标签。`[KNOWN, HIGH]` 这种标签不许缩写成 `K/H`。
- 和 `high-signal-review` 叠加时：review 的"只报可复现问题"门槛优先于本 skill 的完整标注。
