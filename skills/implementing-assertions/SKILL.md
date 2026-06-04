---
name: implementing-assertions
description: "Phylax Credible Layer assertions implementation. Implements V2 Credible Layer assertion contracts using triggers, fork-aware precompiles, call context, and focused helper structure."
---

# Implementing Assertions

Turn a written invariant spec into a correct, gas-safe V2 assertion contract.

## When to Use
- Writing a new assertion contract from a defined invariant.
- Refactoring or optimizing existing assertions.
- Adding V2 trigger logic, call input/output parsing, fork-aware reads, event/state checks, or circuit breakers.

## When NOT to Use
- You only need invariant ideation or trigger selection. Use `designing-assertions`.
- You only need testing patterns. Use `testing-assertions`.

## Quick Start
Before writing code, read `references/v2-precompiles-and-triggers.md` and copy the exact signatures from the target repo's vendored `credible-std` when present.

For new assertions:
1. Inherit `Assertion` from `credible-std`.
2. Register narrow V2 triggers in `triggers()`: `registerFnCallTrigger`, `registerTxEndTrigger`, `registerErc20ChangeTrigger`, `watchCumulativeInflow`, or `watchCumulativeOutflow`.
3. Use `ph.context()` only inside a `registerFnCallTrigger` assertion.
4. Use fork-aware reads (`ph.staticcallAt`, `ph.loadStateAt`, `_preTx()`, `_postTx()`, `_preCall(id)`, `_postCall(id)`) instead of legacy fork switching.
5. Keep each assertion function focused on one protocol property and put retrieval/decoding logic in helpers.

## File and Naming Conventions
- **Assertion files**: `{ContractOrFeature}Assertion.a.sol` (e.g., `VaultOwnerAssertion.a.sol`)
- **Test files**: `{ContractOrFeature}Assertion.t.sol` (e.g., `VaultOwnerAssertion.t.sol`)
- **Assertion functions**: use clear property names such as `assertPoolCustodyCoversBalances`, `assertPostOperationSolvency`, or `assertSharePriceEnvelope`.
- **Directory structure**: `assertions/src/` for assertion contracts, `assertions/test/` for tests

```solidity
contract MyAssertion is Assertion {
    address immutable target;

    constructor(address target_) {
        target = target_;
    }

    function triggers() external view override {
        registerTxEndTrigger(this.assertAccountingEnvelope.selector);
        registerFnCallTrigger(this.assertPerCallRisk.selector, ITarget.borrow.selector);
    }

    function assertAccountingEnvelope() external {
        PhEvm.ForkId memory post = _postTx();
        uint256 liabilities = _readUint(target, abi.encodeCall(ITarget.totalLiabilities, ()), post);
        uint256 assets = _readUint(target, abi.encodeCall(ITarget.totalAssets, ()), post);
        require(assets >= liabilities, "Target: assets below liabilities");
    }

    function assertPerCallRisk() external {
        PhEvm.TriggerContext memory ctx = ph.context();
        PhEvm.ForkId memory postCall = _postCall(ctx.callEnd);
        bytes memory input = ph.callinputAt(ctx.callStart); // raw calldata: selector + args
        // Decode operation context and check the post-call protocol property.
    }

    function _readUint(address account, bytes memory data, PhEvm.ForkId memory fork)
        internal
        view
        returns (uint256 value)
    {
        PhEvm.StaticCallResult memory result = ph.staticcallAt(account, data, 50_000, fork);
        require(result.ok, "Target: read failed");
        value = abi.decode(result.data, (uint256));
    }
}
```

