from __future__ import annotations

import csv
import json
from pathlib import Path

from cash_optimizer import (
    CashOptimizer,
    RobustSettings,
    RobustUncertaintySet,
    Rules,
    SimulationConfig,
    StressScenario,
    build_edge_trend_from_slate_paths,
    build_error_covariance_aligned_by_player,
    evaluate_prediction_models_by_position,
    load_cash_lines,
    load_prediction_eval_rows,
)
from cash_optimizer.io import load_players_from_dk_csv
from cash_optimizer_cli.exporters import write_edge_trend, write_optimal_lineup, write_sensitivity, write_simulation


class OptimizerService:
    def __init__(self) -> None:
        self._optimizer: CashOptimizer | None = None
        self._loaded_path: Path | None = None

    def load_csv(self, path: Path, rules: Rules | None = None) -> CashOptimizer:
        players = load_players_from_dk_csv(path)
        self._optimizer = CashOptimizer(players=players, rules=rules or Rules())
        self._loaded_path = path
        return self._optimizer

    @property
    def loaded_path(self) -> Path | None:
        return self._loaded_path

    @property
    def optimizer(self) -> CashOptimizer:
        if self._optimizer is None:
            raise ValueError("No slate loaded")
        return self._optimizer

    def export_artifacts(self, output_dir: Path, runs: int = 1000, write_json_summary: bool = False) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        optimal = self.optimizer.solve_optimal()
        write_optimal_lineup(output_dir / "optimal_lineup.csv", optimal)

        sensitivity = self.optimizer.solve_sensitivity_all()
        write_sensitivity(output_dir / "sensitivity.csv", sensitivity)

        sim = self.optimizer.run_projection_distribution_simulation(
            SimulationConfig(
                num_runs=runs,
                random_seed=self.optimizer.solver_settings.cp_sat_random_seed,
                worker_count=1,
            )
        )
        write_simulation(output_dir / "simulation", sim)

        if write_json_summary:
            summary = {
                "optimal": {
                    "projection": optimal.optimal_projection,
                    "salary": optimal.lineup.salary_used,
                    "player_ids": list(optimal.lineup.player_ids),
                },
                "sensitivity": {
                    "entry_count": len(sensitivity.entries),
                    "fragility": (
                        None
                        if sensitivity.fragility_summary is None
                        else {
                            "fragility_score": sensitivity.fragility_summary.fragility_score,
                            "alert": sensitivity.fragility_summary.alert,
                        }
                    ),
                },
                "simulation": {
                    "num_runs": sim.num_runs,
                    "mean": sim.mean_optimal_projection,
                    "p05": sim.p05_optimal_projection,
                    "p50": sim.p50_optimal_projection,
                    "p95": sim.p95_optimal_projection,
                    "unique_lineups": sim.unique_lineups,
                },
            }
            (output_dir / "summary_bundle.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return output_dir

    def run_stress(self, projection_overrides: list[float] | None = None, scenario_file: Path | None = None):
        scenarios = self._load_stress_scenarios_from_csv(scenario_file) if scenario_file else None
        return self.optimizer.run_stress_test(base_projections=projection_overrides, scenarios=scenarios)

    def solve_optimal(
        self,
        robust_enabled: bool = False,
        robust_rho: float = 0.0,
        robust_corr_threshold: float = 0.0,
        robust_set: str = "box",
        robust_cov_source: Path | None = None,
    ):
        robust_inputs = self._resolve_robust_inputs(
            robust_enabled=robust_enabled,
            robust_rho=robust_rho,
            robust_corr_threshold=robust_corr_threshold,
            robust_set=robust_set,
            robust_cov_source=robust_cov_source,
        )
        if robust_inputs is None:
            return self.optimizer.solve_optimal()
        robust_settings, robust_covariance = robust_inputs
        return self.optimizer.solve_optimal(
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

    def solve_sensitivity(
        self,
        robust_enabled: bool = False,
        robust_rho: float = 0.0,
        robust_corr_threshold: float = 0.0,
        robust_set: str = "box",
        robust_cov_source: Path | None = None,
    ):
        robust_inputs = self._resolve_robust_inputs(
            robust_enabled=robust_enabled,
            robust_rho=robust_rho,
            robust_corr_threshold=robust_corr_threshold,
            robust_set=robust_set,
            robust_cov_source=robust_cov_source,
        )
        if robust_inputs is None:
            return self.optimizer.solve_sensitivity_all()
        robust_settings, robust_covariance = robust_inputs
        return self.optimizer.solve_sensitivity_all(
            robust_settings=robust_settings,
            robust_covariance=robust_covariance,
        )

    def evaluate_prediction_models(
        self,
        input_csv: Path,
        model_columns: list[str],
        position_col: str = "position",
        actual_col: str = "actual",
        save_csv: Path | None = None,
    ):
        rows = load_prediction_eval_rows(input_csv)
        result = evaluate_prediction_models_by_position(
            rows=rows,
            model_columns=model_columns,
            position_column=position_col,
            actual_column=actual_col,
        )
        if save_csv is not None:
            save_csv.parent.mkdir(parents=True, exist_ok=True)
            with save_csv.open("w", newline="", encoding="utf-8") as f:
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
        return result

    def build_edge_trend(
        self,
        slate_paths: list[Path],
        trials: int,
        top_n_per_slot: int,
        cash_lines_csv: Path | None = None,
        save_csv: Path | None = None,
    ):
        cash_line_by_slate = load_cash_lines(cash_lines_csv) if cash_lines_csv is not None else None
        result = build_edge_trend_from_slate_paths(
            slate_paths=slate_paths,
            rules=self.optimizer.rules,
            solver_settings=self.optimizer.solver_settings,
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            cash_line_by_slate=cash_line_by_slate,
        )
        if save_csv is not None:
            write_edge_trend(save_csv, result)
        return result

    def _resolve_robust_inputs(
        self,
        robust_enabled: bool,
        robust_rho: float,
        robust_corr_threshold: float,
        robust_set: str,
        robust_cov_source: Path | None,
    ) -> tuple[RobustSettings, list[list[float]]] | None:
        if not robust_enabled:
            return None
        if robust_rho <= 0:
            raise ValueError("Robust rho must be > 0 when robust mode is enabled")
        if robust_cov_source is None:
            raise ValueError("Robust error CSV is required when robust mode is enabled")
        if not robust_cov_source.exists() or not robust_cov_source.is_file():
            raise ValueError(f"Robust error CSV not found: {robust_cov_source}")

        history_by_player: dict[str, list[float | None]] = {}
        with robust_cov_source.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "player_id" not in reader.fieldnames:
                raise ValueError("Robust error CSV must include a player_id column")
            history_cols = [c for c in reader.fieldnames if c != "player_id"]
            if not history_cols:
                raise ValueError("Robust error CSV must include at least one history column")

            for row in reader:
                pid = str(row.get("player_id", "")).strip()
                if not pid:
                    continue
                values: list[float | None] = []
                for col in history_cols:
                    cell = str(row.get(col, "")).strip()
                    values.append(float(cell) if cell else None)
                history_by_player[pid] = values

        covariance = build_error_covariance_aligned_by_player(
            ordered_player_ids=[p.player_id for p in self.optimizer.players],
            error_history_by_player_id=history_by_player,
        )
        robust_settings = RobustSettings(
            enabled=True,
            rho=float(robust_rho),
            uncertainty_set=RobustUncertaintySet(robust_set),
            correlation_sparsification_threshold=float(robust_corr_threshold),
        )
        return robust_settings, covariance.tolist()

    def _load_stress_scenarios_from_csv(self, path: Path) -> tuple[StressScenario, ...]:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Scenario file not found: {path}")

        scenarios: list[StressScenario] = []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "scenario_name" not in set(reader.fieldnames):
                raise ValueError("Scenario CSV must include column: scenario_name")

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
                        projection_multiplier_global=projection_multiplier_global,
                        projection_multiplier_by_position=by_position,
                    )
                )

        if not scenarios:
            raise ValueError("Scenario CSV must contain at least one valid scenario row")
        return tuple(scenarios)
