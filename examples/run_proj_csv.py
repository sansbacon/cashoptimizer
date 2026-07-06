from pathlib import Path

from cash_optimizer import CashOptimizer, SimulationConfig
from cash_optimizer.io import load_players_from_dk_csv


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "proj.csv"

    players = load_players_from_dk_csv(csv_path)
    optimizer = CashOptimizer(players=players)

    optimal = optimizer.solve_optimal()
    print("Optimal lineup:")
    for slot, player in optimal.lineup.players_by_slot.items():
        print(f"  {slot:>4} | {player.name:25} | {player.position:3} | ${player.salary:5d} | {player.projection:.2f}")
    print(f"Total salary: ${optimal.lineup.salary_used}")
    print(f"Projected points: {optimal.optimal_projection:.2f}")

    sens = optimizer.solve_sensitivity_all()
    print("\nSensitivity sample (first 10 rows):")
    for row in sens.entries[:10]:
        print(
            row.player_id,
            row.in_optimal,
            row.delta_enter,
            row.delta_exit,
            row.tie_flag,
        )

    sim = optimizer.run_projection_distribution_simulation(
        SimulationConfig(num_runs=200, random_seed=42, worker_count=1)
    )
    print("\nSimulation summary:")
    print(f"Runs: {sim.num_runs}")
    print(f"Mean optimal projection: {sim.mean_optimal_projection:.2f}")
    print(f"P05/P50/P95: {sim.p05_optimal_projection:.2f} / {sim.p50_optimal_projection:.2f} / {sim.p95_optimal_projection:.2f}")
    print(f"Unique lineups: {sim.unique_lineups}")
