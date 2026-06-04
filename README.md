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

### npm (recommended)

The skills are published to npm as [`@phylax-systems/agent-skills`](https://www.npmjs.com/package/@phylax-systems/agent-skills) with a bundled installer CLI. No clone required:

```bash
# Interactive: pick skills and target agents
npx @phylax-systems/agent-skills install

# Install everything into all detected agents (Claude Code, Codex, opencode)
npx @phylax-systems/agent-skills install all

# Install one skill into specific agents
npx @phylax-systems/agent-skills install optimize-assertion-triggers --agent claude-code --agent codex

# List available skills
npx @phylax-systems/agent-skills list
```

Targets resolve automatically:

| Agent | Install location |
| --- | --- |
| `claude-code` | `~/.claude/skills/` |
| `codex` | `$CODEX_HOME/skills/` (or `~/.codex/skills/`) |
| `opencode` | `~/.config/opencode/skills/` |

Use `--dir <path>` to install under a custom root and `--force` to overwrite existing skills.

You can also install globally:

```bash
npm install -g @phylax-systems/agent-skills
agent-skills install all
```

### Manual install

Copy the skill folders into your agent skills directory:

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
- `agents/openai.yaml` - Codex UI metadata (optional)
- `references/` - supporting docs (optional)

## Development

The installer bundles every folder under `skills/` from a generated manifest.

```bash
npm install        # no runtime dependencies; installs dev tooling only
npm run build:manifest   # regenerate src/manifest.json from skills/
npm test           # build manifest + run the test suite
```

After adding or editing a skill, regenerate and commit `src/manifest.json`
(`npm run build:manifest`). CI fails if the committed manifest is stale.

### Publishing

Releases publish to npm automatically. Bump `version` in `package.json`, then
push a matching semver tag:

```bash
git tag 0.1.0
git push origin 0.1.0
```

The release workflow verifies the tag matches `package.json`, runs the tests,
creates a GitHub release, and runs `npm publish --access public`. Publishing
requires an `NPM_TOKEN` repository secret with publish rights to the
`@phylax-systems` org.
