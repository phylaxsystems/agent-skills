# Phylax Assertion Agent Skills

A collection of skills for AI coding agents writing Phylax Credible Layer assertions.
Skills follow the Agent Skills format.

## Available Skills

### write-protection-assertions
Latest consolidated workflow from `agentic-engineering` for building Credible Layer protection assertions.

Use when:
- Classifying a protocol against the protection suite
- Designing 2-5 high-signal external-state invariants
- Implementing and validating assertion examples with `pcl test`

### credible-assertion-integration-tests
Assertion-driven integration testing workflow for Credible SDK, `credible-std`, executor, sidecar, and assertion-verification changes.

Use when:
- Changing precompiles, trigger semantics, assertion specs, or sidecar behavior
- Proving behavior with real assertion bytecode
- Choosing between executor, Foundry assertion-project, and LocalInstance tests

### mapping-invariants
Intro workflow for mapping invariants before writing assertions.

Use when:
- Starting a new protocol
- Building the invariant matrix
- Deciding the step‑by‑step plan

### designing-assertions
Derive invariants and map them to precise triggers.

Use when:
- Scoping a new assertion suite
- Translating protocol rules into invariants
- Choosing V2 function-call, tx-end, ERC20-change, cumulative-flow, or storage triggers

### implementing-assertions
Implement V2 assertion contracts with triggers, fork-aware reads, call context, traces, and storage access.

Use when:
- Writing assertion Solidity
- Optimizing or refactoring assertion logic
- Handling call inputs, logs, or slots

### optimize-assertion-triggers
Narrow assertion trigger selection without weakening the protected invariant.

Use when:
- An assertion fires too often or relies on broad `onFnCall`/`registerFnCallTrigger` coverage
- Reviewing or refactoring `triggers()` to lower execution overhead
- Preferring `onTxEnd`, ERC20-change, storage-change, or cumulative-flow triggers where they cover the same paths

### testing-assertions
Build focused `CredibleTest`, fuzz, and harness tests for assertions.

Use when:
- Writing `CredibleTest` tests
- Adding fuzz coverage
- Diagnosing false positives

### backtesting-assertions
Backtest assertions against historical transactions.

Use when:
- Validating on real chain data
- Replaying known exploits
- Debugging trigger mismatches in production paths

### pcl-assertion-workflow
End-to-end setup, test, store, submit, and deploy with `pcl`.

Use when:
- Bootstrapping a new assertions project
- Storing and submitting assertions
- Deploying via the dApp

### assertion-troubleshooting
Diagnose non-triggering assertions and common failures.

Use when:
- Seeing "Expected 1 assertion to be executed, but 0 were executed"
- Hitting OutOfGas or selector mismatches
- Debugging call input duplication

## Installation

The easiest option is the `npx` installer:

```bash
npx add-skill phylaxsystems/agent-skills
```

Manual install (copy the skill folders into your agent skills directory):

```bash
# Claude Code
cp -r skills/* ~/.claude/skills/

# Codex CLI
cp -r skills/* "$CODEX_HOME/skills/"
```

## Usage

Skills are automatically used when relevant tasks are detected. You can also invoke them by name.

Examples:
```
Use designing-assertions to map invariants for this protocol
```
```
Backtest this assertion on the exploit block
```

## Skill Structure

Each skill contains:
- `SKILL.md` - instructions for the agent
- `references/` - supporting docs (optional)
