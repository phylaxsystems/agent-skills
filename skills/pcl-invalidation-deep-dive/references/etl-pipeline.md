# PCL Invalidation ETL Pipeline

Use this reference for detailed local PCL invalidation investigations. Keep the final user answer short; use this to avoid missing evidence.

The production agentic triage feature has two goals:

- Make transaction and assertion traces understandable to humans.
- Produce a triage report that explains what the dropped transaction attempted, why the assertion invalidated it, whether the transaction looks malicious, and what action the user should take.

This skill implements that flow locally using `pcl`, keyless/public or keyed RPC, Sourcify/4byte/explorer source lookups, `cast`, and local artifacts.

Keyless means no third-party RPC, explorer, source, or decompiler API keys. Live PCL incident discovery still requires PCL platform auth unless the operator starts from exported incident/trace artifacts or a prebuilt evidence packet.

## Stage 0: Intake

Capture:

- User question and intended scope: latest, date range, all history, one incident, one tx, or live exposure.
- Timezone and exact UTC cutoff.
- Project name/slug/id, incident id, chain, adopter, assertion, tx hash, or address.
- Whether the user wants internal triage, public incident copy, customer update, or exact accounting.

If scope is ambiguous and a reasonable default exists, proceed and label it. For "June", use June-to-date and state UTC/local boundaries.

## Stage 1: Source Discovery

Primary PCL commands:

```bash
pcl --version
pcl doctor --toon
pcl auth ensure --toon
pcl workflows show incident-investigation --toon
pcl search --query <project-or-protocol> --toon
pcl incidents --project-id <project-id-or-slug> --environment production --from-date <iso> --to-date <iso> --all --limit 50 --toon
pcl export incidents --project-id <project-id> --environment production --out incidents.jsonl --errors errors.jsonl --checkpoint checkpoint.json --resume --continue-on-error --toon
pcl incidents --incident-id <incident-id> --toon
pcl incidents --incident-id <incident-id> --tx-id <invalidating-transaction-id> --toon
pcl requests list --limit 20 --toon
```

Record:

- `project_id`, slug, chain id/name.
- `incident_id`, `window_start`, `created_at`, public reference id.
- `assertion_id`, assertion title, assertion adopter id/address.
- `transaction_count`, `traces_completed`, `traces_pending`.
- For each invalidating tx: id, hash, from/to, value, block number, timestamp, `landed_on_chain`, revert reason, trace status/error.
- PCL response request ids for failures.

Important: list rows can be stale or less complete than incident detail. Treat `pcl incidents --incident-id` detail as authoritative for transaction ids/status unless proven otherwise.

Prefer `--toon` for agent inspection because it is compact and preserves request metadata. Use `--json` when a local parser needs strict JSON. When writing artifacts, verify the file was actually created and inspect its shape:

- `pcl incidents ... --output <file> --json` can write only the response `data` payload, not the full envelope.
- `pcl export incidents` writes list/index rows to JSONL; it does not replace detail and trace calls.
- Detail/trace commands may need stdout capture if `--output` does not create a file in the current CLI version.

Identity keys:

- Use `(incident_id, invalidating_transaction.id)` for investigation records.
- Treat `transaction_hash` as evidence, not the primary row key. Repeated simulated invalidations can reuse the same hash while differing by PCL tx id, block number, incident window, or trace status.
- Keep block number with every row; the same calldata/hash can be evaluated at different block contexts.

## Stage 1A: Capability Preflight

Before source collection or root-cause analysis, run the local requirements gate for the target chain:

```bash
scripts/check_triage_requirements.py --chain-id <chain-id> --json
scripts/check_triage_requirements.py --chain-id <chain-id> --no-api-keys
scripts/check_triage_requirements.py --chain-id <chain-id> --no-api-keys --require-decompiler
scripts/check_triage_requirements.py --chain-id <chain-id> --require-explorer
```

Use auto-discovery for normal triage. The JSON report includes `capability_selection`:

- `mode=private-or-mixed`: configured/private RPC or keyed explorer access is available. Use it first, then fallback to public RPC/Sourcify/4byte/Heimdall for missing surfaces.
- `mode=keyless-public`: no configured/private endpoints were found, but a public RPC works. Proceed without asking for keys and report archive/debug/account-history limitations.
- `mode=blocked`: no working RPC was found. Stop unless the user accepts degraded source-only analysis.

Use `--no-api-keys` only when the operator wants a no-key proof or when auto-discovery finds no private endpoints. Use `--require-decompiler` when unverified code, created/transient contracts, or source-dependent RCA makes decompiler access necessary. Use keyed explorer mode only when Sourcify/decompilation or public RPC leaves a material gap.

Before collecting source or replay context, show a short capability note:

```text
Capability mode: <private-or-mixed|keyless-public|blocked>.
Configured/private RPC: <yes/no>. Keyed explorer: <yes/no>. Public RPC fallback: <yes/no>.
Proceeding with <mode>; expected gaps: <archive/debug/account-history/source labels/etc>.
```

