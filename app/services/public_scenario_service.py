from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.opportunities import PublicOpportunityBuildResult
from app.models.catalog import SystemCatalog
from app.models.enums import SatelliteSourceType
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.satellite import Satellite
from app.services.scenario_service import LoadedScenario, ScenarioDefinition


PUBLIC_CATALOG_ID = "CATALOG-PUBLIC-PLANNER"
PUBLIC_REQUEST_SET_ID = "REQSET-PUBLIC-SESSION"
PUBLIC_OPPORTUNITY_SET_ID = "OPPSET-PUBLIC-SESSION"


def build_public_system_catalog() -> SystemCatalog:
    """Buduje katalog 4 ICEYE + 2 Pléiades Neo do planowania sesyjnego."""

    sar_sensor = ICEYE_PUBLIC_PROFILE.sensor
    eo_sensor = PLEIADES_NEO_PUBLIC_PROFILE.sensor
    satellites = [
        Satellite(
            satellite_id=f"SAR-{index:02d}",
            name=f"ICEYE public slot {index:02d}",
            constellation_id="CONST-SAR",
            orbit_id=ICEYE_PUBLIC_PROFILE.orbit_template.orbit_id,
            sensor_id=sar_sensor.sensor_id,
            phase_angle_deg=(index - 1) * 90.0,
            memory_capacity_mb=256000.0,
            initial_memory_usage_mb=(10000.0, 8000.0, 12000.0, 5000.0)[
                index - 1
            ],
            minimum_transition_time_s=90.0,
            max_acquisitions_per_day=30,
            max_imaging_time_per_day_s=3600.0,
            source_type=SatelliteSourceType.PUBLIC_DATA,
            source_reference="CelesTrak GP/OMM; ICEYE public sensor profile",
            notes=(
                "Orbita jest pobierana publicznie. Pamięć, limit akwizycji, "
                "czas obrazowania i przerwa przejścia pozostają jawnymi "
                "założeniami planistycznymi projektu."
            ),
        )
        for index in range(1, 5)
    ]
    satellites.extend(
        Satellite(
            satellite_id=f"EO-{index:02d}",
            name=f"Pléiades Neo public slot {index:02d}",
            constellation_id="CONST-EO",
            orbit_id=PLEIADES_NEO_PUBLIC_PROFILE.orbit_template.orbit_id,
            sensor_id=eo_sensor.sensor_id,
            phase_angle_deg=(index - 1) * 180.0,
            memory_capacity_mb=512000.0,
            initial_memory_usage_mb=(20000.0, 15000.0)[index - 1],
            minimum_transition_time_s=60.0,
            max_acquisitions_per_day=40,
            max_imaging_time_per_day_s=3600.0,
            source_type=SatelliteSourceType.PUBLIC_DATA,
            source_reference=(
                "CelesTrak GP/OMM; Airbus Pléiades Neo public profile"
            ),
            notes=(
                "Orbita jest pobierana publicznie. Pamięć, limit akwizycji, "
                "czas obrazowania i przerwa przejścia pozostają jawnymi "
                "założeniami planistycznymi projektu."
            ),
        )
        for index in range(1, 3)
    )
    return SystemCatalog(
        catalog_id=PUBLIC_CATALOG_ID,
        name="Publiczny model ICEYE i Pléiades Neo",
        version="1.0.0",
        orbits=[
            ICEYE_PUBLIC_PROFILE.orbit_template,
            PLEIADES_NEO_PUBLIC_PROFILE.orbit_template,
        ],
        sensors=[sar_sensor, eo_sensor],
        satellites=satellites,
        notes=(
            "Geometria i tryby sensorów korzystają z danych publicznych. "
            "Ograniczenia zasobowe satelitów są transparentnymi założeniami "
            "modelowymi, ponieważ pełne dane operacyjne operatorów nie są "
            "publiczne."
        ),
    )


class PublicScenarioService:
    """Buduje scenariusz planistyczny z okazji utworzonych w sesji UI."""

    def __init__(self, *, catalog: SystemCatalog | None = None) -> None:
        self.catalog = catalog or build_public_system_catalog()

    def build(
        self,
        *,
        requests: list[ObservationRequest],
        builds_by_request_id: dict[str, PublicOpportunityBuildResult],
    ) -> LoadedScenario:
        requests_by_id = {request.request_id: request for request in requests}
        included_request_ids = [
            request_id
            for request_id, build in builds_by_request_id.items()
            if request_id in requests_by_id and build.opportunities
        ]
        if not included_request_ids:
            raise ValueError(
                "Brak wygenerowanych okazji publicznych do planowania"
            )
        included_requests = [
            requests_by_id[request_id]
            for request_id in sorted(included_request_ids)
        ]
        opportunities = [
            opportunity
            for request_id in sorted(included_request_ids)
            for opportunity in builds_by_request_id[request_id].opportunities
        ]
        horizon_start = min(
            request.earliest_start_utc for request in included_requests
        )
        horizon_end = max(
            request.latest_end_utc for request in included_requests
        )
        now = datetime.now(timezone.utc)
        request_set = ObservationRequestSet(
            request_set_id=PUBLIC_REQUEST_SET_ID,
            name="Zlecenia publiczne z bieżącej sesji",
            version="1.0.0",
            horizon_start_utc=horizon_start,
            horizon_end_utc=horizon_end,
            generated_at_utc=now,
            requests=included_requests,
            notes=(
                "Zlecenia utworzone interaktywnie na mapie. Zbiór istnieje "
                "wyłącznie w bieżącej sesji aplikacji."
            ),
        )
        opportunity_set = AcquisitionOpportunitySet(
            opportunity_set_id=PUBLIC_OPPORTUNITY_SET_ID,
            name="Okazje publiczne CelesTrak/Open-Meteo",
            version="1.0.0",
            catalog_id=self.catalog.catalog_id,
            request_set_id=request_set.request_set_id,
            horizon_start_utc=horizon_start,
            horizon_end_utc=horizon_end,
            generated_at_utc=now,
            random_seed=0,
            opportunities=opportunities,
            notes=(
                "Okazje wyznaczone z GP/OMM, SGP4, publicznych profili "
                "sensorów oraz prognozy zachmurzenia Open-Meteo dla EO."
            ),
        )
        opportunity_set.validate_against(self.catalog, request_set)
        definition = ScenarioDefinition(
            scenario_id="PUBLIC",
            name="Publiczne orbity i pogoda",
            description=(
                "Scenariusz sesyjny z publicznych orbit i prognozy pogody."
            ),
            catalog_path=Path("data/generated/public-session/system.json"),
            request_set_path=Path("data/generated/public-session/requests.json"),
            opportunity_set_path=Path(
                "data/generated/public-session/opportunities.json"
            ),
        )
        return LoadedScenario(
            definition=definition,
            catalog=self.catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
        )
