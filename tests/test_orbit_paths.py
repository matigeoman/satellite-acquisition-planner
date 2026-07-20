from pathlib import Path

from app.config.paths import ProjectPaths


def test_generated_orbit_cache_path_is_centralized(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)

    assert paths.generated_orbits == tmp_path.resolve() / "data/generated/orbits"

    paths.ensure_output_directories()
    assert paths.generated_orbits.is_dir()
