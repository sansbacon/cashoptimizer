# Python API Reference

Complete reference for the cash-optimizer Python library.

## Core Optimizer

### CashOptimizer

Main optimization engine for DraftKings lineups.

```python
from cash_optimizer import CashOptimizer

optimizer = CashOptimizer(
    players,
    salary_cap=50000,
    min_players=8,
    position_limits=None,
    team_limits=None
)
```

**Parameters:**
- `players` - List of Player objects
- `salary_cap` - Maximum lineup salary (default: 50000)
- `min_players` - Minimum players required (default: 8)
- `position_limits` - Dict of position max counts (e.g., {'QB': 1, 'RB': 2})
- `team_limits` - Dict of team max concentrations

**Methods:**

#### solve_optimal()

Find the optimal lineup.

```python
result = optimizer.solve_optimal()

# Access results
print(result.lineup)  # Lineup object
print(result.optimal_projection)  # Float: projected points
print(result.lineups_generated)  # Int: number of lineups checked
print(result.solve_time_ms)  # Float: solver time in milliseconds
```

Returns: `OptimalResult` with fields:
- `lineup` - Optimal Lineup object
- `optimal_projection` - Projected points
- `lineups_generated` - Count of lineups evaluated  
- `solve_time_ms` - Solve time in milliseconds

#### run_sensitivity()

Analyze player impact (forced-in, forced-out deltas).

```python
sensitivity_result = optimizer.run_sensitivity()

# Access results
for player_sens in sensitivity_result.player_sensitivity:
    print(f"{player_sens.player_id}")
    print(f"  In optimal: {player_sens.in_optimal}")
    print(f"  Forced in delta: {player_sens.forced_in_delta}")
    print(f"  Forced out delta: {player_sens.forced_out_delta}")
    print(f"  Impact: {player_sens.impact}")
```

Returns: `SensitivityResult` with:
- `player_sensitivity` - List of PlayerSensitivity objects
- `solve_time_ms` - Total solve time

#### run_simulation()

Run high-volume Monte Carlo simulation.

```python
sim_result = optimizer.run_simulation(
    num_simulations=5000,
    num_candidates=25,
    seed=42
)

# Access results
print(sim_result.candidate_lineups)  # List of candidate Lineup objects
print(sim_result.simulation_stats)  # SimulationStats object
print(sim_result.simulation_time_ms)  # Time in ms
```

Returns: `SimulationResult` with:
- `candidate_lineups` - List of diverse lineups
- `simulation_stats` - Aggregate statistics
- `simulation_time_ms` - Simulation runtime

#### select_best_cash_lineup_by_probability()

From candidate lineups, select best for cash threshold.

```python
cash_lineup = optimizer.select_best_cash_lineup_by_probability(
    candidate_lineups=sim_result.candidate_lineups,
    threshold=130.0  # Cash line
)
```

Returns: Lineup object with highest win rate above threshold

#### generate_candidate_lineups()

Generate diverse candidate lineups for analysis.

```python
candidates = optimizer.generate_candidate_lineups(num_candidates=50)

# Each is a Lineup object
for lineup in candidates:
    print(lineup.salary_used, lineup.total_projection)
```

Returns: List of Lineup objects

#### run_stress_test()

Evaluate lineup robustness across stress scenarios.

```python
stress = optimizer.run_stress_test()

print(f"Min projection: {stress.min_projection}")
print(f"Max projection: {stress.max_projection}")
print(f"Prob below 130: {stress.prob_below_threshold}")
```

Returns: `StressTestResult` with fields:
- `min_projection` - Worst-case projection
- `max_projection` - Best-case projection
- `prob_below_threshold` - Downside risk probability

## Data Types

### Player

Represents a DraftKings player.

```python
player = Player(
    player_id="12345",
    name="Player Name",
    position="QB",
    salary=8000,
    projection=25.5,
    team="KC",
    opponent="GB"
)

# Attributes
player.player_id  # Unique identifier
player.name  # Player name
player.position  # Position: QB, RB, WR, TE, DEF
player.salary  # Salary in dollars
player.projection  # Projected points
player.team  # Team abbreviation
player.opponent  # Opponent abbreviation (for game context)
```

### Lineup

Represents a complete lineup (8-9 players).

```python
# Attributes
lineup.players  # List of Player objects
lineup.salary_used  # Total salary
lineup.total_projection  # Sum of projections
lineup.positions_filled  # Dict of positions and counts

# Methods
lineup.is_valid()  # Returns True if valid DK lineup
lineup.to_csv()  # Export to CSV string
```

### OptimalResult

```python
result.lineup  # Optimal Lineup object
result.optimal_projection  # Projected points (float)
result.lineups_generated  # Number evaluated (int)
result.solve_time_ms  # Solver time (float)
```

### SensitivityResult

```python
result.player_sensitivity  # List[PlayerSensitivity]
result.solve_time_ms  # Total time (float)
```

### PlayerSensitivity

```python
ps.player_id  # Player ID
ps.player_name  # Player name
ps.in_optimal  # Boolean: in optimal lineup
ps.forced_in_delta  # Point change if forced in
ps.forced_out_delta  # Point change if forced out  
ps.impact  # Overall impact score
```

### SimulationResult

```python
result.candidate_lineups  # List[Lineup]
result.simulation_stats  # SimulationStats
result.simulation_time_ms  # Time (float)
```

### SimulationStats

