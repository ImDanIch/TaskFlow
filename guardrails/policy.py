from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
import json
from pathlib import Path, PureWindowsPath


POLICY_PATH = Path(__file__).with_name("policies.json")


@dataclass(frozen=True)
class Decision:
    decision: str
    rule: str
    reason: str

    def as_dict(self):
        return asdict(self)


class PolicyEvaluator:
    """Evaluate without reading note contents or writing any files."""

    def __init__(self, vault: Path, policy_path: Path = POLICY_PATH):
        self.vault = vault.resolve(strict=True)
        if not self.vault.is_dir():
            raise ValueError("Vault must be an existing directory")
        self.policy = json.loads(policy_path.read_text(encoding="utf-8"))
        conditions = {
            "invalid_path", "outside_vault", "sensitive_path", "delete", "metadata",
            "unsafe_link", "not_markdown", "read", "existing_write", "write", "always",
        }
        if not isinstance(self.policy.get("rules"), list) or not self.policy["rules"]:
            raise ValueError("Policy rules must be a nonempty list")
        for rule in self.policy["rules"]:
            if (set(rule) != {"id", "condition", "decision", "reason"}
                    or rule["condition"] not in conditions
                    or rule["decision"] not in {"allow", "warn", "block"}):
                raise ValueError("Invalid policy rule")
        for key in ("sensitive_names", "excluded_directories"):
            if not isinstance(self.policy.get(key), list) or not all(
                isinstance(item, str) for item in self.policy[key]
            ):
                raise ValueError(f"Invalid policy {key}")

    def evaluate(self, operation: str, note_path: str) -> Decision:
        try:
            return self._evaluate(operation, note_path)
        except (OSError, ValueError, RuntimeError):
            return Decision("block", "path_error", "Cannot safely evaluate the requested path.")

    def _evaluate(self, operation: str, note_path: str) -> Decision:
        if not isinstance(note_path, str) or not note_path or "\x00" in note_path:
            return Decision("block", "invalid_path", "A nonempty note path is required.")
        raw = note_path.replace("\\", "/")
        path = Path(raw)
        windows = PureWindowsPath(raw)
        invalid = bool(windows.drive and not windows.is_absolute())
        # Reject drive/ADS syntax on platforms where it is not an absolute path.
        invalid = invalid or (":" in raw and not path.is_absolute())
        parts = path.parts[1:] if path.anchor else path.parts
        reserved = {"con", "prn", "aux", "nul"} | {
            f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
        }
        invalid = invalid or any(
            part == ".." or ":" in part or part.endswith((" ", "."))
            or part.split(".")[0].casefold() in reserved for part in parts
        )
        target = path if path.is_absolute() else self.vault / path
        resolved = target.resolve()
        outside = not resolved.is_relative_to(self.vault)
        names = [part.casefold() for part in target.parts]
        sensitive = any(fnmatchcase(name, pattern.casefold())
                        for name in names for pattern in self.policy["sensitive_names"])
        metadata = any(name in self.policy["excluded_directories"] for name in names)
        unsafe_link = False
        for candidate in (target, *target.parents):
            if candidate == self.vault:
                break
            if candidate.is_symlink() or candidate.is_junction():
                unsafe_link = True
        if target.is_file() and target.stat().st_nlink > 1:
            unsafe_link = True
        context = {
            "invalid_path": invalid,
            "outside_vault": outside,
            "sensitive_path": sensitive,
            "delete": operation == "delete",
            "metadata": metadata,
            "unsafe_link": unsafe_link,
            "not_markdown": target.suffix.casefold() != ".md" or target.is_dir(),
            "read": operation == "read",
            "existing_write": operation == "write" and target.exists(),
            "write": operation == "write",
            "always": True,
        }
        for rule in self.policy["rules"]:
            if context[rule["condition"]]:
                return Decision(rule["decision"], rule["id"], rule["reason"])
        return Decision("block", "default_deny", "No matching policy rule.")
