from __future__ import annotations

from .models import SensitivityEntry, SensitivityFragilitySummary


def compute_fragility_summary(
    entries: tuple[SensitivityEntry, ...],
    exit_delta_threshold: float = 0.75,
    enter_delta_threshold: float = 0.75,
    alert_threshold: float = 3.0,
) -> SensitivityFragilitySummary:
    if exit_delta_threshold < 0 or enter_delta_threshold < 0:
        raise ValueError("Fragility thresholds must be >= 0")

    fragile_selected = 0
    near_miss_excluded = 0

    for entry in entries:
        if entry.in_optimal:
            if entry.delta_exit is not None and entry.delta_exit <= exit_delta_threshold:
                fragile_selected += 1
        else:
            if entry.delta_enter is not None and entry.delta_enter <= enter_delta_threshold:
                near_miss_excluded += 1

    fragility_score = float(fragile_selected + near_miss_excluded)
    return SensitivityFragilitySummary(
        exit_delta_threshold=float(exit_delta_threshold),
        enter_delta_threshold=float(enter_delta_threshold),
        fragile_selected_count=fragile_selected,
        near_miss_excluded_count=near_miss_excluded,
        fragility_score=fragility_score,
        alert_threshold=float(alert_threshold),
        alert=fragility_score >= float(alert_threshold),
    )
