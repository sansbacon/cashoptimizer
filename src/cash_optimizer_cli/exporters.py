from __future__ import annotations

import csv
from pathlib import Path

from cash_optimizer import EdgeTrendResult, OptimizationResult, SensitivityResult, SimulationResult, StressTestResult


def write_optimal_lineup(path: Path, result: OptimizationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["slot", "player_id", "name", "position", "team", "salary", "projection"])
        for slot, player in result.lineup.players_by_slot.items():
            w.writerow([slot, player.player_id, player.name, player.position, player.team, player.salary, player.projection])


def write_sensitivity(path: Path, result: SensitivityResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["player_id", "in_optimal", "forced_in_objective", "forced_out_objective", "delta_enter", "delta_exit", "tie_flag"])
        for row in result.entries:
            w.writerow([
                row.player_id,
                row.in_optimal,
                row.forced_in_objective,
                row.forced_out_objective,
                row.delta_enter,
                row.delta_exit,
                row.tie_flag,
            ])


def write_simulation(prefix_path: Path, result: SimulationResult) -> None:
    prefix_path.parent.mkdir(parents=True, exist_ok=True)

    summary = prefix_path.with_name(prefix_path.name + "_summary.csv")
    with summary.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["num_runs", "random_seed", "mean", "p05", "p50", "p95", "unique_lineups"])
        w.writerow([
            result.num_runs,
            result.random_seed,
            result.mean_optimal_projection,
            result.p05_optimal_projection,
            result.p50_optimal_projection,
            result.p95_optimal_projection,
            result.unique_lineups,
        ])

    players = prefix_path.with_name(prefix_path.name + "_player_stats.csv")
    with players.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["player_id", "inclusion_rate", "mean_lineup_projection_when_included", "leverage_to_baseline"])
        for row in result.player_stats:
            w.writerow([row.player_id, row.inclusion_rate, row.mean_lineup_projection_when_included, row.leverage_to_baseline])

    lineups = prefix_path.with_name(prefix_path.name + "_lineup_stats.csv")
    with lineups.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lineup_key", "frequency", "frequency_rate", "mean_projection"])
        for row in result.lineup_stats:
            w.writerow([row.lineup_key, row.frequency, row.frequency_rate, row.mean_projection])


def write_edge_trend(path: Path, result: EdgeTrendResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "slate_label",
            "optimizer_projection",
            "human_best_projection",
            "human_mean_projection",
            "edge_vs_human_best",
            "edge_vs_human_mean",
            "trials",
            "feasible_trials",
            "cash_line",
            "optimizer_above_cash",
            "human_mean_above_cash",
        ])
        for row in result.rows:
            w.writerow([
                row.slate_label,
                row.optimizer_projection,
                row.human_best_projection,
                row.human_mean_projection,
                row.edge_vs_human_best,
                row.edge_vs_human_mean,
                row.trials,
                row.feasible_trials,
                row.cash_line,
                row.optimizer_above_cash,
                row.human_mean_above_cash,
            ])


def write_candidates(path: Path, candidates: tuple[tuple[str, ...], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_index", "lineup_key", "player_ids"])
        for idx, lineup in enumerate(candidates, start=1):
            lineup_key = "|".join(lineup)
            w.writerow([idx, lineup_key, " ".join(lineup)])


def write_stress(path: Path, result: StressTestResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "scenario_name",
                "projected_points",
                "salary_used",
                "lineup_player_ids",
                "base_projection",
                "worst_case_projection",
                "mean_stress_projection",
            ]
        )
        for scenario in result.scenario_results:
            w.writerow(
                [
                    scenario.scenario_name,
                    scenario.projected_points,
                    scenario.salary_used,
                    " ".join(scenario.lineup_player_ids),
                    result.base_projection,
                    result.worst_case_projection,
                    result.mean_stress_projection,
                ]
            )
