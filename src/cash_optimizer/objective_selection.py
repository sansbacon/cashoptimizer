from __future__ import annotations

from typing import Sequence

import numpy as np

from .models import (
    NormalizedObjectiveLineupMetric,
    NormalizedObjectiveSelectionResult,
    NormalizedObjectiveWeights,
    Player,
)


def select_best_lineup_by_normalized_objective(
    candidate_lineups: Sequence[Sequence[str]],
    players: Sequence[Player],
    sample_projection_matrix: np.ndarray,
    weights: NormalizedObjectiveWeights,
    cash_threshold: float | None = None,
    epsilon: float = 1e-9,
) -> NormalizedObjectiveSelectionResult:
    if not candidate_lineups:
        raise ValueError("candidate_lineups cannot be empty")
    if sample_projection_matrix.ndim != 2:
        raise ValueError("sample_projection_matrix must be 2D")

    player_index = {p.player_id: i for i, p in enumerate(players)}
    cov_matrix = np.cov(sample_projection_matrix, rowvar=False)

    means: list[float] = []
    risks: list[float] = []
    cov_penalties: list[float] = []
    cash_probs: list[float] = []
    keys: list[str] = []
    ids_list: list[tuple[str, ...]] = []

    for lineup in candidate_lineups:
        ids = tuple(sorted(lineup))
        key = "|".join(ids)
        if key in keys:
            continue
        try:
            cols = [player_index[pid] for pid in ids]
        except KeyError as exc:
            raise ValueError(f"Unknown player id in lineup: {exc}") from exc

        totals = sample_projection_matrix[:, cols].sum(axis=1)
        mean_val = float(np.mean(totals))
        risk_val = float(np.std(totals))

        sub_cov = cov_matrix[np.ix_(cols, cols)]
        off_diag = sub_cov - np.diag(np.diag(sub_cov))
        downside_cov_penalty = float(np.sum(np.maximum(off_diag, 0.0)))

        if cash_threshold is None:
            cash_prob = 0.0
        else:
            cash_prob = float(np.mean(totals >= cash_threshold))

        means.append(mean_val)
        risks.append(risk_val)
        cov_penalties.append(downside_cov_penalty)
        cash_probs.append(cash_prob)
        keys.append(key)
        ids_list.append(ids)

    mean_norm = _minmax_normalize(np.asarray(means, dtype=float), epsilon=epsilon)
    risk_norm = _minmax_normalize(np.asarray(risks, dtype=float), epsilon=epsilon)
    cov_norm = _minmax_normalize(np.asarray(cov_penalties, dtype=float), epsilon=epsilon)
    cash_norm = _minmax_normalize(np.asarray(cash_probs, dtype=float), epsilon=epsilon)

    scores = (
        (weights.w_mean * mean_norm)
        - (weights.w_risk * risk_norm)
        - (weights.w_cov * cov_norm)
        + (weights.w_cash_prob * cash_norm)
    )

    best_idx = int(np.argmax(scores))
    metrics = tuple(
        NormalizedObjectiveLineupMetric(
            lineup_key=keys[i],
            mean_projection=means[i],
            risk_std=risks[i],
            downside_cov_penalty=cov_penalties[i],
            cash_probability=cash_probs[i],
            normalized_score=float(scores[i]),
        )
        for i in range(len(keys))
    )

    return NormalizedObjectiveSelectionResult(
        selected_lineup_player_ids=ids_list[best_idx],
        candidate_count=len(keys),
        weights=weights,
        lineup_metrics=metrics,
    )


def _minmax_normalize(values: np.ndarray, epsilon: float = 1e-9) -> np.ndarray:
    v_min = float(np.min(values))
    v_max = float(np.max(values))
    denom = max(v_max - v_min, float(epsilon))
    return (values - v_min) / denom
