#!/usr/bin/env node

import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { readBundledSkillFile } from "./lib/bundle.mjs";
import {
  installAllAgents,
  installAllSkills,
  installSkill,
  installAgent,
  installAllWorkflows,
  installWorkflow,
} from "./lib/install.mjs";
import { loadManifest } from "./lib/manifest.mjs";
import {
  promptForAgentSelection,
  promptForInstallSelection,
  promptForWorkflowSelection,
} from "./lib/prompt.mjs";
import { normalizeAgents, resolveInstallRoots } from "./lib/paths.mjs";

function readFlag(args, name) {
  const index = args.indexOf(name);

  if (index === -1) {
    return undefined;
  }

  return args[index + 1];
}

function readFlags(args, name) {
  const values = [];

  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === name && typeof args[index + 1] === "string") {
      values.push(args[index + 1]);
    }
  }

  return values;
}

function usage() {
  return "Usage: agent-skills [install|add] [<skill-name>|all|everything|workflow <name>|workflow all|agent <name>|agent all] [--agent <claude-code|codex|opencode>] [--dir <path>] [--force]\n       agent-skills list [workflows|agents]\n\n'all' installs all skills. Use 'workflow all' for all workflows, 'agent all' for all agents, or 'everything' for all bundled content.";
}

function formatInstallTargets(installRoots) {
  return Object.entries(installRoots)
    .map(([agent, targetRoot]) => `${agent}: ${targetRoot}`)
    .join(", ");
}

const CONTENT_TYPES = {
  skill: {
    key: "skills",
    singular: "skill",
    plural: "skills",
    prompt: promptForInstallSelection,
    installOne: installSkill,
    installAll: installAllSkills,
    selectionKey: "skillNames",
    roleOptionsKey: "skillOptions",
    loadKey: "loadSkillFile",
  },
  workflow: {
    key: "workflows",
    singular: "workflow",
    plural: "workflows",
    prompt: promptForWorkflowSelection,
    installOne: installWorkflow,
    installAll: installAllWorkflows,
    selectionKey: "workflowNames",
    roleOptionsKey: "workflowOptions",
    loadKey: "loadWorkflowFile",
  },
  agent: {
    key: "agents",
    singular: "agent",
    plural: "agents",
    prompt: promptForAgentSelection,
    installOne: installAgent,
    installAll: installAllAgents,
    selectionKey: "agentNames",
    roleOptionsKey: "agentRoleOptions",
    loadKey: "loadAgentFile",
  },
};

function getContentItems(manifest, type) {
  return manifest[CONTENT_TYPES[type].key] ?? {};
}

function buildContentOptions(manifest, type) {
  return Object.entries(getContentItems(manifest, type))
    .sort(([leftName], [rightName]) => leftName.localeCompare(rightName))
    .map(([name, item]) => ({
      value: name,
      label: name,
      description: item.description,
    }));
}

function isAllContentSelection(names, manifest, type) {
  const allNames = Object.keys(getContentItems(manifest, type)).sort();
  const selectedNames = [...names].sort();

  if (allNames.length !== selectedNames.length) {
    return false;
  }

  return allNames.every((name, index) => selectedNames[index] === name);
}

function formatInstalledContent(names, manifest, type) {
  const { singular, plural } = CONTENT_TYPES[type];

  if (isAllContentSelection(names, manifest, type)) {
    return `${names.length} ${plural}`;
  }

  if (names.length === 1) {
    return `${singular} ${names[0]}`;
  }

  return `${names.length} ${plural} (${names.join(", ")})`;
}

