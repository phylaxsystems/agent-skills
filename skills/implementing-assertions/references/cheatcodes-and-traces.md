# Cheatcodes and Traces

## Forking
- `forkPreTx()` and `forkPostTx()` switch global pre/post state.
- `forkPreCall(id)` and `forkPostCall(id)` switch state around a specific call.
- If you do not call a fork function, assertions run against post-state by default.

## Call Inputs
- `getCallInputs(target, selector)` returns only CALLs.
- `getDelegateCallInputs` isolates delegate calls (useful for proxies).
- `getStaticCallInputs` and `getCallCodeInputs` target other call types.
- `getAllCallInputs` includes CALL/STATICCALL/DELEGATECALL/CALLCODE and may duplicate proxy paths.
- Filter proxy duplicates by ignoring entries where `bytecode_address == target_address`.
- Call inputs include `caller`, `value`, `gas_limit`, `bytecode_address`, `target_address`, and `id` for per-call forking.
- Call input arrays can be large; test worst-case sizes to stay under the 300k gas cap.
- For router wrappers (batch/call entrypoints), decode nested calldata to extract the real target and account.

## Logs
- `getLogs()` returns all logs for the triggering transaction.
- Filter by `emitter` and `topics[0]` (event signature).

## State Changes
- `getStateChanges(target, slot)` returns the initial value plus subsequent changes for that slot.
- Use `getStateChangesUint/Address/Bool` helpers when possible.
- If no changes occurred, the array is empty; reverted changes are not included.
- Ordering is per-slot only; do not assume cross-slot timing alignment.

## Helpers
- `getAssertionAdopter()` returns the protected contract for the current run.
- `load(target, slot)` reads a storage slot directly.
- `console.log` (credible-std) logs a single string; use `Strings.toString` for numbers.

## Triggers
- `registerBalanceChangeTrigger` fires on ETH balance changes for the adopter.

## External Call Verification
- To ensure a downstream call occurred (e.g., bridge send), query `getCallInputs` on the callee after `forkPostCall`.

## Notes
- Internal Solidity calls are not traced unless they are externalized via `this.`.
- For nested batches, use `forkPreCall(id)` to detect whether you are inside a batch.
- `getAssertionAdopter()` is only available in `triggers()` and assertion functions (not constructors).
- Use `staticcall` to probe optional interfaces; skip checks when unsupported.
- Enumerating modified mapping keys is not supported; derive keys from call inputs or logs.
