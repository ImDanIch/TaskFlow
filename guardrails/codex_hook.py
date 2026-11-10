"""Documented Codex PreToolUse adapter; no MCP tool implementation changes."""

import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.policy import Decision, PolicyEvaluator


def evaluate_hook(payload: dict, evaluator: PolicyEvaluator) -> dict:
    if payload.get("hook_event_name") != "PreToolUse":
        raise ValueError("Expected PreToolUse event")
    tool = payload.get("tool_name", "")
    if not isinstance(tool, str):
        raise ValueError("Invalid tool name")
    if not tool.startswith("mcp__taskflow_kb__"):
        return {}  # Deliberately outside this integration's scope.
    arguments = payload.get("tool_input", {})
    if not isinstance(arguments, dict):
        raise ValueError("Invalid tool input")
    operation = {
        "mcp__taskflow_kb__get_note": "read",
        "mcp__taskflow_kb__ingest_note": "write",
    }.get(tool)
    if tool == "mcp__taskflow_kb__search_notes":
        query = arguments.get("query")
        if isinstance(query, str) and query.strip():
            # PR7 server applies PolicyEvaluator before every indexed read and
            # before returning results; the hook validates only the query.
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
        result = Decision("block", "invalid_query", "A nonempty search query is required.")
    elif operation is None:
        # Bulk search could expose sensitive note contents even for an innocent
        # query. Its result cannot be filtered by a pre-execution path policy.
        result = Decision("block", "unsupported_tool", "Unsupported knowledge-base tool.")
    else:
        result = evaluator.evaluate(operation, arguments.get("note_path"))
    output = {"hookEventName": "PreToolUse"}
    if result.decision == "block":
        output.update(permissionDecision="deny", permissionDecisionReason=result.reason)
    elif result.decision == "warn":
        # 'ask' is explicitly unsupported by current Codex PreToolUse docs.
        output["additionalContext"] = f"WARNING [{result.rule}]: {result.reason}"
    return {"hookSpecificOutput": output}


def main() -> int:
    try:
        root = Path(os.environ.get("TASKFLOW_KB_PATH", str(Path(__file__).resolve().parents[2] / "TaskFlow-KB")))
        evaluator = PolicyEvaluator(root)
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Hook payload must be an object")
        output = evaluate_hook(payload, evaluator)
    except Exception:
        # Explicit supported denial, without echoing untrusted input or secrets.
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Guardrails could not evaluate the request.",
        }}
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
