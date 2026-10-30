# ROADMAP

The plan for NFL_stats. Claude keeps this current (see CLAUDE.md → "How we work"). One active project at a time.

## Now

**Navigation & sitemap** — make everything inter-navigable. Plan in `docs/SITEMAP.md`.
Done when: every player/team/game has a link you can share or bookmark, phone back/swipe works through cards, there's a breadcrumb trail, and tables have a column chooser + sort everywhere.

## Next (in order, one at a time)

1. **Lab UX** — easier to understand and navigate. Preset filters people can click before they type; the Ask box for everyone else; suggested custom metrics as Lab filters.
2. **Custom metrics + backtests** — William's own filters/metrics, each with a one-line plain-English explanation and a backtest (does it predict next-week points better than a simple baseline like last-3-week average? if not, cut it). Seasons 2022–2025.
3. **Pressers** — head coach press conferences → structured per-player signals (player, topic, tone, short quote snippet). Feeds Trade/compare tabs and outlooks. See Pressers notes below.
4. **Statistical outlooks + grading** — AI outlooks built only from data (QB, defense, depth chart, draft position, presser sentiment, injuries, news), every claim tied to a data row. Save each week's projections, grade them after the games, learn why misses happened, publish accuracy.
5. **Monitor** — health checks with alerts (see Ideas).
6. **Accounts + payments** — after the NFL season. See Business model.

## Ideas (not scheduled)

- 2026-10-29 · **Bug to fix:** the stat description's "in the Guide" link opens the Guide but doesn't scroll to / select that stat (William, talk through 10/30).

- 2026-10-29 · **Monitor / health check:** GitHub Action every 12h (or daily). Checks: each team's presser source has something new within its expected window (skip bye weeks using the nflverse schedule); page structure still parses (title, date, body); nflverse data updated on time; sitemap pages load, no broken links. On failure, open a GitHub Issue naming the team, the check and the last success (GitHub app pushes it to William's phone). Log to `monitor/status.json`; maybe a small status page later. *Ideas only — don't build yet.*
- 2026-10-29 · Track coach reliability: over a season, did "he'll get a bigger role" actually happen? Weight each coach's signals by their track record.
- 2026-10-29 · Outlooks are the same for every user → generate once a week and cache. Only personal Lab runs cost credits.
- 2026-10-29 · Multi-league linking later: Sleeper (public API, already used) → Yahoo (official OAuth API) → ESPN (unofficial; private leagues need espn_s2/SWID cookies, store encrypted). MFL and Fleaflicker also have APIs. NFL Fantasy is shutting down and moving to ESPN.

## Pressers notes

- 2026-10-29 · YouTube's official API only returns captions for videos you own; scraping (yt-dlp etc.) is a terms-of-service gray area and often blocked from cloud runners. Not the main path.
- 2026-10-29 · Better: some teams post written transcripts on their own sites (e.g. patriots.com "Transcript: Head Coach … Press Conference"); fan sites like PatsFans fill gaps. Plan a 3-tier source per team: written transcript → captions from the team site's video player → flag for manual review. First step: sort all 32 teams into tiers in `docs/presser-sources.md`.
- 2026-10-29 · Cost is small (a ~20 min presser ≈ 5k tokens; 32/week is cheap). Current plan from earlier: weekly on Wednesdays, head coaches' latest presser only.
- 2026-10-29 · Existing competition: The Coachspeak Index (human-curated presser notes in a paid Discord/Patreon) and Sentitrac (news-sentiment projections). Nobody found doing automated per-player structured signals that get graded against results. That's the gap.

## Business model (later)

- 2026-10-29 · Mostly free: no-cost sign-up, most features free, tease paid features.
- 2026-10-29 · Paid tier idea: ~$5/mo includes Lab/Claude credit; extra credit packs. Stripe is 2.9% + 30¢, so $1 top-ups lose ~33% → minimum $5 packs (or $10 with a bonus). Price credits ~2–3× real Claude cost.
- 2026-10-29 · Credit ledger (every top-up and run is a row). Before a run, reserve worst-case cost (input + hard `max_tokens` cap); after, charge actual and refund the rest; block runs the balance can't cover.
- 2026-10-29 · Stack when it's time: Supabase or Clerk (auth + database + row-level security), Stripe Checkout + webhooks into the Cloudflare Worker, saved Lab filters per account. Start as an installable web app (PWA); Tauri for desktop later; avoid app stores at first (their payment rules/cuts).
- 2026-10-29 · Validate first: league mates + a few Reddit/Discord fantasy communities on the free version; if 10–20 people use it weekly without reminders, add payments. Build in the offseason, launch in July before draft season.

## Decisions

- 2026-10-29 · This NFL version is the test run for MLB next season. After the NFL season, move to FPL (Premier League Fantasy).
- 2026-10-29 · MLB data (MLB Stats API, Statcast) is likely non-commercial-only; check terms before planning paid MLB features. FPL API is unofficial and the Premier League owns the data; fine free, check terms before charging.
- 2026-10-29 · Differentiators: presser signals, William's own metrics (backtested), much easier Lab, everything clickable/navigable, data-only outlooks that get graded.
- 2026-10-29 · Cards: drop-down + draggable pop-out windows (see docs/SITEMAP.md → Decided). Game card: both teams, Vegas line, weather, top fantasy scorers.
- 2026-10-29 · Whole-roster coverage added: kickers (Sleeper default kicker points), defensive players (box score + PFR pressures/coverage), offensive linemen. New Stats tabs (Defenders, O-line, Kickers), kicker/defender/lineman cards, K + DEF in Waivers search/filters, D/ST card shows pass rush, coverage and next opponent's O-line, Columns button inside cards.
- 2026-10-29 · O-line data limit: no free per-lineman pressures allowed (PFF film charting / NFL tracking data → ESPN Pass Block Win Rate, published only in articles). We use free team-level pressure/sack/YBC rates *with vs without* each lineman (games started vs not). nflverse participation data (on-field per play) isn't available for 2026.
- 2026-10-29 · Context lives in this repo (CLAUDE.md + ROADMAP.md + docs/), not a claude.ai Project.
