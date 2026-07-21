#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const repoRoot = process.cwd();
const registryPath = path.join(repoRoot, "docs/architecture/config-ownership-registry.rules.json");
const snapshotPath = path.join(repoRoot, "docs/architecture/config-ownership-registry.snapshot.json");
const configSchemaPath = path.join(repoRoot, "transports/config.schema.json");
const helmSchemaPath = path.join(repoRoot, "helm-charts/bifrost/values.schema.json");
const configGoPath = path.join(repoRoot, "transports/bifrost-http/lib/config.go");

const writeMode = process.argv.includes("--write");

function readJSON(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function pointerGet(root, ref) {
  if (!ref.startsWith("#/")) {
    throw new Error(`unsupported ref ${ref}`);
  }
  return ref
    .slice(2)
    .split("/")
    .map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"))
    .reduce((cur, part) => {
      if (cur == null || !(part in cur)) {
        throw new Error(`missing ref ${ref}`);
      }
      return cur[part];
    }, root);
}

function uniqByPath(entries) {
  const byPath = new Map();
  for (const entry of entries) {
    const existing = byPath.get(entry.path);
    if (!existing) {
      byPath.set(entry.path, entry);
      continue;
    }
    existing.schema.types = Array.from(new Set([...existing.schema.types, ...entry.schema.types])).sort();
    existing.schema.nullable = existing.schema.nullable || entry.schema.nullable;
    existing.schema.required = existing.schema.required || entry.schema.required;
    if (existing.schema.default === undefined && entry.schema.default !== undefined) {
      existing.schema.default = entry.schema.default;
    }
    if (entry.schema.enum) {
      existing.schema.enum = Array.from(new Set([...(existing.schema.enum || []), ...entry.schema.enum])).sort();
    }
  }
  return Array.from(byPath.values()).sort((a, b) => a.path.localeCompare(b.path));
}

function schemaTypes(schema) {
  if (!schema || typeof schema !== "object") {
    return [];
  }
  const out = new Set();
  if (Array.isArray(schema.type)) {
    for (const t of schema.type) out.add(t);
  } else if (typeof schema.type === "string") {
    out.add(schema.type);
  }
  for (const key of ["anyOf", "oneOf", "allOf"]) {
    if (Array.isArray(schema[key])) {
      for (const sub of schema[key]) {
        for (const t of schemaTypes(sub)) out.add(t);
      }
    }
  }
  return Array.from(out).sort();
}

function walkSchema(root, schema, fieldPath = "", required = false, seenRefs = new Set()) {
  if (!schema || typeof schema !== "object") {
    return [];
  }
  if (schema.$ref) {
    const seenKey = `${schema.$ref}|${fieldPath}`;
    if (seenRefs.has(seenKey)) {
      return [];
    }
    const nextSeen = new Set(seenRefs);
    nextSeen.add(seenKey);
    return walkSchema(root, pointerGet(root, schema.$ref), fieldPath, required, nextSeen);
  }

  const variants = [];
  for (const key of ["allOf", "anyOf", "oneOf"]) {
    if (Array.isArray(schema[key])) {
      variants.push(...schema[key]);
    }
  }
  if (variants.length > 0) {
    const ownStructural = schema.properties || schema.items || (schema.additionalProperties && typeof schema.additionalProperties === "object");
    const variantEntries = variants.flatMap((sub) => walkSchema(root, sub, fieldPath, required, new Set(seenRefs)));
    if (!ownStructural) {
      return uniqByPath(variantEntries);
    }
  }

  if (schema.properties && typeof schema.properties === "object") {
    const req = new Set(Array.isArray(schema.required) ? schema.required : []);
    return Object.entries(schema.properties).flatMap(([name, sub]) => {
      const nextPath = fieldPath ? `${fieldPath}.${name}` : name;
      return walkSchema(root, sub, nextPath, req.has(name), new Set(seenRefs));
    });
  }

  if (schema.items && typeof schema.items === "object") {
    return walkSchema(root, schema.items, `${fieldPath}[]`, required, new Set(seenRefs));
  }

  if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
    const nextPath = fieldPath ? `${fieldPath}.*` : "*";
    return walkSchema(root, schema.additionalProperties, nextPath, required, new Set(seenRefs));
  }

  if (!fieldPath) {
    return [];
  }
  const types = schemaTypes(schema);
  const entry = {
    path: fieldPath,
    schema: {
      types,
      required: Boolean(required),
      nullable: types.includes("null"),
    },
  };
  if (Object.prototype.hasOwnProperty.call(schema, "default")) {
    entry.schema.default = schema.default;
  }
  if (Array.isArray(schema.enum)) {
    entry.schema.enum = schema.enum;
  }
  if (schema.description) {
    entry.schema.description = schema.description;
  }
  return [entry];
}

