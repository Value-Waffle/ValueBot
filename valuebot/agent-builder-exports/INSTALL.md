# Installing the six valuebot agents

`agent-builder-exports/` holds six reference personas:

| File | Agent | Tools |
|:---|:---|:---|
| `vw-orchestrator.json` | VW Orchestrator | all 15 tools |
| `vw-fundamentals-analyst.json` | VW Fundamentals Analyst | 5 fundamentals tools |
| `vw-analysis-analyst.json` | VW Analysis Analyst | ratio and DCF tools |
| `vw-reports-analyst.json` | VW Reports Analyst | filing and report tools |
| `vw-thesis-analyst.json` | VW Thesis Analyst | facts, ratios, DCF, reports, vault |
| `vw-citation-auditor.json` | VW Citation Auditor | verification tools |

These are **not** part of the plugin manifest. LibreChat's Agent Plugins format
carries skills and MCP servers, not agents. Create each agent once in Agent
Builder and copy the fields from the JSON.

## Before you start

1. Install the plugin and restart LibreChat
   ([`../docs/users/01-getting-started.md`](../docs/users/01-getting-started.md)).
2. Ask for `ping` and confirm four modules are `ready` and
   `identity_configured` is true.
3. Confirm the five skill directories exist under `skills/`.
4. Turn `web_search` off for these agents. Evidence comes from the MCP server.

## Create an agent

1. Agent Builder → **Create Agent**.
2. Paste `name`, `description` and `instructions`.
3. Select exactly the tools listed in `tools`.
4. Attach the skills listed in `skills`.
5. Set the model and temperature from `modelParameters`.
6. For the orchestrator, add the other five agents as subagents.

## Format caveat

The JSON is a self-describing reference format (`schemaVersion: 1.0.0`), not a
guaranteed LibreChat import file. If your build exposes an agent import, verify
name, model, instructions, tools, skills and subagents after importing; fall
back to manual entry if anything is dropped.

## Tool naming

```
symbol_resolve company_profile facts_query facts_timeseries statement_get
ratio_catalog ratio_compute dcf_compute
filing_list report_sections report_section report_search report_table
thesis_read thesis_annotations ping
```

If a tool is missing from the picker, the server is not connected or the module
failed to initialise; check `ping` and the api log.
