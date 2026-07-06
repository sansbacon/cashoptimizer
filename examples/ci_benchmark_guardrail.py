from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from cash_optimizer import CashOptimizer, Rules, run_performance_benchmarks
from cash_optimizer.io import load_players_from_dk_csv


_BENCHMARK_PROFILES: dict[str, tuple[float, float, float]] = {
    "strict": (1000.0, 10000.0, 10000.0),
    "ci": (5000.0, 60000.0, 60000.0),
    "relaxed": (10000.0, 120000.0, 120000.0),
}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _resolve_thresholds() -> tuple[float, float, float]:
    profile = os.getenv("BENCH_PROFILE", "ci").strip().lower() or "ci"
    scale = _env_float("BENCH_THRESHOLD_SCALE", 1.0)
    if scale <= 0:
        raise ValueError("BENCH_THRESHOLD_SCALE must be > 0")

    baseline_default, sensitivity_default, simulation_default = _BENCHMARK_PROFILES.get(
        profile,
        _BENCHMARK_PROFILES["ci"],
    )

    baseline_threshold = _env_float("BENCH_BASELINE_MS", baseline_default * scale)
    sensitivity_threshold = _env_float("BENCH_SENSITIVITY_MS", sensitivity_default * scale)
    simulation_threshold = _env_float("BENCH_SIMULATION_MS", simulation_default * scale)
    return baseline_threshold, sensitivity_threshold, simulation_threshold


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    input_csv = root / "tests" / "proj.csv"

    players = load_players_from_dk_csv(input_csv)
    optimizer = CashOptimizer(players=players, rules=Rules())

    simulation_runs = _env_int("BENCH_SIMULATION_RUNS", 200)
    baseline_threshold, sensitivity_threshold, simulation_threshold = _resolve_thresholds()

    result = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=simulation_runs,
        baseline_threshold_ms=baseline_threshold,
        sensitivity_threshold_ms=sensitivity_threshold,
        simulation_threshold_ms=simulation_threshold,
    )
    payload = asdict(result)
    print(json.dumps(payload, indent=2, sort_keys=True))

    passed = (
        result.baseline_under_threshold
        and result.sensitivity_under_threshold
        and result.simulation_under_threshold
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
