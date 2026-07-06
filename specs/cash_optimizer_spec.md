# DraftKings NFL Cash Optimizer - Technical Specification

## 1. Purpose
Build a high-performance optimizer for DraftKings NFL Classic cash lineups that can:

1. Return the optimal lineup under current projections.
2. Return, for every player, the exact projection change needed to get into the optimal lineup or to fall out of it.
3. Support repeated reruns with slightly changed projections at very high speed.

## 2. Scope
In scope:

- NFL DraftKings Classic roster construction.
- Single-lineup optimization for cash contests.
- Exact player sensitivity values (enter/exit thresholds).
- Performance-focused design for repeated objective updates.
- High-volume simulation using sampled projections from player outcome distributions.

Out of scope (initial version):

- GPP portfolio generation.
- Multi-lineup portfolio optimization.
- Ownership/leverage optimization.
- Late-swap optimizer.

## 3. Business Requirements

### 3.1 Functional
1. Load a slate player pool with salary, position, team, game, and projection.
2. Produce the exact optimal lineup for given projections.
3. For each player not in the optimal lineup, compute projection increase needed to become optimal.
4. For each player in the optimal lineup, compute projection decrease needed to no longer be optimal.
5. Return full audit information: objective values, ties, and lineup details.
6. Run many optimizer solves from sampled player projections and return lineup/player stability statistics.
7. Keep all optimization decisions scoped to a single lineup entry for cash contests.

### 3.2 Non-Functional
1. Baseline optimization should be sub-second for typical NFL slates.
2. Sensitivity for all players should complete quickly enough for frequent reruns.
3. Re-optimization with small projection changes should be significantly faster than cold-start solve.
4. Deterministic and reproducible results for the same input.
5. Distribution simulation must support at least 1000 to 10000 runs per slate with reproducible random seed control.
6. Risk controls must prioritize downside robustness over upside-seeking variance behavior.

## 4. DraftKings NFL Classic Rules
Model assumptions for the initial solver:

- Salary cap: 50000.
- Roster size: 9 players.
- Position slots:
  - 1 QB
  - 2 RB
  - 3 WR
  - 1 TE
  - 1 FLEX (RB/WR/TE)
  - 1 DST

Optional configurable constraints (default off):

- Max players from one NFL team.
- No offensive player against chosen DST.
- Team/game exposure limits.

## 5. Mathematical Formulation
Let player index be i in P.

Variables:

- x_i in {0,1}: 1 if player i is selected.

Parameters:

- p_i: projected fantasy points.
- s_i: salary.
- pos_i: player position.

Objective:

- Maximize sum(p_i * x_i)

Constraints:

1. Salary cap: sum(s_i * x_i) <= 50000
2. Roster count: sum(x_i) = 9
3. Position constraints:
   - QB count = 1
   - RB count in lineup = 2 + RB used at FLEX
   - WR count in lineup = 3 + WR used at FLEX
   - TE count in lineup = 1 + TE used at FLEX
   - DST count = 1
4. FLEX eligibility: exactly one of RB/WR/TE above minimum slot counts is selected.

Implementation note:
Use a clean linear formulation with slot-based binary variables or aggregate position constraints that enforce equivalent roster legality.

## 6. Exact Sensitivity Definitions
Let O_star be the objective value of the unconstrained optimal lineup.

For each player j:

- Forced-in objective O_in_j: best objective with x_j = 1.
- Forced-out objective O_out_j: best objective with x_j = 0.

### 6.1 Player Not in Optimal Lineup
Projection increase required to become optimal:

- delta_enter_j = O_star - O_in_j

Interpretation:

- delta_enter_j > 0: player needs this many projection points added.
- delta_enter_j = 0: player can already appear in a tied optimal lineup.

### 6.2 Player In Optimal Lineup
Projection decrease required to be removed from optimal:

- delta_exit_j = O_star - O_out_j

Interpretation:

