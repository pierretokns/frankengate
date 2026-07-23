import assert from "node:assert/strict";
import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const verifier = new URL("./verify-root-lock.mjs", import.meta.url).pathname;
const sriVerifier = new URL("./verify-sri.mjs", import.meta.url).pathname;
const packageName = "@openai/codex";
const version = "0.144.5";
const tarballBytes = Buffer.from("valid packed top-level artifact");
const integrity = `sha512-${crypto.createHash("sha512").update(tarballBytes).digest("base64")}`;
const valid = {lockfileVersion: 3, packages: {"": {}, [`node_modules/${packageName}`]: {version, integrity}}};

function verify(lock) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "verify-root-lock-"));
  const lockPath = path.join(directory, "package-lock.json");
  fs.writeFileSync(lockPath, typeof lock === "string" ? lock : JSON.stringify(lock));
  execFileSync(process.execPath, [verifier, lockPath, packageName, version, integrity], {stdio: "pipe"});
}

function verifyArtifactStillValid() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "verify-root-artifact-"));
  const tarball = path.join(directory, "package.tgz");
  fs.writeFileSync(tarball, tarballBytes);
  execFileSync(process.execPath, [sriVerifier, tarball, integrity], {stdio: "pipe"});
}

test("joins exact scoped top-level lock path to requested artifact", () => verify(valid));

test("rejects lock version and integrity equivocation while artifact identity stays fixed", () => {
	verifyArtifactStillValid();
  for (const mutation of [{version: "0.144.6"}, {integrity: "sha512-different-bytes"}, {name: "@evil/alias"}]) {
    const candidate = structuredClone(valid);
    Object.assign(candidate.packages[`node_modules/${packageName}`], mutation);
    assert.throws(() => verify(candidate));
  }
  const absent = structuredClone(valid); delete absent.packages[`node_modules/${packageName}`];
  assert.throws(() => verify(absent));
});

test("rejects duplicate exact top-level install-path keys", () => {
  const entry = JSON.stringify({version, integrity});
	for (const duplicate of [
		`"node_modules/@openai/codex":${entry},"node_modules/@openai/codex":${entry}`,
		`"node_modules/@openai/codex":${entry},"node_modules/\\u0040openai/codex":${entry}`,
		`"node_modules/@openai/codex":${entry},"node_modules/@openai\\/codex":${entry}`,
		`"node_modules/\\u0040openai\\/codex":${entry},"node_modules/@openai/codex":${entry}`,
	]) {
		assert.throws(() => verify(`{"lockfileVersion":3,"packages":{"":{},${duplicate}}}`));
	}
});
