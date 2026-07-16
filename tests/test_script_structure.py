from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"


def test_scripts_use_shared_bootstrap() -> None:
    operational_scripts = [
        path
        for path in SCRIPTS.glob("*.py")
        if path.name not in {"__init__.py", "_bootstrap.py"}
    ]

    assert operational_scripts

    for path in operational_scripts:
        source = path.read_text(encoding="utf-8")
        assert "from _bootstrap import" in source
        assert "sys.path.insert" not in source


def test_only_bootstrap_modifies_python_path() -> None:
    bootstrap = (SCRIPTS / "_bootstrap.py").read_text(encoding="utf-8")

    assert "sys.path.insert" in bootstrap


def test_all_scripts_compile() -> None:
    for path in SCRIPTS.glob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_project_check_script_exists() -> None:
    path = SCRIPTS / "check_project.py"

    assert path.is_file()
    assert "ScenarioService" in path.read_text(encoding="utf-8")
