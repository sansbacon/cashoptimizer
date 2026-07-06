# API Reference - Additional Details

## Library Modules

The cash-optimizer library is organized into several core modules:

### cash_optimizer (Main Package)

Core optimization engine.

**Key Classes & Functions:**
- `CashOptimizer` - Main optimization class
- `Player` - Player data structure
- `Lineup` - Lineup collection
- `OptimalResult` - Optimization result
- `RobustSettings` - Robust optimization configuration
- `compute_calibration_metrics()` - Projection accuracy metrics
- `build_error_covariance_from_errors()` - Covariance matrix builder

### cash_optimizer.io

File I/O utilities for loading player data.

**Functions:**
- `load_players_from_dk_csv()` - Load DraftKings CSV export
- `load_players_from_dict()` - Load from dictionary
- `validate_player_data()` - Validate player objects

### cash_optimizer.performance

Governance automation and benchmarking.

**Functions:**
- `run_readiness_gate()` - Validate readiness for deployment
- `recommend_rollout_stage()` - Get phased rollout recommendation
- `calibrate_benchmark_thresholds_from_history()` - Auto-calibrate thresholds
- `run_governance_check()` - Comprehensive governance check

**Result Classes:**
- `ReadinessGateResult` - Readiness check result
- `RolloutRecommendation` - Rollout recommendation
- `BenchmarkThresholdRecommendation` - Calibration result
- `GovernanceCheckResult` - Governance check result

### cash_optimizer.models

Data model classes.

**Classes:**
- `Player` - Player information
- `Lineup` - Complete lineup (8-9 players)
- `OptimalResult` - Optimal lineup result
- `SensitivityResult` - Sensitivity analysis result
- `SimulationResult` - Simulation result
- Various result dataclasses for governance

### cash_optimizer.sensitivity

Player sensitivity analysis (forced-in/forced-out).

**Key Functions:**
- Internal helpers for sensitivity computation

### cash_optimizer.simulation

Monte Carlo simulation engine.

**Key Functions:**
- `run_simulation()` - High-volume scenario simulation
- Sampling and evaluation utilities

### cash_optimizer.robust

Robust optimization under uncertainty.

**Key Functions:**
- `solve_robust()` - Robust lineup optimization
- Uncertainty set builders

### cash_optimizer.objective_selection

Multi-objective lineup generation.

**Key Functions:**
- `generate_candidate_lineups()` - Diverse candidate generation
- `select_best_cash_lineup_by_probability()` - Cash threshold selection

### cash_optimizer.stress

Stress testing and downside evaluation.

**Key Functions:**
- `run_stress_test()` - Stress test lineup robustness

## CLI Modules

### cash_optimizer_cli.main

Entry point for CLI commands.

**Key Elements:**
- `@click.group()` main CLI group
- `@click.command()` individual commands
- Command handlers for: optimize, sensitivity, simulate, export, benchmark, readiness-gate, rollout-recommend, benchmark-calibrate, governance-check

### cash_optimizer_cli.validators

Input validation utilities.

**Functions:**
- `validate_csv_path()` - Validate CSV file exists
- `validate_profile()` - Validate threshold profile
- `validate_percentile()` - Validate percentile value

### cash_optimizer_cli.formatters

Output formatting with optional Rich tables.

**Functions:**
- `configure_output()` - Set output mode (plain/rich)
- `format_result()` - Format result object for display

### cash_optimizer_cli.exporters

Result export utilities.

**Functions:**
- `export_optimal_lineup()` - Export to CSV
- `export_sensitivity()` - Export sensitivity analysis
- `export_simulation()` - Export simulation results

### cash_optimizer_cli.context

CLI context and state.

**Classes:**
- `CliContext` - Holds CLI execution context
  - `verbose` - Verbose logging flag
  - `log()` - Log diagnostic messages

### cash_optimizer_cli.projection_overrides

Projection modification utilities.

**Functions:**
- Utilities for adjusting player projections

## GUI Modules

### cash_optimizer_gui.app

Application entry point.

**Functions:**
- `main()` - Launch GUI application

### cash_optimizer_gui.main_window

Main application window.

**Classes:**
- `MainWindow` - Qt main window widget

### cash_optimizer_gui.viewmodels.main_viewmodel

MVVM view model for main window.

**Classes:**
- `MainViewModel` - Connects service to view

### cash_optimizer_gui.services.optimizer_service

Service layer for optimization operations.

**Classes:**
- `OptimizerService` - High-level optimization service

### cash_optimizer_gui.models.table_models

Qt table model implementations.

**Classes:**
- Various QAbstractTableModel subclasses for results display

### cash_optimizer_gui.views.result_view

Result display widgets.

**Classes:**
- Result view widgets for various result types

### cash_optimizer_gui.workers.task_worker

Background task execution.

**Classes:**
- `WorkerSignals` - Qt signals for async updates
- `TaskWorker` - QRunnable for background tasks
- Progress and completion signals

## Configuration

### Governance Policy JSON

Located at `specs/governance_policy.json`:

```json
{
  "simulation_runs": 200,
  "threshold_profile": "ci",
  "threshold_scale": 1.0,
  "require_clean": true,
  "minimum_stage": "phase4_validation"
}
```

### Benchmark Profiles

Predefined profiles in CLI (`main.py`):

```python
{
  "strict": (50, 300, 5000),      # (baseline_ms, sensitivity_ms, simulation_ms)
  "ci": (100, 500, 10000),
  "relaxed": (200, 1000, 20000),
}
```

## Export Formats

### CSV Export

Standard comma-separated values format compatible with Excel.

**Columns vary by result type:**
- Lineup export: Player, Position, Salary, Projection
- Sensitivity export: Player, Position, Salary, In_Optimal, Forced_In_Delta, Forced_Out_Delta, Impact
- Simulation export: Percentile, Projection, Win_Rate_vs_Cash, ...

## Performance Characteristics

### Optimization (solve_optimal)

- **Typical Time**: 50-150 ms on modern hardware
- **Deterministic**: Yes (same results on repeated runs)
- **Scalability**: ~150 players max

### Sensitivity

- **Typical Time**: 300-600 ms
- **Lineups Evaluated**: ~150 (one per player forced-in + one forced-out)
- **Parallelizable**: Yes

### Simulation

- **Typical Time**: 5-20 seconds (for 5000 runs)
- **Deterministic**: With fixed seed
- **Parallelizable**: Yes

## Dependencies

### Runtime

- `ortools>=9.10` - Constraint programming solver
- `numpy>=1.26` - Numerical computing
- `highspy>=1.8` - HiGHS solver (fallback)
- `click>=8.1` - CLI framework

### Optional

- `PySide6>=6.7` - Qt GUI
- `rich>=10.0` - Rich terminal output
- `pytest>=8.0` - Testing

### Documentation

- `mkdocs>=1.6` - Documentation builder
- `mkdocs-material>=9.5` - Material theme
- `pymdown-extensions>=10.8` - Markdown extensions

## Version History

**0.1.0** (Current)
- Initial release
- Core optimization engine
- CLI and GUI interfaces
- Governance automation
- Comprehensive test suite
