## What this changes

<!-- One or two sentences. What is different after this pull request? -->

Closes #

## Type

- [ ] Bug fix
- [ ] New tool
- [ ] New metric or line item
- [ ] New module
- [ ] Documentation
- [ ] Tests only
- [ ] Build, dependency, or CI

## Checklist

### Correctness

- [ ] Numbers trace to a cited line item
- [ ] `quality` states are handled — `gap`, `unavailable`, `not_meaningful`
- [ ] Division by zero and negative-equity cases are covered
- [ ] Period matching uses `period_end`, not `fiscal_year`

### Boundaries

- [ ] No new cross-module import without a documented protocol
- [ ] No SQL or file path crosses a module boundary
- [ ] A new module is guarded in `server.py`
- [ ] The import-isolation test in `tests/contract/test_isolation.py` is extended

### Interface

- [ ] The tool docstring includes argument ranges
- [ ] Arguments are clamped server-side
- [ ] The response respects the byte cap and pages
- [ ] Errors are typed and carry a `hint`

### Operations

- [ ] `.venv/bin/python -m pytest tests -q` passes
- [ ] The offline suite still does not contact the SEC
- [ ] A new dependency is pinned in both `mcp/pyproject.toml` and `requirements.txt`, and added to `THIRD-PARTY-NOTICES.md`
- [ ] No new mandatory configuration — `${PLUGIN_DATA}` stays the only writable root

### Documentation

- [ ] New tools are in `docs/users/03-tools-reference.md`
- [ ] New error codes are in the error table
- [ ] New configuration is in `docs/users/02-configuration.md`
- [ ] A new skill has a `description` that states its trigger

## Review notes

<!--
Anything a reviewer should know: the approach, the trade-offs, what you tried,
what you deliberately did not do, and where you are unsure.
-->
