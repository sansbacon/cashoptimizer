import numpy as np

from cash_optimizer import (
    CashOptimizer,
    Player,
    RobustSettings,
    RobustUncertaintySet,
    Rules,
    build_error_covariance_aligned_by_player,
    build_error_covariance_from_errors,
    sparsify_covariance_by_correlation_threshold,
)


def _robust_players():
    return [
        Player("qb_hi", "QB High", "A", "B", "QB", 7000, 20.0),
        Player("qb_lo", "QB Low", "B", "A", "QB", 7000, 19.4),
        Player("rb1_hi", "RB1 High", "C", "D", "RB", 7000, 18.0),
        Player("rb1_lo", "RB1 Low", "D", "C", "RB", 7000, 17.7),
        Player("rb2_hi", "RB2 High", "E", "F", "RB", 6800, 17.6),
        Player("rb2_lo", "RB2 Low", "F", "E", "RB", 6800, 17.3),
        Player("wr1_hi", "WR1 High", "A", "B", "WR", 6900, 17.1),
        Player("wr1_lo", "WR1 Low", "B", "A", "WR", 6900, 16.9),
        Player("wr2_hi", "WR2 High", "C", "D", "WR", 6700, 16.8),
        Player("wr2_lo", "WR2 Low", "D", "C", "WR", 6700, 16.5),
        Player("wr3_hi", "WR3 High", "E", "F", "WR", 6500, 16.4),
        Player("wr3_lo", "WR3 Low", "F", "E", "WR", 6500, 16.1),
        Player("te_hi", "TE High", "A", "B", "TE", 5000, 12.0),
        Player("te_lo", "TE Low", "B", "A", "TE", 5000, 11.8),
        Player("dst_hi", "DST High", "G", "H", "DST", 3200, 8.0),
        Player("dst_lo", "DST Low", "H", "G", "DST", 3200, 7.8),
    ]


def _diagonal_covariance(players):
    n = len(players)
    cov = np.zeros((n, n), dtype=float)
    for i, p in enumerate(players):
        std = 6.0 if p.player_id.endswith("_hi") else 1.0
        cov[i, i] = std * std
    return cov


def test_covariance_builder_handles_missing_and_is_psd():
    errors = np.array(
        [
            [1.0, 0.7, np.nan, -0.4],
            [0.4, 0.3, -0.2, -0.1],
            [0.8, np.nan, -0.5, -0.3],
            [0.1, 0.2, -0.1, np.nan],
            [0.0, 0.1, -0.2, -0.2],
            [-0.2, -0.3, 0.0, 0.1],
        ],
        dtype=float,
    )

    cov = build_error_covariance_from_errors(errors, min_overlap=3)
    assert cov.shape == (4, 4)
    assert np.all(np.isfinite(cov))
    assert np.allclose(cov, cov.T, atol=1e-9)

    eigvals = np.linalg.eigvalsh(cov)
    assert float(np.min(eigvals)) >= -1e-7


def test_covariance_builder_aligns_by_player_id_order():
    player_order = ["p3", "p1", "p2", "p4"]
    history = {
        "p1": [0.1, 0.2, None, -0.1, 0.0],
        "p2": [0.0, -0.1, 0.2, 0.1, None],
        "p3": [0.3, 0.2, 0.1, None, -0.2],
        # p4 intentionally missing to verify all-NaN fill behavior
    }
    cov = build_error_covariance_aligned_by_player(player_order, history, min_overlap=2)
    assert cov.shape == (4, 4)
    assert np.allclose(cov, cov.T, atol=1e-9)
    eigvals = np.linalg.eigvalsh(cov)
    assert float(np.min(eigvals)) >= -1e-7


def test_robust_box_shifts_to_lower_variance_lineup():
    players = _robust_players()
    optimizer = CashOptimizer(players=players, rules=Rules(salary_cap=70000))
    covariance = _diagonal_covariance(optimizer.players)

    baseline = optimizer.solve_optimal()
    robust = optimizer.solve_optimal(
        robust_settings=RobustSettings(enabled=True, rho=0.6, uncertainty_set=RobustUncertaintySet.BOX),
        robust_covariance=covariance,
    )

    baseline_hi = sum(1 for pid in baseline.lineup.player_ids if pid.endswith("_hi"))
    robust_hi = sum(1 for pid in robust.lineup.player_ids if pid.endswith("_hi"))

    assert robust.optimal_projection <= baseline.optimal_projection
    assert robust_hi < baseline_hi


def test_robust_polygon_solves_feasible_lineup():
    players = _robust_players()
    optimizer = CashOptimizer(players=players, rules=Rules(salary_cap=70000))
    covariance = _diagonal_covariance(optimizer.players)

    result = optimizer.solve_optimal(
        robust_settings=RobustSettings(enabled=True, rho=0.6, uncertainty_set=RobustUncertaintySet.POLYGON),
        robust_covariance=covariance,
    )

    assert len(result.lineup.player_ids) == 9
    assert result.lineup.salary_used <= 70000


def test_covariance_sparsification_zeroes_weak_off_diagonals():
    cov = np.array(
        [
            [4.0, 0.2, 1.0],
            [0.2, 9.0, 0.1],
            [1.0, 0.1, 16.0],
        ],
        dtype=float,
    )
    sparse = sparsify_covariance_by_correlation_threshold(cov, correlation_threshold=0.2)
    corr = np.divide(
        sparse,
        np.sqrt(np.diag(sparse))[:, None] * np.sqrt(np.diag(sparse))[None, :],
    )

    assert sparse.shape == cov.shape
    assert np.allclose(sparse, sparse.T, atol=1e-9)
    assert abs(float(corr[0, 1])) < 1e-6
