from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import CashEvaluation, ContestProfile, ContestProfileSettings, SimulationResult


@dataclass(frozen=True)
class ProfileDefaults:
    lambda_risk: float
    percentile_target: int


_PROFILE_DEFAULTS = {
    ContestProfile.H2H: ProfileDefaults(lambda_risk=0.30, percentile_target=25),
    ContestProfile.DOUBLE_UP: ProfileDefaults(lambda_risk=0.20, percentile_target=20),
    ContestProfile.SMALL_FIELD: ProfileDefaults(lambda_risk=0.15, percentile_target=15),
}


def evaluate_cash_profiles(
    simulation_result: SimulationResult,
    threshold: float,
) -> tuple[CashEvaluation, ...]:
    lineup_means = np.asarray(
        [entry.mean_projection for entry in simulation_result.lineup_stats],
        dtype=float,
    )
    if lineup_means.size == 0:
        lineup_means = np.asarray([simulation_result.mean_optimal_projection], dtype=float)

    outcomes = np.asarray(
        [
            simulation_result.p05_optimal_projection,
            simulation_result.p50_optimal_projection,
            simulation_result.p95_optimal_projection,
        ],
        dtype=float,
    )

    evaluations: list[CashEvaluation] = []
    for profile in ContestProfile:
        defaults = _PROFILE_DEFAULTS[profile]
        sigma = float(np.std(lineup_means))
        mu = float(np.mean(lineup_means))
        p_val = float(np.percentile(outcomes, defaults.percentile_target))
        utility = mu - defaults.lambda_risk * sigma
        est_cash_probability = float(np.mean(outcomes >= threshold))
        evaluations.append(
            CashEvaluation(
                contest_profile=profile,
                lineup_projection_mean=mu,
                lineup_projection_std=sigma,
                risk_adjusted_utility=utility,
                percentile_20_projection=p_val,
                estimated_cash_probability=est_cash_probability,
            )
        )

    return tuple(evaluations)


def get_contest_profile_settings(contest_profile: ContestProfile) -> ContestProfileSettings:
    defaults = _PROFILE_DEFAULTS[contest_profile]
    objective_profile = "cash_probability" if contest_profile == ContestProfile.DOUBLE_UP else "risk_adjusted"
    floor_weight = {
        ContestProfile.H2H: 0.35,
        ContestProfile.DOUBLE_UP: 0.30,
        ContestProfile.SMALL_FIELD: 0.20,
    }[contest_profile]
    median_weight = {
        ContestProfile.H2H: 0.65,
        ContestProfile.DOUBLE_UP: 0.70,
        ContestProfile.SMALL_FIELD: 0.80,
    }[contest_profile]
    return ContestProfileSettings(
        objective_profile=objective_profile,
        lambda_risk=defaults.lambda_risk,
        floor_weight=floor_weight,
        median_weight=median_weight,
        target_percentile=defaults.percentile_target,
        max_players_per_game_environment=4,
        max_non_qb_skill_players_same_team=3,
        correlation_penalty_strength=0.20,
    )
