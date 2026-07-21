import fs from "node:fs";
import path from "node:path";

const [root, version, arch] = process.argv.slice(2);
if (!root || !/^\d+\.\d+\.\d+$/.test(version) || !["amd64", "arm64"].includes(arch)) throw new Error("invalid native selection arguments");
const cpu = arch === "amd64" ? "x64" : "arm64";
const name = `@anthropic-ai/claude-code-linux-${cpu}-musl`;
const wrapper = JSON.parse(fs.readFileSync(path.join(root, "node_modules/@anthropic-ai/claude-code/package.json")));
const lock = JSON.parse(fs.readFileSync(path.join(root, "package-lock.json")));
const installed = JSON.parse(fs.readFileSync(path.join(root, "node_modules", name, "package.json")));
const locked = lock.packages?.[`node_modules/${name}`];
if (wrapper.version !== version || wrapper.optionalDependencies?.[name] !== version || installed.name !== name || installed.version !== version || locked?.version !== version || typeof locked.integrity !== "string" || !locked.integrity.startsWith("sha512-")) throw new Error("native package coordinate/integrity mismatch");
const source = path.join(root, "node_modules", name, "claude");
const target = path.join(root, "node_modules/@anthropic-ai/claude-code/bin/claude.exe");
const bytes = fs.readFileSync(source);
const machine = bytes.length >= 20 && bytes[0] === 0x7f && bytes.subarray(1, 4).toString() === "ELF" ? bytes.readUInt16LE(18) : -1;
if (machine !== (arch === "amd64" ? 62 : 183)) throw new Error("native package ELF architecture mismatch");
fs.copyFileSync(source, target); fs.chmodSync(target, 0o755);
