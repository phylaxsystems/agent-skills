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
- Fix: use `ph.loadStateAt(...)` for V2 fork-aware reads, or `ph.load(...)` only when working with legacy examples.

## Selector Mismatch
- Cause: trigger selector does not match called function.
- Fix: use `Interface.function.selector` and register in `triggers()`.

## Call Input Double-Counting
- Cause: `getAllCallInputs()` includes proxy + delegate calls.
- Fix: use V2 `ph.context()` for the triggering call when possible; otherwise use `getCallInputs()` or `getDelegateCallInputs()` deliberately and dedupe proxy paths.

## Call Input Decode Reverts
- Cause: the decode assumes the wrong input shape.
- Fix: verify the API. `ph.callinputAt(callId)` returns raw calldata including the selector, so strip the first 4 bytes before `abi.decode`. For legacy helpers, check the target repo's `PhEvm.sol`.

## ph.context Reverts
- Cause: `ph.context()` was called outside an assertion fired by `registerFnCallTrigger`.
- Fix: use `registerFnCallTrigger(fn, selector)` for per-call assertions or remove `ph.context()` from tx-end/storage/ERC20-change assertions.

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

## Anti-Pattern: Dispatcher Functions
Routing many triggers through one assertion function hurts gas and debugging:
```solidity
// Avoid: many triggers routed through one dispatcher.
function triggers() external view override {
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.setFee.selector);
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.setGuardian.selector);
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.submitCap.selector);
}
```
```solidity
// Prefer: one coherent property per assertion function.
function triggers() external view override {
    registerFnCallTrigger(this.assertSetFeeBounds.selector, IVault.setFee.selector);
    registerFnCallTrigger(this.assertGuardianChangeSafe.selector, IVault.setGuardian.selector);
    registerFnCallTrigger(this.assertSubmitCapTimelock.selector, IVault.submitCap.selector);
}
```

## Anti-Pattern: Mixed Interfaces
Using selectors from different interfaces when one extends the other causes confusion:
```solidity
// Confusing: mixing IERC4626 and IVault
registerFnCallTrigger(this.assertDeposit.selector, IERC4626.deposit.selector);
registerFnCallTrigger(this.assertSubmitCap.selector, IVault.submitCap.selector);
```
```solidity
// Clear: consistent interface usage
registerFnCallTrigger(this.assertDeposit.selector, IVault.deposit.selector);
registerFnCallTrigger(this.assertSubmitCap.selector, IVault.submitCap.selector);
```
