# Contributing to valuebot

Thanks for considering a contribution. valuebot is a financial-research tool
whose whole value proposition is that **every number it emits can be traced
back to a filing**. A change that breaks that promise is worse than no change
at all.

This document is the map. The rules themselves live in
[docs/dev/10-contributing.md](valuebot/docs/dev/10-contributing.md).

---

## The short version

| I want to… | Start here |
|:---|:---|
| Report a bug | [Issue tracker](https://github.com/valuewaffle/valuebot/issues) → *Bug report* |
| Ask a question | [Discussions](https://github.com/valuewaffle/valuebot/discussions) |
| Propose a feature | [Discussions](https://github.com/valuewaffle/valuebot/discussions), then read the [roadmap](valuebot/docs/roadmap.md) |
| Fix a bug or add a tool | [Development setup](valuebot/docs/dev/04-development-setup.md) |
| Add a metric, a line item, or a module | [Contributing guide](valuebot/docs/dev/10-contributing.md) |
| Report a security issue | [SECURITY.md](SECURITY.md) — **not** a public issue |

---

## Before you write code

**Read the invariants.** They are not style preferences; a reviewer will check
each one.

1. **A module owns its data end to end** — its own source adapter, store,
   schema, and cache. No reading another module's tables or files.
2. **Cross-module access goes through a protocol** — never SQL, never a file
   path. `analysis → fundamentals` is currently the only edge.
3. **Every number leaves with a citation** — accession, form, filing date and
   period, or an explicit note that no citation is possible.
4. **Failures are typed** — a `ValuebotError` subclass with a code and a
   hint. No stack trace ever reaches the model.
5. **stdout is the JSON-RPC channel** — no `print` anywhere under `mcp/`.
   Logging goes to stderr.
6. **Responses are byte-capped and pageable** — tools page with
   `offset`/`next_offset` rather than returning unbounded payloads.

**Check the roadmap first.** If your change lands in a capability that is
already scoped, the review is much faster. See
[docs/roadmap.md](valuebot/docs/roadmap.md) for what is planned and when, and
[dev/09 — Roadmap](valuebot/docs/dev/09-roadmap.md) for the module-level
detail.

**Discuss substantial changes first.** A new module, a new cross-module edge,
a new dependency, or a change to the citation contract all need a design
conversation before a pull request. Open a discussion — it is cheaper than a
rejected PR.

---

## Setting up

```bash
git clone https://github.com/valuewaffle/librechat-plugin.git
cd librechat-plugin/valuebot

./bootstrap.sh                       # creates .venv, installs dependencies
.venv/bin/python -m pytest tests -q  # 76 passed
```

| Requirement | Version | Why |
|:---|:---|:---|
| Python | 3.11–3.13, **3.12 recommended** | 3.14 cannot import `edgartools` or `sec-parser` |
| `uv` or `venv` + `pip` | — | environment and dependency management |
| `uv` inside the LibreChat container | — | only needed for an end-to-end plugin test |

`bootstrap.sh` never writes into `mcp/`; the virtualenv lives at
`valuebot/.venv`. Use `--with-price` to add the optional price extras, and
`--dry-run` to see what it would do.

Full detail: [Development setup](valuebot/docs/dev/04-development-setup.md).

---

## Running the tests

```bash
.venv/bin/python -m pytest tests -q          # everything, offline
.venv/bin/python -m pytest tests/unit -q      # one layer
.venv/bin/python -m pytest tests/contract -q  # architectural contracts
.venv/bin/python -m pytest tests/integration -q
```

The default suite is **offline** — it never contacts the SEC. Live tests are
opt-in and need a real User-Agent:

```bash
SEC_USER_AGENT="you@example.com" .venv/bin/python -m pytest tests -q -k live
```

Every change needs a test. A new tool needs a test for its happy path *and* for
at least one failure path. New behaviour that does not fit the existing
fixture tree should be covered by a unit test with a synthetic fixture.

Testing guide: [dev/05 — Testing](valuebot/docs/dev/05-testing.md).

---

## Style

The codebase is plain and deliberate. Match what is already there.

| Area | Convention |
|:---|:---|
| Imports | stdlib, then `core`, then local. Heavy libraries are imported lazily inside functions. |
| Types | `from __future__ import annotations`; dataclasses are frozen |
| Errors | `ValuebotError` subclasses only — never `SystemExit`, never a bare `Exception` |
| Logging | `logging` to stderr. No `print` under `mcp/`. |
| SQL | Parameterised only. Never interpolate a value into a query string. |
| Paths | `pathlib`, resolved, and checked against the allowed root. |
| Comments | Only where the code cannot say it. No narration. |
| Docstrings | Tool docstrings are **prompts the model reads**. State what the tool does and the valid ranges of its arguments. |
| Naming | Modules are `snake_case` packages; tools are `verb_noun`; metric ids are domain nouns (`roe`, `net_debt_to_ebitda`); section ids are derived, never hand-written. |

---

## Submitting a pull request

1. **Branch** from `main` with a descriptive name: `feat/valuation-models`,
   `fix/identity-json-permissions`, `docs/skill-example`.
2. **Make the change**, with tests, in one focused commit series. A pull
   request that does three unrelated things is three pull requests.
3. **Run the suite.** It must be green before review, not after.
4. **Update the docs** in the same pull request. A new tool needs an entry in
   [03 — Tools reference](valuebot/docs/users/03-tools-reference.md); a new
   error code needs a row in its error table; a new configuration value needs
   a row in [02 — Configuration](valuebot/docs/users/02-configuration.md).
5. **Open the pull request** and fill in the template.

### What a reviewer checks

**Correctness**

- [ ] Numbers trace to a cited line item
- [ ] `quality` states are handled — `gap`, `unavailable`, `not_meaningful`
- [ ] Division by zero and negative-equity cases are covered
- [ ] Period matching uses `period_end`, not `fiscal_year`
- [ ] Instant series use the canonical fiscal-year-end set

**Boundaries**

- [ ] No new cross-module import without a documented protocol
- [ ] No SQL or file path crosses a module boundary
- [ ] A new module is guarded in `server.py`
- [ ] The import-isolation test is extended

**Interface**

- [ ] The tool docstring includes argument ranges
- [ ] Arguments are clamped server-side
- [ ] Integer arguments are bounded
- [ ] The response respects the byte cap and pages
- [ ] Errors are typed and carry a `hint`

**Operations**

- [ ] The offline test suite passes
- [ ] A new dependency is justified, pinned, and license-compatible
- [ ] No new mandatory configuration — `${PLUGIN_DATA}` stays the only writable
      root

---

## Commit messages

Prefix the subject with the module or area that changed:

```
reports: index filings from the SEC submissions JSON

Cold Company.get_filings() took ~480 s; one submissions request returns the
full history in under a second and is cached for 12 h.

- sources/edgar_source.py: submissions index, requests HTML with edgartools fallback
- store/filings_store.py: latest() helper
- requirements: requests>=2.31
- docs: submissions path in user and dev guides
```

| Prefix | Use for |
|:---|:---|
| `fundamentals:` | XBRL facts, company identity, statements |
| `analysis:` | Metrics, ratios, DCF |
| `reports:` | Filing index, parsing, semantics |
| `thesis:` | The read-only vault |
| `core:` | Config, identity, models, errors, citations, cache |
| `setup:` | `setup.sh`, the identity flow, packaging |
| `docs:` | Documentation only |
| `tests:` | Test suite only |

The subject line is one line, lowercase, no trailing period. Explain *why* in
the body when the reason is not obvious from the diff — especially for a change
to a data path, a rate limit, or a parsing heuristic.

---

## Adding a dependency

New dependencies need a clear justification, and they carry licensing
obligations.

- Prefer the standard library. A dependency that saves thirty lines is rarely
  worth it.
- Pin a range in **both** `mcp/pyproject.toml` and `requirements.txt`.
- Check the license is compatible with valuebot's MIT license, and add it to
  [THIRD-PARTY-NOTICES.md](valuebot/THIRD-PARTY-NOTICES.md) with its version
  and project URL.
- Prefer an **optional extra** for anything only one module needs. `yfinance`
  and `tzdata` are the pattern: installed only with `--with-price`, and the
  module stays off unless `VW_ENABLE_PRICE=1`.

---

## Code of conduct

Everyone participating in this project is expected to follow the
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are agreeing to
abide by it.

---

## License

valuebot is MIT licensed — see [LICENSE](LICENSE). By contributing, you agree
that your contributions are licensed under the same terms. You keep the
copyright in your name; you grant us the right to use and redistribute the
work as part of the project.
