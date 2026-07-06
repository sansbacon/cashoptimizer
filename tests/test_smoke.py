from cash_optimizer import CashOptimizer, Player, Rules, SimulationConfig, load_players_from_dk_csv


def _build_players():
    return [
        Player("qb_a", "QB A", "T1", "T2", "QB", 7000, 21.0),
        Player("qb_b", "QB B", "T2", "T1", "QB", 6800, 20.2),
        Player("rb_a", "RB A", "T3", "T4", "RB", 7600, 19.0),
        Player("rb_b", "RB B", "T4", "T3", "RB", 7100, 17.3),
        Player("rb_c", "RB C", "T5", "T6", "RB", 6200, 15.0),
        Player("rb_d", "RB D", "T6", "T5", "RB", 5600, 13.8),
        Player("wr_a", "WR A", "T1", "T2", "WR", 7900, 21.8),
        Player("wr_b", "WR B", "T2", "T1", "WR", 7000, 18.5),
        Player("wr_c", "WR C", "T3", "T4", "WR", 6200, 15.7),
        Player("wr_d", "WR D", "T4", "T3", "WR", 5300, 13.4),
        Player("wr_e", "WR E", "T5", "T6", "WR", 4800, 12.3),
        Player("te_a", "TE A", "T1", "T2", "TE", 5100, 12.9),
        Player("te_b", "TE B", "T2", "T1", "TE", 4300, 10.4),
        Player("dst_a", "DST A", "T7", "T8", "DST", 3500, 8.2),
        Player("dst_b", "DST B", "T8", "T7", "DST", 2900, 6.9),
    ]


def _build_tie_players():
    return [
        Player("qb_1", "QB 1", "T1", "T2", "QB", 7000, 20.0),
        Player("rb_1", "RB 1", "T3", "T4", "RB", 7000, 18.0),
        Player("rb_2", "RB 2", "T4", "T3", "RB", 6900, 17.0),
        Player("rb_3", "RB 3", "T5", "T6", "RB", 6100, 14.0),
        Player("rb_4", "RB 4", "T6", "T5", "RB", 6100, 14.0),
        Player("wr_1", "WR 1", "T7", "T8", "WR", 7000, 17.0),
        Player("wr_2", "WR 2", "T8", "T7", "WR", 6900, 16.5),
        Player("wr_3", "WR 3", "T9", "T10", "WR", 6800, 16.0),
        Player("te_1", "TE 1", "T11", "T12", "TE", 5000, 12.0),
        Player("dst_1", "DST 1", "T11", "T12", "DST", 3000, 7.0),
    ]


def test_optimal_lineup_is_valid():
    optimizer = CashOptimizer(players=_build_players(), rules=Rules())
    result = optimizer.solve_optimal()

    assert len(result.lineup.player_ids) == 9
    assert result.lineup.salary_used <= 50000
    assert result.optimal_projection > 0


def test_sensitivity_computes_entries():
    optimizer = CashOptimizer(players=_build_players(), rules=Rules())
    sens = optimizer.solve_sensitivity_all()

    assert len(sens.entries) == len(_build_players())
    assert any(e.in_optimal for e in sens.entries)
    assert any(not e.in_optimal for e in sens.entries)


def test_simulation_runs_and_aggregates():
    optimizer = CashOptimizer(players=_build_players(), rules=Rules())
    sim = optimizer.run_projection_distribution_simulation(
        SimulationConfig(num_runs=20, random_seed=123, worker_count=1)
    )

    assert sim.num_runs == 20
    assert sim.unique_lineups >= 1
    assert len(sim.player_stats) == len(_build_players())


def test_run_many_sampled_sets_aggregates_online():
    optimizer = CashOptimizer(players=_build_players(), rules=Rules())
    base = [p.projection for p in _build_players()]
    vectors = [base, base, base, base, base]

    sim = optimizer.run_many_sampled_sets(sample_generator=vectors, num_runs=5)

    assert sim.num_runs == 5
    assert sim.unique_lineups >= 1


def test_tie_detection_reports_possible_tie():
    optimizer = CashOptimizer(players=_build_tie_players(), rules=Rules(salary_cap=70000))
    result = optimizer.solve_optimal()

    assert result.ties_possible is True


