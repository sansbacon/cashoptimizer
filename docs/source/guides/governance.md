# Governance Automation

The cash-optimizer includes a layered governance system for safe production deployment of lineup optimization. This guide explains readiness gates, rollout recommendations, threshold calibration, and policy enforcement.

## Overview

Governance consists of three integrated layers:

1. **Readiness Gate** - Validate optimizer is ready (determinism, validity, coverage, benchmarks)
2. **Rollout Recommendation** - Recommend phased rollout stages (phase1-5)
3. **Policy Enforcement** - Apply organizational policy constraints (clean/minimum stage)

## Readiness Gate

The readiness gate performs comprehensive validation before rollout.

### What It Checks

**Determinism**
- Runs optimization twice and compares results
- Verifies results are reproducible (not random artifacts)
- Required for confident production use

**Validity**
- Confirms generated lineup adheres to DraftKings rules
- Checks roster composition (positions filled)
- Validates salary under cap

**Coverage**
- Verifies all players can potentially be selected
- Checks for blocking constraints or impossible scenarios
- Ensures no player is "stuck" in or out

**Performance Benchmarks**
- Baseline optimization time within threshold
- Sensitivity analysis time within threshold
- Simulation runtime within threshold

### Using Readiness Gate

**Python API:**

```python
from cash_optimizer.performance import run_readiness_gate

result = run_readiness_gate(
    optimizer=optimizer,
    players=players,
    baseline_threshold_ms=100,      # Baseline solve time limit
    sensitivity_threshold_ms=500,   # Sensitivity analysis time limit
    simulation_threshold_ms=10000,  # Simulation time limit
)

print(f"Accepted: {result.accepted}")
print(f"Deterministic: {result.deterministic_optimal}")
print(f"Valid lineup: {result.lineup_valid}")
print(f"Coverage complete: {result.sensitivity_coverage_complete}")
print(f"Benchmark: {result.benchmark}")

if result.accepted:
    print("✓ Ready for rollout")
else:
    print("✗ Issues found")
```

**CLI:**

```bash
cash-optimizer readiness-gate players.csv --verbose

# With custom thresholds
cash-optimizer readiness-gate players.csv \
  --profile custom \
  --baseline-ms 150 \
  --sensitivity-ms 600
```

### Benchmark Profiles

Predefined threshold profiles for common environments:

| Profile | Baseline | Sensitivity | Simulation |
|---------|----------|-------------|------------|
| **strict** | 50 ms | 300 ms | 5000 ms |
| **ci** | 100 ms | 500 ms | 10000 ms |
| **relaxed** | 200 ms | 1000 ms | 20000 ms |
| **custom** | User-specified | User-specified | User-specified |

Use `--profile` to select, or specify times directly with `--*-ms` flags.

## Rollout Recommendation

After readiness validation, get a phased recommendation for safe rollout.

### Rollout Stages

**Phase 1: Initial**
- Single test run with real users
- Monitors for critical failures
- Quick rollback if issues found

**Phase 2: Expanded**
- Expand to ~10% of user base
- Collect real-world performance data
- Monitor for edge cases

**Phase 3: Qualified**
- Expand to ~50% of user base
- Sufficient data for statistical confidence
- Threshold for major release

**Phase 4: Validation**
- Full rollout (100% of users)
- Complete replacement of previous version
- Standard production state

**Phase 5: Optimized**
- Optimization phase enabled
- Advanced features unlocked
- Full capability deployment

### Blockers and Notes

The recommendation includes:

- **Blockers** - Issues preventing advancement (must resolve)
- **Notes** - Warnings or observations (informational)

Example blockers:
- "Determinism check failed - results not reproducible"
- "Sensitivity analysis exceeds threshold (750 ms > 500 ms limit)"
- "Coverage incomplete - player X cannot be selected"

### Using Rollout Recommendation

**Python API:**

