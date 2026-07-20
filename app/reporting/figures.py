from __future__ import annotations

import io
from collections import Counter, defaultdict
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.reporting.models import ScientificReportSnapshot


def _save_figure(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_report_figures(snapshot: ScientificReportSnapshot) -> dict[str, bytes]:
    """Buduje statyczne wykresy PNG do HTML, DOCX i pakietu ZIP."""

    figures: dict[str, bytes] = {}

    if snapshot.schedule_rows:
        sensor_counts = Counter(
            str(row.get("sensor_type", "UNKNOWN"))
            for row in snapshot.schedule_rows
        )
        fig, ax = plt.subplots(figsize=(7.2, 4.1))
        labels = list(sensor_counts)
        values = [sensor_counts[label] for label in labels]
        ax.bar(labels, values)
        ax.set_title("Liczba zaplanowanych akwizycji według typu sensora")
        ax.set_xlabel("Typ sensora")
        ax.set_ylabel("Liczba akwizycji")
        ax.grid(axis="y", alpha=0.25)
        figures["schedule_sensor_mix.png"] = _save_figure(fig)

        satellites = Counter(
            str(row.get("satellite_id", "UNKNOWN"))
            for row in snapshot.schedule_rows
        )
        fig, ax = plt.subplots(figsize=(8.0, 4.3))
        labels = list(satellites)
        values = [satellites[label] for label in labels]
        ax.bar(labels, values)
        ax.set_title("Obciążenie satelitów w harmonogramie")
        ax.set_xlabel("Satelita")
        ax.set_ylabel("Liczba akwizycji")
        ax.grid(axis="y", alpha=0.25)
        figures["schedule_satellite_load.png"] = _save_figure(fig)

    if snapshot.request_diagnostic_rows:
        reasons: Counter[str] = Counter()
        for row in snapshot.request_diagnostic_rows:
            raw = str(row.get("reason_codes", "")).strip()
            if not raw:
                continue
            for reason in raw.split(" | "):
                if reason:
                    reasons[reason] += 1
        if reasons:
            fig, ax = plt.subplots(figsize=(8.5, 4.8))
            labels = [item[0] for item in reasons.most_common()]
            values = [item[1] for item in reasons.most_common()]
            ax.barh(labels[::-1], values[::-1])
            ax.set_title("Przyczyny braku pełnej realizacji zleceń")
            ax.set_xlabel("Liczba wskazań")
            ax.grid(axis="x", alpha=0.25)
            figures["unassigned_reasons.png"] = _save_figure(fig)

    if snapshot.benchmark_summary_rows:
        grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for row in snapshot.benchmark_summary_rows:
            objective = row.get("objective_mean")
            if objective in (None, "None", ""):
                continue
            algorithm = str(row.get("algorithm", ""))
            time_limit = row.get("time_limit_s")
            label = algorithm
            if algorithm == "CP_SAT" and time_limit not in (None, "None", ""):
                label = f"CP-SAT {time_limit}s"
            grouped[label].append(
                (int(_float(row.get("request_count"))), _float(objective))
            )
        if grouped:
            fig, ax = plt.subplots(figsize=(8.2, 4.8))
            for label, points in sorted(grouped.items()):
                points = sorted(points)
                ax.plot(
                    [item[0] for item in points],
                    [item[1] for item in points],
                    marker="o",
                    label=label,
                )
            ax.set_title("Wartość funkcji celu w benchmarku")
            ax.set_xlabel("Liczba zleceń")
            ax.set_ylabel("Średnia wartość funkcji celu")
            ax.grid(alpha=0.25)
            ax.legend()
            figures["benchmark_objective.png"] = _save_figure(fig)

        runtime_grouped: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for row in snapshot.benchmark_summary_rows:
            runtime = row.get("runtime_mean_s")
            if runtime in (None, "None", ""):
                continue
            algorithm = str(row.get("algorithm", ""))
            time_limit = row.get("time_limit_s")
            label = algorithm
            if algorithm == "CP_SAT" and time_limit not in (None, "None", ""):
                label = f"CP-SAT {time_limit}s"
            runtime_grouped[label].append(
                (int(_float(row.get("request_count"))), _float(runtime))
            )
        if runtime_grouped:
            fig, ax = plt.subplots(figsize=(8.2, 4.8))
            for label, points in sorted(runtime_grouped.items()):
                points = sorted(points)
                ax.plot(
                    [item[0] for item in points],
                    [item[1] for item in points],
                    marker="o",
                    label=label,
                )
            ax.set_title("Czas obliczeń w benchmarku")
            ax.set_xlabel("Liczba zleceń")
            ax.set_ylabel("Średni czas [s]")
            ax.grid(alpha=0.25)
            ax.legend()
            figures["benchmark_runtime.png"] = _save_figure(fig)

    if snapshot.stk_access_rows:
        categories = ["Start", "Koniec", "Długość"]
        errors = [
            sum(abs(_float(row.get("start_error_s"))) for row in snapshot.stk_access_rows)
            / len(snapshot.stk_access_rows),
            sum(abs(_float(row.get("end_error_s"))) for row in snapshot.stk_access_rows)
            / len(snapshot.stk_access_rows),
            sum(abs(_float(row.get("duration_error_s"))) for row in snapshot.stk_access_rows)
            / len(snapshot.stk_access_rows),
        ]
        fig, ax = plt.subplots(figsize=(7.0, 4.2))
        ax.bar(categories, errors)
        ax.set_title("Średnie błędy bezwzględne względem STK")
        ax.set_ylabel("Błąd [s]")
        ax.grid(axis="y", alpha=0.25)
        figures["stk_access_errors.png"] = _save_figure(fig)

    return figures
