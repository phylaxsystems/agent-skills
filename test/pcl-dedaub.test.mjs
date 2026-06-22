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

function startMockDedaubServer(assertions) {
  const server = createServer(async (request, response) => {
    try {
      assertions.requests.push({
        method: request.method,
        url: request.url,
        apiKey: request.headers["x-api-key"],
      });

      if (request.method === "POST" && request.url === "/api/on_demand") {
        const body = await readRequestBody(request);
        assertions.submittedBody = JSON.parse(body);
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify("0x11111111111111111111111111111111"));
        return;
      }

      if (
        request.method === "GET" &&
        request.url === "/api/on_demand/0x11111111111111111111111111111111/status"
      ) {
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify(assertions.statusResponses.shift() ?? "COMPLETED"));
        return;
      }

      if (
        request.method === "GET" &&
        request.url === "/api/on_demand/decompilation/0x11111111111111111111111111111111"
      ) {
        response.setHeader("Content-Type", "application/json");
        response.end(
          JSON.stringify({
            md5: "0x11111111111111111111111111111111",
            bytecode: "0x60006000",
            disassembled: "0x0: PUSH1 0x00",
            tac: "tac output",
            yul: "object \"Mock\" {}",
            source: "function fallback() public payable {}",
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

test("run_dedaub_decompiler submits bytecode, polls, and writes artifacts", async () => {
  const assertions = {
    requests: [],
    submittedBody: null,
    statusResponses: ["SCHEDULED", "COMPLETED"],
  };
  const { server, baseUrl } = await startMockDedaubServer(assertions);
  try {
    const tempDir = await mkdtemp(path.join(tmpdir(), "pcl-dedaub-"));
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

    const scriptPath = path.join(
      process.cwd(),
      "skills",
      "pcl-invalidation-deep-dive",
      "scripts",
      "run_dedaub_decompiler.py",
    );
    const { stdout } = await execFileAsync(
      "python3",
      [
        scriptPath,
        manifestPath,
        "--out-dir",
        outDir,
        "--api-key",
        "test-key",
        "--base-url",
        baseUrl,
        "--timeout-seconds",
        "5",
        "--poll-interval-seconds",
        "0.01",
        "--require-completed",
      ],
      { cwd: process.cwd() },
    );

    const result = JSON.parse(stdout);
    assert.equal(assertions.submittedBody, "0x60006000");
    assert.ok(assertions.requests.every((request) => request.apiKey === "test-key"));
    assert.equal(result.completed_count, 1);
    assert.equal(result.skipped_count, 1);
    assert.equal(result.results[0].status, "COMPLETED");
    assert.equal(result.results[1].status, "skipped");

    const source = await readFile(
      path.join(outDir, "1", address.toLowerCase(), "source.sol"),
      "utf8",
    );
    assert.match(source, /fallback/);

    const manifest = JSON.parse(
      await readFile(path.join(outDir, "dedaub_decompilation_manifest.json"), "utf8"),
    );
    assert.equal(manifest.completed_count, 1);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