- delta_exit_j > 0: player can lose this many points before no longer being optimal.
- delta_exit_j = 0: there is already a tied optimal lineup without this player.

### 6.3 Why This Is Exact
These values come from constrained re-solves, not local heuristics, so they account for salary, positional interactions, and all lineup combinatorics.

## 7. Performance Architecture

### 7.1 Core Design
1. Build model structure once per slate.
2. Update only objective coefficients when projections change.
3. Reuse solver process and data structures across reruns.
4. Perform sensitivity solves as incremental model modifications (temporary x_j = 1 or x_j = 0).

### 7.2 Solver Choice
Primary: OR-Tools CP-SAT.
Fallback: HiGHS MIP (secondary open-source option).

### 7.2.1 OR-Tools CP-SAT Runtime Configuration
Recommended default solver parameters for this workload:

- num_search_workers = physical CPU cores (or cores minus 1 on shared machines)
- max_time_in_seconds = small bounded value for production (for example, 0.2 to 2.0 depending on SLA)
- relative_gap_limit = 0.0 for exact cash solves
- random_seed = fixed constant for reproducibility
- log_search_progress = false in production

Implementation notes:

- CP-SAT does not provide the same incremental warm-start behavior as commercial MIP re-optimization workflows, so performance should come from fast solves, parallelism, cache reuse, and stable worker processes.
- Use additive objective scaling if needed (for example, integerize projections by multiplying by 1000) to preserve precision and avoid float ambiguity.
- Keep model construction deterministic so repeated runs are reproducible.

### 7.3 Parallelization
- Run per-player forced solves in worker processes using model copies.
- Keep one baseline solve in the main process.
- Merge results into a single sensitivity table.

### 7.4 Caching
- Key cache by slate id, enabled player set, and projection hash.
- Cache baseline optimum and per-player forced objectives.
- Invalidate only changed players when projections are updated incrementally.
- Use two cache tiers:
   - in-memory LRU for current session
   - optional disk cache for repeated batch jobs

### 7.5 Player Pool Pruning (Safe Rules)
- Remove inactive/out players.
- Remove position-ineligible rows.
- Optional conservative dominance pruning by salary/projection within position group.

### 7.6 CP-SAT Execution Pattern
1. Build baseline model and solve for O_star.
2. For sensitivity, dispatch forced-in and forced-out solves in a process pool.
3. In each worker, rebuild from compact preprocessed arrays (avoid heavy object serialization).
4. Return only objective value and selected player ids to minimize IPC overhead.
5. Aggregate into delta_enter and delta_exit table.

### 7.7 Distribution Simulation Architecture
1. Generate sampled projection vectors from configured player distributions.
2. Run solve_optimal for each sampled vector in a persistent process pool.
3. Aggregate lineup frequency and player exposure statistics online to avoid storing full run artifacts.
4. Optionally persist sampled seeds and top lineups for auditability.

Sampling modes:

- Independent mode: each player sampled independently from configured distribution.
- Correlated mode: add shared game-level and team-level latent factors before clipping floors.

Performance notes:

- Pre-generate random tensors in batches to reduce per-run overhead.
- Use chunked dispatch to workers (for example, batches of 64 to 512 simulation runs).
- Keep worker-local immutable slate arrays to minimize serialization and memory churn.

## 8. Data Model

### 8.1 Input Player Schema
Required fields:

- player_id (string)
- name (string)
- team (string)
- opponent (string)
- position (enum: QB, RB, WR, TE, DST)
- salary (int)
- projection (float)
- status (enum: active, questionable, out, etc.)

Optional fields:

- game_total, spread, ownership, floor, ceiling
- std_dev (float)
- distribution_type (enum: normal, lognormal, student_t, empirical)
- distribution_params (json/object)
- game_id (string)
- correlation_group (string)

### 8.2 Output Schema

- optimal_lineup: list of 9 player_ids with slot mapping
- optimal_projection: float
- total_salary: int
- sensitivity: array of:
  - player_id
  - in_optimal (bool)
  - forced_in_objective (float or null)
  - forced_out_objective (float or null)
  - delta_enter (float or null)
  - delta_exit (float or null)
  - tie_flag (bool)

