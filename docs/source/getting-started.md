# Getting Started

## Installation

### System Requirements
- Python 3.11+
- pip or conda

### Core Installation

Install in editable mode for development:

```bash
pip install -e .
```

This installs the library with required dependencies:
- `ortools>=9.10` - Constraint programming solver
- `numpy>=1.26` - Numerical computing
- `highspy>=1.8` - HiGHS solver fallback
- `click>=8.1` - CLI framework

### Optional GUI

To use the desktop GUI application (Qt):

```bash
pip install -e ".[gui]"
```

This adds `PySide6>=6.7` for the graphical interface.

### Development Setup

Install development dependencies:

```bash
pip install -e ".[dev]"
```

This adds:
- `pytest>=8.0` - Testing framework
- `pytest-qt>=4.4` - Qt testing utilities

## Your First Optimization

### 1. Prepare Player Data

Export a DraftKings contest to CSV format. The file should have columns:
- ID
- Name
- Pos (position: QB, RB, WR, TE, DEF)
- Salary
- GameInfo (optional)
- AvgPointsPerContest (or your projection column)

### 2. Run Optimization

```python
from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv

# Load players from DraftKings CSV export
players = load_players_from_dk_csv("path/to/players.csv")

# Create optimizer instance
optimizer = CashOptimizer(players)

# Solve for optimal lineup
result = optimizer.solve_optimal()

# Inspect results
print(f"Optimal Lineup:")
for player in result.lineup.players:
    print(f"  {player.name} ({player.position}) - ${player.salary}")
    
print(f"\nSalary Used: ${result.lineup.salary_used}")
print(f"Projected Points: {result.optimal_projection:.2f}")
```

### 3. Using the CLI

```bash
# Display available commands
cash-optimizer --help

# Optimize a CSV file
cash-optimizer optimize players.csv

# Show sensitivity analysis
cash-optimizer sensitivity players.csv

# Run simulation with 10,000 scenarios
cash-optimizer simulate players.csv --num-simulations 10000

# Export all results
cash-optimizer export players.csv --output-dir ./outputs
```

### 4. Using the GUI

Launch the desktop application:

```bash
cash-optimizer-gui
```

Or from Python:

```python
from cash_optimizer_gui.app import main
main()
```

The GUI provides:
- **Data Panel** - Shows loaded file info and player summary
- **Optimization** - One-click optimal lineup generation
- **Sensitivity** - Analyze player impact  
- **Simulation** - Run Monte Carlo scenarios
- **Results** - Tabular display with export

## Common Workflows

### Cash Lineup Evaluation

Find robust cash lineups using simulation:

```python
# Simulate 5,000 scenarios
sim_result = optimizer.run_simulation(
    num_simulations=5000,
    num_candidates=25
)

# Get best lineup by cash threshold probability
cash_lineup = optimizer.select_best_cash_lineup_by_probability(
    candidate_lineups=sim_result.candidate_lineups,
    threshold=130.0  # Cash line
)
print(cash_lineup)
```

### Stress Testing

Test lineup robustness across scenarios:

```python
stress_result = optimizer.run_stress_test()

print(f"Min Projection: {stress_result.min_projection:.2f}")
print(f"Max Projection: {stress_result.max_projection:.2f}")
print(f"Prob Below 130: {stress_result.prob_below_threshold:.2%}")
```

### Robust Optimization

Optimize for downside protection:

```python
from cash_optimizer import RobustSettings, build_error_covariance_from_errors

# Build covariance from historical projection errors
cov_matrix = build_error_covariance_from_errors(historical_errors)

# Solve with robustness
robust_settings = RobustSettings(
    uncertainty_set_factor=0.1,
    covariance_matrix=cov_matrix
)

result = optimizer.solve_robust(robust_settings)
```

## Troubleshooting

### Import Errors

If you get import errors, ensure you're in the correct Python environment:

```bash
# Check Python version
python --version  # Should be 3.11+

# Verify installation
pip show ortools
```

### Solver Errors

If OR-Tools CP-SAT fails, the library falls back to HiGHS:

```bash
# Install HiGHS if needed
pip install highspy>=1.8
```

### GUI Not Starting

Ensure you have the GUI dependencies:

```bash
pip install "PySide6>=6.7"
```

For PySide6 on Linux, you may need additional system packages:

```bash
sudo apt-get install libqt6gui6
```

## Next Steps

- [CLI Commands](guides/cli.md) - Learn all command-line options
- [GUI Features](guides/gui.md) - Explore the desktop interface  
- [Python API](guides/python-api.md) - Reference for all library functions
- [View Examples](https://github.com/EricTruett/cash_optimizer/tree/main/examples)
