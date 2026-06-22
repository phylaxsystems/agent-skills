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

  assert.doesNotMatch(combined, /Improved Transaction Trace/);
  assert.doesNotMatch(combined, /Improved Assertion Trace/);
  assert.doesNotMatch(combined, /improved transaction trace/);
  assert.doesNotMatch(combined, /improved assertion trace/);
});
