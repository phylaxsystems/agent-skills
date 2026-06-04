import { createInterface } from "node:readline/promises";

function normalizeToken(value) {
  return value.trim().toLowerCase();
}

export function parseMultiSelectAnswer(
  answer,
  options,
  { allowAll = false, defaultValues = [] } = {},
) {
  const trimmedAnswer = answer.trim();

  if (!trimmedAnswer) {
    return [...defaultValues];
  }

  const selectedValues = [];
  const normalizedOptions = options.map((option, index) => ({
    ...option,
    index,
    tokens: [option.value, option.label, ...(option.aliases ?? [])].map(normalizeToken),
  }));

  for (const rawToken of trimmedAnswer.split(/[,\s]+/).filter(Boolean)) {
    const token = normalizeToken(rawToken);

    if (allowAll && (token === "all" || token === "*")) {
      return normalizedOptions.map((option) => option.value);
    }

    if (/^\d+$/.test(token)) {
      const option = normalizedOptions[Number(token) - 1];

      if (!option) {
        throw new Error(`Unknown selection "${rawToken}". Choose one of the listed numbers.`);
      }

      if (!selectedValues.includes(option.value)) {
        selectedValues.push(option.value);
      }

      continue;
    }

    const option = normalizedOptions.find((candidate) => candidate.tokens.includes(token));

    if (!option) {
      throw new Error(`Unknown selection "${rawToken}". Choose a listed number, name, or "all".`);
    }

    if (!selectedValues.includes(option.value)) {
      selectedValues.push(option.value);
    }
  }

  return selectedValues;
}

function printOptions(title, options, writeLine) {
  writeLine(title);

  options.forEach((option, index) => {
    const suffix = option.description ? ` - ${option.description}` : "";
    writeLine(`  ${index + 1}) ${option.label}${suffix}`);
  });
}

async function promptForMultiSelect({
  title,
  options,
  ask,
  writeLine,
  defaultValues,
  promptLabel,
}) {
  while (true) {
    printOptions(title, options, writeLine);
    const defaultHint =
      defaultValues.length > 0 ? ' Press Enter for the default selection, or use "all".' : "";
    const answer = await ask(`${promptLabel}.${defaultHint}\n> `);

    try {
      return parseMultiSelectAnswer(answer, options, {
        allowAll: true,
        defaultValues,
      });
    } catch (error) {
      writeLine(error.message);
      writeLine("");
    }
  }
}

function createAsk({ input, output }) {
  const readline = createInterface({ input, output });

  return {
    ask: (question) => readline.question(question),
    close: () => readline.close(),
  };
}

async function promptForContentSelection({
  options,
  agentOptions,
  writeLine = console.log,
  ask,
  input,
  output,
  contentTitle,
  contentPromptLabel,
  selectionKey,
}) {
  const promptSession = ask ? null : createAsk({ input, output });
  const askQuestion = ask ?? promptSession.ask;

  try {
    const names = await promptForMultiSelect({
      title: contentTitle,
      options,
      ask: askQuestion,
      writeLine,
      defaultValues: options.map((option) => option.value),
      promptLabel: contentPromptLabel,
    });

    if (agentOptions.length === 0) {
      writeLine("");
      return { [selectionKey]: names, agents: [] };
    }

    writeLine("");

    const agents = await promptForMultiSelect({
      title: "Select agents to install to:",
      options: agentOptions,
      ask: askQuestion,
      writeLine,
      defaultValues: agentOptions.map((option) => option.value),
      promptLabel: "Enter agent numbers or names",
    });

    writeLine("");

    return { [selectionKey]: names, agents };
  } finally {
    promptSession?.close();
  }
}

export async function promptForWorkflowSelection({
  workflowOptions,
  agentOptions,
  writeLine = console.log,
  ask,
  input,
  output,
}) {
  return promptForContentSelection({
    options: workflowOptions,
    agentOptions,
    writeLine,
    ask,
    input,
    output,
    contentTitle: "Select workflows to install:",
    contentPromptLabel: "Enter workflow numbers or names",
    selectionKey: "workflowNames",
  });
}

export async function promptForInstallSelection({
  skillOptions,
  agentOptions,
  writeLine = console.log,
  ask,
  input,
  output,
}) {
  return promptForContentSelection({
    options: skillOptions,
    agentOptions,
    writeLine,
    ask,
    input,
    output,
    contentTitle: "Select skills to install:",
    contentPromptLabel: "Enter skill numbers or names",
    selectionKey: "skillNames",
  });
}

export async function promptForAgentSelection({
  agentRoleOptions,
  agentOptions,
  writeLine = console.log,
  ask,
  input,
  output,
}) {
  const promptSession = ask ? null : createAsk({ input, output });
  const askQuestion = ask ?? promptSession.ask;

  try {
    const agentNames = await promptForMultiSelect({
      title: "Select agent roles to install:",
      options: agentRoleOptions,
      ask: askQuestion,
      writeLine,
      defaultValues: agentRoleOptions.map((option) => option.value),
      promptLabel: "Enter agent role numbers or names",
    });

    if (agentOptions.length === 0) {
      writeLine("");
      return { agentNames, agents: [] };
    }

    writeLine("");

    const agents = await promptForMultiSelect({
      title: "Select agents to install to:",
      options: agentOptions,
      ask: askQuestion,
      writeLine,
      defaultValues: agentOptions.map((option) => option.value),
      promptLabel: "Enter agent numbers or names",
    });

    writeLine("");

    return { agentNames, agents };
  } finally {
    promptSession?.close();
  }
}
