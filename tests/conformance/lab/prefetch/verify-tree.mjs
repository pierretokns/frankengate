import fs from "node:fs";

const [lockPath, treePath, outputPath] = process.argv.slice(2);
if (!lockPath || !treePath || !outputPath) throw new Error("lock, tree, and output paths are required");
const lock = JSON.parse(fs.readFileSync(lockPath, "utf8"));
const tree = JSON.parse(fs.readFileSync(treePath, "utf8"));
if (lock.lockfileVersion !== 3 || !lock.packages || !tree.dependencies) throw new Error("unsupported npm dependency evidence");

const permitted = new Set();
for (const [path, entry] of Object.entries(lock.packages)) {
  if (!path) continue;
  if (typeof entry.version !== "string" || typeof entry.integrity !== "string" || !entry.integrity.startsWith("sha512-")) {
    throw new Error(`unlocked package entry ${path}`);
  }
  const marker = "node_modules/";
  const index = path.lastIndexOf(marker);
  const name = entry.name || path.slice(index + marker.length);
  permitted.add(`${name}@${entry.version}`);
}

const observed = [];
function visit(dependencies) {
  for (const name of Object.keys(dependencies || {}).sort()) {
    const node = dependencies[name];
    const coordinate = `${name}@${node.version}`;
    if (!permitted.has(coordinate)) throw new Error(`installed dependency absent from package lock: ${coordinate}`);
    observed.push(coordinate);
    visit(node.dependencies);
  }
}
visit(tree.dependencies);
if (observed.length === 0) throw new Error("empty installed dependency tree");
fs.writeFileSync(outputPath, `${JSON.stringify({schema:"sealed-cli-prefetch-dependencies/v1", packages:[...new Set(observed)].sort()})}\n`);