```python
from cash_optimizer.performance import recommend_rollout_stage

# After readiness check passes
rollout = recommend_rollout_stage(
    readiness_result=readiness_result
)

print(f"Recommended stage: {rollout.stage}")
# Output: phase1_initial, phase2_expanded, phase3_qualified, etc.

print(f"Can promote: {rollout.can_promote}")

for blocker in rollout.blockers:
    print(f"✗ Blocker: {blocker}")

for note in rollout.notes:
    print(f"• Note: {note}")
```

**CLI:**

```bash
cash-optimizer rollout-recommend players.csv

# With verbose details
cash-optimizer rollout-recommend players.csv --verbose
```

## Threshold Calibration

Auto-calibrate performance thresholds from historical benchmark data.

### Why Calibrate?

- Hardcoded thresholds become stale as hardware/data changes
- Data-driven thresholds adapt to your environment
- Percentile-based approach avoids outliers
- Safety multiplier provides cushion

### Calibration Process

1. Collect historical benchmark data (CSV file)
2. Compute percentile (e.g., 95th) of actual runtimes
3. Apply safety multiplier (e.g., 1.1x)
4. Use resulting thresholds

### Using Calibration

**Python API:**

```python
from cash_optimizer.performance import calibrate_benchmark_thresholds_from_history

calibration = calibrate_benchmark_thresholds_from_history(
    csv_file="benchmarks_history.csv",
    percentile=95,           # 95th percentile
    safety_multiplier=1.1,   # 10% safety margin
)

print(f"Baseline: {calibration.baseline_ms} ms")
print(f"Sensitivity: {calibration.sensitivity_ms} ms")
print(f"Simulation: {calibration.simulation_ms} ms")
print(f"Based on {calibration.sample_count} samples")
```

**CLI:**

```bash
cash-optimizer benchmark-calibrate benchmarks_history.csv \
  --percentile 90 \
  --safety-multiplier 1.2

# Save results
cash-optimizer benchmark-calibrate benchmarks_history.csv \
  --output-file calibrated_thresholds.json
```

### Historical Data Format

CSV file with columns:
- `baseline_ms` - Baseline optimization runtime
- `sensitivity_ms` - Sensitivity analysis runtime
- `simulation_ms` - Simulation runtime
- `num_players` - Number of players in slate
- `timestamp` - When measured

Example:

```
baseline_ms,sensitivity_ms,simulation_ms,num_players,timestamp
85.2,420.1,9200.3,150,2024-01-15T10:30:00Z
92.1,445.3,9850.5,150,2024-01-15T11:00:00Z
78.5,395.2,8950.1,150,2024-01-15T11:30:00Z
```

## Policy Enforcement

Apply organizational governance policies via JSON policy file.

### Policy File Structure

```json
{
  "simulation_runs": 200,
  "threshold_profile": "ci",
  "threshold_scale": 1.0,
  "require_clean": true,
  "minimum_stage": "phase4_validation"
}
```

**Fields:**
- `simulation_runs` - Min simulations required (int)
- `threshold_profile` - Profile: strict/ci/relaxed/custom (string)
- `threshold_scale` - Multiplier for thresholds (float, default 1.0)
- `require_clean` - Must pass all checks without issues (bool)
- `minimum_stage` - Minimum rollout stage required (string)

### Governance Check

Combines readiness + rollout + policy.

**Python API:**

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
    print("✓ Governance check passed - ready for production")
else:
    print("✗ Governance check failed")
    for reason in gov_result.reasons:
        print(f"  {reason}")

print(f"Readiness: {gov_result.readiness.accepted}")
print(f"Rollout stage: {gov_result.rollout.stage}")
```

**CLI:**

```bash
cash-optimizer governance-check players.csv \
  --policy-file specs/governance_policy.json \
  --verbose

# Exit code: 0 if passed, 1 if failed
if [ $? -eq 0 ]; then
    echo "Ready for deployment"
else
    echo "Blocked from deployment"
