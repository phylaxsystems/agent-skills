# AGENTS.md

Guidance for AI coding agents working in this repository.

## Repository Overview

This repository contains agent skills for writing Phylax Credible Layer assertions.

## Skill Structure

```
skills/
  <skill-name>/
    SKILL.md
    references/
```

## SKILL.md Requirements

- YAML frontmatter with `name` and `description`.
- Include these sections:
  - `## When to Use`
  - `## When NOT to Use`
- For security skills, include:
  - `## Rationalizations to Reject`
- Keep `SKILL.md` under 500 lines; move details to `references/`.
- Do not hardcode absolute paths; use `{baseDir}` for scripts if needed.

## Naming

- Use kebab-case.
- Prefer gerund names (e.g., `designing-assertions`).

## Progressive Disclosure

- Link from `SKILL.md` to specific files in `references/`.
- Avoid reference chains (references should not link to other references).
