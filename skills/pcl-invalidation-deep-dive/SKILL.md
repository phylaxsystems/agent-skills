---
name: pcl-invalidation-deep-dive
description: Run local agentic triage for Phylax PCL/Credible Layer invalidations, protected-loss events, blocked transactions, failed or pending debug traces, and "we got hacked" requests by using the pcl CLI plus JSON-RPC, cast, explorer/source, and optional decompiler evidence. Use when a user reports a new invalidation, asks what a dropped transaction attempted, why an assertion invalidated it, whether it looks malicious or benign, what value or protocol state was protected, what risk remains, or what action to take next across any EVM protocol, chain, asset type, router, bridge, vault, lending market, token, or custom assertion.
---

# PCL Invalidation Deep Dive

## When to Use

- A user reports a new PCL/Credible Layer invalidation and needs to know what the blocked transaction attempted.
- You need production-style agentic triage for a dropped transaction: transaction summary, assertion reason, verdict, next action, improved traces, and value/exposure.
- You need to estimate actual loss, unique protected value, repeated blocked attempt volume, or unpriced failed-trace gaps from platform invalidation data.
- You are investigating suspicious PCL incidents, failed traces, protected value, blocked exploit attempts, false positives, assertion misconfigurations, allowance drains, NFT or ERC1155 transfers, privileged calls, bridge/router/vault flows, accounting bugs, or "we got hacked" requests.

## When NOT to Use

- You are designing or implementing a new assertion. Use `designing-assertions`, `mapping-invariants`, `implementing-assertions`, or `pcl-assertion-workflow`.
- You are testing assertion behavior in a local project. Use `testing-assertions` or `backtesting-assertions`.
- You only need generic EVM incident analysis that is unrelated to PCL invalidation records.
- You do not have access to PCL incident data and cannot provide a tx hash, incident id, project id, or exported trace artifact.

## Rationalizations to Reject

- "The list row is enough." Fetch incident detail and per-transaction trace records before reasoning.
- "The transaction hash is the row key." Key evidence by `(incident_id, invalidating_transaction.id)` because repeated simulations can reuse a hash across windows.
- "The sender is the victim." Extract source owners from `transferFrom` calls and events; `tx.from`, recipient, source owner, and adopter can all differ.
- "The repeated total is the loss." Separate actual landed loss, unique protected value, repeated blocked volume, and unpriced gaps.
- "Labels are enough for RCA." Important code-bearing contracts need verified source, Sourcify data, decompiled output, or an explicit unresolved-source gap.
- "This is just an allowance drain." Treat allowance abuse as one mechanism, not the default. Check the assertion logic, protocol state, privileged roles, callbacks, oracle/accounting paths, bridges, vaults, NFTs/ERC1155s, and native value where the trace points there.
- "`cast` is optional." `cast` is required for professional selector decoding, calldata decoding, RPC reads, balance/allowance/storage checks, and replay probes unless the user explicitly accepts a degraded analysis.

## Operating Standard

Treat PCL as the primary incident index and chain evidence as the source of truth. Start with the platform's invalidation record, then verify the attempted state/value change with transaction traces, receipts, logs, calldata, and token flows.

Stay mechanism-agnostic until the evidence narrows the case. A protected loss can be a fungible token transfer, NFT/ERC1155 movement, native value movement, mint/burn, vault share accounting change, privileged state mutation, bridge message, oracle/accounting update, or protocol-specific invariant break.

Always separate:

- **Actual landed loss**: value that really moved on-chain.
- **Unique protected value**: lower-bound unique source balances that would have been drained if the first blocked attempt succeeded.
- **Repeated blocked attempt volume**: sum of all invalidated attempts, including retries against the same balances.
- **Unpriced or unavailable traces**: failed/pending trace gaps; never silently fold these into exact totals.
- **Non-fungible or state-only protection**: asset ids, ownership/state changes, or protocol risk that cannot be honestly reduced to a USD number without pricing evidence.

This skill is the local version of the production "Agentic triage" flow: it should work from PCL invalidation records and local/API evidence, without requiring the dApp backend to precompute the report.

Read [references/etl-pipeline.md](references/etl-pipeline.md) when you need the full local ETL checklist, data-source matrix, context packet, or value-accounting rules.

## Fast Feature-Parity Mode

