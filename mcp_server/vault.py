import os
from pathlib import Path

from mcp_server.git_ingest import GitIngestor
from guardrails.policy import PolicyEvaluator
from mcp_server.rag import VectorIndex


EXCLUDED = {".git", ".obsidian"}


class Vault:
    def __init__(self, root: Path, *, index_dir=None, encoder=None):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Vault must be an existing directory")
        self.ingestor = GitIngestor(self)
        self.policy = PolicyEvaluator(self.root)
        self.rag = VectorIndex(self, index_dir=index_dir, encoder=encoder)

    def note_path(self, note_path: str) -> Path:
        # Accept either separator, but never absolute, drive, ADS or parent paths.
        parts = note_path.replace("\\", "/").split("/")
        if any(
            not part or part in {".", ".."} or part.casefold() in EXCLUDED
            or ":" in part or "\x00" in part or part.endswith((" ", "."))
            for part in parts
        ):
            raise ValueError("Use a relative Markdown path inside the vault")
        target = self.root.joinpath(*parts)
        if target.suffix.casefold() != ".md":
            raise ValueError("Only Markdown (.md) notes are allowed")
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink() or current.is_junction():
                raise ValueError("Links and junctions are not allowed")
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Path is outside the vault")
        if target.is_file() and target.stat().st_nlink > 1:
            raise ValueError("Hard-linked files are not allowed")
        return target

    def get_note(self, note_path: str) -> str:
        decision = self.policy.evaluate("read", note_path)
        if decision.decision == "block":
            raise ValueError(decision.reason)
        return self.note_path(note_path).read_text(encoding="utf-8")

    def ingest_note(self, note_path: str, content: str) -> dict:
        return self.ingestor.ingest(note_path, content)

    def search_notes(self, query: str) -> list[str]:
        return [hit["path"] for hit in self.rag.search(query)]

    def lexical_search_notes(self, query: str) -> list[str]:
        """Original substring baseline, with the same safe corpus as RAG."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query must not be blank")
        query = query.casefold()
        return sorted(path for path, content in self.iter_notes()
                      if query in Path(path).name.casefold() or query in content.casefold())

    def iter_notes(self):
        """Apply policy before every file read, shared by lexical and semantic search."""
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs
                if name.casefold() not in EXCLUDED
                and not (Path(directory) / name).is_symlink()
                and not (Path(directory) / name).is_junction()
            )
            for name in sorted(files):
                if Path(name).suffix.casefold() != ".md":
                    continue
                relative = (Path(directory) / name).relative_to(self.root).as_posix()
                if self.policy.evaluate("read", relative).decision == "block":
                    continue
                try:
                    path = self.note_path(relative)
                    content = path.read_text(encoding="utf-8")
                except (OSError, ValueError):
                    # Unreadable, invalid UTF-8 and unsafe notes are not searched.
                    continue
                yield relative, content
