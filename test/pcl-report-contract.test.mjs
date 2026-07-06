import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const skillDir = path.join(process.cwd(), "skills", "pcl-invalidation-deep-dive");

test("pcl invalidation report contract uses one full improved trace", async () => {
  const skill = await readFile(path.join(skillDir, "SKILL.md"), "utf8");
  const etl = await readFile(path.join(skillDir, "references", "etl-pipeline.md"), "utf8");
  const combined = `${skill}\n${etl}`;

  assert.match(combined, /Full Improved Trace/);
  assert.match(combined, /one ordered trace that combines the transaction execution and assertion evaluation/);
  assert.match(combined, /The trace must be a single ordered narrative/);
  assert.match(combined, /Fast Packet-Only Report Mode/);
  assert.match(combined, /Target under 90 seconds/);
  assert.match(combined, /Keep the main report to about 1,200-1,800 words/);
  assert.match(combined, /--no-api-keys/);
  assert.match(combined, /External API keys are mandatory/);
  assert.match(combined, /Sourcify/);
  assert.match(combined, /public RPC/);
  assert.match(combined, /capability_selection/);
  assert.match(combined, /private-or-mixed/);
  assert.match(combined, /keyless-public/);
  assert.match(combined, /Data access mode/);
  assert.match(combined, /\{baseDir\}\/scripts\/check_triage_requirements\.py/);

  const bareScriptReferences = combined
    .split("\n")
    .filter((line) => line.includes("scripts/") && !line.includes("{baseDir}/scripts/"));
  assert.deepEqual(bareScriptReferences, []);

  assert.doesNotMatch(combined, /Improved Transaction Trace/);
  assert.doesNotMatch(combined, /Improved Assertion Trace/);
  assert.doesNotMatch(combined, /improved transaction trace/);
  assert.doesNotMatch(combined, /improved assertion trace/);
});
