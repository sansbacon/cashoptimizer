# cash-optimizer CLI Specification (Click)

## 1. Purpose
Define a production-ready command-line interface for the cash-optimizer library using Click.

Goals:

1. Run core optimizer workflows from terminal.
2. Support local CSV-based experimentation with fast iteration.
3. Export deterministic artifacts for downstream analysis.
4. Provide command parity with major library features.

## 2. Technology
- Python 3.11+
- click >= 8.1
- rich (optional, for pretty tables and status)

## 3. Entry Point
- Module: `cash_optimizer_cli.main`
- Console script: `cash-optimizer`

Command root:
- `cash-optimizer [GLOBAL_OPTIONS] COMMAND [ARGS]`

Global options:
- `--input-csv PATH` (default: `proj.csv`)
- `--salary-cap INT` (default: 50000)
- `--max-team INT` (optional)
- `--disallow-qb-vs-opp-dst / --allow-qb-vs-opp-dst` (default allow)
- `--seed INT` (default: 1729)
- `--json / --no-json` (output format toggle)
- `--output-dir PATH` (default: `outputs`)

## 4. Commands

### 4.1 optimize
Purpose:
- Solve deterministic optimal lineup.

Usage:
- `cash-optimizer optimize`

Options:
- `--projection-file PATH` (optional alternative projections)
- `--save PATH` (optional JSON or CSV)
- `--robust-rho FLOAT` (default 0.0)
- `--robust-set [box|polygon]` (default box)
- `--robust-cov-source PATH` (required when `--robust-rho > 0`)

Output:
- optimal lineup players
- salary used
- projected points
- ties_possible

### 4.2 sensitivity
Purpose:
- Compute forced-in/forced-out player sensitivity.

Usage:
- `cash-optimizer sensitivity`

Options:
- `--top N` (show top N by smallest absolute delta)
- `--save PATH` (CSV)
- `--projection-file PATH` (optional alternative projections)
- `--robust-rho FLOAT` (default 0.0)
- `--robust-set [box|polygon]` (default box)
- `--robust-cov-source PATH` (required when `--robust-rho > 0`)

Output:
- per-player entry:
  - in_optimal
  - delta_enter or delta_exit
  - tie_flag

### 4.3 simulate
Purpose:
- Run Monte Carlo projection-distribution simulation.

Usage:
- `cash-optimizer simulate --runs 5000`

Options:
- `--runs INT` (default 5000)
- `--sampling-mode [independent|correlated]`
- `--workers INT` (default 1)
- `--chunk-size INT` (default 128)
- `--top-k-lineups INT` (default 50)
- `--clip-min FLOAT` (default 0)
- `--clip-max FLOAT` (optional)
- `--save-prefix TEXT` (default: `simulation`)

Output:
- summary metrics
- top lineup frequencies
- player inclusion rates
- optional CSV exports

### 4.4 export
Purpose:
- Run optimize + sensitivity + simulation and export all artifacts.

Usage:
- `cash-optimizer export --runs 1000`

Options:
- simulation options from `simulate`

Output files:
- `optimal_lineup.csv`
- `sensitivity.csv`
- `simulation_summary.csv`
- `simulation_player_stats.csv`
- `simulation_lineup_stats.csv`

### 4.5 candidates
Purpose:
- Generate alternative candidate lineups for cash analysis.

Usage:
- `cash-optimizer candidates --count 25`

Options:
- `--count INT` (default 25)
- `--save PATH`

Output:
- lineup keys and basic stats

### 4.6 select-cash
Purpose:
- Select best lineup by estimated cash probability using sampled scenarios.

Usage:
- `cash-optimizer select-cash --threshold 130 --runs 2000`

Options:
- `--threshold FLOAT` (required)
- `--candidates INT` (default 25)
- simulation options subset (`--runs`, `--sampling-mode`, `--seed`)

Output:
- selected lineup
- estimated cash probability
- candidate_count

### 4.7 stress
Purpose:
- Run stress scenarios against current slate.

Usage:
- `cash-optimizer stress`