function extractConfigDataFields() {
  const source = fs.readFileSync(configGoPath, "utf8");
  const start = source.indexOf("type ConfigData struct {");
  if (start === -1) {
    throw new Error("ConfigData struct not found");
  }
  const lines = source.slice(start).split("\n");
  const fields = [];
  let depth = 0;
  let inStruct = false;
  for (const line of lines) {
    if (line.includes("type ConfigData struct {")) {
      inStruct = true;
      depth = 1;
      continue;
    }
    if (!inStruct) continue;
    if (/^\}/.test(line)) {
      depth -= 1;
      if (depth === 0) break;
    }
    const match = line.match(/^\s*([A-Z][A-Za-z0-9_]*)\s+(.+?)\s+`json:"([^",]+)(?:,[^"]*)?"`/);
    if (!match) continue;
    const [, goName, goType, jsonName] = match;
    if (jsonName === "-") continue;
    fields.push({
      path: jsonName,
      go_name: goName,
      go_type: goType.trim(),
      schema: {
        types: ["go"],
        required: false,
        nullable: goType.trim().startsWith("*") || goType.includes("map[") || goType.includes("[]"),
      },
    });
  }
  return fields.sort((a, b) => a.path.localeCompare(b.path));
}

function globToRegex(pattern) {
  let regex = "";
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] === "*" && pattern[index + 1] === "*") {
      regex += ".*";
      index += 1;
      continue;
    }
    if (pattern[index] === "*") {
      regex += "[^.]+";
      continue;
    }
    regex += pattern[index].replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  }
  return new RegExp(`^${regex}$`);
}

function matchesAny(fieldPath, patterns = []) {
  return patterns.some((pattern) => globToRegex(pattern).test(fieldPath));
}

function matchingRules(registry, surface, fieldPath) {
  return registry.rules.filter((rule) => {
    if (rule.surface !== surface) return false;
    if (!matchesAny(fieldPath, rule.include)) return false;
    if (matchesAny(fieldPath, rule.exclude || [])) return false;
    return true;
  });
}

function secretSemantics(fieldPath) {
  const normalized = fieldPath.toLowerCase();
  if (/(existingsecret|secretref|passwordkey|usernamekey|apikeykey|secretkeykey|connectionstringkey|credentialsjsonkey)$/.test(normalized.replace(/[._[\]]/g, ""))) {
    return "secret_reference: identifies Kubernetes/env/vault material but does not contain the secret itself";
  }
  if (/(encryption[_-]?key|admin[_-]?password|password|secret|api[_-]?key|access[_-]?key|secret[_-]?access[_-]?key|session[_-]?token|refresh[_-]?token|client[_-]?secret|hmac[_-]?key|credential|credentials[_-]?json|service[_-]?account[_-]?key|connection[_-]?string|headers\.\*)/i.test(fieldPath)) {
    return "secret_value_or_indirection: redact on read, permit env./vault./secret indirection, and never log resolved value";
  }
  return "not_secret";
}

function identitySemantics(fieldPath) {
  const segments = fieldPath.split(".");
  if (segments.some((segment) => segment === "*" || segment === "providers" || segment === "provider" || segment === "provider_name")) {
    return "identity_or_selector: stable key participates in lookup, routing, or ownership";
  }
  if (segments.some((segment) => /(^id$|_id$|ids\[\]$|ids$|^name$|_name$|model|issuer|subject|tenant|team|customer|user|role|scope)/i.test(segment))) {
    return "identity_or_selector: stable key participates in lookup, routing, or ownership";
  }
  return "not_identity";
}

function defaultSemantics(entry, rule) {
  if (Object.prototype.hasOwnProperty.call(entry.schema, "default")) {
    return `schema_default:${JSON.stringify(entry.schema.default)}`;
  }
  return rule.default_semantics;
}

function nilSemantics(entry, rule) {
  if (entry.schema.required) {
    return "required_by_schema: missing value is invalid for this schema branch";
  }
  if (entry.schema.nullable) {
    return "nullable_or_pointer: explicit null/missing can be represented and is interpreted by the owning loader";
  }
  return rule.nil_semantics;
}

