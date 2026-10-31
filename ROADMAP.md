# ROADMAP

The plan for NFL_stats. Claude keeps this current (see CLAUDE.md → "How we work"). One active project at a time.

## Now

**Lab UX** — easier to understand and navigate. Preset filters people can click before they type; the Ask box for everyone else; suggested custom metrics as Lab filters.
- ✅ **Recipe settings with search (10/30):** any query with a `WITH settings AS (SELECT … AS name, …)` line gets a form above the SQL: player search (stores the id, fills in his team and that week's opponent), team and week pickers, number/text boxes. Works for recipes, saved queries and anything pasted.
- ✅ **Match players by id, not description text:** `pbp_players_game` matches every `*_player_id` column (runner, passer, target, returner, tacklers, pass defenders, penalties…).
- ✅ **Readable play log (Lab):** recipe `pbp_log` — one row per play: quarter, clock, down & distance, field, run/pass/sack/scramble, QB, ball carrier/target, direction + gap, depth + air yards, result, yards, YAC, tacklers, pass defended, penalty, EPA, original text last. Filter by player (any role), team, week; names link to cards.
- ✅ **Plays in player/game cards:** player card = his plays one game at a time (week chips); game card = every play, filter by offense. TDs green, turnovers red; names link. Data: `data/site/plays/<game_id>.json.gz` (~8 KB a game) from `update_data.py`.
- **Presets before typing:** clickable starting points grouped by question (waivers, matchups, trade checks, play-by-play) with one plain-English line each.
- **Suggested custom metrics as Lab filters** (after metrics are backtested).

## Next (in order, one at a time)

1. **Custom metrics + backtests** — William's own filters/metrics, each with a one-line plain-English explanation and a backtest (does it predict next-week points better than a simple baseline like last-3-week average? if not, cut it). Seasons 2022–2025.
   - Candidates from the Justice Hill look (10/30): production split by opponent's RB points allowed (does he only hit vs bottom-5 run defenses? his two good games were BUF and ARI); scrimmage yards (rush + rec) and share; snap % trend as the role signal.
   - From play-by-play: run direction / gap profile per RB vs where each defense gives up yards by gap; opponent's pass vs run play mix; who makes the tackles on RBs per defense. Defender-on-field data (participation) only goes through 2025, so it's backtest-only.
2. **Pressers + coaching profiles** — head coach press conferences → structured per-player signals (player, topic, tone, short quote snippet). Feeds Trade/compare tabs and outlooks. Grows into a profile per coach: offense style, honesty (said vs did), outlook on players, trust signals, opponent-defense context, injury updates. See Pressers notes below.
3. **Statistical outlooks + grading** — the rest-of-season score (see "Model + public site") plus AI outlooks built only from data (QB, defense, depth chart, draft position, presser sentiment, injuries, news), every claim tied to a data row. Save each week's projections, grade them after the games, learn why misses happened, publish accuracy.
4. **Monitor** — health checks with alerts (see Ideas).
5. **Accounts + payments** — after the NFL season. See Business model.

## Ideas (not scheduled)

- 2026-10-30 · **Same idea for WR vs CB/S (William):** team level works the same with `pass_location` (left/middle/right) × `pass_length` (short/deep) on every target, opponent-adjusted. Per-defender is weaker than for runs: 2026 free data has no coverage assignment or WR alignment (slot vs outside), only pass defenses, tackles and PFR's per-defender coverage totals (targets, catches, yards, TDs, rating allowed, aDOT). 2025 and earlier participation data has coverage type (man/zone, Cover 1/3…) and routes: good for backtests, not live.
- 2026-10-30 · **Defender index for next season (William):** rate each defender on his own (PFR coverage, tackles/missed tackles, pressures, run stops by area via tackles; on-field splits from participation through 2025), then build next year's team defense from the defenders actually on the roster, weighted by snaps (snap_counts has defensive snaps for 2026). Fixes "last year's team stats describe a different team". Combine with the defensive coordinator (scheme changes matter as much as personnel → coaching profiles). Offseason project, also reusable for MLB/FPL thinking.
- 2026-10-30 · **RB vs DEF rating (William):** one number for "this back vs this defense" built from *where* plays go. Team level first: yards / success / explosive rate allowed by run direction + gap and by pass area (left/middle/right, short/deep), opponent-adjusted (a weak RB gaining 10+ in an area counts more than Jeanty doing it; the difference between raw and adjusted flags real holes). Then match each RB's direction/gap profile (and target share) to those holes, plus how often opponents actually attack that side. Per-defender splits only through who made the tackle / pass defense (2026 has no on-field participation data, and the tackler isn't always the player at fault, e.g. a safety cleaning up a 12-yard run). Check before trusting it: sample size (8 games ≈ 20–40 carries per gap, so shrink toward league average), scheme (zone defenders don't own one area every snap), game script (Vegas spread → carries), teammate injuries / depth chart (Hill's role vs Henry's health), the O-line side he runs behind (we have with/without lineman rates), and whether offenses really steer runs at a weak side (testable in pbp: does attack rate rise vs weak gaps?). Backtest like the other metrics. Belongs to Custom metrics.

- 2026-10-29 · **Bug to fix:** the stat description's "in the Guide" link opens the Guide but doesn't scroll to / select that stat (William, talk through 10/30).

- 2026-10-29 · **Monitor / health check:** GitHub Action every 12h (or daily). Checks: each team's presser source has something new within its expected window (skip bye weeks using the nflverse schedule); page structure still parses (title, date, body); nflverse data updated on time; sitemap pages load, no broken links. On failure, open a GitHub Issue naming the team, the check and the last success (GitHub app pushes it to William's phone). Log to `monitor/status.json`; maybe a small status page later. *Ideas only — don't build yet.*
- 2026-10-29 · Track coach reliability: over a season, did "he'll get a bigger role" actually happen? Weight each coach's signals by their track record.
- 2026-10-29 · Outlooks are the same for every user → generate once a week and cache. Only personal Lab runs cost credits.
- 2026-10-30 · **One-page layout (William, still playing with it):** Stats as the main page where everything lives (Stats dropdown up top), and the other tools (Lab, Trade, Waivers) open from a side panel into resizable pop-up windows. Decide after Navigation is done; the pop-out windows we have are the starting point.
- 2026-10-30 · **Trade: team comparison sheet** — both teams' whole offensive rosters side by side by position (QB/RB/WR/TE), not only the players in the trade.
- 2026-10-30 · **"Most receptions through games on roster"** — need William to clarify what this means before it's scheduled.
- 2026-10-29 · Multi-league linking later: Sleeper (public API, already used) → Yahoo (official OAuth API) → ESPN (unofficial; private leagues need espn_s2/SWID cookies, store encrypted). MFL and Fleaflicker also have APIs. NFL Fantasy is shutting down and moving to ESPN.

