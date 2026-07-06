from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cash_optimizer import Rules

from .models.table_models import (
    DictTableModel,
    OptimalLineupTableModel,
    ScenarioResultsModel,
    SensitivityTableModel,
    SimulationLineupStatsModel,
)
from .viewmodels.main_viewmodel import MainViewModel
from .views.result_view import ResultView
from .views.simulation_chart import SimulationSummaryChart


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("cash-optimizer")
        self.resize(1100, 720)

        self.vm = MainViewModel()
        self.vm.status_changed.connect(self._set_status)
        self.vm.progress_changed.connect(self._set_progress)
        self.vm.task_state_changed.connect(self._on_task_state)
        self.vm.error_raised.connect(self._show_error)
        self.vm.log_message.connect(self._append_log)
        self.vm.optimal_ready.connect(self._on_optimal)
        self.vm.sensitivity_ready.connect(self._on_sensitivity)
        self.vm.simulation_ready.connect(self._on_simulation)
        self.vm.stress_ready.connect(self._on_stress)
        self.vm.candidates_ready.connect(self._on_candidates)
        self.vm.select_cash_ready.connect(self._on_select_cash)
        self.vm.calibration_ready.connect(self._on_calibration)
        self.vm.prediction_eval_ready.connect(self._on_prediction_eval)
        self.vm.edge_trend_ready.connect(self._on_edge_trend)
        self.vm.export_ready.connect(self._on_export_ready)
        self._task_items: dict[str, QListWidgetItem] = {}

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        self.btn_load = QPushButton("Load CSV")
        self.btn_optimize = QPushButton("Optimize")
        self.btn_sensitivity = QPushButton("Sensitivity")
        self.btn_simulate = QPushButton("Simulate")
        self.btn_stress = QPushButton("Stress")
        self.btn_candidates = QPushButton("Candidates")
        self.btn_select_cash = QPushButton("Select Cash")
        self.btn_calibrate = QPushButton("Calibrate")
        self.btn_eval_predictions = QPushButton("Eval Predictions")
        self.btn_edge_trend = QPushButton("Edge Trend")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_export = QPushButton("Export")
        self.btn_load.setAccessibleName("action-load-csv")
        self.btn_optimize.setAccessibleName("action-optimize")
        self.btn_sensitivity.setAccessibleName("action-sensitivity")
        self.btn_simulate.setAccessibleName("action-simulate")
        self.btn_stress.setAccessibleName("action-stress")
        self.btn_candidates.setAccessibleName("action-candidates")
        self.btn_select_cash.setAccessibleName("action-select-cash")
        self.btn_calibrate.setAccessibleName("action-calibrate")
        self.btn_eval_predictions.setAccessibleName("action-eval-predictions")
        self.btn_edge_trend.setAccessibleName("action-edge-trend")
        self.btn_cancel.setAccessibleName("action-cancel")
        self.btn_export.setAccessibleName("action-export")
        toolbar.addWidget(self.btn_load)
        toolbar.addWidget(self.btn_optimize)
        toolbar.addWidget(self.btn_sensitivity)
        toolbar.addWidget(self.btn_simulate)
        toolbar.addWidget(self.btn_stress)
        toolbar.addWidget(self.btn_candidates)
        toolbar.addWidget(self.btn_select_cash)
        toolbar.addWidget(self.btn_calibrate)
        toolbar.addWidget(self.btn_eval_predictions)
        toolbar.addWidget(self.btn_edge_trend)
        toolbar.addWidget(self.btn_cancel)
        toolbar.addWidget(self.btn_export)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        data_panel = QGroupBox("Data Panel")
        data_form = QFormLayout(data_panel)
        self.data_path_label = QLabel("No file loaded")
        self.data_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.data_path_label.setWordWrap(True)
        self.data_summary_label = QLabel("Players: 0")
        self.data_rules_label = QLabel("Rules: salary_cap=50000, max_team=None, qb_vs_opp_dst=allow")
        self.data_rules_label.setWordWrap(True)
        data_form.addRow("Loaded CSV", self.data_path_label)
        data_form.addRow("Player Summary", self.data_summary_label)
        data_form.addRow("Rules", self.data_rules_label)
        layout.addWidget(data_panel)

        controls = QGroupBox("Run Controls")
        controls_form = QFormLayout(controls)
        self.salary_cap_spin = QSpinBox()
        self.salary_cap_spin.setRange(10000, 100000)
        self.salary_cap_spin.setValue(50000)
        self.max_team_spin = QSpinBox()
        self.max_team_spin.setRange(0, 9)
        self.max_team_spin.setValue(0)
        self.max_team_spin.setSpecialValueText("None")
        self.disallow_qb_dst = QCheckBox("Disallow QB vs Opp DST")
        self.sim_runs_spin = QSpinBox()
        self.sim_runs_spin.setRange(10, 200000)
        self.sim_runs_spin.setValue(2000)
        self.candidates_spin = QSpinBox()
        self.candidates_spin.setRange(1, 500)
        self.candidates_spin.setValue(25)
        self.cash_threshold_spin = QDoubleSpinBox()
        self.cash_threshold_spin.setRange(1.0, 500.0)
        self.cash_threshold_spin.setValue(130.0)
        self.cash_threshold_spin.setDecimals(2)

        self.robust_enable = QCheckBox("Enable Robust Objective")
        self.robust_rho_spin = QDoubleSpinBox()
        self.robust_rho_spin.setRange(0.0, 10.0)
        self.robust_rho_spin.setDecimals(3)
        self.robust_rho_spin.setSingleStep(0.05)
        self.robust_rho_spin.setValue(0.35)
        self.robust_set_combo = QComboBox()
        self.robust_set_combo.addItems(["box", "polygon"])
        self.robust_corr_threshold_spin = QDoubleSpinBox()
        self.robust_corr_threshold_spin.setRange(0.0, 1.0)
        self.robust_corr_threshold_spin.setDecimals(2)
        self.robust_corr_threshold_spin.setSingleStep(0.05)
        self.robust_corr_threshold_spin.setValue(0.0)
        self.robust_cov_source_edit = QLineEdit()
        self.robust_cov_source_edit.setPlaceholderText("Select robust error CSV")
        self.robust_cov_source_edit.setReadOnly(True)
        self.btn_robust_cov_source = QPushButton("Select")
        robust_cov_row = QHBoxLayout()
        robust_cov_row.addWidget(self.robust_cov_source_edit)
        robust_cov_row.addWidget(self.btn_robust_cov_source)
        robust_cov_widget = QWidget()
        robust_cov_widget.setLayout(robust_cov_row)

        controls_form.addRow("Salary Cap", self.salary_cap_spin)
        controls_form.addRow("Max Players / Team", self.max_team_spin)
        controls_form.addRow("", self.disallow_qb_dst)
        controls_form.addRow("Simulation Runs", self.sim_runs_spin)
        controls_form.addRow("Candidate Count", self.candidates_spin)
        controls_form.addRow("Cash Threshold", self.cash_threshold_spin)
        controls_form.addRow("", self.robust_enable)
        controls_form.addRow("Robust Rho", self.robust_rho_spin)
        controls_form.addRow("Robust Corr Threshold", self.robust_corr_threshold_spin)
        controls_form.addRow("Robust Set", self.robust_set_combo)
        controls_form.addRow("Robust Error CSV", robust_cov_widget)

        self.stress_scenario_file_edit = QLineEdit()
        self.stress_scenario_file_edit.setPlaceholderText("Optional stress scenario CSV")
        self.stress_scenario_file_edit.setReadOnly(True)
        self.btn_stress_scenario_file = QPushButton("Select")
        stress_scenario_row = QHBoxLayout()
        stress_scenario_row.addWidget(self.stress_scenario_file_edit)
        stress_scenario_row.addWidget(self.btn_stress_scenario_file)
        stress_scenario_widget = QWidget()
        stress_scenario_widget.setLayout(stress_scenario_row)
        controls_form.addRow("Stress Scenario CSV", stress_scenario_widget)

        self.export_json_summary = QCheckBox("Export JSON Summary Bundle")
        controls_form.addRow("", self.export_json_summary)
        layout.addWidget(controls)

        analytics = QGroupBox("Analytics")
        analytics_form = QFormLayout(analytics)
        self.eval_models_edit = QTextEdit()
        self.eval_models_edit.setPlaceholderText("lr,rf,lstm")
        self.eval_models_edit.setFixedHeight(38)
        self.eval_position_col_edit = QTextEdit()
        self.eval_position_col_edit.setPlainText("position")
        self.eval_position_col_edit.setFixedHeight(38)
        self.eval_actual_col_edit = QTextEdit()
        self.eval_actual_col_edit.setPlainText("actual")
        self.eval_actual_col_edit.setFixedHeight(38)

        self.edge_trials_spin = QSpinBox()
        self.edge_trials_spin.setRange(10, 50000)
        self.edge_trials_spin.setValue(1000)
        self.edge_top_n_spin = QSpinBox()
        self.edge_top_n_spin.setRange(1, 100)
        self.edge_top_n_spin.setValue(10)

        analytics_form.addRow("Prediction Model Columns (comma)", self.eval_models_edit)
        analytics_form.addRow("Prediction Position Column", self.eval_position_col_edit)
        analytics_form.addRow("Prediction Actual Column", self.eval_actual_col_edit)
        analytics_form.addRow("Edge Trend Trials", self.edge_trials_spin)
        analytics_form.addRow("Edge Trend Top N / Slot", self.edge_top_n_spin)
        layout.addWidget(analytics)

        task_box = QGroupBox("Task Status")
        task_layout = QVBoxLayout(task_box)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.task_list = QListWidget()
        cancel_row = QHBoxLayout()
        self.btn_cancel_selected = QPushButton("Cancel Selected")
        self.btn_cancel_all = QPushButton("Cancel All")
        cancel_row.addWidget(self.btn_cancel_selected)
        cancel_row.addWidget(self.btn_cancel_all)
        task_layout.addWidget(self.progress_bar)
        task_layout.addWidget(self.task_list)
        task_layout.addLayout(cancel_row)
        layout.addWidget(task_box)

        self.tabs = QTabWidget()
        self.opt_view = ResultView(model=OptimalLineupTableModel([]))
        self.sens_view = ResultView(model=SensitivityTableModel([]))
        self.sim_view = ResultView(model=SimulationLineupStatsModel([]))
        self.stress_view = ResultView(model=ScenarioResultsModel([]))
        self.candidates_view = ResultView(model=DictTableModel([]))
        self.select_cash_view = ResultView(model=DictTableModel([]))
        self.calibration_view = ResultView(model=DictTableModel([]))
        self.analytics_view = ResultView(model=DictTableModel([]))
        self.sim_chart = SimulationSummaryChart()
        self.logs_view = QTextEdit()
        self.logs_view.setReadOnly(True)
        self.tabs.addTab(self.opt_view, "Optimal")
        self.tabs.addTab(self.sens_view, "Sensitivity")
        self.tabs.addTab(self.sim_view, "Simulation")
        self.tabs.addTab(self.candidates_view, "Candidates")
        self.tabs.addTab(self.select_cash_view, "Select Cash")
        self.tabs.addTab(self.stress_view, "Stress")
        self.tabs.addTab(self.calibration_view, "Calibrate")
        self.tabs.addTab(self.analytics_view, "Analytics")
        self.tabs.addTab(self.logs_view, "Logs")

        self.opt_view.set_export_filename_hint("optimal_tab.csv")
        self.sens_view.set_export_filename_hint("sensitivity_tab.csv")
        self.sim_view.set_export_filename_hint("simulation_tab.csv")
        self.candidates_view.set_export_filename_hint("candidates_tab.csv")
        self.select_cash_view.set_export_filename_hint("select_cash_tab.csv")
        self.stress_view.set_export_filename_hint("stress_tab.csv")
        self.calibration_view.set_export_filename_hint("calibration_tab.csv")
        self.analytics_view.set_export_filename_hint("analytics_tab.csv")
        self.sim_view.layout().addWidget(self.sim_chart)
        layout.addWidget(self.tabs)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Load a CSV to begin")
        self.progress_label = QLabel("Idle")
        self.progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        status_row.addWidget(self.progress_label)
        layout.addLayout(status_row)

        self.btn_load.clicked.connect(self._load_csv)
        self.btn_optimize.clicked.connect(self._run_optimize)
        self.btn_sensitivity.clicked.connect(self._run_sensitivity)
        self.btn_simulate.clicked.connect(self._run_simulation)
        self.btn_stress.clicked.connect(self._run_stress)
        self.btn_candidates.clicked.connect(self._run_candidates)
        self.btn_select_cash.clicked.connect(self._run_select_cash)
        self.btn_calibrate.clicked.connect(self._run_calibrate)
        self.btn_eval_predictions.clicked.connect(self._run_eval_predictions)
        self.btn_edge_trend.clicked.connect(self._run_edge_trend)
        self.btn_cancel.clicked.connect(self.vm.cancel_all_tasks)
        self.btn_export.clicked.connect(self._run_export)
        self.btn_cancel_selected.clicked.connect(self._cancel_selected_task)
        self.btn_cancel_all.clicked.connect(self.vm.cancel_all_tasks)
        self.btn_robust_cov_source.clicked.connect(self._select_robust_cov_source)
        self.btn_stress_scenario_file.clicked.connect(self._select_stress_scenario_file)

        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._load_csv)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._run_optimize)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._run_export)
        self._load_ui_state()
        self._set_rules_summary(self._build_rules())

    def _ui_state_path(self) -> Path:
        return Path.cwd() / ".cash_optimizer_gui_state.json"

    def _capture_ui_state(self) -> dict[str, object]:
        return {
            "salary_cap": self.salary_cap_spin.value(),
            "max_team": self.max_team_spin.value(),
            "disallow_qb_dst": self.disallow_qb_dst.isChecked(),
            "sim_runs": self.sim_runs_spin.value(),
            "candidates": self.candidates_spin.value(),
            "cash_threshold": self.cash_threshold_spin.value(),
            "robust_enabled": self.robust_enable.isChecked(),
            "robust_rho": self.robust_rho_spin.value(),
            "robust_corr_threshold": self.robust_corr_threshold_spin.value(),
            "robust_set": self.robust_set_combo.currentText(),
            "robust_cov_source": self.robust_cov_source_edit.text(),
            "stress_scenario_file": self.stress_scenario_file_edit.text(),
            "export_json_summary": self.export_json_summary.isChecked(),
            "eval_models": self.eval_models_edit.toPlainText(),
            "eval_position_col": self.eval_position_col_edit.toPlainText(),
            "eval_actual_col": self.eval_actual_col_edit.toPlainText(),
            "edge_trials": self.edge_trials_spin.value(),
            "edge_top_n": self.edge_top_n_spin.value(),
        }

    def _apply_ui_state(self, payload: dict[str, object]) -> None:
        salary_cap = int(payload.get("salary_cap", 50000))
        self.salary_cap_spin.setValue(max(self.salary_cap_spin.minimum(), min(self.salary_cap_spin.maximum(), salary_cap)))

        max_team = int(payload.get("max_team", 0))
        self.max_team_spin.setValue(max(self.max_team_spin.minimum(), min(self.max_team_spin.maximum(), max_team)))

        self.disallow_qb_dst.setChecked(bool(payload.get("disallow_qb_dst", False)))

        sim_runs = int(payload.get("sim_runs", 2000))
        self.sim_runs_spin.setValue(max(self.sim_runs_spin.minimum(), min(self.sim_runs_spin.maximum(), sim_runs)))

        candidates = int(payload.get("candidates", 25))
        self.candidates_spin.setValue(max(self.candidates_spin.minimum(), min(self.candidates_spin.maximum(), candidates)))

        self.cash_threshold_spin.setValue(float(payload.get("cash_threshold", 130.0)))
        self.robust_enable.setChecked(bool(payload.get("robust_enabled", False)))
        self.robust_rho_spin.setValue(float(payload.get("robust_rho", 0.35)))
        self.robust_corr_threshold_spin.setValue(float(payload.get("robust_corr_threshold", 0.0)))

        robust_set = str(payload.get("robust_set", "box"))
        robust_idx = self.robust_set_combo.findText(robust_set)
        if robust_idx >= 0:
            self.robust_set_combo.setCurrentIndex(robust_idx)

        self.robust_cov_source_edit.setText(str(payload.get("robust_cov_source", "")))
        self.stress_scenario_file_edit.setText(str(payload.get("stress_scenario_file", "")))
        self.export_json_summary.setChecked(bool(payload.get("export_json_summary", False)))
        self.eval_models_edit.setPlainText(str(payload.get("eval_models", "")))
        self.eval_position_col_edit.setPlainText(str(payload.get("eval_position_col", "position")))
        self.eval_actual_col_edit.setPlainText(str(payload.get("eval_actual_col", "actual")))

        edge_trials = int(payload.get("edge_trials", 1000))
        self.edge_trials_spin.setValue(max(self.edge_trials_spin.minimum(), min(self.edge_trials_spin.maximum(), edge_trials)))

        edge_top_n = int(payload.get("edge_top_n", 10))
        self.edge_top_n_spin.setValue(max(self.edge_top_n_spin.minimum(), min(self.edge_top_n_spin.maximum(), edge_top_n)))
        self._set_rules_summary(self._build_rules())

    def _load_ui_state(self) -> None:
        state_path = self._ui_state_path()
        if not state_path.exists():
            return
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._apply_ui_state(payload)
        except Exception as exc:
            self._append_log(f"Unable to load GUI state: {exc}")

    def _save_ui_state(self) -> None:
        state_path = self._ui_state_path()
        state_path.write_text(json.dumps(self._capture_ui_state(), indent=2), encoding="utf-8")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._save_ui_state()
        except Exception as exc:
            self._append_log(f"Unable to save GUI state: {exc}")
        super().closeEvent(event)

    def _load_csv(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open CSV", str(Path.cwd()), "CSV Files (*.csv)")
        if not path_str:
            return
        self.vm.load_csv(Path(path_str), rules=self._build_rules())
        self._refresh_data_panel()

    def _build_rules(self) -> Rules:
        max_team = self.max_team_spin.value()
        return Rules(
            salary_cap=self.salary_cap_spin.value(),
            max_players_per_team=(max_team if max_team > 0 else None),
            disallow_qb_vs_opp_dst=self.disallow_qb_dst.isChecked(),
        )

    def _set_rules_summary(self, rules: Rules) -> None:
        max_team_txt = "None" if rules.max_players_per_team is None else str(rules.max_players_per_team)
        qb_dst_txt = "disallow" if rules.disallow_qb_vs_opp_dst else "allow"
        self.data_rules_label.setText(
            f"salary_cap={rules.salary_cap}, max_team={max_team_txt}, qb_vs_opp_dst={qb_dst_txt}"
        )

    def _refresh_data_panel(self) -> None:
        loaded_path = self.vm.service.loaded_path
        if loaded_path is None:
            self.data_path_label.setText("No file loaded")
            self.data_summary_label.setText("Players: 0")
            return

        self.data_path_label.setText(str(loaded_path))
        players = self.vm.service.optimizer.players
        status_counts = Counter((p.status or "unknown") for p in players)
        status_txt = ", ".join(f"{k}:{v}" for k, v in sorted(status_counts.items()))
        self.data_summary_label.setText(f"Players: {len(players)} | Status: {status_txt}")

    def _run_optimize(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        robust_cov_source = self._resolve_robust_cov_source()
        self.vm.run_optimize(
            robust_enabled=self.robust_enable.isChecked(),
            robust_rho=self.robust_rho_spin.value(),
            robust_corr_threshold=self.robust_corr_threshold_spin.value(),
            robust_set=self.robust_set_combo.currentText(),
            robust_cov_source=robust_cov_source,
        )

    def _run_sensitivity(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        robust_cov_source = self._resolve_robust_cov_source()
        self.vm.run_sensitivity(
            robust_enabled=self.robust_enable.isChecked(),
            robust_rho=self.robust_rho_spin.value(),
            robust_corr_threshold=self.robust_corr_threshold_spin.value(),
            robust_set=self.robust_set_combo.currentText(),
            robust_cov_source=robust_cov_source,
        )

    def _run_simulation(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        self.vm.run_simulation(self.sim_runs_spin.value())

    def _run_stress(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        self.vm.run_stress(scenario_file=self._resolve_stress_scenario_file())

    def _run_candidates(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        self.vm.run_candidates(self.candidates_spin.value())

    def _run_select_cash(self) -> None:
        rules = self._build_rules()
        self.vm.update_rules(rules)
        self._set_rules_summary(rules)
        self.vm.run_select_cash(
            threshold=self.cash_threshold_spin.value(),
            candidates=self.candidates_spin.value(),
            runs=self.sim_runs_spin.value(),
        )

    def _run_calibrate(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Calibration CSV",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if not path_str:
            return
        self.vm.run_calibration(Path(path_str))

    def _run_export(self) -> None:
        output_dir = Path.cwd() / "outputs"
        self.vm.run_export(
            output_dir=output_dir,
            runs=self.sim_runs_spin.value(),
            write_json_summary=self.export_json_summary.isChecked(),
        )
        self._append_log(f"Export requested: {output_dir}")

    def _select_robust_cov_source(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Robust Error CSV",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if not path_str:
            return
        self.robust_cov_source_edit.setText(path_str)

    def _resolve_robust_cov_source(self) -> Path | None:
        raw = self.robust_cov_source_edit.text().strip()
        if not raw:
            return None
        return Path(raw)

    def _select_stress_scenario_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Stress Scenario CSV",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if not path_str:
            return
        self.stress_scenario_file_edit.setText(path_str)

    def _resolve_stress_scenario_file(self) -> Path | None:
        raw = self.stress_scenario_file_edit.text().strip()
        if not raw:
            return None
        return Path(raw)

    def _run_eval_predictions(self) -> None:
        eval_path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Prediction Evaluation CSV",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if not eval_path_str:
            return

        raw_models = self.eval_models_edit.toPlainText().strip()
        model_columns = [m.strip() for m in raw_models.split(",") if m.strip()]
        if not model_columns:
            QMessageBox.warning(self, "Missing Models", "Enter model columns (comma-separated)")
            return

        output_path = Path.cwd() / "outputs" / "prediction_eval.csv"
        self.vm.run_prediction_eval(
            eval_csv=Path(eval_path_str),
            model_columns=model_columns,
            position_col=self.eval_position_col_edit.toPlainText().strip() or "position",
            actual_col=self.eval_actual_col_edit.toPlainText().strip() or "actual",
            save_csv=output_path,
        )
        self._append_log(f"Prediction evaluation requested: {eval_path_str}")

    def _run_edge_trend(self) -> None:
        slate_paths_strs, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Slate CSV Files",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if not slate_paths_strs:
            return

        cash_lines_str, _ = QFileDialog.getOpenFileName(
            self,
            "Optional Cash Lines CSV (Cancel to skip)",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        cash_lines_csv = Path(cash_lines_str) if cash_lines_str else None

        output_path = Path.cwd() / "outputs" / "edge_trend.csv"
        self.vm.run_edge_trend(
            slate_paths=[Path(p) for p in slate_paths_strs],
            trials=self.edge_trials_spin.value(),
            top_n_per_slot=self.edge_top_n_spin.value(),
            cash_lines_csv=cash_lines_csv,
            save_csv=output_path,
        )
        self._append_log(f"Edge trend requested for {len(slate_paths_strs)} slates")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _set_progress(self, text: str) -> None:
        self.progress_label.setText(text)

    def _on_task_state(self, task_id: str, task_name: str, status: str, percent: int) -> None:
        item = self._task_items.get(task_id)
        if item is None:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, task_id)
            self.task_list.addItem(item)
            self._task_items[task_id] = item

        item.setText(f"{task_id} | {task_name} | {status} | {percent}%")
        self.progress_bar.setValue(max(0, min(100, int(percent))))

        if status in {"completed", "failed", "cancelled"}:
            self.task_list.scrollToBottom()

    def _cancel_selected_task(self) -> None:
        item = self.task_list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.UserRole)
        if isinstance(task_id, str):
            self.vm.cancel_task(task_id)

    def _append_log(self, message: str) -> None:
        self.logs_view.append(message)

    def _show_error(self, message: str) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Critical)
        dialog.setWindowTitle("Error")
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.Retry | QMessageBox.Close)
        choice = dialog.exec()
        if choice == QMessageBox.Retry:
            if not self.vm.retry_last_failed_task():
                QMessageBox.information(self, "Retry", "No failed task available to retry.")
        self._set_status(message)

    def _on_optimal(self, result) -> None:
        rows = []
        for slot, player in result.lineup.players_by_slot.items():
            rows.append(
                {
                    "slot": slot,
                    "player": player.name,
                    "position": player.position,
                    "salary": player.salary,
                    "projection": player.projection,
                }
            )
        self.opt_view.set_rows(rows)
        self._set_status(f"Optimal ready: {result.optimal_projection:.2f}")

    def _on_sensitivity(self, result) -> None:
        rows = []
        for row in result.entries:
            rows.append(
                {
                    "player_id": row.player_id,
                    "in_optimal": row.in_optimal,
                    "delta_enter": row.delta_enter,
                    "delta_exit": row.delta_exit,
                    "tie_flag": row.tie_flag,
                }
            )
        self.sens_view.set_rows(rows)
        self._set_status(f"Sensitivity ready: {len(rows)} rows")

    def _on_simulation(self, result) -> None:
        rows: list[dict] = [
            {
                "row_type": "summary",
                "num_runs": result.num_runs,
                "mean": result.mean_optimal_projection,
                "p05": result.p05_optimal_projection,
                "p50": result.p50_optimal_projection,
                "p95": result.p95_optimal_projection,
                "unique_lineups": result.unique_lineups,
            }
        ]
        for lineup in result.lineup_stats[:10]:
            rows.append(
                {
                    "row_type": "lineup",
                    "lineup_key": lineup.lineup_key,
                    "frequency": lineup.frequency,
                    "frequency_rate": lineup.frequency_rate,
                    "mean_projection": lineup.mean_projection,
                }
            )
        for player in sorted(result.player_stats, key=lambda p: p.inclusion_rate, reverse=True)[:10]:
            rows.append(
                {
                    "row_type": "player",
                    "player_id": player.player_id,
                    "inclusion_rate": player.inclusion_rate,
                    "mean_lineup_projection_when_included": player.mean_lineup_projection_when_included,
                    "leverage_to_baseline": player.leverage_to_baseline,
                }
            )
        self.sim_view.set_rows(rows)
        self.sim_chart.set_summary(
            mean=result.mean_optimal_projection,
            p05=result.p05_optimal_projection,
            p50=result.p50_optimal_projection,
            p95=result.p95_optimal_projection,
        )
        self._set_status(f"Simulation ready: {result.num_runs} runs")

    def _on_candidates(self, result) -> None:
        rows = [{"lineup_key": "|".join(lineup), "size": len(lineup)} for lineup in result]
        self.candidates_view.set_rows(rows)
        self._set_status(f"Candidates ready: {len(rows)}")

    def _on_select_cash(self, result) -> None:
        rows = [
            {
                "selected_lineup": "|".join(result.selected_lineup_player_ids),
                "estimated_cash_probability": result.estimated_cash_probability,
                "threshold": result.threshold,
                "candidate_count": result.candidate_count,
            }
        ]
        self.select_cash_view.set_rows(rows)
        self._set_status("Cash selection ready")

    def _on_stress(self, result) -> None:
        rows = []
        for s in result.scenario_results:
            rows.append(
                {
                    "scenario": s.scenario_name,
                    "projection": s.projected_points,
                    "salary": s.salary_used,
                }
            )
        self.stress_view.set_rows(rows)
        self._set_status(f"Stress ready: worst-case {result.worst_case_projection:.2f}")

    def _on_calibration(self, result) -> None:
        rows = [
            {
                "brier_score": result.brier_score,
                "log_loss": result.log_loss,
                "mean_predicted_probability": result.mean_predicted_probability,
                "observed_rate": result.observed_rate,
            }
        ]
        self.calibration_view.set_rows(rows)
        self._set_status("Calibration ready")

    def _on_export_ready(self, output_path) -> None:
        self._append_log(f"Export complete: {output_path}")
        self._set_status(f"Export complete: {output_path}")

    def _on_prediction_eval(self, result) -> None:
        rows = []
        for metric in result.metrics:
            rows.append(
                {
                    "position": metric.position,
                    "model": metric.model_name,
                    "rmse": metric.rmse,
                    "sample_count": metric.sample_count,
                    "is_best": result.best_model_by_position.get(metric.position) == metric.model_name,
                }
            )
        self.analytics_view.set_rows(rows)
        self._set_status(f"Prediction eval ready: {len(rows)} rows")

    def _on_edge_trend(self, result) -> None:
        rows = []
        for row in result.rows:
            rows.append(
                {
                    "slate": row.slate_label,
                    "optimizer_projection": row.optimizer_projection,
                    "human_best_projection": row.human_best_projection,
                    "human_mean_projection": row.human_mean_projection,
                    "edge_vs_human_best": row.edge_vs_human_best,
                    "edge_vs_human_mean": row.edge_vs_human_mean,
                    "optimizer_above_cash": row.optimizer_above_cash,
                    "human_mean_above_cash": row.human_mean_above_cash,
                }
            )
        rows.append(
            {
                "slate": "AGGREGATE",
                "optimizer_projection": "",
                "human_best_projection": "",
                "human_mean_projection": "",
                "edge_vs_human_best": result.mean_edge_vs_human_best,
                "edge_vs_human_mean": result.mean_edge_vs_human_mean,
                "optimizer_above_cash": result.optimizer_cash_rate,
                "human_mean_above_cash": result.human_mean_cash_rate,
            }
        )
        self.analytics_view.set_rows(rows)
        self._set_status(f"Edge trend ready: {len(result.rows)} slates")
