from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
import hashlib
import pickle
from typing import Iterable, Sequence

import numpy as np
from ortools.sat.python import cp_model

from .baselines import compare_optimizer_to_human_baseline, run_human_heuristic_baseline
from .cash_metrics import evaluate_cash_profiles, get_contest_profile_settings
from .models import (
    ContestProfileOptimizationResult,
    CashProbabilitySelectionResult,
    CashEvaluation,
    ContestProfileSettings,
    ContestProfile,
    HumanHeuristicBaselineResult,
    HumanVsOptimizerComparison,
    Lineup,
    NormalizedObjectiveSelectionResult,
    NormalizedObjectiveWeights,
    OptimizationResult,
    NewsSignal,
    NewsVolatilityAdjustmentResult,
    Player,
    RobustSettings,
    RobustUncertaintySet,
    Rules,
    SensitivityEntry,
    SensitivityResult,
    SimulationConfig,
    SimulationLineupStat,
    SimulationPlayerStat,
    SimulationResult,
    SolverSettings,
    StressScenario,
    StressTestResult,
)
from .objective_selection import select_best_lineup_by_normalized_objective
from .projections import (
    apply_mean_penalties,
    apply_news_volatility_adjustments,
    blend_cash_projections,
    build_ensemble_shrunk_projections,
)
from .robust import matrix_sqrt_psd, sparsify_covariance_by_correlation_threshold
from .sampling import sample_projection_matrix
from .sensitivity import compute_fragility_summary
from .selection import select_best_lineup_by_cash_probability
from .stress import run_stress_test


_DEFAULT_STATUS_BLOCKLIST = {"out", "inactive", "ir"}


