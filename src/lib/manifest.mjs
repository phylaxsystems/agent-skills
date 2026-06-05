import manifest from "../manifest.json" with { type: "json" };

export function loadManifest() {
  return manifest;
}