When the user asks for production-style agentic triage, optimize for the same user outcome as the Notion spec: a fast answer that explains what the tx attempted, why the assertion stopped it, whether there are red flags, and the next action.

For one to five invalidating transactions:

- Fetch detail, trace, contract context, previous transaction, asset/protocol metadata, and block-pinned state reads, then write the full report.

For larger incident windows:

- Build an index first, then group by route/signature before fetching or loading every raw trace into the model.
- Fully deep-dive one representative completed trace per group and any materially different failed/no-trace rows.
- Keep raw artifacts on disk and summarize the rest in tables. Do not paste large traces into the prompt or final answer.
- Preserve complete row coverage through `(incident_id, pcl_tx_id, hash, block, trace_status)` tables, even when only representative traces are rendered.

If a multi-agent runner is available and the user asks for a deep pass, split the work into three artifact-sharing phases:

- **RCA phase**: PCL context, source/decompiler context, previous txs, and trace evidence.
- **Replay phase**: RPC/cast checks for calldata, selectors, receipts/logs, balances, allowances, owners, protocol storage, and replayability.
- **Report phase**: final invalidation-detail artifact using only the evidence packet and explicit gaps.

If no runner is available, execute the same phases sequentially. Do not let the report phase invent missing source, replay, or previous-transaction evidence.

## Quick Workflow

1. **Scope the incident**
   - Resolve the project or incident from the user's words with `pcl search --query <name> --toon`, `pcl incidents --project-id <id-or-slug> --toon`, or `pcl incidents --incident-id <id> --toon`.
   - Record exact UTC snapshot time, project id/slug, chain id/name, assertion title/id, adopter address, incident id, PCL transaction ids, hashes, and block numbers.
   - State whether the user asked for latest, a date range, all history, or a specific incident. Use exact dates.
   - For "recent" or "latest", include at least one latest failed/no-trace incident and at least two completed traces when available, so both paths are exercised.

2. **Use the right PCL binary**
   - For end-user investigations, prefer the Homebrew CLI on PATH: `command -v pcl` and `pcl --version`.
   - On macOS, the Phylax formula is `phylaxsystems/pcl/phylax`; Homebrew core `pcl` is the unrelated Point Cloud Library.
   - If the user asks for latest Brew PCL, verify `brew info phylaxsystems/pcl/phylax`, then `brew upgrade phylaxsystems/pcl/phylax` if permitted.
   - If working inside a PCL checkout for CLI development, rebuild and run `./target/debug/pcl`; do not mix checkout and Brew outputs in one report.

3. **Extract PCL data**
   - Run `pcl doctor --toon`, `pcl auth ensure --toon`, and `pcl workflows show incident-investigation --toon` before authenticated project incident queries.
   - Use `--toon` for agent-facing inspection and `--json` only when strict JSON parsing is needed.
   - Pull incident lists with explicit filters: `--project-id`, `--environment production`, `--from-date`, `--to-date`, `--all`, `--limit`, `--toon` or `--json`.
   - Use `pcl export incidents --project-id <id> --environment production --out incidents.jsonl --errors errors.jsonl --checkpoint checkpoint.json --resume --continue-on-error --toon` for resumable list artifacts. Treat the export as an index; still fetch detail and trace records separately.
   - When using `pcl incidents ... --output <file> --json`, verify that the file exists and inspect its shape. List outputs may contain only the `data` payload, not the full envelope, and detail/trace commands may need stdout capture instead.
   - For each incident, pull detail with `pcl incidents --incident-id <id> --toon`.
   - For each invalidating transaction, pull trace with `pcl incidents --incident-id <id> --tx-id <pcl-transaction-id> --toon`, even when the list row says no traces completed. A failed trace still returns the transaction object, block env, calldata, and debug trace status.
   - For multi-incident work, save trace JSON artifacts with both ids in the filename, such as `trace_<incident-id>_<pcl-tx-id>.json`; trace-only responses may not repeat the incident id.
   - After fetching traces, run `scripts/normalize_pcl_trace.py --pretty trace_*.json > normalized_traces.json` to extract non-delegatecall token calls, ERC20/ERC721/ERC1155/WETH/ERC4626 events, event-level deltas, and allowance checks. Use the normalized rows as a parsing aid, then spot-check against raw trace text before final accounting.
   - Track `transaction_count`, completed/pending/failed trace counts from each transaction's `debug_traces[].status`, `landed_on_chain`, revert reason, and request ids from the response envelope or `pcl requests list --limit 20 --toon`.
   - Key rows by `(incident_id, invalidating_transaction.id)`. Do not dedupe incident coverage by transaction hash alone; repeated simulations can reuse a hash while differing by incident window, block number, PCL tx id, or trace status.

