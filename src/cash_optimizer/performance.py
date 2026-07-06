from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import time

from .models import (
    BenchmarkThresholdRecommendation,
    GovernanceCheckResult,
    PerformanceBenchmarkResult,
    ReadinessGateResult,
    RolloutRecommendation,
    SimulationConfig,
)
from .optimizer import CashOptimizer


def run_performance_benchmarks(
    optimizer: CashOptimizer,
    simulation_runs: int = 1000,
    baseline_threshold_ms: float = 1000.0,
    sensitivity_threshold_ms: float = 10000.0,
    simulation_threshold_ms: float = 10000.0,
) -> PerformanceBenchmarkResult:
    start = time.perf_counter()
    optimizer.solve_optimal()
    baseline_ms = (time.perf_counter() - start) * 1000.0

    start = time.perf_counter()
    optimizer.solve_sensitivity_all()
    sensitivity_ms = (time.perf_counter() - start) * 1000.0

    start = time.perf_counter()
    optimizer.run_projection_distribution_simulation(
        SimulationConfig(
            num_runs=simulation_runs,
            random_seed=optimizer.solver_settings.cp_sat_random_seed,
            worker_count=1,
        )
    )
    simulation_ms = (time.perf_counter() - start) * 1000.0
    simulation_runs_per_second = float(simulation_runs / max(1e-9, simulation_ms / 1000.0))

    return PerformanceBenchmarkResult(
        baseline_solve_ms=float(baseline_ms),
        sensitivity_ms=float(sensitivity_ms),
        simulation_runs=int(simulation_runs),
        simulation_ms=float(simulation_ms),
        simulation_runs_per_second=float(simulation_runs_per_second),
        baseline_under_threshold=baseline_ms <= baseline_threshold_ms,
        sensitivity_under_threshold=sensitivity_ms <= sensitivity_threshold_ms,
        simulation_under_threshold=simulation_ms <= simulation_threshold_ms,
    )


def append_benchmark_history(
    path: Path,
    result: PerformanceBenchmarkResult,
    parameter_version: str = "v1",
    note: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "parameter_version": parameter_version,
        "note": note,
        **asdict(result),
    }
    header = list(row.keys())
    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def run_readiness_gate(
    optimizer: CashOptimizer,
    simulation_runs: int = 200,
    baseline_threshold_ms: float = 1000.0,
    sensitivity_threshold_ms: float = 10000.0,
    simulation_threshold_ms: float = 10000.0,
) -> ReadinessGateResult:
    reasons: list[str] = []

    optimal_a = optimizer.solve_optimal()
    optimal_b = optimizer.solve_optimal()
    deterministic_optimal = (
        optimal_a.lineup.player_ids == optimal_b.lineup.player_ids
        and optimal_a.optimal_projection == optimal_b.optimal_projection
    )
    if not deterministic_optimal:
        reasons.append("Optimal solve is not deterministic across repeated runs")

    lineup_valid = (
        len(optimal_a.lineup.player_ids) == len(optimizer.rules.roster_slots)
        and optimal_a.lineup.salary_used <= optimizer.rules.salary_cap
    )
    if not lineup_valid:
        reasons.append("Optimal lineup failed roster size or salary-cap sanity checks")

    sensitivity = optimizer.solve_sensitivity_all()
    sensitivity_coverage_complete = len(sensitivity.entries) == len(optimizer.players)
    if not sensitivity_coverage_complete:
        reasons.append("Sensitivity coverage does not include all active players")

    benchmark = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=simulation_runs,
        baseline_threshold_ms=baseline_threshold_ms,
        sensitivity_threshold_ms=sensitivity_threshold_ms,
        simulation_threshold_ms=simulation_threshold_ms,
    )
    if not benchmark.baseline_under_threshold:
        reasons.append("Baseline solve exceeded benchmark threshold")
    if not benchmark.sensitivity_under_threshold:
        reasons.append("Sensitivity solve exceeded benchmark threshold")
    if not benchmark.simulation_under_threshold:
        reasons.append("Simulation benchmark exceeded threshold")

    return ReadinessGateResult(
        accepted=(len(reasons) == 0),
        reasons=tuple(reasons),
        deterministic_optimal=deterministic_optimal,
        lineup_valid=lineup_valid,
        sensitivity_coverage_complete=sensitivity_coverage_complete,
        benchmark=benchmark,
    )


