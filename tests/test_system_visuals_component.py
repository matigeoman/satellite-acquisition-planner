from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = PROJECT_ROOT / "app/ui/components/system_visuals.py"
PAGE_PATH = PROJECT_ROOT / "app/ui/pages/system_overview.py"
DIAGRAM_PATH = PROJECT_ROOT / "docs/assets/diagrams/constellation_phasing.svg"


def test_constellation_component_is_local_and_interactive() -> None:
    source = COMPONENT_PATH.read_text(encoding="utf-8")

    assert "st.iframe(" in source
    assert "streamlit.components.v1" not in source
    assert 'width="stretch"' in source
    assert "tab_index=0" in source
    assert "requestAnimationFrame" in source
    assert "toggleMotion" in source
    assert 'data-speed="1"' in source
    assert 'data-speed="2"' in source
    assert 'data-speed="4"' in source
    assert "prefers-reduced-motion" in source
    assert "render_constellation_phasing_visual" in source
    assert "http://" not in source
    assert "https://" not in source


def test_system_page_uses_interactive_phasing_component() -> None:
    source = PAGE_PATH.read_text(encoding="utf-8")

    assert "render_constellation_phasing_visual" in source
    assert 'with st.expander("Tabela parametrów fazowania"' in source
    assert "phasing.to_dict(orient=\"records\")" in source


def test_static_constellation_diagram_is_valid_and_non_overlapping_by_design() -> None:
    ET.parse(DIAGRAM_PATH)
    source = DIAGRAM_PATH.read_text(encoding="utf-8")

    assert "phase cards" in source
    assert "SAR-01" in source
    assert "EO-02" in source
    assert "Model scenariusza ≠ bieżąca pozycja satelity" in source
    assert 'x="782" y="450"' not in source
