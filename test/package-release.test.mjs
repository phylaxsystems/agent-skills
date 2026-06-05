import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import manifest from "../src/manifest.json" with { type: "json" };

const execFileAsync = promisify(execFile);
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const skillsBinName = process.platform === "win32" ? "agent-skills.cmd" : "agent-skills";

function installTargetRoot(homeRoot, contentType) {
  return path.join(homeRoot, ".codex", contentType);
}

function listManifestFiles(item) {
  if (Array.isArray(item.files)) {
    return item.files;
  }

  if (typeof item.file === "string") {
    return [item.file];
  }

  return [];
}

async function assertBundledFilesExist(packageRoot, items) {
  for (const item of Object.values(items)) {
    for (const file of listManifestFiles(item)) {
      await access(path.join(packageRoot, item.basePath, file), constants.F_OK);
    }
  }
}

async function assertInstalledFilesExist(homeRoot, items, contentType) {
  const targetRoot = installTargetRoot(homeRoot, contentType);

  for (const [itemName, item] of Object.entries(items)) {
    for (const file of listManifestFiles(item)) {
      const destination =
        typeof item.file === "string"
          ? path.join(targetRoot, item.file)
          : path.join(targetRoot, itemName, file);

      await access(destination, constants.F_OK);
    }
  }
}

test("published tarball includes bundled content and installs everything for Codex", async (t) => {
  const npmCacheDir = await mkdtemp(path.join(tmpdir(), "skills-release-cache-"));
  t.after(async () => {
    await rm(npmCacheDir, { recursive: true, force: true });
  });

  const packEnv = {
    ...process.env,
    NPM_CONFIG_CACHE: npmCacheDir,
  };

  const { stdout: packStdout } = await execFileAsync(npmCommand, ["pack", "--json"], {
    cwd: process.cwd(),
    env: packEnv,
  });
  const [{ filename }] = JSON.parse(packStdout);
  const tarballPath = path.join(process.cwd(), filename);

  t.after(async () => {
    await rm(tarballPath, { force: true });
  });

  const consumerDir = await mkdtemp(path.join(tmpdir(), "skills-release-consumer-"));
  t.after(async () => {
    await rm(consumerDir, { recursive: true, force: true });
  });

  await writeFile(
    path.join(consumerDir, "package.json"),
    JSON.stringify({ name: "skills-release-consumer", private: true }, null, 2),
  );

  await execFileAsync(npmCommand, ["install", tarballPath], {
    cwd: consumerDir,
    env: packEnv,
  });

  const packageRoot = path.join(consumerDir, "node_modules", "@phylax-systems", "agent-skills");
  const installedManifest = JSON.parse(
    await readFile(path.join(packageRoot, "src", "manifest.json"), "utf8"),
  );

  assert.deepEqual(installedManifest, manifest);
  await access(path.join(consumerDir, "node_modules", ".bin", skillsBinName), constants.F_OK);
  await assertBundledFilesExist(packageRoot, installedManifest.skills);
  await assertBundledFilesExist(packageRoot, installedManifest.workflows ?? {});
  await assertBundledFilesExist(packageRoot, installedManifest.agents ?? {});

  const { stdout: listStdout, stderr: listStderr } = await execFileAsync(
    path.join(consumerDir, "node_modules", ".bin", skillsBinName),
    ["list"],
    { cwd: consumerDir, env: packEnv },
  );

  assert.equal(listStderr, "");
  assert.deepEqual(listStdout.trim().split("\n"), Object.keys(manifest.skills).sort());

  const homeRoot = await mkdtemp(path.join(tmpdir(), "skills-release-home-"));
  t.after(async () => {
    await rm(homeRoot, { recursive: true, force: true });
  });

  const { stdout: installStdout, stderr: installStderr } = await execFileAsync(
    path.join(consumerDir, "node_modules", ".bin", skillsBinName),
    ["install", "everything", "--agent", "codex", "--dir", homeRoot],
    { cwd: consumerDir, env: packEnv },
  );

  assert.equal(installStderr, "");
  assert.match(installStdout, /Installed \d+ skills?, \d+ workflows?, \d+ agents?/);
  await assertInstalledFilesExist(homeRoot, installedManifest.skills, "skills");
  await assertInstalledFilesExist(homeRoot, installedManifest.workflows ?? {}, "workflows");
  await assertInstalledFilesExist(homeRoot, installedManifest.agents ?? {}, "agents");
});
