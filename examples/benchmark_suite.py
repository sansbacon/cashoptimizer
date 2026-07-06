import time
from pathlib import Path

import numpy as np

from cash_optimizer import (
    CashOptimizer,
    RobustSettings,
    RobustUncertaintySet,
    SimulationConfig,
    run_performance_benchmarks,
)
from cash_optimizer.io import load_players_from_dk_csv


def timed(label, fn):
    start = time.perf_counter()
    out = fn()
    elapsed = (time.perf_counter() - start) * 1000.0
    print(f"{label}: {elapsed:.2f} ms")
    return out, elapsed


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    players = load_players_from_dk_csv(root / "proj.csv")
    optimizer = CashOptimizer(players=players)

    perf = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=1000,
        baseline_threshold_ms=1000.0,
        sensitivity_threshold_ms=10000.0,
        simulation_threshold_ms=10000.0,
    )
    print("\nPerformance guardrail summary")
    print(
        "baseline_ok=",
        perf.baseline_under_threshold,
        "sensitivity_ok=",
        perf.sensitivity_under_threshold,
        "simulation_ok=",
        perf.simulation_under_threshold,
    )

    _, _ = timed("baseline solve", optimizer.solve_optimal)
    _, _ = timed("sensitivity all", optimizer.solve_sensitivity_all)

    for runs in (1000, 5000):
        _, _ = timed(
            f"simulation {runs} runs",
            lambda r=runs: optimizer.run_projection_distribution_simulation(
                SimulationConfig(num_runs=r, random_seed=42, worker_count=1)
            ),
        )

    # Robust profile comparison using a simple diagonal covariance proxy.
    # Real usage should use historical projection-error covariance.
    n = len(optimizer.players)
    cov = np.zeros((n, n), dtype=float)
    for i, p in enumerate(optimizer.players):
        std = max(1.0, 0.18 * p.projection)
        cov[i, i] = std * std

    baseline_result, _ = timed("robust baseline solve", optimizer.solve_optimal)
    box_result, _ = timed(
        "robust box solve",
        lambda: optimizer.solve_optimal(
            robust_settings=RobustSettings(enabled=True, rho=0.35, uncertainty_set=RobustUncertaintySet.BOX),
            robust_covariance=cov,
        ),
    )
    poly_result, _ = timed(
        "robust polygon solve",
        lambda: optimizer.solve_optimal(
            robust_settings=RobustSettings(enabled=True, rho=0.35, uncertainty_set=RobustUncertaintySet.POLYGON),
            robust_covariance=cov,
        ),
    )

    sample = np.random.default_rng(42).normal(
        loc=[p.projection for p in optimizer.players],
        scale=[max(1.0, 0.18 * p.projection) for p in optimizer.players],
        size=(4000, n),
    )

    idx_by_id = {p.player_id: i for i, p in enumerate(optimizer.players)}

    def lineup_scores(player_ids):
        cols = [idx_by_id[pid] for pid in player_ids]
        return sample[:, cols].sum(axis=1)

    baseline_scores = lineup_scores(baseline_result.lineup.player_ids)
    box_scores = lineup_scores(box_result.lineup.player_ids)
    poly_scores = lineup_scores(poly_result.lineup.player_ids)

    def pct(arr, q):
        return float(np.percentile(arr, q))

    print("\nDownside benchmark (synthetic projection-error draws)")
    print(f"baseline p01={pct(baseline_scores,1):.2f} p05={pct(baseline_scores,5):.2f} mean={float(np.mean(baseline_scores)):.2f}")
    print(f"box      p01={pct(box_scores,1):.2f} p05={pct(box_scores,5):.2f} mean={float(np.mean(box_scores)):.2f}")
    print(f"polygon  p01={pct(poly_scores,1):.2f} p05={pct(poly_scores,5):.2f} mean={float(np.mean(poly_scores)):.2f}")
