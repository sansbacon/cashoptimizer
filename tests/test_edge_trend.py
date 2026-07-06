from pathlib import Path

from click.testing import CliRunner

from cash_optimizer import Rules, SolverSettings, build_edge_trend_from_slate_paths
from cash_optimizer_cli.main import cli


def test_build_edge_trend_single_slate_smoke():
    root = Path(__file__).resolve().parents[1]
    result = build_edge_trend_from_slate_paths(
        slate_paths=[root / "proj.csv"],
        rules=Rules(),
        solver_settings=SolverSettings(cp_sat_random_seed=1729),
        trials=50,
        top_n_per_slot=8,
    )

    assert len(result.rows) == 1
    assert result.rows[0].slate_label == "proj"


def test_cli_edge_trend_smoke(tmp_path: Path):
    runner = CliRunner()
    root = Path(__file__).resolve().parents[1]

    data_dir = tmp_path / "slates"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "week1.csv").write_text((root / "proj.csv").read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(root / "proj.csv"),
            "edge-trend",
            "--slates-glob",
            str(data_dir / "*.csv"),
            "--trials",
            "40",
            "--top-n-per-slot",
            "8",
        ],
    )

    assert result.exit_code == 0
    assert "mean_edge_vs_human_mean" in result.output