## Pressers notes

- 2026-10-29 · YouTube's official API only returns captions for videos you own; scraping (yt-dlp etc.) is a terms-of-service gray area and often blocked from cloud runners. Not the main path.
- 2026-10-29 · Better: some teams post written transcripts on their own sites (e.g. patriots.com "Transcript: Head Coach … Press Conference"); fan sites like PatsFans fill gaps. Plan a 3-tier source per team: written transcript → captions from the team site's video player → flag for manual review. First step: sort all 32 teams into tiers in `docs/presser-sources.md`.
- 2026-10-29 · Cost is small (a ~20 min presser ≈ 5k tokens; 32/week is cheap). Current plan from earlier: weekly on Wednesdays, head coaches' latest presser only.
- 2026-10-29 · Existing competition: The Coachspeak Index (human-curated presser notes in a paid Discord/Patreon) and Sentitrac (news-sentiment projections). Nobody found doing automated per-player structured signals that get graded against results. That's the gap.

- 2026-10-30 · **Storage split (William):** full transcripts stay private (local or a private repo, never on the site); the site stores only the signals; a private developer endpoint lets William dig into one coach/stat in depth to keep building profiles.
- 2026-10-30 · **Offense style doesn't need transcripts:** play-by-play has `home_coach`/`away_coach`, so pass rate, run gaps, pace, red zone tendencies per coach come free from nflverse. Transcripts only add the "what he says" half.
- 2026-10-30 · **To check before building:** cost of adding play-calling coordinators (OC/DC when they call plays). Tokens look cheap (~3× the head-coach volume); the real cost is finding transcripts per coordinator. Price it out in `docs/presser-sources.md`.

## Business model (later)

- 2026-10-29 · Mostly free: no-cost sign-up, most features free, tease paid features.
- 2026-10-29 · Paid tier idea: ~$5/mo includes Lab/Claude credit; extra credit packs. Stripe is 2.9% + 30¢, so $1 top-ups lose ~33% → minimum $5 packs (or $10 with a bonus). Price credits ~2–3× real Claude cost.
- 2026-10-29 · Credit ledger (every top-up and run is a row). Before a run, reserve worst-case cost (input + hard `max_tokens` cap); after, charge actual and refund the rest; block runs the balance can't cover.
- 2026-10-29 · Stack when it's time: Supabase or Clerk (auth + database + row-level security), Stripe Checkout + webhooks into the Cloudflare Worker, saved Lab filters per account. Start as an installable web app (PWA); Tauri for desktop later; avoid app stores at first (their payment rules/cuts).
- 2026-10-29 · Validate first: league mates + a few Reddit/Discord fantasy communities on the free version; if 10–20 people use it weekly without reminders, add payments. Build in the offseason, launch in July before draft season.

## Model + public site (decided 2026-10-30)

