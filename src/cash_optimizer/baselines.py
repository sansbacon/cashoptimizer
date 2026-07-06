from __future__ import annotations

from collections import defaultdict
import random
from typing import Sequence

from .models import (
    HumanHeuristicBaselineResult,
    HumanVsOptimizerComparison,
    Lineup,
    Player,
    Rules,
)


def run_human_heuristic_baseline(
    players: Sequence[Player],
    rules: Rules,
    projections: Sequence[float] | None = None,
    trials: int = 1000,
    top_n_per_slot: int = 10,
    random_seed: int = 1729,
) -> HumanHeuristicBaselineResult:
    if trials <= 0:
        raise ValueError("trials must be > 0")
    if top_n_per_slot <= 0:
        raise ValueError("top_n_per_slot must be > 0")

    projection_values = _resolve_projections(players, projections)
    rng = random.Random(random_seed)

    eligible_by_slot = _build_top_n_eligible_by_slot(
        players=players,
        rules=rules,
        projections=projection_values,
        top_n_per_slot=top_n_per_slot,
    )

    feasible = 0
    best_lineup: Lineup | None = None
    best_projection = float("-inf")
    total_projection = 0.0

    for _ in range(trials):
        lineup = _sample_feasible_lineup(
            players=players,
            rules=rules,
            eligible_by_slot=eligible_by_slot,
            projections=projection_values,
            rng=rng,
        )
        if lineup is None:
            continue
        feasible += 1
        total_projection += lineup.projected_points
        if lineup.projected_points > best_projection:
            best_projection = lineup.projected_points
            best_lineup = lineup

    if feasible == 0:
        return HumanHeuristicBaselineResult(
            trials=trials,
            feasible_trials=0,
            best_lineup=None,
            best_projection=0.0,
            mean_projection=0.0,
        )

    return HumanHeuristicBaselineResult(
        trials=trials,
        feasible_trials=feasible,
        best_lineup=best_lineup,
        best_projection=best_projection,
        mean_projection=total_projection / feasible,
    )


def compare_optimizer_to_human_baseline(
    optimizer_projection: float,
    baseline: HumanHeuristicBaselineResult,
) -> HumanVsOptimizerComparison:
    return HumanVsOptimizerComparison(
        optimizer_projection=optimizer_projection,
        human_best_projection=baseline.best_projection,
        human_mean_projection=baseline.mean_projection,
        edge_vs_human_best=optimizer_projection - baseline.best_projection,
        edge_vs_human_mean=optimizer_projection - baseline.mean_projection,
        trials=baseline.trials,
        feasible_trials=baseline.feasible_trials,
    )


def _resolve_projections(players: Sequence[Player], projections: Sequence[float] | None) -> list[float]:
    if projections is None:
        return [p.projection for p in players]
    if len(projections) != len(players):
        raise ValueError("Projection vector length must match active player count")
    return [float(x) for x in projections]


def _build_top_n_eligible_by_slot(
    players: Sequence[Player],
    rules: Rules,
    projections: Sequence[float],
    top_n_per_slot: int,
) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for slot in rules.roster_slots:
        eligible = [
            idx for idx, player in enumerate(players)
            if _is_eligible(player.position, slot)
        ]
        eligible.sort(key=lambda idx: projections[idx], reverse=True)
        out[slot] = eligible[:top_n_per_slot]
    return out


def _sample_feasible_lineup(
    players: Sequence[Player],
    rules: Rules,
    eligible_by_slot: dict[str, list[int]],
    projections: Sequence[float],
    rng: random.Random,
) -> Lineup | None:
    slot_to_idx: dict[str, int] = {}
    used_idx: set[int] = set()

    # Randomize slot order to avoid deterministic bias to early slots.
    slot_order = list(rules.roster_slots)
    rng.shuffle(slot_order)

    for slot in slot_order:
        candidates = [idx for idx in eligible_by_slot[slot] if idx not in used_idx]
        if not candidates:
            return None
        choice = rng.choice(candidates)
        slot_to_idx[slot] = choice
        used_idx.add(choice)

    # Re-map slot assignment back to original roster order for output stability.
    ordered_slot_to_idx = {slot: slot_to_idx[slot] for slot in rules.roster_slots}
    selected_players = [players[idx] for idx in ordered_slot_to_idx.values()]

    if not _lineup_is_feasible(selected_players, rules):
        return None

    salary_used = sum(p.salary for p in selected_players)
    projected_points = sum(projections[idx] for idx in ordered_slot_to_idx.values())
    lineup = Lineup(
        players_by_slot={slot: players[idx] for slot, idx in ordered_slot_to_idx.items()},
        player_ids=tuple(sorted(p.player_id for p in selected_players)),
        salary_used=salary_used,
        projected_points=projected_points,
    )
    return lineup


def _lineup_is_feasible(selected_players: Sequence[Player], rules: Rules) -> bool:
    if len(selected_players) != len(rules.roster_slots):
        return False

    salary = sum(p.salary for p in selected_players)
    if salary > rules.salary_cap:
        return False

    if rules.max_players_per_team is not None:
        team_counts: dict[str, int] = defaultdict(int)
        for p in selected_players:
            team_counts[p.team] += 1
            if team_counts[p.team] > rules.max_players_per_team:
                return False

    if rules.disallow_qb_vs_opp_dst:
        qbs = [p for p in selected_players if p.position == "QB"]
        dsts = [p for p in selected_players if p.position == "DST"]
        if qbs and dsts:
            qb = qbs[0]
            dst = dsts[0]
            if qb.opponent == dst.team:
                return False

    return True


def _is_eligible(position: str, slot: str) -> bool:
    if slot == "QB":
        return position == "QB"
    if slot in {"RB1", "RB2"}:
        return position == "RB"
    if slot in {"WR1", "WR2", "WR3"}:
        return position == "WR"
    if slot == "TE":
        return position == "TE"
    if slot == "FLEX":
        return position in {"RB", "WR", "TE"}
    if slot == "DST":
        return position == "DST"
    return False
