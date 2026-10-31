> **Example only** — a real SKILL.md for Playwright testing. Copy to `.github/skills/run-playwright-tests/SKILL.md` to use.

```markdown
---
name: run-playwright-tests
description: 'Run Playwright end-to-end tests with screenshots and trace viewer. Use when: testing UI, debugging frontend, capturing screenshots, verifying page behavior.'
user-invocable: true
---

# Playwright E2E Testing

Run Playwright end-to-end tests, capture screenshots, and open the trace viewer.

## When to Use
- Verifying frontend behavior after changes
- Debugging flaky UI tests
- Capturing visual evidence of page state
- Cross-browser validation

## Prerequisites
- Playwright installed: `npx playwright install`
- Test server running locally

## Procedure
1. **Start dev server** — `npm run dev` (background).
2. **Run tests with trace** — `npx playwright test --trace on`
3. **View report** — `npx playwright show-report`
4. **Open trace viewer** — `npx playwright show-trace test-results/**/trace.zip`

## Scripts
- [run-tests.sh](./scripts/run-tests.sh) — starts server, runs tests, stops server

## Troubleshooting
- **Browser not found**: Run `npx playwright install chromium`
- **Tests timing out**: Increase `timeout` in `playwright.config.ts`
- **Screenshots differ**: Update snapshots with `--update-snapshots`
```