Exit code `2` means local requirements are missing. Surface the report verbatim to the operator because it explains:

- which capability is missing
- why it is required
- which public fallback, flag, local tool, or environment variable can satisfy it

Do not continue into root-cause analysis after a failed preflight unless the user explicitly accepts a degraded report. When continuing in degraded mode, list the missing capability in `Open Gaps and Confidence`.

## Stage 2: Local Context Packet

Build a local context packet before reasoning. Store large artifacts as files under `/tmp/<project-or-incident>/` or the current workspace.

Required context:

- PCL incident detail.
- Invalidating transaction object and attributes.
- Transaction execution trace.
- Assertion execution trace.
- Previous transaction from the same sender before the invalidation.
- Receipt/logs if the tx landed or has a comparable on-chain tx.
- All touched contract addresses in the transaction trace.
- Source/ABI for all touched contracts when verified source is available.
- Source/ABI for contracts created during the transaction.
- Decompiled or reconstructed code for important unverified code-bearing contracts when verified source is unavailable.
- Asset metadata for token/NFT/vault/share contracts in calls/logs.
- Relevant block-pinned state reads: balances, allowances, owners/operators, vault shares, protocol account state, or storage slots used by the assertion.

Optional context:

- Explorer labels.
- Keyed account-history API data.
- Tenderly/Phalcon visual trace.
- Heimdall-rs decompiler output when verified source is unavailable.
- Related txs before/after the invalidation from the same sender, recipient, or route.

Context packet checklist:

```text
readiness_pcl_doctor.toon
incident_index.json or incident_index.jsonl
incident.json
invalidating_tx_<pcl_tx_id>.json
trace_<incident_id>_<pcl_tx_id>.json
normalized_traces.json
trace_<txid>.txt
assertion_trace_<txid>.txt
tx_object_<hash>.json
receipt_<hash>.json
previous_tx_<sender>.json
touched_contracts.json
sources/<chain>/<address>/*
contract_context/<chain>/<address>/bytecode.txt
contract_context/<chain>/<address>/etherscan_source.json
contract_context/<chain>/<address>/sourcify_contract.json
contract_context/contract_context_manifest.json
decompiled/<chain>/<address>/*
token_metadata.json
balances_allowances.json
ownership_operator_state.json
protocol_state_reads.json
```

After the raw artifacts and targeted state reads exist, build a compact report-agent packet:

```bash
scripts/build_evidence_packet.py \
  --run-dir <run-dir> \
  --project <project-slug> \
  --project-id <project-id> \
  --chain-id <chain-id> \
  --incident-id <incident-id> \
  --pcl-tx-id <pcl-tx-id> \
  --incident-json incident.json \
  --trace-json trace_<incident-id>_<pcl-tx-id>.json \
  --normalized-json normalized_traces.json \
  --contract-context contract_context/contract_context_manifest.json \
  --decompilation-manifest decompiled/heimdall_decompilation_manifest.json \
  --aux-file "state reads=state_reads.json" \
  --aux-file "previous sender txs=previous_tx.json" \
  --aux-file "price snapshot=prices.json" \
  --out evidence_packet.md
```

Use `evidence_packet.md` as the primary input for report writing or spawned report agents. The report agent should read listed auxiliary state/receipt/price/previous-transaction files before doing live RPC or explorer calls, and should open raw JSON only to verify exact call order, quote exact trace lines, or resolve explicit gaps. Do not refetch PCL list/detail/trace data when the packet already lists consistent artifacts.

Fast packet-only report targets:

- Finish one completed-trace report in under 90 seconds after reading the packet.
- Prefer the deterministic renderer first:
  `scripts/render_fast_report.py --packet evidence_packet.md --run-dir <run-dir> --out final_report.md`.
- Use only packet and auxiliary files by default.
- Treat missing non-critical checks as gaps instead of live-fetching them.
- Keep the main report around 1,200-1,800 words.
- Use a concise 10-18 step `Full Improved Trace`; avoid dumping every storage write or every previous transaction.

## Stage 2A: Fast Batching and Split-Agent Pipeline

The local skill should preserve production feature parity without loading every raw artifact into the model.

For one to five invalidating txs:

- Run the full prefetch and packet-builder path for each tx before report writing.
- Hand spawned report agents only the compact packet plus necessary artifact paths, not the entire conversation or every raw trace.
- Include every improved trace unless they are near-identical retries.

For larger windows:

- First build a compact index from PCL list/detail rows.
- Group by route/signature before trace narration.
- Fully analyze one representative completed trace per group, plus any failed/no-trace or materially different tx.
- Keep all raw PCL trace/source/RPC artifacts on disk.
- Preserve complete coverage in a transaction-object table keyed by `(incident_id, pcl_tx_id)`.

Suggested route/signature:

```text
(outer_target, outer_selector, adopter, assertion_id, touched_assets_or_state, source_accounts, beneficiaries, decoded_revert_reason)
```

