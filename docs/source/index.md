# cash-optimizer

**DraftKings NFL Cash Lineup Optimization Library**

A Python library for finding optimal and robust DraftKings NFL cash lineups using integer linear programming and Monte Carlo simulation. Built with OR-Tools CP-SAT solver for guaranteed optimal solutions.

## Key Features

- **Exact Optimal Solver**: Find guaranteed optimal lineups under DraftKings roster rules
- **Sensitivity Analysis**: Analyze player impact on optimal lineup composition
- **High-Volume Simulation**: Evaluate linups across sampled projection distributions  
- **Cash Metrics**: Risk-adjusted evaluation and threshold-based selection
- **Robust Optimization**: Downside robustness using covariance matrices
- **Governance Automation**: Readiness gates, rollout recommendations, threshold calibration
- **CLI & GUI**: Command-line tools and Qt desktop application

## Quick Install

```bash
pip install -e .
```

## Run Tests

```bash
pytest -q
```

## Example

```python
from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv

# Load DraftKings CSV export
players = load_players_from_dk_csv("players.csv")

# Create optimizer
optimizer = CashOptimizer(players)

# Get optimal lineup
result = optimizer.solve_optimal()
print(result.lineup)
print(f"Salary: {result.lineup.salary_used}")
print(f"Projection: {result.optimal_projection}")
```

## What You Can Do

### Optimize
Find the optimal lineup given player projections and DraftKings rules.

### Simulate  
Evaluate lineups across thousands of scenarios with sampled projections.

### Analyze
Measure player sensitivity (forced-in/forced-out impact) and calibration metrics.

### Govern
Validate readiness (determinism, validity, coverage), recommend rollout stages, and enforce policies.

## Next Steps

- [Getting Started](getting-started.md) - Setup and basic usage
- [CLI Guide](guides/cli.md) - Command-line interface
- [GUI Guide](guides/gui.md) - Desktop application
- [Python API](guides/python-api.md) - Library functions
- [Governance](guides/governance.md) - Automation and policies

---

**Version**: 0.1.0 | **License**: MIT | [GitHub](https://github.com/EricTruett/cash_optimizer)
