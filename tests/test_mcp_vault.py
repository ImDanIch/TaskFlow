import os

import pytest

from mcp_server.vault import Vault


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    return Vault(root)


def test_create_read_update(git_vault):
    vault, _ = git_vault
    result = vault.ingest_note("Concepts/API.md", "# API\nУкраїнська")
    assert result["status"] == "created"
    assert result["note_path"] == "Concepts/API.md"
    assert vault.get_note("Concepts/API.md") == "# API\nУкраїнська"
    assert vault.ingest_note("Concepts/API.md", "Updated")["status"] == "updated"
    assert vault.get_note("Concepts/API.md") == "Updated"


def test_search(vault):
    (vault.root / "API.md").write_text("Other", encoding="utf-8")
    (vault.root / "Nested").mkdir()
    (vault.root / "Nested/Note.md").write_text("Learn api", encoding="utf-8")
    (vault.root / "Unrelated.md").write_text("Other", encoding="utf-8")
    for excluded in (".git", ".obsidian"):
        folder = vault.root / excluded
        folder.mkdir()
        (folder / "API.md").write_text("api", encoding="utf-8")
    (vault.root / "API.txt").write_text("api", encoding="utf-8")
    assert vault.search_notes("ApI") == ["API.md", "Nested/Note.md"]
    assert vault.search_notes("missing") == []
    with pytest.raises(ValueError):
        vault.search_notes(" ")


@pytest.mark.parametrize("path", [
    "../outside.md", "nested/../../outside.md", "..\\outside.md", "/outside.md",
    "C:\\outside.md", "C:outside.md", "//server/share/note.md", "note.md:stream",
    ".git/note.md", ".OBSIDIAN/note.md", "note.txt", "", "a/./note.md",
    "a./note.md", "a /note.md", "a\x00.md",
])
def test_rejects_unsafe_paths(vault, path):
    with pytest.raises(ValueError):
        vault.get_note(path)
    with pytest.raises(ValueError):
        vault.ingest_note(path, "Do not write")


def test_missing_note(vault):
    with pytest.raises(FileNotFoundError):
        vault.get_note("missing.md")


def test_symlink_escape(vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    note = outside / "note.md"
    note.write_text("secret", encoding="utf-8")
    link = vault.root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links requires OS permission")
    with pytest.raises(ValueError):
        vault.get_note("linked/note.md")
    with pytest.raises(ValueError):
        vault.ingest_note("linked/note.md", "overwrite")
    assert vault.search_notes("secret") == []
    assert note.read_text(encoding="utf-8") == "secret"


def test_hardlink_escape(vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    os.link(outside, vault.root / "linked.md")
    with pytest.raises(ValueError):
        vault.ingest_note("linked.md", "overwrite")
    with pytest.raises(ValueError):
        vault.get_note("linked.md")
    assert vault.search_notes("secret") == []
    assert outside.read_text(encoding="utf-8") == "secret"
