# Roadmap

What valuebot is building, in which order, and what "done" means for each
release. This is the **product** view: which capabilities arrive and when.

For the internals of the two reserved modules — the protocols, the store
layouts, the enabling checklist — see
[dev/09 — Roadmap](dev/09-roadmap.md). That document is the *how*; this one is
the *what and when*.

---

## How the pipeline works

Every capability moves through four stages. Nothing jumps a stage.

```
candidate ──▶ scoped ──▶ building ──▶ shipped
   ▲            │            │            │
   └────────────┴────────────┴────────────┘
        deferred, with a reason recorded
```

| Stage | What it means | Who moves it |
|:---|:---|:---|
| **candidate** | A request, an observation from a filing, a gap someone hit. No design work yet. | Anyone, via [Discussions](https://github.com/valuewaffle/valuebot/discussions) or an issue |
| **scoped** | Accepted into a release window. Has a name, an owner, a home module, and an exit criterion. | Maintainer, at triage |
| **building** | Merged onto a branch, under review, tested against the invariants. | Contributor, via pull request |
| **shipped** | Exit criteria met, documented, released. | Maintainer, at release |

A candidate is **deferred** — rather than dropped — when it does not fit the
current window. Deferred candidates keep their reasoning, so a later window can
pick them up without re-litigating them.

### What every candidate must clear

These are gates, not preferences. A candidate that cannot clear them is
deferred regardless of how often it is asked for.

| Gate | Why it exists |
|:---|:---|
| **A primary source, or a citable path to one** | Every number valuebot emits leaves with a citation. A capability that cannot cite its inputs breaks the product's core promise. |
| **A home module, and no new cross-module edge** | Modules are isolated by the data they own. `analysis → fundamentals` is the only permitted edge today, and adding a second one is a deliberate, expensive decision. |
| **An own store, or a demonstrable reason not to need one** | A module that reads another's tables couples their schemas. |
| **Offline tests** | The suite runs without contacting the SEC. A capability that needs the network to be testable is not testable. |
| **Documented for users, not just developers** | A tool nobody can find is a tool nobody uses. |

Two standing constraints apply to everything below:

> **The DCF stays a DCF.** No capability may turn an intrinsic value into a
> price target, and market prices may not be mixed into a valuation by default.

> **A new tool is not a new responsibility.** Every tool also needs a skill
> that teaches the model when and how to call it, and a persona that has a use
> for it. A tool that ships without both is incomplete.

---

## Release windows

| Window | Version | Focus | Side quest |
|:---|:---|:---|:---|
| **December 2026** | 0.3.x | Skills + tool expansion — **valuation models** | Calendar events |
| **March 2027** | 0.4.x | Skills + tool expansion — **report parsing** | Price and volume skills |
| **June 2027** | 0.5.x | **News** — latest headlines, by type | Insider information |

**Focus** is the theme of the window: the capabilities that define the release.
**Side quests** are the secondary tracks — real work, but a smaller surface,
and the first thing to be cut if a window runs long. A side quest is not
deferred automatically; it is re-scoped at the start of its window.

Version numbers are intent, not a promise. A window that slips moves its
version with it.

---

## December 2026 — 0.3.x

**Theme:** more ways to value a company, and the skills to use them.

### Focus — valuation models

Today `analysis` computes 36 ratio and growth metrics and one valuation model
(a simple FCFF DCF). This window adds further models, and the skills that make
them usable.

| Capability | Description | Home |
|:---|:---|:---|
| **Multi-model DCF** | Run the same DCF under several assumption sets side by side — bear / base / bull — and show which assumption moves the value most. | `analysis` |
| **Sensitivity grid** | Present value across a WACC × terminal-growth grid rather than a single point, with policy defaults marked. | `analysis` |
| **Reverse DCF** | Given a value, solve for the assumption set that produces it — "what growth rate is priced in?". | `analysis` |
| **Valuation skill** | A new skill teaching the model to pick a model, state the assumptions first, label defaults as defaults, and never present a result as a price target. | `skills/` |

**Exit criteria**

- Multi-model and sensitivity results return a comparison the model can render
  as a table, with each cell carrying its citation.
- Every assumption in every output is labelled `user`, `derived` or `default`.
- A `dcf-valuation` skill revision covers scenario comparison and refuses to
  emit a price target.
- Unit tests cover the arithmetic, the label provenance, and the degenerate
  cases (zero growth, negative EBIT, terminal value dominance).
- The new tools appear in `docs/users/03-tools-reference.md` and in the
  analysis analyst persona.

**Depends on:** nothing new. This is entirely inside `analysis`, which already
has the facts it needs.

**Risk:** the temptation to add comparables or multiples-based valuation.
Multiples need a market price, which does not exist yet (see the March 2027
side quest) and which would make this window a price-dependent release. The
focus is deliberately restricted to cash-flow models that stand on filing data
alone.

### Side quest — calendar events

Activates the reserved `calendar` module. Design and enabling checklist are in
[dev/09 — Roadmap](dev/09-roadmap.md#calendar--planned).

| Capability | Description | Home |
|:---|:---|:---|
| `calendar_events` | Upcoming and past corporate events — earnings dates, dividends, splits — derived from 8-K Items 2.02 and 5.03. | `calendar` (new) |

**Exit criteria**

- Events resolve from primary sources through the existing filing index; no
  new external source is introduced.
- `calendar` owns its own store and passes the import-isolation test.
- The module is registered in `server.py` behind a guard, so a failure
  degrades instead of crashing the server.

---

## March 2027 — 0.4.x

**Theme:** read more out of the filings valuebot already has, and the skills
to navigate them.

### Focus — report parsing

`reports` currently returns filing sections, notes, and table grids. This
window deepens the parsing and the navigation.

| Capability | Description | Home |
|:---|:---|:---|
| **Note-level extraction** | Address individual notes within a financial statement section, not only the section as a whole. | `reports` |
| **Multi-year statement tables** | Render a statement table across several fiscal years side by side, with the period for each column. | `reports` |
| **Section-crossing search** | Search across a filing and return the surrounding context, not only the matching fragment. | `reports` |
| **Parsing skill** | Extend `semantic-report-reading` to cover note addressing, multi-year comparison, and context retrieval. | `skills/` |

**Exit criteria**

- Note addressing is stable: the same note resolves to the same ID across
  repeated calls on the same filing.
- Multi-year tables carry the fiscal year for every column, and every cell
  carries its citation.
- A skill revision teaches the model to use the new retrieval shapes without
  over-claiming coverage when the parser degrades.
- Coverage degradation is reported explicitly rather than silently narrowing
  the result.

**Depends on:** `sec-parser` behaviour. Upgrades to the parser are a known
failure domain for this module, and are handled by the module's own tests
rather than by fixes in `analysis`.

**Risk:** over-promising parse coverage. The `reports` module reports
`coverage.degraded` when a filing does not parse cleanly; the new capabilities
must not launder a degraded parse into a confident answer.

### Side quest — price and volume skills

Activates the reserved `price_action` module. Design and enabling checklist
are in [dev/09 — Roadmap](dev/09-roadmap.md#price_action--planned).

| Capability | Description | Home |
|:---|:---|:---|
| `price_history` | Daily OHLCV series over a chosen window. | `price_action` (new) |
| `price_stats` | Return, volatility, drawdown, moving averages over the same window. | `price_action` (new) |
| **Market-data skill** | A new skill teaching the model to read price series, state the as-of date, and never blend a price with a DCF result into a single "fair value" claim. | `skills/` |

**Exit criteria**

- The `price` extra stays optional and stays uninstalled by default; the
  module remains off unless `VW_ENABLE_PRICE=1`.
- The module owns its own store and cache.
- No code path lets a price reach a valuation result implicitly. A price may
  be *requested* alongside a DCF, and the response must present them as
  separate figures with separate citations.

---

## June 2027 — 0.5.x

**Theme:** what happened, not just what was filed.

### Focus — news

The first capability in valuebot's history that is **not** grounded in a
filing. This window defines the citation model that makes it acceptable.

| Capability | Description | Home |
|:---|:---|:---|
| **Headline retrieval** | The latest headlines for an issuer, filterable by type — earnings, M&A, guidance, regulatory, general. | `news` (new) |
| **Headline-to-filing link** | Where a headline corresponds to a filing already in the index, link to the filing and cite the filing. | `news` |
| **News skill** | A new skill teaching the model to attribute every headline to a publisher and a timestamp, to state clearly when a headline is *unconfirmed* by any filing, and to keep a claim and its provenance together. | `skills/` |

**Exit criteria**

- Every headline carries publisher, timestamp, and a resolvable reference.
  A headline without all three is not returned.
- A headline that cannot be linked to a filing is explicitly marked as
  uncorroborated. Uncorroborated is not a lesser kind of true — it is a
  different kind of claim, and the model must say so.
- The module owns its own store and cache, and is registered behind a guard.
- It does not produce sentiment scores, and it does not summarise a filing's
  content.

> **This reverses an earlier position.** The module roadmap previously listed
> news and sentiment scraping as explicitly out of scope, on the grounds that
> it had no primary-source citation path. This window is that path being
> built. The reversal is deliberate: publisher and timestamp attribution is a
> weaker form of grounding than a filing, and it is worth having **provided**
> the model is told which kind of claim it is making. Sentiment scoring
> remains out of scope, and news never becomes a substitute for filing
> evidence.

### Side quest — insider information

| Capability | Description | Home |
|:---|:---|:---|
| **Insider transactions** | Form 4 and Form 5 filings — insider buys, sells, grants, and option exercises — for a company, with filer, role, and transaction detail. | `insider` (new) |

**Exit criteria**

- Insider transactions are read from **SEC filings**, so they carry the same
  primary-source grounding as everything else in valuebot. Form 4/5 is not a
  news story, and it is not market commentary.
- Filings are attributed to the individual filer, with the officer or
  director role as stated in the filing.
- A derived view — net insider activity over a period, cluster buying — is
  clearly separated from the raw filings it is computed from.

---

## Beyond June 2027

Not scheduled. Listed so the shape of the queue is visible, not as a promise.

| Candidate | Notes |
|:---|:---|
| Comparables and multiples-based valuation | Blocked on price data. Multiples also need a peer set, which conflicts with the one-issuer-per-call design. |
| Portfolio accounting | Different data model, different audience. Not a research tool. |
| Streaming quotes | Cost and licensing. Daily granularity is enough for research. |
| Sentiment scoring | Remains out of scope — see the June 2027 note above. |
| Options analytics | Separate data domain, separate vendor. |
| Order execution, brokerage | Not a research tool; regulatory scope. |

---

## Changing this roadmap

The pipeline is open. To propose a capability:

1. **Open a discussion** on the repository, or an issue. Say what you need and
   what you would do with it.
2. **Answer the gates** — how would it be cited, which module owns it, what
   does "done" look like. A proposal that skips these will be asked for them.
3. **Watch the triage.** Candidates are scheduled into a window at triage, and
   the reasoning for deferral is recorded publicly.

Roadmaps change. When a window shifts, this document is updated in the same
pull request as the change that caused it.

---

## See also

- [dev/09 — Roadmap](dev/09-roadmap.md) — module protocols, the enabling
  checklist, and versioning intent
- [dev/10 — Contributing](dev/10-contributing.md) — how to build any of the
  above
- [02 — Configuration](users/02-configuration.md) — the settings these
  capabilities will use
