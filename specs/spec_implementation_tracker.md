# Spec Implementation Tracker

Last updated: 2026-07-04

Status legend:
- Implemented: feature is present in code and covered by current workflows/tests.
- Partial: foundational support exists, but key parts of the spec item are incomplete.
- Planned: not implemented yet.

## How To Use This Tracker

1. When a feature is added, update the matching spec section row.
2. If behavior changes, update the mapped code artifacts and notes.
3. Keep Partial rows specific about what is missing.
4. Re-run tests and note relevant test files when status changes to Implemented.

## Coverage Matrix

| Spec Section | Status | Implemented Artifacts | Notes / Remaining Work |
| --- | --- | --- | --- |
| 1. Purpose | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py) | Core optimize/sensitivity/simulation goals are delivered. |
| 2. Scope | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Single-lineup cash scope enforced; portfolio out of scope. |
| 3.1 Functional | Implemented | [src/cash_optimizer/io.py](src/cash_optimizer/io.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Input, optimize, sensitivity, simulation, and audit outputs available. |
| 3.2 Non-Functional | Partial | [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [examples/benchmark_suite.py](examples/benchmark_suite.py), [examples/ci_benchmark_guardrail.py](examples/ci_benchmark_guardrail.py), [.github/workflows/ci.yml](.github/workflows/ci.yml), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Determinism, benchmark checks, and CI benchmark guardrails are implemented, including profile-and-scale threshold calibration controls; tighter SLA-style limits still require environment-specific tuning. |
| 4. DK Rules | Implemented | [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Roster legality and optional constraints are implemented. |
| 5. Mathematical Formulation | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Slot-based binary formulation implemented in CP-SAT. |
| 6. Exact Sensitivity | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_smoke.py](tests/test_smoke.py) | Forced-in/forced-out exact deltas implemented. |
| 7.1 Core Design | Partial | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Caching and worker reuse implemented; full incremental model reuse is limited by CP-SAT model rebuild pattern. |
| 7.2 Solver Choice | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [pyproject.toml](pyproject.toml), [tests/test_advanced.py](tests/test_advanced.py) | OR-Tools CP-SAT is primary and configurable HiGHS fallback is implemented with parity coverage tests. |
| 7.2.1 CP-SAT Config | Implemented | [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Seed, workers, gap, time, and logging settings supported. |
| 7.3 Parallelization | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [tests/test_advanced.py](tests/test_advanced.py) | Simulation and sensitivity both support process-level parallelization; sensitivity is controlled by `SolverSettings.sensitivity_worker_count`. |
| 7.4 Caching | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [tests/test_advanced.py](tests/test_advanced.py) | In-memory LRU and optional disk-backed result cache tiers are implemented. |
| 7.5 Player Pool Pruning | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Inactive/out filtering implemented; advanced dominance pruning not added. |
| 7.6 CP-SAT Execution Pattern | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_advanced.py](tests/test_advanced.py) | Baseline solve, simulation worker flow, and sensitivity forced solve worker dispatch/rebuild pattern are implemented. |
| 7.7 Distribution Simulation | Implemented | [src/cash_optimizer/sampling.py](src/cash_optimizer/sampling.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Independent/correlated sampling and online aggregation implemented. |
| 8. Data Model | Implemented | [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer/io.py](src/cash_optimizer/io.py), [tests/test_smoke.py](tests/test_smoke.py) | Core and optional player schema fields (including ownership, game_total, spread, floor/ceiling, status, distribution metadata) are first-class in ingest/model. |
| 9. API Surface | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/__init__.py](src/cash_optimizer/__init__.py) | Service and batch APIs exposed. |
| 10. Tie Handling | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_smoke.py](tests/test_smoke.py) | Deterministic tie-break and tie detection implemented. |
| 11. Benchmark Plan | Implemented | [examples/benchmark_suite.py](examples/benchmark_suite.py), [examples/ci_benchmark_guardrail.py](examples/ci_benchmark_guardrail.py), [examples/benchmark_history_report.py](examples/benchmark_history_report.py), [.github/workflows/ci.yml](.github/workflows/ci.yml), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Baseline/sensitivity/simulation benchmark automation, CI threshold gating, and historical benchmark CSV reporting are implemented. |
| 12. Testing Strategy | Partial | [tests](tests), [pytest.ini](pytest.ini), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py), [tests/test_gui_qt.py](tests/test_gui_qt.py) | Functional, CLI, and pytest-qt GUI integration coverage are expanded (including rich output and benchmark profile controls); strict CI performance gates remain environment-dependent. |
| 13. Implementation Plan | Implemented | [src](src), [tests](tests) | Planned phases are largely completed at baseline level. |
| 14. Risks/Mitigations | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [specs/governance_policy.json](specs/governance_policy.json), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Risks are documented and enforced with executable guardrails for readiness, rollout recommendation, benchmark calibration, and policy-driven governance checks. |
| 15. Definition of Done | Implemented | [src](src), [tests](tests), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [specs/governance_policy.json](specs/governance_policy.json) | DoD checks are executable via readiness-gate and governance-check commands with fail-fast behavior under policy constraints. |
| 16. OR-Tools Environment | Implemented | [pyproject.toml](pyproject.toml) | Dependency and runtime requirements are in place. |
| 17.1 Cash-Probability Objective | Implemented | [src/cash_optimizer/selection.py](src/cash_optimizer/selection.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Candidate-based cash probability selection implemented. |
| 17.2 Risk-Adjusted Objective | Implemented | [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/cash_metrics.py](src/cash_optimizer/cash_metrics.py), [tests/test_advanced.py](tests/test_advanced.py) | Profile-orchestrated risk-adjusted selection implemented through contest-profile optimization routing. |
| 17.3 Floor-Weighted Blending | Implemented | [src/cash_optimizer/projections.py](src/cash_optimizer/projections.py) | Projection blending functions implemented. |
| 17.4 Volatility/Role Penalties | Implemented | [src/cash_optimizer/projections.py](src/cash_optimizer/projections.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_advanced.py](tests/test_advanced.py) | Automated signal-driven mean penalties and variance multipliers implemented via NewsSignal policy layer. |
| 17.5 Correlation-Aware Downside | Implemented | [src/cash_optimizer/robust.py](src/cash_optimizer/robust.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [tests/test_smoke.py](tests/test_smoke.py) | Covariance-aware objective plus rule-level correlation caps for game environments and same-team non-QB skill concentration implemented. |
| 17.6 News-Volatility Layer | Implemented | [src/cash_optimizer/projections.py](src/cash_optimizer/projections.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | End-to-end news-volatility adjustments implemented with default policy table and CLI integration. |
| 17.7 Ensemble/Shrinkage | Implemented | [src/cash_optimizer/projections.py](src/cash_optimizer/projections.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_advanced.py](tests/test_advanced.py) | Ensemble blending with shrinkage toward positional anchors and disagreement penalty implemented. |
| 17.8 Contest-Type Profiles | Implemented | [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer/cash_metrics.py](src/cash_optimizer/cash_metrics.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Profile defaults plus objective orchestration by contest type implemented in library and CLI optimize-profile workflow. |
| 17.9 Fragility Score | Implemented | [src/cash_optimizer/sensitivity.py](src/cash_optimizer/sensitivity.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Sensitivity outputs now include fragility summary and alert flag. |
| 17.10 Stress Regimes | Implemented | [src/cash_optimizer/stress.py](src/cash_optimizer/stress.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Stress runner implemented. |
| 17.11 Backtest/Calibration Loop | Implemented | [src/cash_optimizer/calibration.py](src/cash_optimizer/calibration.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_calibration_governance.py](tests/test_calibration_governance.py) | Weekly calibration metrics, governance promotion gates, and automated profile-parameter tuning from backtest rows are implemented. |
| 17.12 Rollout Plan | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [specs/governance_policy.json](specs/governance_policy.json), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Plan is captured and executable through phased rollout recommendation plus policy-driven governance checks. |
| 18. Default Parameters | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/defaults.py](src/cash_optimizer/defaults.py), [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Runtime defaults are externally configurable via JSON defaults file/API and propagated through CLI workflows with parameter-version metadata. |
| 19.1 Single-Lineup Policy | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | No portfolio objective in implementation. |
| 19.2 Covariance-Aware Downside | Implemented | [src/cash_optimizer/robust.py](src/cash_optimizer/robust.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | Robust covariance-aware objective implemented. |
| 19.3 Normalized Objective Composition | Implemented | [src/cash_optimizer/objective_selection.py](src/cash_optimizer/objective_selection.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_advanced.py](tests/test_advanced.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Normalized multi-term lineup composer implemented with CLI command `select-normalized`. |
| 19.4 Threshold Probability Primary Target | Implemented | [src/cash_optimizer/selection.py](src/cash_optimizer/selection.py) | Candidate scenario threshold selector implemented. |
| 19.5 Contest-Structure Tuning | Implemented | [src/cash_optimizer/models.py](src/cash_optimizer/models.py), [src/cash_optimizer/cash_metrics.py](src/cash_optimizer/cash_metrics.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [tests/test_advanced.py](tests/test_advanced.py) | Contest profile structure now includes correlation caps and penalty strength applied during profile orchestration. |
| 19.6 Covariance Sparsification | Implemented | [src/cash_optimizer/robust.py](src/cash_optimizer/robust.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py) | Configurable correlation-threshold sparsification implemented in library, CLI, and GUI robust controls. |
| 19.7 Weekly Calibration Governance | Implemented | [src/cash_optimizer/calibration.py](src/cash_optimizer/calibration.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [tests/test_calibration_governance.py](tests/test_calibration_governance.py) | Automated governance decision loop implemented via calibration metrics comparison and promotion gates. |
| 19.8 Implementation Priority | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [specs/governance_policy.json](specs/governance_policy.json) | Priority plan is codified through rollout stage recommendations and governance policy thresholds with automated pass/fail decisions. |
| 19.9 Human-Heuristic Benchmark | Implemented | [src/cash_optimizer/baselines.py](src/cash_optimizer/baselines.py), [src/cash_optimizer/optimizer.py](src/cash_optimizer/optimizer.py) | compare-human capability implemented. |
| 19.10 Position-Wise Model Harness | Implemented | [src/cash_optimizer/prediction_eval.py](src/cash_optimizer/prediction_eval.py) | Position-wise RMSE evaluator implemented. |
| 19.11 Weekly Edge Trend Dashboard | Implemented | [src/cash_optimizer/edge_trend.py](src/cash_optimizer/edge_trend.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py) | Multi-slate edge trend analytics/export implemented. |
| 20. Spec Coverage Matrix | Implemented | [cash_optimizer_spec.md](cash_optimizer_spec.md), [spec_implementation_tracker.md](spec_implementation_tracker.md) | This tracker is the detailed source of truth. |

## App Surface Tracking

### CLI

| CLI Spec Section | Status | Implemented Artifacts | Notes / Remaining Work |
| --- | --- | --- | --- |
| 3. Entry Point + Global Options | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [pyproject.toml](pyproject.toml) | Console script and global options are implemented, including input/rules/seed/json/debug toggles. |
| 4.1 optimize | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Robust options and projection override are implemented; `--save` supports both JSON and CSV outputs by extension. |
| 4.2 sensitivity | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py) | Top-N and CSV export paths are implemented with robust options. |
| 4.3 simulate | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Simulation options and default `--save-prefix simulation` now align with spec. |
| 4.4 export | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Export now accepts simulation option parity (`sampling-mode`, workers, chunking, top-k, clipping, save-prefix). |
| 4.5 candidates | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Candidate generation plus `--save` CSV output implemented and tested. |
| 4.6 select-cash | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer/selection.py](src/cash_optimizer/selection.py) | Threshold-based candidate selection and simulation controls are implemented. |
| 4.7 stress | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer/stress.py](src/cash_optimizer/stress.py), [src/cash_optimizer_cli/exporters.py](src/cash_optimizer_cli/exporters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Stress execution now supports `--save` artifact export and custom `--scenario-file` CSV input. |
| 4.8-4.16 advanced commands | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer/performance.py](src/cash_optimizer/performance.py), [src/cash_optimizer/calibration.py](src/cash_optimizer/calibration.py), [src/cash_optimizer/edge_trend.py](src/cash_optimizer/edge_trend.py), [src/cash_optimizer/prediction_eval.py](src/cash_optimizer/prediction_eval.py) | Calibrate, governance, tuning, compare-human, prediction evaluation, edge trend, normalize selection, profile optimization, and benchmark commands are implemented. |
| 5-6 I/O + Error Handling | Implemented | [src/cash_optimizer_cli/validators.py](src/cash_optimizer_cli/validators.py), [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py) | JSON output mode and exit-code mapping (2 validation, 3 infeasible, 1 runtime) are implemented. |
| 7-10 Logging/Perf/Structure/Tests | Implemented | [src/cash_optimizer_cli/main.py](src/cash_optimizer_cli/main.py), [src/cash_optimizer_cli/context.py](src/cash_optimizer_cli/context.py), [src/cash_optimizer_cli/formatters.py](src/cash_optimizer_cli/formatters.py), [tests/test_cli_smoke.py](tests/test_cli_smoke.py) | Package structure, smoke coverage, verbose diagnostics, and optional rich-rendered output mode are implemented. |

### GUI

| GUI Spec Section | Status | Implemented Artifacts | Notes / Remaining Work |
| --- | --- | --- | --- |
| 2-3 Technology + Architecture | Implemented | [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [src/cash_optimizer_gui/viewmodels/main_viewmodel.py](src/cash_optimizer_gui/viewmodels/main_viewmodel.py), [src/cash_optimizer_gui/workers/task_worker.py](src/cash_optimizer_gui/workers/task_worker.py), [src/cash_optimizer_gui/views/simulation_chart.py](src/cash_optimizer_gui/views/simulation_chart.py), [tests/test_gui_qt.py](tests/test_gui_qt.py) | PySide6 MVVM-style separation, threaded task execution, simulation charting view stack, and worker progress hooks with emitted progress messages are implemented. |
| 4 Main Window Layout | Implemented | [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [tests/test_gui_qt.py](tests/test_gui_qt.py) | Main window includes data panel file-path display, player/status summary, rules summary, full action toolbar, results tabs, and bottom status indicators. |
| 5.1-5.8 Screens and Features | Implemented | [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [src/cash_optimizer_gui/services/optimizer_service.py](src/cash_optimizer_gui/services/optimizer_service.py), [src/cash_optimizer_gui/views/result_view.py](src/cash_optimizer_gui/views/result_view.py), [src/cash_optimizer_gui/views/simulation_chart.py](src/cash_optimizer_gui/views/simulation_chart.py) | Core tab workflows include simulation charting, richer diagnostics, scenario-file stress input, and tab-level CSV/JSON export actions. |
| 6 Data Flow | Implemented | [src/cash_optimizer_gui/viewmodels/main_viewmodel.py](src/cash_optimizer_gui/viewmodels/main_viewmodel.py), [src/cash_optimizer_gui/services/optimizer_service.py](src/cash_optimizer_gui/services/optimizer_service.py) | Load -> task -> signal -> result-view refresh pipeline is implemented. |
| 7 UI Models | Implemented | [src/cash_optimizer_gui/models/table_models.py](src/cash_optimizer_gui/models/table_models.py), [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py) | Dedicated per-domain model subclasses with stable sorting and diagnostic color-coding are implemented and wired into views. |
| 8 Export Requirements | Implemented | [src/cash_optimizer_gui/services/optimizer_service.py](src/cash_optimizer_gui/services/optimizer_service.py), [src/cash_optimizer_gui/views/result_view.py](src/cash_optimizer_gui/views/result_view.py), [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [tests/test_gui_import.py](tests/test_gui_import.py) | CSV artifact export and optional JSON summary bundle are implemented; tab-level CSV/JSON export is available in result views. |
| 9-10 Error/Performance UX | Implemented | [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [src/cash_optimizer_gui/viewmodels/main_viewmodel.py](src/cash_optimizer_gui/viewmodels/main_viewmodel.py), [src/cash_optimizer_gui/workers/task_worker.py](src/cash_optimizer_gui/workers/task_worker.py) | Retry affordance for failed actions and periodic heartbeat progress updates are implemented, with cancel controls preserved. |
| 11-14 Package/Test/Accessibility/Phases | Implemented | [src/cash_optimizer_gui](src/cash_optimizer_gui), [src/cash_optimizer_gui/main_window.py](src/cash_optimizer_gui/main_window.py), [src/cash_optimizer_gui/views/result_view.py](src/cash_optimizer_gui/views/result_view.py), [tests/test_gui_import.py](tests/test_gui_import.py), [tests/test_gui_qt.py](tests/test_gui_qt.py) | Package structure, keyboard shortcuts, control-state persistence, pytest-qt click flows (load/optimize/sensitivity/simulate), high-contrast diagnostic color-path assertions, and explicit empty/error-state checks are implemented. |

## Prioritized Implementation Queue

### P0 (High Impact / Core Reliability)

| Priority | Queue Item | Spec Mapping | Outcome To Mark Implemented |
| --- | --- | --- | --- |
| P0 | Parallelize sensitivity forced solves (Completed 2026-07-04) | 7.3, 7.6 | `solve_sensitivity_all` runs forced-in/forced-out solves in worker processes with deterministic result merge and matching sensitivity outputs. |
| P0 | Add CI-enforced performance guardrails (Completed 2026-07-04) | 3.2, 11, 12, 14, 15 | Benchmarks run in CI with pass/fail thresholds and regression alerts; governance checks documented and automated. |
| P0 | Add disk cache tier for repeated runs (Completed 2026-07-04) | 7.4, 7.1 | Optional disk-backed cache keyed by slate/rules/projection hash with invalidation strategy and tests. |
| P0 | Complete CLI parity for missing core options (Completed 2026-07-04) | CLI 4.4, 4.5, 4.7 | `export` accepts full simulation controls; `candidates --save`; `stress --save` and `--scenario-file` implemented and tested. |

### P1 (Product Completeness)

| Priority | Queue Item | Spec Mapping | Outcome To Mark Implemented |
| --- | --- | --- | --- |
| P1 | Add HiGHS fallback solver path (Completed 2026-07-04) | 7.2 | Configurable solver selection with OR-Tools primary and validated HiGHS fallback behavior parity tests. |
| P1 | Extend player ingest for optional schema fields (Completed 2026-07-04) | 8 | Loader and model support optional fields (for example ownership/game_total/spread) with non-breaking defaults and validation. |
| P1 | Expose default parameter table through runtime config (Completed 2026-07-04) | 18, 19.8 | Spec default parameters are externally configurable (CLI/config file/API) and versioned in outputs. |
| P1 | Finish benchmark reporting workflow (Completed 2026-07-04) | 11 | Historical benchmark artifact/report generation (CSV/JSON summary over time) and trend visibility from CLI/examples. |
| P1 | Tighten CLI optimize/simulate output parity (Completed 2026-07-04) | CLI 4.1, 4.3, 7-10 | Optimize save mode handles JSON/CSV explicitly; simulate `--save-prefix` default aligns with spec; richer CLI UX coverage. |

### P2 (GUI UX and Quality Hardening)

| Priority | Queue Item | Spec Mapping | Outcome To Mark Implemented |
| --- | --- | --- | --- |
| P2 | Add GUI simulation charts and richer diagnostics (Completed 2026-07-04) | GUI 2-3, 5.1-5.8 | Simulation histogram/summary visuals and advanced table diagnostics (filters/highlights) are available in tabs. |
| P2 | Add dedicated GUI table models per domain (Completed 2026-07-04) | GUI 7 | Domain-specific `QAbstractTableModel` classes replace generic model where required, with stable sorting and diagnostic coloring. |
| P2 | Expand GUI export and recovery UX (Completed 2026-07-04) | GUI 8, 9-10 | Optional JSON summary bundle export, retry affordances for failed tasks, and better long-task progress behavior. |
| P2 | Add pytest-qt integration and accessibility pass (Completed 2026-07-04) | GUI 11-14, 12 | End-to-end GUI workflow tests and accessibility/usability checks (shortcuts, contrast-friendly states, empty/error state polish). |

### P3 (Test Hardening and Accessibility Coverage)

| Priority | Queue Item | Spec Mapping | Outcome To Mark Implemented |
| --- | --- | --- | --- |
| P3 | Persist GUI control-state across sessions (Completed 2026-07-04) | GUI 13, 14 | Main window stores/restores run-control and analytics inputs to local GUI state file with safe defaults and load/save error handling. |
| P3 | Add pytest-qt state restoration coverage (Completed 2026-07-04) | GUI 12, 14 | Integration test verifies state round-trip across window close/reopen and protects persistence behavior from regressions. |
| P3 | Add pytest-qt click-flow for primary actions (Completed 2026-07-04) | GUI 12, 5.1-5.3 | Simulated load/optimize/sensitivity/simulate action flow asserts table population and task-state transitions. |
| P3 | Add explicit accessibility and empty/error-state assertions (Completed 2026-07-04) | GUI 13 | Tests verify keyboard-first interaction affordances, contrast-oriented row styling paths, and clear empty/error state copy. |

## Suggested Execution Order

1. Deliver all P0 items first to close core reliability and parity gaps.
2. Complete P1 items next to align architecture and configuration with the full spec.
3. Finish P2 items for GUI quality and long-term maintainability.
4. Use P3 as the final polish lane for incremental UX and CI hardening.