- **Two sites.** This one stays William's developer workbench (full SQL, every column). A separate public site later gets only what proved itself: Lab results that held up become one-click tools with a plain-English line. Start it after this roadmap is done.
- **Target = rest-of-season value, not next week's points.** Beating weekly projections is hard; ROS value is where a better schedule read pays off. Building blocks (each its own score, backtested on 2022–2025 before it goes in):
  - Defense vs play type: how each defense does against run gaps/directions, short/deep, by side, screens, play action.
  - Offense tendencies: how often the team runs those plays and how well it does on them.
  - Coaching: preferences weighted by the coach's trust score (said vs did) and his outlook on the player.
  - History vs similar defenses (cluster defenses by style, not just rank).
  - Availability: chance he plays, from presser/injury news + league-wide return times for similar injuries. Report a range, not one number (spread is wide; outliers are normal).
  - Depth chart and teammate injuries (who absorbs the work).
  - Individual defenders: what they allow by play type.
- **Proving it's better.** Lock each week's numbers in a git commit before kickoff (start once the model is ready). Compare against ESPN and Sleeper projections and a simple baseline (last-3-week average); xFP is an input, not a benchmark (it's calculated after the game). Score: average miss, rank order within each position, start/sit and trade calls right/wrong. Backtest + one live season before claiming anything.
- **Benchmarks are for comparison only.** Never republish ESPN/Sleeper numbers or differences on the site.
- **Premium = our score and tools, never raw stats.** nflverse is fine with credit; FTN stays free (CC-BY-SA); NGS (NFL) and PFR (Sports Reference) data have commercial limits, so don't sell features that are just those stats.
- **Competition:** strength-of-schedule tools are everywhere (ESPN/Mike Clay, PFF, CBS, Footballguys, Fantasy Footballers, Sharp Football, 4for4, RotoViz). Most rank defenses by fantasy points allowed per position; a few add scheme grades. FantasyPros grades experts' rankings every year. Gap: play-type matchups + coach signals + a public, locked track record.

## Decisions

- 2026-10-30 · Site version = `1.<PR number>`; shown bottom right on Home with a "Check for updates" button (`version.json`). Nav order: Home, Stats, Waivers, Compare, Lab, Guide. Trade page renamed **Compare** (URL stays `trade.html`). Column names: hover = description, click = sort (no more pop-up box); card tables sort too. Max 2 boxes on screen (open card + pop-outs).

- 2026-10-30 · **Navigation & sitemap done.** Shareable `?card=` links, back/swipe through cards, breadcrumb, game cards, pop-out windows, column chooser (hide all, drag to reorder on desktop), movable/resizable cards, keep a moved card when opening another, injury colors, NGS n/a. Optional `sitemap.xml` skipped for now.

- 2026-10-30 · Out-for-the-season rule (William): Sleeper still lists him IR/PUP/NFI/Out **and** this season's player news (Sleeper + ESPN feeds in the archive) says season-ending / out for the season about him. Ignores "could", "not", last-year mentions, and clears if newer news says designated to return / activated / back at practice.

- 2026-10-29 · This NFL version is the test run for MLB next season. After the NFL season, move to FPL (Premier League Fantasy).
- 2026-10-29 · MLB data (MLB Stats API, Statcast) is likely non-commercial-only; check terms before planning paid MLB features. FPL API is unofficial and the Premier League owns the data; fine free, check terms before charging.
- 2026-10-29 · Differentiators: presser signals, William's own metrics (backtested), much easier Lab, everything clickable/navigable, data-only outlooks that get graded.
- 2026-10-29 · Cards: drop-down + draggable pop-out windows (see docs/SITEMAP.md → Decided). Game card: both teams, Vegas line, weather, top fantasy scorers.
- 2026-10-29 · Whole-roster coverage added: kickers (Sleeper default kicker points), defensive players (box score + PFR pressures/coverage), offensive linemen. New Stats tabs (Defenders, O-line, Kickers), kicker/defender/lineman cards, K + DEF in Waivers search/filters, D/ST card shows pass rush, coverage and next opponent's O-line, Columns button inside cards.
- 2026-10-29 · O-line data limit: no free per-lineman pressures allowed (PFF film charting / NFL tracking data → ESPN Pass Block Win Rate, published only in articles). We use free team-level pressure/sack/YBC rates *with vs without* each lineman (games started vs not). nflverse participation data (on-field per play) isn't available for 2026.
- 2026-10-29 · Added optional "More stats" from NGS (separation, cushion, YAC over expected, RYOE, 8+ box %, time to LOS / throw, aggressiveness), FTN charting (drops, contested / catchable targets, created catches, play action, INT-worthy, throwaways, blitz %, pass rushers, box counts) and play-by-play (red zone / inside-10 / goal-line usage, deep targets, team EPA / success / 3rd down / RZ TD % / explosive plays both sides). FTN credit shown on Stats; FTN-derived stats must stay free (CC-BY-SA).
- 2026-10-29 · Fix: a week only counts as completed when every game in it is final (Thursday night no longer flips the site to next week).
- 2026-10-29 · Context lives in this repo (CLAUDE.md + ROADMAP.md + docs/), not a claude.ai Project.