fi
```

### Policy Violations

Example violations:
- "Policy requires clean readiness, but {N} issues found"
- "Current stage {phase2} below required minimum {phase4_validation}"
- "Require simulations but none run yet"

## Complete Governance Workflow

Typical workflow combining all governance layers:

```python
from cash_optimizer import CashOptimizer
from cash_optimizer.io import load_players_from_dk_csv
from cash_optimizer.performance import (
    run_readiness_gate,
    recommend_rollout_stage,
    run_governance_check,
)

# 1. Load and prepare
players = load_players_from_dk_csv("players.csv")
optimizer = CashOptimizer(players)

# 2. Run readiness checks
print("Running readiness gate...")
readiness = run_readiness_gate(
    optimizer=optimizer,
    players=players,
    baseline_threshold_ms=100,
    sensitivity_threshold_ms=500,
    simulation_threshold_ms=10000,
)

if not readiness.accepted:
    print("✗ Readiness check failed")
    for reason in readiness.reasons:
        print(f"  - {reason}")
    exit(1)

print("✓ Readiness check passed")

# 3. Get rollout recommendation
rollout = recommend_rollout_stage(readiness)
print(f"Recommended stage: {rollout.stage}")

for blocker in rollout.blockers:
    print(f"⚠ {blocker}")

# 4. Run governance check (policy enforcement)
print("\nRunning governance check...")
gov = run_governance_check(
    optimizer=optimizer,
    players=players,
    policy_file="specs/governance_policy.json",
)

if gov.accepted:
    print("✓ Governance check passed")
    print(f"✓ Rollout stage: {gov.rollout.stage}")
    # Deploy to production
else:
    print("✗ Governance check failed")
    for reason in gov.reasons:
        print(f"  {reason}")
    exit(1)
```

## CLI Governance Workflow

```bash
#!/bin/bash

CSV="$1"
POLICY="${2:-specs/governance_policy.json}"

echo "=== Governance Workflow ==="

# 1. Readiness Gate
echo -e "\n1. Running readiness gate..."
if ! cash-optimizer readiness-gate "$CSV" --verbose; then
    echo "✗ Readiness failed"
    exit 1
fi
echo "✓ Readiness passed"

# 2. Rollout Recommendation
echo -e "\n2. Getting rollout recommendation..."
cash-optimizer rollout-recommend "$CSV"

# 3. Governance Check
echo -e "\n3. Running governance check..."
if cash-optimizer governance-check "$CSV" --policy-file "$POLICY"; then
    echo "✓ Governance passed - ready for production"
    exit 0
else
    echo "✗ Governance failed - blocked from production"
    exit 1
fi
```

## Monitoring & Alerting

Track governance status over time:

```bash
# Log governance status for each slate
for csv in slates/*.csv; do
    if cash-optimizer governance-check "$csv" \
       --policy-file policy.json \
       >> governance_log.txt 2>&1; then
        echo "✓ $csv" >> deployments.log
    else
        echo "✗ $csv" >> blockages.log
        # Send alert
        notify "Governance blocked: $csv"
    fi
done
```

## Best Practices

1. **Set Conservative Thresholds** - Use strict profile initially, relax based on data
2. **Calibrate Regularly** - Update thresholds quarterly with historical data
3. **Clean Deployments** - Require `require_clean: true` to eliminate surprises
4. **Phased Rollout** - Don't skip phases; follow phase1→2→3→4→5
5. **Monitor Production** - Collect real-world benchmarks for threshold updates
6. **Policy as Code** - Version control governance_policy.json with your code

## Troubleshooting

### Readiness Gate Fails: "Determinism Check Failed"

Solution: This is expected on first run - may have minor numerical differences. Run again or increase threshold slightly.

### Thresholds Too Strict

Solution: Calibrate from historical data or relax profile:
```bash
cash-optimizer readiness-gate players.csv --profile relaxed
```

### Policy Blocks Production Rollout

Solution: Review policy.json requirements and either:
- Fix the underlying issue (e.g., improve performance)
- Adjust policy to reflect actual requirements
- Document exception and update policy

## See Also

- [CLI Guide](cli.md) - All CLI commands
- [Python API](python-api.md) - Governance API functions
- [Getting Started](../getting-started.md) - Basic setup
