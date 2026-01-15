# Common Errors and Fixes

## Assertion Not Executing
- Cause: `cl.assertion()` not placed immediately before the target call.
- Fix: Move setup before `cl.assertion()` and call the target function next.
- Cause: trigger selector does not match the target function.
- Fix: verify the `triggers()` registration and selector.
- Cause: internal calls are not traced.
- Fix: register triggers on external entrypoints (or `this.` calls).

## OutOfGas
- Cause: assertion exceeds 300k gas limit.
- Fix: fail fast, cache reads, reduce loops, split assertions.

## Wrong Cheatcode
- Cause: using `vm.load()` in assertions.
- Fix: use `ph.load()`.

## Selector Mismatch
- Cause: trigger selector does not match called function.
- Fix: use `Interface.function.selector` and register in `triggers()`.

## Call Input Double-Counting
- Cause: `getAllCallInputs()` includes proxy + delegate calls.
- Fix: use `getCallInputs()` or `getDelegateCallInputs()`.

## Call Input Decode Reverts
- Cause: `CallInputs.input` excludes the selector; decoding with a selector offset reverts.
- Fix: decode args directly; if you need `msg.data`, rebuild with `abi.encodePacked(selector, input)`.

## Internal Calls Not Traced
- Cause: internal Solidity calls are not traced.
- Fix: register triggers on external entrypoints.

## vm.prank Consumed by Inline Call
- Cause: inline view/pure calls after `vm.prank()` consume the prank.
- Fix: store view results before `vm.prank()` and before `cl.assertion()`.

## expectRevert on Internal Calls
- Cause: Foundry v1.0 disables `vm.expectRevert` on internal calls by default.
- Fix: test external entrypoints or refactor to avoid internal-call expectations.

## Constructor Cheatcodes
- Cause: cheatcodes are unavailable in constructors.
- Fix: move logic into assertion functions.

## Backtesting FFI
- Cause: missing `--ffi` or `ffi = true` in the backtest profile.
- Fix: run `pcl test --ffi` or enable `ffi` in `foundry.toml`.

## CreateContractSizeLimit
- Cause: assertion contract bytecode exceeds the create size limit.
- Fix: split assertions across multiple smaller contracts and re-run `pcl test`.

## trace_filter Not Supported
- Cause: RPC provider lacks `trace_filter` support.
- Fix: set `useTraceFilter = false` (block scanning) or switch RPC providers.

## Wrong Profile
- Cause: `pcl test` uses the default Foundry profile.
- Fix: set `FOUNDRY_PROFILE=assertions` (or unit/fuzz/backtest profile).
