from __future__ import annotations

import math
from typing import Sequence

from .models import (
    CalibrationGovernanceDecision,
    CalibrationMetrics,
    CalibrationTuningRecommendation,
    CalibrationTuningResult,
)


def compute_calibration_metrics(
    predicted_cash_probabilities: Sequence[float],
    observed_cash_events: Sequence[int],
    epsilon: float = 1e-12,
) -> CalibrationMetrics:
    if len(predicted_cash_probabilities) != len(observed_cash_events):
        raise ValueError("predicted and observed lengths must match")
    if not predicted_cash_probabilities:
        raise ValueError("inputs must be non-empty")

    probs = [min(max(float(p), epsilon), 1.0 - epsilon) for p in predicted_cash_probabilities]
    obs = [1 if int(x) else 0 for x in observed_cash_events]

    brier = sum((p - y) ** 2 for p, y in zip(probs, obs)) / len(probs)
    log_loss = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(probs, obs)) / len(probs)
    mean_pred = sum(probs) / len(probs)
    observed = sum(obs) / len(obs)

    return CalibrationMetrics(
        brier_score=float(brier),
        log_loss=float(log_loss),
        mean_predicted_probability=float(mean_pred),
        observed_rate=float(observed),
    )


def compute_calibration_metrics_from_rows(
    rows: Sequence[dict[str, str]],
    predicted_column: str = "predicted_probability",
    observed_column: str = "observed_event",
) -> CalibrationMetrics:
    predicted: list[float] = []
    observed: list[int] = []
    for row in rows:
        predicted.append(float(row[predicted_column]))
        observed.append(int(row[observed_column]))
    return compute_calibration_metrics(predicted, observed)


def evaluate_weekly_calibration_governance(
    baseline_metrics: CalibrationMetrics,
    candidate_metrics: CalibrationMetrics,
    baseline_sample_count: int,
    candidate_sample_count: int,
    required_brier_improvement: float = 0.01,
    max_log_loss_increase: float = 0.0,
    min_samples: int = 0,
    require_parameter_versioning: bool = True,
    candidate_parameter_version: str | None = None,
) -> CalibrationGovernanceDecision:
    if required_brier_improvement < 0:
        raise ValueError("required_brier_improvement must be >= 0")
    if max_log_loss_increase < 0:
        raise ValueError("max_log_loss_increase must be >= 0")
    if min_samples < 0:
        raise ValueError("min_samples must be >= 0")

    brier_improvement = float(baseline_metrics.brier_score - candidate_metrics.brier_score)
    log_loss_improvement = float(baseline_metrics.log_loss - candidate_metrics.log_loss)

    reasons: list[str] = []
    if baseline_sample_count < min_samples:
        reasons.append("baseline sample count below minimum")
    if candidate_sample_count < min_samples:
        reasons.append("candidate sample count below minimum")
    if brier_improvement < required_brier_improvement:
        reasons.append("brier improvement below threshold")
    if candidate_metrics.log_loss > baseline_metrics.log_loss + max_log_loss_increase:
        reasons.append("candidate log loss exceeds allowed increase")
    if require_parameter_versioning and not (candidate_parameter_version and candidate_parameter_version.strip()):
        reasons.append("candidate parameter version is required")

    return CalibrationGovernanceDecision(
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        baseline_sample_count=int(baseline_sample_count),
        candidate_sample_count=int(candidate_sample_count),
        required_brier_improvement=float(required_brier_improvement),
        brier_improvement=brier_improvement,
        log_loss_improvement=log_loss_improvement,
        max_log_loss_increase=float(max_log_loss_increase),
        min_samples=int(min_samples),
        require_parameter_versioning=bool(require_parameter_versioning),
        candidate_parameter_version=(candidate_parameter_version.strip() if candidate_parameter_version else None),
        accepted=(len(reasons) == 0),
        rejection_reasons=tuple(reasons),
    )


def tune_profile_parameters_from_backtest_rows(
    rows: Sequence[dict[str, str]],
    contest_profile_column: str = "contest_profile",
    lambda_risk_column: str = "lambda_risk",
    correlation_penalty_column: str = "correlation_penalty_strength",
    predicted_column: str = "predicted_probability",
    observed_column: str = "observed_event",
    min_samples_per_setting: int = 20,
) -> CalibrationTuningResult:
    grouped: dict[tuple[str, float, float], list[tuple[float, int]]] = {}

    for row in rows:
        profile = str(row[contest_profile_column]).strip().lower()
        lambda_risk = float(row[lambda_risk_column])
        corr_penalty = float(row[correlation_penalty_column])
        pred = float(row[predicted_column])
        obs = int(row[observed_column])
        key = (profile, lambda_risk, corr_penalty)
        grouped.setdefault(key, []).append((pred, obs))

    by_profile: dict[str, list[CalibrationTuningRecommendation]] = {}
    for (profile, lambda_risk, corr_penalty), points in grouped.items():
        if len(points) < min_samples_per_setting:
            continue
        preds = [p for p, _ in points]
        obs = [o for _, o in points]
        metrics = compute_calibration_metrics(preds, obs)
        rec = CalibrationTuningRecommendation(
            contest_profile=profile,
            lambda_risk=lambda_risk,
            correlation_penalty_strength=corr_penalty,
            sample_count=len(points),
            metrics=metrics,
        )
        by_profile.setdefault(profile, []).append(rec)

    chosen: list[CalibrationTuningRecommendation] = []
    for profile, candidates in by_profile.items():
        best = min(
            candidates,
            key=lambda r: (
                r.metrics.brier_score,
                r.metrics.log_loss,
                -r.sample_count,
                r.lambda_risk,
                r.correlation_penalty_strength,
            ),
        )
        chosen.append(best)

    chosen.sort(key=lambda r: r.contest_profile)
    return CalibrationTuningResult(recommendations=tuple(chosen))