class CashOptimizer:
    def __init__(
        self,
        players: Sequence[Player],
        rules: Rules | None = None,
        solver_settings: SolverSettings | None = None,
    ) -> None:
        self.rules = rules or Rules()
        self.solver_settings = solver_settings or SolverSettings()
        self.players = tuple(p for p in players if p.status.lower() not in _DEFAULT_STATUS_BLOCKLIST)
        if len(self.players) < len(self.rules.roster_slots):
            raise ValueError("Not enough active players to fill roster slots")
        self._index_by_id = {p.player_id: idx for idx, p in enumerate(self.players)}
        self._result_cache: OrderedDict[tuple, OptimizationResult] = OrderedDict()
        self._sim_pool: ProcessPoolExecutor | None = None
        self._sim_pool_workers: int | None = None
        self._disk_cache_dir: Path | None = None
        if self.solver_settings.enable_disk_result_cache:
            configured = self.solver_settings.disk_result_cache_dir
            self._disk_cache_dir = Path(configured) if configured else Path(".cash_optimizer_cache")
            self._disk_cache_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        if self._sim_pool is not None:
            self._sim_pool.shutdown(wait=True, cancel_futures=False)
            self._sim_pool = None
            self._sim_pool_workers = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def solve_optimal(
        self,
        projections: Sequence[float] | None = None,
        robust_settings: RobustSettings | None = None,
        robust_covariance: Sequence[Sequence[float]] | None = None,
    ) -> OptimizationResult:
        return self._solve_once(
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

    def solve_forced_in(
        self,
        player_id: str,
        projections: Sequence[float] | None = None,
        robust_settings: RobustSettings | None = None,
        robust_covariance: Sequence[Sequence[float]] | None = None,
    ) -> OptimizationResult:
        return self._solve_once(
            forced_in={player_id},
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

    def solve_forced_out(
        self,
        player_id: str,
        projections: Sequence[float] | None = None,
        robust_settings: RobustSettings | None = None,
        robust_covariance: Sequence[Sequence[float]] | None = None,
    ) -> OptimizationResult:
        return self._solve_once(
            forced_out={player_id},
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

    def solve_sensitivity_all(
        self,
        projections: Sequence[float] | None = None,
        robust_settings: RobustSettings | None = None,
        robust_covariance: Sequence[Sequence[float]] | None = None,
        fragility_exit_delta_threshold: float = 0.75,
        fragility_enter_delta_threshold: float = 0.75,
        fragility_alert_threshold: float = 3.0,
    ) -> SensitivityResult:
        base = self.solve_optimal(
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )
        base_ids = set(base.lineup.player_ids)
        resolved_projections = self._resolve_projections(projections)
        entries: list[SensitivityEntry] = []

        worker_count = max(1, int(self.solver_settings.sensitivity_worker_count))
        forced_projection_by_player: dict[str, float] = {}

        if worker_count == 1:
            for player in self.players:
                if player.player_id in base_ids:
                    forced_out = self.solve_forced_out(
                        player.player_id,
                        projections=resolved_projections,
                        robust_settings=robust_settings,
                        robust_covariance=robust_covariance,
                    )
                    forced_projection_by_player[player.player_id] = forced_out.optimal_projection
                else:
                    forced_in = self.solve_forced_in(
                        player.player_id,
                        projections=resolved_projections,
                        robust_settings=robust_settings,
                        robust_covariance=robust_covariance,
                    )
                    forced_projection_by_player[player.player_id] = forced_in.optimal_projection
        else:
            payload = {
                "players": self.players,
                "rules": self.rules,
                "solver_settings": replace(
                    self.solver_settings,
                    cp_sat_num_search_workers=1,
                    enable_result_cache=False,
                    detect_ties=False,
                ),
                "projections": tuple(resolved_projections),
                "robust_settings": robust_settings,
                "robust_covariance": robust_covariance,
            }
            with ProcessPoolExecutor(max_workers=worker_count) as pool:
                futures = [
                    pool.submit(
                        _solve_sensitivity_entry_worker,
                        payload,
                        player.player_id,
                        player.player_id in base_ids,
                    )
                    for player in self.players
                ]
                for future in futures:
                    pid, forced_projection = future.result()
                    forced_projection_by_player[pid] = forced_projection

        for player in self.players:
            forced_projection = forced_projection_by_player[player.player_id]
            if player.player_id in base_ids:
                delta_exit = max(0.0, base.optimal_projection - forced_projection)
                entries.append(
                    SensitivityEntry(
                        player_id=player.player_id,
                        in_optimal=True,
                        forced_in_objective=self._to_scaled_int(base.optimal_projection),
                        forced_out_objective=self._to_scaled_int(forced_projection),
                        delta_enter=None,
                        delta_exit=delta_exit,
                        tie_flag=delta_exit == 0.0,
                    )
                )
            else:
                delta_enter = max(0.0, base.optimal_projection - forced_projection)
                entries.append(
                    SensitivityEntry(
                        player_id=player.player_id,
                        in_optimal=False,
                        forced_in_objective=self._to_scaled_int(forced_projection),
                        forced_out_objective=None,
                        delta_enter=delta_enter,
                        delta_exit=None,
                        tie_flag=delta_enter == 0.0,
                    )
                )

        entries.sort(key=lambda e: e.player_id)
        fragility_summary = compute_fragility_summary(
            entries=tuple(entries),
            exit_delta_threshold=fragility_exit_delta_threshold,
            enter_delta_threshold=fragility_enter_delta_threshold,
            alert_threshold=fragility_alert_threshold,
        )
        return SensitivityResult(
            base_result=base,
            entries=tuple(entries),
            fragility_summary=fragility_summary,
        )

    def run_many_projection_sets(
        self,
        list_of_projection_vectors: Iterable[Sequence[float]],
    ) -> tuple[OptimizationResult, ...]:
        return tuple(self.solve_optimal(projections=vector) for vector in list_of_projection_vectors)

    def generate_candidate_lineups(
        self,
        num_candidates: int = 25,
        projections: Sequence[float] | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        if num_candidates <= 0:
            raise ValueError("num_candidates must be > 0")

        base = self.solve_optimal(projections=projections)
        unique: OrderedDict[tuple[str, ...], None] = OrderedDict()
        unique[base.lineup.player_ids] = None

        if len(unique) >= num_candidates:
            return tuple(unique.keys())

        # Generate alternatives by forcing out each player from current candidates.
        frontier = [base.lineup.player_ids]
        while frontier and len(unique) < num_candidates:
            current = frontier.pop(0)
            for player_id in current:
                alt = self._solve_once(
                    forced_out={player_id},
                    projections=projections,
                    use_cache=True,
                )
                ids = alt.lineup.player_ids
                if ids not in unique:
                    unique[ids] = None
                    frontier.append(ids)
                    if len(unique) >= num_candidates:
                        break

        return tuple(unique.keys())

    def run_many_sampled_sets(
        self,
        sample_generator: Iterable[Sequence[float]],
        num_runs: int,
        top_k_lineups: int = 50,
        random_seed: int = -1,
    ) -> SimulationResult:
        aggregator = _SimulationAggregator(
            players=self.players,
            roster_size=len(self.rules.roster_slots),
            top_k_lineups=top_k_lineups,
            random_seed=random_seed,
        )
        runs_completed = 0
        for vec in sample_generator:
            if num_runs > 0 and runs_completed >= num_runs:
                break
            lineup_ids, projection = self._solve_projection_to_stat(vec, use_cache=False)
            aggregator.add_run(lineup_ids, projection)
            runs_completed += 1
        return aggregator.finalize()

    def select_best_cash_lineup_by_probability(
        self,
        threshold: float,
        num_candidates: int = 25,
        simulation_config: SimulationConfig | None = None,
        projections: Sequence[float] | None = None,
    ) -> CashProbabilitySelectionResult:
        cfg = simulation_config or SimulationConfig(num_runs=2000, random_seed=20260901, worker_count=1)
        candidate_lineups = self.generate_candidate_lineups(
            num_candidates=num_candidates,
            projections=projections,
        )
        sample_matrix = sample_projection_matrix(self.players, cfg)
        return select_best_lineup_by_cash_probability(
            candidate_lineups=candidate_lineups,
            players=self.players,
            sample_projection_matrix=sample_matrix,
            threshold=threshold,
        )

    def select_best_lineup_by_normalized_objective(
        self,
        weights: NormalizedObjectiveWeights,
        num_candidates: int = 25,
        simulation_config: SimulationConfig | None = None,
        cash_threshold: float | None = None,
        projections: Sequence[float] | None = None,
    ) -> NormalizedObjectiveSelectionResult:
        cfg = simulation_config or SimulationConfig(num_runs=2000, random_seed=20260901, worker_count=1)
        candidate_lineups = self.generate_candidate_lineups(
            num_candidates=num_candidates,
            projections=projections,
        )
        sample_matrix = sample_projection_matrix(self.players, cfg)
        return select_best_lineup_by_normalized_objective(
            candidate_lineups=candidate_lineups,
            players=self.players,
            sample_projection_matrix=sample_matrix,
            weights=weights,
            cash_threshold=cash_threshold,
        )

    def run_projection_distribution_simulation(
        self,
        config: SimulationConfig,
    ) -> SimulationResult:
        sampled_matrix = sample_projection_matrix(self.players, config)
        if sampled_matrix.shape[0] != config.num_runs:
            raise ValueError("Sample matrix row count mismatch")

        projections_by_run = [row.tolist() for row in sampled_matrix]
        worker_count = config.worker_count if config.worker_count > 0 else 1
        aggregator = _SimulationAggregator(
            players=self.players,
            roster_size=len(self.rules.roster_slots),
            top_k_lineups=config.top_k_lineups_to_track,
            random_seed=config.random_seed,
        )

        if worker_count == 1:
            for row in projections_by_run:
                lineup_ids, projection = self._solve_projection_to_stat(row, use_cache=False)
                aggregator.add_run(lineup_ids, projection)
        else:
            payload = {
                "players": self.players,
                "rules": self.rules,
                "solver_settings": replace(
                    self.solver_settings,
                    cp_sat_num_search_workers=1,
                    enable_result_cache=False,
                    detect_ties=False,
                ),
            }
            if self.solver_settings.simulation_reuse_worker_pool:
                pool = self._get_or_create_sim_pool(worker_count)
                futures = [
                    pool.submit(_solve_worker_stats, payload, chunk)
                    for chunk in _chunked(projections_by_run, config.chunk_size)
                ]
                for future in futures:
                    for lineup_ids, projection in future.result():
                        aggregator.add_run(lineup_ids, projection)
            else:
                with ProcessPoolExecutor(max_workers=worker_count) as pool:
                    futures = [
                        pool.submit(_solve_worker_stats, payload, chunk)
                        for chunk in _chunked(projections_by_run, config.chunk_size)
                    ]
                    for future in futures:
                        for lineup_ids, projection in future.result():
                            aggregator.add_run(lineup_ids, projection)

        return aggregator.finalize()

    def evaluate_cash_profiles(
        self,
        simulation_result: SimulationResult,
        threshold: float,
    ) -> tuple[CashEvaluation, ...]:
        return evaluate_cash_profiles(simulation_result=simulation_result, threshold=threshold)

    def get_contest_profile_settings(self, contest_profile: ContestProfile) -> ContestProfileSettings:
        return get_contest_profile_settings(contest_profile)

    def build_cash_blended_projections(
        self,
        median_by_player_id: dict[str, float],
        floor_by_player_id: dict[str, float],
        w_median: float = 0.7,
        w_floor: float = 0.3,
    ) -> list[float]:
        return blend_cash_projections(
            players=self.players,
            median_by_player_id=median_by_player_id,
            floor_by_player_id=floor_by_player_id,
            w_median=w_median,
            w_floor=w_floor,
        )

    def build_ensemble_shrunk_projections(
        self,
        projections_by_source: dict[str, dict[str, float]],
        source_weights: dict[str, float] | None = None,
        shrink_strength: float = 0.25,
        disagreement_penalty: float = 0.0,
        clip_min: float = 0.0,
    ) -> list[float]:
        return build_ensemble_shrunk_projections(
            players=self.players,
            projections_by_source=projections_by_source,
            source_weights=source_weights,
            shrink_strength=shrink_strength,
            disagreement_penalty=disagreement_penalty,
            clip_min=clip_min,
        )

    def apply_news_volatility_layer(
        self,
        signal_by_player_id: dict[str, NewsSignal | str],
        base_projections: Sequence[float] | None = None,
        clip_min: float = 0.0,
    ) -> NewsVolatilityAdjustmentResult:
        resolved = self._resolve_projections(base_projections)
        return apply_news_volatility_adjustments(
            players=self.players,
            base_projections=resolved,
            signal_by_player_id=signal_by_player_id,
            clip_min=clip_min,
        )

    def optimize_for_contest_profile(
        self,
        contest_profile: ContestProfile,
        median_by_player_id: dict[str, float] | None = None,
        floor_by_player_id: dict[str, float] | None = None,
        cash_threshold: float | None = None,
        num_candidates: int = 25,
        simulation_config: SimulationConfig | None = None,
        news_signal_by_player_id: dict[str, NewsSignal | str] | None = None,
    ) -> ContestProfileOptimizationResult:
        profile = self.get_contest_profile_settings(contest_profile)
        cfg = simulation_config or SimulationConfig(num_runs=2000, random_seed=20260901, worker_count=1)

        projections: Sequence[float] | None = None
        if median_by_player_id is not None and floor_by_player_id is not None:
            projections = self.build_cash_blended_projections(
                median_by_player_id=median_by_player_id,
                floor_by_player_id=floor_by_player_id,
                w_median=profile.median_weight,
                w_floor=profile.floor_weight,
            )

        if news_signal_by_player_id:
            news_adj = self.apply_news_volatility_layer(
                signal_by_player_id=news_signal_by_player_id,
                base_projections=projections,
            )
            projections = list(news_adj.adjusted_projections)

        if profile.objective_profile == "cash_probability":
            threshold = float(cash_threshold if cash_threshold is not None else 130.0)
            selected = self.select_best_cash_lineup_by_probability(
                threshold=threshold,
                num_candidates=num_candidates,
                simulation_config=cfg,
                projections=projections,
            )
            return ContestProfileOptimizationResult(
                contest_profile=contest_profile,
                objective_profile=profile.objective_profile,
                selected_lineup_player_ids=selected.selected_lineup_player_ids,
                projected_points_estimate=float(0.0),
                details={
                    "estimated_cash_probability": float(selected.estimated_cash_probability),
                    "threshold": float(selected.threshold),
                    "candidate_count": int(selected.candidate_count),
                    "lambda_risk": float(profile.lambda_risk),
                },
            )

        normalized = self.select_best_lineup_by_normalized_objective(
            weights=NormalizedObjectiveWeights(
                w_mean=1.0,
                w_risk=float(profile.lambda_risk),
                w_cov=float(profile.correlation_penalty_strength),
                w_cash_prob=0.0,
            ),
            num_candidates=num_candidates,
            simulation_config=cfg,
            cash_threshold=cash_threshold,
            projections=projections,
        )
        metrics = {m.lineup_key: m for m in normalized.lineup_metrics}
        key = "|".join(normalized.selected_lineup_player_ids)
        best_metric = metrics[key]
        return ContestProfileOptimizationResult(
            contest_profile=contest_profile,
            objective_profile=profile.objective_profile,
            selected_lineup_player_ids=normalized.selected_lineup_player_ids,
            projected_points_estimate=float(best_metric.mean_projection),
            details={
                "normalized_score": float(best_metric.normalized_score),
                "risk_std": float(best_metric.risk_std),
                "downside_cov_penalty": float(best_metric.downside_cov_penalty),
                "candidate_count": int(normalized.candidate_count),
                "lambda_risk": float(profile.lambda_risk),
            },
        )

    def apply_projection_penalties(
        self,
        base_projections: Sequence[float],
        penalties_by_player_id: dict[str, float],
        clip_min: float = 0.0,
    ) -> list[float]:
        return apply_mean_penalties(
            players=self.players,
            base_projections=base_projections,
            penalties_by_player_id=penalties_by_player_id,
            clip_min=clip_min,
        )

    def run_stress_test(
        self,
        base_projections: Sequence[float] | None = None,
        scenarios: Sequence[StressScenario] | None = None,
    ) -> StressTestResult:
        return run_stress_test(
            optimizer=self,
            base_projections=base_projections,
            scenarios=scenarios,
        )

    def run_human_heuristic_baseline(
        self,
        projections: Sequence[float] | None = None,
        trials: int = 1000,
        top_n_per_slot: int = 10,
        random_seed: int | None = None,
    ) -> HumanHeuristicBaselineResult:
        seed = self.solver_settings.cp_sat_random_seed if random_seed is None else random_seed
        return run_human_heuristic_baseline(
            players=self.players,
            rules=self.rules,
            projections=projections,
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            random_seed=seed,
        )

    def compare_against_human_heuristic(
        self,
        projections: Sequence[float] | None = None,
        trials: int = 1000,
        top_n_per_slot: int = 10,
        random_seed: int | None = None,
    ) -> HumanVsOptimizerComparison:
        optimal = self.solve_optimal(projections=projections)
        baseline = self.run_human_heuristic_baseline(
            projections=projections,
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            random_seed=random_seed,
        )
        return compare_optimizer_to_human_baseline(
            optimizer_projection=optimal.optimal_projection,
            baseline=baseline,
        )

    def _solve_once(
        self,
        forced_in: set[str] | None = None,
        forced_out: set[str] | None = None,
        projections: Sequence[float] | None = None,
        robust_settings: RobustSettings | None = None,
        robust_covariance: Sequence[Sequence[float]] | None = None,
        use_cache: bool = True,
    ) -> OptimizationResult:
        forced_in = forced_in or set()
        forced_out = forced_out or set()
        if forced_in & forced_out:
            raise ValueError("A player cannot be forced in and forced out simultaneously")

        backend = str(self.solver_settings.solver_backend or "cp-sat").strip().lower()
        if backend in {"cp-sat", "cpsat", "cp_sat"}:
            return self._solve_once_cp_sat(
                forced_in=forced_in,
                forced_out=forced_out,
                projections=projections,
                robust_settings=robust_settings,
                robust_covariance=robust_covariance,
                use_cache=use_cache,
            )
        if backend == "highs":
            return self._solve_once_highs(
                forced_in=forced_in,
                forced_out=forced_out,
                projections=projections,
                robust_settings=robust_settings,
                robust_covariance=robust_covariance,
                use_cache=use_cache,
            )
        raise ValueError(f"Unsupported solver backend: {self.solver_settings.solver_backend}")

    def _solve_once_cp_sat(
        self,
        forced_in: set[str],
        forced_out: set[str],
        projections: Sequence[float] | None,
        robust_settings: RobustSettings | None,
        robust_covariance: Sequence[Sequence[float]] | None,
        use_cache: bool,
    ) -> OptimizationResult:

        projection_values = self._resolve_projections(projections)
        projection_scaled = [int(round(value * self.solver_settings.projection_scale)) for value in projection_values]
        robust_data = self._resolve_robust_inputs(
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

        cache_key = self._make_cache_key(
            projection_scaled,
            forced_in,
            forced_out,
            robust_data,
        )
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        model, slot_vars, selected_vars = self._build_model(
            projection_scaled=projection_scaled,
            forced_in=forced_in,
            forced_out=forced_out,
            robust_data=robust_data,
            add_objective=True,
        )

        solver = cp_model.CpSolver()
        self._apply_solver_settings(solver)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise ValueError("No feasible lineup found")

        slot_to_player: dict[str, Player] = {}
        selected_indices: list[int] = []
        for (idx, slot), var in slot_vars.items():
            if solver.Value(var) == 1:
                player = self.players[idx]
                slot_to_player[slot] = player
                selected_indices.append(idx)

        selected_players = list(slot_to_player.values())
        selected_player_ids = [p.player_id for p in selected_players]
        salary_used = sum(player.salary for player in selected_players)
        total_projection = sum(projection_values[idx] for idx in selected_indices)

        ties_possible = False
        if self.solver_settings.detect_ties:
            ties_possible = self._has_projection_tie(
                projection_scaled=projection_scaled,
                selected_indices=selected_indices,
                forced_in=forced_in,
                forced_out=forced_out,
            )

        ordered_ids = tuple(sorted(selected_player_ids))
        lineup = Lineup(
            players_by_slot=dict(sorted(slot_to_player.items(), key=lambda item: self.rules.roster_slots.index(item[0]))),
            player_ids=ordered_ids,
            salary_used=salary_used,
            projected_points=total_projection,
        )

        projection_objective = self._to_scaled_int(total_projection)
        result = OptimizationResult(
            lineup=lineup,
            objective_value=projection_objective,
            optimal_projection=total_projection,
            ties_possible=ties_possible,
        )
        if use_cache:
            self._cache_set(cache_key, result)
        return result

    def _solve_once_highs(
        self,
        forced_in: set[str],
        forced_out: set[str],
        projections: Sequence[float] | None,
        robust_settings: RobustSettings | None,
        robust_covariance: Sequence[Sequence[float]] | None,
        use_cache: bool,
    ) -> OptimizationResult:
        try:
            from highspy import Highs, HighsModelStatus, HighsVarType
        except Exception as exc:  # pragma: no cover - dependency edge
            raise ValueError("solver_backend=highs requires installing highspy") from exc

        projection_values = self._resolve_projections(projections)
        projection_scaled = [int(round(value * self.solver_settings.projection_scale)) for value in projection_values]
        robust_data = self._resolve_robust_inputs(
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

        cache_key = self._make_cache_key(
            projection_scaled,
            forced_in,
            forced_out,
            robust_data,
        )
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        highs = Highs()
        highs.setOptionValue("output_flag", False)
        if self.solver_settings.cp_sat_max_time_seconds > 0:
            highs.setOptionValue("time_limit", float(self.solver_settings.cp_sat_max_time_seconds))
        if self.solver_settings.cp_sat_num_search_workers > 0:
            highs.setOptionValue("threads", int(self.solver_settings.cp_sat_num_search_workers))
        highs.setOptionValue("mip_rel_gap", float(self.solver_settings.cp_sat_relative_gap_limit))
        highs.setOptionValue("random_seed", int(self.solver_settings.cp_sat_random_seed))

        slot_vars: dict[tuple[int, str], any] = {}
        selected_vars: dict[int, any] = {}
        for idx, player in enumerate(self.players):
            candidate_slot_vars: list[any] = []
            for slot in self.rules.roster_slots:
                if _is_eligible(player.position, slot):
                    var = highs.addVariable(
                        lb=0.0,
                        ub=1.0,
                        obj=0.0,
                        type=HighsVarType.kInteger,
                        name=f"x_{idx}_{slot}",
                    )
                    slot_vars[(idx, slot)] = var
                    candidate_slot_vars.append(var)
            selected = highs.addVariable(
                lb=0.0,
                ub=1.0,
                obj=0.0,
                type=HighsVarType.kInteger,
                name=f"sel_{idx}",
            )
            selected_vars[idx] = selected
            if candidate_slot_vars:
                highs.addConstr(sum(candidate_slot_vars) == selected)
            else:
                highs.addConstr(selected == 0)

        for slot in self.rules.roster_slots:
            eligible_vars = [
                var
                for (idx, this_slot), var in slot_vars.items()
                if this_slot == slot
            ]
            highs.addConstr(sum(eligible_vars) == 1)

        total_salary = sum(player.salary * selected_vars[idx] for idx, player in enumerate(self.players))
        highs.addConstr(total_salary <= self.rules.salary_cap)

        if self.rules.max_players_per_team is not None:
            by_team: dict[str, list[any]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                by_team[player.team].append(selected_vars[idx])
            for team_vars in by_team.values():
                highs.addConstr(sum(team_vars) <= self.rules.max_players_per_team)

        if self.rules.disallow_qb_vs_opp_dst:
            qb_indices = [idx for idx, p in enumerate(self.players) if p.position == "QB"]
            dst_indices = [idx for idx, p in enumerate(self.players) if p.position == "DST"]
            for qb_idx in qb_indices:
                qb = self.players[qb_idx]
                for dst_idx in dst_indices:
                    dst = self.players[dst_idx]
                    if qb.opponent == dst.team:
                        highs.addConstr(selected_vars[qb_idx] + selected_vars[dst_idx] <= 1)

        if self.rules.max_players_per_game_environment is not None:
            by_game: dict[str, list[any]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                if player.game_id:
                    by_game[player.game_id].append(selected_vars[idx])
            for game_vars in by_game.values():
                if game_vars:
                    highs.addConstr(sum(game_vars) <= self.rules.max_players_per_game_environment)

        if self.rules.max_non_qb_skill_players_same_team is not None:
            by_team_skill: dict[str, list[any]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                if player.position in {"RB", "WR", "TE"}:
                    by_team_skill[player.team].append(selected_vars[idx])
            for team_vars in by_team_skill.values():
                if team_vars:
                    highs.addConstr(sum(team_vars) <= self.rules.max_non_qb_skill_players_same_team)

        for player_id in forced_in:
            idx = self._index_by_id[player_id]
            highs.addConstr(selected_vars[idx] == 1)

        for player_id in forced_out:
            idx = self._index_by_id[player_id]
            highs.addConstr(selected_vars[idx] == 0)

        secondary_multiplier = 10_000
        primary_multiplier = 1_000_000_000
        lex_rank = {
            p.player_id: rank
            for rank, p in enumerate(sorted(self.players, key=lambda q: q.player_id))
        }
        max_rank = len(self.players)

        projection_expr = sum(
            projection_scaled[idx] * selected_vars[idx] for idx in range(len(self.players))
        )
        robust_penalty_expr = None
        robust_penalty_coeff = 0
        if robust_data is not None:
            robust_cfg, robust_matrix_scaled = robust_data
            robust_penalty_expr = self._build_robust_penalty_highs(
                highs=highs,
                selected_vars=selected_vars,
                robust_matrix_scaled=robust_matrix_scaled,
                uncertainty_set=robust_cfg.uncertainty_set,
            )
            robust_penalty_coeff = int(
                round(
                    robust_cfg.rho
                    * self.solver_settings.projection_scale
                    / max(1, self.solver_settings.robust_matrix_scale)
                )
            )

        main_objective = projection_expr
        if robust_penalty_expr is not None and robust_penalty_coeff > 0:
            main_objective = projection_expr - robust_penalty_coeff * robust_penalty_expr

        tie_break_expr = sum(
            (
                player.salary * secondary_multiplier
                + (max_rank - lex_rank[player.player_id])
            )
            * selected_vars[idx]
            for idx, player in enumerate(self.players)
        )
        highs.setObjective(main_objective * primary_multiplier + tie_break_expr)
        highs.setMaximize()
        highs.run()

        status = highs.getModelStatus()
        if status not in {
            HighsModelStatus.kOptimal,
            HighsModelStatus.kObjectiveBound,
            HighsModelStatus.kObjectiveTarget,
            HighsModelStatus.kTimeLimit,
        }:
            if status in {HighsModelStatus.kInfeasible, HighsModelStatus.kUnboundedOrInfeasible}:
                raise ValueError("No feasible lineup found")
            raise ValueError(f"HiGHS solve failed with status: {status}")

        slot_to_player: dict[str, Player] = {}
        selected_indices: list[int] = []
        for (idx, slot), var in slot_vars.items():
            if highs.val(var) > 0.5:
                player = self.players[idx]
                slot_to_player[slot] = player
                selected_indices.append(idx)

        selected_players = list(slot_to_player.values())
        selected_player_ids = [p.player_id for p in selected_players]
        salary_used = sum(player.salary for player in selected_players)
        total_projection = sum(projection_values[idx] for idx in selected_indices)

        ties_possible = False
        if self.solver_settings.detect_ties:
            ties_possible = self._has_projection_tie(
                projection_scaled=projection_scaled,
                selected_indices=selected_indices,
                forced_in=forced_in,
                forced_out=forced_out,
            )

        ordered_ids = tuple(sorted(selected_player_ids))
        lineup = Lineup(
            players_by_slot=dict(sorted(slot_to_player.items(), key=lambda item: self.rules.roster_slots.index(item[0]))),
            player_ids=ordered_ids,
            salary_used=salary_used,
            projected_points=total_projection,
        )

        projection_objective = self._to_scaled_int(total_projection)
        result = OptimizationResult(
            lineup=lineup,
            objective_value=projection_objective,
            optimal_projection=total_projection,
            ties_possible=ties_possible,
        )
        if use_cache:
            self._cache_set(cache_key, result)
        return result

    def _build_robust_penalty_highs(
        self,
        highs,
        selected_vars: dict[int, any],
        robust_matrix_scaled: np.ndarray,
        uncertainty_set: RobustUncertaintySet,
    ):
        from highspy import HighsVarType

        player_count = len(self.players)
        row_bounds = [
            int(np.sum(np.abs(robust_matrix_scaled[i, :])))
            for i in range(player_count)
        ]
        y_vars: list[any] = []
        for i in range(player_count):
            bound = max(0, row_bounds[i])
            y = highs.addVariable(
                lb=-float(bound),
                ub=float(bound),
                obj=0.0,
                type=HighsVarType.kContinuous,
                name=f"robust_y_{i}",
            )
            expr = sum(
                int(robust_matrix_scaled[i, j]) * selected_vars[j]
                for j in range(player_count)
            )
            highs.addConstr(y == expr)
            y_vars.append(y)

        if uncertainty_set == RobustUncertaintySet.BOX:
            z_vars: list[any] = []
            for i, y in enumerate(y_vars):
                bound = max(0, row_bounds[i])
                z = highs.addVariable(
                    lb=0.0,
                    ub=float(bound),
                    obj=0.0,
                    type=HighsVarType.kContinuous,
                    name=f"robust_abs_{i}",
                )
                highs.addConstr(z >= y)
                highs.addConstr(z >= -y)
                z_vars.append(z)
            return sum(z_vars)

        if uncertainty_set == RobustUncertaintySet.POLYGON:
            max_bound = max(0, max(row_bounds) if row_bounds else 0)
            z = highs.addVariable(
                lb=0.0,
                ub=float(max_bound),
                obj=0.0,
                type=HighsVarType.kContinuous,
                name="robust_inf_norm",
            )
            for y in y_vars:
                highs.addConstr(z >= y)
                highs.addConstr(z >= -y)
            return z

        raise ValueError(f"Unsupported uncertainty set: {uncertainty_set}")

    def _build_model(
        self,
        projection_scaled: Sequence[int],
        forced_in: set[str],
        forced_out: set[str],
        robust_data: tuple[RobustSettings, np.ndarray] | None,
        add_objective: bool,
    ) -> tuple[cp_model.CpModel, dict[tuple[int, str], cp_model.IntVar], dict[int, cp_model.IntVar]]:
        model = cp_model.CpModel()
        slot_vars: dict[tuple[int, str], cp_model.IntVar] = {}
        selected_vars: dict[int, cp_model.IntVar] = {}

        for idx, player in enumerate(self.players):
            candidate_slot_vars: list[cp_model.IntVar] = []
            for slot in self.rules.roster_slots:
                if _is_eligible(player.position, slot):
                    var = model.NewBoolVar(f"x_{idx}_{slot}")
                    slot_vars[(idx, slot)] = var
                    candidate_slot_vars.append(var)
            selected = model.NewBoolVar(f"sel_{idx}")
            selected_vars[idx] = selected
            if candidate_slot_vars:
                model.Add(sum(candidate_slot_vars) == selected)
            else:
                model.Add(selected == 0)

        for slot in self.rules.roster_slots:
            eligible_vars = [
                var
                for (idx, this_slot), var in slot_vars.items()
                if this_slot == slot
            ]
            model.Add(sum(eligible_vars) == 1)

        total_salary = sum(player.salary * selected_vars[idx] for idx, player in enumerate(self.players))
        model.Add(total_salary <= self.rules.salary_cap)

        if self.rules.max_players_per_team is not None:
            by_team: dict[str, list[cp_model.IntVar]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                by_team[player.team].append(selected_vars[idx])
            for team_vars in by_team.values():
                model.Add(sum(team_vars) <= self.rules.max_players_per_team)

        if self.rules.disallow_qb_vs_opp_dst:
            qb_indices = [idx for idx, p in enumerate(self.players) if p.position == "QB"]
            dst_indices = [idx for idx, p in enumerate(self.players) if p.position == "DST"]
            for qb_idx in qb_indices:
                qb = self.players[qb_idx]
                for dst_idx in dst_indices:
                    dst = self.players[dst_idx]
                    if qb.opponent == dst.team:
                        model.Add(selected_vars[qb_idx] + selected_vars[dst_idx] <= 1)

        if self.rules.max_players_per_game_environment is not None:
            by_game: dict[str, list[cp_model.IntVar]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                if player.game_id:
                    by_game[player.game_id].append(selected_vars[idx])
            for game_vars in by_game.values():
                if game_vars:
                    model.Add(sum(game_vars) <= self.rules.max_players_per_game_environment)

        if self.rules.max_non_qb_skill_players_same_team is not None:
            by_team_skill: dict[str, list[cp_model.IntVar]] = defaultdict(list)
            for idx, player in enumerate(self.players):
                if player.position in {"RB", "WR", "TE"}:
                    by_team_skill[player.team].append(selected_vars[idx])
            for team_vars in by_team_skill.values():
                if team_vars:
                    model.Add(sum(team_vars) <= self.rules.max_non_qb_skill_players_same_team)

        for player_id in forced_in:
            idx = self._index_by_id[player_id]
            model.Add(selected_vars[idx] == 1)

        for player_id in forced_out:
            idx = self._index_by_id[player_id]
            model.Add(selected_vars[idx] == 0)

        if add_objective:
            # Deterministic tie-breaking without changing primary objective ranking.
            secondary_multiplier = 10_000
            primary_multiplier = 1_000_000_000
            lex_rank = {
                p.player_id: rank
                for rank, p in enumerate(sorted(self.players, key=lambda q: q.player_id))
            }
            max_rank = len(self.players)

            projection_expr = sum(
                projection_scaled[idx] * selected_vars[idx] for idx in range(len(self.players))
            )
            robust_penalty_expr = None
            robust_penalty_coeff = 0
            if robust_data is not None:
                robust_cfg, robust_matrix_scaled = robust_data
                robust_penalty_expr = self._build_robust_penalty(
                    model=model,
                    selected_vars=selected_vars,
                    robust_matrix_scaled=robust_matrix_scaled,
                    uncertainty_set=robust_cfg.uncertainty_set,
                )
                robust_penalty_coeff = int(
                    round(
                        robust_cfg.rho
                        * self.solver_settings.projection_scale
                        / max(1, self.solver_settings.robust_matrix_scale)
                    )
                )

            main_objective = projection_expr
            if robust_penalty_expr is not None and robust_penalty_coeff > 0:
                main_objective = projection_expr - robust_penalty_coeff * robust_penalty_expr

            tie_break_expr = sum(
                (
                    player.salary * secondary_multiplier
                    + (max_rank - lex_rank[player.player_id])
                )
                * selected_vars[idx]
                for idx, player in enumerate(self.players)
            )
            model.Maximize(main_objective * primary_multiplier + tie_break_expr)

        return model, slot_vars, selected_vars

    def _has_projection_tie(
        self,
        projection_scaled: Sequence[int],
        selected_indices: Sequence[int],
        forced_in: set[str],
        forced_out: set[str],
    ) -> bool:
        model, _, selected_vars = self._build_model(
            projection_scaled=projection_scaled,
            forced_in=forced_in,
            forced_out=forced_out,
            robust_data=None,
            add_objective=False,
        )
        target_projection = sum(projection_scaled[idx] for idx in selected_indices)
        model.Add(
            sum(projection_scaled[idx] * selected_vars[idx] for idx in range(len(self.players)))
            == target_projection
        )
        model.Add(sum(selected_vars[idx] for idx in selected_indices) <= len(self.rules.roster_slots) - 1)

        solver = cp_model.CpSolver()
        self._apply_solver_settings(solver)
        status = solver.Solve(model)
        return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def _resolve_projections(self, projections: Sequence[float] | None) -> list[float]:
        if projections is None:
            return [p.projection for p in self.players]
        if len(projections) != len(self.players):
            raise ValueError("Projection vector length must match active player count")
        return [float(x) for x in projections]

    def _apply_solver_settings(self, solver: cp_model.CpSolver) -> None:
        if self.solver_settings.cp_sat_num_search_workers > 0:
            solver.parameters.num_search_workers = self.solver_settings.cp_sat_num_search_workers
        solver.parameters.max_time_in_seconds = self.solver_settings.cp_sat_max_time_seconds
        solver.parameters.relative_gap_limit = self.solver_settings.cp_sat_relative_gap_limit
        solver.parameters.random_seed = self.solver_settings.cp_sat_random_seed
        solver.parameters.log_search_progress = self.solver_settings.cp_sat_log_search_progress

    def _to_scaled_int(self, value: float) -> int:
        return int(round(value * self.solver_settings.projection_scale))

    def _cache_get(self, key: tuple) -> OptimizationResult | None:
        memory_enabled = self.solver_settings.enable_result_cache
        result = None
        if memory_enabled:
            result = self._result_cache.get(key)
            if result is not None:
                self._result_cache.move_to_end(key)
                return result

        if self.solver_settings.enable_disk_result_cache and self._disk_cache_dir is not None:
            cache_file = self._disk_cache_file(key)
            if cache_file.exists():
                try:
                    with cache_file.open("rb") as f:
                        loaded = pickle.load(f)
                    if isinstance(loaded, OptimizationResult):
                        if memory_enabled:
                            self._result_cache[key] = loaded
                            self._result_cache.move_to_end(key)
                            max_size = max(1, self.solver_settings.result_cache_size)
                            while len(self._result_cache) > max_size:
                                self._result_cache.popitem(last=False)
                        return loaded
                except Exception:
                    return None

        return None

    def _cache_set(self, key: tuple, result: OptimizationResult) -> None:
        if self.solver_settings.enable_result_cache:
            self._result_cache[key] = result
            self._result_cache.move_to_end(key)
            max_size = max(1, self.solver_settings.result_cache_size)
            while len(self._result_cache) > max_size:
                self._result_cache.popitem(last=False)

        if self.solver_settings.enable_disk_result_cache and self._disk_cache_dir is not None:
            cache_file = self._disk_cache_file(key)
            try:
                with cache_file.open("wb") as f:
                    pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                pass

    def _disk_cache_file(self, key: tuple) -> Path:
        if self._disk_cache_dir is None:
            raise ValueError("Disk cache directory is not configured")
        digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()
        return self._disk_cache_dir / f"{digest}.pkl"

    def _make_cache_key(
        self,
        projection_scaled: Sequence[int],
        forced_in: set[str],
        forced_out: set[str],
        robust_data: tuple[RobustSettings, np.ndarray] | None,
    ) -> tuple:
        robust_key: tuple | None = None
        if robust_data is not None:
            robust_cfg, robust_matrix_scaled = robust_data
            robust_key = (
                robust_cfg.rho,
                robust_cfg.uncertainty_set.value,
                tuple(tuple(int(v) for v in row) for row in robust_matrix_scaled.tolist()),
            )
        return (
            tuple(projection_scaled),
            tuple(sorted(forced_in)),
            tuple(sorted(forced_out)),
            robust_key,
        )

    def _resolve_robust_inputs(
        self,
        robust_settings: RobustSettings | None,
        robust_covariance: Sequence[Sequence[float]] | None,
    ) -> tuple[RobustSettings, np.ndarray] | None:
        cfg = robust_settings or RobustSettings()
        if not cfg.enabled:
            return None
        if cfg.rho < 0:
            raise ValueError("robust rho must be >= 0")
        if cfg.correlation_sparsification_threshold < 0 or cfg.correlation_sparsification_threshold > 1:
            raise ValueError("robust correlation_sparsification_threshold must be in [0, 1]")
        if cfg.rho == 0:
            return None
        if robust_covariance is None:
            raise ValueError("robust_covariance is required when robust settings are enabled")

        covariance = np.asarray(robust_covariance, dtype=float)
        expected_size = len(self.players)
        if covariance.shape != (expected_size, expected_size):
            raise ValueError("robust_covariance shape must match (active_players, active_players)")

        if cfg.correlation_sparsification_threshold > 0:
            covariance = sparsify_covariance_by_correlation_threshold(
                covariance,
                correlation_threshold=cfg.correlation_sparsification_threshold,
            )

        sqrt_cov = matrix_sqrt_psd(covariance)
        matrix_scale = max(1, self.solver_settings.robust_matrix_scale)
        sqrt_cov_scaled = np.rint(sqrt_cov * matrix_scale).astype(int)
        return cfg, sqrt_cov_scaled

    def _build_robust_penalty(
        self,
        model: cp_model.CpModel,
        selected_vars: dict[int, cp_model.IntVar],
        robust_matrix_scaled: np.ndarray,
        uncertainty_set: RobustUncertaintySet,
    ) -> cp_model.LinearExpr:
        player_count = len(self.players)
        row_bounds = [
            int(np.sum(np.abs(robust_matrix_scaled[i, :])))
            for i in range(player_count)
        ]
        y_vars: list[cp_model.IntVar] = []
        for i in range(player_count):
            bound = max(0, row_bounds[i])
            y = model.NewIntVar(-bound, bound, f"robust_y_{i}")
            expr = sum(
                int(robust_matrix_scaled[i, j]) * selected_vars[j]
                for j in range(player_count)
            )
            model.Add(y == expr)
            y_vars.append(y)

        if uncertainty_set == RobustUncertaintySet.BOX:
            z_vars: list[cp_model.IntVar] = []
            for i, y in enumerate(y_vars):
                bound = max(0, row_bounds[i])
                z = model.NewIntVar(0, bound, f"robust_abs_{i}")
                model.Add(z >= y)
                model.Add(z >= -y)
                z_vars.append(z)
            return sum(z_vars)

        if uncertainty_set == RobustUncertaintySet.POLYGON:
            max_bound = max(0, max(row_bounds) if row_bounds else 0)
            z = model.NewIntVar(0, max_bound, "robust_inf_norm")
            for y in y_vars:
                model.Add(z >= y)
                model.Add(z >= -y)
            return z

        raise ValueError(f"Unsupported uncertainty set: {uncertainty_set}")

    def _get_or_create_sim_pool(self, worker_count: int) -> ProcessPoolExecutor:
        if self._sim_pool is not None and self._sim_pool_workers == worker_count:
            return self._sim_pool
        if self._sim_pool is not None:
            self._sim_pool.shutdown(wait=True, cancel_futures=False)
        self._sim_pool = ProcessPoolExecutor(max_workers=worker_count)
        self._sim_pool_workers = worker_count
        return self._sim_pool

    def _solve_projection_to_stat(
        self,
        projections: Sequence[float],
        use_cache: bool,
    ) -> tuple[tuple[str, ...], float]:
        result = self._solve_once(projections=projections, use_cache=use_cache)
        return result.lineup.player_ids, result.optimal_projection


def _is_eligible(position: str, slot: str) -> bool:
    if slot == "QB":
        return position == "QB"
    if slot in {"RB1", "RB2"}:
        return position == "RB"
    if slot in {"WR1", "WR2", "WR3"}:
        return position == "WR"
    if slot == "TE":
        return position == "TE"
    if slot == "FLEX":
        return position in {"RB", "WR", "TE"}
    if slot == "DST":
        return position == "DST"
    return False


def _chunked(items: Sequence[Sequence[float]], chunk_size: int) -> Iterable[list[Sequence[float]]]:
    for i in range(0, len(items), max(1, chunk_size)):
        yield list(items[i : i + max(1, chunk_size)])


def _solve_worker_stats(
    payload: dict,
    chunk: list[Sequence[float]],
) -> list[tuple[tuple[str, ...], float]]:
    optimizer = CashOptimizer(
        players=payload["players"],
        rules=payload["rules"],
        solver_settings=payload["solver_settings"],
    )
    out: list[tuple[tuple[str, ...], float]] = []
    for vec in chunk:
        result = optimizer._solve_once(projections=vec, use_cache=False)
        out.append((result.lineup.player_ids, result.optimal_projection))
    return out


def _solve_sensitivity_entry_worker(
    payload: dict,
    player_id: str,
    in_optimal: bool,
) -> tuple[str, float]:
    optimizer = CashOptimizer(
        players=payload["players"],
        rules=payload["rules"],
        solver_settings=payload["solver_settings"],
    )
    projections = payload["projections"]
    robust_settings = payload["robust_settings"]
    robust_covariance = payload["robust_covariance"]

    if in_optimal:
        result = optimizer.solve_forced_out(
            player_id=player_id,
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )
    else:
        result = optimizer.solve_forced_in(
            player_id=player_id,
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )
    return player_id, result.optimal_projection


class _SimulationAggregator:
    def __init__(
        self,
        players: Sequence[Player],
        roster_size: int,
        top_k_lineups: int,
        random_seed: int,
    ) -> None:
        self._players = tuple(players)
        self._roster_size = roster_size
        self._top_k_lineups = max(1, top_k_lineups)
        self._random_seed = random_seed
        self._projections: list[float] = []
        self._lineup_counts: Counter[str] = Counter()
        self._lineup_projection_sums: dict[str, float] = defaultdict(float)
        self._included_counts: Counter[str] = Counter()
        self._included_proj_sums: dict[str, float] = defaultdict(float)

    def add_run(self, lineup_ids: tuple[str, ...], optimal_projection: float) -> None:
        self._projections.append(optimal_projection)
        lineup_key = "|".join(lineup_ids)
        self._lineup_counts[lineup_key] += 1
        self._lineup_projection_sums[lineup_key] += optimal_projection
        for pid in lineup_ids:
            self._included_counts[pid] += 1
            self._included_proj_sums[pid] += optimal_projection

    def finalize(self) -> SimulationResult:
        if not self._projections:
            raise ValueError("Simulation produced no run results")

        num_runs = len(self._projections)
        baseline_inclusion = self._roster_size / max(1, len(self._players))

        player_stats: list[SimulationPlayerStat] = []
        for player in sorted(self._players, key=lambda p: p.player_id):
            cnt = self._included_counts[player.player_id]
            inclusion_rate = cnt / num_runs
            mean_when_included = self._included_proj_sums[player.player_id] / cnt if cnt else 0.0
            player_stats.append(
                SimulationPlayerStat(
                    player_id=player.player_id,
                    inclusion_rate=inclusion_rate,
                    mean_lineup_projection_when_included=mean_when_included,
                    leverage_to_baseline=inclusion_rate - baseline_inclusion,
                )
            )

        top_lineups = self._lineup_counts.most_common(self._top_k_lineups)
        lineup_stats = tuple(
            SimulationLineupStat(
                lineup_key=lineup_key,
                frequency=count,
                frequency_rate=count / num_runs,
                mean_projection=self._lineup_projection_sums[lineup_key] / count,
            )
            for lineup_key, count in top_lineups
        )

        arr = np.asarray(self._projections, dtype=float)
        return SimulationResult(
            num_runs=num_runs,
            random_seed=self._random_seed,
            mean_optimal_projection=float(arr.mean()),
            p05_optimal_projection=float(np.percentile(arr, 5)),
            p50_optimal_projection=float(np.percentile(arr, 50)),
            p95_optimal_projection=float(np.percentile(arr, 95)),
            unique_lineups=len(self._lineup_counts),
            player_stats=tuple(player_stats),
            lineup_stats=lineup_stats,
        )


def _aggregate_simulation_results(
    players: Sequence[Player],
    run_results: Sequence[OptimizationResult],
    num_runs: int,
    random_seed: int,
    top_k_lineups: int,
) -> SimulationResult:
    aggregator = _SimulationAggregator(
        players=players,
        roster_size=9,
        top_k_lineups=top_k_lineups,
        random_seed=random_seed,
    )
    for result in run_results:
        aggregator.add_run(result.lineup.player_ids, result.optimal_projection)
    finalized = aggregator.finalize()
    if finalized.num_runs != num_runs:
        return replace(finalized, num_runs=num_runs)
    return finalized
