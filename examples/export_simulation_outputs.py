import csv
from pathlib import Path

from cash_optimizer import CashOptimizer, SimulationConfig
from cash_optimizer.io import load_players_from_dk_csv


def _write_optimal_lineup(out_dir: Path, optimizer: CashOptimizer) -> None:
    result = optimizer.solve_optimal()
    path = out_dir / "optimal_lineup.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["slot", "player_id", "name", "position", "team", "salary", "projection"])
        for slot, player in result.lineup.players_by_slot.items():
            writer.writerow(
                [
                    slot,
                    player.player_id,
                    player.name,
                    player.position,
                    player.team,
                    player.salary,
                    player.projection,
                ]
            )


def _write_sensitivity(out_dir: Path, optimizer: CashOptimizer) -> None:
    result = optimizer.solve_sensitivity_all()
    path = out_dir / "sensitivity.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "player_id",
                "in_optimal",
                "forced_in_objective",
                "forced_out_objective",
                "delta_enter",
                "delta_exit",
                "tie_flag",
            ]
        )
        for row in result.entries:
            writer.writerow(
                [
                    row.player_id,
                    row.in_optimal,
                    row.forced_in_objective,
                    row.forced_out_objective,
                    row.delta_enter,
                    row.delta_exit,
                    row.tie_flag,
                ]
            )


def _write_simulation(out_dir: Path, optimizer: CashOptimizer) -> None:
    sim = optimizer.run_projection_distribution_simulation(
        SimulationConfig(num_runs=1000, random_seed=42, worker_count=1)
    )

    summary_path = out_dir / "simulation_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "num_runs",
                "random_seed",
                "mean_optimal_projection",
                "p05_optimal_projection",
                "p50_optimal_projection",
                "p95_optimal_projection",
                "unique_lineups",
            ]
        )
        writer.writerow(
            [
                sim.num_runs,
                sim.random_seed,
                sim.mean_optimal_projection,
                sim.p05_optimal_projection,
                sim.p50_optimal_projection,
                sim.p95_optimal_projection,
                sim.unique_lineups,
            ]
        )

    player_path = out_dir / "simulation_player_stats.csv"
    with player_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "player_id",
                "inclusion_rate",
                "mean_lineup_projection_when_included",
                "leverage_to_baseline",
            ]
        )
        for row in sim.player_stats:
            writer.writerow(
                [
                    row.player_id,
                    row.inclusion_rate,
                    row.mean_lineup_projection_when_included,
                    row.leverage_to_baseline,
                ]
            )

    lineup_path = out_dir / "simulation_lineup_stats.csv"
    with lineup_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["lineup_key", "frequency", "frequency_rate", "mean_projection"])
        for row in sim.lineup_stats:
            writer.writerow(
                [row.lineup_key, row.frequency, row.frequency_rate, row.mean_projection]
            )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "proj.csv"
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    players = load_players_from_dk_csv(csv_path)
    optimizer = CashOptimizer(players=players)

    _write_optimal_lineup(out_dir, optimizer)
    _write_sensitivity(out_dir, optimizer)
    _write_simulation(out_dir, optimizer)

    print(f"Wrote output files to: {out_dir}")


if __name__ == "__main__":
    main()
