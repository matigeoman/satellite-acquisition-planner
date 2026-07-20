from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UTF8_BOM = b"\xef\xbb\xbf"


def test_powershell_launchers_have_utf8_bom_for_windows_powershell_51() -> None:
    for relative in (
        "scripts/start_satplan.ps1",
        "scripts/stop_satplan.ps1",
    ):
        raw = (PROJECT_ROOT / relative).read_bytes()

        assert raw.startswith(UTF8_BOM), relative
        text = raw.decode("utf-8-sig")
        assert chr(0x00C3) not in text
        assert chr(0x00C5) not in text
        assert chr(0x00C4) not in text


def test_dockerignore_excludes_large_local_research_artifacts() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "*.pdf" in dockerignore
    assert "*.tif" in dockerignore
    assert ".conda/**" in dockerignore
    assert "research/**" in dockerignore
