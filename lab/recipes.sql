-- @recipe pbp_players_game
-- @title Play-by-play: every play a player was in (one game)
-- @blurb Every play-by-play row, all ~370 columns, where either player is on the play: runner, passer, target, returner, tackler, pass defender, penalty and so on (matched by player id, not by name). No row limit. Pick the players, week and teams in the form above the SQL; picking a player fills in his team and that week's opponent. Week "All" = every game between those teams in the last 5 weeks of data. The involved column says which player was on the play.
WITH settings AS (SELECT 6 AS week, 'BAL' AS team_a, 'CLE' AS team_b, '00-0034975' AS player_1, '00-0032764' AS player_2),
names AS (SELECT player_id, any_value(player_display_name) AS name FROM players GROUP BY player_id),
plays AS (
  SELECT p.*, [
    p.td_player_id,
    p.passer_player_id,
    p.receiver_player_id,
    p.rusher_player_id,
    p.lateral_receiver_player_id,
    p.lateral_rusher_player_id,
    p.lateral_sack_player_id,
    p.interception_player_id,
    p.lateral_interception_player_id,
    p.punt_returner_player_id,
    p.lateral_punt_returner_player_id,
    p.kickoff_returner_player_id,
    p.lateral_kickoff_returner_player_id,
    p.punter_player_id,
    p.kicker_player_id,
    p.own_kickoff_recovery_player_id,
    p.blocked_player_id,
    p.tackle_for_loss_1_player_id,
    p.tackle_for_loss_2_player_id,
    p.qb_hit_1_player_id,
    p.qb_hit_2_player_id,
    p.forced_fumble_player_1_player_id,
    p.forced_fumble_player_2_player_id,
    p.solo_tackle_1_player_id,
    p.solo_tackle_2_player_id,
    p.assist_tackle_1_player_id,
    p.assist_tackle_2_player_id,
    p.assist_tackle_3_player_id,
    p.assist_tackle_4_player_id,
    p.tackle_with_assist_1_player_id,
    p.tackle_with_assist_2_player_id,
    p.pass_defense_1_player_id,
    p.pass_defense_2_player_id,
    p.fumbled_1_player_id,
    p.fumbled_2_player_id,
    p.fumble_recovery_1_player_id,
    p.fumble_recovery_2_player_id,
    p.sack_player_id,
    p.half_sack_1_player_id,
    p.half_sack_2_player_id,
    p.penalty_player_id,
    p.safety_player_id,
    p.fantasy_player_id] AS who_
  FROM pbp p, settings s
  WHERE (s.week IS NULL OR p.week = s.week)
    AND ((p.home_team = s.team_a AND p.away_team = s.team_b) OR (p.home_team = s.team_b AND p.away_team = s.team_a)))
SELECT CASE WHEN list_contains(who_, s.player_1) AND list_contains(who_, s.player_2) THEN coalesce(n1.name, s.player_1) || ' + ' || coalesce(n2.name, s.player_2)
            WHEN list_contains(who_, s.player_1) THEN coalesce(n1.name, s.player_1) ELSE coalesce(n2.name, s.player_2) END AS involved,
  plays.* EXCLUDE (who_)
FROM plays CROSS JOIN settings s
LEFT JOIN names n1 ON n1.player_id = s.player_1
LEFT JOIN names n2 ON n2.player_id = s.player_2
WHERE list_contains(who_, s.player_1) OR list_contains(who_, s.player_2)
ORDER BY plays.week, plays.game_seconds_remaining DESC, plays.play_id;

-- @recipe pbp_browse
-- @title Play-by-play: latest 200 plays
-- @blurb The raw play-by-play table (load_pbp(), last 5 weeks of the season, every play), newest week first, all columns. A starting point: add a WHERE line to filter by team (posteam = 'BAL'), play type (play_type = 'run'), down, red zone (yardline_100 <= 20) and so on.
SELECT *
FROM pbp
ORDER BY week DESC, game_id, game_seconds_remaining DESC, play_id
LIMIT 200;

