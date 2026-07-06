from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DictTableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._rows = rows or []
        self._columns = list(self._rows[0].keys()) if self._rows else []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self._columns = list(rows[0].keys()) if rows else []
        self.endResetModel()

    def rows(self) -> list[dict]:
        return [dict(r) for r in self._rows]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = self._columns[index.column()]
        if role == Qt.DisplayRole:
            return str(row.get(col, ""))
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self._columns):
            return self._columns[section]
        return super().headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if not (0 <= column < len(self._columns)):
            return
        key = self._columns[column]
        reverse = order == Qt.DescendingOrder

        def _sort_key(row: dict):
            value = row.get(key)
            if isinstance(value, (int, float)):
                return (0, value)
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                return (1, str(value) if value is not None else "")

        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=_sort_key, reverse=reverse)
        self.layoutChanged.emit()


class OptimalLineupTableModel(DictTableModel):
    pass


class SensitivityTableModel(DictTableModel):
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        value = super().data(index, role)
        if role == Qt.BackgroundRole and index.isValid():
            row = self._rows[index.row()]
            delta_exit = row.get("delta_exit")
            delta_enter = row.get("delta_enter")
            try:
                if delta_exit is not None and float(delta_exit) <= 0.75:
                    return QColor("#ffe6e6")
                if delta_enter is not None and float(delta_enter) <= 0.75:
                    return QColor("#fff7d6")
            except (TypeError, ValueError):
                return None
        return value


class SimulationPlayerStatsModel(DictTableModel):
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        value = super().data(index, role)
        if role == Qt.BackgroundRole and index.isValid():
            row = self._rows[index.row()]
            try:
                inclusion_rate = row.get("inclusion_rate")
                if inclusion_rate is not None and float(inclusion_rate) >= 0.6:
                    return QColor("#e8f7e8")
            except (TypeError, ValueError):
                return None
        return value


class SimulationLineupStatsModel(DictTableModel):
    pass


class ScenarioResultsModel(DictTableModel):
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        value = super().data(index, role)
        if role == Qt.BackgroundRole and index.isValid():
            row = self._rows[index.row()]
            try:
                projection = row.get("projection")
                if projection is not None and float(projection) < 120.0:
                    return QColor("#fff1e6")
            except (TypeError, ValueError):
                return None
        return value
