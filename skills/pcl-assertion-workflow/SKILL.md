---
name: pcl-assertion-workflow
description: "Guides the end-to-end PCL workflow (project setup, testing, store/submit, and deploy). Use when setting up or deploying assertions with the Credible Layer CLI and dApp."
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

## Quick Start
1. From the protocol repo root, keep the standard Foundry layout: `src/`, `test/`, `assertions/src/`, `assertions/test/`.
2. Configure a dedicated Foundry profile (e.g., `[profile.assertions]`) pointing `src` and `test` to the assertions paths, and add remappings for `credible-std` and `forge-std`. Consider separate `out`/`cache_path` to avoid collisions.
2. Initialize or clone a project (e.g., `credible-layer-starter`).
3. Run `FOUNDRY_PROFILE=assertions pcl test` to validate locally. <u>Use `pcl test` for assertion tests because it includes the `cl.addAssertion` cheatcode; use `forge test` only for regular protocol tests.</u>
4. Deploy target contracts with `forge script`.
5. Authenticate: `pcl auth login`.
6. Store assertions: `pcl store <AssertionName> [ctor args...]` (auto-builds; `pcl build` is optional).
7. Submit: `pcl submit` (or `pcl submit -a 'AssertionName(arg1,arg2)' -p <ProjectName>`; project name is case-sensitive).
8. Deploy via dApp (staging or production) and wait for timelock.

## Environment Overrides
- `PCL_AUTH_URL`, `PCL_DA_URL`, `PCL_API_URL` for custom endpoints.

## Rationalizations to Reject
- "Tests can wait until after deployment." Always run `pcl test` first.
- "We can skip store/submit steps." Deployment depends on DA storage.
- "Any wallet works." Use the same address as contract deployer for authentication.

## References
- [Project Structure and CLI Flow](references/workflow-steps.md)
