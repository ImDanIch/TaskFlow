"""Validated handoff ledger; role execution is supplied by the Codex host."""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

from guardrails.policy import CodePolicyEvaluator


@dataclass
class Workflow:
    task: str
    active: str = "Planner"
    events: list[dict] = field(default_factory=list)

    def handoff(self, role, *, agent_id, context, rationale, result, next_role):
        """Record a real result and transfer ownership, including rework."""
        transitions = {"Planner": {"Coder"}, "Coder": {"Reviewer"},
                       "Reviewer": {"Coder", "Complete"}}
        if role != self.active or next_role not in transitions.get(role, set()):
            raise ValueError("Invalid role transition")
        if not all(isinstance(value, str) and value.strip()
                   for value in (agent_id, context, rationale, result)):
            raise ValueError("Agent identity, context, rationale and result are required")
        self.events.append(dict(role=role, agent_id=agent_id, context=context,
                                rationale=rationale, result=result, next_role=next_role))
        self.active = next_role

    def save(self, root: Path, relative_path: str):
        decision = CodePolicyEvaluator(root).evaluate("write", relative_path)
        if decision.decision == "block":
            raise PermissionError(decision.reason)
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