Options:
- `--save PATH`
- `--scenario-file PATH` (optional custom scenario definitions)

Output:
- base projection
- worst_case_projection
- mean_stress_projection
- per-scenario lineup/projection

### 4.8 calibrate
Purpose:
- Compute calibration metrics from predicted probabilities and outcomes.

Usage:
- `cash-optimizer calibrate --input calibration.csv`

Expected CSV columns:
- `predicted_probability`
- `observed_event`

Output:
- brier_score
- log_loss
- mean_predicted_probability
- observed_rate

### 4.9 compare-human
Purpose:
- Compare optimizer lineup to a paper-style human heuristic baseline.

Usage:
- `cash-optimizer compare-human --trials 1000 --top-n-per-slot 10`

Options:
- `--trials INT` (default 1000)
- `--top-n-per-slot INT` (default 10)
- `--projection-file PATH` (optional)

Output:
- optimizer projection
- human best projection
- human mean projection
- edge vs human best
- edge vs human mean
- feasible trial count

### 4.10 evaluate-predictions
Purpose:
- Evaluate candidate prediction columns by position and select best RMSE model per position.

Usage:
- `cash-optimizer evaluate-predictions --input eval.csv --model-col lr --model-col rf`

Options:
- `--input PATH` (required)
- `--position-col TEXT` (default `position`)
- `--actual-col TEXT` (default `actual`)
- `--model-col TEXT` (repeatable, required)
- `--save PATH` (optional output CSV)

Output:
- RMSE rows per (position, model)
- best model mapping by position

### 4.11 edge-trend
Purpose:
- Run optimizer-vs-human benchmark across multiple slates and compute trend metrics.

Usage:
- `cash-optimizer edge-trend --slates-glob "data/slates/*.csv" --trials 1000`

Options:
- `--slates-glob TEXT` (required)
- `--trials INT` (default 1000)
- `--top-n-per-slot INT` (default 10)
- `--cash-lines PATH` (optional CSV with `slate_label,cash_line`)
- `--save PATH` (optional trend CSV)

Output:
- per-slate edge rows
- aggregate mean edges
- optional cash-rate metrics

### 4.12 select-normalized
Purpose:
- Select lineup using a normalized multi-term objective across candidate lineups.

Usage:
- `cash-optimizer select-normalized --threshold 130 --runs 2000`

Options:
- `--mean-weight FLOAT` (default 1.0)
- `--risk-weight FLOAT` (default 1.0)
- `--cov-weight FLOAT` (default 1.0)
- `--cash-prob-weight FLOAT` (default 0.0)
- `--threshold FLOAT` (optional; enables cash probability term)
- `--candidates INT` (default 25)
- `--runs INT` (default 2000)
- `--sampling-mode [independent|correlated]`
- `--projection-file PATH` (optional alternative projections)

Output:
- selected lineup
- candidate_count
- per-lineup metric table including normalized score

### 4.13 calibration-governance
Purpose:
- Run weekly calibration governance checks to decide whether candidate parameters should be promoted.

Usage:
- `cash-optimizer calibration-governance --baseline-input baseline.csv --candidate-input candidate.csv`

Options:
- `--baseline-input PATH` (required, CSV with `predicted_probability,observed_event`)
- `--candidate-input PATH` (required, CSV with `predicted_probability,observed_event`)
- `--required-brier-improvement FLOAT` (default 0.01)
- `--max-log-loss-increase FLOAT` (default 0.0)
- `--min-samples INT` (default 0)
- `--candidate-parameter-version TEXT` (optional)
- `--require-parameter-versioning/--allow-unversioned` (default require)

Output:
- accepted flag
- baseline and candidate calibration metrics
- brier and log-loss improvement deltas
- rejection reasons (if any)

### 4.14 optimize-profile
Purpose:
- Optimize using contest-type profile orchestration with optional floor/median blending and news-volatility adjustments.

Usage:
- `cash-optimizer optimize-profile --contest-profile h2h --runs 2000`

