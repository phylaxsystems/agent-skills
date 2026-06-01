---
name: pcl-assertion-workflow
description: "Phylax Credible Layer assertions workflow. Guides the end-to-end PCL workflow (project setup, testing, store/submit, and deploy). Use when setting up or deploying phylax/credible layer assertions with the CLI and dApp."
---

# PCL Assertion Workflow

Use this when you need the full lifecycle: create, test, store, submit, and deploy assertions.

## When to Use
- Setting up a new assertions project with `pcl`.
- Running local tests and validating assertions before deployment.
- Storing, submitting, and deploying assertions in the Credible Layer dApp.

## When NOT to Use
- You only need invariant design. Use `designing-assertions`.
- You only need Solidity implementation details. Use `implementing-assertions`.
- You only need test patterns and fuzzing. Use `testing-assertions`.

## Project Structure
```
project/
├── src/                        # Protocol smart contracts
├── test/                       # Protocol tests
├── script/                     # Deployment scripts
├── assertions/
│   ├── src/                    # Assertion contracts (.a.sol)
│   └── test/
│       ├── unit/               # Unit tests (.t.sol)
│       ├── fuzz/               # Fuzz tests (.t.sol)
│       └── backtest/           # Backtest tests (.t.sol)
├── foundry.toml                # Foundry config with assertion profiles
└── remappings.txt              # Import remappings
```

## Foundry Configuration
Add profiles for assertions in `foundry.toml`:
```toml
# Runs all assertion tests
[profile.assertions]
src = "assertions/src"
test = "assertions/test"
out = "assertions/out"
cache_path = "assertions/cache"

# Unit tests only
[profile.assertions-unit]
src = "assertions/src"
test = "assertions/test/unit"
out = "assertions/out"
cache_path = "assertions/cache"

# Fuzz tests only
[profile.assertions-fuzz]
src = "assertions/src"
test = "assertions/test/fuzz"
out = "assertions/out"
cache_path = "assertions/cache"

# Backtests only (requires ffi)
[profile.assertions-backtest]
src = "assertions/src"
test = "assertions/test/backtest"
out = "assertions/out"
cache_path = "assertions/cache"
ffi = true
```

Add remappings to `remappings.txt`:
```
credible-std/=lib/credible-std/src/
forge-std/=lib/forge-std/src/
```

Usage:
- All tests: `FOUNDRY_PROFILE=assertions pcl test`
- Unit only: `FOUNDRY_PROFILE=assertions-unit pcl test`
- Fuzz only: `FOUNDRY_PROFILE=assertions-fuzz pcl test`
- Backtests only: `FOUNDRY_PROFILE=assertions-backtest pcl test`

## Quick Start
1. From the protocol repo root, set up the directory structure above.
2. Install dependencies: `forge install phylaxsystems/credible-std`.
3. Configure `foundry.toml` and `remappings.txt` as shown above.
4. Write focused `CredibleTest` E2E tests that arm one assertion immediately before the monitored external call.
5. Run `FOUNDRY_PROFILE=assertions pcl test` to validate locally. Use `pcl test` for assertion behavior; use `forge test` only for regular protocol tests or compile-only checks.
6. Deploy target contracts with `forge script`.
7. Authenticate: `pcl auth login`.
8. Store assertions: `pcl store <AssertionName> [ctor args...]` (auto-builds; `pcl build` is optional).
9. Submit: `pcl submit` (or `pcl submit -a 'AssertionName(arg1,arg2)' -p <ProjectName>`; project name is case-sensitive).
10. Deploy via dApp (staging or production) and wait for timelock.

## Environment Overrides
- `PCL_AUTH_URL`, `PCL_DA_URL`, `PCL_API_URL` for custom endpoints.

## Rationalizations to Reject
- "Tests can wait until after deployment." Always run `pcl test` first.
- "We can skip store/submit steps." Deployment depends on DA storage.
- "Any wallet works." Use the same address as contract deployer for authentication.
- "Forge passing means assertions are verified." `forge test` does not prove the Credible assertion execution path.

## References
- [Project Structure and CLI Flow](references/workflow-steps.md)
- [E2E Testing With PCL](references/e2e-testing-with-pcl.md)
