import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const selector = new URL("./select-claude-native.mjs", import.meta.url).pathname;
function fixture(arch="amd64") {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"claude-native-")); const cpu=arch==="amd64"?"x64":"arm64"; const name=`@anthropic-ai/claude-code-linux-${cpu}-musl`;
  const wrapper=path.join(root,"node_modules/@anthropic-ai/claude-code"), native=path.join(root,"node_modules",name); fs.mkdirSync(path.join(wrapper,"bin"),{recursive:true}); fs.mkdirSync(native,{recursive:true});
  fs.writeFileSync(path.join(wrapper,"package.json"),JSON.stringify({version:"2.1.214",optionalDependencies:{[name]:"2.1.214"}})); fs.writeFileSync(path.join(native,"package.json"),JSON.stringify({name,version:"2.1.214"}));
  const tarball=`https://registry.npmjs.org/${name}/-/${name.split("/")[1]}-2.1.214.tgz`, integrity="sha512-pinned"; fs.writeFileSync(path.join(root,"package-lock.json"),JSON.stringify({packages:{[`node_modules/${name}`]:{version:"2.1.214",integrity,resolved:tarball}}}));
  const elf=Buffer.alloc(64); elf.set([0x7f,0x45,0x4c,0x46]); elf.writeUInt16LE(arch==="amd64"?62:183,18); fs.writeFileSync(path.join(native,"claude"),elf); fs.writeFileSync(path.join(wrapper,"bin/claude.exe"),"stub"); return {root,native,name,tarball,integrity};
}
const args=f=>[selector,f.root,"2.1.214","amd64",f.name,f.tarball,f.integrity];
test("selects only exact locked target ELF",()=>{ const f=fixture(); execFileSync(process.execPath,args(f)); assert.equal(fs.readFileSync(path.join(f.root,"node_modules/@anthropic-ai/claude-code/bin/claude.exe")).readUInt16LE(18),62); });
test("rejects coordinate integrity tarball and ELF mutations",()=>{ for(const mutate of [f=>{f.integrity="sha512-wrong"},f=>{f.tarball=f.tarball.replace("2.1.214","2.1.215")},f=>fs.writeFileSync(path.join(f.root,"package-lock.json"),`{"packages":{}}`), f=>{const p=path.join(f.native,"claude");const b=fs.readFileSync(p);b.writeUInt16LE(183,18);fs.writeFileSync(p,b); }]){const f=fixture();mutate(f);assert.throws(()=>execFileSync(process.execPath,args(f),{stdio:"pipe"}));} });