When a multi-agent runner is available and the user asks for a deep pass, split the pipeline:

- **Root-cause agent**: receives PCL detail/traces, source/decompiler manifest, previous txs, and normalized movements; returns mechanism, actors, confidence, and gaps.
- **Replay agent**: receives tx objects and RPC config; runs `cast`/RPC checks for tx, receipt/logs, calldata, balances, allowances, and replayability; returns commands, outputs, and failures.
- **Packet builder**: writes `evidence_packet.md` from saved artifacts and appends links to replay/state-read outputs.
- **Report agent**: receives only the compact evidence packet, selected raw artifact paths, and explicit gaps; writes the production invalidation-detail artifact.

If no runner is available, run the phases sequentially. Keep the same handoff boundary so the final report does not invent evidence the RCA or replay phase did not produce.

## Stage 3: Trace Extraction

For each transaction trace:

- Strip ANSI before parsing.
- If `transaction_trace_content` and `assertion_trace_content` are null, split combined `trace_content` on headings such as `Transaction Trace` and `Assertion Trace`.
- Save trace JSON artifacts with both the incident id and PCL transaction id in the filename. Some trace endpoints return the PCL transaction object but not the incident id; the normalizer can infer full UUIDs from `trace_<incident-id>_<pcl-tx-id>.json` filenames.
- Prefer running `scripts/normalize_pcl_trace.py --pretty trace_*.json > normalized_traces.json` before manual reasoning. It extracts non-delegatecall token calls, ERC20/ERC721/ERC1155/WETH/ERC4626 events, event-level deltas, non-fungible movements, and allowance checks into JSON. Treat it as a parsing aid, not a replacement for raw trace inspection.
- Count only non-delegatecall calls/events for direct attempted movement accounting.
- Prefer emitted asset/protocol events and executed calls over raw calldata guesses.
- Preserve raw assertion and transaction trace sections as artifacts, but combine them into one ordered `Full Improved Trace` in the final report.
- Preserve revert reason.

For asset-movement attempts, extract:

- asset contract and standard when known
- source owner/from
- recipient/to/beneficiary
- raw amount for fungible assets, token id for ERC721/ERC1155, or state key for protocol-state changes
- event-level balance deltas from ERC20 `Transfer`, WETH `Deposit`/`Withdrawal`, ERC4626 `Deposit`/`Withdraw`, and non-fungible transfer events
- decimals or asset id metadata
- tx hash/id
- incident id/window

Role mapping:

- Do not infer the victim/source from `transaction_data.from_address`.
- Extract source owners from executed calls and emitted events, such as `transferFrom(source, recipient, amount)`, `Transfer(from, to, amount)`, `ownerOf(tokenId)`, or protocol account/state reads.
- Track transaction sender, outer call target, created contracts, assertion adopter/spender, asset owner, protocol account, recipient/beneficiary, and privileged caller as separate roles.
- For exposure checks, query the state relevant to the mechanism: balances and allowances for fungible drains, owner/operator approvals for NFTs/ERC1155s, vault shares/assets for ERC4626, and protocol storage/account state for custom assertions.

Avoid double counting:

- delegatecall mirror lines
- downstream consolidation transfers from attacker-controlled recipient
- swap output transfers
- approvals
- repeated balance reads
- bridge/router internal accounting transfers
- protocol internal bookkeeping that does not change external ownership or extractable value

## Stage 4: Trace Readability Enrichment

Produce a readable trace summary even when raw trace output is noisy.

Resolve names:

- Contract source name from explorer source metadata.
- Asset symbol/name/decimals/token ids from token standards or metadata calls.
- Common router/pool names from explorer labels.
- Created contract names from source or bytecode/decompiler hints.

Decode events and common calls:

- ERC20: `Transfer`, `Approval`, `transfer`, `transferFrom`, `approve`.
- ERC721: `Transfer`, `Approval`, `ApprovalForAll`, `ownerOf`, `getApproved`, `isApprovedForAll`, `safeTransferFrom`.
- ERC1155: `TransferSingle`, `TransferBatch`, `ApprovalForAll`, `balanceOf`, `safeTransferFrom`.
- WETH-like: `Deposit`, `Withdrawal`.
- ERC4626: `Deposit`, `Withdraw`.
- Router/vault/bridge/lending calls: `swap`, `exactInput`, `deposit`, `withdraw`, `borrow`, `repay`, `liquidate`, `bridge`, `claim`, and protocol-specific settlement calls.
- Assertion calls and revert reason.

Formatting rules:

- Show names as `Name (0x...)` the first time.
- Trim normal token amounts to 6 decimals.
- Preserve raw amount or extra decimals only when the amount is dust, a boundary, or used in an exact comparison.
- Keep raw trace snippets short; summarize repeated identical attempts.

Readable trace line example:

```text
USDC.transferFrom(from: 0xaaa..., to: ProtectedSpender, amount: 1,071.751815 USDC)
ERC721.Transfer(from: 0xbbb..., to: 0xccc..., tokenId: 42)
```

