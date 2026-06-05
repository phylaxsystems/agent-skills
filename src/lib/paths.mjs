import os from "node:os";
import path from "node:path";

const SUPPORTED_AGENTS = ["claude-code", "codex", "opencode"];

export function resolveAgentInstallRoot({ homedir = os.homedir, dir } = {}) {
  const homeRoot = dir ? path.resolve(dir) : homedir();
  return path.join(homeRoot, ".claude", "agents");
}

const AGENT_ALIASES = new Map([
  ["claude", "claude-code"],
  ["claude-code", "claude-code"],
  ["codex", "codex"],
  ["opencode", "opencode"],
]);

export function resolveInstallRoot({ env = process.env, homedir = os.homedir, dir } = {}) {
  if (dir) {
    return path.resolve(dir);
  }

  if (env.CODEX_HOME) {
    return path.join(env.CODEX_HOME, "skills");
  }

  return path.join(homedir(), ".codex", "skills");
}

export function normalizeAgents(agents = []) {
  if (agents.length === 0) {
    return [...SUPPORTED_AGENTS];
  }

  const normalizedAgents = [];

  for (const agent of agents) {
    const normalizedAgent = AGENT_ALIASES.get(agent);

    if (!normalizedAgent) {
      throw new Error(
        `Unknown agent "${agent}". Supported agents: ${SUPPORTED_AGENTS.join(", ")}`,
      );
    }

    if (!normalizedAgents.includes(normalizedAgent)) {
      normalizedAgents.push(normalizedAgent);
    }
  }

  return normalizedAgents;
}

export function resolveInstallRoots({
  agents,
  env = process.env,
  homedir = os.homedir,
  dir,
  contentType = "skills",
} = {}) {
  const normalizedAgents = normalizeAgents(agents);
  const homeRoot = dir ? path.resolve(dir) : homedir();
  const installRoots = {};

  for (const agent of normalizedAgents) {
    if (agent === "claude-code") {
      installRoots[agent] = path.join(homeRoot, ".claude", contentType);
      continue;
    }

    if (agent === "codex") {
      if (dir) {
        installRoots[agent] = path.join(homeRoot, ".codex", contentType);
        continue;
      }

      const codexSkillsRoot = resolveInstallRoot({ env, homedir });
      installRoots[agent] = path.join(path.dirname(codexSkillsRoot), contentType);
      continue;
    }

    installRoots[agent] = path.join(homeRoot, ".config", "opencode", contentType);
  }

  return installRoots;
}
