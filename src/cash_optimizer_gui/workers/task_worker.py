from __future__ import annotations

import inspect
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, str)


class TaskWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False
        self.signals = WorkerSignals()

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            self.signals.cancelled.emit()
            return
        try:
            call_kwargs = dict(self._kwargs)
            sig = inspect.signature(self._fn)
            if "progress_callback" in sig.parameters:
                call_kwargs["progress_callback"] = self._emit_progress
            result = self._fn(*self._args, **call_kwargs)
            if self._cancelled:
                self.signals.cancelled.emit()
                return
            self.signals.finished.emit(result)
        except Exception as exc:
            if self._cancelled:
                self.signals.cancelled.emit()
                return
            self.signals.failed.emit(str(exc))

    def _emit_progress(self, percent: int, message: str = "") -> None:
        bounded = max(0, min(100, int(percent)))
        self.signals.progress.emit(bounded, str(message or ""))