Readable balance-change row example:

```text
balance_change token=USDC event=ERC20.Transfer address=0xaaa... delta=-1,071.751815 USDC raw=-1071751815
asset_movement token=CoolNFT event=ERC721.Transfer from=0xbbb... to=0xccc... token_id=42
```

## Stage 4A: Source and Decompiler Context

Before root-cause analysis, collect context for every code-bearing contract in the invalidating execution path.

Address collection:

- Include every address from transaction objects, transaction traces, assertion traces, created-contract lines, token proxy calls, implementation delegatecalls, assertion/runtime helper calls, emitted logs, and explicit calldata-decoded contract arguments.
- Use RPC `eth_getCode` to classify addresses as contract vs EOA. Do not try to fetch source for EOAs.
- Keep proxy and implementation addresses separate; both can matter.
- Keep transient/created contracts even if they have no explorer source. Their bytecode/decompile often explains malicious routing.
- If the tx was invalidated before landing, a created contract may appear in the PCL simulation trace but have no deployed bytecode at `eth_getCode(latest)`. Treat that as a distinct created-contract evidence gap, not as an ordinary EOA.

Recommended command:

```bash
scripts/collect_contract_context.py \
  --chain-id <chain-id> \
  --out-dir contract_context \
  trace_*.json
```

The helper extracts trace addresses, fetches runtime bytecode through explicit/env/provider/public RPC, tries Sourcify verified contract lookup, optionally tries Etherscan V2 `getsourcecode` when not in `--no-api-keys` mode and a key is configured, and writes `contract_context_manifest.json`. Review its `decompiler_targets` before writing the RCA.

By default the helper refuses to run without JSON-RPC because `eth_getCode` is required for contract/EOA classification, bytecode capture, and decompiler target discovery. If no explicit/env/keyed/public RPC works, it exits with a requirements block that names the chain id and the accepted configuration options. Use `--allow-missing-rpc` only for an explicitly degraded source-only packet, and then record the missing RPC as a confidence gap.

Keyless source command when `capability_selection.mode=keyless-public` or when proving no-key operation:

```bash
scripts/collect_contract_context.py \
  --chain-id <chain-id> \
  --no-api-keys \
  --out-dir contract_context \
  trace_*.json
```

Keyed upgrade when keyless source leaves a material gap:

```bash
scripts/collect_contract_context.py \
  --chain-id <chain-id> \
  --out-dir contract_context_keyed \
  trace_*.json
```

For bytecode-backed decompiler targets, run Heimdall-rs:

```bash
scripts/run_heimdall_decompiler.py \
  contract_context/contract_context_manifest.json \
  --out-dir decompiled \
  --require-success
```

Configuration:

- Install `heimdall` on PATH.
- Or set `HEIMDALL_BIN=/absolute/path/to/heimdall`.

The runner executes:

```bash
heimdall decompile <runtime-bytecode> --default --include-sol --output print
```

It writes `decompiled/<chain>/<address>/stdout.txt`, `stderr.txt`, `output.txt`, `source.sol` when Solidity-like output is detected, `heimdall.json`, and `decompiled/heimdall_decompilation_manifest.json`.

If a decompiler target has `bytecode_path: null` because the address was created only in the simulated trace, recover init/runtime bytecode from one of:

- PCL trace creation output, if present.
- The outer transaction calldata and verified/decompiled deployer code.
- `cast run`, `trace_call`, or `debug_traceCall` against the same block context.
- A visual trace tool such as Tenderly/Phalcon.

Do not claim what a temporary contract did solely from its address or label.

Source/decompiler fallback order:

1. Sourcify verified contract data.
2. Verified source and ABI from Etherscan V2 or a chain-specific explorer when keys are configured.
3. Known local labels/ABIs from the project or token metadata.
4. Heimdall-rs for code-bearing addresses without verified source.
5. If no decompiler is configured, store bytecode and list the address as an unresolved source/decompiler gap.

Heimdall notes:

- Heimdall-rs is the only supported decompiler in this skill. That keeps the local triage path fast, deterministic, and easy to test.
- If Heimdall is unavailable, do not substitute another decompiler in the skill run. Record the missing source/decompiler context as a gap and continue only if the user accepts degraded confidence.
- Label decompiled or AI-reconstructed code as approximate. Use it for control-flow, selector, storage, and routing hypotheses, then validate critical claims against trace/RPC evidence.

RCA source-context rule:

- Do not claim a root cause that depends on wrapper/deployer/router logic until that contract has verified source, decompiled code, or an explicit source gap in the report.
- If an important contract is unresolved, state what conclusion is still trace-backed and what remains unknown.

## Stage 5: Failed or Pending Traces

Classify unavailable traces:

- `pending`: not ready; totals are temporary.
- `failed`: retry may require project admin/editor; preserve tx ids and request ids.
- API 500/403: report exact API error and whether retry was attempted.

