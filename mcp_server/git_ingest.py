"""Scoped Git ingestion. Git output is never returned to MCP callers."""

import os
from pathlib import Path
import re
import subprocess
from threading import Lock

from guardrails.policy import PolicyEvaluator


class GitFailure(Exception):
    pass


def git(root, *args):
    # Prevent inherited Git plumbing variables from redirecting writes to a
    # different repository/index or injecting per-command configuration.
    env = {key: value for key, value in os.environ.items() if not (
        key.upper() in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}
        or key.upper().startswith("GIT_CONFIG")
    )}
    try:
        result = subprocess.run(
            ["git", "--literal-pathspecs", "-C", str(root), *args],
            env={**env, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"},
            stdin=subprocess.DEVNULL, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitFailure() from exc
    if result.returncode:
        raise GitFailure()
    return result.stdout.decode("utf-8", errors="replace").strip()


def check_content(content):
    # Reject common credential formats and credential assignments, including
    # YAML frontmatter. Arbitrary secrets in prose cannot be classified reliably.
    if not isinstance(content, str) or re.search(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})\b|"
        r"(?im:^\s*[\w.-]*(?:password|passwd|secret|token|api[_-]?key|credential)"
        r"[\w.-]*\s*[:=]\s*\S+)", content,
    ):
        raise ValueError("Credential-like content is forbidden")


class GitIngestor:
    def __init__(self, vault):
        self.vault = vault
        self.lock = Lock()

    def ingest(self, note_path, content):
        with self.lock:
            return self._ingest(note_path, content)

    def _ingest(self, note_path, content):
        root = self.vault.root
        target = self.vault.note_path(note_path)
        relative = target.relative_to(root).as_posix()
        check_content(content)
        policy = PolicyEvaluator(root)
        if policy.evaluate("write", relative).decision == "block":
            raise ValueError("Note path is forbidden by guardrails")
        phase = "repository"
        commit = None
        result = {"status": "error", "note_path": relative}
        try:
            if os.path.normcase(git(root, "rev-parse", "--show-toplevel").replace("\\", "/")) != os.path.normcase(root.as_posix()):
                raise GitFailure()
            branch = git(root, "symbolic-ref", "--short", "HEAD")
            remote = os.environ.get("TASKFLOW_KB_GIT_REMOTE", "origin")
            if not remote or remote.startswith("-") or remote not in git(root, "remote").splitlines():
                phase = "remote"
                raise GitFailure()
            git(root, "remote", "get-url", "--push", remote)
            phase = "dirty_target"
            if git(root, "status", "--porcelain", "--untracked-files=all", "--ignored", "--", relative):
                raise GitFailure()
            phase = "operation_in_progress"
            for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
                marker_path = Path(git(root, "rev-parse", "--git-path", marker))
                if not marker_path.is_absolute():
                    marker_path = root / marker_path
                if marker_path.exists():
                    raise GitFailure()
            phase = "pull"
            git(root, "-c", "rebase.autoStash=false", "-c", "merge.autoStash=false",
                "pull", "--ff-only", "--no-rebase", remote, branch)
            # Never publish pre-existing local commits along with this note.
            phase = "unpushed_commits"
            if git(root, "rev-list", "--count", "FETCH_HEAD..HEAD") != "0":
                raise GitFailure()
            target = self.vault.note_path(relative)
            if policy.evaluate("write", relative).decision == "block":
                raise GitFailure()
            phase = "dirty_target"
            if git(root, "status", "--porcelain", "--untracked-files=all", "--ignored", "--", relative):
                raise GitFailure()
            content_bytes = content.encode("utf-8")
            if target.exists() and target.read_bytes() == content_bytes:
                return {"status": "unchanged", "note_path": relative}
            phase = "write"
            existed = target.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            target = self.vault.note_path(relative)
            target.write_bytes(content_bytes)
            phase = "commit"
            git(root, "add", "--", relative)
            # --only excludes unrelated staged files and preserves their index.
            git(root, "commit", "--only", "-m", "Ingest knowledge-base note", "--", relative)
            commit = git(root, "rev-parse", "HEAD")
            phase = "push"
            git(root, "push", remote, f"HEAD:refs/heads/{branch}")
            return {"status": "updated" if existed else "created", "note_path": relative, "commit_hash": commit}
        except (GitFailure, OSError, UnicodeError, ValueError):
            result["error"] = phase
            if commit:
                result.update(status="push_failed", commit_hash=commit)
            return result