- simulation_summary:
   - num_runs (int)
   - random_seed (int)
   - mean_optimal_projection (float)
   - p05_optimal_projection (float)
   - p50_optimal_projection (float)
   - p95_optimal_projection (float)
   - unique_lineups (int)

- simulation_player_stats: array of:
   - player_id
   - inclusion_rate (float)
   - mean_lineup_projection_when_included (float)
   - leverage_to_baseline (float)

- simulation_lineup_stats: array of top K lineups:
   - lineup_key (string)
   - frequency (int)
   - frequency_rate (float)
   - mean_projection (float)

## 9. API Surface

### 9.1 Optimizer Service
- solve_optimal(projections) -> OptimalResult
- solve_forced_in(player_id) -> float objective
- solve_forced_out(player_id) -> float objective
- solve_sensitivity_all(projections) -> SensitivityResult
- run_projection_distribution_simulation(config) -> SimulationResult

### 9.2 Batch Runner
- run_many_projection_sets(list_of_projection_vectors) -> list of results
- run_many_sampled_sets(sample_generator, num_runs) -> aggregated simulation stats

Requirements:

- Reuse instantiated model where constraints are unchanged.
- Minimize memory churn and object reconstruction.
- Reuse worker processes across batches to avoid startup cost.
- Guarantee reproducible simulation results for the same seed and software version.

### 9.3 Simulation Config
Required:

- num_runs (int)
- random_seed (int)

Optional:

- sampling_mode (enum: independent, correlated)
- clip_min_projection (float, default 0)
- clip_max_projection (float or null)
- top_k_lineups_to_track (int, default 50)
- worker_count (int)
- chunk_size (int)

## 10. Tie Handling
If multiple lineups share objective O_star:

1. Mark tie_flag for players where delta_enter or delta_exit equals zero.
2. Keep deterministic lineup selection via stable tie-breaker:
   - lower salary left over first, then lexical player_id order.
3. Preserve all objective-equivalent diagnostics.

## 11. Benchmark Plan

### 11.1 Scenarios
1. Cold start solve on full slate.
2. Fast re-solve after small projection perturbation (same constraints).
3. Full per-player sensitivity run.
4. Repeated batch over N projection vectors.
5. Full distribution simulation with 1000, 5000, and 10000 runs.

### 11.2 Metrics
- Baseline solve time (ms)
- Mean and p95 forced solve time (ms)
- Full sensitivity wall clock (ms)
- Memory usage
- Cache hit rate
- Simulation throughput (runs per second)
- p95 simulation worker latency per run (ms)
- Aggregation overhead (ms)

### 11.3 Target Thresholds (Initial)
- Baseline optimal: < 1000 ms
- Fast optimal re-solve: < 400 ms
- Full sensitivity on standard slate: < 10000 ms (single machine target)
- Simulation throughput target: >= 200 runs/second on a modern multi-core desktop for standard slate size

## 12. Testing Strategy

### 12.1 Correctness
1. Unit tests for each lineup legality rule.
2. Brute-force comparison tests on tiny synthetic slates.
3. Sensitivity identity checks:
   - For excluded player j: O_in_j + delta_enter_j equals O_star
   - For included player j: O_out_j + delta_exit_j equals O_star

### 12.2 Regression
- Golden-file tests on historical slates.
- Stability tests for deterministic tie-breaking.

### 12.3 Performance Tests
- Timed benchmark suite with fixed seeds.
- Fails build if p95 latency regresses above threshold.
- Include scalability sweep by player-pool size and worker count.

### 12.4 Simulation Validity Tests
1. Seed reproducibility test: identical outputs for identical seed/config/version.
2. Distribution fidelity test: sampled mean and variance match configured parameters within tolerance.
3. Correlation sanity test: correlated mode produces expected sign and magnitude in grouped players.
4. Stability test: inclusion rates converge as num_runs increases.