Do not rely only on list-level `traces_completed` and `traces_pending`. Inspect each transaction's `debug_traces[].status`; an incident can show `traces_completed=0` and `traces_pending=0` while the transaction has a failed debug trace and no `trace_content`.

Fallback order:

1. Re-query detail once.
2. If user authorized or permissions allow, retry trace generation.
3. Decode calldata selectors and verified ABI.
4. Use external RPC simulation/trace if possible.
5. Otherwise report as unpriced/unverified gap.

Never claim exact protected value for failed traces unless the attempted transfer is independently decoded and verified.

## Stage 6: External Chain Evidence

Use chain data to validate PCL:

- RPC `eth_getTransactionByHash` and receipt.
- `debug_traceTransaction`, `trace_transaction`, or `trace_call` with block context.
- Logs by tx and token `Transfer` event topics.
- Asset balances, allowances, owners/operators, and relevant protocol state at the relevant block and latest block.
- Contract source/ABI from Etherscan v2 or the chain explorer.
- Contract creation tx and labels for attacker, recipient, router, adopter, token, pool, bridge.

Useful environment variables:

- `ALCHEMY_API_KEY`
- `ETHERSCAN_API_KEY`
- `EXPLORER_API_KEY`
- `BLOCKSCOUT_API_KEY`
- `LINEASCAN_API_KEY`
- `BASESCAN_API_KEY`
- `ARBISCAN_API_KEY`
- chain-specific RPC overrides such as `LINEA_RPC_URL`
- generic chain-id RPC overrides such as `CHAIN_<chain_id>_RPC_URL`, `RPC_URL_<chain_id>`, or `EVM_<chain_id>_RPC_URL`

RPC discovery order:

1. Explicit `--rpc-url`.
2. Explicit chain RPC env var, such as `LINEA_RPC_URL`.
3. Generic chain-id RPC env var, such as `CHAIN_59144_RPC_URL`.
4. Generic `RPC_URL`.
5. Derived Alchemy URL from `ALCHEMY_API_KEY` when the chain is known, unless `--no-api-keys` is set.
6. Public RPC fallback for supported chains. Use it for basic reads and label it as non-archive/non-debug unless verified otherwise.

When `ALCHEMY_API_KEY` exists but no explicit RPC URL is set, derive the chain endpoint from chain id/name only when the helper has a known mapping. Do not guess provider hostnames for unknown chains.

```bash
https://<known-alchemy-host>/v2/$ALCHEMY_API_KEY
```

Check only whether secrets are present; do not print API keys in reports or artifacts. In `--no-api-keys` mode, ignore provider/explorer keys even if they exist in the shell so the run proves the keyless path. Do not claim an env var is missing unless you checked it in the current shell.

Explorer/source lookup order:

1. Sourcify `/server/v2/contract/<chain-id>/<address>?fields=all` for no-key verified source/ABI.
2. `cast 4byte <selector>` or 4byte.directory for no-key selectors/events.
3. Etherscan v2 if `ETHERSCAN_API_KEY` is available and the chain id is supported.
4. Chain-specific or Blockscout-style explorer API if configured.
5. Public explorer links for manual follow-up.
6. Heimdall-rs only when verified source is unavailable and deeper root cause requires it.

Useful source/ABI shape:

```bash
curl -fsS "https://api.etherscan.io/v2/api?chainid=<chain_id>&module=contract&action=getsourcecode&address=<address>&apikey=$ETHERSCAN_API_KEY"
cast 4byte <selector>
```

Previous transaction lookup:

```bash
curl -fsS "https://api.etherscan.io/v2/api?chainid=<chain_id>&module=account&action=txlist&address=<sender>&startblock=0&endblock=<block_minus_1>&page=1&offset=3&sort=desc&apikey=$ETHERSCAN_API_KEY" \
  > previous_tx_<sender>.json
```

Use the closest previous tx from the same sender unless a stronger source-specific previous action is needed. If explorer account history is unavailable, use an equivalent indexer, Alchemy enhanced APIs where configured, or a bounded block/RPC scan. Record the source and limits.

In keyless mode, previous-transaction lookup is best effort. A standard JSON-RPC node cannot query account history directly. Use a no-key indexer if one is available for the chain, scan a small block window only when it is cheap, or list sender history as a gap rather than blocking a trace-backed report.

Bounded multi-block lookback:

- Check the sender's previous tx.
- Check recent approvals/transfers or state changes involving the source owner/account, spender/operator/adopter, asset/protocol contract, recipient/beneficiary, and route if the invalidation suggests a multi-block exploit.
- Keep the window explicit, for example "previous 100 blocks" or "previous 24h".
- Stop expanding when it no longer changes the verdict or next action; list the unsearched surface as a gap.

If a selector/source remains unresolved, keep it in open gaps. Do not invent a contract name or function signature.

Explorer/RPC evidence should answer:

