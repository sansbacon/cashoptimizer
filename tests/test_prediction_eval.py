from pathlib import Path

from click.testing import CliRunner

from cash_optimizer import evaluate_prediction_models_by_position
from cash_optimizer_cli.main import cli


def test_evaluate_prediction_models_by_position_selects_expected_best():
    rows = [
        {"position": "QB", "actual": "20", "lr": "19", "rf": "18"},
        {"position": "QB", "actual": "22", "lr": "22", "rf": "20"},
        {"position": "WR", "actual": "15", "lr": "12", "rf": "14"},
        {"position": "WR", "actual": "18", "lr": "16", "rf": "17"},
    ]

    result = evaluate_prediction_models_by_position(rows=rows, model_columns=["lr", "rf"])

    assert result.best_model_by_position["QB"] == "lr"
    assert result.best_model_by_position["WR"] == "rf"
    assert len(result.metrics) == 4


def test_cli_evaluate_predictions_smoke(tmp_path: Path):
    runner = CliRunner()
    root = Path(__file__).resolve().parents[1]

    eval_csv = tmp_path / "eval.csv"
    eval_csv.write_text(
        "\n".join(
            [
                "position,actual,lr,rf",
                "QB,20,19,18",
                "QB,22,22,20",
                "WR,15,12,14",
                "WR,18,16,17",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(root / "proj.csv"),
            "evaluate-predictions",
            "--input",
            str(eval_csv),
            "--model-col",
            "lr",
            "--model-col",
            "rf",
        ],
    )

    assert result.exit_code == 0
    assert "best_model_by_position" in result.output
