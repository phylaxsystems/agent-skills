---
name: optimize-assertion-triggers
description: Optimize Credible Layer/PCL Solidity assertion trigger selection for existing or newly edited assertions. Use when an assertion fires too often, relies on broad onFnCall/registerFnCallTrigger usage, needs lower execution overhead, or needs a trigger review that preserves the same security invariant while preferring narrower triggers such as onTxEnd/registerTxEndTrigger, ERC20-change triggers, storage-change triggers, or cumulative flow triggers where appropriate.
---

# Optimize Assertion Triggers

Reduce unnecessary Credible assertion executions without weakening the protected invariant. The default outcome is either a narrower trigger strategy with explicit security-preservation assumptions, or a documented refusal when the narrower strategy would miss relevant execution paths.

## When to Use
- An assertion fires too often or adds avoidable execution overhead.
- An assertion relies on broad `onFnCall`/`registerFnCallTrigger` coverage that could be a tx-end, ERC20-change, storage-change, or cumulative-flow check instead.
- You are reviewing or refactoring the `triggers()` of an existing or newly edited assertion and want the smallest safe trigger surface.
- A trigger fires on legitimate paths that can never violate the invariant.

## When NOT to Use
- You are designing invariants from scratch. Use `designing-assertions` (and `mapping-invariants` to discover them).
- You are writing new assertion Solidity or need cheatcode/precompile syntax. Use `implementing-assertions` or `write-protection-assertions`.
- The assertion only restates a protocol `require`/custom-error guard. Rethink the invariant with `write-protection-assertions` instead of optimizing a low-value trigger.
- You only need test harness patterns. Use `testing-assertions`.

## Quick Start
1. Read the assertion contract, its `triggers()`, assertion functions, helpers, interfaces, and focused `pcl test` coverage.
2. Verify the target repo's current PCL/Credible APIs before changing syntax (map legacy names, e.g. `onFnCall` → `registerFnCallTrigger`, `onTxEnd` → `registerTxEndTrigger`).
3. Restate the exact security property in protocol terms, then list every path that can violate it.
4. Classify the natural trigger boundary (tx-end, function-call, ERC20-change, cumulative-flow, or storage-change).
5. Search for the narrowest trigger that still observes every violating path; reject any reduction that drops coverage.
6. Implement the smallest safe change, update NatSpec and tests, and validate with `pcl test`.

## Workflow

1. **Load assertion and PCL context**
   - Read the assertion contract, its `triggers()` implementation, assertion functions, helpers, interfaces, and focused `pcl test` coverage.
   - Verify the target repo's current PCL/Credible APIs before changing syntax. Map legacy names to current equivalents when needed, for example `onFnCall` to `registerFnCallTrigger` and `onTxEnd` to `registerTxEndTrigger`.
   - Identify the adopter/target contracts, registered selectors, trigger type, assertion function selector, PCL fork reads, `ph.context()` usage, calldata/output decoding, and external state reads.
   - For exact trigger and precompile signatures, read `../write-protection-assertions/references/v2-precompiles-and-triggers.md` and verify against the target repo's `src/TriggerRecorder.sol` and `src/PhEvm.sol` when vendored.

2. **Restate the invariant before optimizing**
   - State the exact security property in protocol terms.
   - List the execution paths that can violate it, including direct calls, routers, proxies, multicall legs, callbacks, token transfers, storage writes, and transaction-wide side effects.
   - Separate the invariant from the current trigger. The trigger is replaceable only if the replacement observes every relevant path needed for the same property.

3. **Classify the natural trigger boundary**
   - Prefer transaction-end triggers for transaction-wide post-state invariants such as custody covering liabilities, aggregate solvency, reserve/debt bounds, protected balances unchanged across a transaction, and oracle/exchange-rate stability.
   - Keep function-call triggers when the invariant needs per-call boundaries, `ph.context()`, call input/output decoding, selector-specific pre/post-call comparison, or proof that each matched operation is safe in isolation.
   - Prefer ERC20-change triggers when token movement is the risk and relevant movements can happen through multiple entry points or selector coverage is incomplete.
   - Prefer cumulative inflow/outflow triggers when the property is a rolling-window flow limit rather than a single transaction or single call property.
   - Prefer storage-change triggers for protected admin, implementation, configuration, or accounting slots only when the changed slot is the direct risk surface.