-- @recipe rb_pickup
-- @title RB pickup check: usage, efficiency, matchup
-- @blurb Every RB with the numbers that decide a waiver or handcuff add. Usage: snap %, carry share and target share, season vs the last 3 weeks. Efficiency: PFR yards before/after contact and broken tackles, Next Gen rush yards over expected. Role: depth-chart spot, the starter ahead of him and that starter's injury status. Matchup: next opponent's rushing yards and yards per carry allowed (rank 1 = gives up the most) and what this player did if he already faced them. Change the settings line at the top to filter.
WITH settings AS (SELECT 3 AS recent_weeks, 2 AS min_games, 0.15 AS min_snap_pct, NULL::VARCHAR AS only_team),  -- only_team: e.g. 'TEN'
lw AS (SELECT last_completed_week AS w, next_week AS nw FROM meta),
tw AS (SELECT team, week, carries AS team_carries FROM teams),
p AS (
  SELECT p.player_id, arg_max(p.player_display_name, p.week) AS player, arg_max(p.team, p.week) AS team, count(*) AS g,
    avg(offense_pct) AS snap, avg(offense_pct) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS snap_l3,
    avg(p.carries) AS car, avg(p.carries) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS car_l3,
    sum(p.carries) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) / nullif(sum(tw.team_carries) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)), 0) AS car_share_l3,
    sum(p.carries) / nullif(sum(tw.team_carries), 0) AS car_share,
    avg(targets) AS tgt, avg(targets) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS tgt_l3,
    avg(target_share) AS tshare, avg(target_share) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS tshare_l3,
    avg(rushing_yards) AS ryds, sum(rushing_yards) / nullif(sum(p.carries), 0) AS ypc,
    sum(ybc) / nullif(sum(p.carries) FILTER (WHERE ybc IS NOT NULL), 0) AS ybc_att,
    sum(yac_rush) / nullif(sum(p.carries) FILTER (WHERE yac_rush IS NOT NULL), 0) AS yac_att,
    sum(broken_tackles) / nullif(sum(p.carries + p.receptions) FILTER (WHERE broken_tackles IS NOT NULL), 0) AS brk_per_touch,
    avg(xfp) AS xfp, avg(xfp) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS xfp_l3,
    avg(fantasy_points_ppr) AS ppr, avg(fantasy_points_ppr) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS ppr_l3
  FROM players p LEFT JOIN tw ON tw.team = p.team AND tw.week = p.week
  WHERE p.position = 'RB' GROUP BY p.player_id),
ngs AS (  -- Next Gen Stats: weekly rows only list backs with enough carries, so many backups are blank
  SELECT player_gsis_id AS player_id, sum(rush_yards_over_expected) / nullif(sum(rush_attempts), 0) AS ryoe_att,
    sum(percent_attempts_gte_eight_defenders * rush_attempts) / nullif(sum(rush_attempts), 0) AS box8
  FROM nextgen WHERE stat_type = 'rushing' AND week > 0 GROUP BY 1),
dc AS (SELECT gsis_id, team, min(pos_rank) AS rk FROM depth_charts WHERE pos_abb = 'RB' GROUP BY ALL),
inj AS (SELECT gsis_id, arg_max(coalesce(report_status, regexp_replace(regexp_replace(regexp_replace(practice_status, 'Did Not Participate.*', 'DNP'), 'Limited.*', 'Limited'), 'Full.*', 'Full') || ' practice (' || replace(coalesce(practice_primary_injury, report_primary_injury, '?'), 'Not injury related - resting player', 'rest') || ')'), week) AS status
  FROM injuries WHERE week >= (SELECT nw FROM lw) - 1 GROUP BY 1),
lead AS (SELECT dc.team, arg_min(pl.player_display_name, dc.rk) AS starter, arg_min(dc.gsis_id, dc.rk) AS starter_id
  FROM dc JOIN (SELECT player_id, arg_max(player_display_name, week) AS player_display_name FROM players GROUP BY 1) pl ON pl.player_id = dc.gsis_id GROUP BY 1),
nx AS (SELECT team, opp, implied FROM games_long WHERE week = (SELECT nw FROM lw)),
rd AS (  -- run defense: what offenses did against each defense
  SELECT opponent_team AS defense, avg(rushing_yards) AS rya, avg(carries) AS ratt, sum(rushing_yards) / nullif(sum(carries), 0) AS ypca, avg(rushing_tds) AS rtda
  FROM teams GROUP BY 1),
