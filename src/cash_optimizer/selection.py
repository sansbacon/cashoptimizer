from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from .models import CashProbabilitySelectionResult, Player


def evaluate_lineup_cash_probability(
    lineup_player_ids: Sequence[str],
    players: Sequence[Player],
    sample_projection_matrix: np.ndarray,
    threshold: float,
) -> float:
    if sample_projection_matrix.ndim != 2:
        raise ValueError("sample_projection_matrix must be 2D")

    index = {p.player_id: i for i, p in enumerate(players)}
    try:
        cols = [index[pid] for pid in lineup_player_ids]
    except KeyError as exc:
        raise ValueError(f"Unknown player id in lineup: {exc}") from exc

    lineup_totals = sample_projection_matrix[:, cols].sum(axis=1)
    return float(np.mean(lineup_totals >= threshold))


def select_best_lineup_by_cash_probability(
    candidate_lineups: Sequence[Sequence[str]],
    players: Sequence[Player],
    sample_projection_matrix: np.ndarray,
    threshold: float,
) -> CashProbabilitySelectionResult:
    if not candidate_lineups:
        raise ValueError("candidate_lineups cannot be empty")

    probs: dict[str, float] = {}
    best_ids: tuple[str, ...] | None = None
    best_prob = -1.0

    for lineup in candidate_lineups:
        ids = tuple(sorted(lineup))
        key = "|".join(ids)
        if key in probs:
            continue
        prob = evaluate_lineup_cash_probability(
            lineup_player_ids=ids,
            players=players,
            sample_projection_matrix=sample_projection_matrix,
            threshold=threshold,
        )
        probs[key] = prob
        if prob > best_prob:
            best_prob = prob
            best_ids = ids

    assert best_ids is not None
    return CashProbabilitySelectionResult(
        selected_lineup_player_ids=best_ids,
        estimated_cash_probability=best_prob,
        threshold=threshold,
        candidate_count=len(probs),
        lineup_probabilities=probs,
    )
