---
name: forge-reasoning
description: 'Solve a problem by externalising structured reasoning into Thought Forge: classify the problem, enumerate questions, form one or more hypotheses per question, validate each with evidence, and assign an LLM-calibrated confidence score to every hypothesis and piece of evidence. Use when: answering a puzzle or reasoning exercise, working a multi-step problem, comparing hypotheses, or when a task explicitly asks you to "think step by step" and record that thinking.'
user-invocable: false
disable-model-invocation: false
---

# Forge Reasoning — Hypothesis-Test-and-Score

A discipline for using Thought Forge to solve a problem **and** make your
confidence explicit at every step. The confidence on each thought is a number
**you** assign (0.0–1.0) — it is *your calibrated belief*, never a default and
never derived mechanically from a state label.

## When to Use
- A prompt asks you to answer a question that requires reasoning, not just recall.
- The problem can be split into sub-questions.
- You must weigh competing explanations and show *why* you believe one.
- You are being evaluated on how you think, not just your final answer.

## The Four-Stage Procedure

Run this loop in Thought Forge, one typed entry at a time. Record **every**
stage — the goal is a complete, inspectable reasoning trail.

### Stage 1 — Classify the problem
1. Start a thread: `forge_start_thread(title="<short problem name>", description="<the prompt, verbatim or condensed>")`. This captures the task as a `prompt` entry.
2. Classify the problem type in one `note` (or as a `question`): is it a
   probability puzzle, a logical fallacy, a causal claim, a decision under
   uncertainty, a debugging trail? Naming the type primes which pitfalls to
   watch for.

### Stage 2 — Enumerate the questions
3. Break the problem into the sub-questions that must be answered. Create one
   `question` entry per sub-question (`forge_think(thread_id, "question", ...)`),
   each `parent_id`-linked to the prompt or to the note that motivated it.
4. If you find yourself with only one big question, split it again — a problem
   worth forging usually decomposes into 2–4 questions.

### Stage 3 — Hypothesise per question (one or more)
5. For **each** question, write **one or more** competing `hypothesis` entries.
   - Multiple hypotheses per question is the norm, not the exception. If you
     can only think of one, force a second "what else could explain it?".
   - Each hypothesis must be **testable and falsifiable** — it must be clear
     what evidence would confirm it and what would kill it.
   - Assign each hypothesis a **confidence** at creation time — your prior
     belief before evidence: `forge_think(..., entry_type="hypothesis", confidence=0.4)`.
     A speculative prior is `0.2–0.4`; a strong prior is `0.6–0.8`. Never
     leave it at the default.

### Stage 4 — Validate with evidence and re-score
6. For each hypothesis, gather evidence **both ways**:
   - `forge_add_evidence(hyp_id, "for", "…", confidence=0.8)` for supporting data.
   - `forge_add_evidence(hyp_id, "against", "…", confidence=0.7)` for contradicting data.
   - Falsification is mandatory: a hypothesis with no `evidence_against` is
     unvalidated, not strong.
7. Assign each piece of evidence its own **confidence** (how much you trust
   that datum), independent of the hypothesis.
8. **Re-score the hypothesis** after weighing evidence. Update its state and
   confidence together:
   - strong support → `forge_update_state(hyp_id, "confirmed")` and raise its confidence toward `0.85–0.95`.
   - contradicted → `forge_update_state(hyp_id, "invalidated")` and drop confidence to `0.05–0.20`.
   - ambiguous → `"inconclusive"` and keep confidence near `0.5`.
   The state says *what happened*; the confidence says *how much you believe it*.
9. Optionally record a `conclusion` that names the surviving hypothesis and its
   final confidence, then `forge_resolve_thread(...)`.

## How to Assign Confidence (the scoring rubric)

Confidence is **your** calibrated judgment of a claim's truth, on `[0.0, 1.0]`.
It is *not* the entry's state, and it is *not* a lookup table.

| Confidence | Meaning | When to use |
|---|---|---|
| `0.0 – 0.2` | Very likely false | A falsified hypothesis, a contradicted observation |
| `0.3 – 0.5` | Toss-up / uncertain | A speculative prior, an untested hypothesis |
| `0.6 – 0.8` | Likely true | Supported by one strong line of evidence |
| `0.9 – 1.0` | Near-certain | Confirmed by multiple independent lines |

Rules:
- **Every hypothesis and every piece of evidence gets a number you choose.**
  Do not copy a neighbour's value; do not leave the default `0.5` because you
  are unsure — `0.5` *means* unsure, so use it only when genuinely torn.
- **Update confidence when evidence arrives.** A hypothesis's confidence should
  move between Stage 3 (prior) and Stage 4 (posterior). Static confidence is a
  sign you are not actually weighing the evidence.
- **Confidence and state must be consistent.** A `confirmed` hypothesis at
  `0.2` or an `invalidated` one at `0.9` is a bug — fix one or the other.

## Tools
- `forge_start_thread` · `forge_think` · `forge_add_evidence` ·
  `forge_update_state` · `forge_list_states` · `forge_resolve_thread` ·
  `forge_render_mermaid` (inspect) · `python -m hippo.visual` (interactive).

## References
- Typed-thought taxonomy and per-type state machines:
  `.github/skills/thought-forge/SKILL.md`
- Design: `architecture/design-docs/thought-forge-design.md`
