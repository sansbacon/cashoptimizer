from __future__ import annotations

from pathlib import Path
import glob
import json
import traceback
from time import perf_counter
from dataclasses import asdict, is_dataclass

import click

from cash_optimizer import (
    calibrate_benchmark_thresholds_from_history,
    ContestProfile,
    NormalizedObjectiveWeights,
    NewsSignal,
    RobustSettings,
    RobustUncertaintySet,
    Rules,
    StressScenario,
    SamplingMode,
    SimulationConfig,
    SolverSettings,
    RuntimeDefaults,
    append_benchmark_history,
    build_edge_trend_from_slate_paths,
    build_error_covariance_aligned_by_player,
    evaluate_prediction_models_by_position,
    load_cash_lines,
    load_prediction_eval_rows,
    compute_calibration_metrics,
    evaluate_weekly_calibration_governance,
    run_performance_benchmarks,
    recommend_rollout_stage,
    run_readiness_gate,
    tune_profile_parameters_from_backtest_rows,
    load_runtime_defaults,
    run_governance_check,
)

from .context import CLIContext
from .exporters import (
    write_candidates,
    write_edge_trend,
    write_optimal_lineup,
    write_sensitivity,
    write_simulation,
    write_stress,
)
from .formatters import configure_output, emit
from .projection_overrides import load_projection_overrides
from .validators import ensure_file_exists, ensure_positive_int, normalize_runtime_error


_BENCHMARK_THRESHOLD_PROFILES: dict[str, tuple[float, float, float]] = {
    "custom": (1000.0, 10000.0, 10000.0),
    "strict": (1000.0, 10000.0, 10000.0),
    "ci": (5000.0, 60000.0, 60000.0),
    "relaxed": (10000.0, 120000.0, 120000.0),
}


def _resolve_benchmark_thresholds(
    threshold_profile: str,
    threshold_scale: float,
    baseline_threshold_ms: float,
    sensitivity_threshold_ms: float,
    simulation_threshold_ms: float,
) -> tuple[float, float, float]:
    if threshold_scale <= 0:
        raise ValueError("threshold_scale must be > 0")
    if threshold_profile != "custom":
        b, s, sim = _BENCHMARK_THRESHOLD_PROFILES[threshold_profile]
        return (b * threshold_scale, s * threshold_scale, sim * threshold_scale)
    return (baseline_threshold_ms, sensitivity_threshold_ms, simulation_threshold_ms)


@click.group()
@click.option("--input-csv", type=click.Path(path_type=Path), default=Path("proj.csv"), show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("outputs"), show_default=True)
@click.option("--salary-cap", type=int, default=50000, show_default=True)
@click.option("--max-team", type=int, default=None)
@click.option("--disallow-qb-vs-opp-dst/--allow-qb-vs-opp-dst", default=False, show_default=True)
@click.option("--defaults-file", type=click.Path(path_type=Path), default=None)
@click.option("--solver-backend", type=click.Choice(["cp-sat", "highs"]), default=None)
@click.option("--seed", type=int, default=1729, show_default=True)
@click.option("--json/--no-json", "as_json", default=False, show_default=True)
@click.option("--rich/--no-rich", "rich_output", default=False, show_default=True)
@click.option("--verbose/--quiet", default=False, show_default=True)
@click.option("--debug/--no-debug", default=False, show_default=True)
@click.pass_context
def cli(
    ctx: click.Context,
    input_csv: Path,
    output_dir: Path,
    salary_cap: int,
    max_team: int | None,
    disallow_qb_vs_opp_dst: bool,
    defaults_file: Path | None,
    solver_backend: str | None,
    seed: int,
    as_json: bool,
    rich_output: bool,
    verbose: bool,
    debug: bool,
) -> None:
    ensure_file_exists(input_csv)
    rules = Rules(
        salary_cap=salary_cap,
        max_players_per_team=max_team,
        disallow_qb_vs_opp_dst=disallow_qb_vs_opp_dst,
    )
    runtime_defaults = load_runtime_defaults(defaults_file)
    selected_backend = solver_backend or runtime_defaults.solver_backend
    settings = SolverSettings(
        solver_backend=selected_backend,
        projection_scale=runtime_defaults.projection_scale_factor,
        cp_sat_num_search_workers=runtime_defaults.cp_sat_num_search_workers,
        cp_sat_max_time_seconds=runtime_defaults.cp_sat_max_time_seconds,
        cp_sat_relative_gap_limit=runtime_defaults.cp_sat_relative_gap_limit,
        cp_sat_random_seed=seed,
        cp_sat_log_search_progress=runtime_defaults.cp_sat_log_search_progress,
        sensitivity_worker_count=runtime_defaults.sensitivity_worker_count,
    )
    ctx.obj = CLIContext(
        input_csv=input_csv,
        output_dir=output_dir,
        rules=rules,
        solver_settings=settings,
        runtime_defaults=runtime_defaults,
        as_json=as_json,
        verbose=verbose,
        debug=debug,
    )
    configure_output(rich_output=rich_output)


