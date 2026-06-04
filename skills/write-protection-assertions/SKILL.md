---
name: write-protection-assertions
description: Create or update high-quality Credible Layer Solidity example assertions and E2E tests for a protocol repository by classifying the protocol against the existing protection suite, using bundled V2 trigger/precompile digests, organizing examples under the right protection category, and prioritizing a small set of focused external-state invariants that are not already enforced by protocol require statements. Use when the user provides or references a GitHub/protocol repo and asks for example assertions, protection-suite coverage, invariant design, pcl test E2E validation, or assertion workflow guidance.
---

# Write Protection Assertions

## Overview

Use this workflow to turn a protocol reference repository into polished Credible Layer example assertions. The default outcome is fewer assertions with stronger invariants, clear organization, temporary assertion spec cards, and maximum reuse of the existing protection suite.

For detailed classification and quality criteria, read `references/protection-assertion-guide.md` when starting the task or when adding a new suite/category. For assertion spec cards, read `references/assertion-spec-card-template.md` before implementing. For V2 trigger, precompile, and fork-read selection, read `references/v2-precompiles-and-triggers.md` before implementing. For lessons from current assertions, read `references/existing-assertion-lessons.md`. For E2E validation, read `references/e2e-testing-with-pcl.md`. When public Credible Layer behavior, product concepts, or current CLI/test workflow details matter, reference `https://docs.phylax.systems/`. Do not depend on Notion or workspace-local docs for normal assertion-writing tasks; prefer the bundled references and public Phylax docs, then verify against the target repo if it has newer Credible interfaces.

## Workflow

1. **Collect protocol context**
   - Identify the protocol repo, target contracts, deployed addresses if provided, expected chains, and the user-visible protocol category.
   - Inspect interfaces, state variables, accounting flows, admin controls, oracle usage, mutation functions, external token balances, oracle contracts, vault/pool custody, debt/collateral state, and cross-contract dependencies.
   - Prefer source-level understanding over external descriptions. Use GitHub or `git clone` only when the repo is not already available locally.

2. **Load V2 syntax reference**
   - Read `references/v2-precompiles-and-triggers.md`.
   - When the target repo vendors `credible-std` or has current examples, verify exact signatures against its `src/Assertion.sol`, `src/TriggerRecorder.sol`, and `src/PhEvm.sol`.
   - Use the bundled digest and current target-repo examples as syntax exemplars before inventing a new pattern.
   - Do not design V2 Reshiram assertions around custom persistent/stateful assertion storage. Use stateless fork/call reads for invariants; use built-in circuit breaker triggers for rolling-window flow limits.

3. **Review proven implementation patterns**
   - Read `references/existing-assertion-lessons.md` before writing non-trivial assertions.
   - Prefer patterns already proven by the existing suite: assertion/helper/interface split, call-scoped fork comparisons, tx-end envelope checks, explicit selector groups, built-in circuit breakers, and E2E mock knobs that trip one invariant at a time.
   - Keep both assertions and tests small and focused. One assertion should protect one coherent property; one behavior test should prove one expected pass or failure mode.
   - Do not deploy child helper contracts from assertion constructors unless the target runtime explicitly supports them. Prefer inherited helpers/mixins, explicit constructor wiring, or flat test-only assertions for E2E coverage.

4. **Classify before writing**
   - Check whether the protocol fits an existing protection-suite area: `vault`, `lending`, `swaps`, `perpetual`, or `access_control`.
   - If it fits, place examples in that category and inherit/reuse the existing base assertions, trigger helpers, interfaces, and helper structure.
   - If it partially fits, reuse the applicable suite surface and add only protocol-specific helpers/assertions.
   - Create a new category folder only when the protocol model does not belong to an existing suite after a concrete comparison.

5. **Decide whether to extend the base suite**
   - If a reusable invariant, helper, trigger group, or precompile wrapper applies to multiple protocols in the category, modify the base suite instead of duplicating it in one example.
   - Keep protocol-specific selectors, interfaces, thresholds, and idiosyncratic accounting in the example folder.
   - Avoid broad base-suite changes for a one-off property unless the abstraction is clearly reusable and improves readability.

