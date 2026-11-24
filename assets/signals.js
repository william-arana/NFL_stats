/* Shared usage numbers + signal filters for free-agent lists (Waivers, the private Yahoo page).
   Only signals that held up in our backtests (notes repo, docs/backtests):
     role   RB/WR/TE  snap share +15 pts or +3 touches/game, last 3 games vs before   (usage-metrics: snap/opp-share trends)
     buy    RB/WR/TE  expected points beat actual points by 3+, last 3 games            (usage-metrics: xFP)
     depth  RB/WR     our projection adds points because a regular ahead of him is out (depth-vacated)
     imp    QB        his team is a top-8 Vegas implied total this week                 (streamers-implied: QBs only)
   Left out on purpose: soft matchups / defense vs position (matchup ratings didn't predict). */
(function () {
  const num = v => typeof v === 'number' && isFinite(v);
  const mean = a => { const b = a.filter(num); return b.length ? b.reduce((x, y) => x + y, 0) / b.length : null };

  /* A game counts if he played >=10% of snaps and didn't leave early hurt.
     Early exit = under half his usual (median) snap share AND he then missed his team's next game,
     or it's his latest game and he's on this week's injury report. */
  function qualify(logs, META, G, inj) {
    const lw = META.last_completed_week;
    const real = [...logs].sort((x, y) => x.week - y.week).filter(l => num(l.offense_pct) && l.offense_pct >= 0.10);
    const v = real.map(l => l.offense_pct).sort((x, y) => x - y), med = v.length ? v[Math.floor((v.length - 1) / 2)] : 0;
    const played = new Set(real.map(l => l.week));
    const teamNext = (team, wk) => { let n = null; for (const g of G) if ((g.home_team === team || g.away_team === team) && g.week > wk && g.week <= lw && (n == null || g.week < n)) n = g.week; return n };
    return real.filter(l => {
      if (l.offense_pct >= 0.5 * med) return true;
      const nw = teamNext(l.team, l.week);
      if (nw != null) return played.has(nw);
      return !(inj && /out|ir|doubtful|questionable|limited|did not/i.test(inj[0]));
    });
  }

  /* L3 = his last 3 games that count within the last 6 weeks; trends need 2+ counted games on both sides */
  function usage(logs, META, G, inj) {
    const lw = META.last_completed_week;
    const q = qualify(logs, META, G, inj), rec = q.filter(l => l.week > lw - 6).slice(-3), bef = q.filter(l => !rec.includes(l));
    const o = {
      q3: rec.length,
      ppr3: mean(rec.map(l => l.fantasy_points_ppr)), xfp3: mean(rec.map(l => l.xfp)),
      snap3: mean(rec.map(l => l.offense_pct)), snapB: mean(bef.map(l => l.offense_pct)),
      opp3: mean(rec.map(l => (l.carries || 0) + (l.targets || 0))), oppB: mean(bef.map(l => (l.carries || 0) + (l.targets || 0))),
      tgt3: mean(rec.map(l => l.target_share)),
    };
    if (rec.length < 2) o.ppr3 = o.xfp3 = null; // one game isn't enough to rank him
    const okD = rec.length >= 2 && bef.length >= 2;
    o.snapD = okD && num(o.snap3) && num(o.snapB) ? o.snap3 - o.snapB : null;
    o.oppD = okD && num(o.opp3) && num(o.oppB) ? o.opp3 - o.oppB : null;
    return o;
  }

  /* this week's implied-total rank per team (1 = highest) */
  function impliedRanks(G, week) {
    const imp = [];
    for (const g of G) if (g.week === week) { if (num(g.home_implied)) imp.push([g.home_team, g.home_implied]); if (num(g.away_implied)) imp.push([g.away_team, g.away_implied]) }
    imp.sort((a, b) => b[1] - a[1]);
    return Object.fromEntries(imp.map(([t], i) => [t, i + 1]));
  }

  const DEFS = [
    { k: 'role', label: 'Role up', pos: ['RB', 'WR', 'TE'], title: 'Snap share up 15+ points or 3+ more touches a game, last 3 games vs earlier. Usage trends held up in our backtest for RB/WR/TE.' },
    { k: 'buy', label: 'Buy low', pos: ['RB', 'WR', 'TE'], title: 'Expected points (from his usage) beat his actual points by 3+ a game over his last 3. Expected points predicted next week better than actual points in our backtest.' },
    { k: 'depth', label: 'Depth bump', pos: ['RB', 'WR'], title: 'Our projection adds points because a regular ahead of him is Out/IR/released. Held up in our 2019–2026 backtest.' },
    { k: 'imp', label: 'High implied', pos: ['QB'], title: "His team is a top-8 Vegas implied total this week. For waiver-tier QBs that was the strongest single input in our backtest (no edge for RB/WR)." },
  ];

  /* a = {id, pos, team, snapD, oppD, xfp3, ppr3}; ctx = {PROJ, META, irk} */
  function tags(a, ctx) {
    const out = [];
    if (['RB', 'WR', 'TE'].includes(a.pos)) {
      if ((num(a.snapD) && a.snapD >= 0.15) || (num(a.oppD) && a.oppD >= 3)) out.push('role');
      if (num(a.xfp3) && num(a.ppr3) && a.xfp3 - a.ppr3 >= 3) out.push('buy');
    }
    const P = ctx.PROJ, dp = P && P.dp && ctx.META && P.week === ctx.META.next_week ? P.dp[a.id] : null;
    if (['RB', 'WR'].includes(a.pos) && dp && dp[0] > 0) out.push('depth');
    if (a.pos === 'QB' && ctx.irk && ctx.irk[a.team] && ctx.irk[a.team] <= 8) out.push('imp');
    return out;
  }

  /* chip row: extra = [{k,label,title}] page-specific chips; on = Set of active keys; counts = {k: n} */
  function chipsHTML(on, counts, extra) {
    const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    return `<div class="sigchips" role="group" aria-label="Signal filters"><span class="sig-l">Signals</span>${[...DEFS, ...(extra || [])].map(d =>
      `<button type="button" data-sig="${d.k}" aria-pressed="${on.has(d.k)}" title="${esc(d.title)}">${esc(d.label)}<small>${counts && counts[d.k] != null ? counts[d.k] : ''}</small></button>`).join('')
      }${on.size ? '<button type="button" data-sig="" class="sig-clear">Clear</button>' : ''}</div>`;
  }

  window.NFLSSignals = { usage, qualify, impliedRanks, tags, chipsHTML, DEFS };
})();