def recommend_rollout_stage(readiness: ReadinessGateResult) -> RolloutRecommendation:
    blockers = list(readiness.reasons)
    notes: list[str] = []

    if readiness.accepted:
        stage = "phase5_polish"
        notes.append("All readiness checks passed; candidate for broad rollout")
    elif readiness.lineup_valid and readiness.sensitivity_coverage_complete:
        stage = "phase4_validation"
        notes.append("Core functional checks pass; resolve benchmark/determinism blockers before promotion")
    elif readiness.lineup_valid:
        stage = "phase2_sensitivity"
        notes.append("Lineup generation is valid but sensitivity coverage needs remediation")
    else:
        stage = "phase1_core_optimizer"
        notes.append("Core optimizer validity checks must pass before phased rollout")

    if readiness.benchmark.baseline_under_threshold and readiness.benchmark.sensitivity_under_threshold:
        notes.append("Performance envelope is acceptable for baseline and sensitivity")
    else:
        notes.append("Performance thresholds require calibration or optimization")

    return RolloutRecommendation(
        stage=stage,
        can_promote=(len(blockers) == 0),
        blockers=tuple(blockers),
        notes=tuple(notes),
    )


def calibrate_benchmark_thresholds_from_history(
    history_csv: Path,
    percentile: float = 0.95,
    safety_multiplier: float = 1.1,
    min_samples: int = 5,
) -> BenchmarkThresholdRecommendation:
    if percentile <= 0 or percentile > 1:
        raise ValueError("percentile must be in (0, 1]")
    if safety_multiplier <= 0:
        raise ValueError("safety_multiplier must be > 0")
    if min_samples <= 0:
        raise ValueError("min_samples must be > 0")
    if not history_csv.exists() or not history_csv.is_file():
        raise FileNotFoundError(f"Benchmark history CSV not found: {history_csv}")

    baseline_values: list[float] = []
    sensitivity_values: list[float] = []
    simulation_values: list[float] = []
    with history_csv.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"baseline_solve_ms", "sensitivity_ms", "simulation_ms"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "Benchmark history CSV must include columns: baseline_solve_ms, sensitivity_ms, simulation_ms"
            )
        for row in reader:
            baseline_values.append(float(row["baseline_solve_ms"]))
            sensitivity_values.append(float(row["sensitivity_ms"]))
            simulation_values.append(float(row["simulation_ms"]))

    sample_count = len(baseline_values)
    if sample_count < min_samples:
        raise ValueError(f"Benchmark history has {sample_count} rows; requires at least {min_samples}")

    baseline_thr = _percentile(baseline_values, percentile) * safety_multiplier
    sensitivity_thr = _percentile(sensitivity_values, percentile) * safety_multiplier
    simulation_thr = _percentile(simulation_values, percentile) * safety_multiplier

    return BenchmarkThresholdRecommendation(
        sample_count=sample_count,
        percentile=percentile,
        safety_multiplier=safety_multiplier,
        baseline_threshold_ms=float(baseline_thr),
        sensitivity_threshold_ms=float(sensitivity_thr),
        simulation_threshold_ms=float(simulation_thr),
    )


def run_governance_check(
    readiness: ReadinessGateResult,
    rollout: RolloutRecommendation,
    require_clean: bool = True,
    minimum_stage: str = "phase4_validation",
) -> GovernanceCheckResult:
    reasons: list[str] = []

    if require_clean and not readiness.accepted:
        reasons.append("Readiness gate has blockers")

    if _stage_rank(rollout.stage) < _stage_rank(minimum_stage):
        reasons.append(f"Recommended stage {rollout.stage} is below required minimum {minimum_stage}")

    if require_clean and not rollout.can_promote:
        reasons.append("Rollout recommendation indicates blockers")

    return GovernanceCheckResult(
        accepted=(len(reasons) == 0),
        reasons=tuple(reasons),
        readiness=readiness,
        rollout=rollout,
    )


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot compute percentile on empty data")
    if len(ordered) == 1:
        return ordered[0]
    idx = p * (len(ordered) - 1)
    low = int(idx)
    high = min(low + 1, len(ordered) - 1)
    frac = idx - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def _stage_rank(stage: str) -> int:
    order = {
        "phase1_core_optimizer": 1,
        "phase2_sensitivity": 2,
        "phase3_performance": 3,
        "phase4_validation": 4,
        "phase5_polish": 5,
    }
    return order.get(stage, 0)