```python
stats.mean_projection  # Average projection
stats.std_projection  # Standard deviation
stats.percentile_10  # 10th percentile
stats.percentile_25  # 25th percentile
stats.percentile_50  # Median
stats.percentile_75  # 75th percentile
stats.percentile_90  # 90th percentile
stats.min_projection  # Minimum
stats.max_projection  # Maximum
```

## Utilities

### load_players_from_dk_csv()

Load players from DraftKings CSV export.

```python
from cash_optimizer.io import load_players_from_dk_csv

players = load_players_from_dk_csv("players.csv")

# Returns list of Player objects
for player in players:
    print(player.name, player.position, player.salary)
```

### compute_calibration_metrics()

Measure projection accuracy and calibration.

```python
from cash_optimizer import compute_calibration_metrics

metrics = compute_calibration_metrics(
    projections=projected_points,
    actuals=actual_points
)

print(f"MAE: {metrics.mae}")  # Mean absolute error
print(f"RMSE: {metrics.rmse}")  # Root mean squared error
print(f"Calibration: {metrics.calibration}")  # Calibration index
```

## Performance/Governance APIs

### Readiness Gate

Check if optimizer is ready for production.

```python
from cash_optimizer.performance import run_readiness_gate
from cash_optimizer.models import ReadinessGateResult

result: ReadinessGateResult = run_readiness_gate(
    optimizer=optimizer,
    players=players,
    num_baseline_runs=2,
    baseline_threshold_ms=100,
    sensitivity_threshold_ms=500,
    simulation_threshold_ms=10000,
)

if result.accepted:
    print("✓ Ready for rollout")
else:
    for reason in result.reasons:
        print(f"✗ {reason}")
```

### Rollout Recommendation

Get phased rollout recommendations.

```python
from cash_optimizer.performance import recommend_rollout_stage

rollout: RolloutRecommendation = recommend_rollout_stage(
    readiness_result=result
)

print(f"Stage: {rollout.stage}")
# phase1_initial, phase2_expanded, phase3_qualified, phase4_validation, phase5_optimized

for blocker in rollout.blockers:
    print(f"Blocker: {blocker}")

for note in rollout.notes:
    print(f"Note: {note}")
```

### Benchmark Calibration

Auto-calibrate thresholds from historical data.

```python
from cash_optimizer.performance import calibrate_benchmark_thresholds_from_history

calibration = calibrate_benchmark_thresholds_from_history(
    csv_file="historical_benchmarks.csv",
    percentile=95,
    safety_multiplier=1.1
)

print(f"Baseline threshold: {calibration.baseline_ms} ms")
print(f"Sensitivity threshold: {calibration.sensitivity_ms} ms")
print(f"Simulation threshold: {calibration.simulation_ms} ms")
```

### Governance Check

Comprehensive governance check combining readiness, rollout, and policy.

```python
from cash_optimizer.performance import run_governance_check

gov_result = run_governance_check(
    optimizer=optimizer,
    players=players,
    policy_file="specs/governance_policy.json",
    baseline_threshold_ms=100,
    sensitivity_threshold_ms=500,
    simulation_threshold_ms=10000,
)

if gov_result.accepted:
    print("✓ Governance check passed")
else:
    print("✗ Governance check failed")
    for reason in gov_result.reasons:
        print(f"  - {reason}")
```

## Robust Optimization

### RobustSettings

Configure robust optimization.

```python
from cash_optimizer import RobustSettings

settings = RobustSettings(
    uncertainty_set_factor=0.1,  # 10% uncertainty
    covariance_matrix=cov_matrix,  # Projection error covariance
    downside_protection_level=0.95  # 95% confidence
)
```

### solve_robust()

Solve with robustness.

```python
robust_result = optimizer.solve_robust(settings)

print(robust_result.lineup)
print(f"Robust projection: {robust_result.robust_projection}")
print(f"Downside protection: {robust_result.downside_bound}")
```

### build_error_covariance_from_errors()

Build covariance matrix from historical projection errors.

```python
from cash_optimizer import build_error_covariance_from_errors

cov = build_error_covariance_from_errors(
    errors=historical_errors,  # 2D array: (scenarios, players)
    regularization_strength=0.01
)
```

## Complete Example

```python
from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv
from cash_optimizer.performance import run_governance_check

# 1. Load players from DraftKings CSV
players = load_players_from_dk_csv("players.csv")

# 2. Create optimizer
optimizer = CashOptimizer(players, salary_cap=50000)

# 3. Get optimal lineup
optimal = optimizer.solve_optimal()
print(f"Optimal lineup: ${optimal.lineup.salary_used}")
print(f"Projected: {optimal.optimal_projection:.1f} pts")

# 4. Analyze sensitivity
sensitivity = optimizer.run_sensitivity()
for ps in sensitivity.player_sensitivity[:5]:
    if ps.in_optimal:
        print(f"{ps.player_name}: impact={ps.impact:.2f}")

# 5. Run simulation
simulation = optimizer.run_simulation(num_simulations=5000)
cash_lineup = optimizer.select_best_cash_lineup_by_probability(
    candidate_lineups=simulation.candidate_lineups,
    threshold=130.0
)

# 6. Governance check
gov = run_governance_check(
    optimizer=optimizer,
    players=players,
    policy_file="specs/governance_policy.json"
)

if gov.accepted:
    print("✓ Ready for production")
else:
    print("✗ Not ready")
    for reason in gov.reasons:
        print(f"  - {reason}")
```

## See Also

- [CLI Guide](cli.md) - Command-line interface
- [Governance Guide](governance.md) - Governance automation
- [Getting Started](../getting-started.md) - Setup and basics
