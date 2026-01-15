# Test Patterns

## Registering Assertions
- `cl.assertion({ adopter, createData, fnSelector });` runs on the next transaction only.
- Register again for each test action.
- Only one assertion function can be registered at a time; test functions in isolation.
- Put all setup before `cl.assertion()`; the very next call consumes it.
- The next call must match a trigger registered for `fnSelector`, or the assertion will not execute.

## Profiles
- Use `FOUNDRY_PROFILE=assertions` (or unit/fuzz/backtest profiles) to isolate assertion builds.

## Constructor Args
- Use `abi.encodePacked(type(MyAssertion).creationCode, abi.encode(arg1, arg2))`.

## Batch Operations
- Use a helper contract that performs multiple operations in one call.
- Avoid low-level fallback calls when possible; revert reasons are cleaner.
- Internal calls do not trigger assertions; register on external entrypoints.

## Time Windows and Modes
- Use `vm.warp` to test just-before and just-after window expiration.
- Cover mode switches (sync/async, paused/unpaused) on both sides.

## Failure Path Checks
- When a call should fail, assert state is unchanged (balances, debts, indexes).
- For gatekeeping invariants (borrowable/frozen/paused), test both revert and state‑no‑change.
- Use `assertApproxEqAbs(..., 1)` for scaled balance rounding.
- For liveness invariants, assert full repay/withdraw succeeds under the expected preconditions.
- For flashloans, test both repayment success and insufficient repayment failure.

## Prank Consumption
- Do not inline view calls after `vm.prank()`: the inner call consumes the prank.
- Store values before `vm.prank()` and before `cl.assertion()`.

## Protocol Mocking
- Build minimal mock contracts that can be forced into invalid states.
- Use mocks to trigger failure paths that real protocols would normally prevent.

## Fuzzing
- Fuzz amounts and sequence length to stress loops and rounding paths.
- Include `vm.assume` guards to avoid invalid setups.

## Property-Based Testing
- Use roundtrip properties for encode/decode pairs.
- Use idempotence for normalization or formatting logic.
- Use invariants for state transitions (pre/post).

## Backtesting
- Use `CredibleTestWithBacktesting` and `executeBacktest` with a real RPC.
- Run with `--ffi` or a profile that sets `ffi = true`.
- Prefer `useTraceFilter = true` to capture internal calls; use `forkByTxHash` for exact state debugging.
- Expect result buckets like PASS, NEEDS_REVIEW (selector mismatch / prestate issues), ASSERTION_FAIL, UNKNOWN_ERROR.

## PCL Test Parity
- `pcl test` is a fork of `forge test` with identical behavior and flags.
- Use `forge-std/Test` for available helpers and cheatcodes.
- Refer to the Forge Book for detailed cheatcode behavior and test flags.
- Use `vm.expectRevert` for negative cases instead of `testFail` (deprecated in Foundry v1.0).
