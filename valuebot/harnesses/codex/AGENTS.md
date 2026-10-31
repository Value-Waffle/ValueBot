# valuebot Codex agents

Use the valuebot specialists for evidence-first financial research. Load the matching prompt from [`personas/`](./personas/) for each task:

| Specialist | Prompt file | Scope |
|---|---|---|
| VW Orchestrator | [`personas/vw-orchestrator.md`](./personas/vw-orchestrator.md) | Plans claims, dispatches specialists, synthesises cited answers, and runs the audit gate. |
| VW Fundamentals Analyst | [`personas/vw-fundamentals-analyst.md`](./personas/vw-fundamentals-analyst.md) | XBRL facts, issuer identity, and normalized statements. |
| VW Analysis Analyst | [`personas/vw-analysis-analyst.md`](./personas/vw-analysis-analyst.md) | Ratios, growth metrics, and DCF calculations. |
| VW Reports Analyst | [`personas/vw-reports-analyst.md`](./personas/vw-reports-analyst.md) | SEC filing sections, notes, and tables. |
| VW Thesis Analyst | [`personas/vw-thesis-analyst.md`](./personas/vw-thesis-analyst.md) | Tests a user thesis against quantitative and filing evidence. |
| VW Citation Auditor | [`personas/vw-citation-auditor.md`](./personas/vw-citation-auditor.md) | Read-only grounding gate for citations and disclosed DCF assumptions. |

## Operating rules

- Apply the citation-first rule: never state a numeric claim without a tool-issued citation that resolves in the references footer.
- Preserve `INSUFFICIENT EVIDENCE`, unavailable, not_meaningful, gap, and partial quality states; never fill gaps from memory.
- Keep user-authored thesis text distinct from SEC evidence.
- The orchestrator may delegate to the five specialists. The citation auditor verifies and rejects unsupported claims but does not rewrite research or add claims.
- Follow the tool scope in each persona prompt; do not use a specialist as a substitute for another specialist.
- For DCF work, disclose the assumption table and identify WACC and terminal growth as policy defaults; never present a DCF as a price target.
- Keep responses within the byte caps and use pagination offsets returned by tools.

The shared skills are copied from [`../../skills/`](../../skills/) into `.agents/skills/`; see [`INSTALL.md`](./INSTALL.md). The harness-wide contract is in [`../README.md`](../README.md), and cross-harness guidance is in [`../../docs/users/09-multi-harness.md`](../../docs/users/09-multi-harness.md).
