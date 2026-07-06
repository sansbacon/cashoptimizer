from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SimulationSummaryChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self._values: list[tuple[str, float]] = []

    def set_summary(self, mean: float, p05: float, p50: float, p95: float) -> None:
        self._values = [
            ("p05", float(p05)),
            ("p50", float(p50)),
            ("mean", float(mean)),
            ("p95", float(p95)),
        ]
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#f5f7fb"))

        if not self._values:
            painter.setPen(QPen(QColor("#666")))
            painter.drawText(rect, Qt.AlignCenter, "Simulation chart ready after run")
            return

        max_value = max(v for _, v in self._values)
        min_value = min(v for _, v in self._values)
        span = max(1e-9, max_value - min_value)

        bar_count = len(self._values)
        gap = 12.0
        total_gap = gap * (bar_count + 1)
        bar_w = max(10.0, (rect.width() - total_gap) / bar_count)
        baseline = rect.bottom() - 22.0
        max_h = rect.height() - 40.0

        colors = {
            "p05": QColor("#c7d2fe"),
            "p50": QColor("#93c5fd"),
            "mean": QColor("#60a5fa"),
            "p95": QColor("#2563eb"),
        }

        x = rect.left() + gap
        for label, value in self._values:
            norm = (value - min_value) / span if span > 0 else 0.5
            h = max(4.0, norm * max_h)
            y = baseline - h
            bar_rect = QRectF(x, y, bar_w, h)
            painter.fillRect(bar_rect, colors.get(label, QColor("#888")))
            painter.setPen(QPen(QColor("#0f172a")))
            painter.drawRect(bar_rect)
            painter.drawText(QRectF(x - 6, baseline + 4, bar_w + 12, 14), Qt.AlignCenter, label)
            painter.drawText(QRectF(x - 10, y - 16, bar_w + 20, 14), Qt.AlignCenter, f"{value:.1f}")
            x += bar_w + gap
