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


def load_hook(codex_home):
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(codex_home)
    try:
        spec = importlib.util.spec_from_file_location("hands_free_hook_under_test", HOOK_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


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
            )

            self.assertEqual(result["systemMessage"], "Hands-free phone approval was ambiguous; falling back to normal Codex approval.")
            self.assertNotIn("hookSpecificOutput", result)

    def test_approval_allows_user_attributed_answer(self):
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
            )

            self.assertEqual(result["hookSpecificOutput"]["decision"]["behavior"], "allow")


class InstallerTest(unittest.TestCase):
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

            subprocess.run([str(INSTALL_PATH)], check=True, env={**os.environ, "CODEX_HOME": str(codex_home)}, stdout=subprocess.PIPE, text=True)

            hooks = json.loads(hooks_path.read_text())["hooks"]
            stop_commands = [hook["command"] for entry in hooks["Stop"] for hook in entry["hooks"]]
            self.assertIn("/bin/true", stop_commands)
            self.assertTrue(any(command.endswith("/hands-free/scripts/hands_free_hook.py") for command in stop_commands))
            self.assertIn("codex_hooks = true", (codex_home / "config.toml").read_text())
            self.assertTrue((codex_home / "hands-free" / ".env").exists())
            self.assertTrue((codex_home / "skills" / "hands-free" / "scripts" / "hands_free_hook.py").exists())


if __name__ == "__main__":
    unittest.main()
