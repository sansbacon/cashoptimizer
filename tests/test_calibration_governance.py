from pathlib import Path

from click.testing import CliRunner
import pytest

from cash_optimizer import (
    CalibrationMetrics,
    evaluate_weekly_calibration_governance,
    tune_profile_parameters_from_backtest_rows,
)
from cash_optimizer_cli.main import cli


def test_evaluate_weekly_calibration_governance_accepts_improved_candidate():
    baseline = CalibrationMetrics(
        brier_score=0.20,
        log_loss=0.60,
        mean_predicted_probability=0.50,
        observed_rate=0.50,
    )
    candidate = CalibrationMetrics(
        brier_score=0.18,
        log_loss=0.58,
        mean_predicted_probability=0.49,
        observed_rate=0.50,
    )

    result = evaluate_weekly_calibration_governance(
        baseline_metrics=baseline,
        candidate_metrics=candidate,
        baseline_sample_count=200,
        candidate_sample_count=200,
        required_brier_improvement=0.01,
        max_log_loss_increase=0.0,
        min_samples=100,
        require_parameter_versioning=True,
        candidate_parameter_version="v2026.10",
    )

    assert result.accepted is True
    assert result.brier_improvement == pytest.approx(0.02)
    assert len(result.rejection_reasons) == 0


def test_evaluate_weekly_calibration_governance_rejects_without_version_when_required():
    baseline = CalibrationMetrics(
        brier_score=0.20,
        log_loss=0.60,
        mean_predicted_probability=0.50,
        observed_rate=0.50,
    )
    candidate = CalibrationMetrics(
        brier_score=0.19,
        log_loss=0.59,
        mean_predicted_probability=0.49,
        observed_rate=0.50,
    )

    result = evaluate_weekly_calibration_governance(
        baseline_metrics=baseline,
        candidate_metrics=candidate,
        baseline_sample_count=200,
        candidate_sample_count=200,
        required_brier_improvement=0.01,
        max_log_loss_increase=0.0,
        min_samples=100,
        require_parameter_versioning=True,
        candidate_parameter_version=None,
    )

    assert result.accepted is False
    assert "candidate parameter version is required" in result.rejection_reasons


def test_cli_calibration_governance_smoke(tmp_path: Path):
    runner = CliRunner()
    root = Path(__file__).resolve().parents[1]

    baseline_csv = tmp_path / "baseline.csv"
    baseline_csv.write_text(
        "\n".join(
            [
                "predicted_probability,observed_event",
                "0.6,1",
                "0.5,1",
                "0.4,0",
                "0.7,1",
            ]
        ),
        encoding="utf-8",
    )

    candidate_csv = tmp_path / "candidate.csv"
    candidate_csv.write_text(
        "\n".join(
            [
                "predicted_probability,observed_event",
                "0.7,1",
                "0.6,1",
                "0.3,0",
                "0.8,1",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(root / "proj.csv"),
            "--json",
            "calibration-governance",
            "--baseline-input",
            str(baseline_csv),
            "--candidate-input",
            str(candidate_csv),
            "--required-brier-improvement",
            "0.0",
            "--candidate-parameter-version",
            "v2026.10",
        ],
    )

    assert result.exit_code == 0
    assert "accepted" in result.output


def test_tune_profile_parameters_from_backtest_rows_selects_best_per_profile():
    rows = [
        {
            "contest_profile": "h2h",
            "lambda_risk": "0.30",
            "correlation_penalty_strength": "0.20",
            "predicted_probability": "0.70",
            "observed_event": "1",
        },
        {
            "contest_profile": "h2h",
            "lambda_risk": "0.30",
            "correlation_penalty_strength": "0.20",
            "predicted_probability": "0.65",
            "observed_event": "1",
        },
        {
            "contest_profile": "h2h",
            "lambda_risk": "0.15",
            "correlation_penalty_strength": "0.10",
            "predicted_probability": "0.55",
            "observed_event": "1",
        },
        {
            "contest_profile": "h2h",
            "lambda_risk": "0.15",
            "correlation_penalty_strength": "0.10",
            "predicted_probability": "0.50",
            "observed_event": "0",
        },
    ]

    tuned = tune_profile_parameters_from_backtest_rows(rows=rows, min_samples_per_setting=2)

    assert len(tuned.recommendations) == 1
    rec = tuned.recommendations[0]
    assert rec.contest_profile == "h2h"
    assert rec.lambda_risk == 0.30


def test_cli_calibration_tune_smoke(tmp_path: Path):
    runner = CliRunner()
    root = Path(__file__).resolve().parents[1]

    tuning_csv = tmp_path / "tuning.csv"
    tuning_csv.write_text(
        "\n".join(
            [
                "contest_profile,lambda_risk,correlation_penalty_strength,predicted_probability,observed_event",
                "h2h,0.30,0.20,0.7,1",
                "h2h,0.30,0.20,0.6,1",
                "double_up,0.20,0.20,0.6,1",
                "double_up,0.20,0.20,0.4,0",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(root / "proj.csv"),
            "--json",
            "calibration-tune",
            "--input",
            str(tuning_csv),
            "--min-samples",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "recommendations" in result.output
