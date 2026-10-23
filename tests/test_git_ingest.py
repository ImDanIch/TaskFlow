import pytest

from conftest import run_git


@pytest.mark.parametrize("content", ["# Note\n", "# Note\r\n"])
def test_idempotency_and_remote(git_vault, content):
    vault, remote = git_vault
    first = vault.ingest_note("Nested/Note.md", content)
    assert first["status"] == "created"
    assert run_git(remote, "rev-parse", "main") == first["commit_hash"]
    before = run_git(vault.root, "rev-parse", "HEAD")
    assert (vault.root / "Nested/Note.md").read_bytes() == content.encode("utf-8")
    assert vault.ingest_note("Nested/Note.md", content) == {
        "status": "unchanged", "note_path": "Nested/Note.md",
    }
    assert run_git(vault.root, "rev-parse", "HEAD") == before
    assert run_git(remote, "rev-parse", "main") == before


def test_only_target_committed_preserves_unrelated_index(git_vault):
    vault, remote = git_vault
    unrelated = vault.root / "Unrelated.md"
    unrelated.write_text("Unrelated staged content", encoding="utf-8")
    run_git(vault.root, "add", "Unrelated.md")
    (vault.root / ".env").write_text("TEST_ONLY=placeholder", encoding="utf-8")
    staged = run_git(vault.root, "diff", "--cached")
    result = vault.ingest_note("-literal[1].md", "Target only")
    assert result["status"] == "created"
    assert run_git(vault.root, "diff", "--cached") == staged
    assert run_git(remote, "diff-tree", "--no-commit-id", "--name-only", "-r", "main") == "-literal[1].md"
    assert ".env" not in run_git(remote, "ls-tree", "-r", "--name-only", "main")


@pytest.mark.parametrize("stage", [False, True])
def test_dirty_target_refused(git_vault, stage):
    vault, remote = git_vault
    assert vault.ingest_note("Note.md", "Committed")["status"] == "created"
    head = run_git(remote, "rev-parse", "main")
    (vault.root / "Note.md").write_text("Local edit", encoding="utf-8")
    if stage:
        run_git(vault.root, "add", "Note.md")
    result = vault.ingest_note("Note.md", "Replacement")
    assert result["error"] == "dirty_target"
    assert (vault.root / "Note.md").read_text() == "Local edit"
    assert run_git(remote, "rev-parse", "main") == head


def test_untracked_target_refused(git_vault):
    vault, _ = git_vault
    (vault.root / "New.md").write_text("Local work")
    assert vault.ingest_note("New.md", "Replacement")["error"] == "dirty_target"


def test_missing_remote_no_write(git_vault):
    vault, _ = git_vault
    run_git(vault.root, "remote", "remove", "origin")
    assert vault.ingest_note("New.md", "New")["error"] == "remote"
    assert not (vault.root / "New.md").exists()


def test_configured_remote(git_vault, monkeypatch):
    vault, remote = git_vault
    run_git(vault.root, "remote", "rename", "origin", "knowledge")
    monkeypatch.setenv("TASKFLOW_KB_GIT_REMOTE", "knowledge")
    result = vault.ingest_note("New.md", "New")
    assert result["status"] == "created"
    assert run_git(remote, "rev-parse", "main") == result["commit_hash"]


def test_failed_pull_no_write(git_vault):
    vault, _ = git_vault
    run_git(vault.root, "remote", "set-url", "origin", str(vault.root.parent / "missing.git"))
    assert vault.ingest_note("New.md", "New")["error"] == "pull"
    assert not (vault.root / "New.md").exists()


def test_in_progress_operation_no_write(git_vault):
    vault, _ = git_vault
    (vault.root / ".git/MERGE_HEAD").write_text(run_git(vault.root, "rev-parse", "HEAD"))
    assert vault.ingest_note("New.md", "New")["error"] == "operation_in_progress"
    assert not (vault.root / "New.md").exists()


def test_commit_failure_preserves_local_work(git_vault):
    vault, remote = git_vault
    head = run_git(remote, "rev-parse", "main")
    hook = vault.root / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    result = vault.ingest_note("New.md", "New")
    assert result == {"status": "error", "note_path": "New.md", "error": "commit"}
    assert (vault.root / "New.md").read_text() == "New"
    assert run_git(remote, "rev-parse", "main") == head
    assert run_git(vault.root, "rev-parse", "HEAD") == head


def test_inherited_git_index_cannot_redirect_commit(git_vault, monkeypatch):
    vault, _ = git_vault
    foreign_index = vault.root.parent / "foreign-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(foreign_index))
    result = vault.ingest_note("New.md", "New")
    assert result["status"] == "created"
    assert not foreign_index.exists()


def peer_clone(vault, remote):
    peer = vault.root.parent / "peer"
    run_git(vault.root.parent, "clone", str(remote), str(peer))
    run_git(peer, "config", "user.name", "Peer Test")
    run_git(peer, "config", "user.email", "peer@example.invalid")
    return peer


def test_pull_before_comparison(git_vault):
    vault, remote = git_vault
    peer = peer_clone(vault, remote)
    (peer / "Note.md").write_text("Remote note")
    run_git(peer, "add", "Note.md")
    run_git(peer, "commit", "-m", "Remote change")
    run_git(peer, "push")
    result = vault.ingest_note("Note.md", "Remote note")
    assert result["status"] == "unchanged"
    assert (vault.root / "Note.md").read_text() == "Remote note"


def test_diverged_history_no_write(git_vault):
    vault, remote = git_vault
    peer = peer_clone(vault, remote)
    for root, content in [(vault.root, "local"), (peer, "remote")]:
        (root / "README.md").write_text(content)
        run_git(root, "add", "README.md")
        run_git(root, "commit", "-m", "Divergent change")
    run_git(peer, "push")
    assert vault.ingest_note("New.md", "New")["error"] == "pull"
    assert not (vault.root / "New.md").exists()
    assert (vault.root / "README.md").read_text() == "local"


def test_unpushed_commits_not_published(git_vault):
    vault, remote = git_vault
    remote_head = run_git(remote, "rev-parse", "main")
    (vault.root / "Other.md").write_text("Unpublished")
    run_git(vault.root, "add", "Other.md")
    run_git(vault.root, "commit", "-m", "Unpublished work")
    assert vault.ingest_note("New.md", "New")["error"] == "unpushed_commits"
    assert run_git(remote, "rev-parse", "main") == remote_head
    assert not (vault.root / "New.md").exists()


def test_push_failure_retains_commit(git_vault):
    vault, remote = git_vault
    before = run_git(remote, "rev-parse", "main")
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    result = vault.ingest_note("New.md", "New")
    assert result["status"] == "push_failed"
    assert result["error"] == "push"
    assert result["commit_hash"] == run_git(vault.root, "rev-parse", "HEAD")
    assert run_git(remote, "rev-parse", "main") == before
    assert (vault.root / "New.md").read_text() == "New"
    # Retrying does not silently publish pending commits or report unchanged.
    assert vault.ingest_note("New.md", "New")["error"] == "unpushed_commits"


@pytest.mark.parametrize("path,content", [
    (".env.md", "example"), ("Credentials.md", "example"),
    ("Nested/Secrets.md", "example"), (".aws/Note.md", "example"),
    ("Note.md", "password: example-value"),
    ("Note.md", "-----BEGIN PRIVATE KEY-----\nexample"),
])
def test_credentials_refused_before_git(tmp_path, path, content):
    from mcp_server.vault import Vault
    vault = Vault(tmp_path)
    with pytest.raises(ValueError):
        vault.ingest_note(path, content)
    assert list(vault.root.rglob("*.md")) == []
