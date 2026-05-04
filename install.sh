#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
HANDS_FREE_HOME="$CODEX_HOME/hands-free"
SKILL_HOME="$CODEX_HOME/skills/hands-free"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
HOOK_SOURCE="$ROOT_DIR/skills/hands-free/scripts/hands_free_hook.py"

install -d -m 700 "$HANDS_FREE_HOME/scripts" "$SKILL_HOME/agents" "$SKILL_HOME/scripts"
install -m 700 "$HOOK_SOURCE" "$HANDS_FREE_HOME/scripts/hands_free_hook.py"
install -m 644 "$ROOT_DIR/skills/hands-free/SKILL.md" "$SKILL_HOME/SKILL.md"
install -m 644 "$ROOT_DIR/skills/hands-free/agents/openai.yaml" "$SKILL_HOME/agents/openai.yaml"
install -m 700 "$HOOK_SOURCE" "$SKILL_HOME/scripts/hands_free_hook.py"

if [[ ! -f "$HANDS_FREE_HOME/.env" ]]; then
  install -m 600 "$ROOT_DIR/.env.example" "$HANDS_FREE_HOME/.env"
fi

"$PYTHON_BIN" - "$CODEX_HOME" "$PYTHON_BIN" <<'PY'
import json
import pathlib
import shlex
import sys

codex_home = pathlib.Path(sys.argv[1]).expanduser()
python_bin = sys.argv[2]
hooks_path = codex_home / "hooks.json"
command = f"{shlex.quote(python_bin)} {shlex.quote(str(codex_home / 'hands-free' / 'scripts' / 'hands_free_hook.py'))}"

desired = {
    "UserPromptSubmit": [{
        "hooks": [{"type": "command", "command": command, "timeout": 10}]
    }],
    "PermissionRequest": [{
        "matcher": ".*",
        "hooks": [{
            "type": "command",
            "command": command,
            "statusMessage": "Calling for hands-free approval",
            "timeout": 220,
        }],
    }],
    "Stop": [{
        "hooks": [{
            "type": "command",
            "command": command,
            "statusMessage": "Checking hands-free phone input",
            "timeout": 240,
        }],
    }],
}

if hooks_path.exists():
    data = json.loads(hooks_path.read_text())
else:
    data = {"hooks": {}}

hooks = data.setdefault("hooks", {})
for event_name, entries in desired.items():
    existing_entries = hooks.setdefault(event_name, [])
    filtered_entries = []
    for entry in existing_entries:
        entry_hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
        if any("hands-free/scripts/hands_free_hook.py" in str(hook.get("command", "")) for hook in entry_hooks if isinstance(hook, dict)):
            continue
        filtered_entries.append(entry)
    hooks[event_name] = filtered_entries + entries

hooks_path.write_text(json.dumps(data, indent=2) + "\n")
hooks_path.chmod(0o600)
PY

"$PYTHON_BIN" - "$CODEX_HOME" <<'PY'
import pathlib
import sys

config_path = pathlib.Path(sys.argv[1]).expanduser() / "config.toml"
text = config_path.read_text() if config_path.exists() else ""
if "[features]" not in text:
    text = text.rstrip() + "\n\n[features]\ncodex_hooks = true\n"
else:
    lines = text.splitlines()
    in_features = False
    saw_codex_hooks = False
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_features and not saw_codex_hooks:
                output.append("codex_hooks = true")
                saw_codex_hooks = True
            in_features = stripped == "[features]"
        if in_features and stripped.startswith("codex_hooks"):
            output.append("codex_hooks = true")
            saw_codex_hooks = True
            continue
        output.append(line)
    if in_features and not saw_codex_hooks:
        output.append("codex_hooks = true")
    text = "\n".join(output) + "\n"
config_path.write_text(text)
config_path.chmod(0o600)
PY

echo "Installed hands-free skill and hooks."
echo "Edit $HANDS_FREE_HOME/.env, then restart Codex."
