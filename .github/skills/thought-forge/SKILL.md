---
name: thought-forge
description: 'Structure, persist and visualize agent thinking in Thought Forge, the SQLite-backed cognitive scratchpad (a subsystem of Hippo). Use when: working through a multi-step problem or debugging trail, comparing options, tracking hypotheses and evidence, resuming reasoning across sessions, externalizing chain-of-thought, promoting validated conclusions to long-term memory or tasks.'
user-invocable: false
disable-model-invocation: false
---

# Thought Forge — Externalize & Structure Your Thinking

## When to Use
- **During a multi-step investigation** — debugging trails, design tradeoffs, root-cause analysis that spans many turns.
- **Before comparing options** — when you must weigh alternatives against criteria rather than deciding from memory.
- **When you must resume later** — reasoning that will not finish this session (context windows reset; Thought Forge does not).
- **After forming a testable claim** — record the hypothesis *before* you forget what you were testing.
- **When a conclusion deserves promotion** — a validated insight should move to Hippo LTM; an actionable decision should become a Board Games task.

## What It Does
Thought Forge is a **typed thinking workspace**: a SQLite database (`~/.hippo/thought_forge.db`) where each thought is a row in a thread, with a type and a state. It sits between the ephemeral context window (lost on reset) and permanent storage — Hippo LTM (what we know) and Board Games PM (what we must do). Modeled on LangGraph's concepts, but with zero dependencies beyond the existing `SQL_handler.py`.

- **API:** `from hippo import forge_*` (or the 19 `forge_*` MCP tools via the `thought-forge` server).
- **DB:** `~/.hippo/thought_forge.db` (configurable via `THOUGHT_FORGE_DB_PATH`).
- **Browse:** `datasette ~/.hippo/thought_forge.db --port 8002` (raw tables), `forge_render_mermaid(thread_id)` (static flowchart), or `python -m hippo.visual --open` (interactive mindmap).

## The Thought Type Taxonomy
Every thought is **typed**. Use the type that matches your intent — `note` is an escape hatch, not the default.

| Type | Phase | Meaning | Example |
|---|---|---|---|
| `prompt` | 🔔 Trigger | The request/task that started this thread | "Debug the connection leak in write mode" |
| `hypothesis` | 💡 Explore | A **testable**, falsifiable claim | "Leak is from not closing connections in the error path" |
| `idea` | 💡 Explore | A creative, not-yet-testable suggestion | "What if we used a connection pool with refcounting?" |
| `option` | 💡 Explore | A candidate solution among alternatives | "Option B: context managers guarantee cleanup" |
| `observation` | 🔍 Examine | A neutral fact noticed | "WAL grows 500MB after 1000 writes without close()" |
| `evidence_for` | 🔍 Examine | Data that supports a hypothesis/option | "Test with explicit close() → memory stable" |
| `evidence_against` | 🔍 Examine | Data that contradicts a hypothesis/option | "Same leak with read-only connections" |
| `assumption` | 🔍 Examine | An unverified premise the reasoning depends on | "Assuming single-agent access" |
| `question` | 🔍 Examine | An open question needing investigation | "Does SQLite release WAL pages on close or checkpoint?" |
| `conclusion` | 🎯 Synthesize | A final judgment / resolution | "Root cause: missing close() in error path" |
| `note` | 📝 Freeform | Annotation / aside (use sparingly) | "Also check board-games/db.py for the same pattern" |

## Per-Type States
States are type-specific — a hypothesis is never "complete", it is `confirmed` / `invalidated` / `inconclusive`. Call `forge_list_states(entry_type)` to discover valid transitions.

| Type | Valid states (default first) |
|---|---|
| `prompt` | received → clarified → addressed ; deferred |
| `hypothesis` | proposed → under_review → confirmed / invalidated / inconclusive |
| `idea` | proposed → exploring → viable / adopted / discarded |
| `option` | proposed → evaluating → selected / rejected / deferred |
| `observation` | noted → verified / invalidated |
| `evidence_for` / `evidence_against` | gathered → accepted / dismissed |
| `assumption` | stated → validated / invalidated ; risky |
| `question` | open → answered / blocked / irrelevant |
| `conclusion` | draft → final / superseded / retracted |
| `note` | active → archived |