4. **Assemble the local triage context**
   - Run `scripts/check_triage_requirements.py --chain-id <chain-id> --require-explorer` before deep RCA. Add `--require-decompiler` when unverified code, transient contracts, or source gaps must be resolved for the answer.
   - If the requirements preflight exits non-zero, stop and surface its output verbatim. Do not continue to a root-cause report until the missing RPC/explorer/decompiler capability is configured, unless the user explicitly accepts a degraded report.
   - Build a local evidence packet from PCL plus RPC/explorer data: transaction object, transaction execution trace, assertion execution trace, previous transaction from the sender, all touched contract addresses, created contracts, ABIs/source when available, asset/protocol metadata, receipts/logs, and relevant state reads.
   - Fetch the previous transaction from the same sender before the invalidation block/hash using explorer account history or an equivalent RPC/indexer source. Save it as `previous_tx_<sender>.json`; if unavailable, list it as a gap because it can distinguish benign user flow, preparatory approvals, and multi-block exploit setup.
   - Treat contract source context as a required stage before root-cause analysis. Extract every address from transaction traces, assertion traces, transaction objects, created-contract lines, token proxy/implementation delegatecalls, and assertion/runtime helper calls.
   - Run `scripts/collect_contract_context.py --chain-id <chain-id> --out-dir contract_context trace_*.json` after traces are saved. Provide `--rpc-url` explicitly or rely on current env. It fetches bytecode, Etherscan V2 source, Sourcify source, and emits `contract_context_manifest.json` with unverified decompiler targets.
   - When `contract_context_manifest.json` has bytecode-backed `decompiler_targets`, run `scripts/run_heimdall_decompiler.py contract_context/contract_context_manifest.json --out-dir decompiled --require-success`. Heimdall-rs is the only supported decompiler path for this skill. Install `heimdall` on PATH or set `HEIMDALL_BIN=/absolute/path/to/heimdall`.
   - The contract-context helper exits with the exact missing JSON-RPC requirement when no RPC is configured. Use `--allow-missing-rpc` only when explicitly accepting a degraded source-only packet, then list that as a confidence gap.
   - For contracts created inside a non-landed PCL simulation, `eth_getCode(latest)` may return no code. Treat these as transient created-contract gaps, then recover init/runtime bytecode from trace output, calldata, replay, or decompiler tooling before relying on that route for RCA.
   - For every code-bearing address, attach one of: verified source/ABI, Sourcify contract data, decompiled output, or a specific unresolved-source gap. Do not do root-cause analysis from labels alone when source/decompiled context is missing for an important touched contract.
   - Store large JSON artifacts under `/tmp` or the current workspace and summarize from files instead of pasting huge traces into the final answer.
   - If any context is unavailable, keep an explicit gap list.

5. **Improve trace readability**
   - Strip ANSI before parsing or summarizing trace text.
   - If `transaction_trace_content` and `assertion_trace_content` are null, split combined `trace_content` on the `Transaction Trace` and `Assertion Trace` headings.
   - Resolve contract and asset names from explorer source/ABI, token metadata, NFT metadata, or labels before explaining the trace.
   - Decode ERC20 `Transfer`/`Approval`, ERC721 `Transfer`, ERC1155 `TransferSingle`/`TransferBatch`, WETH `Deposit`/`Withdrawal`, ERC4626 `Deposit`/`Withdraw`, and protocol-specific events when present.
   - Convert decoded asset events into movement rows: asset contract, standard, address or owner, raw delta or token id, human amount where applicable, source event, and whether the event came from a delegate context.
   - Pretty-print fungible amounts with decimals and symbols; cap display precision at 6 decimals unless the dust amount or precision matters. For NFTs and state changes, preserve ids and raw state keys.
   - Present raw addresses next to names the first time they appear.

