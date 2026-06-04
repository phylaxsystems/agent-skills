import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, mkdtemp, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

import { run } from "../src/cli.mjs";
import {
  installAllAgents,
  installAllSkills,
  installSkill,
  installAgent,
  installWorkflow,
  installAllWorkflows,
} from "../src/lib/install.mjs";
import { loadManifest } from "../src/lib/manifest.mjs";
import {
  promptForAgentSelection,
  promptForInstallSelection,
  promptForWorkflowSelection,
} from "../src/lib/prompt.mjs";
import { resolveInstallRoot, resolveInstallRoots } from "../src/lib/paths.mjs";

const execFileAsync = promisify(execFile);

test("resolveInstallRoot prefers CODEX_HOME", () => {
  assert.equal(
    resolveInstallRoot({
      env: { CODEX_HOME: "/tmp/codex" },
      homedir: () => "/Users/test",
    }),
    path.join("/tmp/codex", "skills"),
  );
});

test("resolveInstallRoots reuses Codex root resolution for non-skill content", () => {
  assert.deepEqual(
    resolveInstallRoots({
      agents: ["codex"],
      contentType: "workflows",
      env: { CODEX_HOME: "/tmp/codex-home" },
      homedir: () => "/Users/test",
    }),
    { codex: path.join("/tmp/codex-home", "workflows") },
  );
});

test("resolveInstallRoots falls back to ~/.codex for Codex when CODEX_HOME is unset", () => {
  assert.deepEqual(
    resolveInstallRoots({
      agents: ["codex"],
      contentType: "agents",
      env: {},
      homedir: () => "/Users/test",
    }),
    { codex: path.join("/Users/test", ".codex", "agents") },
  );
});

test("CLI executes when launched through a symlinked bin path", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "skills-bin-"));
  const symlinkPath = path.join(tempDir, "skills");
  const cliPath = path.resolve("src/cli.mjs");

  await symlink(cliPath, symlinkPath);

  const { stdout, stderr } = await execFileAsync(process.execPath, [symlinkPath, "list"], {
    cwd: process.cwd(),
  });

  assert.equal(stderr, "");
  assert.equal(stdout.trim(), Object.keys(loadManifest().skills).sort().join("\n"));
});

test("installSkill writes every bundled file into the target skill directory", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "skills-install-"));
  const calls = [];
  const manifest = {
    skills: {
      rust: { basePath: "skills/rust", files: ["SKILL.md", "references/tips.md"] },
    },
  };

  await installSkill({
    manifest,
    skillName: "rust",
    targetRoot,
    loadSkillFile: async (fileSpec) => {
      calls.push(fileSpec);
      return "# Rust\n";
    },
  });

  assert.deepEqual(calls, [
    { basePath: "skills/rust", file: "SKILL.md" },
    { basePath: "skills/rust", file: "references/tips.md" },
  ]);
  assert.equal(
    await readFile(path.join(targetRoot, "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  assert.equal(
    await readFile(path.join(targetRoot, "rust", "references", "tips.md"), "utf8"),
    "# Rust\n",
  );
});

test("installSkill refuses overwrite without force", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "skills-overwrite-"));
  await mkdir(path.join(targetRoot, "rust"), { recursive: true });
  await writeFile(path.join(targetRoot, "rust", "SKILL.md"), "existing\n");

  await assert.rejects(
    installSkill({
      manifest: {
        skills: {
          rust: { basePath: "skills/rust", files: ["SKILL.md"] },
        },
      },
      skillName: "rust",
      targetRoot,
      loadSkillFile: async () => "# Rust\n",
    }),
    /already exists/i,
  );
});

test("installSkill rejects manifest file paths that escape the target root", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "skills-path-"));
  const escapeFile = `${path.basename(targetRoot)}-escape.md`;
  const outsidePath = path.join(path.dirname(targetRoot), escapeFile);

  await assert.rejects(
    installSkill({
      manifest: {
        skills: {
          rust: { basePath: "skills/rust", files: [`../${escapeFile}`] },
        },
      },
      skillName: "rust",
      targetRoot,
      loadSkillFile: async () => "# Rust\n",
    }),
    /parent path segments/i,
  );
  await assert.rejects(access(outsidePath, constants.F_OK), /ENOENT/);
});

