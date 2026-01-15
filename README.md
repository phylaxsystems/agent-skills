# Phylax Assertion Agent Skills

A collection of skills for AI coding agents writing Phylax Credible Layer assertions.
Skills follow the Agent Skills format.

## Available Skills

### designing-assertions
Derive invariants and map them to precise triggers.

Use when:
- Scoping a new assertion suite
- Translating protocol rules into invariants
- Choosing call vs storage vs balance triggers

### implementing-assertions
Implement assertion contracts with cheatcodes, traces, and storage access.

Use when:
- Writing assertion Solidity
- Optimizing or refactoring assertion logic
- Handling call inputs, logs, or slots

### testing-assertions
Build unit, fuzz, and harness tests for assertions.

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

Copy the skill folders into your agent skills directory.

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
