# CLAUDE.md — NFL_stats

William's fantasy football stats site. Static site on GitHub Pages, data from nflverse + Sleeper, refreshed by GitHub Actions. README.md has the page list, data pipeline and repo layout; read it before changing anything.

## How we work

- **One project at a time.** `ROADMAP.md` → "Now" holds the single active project. Finish it to a version William is happy with before starting the next. If a new idea comes up mid-project, log it in `ROADMAP.md` → "Ideas" and keep going on the current one.
- **Log important things without being asked.** When a decision is made, an idea comes up, a constraint is discovered, or something is ruled out, add a short dated line to the right section of `ROADMAP.md` (or the relevant `docs/` file) in the same change. Mention it in one line in the reply ("logged to ROADMAP → Ideas"). Don't log routine edits; git history covers those.
- **Start of a session:** read `ROADMAP.md` (Now + Decisions) so nothing has to be re-explained.
- William is on his phone a lot: keep replies short and concrete. Open PRs for review instead of pushing to `main`.

## Site rules

- **Static only.** HTML + vanilla JS + `assets/site.css`. No build step, no framework. Every page shares `assets/site.js` (nav, theme, league picker), `assets/cards.js` (player/defense cards), `assets/glossary.js` (stat descriptions).
- **Light mode is the default** (white/light backgrounds, high contrast, shaded sections). Dark is a toggle only.
- Every player/defense name should be clickable (`NFLSCards.pbtn` / `dbtn`, `data-card="p:<gsis_id>"` or `d:<TEAM>`). Every stat column header should go through the glossary.
- Data files the browser reads live in `data/site/` (compact JSON) and `data/lab/` (gzipped CSV for DuckDB). Keep them small; big files go to the `data-latest` release.
- **Cache busting:** pages load shared files as `assets/<file>?v=<version>`. Whenever you change anything in `assets/` (css/js), bump the version in every `.html` in the same change (one sed over `*.html`), or phones keep the old file.
- The Claude API key lives only in the Cloudflare Worker (`worker/ask-worker.js`), never in page code.

## Data & licensing (don't break these)

- nflverse data is CC-BY 4.0: keep the "Data: nflverse" credit. FTN charting is CC-BY-SA 4.0: credit "FTN Data via nflverse" and never put FTN-derived stats behind a paywall.
- No NFL/team logos, no NFL-owned headshots, nothing that looks official.
- Press conferences: store transcripts/captions as private inputs only. Publish our own summaries and structured signals, never the full transcript or video.
- Future paid features charge for *our* tools (Lab runs, custom metrics, alerts), never for raw stats.
