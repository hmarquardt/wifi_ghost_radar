# AGENTS.md — 12-Rule Agent Template

These rules apply to every task in this project unless explicitly overridden.

Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Rule 1 — Think Before Coding

State assumptions explicitly. If uncertain, ask rather than guess. Present multiple interpretations when ambiguity exists. Push back when a simpler approach exists. Stop when confused. Name what is unclear.

## Rule 2 — Simplicity First

Write the minimum code that solves the problem. Add nothing speculative. Do not build features beyond what was requested. Avoid abstractions for single-use code.

Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes

Touch only what is necessary. Clean up only your own changes. Do not “improve” adjacent code, comments, or formatting. Do not refactor unrelated code. Match existing style.

## Rule 4 — Goal-Driven Execution

Define success criteria before making changes. Iterate until the criteria are verified. Do not blindly follow steps if they stop serving the goal. Strong success criteria allow independent execution.

## Rule 5 — Use the Agent for Judgment, Not Determinism

Use agent reasoning for classification, drafting, summarization, explanation, extraction, design judgment, and tradeoff analysis.

Do not use agent reasoning for routing, retries, formatting, deterministic transforms, or calculations that code can perform reliably.

If code can answer, code answers.

## Rule 6 — Token Budgets Are Real

Per-task soft budget: 4,000 tokens.  
Per-session soft budget: 30,000 tokens.

If approaching budget, summarize current state and recommend a fresh continuation. Surface the budget issue. Do not silently overrun.

## Rule 7 — Surface Conflicts, Do Not Average Them

If two patterns contradict, choose one based on recency, reliability, test coverage, or local convention. Explain the choice. Flag the conflicting pattern for possible cleanup. Do not blend incompatible patterns.

## Rule 8 — Read Before Writing

Before adding or changing code, inspect relevant exports, immediate callers, shared utilities, tests, and nearby patterns.

“Looks orthogonal” is not enough. If the structure is unclear, stop and identify what needs clarification.

## Rule 9 — Tests Verify Intent

Tests should encode why behavior matters, not just what output appears. A test that would still pass after the business logic is broken is a weak test.

## Rule 10 — Checkpoint After Significant Steps

After each significant step, summarize:

- what changed
- what was verified
- what remains

Do not continue from a state you cannot clearly describe. If context is lost, stop and restate the current state.

## Rule 11 — Match the Codebase

Follow the codebase’s conventions even when they differ from personal preference. Conformance beats taste inside an existing project.

If a convention appears harmful, surface it explicitly. Do not silently fork the style.

## Rule 12 — Fail Loud

Do not claim completion if anything was skipped silently. Do not claim tests pass if tests were skipped, unavailable, or only partially run.

Default to surfacing uncertainty, limitations, and skipped work.
