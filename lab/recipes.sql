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
