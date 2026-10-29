CREATE OR REPLACE VIEW games_long AS
  SELECT week, gameday, home_team AS team, away_team AS opp, TRUE AS is_home, home_implied AS implied, away_implied AS opp_implied,
         spread_line, total_line, home_score AS points_for, away_score AS points_against, roof, temp, wind, div_game
  FROM schedule
  UNION ALL
  SELECT week, gameday, away_team, home_team, FALSE, away_implied, home_implied,
         -spread_line, total_line, away_score, home_score, roof, temp, wind, div_game
  FROM schedule;
