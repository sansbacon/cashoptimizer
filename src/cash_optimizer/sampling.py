from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import numpy as np

from .models import Player, SamplingMode, SimulationConfig


_DEFAULT_STD_MULTIPLIER_BY_POSITION = {
    "QB": 0.18,
    "RB": 0.25,
    "WR": 0.32,
    "TE": 0.30,
    "DST": 0.40,
}


def sample_projection_matrix(players: Sequence[Player], config: SimulationConfig) -> np.ndarray:
    rng = np.random.default_rng(config.random_seed)
    means = np.asarray([p.projection for p in players], dtype=float)

    if config.sampling_mode == SamplingMode.INDEPENDENT:
        samples = _sample_independent(players=players, means=means, num_runs=config.num_runs, rng=rng)
    elif config.sampling_mode == SamplingMode.CORRELATED:
        base = _sample_independent(players=players, means=means, num_runs=config.num_runs, rng=rng)
        samples = _apply_correlation_overlay(players=players, base_samples=base, means=means, rng=rng)
    else:
        raise ValueError(f"Unsupported sampling mode: {config.sampling_mode}")

    if config.clip_min_projection is not None:
        samples = np.maximum(samples, config.clip_min_projection)
    if config.clip_max_projection is not None:
        samples = np.minimum(samples, config.clip_max_projection)
    return samples


def _sample_independent(
    players: Sequence[Player],
    means: np.ndarray,
    num_runs: int,
    rng: np.random.Generator,
) -> np.ndarray:
    cols: list[np.ndarray] = []
    for idx, player in enumerate(players):
        std_dev = player.distribution.std_dev
        if std_dev is None:
            multiplier = _DEFAULT_STD_MULTIPLIER_BY_POSITION.get(player.position, 0.25)
            std_dev = max(0.1, means[idx] * multiplier)

        dist_type = player.distribution.distribution_type.lower()
        if dist_type == "normal":
            col = rng.normal(loc=means[idx], scale=std_dev, size=num_runs)
        elif dist_type in {"student_t", "student_t_df_6"}:
            df = int(player.distribution.params.get("df", 6.0))
            col = means[idx] + rng.standard_t(df=df, size=num_runs) * std_dev
        elif dist_type == "lognormal":
            variance = std_dev**2
            mu = np.log((means[idx] ** 2) / np.sqrt(variance + means[idx] ** 2)) if means[idx] > 0 else 0.0
            sigma = np.sqrt(np.log(1 + variance / max(means[idx] ** 2, 1e-9)))
            col = rng.lognormal(mean=mu, sigma=sigma, size=num_runs)
        else:
            col = rng.normal(loc=means[idx], scale=std_dev, size=num_runs)
        cols.append(col)

    return np.column_stack(cols)


def _apply_correlation_overlay(
    players: Sequence[Player],
    base_samples: np.ndarray,
    means: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    result = np.array(base_samples, copy=True)

    game_to_indices: dict[str, list[int]] = defaultdict(list)
    team_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, player in enumerate(players):
        if player.game_id:
            game_to_indices[player.game_id].append(idx)
        team_to_indices[player.team].append(idx)

    game_noise = {gid: rng.normal(loc=0.0, scale=1.0, size=result.shape[0]) for gid in game_to_indices}
    team_noise = {team: rng.normal(loc=0.0, scale=1.0, size=result.shape[0]) for team in team_to_indices}

    for idx, player in enumerate(players):
        mean_proj = means[idx]
        overlay = np.zeros(result.shape[0], dtype=float)
        if player.game_id and player.game_id in game_noise:
            overlay += game_noise[player.game_id] * (0.05 * mean_proj)
        overlay += team_noise[player.team] * (0.03 * mean_proj)
        result[:, idx] += overlay

    return result
