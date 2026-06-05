import path from "node:path";

function assertString(value, label) {
  if (typeof value !== "string") {
    throw new TypeError(`${label} must be a string.`);
  }
}

function assertNoUnsafeCharacters(value, label) {
  if (value.includes("\0")) {
    throw new Error(`${label} must not contain null bytes.`);
  }

  if (value.includes("\\")) {
    throw new Error(`${label} must use POSIX-style relative paths.`);
  }

  if (value.includes(":")) {
    throw new Error(`${label} must use portable relative paths.`);
  }
}

export function assertSafePathSegment(value, label) {
  assertString(value, label);
  assertNoUnsafeCharacters(value, label);

  if (
    value.length === 0 ||
    value === "." ||
    value === ".." ||
    value.includes("/") ||
    path.isAbsolute(value) ||
    path.win32.isAbsolute(value)
  ) {
    throw new Error(`${label} must be a single safe path segment.`);
  }

  return value;
}

export function normalizeSafeRelativePath(value, label) {
  assertString(value, label);
  assertNoUnsafeCharacters(value, label);

  if (value.length === 0 || path.isAbsolute(value) || path.win32.isAbsolute(value)) {
    throw new Error(`${label} must be a relative path.`);
  }

  const segments = value.split("/");
  if (segments.some((segment) => segment.length === 0 || segment === "." || segment === "..")) {
    throw new Error(`${label} must not contain empty, current, or parent path segments.`);
  }

  return path.posix.normalize(value);
}

export function resolveInside(root, relativePath, label) {
  const safeRelativePath = normalizeSafeRelativePath(relativePath, label);
  const rootPath = path.resolve(root);
  const resolvedPath = path.resolve(rootPath, safeRelativePath);
  const relativeToRoot = path.relative(rootPath, resolvedPath);

  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) {
    throw new Error(`${label} must stay inside the target root.`);
  }

  return resolvedPath;
}
