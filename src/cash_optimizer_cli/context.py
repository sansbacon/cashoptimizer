from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import click

from cash_optimizer import CashOptimizer, Rules, SolverSettings
from cash_optimizer.defaults import RuntimeDefaults
from cash_optimizer.io import load_players_from_dk_csv


@dataclass
class CLIContext:
    input_csv: Path
    output_dir: Path
    rules: Rules
    solver_settings: SolverSettings
    runtime_defaults: RuntimeDefaults
    as_json: bool
    debug: bool = False
    verbose: bool = False

    _optimizer: CashOptimizer | None = None
    _projection_cache: dict[Path, list[float]] | None = None

    def create_optimizer(self) -> CashOptimizer:
        if self._optimizer is None:
            players = load_players_from_dk_csv(self.input_csv)
            self._optimizer = CashOptimizer(players=players, rules=self.rules, solver_settings=self.solver_settings)
            self.log(f"Loaded {len(players)} players from {self.input_csv}")
        return self._optimizer

    def log(self, message: str) -> None:
        if self.verbose:
            click.echo(f"[verbose] {message}", err=True)

    def resolve_projection_overrides(self, projection_by_player_id: Mapping[str, float] | None) -> list[float] | None:
        if projection_by_player_id is None:
            return None
        optimizer = self.create_optimizer()
        return [
            float(
                projection_by_player_id.get(
                    player.player_id,
                    projection_by_player_id.get(player.name, player.projection),
                )
            )
            for player in optimizer.players
        ]
