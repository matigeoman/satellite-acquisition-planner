from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = PROJECT_ROOT / "docs"
_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _relative_markdown_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    text = path.read_text(encoding="utf-8")

    for match in _MARKDOWN_LINK.finditer(text):
        raw_target = match.group(1).strip()
        if raw_target.startswith(("http://", "https://", "mailto:", "#")):
            continue

        target_without_anchor = raw_target.split("#", maxsplit=1)[0]
        if not target_without_anchor:
            continue

        targets.append((path.parent / target_without_anchor).resolve())

    return targets


def test_relative_markdown_links_resolve() -> None:
    markdown_files = [PROJECT_ROOT / "README.md", *sorted(DOCS_ROOT.glob("*.md"))]
    missing: list[str] = []

    for markdown_file in markdown_files:
        for target in _relative_markdown_targets(markdown_file):
            if not target.exists():
                missing.append(
                    f"{markdown_file.relative_to(PROJECT_ROOT)} -> "
                    f"{target.relative_to(PROJECT_ROOT)}"
                )

    assert not missing, "Nieistniejące odnośniki:\n" + "\n".join(missing)


def test_documentation_index_references_every_document() -> None:
    index_targets = {
        target
        for target in _relative_markdown_targets(DOCS_ROOT / "index.md")
        if target.parent == DOCS_ROOT.resolve()
    }
    expected = {
        path.resolve()
        for path in DOCS_ROOT.glob("*.md")
        if path.name != "index.md"
    }

    assert index_targets == expected


def test_documented_compose_filename_matches_repository() -> None:
    project_structure = (DOCS_ROOT / "project_structure.md").read_text(
        encoding="utf-8"
    )

    assert "docker-compose.yml" in project_structure
    assert "Docker-compose.yml" not in project_structure
    assert (PROJECT_ROOT / "docker-compose.yml").is_file()


def test_architecture_routes_orchestration_through_services() -> None:
    architecture = (DOCS_ROOT / "architecture.md").read_text(encoding="utf-8")

    assert "UI->>S: uruchom przypadek użycia" in architecture
    assert "S->>O: pobierz OMM i propaguj" in architecture
    assert "S->>P: okazje + kontakty + ograniczenia" in architecture