test("installSkill rejects manifest item names that escape the target root", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "skills-name-"));
  const escapeName = `${path.basename(targetRoot)}-rust`;
  const skillName = `../${escapeName}`;
  const outsidePath = path.join(path.dirname(targetRoot), escapeName);

  await assert.rejects(
    installSkill({
      manifest: {
        skills: {
          [skillName]: { basePath: "skills/rust", files: ["SKILL.md"] },
        },
      },
      skillName,
      targetRoot,
      loadSkillFile: async () => "# Rust\n",
    }),
    /single safe path segment/i,
  );
  await assert.rejects(access(outsidePath, constants.F_OK), /ENOENT/);
});

test("installAllSkills installs every skill in the manifest", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "skills-all-"));

  await installAllSkills({
    manifest: {
      skills: {
        eth: { basePath: "skills/eth", files: ["README.md"] },
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    targetRoot,
    loadSkillFile: async ({ file }) => (file.endsWith("README.md") ? "# Ethereum\n" : "# Rust\n"),
  });

  assert.equal(
    await readFile(path.join(targetRoot, "eth", "README.md"), "utf8"),
    "# Ethereum\n",
  );
  assert.equal(
    await readFile(path.join(targetRoot, "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
});

test("run prints available skills for list", async () => {
  const lines = [];

  const exitCode = await run(["list"], {
    manifest: {
      skills: {
        eth: { basePath: "skills/eth", files: ["README.md"] },
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    version: "0.1.0",
    stdout: (line) => lines.push(line),
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(lines, ["eth", "rust"]);
});

test("run reports unknown skills with a non-zero exit code", async () => {
  const errors = [];

  const exitCode = await run(["install", "missing"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    stderr: (line) => errors.push(line),
    loadSkillFile: async () => "# Rust\n",
    resolveInstallRootImpl: () => "/tmp/ignored",
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /Available/);
});

test("run shows clarified usage for all versus everything", async () => {
  const errors = [];

  const exitCode = await run(["install"], {
    manifest: { skills: {} },
    stderr: (line) => errors.push(line),
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /'all' installs all skills/);
  assert.match(errors[0], /'workflow all' for all workflows/);
  assert.match(errors[0], /'agent all' for all agents/);
  assert.match(errors[0], /'everything' for all bundled content/);
});

test("run installs a skill into Claude Code, Codex, and OpenCode by default", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "skills-multi-agent-"));

  const exitCode = await run(["install", "rust", "--dir", homeRoot], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    loadSkillFile: async () => "# Rust\n",
  });

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(homeRoot, ".claude", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".config", "opencode", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
});

test("run installs a Codex skill into CODEX_HOME/skills by default", async () => {
  const codexHome = await mkdtemp(path.join(tmpdir(), "skills-codex-home-"));
  const fakeHome = await mkdtemp(path.join(tmpdir(), "skills-home-fallback-"));

  const exitCode = await run(["install", "rust", "--agent", "codex"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    env: { CODEX_HOME: codexHome },
    homedir: () => fakeHome,
    loadSkillFile: async () => "# Rust\n",
  });

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(codexHome, "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  await assert.rejects(
    access(path.join(fakeHome, ".codex", "skills", "rust", "SKILL.md"), constants.F_OK),
    /ENOENT/,
  );
});

test("run installs a Codex skill into ~/.codex/skills when CODEX_HOME is unset", async () => {
  const fakeHome = await mkdtemp(path.join(tmpdir(), "skills-home-default-"));

  const exitCode = await run(["install", "rust", "--agent", "codex"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    env: {},
    homedir: () => fakeHome,
    loadSkillFile: async () => "# Rust\n",
  });

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(fakeHome, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
});

test("run supports add plus --agent to target a subset of agents", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "skills-agent-subset-"));

  const exitCode = await run(
    ["add", "rust", "--dir", homeRoot, "--agent", "claude", "--agent", "codex"],
    {
      manifest: {
        skills: {
          rust: { basePath: "skills/rust", files: ["SKILL.md"] },
        },
      },
      loadSkillFile: async () => "# Rust\n",
    },
  );

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(homeRoot, ".claude", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Rust\n",
  );
  await assert.rejects(
    access(path.join(homeRoot, ".config", "opencode", "skills", "rust", "SKILL.md"), constants.F_OK),
    /ENOENT/,
  );
});

test("run reports unknown agents with a non-zero exit code", async () => {
  const errors = [];

  const exitCode = await run(["install", "rust", "--agent", "mystery"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    stderr: (line) => errors.push(line),
    loadSkillFile: async () => "# Rust\n",
    resolveInstallRootImpl: () => "/tmp/ignored",
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /Unknown agent/i);
});

test("promptForInstallSelection accepts numbered skill input and blank agent input", async () => {
  const prompts = [];
  const lines = [];
  const answers = ["2", ""];

  const selection = await promptForInstallSelection({
    skillOptions: [
      { value: "foo", label: "foo", description: "Foo skill" },
      { value: "rust", label: "rust", description: "Rust skill" },
    ],
    agentOptions: [
      { value: "claude-code", label: "claude-code", aliases: ["claude"] },
      { value: "codex", label: "codex" },
      { value: "opencode", label: "opencode" },
    ],
    ask: async (prompt) => {
      prompts.push(prompt);
      return answers.shift();
    },
    writeLine: (line) => lines.push(line),
  });

  assert.deepEqual(selection, {
    skillNames: ["rust"],
    agents: ["claude-code", "codex", "opencode"],
  });
  assert(prompts[0].includes("Enter skill numbers or names"));
  assert(lines.some((line) => line.includes("Rust skill")));
});

test("promptForWorkflowSelection accepts numbered workflow input and blank agent input", async () => {
  const prompts = [];
  const lines = [];
  const answers = ["1", ""];

  const selection = await promptForWorkflowSelection({
    workflowOptions: [
      {
        value: "plan-implement-review",
        label: "plan-implement-review",
        description: "Three-phase workflow",
      },
      { value: "triage", label: "triage", description: "Triage workflow" },
    ],
    agentOptions: [
      { value: "claude-code", label: "claude-code", aliases: ["claude"] },
      { value: "codex", label: "codex" },
      { value: "opencode", label: "opencode" },
    ],
    ask: async (prompt) => {
      prompts.push(prompt);
      return answers.shift();
    },
    writeLine: (line) => lines.push(line),
  });

  assert.deepEqual(selection, {
    workflowNames: ["plan-implement-review"],
    agents: ["claude-code", "codex", "opencode"],
  });
  assert(prompts[0].includes("Enter workflow numbers or names"));
  assert(lines.some((line) => line.includes("Three-phase workflow")));
});

test("promptForAgentSelection accepts numbered agent role input and blank agent input", async () => {
  const prompts = [];
  const lines = [];
  const answers = ["1", ""];

  const selection = await promptForAgentSelection({
    agentRoleOptions: [
      { value: "planner", label: "planner", description: "Planner role" },
      { value: "implementer", label: "implementer", description: "Implementer role" },
    ],
    agentOptions: [
      { value: "codex", label: "codex" },
    ],
    ask: async (prompt) => {
      prompts.push(prompt);
      return answers.shift();
    },
    writeLine: (line) => lines.push(line),
  });

  assert.deepEqual(selection, {
    agentNames: ["planner"],
    agents: ["codex"],
  });
  assert(prompts[0].includes("Enter agent role numbers or names"));
  assert(lines.some((line) => line.includes("Planner role")));
});

test("run prompts interactively when no skill name is provided", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "skills-interactive-"));
  const prompts = [];

  const exitCode = await run(["--dir", homeRoot], {
    manifest: {
      skills: {
        foo: { basePath: "skills/foo", description: "Foo skill", files: ["SKILL.md"] },
        rust: { basePath: "skills/rust", description: "Rust skill", files: ["SKILL.md"] },
      },
    },
    loadSkillFile: async () => "# Skill\n",
    promptForInstallSelectionImpl: async (options) => {
      prompts.push(options);
      return { skillNames: ["rust"], agents: ["codex"] };
    },
  });

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Skill\n",
  );
  await assert.rejects(
    access(path.join(homeRoot, ".claude", "skills", "rust", "SKILL.md"), constants.F_OK),
    /ENOENT/,
  );
  assert.equal(prompts[0].skillOptions[0].description, "Foo skill");
});

test("run skips the agent prompt when --agent is already provided", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "skills-interactive-agent-"));
  const prompts = [];

  const exitCode = await run(["install", "--dir", homeRoot, "--agent", "codex"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", description: "Rust skill", files: ["SKILL.md"] },
      },
    },
    loadSkillFile: async () => "# Skill\n",
    promptForInstallSelectionImpl: async (options) => {
      prompts.push(options);
      return { skillNames: ["rust"], agents: [] };
    },
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(prompts[0].agentOptions, []);
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Skill\n",
  );
});

