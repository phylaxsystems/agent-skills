---
name: mapping-invariants
description: "Phylax Credible Layer assertions invariant mapping. Use when starting a protocol to map invariants before writing phylax/credible layer assertions or tests."
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
1. Build the protocol map (assets, roles, entrypoints, state, routers).
2. Classify the dominant protection surface (`vault`, `lending`, `swaps`, `perpetual`, `access_control`, or justified other).
3. Enumerate invariants by category (access control, accounting, pricing, solvency, limits, modes).
4. Rank invariants by impact and likelihood (losses, control-plane, liveness).
5. Drop invariants that only restate an existing `require`, custom error, or modifier.
6. Pick 2-5 high-signal external-state invariants for the first implementation pass.
7. Identify exceptions and acceptable violations.
8. Pick data sources (fork reads, logs, call inputs/outputs, slots, ERC20 deltas).
9. Choose enforcement location (chokepoint vs per-contract).
10. Produce the invariant matrix and trigger map.
11. Hand off to `designing-assertions` -> `implementing-assertions` -> `testing-assertions`.

## Skill Map
- `designing-assertions`: turn the invariant map into triggerable invariants and edge cases.
- `implementing-assertions`: write Solidity assertions and cheatcode logic.
- `testing-assertions`: build PCL/forge tests for assertions.
- `backtesting-assertions`: replay mainnet txs to validate triggers.
- `pcl-assertion-workflow`: set up PCL project, store/submit/deploy.
- `assertion-troubleshooting`: diagnose non-triggering or failing assertions.

## Workflow
- **Protocol map**: read docs/specs/audits/tests; list contracts, assets, roles, and critical entrypoints.
- **Invariant inventory**: express “states that must never occur” and rank by impact.
- **Surface classification**: map each candidate to the closest reusable protection-suite category before inventing a new shape.
- **Guard overlap review**: scan relevant functions for `require`, `revert`, custom errors, modifiers, and library checks; keep properties that observe stronger external state.
- **Spec classification**: split tx-end invariants, action-specific postconditions, flow limits, storage protections, and backtesting candidates.
- **Exception audit**: capture legitimate exceptions (bad debt, emergency modes, timelocks).
- **Observation plan**: decide which values/events you will read to validate each invariant.
- **Trigger plan**: select the narrowest trigger that guarantees coverage.
- **Coverage check**: confirm each invariant is reachable from at least one trigger and entrypoint.
- **Feasibility check**: internal calls are not traced; call inputs are scoped by selector/call id; modified mapping keys must be derived from call inputs, outputs, logs, or explicit storage math.

## Heuristics
- Start with loss‑bearing invariants: solvency, accounting integrity, and upgrade control.
- Prefer cross‑function invariants over per‑function reverts already in code.
- If you cannot observe an invariant reliably, rephrase it to observable signals.
- For lending protocols, classify actions by health‑factor impact and list allowed transitions.
- If an invariant depends on intermediate call frames, plan a V2 `registerFnCallTrigger` assertion with `ph.context()` and `_preCall`/`_postCall` fork ids from the start.
- For rolling-window flow risk, plan built-in cumulative inflow/outflow triggers instead of assertion-authored storage.

## Deliverables
- Invariant matrix (definition, source, exceptions, priority).
- Trigger map (selector/slot/balance mapping).
- Data source list (storage layout, logs, call inputs).
- Guard-overlap notes explaining why selected invariants are stronger than protocol-local checks.
- Test plan (positive/negative, fuzz, backtest candidates).

## Rationalizations to Reject
- “We can skip invariant mapping and write code directly.”
- “We only need owner checks.” (Protocols usually fail on accounting and pricing.)
- “One broad assertion is enough.” (Gas and coverage risks.)
- “We’ll add exceptions later.” (Most false positives come from ignored exceptions.)

## References
- [Invariant Mapping Workflow](references/invariant-mapping-workflow.md)
- [Protocol Example Patterns](references/protocol-examples.md)
- [Lending Protocol Invariant Checklist](references/lending-invariant-checklist.md)
