#!/usr/bin/env node
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const command = process.argv[2] || "help";

function usage() {
  console.log(`Hands Free for Codex

Usage:
  hands-free-codex install   Install the Codex skill and hooks
  hands-free-codex doctor    Check local hook and env setup
  hands-free-codex help      Show this help

Environment:
  CODEX_HOME       Defaults to ~/.codex
  PYTHON_BIN       Defaults to python3 found on PATH
`);
}

function codexHome() {
  return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
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
    console.error("hands-free-codex install currently requires a POSIX shell.");
    process.exit(1);
  }
  const result = spawnSync("bash", [path.join(root, "install.sh")], {
    cwd: root,
    env: process.env,
    stdio: "inherit",
  });
  process.exit(result.status === null ? 1 : result.status);
}

function doctor() {
  const home = codexHome();
  const runtimeHook = path.join(home, "hands-free", "scripts", "hands_free_hook.py");
  const skillFile = path.join(home, "skills", "hands-free", "SKILL.md");
  const hooksFile = path.join(home, "hooks.json");
  const configFile = path.join(home, "config.toml");
  const envFile = path.join(home, "hands-free", ".env");
  const env = { ...parseEnv(envFile), ...process.env };
  const required = ["VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID", "HANDS_FREE_PHONE_NUMBER"];

  const checks = [
    [fs.existsSync(runtimeHook), `runtime hook: ${runtimeHook}`],
    [fs.existsSync(skillFile), `skill file: ${skillFile}`],
    [fs.existsSync(hooksFile), `hooks config: ${hooksFile}`],
    [fs.existsSync(configFile) && fs.readFileSync(configFile, "utf8").includes("codex_hooks = true"), "codex_hooks enabled"],
    [required.every((key) => env[key] && env[key] !== "+15555550123"), "required Vapi env values configured"],
  ];

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
