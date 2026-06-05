import assert from "node:assert/strict";
import test from "node:test";

import { readBundledSkillFile, resolveBundledSkillFileUrl } from "../src/lib/bundle.mjs";

test("resolveBundledSkillFileUrl points at bundled package content", () => {
  const url = resolveBundledSkillFileUrl({
    basePath: "skills/optimize-assertion-triggers",
    file: "SKILL.md",
  });

  assert.match(url.pathname, /skills\/optimize-assertion-triggers\/SKILL\.md$/);
});

test("readBundledSkillFile reads packaged skill content", async () => {
  const content = await readBundledSkillFile({
    basePath: "skills/optimize-assertion-triggers",
    file: "SKILL.md",
  });

  assert.match(content.toString("utf8"), /^---\nname: optimize-assertion-triggers/m);
});

test("resolveBundledSkillFileUrl works for nested skill files", () => {
  const url = resolveBundledSkillFileUrl({
    basePath: "skills/optimize-assertion-triggers",
    file: "agents/openai.yaml",
  });

  assert.match(url.pathname, /skills\/optimize-assertion-triggers\/agents\/openai\.yaml$/);
});

test("resolveBundledSkillFileUrl rejects unsafe bundled paths", () => {
  assert.throws(
    () =>
      resolveBundledSkillFileUrl({
        basePath: "../skills",
        file: "SKILL.md",
      }),
    /parent path segments/i,
  );
  assert.throws(
    () =>
      resolveBundledSkillFileUrl({
        basePath: "skills/optimize-assertion-triggers",
        file: "../package.json",
      }),
    /parent path segments/i,
  );
  assert.throws(
    () =>
      resolveBundledSkillFileUrl({
        basePath: "/tmp/skills",
        file: "SKILL.md",
      }),
    /relative path/i,
  );
});

test("readBundledSkillFile reads packaged Codex UI metadata", async () => {
  const content = await readBundledSkillFile({
    basePath: "skills/optimize-assertion-triggers",
    file: "agents/openai.yaml",
  });

  assert.match(content.toString("utf8"), /default_prompt:/);
});
