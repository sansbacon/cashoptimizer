from __future__ import annotations

from typing import Sequence

from .models import Player, StressScenario, StressScenarioResult, StressTestResult


def apply_stress_scenario(
    players: Sequence[Player],
    base_projections: Sequence[float],
    scenario: StressScenario,
) -> list[float]:
    if len(players) != len(base_projections):
        raise ValueError("players and base_projections length mismatch")

    stressed: list[float] = []
    for idx, player in enumerate(players):
        base = float(base_projections[idx])
        pos_mult = float(scenario.projection_multiplier_by_position.get(player.position, 1.0))
        value = base * scenario.projection_multiplier_global * pos_mult
        stressed.append(max(0.0, value))
    return stressed


def default_stress_scenarios() -> tuple[StressScenario, ...]:
    return (
        StressScenario(
            name="all_wr_downshift",
            projection_multiplier_by_position={"WR": 0.90},
        ),
        StressScenario(
            name="all_rb_efficiency_downshift",
            projection_multiplier_by_position={"RB": 0.92},
        ),
        StressScenario(
            name="primary_game_environment_fail",
            projection_multiplier_global=0.88,
        ),
    )


def run_stress_test(
    optimizer,
    base_projections: Sequence[float] | None = None,
    scenarios: Sequence[StressScenario] | None = None,
) -> StressTestResult:
    projections = list(base_projections) if base_projections is not None else [p.projection for p in optimizer.players]
    base_result = optimizer.solve_optimal(projections=projections)

    scenario_defs = tuple(scenarios) if scenarios is not None else default_stress_scenarios()
    scenario_results: list[StressScenarioResult] = []
    for scenario in scenario_defs:
        stressed_vector = apply_stress_scenario(optimizer.players, projections, scenario)
        stressed_result = optimizer.solve_optimal(projections=stressed_vector)
        scenario_results.append(
            StressScenarioResult(
                scenario_name=scenario.name,
                projected_points=stressed_result.optimal_projection,
                salary_used=stressed_result.lineup.salary_used,
                lineup_player_ids=stressed_result.lineup.player_ids,
            )
        )

    values = [s.projected_points for s in scenario_results]
    return StressTestResult(
        base_projection=base_result.optimal_projection,
        scenario_results=tuple(scenario_results),
        worst_case_projection=min(values) if values else base_result.optimal_projection,
        mean_stress_projection=(sum(values) / len(values)) if values else base_result.optimal_projection,
    )
