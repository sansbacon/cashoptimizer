from pathlib import Path

from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv


def test_proj_csv_load_and_optimize():
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "proj.csv"

    players = load_players_from_dk_csv(csv_path)
    assert len(players) > 20

    optimizer = CashOptimizer(players=players)
    result = optimizer.solve_optimal()

    assert len(result.lineup.player_ids) == 9
    assert result.lineup.salary_used <= 50000
    assert result.optimal_projection > 0
