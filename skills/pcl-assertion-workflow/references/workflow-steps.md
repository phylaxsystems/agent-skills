# Project Structure and CLI Flow

## Expected Layout
```
my-protocol/
  assertions/
    src/      # Assertion source files (.a.sol)
    test/     # Assertion tests (.t.sol)
  src/        # Protocol contracts
```

## Core Commands
- `pcl test` runs assertion tests locally.
- `pcl auth login` authenticates your wallet for the dApp.
- `pcl store <AssertionName> [ctor args...]` stores assertion code in Assertion DA (auto-builds).
- `pcl submit` submits stored assertions to a project.
- `pcl submit -a 'AssertionName(arg1,arg2)' -p <Project>` submits specific assertions.
- `pcl config show` inspects saved auth and pending submissions.

## Test Parity Notes
- `pcl test` behaves like `forge test` (same flags, fuzzing, verbosity).
- `pcl` can lag Forge versions; confirm new flags before relying on them.
- Use `forge-std/Test` for available helpers and cheatcodes.
- Refer to the Forge Book for cheatcode semantics and testing flags.
- Tests are any functions starting with `test`; conventionally in `test/*.t.sol`.

## Deployment Flow
1. Deploy target contracts with `forge script`.
2. Create a project in the dApp and link the target contract.
3. Store and submit assertions using `pcl`.
4. Deploy the assertion in the dApp (staging or production) and wait for timelock.

## Gotchas
- Use the same address for deploy + authentication.
- Contracts usually must expose `owner()` for verification unless the network uses an allowlist verifier.
- Timelock delays enforcement; a pass in staging does not imply production is active.

## Environment Overrides
- `PCL_AUTH_URL`, `PCL_DA_URL`, `PCL_API_URL` override default endpoints.
