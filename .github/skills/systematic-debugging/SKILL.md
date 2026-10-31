---
name: systematic-debugging
description: 'Debug issues systematically using a four-stage process: Issue, Bug, Evidence, Fix. Use when: debugging, troubleshooting, fixing bugs, investigating failures, resolving errors, diagnosing problems.'
user-invocable: true
---

# Systematic Debugging

## When to Use
- Debugging a failing test, error, or crash
- Investigating unexpected behavior or wrong output
- Fixing a bug reported by a user, linter, or CI pipeline
- Troubleshooting runtime, logic, or integration issues
- Any task where you need to find *and fix* a root cause

## What It Does
Guides you through a structured four-stage debugging process that separates symptom analysis from root cause investigation, ensures claims are backed by evidence, and produces safe fixes that don't introduce regressions.

## Procedure

Follow these four stages **in order**. Do not skip or reorder them — each stage builds on the previous one.

---

### Stage 1: Issue — Identify the Symptom

**Goal**: Clearly describe what is *observed* to be wrong.

1. **Reproduce** — Run the failing code or test to confirm the symptom.
2. **Describe the symptom** — State the exact error message, wrong output, or unexpected behavior. Use concrete facts (traceback text, assertion output, screenshot description).
3. **Define correct behavior** — State what *should* happen instead. This gives the fix a clear target.
4. **Scope the issue** — Is it consistent or intermittent? One environment or all? One input or many?

**Output**: A one- or two-sentence problem statement starting with "The issue is that..."

---

### Stage 2: Bug — Find the Root Cause

**Goal**: Identify the specific defect in the code that causes the symptom.

1. **Trace the execution path** — Follow the data flow from where the symptom appears back to where the wrong value or state originates.
2. **Narrow the location** — Use binary search (comment out / toggle code paths), logging, or a debugger to pinpoint the exact line or expression.
3. **State the root cause** — Identify *what* is wrong (wrong variable, missing check, incorrect logic, off-by-one, race condition, etc.) and *where* it is (file + line).
4. **DO NOT propose a fix yet** — The fix comes in Stage 4. Stay focused on diagnosis.

**Output**: A statement of the form "The root cause is in `file:line` — [description of the defect]."

---

### Stage 3: Evidence — Validate the Hypothesis

**Goal**: Verify that the identified root cause actually produces the symptom, and rule out alternative explanations.

1. **Gather supporting evidence** — Use one or more of:
   - **Logging**: Add temporary print/log statements to observe intermediate values.
   - **Debugger**: Step through the code, inspect variables at the suspect location.
   - **Unit test**: Write or run a minimal test that isolates the suspected code path.
   - **Diff**: Compare the suspect code against a known-good version (e.g., `git diff`, previous commit).
   - **Assertions**: Add temporary `assert` statements to validate assumptions.
2. **Confirm the causal link** — Show that changing the suspected value or condition changes the symptom.
3. **Check for secondary causes** — Does the same root cause explain all facets of the symptom? Are there other defects in the same area?
4. **Clean up temporary diagnostics** — Remove any debug prints, temporary assertions, or logging added only for evidence gathering.
5. **If the evidence is inconclusive**, return to Stage 2 and re-analyze the root cause.

**Output**: "Evidence confirms the root cause because [reason]. Alternative explanations [ruled in / ruled out]."

---

### Stage 4: Fix — Apply the Solution Safely

**Goal**: Implement a minimal, correct fix that resolves the root cause without breaking existing behavior.

1. **Design the fix** — Determine the smallest change that corrects the defect. Consider:
   - Edge cases (empty inputs, boundary values, null/none, type mismatches)
   - Impact on callers and dependent code
   - Whether the same pattern exists elsewhere (fix it all, or leave a TODO)
2. **Implement** — Apply the change.
3. **Verify the fix** — Re-run the reproduction case from Stage 1. Confirm the symptom is gone.
4. **Regression check** — Run existing tests (`pytest`, `npm test`, etc.) or a relevant subset to confirm no breakage.
5. **Handle side effects** — If the fix reveals other issues or requires updating docs/types/tests, do that now.

**Output**: "Fix applied at `file:line`. Symptom resolved. All [N] existing tests pass."

---

## Quality Criteria

A complete debugging cycle must satisfy all of the following:

- [ ] Symptom is reproduced and clearly described (Stage 1)
- [ ] Root cause is identified at a specific location (Stage 2)
- [ ] Evidence confirms that the root cause → symptom link is real (Stage 3)
- [ ] Fix is minimal, correct, and passes existing tests (Stage 4)
- [ ] Temporary diagnostics are removed from the codebase
- [ ] The problem statement and fix are documented (commit message, PR description, or inline comment)

## Troubleshooting

| Pitfall | How to Avoid |
|---------|-------------|
| **Jumping to a fix before finding the root cause** | Force yourself to complete Stage 2 and Stage 3 before writing any fix code. |
| **Incomplete evidence** | If you can't explain *why* the root cause leads to the symptom, gather more data. |
| **Fix breaks other tests** | Always run the full test suite in Stage 4. If something fails, loop back to Stage 2. |
| **Symptom disappears but root cause is still present** | This means the fix was incidental. Revert and re-analyze. |
| **Multiple root causes** | Fix one at a time. After each fix, re-verify the symptom. |
