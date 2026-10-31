# 07 — Analysis and DCF

How the 36 metrics are computed, how quality states are decided, and how the
FCFF DCF derives, validates and projects.

## Module shape

```
analysis/
├── domain/
│   ├── metrics.py   declarative catalog: 36 MetricDef entries
│   ├── engine.py    compute_one(series, metric_id, period) → MetricResult
│   └── dcf.py       derive → validate → project → discount → sensitivity
├── service.py       line-item fetch, cache, orchestration
└── tools/           ratio_catalog, ratio_compute, dcf_compute
```

`engine.py` is pure: it receives a `LineItemSeries` and a period, and returns a
result. It never touches SQLite or the network. That is why the metric tests need
no fixtures.

## Metric definitions

```python
@dataclass(frozen=True)
class MetricDef:
    metric_id: str
    label: str
    family: str          # profitability | liquidity | leverage | efficiency
                         # cash_quality | per_share | growth
    formula: str          # human-readable, echoed in results
    line_items: tuple[str, ...]
    unit: str             # ratio | USD | shares | days | percent
    direction: str = "contextual"   # higher_is_better | lower_is_better | contextual
    window: int = 0       # extra periods of history required
    version: int = 1
```

`FORMULA_VERSION = 1` invalidates the metric cache when bumped.

### Catalog

| Family | Metrics |
|:---|:---|
| profitability | `gross_margin`, `operating_margin`, `net_margin`, `roa`, `roe`, `roic`, `fcf_margin`, `dupont_return` |
| liquidity | `current_ratio`, `quick_ratio`, `cash_ratio`, `working_capital` |
| leverage | `debt_to_equity`, `net_debt`, `net_debt_to_ebitda`, `interest_coverage`, `equity_multiplier` |
| efficiency | `asset_turnover`, `inventory_turnover`, `receivables_turnover`, `dso`, `dio`, `dpo`, `cash_conversion_cycle`, `capex_to_revenue` |
| cash_quality | `fcf`, `fcf_per_share`, `cfo_to_net_income`, `accrual_ratio` |
| per_share | `book_value_per_share`, `revenue_per_share` |
| growth | `revenue_cagr` (window 3), `eps_cagr` (3), `fcf_cagr` (3), `equity_growth` (1), `share_dilution` (1) |

### Windows and lookback

Growth metrics need history beyond the requested periods. The service fetches:

```python
lookback = max(definition.window for definition in definitions)
fetched_periods = max(1, min(periods + lookback, 20))
```

so `ratio_compute(symbol, ["revenue_cagr"], periods=3)` requests 6 periods,
computes 4 CAGR points, and returns the 3 requested.

`_growth()` enforces the spacing:

```python
gap_days = abs((current_date - previous_date).days)
if not 330 * window <= gap_days <= 400 * window:
    return "gap"
```

A fiscal-year change (52/53-week calendars) still passes; a missing year does
not.

## Quality states

Every result carries `quality`:

| State | Set when |
|:---|:---|
| `ok` | all inputs present and the result is meaningful |
| `partial` | some components missing (value computed from the rest) |
| `gap` | insufficient history for the window, or a missing period |
| `unavailable` | a required input is absent for this issuer |
| `not_meaningful` | inputs present but the ratio has no interpretation |

Transition rules in `compute_one`:

```python
quality = {"gap": "gap",
           "unavailable": "unavailable",
           "component_unavailable": "partial"}.get(reason, ...)
```

Typical `not_meaningful` cases: negative equity for `roe`, zero denominator,
negative revenue for a margin. The engine sets `value=None` and a `reason`, and
never emits a number that would be misread.

`display` formats the value for humans (`31.5%`, `1.71×`, `$54.8bn`) but the
numeric `value` is authoritative.

## Balance-sheet basis

Instant line items can use two bases:

| Basis | Meaning | Use |
|:---|:---|:---|
| `average` (default) | mean of the fiscal year-end balance and the prior one | flow-over-stock ratios (ROE, ROA, turnover) |
| `ending` | the fiscal year-end balance | point-in-time statements and DCF inputs |

`average` matters for comparability; using an ending balance for ROE overstates
returns when equity is growing.

Annual instants are restricted to the canonical fiscal year-end set (derived from
a revenue-like duration series). Without that filter, `ROW_NUMBER() …
ORDER BY period_end DESC LIMIT 6` returned the six most recent instant dates —
which are quarters — and left balance-sheet items with a single annual period.

## Caching

```python
def _key(self, cik, metric_id, period, basis, version, facts_version) -> str:
    return f"metric:{cik}:{metric_id}:{period}:{basis}:{version}:{facts_version}"
```

| Aspect | Value |
|:---|:---|
| TTL | 24 h |
| Bucket | `metrics` |
| Cap | 64 MB with LRU eviction |
| Invalidated by | new facts (`facts_version`), formula change (`version`), basis |

DCF results are **not** cached: they depend on overrides and must be
reproducible.

## DCF model

### Formula

```
FCFF_t   = EBIT_t × (1 − tax) + D&A_t − capex_t − ΔNWC_t
PV_t     = FCFF_t / (1 + WACC)^t
TV       = FCFF_n × (1 + g) / (WACC − g)          # gordon
TV       = EBITDA_n × exit_multiple               # exit_multiple
EV       = Σ PV_t + PV(TV)
Equity   = EV − net_debt
Per share= Equity / diluted shares
```

`net_debt = total_debt − cash`; `ΔNWC = nwc_pct_revenue × Δrevenue`.

### Assumptions

Derived in this order, then overridden by the caller:

