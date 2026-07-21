import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const verifier = new URL("./verify-tree.mjs", import.meta.url).pathname;
const incompatibleOS = process.platform === "linux" ? "darwin" : "linux";
const incompatibleCPU = process.arch === "arm64" ? "x64" : "arm64";
const lock = {lockfileVersion: 3, packages: {
  "": {},
  "node_modules/root": {name: "root", version: "1.0.0", integrity: "sha512-root"},
  "node_modules/optional-linux": {name: "optional-linux", version: "1.0.0-linux", integrity: "sha512-linux"},
  "node_modules/optional-other": {name: "optional-other", version: "1.0.0-other", integrity: "sha512-other", optional: true, os: [incompatibleOS], cpu: [process.arch]},
  "node_modules/optional-negated": {name: "optional-negated", version: "1.0.0-negated", integrity: "sha512-negated", optional: true, os: [`!${process.platform}`]},
  "node_modules/optional-other-cpu": {name: "optional-other-cpu", version: "1.0.0-other-cpu", integrity: "sha512-other-cpu", optional: true, cpu: [incompatibleCPU]},
	"node_modules/optional-compatible": {name: "optional-compatible", version: "1.0.0-compatible", integrity: "sha512-compatible", optional: true, os: [process.platform], cpu: [process.arch]},
	"node_modules/optional-compatible-negative": {name: "optional-compatible-negative", version: "1.0.0-compatible-negative", integrity: "sha512-compatible-negative", optional: true, os: [`!${incompatibleOS}`]},
  "node_modules/required-other": {name: "required-other", version: "1.0.0-required", integrity: "sha512-required", os: [incompatibleOS]},
}};

function verify(tree, lockInput = lock) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "verify-tree-"));
  const lockPath = path.join(directory, "lock.json");
  const treePath = path.join(directory, "tree.json");
  const outputPath = path.join(directory, "output.json");
  fs.writeFileSync(lockPath, JSON.stringify(lockInput));
  fs.writeFileSync(treePath, JSON.stringify(tree));
  execFileSync(process.execPath, [verifier, lockPath, treePath, outputPath], {stdio: "pipe"});
  return JSON.parse(fs.readFileSync(outputPath, "utf8"));
}

test("excludes lock-declared empty optional nodes and records installed coordinates", () => {
  const output = verify({dependencies: {root: {version: "1.0.0", dependencies: {
		"optional-linux": {version: "1.0.0-linux"}, "optional-other": {}, "optional-negated": {}, "optional-other-cpu": {},
  }}}});
  assert.deepEqual(output.packages, ["optional-linux@1.0.0-linux", "root@1.0.0"]);
});

test("uses package-lock install-path aliases rather than target package metadata", () => {
  const aliasLock = {lockfileVersion: 3, packages: {
    "": {},
    "node_modules/@openai/codex": {name: "@openai/codex", version: "0.144.5", integrity: "sha512-root"},
    "node_modules/@openai/codex-linux-arm64": {name: "@openai/codex", version: "0.144.5-linux-arm64", integrity: "sha512-linux", optional: true, os: [process.platform], cpu: [process.arch]},
    "node_modules/@openai/codex-darwin-arm64": {name: "@openai/codex", version: "0.144.5-darwin-arm64", integrity: "sha512-darwin", optional: true, os: [incompatibleOS], cpu: [process.arch]},
  }};
  const output = verify({dependencies: {"@openai/codex": {version: "0.144.5", dependencies: {
    "@openai/codex-linux-arm64": {version: "0.144.5-linux-arm64"},
    "@openai/codex-darwin-arm64": {},
  }}}}, aliasLock);
  assert.deepEqual(output.packages, ["@openai/codex-linux-arm64@0.144.5-linux-arm64", "@openai/codex@0.144.5"]);
});

test("rejects populated versionless and unlocked installed nodes", () => {
  assert.throws(() => verify({dependencies: {root: {version: "1.0.0", dependencies: {"optional-other": {optional: true}}}}}));
  assert.throws(() => verify({dependencies: {root: {version: "1.0.0", dependencies: {intruder: {version: "9.9.9"}}}}}));
});

test("rejects empty required and platform-compatible optional nodes", () => {
  assert.throws(() => verify({dependencies: {root: {version: "1.0.0", dependencies: {"required-other": {}}}}}));
  assert.throws(() => verify({dependencies: {root: {version: "1.0.0", dependencies: {"optional-compatible": {}}}}}));
	assert.throws(() => verify({dependencies: {root: {version: "1.0.0", dependencies: {"optional-compatible-negative": {}}}}}));
});

test("rejects malformed os and cpu lock constraints before omission", () => {
  const tree = {dependencies: {root: {version: "1.0.0"}}};
  const mutants = [
    {os: "darwin"}, {os: []}, {os: [""]}, {os: ["!"]}, {os: [42]},
    {cpu: "arm64"}, {cpu: []}, {cpu: [""]}, {cpu: ["!"]}, {cpu: [false]},
  ];
  for (const mutation of mutants) {
    const candidate = structuredClone(lock);
    Object.assign(candidate.packages["node_modules/optional-other"], mutation);
    assert.throws(() => verify(tree, candidate));
  }
});

test("does not let an incompatible optional duplicate mask a required or compatible entry", () => {
  const tree = {dependencies: {root: {version: "1.0.0", dependencies: {"optional-other": {}}}}};
  for (const duplicate of [
    {name: "optional-other", version: "2.0.0", integrity: "sha512-required"},
    {name: "optional-other", version: "2.0.0", integrity: "sha512-compatible", optional: true, os: [process.platform], cpu: [process.arch]},
  ]) {
    const candidate = structuredClone(lock);
    candidate.packages["node_modules/root/node_modules/optional-other"] = duplicate;
    assert.throws(() => verify(tree, candidate));
  }
});
