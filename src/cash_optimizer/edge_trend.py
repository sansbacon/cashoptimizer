from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .io import load_players_from_dk_csv
from .models import EdgeTrendResult, Rules, SolverSettings, WeeklyEdgeRow
from .optimizer import CashOptimizer


def build_edge_trend_from_slate_paths(
    slate_paths: Sequence[str | Path],
    rules: Rules,
    solver_settings: SolverSettings,
    trials: int = 1000,
    top_n_per_slot: int = 10,
    cash_line_by_slate: dict[str, float] | None = None,
) -> EdgeTrendResult:
    if not slate_paths:
        raise ValueError("slate_paths cannot be empty")

    rows: list[WeeklyEdgeRow] = []
    for slate_path in slate_paths:
        path = Path(slate_path)
        players = load_players_from_dk_csv(path)
        optimizer = CashOptimizer(players=players, rules=rules, solver_settings=solver_settings)
        comparison = optimizer.compare_against_human_heuristic(
            trials=trials,
            top_n_per_slot=top_n_per_slot,
            random_seed=solver_settings.cp_sat_random_seed,
        )

        label = path.stem
        cash_line = None
        if cash_line_by_slate is not None:
            cash_line = cash_line_by_slate.get(label)

        optimizer_above_cash = None
        human_mean_above_cash = None
        if cash_line is not None:
            optimizer_above_cash = comparison.optimizer_projection >= cash_line
            human_mean_above_cash = comparison.human_mean_projection >= cash_line

        rows.append(
            WeeklyEdgeRow(
                slate_label=label,
                optimizer_projection=comparison.optimizer_projection,
                human_best_projection=comparison.human_best_projection,
                human_mean_projection=comparison.human_mean_projection,
                edge_vs_human_best=comparison.edge_vs_human_best,
                edge_vs_human_mean=comparison.edge_vs_human_mean,
                trials=comparison.trials,
                feasible_trials=comparison.feasible_trials,
                cash_line=cash_line,
                optimizer_above_cash=optimizer_above_cash,
                human_mean_above_cash=human_mean_above_cash,
            )
        )

    mean_edge_best = sum(r.edge_vs_human_best for r in rows) / len(rows)
    mean_edge_mean = sum(r.edge_vs_human_mean for r in rows) / len(rows)

    rates = [
        (r.optimizer_above_cash, r.human_mean_above_cash)
        for r in rows
        if r.optimizer_above_cash is not None and r.human_mean_above_cash is not None
    ]
    optimizer_cash_rate = None
    human_mean_cash_rate = None
    if rates:
        optimizer_cash_rate = sum(1 for a, _ in rates if a) / len(rates)
        human_mean_cash_rate = sum(1 for _, b in rates if b) / len(rates)

    return EdgeTrendResult(
        rows=tuple(rows),
        mean_edge_vs_human_best=mean_edge_best,
        mean_edge_vs_human_mean=mean_edge_mean,
        optimizer_cash_rate=optimizer_cash_rate,
        human_mean_cash_rate=human_mean_cash_rate,
    )


def load_cash_lines(csv_path: str | Path) -> dict[str, float]:
    path = Path(csv_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    out: dict[str, float] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"slate_label", "cash_line"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("cash-lines CSV must include columns: slate_label,cash_line")
        for row in reader:
            label = str(row.get("slate_label", "")).strip()
            cash_line_raw = str(row.get("cash_line", "")).strip()
            if not label or not cash_line_raw:
                continue
            out[label] = float(cash_line_raw)
    return out
