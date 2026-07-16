from __future__ import annotations

import json
from typing import Any

import streamlit as st

from app.models.geometry import PointGeometry, TargetGeometry
from app.geospatial.aoi import (
    geometry_centroid,
    target_geometry_from_geojson,
    target_geometry_to_feature,
)


def _map_dependencies():
    import folium
    from folium.plugins import Draw
    from streamlit_folium import st_folium

    return folium, Draw, st_folium


def _map_for_geometry(geometry: TargetGeometry | None):
    folium, Draw, _st_folium = _map_dependencies()

    if geometry is None:
        center = [52.0, 19.0]
        zoom = 5
    else:
        longitude, latitude = geometry_centroid(geometry)
        center = [latitude, longitude]
        zoom = 11 if isinstance(geometry, PointGeometry) else 8

    map_object = folium.Map(
        location=center,
        zoom_start=zoom,
        control_scale=True,
        tiles="OpenStreetMap",
    )

    folium.TileLayer(
        "CartoDB positron",
        name="Jasna mapa",
    ).add_to(map_object)

    if geometry is not None:
        folium.GeoJson(
            target_geometry_to_feature(geometry),
            name="Aktualny AOI",
            style_function=lambda _feature: {
                "color": "#1565c0",
                "weight": 3,
                "fillOpacity": 0.20,
            },
            marker=folium.CircleMarker(
                radius=8,
                color="#1565c0",
                fill=True,
            ),
        ).add_to(map_object)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": True,
            "polygon": True,
            "rectangle": True,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(map_object)
    folium.LayerControl(collapsed=True).add_to(map_object)
    return map_object


def _drawing_candidate(result: dict[str, Any]) -> dict[str, Any] | None:
    active = result.get("last_active_drawing")
    if isinstance(active, dict):
        return active

    drawings = result.get("all_drawings")
    if isinstance(drawings, list) and drawings:
        candidate = drawings[-1]
        if isinstance(candidate, dict):
            return candidate
    return None


def render_aoi_editor(*, key: str = "aoi") -> TargetGeometry | None:
    """Renderuje dwukierunkowy edytor Point/Polygon/Rectangle w WGS84."""

    state_key = f"{key}_geometry"
    geometry = st.session_state.get(state_key)

    st.subheader("Obszar zainteresowania")
    st.caption(
        "Narysuj punkt, prostokąt albo poligon. Prostokąt jest zapisywany "
        "jako Polygon GeoJSON. Współrzędne są przechowywane w WGS84."
    )

    map_object = _map_for_geometry(geometry)
    _folium, _Draw, st_folium = _map_dependencies()
    result = st_folium(
        map_object,
        height=560,
        use_container_width=True,
        returned_objects=[
            "last_active_drawing",
            "all_drawings",
            "last_clicked",
        ],
        key=f"{key}_map",
    )

    candidate = _drawing_candidate(result or {})
    if candidate is not None:
        try:
            parsed = target_geometry_from_geojson(candidate)
        except ValueError as error:
            st.warning(f"Nie można odczytać geometrii z mapy: {error}")
        else:
            if parsed != geometry:
                st.session_state[state_key] = parsed
                geometry = parsed

    with st.expander("Współrzędne ręczne i GeoJSON", expanded=False):
        point_col, geojson_col = st.columns(2)

        with point_col:
            default_lon = 21.0122
            default_lat = 52.2297
            if isinstance(geometry, PointGeometry):
                default_lon, default_lat = geometry.coordinates

            longitude = st.number_input(
                "Długość geograficzna",
                min_value=-180.0,
                max_value=180.0,
                value=float(default_lon),
                format="%.6f",
                key=f"{key}_longitude",
            )
            latitude = st.number_input(
                "Szerokość geograficzna",
                min_value=-90.0,
                max_value=90.0,
                value=float(default_lat),
                format="%.6f",
                key=f"{key}_latitude",
            )
            if st.button("Ustaw punkt", key=f"{key}_set_point"):
                st.session_state[state_key] = PointGeometry(
                    coordinates=(longitude, latitude)
                )
                st.rerun()

        with geojson_col:
            default_geojson = (
                json.dumps(
                    target_geometry_to_feature(geometry),
                    ensure_ascii=False,
                    indent=2,
                )
                if geometry is not None
                else ""
            )
            geojson_text = st.text_area(
                "GeoJSON",
                value=default_geojson,
                height=210,
                key=f"{key}_geojson_text",
            )
            uploaded = st.file_uploader(
                "Wczytaj .geojson lub .json",
                type=["geojson", "json"],
                key=f"{key}_geojson_upload",
            )
            if uploaded is not None:
                geojson_text = uploaded.getvalue().decode("utf-8")

            if st.button("Zastosuj GeoJSON", key=f"{key}_apply_geojson"):
                try:
                    payload = json.loads(geojson_text)
                    st.session_state[state_key] = target_geometry_from_geojson(
                        payload
                    )
                except (json.JSONDecodeError, ValueError) as error:
                    st.error(f"Niepoprawny GeoJSON: {error}")
                else:
                    st.rerun()

    controls = st.columns([1, 1, 3])
    if controls[0].button("Wyczyść AOI", key=f"{key}_clear"):
        st.session_state.pop(state_key, None)
        st.rerun()

    geometry = st.session_state.get(state_key)
    if geometry is None:
        st.info("Narysuj albo wprowadź geometrię, aby utworzyć zlecenie.")
        return None

    controls[1].download_button(
        "Pobierz GeoJSON",
        data=json.dumps(
            target_geometry_to_feature(geometry),
            ensure_ascii=False,
            indent=2,
        ),
        file_name="aoi.geojson",
        mime="application/geo+json",
        key=f"{key}_download",
    )

    geometry_type = geometry.type
    st.success(f"Aktywna geometria: {geometry_type}")
    return geometry