## 13. Implementation Plan

Phase 1: Core exact optimizer
1. Build player ingest and validation.
2. Implement DK legality constraints.
3. Implement baseline optimal solve.

Phase 2: Exact sensitivity engine
1. Add forced-in and forced-out solves.
2. Produce delta_enter and delta_exit for all players.
3. Add tie diagnostics.

Phase 3: Performance layer
1. Persistent model lifecycle.
2. Incremental objective updates and process reuse.
3. Parallel sensitivity worker pool.
4. Caching and profiling.

Phase 4: Productization
1. CLI or service endpoint.
2. Structured result export.
3. Monitoring and benchmark dashboard.

Phase 5: Distribution simulation
1. Add player-level distribution inputs and validation.
2. Implement sampled projection generator (independent mode first, correlated mode second).
3. Implement high-throughput parallel simulation runner.
4. Add online aggregation for player inclusion and lineup frequency stats.
5. Add reproducibility and distribution-fidelity tests.

## 14. Risks And Mitigations
1. Risk: Sensitivity runtime too high on large pools.
   - Mitigation: process-level parallelism, caching, pruning, solver parameter tuning.
2. Risk: Ambiguity from tied optimals.
   - Mitigation: explicit tie flags and deterministic tie-breakers.
3. Risk: Model drift from changing site rules.
   - Mitigation: versioned rule config and validation tests.
4. Risk: Unrealistic projection sampling assumptions.
   - Mitigation: support multiple distribution families and calibration backtesting.
5. Risk: Simulation run-time explosion at high run counts.
   - Mitigation: chunked multiprocessing, online aggregation, and optional adaptive stop criteria.

## 15. Definition Of Done
1. Optimizer returns valid DK cash lineup and objective.
2. Sensitivity output is available for all players with exact deltas.
3. Repeated reruns with minor projection changes demonstrate strong cache and process-reuse speedup.
4. Test suite covers legality, correctness, tie behavior, and performance guardrails.
5. Distribution simulation returns reproducible player and lineup stability stats at target throughput.

## 16. OR-Tools Dependency And Environment
Python dependency:

- ortools >= 9.10

Recommended runtime environment:

- Python 3.11+
- Dedicated CPU cores for worker pool
- Optional pinned affinity for stable benchmark results

Validation command:

- python -c "from ortools.sat.python import cp_model; print('ortools ok')"

## 17. Advanced Cash Lineup Selection Enhancements
This section defines optional but recommended features that improve cash lineup quality beyond pure mean-projection maximization.

Important scope note:

- All features in this section are for selecting one lineup only.
- Portfolio objectives (lineup diversification across many entries) are explicitly out of scope for this project.

### 17.1 Cash-Probability Objective
Primary idea:

- Maximize probability that lineup score exceeds a contest-specific cash threshold.

Definition:

- Let L be a lineup and T_cash be contest cash line estimate.
- Optimize max P(S(L) >= T_cash), where S(L) is simulated lineup score.

Implementation options:

1. Two-stage approach:
   - Stage A: generate top M candidate legal lineups by deterministic optimizer.
   - Stage B: evaluate candidates with Monte Carlo simulation and choose lineup with highest estimated cash probability.
2. Scenario MILP approximation:
   - Pre-sample K projection scenarios.
   - Maximize fraction of scenarios where lineup score exceeds T_cash.

### 17.2 Risk-Adjusted Objective For Cash
When direct threshold optimization is not used, rank lineups by risk-adjusted utility:

- Utility(L) = mu(L) - lambda * sigma(L)

Where:

- mu(L): expected lineup score
- sigma(L): lineup score standard deviation from simulation
- lambda: risk-aversion coefficient (cash-specific, tuned by backtest)

Alternative robust objective:

- Maximize p20(L), the 20th percentile simulated lineup score.

Exact robust formulation option:

