import fs from "node:fs";

const [lockPath, treePath, outputPath] = process.argv.slice(2);
if (!lockPath || !treePath || !outputPath) throw new Error("lock, tree, and output paths are required");
const lock = JSON.parse(fs.readFileSync(lockPath, "utf8"));
const tree = JSON.parse(fs.readFileSync(treePath, "utf8"));
if (lock.lockfileVersion !== 3 || !lock.packages || !tree.dependencies) throw new Error("unsupported npm dependency evidence");

const permitted = new Set();
const permittedByName = new Map();
function validateConstraint(values, field, path) {
  if (values === undefined) return;
  if (!Array.isArray(values) || values.length === 0 || values.some(value =>
    typeof value !== "string" || value.length === 0 || value === "!"
  )) throw new Error(`malformed ${field} constraint for ${path}`);
}
for (const [path, entry] of Object.entries(lock.packages)) {
  if (!path) continue;
  if (typeof entry.version !== "string" || typeof entry.integrity !== "string" || !entry.integrity.startsWith("sha512-")) {
    throw new Error(`unlocked package entry ${path}`);
  }
  validateConstraint(entry.os, "os", path);
  validateConstraint(entry.cpu, "cpu", path);
  const marker = "node_modules/";
  const index = path.lastIndexOf(marker);
  if (index < 0) throw new Error(`invalid package-lock path ${path}`);
  // npm ls keys dependencies by the alias/install path. package-lock's
  // entry.name is package metadata and can name the alias target instead.
  const name = path.slice(index + marker.length);
  if (!name) throw new Error(`invalid package-lock path ${path}`);
  permitted.add(`${name}@${entry.version}`);
  const entries = permittedByName.get(name) || [];
  entries.push(entry);
  permittedByName.set(name, entries);
}

function constraintAllows(values, current) {
  if (values === undefined) return true;
  const positive = values.filter(value => !value.startsWith("!"));
  const excluded = values.some(value => value === `!${current}`);
  return !excluded && (positive.length === 0 || positive.includes(current));
}

function isAuthorizedPlatformOmission(name) {
  const entries = permittedByName.get(name) || [];
  return entries.length > 0 && entries.every(entry =>
    entry.optional === true &&
    (!constraintAllows(entry.os, process.platform) || !constraintAllows(entry.cpu, process.arch))
  );
}

const observed = [];
function visit(dependencies) {
  for (const name of Object.keys(dependencies || {}).sort()) {
    const node = dependencies[name];
    if (!node || typeof node !== "object" || Array.isArray(node)) throw new Error(`invalid dependency evidence: ${name}`);
    // npm ls represents platform-incompatible optional dependencies as an
    // empty object. They are not installed and must not enter resolved output.
    // Only a lock-declared name may be omitted; any populated versionless node
    // remains malformed and fails closed.
    if (node.version === undefined && Object.keys(node).length === 0 && isAuthorizedPlatformOmission(name)) continue;
    if (typeof node.version !== "string" || node.version.length === 0) throw new Error(`invalid installed dependency evidence: ${name}`);
    const coordinate = `${name}@${node.version}`;
    if (!permitted.has(coordinate)) throw new Error(`installed dependency absent from package lock: ${coordinate}`);
    observed.push(coordinate);
    visit(node.dependencies);
  }
}
visit(tree.dependencies);
if (observed.length === 0) throw new Error("empty installed dependency tree");
fs.writeFileSync(outputPath, `${JSON.stringify({schema:"sealed-cli-prefetch-dependencies/v1", packages:[...new Set(observed)].sort()})}\n`);
