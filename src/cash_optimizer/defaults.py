from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import SamplingMode, SolverSettings


@dataclass(frozen=True)
class RuntimeDefaults:
    parameter_version: str = "v1"
    solver_backend: str = "cp-sat"
    projection_scale_factor: int = 1000
    cp_sat_num_search_workers: int = 0
    cp_sat_max_time_seconds: float = 0.5
    cp_sat_relative_gap_limit: float = 0.0
    cp_sat_random_seed: int = 1729
    cp_sat_log_search_progress: bool = False
    sensitivity_worker_count: int = 1
    simulation_num_runs_default: int = 5000
    simulation_sampling_mode: SamplingMode = SamplingMode.INDEPENDENT
    simulation_clip_min_projection: float = 0.0
    simulation_clip_max_projection: float | None = None
    simulation_top_k_lineups: int = 50
    simulation_chunk_size: int = 128
    simulation_worker_count: int = 1
    simulation_save_prefix: str = "simulation"

    def to_solver_settings(self) -> SolverSettings:
        return SolverSettings(
            solver_backend=self.solver_backend,
            projection_scale=self.projection_scale_factor,
            cp_sat_num_search_workers=self.cp_sat_num_search_workers,
            cp_sat_max_time_seconds=self.cp_sat_max_time_seconds,
            cp_sat_relative_gap_limit=self.cp_sat_relative_gap_limit,
            cp_sat_random_seed=self.cp_sat_random_seed,
            cp_sat_log_search_progress=self.cp_sat_log_search_progress,
            sensitivity_worker_count=self.sensitivity_worker_count,
        )


def load_runtime_defaults(path: Path | None) -> RuntimeDefaults:
    if path is None:
        return RuntimeDefaults()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Defaults file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Defaults file must contain a JSON object")

    def _sampling_mode(raw: object) -> SamplingMode:
        if raw is None:
            return RuntimeDefaults().simulation_sampling_mode
        return SamplingMode(str(raw))

    return RuntimeDefaults(
        parameter_version=str(payload.get("parameter_version", RuntimeDefaults().parameter_version)),
        solver_backend=str(payload.get("solver_backend", RuntimeDefaults().solver_backend)),
        projection_scale_factor=int(payload.get("projection_scale_factor", RuntimeDefaults().projection_scale_factor)),
        cp_sat_num_search_workers=int(payload.get("cp_sat_num_search_workers", RuntimeDefaults().cp_sat_num_search_workers)),
        cp_sat_max_time_seconds=float(payload.get("cp_sat_max_time_seconds", RuntimeDefaults().cp_sat_max_time_seconds)),
        cp_sat_relative_gap_limit=float(payload.get("cp_sat_relative_gap_limit", RuntimeDefaults().cp_sat_relative_gap_limit)),
        cp_sat_random_seed=int(payload.get("cp_sat_random_seed", RuntimeDefaults().cp_sat_random_seed)),
        cp_sat_log_search_progress=bool(payload.get("cp_sat_log_search_progress", RuntimeDefaults().cp_sat_log_search_progress)),
        sensitivity_worker_count=int(payload.get("sensitivity_worker_count", RuntimeDefaults().sensitivity_worker_count)),
        simulation_num_runs_default=int(payload.get("simulation_num_runs_default", RuntimeDefaults().simulation_num_runs_default)),
        simulation_sampling_mode=_sampling_mode(payload.get("simulation_sampling_mode")),
        simulation_clip_min_projection=float(payload.get("simulation_clip_min_projection", RuntimeDefaults().simulation_clip_min_projection)),
        simulation_clip_max_projection=(
            None
            if payload.get("simulation_clip_max_projection", RuntimeDefaults().simulation_clip_max_projection) is None
            else float(payload.get("simulation_clip_max_projection"))
        ),
        simulation_top_k_lineups=int(payload.get("simulation_top_k_lineups", RuntimeDefaults().simulation_top_k_lineups)),
        simulation_chunk_size=int(payload.get("simulation_chunk_size", RuntimeDefaults().simulation_chunk_size)),
        simulation_worker_count=int(payload.get("simulation_worker_count", RuntimeDefaults().simulation_worker_count)),
        simulation_save_prefix=str(payload.get("simulation_save_prefix", RuntimeDefaults().simulation_save_prefix)),
    )