- Maximize: p^T x - rho * ||Sigma_e^(1/2) x||_q
- q = 1 (box) for summed absolute penalty
- q = infinity (polygon) for max absolute component penalty

Implementation requirements:

- expose rho as a first-class profile parameter
- support both box and polygon uncertainty sets
- require covariance alignment with active-player ordering
- disable robust penalty when rho = 0

### 17.3 Floor-Weighted Projection Blending
Create a cash blend projection for each player:

- cash_projection_i = w_med * median_i + w_floor * floor_i

Suggested defaults:

- w_med = 0.7
- w_floor = 0.3

Calibrate weights by historical cash hit-rate backtesting.

### 17.4 Volatility And Role-Uncertainty Penalties
Apply penalty terms for fragile players:

- questionable injury status
- uncertain snap share
- uncertain touch/target volume
- unstable role changes

Example adjusted projection:

- adj_projection_i = base_projection_i - penalty_i

Penalty should be parameterized and versioned for auditability.

### 17.5 Correlation-Aware Downside Control
Introduce optional downside controls to avoid fragile lineup structures:

- cap number of players from single game environments when volatility is high
- penalize known negative-correlation pairs
- cap overconcentration in one offensive environment

Correlated-mode simulation should validate whether constraints reduce left-tail risk.

Covariance pipeline requirements:

- estimate projection-error covariance from historical projection misses (not raw points)
- allow pairwise estimation with missing values
- apply PSD repair before square-root operations (nearest-PSD / nearest-correlation workflow)
- preserve diagonal variances during repair when feasible

### 17.6 News-Volatility Layer
Add late-news uncertainty adjustments:

- apply temporary uncertainty multipliers to players affected by unresolved injury/depth-chart situations
- increase variance and/or reduce adjusted mean for high-news-risk players
- allow final-hour re-optimization with stricter uncertainty penalties

### 17.7 Projection Ensemble And Shrinkage
Use multiple projection sources and shrink extremes:

1. Source blending:
   - blend median projection across providers
2. Outlier control:
   - shrink extreme deviations toward ensemble mean
3. Stability preference:
   - prioritize players with lower inter-source disagreement for close decisions

### 17.8 Contest-Type Objective Profiles
Support objective presets by contest type:

- H2H profile: stronger risk aversion and floor weighting
- Double-up/50-50 profile: maximize cash probability vs threshold
- Small-field multiplier profile: moderate risk aversion

Each profile must define:

- objective type
- lambda value (if applicable)
- floor/median blend weights
- correlation caps and risk penalties

### 17.9 Sensitivity-Guided Lineup Robustness Review
Use existing delta_enter and delta_exit outputs to detect fragile lineups:

- low delta_exit among selected players indicates high fragility
- low delta_enter among excluded players indicates near-equivalent alternatives

Add a lineup fragility score based on aggregate small-delta counts.

### 17.10 Stress-Test Regimes
Run deterministic stress scenarios before final lineup lock:

1. Position-wide downshift (for example, all WR means minus x percent)
2. Game-environment underperformance scenarios
3. Chalk failure scenario for top-owned value plays

Select lineups that remain competitive across stress regimes.

### 17.11 Backtesting And Calibration Loop
Weekly calibration workflow:

1. Compare predicted distribution metrics vs realized outcomes.
2. Refit variance and correlation parameters.
3. Re-tune lambda and blend weights by contest type.
4. Track calibration drift and version model settings.

Required metrics:

- predicted vs realized lineup percentile accuracy
- predicted cash probability vs actual cash outcome rate
- Brier/log-loss for threshold cash events

### 17.12 Rollout Plan For Advanced Cash Features
Phase A (low complexity, high value):

1. Floor-weighted projection blend
2. Risk-adjusted lineup ranking
3. Sensitivity-based fragility score

Phase B (medium complexity):

1. Projection ensemble and outlier shrinkage
2. News-volatility penalty layer
3. Stress-test scenario runner

Phase C (higher complexity):

1. Cash-threshold probability objective
2. Correlation-aware downside controls
3. Full backtesting auto-calibration pipeline

