import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { copyFile, mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { generateManifest, parseFrontmatter } from "../scripts/generate-manifest.mjs";

const execFileAsync = promisify(execFile);

test("generateManifest collects skill directories and files", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "skills-manifest-"));

  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await mkdir(path.join(root, "skills", "eth"), { recursive: true });
  await mkdir(path.join(root, "skills", "rust", "references"), { recursive: true });
  await mkdir(path.join(root, "agents", "planner"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n# Rust\n",
  );
  await writeFile(path.join(root, "skills", "rust", "references", "tips.md"), "Use cargo fmt.\n");
  await writeFile(path.join(root, "skills", "eth", "README.md"), "# Ethereum\n");
  await writeFile(
    path.join(root, "agents", "planner", "AGENT.md"),
    "---\nname: planner\ndescription: Planner agent\n---\n# Planner\n",
  );
  await writeFile(path.join(root, "agents", "planner", "openai.yaml"), "display_name: Planner\n");

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
    agentsDir: path.join(root, "agents"),
  });

  assert.deepEqual(manifest, {
    agents: {
      planner: {
        basePath: "agents/planner",
        description: "Planner agent",
        files: ["AGENT.md", "openai.yaml"],
      },
    },
    skills: {
      rust: {
        basePath: "skills/rust",
        description: "Rust skill",
        files: ["SKILL.md", "references/tips.md"],
      },
    },
  });
});

test("generate-manifest script writes src/manifest.json when run directly", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "skills-manifest-script-"));

  await mkdir(path.join(root, "scripts"), { recursive: true });
  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await mkdir(path.join(root, "skills", "eth"), { recursive: true });
  await mkdir(path.join(root, "src"), { recursive: true });
  await copyFile(
    path.join(process.cwd(), "scripts", "generate-manifest.mjs"),
    path.join(root, "scripts", "generate-manifest.mjs"),
  );
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n# Rust\n",
  );
  await writeFile(path.join(root, "skills", "eth", "README.md"), "# Ethereum\n");
  await writeFile(path.join(root, "src", "manifest.json"), "{}\n");

  await execFileAsync("node", ["scripts/generate-manifest.mjs"], { cwd: root });

  assert.deepEqual(JSON.parse(await readFile(path.join(root, "src", "manifest.json"), "utf8")), {
    agents: {},
    skills: {
      rust: { basePath: "skills/rust", description: "Rust skill", files: ["SKILL.md"] },
    },
  });
});

test("generateManifest collects workflow directories with WORKFLOW.md marker", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "wf-manifest-"));

  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await mkdir(path.join(root, "workflows", "plan-implement-review", "references"), {
    recursive: true,
  });
  await mkdir(path.join(root, "workflows", "empty-dir"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n# Rust\n",
  );
  await writeFile(
    path.join(root, "workflows", "plan-implement-review", "WORKFLOW.md"),
    "---\nname: plan-implement-review\ndescription: Three-phase workflow\n---\n# PIR\n",
  );
  await writeFile(
    path.join(root, "workflows", "plan-implement-review", "references", "state-schema.md"),
    "# Schema\n",
  );
  await writeFile(
    path.join(root, "workflows", "empty-dir", "README.md"),
    "# No marker\n",
  );

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
  });

  assert.deepEqual(manifest, {
    agents: {},
    skills: {
      rust: {
        basePath: "skills/rust",
        description: "Rust skill",
        files: ["SKILL.md"],
      },
    },
    workflows: {
      "plan-implement-review": {
        basePath: "workflows/plan-implement-review",
        description: "Three-phase workflow",
        files: ["WORKFLOW.md", "references/state-schema.md"],
      },
    },
  });
});

test("generateManifest collects top-level markdown agent files", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "agent-file-manifest-"));

  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await mkdir(path.join(root, "agents"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n",
  );
  await writeFile(
    path.join(root, "agents", "ui-audit.md"),
    "---\nname: ui-audit\ndescription: UI audit agent\n---\n# UI Audit\n",
  );

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
    agentsDir: path.join(root, "agents"),
  });

  assert.deepEqual(manifest.agents["ui-audit"], {
    basePath: "agents",
    description: "UI audit agent",
    file: "ui-audit.md",
  });
});

test("generateManifest omits workflows key when no workflows exist", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "wf-manifest-empty-"));

  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n",
  );

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
    agentsDir: path.join(root, "agents"),
  });

  assert.equal(manifest.workflows, undefined);
  assert.deepEqual(manifest.agents, {});
});

test("generateManifest excludes .DS_Store files", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "manifest-dsstore-"));

  await mkdir(path.join(root, "skills", "rust"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n",
  );
  await writeFile(path.join(root, "skills", "rust", ".DS_Store"), "");

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
    agentsDir: path.join(root, "agents"),
  });

  assert.deepEqual(manifest.skills.rust.files, ["SKILL.md"]);
});

test("generateManifest excludes Python cache artifacts", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "manifest-pycache-"));

  await mkdir(path.join(root, "skills", "rust", "scripts", "__pycache__"), { recursive: true });
  await writeFile(
    path.join(root, "skills", "rust", "SKILL.md"),
    "---\nname: rust\ndescription: Rust skill\n---\n",
  );
  await writeFile(path.join(root, "skills", "rust", "scripts", "tool.py"), "print('ok')\n");
  await writeFile(
    path.join(root, "skills", "rust", "scripts", "__pycache__", "tool.cpython-312.pyc"),
    "",
  );
  await writeFile(path.join(root, "skills", "rust", "scripts", "tool.pyo"), "");

  const manifest = await generateManifest({
    skillsDir: path.join(root, "skills"),
    workflowsDir: path.join(root, "workflows"),
    agentsDir: path.join(root, "agents"),
  });

  assert.deepEqual(manifest.skills.rust.files, ["SKILL.md", "scripts/tool.py"]);
});

test("optimize-assertion-triggers skill ships with Codex UI metadata", async () => {
  const manifest = await generateManifest({
    skillsDir: path.join(process.cwd(), "skills"),
  });

  assert.ok(
    manifest.skills["optimize-assertion-triggers"].files.includes("agents/openai.yaml"),
  );
});

test("Codex skills advertise a default prompt in agents/openai.yaml", async () => {
  const openaiYaml = await readFile(
    path.join(process.cwd(), "skills", "optimize-assertion-triggers", "agents", "openai.yaml"),
    "utf8",
  );

  assert.match(openaiYaml, /default_prompt:/);
  assert.match(openaiYaml, /short_description:/);
});

test("parseFrontmatter strips matching quotes from scalar values", () => {
  const metadata = parseFrontmatter(
    "---\nname: \"quoted-name\"\ndescription: 'Quoted description'\nplain: value\n---\n",
  );

  assert.deepEqual(metadata, {
    name: "quoted-name",
    description: "Quoted description",
    plain: "value",
  });
});
