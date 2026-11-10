import pytest

from orchestration.workflow import Workflow


def transfer(flow, role, next_role):
    flow.handoff(role, agent_id=f"agent-{role}", context="scope and acceptance",
                 rationale="decision evidence", result="actual result", next_role=next_role)


def test_full_cycle_and_rework():
    flow = Workflow("small API enhancement")
    for role, successor in [("Planner", "Coder"), ("Coder", "Reviewer"),
                            ("Reviewer", "Coder"), ("Coder", "Reviewer"),
                            ("Reviewer", "Complete")]:
        transfer(flow, role, successor)
    assert flow.active == "Complete"
    assert len(flow.events) == 5
    with pytest.raises(ValueError):
        transfer(flow, "Planner", "Coder")


def test_cannot_skip_review_or_omit_context():
    flow = Workflow("task")
    with pytest.raises(ValueError):
        transfer(flow, "Planner", "Complete")
    with pytest.raises(ValueError):
        flow.handoff("Planner", agent_id="a", context=" ", rationale="r",
                     result="x", next_role="Coder")
    assert flow.events == []
    assert flow.active == "Planner"


def test_ledger_save_respects_guardrails(tmp_path):
    flow = Workflow("task")
    with pytest.raises(PermissionError):
        flow.save(tmp_path, "../escape.json")
    with pytest.raises(PermissionError):
        flow.save(tmp_path, ".codex/run.json")
    flow.save(tmp_path, "artifacts/run.json")
    assert '"task": "task"' in (tmp_path / "artifacts/run.json").read_text()
