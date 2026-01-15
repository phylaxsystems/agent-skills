# Trigger Mapping Guide

## Choose the Smallest Trigger
- **Call trigger**: when invariants depend on a specific function or selector.
- **Storage trigger**: when any function can mutate a slot (e.g., implementation slot, totalSupply).
- **Balance trigger**: when adopter ETH balance changes are the key signal.

## Call Trigger Tips
- Prefer `registerCallTrigger(fn, selector)` over `registerCallTrigger(fn)`.
- Parse inputs with `getCallInputs` to extract accounts or amounts.
- For proxies, use `getDelegateCallInputs` if you only want delegate calls.
- Internal Solidity calls are not traced; register on external entrypoints.
- Call inputs are ordered per selector, not across different selectors.
- For router/batch entrypoints, decode nested calldata to extract the real target and account.

## Storage Trigger Tips
- Use specific slot offsets to avoid global triggers.
- For mappings, compute slot = keccak256(key, baseSlot) + offset.
- For packed fields, mask or shift bits after `ph.load`.

## Avoid Over-Triggering
- Global triggers increase gas and raise the risk of dropping valid transactions.
- If you must trigger broadly, add early exits (e.g., skip non-contract addresses).
- In tests, `cl.assertion()` still requires a matching trigger to fire.

## Enforcement Location
- If all sensitive actions pass through a chokepoint, trigger there once.
- If not, trigger on each entrypoint that can violate the invariant.

## Nested Call Coverage
- Batched or nested calls can double-trigger.
- Use `forkPreCall(callId)`/`forkPostCall(callId)` for per-call checks.
- Filter proxy duplicates by ignoring calls where `bytecode_address == target_address`.
