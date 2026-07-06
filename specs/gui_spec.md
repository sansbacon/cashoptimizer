# cash-optimizer GUI Specification (PySide6)

## 1. Purpose
Define a desktop GUI for cash-optimizer using PySide6 to support interactive lineup analysis.

Goals:

1. Provide a fast visual workflow for optimize/sensitivity/simulation.
2. Make lineup diagnostics and stability insights easy to inspect.
3. Support export-first workflows for analysts.

## 2. Technology
- Python 3.11+
- PySide6 >= 6.7
- pandas (optional for table model convenience)
- matplotlib or pyqtgraph (for charts)

## 3. Application Architecture
Pattern:
- MVVM-like separation
  - Views: QWidget/QMainWindow UI
  - ViewModels: command orchestration, async state
  - Services: wrappers over cash_optimizer library

Threading:
- run heavy tasks off UI thread using QThreadPool + QRunnable (or QtConcurrent)
- signal/slot for progress, completion, and errors

## 4. Main Window Layout
Top-level areas:

1. Data Panel (left)
- load CSV button
- file path display
- player count and status summary
- rules controls (salary cap, max team, qb-vs-dst toggle)

2. Action Toolbar (top)
- Optimize
- Sensitivity
- Simulate
- Select Cash
- Stress Test
- Eval Predictions
- Edge Trend
- Export Artifacts

3. Results Tabs (center/right)
- Optimal Lineup
- Sensitivity
- Simulation
- Candidate/Cash Selection
- Stress
- Calibrate
- Analytics
- Logs

4. Status Bar (bottom)
- current task
- elapsed time
- warnings/errors

## 5. Screens and Features

### 5.1 Optimal Lineup Tab
Components:
- slot-based table (QB, RB1, RB2, WR1, WR2, WR3, TE, FLEX, DST)
- salary used, projected points, ties_possible badges

Actions:
- copy lineup
- export lineup CSV

Robust controls:
- enable robust objective
- robust rho
- uncertainty set (`box` or `polygon`)
- robust error CSV selector (player_id + history columns)

### 5.2 Sensitivity Tab
Components:
- sortable table with filters:
  - player_id/name
  - in_optimal
  - delta_enter
  - delta_exit
  - tie_flag
- highlight low-delta fragile spots

Actions:
- export sensitivity CSV

### 5.3 Simulation Tab
Inputs:
- num runs
- sampling mode
- worker count
- seed
- top-k lineups

Outputs:
- summary cards (mean, p05, p50, p95, unique lineups)
- top lineup frequency table
- player inclusion rate table
- optional histogram of optimal projections

Actions:
- cancel run
- export simulation CSVs

### 5.4 Candidate / Cash Selection Tab
Inputs:
- candidate count
- cash threshold
- simulation runs for evaluation

Outputs:
- selected lineup by cash probability
- estimated cash probability
- candidate lineup probability table

### 5.5 Stress Test Tab
Inputs:
- choose default/custom scenarios

Outputs:
- base projection
- worst-case projection
- mean stress projection
- scenario result table

### 5.6 Logs Tab
- task history
- errors with stack trace toggle
- recent output file locations

### 5.7 Calibrate Tab
Inputs:
- calibration CSV selector

Outputs:
- brier score
- log loss
- mean predicted probability
- observed rate

### 5.8 Analytics Tab
Workflows:
1. Prediction evaluation
  - input eval CSV
  - model columns list
  - position/actual column names
  - output RMSE table by (position, model) and best model flag
2. Edge trend
  - select one or more slate CSV files
  - optional cash-lines CSV
  - configure trials and top-N per slot
  - output per-slate and aggregate edge rows

## 6. Data Flow
1. User loads CSV.
2. ViewModel constructs CashOptimizer service.
3. Action triggers worker task.
4. Worker emits progress/results.
5. ViewModel normalizes payload for UI models.
6. Tables/charts refresh.

## 7. UI Models
Use QAbstractTableModel subclasses:
- `OptimalLineupTableModel`
- `SensitivityTableModel`
- `SimulationPlayerStatsModel`
- `SimulationLineupStatsModel`
- `ScenarioResultsModel`

Requirements:
- stable sorting
- copy-to-clipboard support
- row color coding for key diagnostics

## 8. Export Requirements
Export directory:
- default `outputs/`
- configurable via file dialog

Artifacts:
- same CSV artifacts as CLI export flow
- optional JSON summary bundle

## 9. Error Handling UX
- non-blocking toast/dialog for validation errors
- detailed error dialog for exceptions
- retry option for failed actions

## 10. Performance Requirements
- no UI freeze during optimization/simulation
- progress updates at least every 250 ms for long tasks
- ability to cancel simulation and sensitivity jobs
- keep memory bounded for large run counts (aggregate in service)

## 11. GUI Package Structure
- `src/cash_optimizer_gui/app.py` (app bootstrap)
- `src/cash_optimizer_gui/main_window.py`
- `src/cash_optimizer_gui/viewmodels/`
- `src/cash_optimizer_gui/views/`
- `src/cash_optimizer_gui/models/` (Qt table models)
- `src/cash_optimizer_gui/services/optimizer_service.py`
- `src/cash_optimizer_gui/workers/`
- `src/cash_optimizer_gui/resources/`

## 12. Testing Plan

### 12.1 Unit Tests
- ViewModel command mapping to service calls
- table model sorting/filter logic
- settings serialization/deserialization

### 12.2 GUI Integration Tests
- use pytest-qt for click flows:
  - load CSV
  - run optimize/sensitivity/simulate
  - assert tables populated
  - assert export files created

### 12.3 Performance Smoke
- run 1000 simulation scenario in worker
- assert UI remains responsive and completion state updates

## 13. Accessibility and Usability
- keyboard shortcuts for primary actions
- high-contrast friendly table themes
- clear empty/error states

## 14. Phased Implementation
1. Phase 1: CSV load, Optimize, Sensitivity, Export
2. Phase 2: Simulation tab + charts + cancellation
3. Phase 3: Candidate/Cash selection + Stress tab
4. Phase 4: Calibrate + Analytics workflows
5. Phase 5: polish, settings persistence, test hardening