test("run rejects --ref because skills are bundled in the package", async () => {
  const errors = [];

  const exitCode = await run(["install", "rust", "--ref", "main"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
    },
    stderr: (line) => errors.push(line),
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /no longer supported/i);
});

// --- Workflow tests ---

const WORKFLOW_MANIFEST = {
  skills: {
    rust: { basePath: "skills/rust", files: ["SKILL.md"] },
  },
  workflows: {
    "plan-implement-review": {
      basePath: "workflows/plan-implement-review",
      files: ["WORKFLOW.md", "references/state-schema.md"],
      description: "Three-phase delivery workflow",
    },
  },
};

test("run lists workflows for list workflows", async () => {
  const lines = [];

  const exitCode = await run(["list", "workflows"], {
    manifest: WORKFLOW_MANIFEST,
    stdout: (line) => lines.push(line),
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(lines, ["plan-implement-review"]);
});

test("run lists only skills for list (not workflows)", async () => {
  const lines = [];

  const exitCode = await run(["list"], {
    manifest: WORKFLOW_MANIFEST,
    stdout: (line) => lines.push(line),
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(lines, ["rust"]);
});

test("run installs a single workflow into all agents by default", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "wf-install-single-"));

  const exitCode = await run(
    ["install", "workflow", "plan-implement-review", "--dir", homeRoot],
    {
      manifest: WORKFLOW_MANIFEST,
      loadSkillFile: async () => "# Workflow\n",
    },
  );

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(
      path.join(homeRoot, ".claude", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
  assert.equal(
    await readFile(
      path.join(homeRoot, ".codex", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
  assert.equal(
    await readFile(
      path.join(
        homeRoot,
        ".config",
        "opencode",
        "workflows",
        "plan-implement-review",
        "WORKFLOW.md",
      ),
      "utf8",
    ),
    "# Workflow\n",
  );
});

test("run installs all workflows", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "wf-install-all-"));

  const lines = [];
  const exitCode = await run(["install", "workflow", "all", "--dir", homeRoot], {
    manifest: WORKFLOW_MANIFEST,
    stdout: (line) => lines.push(line),
    loadSkillFile: async () => "# Workflow\n",
  });

  assert.equal(exitCode, 0);
  assert.match(lines[0], /Installed 1 workflow/);
  assert.equal(
    await readFile(
      path.join(homeRoot, ".claude", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
});

const AGENT_MANIFEST = {
  skills: {
    rust: { basePath: "skills/rust", files: ["SKILL.md"] },
  },
  agents: {
    implementer: {
      basePath: "agents/implementer",
      files: ["AGENTS.md"],
      description: "Use for scoped engineering implementation tasks.",
    },
    planner: {
      basePath: "agents/planner",
      files: ["AGENT.md", "openai.yaml"],
      description: "Dedicated planner agent for multi-agent software delivery.",
    },
  },
};

test("run lists agents for list agents", async () => {
  const lines = [];

  const exitCode = await run(["list", "agents"], {
    manifest: AGENT_MANIFEST,
    stdout: (line) => lines.push(line),
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(lines, ["implementer", "planner"]);
});

test("installAgent writes agent files into the target directory", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "agent-unit-install-"));
  const calls = [];

  await installAgent({
    manifest: AGENT_MANIFEST,
    agentName: "planner",
    targetRoot,
    loadAgentFile: async (fileSpec) => {
      calls.push(fileSpec);
      return "# Planner\n";
    },
  });

  assert.deepEqual(calls, [
    { basePath: "agents/planner", file: "AGENT.md" },
    { basePath: "agents/planner", file: "openai.yaml" },
  ]);
  assert.equal(
    await readFile(path.join(targetRoot, "planner", "AGENT.md"), "utf8"),
    "# Planner\n",
  );
  assert.equal(
    await readFile(path.join(targetRoot, "planner", "openai.yaml"), "utf8"),
    "# Planner\n",
  );
});

test("installAgent writes single-file agent definitions into the target root", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "agent-file-install-"));
  const calls = [];

  await installAgent({
    manifest: {
      skills: {},
      agents: {
        "ui-audit": {
          basePath: "agents",
          file: "ui-audit.md",
          description: "UI audit agent",
        },
      },
    },
    agentName: "ui-audit",
    targetRoot,
    loadAgentFile: async (fileSpec) => {
      calls.push(fileSpec);
      return "# UI Audit\n";
    },
  });

  assert.deepEqual(calls, [{ basePath: "agents", file: "ui-audit.md" }]);
  assert.equal(await readFile(path.join(targetRoot, "ui-audit.md"), "utf8"), "# UI Audit\n");
});

test("installAllAgents installs every agent in the manifest", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "agent-unit-all-"));

  await installAllAgents({
    manifest: AGENT_MANIFEST,
    targetRoot,
    loadAgentFile: async () => "# Agent\n",
  });

  assert.equal(
    await readFile(path.join(targetRoot, "implementer", "AGENTS.md"), "utf8"),
    "# Agent\n",
  );
  assert.equal(
    await readFile(path.join(targetRoot, "planner", "AGENT.md"), "utf8"),
    "# Agent\n",
  );
});

