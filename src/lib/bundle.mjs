import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

import { normalizeSafeRelativePath, resolveInside } from "./path-safety.mjs";

export function resolveBundledSkillFileUrl({ basePath, file }) {
  const safeBasePath = normalizeSafeRelativePath(basePath, "Bundled base path");
  const safeFile = normalizeSafeRelativePath(file, "Bundled file path");
  const packageRoot = fileURLToPath(new URL("../..", import.meta.url));
  const bundledPath = resolveInside(
    packageRoot,
    path.posix.join(safeBasePath, safeFile),
    "Bundled path",
  );

  return pathToFileURL(bundledPath);
}

export async function readBundledSkillFile(options, readFileImpl = readFile) {
  return readFileImpl(resolveBundledSkillFileUrl(options));
}
