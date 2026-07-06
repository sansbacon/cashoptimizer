# CLI Guide

The `cash-optimizer` command-line interface provides powerful tools for DraftKings optimization without writing code.

## Installation

```bash
pip install -e .
```

Verify installation:

```bash
cash-optimizer --version
```

## Global Options

All commands accept these global options:

```bash
--help              Show command help and exit
--verbose           Enable detailed diagnostic output (stderr)
--rich              Use rich formatted tables for output (default: plain text)
```

## Commands

### optimize

Find the optimal lineup for a DraftKings contest.

```bash
cash-optimizer optimize <csv_file> [options]
```

**Options:**
- `--max-lineup-salary SALARY` - Cap salary (default: 50000)
- `--min-players-required NUM` - Minimum players in lineup (default: 8)
- `--output-file FILE` - Save result to CSV file

**Example:**

```bash
# Find optimal lineup
cash-optimizer optimize players.csv

# With custom salary cap
cash-optimizer optimize players.csv --max-lineup-salary 49500

# With verbose output
cash-optimizer optimize players.csv --verbose

# Save to file
cash-optimizer optimize players.csv --output-file optimal.csv
```

### sensitivity

Analyze how each player impacts the optimal lineup (forced-in and forced-out analysis).

```bash
cash-optimizer sensitivity <csv_file> [options]
```

**Options:**
- `--max-lineup-salary SALARY` - Salary cap (default: 50000)
- `--output-file FILE` - Save results to CSV

**Example:**

```bash
# Show sensitivity for all players
cash-optimizer sensitivity players.csv

# Export to CSV
cash-optimizer sensitivity players.csv --output-file sensitivity.csv
```

**Output Columns:**
- `Player` - Player name
- `Position` - Player position
- `Salary` - Player salary  
- `In_Optimal` - Is player in optimal lineup?
- `Forced_In_Delta` - Point change when forced into lineup
- `Forced_Out_Delta` - Point change when forced out of lineup
- `Impact` - Player's impact score

### simulate

Run high-volume Monte Carlo simulation over player projection distributions.

```bash
cash-optimizer simulate <csv_file> [options]
```

**Options:**
- `--num-simulations NUM` - Number of scenarios (default: 1000)
- `--num-candidates NUM` - Candidate lineups to generate (default: 25)
- `--seed SEED` - Random seed for reproducibility
- `--output-dir DIR` - Save all results to directory
- `--percentile PERCENT` - Return lineups at percentile threshold (1-99)

**Example:**

```bash
# Run 10,000 simulations
cash-optimizer simulate players.csv --num-simulations 10000

# Save all results
cash-optimizer simulate players.csv --num-simulations 5000 --output-dir ./sim_results

# Get 75th percentile lineups
cash-optimizer simulate players.csv --percentile 75
```

### export

Export optimization results in multiple formats.

```bash
cash-optimizer export <csv_file> [options]
```

**Options:**
- `--output-dir DIR` - Output directory (default: ./outputs)
- `--include-sensitivity` - Include sensitivity analysis
- `--include-simulation` - Include simulation results

**Example:**

```bash
# Export optimal and sensitivity
cash-optimizer export players.csv --include-sensitivity

# Export with simulation (takes longer)
cash-optimizer export players.csv --include-simulation --output-dir ./full_export
```

**Generated Files:**
- `optimal_lineup.csv` - Optimal lineup players and positions
- `sensitivity.csv` - Player sensitivity analysis
- `simulation_summary.csv` - Summary statistics from simulation
- `simulation_player_stats.csv` - Per-player simulation performance
- `simulation_lineup_stats.csv` - Lineup-level statistics

### benchmark

Measure and profile optimization performance.

```bash
cash-optimizer benchmark <csv_file> [options]
```

**Options:**
- `--num-runs NUM` - Number of runs to average (default: 5)
- `--profile PROFILE` - Profile preset: strict, ci, relaxed, custom (default: ci)
- `--scale SCALE` - Threshold scale multiplier (default: 1.0)
- `--baseline-ms MS` - Custom baseline threshold
- `--sensitivity-ms MS` - Custom sensitivity threshold
- `--simulation-ms MS` - Custom simulation threshold

**Example:**

```bash
# Benchmark with default CI profile
cash-optimizer benchmark players.csv

# Benchmark with relaxed thresholds
cash-optimizer benchmark players.csv --profile relaxed

# Custom thresholds
cash-optimizer benchmark players.csv --profile custom --baseline-ms 50 --sensitivity-ms 100
```

### readiness-gate

Check if the optimizer is ready for deployment.

