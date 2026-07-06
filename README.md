# cash-optimizer

Python library for DraftKings NFL cash lineup optimization using OR-Tools CP-SAT.

Includes:

- Exact optimal lineup solver under DraftKings NFL classic roster rules
- Exact player sensitivity deltas (forced-in and forced-out)
- High-volume simulation over sampled projection distributions
- Cash-oriented evaluation utilities (risk-adjusted and threshold metrics)

This package intentionally keeps runtime configuration in code for now.

## Quick Start

Install in editable mode:

pip install -e .

Run tests:

pytest -q

## Test With proj.csv

You can run the included example script against the local proj.csv file:

python examples/run_proj_csv.py

Or call the loader directly:

from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv

players = load_players_from_dk_csv("proj.csv")
optimizer = CashOptimizer(players)
result = optimizer.solve_optimal()
print(result.lineup.salary_used, result.optimal_projection)

## Export Simulation Outputs

Run the export example to generate CSV artifacts under outputs/:

python examples/export_simulation_outputs.py

Generated files:

- outputs/optimal_lineup.csv
- outputs/sensitivity.csv
- outputs/simulation_summary.csv
- outputs/simulation_player_stats.csv
- outputs/simulation_lineup_stats.csv

## Advanced APIs

The library also includes higher-level cash utilities:

- Candidate lineup generation:
	- optimizer.generate_candidate_lineups(num_candidates=25)
- Cash-threshold probability selection from sampled scenarios:
	- optimizer.select_best_cash_lineup_by_probability(threshold=130.0)
- Stress testing:
	- optimizer.run_stress_test()
- Projection blending and penalties:
	- optimizer.build_cash_blended_projections(...)
	- optimizer.apply_projection_penalties(...)
- Calibration metrics:
	- from cash_optimizer import compute_calibration_metrics

## Robust Cash Optimization

You can optimize for downside robustness using a covariance matrix of projection errors:

from cash_optimizer import (
	CashOptimizer,
	RobustSettings,
	RobustUncertaintySet,
	build_error_covariance_from_errors,
)

# errors shape: (historical_slates, active_players)
cov = build_error_covariance_from_errors(errors)

result = optimizer.solve_optimal(
	robust_settings=RobustSettings(
		enabled=True,
		rho=0.5,
		uncertainty_set=RobustUncertaintySet.BOX,  # or POLYGON
	),
	robust_covariance=cov,
)

Notes:

- Robust objective is: projection - rho * robust_penalty
- BOX uses L1-style penalty, POLYGON uses Linf-style penalty
- covariance shape must match active player count
- optional correlation sparsification threshold is supported to zero weak correlations before robust penalty construction

If you have historical projection errors keyed by player_id, you can build aligned covariance directly:

from cash_optimizer import build_error_covariance_aligned_by_player

cov = build_error_covariance_aligned_by_player(
	ordered_player_ids=[p.player_id for p in optimizer.players],
	error_history_by_player_id=error_history,
)

## CLI App

After installation, use the Click CLI entry point:

cash-optimizer --input-csv proj.csv optimize
cash-optimizer --input-csv proj.csv sensitivity --top 20
cash-optimizer --input-csv proj.csv simulate --runs 5000 --save-prefix simulation
cash-optimizer --input-csv proj.csv candidates --count 25
cash-optimizer --input-csv proj.csv select-cash --threshold 130 --runs 2000
cash-optimizer --input-csv proj.csv stress
cash-optimizer --input-csv proj.csv export --runs 1000

Projection override support:

cash-optimizer --input-csv proj.csv optimize --projection-file projection_overrides.csv

Where projection_overrides.csv can contain either:

- player_id,projection
- Player,Projection

Robust solve flags for optimize/sensitivity:

cash-optimizer --input-csv proj.csv optimize --robust-rho 0.35 --robust-set box --robust-cov-source robust_errors.csv
cash-optimizer --input-csv proj.csv sensitivity --robust-rho 0.35 --robust-set polygon --robust-cov-source robust_errors.csv
cash-optimizer --input-csv proj.csv optimize --robust-rho 0.35 --robust-corr-threshold 0.10 --robust-set box --robust-cov-source robust_errors.csv

Where robust_errors.csv contains player_id and one or more historical error columns, e.g.:

player_id,w1,w2,w3,w4
qb_bal_lamar_jackson,1.2,0.2,-0.4,0.5
wr_bal_zay_flowers,-0.6,0.1,0.2,-0.1

Paper3-inspired optimizer vs human baseline comparison:

cash-optimizer --input-csv proj.csv compare-human --trials 1000 --top-n-per-slot 10

This simulates a common human heuristic (top-N-by-slot filtered random lineup construction)
and reports optimizer edge over baseline best and mean outcomes.

Sensitivity responses now include a fragility summary with small-delta counts and alert status.

Position-wise prediction model evaluation:

cash-optimizer --input-csv proj.csv evaluate-predictions --input eval_rows.csv --model-col lr --model-col rf --model-col lstm

Expected eval_rows.csv columns:

- position
- actual
- one or more model prediction columns (specified with --model-col)

Weekly optimizer-edge trend across slates:

cash-optimizer --input-csv proj.csv edge-trend --slates-glob "data/slates/*.csv" --trials 1000 --top-n-per-slot 10 --save outputs/edge_trend.csv

Optional cash line file for rate calculations:

- columns: slate_label,cash_line

## GUI App

Install GUI dependency first:

pip install -e .[gui]

Launch:

cash-optimizer-gui

Current GUI supports:

- load DK CSV
- optimize, sensitivity, simulation, candidates, select cash, stress
- robust optimize/sensitivity controls (enable, rho, uncertainty set, robust error CSV)
- calibration metrics from CSV
- prediction-model evaluation (position-wise RMSE and best model selection)
- weekly edge-trend analysis across selected slate CSV files
- export artifacts to outputs/
- task cancellation
