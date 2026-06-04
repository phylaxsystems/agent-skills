---
name: designing-assertions
description: "Phylax Credible Layer assertions design. Designs high-signal invariants, classifies protocol protection surfaces, and maps them to V2 triggers before implementation."
---

# Designing Assertions

Design high-signal invariants and map them to precise triggers before writing any Solidity.

## When to Use
- Starting a new assertion suite for a protocol or contract.
- Turning protocol rules into enforceable pre/post invariants.
- Choosing between tx-end, function-call, ERC20-change, cumulative-flow, or storage triggers.

## When NOT to Use
- You need to discover invariants from scratch. Use `mapping-invariants`.
- You only need cheatcode syntax or implementation details. Use `implementing-assertions`.
- You only need test harness patterns. Use `testing-assertions`.
- You are doing a general security review without writing assertions.

## Quick Start
1. Identify assets, roles, and trust boundaries.
2. Classify the protocol surface: `vault`, `lending`, `swaps`, `perpetual`, `access_control`, or a clearly justified new category.
3. List state transitions that can violate external-state safety properties.
4. Scan relevant protocol functions for `require`, custom errors, modifiers, and downstream checks.
5. Prefer invariants stronger than local guards: custody versus accounting, fork-to-fork deltas, oracle bounds, health/risk post-state, protected slots/balances, or cumulative flows.
6. Select data sources: fork reads, logs, call inputs/outputs, ERC20 deltas, or storage slots.
7. Choose minimal V2 triggers that cover all violating paths.
8. Write a short spec card for each selected invariant before Solidity.

## Workflow
- Build a protocol map: key contracts, roles, assets, mutable state, custody, oracle dependencies, and critical entrypoints.
- Draft invariants in plain language and math form.
- Identify legitimate exceptions in specs/audits and encode them explicitly (events/logs are often the signal).
- Decide if the invariant is transaction-scoped, call-scoped, token-flow-scoped, or storage-scoped.
- Choose enforcement location (per-contract vs chokepoint) based on call routing.
- Flag upgradeability/proxy entrypoints and token integration assumptions.
- Pick observation strategy:
  - State comparisons for monotonicity and conservation.
  - Event-based accounting when internal state is opaque.
  - Call input parsing for authorization or parameter bounds.
  - ERC20 delta/circuit-breaker monitoring for treasury, vault, bridge, escrow, or reserve flows.
- Map to triggers with the smallest blast radius.
- For calldata-keyed invariants, check whether the chosen API returns raw calldata or args-only data and document the decoding strategy.
- Reuse existing protection-suite surfaces before custom logic: ERC4626 vault checks, lending operation safety, perpetual risk checks, access-control slot/balance guards, and protection precompiles.
- Group invariants into multiple assertion contracts when needed to avoid `CreateContractSizeLimit`.
- Enumerate edge cases (zero supply, empty vaults, proxy upgrades, nested batches).

## Rationalizations to Reject
- "Trigger on any call; it is simpler." This risks gas-limit reverts and false drops.
- "Post-state is enough." Many invariants need pre/post deltas.
- "Ignore batch or nested calls." Real protocols use them heavily.
- "We can skip edge cases like zero supply." These are common sources of false positives.
- "The protocol already tests this." Assertion design must protect external post-state that may not be enforced by local unit tests.
- "Use custom state to track rolling windows." Use built-in cumulative inflow/outflow triggers for V2 flow limits.

## Deliverable
- Invariant spec card with: category, protected functions/selectors, trigger type, data reads, guard overlap, exceptions, implementation plan, and test plan.
- A candidate list of assertion functions with one invariant per function.
- A short note explaining why each invariant is not merely a restated `require`/custom-error check.

## References
- [Invariant Patterns](references/invariant-patterns.md)
- [Trigger Mapping Guide](references/trigger-mapping.md)
- [Protection Assertion Guide](references/protection-assertion-guide.md)
- [Assertion Spec Card Template](references/assertion-spec-card-template.md)
