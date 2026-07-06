from cash_optimizer import (
    calibrate_benchmark_thresholds_from_history,
    RuntimeDefaults,
    CashOptimizer,
    ContestProfile,
    NewsSignal,
    NormalizedObjectiveWeights,
    Player,
    Rules,
    SimulationConfig,
    SolverSettings,
    StressScenario,
    compute_calibration_metrics,
    get_contest_profile_settings,
    run_performance_benchmarks,
    run_governance_check,
    recommend_rollout_stage,
    run_readiness_gate,
    append_benchmark_history,
    load_runtime_defaults,
)


def _players():
    return [
        Player("qb_a", "QB A", "T1", "T2", "QB", 7000, 21.0),
        Player("qb_b", "QB B", "T2", "T1", "QB", 6800, 20.2),
        Player("rb_a", "RB A", "T3", "T4", "RB", 7600, 19.0),
        Player("rb_b", "RB B", "T4", "T3", "RB", 7100, 17.3),
        Player("rb_c", "RB C", "T5", "T6", "RB", 6200, 15.0),
        Player("wr_a", "WR A", "T1", "T2", "WR", 7900, 21.8),
        Player("wr_b", "WR B", "T2", "T1", "WR", 7000, 18.5),
        Player("wr_c", "WR C", "T3", "T4", "WR", 6200, 15.7),
        Player("wr_d", "WR D", "T4", "T3", "WR", 5300, 13.4),
        Player("te_a", "TE A", "T1", "T2", "TE", 5100, 12.9),
        Player("te_b", "TE B", "T2", "T1", "TE", 4300, 10.4),
        Player("dst_a", "DST A", "T7", "T8", "DST", 3500, 8.2),
        Player("dst_b", "DST B", "T8", "T7", "DST", 2900, 6.9),
    ]


def test_projection_blending_and_penalties():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    med = {p.player_id: p.projection for p in optimizer.players}
    floor = {p.player_id: p.projection - 2.0 for p in optimizer.players}
    blended = optimizer.build_cash_blended_projections(med, floor, w_median=0.7, w_floor=0.3)

    assert len(blended) == len(optimizer.players)
    assert blended[0] < optimizer.players[0].projection

    penalties = {optimizer.players[0].player_id: 1.0}
    penalized = optimizer.apply_projection_penalties(blended, penalties)
    assert penalized[0] == max(0.0, blended[0] - 1.0)


def test_stress_test_runner_returns_scenarios():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    stress = optimizer.run_stress_test(
        scenarios=[
            StressScenario("wr_down", projection_multiplier_by_position={"WR": 0.9}),
            StressScenario("rb_down", projection_multiplier_by_position={"RB": 0.9}),
        ]
    )

    assert stress.base_projection > 0
    assert len(stress.scenario_results) == 2
    assert stress.worst_case_projection <= stress.base_projection


def test_calibration_metrics_computation():
    metrics = compute_calibration_metrics(
        predicted_cash_probabilities=[0.7, 0.5, 0.3, 0.9],
        observed_cash_events=[1, 1, 0, 1],
    )

    assert 0 <= metrics.brier_score <= 1
    assert metrics.log_loss > 0
    assert 0 <= metrics.mean_predicted_probability <= 1
    assert 0 <= metrics.observed_rate <= 1


def test_simulation_seed_reproducibility_worker1():
    settings = SolverSettings(cp_sat_random_seed=123)
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000), solver_settings=settings)
    cfg = SimulationConfig(num_runs=25, random_seed=99, worker_count=1)

    sim1 = optimizer.run_projection_distribution_simulation(cfg)
    sim2 = optimizer.run_projection_distribution_simulation(cfg)

    assert sim1.num_runs == sim2.num_runs
    assert sim1.mean_optimal_projection == sim2.mean_optimal_projection
    assert sim1.p50_optimal_projection == sim2.p50_optimal_projection
    assert sim1.unique_lineups == sim2.unique_lineups


def test_optimizer_result_cache_populates():
    settings = SolverSettings(enable_result_cache=True, result_cache_size=8)
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000), solver_settings=settings)

    _ = optimizer.solve_optimal()
    _ = optimizer.solve_optimal()

    assert len(optimizer._result_cache) >= 1


def test_optimizer_disk_result_cache_roundtrip(tmp_path):
    cache_dir = tmp_path / "disk_cache"
    settings = SolverSettings(
        enable_result_cache=False,
        enable_disk_result_cache=True,
        disk_result_cache_dir=str(cache_dir),
    )

    optimizer_1 = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000), solver_settings=settings)
    result_1 = optimizer_1.solve_optimal()

    files_after_first = list(cache_dir.glob("*.pkl"))
    assert files_after_first

    optimizer_2 = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000), solver_settings=settings)
    result_2 = optimizer_2.solve_optimal()

    assert result_1.lineup.player_ids == result_2.lineup.player_ids
    assert result_1.optimal_projection == result_2.optimal_projection