def _handle_or_raise(app: CLIContext, fn):
    start = perf_counter()
    app.log("Starting command execution")
    try:
        result = fn()
        elapsed_ms = (perf_counter() - start) * 1000.0
        app.log(f"Completed command in {elapsed_ms:.1f} ms")
        return result
    except Exception as exc:
        elapsed_ms = (perf_counter() - start) * 1000.0
        app.log(f"Command failed after {elapsed_ms:.1f} ms: {exc}")
        if app.debug:
            traceback.print_exc()
        raise normalize_runtime_error(exc)


def _normalize_for_json(value):
    if is_dataclass(value):
        return {k: _normalize_for_json(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _normalize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_json(v) for v in value]
    return value


def _write_json_artifact(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_normalize_for_json(payload), indent=2, sort_keys=True), encoding="utf-8")


def _load_robust_covariance_from_csv(path: Path, ordered_player_ids: list[str]) -> list[list[float]]:
    import csv

    ensure_file_exists(path)
    history_by_player: dict[str, list[float | None]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "player_id" not in reader.fieldnames:
            raise ValueError("robust-cov-source CSV must include a player_id column")
        value_columns = [c for c in reader.fieldnames if c != "player_id"]
        if not value_columns:
            raise ValueError("robust-cov-source CSV must include at least one history column")

        for row in reader:
            pid = str(row["player_id"]).strip()
            if not pid:
                continue
            values: list[float | None] = []
            for col in value_columns:
                cell = (row.get(col) or "").strip()
                if not cell:
                    values.append(None)
                else:
                    values.append(float(cell))
            history_by_player[pid] = values

    covariance = build_error_covariance_aligned_by_player(
        ordered_player_ids=ordered_player_ids,
        error_history_by_player_id=history_by_player,
    )
    return covariance.tolist()


def _load_news_signals_from_csv(path: Path) -> dict[str, NewsSignal | str]:
    import csv

    ensure_file_exists(path)
    result: dict[str, NewsSignal | str] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"player_id", "signal"}.issubset(set(reader.fieldnames)):
            raise ValueError("news-signal CSV must include columns: player_id, signal")
        for row in reader:
            pid = str(row.get("player_id", "")).strip()
            signal_raw = str(row.get("signal", "")).strip().lower()
            if not pid or not signal_raw:
                continue
            try:
                result[pid] = NewsSignal(signal_raw)
            except ValueError:
                result[pid] = signal_raw
    return result


def _load_stress_scenarios_from_csv(path: Path) -> tuple[StressScenario, ...]:
    import csv

    ensure_file_exists(path)
    scenarios: list[StressScenario] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("scenario-file CSV must include headers")
        fieldnames = set(reader.fieldnames)
        if "scenario_name" not in fieldnames:
            raise ValueError("scenario-file CSV must include column: scenario_name")

        for row in reader:
            name = str(row.get("scenario_name", "")).strip()
            if not name:
                continue

            projection_multiplier_global = float((row.get("projection_multiplier_global") or "1.0").strip())
            by_position: dict[str, float] = {}
            for pos in ("QB", "RB", "WR", "TE", "DST"):
                raw = (row.get(pos) or "").strip()
                if raw:
                    by_position[pos] = float(raw)

            scenarios.append(
                StressScenario(
                    name=name,
                    projection_multiplier_by_position=by_position,
                    projection_multiplier_global=projection_multiplier_global,
                )
            )

    if not scenarios:
        raise ValueError("scenario-file CSV must include at least one valid scenario row")
    return tuple(scenarios)


