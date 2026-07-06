from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal

from cash_optimizer import Rules, SimulationConfig, compute_calibration_metrics

from ..services.optimizer_service import OptimizerService
from ..workers.task_worker import TaskWorker


class MainViewModel(QObject):
    status_changed = Signal(str)
    progress_changed = Signal(str)
    optimal_ready = Signal(object)
    sensitivity_ready = Signal(object)
    simulation_ready = Signal(object)
    stress_ready = Signal(object)
    candidates_ready = Signal(object)
    select_cash_ready = Signal(object)
    calibration_ready = Signal(object)
    prediction_eval_ready = Signal(object)
    edge_trend_ready = Signal(object)
    export_ready = Signal(object)
    log_message = Signal(str)
    task_state_changed = Signal(str, str, str, int)
    error_raised = Signal(str)

    def __init__(self, service: OptimizerService | None = None) -> None:
        super().__init__()
        self.service = service or OptimizerService()
        self.pool = QThreadPool.globalInstance()
        self._active_workers: dict[str, TaskWorker] = {}
        self._active_timers: dict[str, QTimer] = {}
        self._active_progress: dict[str, int] = {}
        self._last_failed_task: tuple[Callable, object, str] | None = None
        self._rules = Rules()

    def load_csv(self, path: Path, rules: Rules | None = None) -> None:
        if rules is not None:
            self._rules = rules
        self.service.load_csv(path, rules=self._rules)
        self.log_message.emit(f"Loaded CSV: {path}")
        self.status_changed.emit(f"Loaded {path}")

    def update_rules(self, rules: Rules) -> None:
        self._rules = rules
        if self.service.loaded_path is not None:
            self.load_csv(self.service.loaded_path, rules=rules)

    def run_optimize(
        self,
        robust_enabled: bool = False,
        robust_rho: float = 0.0,
        robust_corr_threshold: float = 0.0,
        robust_set: str = "box",
        robust_cov_source: Path | None = None,
    ) -> None:
        def _task(progress_callback=None):
            if progress_callback is not None:
                progress_callback(20, "Building optimize request")
            result = self.service.solve_optimal(
                robust_enabled=robust_enabled,
                robust_rho=robust_rho,
                robust_corr_threshold=robust_corr_threshold,
                robust_set=robust_set,
                robust_cov_source=robust_cov_source,
            )
            if progress_callback is not None:
                progress_callback(95, "Finalize optimize result")
            return result

        self._run_task(
            _task,
            self.optimal_ready,
            "Optimize",
        )

    def run_sensitivity(
        self,
        robust_enabled: bool = False,
        robust_rho: float = 0.0,
        robust_corr_threshold: float = 0.0,
        robust_set: str = "box",
        robust_cov_source: Path | None = None,
    ) -> None:
        def _task(progress_callback=None):
            if progress_callback is not None:
                progress_callback(15, "Preparing sensitivity solves")
            result = self.service.solve_sensitivity(
                robust_enabled=robust_enabled,
                robust_rho=robust_rho,
                robust_corr_threshold=robust_corr_threshold,
                robust_set=robust_set,
                robust_cov_source=robust_cov_source,
            )
            if progress_callback is not None:
                progress_callback(95, "Finalize sensitivity result")
            return result

        self._run_task(
            _task,
            self.sensitivity_ready,
            "Sensitivity",
        )

    def run_simulation(self, runs: int = 2000) -> None:
        cfg = SimulationConfig(num_runs=runs, worker_count=1)

        def _task(progress_callback=None):
            if progress_callback is not None:
                progress_callback(15, "Preparing simulation")
            result = self.service.optimizer.run_projection_distribution_simulation(cfg)
            if progress_callback is not None:
                progress_callback(95, "Finalize simulation result")
            return result

        self._run_task(
            _task,
            self.simulation_ready,
            "Simulation",
        )

    def run_stress(self, scenario_file: Path | None = None) -> None:
        def _task(progress_callback=None):
            if progress_callback is not None:
                progress_callback(20, "Preparing stress scenarios")
            result = self.service.run_stress(scenario_file=scenario_file)
            if progress_callback is not None:
                progress_callback(95, "Finalize stress result")
            return result

        self._run_task(
            _task,
            self.stress_ready,
            "Stress",
        )

    def run_candidates(self, count: int = 25) -> None:
        self._run_task(
            lambda: self.service.optimizer.generate_candidate_lineups(count),
            self.candidates_ready,
            "Candidates",
        )

    def run_select_cash(self, threshold: float, candidates: int = 25, runs: int = 2000) -> None:
        cfg = SimulationConfig(num_runs=runs, worker_count=1)
        self._run_task(
            lambda: self.service.optimizer.select_best_cash_lineup_by_probability(
                threshold=threshold,
                num_candidates=candidates,
                simulation_config=cfg,
            ),
            self.select_cash_ready,
            "Select Cash",
        )

    def run_calibration(self, csv_path: Path) -> None:
        def _compute():
            import csv

            preds: list[float] = []
            obs: list[int] = []
            with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    preds.append(float(row["predicted_probability"]))
                    obs.append(int(row["observed_event"]))
            return compute_calibration_metrics(preds, obs)

        self._run_task(_compute, self.calibration_ready, "Calibrate")

    def run_export(self, output_dir: Path, runs: int = 1000, write_json_summary: bool = False) -> None:
        self._run_task(
            lambda: self.service.export_artifacts(
                output_dir=output_dir,
                runs=runs,
                write_json_summary=write_json_summary,
            ),
            self.export_ready,
            "Export",
        )

    def run_prediction_eval(
        self,
        eval_csv: Path,
        model_columns: list[str],
        position_col: str = "position",
        actual_col: str = "actual",
        save_csv: Path | None = None,
    ) -> None:
        self._run_task(
            lambda: self.service.evaluate_prediction_models(
                input_csv=eval_csv,
                model_columns=model_columns,
                position_col=position_col,
                actual_col=actual_col,
                save_csv=save_csv,
            ),
            self.prediction_eval_ready,
            "Eval Predictions",
        )

    def run_edge_trend(
        self,
        slate_paths: list[Path],
        trials: int,
        top_n_per_slot: int,
        cash_lines_csv: Path | None = None,
        save_csv: Path | None = None,
    ) -> None:
        self._run_task(
            lambda: self.service.build_edge_trend(
                slate_paths=slate_paths,
                trials=trials,
                top_n_per_slot=top_n_per_slot,
                cash_lines_csv=cash_lines_csv,
                save_csv=save_csv,
            ),
            self.edge_trend_ready,
            "Edge Trend",
        )

    def cancel_all_tasks(self) -> None:
        for worker in self._active_workers.values():
            worker.cancel()
        for timer in self._active_timers.values():
            timer.stop()
        self._active_workers.clear()
        self._active_timers.clear()
        self._active_progress.clear()
        self.progress_changed.emit("Cancelled active tasks")
        self.log_message.emit("Cancelled active tasks")

    def cancel_task(self, task_id: str) -> None:
        worker = self._active_workers.get(task_id)
        if worker is None:
            return
        worker.cancel()
        self.log_message.emit(f"Cancellation requested: {task_id}")

    def retry_last_failed_task(self) -> bool:
        if self._last_failed_task is None:
            return False
        fn, signal, task_name = self._last_failed_task
        self._run_task(fn, signal, task_name)
        return True

    def _run_task(self, fn: Callable, signal, task_name: str) -> None:
        task_id = uuid4().hex[:8]
        self.progress_changed.emit(f"Running task: {task_name}")
        worker = TaskWorker(fn)
        self._active_workers[task_id] = worker
        self._active_progress[task_id] = 50
        self.task_state_changed.emit(task_id, task_name, "queued", 5)
        self.task_state_changed.emit(task_id, task_name, "running", 50)

        timer = QTimer(self)
        timer.setInterval(250)

        def _heartbeat():
            current = self._active_progress.get(task_id, 50)
            next_val = min(95, current + 2)
            self._active_progress[task_id] = next_val
            self.task_state_changed.emit(task_id, task_name, "running", next_val)

        timer.timeout.connect(_heartbeat)
        timer.start()
        self._active_timers[task_id] = timer

        def _on_finished(result):
            self._active_workers.pop(task_id, None)
            t = self._active_timers.pop(task_id, None)
            if t is not None:
                t.stop()
            self._active_progress.pop(task_id, None)
            self.progress_changed.emit(f"Task completed: {task_name}")
            self.task_state_changed.emit(task_id, task_name, "completed", 100)
            signal.emit(result)

        def _on_progress(percent: int, message: str):
            if task_id not in self._active_progress:
                return
            self._active_progress[task_id] = max(self._active_progress.get(task_id, 0), percent)
            self.task_state_changed.emit(task_id, task_name, "running", self._active_progress[task_id])
            if message:
                self.progress_changed.emit(f"{task_name}: {message}")

        def _on_failed(message: str):
            self._active_workers.pop(task_id, None)
            t = self._active_timers.pop(task_id, None)
            if t is not None:
                t.stop()
            self._active_progress.pop(task_id, None)
            self.progress_changed.emit(f"Task failed: {task_name}")
            self.task_state_changed.emit(task_id, task_name, "failed", 100)
            self.log_message.emit(f"Error: {message}")
            self._last_failed_task = (fn, signal, task_name)
            self.error_raised.emit(message)

        def _on_cancelled():
            self._active_workers.pop(task_id, None)
            t = self._active_timers.pop(task_id, None)
            if t is not None:
                t.stop()
            self._active_progress.pop(task_id, None)
            self.progress_changed.emit(f"Task cancelled: {task_name}")
            self.task_state_changed.emit(task_id, task_name, "cancelled", 100)
            self.log_message.emit(f"Task cancelled: {task_id}")

        worker.signals.finished.connect(_on_finished)
        worker.signals.failed.connect(_on_failed)
        worker.signals.cancelled.connect(_on_cancelled)
        worker.signals.progress.connect(_on_progress)
        self.pool.start(worker)
