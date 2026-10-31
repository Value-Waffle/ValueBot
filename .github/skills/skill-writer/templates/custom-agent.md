Copy this template and save it as `.github/agents/<your-agent>.agent.md`.

```markdown
---
description: "Do one specific thing. Use when: trigger-keyword, another-trigger."
tools: [read, search, edit]
user-invocable: true
---
You are a specialist at {specific task}. Your only job is {clear purpose}.

## Constraints
- DO NOT do thing this agent should never do
- DO NOT do another restricted thing
- ONLY focus on this one task

## Approach
1. Step one — what to do first
2. Step two — what to do next
3. Step three — produce the output

## Output
Return the path of the created file and a one-line summary.
```
