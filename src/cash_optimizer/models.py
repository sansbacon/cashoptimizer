from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


Position = str


class ContestProfile(str, Enum):
    H2H = "h2h"
    DOUBLE_UP = "double_up"
    SMALL_FIELD = "small_field"


class SamplingMode(str, Enum):
    INDEPENDENT = "independent"
    CORRELATED = "correlated"


class RobustUncertaintySet(str, Enum):
    BOX = "box"
    POLYGON = "polygon"


class NewsSignal(str, Enum):
    HEALTHY_CONFIRMED_ROLE = "healthy_confirmed_role"
    QUESTIONABLE_TAG = "questionable_tag"
    GAME_TIME_DECISION = "game_time_decision"
    ROLE_CHANGE_RISK = "role_change_risk"
    WEATHER_ELEVATED_RISK = "weather_elevated_risk"


@dataclass(frozen=True)
class DistributionSpec:
    distribution_type: str = "normal"
    std_dev: float | None = None
    params: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    team: str
    opponent: str
    position: Position
    salary: int
    projection: float
    status: str = "active"
    game_id: str | None = None
    correlation_group: str | None = None
    ownership: float | None = None
    game_total: float | None = None
    spread: float | None = None
    floor: float | None = None
    ceiling: float | None = None
    distribution: DistributionSpec = field(default_factory=DistributionSpec)


@dataclass(frozen=True)
class Rules:
    salary_cap: int = 50000
    roster_slots: tuple[str, ...] = (
        "QB",
        "RB1",
        "RB2",
        "WR1",
        "WR2",
        "WR3",
        "TE",
        "FLEX",
        "DST",
    )
    max_players_per_team: int | None = None
    disallow_qb_vs_opp_dst: bool = False
    max_players_per_game_environment: int | None = None
    max_non_qb_skill_players_same_team: int | None = None


@dataclass(frozen=True)
class SolverSettings:
    solver_backend: str = "cp-sat"
    projection_scale: int = 1000
    cp_sat_num_search_workers: int = 0
    cp_sat_max_time_seconds: float = 0.5
    cp_sat_relative_gap_limit: float = 0.0
    cp_sat_random_seed: int = 1729
    cp_sat_log_search_progress: bool = False
    enable_result_cache: bool = True
    result_cache_size: int = 2048
    detect_ties: bool = True
    simulation_reuse_worker_pool: bool = True
    sensitivity_worker_count: int = 1
    enable_disk_result_cache: bool = False
    disk_result_cache_dir: str | None = None
    robust_matrix_scale: int = 100


@dataclass(frozen=True)
class RobustSettings:
    enabled: bool = False
    rho: float = 0.0
    uncertainty_set: RobustUncertaintySet = RobustUncertaintySet.BOX
    correlation_sparsification_threshold: float = 0.0


@dataclass(frozen=True)
class Lineup:
    players_by_slot: Mapping[str, Player]
    player_ids: tuple[str, ...]
    salary_used: int
    projected_points: float


@dataclass(frozen=True)
class OptimizationResult:
    lineup: Lineup
    objective_value: int
    optimal_projection: float
    ties_possible: bool = False


@dataclass(frozen=True)
class SensitivityEntry:
    player_id: str
    in_optimal: bool
    forced_in_objective: int | None
    forced_out_objective: int | None
    delta_enter: float | None
    delta_exit: float | None
    tie_flag: bool


@dataclass(frozen=True)
class SensitivityFragilitySummary:
    exit_delta_threshold: float
    enter_delta_threshold: float
    fragile_selected_count: int
    near_miss_excluded_count: int
    fragility_score: float
    alert_threshold: float
    alert: bool


@dataclass(frozen=True)
class SensitivityResult:
    base_result: OptimizationResult
    entries: tuple[SensitivityEntry, ...]
    fragility_summary: SensitivityFragilitySummary | None = None


@dataclass(frozen=True)
class ContestProfileSettings:
    objective_profile: str
    lambda_risk: float
    floor_weight: float
    median_weight: float
    target_percentile: int
    max_players_per_game_environment: int
    max_non_qb_skill_players_same_team: int
    correlation_penalty_strength: float


@dataclass(frozen=True)
class SimulationConfig:
    num_runs: int = 5000
    random_seed: int = 20260901
    sampling_mode: SamplingMode = SamplingMode.INDEPENDENT
    clip_min_projection: float = 0.0
    clip_max_projection: float | None = None
    top_k_lineups_to_track: int = 50
    worker_count: int = 0
    chunk_size: int = 128


@dataclass(frozen=True)
class SimulationPlayerStat:
    player_id: str
    inclusion_rate: float
    mean_lineup_projection_when_included: float
    leverage_to_baseline: float


@dataclass(frozen=True)
class SimulationLineupStat:
    lineup_key: str
    frequency: int
    frequency_rate: float
    mean_projection: float


@dataclass(frozen=True)
class SimulationResult:
    num_runs: int
    random_seed: int
    mean_optimal_projection: float
    p05_optimal_projection: float
    p50_optimal_projection: float
    p95_optimal_projection: float
    unique_lineups: int
    player_stats: tuple[SimulationPlayerStat, ...]
    lineup_stats: tuple[SimulationLineupStat, ...]


@dataclass(frozen=True)
class CashEvaluation:
    contest_profile: ContestProfile
    lineup_projection_mean: float
    lineup_projection_std: float
    risk_adjusted_utility: float
    percentile_20_projection: float
    estimated_cash_probability: float