**Key semantics:** `inconclusive` = null result (re-formulate or gather better evidence) · `dismissed` (evidence) = judged irrelevant, not false · `superseded` = replaced by a newer conclusion · `retracted` = explicitly withdrawn as wrong · `risky` (assumption) = non-terminal warning flag.

## Procedure
1. **Start a thread** — `forge_start_thread(title="Debug: connection leak", description="...")`. Capture the problem as a `prompt` entry.
2. **Think in typed steps** — `forge_think(thread_id, "hypothesis", "Leak is in the error path — finally block missing close()")`. Branch with `parent_id` when one thought refines another.
3. **Add evidence** — `forge_add_evidence(entry_id, "for"/"against", "Test: 10K writes with explicit close() → stable")`.
4. **Update states as you learn** — `forge_update_state(entry_id, "under_review")` → later `"confirmed"` / `"invalidated"`. Keep evidence `accepted` or `dismissed`.
5. **Compare options when choosing** — `forge_compare_options(thread_id, "DB selection", ["perf","ops"], ["SQLite","PG"])` then `forge_score_option(...)`.
6. **Resolve when done** — `forge_resolve_thread(thread_id, "Fix committed; memory stable", "resolved")`.
7. **Visualize if useful** — `forge_render_mermaid(thread_id)` → render the flowchart in VS Code to inspect the thought graph.
8. **Visualize interactively (optional)** — `./hippo/visual/serve.sh` (or `python -m hippo.visual --open`) launches a read-only, localhost **mindmap viewer** for any thread: pan/zoom, collapse/expand, filter by type/state, search, and detail inspection. The same graph is available programmatically via `forge_export_mindmap(thread_id)` (returns `{thread, nodes, edges, references}` JSON).
9. **Promote what matters** — see Bridging below.

## Bridging to Hippo & Board Games
- **`forge_promote_to_ltm(entry_id, category=None, tags=None)`** — promote a validated `conclusion`/`hypothesis` to Hippo LTM (permanent knowledge). The Hippo write happens first; the entry records `promoted_to_ltm`.
- **`forge_convert_to_task(entry_id, parent_node_id, priority)`** — convert an actionable decision to a Board Games task. Requires `board-games/` on the path and a running Board Games server; if it is unavailable you will get a `BoardGamesUnavailableError` with fix instructions.
- **`forge_link_reference(entry_id, ref_type, ref_id/ref_url, label)`** — attach cross-references (ltm_knowledge / pm_task / url / file).
- **`forge_validate_references(thread_id)`** — check references still resolve; returns `valid`, `stale`, and `unreachable` (subsystem not reachable — treat as "check manually", not "dead").

## Important Rules
- **Promotion is explicit, never automatic.** The act of promoting is a quality gate — you decide what is worth keeping long-term. `adopted` ideas do not auto-create hypotheses.
- **Threads are ephemeral.** Most are pruned (`forge_prune_threads`); only what you promote survives. Do not treat the forge as a knowledge base.
- **Query before assuming** — `forge_list_threads`, `forge_get_unresolved`, `forge_get_stats` let you see what is open before re-deriving it.
- **Type honestly.** If you cannot decide between `hypothesis` and `idea`, the content is probably an `idea` (untestable) — refine it later.
- **Keep content ≤ 5 KB** if it may be promoted (Hippo's body limit).

## References
- Design: `architecture/design-docs/thought-forge-design.md` (schema, taxonomy, state machines)
- Plan: `architecture/design-docs/thought-forge-implementation-plan.md`
- Visual Engine: `architecture/design-docs/thought-forge-visual-engine-design.md` + `-implementation-plan.md`
- Companion skill: `longterm-memory` (Hippo store & retrieve) · Board Games skill for task management
- DB mapping: `architecture/db-mapping.md` → Thought Forge section
