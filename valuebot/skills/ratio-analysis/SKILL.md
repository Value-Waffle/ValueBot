---
name: ratio-analysis
description: Choose and interpret valuebot ratio metrics — use ratio_catalog, respect quality states, cite inputs, and never present unavailable or not_meaningful values as numbers.
---

# Ratio analysis

## Workflow

1. Call `ratio_catalog(symbol)` once. It returns every metric with its formula,
   required line items and per-metric `available` / `missing_line_items`.
2. Select the smallest set of metrics that answers the question. Groups:
   profitability, liquidity, leverage, efficiency, cash_quality, per_share,
   growth.
3. Call `ratio_compute(symbol, metric_ids, periods=N)`.
4. Present values newest-first, with the period and unit.

## Quality states

| Quality | Meaning | How to present |
|:---|:---|:---|
| `ok` | Value is complete | Show the number |
| `partial` | An optional input was missing or a component was unavailable | Show the number and the caveat |
| `unavailable` | A required line item is absent | No number; name the missing line item |
| `not_meaningful` | Zero or negative denominator, negative equity, negative EBITDA, negative earnings | No number; name the reason |
| `gap` | The growth window is not covered by consecutive annual periods | No number; say the history is too short |

Never convert a non-`ok` quality into "roughly zero" or an estimate.

## Interpretation rules

- Ratios are derived, not audited. Cite the input facts from `inputs[]`.
- Compare like periods. Do not compare a 52-week year to a 53-week year without
  saying so.
- `balance_basis` is part of the meaning: `average` and `ending` produce
  different values. State which one was used.
- Growth metrics use annual periods; a `gap` means the required prior period is
  absent, not that growth is zero.
- A ratio that is `not_meaningful` is still a finding: report it as such.

## Output

A compact table: metric, periods, value, quality, inputs used. Then one or two
sentences of interpretation tied to those values. End with a references footer
per the grounded-citation skill.
