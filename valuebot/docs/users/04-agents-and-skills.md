# 04 — Agents and skills

The plugin ships **five skills** and **six reference agents**. Skills are part
of the plugin and load automatically; agents are created once in Agent Builder.

## Skills

Skills are instruction bundles the model loads when a task matches. They encode
the behaviour that makes valuebot's output trustworthy: cite everything, never
invent a number, never turn a DCF into a price target.

| Skill | Teaches the model to | Sections |
|:---|:---|:---|
| `grounded-citation` | attach `[n]` markers to tool citations, render the references footer, and drop any claim without a citation | Marker protocol · Source types · Derived values · References footer · Rejection rule · Banned behaviour |
| `hypothesis-analysis` | structure research as hypothesis → claims → evidence → verdict, gather facts before prose, stop after two fruitless calls | Structure · Facts before prose · Size discipline · Circuit breaker · Answer template |
| `ratio-analysis` | choose metrics with `ratio_catalog`, respect quality states, cite inputs, never present `unavailable`/`not_meaningful` as numbers | Workflow · Quality states · Interpretation rules · Output |
| `dcf-valuation` | run the DCF assumptions-first, name policy defaults, show sensitivity, and label the output as intrinsic value | Workflow · Rules · Output |
| `semantic-report-reading` | navigate section IDs and notes, handle `coverage.degraded`, page tables, cite sections | Workflow · Coverage and degradation · Tables · Citations · Boundaries |

Skills live in [`../../skills/`](../../skills/). Each is a `SKILL.md` with YAML
front matter (`name`, `description`) and a workflow body. LibreChat reports them
in the plugin load log:

```
[agentPlugins] Loaded 1 plugin(s) from /app/plugin: 5 skill(s), 1 MCP server(s)
```

## Agents

`agent-builder-exports/` holds six personas. They are **not** part of the plugin
manifest — Agent Plugins carries skills and MCP servers, not agents — so you
create each one once in Agent Builder.

| Agent | Job | Tools | Skills |
|:---|:---|:---|:---|
| **VW Orchestrator** | plans evidence, dispatches specialists, synthesises a cited answer, runs the citation audit | all 15 | `grounded-citation`, `hypothesis-analysis` |
| **VW Fundamentals Analyst** | XBRL facts, company identity, normalized statements | `symbol_resolve`, `company_profile`, `facts_query`, `facts_timeseries`, `statement_get` | `grounded-citation`, `hypothesis-analysis` |
| **VW Analysis Analyst** | ratios, growth, DCF, quality states | `symbol_resolve`, `facts_timeseries`, `statement_get`, `ratio_catalog`, `ratio_compute`, `dcf_compute` | `grounded-citation`, `ratio-analysis`, `dcf-valuation` |
| **VW Reports Analyst** | filing discovery, sections, notes, tables | `company_profile`, `filing_list`, `report_sections`, `report_section`, `report_search`, `report_table` | `grounded-citation`, `semantic-report-reading` |
| **VW Thesis Analyst** | tests a thesis against ratios, a DCF, filings and the vault | `symbol_resolve`, `facts_timeseries`, `ratio_compute`, `dcf_compute`, `report_section`, `thesis_read`, `thesis_annotations` | `grounded-citation`, `hypothesis-analysis`, `dcf-valuation` |
| **VW Citation Auditor** | verification gate: every number resolves to a tool citation, every assumption disclosed | `company_profile`, `filing_list`, `report_sections`, `report_section`, `facts_query`, `statement_get`, `ratio_catalog`, `dcf_compute` | `grounded-citation` |

### Why the split

| Reason | Effect |
|:---|:---|
| Fewer tools per agent | the model picks the right tool more reliably and uses fewer tokens on schemas |
| Narrow instructions | each persona's rules stay short and non-conflicting |
| Separate auditor | grounding becomes a check rather than a hope |
| Orchestrator keeps all tools | it can answer simple questions directly and delegate the rest |

## Installing the agents

Full steps: [`../../agent-builder-exports/INSTALL.md`](../../agent-builder-exports/INSTALL.md).

Summary:

1. Confirm the plugin is loaded and `ping` reports four `ready` modules.
2. Agent Builder → **Create Agent**.
3. Copy `name`, `description` and `instructions` from the JSON file.
4. Select exactly the tools listed in `tools` — use the picker names
   (`ratio_compute` etc.); LibreChat stores them as
   `ratio_compute_mcp_vw-mcp`.
5. Attach the skills listed in `skills/`.
6. Set the model and temperature from `modelParameters`.
7. For the orchestrator, add the other five agents as subagents.
8. Turn `web_search` off. Evidence must come from the MCP server, not the web.

Repeat once per agent. The JSON is a self-describing reference format
(`schemaVersion: 1.0.0`), not a guaranteed import file; verify after importing
and fall back to manual entry if a field is dropped.

## Tool naming

The MCP server is `vw-mcp`, so LibreChat prefixes every tool:

```
facts_query          →  facts_query_mcp_vw-mcp
dcf_compute          →  dcf_compute_mcp_vw-mcp
thesis_annotations   →  thesis_annotations_mcp_vw-mcp
```

All 19 tools — 3 core (`ping`, `citation_resolve`, `citation_view`) plus 16 domain:

```
ping
 citation_resolve citation_view
symbol_resolve company_profile facts_query facts_export facts_timeseries statement_get
ratio_catalog ratio_compute dcf_compute
filing_list report_sections report_section report_search report_table
thesis_read thesis_annotations
```

If a tool is missing from the picker, the server is not connected or a module
failed to initialise — check `ping` and the api log.

## Choosing a model

Any tool-calling model works. Practical guidance:

| Role | Model class | Why |
|:---|:---|:---|
| Orchestrator | strongest available | planning, synthesis, discipline |
| Fundamentals / Reports analysts | mid-tier | mostly extraction and summarising |
| Analysis analyst | mid-tier with good arithmetic | ratio interpretation, DCF framing |
| Citation auditor | cheap and literal | pattern checking, not reasoning |

Keep temperature low (0–0.3). See [Model endpoints](07-model-endpoints.md) for
DeepSeek and OpenCode Zen configuration.

## Skills without agents

You do not need the six agents to use the plugin. In a plain chat with `vw-mcp`
attached, the model can call any tool; the plugin's instructions already require
citations. Agents add routing, role separation and the audit gate.

## Next

- [Research workflows](05-research-workflows.md)
- [Tools reference](03-tools-reference.md)
