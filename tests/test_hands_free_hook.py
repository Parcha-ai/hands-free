import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "scripts" / "hands_free_hook.py"
BUNDLED_HOOK_PATH = ROOT / "skills" / "hands-free" / "scripts" / "hands_free_hook.py"
INSTALL_PATH = ROOT / "install.sh"


def load_hook(hands_free_home, harness="codex"):
    previous_home = os.environ.get("HANDS_FREE_HOME")
    previous_harness = os.environ.get("HANDS_FREE_HARNESS")
    os.environ["HANDS_FREE_HOME"] = str(hands_free_home)
    os.environ["HANDS_FREE_HARNESS"] = harness
    try:
        spec = importlib.util.spec_from_file_location("hands_free_hook_under_test", HOOK_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for key, prev in (("HANDS_FREE_HOME", previous_home), ("HANDS_FREE_HARNESS", previous_harness)):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev


def capture_json(fn, *args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        fn(*args)
    text = output.getvalue().strip()
    return json.loads(text) if text else None


class HandsFreeHookTest(unittest.TestCase):
    def test_bundled_skill_hook_matches_runtime_hook(self):
        self.assertEqual(HOOK_PATH.read_text(), BUNDLED_HOOK_PATH.read_text())

    def test_activation_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp))
            for prompt in ("activate hands free", "activate hands-free", "activate handsfree", "turn on handsfree"):
                result = capture_json(hook.handle_user_prompt_submit, {"prompt": prompt}, {"active": False})
                self.assertEqual(result["systemMessage"], "Hands-free mode activated. Future approval and input requests will be routed by phone.")

            for prompt in ("deactivate hands free", "deactivate hands-free", "deactivate handsfree", "turn off handsfree"):
                result = capture_json(hook.handle_user_prompt_submit, {"prompt": prompt}, {"active": True})
                self.assertEqual(result["systemMessage"], "Hands-free mode deactivated.")

    def test_activation_reads_claude_user_message_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp), harness="claude-code")
            result = capture_json(
                hook.handle_user_prompt_submit,
                {"user_message": "activate hands-free please", "hook_event_name": "UserPromptSubmit"},
                {"active": False},
            )
            self.assertEqual(result["systemMessage"], "Hands-free mode activated. Future approval and input requests will be routed by phone.")

    def test_stop_uses_top_level_block_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp))
            hook.call_for_input = lambda message, purpose: "Run the live approval test."

            result = capture_json(
                hook.handle_stop,
                {"last_assistant_message": "What should I do next?"},
                {"active": True},
            )

            self.assertEqual(result["decision"], "block")
            self.assertIn("Run the live approval test.", result["reason"])
            self.assertNotIn("hookSpecificOutput", result)

    def test_approval_requires_user_attributed_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp))
            hook.call_for_input = lambda message, purpose, raw_call=False: {
                "artifact": {
                    "messages": [{"role": "assistant", "message": "Say approve or deny."}],
                    "transcript": "Code assistant: Say approve or deny.",
                }
            }

            result = capture_json(
                hook.handle_permission_request,
                {"tool_name": "shell", "tool_input": {"command": "date"}},
                {"active": True},
                "codex",
            )

            self.assertEqual(result["systemMessage"], "Hands-free phone approval was ambiguous; falling back to normal approval.")
            self.assertNotIn("hookSpecificOutput", result)

    def test_approval_allows_user_attributed_answer_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp))
            hook.call_for_input = lambda message, purpose, raw_call=False: {
                "artifact": {
                    "messages": [{"role": "user", "message": "approve"}],
                }
            }

            result = capture_json(
                hook.handle_permission_request,
                {"tool_name": "shell", "tool_input": {"command": "date"}},
                {"active": True},
                "codex",
            )

            self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PermissionRequest")
            self.assertEqual(result["hookSpecificOutput"]["decision"]["behavior"], "allow")

    def test_approval_allows_user_attributed_answer_claude_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp), harness="claude-code")
            hook.call_for_input = lambda message, purpose, raw_call=False: {
                "artifact": {
                    "messages": [{"role": "user", "message": "deny"}],
                }
            }

            result = capture_json(
                hook.handle_permission_request,
                {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/x"}},
                {"active": True},
                "claude-code",
            )

            self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("Hands-free phone response: deny", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_detect_harness_from_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = load_hook(pathlib.Path(tmp))
            # Clear explicit harness env so detection runs.
            previous = os.environ.pop("HANDS_FREE_HARNESS", None)
            try:
                self.assertEqual(hook.detect_harness({"hook_event_name": "PreToolUse"}), "claude-code")
                self.assertEqual(hook.detect_harness({"hook_event_name": "PermissionRequest"}), "codex")
            finally:
                if previous is not None:
                    os.environ["HANDS_FREE_HARNESS"] = previous


class CodexInstallerTest(unittest.TestCase):
    def test_installer_preserves_unrelated_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = pathlib.Path(tmp) / "codex"
            codex_home.mkdir()
            hooks_path = codex_home / "hooks.json"
            hooks_path.write_text(json.dumps({
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": "/bin/true"}]}],
                }
            }))
            (codex_home / "config.toml").write_text("[features]\nother_feature = true\n")

            subprocess.run(
                [str(INSTALL_PATH), "--harness=codex"],
                check=True,
                env={**os.environ, "CODEX_HOME": str(codex_home)},
                stdout=subprocess.PIPE,
                text=True,
            )

            hooks = json.loads(hooks_path.read_text())["hooks"]
            stop_commands = [hook["command"] for entry in hooks["Stop"] for hook in entry["hooks"]]
            self.assertIn("/bin/true", stop_commands)
            self.assertTrue(any(command.endswith("/hands-free/scripts/hands_free_hook.py") for command in stop_commands))
            self.assertTrue(any("HANDS_FREE_HARNESS=codex" in command for command in stop_commands))
            self.assertIn("codex_hooks = true", (codex_home / "config.toml").read_text())
            self.assertTrue((codex_home / "hands-free" / ".env").exists())
            self.assertTrue((codex_home / "skills" / "hands-free" / "scripts" / "hands_free_hook.py").exists())


class ClaudeInstallerTest(unittest.TestCase):
    def test_installer_writes_pre_tool_use_into_settings_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_home = pathlib.Path(tmp) / "claude"
            claude_home.mkdir()
            settings_path = claude_home / "settings.json"
            settings_path.write_text(json.dumps({
                "hooks": {
                    "Stop": [{"hooks": [{"type": "command", "command": "/bin/true"}]}],
                },
                "model": "claude-opus-4-7",
            }))

            subprocess.run(
                [str(INSTALL_PATH), "--harness=claude-code"],
                check=True,
                env={**os.environ, "CLAUDE_HOME": str(claude_home)},
                stdout=subprocess.PIPE,
                text=True,
            )

            settings = json.loads(settings_path.read_text())
            self.assertEqual(settings["model"], "claude-opus-4-7", "unrelated settings preserved")
            hooks = settings["hooks"]
            self.assertIn("PreToolUse", hooks)
            self.assertNotIn("PermissionRequest", hooks)
            pre_tool_cmds = [hook["command"] for entry in hooks["PreToolUse"] for hook in entry["hooks"]]
            self.assertTrue(any("HANDS_FREE_HARNESS=claude-code" in c for c in pre_tool_cmds))
            stop_commands = [hook["command"] for entry in hooks["Stop"] for hook in entry["hooks"]]
            self.assertIn("/bin/true", stop_commands)
            self.assertFalse((claude_home / "config.toml").exists(), "no codex config written for claude harness")
            self.assertTrue((claude_home / "hands-free" / ".env").exists())
            self.assertTrue((claude_home / "skills" / "hands-free" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
