from pathlib import Path

from click.testing import CliRunner

from cash_optimizer_cli.main import cli


def _input_csv_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    root_proj = root / "proj.csv"
    if root_proj.exists():
        return root_proj
    tests_proj = root / "tests" / "proj.csv"
    if tests_proj.exists():
        return tests_proj
    raise FileNotFoundError("Could not locate proj.csv test input")


def test_cli_optimize_smoke():
    runner = CliRunner()
    result = runner.invoke(cli, ["--input-csv", str(_input_csv_path()), "optimize"])

    assert result.exit_code == 0
    assert "optimal_projection" in result.output or "objective_value" in result.output


def test_cli_optimize_verbose_logs():
    runner = CliRunner()
    result = runner.invoke(cli, ["--input-csv", str(_input_csv_path()), "--verbose", "optimize"])

    assert result.exit_code == 0
    assert "[verbose]" in result.output
    assert "Completed command" in result.output


def test_cli_optimize_rich_flag_smoke():
    runner = CliRunner()
    result = runner.invoke(cli, ["--input-csv", str(_input_csv_path()), "--rich", "optimize"])

    assert result.exit_code == 0
    assert "optimal_projection" in result.output or "objective_value" in result.output


def test_cli_candidates_smoke():
    runner = CliRunner()
    result = runner.invoke(cli, ["--input-csv", str(_input_csv_path()), "candidates", "--count", "5"])

    assert result.exit_code == 0
    assert "candidate_count" in result.output


def test_cli_candidates_save(tmp_path: Path):
    runner = CliRunner()
    out_path = tmp_path / "candidates.csv"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "candidates",
            "--count",
            "5",
            "--save",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert out_path.exists()


def test_cli_optimize_projection_override(tmp_path: Path):
    runner = CliRunner()

    override_path = tmp_path / "override.csv"
    override_path.write_text("player_id,projection\nqb_bal_lamar_jackson,1\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "optimize",
            "--projection-file",
            str(override_path),
        ],
    )

    assert result.exit_code == 0
    assert "optimal_projection" in result.output


def test_cli_optimize_save_json(tmp_path: Path):
    runner = CliRunner()
    out_path = tmp_path / "optimal.json"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "optimize",
            "--save",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert out_path.exists()
    assert "optimal_projection" in out_path.read_text(encoding="utf-8")


def test_cli_calibrate_validation_exit_code(tmp_path: Path):
    runner = CliRunner()
    bad_path = tmp_path / "bad_calibration.csv"
    bad_path.write_text("foo,bar\n1,2\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "calibrate",
            "--input",
            str(bad_path),
        ],
    )

    assert result.exit_code == 2


def test_cli_optimize_robust_requires_cov_source():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "optimize",
            "--robust-rho",
            "0.35",
        ],
    )

    assert result.exit_code == 2
    assert "robust-cov-source" in result.output


def test_cli_optimize_robust_with_cov_source(tmp_path: Path):
    runner = CliRunner()

    cov_src = tmp_path / "robust_errors.csv"
    cov_src.write_text(
        "\n".join(
            [
                "player_id,w1,w2,w3,w4,w5",
                "qb_bal_lamar_jackson,1.1,0.2,-0.4,0.6,0.0",
                "rb_bal_derrick_henry,0.2,-0.3,0.1,0.0,0.4",
                "wr_bal_zay_flowers,-0.5,0.1,0.2,-0.2,0.3",
                "dst_bal_ravens,0.3,0.0,-0.1,0.2,-0.2",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "optimize",
            "--robust-rho",
            "0.35",
            "--robust-set",
            "box",
            "--robust-cov-source",
            str(cov_src),
        ],
    )

    assert result.exit_code == 0
    assert "optimal_projection" in result.output


def test_cli_compare_human_smoke():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "compare-human",
            "--trials",
            "100",
            "--top-n-per-slot",
            "8",
        ],
    )

    assert result.exit_code == 0
    assert "optimizer_projection" in result.output


def test_cli_select_normalized_smoke():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "select-normalized",
            "--mean-weight",
            "1.0",
            "--risk-weight",
            "0.5",
            "--cov-weight",
            "0.25",
            "--cash-prob-weight",
            "0.2",
            "--threshold",
            "120",
            "--candidates",
            "6",
            "--runs",
            "200",
        ],
    )

    assert result.exit_code == 0
    assert "selected_lineup_player_ids" in result.output


def test_cli_optimize_profile_smoke(tmp_path: Path):
    runner = CliRunner()

    news_csv = tmp_path / "news.csv"
    news_csv.write_text(
        "\n".join(
            [
                "player_id,signal",
                "qb_bal_lamar_jackson,questionable_tag",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "optimize-profile",
            "--contest-profile",
            "double_up",
            "--threshold",
            "120",
            "--candidates",
            "6",
            "--runs",
            "200",
            "--news-signal-file",
            str(news_csv),
        ],
    )

    assert result.exit_code == 0
    assert "selected_lineup_player_ids" in result.output


def test_cli_benchmark_smoke():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "benchmark",
            "--simulation-runs",
            "50",
            "--baseline-threshold-ms",
            "10000",
            "--sensitivity-threshold-ms",
            "30000",
            "--simulation-threshold-ms",
            "30000",
        ],
    )

    assert result.exit_code == 0
    assert "baseline_solve_ms" in result.output


