---
name: dcf-valuation
description: Run and present valuebot's simple FCFF DCF — assumptions first, policy defaults named, sensitivity shown, and no price target.
---

# DCF valuation

## Workflow

1. Call `dcf_compute(symbol)` with no assumptions.
   - It derives assumptions from annual history, labels each one
     `user`, `derived` or `default`, and returns the valuation.
   - If you want to inspect assumptions before valuing, call with
     `assumptions_only=true`.
2. Present the assumption table before any value:
   - revenue growth, operating margin, tax rate, capex %, D&A %, NWC %;
   - WACC and terminal growth, explicitly marked as policy defaults;
   - base period, forecast years, diluted shares and net debt.
3. If the user supplies an assumption, call again with that value. Rates are
   decimals: 8% is `0.08`.
4. Show the sensitivity range (WACC ±2 points, terminal growth ±1 point)
   alongside the base value.

## Rules

- Never hide the assumptions. A DCF without its assumption table is not a
  citable result.
- Never describe the 9% WACC or 2.5% terminal growth as observed or
  market-derived. They are policy defaults until the user replaces them.
- Never present the output as a price target, a buy/sell signal, or a
  comparison to market price. It is an intrinsic value under stated
  assumptions.
- If the tool returns `unavailable`, name the missing line items. Do not
  supply your own revenue, shares or net debt.
- If `terminal_value_dominates` appears, say that most of the value comes from
  the terminal assumption and show the sensitivity spread.
- Round for readability, but keep enough precision that two assumptions produce
  visibly different values.

## Output

```markdown
**Base period:** FY2025 (2025-09-27)
**Assumptions:** growth 4.4% (derived), margin 31.9% (derived),
tax 15.6% (derived), WACC 9.0% (policy default), terminal growth 2.5% (policy default)
**Value per share:** $90.33 (base case)
**Sensitivity:** $72–$118 across WACC 7–11% and terminal growth 1.5–3.5%

This is an intrinsic-value estimate under the assumptions above, not a price target.
```

Then the references footer per grounded-citation.
