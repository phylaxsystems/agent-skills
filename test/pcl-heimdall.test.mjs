import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { chmod, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

test("run_heimdall_decompiler runs heimdall decompile and writes artifacts", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-heimdall-"));
  const binDir = path.join(tempDir, "bin");
  const heimdallPath = path.join(binDir, "heimdall");
  const bytecodePath = path.join(tempDir, "bytecode.txt");
  const manifestPath = path.join(tempDir, "contract_context_manifest.json");
  const outDir = path.join(tempDir, "decompiled");
  const address = `0x${"a".repeat(40)}`;

  await writeFile(bytecodePath, "0x60006000\n");
  await writeFile(
    manifestPath,
    JSON.stringify({
      chain_id: "1",
      decompiler_targets: [
        {
          address,
          bytecode_path: bytecodePath,
          reason: "runtime bytecode found but no verified source",
        },
        {
          address: `0x${"b".repeat(40)}`,
          bytecode_path: null,
          reason: "trace-created contract without runtime bytecode",
        },
      ],
    }),
  );

  await execFileAsync("mkdir", ["-p", binDir]);
  await writeFile(
    heimdallPath,
    [
      "#!/usr/bin/env node",
      "const fs = require('node:fs');",
      "const args = process.argv.slice(2);",
      "fs.writeFileSync(process.env.HEIMDALL_ARGS_PATH, JSON.stringify(args));",
      "if (args[0] !== 'decompile') process.exit(9);",
      "console.log('contract Decompiled { function fallback_() external payable {} }');",
    ].join("\n"),
  );
  await chmod(heimdallPath, 0o755);

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "run_heimdall_decompiler.py",
  );
  const argsPath = path.join(tempDir, "heimdall_args.json");
  const { stdout } = await execFileAsync(
    "python3",
    [scriptPath, manifestPath, "--out-dir", outDir, "--require-success"],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        PATH: `${binDir}:${process.env.PATH ?? ""}`,
        HEIMDALL_ARGS_PATH: argsPath,
      },
    },
  );

  const result = JSON.parse(stdout);
  assert.equal(result.decompiler, "heimdall-rs");
  assert.equal(result.completed_count, 1);
  assert.equal(result.skipped_count, 1);
  assert.equal(result.error_count, 0);
  assert.equal(result.results[0].status, "completed");
  assert.equal(result.results[1].status, "skipped");

  const heimdallArgs = JSON.parse(await readFile(argsPath, "utf8"));
  assert.deepEqual(heimdallArgs, [
    "decompile",
    "0x60006000",
    "--default",
    "--include-sol",
    "--output",
    "print",
  ]);

  const contractDir = path.join(outDir, "1", address.toLowerCase());
  assert.match(await readFile(path.join(contractDir, "source.sol"), "utf8"), /contract Decompiled/);
  const manifest = JSON.parse(
    await readFile(path.join(outDir, "heimdall_decompilation_manifest.json"), "utf8"),
  );
  assert.equal(manifest.completed_count, 1);
});
