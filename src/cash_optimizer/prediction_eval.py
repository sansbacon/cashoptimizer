from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .models import PositionPredictionMetric, PredictionModelSelectionResult


def evaluate_prediction_models_by_position(
    rows: Sequence[Mapping[str, str | float | int]],
    model_columns: Sequence[str],
    position_column: str = "position",
    actual_column: str = "actual",
) -> PredictionModelSelectionResult:
    if not model_columns:
        raise ValueError("model_columns cannot be empty")

    sqerr_by_key: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        pos = str(row.get(position_column, "")).strip().upper()
        if not pos:
            continue
        actual_raw = row.get(actual_column)
        if actual_raw is None or str(actual_raw).strip() == "":
            continue
        actual = float(actual_raw)

        for model in model_columns:
            pred_raw = row.get(model)
            if pred_raw is None or str(pred_raw).strip() == "":
                continue
            pred = float(pred_raw)
            key = (pos, model)
            sqerr_by_key.setdefault(key, []).append((pred - actual) ** 2)

    metrics: list[PositionPredictionMetric] = []
    by_position: dict[str, list[PositionPredictionMetric]] = {}
    for (pos, model), sqerrs in sqerr_by_key.items():
        if not sqerrs:
            continue
        rmse = float(np.sqrt(np.mean(np.asarray(sqerrs, dtype=float))))
        m = PositionPredictionMetric(
            position=pos,
            model_name=model,
            rmse=rmse,
            sample_count=len(sqerrs),
        )
        metrics.append(m)
        by_position.setdefault(pos, []).append(m)

    metrics.sort(key=lambda m: (m.position, m.rmse, m.model_name))

    best_model_by_position: dict[str, str] = {}
    for pos, values in by_position.items():
        best = min(values, key=lambda m: (m.rmse, -m.sample_count, m.model_name))
        best_model_by_position[pos] = best.model_name

    return PredictionModelSelectionResult(
        metrics=tuple(metrics),
        best_model_by_position=best_model_by_position,
    )


def load_prediction_eval_rows(csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(csv_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]
