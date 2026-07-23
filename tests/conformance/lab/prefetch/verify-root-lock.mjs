import fs from "node:fs";

const [lockPath, packageName, expectedVersion, expectedIntegrity] = process.argv.slice(2);
if (!lockPath || !packageName || !expectedVersion || !expectedIntegrity?.startsWith("sha512-")) throw new Error("lock and exact CLI identity are required");
if (!/^(@[a-z0-9._-]+\/)?[a-z0-9._-]+$/.test(packageName)) throw new Error("invalid CLI package name");
const raw = fs.readFileSync(lockPath, "utf8");
const installPath = `node_modules/${packageName}`;
function decodedKeyOccurrences(json, expected) {
  let count = 0;
  for (let index = 0; index < json.length; index++) {
    if (json[index] !== '"') continue;
    const start = index++;
    for (; index < json.length; index++) {
      if (json[index] === "\\") { index++; continue; }
      if (json[index] === '"') break;
    }
    if (index >= json.length) throw new Error("unterminated JSON string");
    let next = index + 1;
    while (/\s/.test(json[next] || "")) next++;
    if (json[next] !== ":") continue;
    const decoded = JSON.parse(json.slice(start, index + 1));
    if (decoded === expected) count++;
  }
  return count;
}
const occurrences = decodedKeyOccurrences(raw, installPath);
if (occurrences !== 1) throw new Error("top-level CLI install path is absent or duplicated");
const lock = JSON.parse(raw);
if (lock.lockfileVersion !== 3 || !lock.packages || typeof lock.packages !== "object") throw new Error("unsupported package lock");
const entry = lock.packages[installPath];
if (!entry || entry.version !== expectedVersion || entry.integrity !== expectedIntegrity) throw new Error("top-level CLI lock identity does not match requested artifact");
if (entry.name !== undefined && entry.name !== packageName) throw new Error("top-level CLI lock path is an ambiguous alias");
