import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

function readRequestBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => resolve(body));
    request.on("error", reject);
  });
}

function startMockDecompilerApi(assertions) {
  const server = createServer(async (request, response) => {
    try {
      assertions.requests.push({
        method: request.method,
        url: request.url,
        apiKey: request.headers["x-api-key"],
      });

      if (request.method === "POST" && request.url === "/api/decompile") {
        const body = JSON.parse(await readRequestBody(request));
        assertions.payload = body;
        response.setHeader("Content-Type", "application/json");
        response.end(
          JSON.stringify({
            source: "contract Decompiled { function fallback_() external payable {} }",
            yul: "object \"Decompiled\" {}",
            disassembled: "0x0: PUSH1 0x00",
            abi: [{ type: "fallback", stateMutability: "payable" }],
          }),
        );
        return;
      }

      response.statusCode = 404;
      response.end("not found");
    } catch (error) {
      response.statusCode = 500;
      response.end(String(error.stack || error));
    }
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });
}

test("run_decompiler command backend runs a configured wrapper and writes artifacts", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-decompiler-command-"));
  const bytecodePath = path.join(tempDir, "bytecode.txt");
  const manifestPath = path.join(tempDir, "contract_context_manifest.json");
  const wrapperPath = path.join(tempDir, "fake_decompiler.py");
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
  await writeFile(
    wrapperPath,
    [
      "import argparse",
      "from pathlib import Path",
      "parser = argparse.ArgumentParser()",
      "parser.add_argument('--bytecode-path')",
      "parser.add_argument('--out-dir')",
      "parser.add_argument('--address')",
      "args = parser.parse_args()",
      "Path(args.out_dir, 'wrapper_source.sol').write_text('contract Wrapped { function target() external {} }\\n')",
      "print(f'contract Printed {{ function at_{args.address[-4:]}() external {{}} }}')",
    ].join("\n"),
  );

  const scriptPath = path.join(
    process.cwd(),
    "skills",
    "pcl-invalidation-deep-dive",
    "scripts",
    "run_decompiler.py",
  );
  const { stdout } = await execFileAsync(
    "python3",
    [
      scriptPath,
      manifestPath,
      "--out-dir",
      outDir,
      "--backend",
      "command",
      "--cmd",
      `python3 ${wrapperPath} --bytecode-path {bytecode_path} --out-dir {out_dir} --address {address}`,
      "--require-success",
    ],
    { cwd: process.cwd() },
  );

  const result = JSON.parse(stdout);
  assert.equal(result.backend, "command");
  assert.equal(result.completed_count, 1);
  assert.equal(result.skipped_count, 1);
  assert.equal(result.error_count, 0);
  assert.equal(result.results[0].status, "completed");
  assert.equal(result.results[1].status, "skipped");

  const contractDir = path.join(outDir, "1", address.toLowerCase());
  assert.match(await readFile(path.join(contractDir, "source.sol"), "utf8"), /contract Printed/);
  assert.match(await readFile(path.join(contractDir, "wrapper_source.sol"), "utf8"), /contract Wrapped/);
  const manifest = JSON.parse(await readFile(path.join(outDir, "decompiler_manifest.json"), "utf8"));
  assert.equal(manifest.completed_count, 1);
});

test("run_decompiler api backend posts bytecode and writes normalized artifacts", async () => {
  const assertions = { requests: [], payload: null };
  const { server, baseUrl } = await startMockDecompilerApi(assertions);
  try {
    const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-decompiler-api-"));
    const bytecodePath = path.join(tempDir, "bytecode.txt");
    const manifestPath = path.join(tempDir, "contract_context_manifest.json");
    const outDir = path.join(tempDir, "decompiled");
    const address = `0x${"c".repeat(40)}`;

    await writeFile(bytecodePath, "0x60006000\n");
    await writeFile(
      manifestPath,
      JSON.stringify({
        chain_id: "8453",
        decompiler_targets: [
          {
            address,
            bytecode_path: bytecodePath,
            reason: "runtime bytecode found but no verified source",
          },
        ],
      }),
    );

    const scriptPath = path.join(
      process.cwd(),
      "skills",
      "pcl-invalidation-deep-dive",
      "scripts",
      "run_decompiler.py",
    );
    const { stdout } = await execFileAsync(
      "python3",
      [
        scriptPath,
        manifestPath,
        "--out-dir",
        outDir,
        "--backend",
        "api",
        "--api-url",
        `${baseUrl}/api/decompile`,
        "--api-key",
        "test-key",
        "--api-key-header",
        "x-api-key",
        "--api-key-prefix",
        "",
        "--require-success",
      ],
      { cwd: process.cwd() },
    );

    const result = JSON.parse(stdout);
    assert.equal(assertions.requests[0].apiKey, "test-key");
    assert.equal(assertions.payload.bytecode, "0x60006000");
    assert.equal(assertions.payload.address, address);
    assert.equal(assertions.payload.chain_id, "8453");
    assert.equal(result.backend, "api");
    assert.equal(result.completed_count, 1);

    const contractDir = path.join(outDir, "8453", address.toLowerCase());
    assert.match(await readFile(path.join(contractDir, "source.sol"), "utf8"), /contract Decompiled/);
    assert.match(await readFile(path.join(contractDir, "yul.yul"), "utf8"), /object/);
    assert.deepEqual(JSON.parse(await readFile(path.join(contractDir, "abi.json"), "utf8")), [
      { type: "fallback", stateMutability: "payable" },
    ]);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