test("run installs a single agent into all agent targets by default", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "agent-install-single-"));

  const exitCode = await run(
    ["install", "agent", "planner", "--dir", homeRoot],
    {
      manifest: AGENT_MANIFEST,
      loadSkillFile: async () => "# Agent\n",
    },
  );

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(path.join(homeRoot, ".claude", "agents", "planner", "AGENT.md"), "utf8"),
    "# Agent\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "agents", "planner", "AGENT.md"), "utf8"),
    "# Agent\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".config", "opencode", "agents", "planner", "AGENT.md"), "utf8"),
    "# Agent\n",
  );
});

test("run installs all agents", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "agent-install-all-"));
  const lines = [];

  const exitCode = await run(["install", "agent", "all", "--dir", homeRoot], {
    manifest: AGENT_MANIFEST,
    stdout: (line) => lines.push(line),
    loadSkillFile: async () => "# Agent\n",
  });

  assert.equal(exitCode, 0);
  assert.match(lines[0], /Installed 2 agents/);
  assert.equal(
    await readFile(path.join(homeRoot, ".claude", "agents", "implementer", "AGENTS.md"), "utf8"),
    "# Agent\n",
  );
});

test("run installs everything into the selected agent roots", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "everything-install-"));
  const lines = [];

  const exitCode = await run(["install", "everything", "--dir", homeRoot, "--agent", "codex"], {
    manifest: {
      skills: {
        rust: { basePath: "skills/rust", files: ["SKILL.md"] },
      },
      workflows: {
        "plan-implement-review": {
          basePath: "workflows/plan-implement-review",
          files: ["WORKFLOW.md"],
          description: "Workflow",
        },
      },
      agents: {
        planner: {
          basePath: "agents/planner",
          files: ["AGENT.md"],
          description: "Planner",
        },
      },
    },
    stdout: (line) => lines.push(line),
    loadSkillFile: async () => "# Content\n",
  });

  assert.equal(exitCode, 0);
  assert.match(lines[0], /Installed 1 skill, 1 workflow, 1 agent/);
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "skills", "rust", "SKILL.md"), "utf8"),
    "# Content\n",
  );
  assert.equal(
    await readFile(
      path.join(homeRoot, ".codex", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Content\n",
  );
  assert.equal(
    await readFile(path.join(homeRoot, ".codex", "agents", "planner", "AGENT.md"), "utf8"),
    "# Content\n",
  );
});

