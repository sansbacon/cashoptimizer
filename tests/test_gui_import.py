import importlib
from pathlib import Path

import pytest

from cash_optimizer import Rules


def test_gui_module_importable_or_skipped():
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 not installed")

    mod = importlib.import_module("cash_optimizer_gui.main_window")
    assert mod is not None


def test_gui_service_robust_methods_exist():
    service_mod = importlib.import_module("cash_optimizer_gui.services.optimizer_service")
    cls = getattr(service_mod, "OptimizerService")
    assert hasattr(cls, "solve_optimal")
    assert hasattr(cls, "solve_sensitivity")


def test_gui_service_export_json_and_stress_scenario(tmp_path: Path):
    service_mod = importlib.import_module("cash_optimizer_gui.services.optimizer_service")
    cls = getattr(service_mod, "OptimizerService")
    service = cls()

    root = Path(__file__).resolve().parents[1]
    input_csv = (root / "proj.csv") if (root / "proj.csv").exists() else (root / "tests" / "proj.csv")
    service.load_csv(input_csv, rules=Rules())

    out_dir = tmp_path / "gui_exports"
    service.export_artifacts(out_dir, runs=20, write_json_summary=True)
    assert (out_dir / "summary_bundle.json").exists()

    scenario_file = tmp_path / "scenarios.csv"
    scenario_file.write_text(
        "\n".join(
            [
                "scenario_name,projection_multiplier_global,QB,RB,WR,TE,DST",
                "all_down_5,0.95,1.0,1.0,1.0,1.0,1.0",
            ]
        ),
        encoding="utf-8",
    )
    result = service.run_stress(scenario_file=scenario_file)
    assert len(result.scenario_results) == 1