def test_cli_stress_save_with_scenario_file(tmp_path: Path):
    runner = CliRunner()

    scenario_csv = tmp_path / "scenarios.csv"
    scenario_csv.write_text(
        "\n".join(
            [
                "scenario_name,projection_multiplier_global,QB,RB,WR,TE,DST",
                "all_down_5,0.95,1.0,1.0,1.0,1.0,1.0",
                "wr_down_12,1.0,1.0,1.0,0.88,1.0,1.0",
            ]
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "stress.csv"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "stress",
            "--scenario-file",
            str(scenario_csv),
            "--save",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert out_path.exists()


def test_cli_export_simulation_options_parity(tmp_path: Path):
    runner = CliRunner()
    output_dir = tmp_path / "exports"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--output-dir",
            str(output_dir),
            "export",
            "--runs",
            "40",
            "--sampling-mode",
            "independent",
            "--workers",
            "1",
            "--chunk-size",
            "8",
            "--top-k-lineups",
            "10",
            "--clip-min",
            "0",
            "--save-prefix",
            "custom_sim",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "optimal_lineup.csv").exists()
    assert (output_dir / "sensitivity.csv").exists()
    assert (output_dir / "custom_sim_summary.csv").exists()
    assert (output_dir / "custom_sim_player_stats.csv").exists()
    assert (output_dir / "custom_sim_lineup_stats.csv").exists()


def test_cli_defaults_file_applies_simulate_defaults(tmp_path: Path):
    runner = CliRunner()
    defaults_path = tmp_path / "defaults.json"
    defaults_path.write_text(
        """
{
  "parameter_version": "v2-test",
  "simulation_num_runs_default": 17,
  "simulation_sampling_mode": "independent",
  "simulation_worker_count": 1,
  "simulation_chunk_size": 8,
  "simulation_top_k_lineups": 5,
  "simulation_save_prefix": "sim_defaults"
}
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--defaults-file",
            str(defaults_path),
            "simulate",
        ],
    )

    assert result.exit_code == 0
    assert "num_runs: 17" in result.output


def test_cli_benchmark_history_csv(tmp_path: Path):
    runner = CliRunner()
    history = tmp_path / "history.csv"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "benchmark",
            "--simulation-runs",
            "20",
            "--baseline-threshold-ms",
            "60000",
            "--sensitivity-threshold-ms",
            "60000",
            "--simulation-threshold-ms",
            "60000",
            "--history-csv",
            str(history),
            "--history-note",
            "cli-test",
        ],
    )

    assert result.exit_code == 0
    assert history.exists()
    assert "parameter_version" in history.read_text(encoding="utf-8")


def test_cli_benchmark_threshold_profile_ci():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "benchmark",
            "--simulation-runs",
            "20",
            "--threshold-profile",
            "ci",
            "--threshold-scale",
            "1.0",
        ],
    )

    assert result.exit_code == 0
    assert '"threshold_profile": "ci"' in result.output
    assert '"baseline_threshold_ms": 5000.0' in result.output


def test_cli_readiness_gate_success():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "readiness-gate",
            "--simulation-runs",
            "20",
            "--threshold-profile",
            "ci",
        ],
    )

    assert result.exit_code == 0
    assert '"accepted": true' in result.output


def test_cli_readiness_gate_failure_exit_code():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "readiness-gate",
            "--simulation-runs",
            "20",
            "--baseline-threshold-ms",
            "0.0001",
            "--sensitivity-threshold-ms",
            "0.0001",
            "--simulation-threshold-ms",
            "0.0001",
            "--threshold-profile",
            "custom",
        ],
    )

    assert result.exit_code == 1
    assert "Readiness gate failed" in result.output


def test_cli_rollout_recommend_smoke():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "rollout-recommend",
            "--simulation-runs",
            "20",
            "--threshold-profile",
            "ci",
            "--allow-blockers",
        ],
    )

    assert result.exit_code == 0
    assert '"rollout"' in result.output
    assert '"stage"' in result.output


def test_cli_rollout_recommend_require_clean_failure():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "rollout-recommend",
            "--simulation-runs",
            "20",
            "--threshold-profile",
            "custom",
            "--baseline-threshold-ms",
            "0.0001",
            "--sensitivity-threshold-ms",
            "0.0001",
            "--simulation-threshold-ms",
            "0.0001",
            "--require-clean",
        ],
    )

    assert result.exit_code == 1
    assert "Rollout recommendation includes blockers" in result.output


def test_cli_benchmark_calibrate_writes_env(tmp_path: Path):
    runner = CliRunner()
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
    env_path = tmp_path / "bench.env"

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "benchmark-calibrate",
            "--history-csv",
            str(history),
            "--write-env",
            str(env_path),
        ],
    )

    assert result.exit_code == 0
    assert env_path.exists()
    env_text = env_path.read_text(encoding="utf-8")
    assert "BENCH_BASELINE_MS=" in env_text
    assert '"sample_count": 5' in result.output


def test_cli_governance_check_policy(tmp_path: Path):
    runner = CliRunner()
    policy = tmp_path / "policy.json"
    policy.write_text(
        "\n".join(
            [
                "{",
                '  "simulation_runs": 20,',
                '  "threshold_profile": "ci",',
                '  "threshold_scale": 1.0,',
                '  "require_clean": true,',
                '  "minimum_stage": "phase4_validation"',
                "}",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "--input-csv",
            str(_input_csv_path()),
            "--json",
            "governance-check",
            "--policy-file",
            str(policy),
        ],
    )

    assert result.exit_code == 0
    assert '"governance"' in result.output
    assert '"accepted": true' in result.output