## 18. Default Parameter Table (Initial Values)
These defaults are starting points for implementation. They should be calibrated with historical backtests and adjusted by contest type.

### 18.1 Core Optimization Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| objective_mode | mean_projection | Baseline deterministic objective |
| projection_scale_factor | 1000 | Integerize objective for CP-SAT precision |
| cp_sat_num_search_workers | physical_cores_minus_1 | Use all physical cores on dedicated host |
| cp_sat_max_time_seconds | 0.5 | Increase to 1.0 to 2.0 for larger slates |
| cp_sat_relative_gap_limit | 0.0 | Exact cash solves |
| cp_sat_random_seed | 1729 | Reproducibility |

### 18.2 Cash-Risk Objective Defaults

| Parameter | H2H | Double-Up/50-50 | Small-Field Multiplier | Notes |
| --- | --- | --- | --- | --- |
| objective_profile | risk_adjusted | cash_probability | risk_adjusted | Profile selector |
| lambda_risk | 0.30 | 0.20 | 0.15 | Used for mu - lambda * sigma |
| floor_weight_w_floor | 0.35 | 0.30 | 0.20 | Floor component weight |
| median_weight_w_med | 0.65 | 0.70 | 0.80 | Median component weight |
| target_percentile | p25 | p20 | p15 | If percentile objective is enabled |

### 18.3 Cash Threshold Estimation Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| threshold_model | historical_quantile_by_contest | Contest-specific historical estimate |
| threshold_quantile_h2h | 0.50 | H2H break-even proxy |
| threshold_quantile_double_up | 0.44 | Approximate cash line percentile |
| threshold_quantile_small_field | 0.40 | Tune with actual contest history |
| minimum_history_slates | 20 | Fallback to blended global estimate below this |

### 18.4 Simulation Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| simulation_num_runs_default | 5000 | Standard production run count |
| simulation_num_runs_fast | 1000 | Quick interactive analysis |
| simulation_num_runs_deep | 10000 | Deeper pre-lock analysis |
| simulation_sampling_mode | independent | Start simple; enable correlated after calibration |
| simulation_clip_min_projection | 0.0 | No negative fantasy projections |
| simulation_top_k_lineups | 50 | Track most frequent lineups |
| simulation_chunk_size | 128 | Per-worker task batching |
| simulation_worker_count | physical_cores_minus_1 | Tune for throughput |
| simulation_seed | 20260901 | Logged with each run for reproducibility |

### 18.5 Distribution Defaults By Position

| Position | Distribution | Std Dev Multiplier | Min Clip | Notes |
| --- | --- | --- | --- | --- |
| QB | normal | 0.18 * projection | 0 | Stable role, moderate variance |
| RB | normal | 0.25 * projection | 0 | Workload risk |
| WR | student_t_df_6 | 0.32 * projection | 0 | Higher tail volatility |
| TE | student_t_df_6 | 0.30 * projection | 0 | Volatile target share |
| DST | normal | 0.40 * projection | 0 | High outcome variance |

Implementation note:

- Use empirical distributions when enough historical samples are available per player-role archetype.

### 18.6 News And Uncertainty Penalty Defaults

| Signal | Mean Penalty | Variance Multiplier | Notes |
| --- | --- | --- | --- |
| healthy_confirmed_role | 0.00 | 1.00 | No adjustment |
| questionable_tag | 0.75 | 1.20 | Increase uncertainty |
| game_time_decision | 1.25 | 1.35 | Strong downside caution |
| role_change_risk | 0.60 | 1.25 | Depth-chart uncertainty |
| weather_elevated_risk | 0.40 | 1.15 | Adjust by severity |

All penalties are fantasy points on projected mean before optimization.

