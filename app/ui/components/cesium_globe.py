from __future__ import annotations

import json

import streamlit.components.v1 as components

from app.visualization import CesiumScene


CESIUM_VERSION = "1.130.0"
CESIUM_BASE_URL = f"https://cdn.jsdelivr.net/npm/cesium@{CESIUM_VERSION}/Build/Cesium/"


def build_cesium_html(
    scene: CesiumScene,
    *,
    height_px: int = 820,
) -> str:
    """Tworzy samodzielny dokument HTML z globusem CesiumJS."""

    if height_px < 480:
        raise ValueError("Widok Cesium powinien mieć co najmniej 480 px wysokości")

    czml_json = scene.to_json(indent=None).replace("</", "<\\/")
    metadata_json = json.dumps(
        {
            "satellites": scene.satellite_count,
            "requests": scene.request_count,
            "access": scene.access_window_count,
            "schedule": scene.scheduled_acquisition_count,
        }
    )
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="{CESIUM_BASE_URL}Widgets/widgets.css" />
  <script>window.CESIUM_BASE_URL = {json.dumps(CESIUM_BASE_URL)};</script>
  <script src="{CESIUM_BASE_URL}Cesium.js"></script>
  <style>
    html, body, #cesiumContainer {{
      width: 100%; height: 100%; margin: 0; overflow: hidden;
      background: #030712; font-family: Inter, system-ui, sans-serif;
    }}
    #cesiumContainer {{ height: {height_px}px; }}
    .legend {{
      position: absolute; z-index: 10; top: 14px; left: 14px;
      min-width: 270px; padding: 13px 15px; border-radius: 12px;
      color: #f8fafc; background: rgba(5, 12, 24, 0.9);
      border: 1px solid rgba(148, 163, 184, 0.35);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.38);
      font-size: 15px; line-height: 1.35; backdrop-filter: blur(8px);
    }}
    .legend strong {{ display: block; font-size: 17px; margin-bottom: 8px; }}
    .legend-row {{ display: flex; align-items: center; gap: 9px; margin: 6px 0; }}
    .swatch {{ width: 23px; height: 5px; border-radius: 99px; flex: 0 0 auto; }}
    .swatch.ground {{ height: 3px; border-top: 2px dashed rgba(255,255,255,.8); background: transparent; }}
    .dot {{ width: 12px; height: 12px; border-radius: 50%; flex: 0 0 auto; }}
    .meta {{ color: #cbd5e1; margin-top: 9px; font-size: 13px; }}
    .status {{
      display: inline-flex; margin-top: 8px; padding: 4px 8px; border-radius: 999px;
      color: #bfdbfe; background: rgba(30, 64, 175, 0.25);
      border: 1px solid rgba(96, 165, 250, 0.35); font-size: 12px;
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .actions button {{
      border: 1px solid rgba(148, 163, 184, 0.38); border-radius: 8px;
      background: #111c2e; color: #f8fafc; padding: 8px 11px;
      font: 650 13px system-ui, sans-serif; cursor: pointer;
    }}
    .actions button:hover {{ background: #1e293b; }}
    #errorBanner {{
      display: none; position: absolute; z-index: 20; inset: 16px 16px auto 16px;
      padding: 14px 16px; border-radius: 10px; background: #7f1d1d;
      color: white; font-size: 15px; line-height: 1.45;
    }}
    .cesium-viewer-toolbar {{ top: 12px; right: 12px; }}
    .cesium-button {{ width: 38px; height: 38px; }}
    .cesium-viewer-timelineContainer {{ right: 0; }}
    .cesium-infoBox {{ max-width: 540px; }}
    .cesium-infoBox-title {{ font-size: 18px; }}
    .cesium-widget-credits {{ font-size: 10px; }}
  </style>
</head>
<body>
  <div id="cesiumContainer"></div>
  <div id="errorBanner"></div>
  <div class="legend">
    <strong>Globus operacyjny 3D</strong>
    <div class="legend-row"><span class="swatch" style="background:#ff636a"></span>ICEYE SAR — satelita/orbita</div>
    <div class="legend-row"><span class="swatch" style="background:#50a9ff"></span>Pléiades Neo EO — satelita/orbita</div>
    <div class="legend-row"><span class="swatch ground"></span>Ground track na powierzchni</div>
    <div class="legend-row"><span class="dot" style="background:#facc15"></span>AOI / zlecenie</div>
    <div class="legend-row"><span class="swatch" style="background:#f59e0b"></span>Okno dostępu / footprint</div>
    <div class="legend-row"><span class="swatch" style="background:#34d399;height:7px"></span>Zaplanowana akwizycja</div>
    <div class="meta" id="sceneMeta"></div>
    <div class="status" id="mapStatus">Ziemia: elipsoida awaryjna</div>
    <div class="actions">
      <button id="earthButton" type="button">Pokaż Ziemię</button>
      <button id="sceneButton" type="button">Cała scena</button>
      <button id="playButton" type="button">Pauza</button>
    </div>
  </div>
  <script>
    const czml = {czml_json};
    const metadata = {metadata_json};
    const errorBanner = document.getElementById("errorBanner");
    const mapStatus = document.getElementById("mapStatus");
    function showError(message) {{
      errorBanner.style.display = "block";
      errorBanner.textContent = message;
    }}
    document.getElementById("sceneMeta").textContent =
      `${{metadata.satellites}} sat. · ${{metadata.requests}} AOI · ` +
      `${{metadata.access}} okien · ${{metadata.schedule}} akwizycji`;

    try {{
      if (typeof Cesium === "undefined") {{
        throw new Error("Nie udało się wczytać CesiumJS. Sprawdź połączenie z CDN.");
      }}

      const viewer = new Cesium.Viewer("cesiumContainer", {{
        animation: false,
        timeline: true,
        baseLayerPicker: false,
        baseLayer: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: true,
        navigationHelpButton: false,
        fullscreenButton: true,
        infoBox: true,
        selectionIndicator: true,
        shouldAnimate: true,
        terrainProvider: new Cesium.EllipsoidTerrainProvider()
      }});

      const globe = viewer.scene.globe;
      globe.show = true;
      globe.baseColor = Cesium.Color.fromCssColorString("#1d5f7a");
      globe.undergroundColor = Cesium.Color.fromCssColorString("#0b2636");
      globe.enableLighting = false;
      globe.showGroundAtmosphere = true;
      globe.depthTestAgainstTerrain = true;
      globe.maximumScreenSpaceError = 2;
      viewer.scene.skyAtmosphere.show = true;
      viewer.scene.highDynamicRange = true;
      viewer.scene.logarithmicDepthBuffer = true;
      viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#030712");
      viewer.scene.screenSpaceCameraController.minimumZoomDistance = 800000;
      viewer.scene.screenSpaceCameraController.maximumZoomDistance = 80000000;
      viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.6);

      function showEarth(duration = 1.2) {{
        viewer.camera.flyTo({{
          destination: Cesium.Cartesian3.fromDegrees(19.0, 51.5, 18500000.0),
          orientation: {{
            heading: 0.0,
            pitch: Cesium.Math.toRadians(-90.0),
            roll: 0.0
          }},
          duration
        }});
      }}

      function addMapLayer() {{
        try {{
          const provider = new Cesium.OpenStreetMapImageryProvider({{
            url: "https://tile.openstreetmap.org/"
          }});
          provider.errorEvent.addEventListener((error) => {{
            mapStatus.textContent = "Ziemia: elipsoida awaryjna (błąd kafelków)";
            console.warn("OSM imagery error", error);
          }});
          const layer = viewer.imageryLayers.addImageryProvider(provider);
          layer.alpha = 0.95;
          mapStatus.textContent = "Ziemia: OpenStreetMap + elipsoida awaryjna";
        }} catch (error) {{
          mapStatus.textContent = "Ziemia: elipsoida awaryjna";
          console.warn("Nie udało się dodać OSM", error);
        }}
      }}
      addMapLayer();

      Cesium.CzmlDataSource.load(czml)
        .then((dataSource) => {{
          viewer.dataSources.add(dataSource);
          viewer.clockTrackedDataSource = dataSource;
          viewer.clock.shouldAnimate = true;
          showEarth(0.0);
        }})
        .catch((error) => showError(`Błąd ładowania CZML: ${{error.message || error}}`));

      document.getElementById("earthButton").addEventListener("click", () => {{
        showEarth();
      }});
      document.getElementById("sceneButton").addEventListener("click", () => {{
        const dataSource = viewer.dataSources.get(0);
        if (dataSource) viewer.flyTo(dataSource.entities, {{ duration: 1.5 }});
      }});
      document.getElementById("playButton").addEventListener("click", (event) => {{
        viewer.clock.shouldAnimate = !viewer.clock.shouldAnimate;
        event.currentTarget.textContent = viewer.clock.shouldAnimate ? "Pauza" : "Odtwórz";
      }});
    }} catch (error) {{
      showError(error.message || String(error));
    }}
  </script>
</body>
</html>"""


def render_cesium_globe(
    scene: CesiumScene,
    *,
    height_px: int = 820,
) -> None:
    """Osadza globus CesiumJS w aplikacji Streamlit."""

    components.html(
        build_cesium_html(scene, height_px=height_px),
        height=height_px + 4,
        scrolling=False,
    )
