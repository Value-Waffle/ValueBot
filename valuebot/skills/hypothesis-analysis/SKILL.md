---
name: hypothesis-analysis
description: Structure investment-hypothesis work as hypothesis → claims → evidence → verdict, gather facts before prose, keep responses within caps, and stop after two fruitless calls.
---

# Hypothesis analysis

Use this skill when asked to test, support or refute an investment hypothesis.
The output is a verdict backed only by cited evidence.

## Structure

1. **Hypothesis** — one falsifiable sentence with ticker, metric, direction and
   time window.
2. **Claims** — 2–6 checkable claims; each names the metric, period and
   comparison it needs.
3. **Evidence** — attach tool evidence to each claim with `[n]` markers. Record
   what would falsify the claim.
4. **Verdict** — `SUPPORTED`, `PARTIALLY SUPPORTED`, `REFUTED` or
   `INSUFFICIENT EVIDENCE`, per claim and overall, with counter-evidence named.

Do not write the verdict before the evidence exists. An evidence gap is a
finding.

## Facts before prose — tool order

1. `facts_query` / `facts_timeseries` — the cheapest precise evidence.
2. `statement_get` — normalized statements when several line items are needed.
3. `ratio_compute` — ratios and growth, with inputs and quality states.
4. `dcf_compute` — only when the claim is about intrinsic value; call it
   without assumptions first and present the assumption table.
5. `report_sections` / `report_section` / `report_search` — narrative (MD&A,
   risk factors, notes) only when the claim is qualitative.
6. `report_table` — only when a table carries the detail.

Never call `report_section` to re-derive a number that `facts_query` already
returned. Never read a whole filing when a table answers the claim.

## Size discipline

Treat each tool response and each answer section as an 8 KB budget. Page with
`offset=next_offset` only when the next chunk answers the claim. Request narrow
scopes: one concept, one period range, one section.

## Circuit breaker

After two fruitless calls for the same claim (empty, wrong period, missing
line item), stop. Record `INSUFFICIENT EVIDENCE` with the tools tried and what
was missing. Do not loop over symbol variants, wider periods or alternate
tools. An empty result is not a refutation.

## Answer template

```markdown
**Hypothesis:** …
**Verdict:** PARTIALLY SUPPORTED

| Claim | Evidence | Finding | Verdict |
|---|---|---|---|
| Services growth | facts_query FY2024–FY2025 [1][2] | +12% YoY | SUPPORTED |
| Margin offset | ratio_compute gross_margin [3] | −40 bps | REFUTED |
| FY2026 offset | no FY2026 data | — | INSUFFICIENT EVIDENCE |

**Counter-evidence:** …
---
**References**
1. …
```

Every number in the table carries a marker that resolves in the footer.