@dataclass(frozen=True)
class StressScenario:
    name: str
    projection_multiplier_by_position: Mapping[str, float] = field(default_factory=dict)
    projection_multiplier_global: float = 1.0
    variance_multiplier_by_position: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class StressScenarioResult:
    scenario_name: str
    projected_points: float
    salary_used: int
    lineup_player_ids: tuple[str, ...]


@dataclass(frozen=True)
class StressTestResult:
    base_projection: float
    scenario_results: tuple[StressScenarioResult, ...]
    worst_case_projection: float
    mean_stress_projection: float


@dataclass(frozen=True)
class CalibrationMetrics:
    brier_score: float
    log_loss: float
    mean_predicted_probability: float
    observed_rate: float


@dataclass(frozen=True)
class CalibrationGovernanceDecision:
    baseline_metrics: CalibrationMetrics
    candidate_metrics: CalibrationMetrics
    baseline_sample_count: int
    candidate_sample_count: int
    required_brier_improvement: float
    brier_improvement: float
    log_loss_improvement: float
    max_log_loss_increase: float
    min_samples: int
    require_parameter_versioning: bool
    candidate_parameter_version: str | None
    accepted: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationTuningRecommendation:
    contest_profile: str
    lambda_risk: float
    correlation_penalty_strength: float
    sample_count: int
    metrics: CalibrationMetrics


@dataclass(frozen=True)
class CalibrationTuningResult:
    recommendations: tuple[CalibrationTuningRecommendation, ...]


@dataclass(frozen=True)
class CashProbabilitySelectionResult:
    selected_lineup_player_ids: tuple[str, ...]
    estimated_cash_probability: float
    threshold: float
    candidate_count: int
    lineup_probabilities: Mapping[str, float]


@dataclass(frozen=True)
class NormalizedObjectiveWeights:
    w_mean: float = 1.0
    w_risk: float = 1.0
    w_cov: float = 1.0
    w_cash_prob: float = 0.0


@dataclass(frozen=True)
class NormalizedObjectiveLineupMetric:
    lineup_key: str
    mean_projection: float
    risk_std: float
    downside_cov_penalty: float
    cash_probability: float
    normalized_score: float


@dataclass(frozen=True)
class NormalizedObjectiveSelectionResult:
    selected_lineup_player_ids: tuple[str, ...]
    candidate_count: int
    weights: NormalizedObjectiveWeights
    lineup_metrics: tuple[NormalizedObjectiveLineupMetric, ...]


@dataclass(frozen=True)
class NewsSignalPolicy:
    signal: NewsSignal
    mean_penalty: float
    variance_multiplier: float


@dataclass(frozen=True)
class NewsVolatilityAdjustmentResult:
    adjusted_projections: tuple[float, ...]
    adjusted_players: tuple[Player, ...]
    penalties_by_player_id: Mapping[str, float]
    variance_multiplier_by_player_id: Mapping[str, float]


@dataclass(frozen=True)
class ContestProfileOptimizationResult:
    contest_profile: ContestProfile
    objective_profile: str
    selected_lineup_player_ids: tuple[str, ...]
    projected_points_estimate: float
    details: Mapping[str, float | int | str | bool]


@dataclass(frozen=True)
class HumanHeuristicBaselineResult:
    trials: int
    feasible_trials: int
    best_lineup: Lineup | None
    best_projection: float
    mean_projection: float


@dataclass(frozen=True)
class HumanVsOptimizerComparison:
    optimizer_projection: float
    human_best_projection: float
    human_mean_projection: float
    edge_vs_human_best: float
    edge_vs_human_mean: float
    trials: int
    feasible_trials: int


@dataclass(frozen=True)
class PositionPredictionMetric:
    position: str
    model_name: str
    rmse: float
    sample_count: int


@dataclass(frozen=True)
class PredictionModelSelectionResult:
    metrics: tuple[PositionPredictionMetric, ...]
    best_model_by_position: Mapping[str, str]


@dataclass(frozen=True)
class WeeklyEdgeRow:
    slate_label: str
    optimizer_projection: float
    human_best_projection: float
    human_mean_projection: float
    edge_vs_human_best: float
    edge_vs_human_mean: float
    trials: int
    feasible_trials: int
    cash_line: float | None = None
    optimizer_above_cash: bool | None = None
    human_mean_above_cash: bool | None = None


@dataclass(frozen=True)
class EdgeTrendResult:
    rows: tuple[WeeklyEdgeRow, ...]
    mean_edge_vs_human_best: float
    mean_edge_vs_human_mean: float
    optimizer_cash_rate: float | None = None
    human_mean_cash_rate: float | None = None


@dataclass(frozen=True)
class PerformanceBenchmarkResult:
    baseline_solve_ms: float
    sensitivity_ms: float
    simulation_runs: int
    simulation_ms: float
    simulation_runs_per_second: float
    baseline_under_threshold: bool
    sensitivity_under_threshold: bool
    simulation_under_threshold: bool


@dataclass(frozen=True)
class ReadinessGateResult:
    accepted: bool
    reasons: tuple[str, ...]
    deterministic_optimal: bool
    lineup_valid: bool
    sensitivity_coverage_complete: bool
    benchmark: PerformanceBenchmarkResult


@dataclass(frozen=True)
class RolloutRecommendation:
    stage: str
    can_promote: bool
    blockers: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkThresholdRecommendation:
    sample_count: int
    percentile: float
    safety_multiplier: float
    baseline_threshold_ms: float
    sensitivity_threshold_ms: float
    simulation_threshold_ms: float


@dataclass(frozen=True)
class GovernanceCheckResult:
    accepted: bool
    reasons: tuple[str, ...]
    readiness: ReadinessGateResult
    rollout: RolloutRecommendation