### 18.7 Correlation Control Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| max_players_per_game_environment | 4 | Prevent overconcentration |
| max_non_qb_skill_players_same_team | 3 | Cash downside control |
| enable_negative_pair_penalty | true | Penalize known negative-correlation pairings |
| qb_dst_opposition_penalty | enabled | Avoid direct QB vs opposing DST if close calls |
| penalty_strength | 0.20 | Applied as projection-equivalent penalty points |

### 18.8 Sensitivity Fragility Score Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| fragility_exit_delta_threshold | 0.75 | Player considered fragile if delta_exit <= threshold |
| fragility_enter_delta_threshold | 0.75 | Near-miss alternative threshold |
| fragility_score_formula | weighted_count_small_deltas | Implementation-defined deterministic function |
| fragility_alert_threshold | 3 | Alert when score exceeds threshold |

### 18.9 Stress-Test Scenario Defaults

| Scenario | Default Shock | Notes |
| --- | --- | --- |
| all_wr_downshift | -10 percent mean | Tests pass-catching downside |
| all_rb_efficiency_downshift | -8 percent mean | Tests run-game underperformance |
| top_chalk_value_fail | -25 percent mean for top owned value tier | Tests chalk bust resilience |
| primary_game_environment_fail | -12 percent mean for game stack group | Tests concentration risk |
| adverse_weather_band | +20 percent variance for affected games | Volatility stress |

### 18.10 Calibration And Governance Defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| recalibration_frequency | weekly | After each main slate |
| rolling_backtest_window_slates | 26 | Roughly half-season window |
| min_runs_for_calibration_eval | 1000 | Per slate simulation minimum |
| required_brier_improvement | 0.01 | Minimum gain to accept model change |
| parameter_versioning | required | Log all production parameters with run id |

### 18.11 Initial Implementation Priority Using Defaults
1. Start with Sections 18.1, 18.2, and 18.4 for immediate deployability.
2. Add 18.6 and 18.9 next for better downside control.
3. Add 18.7 only after baseline and simulation calibration are stable.

## 19. Single-Lineup Enhancements From Generative-Model Literature
This section captures paper-inspired ideas that apply to cash contests with one lineup entry.

### 19.1 Single-Lineup-Only Policy
1. Do not optimize a portfolio of lineups.
2. Do not include lineup-overlap terms in any objective.
3. Keep optimization target as one final lineup submission.

### 19.2 Covariance-Aware Downside Objective
Use covariance from simulation scenarios to penalize fragile single-lineup constructions.

Recommended forms:

- Utility(L) = mu(L) - lambda_sigma * sigma(L) - lambda_cov * downside_cov_penalty(L)
- Alternative robust form: maximize percentile floor p20(L)

Where:

- mu(L): expected lineup score
- sigma(L): lineup score standard deviation
- downside_cov_penalty(L): positive scalar penalizing harmful co-movements inside one lineup

Cash-specific guidance:

- covariance terms should reduce downside concentration, not promote high variance.

### 19.3 Normalized Objective Composition
Before combining objective terms, normalize each term to a comparable range.

Recommended normalization:

- term_norm = (term - term_min) / max(term_max - term_min, epsilon)

Then combine with weights:

- objective = w_mean * mean_norm - w_risk * risk_norm - w_cov * cov_norm

Rationale:

- prevents one term from dominating due to scale differences
- improves weight transfer across slates

### 19.4 Cash-Threshold Probability As Primary Target
For contests where threshold estimates are available, primary objective should be:

- maximize P(S(L) >= T_cash)

Implementation:

1. Generate candidate lineups from deterministic optimizer.
2. Evaluate each candidate on scenario matrix.
3. Select lineup with highest estimated cash probability.

### 19.5 Contest-Size And Structure Tuning
Tune risk and threshold behavior by contest profile:

- H2H: higher floor emphasis
- Double-up/50-50: direct threshold probability maximization
- Small-field multiplier cash-like contests: moderate downside penalty

Parameters to tune per profile:

- lambda_sigma
- lambda_cov
- target percentile
- threshold model settings

### 19.6 Covariance Sparsification For Stability And Speed
Introduce covariance threshold pc in [0,1]-scaled correlation space:

