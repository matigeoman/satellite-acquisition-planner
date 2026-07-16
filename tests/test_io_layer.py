from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from app.catalog_loader import load_system_catalog as legacy_load_catalog
from app.io import (
    load_schedule,
    load_system_catalog,
    save_schedule,
)
from app.io.json_files import load_json_model, save_json_model
from app.models.schedule import Schedule


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ExampleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int
    label: str


def test_generic_json_round_trip(tmp_path: Path) -> None:
    model = ExampleModel(value=7, label="próba")
    path = tmp_path / "nested" / "model.json"

    saved = save_json_model(model, path)
    loaded = load_json_model(
        saved,
        model_type=ExampleModel,
        description="testowego modelu",
    )

    assert loaded == model
    assert saved.read_text(encoding="utf-8").endswith("\n")


def test_generic_loader_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nie wskazuje pliku"):
        load_json_model(
            tmp_path,
            model_type=ExampleModel,
            description="testowego modelu",
        )


def test_generic_loader_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="poprawnego JSON"):
        load_json_model(
            path,
            model_type=ExampleModel,
            description="testowego modelu",
        )


def test_legacy_catalog_import_uses_new_io_layer() -> None:
    assert legacy_load_catalog is load_system_catalog


def test_catalog_can_be_loaded_through_new_io_layer() -> None:
    catalog = load_system_catalog(
        PROJECT_ROOT / "data" / "example_system.json"
    )

    assert len(catalog.satellites) == 6


def test_schedule_round_trip_through_new_io_layer(tmp_path: Path) -> None:
    source = load_schedule(
        PROJECT_ROOT / "data" / "example_schedule_greedy.json"
    )
    destination = tmp_path / "schedule.json"

    save_schedule(source, destination)
    loaded = load_schedule(destination)

    assert isinstance(loaded, Schedule)
    assert loaded.model_dump(mode="json") == source.model_dump(mode="json")
