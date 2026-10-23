import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from guardrails.codex_hook import evaluate_hook
from guardrails.policy import PolicyEvaluator


@pytest.fixture
def evaluator(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Existing.md").write_text("Keep this", encoding="utf-8")
    return PolicyEvaluator(vault)


@pytest.mark.parametrize("operation,path,expected", [
    ("read", "Existing.md", "allow"),
    ("read", "Missing.md", "allow"),
    ("write", "New.md", "allow"),
    ("write", "Existing.md", "warn"),
    ("delete", "Existing.md", "block"),
    ("delete", "New.md", "block"),
    ("read", "../outside.md", "block"),
    ("write", "..\\outside.md", "block"),
    ("read", "C:outside.md", "block"),
    ("read", "Note.md:stream", "block"),
    ("read", ".env", "block"),
    ("read", ".env.local.md", "block"),
    ("read", "Credentials.md", "block"),
    ("write", "Nested/secrets.md", "block"),
    ("read", "AccessToken.md", "block"),
    ("read", "private.key", "block"),
    ("read", "id_rsa.md", "block"),
    ("read", ".git/Note.md", "block"),
    ("read", ".obsidian/Note.md", "block"),
    ("read", "note.txt", "block"),
    ("execute", "Existing.md", "block"),
    ("read", "", "block"),
    ("read", None, "block"),
    ("read", "nul.md", "block"),
    ("read", "Folder./Note.md", "block"),
])
def test_decisions(evaluator, operation, path, expected):
    before = (evaluator.vault / "Existing.md").read_bytes()
    assert evaluator.evaluate(operation, path).decision == expected
    assert (evaluator.vault / "Existing.md").read_bytes() == before
    assert not (evaluator.vault / "New.md").exists()


def test_absolute_paths(evaluator, tmp_path):
    assert evaluator.evaluate("read", str(tmp_path / "outside.md")).decision == "block"
    assert evaluator.evaluate("read", str(evaluator.vault / "Existing.md")).decision == "allow"


def test_policy_file_controls_decisions(evaluator, tmp_path):
    policy = evaluator.policy
    for rule in policy["rules"]:
        if rule["id"] == "read_note":
            rule["decision"] = "warn"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    assert PolicyEvaluator(evaluator.vault, path).evaluate("read", "Existing.md").decision == "warn"
    policy["rules"][0]["decision"] = "invalid"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError):
        PolicyEvaluator(evaluator.vault, path)


def test_hardlink(evaluator, tmp_path):
    outside = tmp_path / "Outside.md"
    outside.write_text("Do not read", encoding="utf-8")
    os.link(outside, evaluator.vault / "Linked.md")
    assert evaluator.evaluate("read", "Linked.md").decision == "block"


def test_symlink(evaluator, tmp_path):
    outside = tmp_path / "Outside.md"
    outside.write_text("Do not read", encoding="utf-8")
    try:
        (evaluator.vault / "Linked.md").symlink_to(outside)
    except OSError:
        pytest.skip("OS permission required to create symbolic links")
    assert evaluator.evaluate("read", "Linked.md").decision == "block"


@pytest.mark.parametrize("tool,path,expected", [
    ("get_note", "Existing.md", "allow"),
    ("ingest_note", "Existing.md", "warn"),
    ("get_note", ".env", "block"),
    ("ingest_note", "../outside.md", "block"),
    ("search_notes", "Existing.md", "block"),
])
def test_hook_mapping(evaluator, tool, path, expected):
    output = evaluate_hook({
        "hook_event_name": "PreToolUse", "tool_name": f"mcp__taskflow_kb__{tool}",
        "tool_input": {"note_path": path},
    }, evaluator)["hookSpecificOutput"]
    if expected == "block":
        assert output["permissionDecision"] == "deny"
    elif expected == "warn":
        assert "WARNING" in output["additionalContext"]
        assert "permissionDecision" not in output
    else:
        assert output == {"hookEventName": "PreToolUse"}


def test_other_tools_unaffected(evaluator):
    assert evaluate_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"}, evaluator) == {}


@pytest.mark.parametrize("argument_name,reason", [
    ("path", "A nonempty note path is required."),
    ("note_path", "Invalid or ambiguous path."),
])
def test_hook_traversal_argument_regression(evaluator, argument_name, reason):
    # Reproduce the original call and the same request with the MCP schema's
    # actual argument name. Exercise stdin parsing and the configured adapter.
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "mcp__taskflow_kb__get_note",
        "tool_input": {argument_name: "../guardrail_test_nonexistent.md"},
    }
    result = subprocess.run(
        [sys.executable, "-m", "guardrails.codex_hook"],
        input=json.dumps(payload), text=True, capture_output=True,
        env={**os.environ, "TASKFLOW_KB_PATH": str(evaluator.vault)},
        timeout=10,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}


@pytest.mark.parametrize("payload", ["not JSON", "[]", json.dumps({
    "hook_event_name": "PreToolUse", "tool_name": "mcp__taskflow_kb__get_note",
    "tool_input": {"note_path": ".env"},
})])
def test_hook_process(evaluator, payload):
    result = subprocess.run(
        [sys.executable, "-m", "guardrails.codex_hook"], input=payload,
        text=True, capture_output=True,
        env={**os.environ, "TASKFLOW_KB_PATH": str(evaluator.vault)},
        timeout=10,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_config():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".codex/hooks.json").read_text(encoding="utf-8"))
    hook = config["hooks"]["PreToolUse"][0]
    assert hook["matcher"] == "^mcp__taskflow_kb__.*$"
    assert "codex_hook.py" in hook["hooks"][0]["command"]
