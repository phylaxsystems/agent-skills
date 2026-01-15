# Backtesting Template

## Example Test
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {CredibleTestWithBacktesting} from "credible-std/backtesting/CredibleTestWithBacktesting.sol";
import {BacktestingTypes} from "credible-std/backtesting/BacktestingTypes.sol";
import {MyAssertion} from "../../assertions/src/MyAssertion.a.sol";

contract MyBacktestingTest is CredibleTestWithBacktesting {
    function testBacktest_RecentBlocks() public {
        BacktestingTypes.BacktestingResults memory results = executeBacktest(
            BacktestingTypes.BacktestingConfig({
                targetContract: 0x1111111111111111111111111111111111111111,
                endBlock: 20000000,
                blockRange: 50,
                assertionCreationCode: type(MyAssertion).creationCode,
                assertionSelector: MyAssertion.assertionInvariant.selector,
                rpcUrl: vm.envString("MAINNET_RPC_URL"),
                detailedBlocks: false,
                useTraceFilter: true,
                forkByTxHash: false
            })
        );

        require(results.assertionFailures == 0, "Backtest failures");
    }
}
```

## Running Backtests
- `FOUNDRY_PROFILE=backtest-assertions pcl test --ffi`
- Set `ffi = true` in the backtest profile to avoid `--ffi`.

## Config Tips
- `useTraceFilter = true` detects internal calls; requires RPC support.
- `forkByTxHash = true` replays prior txs in the block for exact state (slow).
- Use `blockRange = 1` with a known exploit block to validate detection.

## Foundry Profile Snippet
```toml
[profile.backtest-assertions]
src = "assertions/src"
test = "assertions/test/backtest"
out = "assertions/out"
libs = ["lib"]
solc = "0.8.29"
optimizer = true
optimizer_runs = 200
ffi = true
```

## Result Buckets
- `PASS`: assertion ran and passed.
- `NEEDS_REVIEW`: selector mismatch or prestate issues.
- `ASSERTION_FAIL`: assertion reverted (often false positive or gas cap).
- `UNKNOWN_ERROR`: RPC or unexpected execution error.

## Debugging
- Reduce `blockRange` around the failing block.
- Flip `forkByTxHash = true` when state dependencies are suspected.
- Use `pcl test -vvv` for logs and traces.
