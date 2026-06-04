# Trigger Mapping Guide

## Choose the Smallest Trigger
- **Function-call trigger**: use `registerFnCallTrigger(fn, selector)` when the invariant depends on one matching operation and needs call context.
- **Transaction-end trigger**: use `registerTxEndTrigger(fn)` for whole-transaction envelopes such as custody, accounting, oracle bounds, or protected slots after all side effects.
- **ERC20-change trigger**: use `registerErc20ChangeTrigger(fn, token)` when token balance changes are the broad signal and selectors are incomplete.
- **Cumulative-flow trigger**: use `watchCumulativeOutflow` or `watchCumulativeInflow` for rolling-window flow limits.
- **Storage trigger**: use a specific storage slot when the direct risk is unauthorized mutation.

## Call Trigger Tips
- Prefer `registerFnCallTrigger(fn, selector)` for new V2 assertions.
- Use `ph.context()` to get the triggering selector and call ids.
- Parse raw calldata with `ph.callinputAt(ctx.callStart)`; it includes the selector.
- Use `ph.callOutputAt(ctx.callStart)` when the invariant depends on the operation return value.
- For proxies, use `getDelegateCallInputs` if you only want delegate calls.
- Internal Solidity calls are not traced; register on external entrypoints.
- Call inputs are ordered per selector, not across different selectors.
- For router/batch entrypoints, decode nested calldata to extract the real target and account.
- Guard hooks (e.g., `before*` validators) are good precondition triggers.
- Use `getAllCallInputs` when delegatecall batches hide nested calls; dedupe carefully.

## Transaction-End Trigger Tips
- Use tx-end checks for accounting/custody envelopes that should hold after the full transaction, not after each intermediate call.
- Compare `_preTx()` to `_postTx()` when the property is about bounded movement or protected state.
- Keep tx-end assertions narrow enough to stay under the 300k gas cap.

## Cumulative Flow Tips
- Use `watchCumulativeOutflow(token, thresholdBps, windowDuration, fn)` for treasury, vault, bridge, escrow, reserve, or AMM reserve drains.
- Use `watchCumulativeInflow(token, thresholdBps, windowDuration, fn)` for donation, reserve-stuffing, or oracle-manipulation inflows.
- Read `ph.outflowContext()` or `ph.inflowContext()` only inside the corresponding triggered assertion when selector-aware logic is needed.
- Do not implement custom rolling-window storage in the assertion contract for V2 examples.

## Storage Trigger Tips
- Use specific slot offsets to avoid global triggers.
- `registerStorageChangeTrigger(fn)` fires on any slot change; avoid unless broad storage writes are the direct risk.
- For mappings, compute slot = keccak256(key, baseSlot) + offset.
- For packed fields, mask or shift bits after `ph.loadStateAt`.

## Avoid Over-Triggering
- Global triggers increase gas and raise the risk of dropping valid transactions.
- If you must trigger broadly, add early exits (e.g., skip non-contract addresses).
- In tests, `cl.assertion()` still requires a matching trigger to fire.
- Prefer built-in protection-suite precompiles and base assertions when they express the property directly.

## Enforcement Location
- If all sensitive actions pass through a chokepoint, trigger there once.
- If not, trigger on each entrypoint that can violate the invariant.

## Nested Call Coverage
- Batched or nested calls can double-trigger.
- Use `_preCall(ctx.callStart)`/`_postCall(ctx.callEnd)` for V2 per-call checks.
- Filter proxy duplicates by ignoring calls where `bytecode_address == target_address`.
- For multi-item batches, deduplicate accounts and targets before running checks.