- set small absolute covariance/correlation entries to zero

Benefits:

- reduces noise in risk penalty
- improves computational tractability

### 19.7 Weekly Calibration And Governance
Weekly monitoring loop:

1. Compare predicted cash probabilities to realized outcomes.
2. Track Brier score and log-loss.
3. Refit distribution and risk parameters when drift is detected.
4. Version all parameter sets and model artifacts.

Acceptance thresholds:

- no deployment if calibration degradation exceeds configured guardrails

### 19.8 Implementation Priority
Phase A:

1. normalized objective composer
2. covariance-aware downside penalty for single lineup
3. threshold-probability selector hardening

Phase B:

1. contest-profile-specific parameter tuning
2. covariance sparsification controls
3. calibration guardrails and rollback policy

### 19.9 Human-Heuristic Benchmark Guardrail
Add a paper3-style human baseline benchmark to validate optimizer edge each slate.

Human baseline definition:

1. For each roster slot, take top-N projected players eligible for that slot.
2. Randomly assemble lineups from this filtered pool under DFS constraints.
3. Run many trials and record best and mean projected points.

Required report fields:

- optimizer projection
- human baseline best projection
- human baseline mean projection
- edge vs baseline best
- edge vs baseline mean
- feasible trial count

Operational guidance:

- do not ship projection/risk changes if optimizer edge vs human baseline mean collapses below configured threshold
- run this benchmark as a weekly sanity check across slates

### 19.10 Position-Wise Prediction Model Selection Harness
Implement a rolling evaluation harness that compares candidate prediction columns by DFS position.

Inputs:

1. historical row dataset with columns: position, actual, model_a, model_b, ...
2. list of candidate model columns

Outputs:

1. RMSE per (position, model)
2. best model per position under minimum RMSE (tie-break: larger sample count)

Operational use:

- update per-position default prediction source only when harness shows stable improvement over baseline

### 19.11 Weekly Edge Trend Dashboard Export
Add an analytics workflow that runs optimizer-vs-human benchmark across multiple weekly slates.

Inputs:

1. slate CSV list/glob
2. trials and top-N baseline controls
3. optional cash lines by slate label

Required output fields per slate:

- slate label
- optimizer projection
- human best and mean projection
- edge vs human best
- edge vs human mean
- feasible trial count
- optional cash-line pass indicators

Aggregate outputs:

- mean edge vs human best
- mean edge vs human mean
- optional optimizer cash rate vs human mean cash rate

## 20. Spec Coverage Matrix
Coverage status as of current implementation.

Detailed tracker:

- See [spec_implementation_tracker.md](spec_implementation_tracker.md) for section-by-section status with code artifact mapping.

Implemented:

1. Core optimize/sensitivity/simulation architecture and APIs.
2. Exact tie handling and deterministic tie-break behavior.
3. Robust objective with rho, box/polygon uncertainty sets, covariance alignment, and PSD-safe covariance pipeline.
4. Stress test runner, calibration metrics, candidate generation, and cash-threshold selection.
5. Human heuristic baseline benchmark, position-wise prediction evaluation harness, and weekly edge trend analytics.
6. CLI support for robust options, compare-human, evaluate-predictions, and edge-trend.
7. GUI support for optimize/sensitivity/simulation/candidates/select-cash/stress/calibrate, analytics workflows, and robust controls.

Partially implemented:

1. Contest-type objective profiles (parameters exist, full profile-driven orchestration incomplete).
2. Correlated downside controls beyond covariance-aware robust objective (constraint-level controls limited).

Not implemented yet:

1. Normalized objective composer from section 19.3.
2. Full projection ensemble and outlier shrinkage pipeline from section 17.7.
3. News-volatility layer automation from section 17.6.
4. Sensitivity fragility score computation/output from section 17.9.
5. Full automated weekly recalibration/governance loop with deployment guardrails from sections 17.11 and 19.7.
6. Covariance sparsification controls from section 19.6.
