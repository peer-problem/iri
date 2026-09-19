import { readFileSync, writeFileSync } from "node:fs";

// Liquid DOM 0.1.1 clears its empty scene to opaque black and does not expose
// a background option. Keep the package shader intact while matching IRI white.
for (const file of ["index.js", "index.cjs"]) {
  const path = new URL(
    `../node_modules/@liquid-dom/core/dist/${file}`,
    import.meta.url,
  );
  const source = readFileSync(path, "utf8");
  const before = "var OPAQUE_BLACK = { r: 0, g: 0, b: 0, a: 1 };";
  const after = "var OPAQUE_BLACK = { r: 1, g: 1, b: 1, a: 1 };";
  if (!source.includes(before) && !source.includes(after)) {
    throw new Error("Liquid DOM backdrop patch needs review");
  }
  writeFileSync(path, source.replace(before, after));
}