6. **Decode attempted action**
   - Use completed PCL traces first. Extract real asset movements and protocol state changes from non-delegatecall calls, emitted logs, and assertion reads.
   - Separate roles from trace evidence: transaction sender, outer call target, source owner, recipient/beneficiary, asset contract, protocol account, and assertion adopter can all be different addresses. Do not assume `tx.from` is the victim/source owner.
   - Decode selectors with `cast 4byte`, verified ABIs, or explorer ABIs. Decode calldata only as supporting evidence unless trace execution is unavailable.
   - For failed traces, inspect calldata to identify candidate tokens/routes, but report value as a lower bound unless the calldata decodes cleanly into actual attempted transfer amounts.
   - Preserve the exact assertion failure reason. Do not paraphrase it into an allowance or transfer story unless the trace supports that mechanism.
   - For proxy tokens, avoid counting both the proxy call and implementation delegatecall. Count one attempted token movement at the proxy token address, using the event or non-delegatecall line as the canonical row.

7. **Replay and verify on chain**
   - Use Alchemy or another archive RPC for `eth_getTransactionByHash`, receipts, logs, balances, allowances, storage reads, and `debug_traceTransaction` or `trace_call` when available.
   - If chain-specific RPC env vars are missing but `ALCHEMY_API_KEY` is set, derive the chain RPC URL only when the chain is known to the helper. Do not print secrets.
   - RPC discovery order: `--rpc-url`, explicit chain RPC env var, generic chain-id env patterns, generic `RPC_URL`, derived Alchemy URL from `ALCHEMY_API_KEY`, then public RPC only for basic reads. Label public-RPC results as non-archive/non-debug unless verified otherwise.
   - Record whether each RPC or explorer data source was environment-provided, derived, or public fallback. Do not say an env var is missing unless you checked it in the current shell.
   - Use `cast 4byte`, `cast calldata-decode`, `cast call`, `cast run`, `cast rpc`, and block-pinned state reads to decode, replay, or sanity-check the invalidating transaction where possible.
   - Fetch the sender's previous transaction with Etherscan v2 account history when available:
     `module=account&action=txlist&address=<sender>&endblock=<block-1>&sort=desc&page=1&offset=3&chainid=<chain_id>`.
     If explorer history is unavailable, use an equivalent indexer or bounded block/RPC scan and record the limitation.
   - For suspicious sequences, run a bounded related-transaction lookback around previous blocks for the same sender, source owner/account, recipient/beneficiary, asset, spender/operator/adopter, and outer route. Keep the expansion bounded, save the query, and report if the analysis depends on it.
   - Use Etherscan v2 or chain explorers for verified source/ABI, asset transfers, contract labels, creation txs, and public links. For Etherscan V2-compatible explorers, try `module=contract&action=getsourcecode&address=<address>&chainid=<chain_id>` when an Etherscan-compatible key is available; otherwise use chain-specific explorer APIs when configured.
   - Use Sourcify as a no-key verified-source fallback with `/server/v2/contract/<chain-id>/<address>?fields=all`.
   - For code-bearing addresses without verified source, use Heimdall-rs via `scripts/run_heimdall_decompiler.py`. If Heimdall is unavailable, store runtime bytecode and list the address as a source/decompiler gap instead of switching to a different decompiler.
   - Label all decompiled output as approximate. Use it to understand control flow, selectors, storage, and call routing; do not treat it as verified source.
   - Decode unknown selectors with `cast 4byte <selector>`; if unresolved, include the selector in open gaps instead of inventing a function name.
   - If PCL says `landed_on_chain=false`, treat it as a blocked simulation/invalidation unless chain evidence proves otherwise.
   - If any transaction landed, split the analysis into blocked value vs actual loss.
   - Run exposure reads against trace source owners, asset owners, protocol accounts, spenders, operators, and adopter addresses, not just the invalidating transaction sender.

8. **Compute value**
   - Price by asset address and chain. DeFiLlama coin prices are acceptable for quick current marks; use block-time prices when the user asks for historical accounting or public incident numbers.
   - Normalize fungible decimals from token metadata, not assumptions. For NFTs/ERC1155s, preserve token ids and use collection/floor or explicit valuation only when sourced.
   - Repeated volume: sum every confirmed fungible attempted transfer; for non-fungible/state-only attempts, count repeated attempted asset ids or state changes separately.
   - Unique protected value: dedupe by `(chain, asset, source owner, token id when applicable)` and usually take the max observed fungible attempted amount per source balance.
   - Do not double count delegatecalls, downstream consolidation transfers, swap outputs, approvals, or the same balance retried by multiple bots.

