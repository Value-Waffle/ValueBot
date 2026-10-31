# 10 — Contributing

How to change valuebot without breaking its invariants, and what a reviewer will
look for.

> For the full contribution workflow — setup, issue reporting, the pull request
> process, commit conventions and the code of conduct — see the repository
> [CONTRIBUTING.md](../../../CONTRIBUTING.md). This page is the valuebot-specific
> detail: where to change what, and what the architecture forbids.

## Before you start

```bash
cd valuebot
./bootstrap.sh                       # local venv
.venv/bin/python -m pytest tests -q  # 76 passed (or passed + skipped)
```

Read [Architecture](01-architecture.md) and
[Module contracts](02-module-contracts.md). The short version:

1. A module owns its data end to end.
2. Cross-module access only through a protocol.
3. `analysis → fundamentals` is the only edge.
4. Every number leaves with a citation.
5. stdout is the JSON-RPC channel.

## Recipes

### Add a tool

```
mcp/modules/<module>/tools/__init__.py
```

```python
@mcp.tool()
def my_tool(symbol: str, limit: int = 20) -> dict:
    """One sentence the model will read.

    Args:
        symbol: Exact ticker.
        limit: Page size (1-50).
    """
    started = time.perf_counter()
    try:
        data = service.my_method(symbol, limit=max(1, min(int(limit), 50)))
        return success(MODULE, "my_tool", data, symbol=data.get("symbol"),
                       cik=data.get("cik"), citations=data.pop("citations", []),
                       paging=data.get("paging"), started=started, cap=6144)
    except Exception as exc:
        return _error("my_tool", exc, started)
```

Then:

| File | Change |
|:---|:---|
| `server.py` | add the name to `MODULE_TOOLS[module]` |
| agent exports | add to `tools` if a persona needs it |
| `docs/users/03-tools-reference.md` | document arguments, returns and errors |
| `tests` | argument clamping + one failure path |

Checklist: docstring (the model reads it), integer clamps, typed errors, `cap=`,
citations, no prints.

### Add a line item

`mcp/modules/fundamentals/domain/concepts.py`:

```python
LineItemDef(
    name="deferred_revenue",
    label="Deferred revenue",
    concepts=("ContractWithCustomerLiabilityCurrent",
              "DeferredRevenueCurrent"),
    unit="USD",
    period_type="instant",
)
```

Rules:

| Rule | Detail |
|:---|:---|
| Candidates ordered | first concept that returns rows wins; put the most specific first |
| `unit` | `USD`, `shares`, `USD/shares` |
| `period_type` | `duration` for flows, `instant` for balances |
| `derived_from` | only when the item is a sum of other line items |
| Version | bump `VOCABULARY_VERSION` only if an existing mapping changes |

Verify against the local fixture:

```bash
.venv/bin/python -m pytest tests/unit/fundamentals -q
```

### Add a metric