def test_max_players_per_game_environment_constraint_applies():
    players = [
        Player("qb1", "QB1", "A", "B", "QB", 7000, 20.0, game_id="g1"),
        Player("rb1", "RB1", "A", "B", "RB", 7000, 19.0, game_id="g1"),
        Player("rb2", "RB2", "C", "D", "RB", 6900, 18.0, game_id="g2"),
        Player("rb3", "RB3", "E", "F", "RB", 6200, 15.0, game_id="g3"),
        Player("rb4", "RB4", "G", "H", "RB", 5900, 14.2, game_id="g4"),
        Player("wr1", "WR1", "A", "B", "WR", 7000, 19.0, game_id="g1"),
        Player("wr2", "WR2", "C", "D", "WR", 6800, 17.5, game_id="g2"),
        Player("wr3", "WR3", "E", "F", "WR", 6400, 16.0, game_id="g3"),
        Player("wr4", "WR4", "G", "H", "WR", 5200, 13.8, game_id="g4"),
        Player("te1", "TE1", "I", "J", "TE", 5000, 12.0, game_id="g5"),
        Player("dst1", "DST1", "I", "J", "DST", 3000, 8.0, game_id="g5"),
        Player("te2", "TE2", "K", "L", "TE", 4200, 10.2, game_id="g6"),
    ]
    rules = Rules(salary_cap=70000, max_players_per_game_environment=2)
    optimizer = CashOptimizer(players=players, rules=rules)
    result = optimizer.solve_optimal()

    selected = [p for p in players if p.player_id in set(result.lineup.player_ids)]
    per_game: dict[str, int] = {}
    for p in selected:
        key = p.game_id or ""
        per_game[key] = per_game.get(key, 0) + 1
    assert max(per_game.values()) <= 2


def test_max_non_qb_skill_players_same_team_constraint_applies():
    players = [
        Player("qb1", "QB1", "A", "B", "QB", 7000, 20.0),
        Player("rb1", "RB1", "A", "B", "RB", 7000, 19.0),
        Player("rb2", "RB2", "C", "D", "RB", 6900, 18.0),
        Player("rb3", "RB3", "E", "F", "RB", 6200, 15.0),
        Player("rb4", "RB4", "G", "H", "RB", 5900, 14.0),
        Player("wr1", "WR1", "A", "B", "WR", 7000, 19.0),
        Player("wr2", "WR2", "C", "D", "WR", 6800, 18.5),
        Player("wr3", "WR3", "E", "F", "WR", 6400, 17.9),
        Player("wr4", "WR4", "G", "H", "WR", 5600, 14.8),
        Player("te1", "TE1", "I", "J", "TE", 5000, 12.0),
        Player("dst1", "DST1", "I", "J", "DST", 3000, 8.0),
        Player("te2", "TE2", "K", "L", "TE", 4200, 10.5),
    ]
    rules = Rules(salary_cap=70000, max_non_qb_skill_players_same_team=2)
    optimizer = CashOptimizer(players=players, rules=rules)
    result = optimizer.solve_optimal()

    selected = [p for p in players if p.player_id in set(result.lineup.player_ids)]
    team_skill_counts: dict[str, int] = {}
    for p in selected:
        if p.position in {"RB", "WR", "TE"}:
            team_skill_counts[p.team] = team_skill_counts.get(p.team, 0) + 1
    assert max(team_skill_counts.values()) <= 2


def test_loader_optional_schema_fields(tmp_path):
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Position,Name,Salary,TeamAbbrev,Opp,Projection,Status,Floor,Ceiling,Ownership,GameTotal,Spread,CorrelationGroup,StdDev,DistributionType,Matchup",
                "QB,Test QB,7000,AAA,BBB,20.5,questionable,16.0,28.0,0.12,47.5,-3.5,g1,4.2,normal,AAA@BBB 1:00PM ET",
            ]
        ),
        encoding="utf-8",
    )

    players = load_players_from_dk_csv(csv_path)
    assert len(players) == 1
    p = players[0]
    assert p.status == "questionable"
    assert p.floor == 16.0
    assert p.ceiling == 28.0
    assert p.ownership == 0.12
    assert p.game_total == 47.5
    assert p.spread == -3.5
    assert p.correlation_group == "g1"
    assert p.distribution.std_dev == 4.2
    assert p.distribution.distribution_type == "normal"
