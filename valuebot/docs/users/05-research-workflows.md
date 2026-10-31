# 05 — Research workflows

Proven sequences for common research tasks. Each one names the tools the model
should reach for and what a good answer looks like.

## Ground rules

1. **Resolve first.** Unknown ticker → `symbol_resolve`, never guess.
2. **Facts before prose.** Numbers come from tools, then the narrative.
3. **Every number has a citation.** A claim without one is dropped, not
   softened.
4. **Quality states are part of the answer.** `gap`, `unavailable` and
   `not_meaningful` are reported, not estimated around.
5. **Two fruitless calls is a stop.** If two attempts return nothing useful, say
   what is missing.

---

## 1. Quick company screen (3–5 calls)

**Ask:**

> Screen AAPL on profitability, leverage and growth for the last four fiscal
> years. Cite every number and flag anything not `ok`.

**Flow:**

```
company_profile           identity, fiscal year end, data availability
ratio_compute             roe, net_margin, operating_margin,
                          net_debt_to_ebitda, revenue_cagr, fcf_margin
facts_timeseries          only for a series the ratios do not expose
```

**Good answer:** a compact table of values by fiscal year, each row carrying an
accession, plus one short paragraph on direction and one on quality states.

**Watch for:** `roe` with negative equity → `not_meaningful`. That is a finding,
not a gap.

---

## 2. Earnings-quality review

**Ask:**

> Is Apple's reported earnings backed by cash? Compare net income, operating
> cash flow and accruals for four years.

**Flow:**

```
ratio_compute       cfo_to_net_income, accrual_ratio, fcf, fcf_margin
statement_get       cashflow (basis: company, periods: 4)
facts_query         NetIncomeLoss, NetCashProvidedByUsedInOperatingActivities
```

**Good answer:** a two-part table (earnings vs cash, then accruals as a share of
assets) and a verdict tied to the trend, not to a single year.

**Watch for:** a `gap` in `accrual_ratio` usually means total assets for an older
period is missing — check `facts_timeseries` before declaring a conclusion.

---

## 3. Filing deep dive

**Ask:**

> What did Apple say about Services margin in the latest 10-K? Quote the passage
> and show any related table.

**Flow:**

```
filing_list          forms: ["10-K"], limit: 3
report_sections      accession, include_tables: true
report_search        query: "Services gross margin"
report_section       the section_id returned above
report_table         the table_id returned above
```

**Good answer:** the section ID and title, a short verbatim quote, and — if a
table exists — the rendered grid with the caption. Every claim cites the
accession and section.

**Watch for:** `coverage.degraded: true`. It means expected items or notes were
not located; say so and, if needed, search for the passage instead of asserting
absence.

**Cost tip:** `report_search` first. Paging a 40k-character Item 7 to find one
paragraph wastes the budget.

---

## 4. DCF valuation, assumptions first

**Ask:**

> Value AAPL with a simple DCF. Show your assumptions before the result and tell
> me which ones are policy defaults.

**Flow:**

```
dcf_compute    assumptions_only: true          → assumption table
   (present it, ask the user to confirm or override)
dcf_compute    with confirmed overrides        → valuation + sensitivity
```

**Good answer:**

1. The assumption table with `value`, `source` (`user`/`derived`/`default`) and
   `assumption_quality`.
2. An explicit statement that WACC (9%) and terminal growth (2.5%) are policy
   defaults, not market observations — and the `assumptions_not_company_specific`
   warning.
3. Valuation: enterprise value, net debt, equity value, value per share.
4. Sensitivity: how value per share moves across WACC and growth.
5. The sentence "this is intrinsic value under these assumptions, not a price
   target."

**Watch for:** a model that skips straight to a share price. That violates the
`dcf-valuation` skill; re-ask with "assumptions only first".

Typical result on AAPL (verified): revenue growth 1.81%, operating margin
31.5%, tax rate 15.6%, capex 2.86% of revenue, D&A 2.93%, ΔNWC −4.25%, WACC 9%
(default), terminal growth 2.5% (default), diluted shares 15.0bn, net debt
$54.8bn.

---

## 5. Thesis test

**Ask:**

> Read my AAPL thesis, list its claims, and test each one against the data.

**Flow:**

```
thesis_read           front matter, body, attachments
ratio_compute         the metrics each claim depends on
dcf_compute           assumptions_only: true  (if a claim implies value)
report_section        the filing passage behind any qualitative claim
```

**Good answer:** a claim table — claim, evidence, verdict (`supported`,
`contradicted`, `unverifiable`) — and a closing list of what would change the
verdict.

**Watch for:** an empty vault is normal. `thesis_read` returns `ok: true` with
`has_thesis: false`; ask the user for their notes instead of inventing them.

---

## 6. Citation audit

Run this before publishing anything.

**Ask:**

> Audit the previous answer: does every number resolve to a tool citation? List
> any claim without one.

**Flow:** the auditor agent re-calls the specific tools used (`facts_query`,
`ratio_compute`, `dcf_compute`, `report_section`) and compares values.

**Good answer:** a table of claim → citation → verified (yes/no), plus a list of
dropped claims.

**Common failures:**

| Failure | Fix |
|:---|:---|
| Market cap or share price quoted | out of scope — no price data exists |
| A ratio shown as a number although `quality != "ok"` | quote the state instead |
| DCF assumption with no `source` | re-run and show the table |
| Filing quote with no accession or section | re-read with `report_section` |

---

## 7. Comparing two companies

valuebot is single-issuer per call, so compare by running the same tool twice.

**Ask:**

> Compare AAPL and MSFT on gross margin, operating margin, ROE and revenue CAGR
> for the last three fiscal years.

**Flow:** two `ratio_compute` calls with identical `metric_ids`.

**Watch for:** different fiscal year ends. Align on `period_end`, not on labels,
and say so in the answer.

---

## 8. When the data is not there

| Situation | Correct behaviour |
|:---|:---|
| Ticker not in SEC | `symbol_resolve` returns no match → say so |
| Metric `gap` | report the window limitation |
| No 10-K parsed | `filing_not_found` → fall back to `facts_*` |
| `coverage.degraded` | quote what was found, state what was not |
| `edgar_rate_limited` | wait `retry_after_s`, then retry once |
| `identity_not_configured` | operator action: run `setup.sh` |

Never fill a gap with an estimate, an external website, or memory.

## Next

- [Tools reference](03-tools-reference.md) — argument details
- [Troubleshooting and FAQ](08-troubleshooting-and-faq.md)
