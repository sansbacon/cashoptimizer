from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping, Sequence
import statistics

from .models import DistributionSpec, NewsSignal, NewsSignalPolicy, NewsVolatilityAdjustmentResult, Player


_DEFAULT_NEWS_SIGNAL_POLICIES: tuple[NewsSignalPolicy, ...] = (
    NewsSignalPolicy(signal=NewsSignal.HEALTHY_CONFIRMED_ROLE, mean_penalty=0.0, variance_multiplier=1.0),
    NewsSignalPolicy(signal=NewsSignal.QUESTIONABLE_TAG, mean_penalty=0.75, variance_multiplier=1.20),
    NewsSignalPolicy(signal=NewsSignal.GAME_TIME_DECISION, mean_penalty=1.25, variance_multiplier=1.35),
    NewsSignalPolicy(signal=NewsSignal.ROLE_CHANGE_RISK, mean_penalty=0.60, variance_multiplier=1.25),
    NewsSignalPolicy(signal=NewsSignal.WEATHER_ELEVATED_RISK, mean_penalty=0.40, variance_multiplier=1.15),
)


def default_news_signal_policies() -> tuple[NewsSignalPolicy, ...]:
    return _DEFAULT_NEWS_SIGNAL_POLICIES


def blend_cash_projections(
    players: Sequence[Player],
    median_by_player_id: Mapping[str, float],
    floor_by_player_id: Mapping[str, float],
    w_median: float = 0.7,
    w_floor: float = 0.3,
) -> list[float]:
    if abs((w_median + w_floor) - 1.0) > 1e-9:
        raise ValueError("w_median + w_floor must equal 1.0")

    out: list[float] = []
    for player in players:
        median = median_by_player_id.get(player.player_id, player.projection)
        floor = floor_by_player_id.get(player.player_id, median)
        out.append((w_median * float(median)) + (w_floor * float(floor)))
    return out


def apply_mean_penalties(
    players: Sequence[Player],
    base_projections: Sequence[float],
    penalties_by_player_id: Mapping[str, float],
    clip_min: float = 0.0,
) -> list[float]:
    if len(base_projections) != len(players):
        raise ValueError("base_projections length must match players length")

    out: list[float] = []
    for i, player in enumerate(players):
        penalty = float(penalties_by_player_id.get(player.player_id, 0.0))
        adjusted = float(base_projections[i]) - penalty
        out.append(max(clip_min, adjusted))
    return out


def projection_vector_from_players(players: Iterable[Player]) -> list[float]:
    return [float(p.projection) for p in players]


def build_ensemble_shrunk_projections(
    players: Sequence[Player],
    projections_by_source: Mapping[str, Mapping[str, float]],
    source_weights: Mapping[str, float] | None = None,
    shrink_strength: float = 0.25,
    disagreement_penalty: float = 0.0,
    clip_min: float = 0.0,
) -> list[float]:
    """Blend projections across sources, shrink toward position mean, and penalize source disagreement."""
    if shrink_strength < 0 or shrink_strength > 1:
        raise ValueError("shrink_strength must be in [0, 1]")
    if disagreement_penalty < 0:
        raise ValueError("disagreement_penalty must be >= 0")

    weighted_raw: list[float] = []
    by_position: dict[str, list[float]] = {}

    for player in players:
        source_values = [
            float(source_map[player.player_id])
            for source_map in projections_by_source.values()
            if player.player_id in source_map
        ]
        if source_values:
            if source_weights is None:
                raw = float(sum(source_values) / len(source_values))
            else:
                num = 0.0
                den = 0.0
                for source_name, source_map in projections_by_source.items():
                    if player.player_id not in source_map:
                        continue
                    w = float(source_weights.get(source_name, 1.0))
                    if w <= 0:
                        continue
                    num += w * float(source_map[player.player_id])
                    den += w
                raw = float(num / den) if den > 0 else float(player.projection)
        else:
            raw = float(player.projection)

        weighted_raw.append(raw)
        by_position.setdefault(player.position, []).append(raw)

    position_anchor = {
        pos: float(sum(vals) / len(vals))
        for pos, vals in by_position.items()
    }

    out: list[float] = []
    for idx, player in enumerate(players):
        raw = weighted_raw[idx]
        anchor = position_anchor.get(player.position, raw)
        shrunk = anchor + ((1.0 - shrink_strength) * (raw - anchor))

        source_values = [
            float(source_map[player.player_id])
            for source_map in projections_by_source.values()
            if player.player_id in source_map
        ]
        disagreement = float(statistics.pstdev(source_values)) if len(source_values) >= 2 else 0.0
        adjusted = shrunk - (disagreement_penalty * disagreement)
        out.append(max(clip_min, adjusted))

    return out


def apply_news_volatility_adjustments(
    players: Sequence[Player],
    base_projections: Sequence[float],
    signal_by_player_id: Mapping[str, NewsSignal | str],
    signal_policies: Sequence[NewsSignalPolicy] | None = None,
    clip_min: float = 0.0,
) -> NewsVolatilityAdjustmentResult:
    if len(players) != len(base_projections):
        raise ValueError("base_projections length must match players length")

    policy_index = {
        policy.signal.value: policy
        for policy in (signal_policies if signal_policies is not None else _DEFAULT_NEWS_SIGNAL_POLICIES)
    }

    adjusted_projections: list[float] = []
    adjusted_players: list[Player] = []
    penalties: dict[str, float] = {}
    variance_multipliers: dict[str, float] = {}

    for i, player in enumerate(players):
        raw_signal = signal_by_player_id.get(player.player_id, NewsSignal.HEALTHY_CONFIRMED_ROLE.value)
        signal_value = raw_signal.value if isinstance(raw_signal, NewsSignal) else str(raw_signal).strip().lower()
        policy = policy_index.get(signal_value)
        if policy is None:
            policy = policy_index[NewsSignal.HEALTHY_CONFIRMED_ROLE.value]

        base = float(base_projections[i])
        adjusted = max(clip_min, base - float(policy.mean_penalty))
        adjusted_projections.append(adjusted)
        penalties[player.player_id] = float(policy.mean_penalty)
        variance_multipliers[player.player_id] = float(policy.variance_multiplier)

        base_std = player.distribution.std_dev
        if base_std is None:
            adjusted_distribution = replace(player.distribution)
        else:
            adjusted_distribution = DistributionSpec(
                distribution_type=player.distribution.distribution_type,
                std_dev=max(0.0, float(base_std) * float(policy.variance_multiplier)),
                params=player.distribution.params,
            )
        adjusted_players.append(replace(player, distribution=adjusted_distribution))

    return NewsVolatilityAdjustmentResult(
        adjusted_projections=tuple(adjusted_projections),
        adjusted_players=tuple(adjusted_players),
        penalties_by_player_id=penalties,
        variance_multiplier_by_player_id=variance_multipliers,
    )
