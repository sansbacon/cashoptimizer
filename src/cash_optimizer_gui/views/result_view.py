from __future__ import annotations

import csv
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget

from ..models.table_models import DictTableModel


class ResultView(QWidget):
    def __init__(self, parent=None, model: DictTableModel | None = None) -> None:
        super().__init__(parent)
        self.model = model or DictTableModel([])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.export_button = QPushButton("Export Tab CSV")
        self.export_json_button = QPushButton("Export Tab JSON")
        self.copy_button = QPushButton("Copy Selected")
        self.empty_label = QLabel("No results yet. Run an action to populate this tab.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #555555;")
        self._default_filename = "results.csv"
        self.export_button.clicked.connect(self._export_rows)
        self.export_json_button.clicked.connect(self._export_json)
        self.copy_button.clicked.connect(self._copy_selected)

        layout = QVBoxLayout(self)
        layout.addWidget(self.export_button)
        layout.addWidget(self.export_json_button)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)
        self._sync_empty_state()

    def set_rows(self, rows: list[dict]) -> None:
        self.model.set_rows(rows)
        self._sync_empty_state()

    def set_export_filename_hint(self, filename: str) -> None:
        self._default_filename = filename

    def _export_rows(self) -> None:
        rows = self.model.rows()
        if not rows:
            return

        start_path = Path.cwd() / "outputs" / self._default_filename
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tab CSV",
            str(start_path),
            "CSV Files (*.csv)",
        )
        if not path_str:
            return

        out_path = Path(path_str)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        columns = list(rows[0].keys())
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _export_json(self) -> None:
        rows = self.model.rows()
        if not rows:
            return

        start_path = Path.cwd() / "outputs" / self._default_filename.replace(".csv", ".json")
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tab JSON",
            str(start_path),
            "JSON Files (*.json)",
        )
        if not path_str:
            return

        out_path = Path(path_str)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def _copy_selected(self) -> None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return

        indexes = sorted(indexes, key=lambda i: (i.row(), i.column()))
        current_row = indexes[0].row()
        row_values: list[str] = []
        lines: list[str] = []

        for idx in indexes:
            if idx.row() != current_row:
                lines.append("\t".join(row_values))
                row_values = []
                current_row = idx.row()
            row_values.append(str(self.model.data(idx, role=Qt.DisplayRole) or ""))
        if row_values:
            lines.append("\t".join(row_values))

        QApplication.clipboard().setText("\n".join(lines))

    def _sync_empty_state(self) -> None:
        has_rows = self.model.rowCount() > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)
