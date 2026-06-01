---
name: assertion-troubleshooting
description: "Phylax Credible Layer assertions troubleshooting. Diagnoses common assertion failures and non-triggering issues. Use when phylax/credible layer assertions fail unexpectedly or do not execute."
---

# Assertion Troubleshooting

Use this when assertions fail unexpectedly, revert with OutOfGas, or never execute.

## When to Use
- Tests show "Expected 1 assertion to be executed, but 0 were executed".
- Assertions revert with `OutOfGas` or unknown reasons.
- Call inputs appear empty or duplicate.

## When NOT to Use
- You need invariant design. Use `designing-assertions`.
- You need implementation details. Use `implementing-assertions`.
- You need test strategy or fuzzing. Use `testing-assertions`.

## Quick Start
1. Confirm the registered V2 trigger matches the intended target path: `registerFnCallTrigger`, `registerTxEndTrigger`, `registerErc20ChangeTrigger`, cumulative flow trigger, or storage trigger.
2. Ensure `cl.assertion()` is immediately before the monitored external call; the next monitored call consumes it.
3. Check if the target call reverted before assertions ran.
4. Verify `ph.*` calls are used in assertion functions, not constructors.
5. Remember internal Solidity calls are not traced; triggers only fire on external entrypoints.
6. Use `pcl test -vvvv` for full traces and gas diagnostics.
7. Confirm `FOUNDRY_PROFILE=assertions` when running `pcl test`.
8. Use `pcl test` for assertion behavior; use `forge test` only for regular protocol tests or compile-only checks.
9. If the failure is `CreateContractSizeLimit`, split assertions into smaller contracts.
10. If the failure is an empty revert or ABI decode panic, re-check whether the API returns raw calldata with selector (`ph.callinputAt`) or args-only data.
11. If `ph.context()` reverts, the assertion was not triggered by `registerFnCallTrigger`.
12. If a rolling-window breaker does not fire, confirm the watched token, threshold bps, window duration, and adopter balance source.

## Rationalizations to Reject
- "The assertion should have run." Verify triggers and call order first.
- "It is probably a test issue." Validate the target call succeeds without assertions.
- "Gas is fine." Happy path often consumes the most gas.
- "The old fork-switching example should be enough." Prefer current V2 fork-aware reads for new assertions.

## References
- [Common Errors and Fixes](references/common-errors.md)