4. **Search for safe reductions**
   - Replace broad function-call coverage with `onTxEnd`/`registerTxEndTrigger` only when a final post-transaction check catches the same violation after all side effects settle.
   - Narrow function-call triggers to the minimal selector set when the property genuinely depends on per-call context.
   - Replace selector lists with ERC20-change, storage-change, or cumulative flow triggers when those events are closer to the risk surface and cover bypass paths.
   - Remove duplicate triggers only after proving another trigger fires at an equivalent or stronger boundary for the same invariant.
   - Do not optimize by ignoring routers, proxy entrypoints, delegatecall paths, callbacks, internal multicall legs, token hooks, or downstream contracts that can affect the protected state.

5. **Reject unsafe optimizations**
   - Decline any trigger reduction that would miss a relevant execution path, lose required calldata/output context, check only an intermediate state when the invariant requires per-call safety, or depend on an unproven protocol assumption.
   - If the invariant is too broad to optimize safely, split it into smaller assertions with different natural trigger boundaries instead of weakening it.
   - If the current assertion only restates a protocol `require`/custom-error guard, rethink the invariant using `write-protection-assertions` rather than optimizing a low-value trigger.

6. **Implement the smallest safe change**
   - Keep the assertion function's security property unchanged.
   - Update NatSpec to name the new trigger boundary and failure meaning.
   - Update tests so they prove both the preserved invariant and the trigger strategy: at least one honest passing path, one violating path, and one formerly noisy path when practical.
   - Use `pcl test` as the validation source of truth for Credible behavior.

## Rationalizations to Reject
- "Trigger on every call; it is simpler." Broad coverage risks gas-limit reverts, false drops, and avoidable execution cost.
- "Tx-end is always cheaper, so switch to it." Tx-end loses per-call context; only switch when a post-transaction check catches the same violation after side effects settle.
- "Fewer selectors is fine." Not if routers, proxies, delegatecall, multicall legs, callbacks, or token hooks reach the protected state through the dropped paths.
- "This duplicate trigger is redundant." Only remove it after proving another trigger fires at an equivalent or stronger boundary for the same invariant.
- "The protocol already guards this." If the assertion only restates a `require`/custom-error guard, the fix is a better invariant, not a narrower trigger.
- "Checking an intermediate state is good enough." Reject it when the invariant requires per-call safety or transaction-wide post-state.

## Output
Report the optimization in this shape:

- **Original trigger strategy**: trigger type, selectors/events/slots/tokens, and why it was noisy.
- **Invariant preserved**: the exact property that remains protected.
- **Optimized trigger strategy**: the chosen trigger type and registered surfaces.
- **Rationale**: why the new trigger fires fewer times while still observing every relevant violation path.
- **Security-preservation assumptions**: proxy/router coverage, token movement paths, required call context, fork boundary assumptions, and legitimate exceptions.
- **Rejected alternatives**: any narrower trigger that was considered but would reduce coverage.
- **Validation**: focused `pcl test` commands run, or the concrete blocker if validation could not run.

## Quality Bar
Before finishing, verify:

- The optimized assertion checks the same invariant as the original assertion.
- Every relevant execution path is still covered by the new trigger strategy.
- `onFnCall`/`registerFnCallTrigger` is used only when per-call context or selector-specific safety is necessary.
- `onTxEnd`/`registerTxEndTrigger` is preferred when transaction-wide post-state coverage is equivalent.
- Any optimization that weakens security coverage is rejected or reworked.
- The final explanation includes the trigger reduction rationale and security-preservation assumptions.

## References
- [V2 Precompiles and Triggers](../write-protection-assertions/references/v2-precompiles-and-triggers.md)
- [Trigger Mapping Guide](../designing-assertions/references/trigger-mapping.md)
- [Invariant Patterns](../designing-assertions/references/invariant-patterns.md)
