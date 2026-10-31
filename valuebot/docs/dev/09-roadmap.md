# 09 — Roadmap

Two modules ship as protocols only. They exist so the interface is fixed before
the implementation lands, and so no existing module has to change when it does.

> **This is the module-level view.** For what is being built across the whole
> product, and in which order, see the [product roadmap](../roadmap.md). The two
> documents agree: `calendar` is the December 2026 side quest, `price_action`
> the March 2027 one.

## Current state

| Module | Status | Tools | Store | Dependencies |
|:---|:---|:---:|:---:|:---|
| `fundamentals` | shipped | 5 | yes | `core` |
| `analysis` | shipped | 3 | cache only | `core`, `fundamentals` |
| `reports` | shipped | 5 | yes | `core` |
| `thesis` | shipped | 2 | index reserved | `core` |
| `calendar` | reserved | 0 | — | — |
| `price_action` | reserved | 0 | — | — |

```python
# mcp/modules/calendar/api.py
@runtime_checkable
class CalendarAPI(Protocol):
    api_version: int
    def events(self, symbol: str, *, kinds=None, start=None, end=None) -> dict: ...

# mcp/modules/price_action/api.py
@runtime_checkable
class PriceAPI(Protocol):
    api_version: int
    def history(self, symbol: str, *, period: str = "1y", interval: str = "1d") -> dict: ...
```

Neither is registered in `server.py`; `VW_ENABLE_PRICE=0` keeps the optional
`price` extras uninstalled.

## `calendar` — planned

**Answers:** when is the next earnings report, what splits and dividends
happened, what is the ex-dividend date.

| Planned tool | Arguments | Returns |
|:---|:---|:---|
| `calendar_events` | `symbol`, `kinds`, `start`, `end`, `limit` | upcoming and past events |

Event kinds: `earnings`, `dividend`, `split`.

Design constraints already decided:

| Constraint | Reason |
|:---|:---|
| Own store (`modules/calendar/calendar.sqlite`) | no change to fundamentals tables |
| Own source adapter | calendar data is not XBRL and not in submissions JSON |
| Read-only, request-scoped | no scheduler, no background jobs |
| Citations point at the filing or the announcement | consistent with every other number |
| `api_version` from day one | cross-module compatibility |

Candidate sources, in preference order:

1. SEC 8-K Item 2.02 (results of operations) and Item 5.03 (dividend/split
   changes) — primary source, already reachable through `reports`.
2. Company IR pages via a documented fetch, if a stable URL exists.
3. A paid market calendar — only if the first two prove insufficient.

The first version should use (1) only: it keeps valuebot on primary sources and
reuses the existing filing index.

## `price_action` — planned

**Answers:** how the stock has traded, volatility, drawdown, relative strength.

| Planned tool | Arguments | Returns |
|:---|:---|:---|
| `price_history` | `symbol`, `period`, `interval` | OHLCV series |
| `price_stats` | `symbol`, `period` | return, volatility, drawdown, 50/200-day averages |

Design constraints already decided:

| Constraint | Reason |
|:---|:---|
| Optional dependency (`price` extra: `yfinance`, `tzdata`) | keeps the default install lean |
| Off by default (`VW_ENABLE_PRICE=0`) | no unexpected network calls to a third party |
| Never mixed into DCF by default | intrinsic value must not silently become a price target |
| Own store and cache | isolation, same as every other module |
| Market-cap and multiples require a price *and* a share count | share count comes from `fundamentals`; this would be the second cross-module edge if added |

If a cross-module edge is added, it must go through a protocol in
`modules/price_action/api.py` and be documented in
[Module contracts](02-module-contracts.md). Prefer returning a price series and
letting `analysis` combine it, so `price_action` keeps no financial knowledge.

## Enabling a reserved module

The pattern is the same for both:

1. Implement `sources/`, `domain/`, `store/` and `service.py`.
2. Register tools in `tools/__init__.py`.
3. Add the module to `MODULE_TOOLS` in `server.py` and to `build_modules()`.
4. Add the dependency to `mcp/pyproject.toml` (optional extra if third-party).
5. Extend the import matrix in `tests/contract/test_isolation.py`.
6. Add unit tests plus one contract assertion.
7. Document the tools in `docs/users/03-tools-reference.md` and move a row in
   the status table above to "shipped".

## Explicitly out of scope

| Not planned | Why |
|:---|:---|
| Order execution / brokerage integration | not a research tool; regulatory scope |
| Portfolio accounting | different data model, different audience |
| Real-time streaming quotes | cost and licensing; daily granularity is enough for research |
| **Sentiment scoring** | a score has no citation path and no verifiable meaning; the June 2027 news module is attributed retrieval, not scoring |
| Peer screening across thousands of issuers | one issuer per call keeps citations honest |
| Options analytics | separate data domain, separate vendor |

> **News itself is no longer out of scope.** It was previously listed here
> because it had no primary-source citation path. The
> [June 2027 window](../roadmap.md#june-2027--05x) defines that path —
> publisher, timestamp and a resolvable reference, with anything that cannot
> be tied to a filing marked uncorroborated.

## Versioning intent

| Version | Scope | Window |
|:---|:---|:---|
| 0.2.x | current: four modules, 19 tools, docs restructure | shipped |
| 0.3.x | valuation models; `calendar.events` from 8-K primary sources | December 2026 |
| 0.4.x | report parsing depth; `price_action` behind the optional extra | March 2027 |
| 0.5.x | news headlines by type; insider transactions | June 2027 |
| 1.0.0 | schema freeze: `api_version` 1 stable, artifact schema stable | after 0.5.x |

See the [product roadmap](../roadmap.md) for the full pipeline and the exit
criteria for each window.

Breaking changes bump the module `api_version`, the relevant version constant
(`SCHEMA_VERSION`, `RULES_VERSION`, `FORMULA_VERSION`, `model_version`) and the
plugin minor version.

## Next

- [Product roadmap](../roadmap.md) — the full feature pipeline
- [Module contracts](02-module-contracts.md)
- [Contributing](10-contributing.md)
