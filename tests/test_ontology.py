import subprocess
import sys

import pytest

from ontology.validator import validate_vault


def note(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_existing_style_and_no_writes(tmp_path):
    note(tmp_path, "Components/SQLite.md", "---\ntype: component\ntags: [database]\n---\n# SQLite")
    note(tmp_path, "Concepts/API.md", "---\ntype: concept\n---\n[[SQLite|DB]] [[Components/SQLite#Details]]")
    note(tmp_path, "README.md", "# Navigation")
    note(tmp_path, "MOC.md", "---\ntype: moc\n---\n[[Unknown]]")
    for folder in (".git", ".obsidian"):
        note(tmp_path, f"{folder}/bad.md", "---\ntype: invalid\n---")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.md")}
    report = validate_vault(tmp_path)
    assert report.errors == []
    assert len(report.entities) == 2
    assert len(report.relationships) == 1
    assert report.relationships[0]["type"] == "related_to"
    assert len(report.warnings) == 2
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.md")}


@pytest.mark.parametrize("kind", ["uses", "depends_on", "implements", "related_to"])
def test_typed_relationships(tmp_path, kind):
    note(tmp_path, "DB.md", "---\ntype: component\n---")
    note(tmp_path, "Decision.md", f'---\ntype: decision\nrelationships:\n  - type: {kind}\n    target: "[[DB]]"\n---')
    report = validate_vault(tmp_path)
    assert not report.errors
    assert report.relationships == [{"source": "Decision.md", "type": kind, "target": "DB.md"}]


@pytest.mark.parametrize("kind", ["concept", "component", "decision", "glossary"])
def test_entity_types(tmp_path, kind):
    note(tmp_path, "Note.md", f"---\ntype: {kind}\n---")
    assert validate_vault(tmp_path).entities == {"Note.md": kind}


@pytest.mark.parametrize("frontmatter", [
    "type: unknown", "tags: []", "type: [concept]", "type: concept\ntype: component",
    "[concept]", "type: [", "type: concept\nrelationships: null",
    "type: concept\nrelationships: [bad]",
    "type: concept\nrelationships: [{type: invalid, target: DB}]",
    "type: concept\nrelationships: [{type: uses, target: 42}]",
    "type: concept\nrelationships: [{type: uses}]",
])
def test_invalid_frontmatter(tmp_path, frontmatter):
    note(tmp_path, "Bad.md", f"---\n{frontmatter}\n---")
    assert validate_vault(tmp_path).errors


@pytest.mark.parametrize("target", ["Missing", "../outside", "/outside", "C:/outside", ".obsidian/hidden"])
def test_invalid_references(tmp_path, target):
    note(tmp_path, "Note.md", f'---\ntype: concept\n---\n[[{target}]]')
    assert validate_vault(tmp_path).errors


def test_ambiguous_reference(tmp_path):
    for folder in ("A", "B"):
        note(tmp_path, f"{folder}/DB.md", "---\ntype: component\n---")
    note(tmp_path, "Note.md", "---\ntype: glossary\n---\n[[DB]]")
    assert "Ambiguous" in validate_vault(tmp_path).errors[0]
    note(tmp_path, "Note.md", "---\ntype: glossary\n---\n[[A/DB]]")
    assert not validate_vault(tmp_path).errors


def test_unclosed_yaml(tmp_path):
    note(tmp_path, "Note.md", "---\ntype: concept")
    assert "Unclosed" in validate_vault(tmp_path).errors[0]


def test_cli_exit_codes(tmp_path):
    note(tmp_path, "Note.md", "---\ntype: concept\n---")
    command = [sys.executable, "-m", "ontology.validator", str(tmp_path)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    note(tmp_path, "Note.md", "---\ntype: unknown\n---")
    assert subprocess.run(command, capture_output=True).returncode == 1