Options:
- `--contest-profile [h2h|double_up|small_field]` (default h2h)
- `--threshold FLOAT` (optional; cash threshold for cash-probability profile)
- `--candidates INT` (default 25)
- `--runs INT` (default 2000)
- `--sampling-mode [independent|correlated]`
- `--median-file PATH` (optional projection CSV)
- `--floor-file PATH` (optional projection CSV)
- `--news-signal-file PATH` (optional CSV with `player_id,signal`)

Output:
- selected lineup ids
- objective_profile
- profile metadata and score diagnostics

### 4.15 calibration-tune
Purpose:
- Fit recommended risk and correlation-penalty parameters per contest profile from historical calibration rows.

Usage:
- `cash-optimizer calibration-tune --input tuning.csv --min-samples 20`

Options:
- `--input PATH` (required)
- `--profile-col TEXT` (default `contest_profile`)
- `--lambda-col TEXT` (default `lambda_risk`)
- `--corr-penalty-col TEXT` (default `correlation_penalty_strength`)
- `--pred-col TEXT` (default `predicted_probability`)
- `--obs-col TEXT` (default `observed_event`)
- `--min-samples INT` (default 20)

Output:
- per-profile recommended lambda and correlation-penalty settings
- supporting calibration metrics and sample counts

### 4.16 benchmark
Purpose:
- Run baseline performance benchmarks and evaluate threshold guardrails for solve, sensitivity, and simulation runtime.

Usage:
- `cash-optimizer benchmark --simulation-runs 1000`

Options:
- `--simulation-runs INT` (default 1000)
- `--baseline-threshold-ms FLOAT` (default 1000)
- `--sensitivity-threshold-ms FLOAT` (default 10000)
- `--simulation-threshold-ms FLOAT` (default 10000)

Output:
- measured baseline/sensitivity/simulation runtimes
- simulation throughput (runs/sec)
- threshold pass/fail booleans

## 5. Input/Output Contracts

### 5.1 Slate Input
Default input uses existing loader:
- `load_players_from_dk_csv(path)`

### 5.2 Projection Override File
Optional CSV with columns:
- `player_id`
- `projection`

Rules:
- unknown player_id -> warning and ignore
- missing player -> fallback to base projection

### 5.3 JSON Output Mode
If `--json` is set:
- output strict JSON payload
- no ANSI formatting

## 6. Error Handling
- Input validation errors: exit code 2
- Infeasible solve: exit code 3
- Runtime/internal errors: exit code 1

User-facing behavior:
- concise human-readable error
- optional `--debug` stack trace mode

## 7. Logging and UX
- default concise logging
- optional `--verbose`
- optional rich tables and progress bars for simulation and sensitivity

## 8. Performance Requirements
- avoid reloading player CSV between chained commands in a single invocation
- reuse CashOptimizer instance where possible
- avoid storing all per-run simulation objects when export only needs aggregates

## 9. CLI Package Structure
- `src/cash_optimizer_cli/main.py` (click group and command wiring)
- `src/cash_optimizer_cli/context.py` (shared runtime context)
- `src/cash_optimizer_cli/formatters.py` (table/json formatters)
- `src/cash_optimizer_cli/exporters.py` (CSV/JSON artifact writers)
- `src/cash_optimizer_cli/validators.py` (input checks)

## 10. Testing Plan

### 10.1 Unit Tests
- command argument parsing
- context construction and solver settings mapping
- formatter output snapshots (json/plain)

### 10.2 Integration Tests
- run each command with sample `proj.csv`
- assert output artifacts are generated
- assert non-zero exit codes for invalid inputs

### 10.3 Performance Smoke
- benchmark `simulate --runs 1000` and `sensitivity`

## 11. Phased Implementation
1. Phase 1: `optimize`, `sensitivity`, `simulate`, `export`
2. Phase 2: `candidates`, `select-cash`, `stress`
3. Phase 3: `calibrate`, `compare-human`, robust CLI options
4. Phase 4: `evaluate-predictions`, `edge-trend`, richer analytics exports
5. Phase 5: `select-normalized`, `calibration-governance`, `optimize-profile`, `calibration-tune`, `benchmark`
