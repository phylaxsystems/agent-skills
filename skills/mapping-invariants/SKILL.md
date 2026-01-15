---
name: mapping-invariants
description: "Intro skill for designing and implementing assertions. Use when starting a new protocol to map invariants before writing assertions or tests."
---

# Mapping Invariants

Start here before designing or implementing assertions. This skill defines the invariant‑mapping workflow and hands off to the other skills.

## When to Use
- Starting a new protocol assertion effort.
- You need a structured method to discover invariants.
- You want the step‑by‑step path before `designing-assertions` and `implementing-assertions`.

## When NOT to Use
- You already have a vetted invariant list.
- You only need implementation details. Use `implementing-assertions`.
- You only need testing guidance. Use `testing-assertions`.

## Quick Start
1. Build the protocol map (assets, roles, entrypoints, state).
2. Enumerate invariants by category (access control, accounting, pricing, solvency, limits, modes).
3. Identify exceptions and acceptable violations.
4. Pick data sources (state, logs, call inputs, slots).
5. Choose enforcement location (chokepoint vs per‑contract).
6. Produce the invariant matrix and trigger map.
7. Hand off to `designing-assertions` → `implementing-assertions` → `testing-assertions`.

## Workflow
- **Protocol map**: read docs/specs/audits; list contracts, assets, roles, and critical entrypoints.
- **Invariant inventory**: express “states that must never occur” and rank by impact.
- **Exception audit**: capture legitimate exceptions (bad debt, emergency modes, timelocks).
- **Observation plan**: decide which values/events you will read to validate each invariant.
- **Trigger plan**: select the narrowest trigger that guarantees coverage.
- **Coverage check**: confirm each invariant is reachable from at least one trigger.

## Deliverables
- Invariant matrix (definition, source, exceptions, priority).
- Trigger map (selector/slot/balance mapping).
- Data source list (storage layout, logs, call inputs).
- Test plan (positive/negative, fuzz, backtest candidates).

## Rationalizations to Reject
- “We can skip invariant mapping and write code directly.”
- “We only need owner checks.” (Protocols usually fail on accounting and pricing.)
- “One broad assertion is enough.” (Gas and coverage risks.)

## References
- [Invariant Mapping Workflow](references/invariant-mapping-workflow.md)
- [Protocol Example Patterns](references/protocol-examples.md)
