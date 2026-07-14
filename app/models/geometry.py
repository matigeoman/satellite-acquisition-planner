from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PointGeometry(BaseModel):
    """Punkt GeoJSON zapisany w układzie WGS84."""

    model_config = ConfigDict(
        extra="forbid",
    )

    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(
        cls,
        value: tuple[float, float],
    ) -> tuple[float, float]:
        longitude, latitude = value

        if not -180.0 <= longitude <= 180.0:
            raise ValueError(
                "Długość geograficzna musi należeć do zakresu "
                "[-180, 180]"
            )

        if not -90.0 <= latitude <= 90.0:
            raise ValueError(
                "Szerokość geograficzna musi należeć do zakresu "
                "[-90, 90]"
            )

        return value


class PolygonGeometry(BaseModel):
    """Polygon GeoJSON zapisany w układzie WGS84."""

    model_config = ConfigDict(
        extra="forbid",
    )

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[float, float]]]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(
        cls,
        value: list[list[tuple[float, float]]],
    ) -> list[list[tuple[float, float]]]:
        if not value:
            raise ValueError(
                "Polygon musi zawierać co najmniej jeden pierścień"
            )

        for ring_index, ring in enumerate(value):
            if len(ring) < 4:
                raise ValueError(
                    f"Pierścień {ring_index} musi zawierać "
                    "co najmniej cztery pozycje"
                )

            for longitude, latitude in ring:
                if not -180.0 <= longitude <= 180.0:
                    raise ValueError(
                        "Długość geograficzna musi należeć do zakresu "
                        "[-180, 180]"
                    )

                if not -90.0 <= latitude <= 90.0:
                    raise ValueError(
                        "Szerokość geograficzna musi należeć do zakresu "
                        "[-90, 90]"
                    )

            if ring[0] != ring[-1]:
                raise ValueError(
                    f"Pierścień {ring_index} musi być zamknięty"
                )

            distinct_vertices = set(ring[:-1])

            if len(distinct_vertices) < 3:
                raise ValueError(
                    f"Pierścień {ring_index} musi zawierać "
                    "co najmniej trzy różne wierzchołki"
                )

        outer_ring_area = cls._signed_area(value[0])

        if abs(outer_ring_area) < 1e-12:
            raise ValueError(
                "Zewnętrzny pierścień Polygon nie może mieć zerowego pola"
            )

        return value

    @staticmethod
    def _signed_area(
        ring: list[tuple[float, float]],
    ) -> float:
        """Oblicza orientowane pole pierścienia metodą shoelace."""

        area = 0.0

        for current, following in zip(ring, ring[1:]):
            x1, y1 = current
            x2, y2 = following

            area += x1 * y2 - x2 * y1

        return area / 2.0


TargetGeometry = Annotated[
    PointGeometry | PolygonGeometry,
    Field(discriminator="type"),
]