def test_generate_candidate_lineups_and_cash_probability_selection():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))

    candidates = optimizer.generate_candidate_lineups(num_candidates=6)
    assert len(candidates) >= 1
    assert len(candidates[0]) == 9

    selection = optimizer.select_best_cash_lineup_by_probability(
        threshold=130.0,
        num_candidates=6,
        simulation_config=SimulationConfig(num_runs=200, random_seed=77, worker_count=1),
    )

    assert selection.candidate_count >= 1
    assert len(selection.selected_lineup_player_ids) == 9
    assert 0.0 <= selection.estimated_cash_probability <= 1.0


def test_sensitivity_returns_fragility_summary():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    sens = optimizer.solve_sensitivity_all(
        fragility_exit_delta_threshold=0.75,
        fragility_enter_delta_threshold=0.75,
        fragility_alert_threshold=1.0,
    )

    assert sens.fragility_summary is not None
    summary = sens.fragility_summary
    assert summary.fragility_score >= 0.0
    assert isinstance(summary.alert, bool)


def test_sensitivity_parallel_matches_sequential():
    players = _players()
    rules = Rules(salary_cap=70000)

    seq_optimizer = CashOptimizer(
        players=players,
        rules=rules,
        solver_settings=SolverSettings(sensitivity_worker_count=1),
    )
    par_optimizer = CashOptimizer(
        players=players,
        rules=rules,
        solver_settings=SolverSettings(sensitivity_worker_count=2),
    )

    seq = seq_optimizer.solve_sensitivity_all()
    par = par_optimizer.solve_sensitivity_all()

    assert seq.base_result.lineup.player_ids == par.base_result.lineup.player_ids
    assert seq.base_result.optimal_projection == par.base_result.optimal_projection
    assert [
        (e.player_id, e.in_optimal, e.delta_enter, e.delta_exit, e.tie_flag)
        for e in seq.entries
    ] == [
        (e.player_id, e.in_optimal, e.delta_enter, e.delta_exit, e.tie_flag)
        for e in par.entries
    ]


def test_contest_profile_settings_defaults():
    h2h = get_contest_profile_settings(ContestProfile.H2H)
    du = get_contest_profile_settings(ContestProfile.DOUBLE_UP)

    assert h2h.objective_profile == "risk_adjusted"
    assert du.objective_profile == "cash_probability"
    assert h2h.floor_weight + h2h.median_weight == 1.0
    assert h2h.max_players_per_game_environment == 4
    assert du.max_non_qb_skill_players_same_team == 3


def test_select_best_lineup_by_normalized_objective_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    result = optimizer.select_best_lineup_by_normalized_objective(
        weights=NormalizedObjectiveWeights(w_mean=1.0, w_risk=0.5, w_cov=0.25, w_cash_prob=0.2),
        num_candidates=8,
        simulation_config=SimulationConfig(num_runs=200, random_seed=77, worker_count=1),
        cash_threshold=130.0,
    )

    assert result.candidate_count >= 1
    assert len(result.selected_lineup_player_ids) == 9
    assert len(result.lineup_metrics) == result.candidate_count


def test_build_ensemble_shrunk_projections_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    source_a = {p.player_id: p.projection for p in optimizer.players}
    source_b = {p.player_id: p.projection + 1.0 for p in optimizer.players}

    shrunk = optimizer.build_ensemble_shrunk_projections(
        projections_by_source={"a": source_a, "b": source_b},
        source_weights={"a": 0.6, "b": 0.4},
        shrink_strength=0.3,
        disagreement_penalty=0.1,
        clip_min=0.0,
    )

    assert len(shrunk) == len(optimizer.players)
    assert all(v >= 0.0 for v in shrunk)


def test_apply_news_volatility_layer_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    player_id = optimizer.players[0].player_id
    out = optimizer.apply_news_volatility_layer(
        signal_by_player_id={player_id: NewsSignal.GAME_TIME_DECISION},
    )

    assert len(out.adjusted_projections) == len(optimizer.players)
    assert out.adjusted_projections[0] < optimizer.players[0].projection
    assert out.variance_multiplier_by_player_id[player_id] >= 1.0


def test_optimize_for_contest_profile_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))

    h2h = optimizer.optimize_for_contest_profile(
        contest_profile=ContestProfile.H2H,
        num_candidates=8,
        simulation_config=SimulationConfig(num_runs=200, random_seed=77, worker_count=1),
    )
    du = optimizer.optimize_for_contest_profile(
        contest_profile=ContestProfile.DOUBLE_UP,
        cash_threshold=130.0,
        num_candidates=8,
        simulation_config=SimulationConfig(num_runs=200, random_seed=77, worker_count=1),
    )

    assert len(h2h.selected_lineup_player_ids) == 9
    assert h2h.objective_profile == "risk_adjusted"
    assert len(du.selected_lineup_player_ids) == 9
    assert du.objective_profile == "cash_probability"


def test_run_performance_benchmarks_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    out = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=50,
        baseline_threshold_ms=10000.0,
        sensitivity_threshold_ms=30000.0,
        simulation_threshold_ms=30000.0,
    )

    assert out.simulation_runs == 50
    assert out.baseline_solve_ms >= 0.0
    assert out.simulation_runs_per_second > 0.0


