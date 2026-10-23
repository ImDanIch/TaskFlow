import pytest
import subprocess
from sqlalchemy import create_engine

from app import database


def run_git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True, timeout=15,
    ).stdout.strip()


@pytest.fixture
def git_vault(tmp_path):
    from mcp_server.vault import Vault

    remote = tmp_path / "remote.git"
    remote.mkdir()
    run_git(remote, "init", "--bare", "--initial-branch=main")
    root = tmp_path / "vault"
    root.mkdir()
    run_git(root, "init", "--initial-branch=main")
    run_git(root, "config", "user.name", "Ingestion Test")
    run_git(root, "config", "user.email", "test@example.invalid")
    run_git(root, "config", "core.autocrlf", "false")
    (root / "README.md").write_text("# Test vault\n", encoding="utf-8")
    run_git(root, "add", "README.md")
    run_git(root, "commit", "-m", "Initial vault")
    run_git(root, "remote", "add", "origin", str(remote))
    run_git(root, "push", "-u", "origin", "main")
    return Vault(root), remote


@pytest.fixture(autouse=True)
def database_engine(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", database.sessionmaker(bind=engine))
    yield engine
    engine.dispose()
