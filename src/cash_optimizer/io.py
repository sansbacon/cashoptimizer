from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

from .models import DistributionSpec, Player


def load_players_from_dk_csv(csv_path: str | Path) -> tuple[Player, ...]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    players: list[Player] = []
    seen_ids: set[str] = set()

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"Position", "Name", "Salary", "TeamAbbrev", "Opp", "Projection"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")

        for row_idx, row in enumerate(reader, start=1):
            position = (row.get("Position") or "").strip().upper()
            name = (row.get("Name") or "").strip()
            team = (row.get("TeamAbbrev") or "").strip().upper()
            opp = (row.get("Opp") or "").strip().upper()
            game_id = _normalize_game_id((row.get("Matchup") or row.get("Game Info") or "").strip())
            status = (row.get("Status") or row.get("status") or "active").strip().lower() or "active"
            floor = _parse_optional_float(row.get("Floor") or row.get("floor"))
            ceiling = _parse_optional_float(row.get("Ceiling") or row.get("ceiling"))
            ownership = _parse_optional_float(row.get("Ownership") or row.get("ownership"))
            game_total = _parse_optional_float(row.get("GameTotal") or row.get("game_total") or row.get("Total"))
            spread = _parse_optional_float(row.get("Spread") or row.get("spread"))
            correlation_group = (row.get("CorrelationGroup") or row.get("correlation_group") or "").strip() or None
            std_dev = _parse_optional_float(row.get("StdDev") or row.get("std_dev"))
            distribution_type = (row.get("DistributionType") or row.get("distribution_type") or "normal").strip() or "normal"

            if not position or not name or not team:
                continue

            salary_raw = (row.get("Salary") or "").replace(",", "").strip()
            proj_raw = (row.get("Projection") or "").strip()
            try:
                salary = int(float(salary_raw))
                projection = float(proj_raw)
            except ValueError:
                continue

            player_id = _make_player_id(name=name, position=position, team=team)
            if player_id in seen_ids:
                player_id = f"{player_id}_{row_idx}"
            seen_ids.add(player_id)

            players.append(
                Player(
                    player_id=player_id,
                    name=name,
                    team=team,
                    opponent=opp,
                    position=position,
                    salary=salary,
                    projection=projection,
                    status=status,
                    game_id=game_id,
                    correlation_group=correlation_group,
                    ownership=ownership,
                    game_total=game_total,
                    spread=spread,
                    floor=floor,
                    ceiling=ceiling,
                    distribution=DistributionSpec(
                        distribution_type=distribution_type,
                        std_dev=std_dev,
                    ),
                )
            )

    if not players:
        raise ValueError("No valid player rows found in CSV")
    return tuple(players)


def _make_player_id(name: str, position: str, team: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{position.lower()}_{team.lower()}_{slug}"


def _normalize_game_id(value: str) -> str | None:
    if not value:
        return None
    first_token = value.split(" ", 1)[0].strip()
    if "@" in first_token:
        away, home = first_token.split("@", 1)
        away = away.strip().upper()
        home = home.strip().upper()
        if away and home:
            return f"{away}_{home}"
    return None


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None
