# E2E Testing With PCL

Use `pcl test` for Credible assertion behavior. `forge test` can compile contracts and run ordinary tests, but it is not enough to validate assertions that rely on the Credible cheatcode/precompile execution path.

## Local E2E Test Shape

Create focused tests that inherit `CredibleTest` and arm one assertion function immediately before the monitored external call:

```solidity
contract ProtocolAssertionTest is Test, CredibleTest {
    ProtocolMock protocol;
    TokenMock token;

    function setUp() public {
        protocol = new ProtocolMock();
        token = new TokenMock();
        // Seed non-trivial balances, approvals, reserves, oracle state, or account health.
    }

    function _arm(bytes4 fnSelector) internal {
        bytes memory createData = abi.encodePacked(
            type(ProtocolAssertion).creationCode,
            abi.encode(address(protocol), address(token))
        );

        cl.assertion(address(protocol), createData, fnSelector);
    }

    function testHonestPathPasses() public {
        _arm(ProtocolAssertion.assertCriticalProperty.selector);
        protocol.monitoredMutation();
    }

    function testBrokenPathTrips() public {
        protocol.setMode(ProtocolMock.Mode.BrokenProperty);

        _arm(ProtocolAssertion.assertCriticalProperty.selector);
        vm.expectRevert(bytes("Protocol: property broken"));
        protocol.monitoredMutation();
    }
}
```

Rules:

- Import both `forge-std/Test.sol` and `CredibleTest`.
- Build `createData` with `abi.encodePacked(type(AssertionContract).creationCode, abi.encode(constructorArgs...))`.
- Pass the assertion adopter as the first `cl.assertion` argument. The next monitored external call should be to that adopter or should trigger the target path through it.
- Arm `cl.assertion` immediately before the call under test. Treat it as one-shot and consumed by the next monitored call.
- Keep behavior tests small: one assertion, one monitored call, one expected result.
- Do not arm assertions in smoke tests that only deploy contracts and do not execute a monitored call.
- Add at least one honest passing path and one failing path for each high-risk assertion function.
- Prefer one broken mock mode per invariant so a failure explains exactly which property tripped.
- Use `vm.expectRevert(bytes("..."))` for expected assertion failures when the revert string is stable.

## Commands

Run the full local suite:

```bash
pcl test
```

Run only the assertion area you changed:

```bash
pcl test --match-path 'test/protection/<category>/*.t.sol'
```

Run one behavior test with useful traces:

```bash
pcl test --match-test testBrokenPathTrips -vvvv
```

Run one contract or path when iterating:

```bash
pcl test --match-contract ProtocolAssertionTest
pcl test --match-path test/protection/vault/Erc4626Assertion.t.sol
```

For backtesting or tests that use FFI:

```bash
pcl test --ffi -vvvv --match-test testHistoricalTransactions
FOUNDRY_PROFILE=backtesting pcl test -vvvv
```

If dependencies or repo profiles require a specific Foundry profile, preserve it:

```bash
FOUNDRY_PROFILE=unit-assertions pcl test -vvv
```

## Backtesting Guide

Use `CredibleTestWithBacktesting` when the assertion should be checked against historical transactions.

- Use single-transaction mode for a known exploit, regression, or transaction fixture.
- Use block-range mode to estimate false positives across ordinary protocol activity.
- Set `CREDIBLE_STD_PATH` if the backtesting script cannot be auto-detected.
- Use `--ffi` or a profile with `ffi = true`.
- Treat replay failures separately from assertion failures; replay can fail because of RPC/archive limitations, fork configuration, or unsupported trace APIs.

## Completion Checklist

- `pcl test` or a focused `pcl test --match-*` command was run.
- Tests include honest and malicious/failing behavior for new assertion functions where feasible.
- Tests are small and focused rather than scenario-heavy.
- Constructor/createData wiring includes all addresses and thresholds needed at assertion runtime.
- Tests do not rely on assertion-authored persistent storage for V2 Reshiram behavior.
- Circuit breaker tests, when present, verify the intended response tier: hard pause, liquidation-only, withdrawal-only, or selector-aware allowance.
- Any skipped E2E or backtesting coverage is called out with the runtime limitation or missing external dependency.
