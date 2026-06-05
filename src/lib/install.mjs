import { access, mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";

import { readBundledSkillFile } from "./bundle.mjs";
import {
  assertSafePathSegment,
  normalizeSafeRelativePath,
  resolveInside,
} from "./path-safety.mjs";

function listNames(items) {
  return Object.keys(items).sort();
}

function listItemFiles(item) {
  if (Array.isArray(item.files)) {
    return item.files;
  }

  if (typeof item.file === "string") {
    return [item.file];
  }

  return [];
}

function listSkillNames(manifest) {
  return listNames(manifest.skills);
}

async function installItem({
  items,
  itemName,
  itemType,
  targetRoot,
  force = false,
  loadFile = readBundledSkillFile,
}) {
  const item = items[itemName];

  if (!item) {
    throw new Error(`Unknown ${itemType} "${itemName}". Available: ${listNames(items).join(", ")}`);
  }

  if (typeof loadFile !== "function") {
    throw new TypeError("loadFile is required");
  }

  const safeItemName = assertSafePathSegment(itemName, `${itemType} name`);
  const safeBasePath = normalizeSafeRelativePath(item.basePath, `${itemType} base path`);
  const files = listItemFiles(item).map((file) =>
    normalizeSafeRelativePath(file, `${itemType} file path`),
  );

  await mkdir(targetRoot, { recursive: true });

  if (files.length === 0) {
    throw new Error(`No bundled files configured for ${itemType} "${itemName}".`);
  }

  if (typeof item.file === "string") {
    const file = files[0];
    const finalPath = resolveInside(targetRoot, file, `${itemType} destination path`);

    try {
      await access(finalPath, constants.F_OK);
      if (!force) {
        throw new Error(`Destination already exists: ${finalPath}. Re-run with --force to overwrite.`);
      }
      await rm(finalPath, { force: true });
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
    }

    const tempDir = await mkdtemp(path.join(targetRoot, `.${safeItemName}-tmp-`));
    const stagedPath = resolveInside(tempDir, file, `${itemType} staged path`);

    try {
      const content = await loadFile({
        basePath: safeBasePath,
        file,
      });

      await mkdir(path.dirname(stagedPath), { recursive: true });
      await writeFile(stagedPath, content);
      await rename(stagedPath, finalPath);
    } catch (error) {
      await rm(tempDir, { recursive: true, force: true });
      throw error;
    }

    await rm(tempDir, { recursive: true, force: true });
    return finalPath;
  }

  const finalDir = resolveInside(targetRoot, safeItemName, `${itemType} destination path`);

  try {
    await access(finalDir, constants.F_OK);
    if (!force) {
      throw new Error(`Destination already exists: ${finalDir}. Re-run with --force to overwrite.`);
    }
    await rm(finalDir, { recursive: true, force: true });
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }

  const tempDir = await mkdtemp(path.join(targetRoot, `.${safeItemName}-tmp-`));
  const stagedDir = resolveInside(tempDir, safeItemName, `${itemType} staged path`);

  try {
    await mkdir(stagedDir, { recursive: true });

    for (const file of files) {
      const content = await loadFile({
        basePath: safeBasePath,
        file,
      });
      const destination = resolveInside(stagedDir, file, `${itemType} file destination path`);

      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(destination, content);
    }

    await rename(stagedDir, finalDir);
  } catch (error) {
    await rm(tempDir, { recursive: true, force: true });
    throw error;
  }

  await rm(tempDir, { recursive: true, force: true });
  return finalDir;
}

export async function installSkill({
  manifest,
  skillName,
  targetRoot,
  force = false,
  loadSkillFile = readBundledSkillFile,
}) {
  return installItem({
    items: manifest.skills,
    itemName: skillName,
    itemType: "skill",
    targetRoot,
    force,
    loadFile: loadSkillFile,
  });
}

export async function installAllSkills(options) {
  for (const skillName of listSkillNames(options.manifest)) {
    await installSkill({ ...options, skillName });
  }
}

export async function installWorkflow({
  manifest,
  workflowName,
  targetRoot,
  force = false,
  loadWorkflowFile = readBundledSkillFile,
}) {
  const workflows = manifest.workflows ?? {};
  return installItem({
    items: workflows,
    itemName: workflowName,
    itemType: "workflow",
    targetRoot,
    force,
    loadFile: loadWorkflowFile,
  });
}

export async function installAllWorkflows(options) {
  const workflows = options.manifest.workflows ?? {};
  for (const workflowName of listNames(workflows)) {
    await installWorkflow({ ...options, workflowName });
  }
}

export async function installAgent({
  manifest,
  agentName,
  targetRoot,
  force = false,
  loadAgentFile = readBundledSkillFile,
}) {
  return installItem({
    items: manifest.agents ?? {},
    itemName: agentName,
    itemType: "agent",
    targetRoot,
    force,
    loadFile: loadAgentFile,
  });
}

export async function installAllAgents(options) {
  const agents = options.manifest.agents ?? {};
  for (const agentName of listNames(agents)) {
    await installAgent({ ...options, agentName });
  }
}