6. **Design high-signal assertions**
   - Prefer 2-5 excellent invariants over broad shallow coverage.
   - Keep each invariant narrow enough to explain in one NatSpec paragraph and one expected revert reason.
   - Target protocol-critical external-state facts: custody versus liabilities, external token balance conservation, share price/exchange-rate behavior, oracle bounds across forks, health-factor safety, liquidation outcomes, cumulative treasury/vault/pool flows, privileged mutation containment, and user balance/share consistency across contracts.
   - Before writing an assertion, inspect the target protocol's `require`/custom-error guards on the relevant path. Avoid properties already fully enforced by those guards; prefer properties spanning post-state, external balances, oracle responses, cross-contract accounting, or call side effects that the protocol itself does not directly require.
   - Treat cumulative inflow/outflow circuit breakers as first-class V2 primitives when rolling-window external balance movement is the risk.
   - Avoid assertions that only restate require checks, duplicate unit tests, confirm a function was called, or encode brittle implementation trivia.

7. **Write assertion spec cards**
   - Before writing Solidity, create one temporary spec card per selected invariant using `references/assertion-spec-card-template.md`.
   - In a coordinated report run, write spec cards under `<protocol>-report/assertions/specs/`.
   - In a standalone assertion task, write spec cards under the requested artifact folder or summarize them in the final response if no artifact folder exists.
   - Each spec must state the trigger, protected functions, state reads, protocol guard overlap, false-positive cases, test plan, and liveness/report relevance.
   - Do not implement an invariant whose spec cannot explain why the property is stronger than existing protocol `require`/custom-error checks.

8. **Organize files for readability**
   - Keep the main assertion contract(s) short and presentable: constructor, `triggers()`, then assertion functions.
   - Put helper functions that retrieve state or protocol data in a separate helper/protocol file when they are not core assertion logic.
   - Put imports in source imports where possible. If helper imports/interfaces become noisy, create a separate protocol/interface/helper file for them.
   - Multiple contracts are fine when the separation matches protocol surfaces or invariant families.

9. **Document intent inline**
   - Every assertion contract must have a short NatSpec summary in a few lines or bullets describing what it protects and why it exists.
   - Every assertion function must have a short NatSpec summary in a few lines or bullets describing the property checked, the trigger context, and the expected failure meaning.
   - Do not use the words "executive summary" in these comments.

10. **Validate**
   - Read `references/e2e-testing-with-pcl.md`.
   - Run the repo's Solidity formatter/build/tests relevant to the changed files.
   - For assertion tests, use `pcl test` as the primary test command; do not rely on `forge test` alone for Credible assertions.
   - Add focused `CredibleTest` E2E coverage when behavior is new or changed: at least one honest passing path and one malicious/failing path for each high-risk assertion function.
   - Keep E2E tests small: arm one assertion, execute one monitored call, and verify one result.
   - If a protocol repo is external and cannot be built locally, still run formatting or static checks in the assertion repo when possible.
   - Summarize what category was chosen, which suite surfaces were reused or extended, and why the final invariant set is intentionally small.

## Output Shape

For coordinated report runs, produce:

- `<protocol>-report/assertions/assertion-surfaces.md`
- `<protocol>-report/assertions/specs/<InvariantName>.md`
- `<protocol>-report/assertions/files-changed.md`
- `<protocol>-report/assertions/test-results.md`

When implementing in `credible-std`, prefer paths like:

- `src/protection/<category>/examples/<Protocol>Assertion.sol`
- `src/protection/<category>/examples/<Protocol>Helpers.sol`
- `src/protection/<category>/examples/<Protocol>Interfaces.sol`
- `test/protection/<category>/<Protocol>Assertion.t.sol`

Use the existing category naming and local file style. Do not invent a parallel layout unless the repository already has moved to a newer pattern.

## Quality Bar

Before finishing, verify:

- The protocol category decision is explicit and defensible.
- Existing protection-suite code is reused before writing custom logic.
- Each selected invariant has a spec card before Solidity is written.
- Any base-suite change benefits more than one protocol or removes meaningful duplication.
- Assertions read like protocol properties, not implementation spelunking.
- Assertions are small and focused; tests are small and focused.
- Assertion tests arm `cl.assertion` immediately before the monitored call and cover both passing and tripping behavior where practical.
- `pcl test` validation is run or a blocker is reported.
- Assertion contracts and assertion functions each include a short summary comment without the words "executive summary".
- Helper files contain retrieval/decoding/state-access logic, while assertion contracts remain focused.
- Imports are direct and local; no hidden mega-files unless they improve readability.
- Revert reasons and NatSpec make failures presentable to users.