| # | Assumption | Derivation |
|:---:|:---|:---|
| 1 | `revenue_growth` | 3-year revenue CAGR, clipped to range |
| 2 | `operating_margin` | mean EBIT margin over available years |
| 3 | `tax_rate` | `income_tax / pretax_income`, mean |
| 4 | `capex_pct_revenue` | mean capex / revenue |
| 5 | `da_pct_revenue` | mean D&A / revenue |
| 6 | `nwc_pct_revenue` | Δ(current assets − current liabilities) / Δrevenue |
| 7 | `wacc` | **policy default 0.09** |
| 8 | `terminal_growth` | **policy default 0.025** |
| 9 | `shares_diluted` | latest diluted shares |
| 10 | `net_debt` | `total_debt − cash` |

Each entry carries `source` (`user`/`derived`/`default`),
`assumption_quality` (`user_input`/`company_history`/`policy_default`),
`derivation`, `periods_used` and `citation`.

When any assumption is a policy default the result includes the warning
`assumptions_not_company_specific`, and the tool description tells the model to
disclose it.

### Validation

Rates are **decimals** (`0.08` = 8%). `_RANGES` is inclusive:

| Input | Min | Max |
|:---|:---:|:---:|
| `revenue_growth` | −0.10 | 0.25 |
| `operating_margin` | 0.00 | 0.60 |
| `tax_rate` | 0.00 | 0.40 |
| `capex_pct_revenue` | 0.00 | 0.30 |
| `da_pct_revenue` | 0.00 | 0.20 |
| `nwc_pct_revenue` | −0.20 | 0.50 |
| `wacc` | 0.03 | 0.30 |
| `terminal_growth` | −0.02 | 0.04 |

Additional rules:

| Rule | Failure |
|:---|:---|
| `wacc − terminal_growth ≥ 0.01` | `InvalidArgument` |
| `forecast_years` integer 3–15 | `InvalidArgument` |
| `terminal_method ∈ {gordon, exit_multiple}` | `InvalidArgument` |
| `exit_multiple` required and 3–30 for `exit_multiple` | `InvalidArgument` |
| revenue, diluted shares and net debt must exist | `MetricUnavailable` |
| `8` (meaning 8%) rejected | `InvalidArgument` |

Derived values are clipped to their ranges rather than rejected, so an unusual
history still produces a labelled result.

### Projection

```
for t in 1..forecast_years:
    revenue_t = revenue_{t-1} × (1 + growth_t)
    ebit_t    = revenue_t × margin
    nopat_t   = ebit_t × (1 − tax)
    fcff_t    = nopat_t + da_t − capex_t − Δnwc_t
    pv_t      = fcff_t / (1 + wacc)^t
```

`growth` may be a scalar or a per-year list; a list shorter than
`forecast_years` repeats its last value.

### Output

| Block | Fields |
|:---|:---|
| `assumptions[]` | `name`, `value`, `display`, `unit`, `source`, `derivation`, `periods_used`, `assumption_quality`, `citation` |
| `valuation` | `enterprise_value`, `net_debt`, `equity_value`, `shares_diluted`, `value_per_share`, `currency` |
| `terminal` | `method`, `value`, `pv`, `share_of_ev` |
| `forecast[]` | `year`, `period_end`, `revenue`, `ebit`, `taxes`, `nopat`, `da`, `capex`, `delta_nwc`, `fcff`, `discount_factor`, `pv` |
| `sensitivity` | `wacc_values` (±2 pp, 5 steps), `growth_values` (±1 pp, 5 steps), `grid[][]` |
| `warnings[]` | e.g. `assumptions_not_company_specific` |

`assumptions_only=True` returns `valuation=None`, `forecast=[]`, `terminal=None`,
`sensitivity=None` — the same assumption table, no arithmetic.

### Deliberate simplifications

| Simplification | Reason |
|:---|:---|
| Single-stage growth, no fade curve | the model must be explainable in one screen |
| Policy WACC instead of CAPM | no risk-free curve, beta or ERP source exists in scope |
| No mid-year convention | keeps the arithmetic auditable |
| No terminal-value cross-check against multiples (unless requested) | avoids implying a target price |
| Nothing persisted | determinism and no stale valuations |

## Adding or changing a metric

1. Add a `MetricDef` to `domain/metrics.py` (unique id, family, formula,
   line items, unit, direction, window).
2. Implement the branch in `engine.compute_one`. Return `"unavailable"` when a
   line item tuple is empty; return `"gap"` only for history problems.
3. If new line items are needed, add them to `fundamentals/domain/concepts.py`
   first (see [Contributing](10-contributing.md#add-a-line-item)).
4. Bump `FORMULA_VERSION` if an existing metric's arithmetic changes.
5. Add tests: one arithmetic case and one quality-state case in
   `tests/unit/analysis/test_metrics_dcf.py`.

Checklist for a new metric:

| Check | Why |
|:---|:---|
| Denominator can be zero | must return `not_meaningful`, not `inf` |
| Negative equity case | must return `not_meaningful` |
| Instant items | declare `balance_basis` sensitivity in the formula text |
| Window | set it, or the series will be too short |
| Family | `ratio_catalog` filters on it |

## Changing the DCF

| Change | Also update |
|:---|:---|
| New assumption | `DCF_ITEMS` in `service.py`, `_derive()`, the tool signature, `users/03-tools-reference.md` |
| New range | `_RANGES`, this page, the tool docstring |
| New terminal method | `terminal_method` validation, `_terminal()`, output docs |
| Different formula | `model_version`, this page, `dcf-valuation` skill |

The `dcf-valuation` skill tells the model to present assumptions first. If the
output shape changes, update the skill too, or the model will describe fields
that no longer exist.

## Next

- [Reports and parser](06-reports-parser.md)
- [Contributing](10-contributing.md)