rdr AS (SELECT *, rank() OVER (ORDER BY rya DESC) AS rya_rk, rank() OVER (ORDER BY ypca DESC) AS ypca_rk FROM rd),
dvp AS (SELECT opponent_team AS defense, rank() OVER (ORDER BY sum(fantasy_points_ppr) / count(DISTINCT week) DESC) AS rb_rk
  FROM players WHERE position = 'RB' GROUP BY 1),
prev AS (SELECT player_id, opponent_team, arg_max(fantasy_points_ppr, week) AS ppr, arg_max(carries, week) AS car, arg_max(rushing_yards, week) AS yds FROM players GROUP BY ALL)
SELECT p.player, p.team, 'RB' || dc.rk::VARCHAR AS depth,
  CASE WHEN dc.rk > 1 THEN lead.starter END AS starter_ahead, CASE WHEN dc.rk > 1 THEN si.status END AS starter_injury, mi.status AS injury,
  p.g, round(p.snap*100) AS snap_pct, round(p.snap_l3*100) AS snap_pct_l3,
  round(p.car,1) AS rush_att_per_g, round(p.car_l3,1) AS rush_att_l3, round(p.car_share*100) AS carry_share_pct, round(p.car_share_l3*100) AS carry_share_l3,
  round(p.tgt,1) AS targets_per_g, round(p.tshare*100,1) AS tgt_share_pct, round(p.tshare_l3*100,1) AS tgt_share_l3,
  round(p.ryds,1) AS rush_yds_per_g, round(p.ypc,2) AS ypc, round(p.ybc_att,2) AS ybc_per_att, round(p.yac_att,2) AS yac_per_att,
  round(p.brk_per_touch*100,1) AS broken_tkl_per_100_touches, round(ngs.ryoe_att,2) AS ryoe_per_att, round(ngs.box8,0) AS box8_pct,
  round(p.xfp,1) AS xfp_per_g, round(p.xfp_l3,1) AS xfp_l3, round(p.ppr,1) AS ppr_per_g, round(p.ppr_l3,1) AS ppr_l3, round(p.ppr - p.xfp,1) AS ppr_minus_xfp,
  nx.opp AS next_opp, round(rdr.rya,1) AS opp_rush_yds_alw, rdr.rya_rk AS opp_rush_yds_alw_rk, round(rdr.ypca,2) AS opp_ypc_alw, rdr.ypca_rk AS opp_ypc_alw_rk,
  dvp.rb_rk AS opp_rb_ppr_alw_rk, round(nx.implied,1) AS team_implied_pts,
  CASE WHEN prev.ppr IS NOT NULL THEN prev.car::VARCHAR || '-' || prev.yds::VARCHAR || ', ' || round(prev.ppr,1)::VARCHAR || ' PPR' END AS earlier_vs_opp
FROM p
LEFT JOIN dc ON dc.gsis_id = p.player_id AND dc.team = p.team
LEFT JOIN lead ON lead.team = p.team
LEFT JOIN inj si ON si.gsis_id = lead.starter_id
LEFT JOIN inj mi ON mi.gsis_id = p.player_id
LEFT JOIN ngs ON ngs.player_id = p.player_id
LEFT JOIN nx ON nx.team = p.team
LEFT JOIN rdr ON rdr.defense = nx.opp
LEFT JOIN dvp ON dvp.defense = nx.opp
LEFT JOIN prev ON prev.player_id = p.player_id AND prev.opponent_team = nx.opp
WHERE p.g >= (SELECT min_games FROM settings)
  AND coalesce(p.snap_l3, p.snap) >= (SELECT min_snap_pct FROM settings)
  AND ((SELECT only_team FROM settings) IS NULL OR p.team = (SELECT only_team FROM settings))
ORDER BY p.xfp_l3 DESC NULLS LAST
LIMIT 80;