## Implementation Checklist
- **Triggers**: use the narrowest useful V2 trigger. Prefer `registerFnCallTrigger(fn, selector)` for per-operation properties and `registerTxEndTrigger(fn)` for whole-transaction envelopes.
- **Circuit Breakers**: use `watchCumulativeOutflow` or `watchCumulativeInflow` for rolling-window flow limits instead of custom assertion storage.
- **One Property, One Assertion**: avoid broad dispatchers. Register selector groups explicitly and keep one coherent failure meaning per assertion function.
- **Interface Clarity**: use selectors from the interface that declares the protected function; call out inherited selectors when the adopter uses ERC20/ERC4626 surfaces.
- **Fork Reads**: use `ph.staticcallAt` and `ph.loadStateAt` with `_preTx()`, `_postTx()`, `_preCall(ctx.callStart)`, and `_postCall(ctx.callEnd)`.
- **Call Context**: use `ph.context()` only for `registerFnCallTrigger` assertions; use `ph.callinputAt(ctx.callStart)` and `ph.callOutputAt(ctx.callStart)` for input/output-dependent checks.
- **Call Input Shape**: `ph.callinputAt` returns raw calldata including the selector. Strip the first 4 bytes before `abi.decode` unless your helper expects full calldata.
- **Event Parsing**: filter by `emitter` and `topics[0]`; decode indexed vs data fields correctly.
- **Storage Slots**: use `ph.loadStateAt` for EIP-1967 slots, packed fields, and mappings; derive slots from source or `forge inspect <Contract> storage-layout`.
- **State Changes**: `getStateChanges*` includes the initial value at index 0; length 0 means no changes.
- **Constructors**: keep constructor work simple. Pass important addresses and thresholds in; do not deploy child helpers from assertion constructors unless the target runtime explicitly supports it.
- **Nested Calls**: avoid double counting; use `ph.matchingCalls` or legacy call-input helpers deliberately and cap result sizes.
- **Internal Calls**: internal Solidity calls are not traced; register on external entrypoints or explicit `this.` calls when you need call context.
- **Tolerances**: use minimal, documented tolerances for price/decimals rounding.
- **Optional Interfaces**: use `staticcall` probing and skip when unsupported.
- **Token Quirks**: validate using balance deltas; handle fee-on-transfer and rebasing tokens.
- **Packed Calldata**: decode using protocol packing logic and guard invalid ids before applying invariants.
- **Sentinel Amounts**: normalize `max`/sentinel values (e.g., full repay/withdraw) using pre-state.
- **Gas**: assertion gas cap is 300k; happy path is often most expensive; early return, cache reads, and limit loops.
- **Size Limit**: organize assertions by domain (e.g., access control, timelock, accounting) and split if you hit `CreateContractSizeLimit`.
- **NatSpec**: add a short summary to each assertion contract and assertion function that explains the protected property, trigger context, and failure meaning.

## Anti-Patterns

### Dispatcher Pattern To Avoid
Do not route unrelated trigger families through one assertion function that dispatches to helpers:
```solidity
function triggers() external view override {
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.setFee.selector);
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.setGuardian.selector);
    registerFnCallTrigger(this.assertAdminMutation.selector, IVault.submitCap.selector);
}

function assertAdminMutation() external {
    // Dispatches internally based on what was called.
}
```

### Preferred Shape
Register separate assertion functions when failure meanings differ. Share helpers for common reads:
```solidity
function triggers() external view override {
    registerFnCallTrigger(this.assertSetFeeBounds.selector, IVault.setFee.selector);
    registerFnCallTrigger(this.assertGuardianChangeSafe.selector, IVault.setGuardian.selector);
}

function assertSetFeeBounds() external {
    _checkFeeBounds();
}

function assertGuardianChangeSafe() external {
    _checkGuardianState();
}
```

### Mixed Interfaces To Avoid
Do not mix selectors from parent and child interfaces:
```solidity
registerFnCallTrigger(this.assertDeposit.selector, IERC4626.deposit.selector);
registerFnCallTrigger(this.assertSubmitCap.selector, IVault.submitCap.selector);
```

Use the adopter's interface consistently:
```solidity
registerFnCallTrigger(this.assertDeposit.selector, IVault.deposit.selector);
registerFnCallTrigger(this.assertSubmitCap.selector, IVault.submitCap.selector);
```

## Rationalizations to Reject
- "Legacy fork switching is easier." V2 fork-aware reads are clearer and safer for new assertions.
- "Custom assertion storage can track rolling windows." Use built-in cumulative flow triggers for V2 circuit breakers.
- "Use getAllCallInputs everywhere." It can double-count proxy calls.
- "Many selectors can share one assertion dispatcher." It hurts gas and makes debugging harder.
- "I can ignore nested calls." Batched flows are common and must be handled.
- "Events are enough." If events can be skipped, back them with state checks.
- "We can rely on storage layout guesses." Always derive slots from layout.

## References
- [Cheatcodes and Traces](references/cheatcodes-and-traces.md)
- [V2 Precompiles and Triggers](references/v2-precompiles-and-triggers.md)
- [Existing Assertion Lessons](references/existing-assertion-lessons.md)
- [Storage Layouts and Slots](references/storage-layouts-and-slots.md)
- [Event Parsing](references/event-parsing.md)
- [Tolerance and Rounding](references/tolerance-and-rounding.md)
- [Token Integration Safety](references/token-integration-safety.md)
