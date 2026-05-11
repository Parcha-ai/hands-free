#!/usr/bin/env node
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const args = process.argv.slice(2);
const command = args.shift() || "help";

function usage() {
  console.log(`Hands Free — phone-call bridge for AI coding assistants

Usage:
  hands-free install [--harness=claude-code|codex]
  hands-free doctor  [--harness=claude-code|codex]
  hands-free help

Defaults:
  --harness auto-detects (prefers ~/.claude when present, else ~/.codex)

Environment:
  CLAUDE_HOME      Override ~/.claude
  CODEX_HOME       Override ~/.codex
  HANDS_FREE_HOME  Override the per-harness <home>/hands-free directory
  PYTHON_BIN       Defaults to python3 found on PATH
`);
}

function parseFlag(name) {
  for (const arg of args) {
    if (arg.startsWith(`--${name}=`)) return arg.slice(name.length + 3);
    if (arg === `--${name}`) {
      const next = args[args.indexOf(arg) + 1];
      if (next && !next.startsWith("--")) return next;
    }
  }
  return undefined;
}

function detectHarness() {
  const explicit = parseFlag("harness") || process.env.HANDS_FREE_HARNESS;
  if (explicit) return explicit;
  if (fs.existsSync(path.join(process.env.CLAUDE_HOME || path.join(os.homedir(), ".claude")))) {
    return "claude-code";
  }
  if (fs.existsSync(path.join(process.env.CODEX_HOME || path.join(os.homedir(), ".codex")))) {
    return "codex";
  }
  return "claude-code";
}

function harnessHome(harness) {
  if (harness === "codex") {
    return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
  }
  return process.env.CLAUDE_HOME || path.join(os.homedir(), ".claude");
}

function parseEnv(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const env = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim().replace(/^["']|["']$/g, "");
    env[key] = value;
  }
  return env;
}

function install() {
  if (process.platform === "win32") {
    console.error("hands-free install currently requires a POSIX shell.");
    process.exit(1);
  }
  const harness = detectHarness();
  const result = spawnSync("bash", [path.join(root, "install.sh"), `--harness=${harness}`], {
    cwd: root,
    env: process.env,
    stdio: "inherit",
  });
  process.exit(result.status === null ? 1 : result.status);
}

function doctor() {
  const harness = detectHarness();
  const home = harnessHome(harness);
  const runtimeHook = path.join(home, "hands-free", "scripts", "hands_free_hook.py");
  const skillFile = path.join(home, "skills", "hands-free", "SKILL.md");
  const settingsFile = harness === "claude-code"
    ? path.join(home, "settings.json")
    : path.join(home, "hooks.json");
  const envFile = path.join(home, "hands-free", ".env");
  const env = { ...parseEnv(envFile), ...process.env };
  const required = ["VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID", "HANDS_FREE_PHONE_NUMBER"];

  const checks = [
    [fs.existsSync(runtimeHook), `runtime hook: ${runtimeHook}`],
    [fs.existsSync(skillFile), `skill file: ${skillFile}`],
    [fs.existsSync(settingsFile), `settings file: ${settingsFile}`],
  ];

  if (harness === "codex") {
    const configFile = path.join(home, "config.toml");
    checks.push([
      fs.existsSync(configFile) && fs.readFileSync(configFile, "utf8").includes("codex_hooks = true"),
      "codex_hooks enabled",
    ]);
  }

  checks.push([
    required.every((key) => env[key] && env[key] !== "+15555550123"),
    "required Vapi env values configured",
  ]);

  console.log(`harness: ${harness}`);
  let ok = true;
  for (const [passed, label] of checks) {
    console.log(`${passed ? "ok" : "missing"} ${label}`);
    ok = ok && passed;
  }
  process.exit(ok ? 0 : 1);
}

if (command === "install") {
  install();
} else if (command === "doctor") {
  doctor();
} else {
  usage();
}
