"""Interaktywne wizualizacje techniczne strony systemu satelitarnego."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import json
from textwrap import dedent
from typing import TypedDict


class ConstellationSlot(TypedDict):
    slot: str
    group: str
    phase_deg: float
    altitude_km: float
    inclination_deg: float
    raan_deg: float


_DEFAULT_SLOTS: tuple[Mapping[str, object], ...] = (
    {
        "slot": "SAR-01",
        "group": "SAR",
        "phase_deg": 0.0,
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 10.0,
    },
    {
        "slot": "SAR-02",
        "group": "SAR",
        "phase_deg": 90.0,
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 10.0,
    },
    {
        "slot": "SAR-03",
        "group": "SAR",
        "phase_deg": 180.0,
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 10.0,
    },
    {
        "slot": "SAR-04",
        "group": "SAR",
        "phase_deg": 270.0,
        "altitude_km": 550.0,
        "inclination_deg": 97.6,
        "raan_deg": 10.0,
    },
    {
        "slot": "EO-01",
        "group": "EO",
        "phase_deg": 0.0,
        "altitude_km": 620.0,
        "inclination_deg": 97.9,
        "raan_deg": 25.0,
    },
    {
        "slot": "EO-02",
        "group": "EO",
        "phase_deg": 180.0,
        "altitude_km": 620.0,
        "inclination_deg": 97.9,
        "raan_deg": 25.0,
    },
)


def _coalesce(
    row: Mapping[str, object],
    *keys: str,
    default: object = None,
) -> object:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]

    return default


def _as_float(value: object) -> float:
    if isinstance(value, (int, float, str)):
        return float(value)

    raise TypeError(
        "Expected a numeric constellation slot value, "
        f"received {type(value).__name__}."
    )


def _normalise_slots(
    rows: Sequence[Mapping[str, object]] | None,
) -> list[ConstellationSlot]:
    source: Sequence[Mapping[str, object]] = (
        rows or _DEFAULT_SLOTS
    )
    normalised: list[ConstellationSlot] = []

    for row in source:
        slot = str(
            _coalesce(
                row,
                "slot",
                "Slot",
                "satellite_id",
                default="",
            )
        )

        if not slot:
            continue

        group = str(
            _coalesce(
                row,
                "group",
                "Grupa",
                default=(
                    "SAR"
                    if slot.upper().startswith("SAR")
                    else "EO"
                ),
            )
        ).upper()

        normalised.append(
            {
                "slot": slot,
                "group": group,
                "phase_deg": _as_float(
                    _coalesce(
                        row,
                        "phase_deg",
                        "Faza [°]",
                        "phase_angle_deg",
                        default=0.0,
                    )
                ),
                "altitude_km": _as_float(
                    _coalesce(
                        row,
                        "altitude_km",
                        "Wysokość scenariusza [km]",
                        default=0.0,
                    )
                ),
                "inclination_deg": _as_float(
                    _coalesce(
                        row,
                        "inclination_deg",
                        "Inklinacja scenariusza [°]",
                        default=0.0,
                    )
                ),
                "raan_deg": _as_float(
                    _coalesce(
                        row,
                        "raan_deg",
                        "RAAN scenariusza [°]",
                        default=0.0,
                    )
                ),
            }
        )

    return sorted(
        normalised,
        key=lambda item: (
            item["group"],
            item["phase_deg"],
        ),
    )


def _phase_cards(
    slots: Sequence[ConstellationSlot],
    group: str,
) -> str:
    cards: list[str] = []

    for slot in slots:
        if slot["group"] != group:
            continue

        slot_name = escape(slot["slot"])
        phase = slot["phase_deg"]
        short_id = escape(
            slot_name.split("-")[-1]
        )

        cards.append(
            f"""
            <button class="phase-card {group.lower()}" type="button"
                    data-card-slot="{slot_name}" aria-label="{slot_name}, faza {phase:.0f} stopni">
              <span class="phase-index">{short_id}</span>
              <span class="phase-copy"><strong>{slot_name}</strong><small>faza {phase:.0f}°</small></span>
            </button>
            """
        )

    return "".join(cards)


def _satellite_nodes(
    slots: Sequence[ConstellationSlot],
    group: str,
) -> str:
    nodes: list[str] = []

    for slot in slots:
        if slot["group"] != group:
            continue

        slot_name = escape(slot["slot"])
        short_id = escape(
            slot_name.split("-")[-1]
        )
        phase = slot["phase_deg"]
        altitude = slot["altitude_km"]
        inclination = slot["inclination_deg"]
        raan = slot["raan_deg"]

        nodes.append(
            f"""
            <g class="sat-node {group.lower()}" data-satellite="{slot_name}"
               data-group="{group}" data-phase="{phase:.6f}"
               data-altitude="{altitude:.1f}" data-inclination="{inclination:.1f}"
               data-raan="{raan:.1f}" tabindex="0" role="button"
               aria-label="{slot_name}, faza {phase:.0f} stopni">
              <circle class="sat-halo" r="27"></circle>
              <circle class="sat-core" r="18"></circle>
              <text class="sat-number" x="0" y="1">{short_id}</text>
              <title>{slot_name} · faza {phase:.0f}° · {altitude:.0f} km · i={inclination:.1f}°</title>
            </g>
            """
        )

    return "".join(nodes)


def build_constellation_phasing_html(
    rows: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Buduje samowystarczalny HTML animowanej wizualizacji fazowania."""

    slots = _normalise_slots(rows)
    payload = json.dumps(slots, ensure_ascii=False).replace("</", "<\\/")

    sar_slots = [slot for slot in slots if slot["group"] == "SAR"]
    eo_slots = [slot for slot in slots if slot["group"] == "EO"]
    sar_altitude = (
        sar_slots[0]["altitude_km"]
        if sar_slots
        else 0.0
    )
    sar_inclination = (
        sar_slots[0]["inclination_deg"]
        if sar_slots
        else 0.0
    )
    eo_altitude = (
        eo_slots[0]["altitude_km"]
        if eo_slots
        else 0.0
    )
    eo_inclination = (
        eo_slots[0]["inclination_deg"]
        if eo_slots
        else 0.0
    )

    return dedent(
        f"""
        <!doctype html>
        <html lang="pl">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <style>
            :root {{
              color-scheme: dark;
              --bg: #070b12;
              --panel: #0e1727;
              --panel-strong: #111d30;
              --panel-soft: #17253a;
              --border: rgba(130, 157, 190, 0.28);
              --border-soft: rgba(130, 157, 190, 0.16);
              --text: #f7f9fc;
              --muted: #9fb0c6;
              --muted-2: #73869f;
              --sar: #ff636a;
              --sar-soft: rgba(255, 99, 106, 0.16);
              --eo: #50a9ff;
              --eo-soft: rgba(80, 169, 255, 0.16);
              --green: #3dd8a0;
              --shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
            }}

            * {{ box-sizing: border-box; }}
            html, body {{
              margin: 0;
              min-height: 100%;
              background: transparent;
              color: var(--text);
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
                           "Segoe UI", sans-serif;
            }}
            button {{ font: inherit; }}

            .shell {{
              width: 100%;
              overflow: hidden;
              border: 1px solid var(--border);
              border-radius: 22px;
              background:
                radial-gradient(circle at 13% 0%, rgba(80, 169, 255, 0.10), transparent 34%),
                radial-gradient(circle at 92% 10%, rgba(255, 99, 106, 0.08), transparent 32%),
                linear-gradient(145deg, #080d16, #060a11 68%);
              box-shadow: var(--shadow);
            }}

            .topbar {{
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              gap: 24px;
              padding: 22px 24px 19px;
              border-bottom: 1px solid var(--border-soft);
            }}
            .kicker {{
              margin-bottom: 7px;
              color: var(--eo);
              font-size: 11px;
              font-weight: 800;
              letter-spacing: 0.13em;
              text-transform: uppercase;
            }}
            h2 {{ margin: 0; font-size: 25px; line-height: 1.18; letter-spacing: -0.02em; }}
            .lead {{ margin: 7px 0 0; max-width: 760px; color: var(--muted); font-size: 13px; line-height: 1.55; }}

            .controls {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
            .control-button, .speed-button {{
              min-height: 36px;
              border: 1px solid var(--border);
              border-radius: 10px;
              background: rgba(20, 33, 53, 0.86);
              color: var(--text);
              cursor: pointer;
              transition: transform .16s ease, border-color .16s ease, background .16s ease;
            }}
            .control-button {{ padding: 0 13px; font-weight: 720; }}
            .speed-group {{ display: inline-flex; padding: 3px; border: 1px solid var(--border-soft); border-radius: 11px; background: rgba(7, 12, 20, .74); }}
            .speed-button {{ min-width: 39px; min-height: 29px; border: 0; border-radius: 8px; background: transparent; color: var(--muted); font-size: 12px; font-weight: 760; }}
            .speed-button.active {{ background: var(--panel-soft); color: var(--text); box-shadow: inset 0 0 0 1px var(--border); }}
            .control-button:hover, .speed-button:hover {{ transform: translateY(-1px); border-color: rgba(132, 188, 255, .55); }}
            .control-button:focus-visible, .speed-button:focus-visible, .phase-card:focus-visible {{ outline: 2px solid var(--eo); outline-offset: 2px; }}

            .grid {{
              display: grid;
              grid-template-columns: minmax(0, 1.55fr) minmax(330px, .95fr);
              gap: 16px;
              padding: 16px;
            }}
            .orbit-card {{
              min-width: 0;
              overflow: hidden;
              border: 1px solid var(--border);
              border-radius: 18px;
              background: linear-gradient(160deg, rgba(17, 29, 48, .98), rgba(10, 18, 31, .98));
            }}
            .card-head {{
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              gap: 16px;
              padding: 17px 18px 10px;
            }}
            .card-title-row {{ display: flex; align-items: center; gap: 9px; }}
            .group-badge {{
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-width: 43px;
              height: 25px;
              border-radius: 999px;
              font-size: 11px;
              font-weight: 850;
              letter-spacing: .08em;
            }}
            .group-badge.sar {{ color: #ff9aa0; background: var(--sar-soft); border: 1px solid rgba(255,99,106,.32); }}
            .group-badge.eo {{ color: #9bd0ff; background: var(--eo-soft); border: 1px solid rgba(80,169,255,.32); }}
            .card-head h3 {{ margin: 0; font-size: 17px; line-height: 1.3; }}
            .card-subtitle {{ margin: 5px 0 0; color: var(--muted); font-size: 12px; }}
            .metric-pills {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
            .metric-pill {{
              padding: 6px 8px;
              border: 1px solid var(--border-soft);
              border-radius: 9px;
              background: rgba(7, 12, 20, .58);
              color: var(--muted);
              font-size: 10.5px;
              white-space: nowrap;
            }}
            .metric-pill strong {{ color: var(--text); font-weight: 760; }}

            .orbit-stage {{ position: relative; margin: 0 12px; border-radius: 15px; overflow: hidden; background: radial-gradient(circle at 50% 48%, rgba(36, 81, 125, .17), transparent 44%); }}
            .orbit-stage.sar {{ height: 335px; }}
            .orbit-stage.eo {{ height: 335px; }}
            .orbit-stage svg {{ display: block; width: 100%; height: 100%; }}
            .grid-line {{ fill: none; stroke: rgba(115, 142, 176, .16); stroke-width: 1; stroke-dasharray: 6 9; }}
            .orbit-line {{ fill: none; stroke-width: 2.1; }}
            .orbit-line.sar {{ stroke: rgba(255, 99, 106, .68); }}
            .orbit-line.eo {{ stroke: rgba(80, 169, 255, .76); }}
            .orbit-ghost {{ fill: none; stroke: rgba(120, 151, 189, .28); stroke-width: 1.2; stroke-dasharray: 8 10; }}
            .earth-ring {{ fill: rgba(80,169,255,.08); stroke: rgba(118,178,226,.38); stroke-width: 2; }}
            .earth {{ fill: url(#earthGradient); stroke: rgba(112, 180, 230, .72); stroke-width: 2; }}
            .land {{ fill: rgba(61, 216, 160, .56); }}
            .direction {{ fill: none; stroke-width: 2.3; stroke-linecap: round; }}
            .direction.sar {{ stroke: rgba(255,99,106,.82); marker-end: url(#arrowSar); }}
            .direction.eo {{ stroke: rgba(80,169,255,.86); marker-end: url(#arrowEo); }}

            .sat-node {{ cursor: pointer; transition: opacity .18s ease; }}
            .sat-halo {{ opacity: .18; transition: opacity .18s ease, r .18s ease; }}
            .sat-node.sar .sat-halo {{ fill: var(--sar); }}
            .sat-node.eo .sat-halo {{ fill: var(--eo); }}
            .sat-core {{ stroke-width: 2; transition: filter .18s ease, r .18s ease; }}
            .sat-node.sar .sat-core {{ fill: var(--sar); stroke: #ffb0b4; }}
            .sat-node.eo .sat-core {{ fill: var(--eo); stroke: #b8ddff; }}
            .sat-number {{
              fill: #07101c;
              font-size: 10px;
              font-weight: 900;
              text-anchor: middle;
              dominant-baseline: middle;
              pointer-events: none;
            }}
            .sat-node:hover .sat-halo, .sat-node.active .sat-halo, .sat-node:focus .sat-halo {{ opacity: .38; r: 32px; }}
            .sat-node:hover .sat-core, .sat-node.active .sat-core, .sat-node:focus .sat-core {{ r: 20px; filter: drop-shadow(0 0 7px currentColor); }}

            .orbit-label {{
              position: absolute;
              left: 14px;
              bottom: 12px;
              display: inline-flex;
              align-items: center;
              gap: 7px;
              padding: 6px 9px;
              border: 1px solid var(--border-soft);
              border-radius: 9px;
              background: rgba(5, 10, 17, .72);
              color: var(--muted);
              font-size: 10.5px;
              backdrop-filter: blur(8px);
            }}
            .pulse-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 0 4px rgba(61,216,160,.10); }}

            .phase-grid {{ display: grid; gap: 7px; padding: 11px 12px 13px; }}
            .phase-grid.sar {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
            .phase-grid.eo {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .phase-card {{
              display: flex;
              align-items: center;
              gap: 8px;
              width: 100%;
              min-width: 0;
              padding: 8px;
              border: 1px solid var(--border-soft);
              border-radius: 11px;
              background: rgba(7, 12, 20, .52);
              color: var(--text);
              text-align: left;
              cursor: pointer;
              transition: background .16s ease, border-color .16s ease, transform .16s ease;
            }}
            .phase-card:hover, .phase-card.active {{ transform: translateY(-1px); background: var(--panel-soft); }}
            .phase-card.sar:hover, .phase-card.sar.active {{ border-color: rgba(255,99,106,.56); }}
            .phase-card.eo:hover, .phase-card.eo.active {{ border-color: rgba(80,169,255,.56); }}
            .phase-index {{
              display: grid;
              place-items: center;
              flex: 0 0 27px;
              width: 27px;
              height: 27px;
              border-radius: 9px;
              font-size: 10px;
              font-weight: 900;
            }}
            .phase-card.sar .phase-index {{ background: var(--sar-soft); color: #ff9ca1; }}
            .phase-card.eo .phase-index {{ background: var(--eo-soft); color: #a9d6ff; }}
            .phase-copy {{ display: flex; flex-direction: column; min-width: 0; line-height: 1.15; }}
            .phase-copy strong {{ overflow: hidden; text-overflow: ellipsis; font-size: 10.5px; white-space: nowrap; }}
            .phase-copy small {{ margin-top: 3px; color: var(--muted-2); font-size: 9.5px; }}

            .benefits {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; padding: 0 12px 13px; }}
            .benefit {{ padding: 10px; border: 1px solid var(--border-soft); border-radius: 11px; background: rgba(7, 12, 20, .45); }}
            .benefit strong {{ display: block; margin-bottom: 4px; font-size: 10.5px; }}
            .benefit span {{ color: var(--muted); font-size: 9.5px; line-height: 1.35; }}

            .footer {{
              display: grid;
              grid-template-columns: minmax(0, 1fr) minmax(260px, .42fr);
              gap: 12px;
              padding: 0 16px 16px;
            }}
            .note, .selection {{
              min-width: 0;
              border: 1px solid var(--border);
              border-radius: 14px;
              background: rgba(15, 25, 41, .76);
              padding: 12px 14px;
            }}
            .note {{ display: flex; align-items: center; gap: 11px; }}
            .note-icon {{ display: grid; place-items: center; flex: 0 0 34px; width: 34px; height: 34px; border-radius: 11px; background: rgba(61,216,160,.12); color: var(--green); font-weight: 900; }}
            .note strong, .selection strong {{ display: block; font-size: 11px; }}
            .note span, .selection span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 10px; line-height: 1.45; }}
            .selection {{ border-color: rgba(80,169,255,.28); }}
            .selection-meta {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }}
            .selection-meta b {{ padding: 4px 6px; border-radius: 7px; background: rgba(80,169,255,.10); color: #b9dcff; font-size: 9px; font-weight: 750; }}

            @media (max-width: 980px) {{
              .grid {{ grid-template-columns: 1fr; }}
              .orbit-stage.sar, .orbit-stage.eo {{ height: 330px; }}
              .footer {{ grid-template-columns: 1fr; }}
            }}
            @media (max-width: 620px) {{
              .topbar {{ flex-direction: column; }}
              .controls {{ justify-content: flex-start; }}
              .phase-grid.sar {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
              .benefits {{ grid-template-columns: 1fr; }}
              .metric-pills {{ display: none; }}
            }}
            @media (prefers-reduced-motion: reduce) {{
              *, *::before, *::after {{ scroll-behavior: auto !important; transition-duration: .01ms !important; }}
            }}
          </style>
        </head>
        <body>
          <main class="shell">
            <header class="topbar">
              <div>
                <div class="kicker">POLAND_DEMO · MODEL REFERENCYJNY</div>
                <h2>Konstelacja demonstracyjna i fazowanie</h2>
                <p class="lead">Animacja pokazuje zachowanie stałej separacji fazowej. Numery poruszają się po orbitach, natomiast wartości 0°/90°/180°/270° opisują konfigurację początkową scenariusza.</p>
              </div>
              <div class="controls" aria-label="Sterowanie animacją">
                <button class="control-button" id="toggleMotion" type="button">⏸ Wstrzymaj</button>
                <div class="speed-group" role="group" aria-label="Prędkość animacji">
                  <button class="speed-button active" type="button" data-speed="1">1×</button>
                  <button class="speed-button" type="button" data-speed="2">2×</button>
                  <button class="speed-button" type="button" data-speed="4">4×</button>
                </div>
              </div>
            </header>

            <section class="grid">
              <article class="orbit-card">
                <div class="card-head">
                  <div>
                    <div class="card-title-row"><span class="group-badge sar">SAR</span><h3>4 sloty · separacja 90°</h3></div>
                    <p class="card-subtitle">Równomierny rozkład kandydatów do akwizycji w modelu testowym.</p>
                  </div>
                  <div class="metric-pills">
                    <span class="metric-pill"><strong>{sar_altitude:.0f} km</strong> wysokość</span>
                    <span class="metric-pill"><strong>{sar_inclination:.1f}°</strong> inklinacja</span>
                  </div>
                </div>
                <div class="orbit-stage sar">
                  <svg viewBox="0 0 720 360" role="img" aria-label="Animowana orbita czterech slotów SAR">
                    <defs>
                      <radialGradient id="earthGradient" cx="38%" cy="32%"><stop offset="0" stop-color="#367fb7"/><stop offset=".72" stop-color="#17446f"/><stop offset="1" stop-color="#0b2541"/></radialGradient>
                      <marker id="arrowSar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L0 6 L7 3Z" fill="#ff636a"/></marker>
                    </defs>
                    <ellipse class="grid-line" cx="360" cy="180" rx="300" ry="132"></ellipse>
                    <ellipse class="orbit-ghost" cx="360" cy="180" rx="265" ry="113"></ellipse>
                    <ellipse class="orbit-line sar" cx="360" cy="180" rx="300" ry="132"></ellipse>
                    <path class="direction sar" d="M560 82 C616 112 648 146 654 181"></path>
                    <circle class="earth-ring" cx="360" cy="180" r="78"></circle>
                    <circle class="earth" cx="360" cy="180" r="62"></circle>
                    <path class="land" d="M321 153 C337 129 373 125 397 143 C419 160 417 197 395 218 C370 240 332 229 316 204 C305 187 308 169 321 153Z"></path>
                    {_satellite_nodes(slots, "SAR")}
                  </svg>
                  <div class="orbit-label"><span class="pulse-dot"></span> fazowanie zachowywane podczas animacji</div>
                </div>
                <div class="phase-grid sar">{_phase_cards(slots, "SAR")}</div>
                <div class="benefits">
                  <div class="benefit"><strong>Równomierna separacja</strong><span>Każdy slot jest odsunięty o 90°.</span></div>
                  <div class="benefit"><strong>Większa częstotliwość</strong><span>Więcej kandydatów w różnych porach.</span></div>
                  <div class="benefit"><strong>Elastyczny scheduler</strong><span>Łatwiejsze omijanie konfliktów.</span></div>
                </div>
              </article>

              <article class="orbit-card">
                <div class="card-head">
                  <div>
                    <div class="card-title-row"><span class="group-badge eo">EO</span><h3>2 sloty · separacja 180°</h3></div>
                    <p class="card-subtitle">Dwie jednostki pozostają po przeciwnych stronach orbity modelowej.</p>
                  </div>
                  <div class="metric-pills">
                    <span class="metric-pill"><strong>{eo_altitude:.0f} km</strong> wysokość</span>
                    <span class="metric-pill"><strong>{eo_inclination:.1f}°</strong> inklinacja</span>
                  </div>
                </div>
                <div class="orbit-stage eo">
                  <svg viewBox="0 0 430 360" role="img" aria-label="Animowana orbita dwóch slotów EO">
                    <defs>
                      <radialGradient id="earthGradientEo" cx="38%" cy="32%"><stop offset="0" stop-color="#367fb7"/><stop offset=".72" stop-color="#17446f"/><stop offset="1" stop-color="#0b2541"/></radialGradient>
                      <marker id="arrowEo" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L0 6 L7 3Z" fill="#50a9ff"/></marker>
                    </defs>
                    <ellipse class="grid-line" cx="215" cy="180" rx="112" ry="143"></ellipse>
                    <ellipse class="orbit-ghost" cx="215" cy="180" rx="88" ry="116"></ellipse>
                    <ellipse class="orbit-line eo" cx="215" cy="180" rx="112" ry="143"></ellipse>
                    <path class="direction eo" d="M285 66 C320 98 334 135 330 178"></path>
                    <circle class="earth-ring" cx="215" cy="180" r="70"></circle>
                    <circle cx="215" cy="180" r="56" fill="url(#earthGradientEo)" stroke="rgba(112,180,230,.72)" stroke-width="2"></circle>
                    {_satellite_nodes(slots, "EO")}
                  </svg>
                  <div class="orbit-label"><span class="pulse-dot"></span> dwa równoważne sloty obserwacyjne</div>
                </div>
                <div class="phase-grid eo">{_phase_cards(slots, "EO")}</div>
                <div class="benefits">
                  <div class="benefit"><strong>Lepszy rozkład czasu</strong><span>Mniej skupionych przelotów.</span></div>
                  <div class="benefit"><strong>Więcej alternatyw</strong><span>Scheduler ma większy wybór okien.</span></div>
                  <div class="benefit"><strong>Odporność planu</strong><span>Łatwiejsze przeplanowanie.</span></div>
                </div>
              </article>
            </section>

            <footer class="footer">
              <div class="note">
                <span class="note-icon">i</span>
                <div><strong>Model scenariusza ≠ aktualna pozycja satelity</strong><span>Fazy powyżej są założeniem `POLAND_DEMO`. Bieżące położenie jednostek publicznych wyznaczają aktualne OMM i propagacja SGP4.</span></div>
              </div>
              <div class="selection" id="selectionPanel" aria-live="polite">
                <strong>Najedź na slot</strong>
                <span>Zobacz fazę i parametry jego orbity scenariuszowej.</span>
              </div>
            </footer>
          </main>

          <script type="application/json" id="slotData">{payload}</script>
          <script>
            (() => {{
              const slots = JSON.parse(document.getElementById('slotData').textContent);
              const nodes = [...document.querySelectorAll('[data-satellite]')];
              const cards = [...document.querySelectorAll('[data-card-slot]')];
              const selection = document.getElementById('selectionPanel');
              const toggle = document.getElementById('toggleMotion');
              const speedButtons = [...document.querySelectorAll('[data-speed]')];
              const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

              let running = !reducedMotion;
              let speed = 1;
              let elapsed = 0;
              let lastFrame = performance.now();

              const orbit = {{
                SAR: {{cx: 360, cy: 180, rx: 300, ry: 132, period: 36000}},
                EO: {{cx: 215, cy: 180, rx: 112, ry: 143, period: 30000}}
              }};

              function updateButton() {{
                toggle.textContent = running ? '⏸ Wstrzymaj' : '▶ Uruchom';
                toggle.setAttribute('aria-pressed', String(!running));
              }}

              function positionNodes() {{
                nodes.forEach((node) => {{
                  const group = node.dataset.group;
                  const geometry = orbit[group];
                  const phase = Number(node.dataset.phase || 0) * Math.PI / 180;
                  const angle = (elapsed / geometry.period) * Math.PI * 2 + phase - Math.PI / 2;
                  const x = geometry.cx + geometry.rx * Math.cos(angle);
                  const y = geometry.cy + geometry.ry * Math.sin(angle);
                  node.setAttribute('transform', `translate(${{x.toFixed(2)}} ${{y.toFixed(2)}})`);
                }});
              }}

              function frame(now) {{
                const delta = Math.min(now - lastFrame, 80);
                lastFrame = now;
                if (running) elapsed += delta * speed;
                positionNodes();
                requestAnimationFrame(frame);
              }}

              function escapeHtml(value) {{
                return String(value).replace(/[&<>"']/g, (character) => ({{
                  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
                }})[character]);
              }}

              function selectSlot(slotName) {{
                nodes.forEach((node) => node.classList.toggle('active', node.dataset.satellite === slotName));
                cards.forEach((card) => card.classList.toggle('active', card.dataset.cardSlot === slotName));
                const slot = slots.find((item) => item.slot === slotName);
                if (!slot) return;
                selection.innerHTML = `
                  <strong>${{escapeHtml(slot.slot)}} · grupa ${{escapeHtml(slot.group)}}</strong>
                  <span>Kontrolowany slot scenariusza referencyjnego.</span>
                  <div class="selection-meta">
                    <b>faza ${{Number(slot.phase_deg).toFixed(0)}}°</b>
                    <b>${{Number(slot.altitude_km).toFixed(0)}} km</b>
                    <b>i=${{Number(slot.inclination_deg).toFixed(1)}}°</b>
                    <b>RAAN ${{Number(slot.raan_deg).toFixed(1)}}°</b>
                  </div>`;
              }}

              nodes.forEach((node) => {{
                const name = node.dataset.satellite;
                node.addEventListener('mouseenter', () => selectSlot(name));
                node.addEventListener('focus', () => selectSlot(name));
                node.addEventListener('click', () => selectSlot(name));
                node.addEventListener('keydown', (event) => {{
                  if (event.key === 'Enter' || event.key === ' ') {{
                    event.preventDefault();
                    selectSlot(name);
                  }}
                }});
              }});

              cards.forEach((card) => {{
                const name = card.dataset.cardSlot;
                card.addEventListener('mouseenter', () => selectSlot(name));
                card.addEventListener('focus', () => selectSlot(name));
                card.addEventListener('click', () => selectSlot(name));
              }});

              toggle.addEventListener('click', () => {{ running = !running; updateButton(); }});
              speedButtons.forEach((button) => button.addEventListener('click', () => {{
                speed = Number(button.dataset.speed || 1);
                speedButtons.forEach((candidate) => candidate.classList.toggle('active', candidate === button));
              }}));

              updateButton();
              positionNodes();
              if (slots.length) selectSlot(slots[0].slot);
              requestAnimationFrame(frame);
            }})();
          </script>
        </body>
        </html>
        """
    ).strip()


def render_constellation_phasing_visual(
    rows: Sequence[Mapping[str, object]] | None = None,
    *,
    height: int = 900,
) -> None:
    """Renderuje interaktywną wizualizację w izolowanym komponencie Streamlit."""

    import streamlit as st

    st.iframe(
        build_constellation_phasing_html(rows),
        width="stretch",
        height=height,
        tab_index=0,
    )


__all__ = [
    "build_constellation_phasing_html",
    "render_constellation_phasing_visual",
]
