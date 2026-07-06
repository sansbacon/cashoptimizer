import importlib
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None or importlib.util.find_spec("pytestqt") is None,
    reason="PySide6 or pytest-qt not installed",
)
def test_main_window_instantiates_with_qtbot(qtbot):
    from cash_optimizer_gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "cash-optimizer"
    assert window.progress_bar.value() == 0
    assert window.sim_chart is not None


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None or importlib.util.find_spec("pytestqt") is None,
    reason="PySide6 or pytest-qt not installed",
)
def test_main_window_persists_control_state(qtbot, monkeypatch, tmp_path):
    from cash_optimizer_gui.main_window import MainWindow

    monkeypatch.chdir(tmp_path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.salary_cap_spin.setValue(49000)
    window.max_team_spin.setValue(3)
    window.disallow_qb_dst.setChecked(True)
    window.sim_runs_spin.setValue(3333)
    window.candidates_spin.setValue(31)
    window.cash_threshold_spin.setValue(125.5)
    window.robust_enable.setChecked(True)
    window.robust_rho_spin.setValue(0.6)
    window.robust_set_combo.setCurrentText("polygon")
    window.stress_scenario_file_edit.setText("C:/tmp/scenarios.csv")
    window.export_json_summary.setChecked(True)
    window.eval_models_edit.setPlainText("lr,rf")
    window.edge_trials_spin.setValue(2222)
    window.edge_top_n_spin.setValue(7)
    window.close()

    restored = MainWindow()
    qtbot.addWidget(restored)
    restored.show()

    assert restored.salary_cap_spin.value() == 49000
    assert restored.max_team_spin.value() == 3
    assert restored.disallow_qb_dst.isChecked() is True
    assert restored.sim_runs_spin.value() == 3333
    assert restored.candidates_spin.value() == 31
    assert restored.cash_threshold_spin.value() == pytest.approx(125.5)
    assert restored.robust_enable.isChecked() is True
    assert restored.robust_rho_spin.value() == pytest.approx(0.6)
    assert restored.robust_set_combo.currentText() == "polygon"
    assert restored.stress_scenario_file_edit.text() == "C:/tmp/scenarios.csv"
    assert restored.export_json_summary.isChecked() is True
    assert restored.eval_models_edit.toPlainText() == "lr,rf"
    assert restored.edge_trials_spin.value() == 2222
    assert restored.edge_top_n_spin.value() == 7


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None or importlib.util.find_spec("pytestqt") is None,
    reason="PySide6 or pytest-qt not installed",
)
def test_main_window_primary_click_flow_populates_results(qtbot, monkeypatch, tmp_path):
    from cash_optimizer_gui.main_window import MainWindow

    csv_path = tmp_path / "mini_slate.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Position,Name,Salary,TeamAbbrev,Opp,Projection,Status",
                "QB,QB One,7200,AAA,BBB,21.0,active",
                "QB,QB Two,6800,MMM,NNN,19.0,active",
                "RB,RB One,6400,AAA,BBB,16.0,active",
                "RB,RB Two,6000,CCC,DDD,15.0,active",
                "RB,RB Three,5600,EEE,FFF,13.0,active",
                "RB,RB Four,5200,MMM,NNN,12.5,active",
                "WR,WR One,6900,AAA,BBB,18.0,active",
                "WR,WR Two,6200,CCC,DDD,15.5,active",
                "WR,WR Three,5800,EEE,FFF,14.0,active",
                "WR,WR Four,5000,GGG,HHH,12.0,active",
                "WR,WR Five,4700,MMM,NNN,11.0,active",
                "TE,TE One,4700,CCC,DDD,11.0,active",
                "TE,TE Two,4200,GGG,HHH,9.5,active",
                "TE,TE Three,3900,MMM,NNN,8.5,active",
                "DST,DST One,3200,III,JJJ,8.0,active",
                "DST,DST Two,2800,KKK,LLL,7.0,active",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "cash_optimizer_gui.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(csv_path), "CSV Files (*.csv)"),
    )

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.sim_runs_spin.setValue(20)

    qtbot.mouseClick(window.btn_load, Qt.LeftButton)
    assert "Loaded" in window.status_label.text()
    assert "mini_slate.csv" in window.data_path_label.text()
    assert "Players:" in window.data_summary_label.text()
    assert "active:" in window.data_summary_label.text()
    assert "salary_cap=50000" in window.data_rules_label.text()
    window.vm.service.optimizer.solver_settings = replace(
        window.vm.service.optimizer.solver_settings,
        cp_sat_max_time_seconds=0.1,
    )

    qtbot.mouseClick(window.btn_optimize, Qt.LeftButton)
    qtbot.waitUntil(lambda: window.opt_view.model.rowCount() > 0, timeout=20000)

    qtbot.mouseClick(window.btn_sensitivity, Qt.LeftButton)
    qtbot.waitUntil(lambda: window.sens_view.model.rowCount() > 0, timeout=120000)

    qtbot.mouseClick(window.btn_simulate, Qt.LeftButton)
    qtbot.waitUntil(lambda: window.sim_view.model.rowCount() > 0, timeout=30000)

    assert "Simulation:" in window.progress_label.text() or "Task completed: Simulation" in window.progress_label.text()
    assert window.progress_bar.value() == 100


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None or importlib.util.find_spec("pytestqt") is None,
    reason="PySide6 or pytest-qt not installed",
)
def test_main_window_accessibility_and_error_empty_states(qtbot, monkeypatch):
    from cash_optimizer_gui.main_window import MainWindow
    from cash_optimizer_gui.models.table_models import SensitivityTableModel

    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Close)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.btn_load.accessibleName() == "action-load-csv"
    assert window.btn_optimize.accessibleName() == "action-optimize"
    assert window.btn_sensitivity.accessibleName() == "action-sensitivity"
    assert window.btn_simulate.accessibleName() == "action-simulate"
    assert window.opt_view.empty_label.isVisible()

    model = SensitivityTableModel(
        [
            {"player_id": "p1", "delta_exit": 0.5, "delta_enter": None, "tie_flag": False},
            {"player_id": "p2", "delta_exit": None, "delta_enter": 0.3, "tie_flag": False},
        ]
    )
    color1 = model.data(model.index(0, 0), role=Qt.BackgroundRole)
    color2 = model.data(model.index(1, 0), role=Qt.BackgroundRole)
    assert isinstance(color1, QColor)
    assert isinstance(color2, QColor)

    window._show_error("validation error: missing input")
    assert "validation error" in window.status_label.text()
