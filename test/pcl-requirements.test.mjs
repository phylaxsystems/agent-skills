import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

test("check_triage_requirements reports generic chain RPC env options", async () => {
  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync("python3", [scriptPath, "--chain-id", "777777", "--json"], {
      cwd: process.cwd(),
      env: { PATH: process.env.PATH ?? "" },
    });
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const rpcRequirement = report.requirements.find((item) => item.name === "chain_rpc");
  assert.ok(rpcRequirement);
  assert.equal(rpcRequirement.ok, false);
  assert.deepEqual(
    rpcRequirement.acceptable_configuration.slice(0, 5),
    [
      "--rpc-url <url>",
      "CHAIN_777777_RPC_URL",
      "RPC_URL_777777",
      "EVM_777777_RPC_URL",
      "RPC_URL",
    ],
  );
});

test("collect_contract_context missing RPC error names generic chain env options", async () => {
  const tempPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "collect_contract_context.py",
  );

  let stderr = "";
  try {
    await execFileAsync(
      "python3",
      [tempPath, "--chain-id", "777777", "--out-dir", "/tmp/pcl-missing-rpc-test", "README.md"],
      {
        cwd: process.cwd(),
        env: { PATH: process.env.PATH ?? "" },
      },
    );
  } catch (error) {
    stderr = error.stderr;
    assert.equal(error.code, 2);
  }

  assert.match(stderr, /CHAIN_777777_RPC_URL/);
  assert.match(stderr, /RPC_URL_777777/);
  assert.match(stderr, /EVM_777777_RPC_URL/);
});
