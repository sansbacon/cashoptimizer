from cash_optimizer import CashOptimizer, Player, Rules


def _players():
    return [
        Player("qb_a", "QB A", "T1", "T2", "QB", 7000, 21.0),
        Player("qb_b", "QB B", "T2", "T1", "QB", 6800, 20.2),
        Player("rb_a", "RB A", "T3", "T4", "RB", 7600, 19.0),
        Player("rb_b", "RB B", "T4", "T3", "RB", 7100, 17.3),
        Player("rb_c", "RB C", "T5", "T6", "RB", 6200, 15.0),
        Player("rb_d", "RB D", "T6", "T5", "RB", 5600, 13.8),
        Player("wr_a", "WR A", "T1", "T2", "WR", 7900, 21.8),
        Player("wr_b", "WR B", "T2", "T1", "WR", 7000, 18.5),
        Player("wr_c", "WR C", "T3", "T4", "WR", 6200, 15.7),
        Player("wr_d", "WR D", "T4", "T3", "WR", 5300, 13.4),
        Player("wr_e", "WR E", "T5", "T6", "WR", 4800, 12.3),
        Player("te_a", "TE A", "T1", "T2", "TE", 5100, 12.9),
        Player("te_b", "TE B", "T2", "T1", "TE", 4300, 10.4),
        Player("dst_a", "DST A", "T7", "T8", "DST", 3500, 8.2),
        Player("dst_b", "DST B", "T8", "T7", "DST", 2900, 6.9),
    ]


def test_human_baseline_runs_and_returns_feasible_trials():
    optimizer = CashOptimizer(players=_players(), rules=Rules())
    baseline = optimizer.run_human_heuristic_baseline(trials=200, top_n_per_slot=8, random_seed=99)

    assert baseline.trials == 200
    assert baseline.feasible_trials > 0
    assert baseline.best_projection >= baseline.mean_projection


def test_compare_against_human_heuristic_returns_edges():
    optimizer = CashOptimizer(players=_players(), rules=Rules())
    comparison = optimizer.compare_against_human_heuristic(trials=200, top_n_per_slot=8, random_seed=99)

    assert comparison.trials == 200
    assert comparison.feasible_trials > 0
    assert comparison.optimizer_projection > 0