test("run installs workflow into a specific agent", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "wf-install-agent-"));

  const exitCode = await run(
    ["add", "workflow", "plan-implement-review", "--dir", homeRoot, "--agent", "claude"],
    {
      manifest: WORKFLOW_MANIFEST,
      loadSkillFile: async () => "# Workflow\n",
    },
  );

  assert.equal(exitCode, 0);
  assert.equal(
    await readFile(
      path.join(homeRoot, ".claude", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
  await assert.rejects(
    access(
      path.join(homeRoot, ".codex", "workflows", "plan-implement-review", "WORKFLOW.md"),
      constants.F_OK,
    ),
    /ENOENT/,
  );
});

test("run reports unknown workflow with a non-zero exit code", async () => {
  const errors = [];

  const exitCode = await run(["install", "workflow", "nonexistent", "--dir", "/tmp/ignored"], {
    manifest: WORKFLOW_MANIFEST,
    stderr: (line) => errors.push(line),
    loadSkillFile: async () => "# nope\n",
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /Unknown workflow/i);
});

test("installWorkflow writes workflow files into the target directory", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "wf-unit-install-"));
  const calls = [];

  await installWorkflow({
    manifest: WORKFLOW_MANIFEST,
    workflowName: "plan-implement-review",
    targetRoot,
    loadWorkflowFile: async (fileSpec) => {
      calls.push(fileSpec);
      return "# content\n";
    },
  });

  assert.deepEqual(calls, [
    { basePath: "workflows/plan-implement-review", file: "WORKFLOW.md" },
    { basePath: "workflows/plan-implement-review", file: "references/state-schema.md" },
  ]);
  assert.equal(
    await readFile(
      path.join(targetRoot, "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# content\n",
  );
  assert.equal(
    await readFile(
      path.join(targetRoot, "plan-implement-review", "references", "state-schema.md"),
      "utf8",
    ),
    "# content\n",
  );
});

test("installAllWorkflows installs every workflow in the manifest", async () => {
  const targetRoot = await mkdtemp(path.join(tmpdir(), "wf-unit-all-"));

  await installAllWorkflows({
    manifest: WORKFLOW_MANIFEST,
    targetRoot,
    loadWorkflowFile: async () => "# wf\n",
  });

  assert.equal(
    await readFile(
      path.join(targetRoot, "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# wf\n",
  );
});

test("run shows usage when install workflow has no name and is non-interactive", async () => {
  const errors = [];

  const exitCode = await run(["install", "workflow"], {
    manifest: WORKFLOW_MANIFEST,
    stderr: (line) => errors.push(line),
  });

  assert.equal(exitCode, 1);
  assert.match(errors[0], /Usage/);
});

test("run prompts interactively when install workflow has no name", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "wf-interactive-"));
  const prompts = [];

  const exitCode = await run(["install", "workflow", "--dir", homeRoot], {
    manifest: WORKFLOW_MANIFEST,
    loadSkillFile: async () => "# Workflow\n",
    promptForWorkflowSelectionImpl: async (options) => {
      prompts.push(options);
      return { workflowNames: ["plan-implement-review"], agents: ["codex"] };
    },
  });

  assert.equal(exitCode, 0);
  assert.equal(prompts.length, 1);
  assert.equal(prompts[0].workflowOptions[0].value, "plan-implement-review");
  assert.equal(prompts[0].workflowOptions[0].description, "Three-phase delivery workflow");
  assert.equal(
    await readFile(
      path.join(homeRoot, ".codex", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
  await assert.rejects(
    access(
      path.join(homeRoot, ".claude", "workflows", "plan-implement-review", "WORKFLOW.md"),
      constants.F_OK,
    ),
    /ENOENT/,
  );
});

test("run skips agent prompt for workflow when --agent is already provided", async () => {
  const homeRoot = await mkdtemp(path.join(tmpdir(), "wf-interactive-agent-"));
  const prompts = [];

  const exitCode = await run(["install", "workflow", "--dir", homeRoot, "--agent", "claude"], {
    manifest: WORKFLOW_MANIFEST,
    loadSkillFile: async () => "# Workflow\n",
    promptForWorkflowSelectionImpl: async (options) => {
      prompts.push(options);
      return { workflowNames: ["plan-implement-review"], agents: [] };
    },
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(prompts[0].agentOptions, []);
  assert.equal(
    await readFile(
      path.join(homeRoot, ".claude", "workflows", "plan-implement-review", "WORKFLOW.md"),
      "utf8",
    ),
    "# Workflow\n",
  );
});
