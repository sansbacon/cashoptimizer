from __future__ import annotations

import csv
from pathlib import Path

from .validators import CLIValidationError, ensure_file_exists


def load_projection_overrides(path: Path) -> dict[str, float]:
    ensure_file_exists(path)
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise CLIValidationError("Projection override file must include headers")

        fields = set(reader.fieldnames)
        if not ({"player_id", "projection"}.issubset(fields) or {"Player", "Projection"}.issubset(fields)):
            raise CLIValidationError(
                "Projection override file must contain either columns [player_id, projection] or [Player, Projection]"
            )

        overrides: dict[str, float] = {}
        for i, row in enumerate(reader, start=2):
            raw_projection = row.get("projection", row.get("Projection", ""))
            key = row.get("player_id", row.get("Player", "")).strip()
            if not key:
                continue
            try:
                overrides[key] = float(raw_projection)
            except (TypeError, ValueError) as exc:
                raise CLIValidationError(f"Invalid projection value at row {i}: {raw_projection}") from exc

    if not overrides:
        raise CLIValidationError("No valid projection overrides found")
    return overrides