9. **Root-cause, verdict, and exposure**
   - Classify the mechanism: allowance abuse, Permit2/AllowanceHolder path, router/path abuse, compromised key, privileged function, oracle/accounting bug, bridge route issue, NFT/operator approval abuse, vault share/accounting issue, liquidation path issue, or assertion false positive.
   - Identify victim/source owners or accounts, attacker/recipient, spender/operator/adopter, asset/protocol contracts, routers, pools, bridges, and any temporary contracts.
   - Decide whether the transaction looks malicious, benign/expected, misconfigured, or inconclusive. Support the verdict with trace evidence.
   - Check whether risk remains: outstanding approvals, same route still callable, same adopter/spender still approved, funds still in source wallets, and whether the attacker can retry.
   - Recommend one concrete next step: do nothing, revoke/modify approvals, adjust/reset an assertion/circuit breaker, investigate further, pause a route, or escalate.

10. **Report**
   - Default to the production invalidation-detail shape, not a terse incident summary.
   - First render an above-the-fold executive summary that breaks down the transaction, the assertion that invalidated it, an evidence-backed verdict, and one recommended next step.
   - Then render a detailed triage report with transaction explanation, mermaid diagram, root-cause analysis, transaction object, full improved trace, value accounting, exposure, and data gaps.
   - The trace section must be one ordered **Full Improved Trace**, not separate transaction/assertion fragments. Start at the outer transaction call, include intermediate contract calls, decoded movements/state reads, assertion inspection calls, state checks, and the final invalidation/revert reason in execution order.
   - In the full improved trace, include decoded movement rows from ERC20/ERC721/ERC1155/ERC4626/native/protocol events when present. These are the easiest rows for operators to verify against the raw trace.
   - For repeated invalidations, group by route/signature and render one representative full improved trace per group, plus a complete transaction-object table for every `(incident_id, pcl_tx_id)`. Do not paste six near-identical traces when a grouped summary is clearer.
   - Use a Mermaid `sequenceDiagram` as the primary diagram for step-by-step transaction execution. Use `flowchart` only as a secondary actor/topology/value-flow view.
   - Include a warning that agentic triage can be wrong when the report will be shown directly to users or operators.
   - Give exact counts: incidents, invalidating txs, completed traces, failed/pending traces, landed txs.
   - Give three numbers when applicable: actual loss, unique protected value, repeated blocked attempt volume.
   - Provide hashes/addresses for evidence, plus explorer links when possible.

## Mermaid Diagram Rules

Use the diagram type that matches the question:

- **Sequence diagram** for ordered execution: who called whom, in what order, where the assertion checked state, and where the transaction stopped. This is the default for invalidation triage.
- **Flowchart** for static relationships: actor topology, value-flow overview, component ownership, or multiple independent routes. Do not use a flowchart as the only diagram when the key question is step-by-step execution.

For production triage sequence diagrams:

- Start with `sequenceDiagram` and `autonumber` so each step can be referenced in the text.
- Declare participants explicitly and in left-to-right execution order. Use aliases for readable labels and line breaks.
- Keep participant labels short: role + short address, not full paragraphs.
- Use message labels that name the exact function or check: `deploy`, `execute`, `transferFrom`, `ownerOf`, `safeTransferFrom`, `getLogs`, `allowance`, `storage read`, `revert`.
- Put token amounts in message labels only when they are central to the incident.
- Use `Note over` for context such as "source owner is not tx sender" or "delegatecall mirror ignored".
- Use `loop` for repeated attempts or repeated source-owner drains.
- Use `alt`/`else` for completed-trace vs failed-trace branches, or allowed vs invalidated paths.
- Mark the assertion stop point explicitly with a final `-->>` or `--x`-style message label such as `revert: <reason>`.
- Avoid labels that contain lowercase `end` as a standalone word in flowcharts; it can break Mermaid parsing. Keep node ids stable and labels quoted when using punctuation.
- In flowcharts, avoid edge targets that start with lowercase `o` or `x` immediately after an edge marker such as `---`; add a space or capitalize the node id/label so Mermaid does not parse a circle or cross edge accidentally.