Validates:
- Determinism (2x solve = identical results)
- Validity (valid roster and salary)
- Coverage (all players can be selected)
- Benchmarks (performance within thresholds)

```bash
cash-optimizer readiness-gate <csv_file> [options]
```

**Options:**
- `--profile PROFILE` - Threshold profile (default: ci)
- `--scale SCALE` - Threshold scale (default: 1.0)
- `--verbose` - Show detailed diagnostic output

**Exit Codes:**
- `0` - All checks passed, ready for rollout
- `1` - One or more checks failed, not ready

**Example:**

```bash
# Run readiness gate
cash-optimizer readiness-gate players.csv

# With verbose diagnostics
cash-optimizer readiness-gate players.csv --verbose

# Use strict profile
cash-optimizer readiness-gate players.csv --profile strict
```

### rollout-recommend

Get a phased recommendation for safe production rollout.

Returns staged recommendations:
- **phase1_initial** - Single test run
- **phase2_expanded** - Limited release (10% users)
- **phase3_qualified** - Wider rollout (50% users)
- **phase4_validation** - Full rollout (100% users)
- **phase5_optimized** - Production optimization

```bash
cash-optimizer rollout-recommend <csv_file> [options]
```

**Example:**

```bash
cash-optimizer rollout-recommend players.csv

# With verbose output
cash-optimizer rollout-recommend players.csv --verbose
```

### benchmark-calibrate

Auto-calibrate performance thresholds from historical CSV data.

Computes percentile-based thresholds with safety multiplier.

```bash
cash-optimizer benchmark-calibrate <history_csv> [options]
```

**Options:**
- `--percentile PERCENT` - Percentile for threshold (default: 95)
- `--safety-multiplier FACTOR` - Safety margin factor (default: 1.1)
- `--output-file FILE` - Save calibration results

**Example:**

```bash
# Calibrate from historical data
cash-optimizer benchmark-calibrate historical_benchmarks.csv

# Use 90th percentile with 1.2x safety
cash-optimizer benchmark-calibrate historical_benchmarks.csv --percentile 90 --safety-multiplier 1.2
```

### governance-check

Comprehensive governance check combining readiness + rollout + policy.

```bash
cash-optimizer governance-check <csv_file> [options]
```

**Options:**
- `--policy-file FILE` - Policy JSON file (default: specs/governance_policy.json)
- `--verbose` - Show detailed output

**Exit Codes:**
- `0` - Governance check passed
- `1` - Governance check failed (policy violation or readiness issues)

**Example:**

```bash
# Run governance check with default policy
cash-optimizer governance-check players.csv

# Use custom policy
cash-optimizer governance-check players.csv --policy-file custom_policy.json

# With detailed output
cash-optimizer governance-check players.csv --verbose
```

## Output Formatting

### Plain Text (Default)

```bash
cash-optimizer optimize players.csv
```

Output is human-readable but not tabular.

### Rich Tables

Enable rich formatted tables:

```bash
cash-optimizer optimize players.csv --rich
```

Produces nice ASCII tables with colors (if terminal supports it).

### Verbose Logging

Get detailed diagnostic output:

```bash
cash-optimizer optimize players.csv --verbose
```

Diagnostic messages appear on stderr with `[verbose]` prefix.

## Exit Codes

All commands follow Unix convention:

- `0` - Success
- `1` - Error or validation failure
- `2` - Invalid arguments

## Examples

### Simple Optimization

```bash
cash-optimizer optimize my_slate.csv
```

### Full Analysis

```bash
cash-optimizer export my_slate.csv \
  --include-sensitivity \
  --include-simulation \
  --output-dir ./analysis
```

### Governance Workflow

```bash
# 1. Check readiness
cash-optimizer readiness-gate my_slate.csv || exit 1

# 2. Get rollout recommendation  
cash-optimizer rollout-recommend my_slate.csv

# 3. Run governance check
cash-optimizer governance-check my_slate.csv --verbose
```

## Scripting

Since commands use Unix exit codes, you can use them in bash scripts:

```bash
#!/bin/bash

CSV_FILE="$1"
POLICY="${2:-specs/governance_policy.json}"

# Check governance
if cash-optimizer governance-check "$CSV_FILE" --policy-file "$POLICY"; then
    echo "✓ Governance check passed"
    cash-optimizer export "$CSV_FILE" --include-simulation
else
    echo "✗ Governance check failed"
    exit 1
fi
```

## Getting Help

```bash
# Show all commands
cash-optimizer --help

# Show specific command help
cash-optimizer optimize --help

# Enable verbose output for debugging
cash-optimizer optimize players.csv --verbose
```
