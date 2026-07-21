import assert from "node:assert/strict";
import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const verifier = new URL("./verify-sri.mjs", import.meta.url).pathname;
test("binds packed tarball bytes and rejects same-coordinate mutation", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "verify-sri-"));
  const tarball = path.join(directory, "package-1.0.0.tgz");
  const bytes = Buffer.from("synthetic packed bytes");
  fs.writeFileSync(tarball, bytes);
  const integrity = `sha512-${crypto.createHash("sha512").update(bytes).digest("base64")}`;
  execFileSync(process.execPath, [verifier, tarball, integrity]);
  fs.appendFileSync(tarball, "mutated");
  assert.throws(() => execFileSync(process.execPath, [verifier, tarball, integrity], {stdio: "pipe"}));
});