-- @recipe wr_pickup
-- @title WR pickup check: targets, quality, matchup
-- @blurb Every WR (set positions to add TEs) with the stats that drive receiver value. Usage: snap %, targets, target share and air yards share, season vs the last 3 weeks, and WOPR. Quality: aDOT, catch %, YAC, RACR, Next Gen separation and cushion, PFR drops. Matchup: next opponent's passing yards allowed (rank 1 = gives up the most), its WR points allowed rank, and the team's Vegas implied total. Change the settings line at the top to filter.
WITH settings AS (SELECT 3 AS recent_weeks, 2 AS min_games, 0.30 AS min_snap_pct, ['WR'] AS positions, NULL::VARCHAR AS only_team),  -- positions: ['WR','TE']
lw AS (SELECT last_completed_week AS w, next_week AS nw FROM meta),
p AS (
  SELECT p.player_id, arg_max(p.player_display_name, p.week) AS player, arg_max(p.position, p.week) AS pos, arg_max(p.team, p.week) AS team, count(*) AS g,
    avg(offense_pct) AS snap, avg(offense_pct) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS snap_l3,
    avg(targets) AS tgt, avg(targets) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS tgt_l3,
    avg(target_share) AS tshare, avg(target_share) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS tshare_l3,
    avg(target_share) FILTER (WHERE p.week <= (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS tshare_before,
    avg(air_yards_share) AS ashare, avg(wopr) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS wopr_l3,
    sum(receiving_air_yards) / nullif(sum(targets), 0) AS adot, sum(receptions) / nullif(sum(targets), 0) AS catch,
    avg(receiving_yards) AS ryds, sum(receiving_yards_after_catch) / nullif(sum(receptions), 0) AS yac_rec,
    sum(receiving_yards) / nullif(sum(receiving_air_yards), 0) AS racr, avg(receiving_tds) AS rtd,
    avg(xfp) AS xfp, avg(xfp) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS xfp_l3,
    avg(fantasy_points_ppr) AS ppr, avg(fantasy_points_ppr) FILTER (WHERE p.week > (SELECT w FROM lw) - (SELECT recent_weeks FROM settings)) AS ppr_l3
  FROM players p WHERE list_contains((SELECT positions FROM settings), p.position) GROUP BY p.player_id),
ngs AS (  -- Next Gen Stats only lists receivers with enough targets that week
  SELECT player_gsis_id AS player_id, sum(avg_separation * targets) / nullif(sum(targets), 0) AS sep, sum(avg_cushion * targets) / nullif(sum(targets), 0) AS cush,
    sum(avg_yac_above_expectation * receptions) / nullif(sum(receptions), 0) AS yacoe
  FROM nextgen WHERE stat_type = 'receiving' AND week > 0 GROUP BY 1),
drops AS (SELECT pfr_player_name, team, sum(receiving_drop) AS drops, sum(receiving_drop) / nullif(count(*), 0) AS drops_g FROM pfr_rec GROUP BY ALL),
dc AS (SELECT gsis_id, team, min(pos_rank) AS rk, arg_min(pos_abb, pos_rank) AS slot FROM depth_charts WHERE pos_abb IN ('WR','LWR','RWR','SWR','TE') GROUP BY ALL),
inj AS (SELECT gsis_id, arg_max(coalesce(report_status, regexp_replace(regexp_replace(regexp_replace(practice_status, 'Did Not Participate.*', 'DNP'), 'Limited.*', 'Limited'), 'Full.*', 'Full') || ' practice (' || replace(coalesce(practice_primary_injury, report_primary_injury, '?'), 'Not injury related - resting player', 'rest') || ')'), week) AS status
  FROM injuries WHERE week >= (SELECT nw FROM lw) - 1 GROUP BY 1),
nx AS (SELECT team, opp, implied FROM games_long WHERE week = (SELECT nw FROM lw)),
pd AS (SELECT opponent_team AS defense, avg(passing_yards) AS pya, sum(passing_yards) / nullif(sum(attempts), 0) AS ypa, avg(passing_tds) AS ptda FROM teams GROUP BY 1),
pdr AS (SELECT *, rank() OVER (ORDER BY pya DESC) AS pya_rk FROM pd),
dvp AS (SELECT opponent_team AS defense, rank() OVER (ORDER BY sum(fantasy_points_ppr) FILTER (WHERE position = 'WR') / count(DISTINCT week) DESC) AS wr_rk,
  rank() OVER (ORDER BY sum(fantasy_points_ppr) FILTER (WHERE position = 'TE') / count(DISTINCT week) DESC) AS te_rk FROM players GROUP BY 1),
prev AS (SELECT player_id, opponent_team, arg_max(fantasy_points_ppr, week) AS ppr, arg_max(receptions, week) AS rec, arg_max(receiving_yards, week) AS yds FROM players GROUP BY ALL)
SELECT p.player, p.pos AS position, p.team, dc.slot || dc.rk::VARCHAR AS depth, mi.status AS injury, p.g,
  round(p.snap*100) AS snap_pct, round(p.snap_l3*100) AS snap_pct_l3,
  round(p.tgt,1) AS targets_per_g, round(p.tgt_l3,1) AS targets_l3,
  round(p.tshare*100,1) AS tgt_share_pct, round(p.tshare_l3*100,1) AS tgt_share_l3, round((p.tshare_l3 - p.tshare_before)*100,1) AS tgt_share_change,
  round(p.ashare*100,1) AS air_share_pct, round(p.wopr_l3,2) AS wopr_l3,
  round(p.adot,1) AS adot, round(p.catch*100) AS catch_pct, round(p.ryds,1) AS rec_yds_per_g, round(p.yac_rec,1) AS yac_per_rec, round(p.racr,2) AS racr,
  round(ngs.sep,2) AS separation, round(ngs.cush,2) AS cushion, round(ngs.yacoe,2) AS yac_over_exp, drops.drops AS drops,
  round(p.xfp,1) AS xfp_per_g, round(p.xfp_l3,1) AS xfp_l3, round(p.ppr,1) AS ppr_per_g, round(p.ppr_l3,1) AS ppr_l3, round(p.ppr - p.xfp,1) AS ppr_minus_xfp,
  nx.opp AS next_opp, round(pdr.pya,1) AS opp_pass_yds_alw, pdr.pya_rk AS opp_pass_yds_alw_rk, round(pdr.ypa,2) AS opp_ypa_alw,
  CASE WHEN p.pos = 'TE' THEN dvp.te_rk ELSE dvp.wr_rk END AS opp_pos_ppr_alw_rk, round(nx.implied,1) AS team_implied_pts,
  CASE WHEN prev.ppr IS NOT NULL THEN prev.rec::VARCHAR || '-' || prev.yds::VARCHAR || ', ' || round(prev.ppr,1)::VARCHAR || ' PPR' END AS earlier_vs_opp
FROM p
LEFT JOIN dc ON dc.gsis_id = p.player_id AND dc.team = p.team
LEFT JOIN inj mi ON mi.gsis_id = p.player_id
LEFT JOIN ngs ON ngs.player_id = p.player_id
LEFT JOIN drops ON drops.pfr_player_name = p.player AND drops.team = p.team
LEFT JOIN nx ON nx.team = p.team
LEFT JOIN pdr ON pdr.defense = nx.opp
LEFT JOIN dvp ON dvp.defense = nx.opp
LEFT JOIN prev ON prev.player_id = p.player_id AND prev.opponent_team = nx.opp
WHERE p.g >= (SELECT min_games FROM settings)
  AND coalesce(p.snap_l3, p.snap) >= (SELECT min_snap_pct FROM settings)
  AND ((SELECT only_team FROM settings) IS NULL OR p.team = (SELECT only_team FROM settings))
ORDER BY p.xfp_l3 DESC NULLS LAST
LIMIT 80;

-- @recipe dst_pressure
-- @title D/ST streamers: pressure matchup
-- @blurb Your sack idea. Ranks each defense's next game by how much pressure it creates against how much pressure its opponent's line allows, minus the opponent's Vegas implied points. Each piece is a z-score (how many standard deviations from league average), so they add up fairly.
WITH d AS (
  SELECT team, avg(def_pressures) AS pr_made, avg(def_sacks) AS sk_made, avg(def_interceptions + fumble_recovery_opp) AS takeaways, avg(dst_pts) AS dst_pts
  FROM teams GROUP BY team),
o AS (
  SELECT team, avg(pressures_allowed) AS pr_alw, avg(sacks_suffered) AS sk_alw, avg(passing_interceptions) AS int_thrown
  FROM teams GROUP BY team),
nx AS (SELECT team, opp, opp_implied FROM games_long WHERE week = (SELECT next_week FROM meta)),
j AS (
  SELECT nx.team AS defense, nx.opp AS opponent, d.dst_pts, d.pr_made, o.pr_alw AS opp_pr_alw, d.sk_made, o.sk_alw AS opp_sk_alw, o.int_thrown AS opp_int, d.takeaways, nx.opp_implied
  FROM nx JOIN d ON d.team = nx.team JOIN o ON o.team = nx.opp)
SELECT defense, opponent,
  round(dst_pts,1) AS dst_pts_per_g,
  round(pr_made,1) AS pressures_per_g, round(opp_pr_alw,1) AS opp_pressures_allowed,
  round(sk_made,1) AS sacks_per_g, round(opp_sk_alw,1) AS opp_sacks_allowed,
  round(opp_implied,1) AS opp_implied_pts,
  round( (pr_made - avg(pr_made) OVER ()) / stddev_samp(pr_made) OVER ()
       + (opp_pr_alw - avg(opp_pr_alw) OVER ()) / stddev_samp(opp_pr_alw) OVER ()
       + (sk_made - avg(sk_made) OVER ()) / stddev_samp(sk_made) OVER ()
       + (opp_sk_alw - avg(opp_sk_alw) OVER ()) / stddev_samp(opp_sk_alw) OVER ()
       - (opp_implied - avg(opp_implied) OVER ()) / stddev_samp(opp_implied) OVER (), 2) AS matchup_score
FROM j
ORDER BY matchup_score DESC;

-- @recipe usage_risers
-- @title Usage risers (last 3 weeks vs before)
-- @blurb Players whose snap share and opportunities jumped recently. Usage moves before points do, so this is the earliest waiver signal.
WITH lw AS (SELECT max(week) AS w FROM players),
s AS (
  SELECT player_display_name AS player, position, arg_max(team, week) AS team,
    avg(offense_pct) FILTER (WHERE week >  (SELECT w FROM lw) - 3) AS snap_recent,
    avg(offense_pct) FILTER (WHERE week <= (SELECT w FROM lw) - 3) AS snap_before,
    avg(carries + targets) FILTER (WHERE week >  (SELECT w FROM lw) - 3) AS opps_recent,
    avg(carries + targets) FILTER (WHERE week <= (SELECT w FROM lw) - 3) AS opps_before,
    avg(xfp) FILTER (WHERE week > (SELECT w FROM lw) - 3) AS xfp_recent,
    avg(fantasy_points_ppr) FILTER (WHERE week > (SELECT w FROM lw) - 3) AS ppr_recent
  FROM players WHERE position IN ('RB','WR','TE') GROUP BY ALL)
SELECT player, position, team,
  round(snap_before*100) AS snap_pct_before, round(snap_recent*100) AS snap_pct_recent,
  round((snap_recent - snap_before)*100) AS snap_change,
  round(opps_before,1) AS opps_before, round(opps_recent,1) AS opps_recent,
  round(xfp_recent,1) AS xfp_recent, round(ppr_recent,1) AS ppr_recent
FROM s
WHERE snap_recent IS NOT NULL AND snap_before IS NOT NULL
ORDER BY (snap_recent - snap_before) + (opps_recent - opps_before)/40 DESC
LIMIT 40;

-- @recipe buy_low
-- @title Buy low: usage without the points
-- @blurb Players getting volume that should produce points (high expected points) who've scored less than expected. Points tend to catch up with usage.
SELECT player_display_name AS player, position, arg_max(team, week) AS team, count(*) AS g,
  round(avg(xfp),1) AS xfp_per_g, round(avg(fantasy_points_ppr),1) AS ppr_per_g,
  round(avg(xfp_diff),1) AS ppr_minus_xfp, round(avg(offense_pct)*100) AS snap_pct
FROM players
WHERE xfp IS NOT NULL AND position IN ('RB','WR','TE')
GROUP BY ALL
HAVING count(*) >= 3 AND avg(xfp) >= 8
ORDER BY avg(xfp_diff) ASC
LIMIT 40;

-- @recipe composite
-- @title My final number: WR/TE composite score
-- @blurb The notebook method, automated. Each stat becomes a z-score within the position, then they're added with weights. Edit the weights on the last lines to make it yours.
WITH p AS (
  SELECT player_display_name AS player, position, arg_max(team, week) AS team, count(*) AS g,
    avg(target_share) AS tgt_share, avg(air_yards_share) AS air_share, avg(xfp) AS xfp, avg(offense_pct) AS snap
  FROM players WHERE position IN ('WR','TE') GROUP BY ALL HAVING count(*) >= 3),
z AS (
  SELECT *,
    (tgt_share - avg(tgt_share) OVER w) / stddev_samp(tgt_share) OVER w AS z_tgt,
    (air_share - avg(air_share) OVER w) / stddev_samp(air_share) OVER w AS z_air,
    (xfp - avg(xfp) OVER w) / stddev_samp(xfp) OVER w AS z_xfp,
    (snap - avg(snap) OVER w) / stddev_samp(snap) OVER w AS z_snap
  FROM p WINDOW w AS (PARTITION BY position))
SELECT player, position, team, g,
  round(tgt_share*100) AS tgt_share_pct, round(air_share*100) AS air_share_pct, round(xfp,1) AS xfp_per_g, round(snap*100) AS snap_pct,
  round(1.0*z_tgt + 0.6*z_air + 1.0*z_xfp + 0.4*z_snap, 2) AS final_number
FROM z
ORDER BY final_number DESC
LIMIT 50;

-- @recipe dvp
-- @title Defense vs position, next week
-- @blurb Fantasy points each defense allows per game by position, as z-scores, joined to who they play next. Positive = soft matchup for that position.
WITH a AS (
  SELECT opponent_team AS defense, position, sum(fantasy_points_ppr) / count(DISTINCT week) AS ppr_allowed
  FROM players GROUP BY ALL),
z AS (
  SELECT *, (ppr_allowed - avg(ppr_allowed) OVER (PARTITION BY position)) / stddev_samp(ppr_allowed) OVER (PARTITION BY position) AS z
  FROM a),
w AS (
  SELECT defense,
    round(max(z) FILTER (WHERE position = 'QB'),2) AS QB, round(max(z) FILTER (WHERE position = 'RB'),2) AS RB,
    round(max(z) FILTER (WHERE position = 'WR'),2) AS WR, round(max(z) FILTER (WHERE position = 'TE'),2) AS TE
  FROM z GROUP BY defense)
SELECT g.opp AS offense, g.team AS faces_defense, w.QB, w.RB, w.WR, w.TE
FROM games_long g JOIN w ON w.defense = g.team
WHERE g.week = (SELECT next_week FROM meta)
ORDER BY w.WR DESC;

-- @recipe tiers
-- @title Production vs good, average and bad defenses
-- @blurb Your "similarly rated teams" idea. Defenses are split into thirds by points allowed, then each player's PPR average is shown against each tier. A player who produces against good defenses is real.
WITH tier AS (
  SELECT team, ntile(3) OVER (ORDER BY avg(points_against)) AS t
  FROM teams GROUP BY team),
pt AS (
  SELECT p.player_display_name AS player, p.position, p.team, p.fantasy_points_ppr AS ppr, tier.t
  FROM players p JOIN tier ON tier.team = p.opponent_team)
SELECT player, position, arg_max(team, t) AS team, count(*) AS g,
  round(avg(ppr) FILTER (WHERE t = 1),1) AS vs_top_defenses,
  round(avg(ppr) FILTER (WHERE t = 2),1) AS vs_middle,
  round(avg(ppr) FILTER (WHERE t = 3),1) AS vs_bottom_defenses,
  count(*) FILTER (WHERE t = 1) AS g_vs_top
FROM pt GROUP BY player, position
HAVING count(*) >= 4 AND count(*) FILTER (WHERE t = 1) >= 2
ORDER BY vs_top_defenses DESC NULLS LAST
LIMIT 50;

-- @recipe qb_pressure
-- @title QB danger: pressured QBs vs this week's pass rush
-- @blurb For each QB, how often he's pressured and how hard his next opponent gets home. High = rough day for the QB, good day for that D/ST.
WITH starter AS (
  -- the QB with the most attempts in each team's latest game
  SELECT team, arg_max(player_id, week * 1000 + attempts) AS player_id FROM players WHERE position = 'QB' GROUP BY team),
q AS (
  SELECT any_value(p.player_display_name) AS qb, s.team, count(*) AS g,
    sum(qb_pressured) / nullif(sum(attempts + sacks_suffered),0) AS press_rate,
    avg(sacks_suffered) AS sacks_per_g, avg(passing_epa) AS epa_per_g
  FROM players p JOIN starter s ON s.player_id = p.player_id
  WHERE attempts >= 10 GROUP BY s.team),
d AS (SELECT team, avg(def_pressures) AS pr_made FROM teams GROUP BY team),
nx AS (SELECT team, opp FROM games_long WHERE week = (SELECT next_week FROM meta))
SELECT q.qb, q.team, nx.opp AS faces, round(q.press_rate*100) AS pressured_pct, round(q.sacks_per_g,1) AS sacks_per_g,
  round(d.pr_made,1) AS opp_pressures_per_g, round(q.epa_per_g,1) AS pass_epa_per_g
FROM q JOIN nx ON nx.team = q.team JOIN d ON d.team = nx.opp
ORDER BY q.press_rate * d.pr_made DESC;

-- @recipe implied
-- @title Vegas: implied team totals this week
-- @blurb What Vegas expects each offense to score, next to how many points they've actually averaged.
SELECT g.team, g.opp, g.is_home, round(g.implied,1) AS implied_pts, round(avg(t.points_for),1) AS avg_pts_scored,
  round(g.implied - avg(t.points_for),1) AS implied_vs_avg, g.spread_line, g.total_line
FROM games_long g JOIN teams t ON t.team = g.team
WHERE g.week = (SELECT next_week FROM meta)
GROUP BY g.team, g.opp, g.is_home, g.implied, g.spread_line, g.total_line
ORDER BY implied_pts DESC;

-- @recipe available_matchups
-- @title Free agents with soft matchups this week
-- @blurb Uses the avail table (your selected league). Available RB/WR/TE who are getting used, ranked by recent expected points (z-score, counts double) plus half of how many points their next opponent allows to their position (z-score). Add a team filter like AND a.team = 'LV' to narrow it.
WITH dvp AS (
  SELECT opponent_team AS defense, position, sum(fantasy_points_ppr) / count(DISTINCT week) AS allowed
  FROM players GROUP BY ALL),
dz AS (SELECT *, (allowed - avg(allowed) OVER (PARTITION BY position)) / stddev_samp(allowed) OVER (PARTITION BY position) AS matchup_z FROM dvp),
recent AS (
  SELECT player_id, avg(xfp) AS xfp_l3, avg(fantasy_points_ppr) AS ppr_l3, avg(offense_pct) AS snap_l3
  FROM players WHERE week > (SELECT last_completed_week FROM meta) - 3 GROUP BY player_id)
SELECT a.player_display_name AS player, a.position, a.team, g.opp AS next_opp,
  round(r.xfp_l3,1) AS xfp_l3, round(r.ppr_l3,1) AS ppr_l3, round(r.snap_l3*100) AS snap_pct_l3,
  round(dz.matchup_z,2) AS matchup_z,
  round((r.xfp_l3 - avg(r.xfp_l3) OVER (PARTITION BY a.position)) / stddev_samp(r.xfp_l3) OVER (PARTITION BY a.position)
        + 0.5 * dz.matchup_z, 2) AS pickup_score
FROM avail a
JOIN recent r USING (player_id)
JOIN games_long g ON g.team = a.team AND g.week = (SELECT next_week FROM meta)
JOIN dz ON dz.defense = g.opp AND dz.position = a.position
WHERE coalesce(a.status, 'fa') = 'fa' AND a.position IN ('RB','WR','TE') AND r.snap_l3 >= 0.3
ORDER BY pickup_score DESC
LIMIT 40;
