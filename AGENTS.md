# AGENTS.md — working agreement

## Agent handoff — per-delegation job cards

The orchestrator writes one job card per delegation at
`.agent_state/<delegation_id>.spec.json` and pre-creates
`.agent_state/<delegation_id>.report.json` with `status: "in_progress"`.

### Job card (written by the orchestrator, read-only for the sub-agent)

```json
{
  "delegation_id": "T1-core-platform",
  "problem": "why this delegation exists",
  "target_files": ["repo-relative paths"],
  "actions": ["ordered, testable instructions"],
  "verification_commands": ["cheapest/highest-value first"],
  "acceptance_criteria": ["observable pass conditions"],
  "notes": "constraints, prior decisions, do-not-do list"
}
```

### Report (written by the sub-agent, overwrites the stub)

```json
{
  "delegation_id": "T1-core-platform",
  "status": "done | partial | blocked",
  "summary": "what changed",
  "files_changed": ["..."],
  "verification_results": [{"criterion": "...", "result": "PASS|FAIL|UNVERIFIED", "evidence": "..."}],
  "open_issues": ["..."],
  "next_steps": ["..."]
}
```

Rules:

- Read your own spec first; do not edit other cards or other delegations' reports.
- Append one line per completed action to `.agent_state/<delegation_id>.events.jsonl`.
- `status: "partial"` or `"blocked"` is a valid success — record exactly where you stopped and why.
- Never widen scope beyond the card. If the card is wrong, stop and report `blocked`.
