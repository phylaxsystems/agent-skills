import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

test("normalize_pcl_trace preserves all debug trace statuses and parses later usable traces", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-normalize-"));
  const fixturePath = path.join(tempDir, "trace.json");
  const token = `0x${"1".repeat(40)}`;
  const source = `0x${"2".repeat(40)}`;
  const recipient = `0x${"3".repeat(40)}`;

  await writeFile(
    fixturePath,
    JSON.stringify({
      data: {
        incident_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        invalidating_transaction: {
          id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
          transaction_hash: `0x${"4".repeat(64)}`,
          from_address: `0x${"5".repeat(40)}`,
          to_address: `0x${"6".repeat(40)}`,
          block_number: 123,
          landed_on_chain: false,
        },
        debug_traces: [
          {
            id: "trace-failed",
            status: "failed",
            transaction_trace_content: null,
            assertion_trace_content: null,
            trace_content: null,
          },
          {
            id: "trace-completed",
            status: "completed",
            transaction_trace_content: `${token}::transferFrom(${source}, ${recipient}, 12345)`,
            assertion_trace_content: "Assertion::check()",
          },
        ],
      },
    }),
  );

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "normalize_pcl_trace.py",
  );
  const { stdout } = await execFileAsync("python3", [scriptPath, fixturePath], {
    cwd: process.cwd(),
  });
  const record = JSON.parse(stdout).records[0];

  assert.equal(record.trace_present, true);
  assert.equal(record.debug_trace_status, "mixed");
  assert.deepEqual(record.debug_trace_statuses, ["failed", "completed"]);
  assert.deepEqual(record.debug_trace_status_counts, { failed: 1, completed: 1 });
  assert.deepEqual(
    record.debug_trace_results.map((result) => ({
      id: result.id,
      status: result.status,
      trace_present: result.trace_present,
    })),
    [
      { id: "trace-failed", status: "failed", trace_present: false },
      { id: "trace-completed", status: "completed", trace_present: true },
    ],
  );
  assert.equal(record.transfer_from_call_count, 1);
  assert.deepEqual(record.transfers[0], {
    token,
    source_owner: source,
    recipient,
    raw_amount: "12345",
    line: `${token}::transferFrom(${source}, ${recipient}, 12345)`,
  });
});