@cli.command("optimize")
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.option("--robust-rho", type=float, default=0.0, show_default=True)
@click.option("--robust-corr-threshold", type=float, default=0.0, show_default=True)
@click.option(
    "--robust-set",
    type=click.Choice([RobustUncertaintySet.BOX.value, RobustUncertaintySet.POLYGON.value]),
    default=RobustUncertaintySet.BOX.value,
    show_default=True,
)
@click.option(
    "--robust-cov-source",
    type=click.Path(path_type=Path),
    default=None,
    help="CSV with player_id and historical error columns used to build aligned covariance",
)
@click.pass_obj
def optimize_cmd(
    app: CLIContext,
    save: Path | None,
    projection_file: Path | None,
    robust_rho: float,
    robust_corr_threshold: float,
    robust_set: str,
    robust_cov_source: Path | None,
) -> None:
    def _run():
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        robust_settings = None
        robust_covariance = None
        if robust_rho > 0:
            if robust_cov_source is None:
                raise ValueError("--robust-cov-source is required when --robust-rho > 0")
            robust_settings = RobustSettings(
                enabled=True,
                rho=robust_rho,
                uncertainty_set=RobustUncertaintySet(robust_set),
                correlation_sparsification_threshold=robust_corr_threshold,
            )
            robust_covariance = _load_robust_covariance_from_csv(
                robust_cov_source,
                [p.player_id for p in opt.players],
            )

        result = opt.solve_optimal(
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )
        if save is not None:
            if save.suffix.lower() == ".json":
                _write_json_artifact(save, result)
            else:
                write_optimal_lineup(save, result)
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("sensitivity")
@click.option("--top", type=int, default=0, show_default=True)
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.option("--robust-rho", type=float, default=0.0, show_default=True)
@click.option("--robust-corr-threshold", type=float, default=0.0, show_default=True)
@click.option(
    "--robust-set",
    type=click.Choice([RobustUncertaintySet.BOX.value, RobustUncertaintySet.POLYGON.value]),
    default=RobustUncertaintySet.BOX.value,
    show_default=True,
)
@click.option(
    "--robust-cov-source",
    type=click.Path(path_type=Path),
    default=None,
    help="CSV with player_id and historical error columns used to build aligned covariance",
)
@click.pass_obj
def sensitivity_cmd(
    app: CLIContext,
    top: int,
    save: Path | None,
    projection_file: Path | None,
    robust_rho: float,
    robust_corr_threshold: float,
    robust_set: str,
    robust_cov_source: Path | None,
) -> None:
    def _run():
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        robust_settings = None
        robust_covariance = None
        if robust_rho > 0:
            if robust_cov_source is None:
                raise ValueError("--robust-cov-source is required when --robust-rho > 0")
            robust_settings = RobustSettings(
                enabled=True,
                rho=robust_rho,
                uncertainty_set=RobustUncertaintySet(robust_set),
                correlation_sparsification_threshold=robust_corr_threshold,
            )
            robust_covariance = _load_robust_covariance_from_csv(
                robust_cov_source,
                [p.player_id for p in opt.players],
            )

        result = opt.solve_sensitivity_all(
            projections=projections,
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )
        if save is not None:
            write_sensitivity(save, result)
        payload = result
        if top > 0:
            entries = sorted(
                result.entries,
                key=lambda e: (
                    999.0
                    if e.delta_enter is None and e.delta_exit is None
                    else min(x for x in [e.delta_enter, e.delta_exit] if x is not None)
                ),
            )[:top]
            payload = {"base_result": result.base_result, "entries": entries}
        emit(payload, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("simulate")
@click.option("--runs", type=int, default=None)
@click.option("--sampling-mode", type=click.Choice([SamplingMode.INDEPENDENT.value, SamplingMode.CORRELATED.value]), default=None)
@click.option("--workers", type=int, default=None)
@click.option("--chunk-size", type=int, default=None)
@click.option("--top-k-lineups", type=int, default=None)
@click.option("--clip-min", type=float, default=None)
@click.option("--clip-max", type=float, default=None)
@click.option("--save-prefix", type=str, default=None)
@click.pass_obj
def simulate_cmd(
    app: CLIContext,
    runs: int | None,
    sampling_mode: str | None,
    workers: int | None,
    chunk_size: int | None,
    top_k_lineups: int | None,
    clip_min: float | None,
    clip_max: float | None,
    save_prefix: str | None,
) -> None:
    def _run():
        defaults = app.runtime_defaults
        runs_effective = runs if runs is not None else defaults.simulation_num_runs_default
        sampling_mode_effective = sampling_mode if sampling_mode is not None else defaults.simulation_sampling_mode.value
        workers_effective = workers if workers is not None else defaults.simulation_worker_count
        chunk_size_effective = chunk_size if chunk_size is not None else defaults.simulation_chunk_size
        top_k_effective = top_k_lineups if top_k_lineups is not None else defaults.simulation_top_k_lineups
        clip_min_effective = clip_min if clip_min is not None else defaults.simulation_clip_min_projection
        clip_max_effective = clip_max if clip_max is not None else defaults.simulation_clip_max_projection
        save_prefix_effective = save_prefix if save_prefix is not None else defaults.simulation_save_prefix

        ensure_positive_int(runs_effective, "runs")
        opt = app.create_optimizer()
        cfg = SimulationConfig(
            num_runs=runs_effective,
            random_seed=opt.solver_settings.cp_sat_random_seed,
            sampling_mode=SamplingMode(sampling_mode_effective),
            worker_count=workers_effective,
            chunk_size=chunk_size_effective,
            top_k_lineups_to_track=top_k_effective,
            clip_min_projection=clip_min_effective,
            clip_max_projection=clip_max_effective,
        )
        result = opt.run_projection_distribution_simulation(cfg)
        if save_prefix_effective:
            write_simulation(app.output_dir / save_prefix_effective, result)
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("export")
@click.option("--runs", type=int, default=None)
@click.option("--sampling-mode", type=click.Choice([SamplingMode.INDEPENDENT.value, SamplingMode.CORRELATED.value]), default=None)
@click.option("--workers", type=int, default=None)
@click.option("--chunk-size", type=int, default=None)
@click.option("--top-k-lineups", type=int, default=None)
@click.option("--clip-min", type=float, default=None)
@click.option("--clip-max", type=float, default=None)
@click.option("--save-prefix", type=str, default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def export_cmd(
    app: CLIContext,
    runs: int | None,
    sampling_mode: str | None,
    workers: int | None,
    chunk_size: int | None,
    top_k_lineups: int | None,
    clip_min: float | None,
    clip_max: float | None,
    save_prefix: str | None,
    projection_file: Path | None,
) -> None:
    def _run():
        defaults = app.runtime_defaults
        runs_effective = runs if runs is not None else defaults.simulation_num_runs_default
        sampling_mode_effective = sampling_mode if sampling_mode is not None else defaults.simulation_sampling_mode.value
        workers_effective = workers if workers is not None else defaults.simulation_worker_count
        chunk_size_effective = chunk_size if chunk_size is not None else defaults.simulation_chunk_size
        top_k_effective = top_k_lineups if top_k_lineups is not None else defaults.simulation_top_k_lineups
        clip_min_effective = clip_min if clip_min is not None else defaults.simulation_clip_min_projection
        clip_max_effective = clip_max if clip_max is not None else defaults.simulation_clip_max_projection
        save_prefix_effective = save_prefix if save_prefix is not None else defaults.simulation_save_prefix

        ensure_positive_int(runs_effective, "runs")
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        app.output_dir.mkdir(parents=True, exist_ok=True)

        optimal = opt.solve_optimal(projections=projections)
        write_optimal_lineup(app.output_dir / "optimal_lineup.csv", optimal)

        sensitivity = opt.solve_sensitivity_all(projections=projections)
        write_sensitivity(app.output_dir / "sensitivity.csv", sensitivity)

        sim = opt.run_projection_distribution_simulation(
            SimulationConfig(
                num_runs=runs_effective,
                random_seed=opt.solver_settings.cp_sat_random_seed,
                sampling_mode=SamplingMode(sampling_mode_effective),
                worker_count=workers_effective,
                chunk_size=chunk_size_effective,
                top_k_lineups_to_track=top_k_effective,
                clip_min_projection=clip_min_effective,
                clip_max_projection=clip_max_effective,
            )
        )
        write_simulation(app.output_dir / save_prefix_effective, sim)

        _write_json_artifact(
            app.output_dir / "run_metadata.json",
            {
                "parameter_version": app.runtime_defaults.parameter_version,
                "solver_backend": app.solver_settings.solver_backend,
                "simulation": {
                    "num_runs": runs_effective,
                    "sampling_mode": sampling_mode_effective,
                    "worker_count": workers_effective,
                    "chunk_size": chunk_size_effective,
                    "top_k_lineups_to_track": top_k_effective,
                    "clip_min_projection": clip_min_effective,
                    "clip_max_projection": clip_max_effective,
                    "save_prefix": save_prefix_effective,
                },
            },
        )

        emit({"output_dir": str(app.output_dir)}, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("candidates")
@click.option("--count", type=int, default=25, show_default=True)
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def candidates_cmd(app: CLIContext, count: int, save: Path | None, projection_file: Path | None) -> None:
    def _run():
        ensure_positive_int(count, "count")
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        out = opt.generate_candidate_lineups(num_candidates=count, projections=projections)
        if save is not None:
            write_candidates(save, out)
        emit({"candidate_count": len(out), "lineups": out}, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("select-cash")
@click.option("--threshold", type=float, required=True)
@click.option("--candidates", type=int, default=25, show_default=True)
@click.option("--runs", type=int, default=None)
@click.option("--sampling-mode", type=click.Choice([SamplingMode.INDEPENDENT.value, SamplingMode.CORRELATED.value]), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def select_cash_cmd(
    app: CLIContext,
    threshold: float,
    candidates: int,
    runs: int | None,
    sampling_mode: str | None,
    projection_file: Path | None,
) -> None:
    def _run():
        defaults = app.runtime_defaults
        runs_effective = runs if runs is not None else defaults.simulation_num_runs_default
        sampling_mode_effective = sampling_mode if sampling_mode is not None else defaults.simulation_sampling_mode.value
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        sim_cfg = SimulationConfig(
            num_runs=runs_effective,
            random_seed=opt.solver_settings.cp_sat_random_seed,
            sampling_mode=SamplingMode(sampling_mode_effective),
            worker_count=1,
        )
        result = opt.select_best_cash_lineup_by_probability(
            threshold=threshold,
            num_candidates=candidates,
            simulation_config=sim_cfg,
            projections=projections,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("select-normalized")
@click.option("--mean-weight", type=float, default=1.0, show_default=True)
@click.option("--risk-weight", type=float, default=1.0, show_default=True)
@click.option("--cov-weight", type=float, default=1.0, show_default=True)
@click.option("--cash-prob-weight", type=float, default=0.0, show_default=True)
@click.option("--threshold", type=float, default=None)
@click.option("--candidates", type=int, default=25, show_default=True)
@click.option("--runs", type=int, default=None)
@click.option("--sampling-mode", type=click.Choice([SamplingMode.INDEPENDENT.value, SamplingMode.CORRELATED.value]), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def select_normalized_cmd(
    app: CLIContext,
    mean_weight: float,
    risk_weight: float,
    cov_weight: float,
    cash_prob_weight: float,
    threshold: float | None,
    candidates: int,
    runs: int | None,
    sampling_mode: str | None,
    projection_file: Path | None,
) -> None:
    def _run():
        defaults = app.runtime_defaults
        runs_effective = runs if runs is not None else defaults.simulation_num_runs_default
        sampling_mode_effective = sampling_mode if sampling_mode is not None else defaults.simulation_sampling_mode.value
        ensure_positive_int(candidates, "candidates")
        ensure_positive_int(runs_effective, "runs")
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        sim_cfg = SimulationConfig(
            num_runs=runs_effective,
            random_seed=opt.solver_settings.cp_sat_random_seed,
            sampling_mode=SamplingMode(sampling_mode_effective),
            worker_count=1,
        )
        weights = NormalizedObjectiveWeights(
            w_mean=mean_weight,
            w_risk=risk_weight,
            w_cov=cov_weight,
            w_cash_prob=cash_prob_weight,
        )
        result = opt.select_best_lineup_by_normalized_objective(
            weights=weights,
            num_candidates=candidates,
            simulation_config=sim_cfg,
            cash_threshold=threshold,
            projections=projections,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("optimize-profile")
@click.option(
    "--contest-profile",
    type=click.Choice([ContestProfile.H2H.value, ContestProfile.DOUBLE_UP.value, ContestProfile.SMALL_FIELD.value]),
    default=ContestProfile.H2H.value,
    show_default=True,
)
@click.option("--threshold", type=float, default=None)
@click.option("--candidates", type=int, default=25, show_default=True)
@click.option("--runs", type=int, default=None)
@click.option("--sampling-mode", type=click.Choice([SamplingMode.INDEPENDENT.value, SamplingMode.CORRELATED.value]), default=None)
@click.option("--median-file", type=click.Path(path_type=Path), default=None)
@click.option("--floor-file", type=click.Path(path_type=Path), default=None)
@click.option("--news-signal-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def optimize_profile_cmd(
    app: CLIContext,
    contest_profile: str,
    threshold: float | None,
    candidates: int,
    runs: int | None,
    sampling_mode: str | None,
    median_file: Path | None,
    floor_file: Path | None,
    news_signal_file: Path | None,
) -> None:
    def _run():
        defaults = app.runtime_defaults
        runs_effective = runs if runs is not None else defaults.simulation_num_runs_default
        sampling_mode_effective = sampling_mode if sampling_mode is not None else defaults.simulation_sampling_mode.value
        ensure_positive_int(candidates, "candidates")
        ensure_positive_int(runs_effective, "runs")
        opt = app.create_optimizer()

        median_by_player = load_projection_overrides(median_file) if median_file else None
        floor_by_player = load_projection_overrides(floor_file) if floor_file else None
        news_by_player = _load_news_signals_from_csv(news_signal_file) if news_signal_file else None

        sim_cfg = SimulationConfig(
            num_runs=runs_effective,
            random_seed=opt.solver_settings.cp_sat_random_seed,
            sampling_mode=SamplingMode(sampling_mode_effective),
            worker_count=1,
        )
        result = opt.optimize_for_contest_profile(
            contest_profile=ContestProfile(contest_profile),
            median_by_player_id=median_by_player,
            floor_by_player_id=floor_by_player,
            cash_threshold=threshold,
            num_candidates=candidates,
            simulation_config=sim_cfg,
            news_signal_by_player_id=news_by_player,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("stress")
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.option("--scenario-file", type=click.Path(path_type=Path), default=None)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def stress_cmd(
    app: CLIContext,
    save: Path | None,
    scenario_file: Path | None,
    projection_file: Path | None,
) -> None:
    def _run():
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        scenarios = _load_stress_scenarios_from_csv(scenario_file) if scenario_file else None
        result = opt.run_stress_test(base_projections=projections, scenarios=scenarios)
        if save is not None:
            write_stress(save, result)
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("calibrate")
@click.option("--input", "input_path", type=click.Path(path_type=Path), required=True)
@click.pass_obj
def calibrate_cmd(app: CLIContext, input_path: Path) -> None:
    def _run():
        import csv

        ensure_file_exists(input_path)
        preds: list[float] = []
        observed: list[int] = []
        with input_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not {"predicted_probability", "observed_event"}.issubset(set(reader.fieldnames)):
                raise ValueError("Calibration CSV must include columns: predicted_probability, observed_event")
            for row in reader:
                preds.append(float(row["predicted_probability"]))
                observed.append(int(row["observed_event"]))

        result = compute_calibration_metrics(preds, observed)
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("calibration-governance")
@click.option("--baseline-input", type=click.Path(path_type=Path), required=True)
@click.option("--candidate-input", type=click.Path(path_type=Path), required=True)
@click.option("--required-brier-improvement", type=float, default=0.01, show_default=True)
@click.option("--max-log-loss-increase", type=float, default=0.0, show_default=True)
@click.option("--min-samples", type=int, default=0, show_default=True)
@click.option("--candidate-parameter-version", type=str, default=None)
@click.option("--require-parameter-versioning/--allow-unversioned", default=True, show_default=True)
@click.pass_obj
def calibration_governance_cmd(
    app: CLIContext,
    baseline_input: Path,
    candidate_input: Path,
    required_brier_improvement: float,
    max_log_loss_increase: float,
    min_samples: int,
    candidate_parameter_version: str | None,
    require_parameter_versioning: bool,
) -> None:
    def _run():
        import csv

        ensure_file_exists(baseline_input)
        ensure_file_exists(candidate_input)

        baseline_preds: list[float] = []
        baseline_obs: list[int] = []
        with baseline_input.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not {"predicted_probability", "observed_event"}.issubset(set(reader.fieldnames)):
                raise ValueError("Baseline CSV must include columns: predicted_probability, observed_event")
            for row in reader:
                baseline_preds.append(float(row["predicted_probability"]))
                baseline_obs.append(int(row["observed_event"]))

        candidate_preds: list[float] = []
        candidate_obs: list[int] = []
        with candidate_input.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not {"predicted_probability", "observed_event"}.issubset(set(reader.fieldnames)):
                raise ValueError("Candidate CSV must include columns: predicted_probability, observed_event")
            for row in reader:
                candidate_preds.append(float(row["predicted_probability"]))
                candidate_obs.append(int(row["observed_event"]))

        baseline_metrics = compute_calibration_metrics(baseline_preds, baseline_obs)
        candidate_metrics = compute_calibration_metrics(candidate_preds, candidate_obs)
        result = evaluate_weekly_calibration_governance(
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            baseline_sample_count=len(baseline_preds),
            candidate_sample_count=len(candidate_preds),
            required_brier_improvement=required_brier_improvement,
            max_log_loss_increase=max_log_loss_increase,
            min_samples=min_samples,
            require_parameter_versioning=require_parameter_versioning,
            candidate_parameter_version=candidate_parameter_version,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("calibration-tune")
@click.option("--input", "input_path", type=click.Path(path_type=Path), required=True)
@click.option("--profile-col", type=str, default="contest_profile", show_default=True)
@click.option("--lambda-col", type=str, default="lambda_risk", show_default=True)
@click.option("--corr-penalty-col", type=str, default="correlation_penalty_strength", show_default=True)
@click.option("--pred-col", type=str, default="predicted_probability", show_default=True)
@click.option("--obs-col", type=str, default="observed_event", show_default=True)
@click.option("--min-samples", type=int, default=20, show_default=True)
@click.pass_obj
def calibration_tune_cmd(
    app: CLIContext,
    input_path: Path,
    profile_col: str,
    lambda_col: str,
    corr_penalty_col: str,
    pred_col: str,
    obs_col: str,
    min_samples: int,
) -> None:
    def _run():
        import csv

        ensure_file_exists(input_path)
        ensure_positive_int(min_samples, "min_samples")
        rows: list[dict[str, str]] = []
        with input_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("Input CSV must include headers")
            required = {profile_col, lambda_col, corr_penalty_col, pred_col, obs_col}
            if not required.issubset(set(reader.fieldnames)):
                raise ValueError(
                    "Input CSV missing required columns for tuning: "
                    + ", ".join(sorted(required))
                )
            rows = [dict(r) for r in reader]

        result = tune_profile_parameters_from_backtest_rows(
            rows=rows,
            contest_profile_column=profile_col,
            lambda_risk_column=lambda_col,
            correlation_penalty_column=corr_penalty_col,
            predicted_column=pred_col,
            observed_column=obs_col,
            min_samples_per_setting=min_samples,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("compare-human")
@click.option("--trials", type=int, default=1000, show_default=True)
@click.option("--top-n-per-slot", type=int, default=10, show_default=True)
@click.option("--projection-file", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def compare_human_cmd(
    app: CLIContext,
    trials: int,
    top_n_per_slot: int,
    projection_file: Path | None,
) -> None:
    def _run():
        ensure_positive_int(trials, "trials")
        ensure_positive_int(top_n_per_slot, "top_n_per_slot")
        opt = app.create_optimizer()
        projection_map = load_projection_overrides(projection_file) if projection_file else None
        projections = app.resolve_projection_overrides(projection_map)
        result = opt.compare_against_human_heuristic(
            projections=projections,
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            random_seed=opt.solver_settings.cp_sat_random_seed,
        )
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("evaluate-predictions")
@click.option("--input", "input_path", type=click.Path(path_type=Path), required=True)
@click.option("--position-col", type=str, default="position", show_default=True)
@click.option("--actual-col", type=str, default="actual", show_default=True)
@click.option("--model-col", "model_cols", multiple=True, required=True)
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def evaluate_predictions_cmd(
    app: CLIContext,
    input_path: Path,
    position_col: str,
    actual_col: str,
    model_cols: tuple[str, ...],
    save: Path | None,
) -> None:
    def _run():
        ensure_file_exists(input_path)
        rows = load_prediction_eval_rows(input_path)
        result = evaluate_prediction_models_by_position(
            rows=rows,
            model_columns=list(model_cols),
            position_column=position_col,
            actual_column=actual_col,
        )
        if save is not None:
            save.parent.mkdir(parents=True, exist_ok=True)
            import csv

            with save.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["position", "model_name", "rmse", "sample_count", "is_best"])
                for m in result.metrics:
                    w.writerow([
                        m.position,
                        m.model_name,
                        m.rmse,
                        m.sample_count,
                        result.best_model_by_position.get(m.position) == m.model_name,
                    ])
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("edge-trend")
@click.option("--slates-glob", type=str, required=True)
@click.option("--trials", type=int, default=1000, show_default=True)
@click.option("--top-n-per-slot", type=int, default=10, show_default=True)
@click.option("--cash-lines", type=click.Path(path_type=Path), default=None)
@click.option("--save", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def edge_trend_cmd(
    app: CLIContext,
    slates_glob: str,
    trials: int,
    top_n_per_slot: int,
    cash_lines: Path | None,
    save: Path | None,
) -> None:
    def _run():
        ensure_positive_int(trials, "trials")
        ensure_positive_int(top_n_per_slot, "top_n_per_slot")
        matches = sorted(glob.glob(slates_glob))
        if not matches:
            raise ValueError(f"No files matched --slates-glob: {slates_glob}")

        cash_line_by_slate = load_cash_lines(cash_lines) if cash_lines is not None else None
        result = build_edge_trend_from_slate_paths(
            slate_paths=matches,
            rules=app.rules,
            solver_settings=app.solver_settings,
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            cash_line_by_slate=cash_line_by_slate,
        )
        if save is not None:
            write_edge_trend(save, result)
        emit(result, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("benchmark")
@click.option("--simulation-runs", type=int, default=1000, show_default=True)
@click.option("--baseline-threshold-ms", type=float, default=1000.0, show_default=True)
@click.option("--sensitivity-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option("--simulation-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option(
    "--threshold-profile",
    type=click.Choice(["custom", "strict", "ci", "relaxed"]),
    default="custom",
    show_default=True,
)
@click.option("--threshold-scale", type=float, default=1.0, show_default=True)
@click.option("--history-csv", type=click.Path(path_type=Path), default=None)
@click.option("--history-note", type=str, default="")
@click.pass_obj
def benchmark_cmd(
    app: CLIContext,
    simulation_runs: int,
    baseline_threshold_ms: float,
    sensitivity_threshold_ms: float,
    simulation_threshold_ms: float,
    threshold_profile: str,
    threshold_scale: float,
    history_csv: Path | None,
    history_note: str,
) -> None:
    def _run():
        ensure_positive_int(simulation_runs, "simulation_runs")
        baseline_ms, sensitivity_ms, simulation_ms = _resolve_benchmark_thresholds(
            threshold_profile=threshold_profile,
            threshold_scale=threshold_scale,
            baseline_threshold_ms=baseline_threshold_ms,
            sensitivity_threshold_ms=sensitivity_threshold_ms,
            simulation_threshold_ms=simulation_threshold_ms,
        )

        opt = app.create_optimizer()
        result = run_performance_benchmarks(
            optimizer=opt,
            simulation_runs=simulation_runs,
            baseline_threshold_ms=baseline_ms,
            sensitivity_threshold_ms=sensitivity_ms,
            simulation_threshold_ms=simulation_ms,
        )
        if history_csv is not None:
            append_benchmark_history(
                path=history_csv,
                result=result,
                parameter_version=app.runtime_defaults.parameter_version,
                note=history_note,
            )
        emit(
            {
                "parameter_version": app.runtime_defaults.parameter_version,
                "threshold_profile": threshold_profile,
                "threshold_scale": threshold_scale,
                "thresholds": {
                    "baseline_threshold_ms": baseline_ms,
                    "sensitivity_threshold_ms": sensitivity_ms,
                    "simulation_threshold_ms": simulation_ms,
                },
                "benchmark": result,
            },
            app.as_json,
        )

    _handle_or_raise(app, _run)


@cli.command("readiness-gate")
@click.option("--simulation-runs", type=int, default=200, show_default=True)
@click.option("--baseline-threshold-ms", type=float, default=1000.0, show_default=True)
@click.option("--sensitivity-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option("--simulation-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option(
    "--threshold-profile",
    type=click.Choice(["custom", "strict", "ci", "relaxed"]),
    default="ci",
    show_default=True,
)
@click.option("--threshold-scale", type=float, default=1.0, show_default=True)
@click.pass_obj
def readiness_gate_cmd(
    app: CLIContext,
    simulation_runs: int,
    baseline_threshold_ms: float,
    sensitivity_threshold_ms: float,
    simulation_threshold_ms: float,
    threshold_profile: str,
    threshold_scale: float,
) -> None:
    def _run():
        ensure_positive_int(simulation_runs, "simulation_runs")
        baseline_ms, sensitivity_ms, simulation_ms = _resolve_benchmark_thresholds(
            threshold_profile=threshold_profile,
            threshold_scale=threshold_scale,
            baseline_threshold_ms=baseline_threshold_ms,
            sensitivity_threshold_ms=sensitivity_threshold_ms,
            simulation_threshold_ms=simulation_threshold_ms,
        )
        opt = app.create_optimizer()
        result = run_readiness_gate(
            optimizer=opt,
            simulation_runs=simulation_runs,
            baseline_threshold_ms=baseline_ms,
            sensitivity_threshold_ms=sensitivity_ms,
            simulation_threshold_ms=simulation_ms,
        )
        emit(
            {
                "threshold_profile": threshold_profile,
                "threshold_scale": threshold_scale,
                "thresholds": {
                    "baseline_threshold_ms": baseline_ms,
                    "sensitivity_threshold_ms": sensitivity_ms,
                    "simulation_threshold_ms": simulation_ms,
                },
                "readiness": result,
            },
            app.as_json,
        )
        if not result.accepted:
            raise click.ClickException("Readiness gate failed")

    _handle_or_raise(app, _run)


@cli.command("benchmark-calibrate")
@click.option("--history-csv", type=click.Path(path_type=Path), required=True)
@click.option("--percentile", type=float, default=0.95, show_default=True)
@click.option("--safety-multiplier", type=float, default=1.1, show_default=True)
@click.option("--min-samples", type=int, default=5, show_default=True)
@click.option("--write-env", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def benchmark_calibrate_cmd(
    app: CLIContext,
    history_csv: Path,
    percentile: float,
    safety_multiplier: float,
    min_samples: int,
    write_env: Path | None,
) -> None:
    def _run():
        recommendation = calibrate_benchmark_thresholds_from_history(
            history_csv=history_csv,
            percentile=percentile,
            safety_multiplier=safety_multiplier,
            min_samples=min_samples,
        )
        if write_env is not None:
            write_env.parent.mkdir(parents=True, exist_ok=True)
            write_env.write_text(
                "\n".join(
                    [
                        f"BENCH_BASELINE_MS={recommendation.baseline_threshold_ms}",
                        f"BENCH_SENSITIVITY_MS={recommendation.sensitivity_threshold_ms}",
                        f"BENCH_SIMULATION_MS={recommendation.simulation_threshold_ms}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        emit(recommendation, app.as_json)

    _handle_or_raise(app, _run)


@cli.command("rollout-recommend")
@click.option("--simulation-runs", type=int, default=200, show_default=True)
@click.option("--baseline-threshold-ms", type=float, default=1000.0, show_default=True)
@click.option("--sensitivity-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option("--simulation-threshold-ms", type=float, default=10000.0, show_default=True)
@click.option(
    "--threshold-profile",
    type=click.Choice(["custom", "strict", "ci", "relaxed"]),
    default="ci",
    show_default=True,
)
@click.option("--threshold-scale", type=float, default=1.0, show_default=True)
@click.option("--require-clean/--allow-blockers", default=False, show_default=True)
@click.pass_obj
def rollout_recommend_cmd(
    app: CLIContext,
    simulation_runs: int,
    baseline_threshold_ms: float,
    sensitivity_threshold_ms: float,
    simulation_threshold_ms: float,
    threshold_profile: str,
    threshold_scale: float,
    require_clean: bool,
) -> None:
    def _run():
        ensure_positive_int(simulation_runs, "simulation_runs")
        baseline_ms, sensitivity_ms, simulation_ms = _resolve_benchmark_thresholds(
            threshold_profile=threshold_profile,
            threshold_scale=threshold_scale,
            baseline_threshold_ms=baseline_threshold_ms,
            sensitivity_threshold_ms=sensitivity_threshold_ms,
            simulation_threshold_ms=simulation_threshold_ms,
        )
        opt = app.create_optimizer()
        readiness = run_readiness_gate(
            optimizer=opt,
            simulation_runs=simulation_runs,
            baseline_threshold_ms=baseline_ms,
            sensitivity_threshold_ms=sensitivity_ms,
            simulation_threshold_ms=simulation_ms,
        )
        recommendation = recommend_rollout_stage(readiness)
        emit(
            {
                "threshold_profile": threshold_profile,
                "threshold_scale": threshold_scale,
                "readiness": readiness,
                "rollout": recommendation,
            },
            app.as_json,
        )
        if require_clean and not recommendation.can_promote:
            raise click.ClickException("Rollout recommendation includes blockers")

    _handle_or_raise(app, _run)


@cli.command("governance-check")
@click.option("--policy-file", type=click.Path(path_type=Path), required=True)
@click.pass_obj
def governance_check_cmd(app: CLIContext, policy_file: Path) -> None:
    def _run():
        ensure_file_exists(policy_file)
        raw = json.loads(policy_file.read_text(encoding="utf-8"))
        simulation_runs = int(raw.get("simulation_runs", 200))
        threshold_profile = str(raw.get("threshold_profile", "ci"))
        threshold_scale = float(raw.get("threshold_scale", 1.0))
        require_clean = bool(raw.get("require_clean", True))
        minimum_stage = str(raw.get("minimum_stage", "phase4_validation"))

        baseline_default = float(raw.get("baseline_threshold_ms", 1000.0))
        sensitivity_default = float(raw.get("sensitivity_threshold_ms", 10000.0))
        simulation_default = float(raw.get("simulation_threshold_ms", 10000.0))

        baseline_ms, sensitivity_ms, simulation_ms = _resolve_benchmark_thresholds(
            threshold_profile=threshold_profile,
            threshold_scale=threshold_scale,
            baseline_threshold_ms=baseline_default,
            sensitivity_threshold_ms=sensitivity_default,
            simulation_threshold_ms=simulation_default,
        )
        opt = app.create_optimizer()
        readiness = run_readiness_gate(
            optimizer=opt,
            simulation_runs=simulation_runs,
            baseline_threshold_ms=baseline_ms,
            sensitivity_threshold_ms=sensitivity_ms,
            simulation_threshold_ms=simulation_ms,
        )
        rollout = recommend_rollout_stage(readiness)
        governance = run_governance_check(
            readiness=readiness,
            rollout=rollout,
            require_clean=require_clean,
            minimum_stage=minimum_stage,
        )
        emit(
            {
                "policy_file": str(policy_file),
                "threshold_profile": threshold_profile,
                "threshold_scale": threshold_scale,
                "governance": governance,
            },
            app.as_json,
        )
        if not governance.accepted:
            raise click.ClickException("Governance check failed")

    _handle_or_raise(app, _run)


if __name__ == "__main__":
    cli()