- Did the tx land?
- What would have moved if invalidation did not stop it?
- Was it allowance abuse, a signed owner action, privileged call, route abuse, or a protocol logic bug?
- Did it affect fungible balances, ownership/operator rights, protocol accounting/state, or only internal routing?
- Is the same route still exploitable?

## Stage 7: Replay and Simulation

Use local tools to verify what happened and what would have happened.

Recommended commands:

```bash
cast 4byte <selector>
cast --to-ascii <hex-revert-string>
cast calldata-decode '<signature>' <calldata>
cast rpc eth_getTransactionByHash <hash> --rpc-url <url>
cast rpc eth_getTransactionReceipt <hash> --rpc-url <url>
cast call <token> 'symbol()(string)' --rpc-url <url>
cast call <token> 'decimals()(uint8)' --rpc-url <url>
cast call <token> 'balanceOf(address)(uint256)' <owner> --block <block> --rpc-url <url>
cast call <token> 'allowance(address,address)(uint256)' <owner> <spender> --block <block> --rpc-url <url>
cast call <nft> 'ownerOf(uint256)(address)' <token_id> --block <block> --rpc-url <url>
cast call <nft> 'isApprovedForAll(address,address)(bool)' <owner> <operator> --block <block> --rpc-url <url>
cast run <hash> --rpc-url <url>
```

Use `cast run` or `debug_traceTransaction` for landed or replayable transactions. For non-landed PCL simulations, prefer the PCL trace, then attempt `eth_call`/`trace_call` with the same transaction object and block context if the RPC supports it.

Replay goals:

- Confirm whether balances, allowances, ownership/operator approvals, vault shares, or protocol state made the attempted action feasible.
- Confirm the assertion reverted for the claimed reason.
- Identify whether the transaction was a malicious pull, benign route, assertion false positive, or inconclusive.
- Identify all contracts created or touched by the tx.

Cast may print Foundry nightly warnings before the result; ignore the warning when the call succeeds, but do not paste it into reports.

## Stage 8: Value Accounting

Produce at most three headline numbers:

1. **Actual loss**: landed on-chain value transferred out.
2. **Unique protected value**: deduped source balances blocked by the invalidation.
3. **Repeated blocked attempt volume**: all repeated fungible attempts, including retries.

For NFTs, ERC1155s, or protocol state, add a separate count/list of protected token ids or state changes. Do not force a USD estimate unless there is a sourced price or explicit valuation model.

Rules:

- Use raw integer math as long as possible.
- Normalize by token decimals from chain metadata for fungible assets.
- Price by chain asset address and token id where applicable.
- For current/internal reads, current DeFiLlama marks are acceptable and should be labeled.
- For public incident reports, prefer block-time prices or a fixed timestamp price.
- Mark lower bounds when traces are missing or unpriced.

Dedupe default:

- Key fungible assets by `(chain_id, token_address, source_owner)`.
- Key non-fungible assets by `(chain_id, token_address, token_id, source_owner)`.
- Use the maximum observed raw attempted amount per key.
- If balances change over time, split by block/time window and explain.

Repeated volume default:

- Sum all verified attempted transfer amounts.
- This is useful for showing bot persistence and security workload, but it is not the same as unique funds at risk.

Multi-incident grouping:

- Group repeated invalidations by route/signature before writing the report.
- Suggested signature: `(outer_target, outer_selector, adopter, assertion_id, touched_assets_or_state, sorted(source_accounts), beneficiaries, decoded_revert_reason)`.
- Render one representative full improved trace per group, then list every `(incident_id, pcl_tx_id, hash, block, trace_status)` in the transaction-object table.
- If a group contains a failed/no-trace retry, keep it in the group only as an unverified estimate unless calldata or RPC independently verifies the same movement.
- If balances or recipients differ materially, split into a separate group.

When an assertion checks non-zero allowance to an adopter, report both:

- **Attempted transfer amount** from the trace.
- **Remaining exposure** from latest balance and allowance reads for the same source owner/spender.

If a balance is still present and allowance is still non-zero or effectively infinite, recommend a concrete revoke/check action even if the invalidation blocked the attempted transfer.

When an assertion checks ownership, operator approvals, privileged roles, vault shares, or protocol storage, report the equivalent remaining exposure: current owner/operator, role holder, share balance, debt/collateral state, oracle value, or storage slot value at the relevant block and latest.

## Stage 9: Verdict and Recommended Action

Use a clear verdict:

- **Likely malicious**: attempted unauthorized drain, suspicious route, no clear user-intended settlement, known exploit pattern, repeated retries, attacker-controlled recipient, or hostile source/route.
- **Likely benign / expected**: normal strategy/route behavior blocked by an overly strict assertion, known protocol flow, no adverse user value transfer.
- **Misconfiguration**: assertion/circuit breaker parameter likely wrong or too broad.
- **Inconclusive**: missing traces/source/RPC, ambiguous calldata, or insufficient context.

Each verdict must include evidence. Do not output a verdict without a reason.

Recommended next step must be concrete:

