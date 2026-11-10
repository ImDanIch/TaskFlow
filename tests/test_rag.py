import json
from pathlib import Path

import pytest

from mcp_server.rag import chunk_text, SentenceEncoder
from mcp_server.vault import Vault


class FakeEncoder:
    """Controlled semantic equivalence without network/model downloads."""
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(texts)
        return [[float(any(word in text.casefold() for word in
                           ("database", "persistence", "сховище"))),
                 float(any(word in text.casefold() for word in ("api", "endpoint"))),
                 0.01] for text in texts]


@pytest.fixture
def indexed(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    encoder = FakeEncoder()
    return Vault(root, index_dir=tmp_path / "index", encoder=encoder), encoder


def test_windows_cover_source_with_overlap():
    text = "a" * 1300
    chunks = list(chunk_text(text))
    assert [(start, end) for start, end, _ in chunks] == [(0, 600), (500, 1100), (1000, 1300)]
    assert all(content == text[start:end] for start, end, content in chunks)
    assert list(chunk_text(" \n")) == []
    with pytest.raises(ValueError):
        list(chunk_text("x", 100, 100))


def test_semantic_paraphrase_rank_dedup_top5(indexed):
    vault, _ = indexed
    (vault.root / "Storage.md").write_text("database " * 200, encoding="utf-8")
    for i in range(6):
        (vault.root / f"API{i}.md").write_text("endpoint", encoding="utf-8")
    assert vault.lexical_search_notes("persistence") == []
    vault.rag.build_index()
    hits = vault.rag.search("persistence")
    assert hits[0]["path"] == "Storage.md"
    assert hits[0]["score"] == pytest.approx(1)
    assert len(hits) == len({hit["path"] for hit in hits}) == 5
    assert vault.search_notes("persistence") == [hit["path"] for hit in hits]


def test_cache_reuse_edit_delete_and_corruption(indexed):
    vault, encoder = indexed
    note = vault.root / "One.md"
    note.write_text("database", encoding="utf-8")
    vault.rag.build_index()
    assert vault.search_notes("persistence") == ["One.md"]
    assert len(encoder.calls) == 2
    vault.search_notes("persistence")
    assert len(encoder.calls) == 3  # cached documents, query only
    # A fresh process/object also reuses the disk cache.
    new_encoder = FakeEncoder()
    new_vault = Vault(vault.root, index_dir=vault.rag.directory, encoder=new_encoder)
    new_vault.search_notes("persistence")
    assert len(new_encoder.calls) == 1
    note.write_text("endpoint", encoding="utf-8")
    vault.rag.build_index()
    assert vault.rag.search("api")[0]["text"] == "endpoint"
    assert len(encoder.calls) == 5
    vault.rag.path.write_text("broken JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        vault.search_notes("api")
    vault.rag.build_index()
    assert vault.search_notes("api") == ["One.md"]
    assert len(encoder.calls) == 7
    note.unlink()
    vault.rag.build_index()
    assert vault.search_notes("api") == []
    assert json.loads(vault.rag.path.read_text(encoding="utf-8"))["chunks"] == []


def test_policy_filters_before_read_and_invalidates_cached_note(indexed, monkeypatch):
    vault, _ = indexed
    for name in ("Public.md", "Credentials.md", "Secrets.md", ".env.local.md"):
        (vault.root / name).write_text("database", encoding="utf-8")
    original = Path.read_text
    blocked = {"Credentials.md", "Secrets.md", ".env.local.md"}

    def guarded(path, *args, **kwargs):
        assert path.name not in blocked, "Sensitive file content was read"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    vault.rag.build_index()
    assert vault.search_notes("persistence") == ["Public.md"]
    assert vault.lexical_search_notes("database") == ["Public.md"]
    with pytest.raises(ValueError):
        vault.get_note("Credentials.md")
    vault.policy.policy["sensitive_names"].append("public.md")
    blocked.add("Public.md")
    assert vault.search_notes("persistence") == []
    vault.rag.build_index()
    assert "Public.md" not in vault.rag.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("query", ["", " \n", None, 5])
def test_invalid_query(indexed, query):
    with pytest.raises(ValueError):
        indexed[0].search_notes(query)


def test_forbid_index_in_vault(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        Vault(tmp_path, index_dir=tmp_path / "cache", encoder=FakeEncoder())


def test_nonfinite_or_wrong_dimension_cache_rebuild(indexed):
    vault, encoder = indexed
    (vault.root / "One.md").write_text("database", encoding="utf-8")
    vault.rag.build_index()
    vault.search_notes("persistence")
    cached = json.loads(vault.rag.path.read_text(encoding="utf-8"))
    cached["vectors"] = [[float("nan")]]
    vault.rag.path.write_text(json.dumps(cached), encoding="utf-8")
    vault.rag.build_index()
    assert vault.search_notes("persistence") == ["One.md"]
    assert len(encoder.calls) == 4


def test_search_uses_ready_index_without_rescanning(indexed, monkeypatch):
    vault, encoder = indexed
    (vault.root / 'One.md').write_text('database', encoding='utf-8')
    vault.rag.build_index()
    monkeypatch.setattr(vault.rag, '_snapshot', lambda: pytest.fail('Search rescanned corpus'))
    vault.search_notes('persistence')
    vault.search_notes('persistence')
    assert [len(call) for call in encoder.calls] == [1, 1, 1]


def test_model_manifest_missing_files_fails_before_import(monkeypatch):
    from mcp_server import rag
    monkeypatch.setattr(rag, '_MODELS', {})
    monkeypatch.setattr(Path, 'read_text', lambda *a, **k: json.dumps(
        dict(model=rag.MODEL, revision=rag.REVISION, hashes={})))
    with pytest.raises(RuntimeError, match='Local model incomplete'):
        SentenceEncoder(None).encode(['query'])