function formatCountLabel(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function buildAgentRoleOptions() {
  return [
    { value: "claude-code", label: "claude-code", aliases: ["claude"] },
    { value: "codex", label: "codex" },
    { value: "opencode", label: "opencode" },
  ];
}

async function installIntoRoots({ installRoots, install }) {
  const installedPaths = [];

  for (const targetRoot of Object.values(installRoots)) {
    installedPaths.push(await install(targetRoot));
  }

  return installedPaths;
}

function isFlag(value) {
  return typeof value === "string" && value.startsWith("-");
}

function parseCommand(argv) {
  const [firstArg, secondArg, thirdArg] = argv;

  if (!firstArg || isFlag(firstArg)) {
    return { command: "install", type: "skill", subject: undefined };
  }

  if (firstArg === "list" && secondArg === "workflows") {
    return { command: "list", type: "workflow", subject: undefined };
  }

  if (firstArg === "list" && secondArg === "agents") {
    return { command: "list", type: "agent", subject: undefined };
  }

  if (firstArg === "list") {
    return { command: "list", type: "skill", subject: undefined };
  }

  if ((firstArg === "install" || firstArg === "add") && secondArg === "workflow") {
    return { command: firstArg, type: "workflow", subject: isFlag(thirdArg) ? undefined : thirdArg };
  }

  if ((firstArg === "install" || firstArg === "add") && secondArg === "agent") {
    return { command: firstArg, type: "agent", subject: isFlag(thirdArg) ? undefined : thirdArg };
  }

  if ((firstArg === "install" || firstArg === "add") && secondArg === "everything") {
    return { command: firstArg, type: "everything", subject: undefined };
  }

  if (firstArg === "install" || firstArg === "add") {
    return { command: firstArg, type: "skill", subject: isFlag(secondArg) ? undefined : secondArg };
  }

  return { command: firstArg, type: "skill", subject: secondArg };
}

function isInteractiveSession({
  stdin = process.stdin,
  stdoutStream = process.stdout,
} = {}) {
  return Boolean(stdin?.isTTY && stdoutStream?.isTTY);
}

function resolveExecutionPath(filePath) {
  try {
    return realpathSync(filePath);
  } catch {
    return filePath;
  }
}

function isDirectExecution(argv1 = process.argv[1]) {
  if (!argv1) {
    return false;
  }

  return resolveExecutionPath(argv1) === resolveExecutionPath(fileURLToPath(import.meta.url));
}

export async function run(argv, deps = {}) {
  const manifest = deps.manifest ?? loadManifest();
  const stdout = deps.stdout ?? console.log;
  const stderr = deps.stderr ?? console.error;
  const resolveInstallRootsImpl =
    deps.resolveInstallRootsImpl ??
    ((options) => {
      if (
        deps.resolveInstallRootImpl &&
        (!options.agents || options.agents.length === 0) &&
        options.contentType === "skills"
      ) {
        return { codex: deps.resolveInstallRootImpl({ dir: options.dir }) };
      }

      return resolveInstallRoots({
        ...options,
        env: deps.env,
        homedir: deps.homedir,
      });
    });
  const loadSkillFile = deps.loadSkillFile ?? readBundledSkillFile;
  const args = [...argv];
  const stdin = deps.stdin ?? process.stdin;
  const stdoutStream = deps.stdoutStream ?? process.stdout;
  const promptForInstallSelectionImpl =
    deps.promptForInstallSelectionImpl ??
    ((options) =>
      promptForInstallSelection({
        ...options,
        input: stdin,
        output: stdoutStream,
        writeLine: stdout,
      }));
  const promptForWorkflowSelectionImpl =
    deps.promptForWorkflowSelectionImpl ??
    ((options) =>
      promptForWorkflowSelection({
        ...options,
        input: stdin,
        output: stdoutStream,
        writeLine: stdout,
      }));
  const promptForAgentSelectionImpl =
    deps.promptForAgentSelectionImpl ??
    ((options) =>
      promptForAgentSelection({
        ...options,
        input: stdin,
        output: stdoutStream,
        writeLine: stdout,
      }));
  const promptSelectionImpls = {
    skill: promptForInstallSelectionImpl,
    workflow: promptForWorkflowSelectionImpl,
    agent: promptForAgentSelectionImpl,
  };

  try {
    const { command, type, subject } = parseCommand(args);
    const dir = readFlag(args, "--dir");
    const agents = readFlags(args, "--agent");
    const force = args.includes("--force");
    const isInstallCommand = command === "install" || command === "add";

    if (args.includes("--ref")) {
      stderr("--ref is no longer supported. Skills are bundled with the npm package.");
      return 1;
    }

    if (command === "list") {
      const content = getContentItems(manifest, type);
      for (const contentName of Object.keys(content).sort()) {
        stdout(contentName);
      }
      return 0;
    }

    if (isInstallCommand) {
      if (type === "everything") {
        const normalizedAgents = normalizeAgents(agents);
        const counts = [];

        for (const contentType of ["skill", "workflow", "agent"]) {
          const installRoots = resolveInstallRootsImpl({
            agents: normalizedAgents,
            dir,
            contentType: CONTENT_TYPES[contentType].plural,
          });

          await installIntoRoots({
            installRoots,
            install: (targetRoot) =>
              CONTENT_TYPES[contentType].installAll({
                manifest,
                targetRoot,
                force,
                [CONTENT_TYPES[contentType].loadKey]: loadSkillFile,
              }),
          });

          const content = getContentItems(manifest, contentType);
          counts.push(
            formatCountLabel(
              Object.keys(content).length,
              CONTENT_TYPES[contentType].singular,
              CONTENT_TYPES[contentType].plural,
            ),
          );
        }

        stdout(`Installed ${counts.join(", ")} into selected targets`);
        return 0;
      }

      if (subject === "all") {
        const normalizedAgents = normalizeAgents(agents);
        const installRoots = resolveInstallRootsImpl({
          agents: normalizedAgents,
          dir,
          contentType: CONTENT_TYPES[type].plural,
        });

        await installIntoRoots({
          installRoots,
          install: (targetRoot) =>
            CONTENT_TYPES[type].installAll({
              manifest,
              targetRoot,
              force,
              [CONTENT_TYPES[type].loadKey]: loadSkillFile,
            }),
        });

        const content = getContentItems(manifest, type);
        stdout(
          `Installed ${Object.keys(content).length} ${CONTENT_TYPES[type].plural} into ${formatInstallTargets(installRoots)}`,
        );
        return 0;
      }

      let contentNames;
      let selectedAgents = agents;

      if (subject) {
        contentNames = [subject];
      } else {
        if (!isInteractiveSession({ stdin, stdoutStream }) && !deps.promptForInstallSelectionImpl && type === "skill") {
          stderr(usage());
          return 1;
        }

        if (!isInteractiveSession({ stdin, stdoutStream }) && !deps.promptForWorkflowSelectionImpl && type === "workflow") {
          stderr(usage());
          return 1;
        }

        if (!isInteractiveSession({ stdin, stdoutStream }) && !deps.promptForAgentSelectionImpl && type === "agent") {
          stderr(usage());
          return 1;
        }

        const selection = await promptSelectionImpls[type]({
          [CONTENT_TYPES[type].roleOptionsKey]: buildContentOptions(manifest, type),
          agentOptions: selectedAgents.length === 0 ? buildAgentRoleOptions() : [],
        });

        contentNames = selection[CONTENT_TYPES[type].selectionKey];

        if (selectedAgents.length === 0) {
          selectedAgents = selection.agents;
        }
      }

      const normalizedAgents = normalizeAgents(selectedAgents);
      const installRoots = resolveInstallRootsImpl({
        agents: normalizedAgents,
        dir,
        contentType: CONTENT_TYPES[type].plural,
      });

      if (isAllContentSelection(contentNames, manifest, type)) {
        await installIntoRoots({
          installRoots,
          install: (targetRoot) =>
            CONTENT_TYPES[type].installAll({
              manifest,
              targetRoot,
              force,
              [CONTENT_TYPES[type].loadKey]: loadSkillFile,
            }),
        });
      } else {
        for (const contentName of contentNames) {
          await installIntoRoots({
            installRoots,
            install: (targetRoot) =>
              CONTENT_TYPES[type].installOne({
                manifest,
                [`${type}Name`]: contentName,
                targetRoot,
                force,
                [CONTENT_TYPES[type].loadKey]: loadSkillFile,
              }),
          });
        }
      }

      stdout(`Installed ${formatInstalledContent(contentNames, manifest, type)} into ${formatInstallTargets(installRoots)}`);
      return 0;
    }

    stderr(usage());
    return 1;
  } catch (error) {
    stderr(error.message);
    return 1;
  }
}

if (isDirectExecution()) {
  process.exitCode = await run(process.argv.slice(2));
}
