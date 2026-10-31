---
name: longterm-memory
description: 'Store and retrieve knowledge in Hippo, the SQLite-backed long-term memory for development agents. Use when: persisting design decisions, learned patterns, bugs, tricks, rationale; searching prior knowledge before answering questions or making plans; exploring untested ideas; confirming knowledge was useful.'
user-invocable: false
disable-model-invocation: false
---

# Long-Term Memory (Hippo) — Store & Retrieve

## When to Use
- **Before answering a question** about this project or its conventions — always check memory first
- **Before making a plan or evaluating an option** that may depend on past work
- **After learning something new** — a fact, rule, trick, heuristic, or pattern
- **After resolving a contradiction** — record the resolution and why
- **After making a decision** — capture the option chosen and the rationale
- **When searching for prior knowledge** on a topic you've worked on before

## What It Does
Hippo is a standalone, agent-agnostic, SQLite-backed knowledge store. It persists what agents learn across sessions so past mistakes are not repeated and known solutions are not re-discovered. The real content lives at the source; Hippo stores a curated insight about it plus a pointer (`metadata`) back to the source. Curation (promotion, pruning, connection maintenance) is handled by the `longterm-memory-curation` skill.

## Procedure

> **Access:** In VS Code Copilot / Claude Desktop / Cline, use the `hippo_*` MCP tools directly (server: `hippo/hippo_mcp/`, client config in `hippo/hippo_mcp/README.md`). In a Python process, `from hippo.agents import ...`. Both paths map 1:1 — every `hippo.agents` function has a matching `hippo_*` MCP tool. See `architecture/design-docs/hippo-mcp-server-design.md` for details.

### Retrieving Knowledge (always do this first)
1. **Search** — call `retrieve_knowledge(query="...", tags=[...], category="...")` from `hippo.agents`. Start with specific tags; call `list_tags(prefix="...")` if unsure what tags exist.
2. **Evaluate** — read `total_matches` in the response. If 0, loosen tags (drop `match_all_tags=True`) or add a text query. If >50, add a text query to narrow.
3. **Paginate** — if the first batch isn't helpful, call again with `offset=10`. Try 2–3 synonym variations of your query.
4. **Cross-check** — for important retrievals, call `get_connections(...)` on the top results to surface supporting and contradicting knowledge.
5. **Explore untested** — call `explore()` when you suspect newer, unproven knowledge exists. Returns `usefulness == 0` items first.

### Storing Knowledge (after learning something)
1. **Decide if it's a thought or knowledge** — if the idea is not yet fully formed, call `store_thought(...)` and promote it later during curation. Otherwise, proceed.
2. **Choose a category** — see `./references/category-decision-tree.md`. Pick exactly one.
3. **Choose tags** — use lowercase-hyphenated tags. Call `list_tags()` to prefer existing tags over inventing new ones. Tag by 4 dimensions: topic, tool, source, use-case.
4. **Calibrate confidence** — default is `1.0`. Lower deliberately when unsure. See `./references/knowledge-fields.md` for the confidence scale.
5. **Store** — call `store_knowledge(title, body, category, tags=[...], short_description="...", confidence=N, metadata="path/to/source")`. `short_description` is required (one verb sentence, ≤300 chars). Bodies over 5 KB are rejected — split into connected items or store at the source and link via `metadata`.
6. **Connect** — after storing, search for items with overlapping tags and create `related_to` edges using `connect_knowledge(...)`.

### After Applying Knowledge
1. **Mark useful** — call `mark_useful(knowledge_id)` after successfully applying retrieved knowledge. This drives ranking so good knowledge surfaces first in future searches. Do not mark useful prematurely.
2. **Run maintenance** — at session start, call `get_maintenance_checklist()` and review the top priorities. Full curation procedures are in the `longterm-memory-curation` skill.

## Important Rules
- **Algorithm results are suggestions, not ground truth.** The retrieval engine filters and ranks; you reason. Never treat the top hit as authoritative just because it ranked first.
- **Bodies ≤ 5 KB.** Split large content into connected items or store at the source.
- **Metadata is a pointer** (path or URL), not a JSON blob. The real content lives at the source.

## References
- [Category Decision Tree](./references/category-decision-tree.md) — the 10 categories and when to use each
- [Retrieval Tools](./references/retrieval-tools.md) — all available search and fetch tools
- [Knowledge Fields](./references/knowledge-fields.md) — field roles, confidence calibration, and tag conventions
