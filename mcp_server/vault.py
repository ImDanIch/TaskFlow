import os
from pathlib import Path

from mcp_server.git_ingest import GitIngestor


EXCLUDED = {".git", ".obsidian"}


class Vault:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Vault must be an existing directory")
        self.ingestor = GitIngestor(self)

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
        return self.note_path(note_path).read_text(encoding="utf-8")

    def ingest_note(self, note_path: str, content: str) -> dict:
        return self.ingestor.ingest(note_path, content)

    def search_notes(self, query: str) -> list[str]:
        if not query.strip():
            raise ValueError("Search query must not be blank")
        query = query.casefold()
        matches = []
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
                try:
                    path = self.note_path(relative)
                    content = path.read_text(encoding="utf-8")
                except (OSError, ValueError):
                    # Unreadable, invalid UTF-8 and unsafe notes are not searched.
                    continue
                if query in name.casefold() or query in content.casefold():
                    matches.append(relative)
        return sorted(matches)
