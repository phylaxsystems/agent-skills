import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { chmod, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
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

test("check_triage_requirements can skip keyed explorer APIs in no-key mode", async () => {
  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync(
      "python3",
      [scriptPath, "--chain-id", "777777", "--require-explorer", "--no-api-keys", "--json"],
      {
        cwd: process.cwd(),
        env: {
          PATH: process.env.PATH ?? "",
          ETHERSCAN_API_KEY: "must-not-be-required",
          ALCHEMY_API_KEY: "must-not-be-used",
        },
      },
    );
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const explorerRequirement = report.requirements.find((item) => item.name === "keyed_explorer_api");
  const sourceRequirement = report.requirements.find((item) => item.name === "keyless_source_lookup");
  assert.ok(explorerRequirement);
  assert.equal(explorerRequirement.ok, true);
  assert.match(explorerRequirement.notes.join(" "), /--no-api-keys/);
  assert.ok(sourceRequirement);
  assert.equal(sourceRequirement.ok, true);
});

test("requirements helper lists public RPC fallback for supported chains", async () => {
  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );
  const code = [
    "import importlib.util",
    `spec = importlib.util.spec_from_file_location("check_reqs", ${JSON.stringify(scriptPath)})`,
    "module = importlib.util.module_from_spec(spec)",
    "spec.loader.exec_module(module)",
    "print('\\n'.join(module.public_rpc_options('59144')))",
  ].join("; ");

  const { stdout } = await execFileAsync("python3", ["-c", code], {
    cwd: process.cwd(),
    env: { PATH: process.env.PATH ?? "" },
  });

  assert.match(stdout, /https:\/\/rpc\.linea\.build/);
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

test("collect_contract_context can ignore explorer API keys in no-key mode", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-contract-context-nokey-"));
  const tracePath = path.join(tempDir, "trace.txt");
  const outDir = path.join(tempDir, "contract_context");
  const callTarget = `0x${"8".repeat(40)}`;

  await writeFile(tracePath, `${callTarget}::execute()\n`);

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "collect_contract_context.py",
  );
  await execFileAsync(
    "python3",
    [
      scriptPath,
      "--chain-id",
      "777777",
      "--out-dir",
      outDir,
      "--allow-missing-rpc",
      "--skip-sourcify",
      "--no-api-keys",
      tracePath,
    ],
    {
      cwd: process.cwd(),
      env: {
        PATH: process.env.PATH ?? "",
        ETHERSCAN_API_KEY: "must-not-be-used",
        EXPLORER_API_KEY: "must-not-be-used",
      },
    },
  );

  const manifest = JSON.parse(
    await readFile(path.join(outDir, "contract_context_manifest.json"), "utf8"),
  );
  assert.equal(manifest.no_api_keys, true);
  assert.equal(manifest.keyed_explorer_configured, false);
  assert.equal(manifest.addresses[0].etherscan_source, null);
});

test("check_triage_requirements requires Heimdall for decompiler access", async () => {
  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync(
      "python3",
      [scriptPath, "--chain-id", "777777", "--require-decompiler", "--json"],
      {
        cwd: process.cwd(),
        env: {
          PATH: "/usr/bin:/bin",
        },
      },
    );
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const requirement = report.requirements.find((item) => item.name === "heimdall_decompiler");
  assert.equal(requirement.configured, false);
  assert.equal(requirement.ok, false);
  assert.match(requirement.error, /Missing Heimdall-rs/);
});

test("check_triage_requirements accepts Heimdall on PATH", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-heimdall-path-"));
  const heimdallPath = path.join(tempDir, "heimdall");
  await writeFile(heimdallPath, "#!/bin/sh\nexit 0\n");
  await chmod(heimdallPath, 0o755);

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync(
      "python3",
      [scriptPath, "--chain-id", "777777", "--require-decompiler", "--json"],
      {
        cwd: process.cwd(),
        env: {
          PATH: `${tempDir}:/usr/bin:/bin`,
        },
      },
    );
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const requirement = report.requirements.find((item) => item.name === "heimdall_decompiler");
  assert.equal(requirement.configured, true);
  assert.equal(requirement.ok, true);
  assert.equal(requirement.selected_source, heimdallPath);
});

test("check_triage_requirements accepts HEIMDALL_BIN", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-heimdall-bin-"));
  const heimdallPath = path.join(tempDir, "custom-heimdall");
  await writeFile(heimdallPath, "#!/bin/sh\nexit 0\n");
  await chmod(heimdallPath, 0o755);

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync(
      "python3",
      [scriptPath, "--chain-id", "777777", "--require-decompiler", "--json"],
      {
        cwd: process.cwd(),
        env: {
          PATH: "/usr/bin:/bin",
          HEIMDALL_BIN: heimdallPath,
        },
      },
    );
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const requirement = report.requirements.find((item) => item.name === "heimdall_decompiler");
  assert.equal(requirement.configured, true);
  assert.equal(requirement.ok, true);
  assert.equal(requirement.selected_source, "HEIMDALL_BIN");
});

test("check_triage_requirements rejects non-executable HEIMDALL_BIN", async () => {
  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "check_triage_requirements.py",
  );

  let stdout = "";
  try {
    await execFileAsync(
      "python3",
      [scriptPath, "--chain-id", "777777", "--require-decompiler", "--json"],
      {
        cwd: process.cwd(),
        env: {
          PATH: "/usr/bin:/bin",
          HEIMDALL_BIN: "/tmp/not-heimdall",
        },
      },
    );
  } catch (error) {
    stdout = error.stdout;
    assert.equal(error.code, 2);
  }

  const report = JSON.parse(stdout);
  const requirement = report.requirements.find((item) => item.name === "heimdall_decompiler");
  assert.equal(requirement.configured, true);
  assert.equal(requirement.ok, false);
  assert.match(requirement.error, /HEIMDALL_BIN is set but is not executable/);
});

test("collect_contract_context ignores non-address hex substrings", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-contract-context-"));
  const tracePath = path.join(tempDir, "trace.txt");
  const outDir = path.join(tempDir, "contract_context");
  const callTarget = `0x${"1".repeat(40)}`;
  const created = `0x${"2".repeat(40)}`;
  const txHash = `0x${"3".repeat(64)}`;
  const storageSlot = `0x${"4".repeat(64)}`;
  const bytecode = `0x60806040${"5".repeat(120)}`;

  await writeFile(
    tracePath,
    [
      txHash,
      `0x08c379a${"0".repeat(56)}`,
      bytecode,
      `@ ${storageSlot}: 0 -> 1`,
      `→ new <unknown>@${created}`,
      `${callTarget}::transfer(${created}, 1)`,
      `← [Return] 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`,
    ].join("\n"),
  );

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "collect_contract_context.py",
  );
  await execFileAsync(
    "python3",
    [scriptPath, "--chain-id", "777777", "--out-dir", outDir, "--allow-missing-rpc", tracePath],
    {
      cwd: process.cwd(),
      env: { PATH: process.env.PATH ?? "" },
    },
  );

  const manifest = JSON.parse(
    await readFile(path.join(outDir, "contract_context_manifest.json"), "utf8"),
  );
  const addresses = manifest.addresses.map((item) => item.address.toLowerCase());

  assert.deepEqual(addresses, [callTarget, created].map((address) => address.toLowerCase()).sort());
  assert.deepEqual(manifest.created_addresses, [created.toLowerCase()]);
});