def test_highs_backend_parity_with_cp_sat():
    players = _players()
    rules = Rules(salary_cap=70000)

    cp = CashOptimizer(
        players=players,
        rules=rules,
        solver_settings=SolverSettings(solver_backend="cp-sat"),
    )
    hs = CashOptimizer(
        players=players,
        rules=rules,
        solver_settings=SolverSettings(solver_backend="highs"),
    )

    cp_res = cp.solve_optimal()
    hs_res = hs.solve_optimal()

    assert cp_res.lineup.player_ids == hs_res.lineup.player_ids
    assert cp_res.optimal_projection == hs_res.optimal_projection


def test_runtime_defaults_load_from_json(tmp_path):
    path = tmp_path / "defaults.json"
    path.write_text(
        """
{
  "parameter_version": "v2-test",
  "solver_backend": "highs",
  "simulation_num_runs_default": 42,
  "simulation_sampling_mode": "independent"
}
""".strip(),
        encoding="utf-8",
    )

    defaults = load_runtime_defaults(path)
    assert defaults.parameter_version == "v2-test"
    assert defaults.solver_backend == "highs"
    assert defaults.simulation_num_runs_default == 42


def test_append_benchmark_history_writes_row(tmp_path):
    players = _players()
    optimizer = CashOptimizer(players=players, rules=Rules(salary_cap=70000))
    result = run_performance_benchmarks(
        optimizer=optimizer,
        simulation_runs=20,
        baseline_threshold_ms=10000.0,
        sensitivity_threshold_ms=30000.0,
        simulation_threshold_ms=30000.0,
    )
    out = tmp_path / "bench_history.csv"
    append_benchmark_history(out, result, parameter_version="v-test", note="unit")

    text = out.read_text(encoding="utf-8")
    assert "timestamp_utc" in text
    assert "parameter_version" in text
    assert "v-test" in text


def test_runtime_defaults_to_solver_settings():
    defaults = RuntimeDefaults(solver_backend="highs", sensitivity_worker_count=3)
    settings = defaults.to_solver_settings()
    assert settings.solver_backend == "highs"
    assert settings.sensitivity_worker_count == 3


def test_run_readiness_gate_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    result = run_readiness_gate(
        optimizer=optimizer,
        simulation_runs=20,
        baseline_threshold_ms=60000.0,
        sensitivity_threshold_ms=60000.0,
        simulation_threshold_ms=60000.0,
    )

    assert result.lineup_valid is True
    assert result.sensitivity_coverage_complete is True
    assert result.deterministic_optimal is True
    assert isinstance(result.reasons, tuple)


def test_recommend_rollout_stage_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    readiness = run_readiness_gate(
        optimizer=optimizer,
        simulation_runs=20,
        baseline_threshold_ms=60000.0,
        sensitivity_threshold_ms=60000.0,
        simulation_threshold_ms=60000.0,
    )
    rollout = recommend_rollout_stage(readiness)

    assert rollout.stage in {"phase5_polish", "phase4_validation", "phase2_sensitivity", "phase1_core_optimizer"}
    assert isinstance(rollout.can_promote, bool)


def test_calibrate_benchmark_thresholds_from_history(tmp_path):
    history = tmp_path / "history.csv"
    history.write_text(
        "\n".join(
            [
                "timestamp_utc,parameter_version,note,baseline_solve_ms,sensitivity_ms,simulation_runs,simulation_ms,simulation_runs_per_second,baseline_under_threshold,sensitivity_under_threshold,simulation_under_threshold",
                "2026-01-01T00:00:00+00:00,v1,a,100,500,20,300,66.6,true,true,true",
                "2026-01-02T00:00:00+00:00,v1,b,120,600,20,350,57.1,true,true,true",
                "2026-01-03T00:00:00+00:00,v1,c,140,700,20,400,50.0,true,true,true",
                "2026-01-04T00:00:00+00:00,v1,d,160,800,20,450,44.4,true,true,true",
                "2026-01-05T00:00:00+00:00,v1,e,180,900,20,500,40.0,true,true,true",
            ]
        ),
        encoding="utf-8",
    )

    rec = calibrate_benchmark_thresholds_from_history(
        history_csv=history,
        percentile=0.8,
        safety_multiplier=1.1,
        min_samples=5,
    )

    assert rec.sample_count == 5
    assert rec.baseline_threshold_ms > 0
    assert rec.sensitivity_threshold_ms > 0
    assert rec.simulation_threshold_ms > 0


def test_run_governance_check_smoke():
    optimizer = CashOptimizer(players=_players(), rules=Rules(salary_cap=70000))
    readiness = run_readiness_gate(
        optimizer=optimizer,
        simulation_runs=20,
        baseline_threshold_ms=60000.0,
        sensitivity_threshold_ms=60000.0,
        simulation_threshold_ms=60000.0,
    )
    rollout = recommend_rollout_stage(readiness)
    gov = run_governance_check(
        readiness=readiness,
        rollout=rollout,
        require_clean=True,
        minimum_stage="phase4_validation",
    )

    assert isinstance(gov.accepted, bool)
    assert isinstance(gov.reasons, tuple)
