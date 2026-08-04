import crypto from "node:crypto";
import fs from "node:fs";

const [file, expected] = process.argv.slice(2);
if (!file || !expected || !expected.startsWith("sha512-")) throw new Error("tarball and sha512 SRI are required");
const actual = `sha512-${crypto.createHash("sha512").update(fs.readFileSync(file)).digest("base64")}`;
const left = Buffer.from(actual);
const right = Buffer.from(expected);
if (left.length !== right.length || !crypto.timingSafeEqual(left, right)) throw new Error("packed tarball bytes do not match locked integrity");