## Value Language

Use wording that cannot be misread:

- "Blocked `$X` in repeated drain attempts" for summed retries.
- "Protected about `$Y` in unique user funds" for deduped source balances.
- "Trace-backed lower bound" when any trace failed, is pending, or calldata-only inference is required.
- "Unverified calldata estimate" for decoded routes without execution traces.

Do not turn a repeated-attempt figure into a real-loss figure. Do not call failed-trace calldata "protected value" unless the attempted token transfer is decoded and verified.

## Data Access Checklist

Expect to need:

- PCL CLI auth and platform incident APIs.
- Chain RPC with archive/debug support, preferably Alchemy.
- Etherscan v2 or chain-specific explorer API keys for tx, receipt, logs, source, and ABI.
- Sourcify for no-key verified contract lookup where supported.
- Heimdall-rs for unverified contract decompilation. Install `heimdall` on PATH or set `HEIMDALL_BIN=/absolute/path/to/heimdall`.
- `cast` for selectors, calldata, storage, balances, and ad hoc ABI calls.
- Asset metadata and prices from chain calls, DeFiLlama, CoinGecko, NFT/indexer APIs, or a verified token list.
- Optional: Tenderly/Phalcon for visual traces when RPC debug traces are unavailable.

Minimum useful environment:

- `pcl` authenticated against the platform.
- One chain RPC URL with archive/debug capability, such as Alchemy.
- Explorer API access for the target chain, such as Etherscan v2, Blockscout, or a chain-specific explorer.
- `cast` from Foundry.
- Optional decompiler access for unverified or transient contracts.

Before RCA, run the requirement gate and treat failures as blocking:

```bash
scripts/check_triage_requirements.py --chain-id <chain-id> --require-explorer
scripts/check_triage_requirements.py --chain-id <chain-id> --require-explorer --require-decompiler
```

The gate reports which capability is missing, why it is required, and which env var or flag can satisfy it. Surface that output directly instead of producing a low-confidence triage that hides missing RPC, verification, or decompiler access.

## Final Answer Shape

When the user asks to see the agentic triage output, produce a production-style invalidation detail artifact. Do not collapse it into a short incident brief.

Use this order:

1. **Executive Summary**
   - Transaction: one paragraph on what the invalidated transaction attempted.
   - Assertion: assertion title/id, adopter, and exact invalidation reason.
   - Verdict: malicious/benign/misconfiguration/inconclusive plus the evidence for that verdict.
   - Recommended next step: one actionable operator/user action.
   - Agent warning: "This triage was generated by an agent and can be wrong. Verify critical conclusions against the raw transaction, trace, and assertion evidence before taking irreversible action."

2. **Triage Report**
   - Scope and data freshness: snapshot time, project, chain, date range or incident ids, PCL version, trace counts, request ids when relevant.
   - Detailed transaction explanation: actors, contracts, route, created contracts, source owners/accounts, recipient/beneficiary, asset movements or state changes, landed/not landed status.
   - Mermaid diagram: prefer a numbered `sequenceDiagram` that shows each transaction/assertion step and the assertion stop point. Add a flowchart only if a separate topology/value-flow view is useful.
   - Root cause analysis: evidence-backed mechanism and why it was invalidated.
   - Source/decompiler context: source coverage for all touched code-bearing contracts, plus unresolved or decompiled-only gaps.
   - Transaction object: concise key fields (`hash`, PCL tx id, from, to, value, block, calldata selectors, landed status).
   - Full improved trace: one ordered trace that combines the transaction execution and assertion evaluation. Include formatted contract names, decoded asset/protocol events, human-readable amounts or ids, delegatecall notes, adopter reads, logs/call inputs inspected, state checks, and the final revert reason.
   - Value and exposure: actual loss, unique protected value, repeated blocked attempt volume, unverified estimates, remaining balances/allowances/ownership/state exposure.
   - Open gaps and confidence: failed/pending traces, missing source/ABI, unpriced assets, and what would improve confidence.

Avoid generic security advice unless the user asks. Prioritize the concrete mechanism, value, what happened, why it was stopped, and exactly what to check or revoke now.