See [Analysis and DCF § Adding or changing a metric](07-analysis-and-dcf.md#adding-or-changing-a-metric).
Required: `MetricDef`, an `engine.compute_one` branch, tests for arithmetic and
for each applicable quality state.

### Add a module

1. `mcp/modules/<name>/{__init__,service.py,tools/__init__.py}`.
2. Optional `sources/`, `domain/`, `store/` — keep I/O out of `domain/`.
3. Declare `api_version = 1`.
4. Register in `server.py` (`MODULE_TOOLS` + `build_modules()`), guarded with
   `_build()` so a failure degrades instead of crashing.
5. Add the isolation matrix row in `tests/contract/test_isolation.py`.
6. Give it its own SQLite file under `${PLUGIN_DATA}/modules/<name>/`.
7. Document a numbered page under `docs/dev/` if it needs internals, and the
   tools under `docs/users/03-tools-reference.md`.

### Add a skill

`skills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: One sentence describing exactly when the model should use this.
---

## Workflow
1. …
2. …

## Rules
- Never …
```

| Rule | Why |
|:---|:---|
| `description` states the trigger | it is the retrieval signal |
| Short and imperative | long skills get partially ignored |
| No tool names that do not exist | the model will call them and fail |
| Reference citation keys, not URLs | only the server mints citations |

Then add it to the agent exports that need it and to
`tests/contract/test_package.py` if it is a required skill.

### Add an error type

`mcp/core/errors.py`:

```python
class MyError(ValuebotError):
    code = "my_error"
```

Set `retryable = True` only when a retry can succeed. Add a `hint` that tells the
operator what to do. Document the code in
[`users/03-tools-reference.md`](../users/03-tools-reference.md#error-codes).

### Add configuration

1. `mcp/core/config.py`: module constant + `refresh()` + `describe()`.
2. `mcp.json` `env:` if LibreChat should set it.
3. `.env.example`.
4. `docs/users/02-configuration.md` table.
5. A precedence test in `tests/unit/core/test_config_identity.py`.

Never read another module's environment variable, and never make a path
mandatory — `${PLUGIN_DATA}` must stay the only writable root.

## Style

| Area | Convention |
|:---|:---|
| Imports | stdlib, then `core`, then local; lazy-import heavy libraries inside functions |
| Types | `from __future__ import annotations`; dataclasses are frozen |
| Errors | raise `ValuebotError` subclasses; never `SystemExit` or bare `Exception` |
| Logging | `logging` to stderr; no `print` anywhere under `mcp/` |
| SQL | parameterised only; no string interpolation of values |
| Paths | `pathlib`, resolved, and checked against the allowed root |
| Comments | only where the code cannot say it — no narration |
| Docstrings | tool docstrings are model prompts: state what it does and its ranges |

Naming: modules use `snake_case` packages, tools use `verb_noun`, metric ids use
domain nouns (`roe`, `net_debt_to_ebitda`), section IDs are derived, never
hand-written.

## Review checklist

**Correctness**

- [ ] Numbers trace to a cited line item
- [ ] `quality` states handled (`gap`, `unavailable`, `not_meaningful`)
- [ ] Division by zero and negative-equity cases covered
- [ ] Period matching uses `period_end`, not `fiscal_year`
- [ ] Instant series use the canonical fiscal year-end set

**Boundaries**

- [ ] No new cross-module import without a documented protocol
- [ ] No SQL or file path crosses a module boundary
- [ ] New module is guarded in `server.py`
- [ ] Isolation test extended

**Interface**

- [ ] Tool docstring includes argument ranges
- [ ] Arguments clamped server-side
- [ ] Failures return a typed code with a hint
- [ ] `cap=` set and paging exposed
- [ ] Version constant bumped if semantics changed

**Ops**

- [ ] No secrets, `identity.json`, `*.sqlite` or probe data added
- [ ] `mcp.json` / `plugin.json` schema versions still 1.0.0 and equal
- [ ] Docs updated (`users/03-tools-reference.md`, `dev/` page as needed)
- [ ] `.venv/bin/python -m pytest tests -q` passes

## Commit and PR

```
reports: index filings from the SEC submissions JSON

Cold Company.get_filings() took ~480 s; one submissions request returns the
full history in under a second and is cached for 12 h.

- sources/edgar_source.py: submissions index, requests HTML with edgartools fallback
- store/filings_store.py: latest() helper
- requirements: requests>=2.31
- docs: submissions path in user and dev guides
```

Prefixes: `fundamentals:`, `analysis:`, `reports:`, `thesis:`, `core:`, `docs:`,
`tests:`, `setup:`.

A PR should state which module changed, why the boundary is unchanged (or which
protocol was added), and the test evidence.

## Where to ask

| Question | Look at |
|:---|:---|
| Why is it isolated this way? | [Architecture](01-architecture.md), design docs |
| Why does the parser do that? | [Reports and parser](06-reports-parser.md) |
| Why is the DCF this simple? | [Analysis and DCF](07-analysis-and-dcf.md) |
| Why did a tool return that error? | [`users/08-troubleshooting-and-faq.md`](../users/08-troubleshooting-and-faq.md) |

## Next

- [Testing](05-testing.md)
- [Deployment](08-deployment.md)
- [Roadmap](09-roadmap.md)
- [Product roadmap](../roadmap.md)
