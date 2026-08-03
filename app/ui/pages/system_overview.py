from __future__ import annotations

import json
from typing import TypedDict
import pandas as pd
import streamlit as st

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.catalogs.models import PublicMissionProfile
from app.ui.components.system_visuals import render_constellation_phasing_visual
from app.ui.page_layout import render_page_header, render_section_header
from app.ui.paths import PROJECT_ROOT


_DIAGRAM_ROOT = PROJECT_ROOT / "docs" / "assets" / "diagrams"
_DEMO_SYSTEM_PATH = (
    PROJECT_ROOT / "data" / "scenarios" / "poland_demo" / "system.json"
)


def _render_svg(filename: str, caption: str) -> None:
    path = _DIAGRAM_ROOT / filename
    if not path.is_file():
        st.warning(f"Brak diagramu: {path.relative_to(PROJECT_ROOT)}")
        return

    svg = path.read_text(encoding="utf-8")
    st.markdown(
        f'<div class="satplan-diagram">{svg}</div>',
        unsafe_allow_html=True,
    )
    st.caption(caption)


def _nominal_orbit_table() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for profile in (ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE):
        orbit = profile.orbit_template
        rows.append(
            {
                "Profil": profile.name,
                "Operator": profile.operator,
                "Sloty": profile.satellite_slots,
                "Typ orbity": orbit.orbit_type.value,
                "Wysokość nominalna [km]": orbit.altitude_km,
                "Inklinacja nominalna [°]": orbit.inclination_deg,
                "SSO": "tak" if orbit.is_sun_synchronous else "nie",
                "RAAN / epoka": "szablon — zastępowane przez OMM",
            }
        )
    return pd.DataFrame(rows)


def _sensor_table() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for profile in (ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE):
        sensor = profile.sensor
        maximum_off_nadir = max(
            mode.max_off_nadir_deg for mode in profile.imaging_modes
        )
        rows.append(
            {
                "Profil": profile.name,
                "Sensor": sensor.name,
                "Typ": sensor.sensor_type.value,
                "Pasmo": "—" if sensor.frequency_band is None else sensor.frequency_band.value,
                "Maks. off-nadir [°]": maximum_off_nadir,
                "Światło dzienne": "wymagane" if sensor.daylight_required else "nie",
                "Wrażliwość na chmury": "tak" if sensor.cloud_sensitive else "nie",
                "Min. elewacja Słońca [°]": (
                    "—"
                    if sensor.minimum_sun_elevation_deg is None
                    else f"{sensor.minimum_sun_elevation_deg:.1f}"
                ),
                "Domyślny limit chmur": (
                    "—"
                    if sensor.default_max_cloud_cover is None
                    else f"{sensor.default_max_cloud_cover:.0%}"
                ),
            }
        )
    return pd.DataFrame(rows)


def _mode_table(profile: PublicMissionProfile) -> pd.DataFrame:
    return pd.DataFrame(profile.mode_rows())


class _DemoSystem(TypedDict):
    orbits: list[dict[str, object]]
    satellites: list[dict[str, object]]


def _load_demo_system() -> _DemoSystem | None:
    if not _DEMO_SYSTEM_PATH.is_file():
        return None
    return json.loads(_DEMO_SYSTEM_PATH.read_text(encoding="utf-8"))


def _phasing_table() -> pd.DataFrame:
    system = _load_demo_system()
    if system is None:
        return pd.DataFrame()

    orbit_by_id = {
        str(orbit["orbit_id"]): orbit
        for orbit in system.get("orbits", [])
    }
    rows: list[dict[str, object]] = []
    for satellite in system.get("satellites", []):
        orbit = orbit_by_id.get(str(satellite["orbit_id"]), {})
        rows.append(
            {
                "Slot": satellite["satellite_id"],
                "Grupa": "SAR" if str(satellite["satellite_id"]).startswith("SAR") else "EO",
                "Faza [°]": satellite["phase_angle_deg"],
                "Wysokość scenariusza [km]": orbit.get("altitude_km"),
                "Inklinacja scenariusza [°]": orbit.get("inclination_deg"),
                "RAAN scenariusza [°]": orbit.get("raan_deg"),
            }
        )
    return pd.DataFrame(rows)


def _source_table() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for profile in (ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE):
        for source in profile.parameter_sources:
            rows.append(
                {
                    "Profil": profile.name,
                    "Grupa parametrów": source.parameter_group,
                    "Pochodzenie": source.origin.value,
                    "Źródło / odniesienie": source.reference,
                    "Uwagi": source.notes or "—",
                }
            )
    return pd.DataFrame(rows)