- Do nothing / acknowledge false positive.
- Modify or reset assertion/circuit breaker parameters.
- Revoke approval for specific spender/token.
- Pause a route/integration.
- Retry traces or fetch missing source.
- Investigate related txs before/after the invalidation.
- Notify affected users or partner team.

When showing an agent-generated triage summary to operators or end users, include a warning:

```text
This triage was generated by an agent and can be wrong. Verify critical conclusions against the raw transaction, trace, and assertion evidence before taking irreversible action.
```

## Stage 10: Root-Cause Classification

Use evidence, not labels:

- **Allowance abuse**: `transferFrom` from source owner by adopter/spender, non-zero allowance, no source-owner signed transfer.
- **Permit2 / AllowanceHolder issue**: route uses Permit2/AllowanceHolder approvals or spender plumbing.
- **NFT/operator approval abuse**: `safeTransferFrom`/`transferFrom` or ERC1155 transfer by an approved operator rather than the owner.
- **Router/path abuse**: malicious route or callback reaches adopter/router in a way assertions disallow.
- **Key compromise**: source EOA signs transfers/approvals directly.
- **Privileged abuse**: admin/owner/minter/upgrader role call enables transfer or mint.
- **Accounting/oracle bug**: protocol state update lets attacker extract without matching backing.
- **Bridge/route issue**: payload attempts bridgeable exit or cross-chain route.
- **State-only invariant break**: no immediate transfer, but assertion stopped a harmful storage/accounting transition.

State confidence and what would raise it.

## Stage 11: Exposure Triage

For the affected user/project, check:

- Is any approval still live for the adopter/spender/router?
- Is any operator approval, privileged role, or protocol state exposure still live?
- Does the source wallet still hold funds?
- Have the same attacker recipients retried?
- Are there more invalidations after the cutoff?
- Did any related transaction land outside PCL invalidations?
- Can a revoked approval or changed route remove the risk?
- Is the assertion currently enforcing, monitoring, or only reporting?

Recommended immediate outputs:

- addresses to revoke approvals for
- token/NFT/protocol contracts involved
- tx hashes to inspect/share
- whether to pause a route, disable an integration, or notify users

## Stage 12: Report Template

The production invalidation detail output has two layers:

- An above-the-fold executive summary for quick operator understanding.
- A detailed triage report with the transaction explanation, root cause, transaction object, and one full improved trace that combines transaction execution with assertion evaluation.

Do not emit only a terse incident summary when the user asks to see the agentic triage output.

```text
# Executive Summary

Transaction
<Plain-English explanation of what the dropped transaction attempted. Include the source owner/account, recipient/beneficiary, asset or state touched, amount or ids, route, created contracts, and whether it landed.>

Assertion
<Assertion title/id, adopter, and exact invalidation/revert reason. Explain what the assertion checked.>

Verdict
<Likely malicious / likely benign / misconfiguration / inconclusive> because <evidence from trace, logs, source, or RPC>.

Recommended next step
<One concrete action: revoke exact approval, investigate exact tx, retry trace, adjust assertion, or do nothing.>

Agent warning
This triage was generated by an agent and can be wrong. Verify critical conclusions against the raw transaction, trace, and assertion evidence before taking irreversible action.

# Triage Report

## Scope and Data Freshness

- Snapshot: <timestamp>
- Project: <project id/slug/name>
- Chain: <chain id/name>
- Environment: <production/staging>
- Incidents: <ids/windows>
- Invalidating PCL tx ids: <ids>
- Trace state: <completed/failed/pending>
- PCL: <binary path/version>
- RPC/explorer data used: <yes/no/which>
- Request ids: <when useful>

## Detailed Transaction Explanation

<Narrative that explains the transaction route, actors, asset movements or protocol state changes, temporary contracts, calldata selectors, and why source owner/account != tx sender if applicable.>

```mermaid
sequenceDiagram
  autonumber
  actor Sender as Tx sender / recipient<br/><short address>
  participant Target as Outer target / deployer<br/><short address>
  participant Temp as Temporary contract(s)
  participant Protected as Protected contract<br/><short address>
  participant Asset as Asset or state<br/><symbol/id + short address>
  participant Source as Source account<br/><short address>
  participant Assertion as Assertion<br/><title>

  Sender->>Target: submit invalidating tx / deploy(...)
  Target->>Temp: create temporary executor
  Temp->>Source: balanceOf(source)
  Source-->>Temp: balance available
  Temp->>Protected: execute(... encoded route ...)
  Protected->>Asset: transfer/state change attempt
  Asset-->>Protected: would emit event or update state
  Note over Sender,Source: Source account can differ from tx sender
  Assertion->>Protected: getAssertionAdopter()
  Assertion->>Assertion: inspect logs and call inputs
  Assertion->>Asset: read balance/owner/allowance/storage
  Asset-->>Assertion: protected state observed
  Assertion--xProtected: revert: <reason>
  Note over Asset,Assertion: Transaction is invalidated; no on-chain loss if landed_on_chain=false
