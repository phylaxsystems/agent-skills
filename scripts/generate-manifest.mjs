import { access, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const IGNORED_FILES = [".DS_Store", "Thumbs.db"];
const IGNORED_DIRECTORIES = ["__pycache__"];
const IGNORED_EXTENSIONS = [".pyc", ".pyo"];

function shouldIgnoreFile(name) {
  return IGNORED_FILES.includes(name) || IGNORED_EXTENSIONS.includes(path.extname(name));
}

async function collectFiles(rootDir, markerFiles, relativeDir = "") {
  const directory = relativeDir ? path.join(rootDir, ...relativeDir.split("/")) : rootDir;
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    const relativePath = relativeDir ? `${relativeDir}/${entry.name}` : entry.name;

    if (entry.isDirectory()) {
      if (IGNORED_DIRECTORIES.includes(entry.name)) {
        continue;
      }
      files.push(...(await collectFiles(rootDir, markerFiles, relativePath)));
      continue;
    }

    if (entry.isFile() && !shouldIgnoreFile(entry.name)) {
      files.push(relativePath);
    }
  }

  return files.sort((left, right) => {
    if (markerFiles.includes(left)) {
      return -1;
    }

    if (markerFiles.includes(right)) {
      return 1;
    }

    return left.localeCompare(right);
  });
}

// Intentionally only supports single-line key: value pairs in YAML frontmatter.
// Multi-line values, list items (- foo), and indented continuation lines are
// silently ignored. All current frontmatter fields are single-line comma-separated.
export function parseFrontmatter(markdown) {
  const lines = markdown.split(/\r?\n/);

  if (lines[0] !== "---") {
    return {};
  }

  const metadata = {};

  for (let index = 1; index < lines.length; index += 1) {
    const line = lines[index];

    if (line === "---") {
      break;
    }

    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);

    if (match) {
      let value = match[2].trim();

      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }

      metadata[match[1]] = value;
    }
  }

  return metadata;
}

async function readContentMetadata(dir, markerFile) {
  const markdown = await readFile(path.join(dir, markerFile), "utf8");
  return parseFrontmatter(markdown);
}

async function readMarkdownMetadata(filePath) {
  const markdown = await readFile(filePath, "utf8");
  return parseFrontmatter(markdown);
}

async function readSkillMetadata(skillDir) {
  const metadata = await readContentMetadata(skillDir, "SKILL.md");
  const result = { description: metadata.description };

  if (metadata.agents) {
    result.agents = metadata.agents
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
  }

  if (metadata.hosts) {
    result.hosts = metadata.hosts
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
  }

  return result;
}

async function scanContentDir(contentDir, markerFiles, basePathPrefix) {
  if (!contentDir) {
    return {};
  }

  let entries;

  try {
    entries = await readdir(contentDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") {
      return {};
    }
    throw error;
  }

  const items = {};

  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isDirectory()) {
      continue;
    }

    const itemDir = path.join(contentDir, entry.name);
    const files = await collectFiles(itemDir, markerFiles);
    const markerFile = markerFiles.find((candidate) => files.includes(candidate));

    if (!markerFile) {
      continue;
    }

    const metadata =
      markerFile === "SKILL.md"
        ? await readSkillMetadata(itemDir)
        : await readContentMetadata(itemDir, markerFile);

    const item = {
      basePath: `${basePathPrefix}/${entry.name}`,
      description: metadata.description,
      files,
    };

    if (metadata.agents) {
      item.agents = metadata.agents;
    }

    if (metadata.hosts) {
      item.hosts = metadata.hosts;
    }

    items[entry.name] = item;
  }

  return items;
}

async function scanAgentsDir(agentsDir) {
  if (!agentsDir) {
    return {};
  }

  let entries;

  try {
    entries = await readdir(agentsDir, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") {
      return {};
    }
    throw error;
  }

  const items = {};

  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (entry.isDirectory()) {
      const itemDir = path.join(agentsDir, entry.name);
      const files = await collectFiles(itemDir, ["AGENT.md", "AGENTS.md"]);
      const markerFile = ["AGENT.md", "AGENTS.md"].find((candidate) => files.includes(candidate));

      if (!markerFile) {
        continue;
      }

      const metadata = await readContentMetadata(itemDir, markerFile);
      items[entry.name] = {
        basePath: `agents/${entry.name}`,
        description: metadata.description,
        files,
      };
      continue;
    }

    if (!entry.isFile() || shouldIgnoreFile(entry.name) || path.extname(entry.name) !== ".md") {
      continue;
    }

    const metadata = await readMarkdownMetadata(path.join(agentsDir, entry.name));

    if (!metadata.name) {
      continue;
    }

    items[metadata.name] = {
      basePath: "agents",
      description: metadata.description,
      file: entry.name,
    };
  }

  return items;
}

export async function generateManifest({ skillsDir, workflowsDir, agentsDir }) {
  const skills = await scanContentDir(skillsDir, ["SKILL.md"], "skills");
  const workflows = await scanContentDir(workflowsDir, ["WORKFLOW.md"], "workflows");
  const agents = await scanAgentsDir(agentsDir);

  const manifest = { skills };

  if (Object.keys(workflows).length > 0) {
    manifest.workflows = workflows;
  }

  manifest.agents = agents;

  return manifest;
}

const currentFile = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(currentFile), "..");

if (process.argv[1] === currentFile) {
  const workflowsDir = path.join(repoRoot, "workflows");
  const manifest = await generateManifest({
    skillsDir: path.join(repoRoot, "skills"),
    workflowsDir,
    agentsDir: await access(path.join(repoRoot, "agents"), constants.F_OK)
      .then(() => path.join(repoRoot, "agents"))
      .catch(() => undefined),
  });

  await mkdir(path.join(repoRoot, "src"), { recursive: true });
  await writeFile(
    path.join(repoRoot, "src", "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
}