function annotate(entries, registry, surface) {
  const errors = [];
  const annotated = [];
  for (const entry of entries) {
    const matches = matchingRules(registry, surface, entry.path);
    if (matches.length !== 1) {
      errors.push({ surface, path: entry.path, matches: matches.map((rule) => rule.id) });
      continue;
    }
    const rule = matches[0];
    annotated.push({
      path: entry.path,
      ...(entry.go_name ? { go_name: entry.go_name, go_type: entry.go_type } : {}),
      schema: entry.schema,
      authority: rule.authority,
      source_of_truth: rule.authority === "bootstrap_only" ? "bootstrap" : registry.target_source_of_truth,
      reload_contract: rule.reload_contract,
      schema_semantics: rule.schema_semantics,
      default_semantics: defaultSemantics(entry, rule),
      nil_semantics: nilSemantics(entry, rule),
      secret_semantics: secretSemantics(entry.path),
      identity_semantics: identitySemantics(entry.path),
      rule_id: rule.id,
      evidence: rule.evidence,
    });
  }
  return { annotated: annotated.sort((a, b) => a.path.localeCompare(b.path)), errors };
}

function countBy(entries, key) {
  return entries.reduce((acc, entry) => {
    acc[entry[key]] = (acc[entry[key]] || 0) + 1;
    return acc;
  }, {});
}

function buildSnapshot() {
  const registry = readJSON(registryPath);
  const configSchema = readJSON(configSchemaPath);
  const helmSchema = readJSON(helmSchemaPath);
  const configData = extractConfigDataFields();
  const configFields = uniqByPath(walkSchema(configSchema, configSchema));
  const helmFields = uniqByPath(walkSchema(helmSchema, helmSchema));

  const configDataAnnotated = annotate(configData, registry, "config_data");
  const configSchemaAnnotated = annotate(configFields, registry, "config_schema");
  const helmAnnotated = annotate(helmFields, registry, "helm_values");
  const errors = [...configDataAnnotated.errors, ...configSchemaAnnotated.errors, ...helmAnnotated.errors];
  if (errors.length > 0) {
    const sample = errors.slice(0, 50).map((err) => `${err.surface}:${err.path} -> [${err.matches.join(", ")}]`).join("\n");
    throw new Error(`ownership registry coverage failed for ${errors.length} fields:\n${sample}`);
  }

  const snapshot = {
    schema_version: registry.schema_version,
    registry_id: registry.registry_id,
    target_source_of_truth: registry.target_source_of_truth,
    generated_from: {
      rules: path.relative(repoRoot, registryPath),
      config_data: path.relative(repoRoot, configGoPath),
      config_schema: path.relative(repoRoot, configSchemaPath),
      helm_values_schema: path.relative(repoRoot, helmSchemaPath),
    },
    counts: {
      config_data_fields: configDataAnnotated.annotated.length,
      config_schema_fields: configSchemaAnnotated.annotated.length,
      helm_values_fields: helmAnnotated.annotated.length,
      by_surface_authority: {
        config_data: countBy(configDataAnnotated.annotated, "authority"),
        config_schema: countBy(configSchemaAnnotated.annotated, "authority"),
        helm_values: countBy(helmAnnotated.annotated, "authority"),
      },
    },
    config_data_fields: configDataAnnotated.annotated,
    config_schema_fields: configSchemaAnnotated.annotated,
    helm_values_fields: helmAnnotated.annotated,
  };
  return snapshot;
}

function stableJSON(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

try {
  const snapshot = buildSnapshot();
  const rendered = stableJSON(snapshot);
  if (writeMode) {
    fs.writeFileSync(snapshotPath, rendered);
  } else {
    const existing = fs.existsSync(snapshotPath) ? fs.readFileSync(snapshotPath, "utf8") : "";
    if (existing !== rendered) {
      throw new Error(`snapshot is stale; run node scripts/verify-config-ownership-registry.mjs --write`);
    }
  }
  console.log(`config_data_fields=${snapshot.counts.config_data_fields}`);
  console.log(`config_schema_fields=${snapshot.counts.config_schema_fields}`);
  console.log(`helm_values_fields=${snapshot.counts.helm_values_fields}`);
  console.log(JSON.stringify(snapshot.counts.by_surface_authority));
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
}