def render_system_overview_page() -> None:
    """Wyjaśnia model konstelacji, parametry i geometrię systemu."""

    render_page_header(
        "System i satelity",
        "Techniczny przewodnik po profilach ICEYE i Pléiades Neo, "
        "fazowaniu konstelacji demonstracyjnej, geometrii akwizycji oraz "
        "rozdzieleniu parametrów nominalnych od aktualnych elementów OMM.",
        eyebrow="Model systemu",
        badges=("4 SAR + 2 EO", "SSO/LEO", "OMM + SGP4", "Geometria"),
    )

    summary = st.columns(4)
    summary[0].metric("Sloty satelitarne", "6")
    summary[1].metric("Satelity SAR", "4")
    summary[2].metric("Satelity EO", "2")
    summary[3].metric("Źródło stanu orbity", "OMM + SGP4")

    tabs = st.tabs(
        [
            "Konstelacja i fazowanie",
            "Parametry nominalne",
            "Geometria akwizycji",
            "Przepływ danych",
            "Źródła i interpretacja",
        ]
    )

    with tabs[0]:
        render_section_header(
            "Fazowanie scenariusza POLAND_DEMO",
            "Kąty fazowe definiują kontrolowany model testowy. Nie są próbą "
            "odtworzenia pełnej, rzeczywistej geometrii komercyjnych konstelacji.",
        )
        phasing = _phasing_table()
        if phasing.empty:
            st.warning("Nie znaleziono katalogu scenariusza POLAND_DEMO.")
            render_constellation_phasing_visual()
        else:
            render_constellation_phasing_visual(
                phasing.to_dict(orient="records"),
            )

        explanation = st.columns(3)
        with explanation[0].container(border=True):
            st.markdown("#### Stała separacja")
            st.write(
                "Sloty SAR zachowują odstęp 90°, a EO 180°. Animacja obraca "
                "cały układ bez zmiany wzajemnego fazowania."
            )
        with explanation[1].container(border=True):
            st.markdown("#### Znaczenie planistyczne")
            st.write(
                "Równomierny rozkład ogranicza skupianie przelotów i zwiększa "
                "liczbę alternatywnych okien dla schedulera."
            )
        with explanation[2].container(border=True):
            st.markdown("#### Ważne rozróżnienie")
            st.write(
                "To konfiguracja scenariusza testowego. Bieżące pozycje "
                "publicznych jednostek pochodzą z OMM i SGP4."
            )

        with st.expander("Tabela parametrów fazowania", expanded=False):
            if not phasing.empty:
                st.dataframe(phasing, width="stretch", hide_index=True)

    with tabs[1]:
        render_section_header(
            "Parametry profili publicznych",
            "Tabele są budowane bezpośrednio z app/catalogs, więc nie dublują "
            "ręcznie utrzymywanych wartości.",
        )
        st.dataframe(
            _nominal_orbit_table(),
            width="stretch",
            hide_index=True,
        )
        st.dataframe(
            _sensor_table(),
            width="stretch",
            hide_index=True,
        )

        sar_tab, eo_tab = st.tabs(["Tryby ICEYE SAR", "Tryby Pléiades Neo EO"])
        with sar_tab:
            st.dataframe(
                _mode_table(ICEYE_PUBLIC_PROFILE),
                width="stretch",
                hide_index=True,
                height=390,
            )
        with eo_tab:
            st.dataframe(
                _mode_table(PLEIADES_NEO_PUBLIC_PROFILE),
                width="stretch",
                hide_index=True,
            )

        st.info(
            "Wysokość, inklinacja i parametry sensora są nominalnym opisem "
            "misji. RAAN, epoka, mimośród i bieżąca pozycja każdej jednostki "
            "pochodzą z OMM i są prezentowane w module „Orbity i dane OMM”."
        )

    with tabs[2]:
        render_section_header(
            "Geometria obserwacji",
            "Okno geometryczne nie oznacza jeszcze wykonalnej akwizycji. "
            "Kandydat przechodzi później filtry sensora i ograniczenia operacyjne.",
        )
        _render_svg(
            "acquisition_geometry.svg",
            "Off-nadir opisuje odchylenie linii obserwacji od kierunku nadiru. "
            "W modelu publicznym limit wynosi 45° dla ICEYE i 52° dla Pléiades Neo.",
        )
        _render_svg(
            "pass_geometry.svg",
            "Mapa nieba wykorzystuje lokalny układ obserwatora i pokazuje AOS, "
            "maksymalną elewację oraz LOS.",
        )

    with tabs[3]:
        render_section_header(
            "Warstwy orbitalne i planistyczne",
            "Ten sam stan SGP4 zasila śledzenie, okna dostępu oraz wejście do "
            "algorytmów Greedy, CP-SAT i Hybrid.",
        )
        _render_svg(
            "orbit_data_layers.svg",
            "Profil nominalny odpowiada za interpretację misji, natomiast OMM "
            "i SGP4 za stan dynamiczny.",
        )
        _render_svg(
            "planning_pipeline.svg",
            "Pełny przepływ od AOI do harmonogramu, raportów i przeplanowania.",
        )

    with tabs[4]:
        render_section_header(
            "Pochodzenie parametrów",
            "Każda grupa wartości jest oznaczona jako publiczna, modelowo "
            "wyprowadzona albo pochodząca z publicznych danych orbitalnych.",
        )
        st.dataframe(
            _source_table(),
            width="stretch",
            hide_index=True,
            height=420,
        )

        with st.container(border=True):
            st.markdown("### Zasady interpretacji")
            st.markdown(
                "- **PUBLIC_DATA** — wartość zaczerpnięta z jawnej dokumentacji;\n"
                "- **MODEL_DERIVED** — jawne założenie lub wartość pomocnicza "
                "wyprowadzona na potrzeby optymalizacji;\n"
                "- **PUBLIC_ORBIT_DATA** — elementy GP/OMM pobierane z CelesTrak;\n"
                "- scenariusz `POLAND_DEMO` jest kontrolowanym środowiskiem "
                "badawczym, a nie deklaracją konfiguracji operatora."
            )

        st.markdown(
            "Pełne omówienie wraz z diagramami znajduje się w "
            "`docs/satellite_system.md`."
        )


__all__ = ["render_system_overview_page"]
