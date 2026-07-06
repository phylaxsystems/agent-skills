import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

test("build_evidence_packet writes compact report-agent packet", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-packet-"));
  const incidentPath = path.join(tempDir, "incident.json");
  const tracePath = path.join(tempDir, "trace.json");
  const normalizedPath = path.join(tempDir, "normalized.json");
  const contextPath = path.join(tempDir, "contract_context_manifest.json");
  const decompilationPath = path.join(tempDir, "heimdall_decompilation_manifest.json");
  const statePath = path.join(tempDir, "state_reads.json");
  const preflightPath = path.join(tempDir, "capability_preflight.json");
  const stateTranscriptPath = path.join(tempDir, "state_reads_transcript.txt");
  const outPath = path.join(tempDir, "evidence_packet.md");
  const reportPath = path.join(tempDir, "final_report.md");

  const token = `0x${"1".repeat(40)}`;
  const owner = `0x${"2".repeat(40)}`;
  const recipient = `0x${"3".repeat(40)}`;
  const adopter = `0x${"4".repeat(40)}`;
  const wrapper = `0x${"5".repeat(40)}`;
  const txHash = `0x${"6".repeat(64)}`;
  const errorPayload =
    "0x08c379a0" +
    "0000000000000000000000000000000000000000000000000000000000000020" +
    "0000000000000000000000000000000000000000000000000000000000000038" +
    Buffer.from("Transfer from address with non-zero allowance to adopter")
      .toString("hex")
      .padEnd(64 * 2, "0");

  await writeFile(
    incidentPath,
    JSON.stringify({
      status: "ok",
      data: {
        data: {
          incident_id: "incident-1",
          assertion_id: "assertion-1",
          chain_id: 59144,
          window_start: "2026-06-13T14:01:35+00:00",
          environment: "production",
          assertion: { title: "AllowanceAssertion" },
          assertion_adopter: { name: "LineaSettler", address: adopter },
          invalidating_transactions: [
            {
              id: "tx-1",
              transaction_hash: txHash,
              from_address: recipient,
              to_address: wrapper,
              block_number: 123,
              incident_timestamp: "2026-06-13T14:06:01+00:00",
              landed_on_chain: false,
              revert_reason: errorPayload,
            },
            { id: "tx-2", transaction_hash: `0x${"7".repeat(64)}` },
          ],
        },
      },
    }),
  );
  await writeFile(tracePath, JSON.stringify({ data: { data: { invalidating_transaction: {} } } }));
  await writeFile(
    normalizedPath,
    JSON.stringify({
      records: [
        {
          incident_id: "incident-1",
          pcl_tx_id: "tx-1",
          transaction_hash: txHash,
          debug_trace_status: "completed",
          transfer_from_calls: [
            {
              token,
              source_owner: owner,
              recipient,
              raw_amount: "1071751815",
            },
          ],
          events: [
            {
              standard: "ERC20",
              event: "Transfer",
              from: owner,
              to: recipient,
              raw_amount: "1071751815",
            },
          ],
          allowance_checks: [
            {
              token,
              owner,
              spender: adopter,
              returned: `0x${"f".repeat(64)}`,
            },
          ],
        },
      ],
    }),
  );
  await writeFile(
    contextPath,
    JSON.stringify({
      addresses: [
        { address: token, code_type: "contract", verified_source_available: true },
        { address: wrapper, code_type: "contract", decompiler_needed: true, created_in_trace: true },
        { address: owner, code_type: "no_code" },
      ],
    }),
  );
  await writeFile(
    decompilationPath,
    JSON.stringify({
      decompiler: "heimdall-rs",
      completed_count: 1,
      skipped_count: 0,
      error_count: 0,
      results: [{ address: wrapper, status: "completed", reason: "unverified", output_dir: tempDir }],
    }),
  );
  await writeFile(
    statePath,
    JSON.stringify({
      transaction: null,
      receipt: null,
      tokens: { [token]: { symbol: "USDC", decimals: 6 } },
      reads: [
        {
          token,
          source_owner: owner,
          recipient,
          raw_attempted_amount: "1071751815",
          balance_at_block: "1071751815",
          balance_latest: "1071751815",
          allowance_latest:
            "115792089237316195423570985008687907853269984665640564039457584007913129639935",
        },
      ],
    }),
  );
  await writeFile(
    preflightPath,
    JSON.stringify({
      capability_selection: {
        mode: "private-or-mixed",
        private_or_configured_rpc_available: true,
        keyed_explorer_available: true,
        public_rpc_available: false,
        local_decompiler_available: true,
        operator_message: "Use configured/private endpoints first.",
      },
      requirements: [
        { name: "chain_rpc", selected_source: "ALCHEMY_API_KEY" },
        { name: "explorer_api", selected_source: "ETHERSCAN_API_KEY", configured: true, ok: true },
        { name: "heimdall_decompiler", selected_source: "/tmp/heimdall", configured: true, ok: true },
      ],
    }),
  );
  await writeFile(stateTranscriptPath, "state read transcript, not JSON\n");

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "build_evidence_packet.py",
  );
  await execFileAsync("python3", [
    scriptPath,
    "--run-dir",
    tempDir,
    "--project",
    "0x-settler",
    "--project-id",
    "project-1",
    "--chain-id",
    "59144",
    "--incident-json",
    incidentPath,
    "--trace-json",
    tracePath,
    "--normalized-json",
    normalizedPath,
    "--contract-context",
    contextPath,
    "--decompilation-manifest",
    decompilationPath,
    "--aux-file",
    `state reads=${statePath}`,
    "--aux-file",
    `state transcript=${stateTranscriptPath}`,
    "--aux-file",
    `capability preflight=${preflightPath}`,
    "--pcl-tx-id",
    "tx-1",
    "--out",
    outPath,
  ]);

  const packet = await readFile(outPath, "utf8");
  assert.match(packet, /Use this compact packet first/);
  assert.match(packet, /Do not refetch PCL list\/detail\/trace data/);
  assert.match(packet, /target under 90 seconds/);
  assert.match(packet, /Do not do local Homebrew\/formula\/version checks/);
  assert.match(packet, /If a non-critical check is missing, list it as a gap/);
  assert.match(packet, /Full Improved Trace/);
  assert.match(packet, /state reads: `state_reads\.json`/);
  assert.match(packet, /Read listed auxiliary state, receipt, price, and previous-transaction files/);
  assert.match(packet, /Transfer from address with non-zero allowance to adopter/);
  assert.match(packet, /Incident invalidating tx count from detail: `2`/);
  assert.match(packet, /raw `1071751815`/);
  assert.doesNotMatch(packet, /assuming 6 decimals/);
  assert.match(packet, /\{baseDir\}\/scripts\/render_fast_report\.py/);
  assert.match(packet, /created_contracts: `1`/);

  const renderScriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "render_fast_report.py",
  );
  const { stdout } = await execFileAsync("python3", [
    renderScriptPath,
    "--packet",
    outPath,
    "--run-dir",
    tempDir,
    "--out",
    reportPath,
  ]);
  const renderResult = JSON.parse(stdout);
  assert.ok(renderResult.elapsed_ms < 1000);

  const report = await readFile(reportPath, "utf8");
  assert.match(report, /Data Access Mode/);
  assert.match(report, /Capability mode: `private-or-mixed`/);
  assert.match(report, /ALCHEMY_API_KEY/);
  assert.match(report, /ETHERSCAN_API_KEY/);
  assert.match(report, /Full Improved Trace/);
  assert.match(report, /Actual landed loss/);
  assert.match(report, /Unique protected value/);
  assert.match(report, /Transfer from address with non-zero allowance to adopter/);
  const adopterLine = report.split("\n").find((line) => line.includes("participant Adopter"));
  assert.ok(adopterLine);
  assert.doesNotMatch(adopterLine, /`0x/);
});

test("render_fast_report is generic and accounts per token", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-generic-report-"));
  const incidentPath = path.join(tempDir, "incident.json");
  const tracePath = path.join(tempDir, "trace.json");
  const normalizedPath = path.join(tempDir, "normalized.json");
  const contextPath = path.join(tempDir, "contract_context_manifest.json");
  const decompilationPath = path.join(tempDir, "heimdall_decompilation_manifest.json");
  const statePath = path.join(tempDir, "state_reads.json");
  const outPath = path.join(tempDir, "evidence_packet.md");
  const reportPath = path.join(tempDir, "final_report.md");

  const zeroDecimalToken = `0x${"a".repeat(40)}`;
  const dai = `0x${"b".repeat(40)}`;
  const ownerOne = `0x${"c".repeat(40)}`;
  const ownerTwo = `0x${"d".repeat(40)}`;
  const recipient = `0x${"e".repeat(40)}`;
  const adopter = `0x${"f".repeat(40)}`;
  const target = `0x${"1".repeat(40)}`;
  const txHash = `0x${"2".repeat(64)}`;

  await writeFile(
    incidentPath,
    JSON.stringify({
      data: {
        incident_id: "incident-generic",
        assertion_id: "assertion-vault",
        chain_id: 8453,
        window_start: "2026-07-01T00:00:00+00:00",
        environment: "production",
        assertion: { title: "VaultBalanceAssertion" },
        assertion_adopter: { name: "VaultRouter", address: adopter },
        invalidating_transactions: [
          {
            id: "tx-generic",
            transaction_hash: txHash,
            from_address: recipient,
            to_address: target,
            block_number: 456,
            landed_on_chain: false,
            revert_reason: "Vault invariant failed",
          },
        ],
      },
    }),
  );
  await writeFile(tracePath, JSON.stringify({ data: { invalidating_transaction: {} } }));
  await writeFile(
    normalizedPath,
    JSON.stringify({
      records: [
        {
          incident_id: "incident-generic",
          pcl_tx_id: "tx-generic",
          transaction_hash: txHash,
          debug_trace_status: "completed",
          transfer_from_calls: [
            { token: zeroDecimalToken, source_owner: ownerOne, recipient, raw_amount: "1" },
            { token: dai, source_owner: ownerTwo, recipient, raw_amount: "1000000000000000000" },
          ],
          events: [],
          allowance_checks: [{ token: zeroDecimalToken, owner: ownerOne, spender: adopter, returned: "1" }],
        },
      ],
    }),
  );
  await writeFile(
    contextPath,
    JSON.stringify({
      addresses: [
        { address: zeroDecimalToken, code_type: "contract", verified_source_available: true },
        { address: dai, code_type: "contract", verified_source_available: true },
      ],
    }),
  );
  await writeFile(
    decompilationPath,
    JSON.stringify({ decompiler: "heimdall-rs", completed_count: 10, skipped_count: 0, error_count: 0 }),
  );
  await writeFile(
    statePath,
    JSON.stringify({
      transaction: null,
      receipt: null,
      tokens: {
        [zeroDecimalToken.toLowerCase()]: { symbol: "GOV", decimals: 0 },
        [dai.toLowerCase()]: { symbol: "DAI", decimals: 18 },
      },
      reads: [
        {
          token: zeroDecimalToken,
          source_owner: ownerOne,
          balance_at_block: "1",
          balance_latest: "",
          allowance_latest: "",
        },
      ],
    }),
  );

  const packetScriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "build_evidence_packet.py",
  );
  await execFileAsync("python3", [
    packetScriptPath,
    "--run-dir",
    tempDir,
    "--project",
    "generic-vault",
    "--project-id",
    "project-generic",
    "--chain-id",
    "8453",
    "--incident-json",
    incidentPath,
    "--trace-json",
    tracePath,
    "--normalized-json",
    normalizedPath,
    "--contract-context",
    contextPath,
    "--decompilation-manifest",
    decompilationPath,
    "--aux-file",
    `state reads=${statePath}`,
    "--pcl-tx-id",
    "tx-generic",
    "--out",
    outPath,
  ]);

  const renderScriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "render_fast_report.py",
  );
  await execFileAsync("python3", [
    renderScriptPath,
    "--packet",
    outPath,
    "--run-dir",
    tempDir,
    "--out",
    reportPath,
  ]);

  const report = await readFile(reportPath, "utf8");
  assert.match(report, /PCL Invalidation Triage Report: generic-vault/);
  assert.match(report, /Base \/ 8453/);
  assert.match(report, /VaultBalanceAssertion/);
  assert.match(report, /VaultRouter/);
  assert.match(report, /1\.000000 GOV/);
  assert.match(report, /1\.000000 DAI/);
  assert.match(report, /Decompiler output is approximate/);
  assert.doesNotMatch(report, /0x-settler/);
  assert.doesNotMatch(report, /LineaSettler/);
  assert.doesNotMatch(report, /AllowanceAssertion/);
  assert.doesNotMatch(report, /1,000,000,000,000\.000000/);
});
