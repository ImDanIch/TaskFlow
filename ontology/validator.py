import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

import yaml


DEFINITIONS = json.loads(Path(__file__).with_name("definitions.json").read_text(encoding="utf-8"))


class UniqueKeyLoader(yaml.SafeLoader):
    """Do not silently accept contradictory duplicate frontmatter keys."""


def unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in mapping:
            raise ValueError("YAML keys must be unique strings")
        mapping[key] = loader.construct_object(value_node)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


@dataclass
class Report:
    entities: dict[str, str] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_note(text: str):
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("Unclosed YAML frontmatter")
    metadata = yaml.load("\n".join(lines[1:end]), Loader=UniqueKeyLoader)
    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter must be a mapping")
    return metadata, "\n".join(lines[end + 1:])


def resolve_reference(reference: str, entities: dict[str, str]) -> str:
    name = reference.strip()
    if name.startswith("[[") and name.endswith("]]"):
        name = name[2:-2]
    name = name.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
    if not name or ":" in name or any(p in {"", ".", ".."} for p in name.split("/")):
        raise ValueError(f"Invalid reference: {reference!r}")
    if not name.casefold().endswith(".md"):
        name += ".md"
    if "/" in name:
        candidates = [path for path in entities if path == name]
    else:
        candidates = [path for path in entities if Path(path).name == name]
    if len(candidates) != 1:
        reason = "Ambiguous" if candidates else "Missing or invalid entity"
        raise ValueError(f"{reason} reference: {reference!r}")
    return candidates[0]


def validate_vault(root: Path) -> Report:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Vault must be a directory")
    report = Report()
    notes = {}
    # Path.walk permits pruning metadata folders without traversing them.
    for directory, dirs, files in root.walk(follow_symlinks=False):
        dirs[:] = sorted(d for d in dirs if d.casefold() not in {".git", ".obsidian"}
                         and not (directory / d).is_symlink()
                         and not (directory / d).is_junction())
        for filename in sorted(files):
            path = directory / filename
            if path.suffix.casefold() != ".md" or path.is_symlink() or path.is_junction():
                continue
            relative = path.relative_to(root).as_posix()
            try:
                metadata, body = parse_note(path.read_text(encoding="utf-8"))
                if metadata is None or metadata.get("type") == "moc":
                    report.warnings.append(f"{relative}: skipped non-entity note")
                    continue
                entity_type = metadata.get("type")
                if not isinstance(entity_type, str) or entity_type not in DEFINITIONS["entity_types"]:
                    raise ValueError(f"Invalid entity type: {entity_type!r}")
                report.entities[relative] = entity_type
                notes[relative] = metadata, body
            except (OSError, ValueError, yaml.YAMLError) as exc:
                report.errors.append(f"{relative}: {exc}")

    for source, (metadata, body) in notes.items():
        relations = metadata.get("relationships", [])
        if not isinstance(relations, list):
            report.errors.append(f"{source}: relationships must be a list")
            relations = []
        # Legacy body links have no explicit predicate; interpret as related_to.
        relations = relations + [
            {"type": "related_to", "target": link}
            for link in re.findall(r"(?<!!)\[\[([^\]\n]+)\]\]", body)
        ]
        for relation in relations:
            try:
                if not isinstance(relation, dict) or set(relation) != {"type", "target"}:
                    raise ValueError("Relationship requires exactly type and target")
                kind, target = relation["type"], relation["target"]
                if not isinstance(kind, str) or kind not in DEFINITIONS["relationship_types"]:
                    raise ValueError(f"Invalid relationship type: {kind!r}")
                if not isinstance(target, str):
                    raise ValueError("Relationship target must be a string")
                resolved = resolve_reference(target, report.entities)
                edge = {"source": source, "type": kind, "target": resolved}
                if edge not in report.relationships:
                    report.relationships.append(edge)
            except ValueError as exc:
                report.errors.append(f"{source}: {exc}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Markdown ontology without writing notes")
    parser.add_argument("vault", type=Path)
    args = parser.parse_args()
    try:
        report = validate_vault(args.vault)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    print(f"Entities: {len(report.entities)}; relationships: {len(report.relationships)}; errors: {len(report.errors)}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
