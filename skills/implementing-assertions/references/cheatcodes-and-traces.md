# Cheatcodes and Traces

## V2 Fork Reads
- Prefer fork-aware reads over legacy fork switching for new assertions.
- Use `_preTx()` and `_postTx()` for transaction-wide snapshots.
- Use `_preCall(ctx.callStart)` and `_postCall(ctx.callEnd)` inside assertions fired by `registerFnCallTrigger`.
- Use `ph.staticcallAt(target, data, gasLimit, fork)` for view calls against a snapshot.
- Use `ph.loadStateAt(target, slot, fork)` for direct storage reads.
- Treat legacy fork switching and direct `ph.load` as compatibility APIs unless the target repo's examples still require them.

```solidity
PhEvm.TriggerContext memory ctx = ph.context();
PhEvm.ForkId memory preCall = _preCall(ctx.callStart);
PhEvm.ForkId memory postCall = _postCall(ctx.callEnd);

uint256 preAssets = _readUint(vault, abi.encodeCall(IVault.totalAssets, ()), preCall);
uint256 postAssets = _readUint(vault, abi.encodeCall(IVault.totalAssets, ()), postCall);
```

## V2 Triggers
- `registerFnCallTrigger(fn, selector)`: fires once per matching adopter call and makes `ph.context()` available.
- `registerTxEndTrigger(fn)`: fires once after the whole transaction and is best for accounting envelopes, protected slots, protected balances, and oracle bounds.
- `registerErc20ChangeTrigger(fn, token)`: fires when the token balance set changes and is useful for custody/reserve checks.
- `watchCumulativeOutflow(token, thresholdBps, windowDuration, fn)`: built-in rolling-window outflow circuit breaker.
- `watchCumulativeInflow(token, thresholdBps, windowDuration, fn)`: built-in rolling-window inflow circuit breaker.
- Storage triggers are still available for protected slots; avoid global storage triggers unless broad storage writes are the risk.

## Call Inputs
- `ph.context()` returns the selector and call ids for the current `registerFnCallTrigger` invocation.
- `ph.callinputAt(ctx.callStart)` returns raw calldata: selector plus ABI-encoded arguments.
- `ph.callOutputAt(ctx.callStart)` returns raw return or revert bytes for that call.
- Legacy `getCallInputs(target, selector)` returns only CALLs.
- Legacy `getDelegateCallInputs` isolates delegate calls (useful for proxies).
- Legacy `getStaticCallInputs` and `getCallCodeInputs` target other call types.
- Legacy `getAllCallInputs` includes CALL/STATICCALL/DELEGATECALL/CALLCODE and may duplicate proxy paths.
- Filter proxy duplicates by comparing `bytecode_address` and `target_address`; keep the entry that represents the intended code path (often the one where they are equal).
- Call inputs include `caller`, `value`, `gas_limit`, `bytecode_address`, `target_address`, and `id` for per-call forking.
- Call input arrays can be large; test worst-case sizes to stay under the 300k gas cap.
- For router wrappers (batch/call entrypoints), decode nested calldata to extract the real target and account.
- For delegatecall batches, `getAllCallInputs` is the only way to see nested items; dedupe targets/accounts.
- For packed calldata protocols, decode inputs using the protocol's bit layout before applying invariants.
- If a protocol uses sentinel values (e.g., max uint for "full repay"), replace with the pre-state balance/debt.

## Logs
- `getLogs()` returns all logs for the triggering transaction.
- `ph.getLogsQuery(query, fork)` reads logs for a snapshot.
- `ph.getLogsForCall(query, callId)` reads logs for a specific call frame.
- Filter by `emitter` and `topics[0]`/signature.

## State Changes
- `getStateChanges(target, slot)` returns the initial value plus subsequent changes for that slot.
- Use `getStateChangesUint/Address/Bool` helpers when possible.
- If no changes occurred, the array is empty; reverted changes are not included.
- Ordering is per-slot only; do not assume cross-slot timing alignment.

## ERC20 Flow Helpers
- `ph.getErc20Transfers(token, fork)` returns decoded ERC20 transfers for one token.
- `ph.getErc20TransfersForTokens(tokens, fork)` returns decoded transfers for several tokens.
- `ph.changedErc20BalanceDeltas(token, fork)` and `ph.reduceErc20BalanceDeltas(token, fork)` help model token balance movement.
- For rolling-window movement, use `watchCumulativeOutflow` or `watchCumulativeInflow` instead of assertion-authored storage.

## Common Helpers
- `getAssertionAdopter()` returns the protected contract for the current run.
- `_successOnlyFilter()` and `_matchingCalls(...)` from `Assertion` help bound downstream-call inspection in V2 examples.
- Use typed helper functions around `staticcallAt` so decode failures produce clear revert messages.

## Console Logging (Debugging)
`console.log` accepts only strings. Use `string.concat` and `Strings.toString` for numbers:
```solidity
import {console} from "forge-std/console.sol";
import {Strings} from "openzeppelin-contracts/contracts/utils/Strings.sol";

function assertionDebug() external {
    uint256 value = 123;
    console.log(string.concat("Value: ", Strings.toString(value)));
}
```

## External Call Verification
- Use `ph.matchingCalls(target, selector, filter, limit)` when a downstream call is part of the safety property.
- Do not assert only that a function was called unless the call proves a larger invariant.

## Notes
- Internal Solidity calls are not traced unless they are externalized via `this.`.
- For nested batches, use the V2 trigger context and bounded call matching where possible.
- `getAssertionAdopter()` is only available in `triggers()` and assertion functions (not constructors).
- Use `ph.loadStateAt` or `ph.load` in assertions; `vm.load` is unavailable.
- Use `staticcall` to probe optional interfaces; skip checks when unsupported.
- Enumerating modified mapping keys is not supported; derive keys from call inputs or logs.
- For intra-tx stability checks, use `_preTx()` as a baseline and `_postCall(ctx.callEnd)` per call.

## Intra-Transaction Monitoring Example
Check intermediate states after each call within a transaction:
```solidity
function assertionIntraTxPriceDeviation() external {
    PhEvm.TriggerContext memory ctx = ph.context();
    PhEvm.ForkId memory preTx = _preTx();
    PhEvm.ForkId memory postCall = _postCall(ctx.callEnd);

    uint256 initialPrice = _readUint(oracle, abi.encodeCall(IOracle.price, ()), preTx);
    uint256 maxPrice = (initialPrice * 110) / 100; // +10%
    uint256 minPrice = (initialPrice * 90) / 100;  // -10%

    uint256 priceAfterCall = _readUint(oracle, abi.encodeCall(IOracle.price, ()), postCall);
    require(priceAfterCall >= minPrice && priceAfterCall <= maxPrice, "Oracle: intra-tx deviation");
}
```