```

Diagram rules:

- Use `sequenceDiagram` as the primary diagram for invalidations because the main question is ordered execution.
- Use `autonumber` so text can refer to exact steps.
- Declare participants explicitly, left to right, in execution order.
- Use aliases and `<br/>` for readable labels; do not put full addresses in every node.
- Use notes for context and caveats, not extra boxes.
- Use `loop` for repeated attempts and `alt` for completed-trace vs failed-trace branches.
- Use a separate `flowchart` only when a topology/value-flow overview adds information that the sequence diagram cannot show clearly.
- For flowcharts, avoid lowercase `end` as a node label and avoid edge targets beginning with lowercase `o` or `x` immediately after an edge marker such as `---`; quote labels or capitalize where needed.

## Root Cause Analysis

<Evidence-backed mechanism: allowance abuse, NFT/operator approval abuse, Permit2/AllowanceHolder issue, router/path abuse, compromised key, privileged call, protocol-state bug, false positive, etc. Include what would raise/lower confidence.>

## Source and Decompiler Context

```text
source_coverage:
  verified_source: <count/list>
  sourcify_source: <count/list>
  decompiled: <count/list, tool used>
  unresolved_code: <count/list>
  eoas_or_no_code: <count/list>
important_gaps:
  - <address/functionality still unresolved and impact on confidence>
```

Summarize how contract source/decompiled context changed the RCA. If decompiled output is used, state that it is approximate and name the raw trace/RPC evidence that confirms the critical claim.

## Transaction Object

For one incident, include one object. For repeated invalidations, use a compact table with one row per `(incident_id, pcl_tx_id)` and a separate representative object for each route group.

```text
hash: <hash>
pcl_tx_id: <id>
incident_id: <id>
from: <tx sender>
to: <outer target>
value: <native value>
block: <block>
timestamp: <timestamp>
landed_on_chain: <true/false>
selectors: <decoded selectors>
revert_reason: <decoded reason>
```

## Full Improved Trace

For grouped repeated invalidations, show one representative full improved trace per route/signature and state how many PCL txs share that pattern. Do not repeat near-identical trace trees.

The trace must be a single ordered narrative, not separate transaction and assertion sections. Start with the invalidating transaction's outer call, preserve the relevant call order, include decoded asset/protocol movements and state reads inline, then continue into assertion inspection calls, assertion state checks, and the final invalidation/revert reason.

```solidity
[gas] ContractName (0x...)::function(...)
  ├─ AssetOrProtocol (0x...)::function(...)
  │   ├─ movement/state read: <source/account> -> <recipient/beneficiary> <amount/id/state>
  │   ├─ decoded event: <standard/event and fields>
  │   └─ delegatecall mirror ignored for accounting
  ├─ ...
AssertionContract (0x...)::check()
  ├─ getAssertionAdopter() -> <adopter>
  ├─ getLogs() -> <decoded logs inspected>
  ├─ getCallInputs(<adopter>, <selector>) -> <decoded calls inspected>
  ├─ AssetOrProtocol.stateRead(<source/account>, <adopter>) -> <value>
  └─ Revert: <reason>
```

## Value and Exposure

- Actual loss: <amount/USD>
- Unique protected value: <amount/USD>
- Repeated blocked attempt volume: <amount/USD>
- Unverified estimates: <amount/USD or none>
- Remaining exposure: <source owners/accounts, balances, allowances, ownership/operator state, token ids, protocol state, spender/operator/adopter>

## Open Gaps and Confidence

<failed traces, unpriced tokens, missing ABI/RPC, uncertain source role>

## Next Actions

<revokes, monitoring, trace retry, source/source-code review, public/internal comms>
```

## Stage 13: Self-Review After Test Runs

After running the skill on live invalidations, review the result before reporting:

- Did the commands use the current Brew `pcl` and record `pcl --version`?
- Did PCL auth and platform health pass?
- Did the capability preflight run, and did the report record which RPC/explorer/decompiler capabilities were present or missing?
- Did the run include both a failed/no-trace case and completed traces when available?
- Were list/export artifacts treated as indexes rather than full evidence?
- Were incident rows keyed by `(incident_id, pcl_tx_id)`, not hash alone?
- Were per-transaction `debug_traces[].status` values inspected?
- Was combined `trace_content` split into transaction and assertion sections?
- Were ERC20/ERC721/ERC1155/WETH/ERC4626 events decoded into movement rows, not just described in prose?
- Were delegatecall mirror transfers ignored for accounting?
- Were `transferFrom` source owners separated from transaction senders?
- Was the sender's previous transaction fetched or explicitly listed as unavailable?
- Were transient created contracts handled separately from EOAs/no-code addresses?
- Were asset metadata, block-pinned balances/owners/operator approvals, and relevant protocol state verified with RPC?
- Did the final output separate actual loss, unique protected value, repeated blocked volume, and unpriced gaps?
- Did the next action name exact owner/spender/token addresses to revoke or inspect?
