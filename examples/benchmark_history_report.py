from __future__ import annotations

from pathlib import Path

from cash_optimizer import (
    CashOptimizer,
    Rules,
    RuntimeDefaults,
    append_benchmark_history,
    run_performance_benchmarks,
)
from cash_optimizer.io import load_players_from_dk_csv


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    players = load_players_from_dk_csv(root / "tests" / "proj.csv")
    optimizer = CashOptimizer(players=players, rules=Rules())

    defaults = RuntimeDefaults()
    result = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=defaults.simulation_num_runs_default,
        baseline_threshold_ms=1000.0,
        sensitivity_threshold_ms=10000.0,
        simulation_threshold_ms=10000.0,
    )

    history_path = root / "outputs" / "benchmark_history.csv"
    append_benchmark_history(
        path=history_path,
        result=result,
        parameter_version=defaults.parameter_version,
        note="local benchmark history append",
    )
    print(f"Wrote benchmark history row to {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
