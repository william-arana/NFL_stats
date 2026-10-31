/* Stat glossary: click a dotted-underlined stat name (table headers on Stats, Lab, Waivers, Trade) to see what it means.
   Descriptions come from the Guide (data/catalog.json, the nflverse data dictionary) plus plain-English notes for the
   stats this site calculates itself. Usage:  NFLSGloss.label(key, 'Label')  →  label HTML with a hover description (or plain label if unknown). */
(function(){
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  /* key: [name, description, guide field (dataset.field) or ''] */
  const S={
    /* ---- player usage & fantasy ---- */
    fp:['Fantasy points','Fantasy points in the scoring you picked (PPR, half or standard).','player_stats.fantasy_points_ppr'],
    ppr:['PPR points','PPR fantasy points: a point per reception plus yards and touchdowns.','player_stats.fantasy_points_ppr'],
    fpg:['FP per game','Fantasy points per game played, in the scoring you picked.','player_stats.fantasy_points_ppr'],
    xfp:['xFP (expected fantasy points)','Expected PPR points from usage: what an average player would score with the same targets, carries, depth of target and field position. Usage is steadier than points, so xFP predicts next week better than last week\'s score does.','ff_opportunity.total_fantasy_points_exp'],
    xfp_diff:['PPR − xFP','Actual PPR points minus expected. Big negative = unlucky or inefficient, often due for a bounce back. Big positive = scoring more than the usage supports (touchdown luck), may cool off.','ff_opportunity.total_fantasy_points_diff'],
    offense_pct:['Snap %','Percent of the team\'s offensive snaps the player was on the field. The first sign of a bigger role, before targets or carries show it.','snap_counts.offense_pct'],
    offense_snaps:['Offensive snaps','Number of snaps on offense.','snap_counts.offense_snaps'],
    target_share:['Target share','Player\'s share of the team\'s targets. 20%+ is a featured receiver; for RBs, 10%+ means a real passing-down role.','player_stats.target_share'],
    air_yards_share:['Air yards share','Player\'s share of the team\'s air yards (how far passes travel past the line of scrimmage, catch or not). Shows who gets the deep, valuable looks.','player_stats.air_yards_share'],
    opps:['Opportunities','Carries + targets per game: every chance to touch the ball.',''],
    tds:['Touchdowns','Passing + rushing + receiving touchdowns.','player_stats.rushing_tds'],
    trend:['Weekly FP','Fantasy points each week in the range you picked. The gray line is 10 points.',''],
    g:['Games','Games played in the selected weeks.',''],
    next:['Next opponent','Next week\'s opponent. The colored rank is how many PPR points that defense allows to the position: green = top-8 most allowed (good matchup), red = bottom-8.',''],
    /* ---- receiving ---- */
    targets:['Targets','The number of pass plays where the player was the targeted receiver.','player_stats.targets'],
    receptions:['Receptions','The number of pass receptions.','player_stats.receptions'],
    catch:['Catch %','Receptions ÷ targets.',''],
    receiving_yards:['Receiving yards','Yards gained after a pass reception.','player_stats.receiving_yards'],
    receiving_tds:['Receiving TDs','The number of touchdowns following a pass reception.','player_stats.receiving_tds'],
    receiving_air_yards:['Air yards','Receiving air yards, incomplete passes included: how far downfield the player was targeted.','player_stats.receiving_air_yards'],
    adot:['aDOT','Average depth of target: air yards per target. High = deep threat (boom/bust), low = short-area, catch-and-run role.',''],
    receiving_yards_after_catch:['YAC','Yards after the catch (unofficial stat; may differ slightly between sources).','player_stats.receiving_yards_after_catch'],
    wopr:['WOPR','Weighted Opportunity Rating: 1.5 × target share + 0.7 × air yards share. One number for a receiver\'s fantasy usage. 0.7+ is elite.','player_stats.wopr'],
    racr:['RACR','Receiving yards per air yard targeted. Above 1 = gains extra after the catch; below 1 = deep targets that often fall incomplete.','player_stats.racr'],
    receiving_epa:['Receiving EPA','Total expected points added on plays where this receiver was targeted. Positive = the offense got better when they threw his way.','player_stats.receiving_epa'],
    /* ---- rushing ---- */
    carries:['Rush attempts','The number of official rush attempts (carries), scrambles and kneel downs included.','player_stats.carries'],
    rushing_yards:['Rushing yards','Yards gained when rushing with the ball.','player_stats.rushing_yards'],
    ypc:['Yards per carry','Rushing yards ÷ carries.',''],
    rushing_tds:['Rushing TDs','The number of rushing touchdowns.','player_stats.rushing_tds'],
    rushing_first_downs:['Rushing first downs','First downs on rush attempts.','player_stats.rushing_first_downs'],
    ybc_att:['YBC per carry','Yards before contact per carry (PFR). Mostly the offensive line: how much room the runner gets before a defender touches him.','pfr_rush.rushing_yards_before_contact_avg'],
    yac_att:['YAC per carry','Yards after contact per carry (PFR). Mostly the runner: what he gains after the first hit.','pfr_rush.rushing_yards_after_contact_avg'],
    broken_tackles:['Broken tackles','Rushing + receiving broken tackles (PFR).','pfr_rush.rushing_broken_tackles'],
    rushing_epa:['Rushing EPA','Expected points added on rush attempts.','player_stats.rushing_epa'],
    fum:['Fumbles lost','Rushing + receiving + sack fumbles lost.','player_stats.rushing_fumbles_lost'],
    /* ---- passing ---- */
    completions:['Completions','The number of completed passes.','player_stats.completions'],
    attempts:['Pass attempts','The number of pass attempts as defined by the NFL.','player_stats.attempts'],
    passing_yards:['Passing yards','Yards gained on pass plays.','player_stats.passing_yards'],
    passing_tds:['Passing TDs','The number of passing touchdowns.','player_stats.passing_tds'],
    passing_interceptions:['Interceptions','Number of passing interceptions.','player_stats.passing_interceptions'],
    sacks_suffered:['Sacks taken','Number of sacks taken.','player_stats.sacks_suffered'],
    press_pct:['Pressured %','Times pressured ÷ dropbacks (PFR). Pressure kills fantasy production more than almost anything else for a QB.','pfr_pass.times_pressured'],
    qb_blitzed:['Times blitzed','Times the defense sent a blitz (PFR).','pfr_pass.times_blitzed'],
    passing_cpoe:['CPOE','Completion percentage over expected: completion % compared with what an average QB completes on the same throws (depth, coverage, pressure).','player_stats.passing_cpoe'],
    passing_epa:['Passing EPA','Total expected points added on pass attempts and sacks.','player_stats.passing_epa'],
    ypa:['Yards per attempt','Passing yards ÷ pass attempts.',''],
    /* ---- team offense (Teams tab) ---- */
    't:points_for':['Points scored','Points the team scored per game (or total).',''],
    't:total_yards':['Total yards','Passing + rushing yards gained by the offense.',''],
    't:passing_yards':['Pass yards','Yards the offense gained passing.','team_stats.passing_yards'],
    't:rushing_yards':['Rush yards','Yards the offense gained rushing.','team_stats.rushing_yards'],
    't:attempts':['Pass attempts','The offense\'s pass attempts.','team_stats.attempts'],
    't:carries':['Rush attempts','The offense\'s rush attempts (carries).','team_stats.carries'],
    pass_rate:['Pass %','Pass attempts ÷ (pass + rush attempts). Pass-heavy teams feed WRs and TEs; run-heavy teams feed the lead RB.',''],
    epa_play:['EPA per play','Expected points added per play (passes, runs and sacks). The best single measure of how good an offense is; 0 is average.',''],
    't:tds':['Offensive TDs','Passing + rushing touchdowns.',''],
    rec:['Record','Wins-losses in the selected weeks.',''],
    /* ---- team defense ---- */
    dst_pts:['D/ST points','Fantasy points for the defense in your Sleeper scoring: sack 1, INT 2, fumble recovery 2, forced fumble 1, TD 6, safety 2, blocked kick 2, plus points-allowed tiers.',''],
    points_against:['Points allowed','Points the defense gave up.',''],
    yards_allowed:['Yards allowed','Total yards (passing + rushing) the defense gave up.',''],
    pass_yards_allowed:['Pass yards allowed','Passing yards the defense gave up. High = good matchup for opposing QBs, WRs and TEs.',''],
    rush_yards_allowed:['Rush yards allowed','Rushing yards the defense gave up. High = good matchup for opposing RBs.',''],
    rush_att_allowed:['Rush attempts allowed','Carries opponents ran against this defense. Lots of carries usually means teams were winning and running out the clock against them.',''],
    ypc_allowed:['Yards per carry allowed','Rushing yards allowed ÷ carries faced. Separates a truly soft run defense from one that just faces a lot of runs.',''],
    pass_att_allowed:['Pass attempts allowed','Pass attempts opponents threw against this defense.',''],
    ypa_allowed:['Yards per pass allowed','Passing yards allowed ÷ pass attempts faced.',''],
    def_sacks:['Sacks','Sacks by the defense.','player_stats.def_sacks'],
    def_interceptions:['Interceptions','Interceptions by the defense.','player_stats.def_interceptions'],
    fumble_recovery_opp:['Fumble recoveries','Opponent fumbles the defense recovered.','player_stats.fumble_recovery_opp'],
    takeaways:['Takeaways','Interceptions + fumble recoveries.',''],
    epa_allowed:['EPA allowed','Expected points the defense gave up. Lower = better defense.',''],
    press_alw_pct:['Pressure % allowed','Times the QB was pressured ÷ dropbacks (PFR). The best single pass-blocking number available.',''],
    sack_alw_pct:['Sack % allowed','Sacks taken ÷ dropbacks.',''],
    pressures_allowed:['Pressures allowed','Times this team\'s QBs were pressured (PFR).','pfr_pass.times_pressured'],
    't:ybc_att':['YBC per carry','Yards before contact per carry (PFR): how much room the line creates for its runners.','pfr_rush.rushing_yards_before_contact_avg'],
    't:ypc':['Yards per carry','The offense\'s rushing yards ÷ carries.',''],
    rush_epa_play:['Rush EPA per play','Expected points added per run play.',''],
    def_pressures:['Pressures','Sum of defender pressures (hurries + hits + sacks, PFR). Pressure turns into sacks and turnovers.','pfr_def.def_pressures'],
    def_qb_hits:['QB hits','Times defenders hit the QB (not counting sacks).','player_stats.def_qb_hits'],
    def_blitzes:['Blitzes','Times the defense blitzed (PFR).',''],
    /* ---- defense vs position ---- */
    'dvp:QB':['QB points allowed','Fantasy points per game this defense allows to QBs. Higher = better matchup for the QB facing them. rk 1 = gives up the most.',''],
    'dvp:RB':['RB points allowed','Fantasy points per game this defense allows to RBs (rushing and receiving). rk 1 = gives up the most.',''],
    'dvp:WR':['WR points allowed','Fantasy points per game this defense allows to WRs. rk 1 = gives up the most.',''],
    'dvp:TE':['TE points allowed','Fantasy points per game this defense allows to TEs. rk 1 = gives up the most.',''],
    /* ---- waivers / trade ---- */
    score:['Waiver score','0.45 × expected points (last 3) + 0.20 × PPR (last 3) + 0.15 × snap-share change + 0.10 × touch change + 0.10 × next-week matchup, each as a z-score within the position. 0 = average, +1 = one standard deviation above.',''],
    xfp3:['xFP last 3','Expected PPR points per game over the last 3 weeks, from usage.','ff_opportunity.total_fantasy_points_exp'],
    ppr3:['PPR last 3','PPR points per game over the last 3 weeks.','player_stats.fantasy_points_ppr'],
    l3:['Last 3','Fantasy points per game over the last 3 weeks.',''],
    snap3:['Snap % last 3','Average offensive snap share over the last 3 weeks.','snap_counts.offense_pct'],
    snapD:['Snap Δ','Snap share over the last 3 weeks minus earlier in the season, in percentage points. A jump is the earliest sign of a new role.',''],
    opp3:['Touches last 3','Carries + targets per game over the last 3 weeks.',''],
    oppD:['Touch Δ','Carries + targets per game: last 3 weeks minus earlier in the season.',''],
    tgt3:['Target share last 3','Share of team targets over the last 3 weeks.','player_stats.target_share'],
    tgt:['Target share','Share of the team\'s targets this season.','player_stats.target_share'],
    best:['Best week','Highest single-week fantasy score.',''],
    sd:['Weekly swing','Standard deviation of weekly points. Lower = steadier floor; higher = boom/bust.',''],
    rank:['Position rank','Rank at the position by fantasy points per game (D/ST: by D/ST points).',''],
    left:['Games left','Games left on the schedule through the last week counted.',''],
    sos:['Rest-of-season SoS','Average rank of the remaining opponents. 1st = easiest (gives up the most to this position; for D/ST, opponents that score the fewest).',''],
    ros:['ROS points','Fantasy points per game × games left. Doesn\'t adjust for matchups, so read it with ROS SoS.',''],
    /* ---- Lab recipe columns ---- */
    depth:['Depth chart','Spot on the team\'s latest depth chart (RB1 = starter).','depth_charts.pos_rank'],
    starter_ahead:['Starter ahead','The player listed ahead of him at RB. If the starter misses time, this is whose work opens up.','depth_charts.pos_rank'],
    starter_injury:['Starter injury','The starter\'s latest injury report: game status if set, otherwise practice participation (DNP / Limited / Full).','injuries.report_status'],
    injury:['Injury','Latest injury report: game status (Out, Doubtful, Questionable) if set, otherwise practice participation (DNP / Limited / Full) and the injury.','injuries.report_status'],
    carry_share:['Carry share','Player\'s carries ÷ the team\'s carries. 60%+ is a workhorse; the backup\'s share shows how much he\'d inherit.',''],
    rush_att:['Rush attempts','Carries (official rush attempts).','player_stats.carries'],
    broken_tkl_per_100_touches:['Broken tackles per 100 touches','PFR broken tackles ÷ (carries + receptions) × 100. Creating yards on his own, separate from the line.','pfr_rush.rushing_broken_tackles'],
    ryoe:['Rush yards over expected','Next Gen Stats: rushing yards gained minus what an average back gains given blockers and defenders at handoff. Per attempt: +0.5 is very good. Only backs with enough carries that week are tracked.','nextgen.rush_yards_over_expected_per_att'],
    box8:['8+ in the box %','Next Gen Stats: how often the runner faced 8 or more defenders in the box. High = defenses selling out to stop him (tough sledding).','nextgen.percent_attempts_gte_eight_defenders'],
    separation:['Separation','Next Gen Stats: yards between the receiver and the nearest defender when the ball arrives. 3+ is getting open.','nextgen.avg_separation'],
    cushion:['Cushion','Next Gen Stats: yards between the receiver and the defender lined up on him at the snap.','nextgen.avg_cushion'],
    yac_over_exp:['YAC over expected','Next Gen Stats: yards after catch compared with expected YAC.','nextgen.avg_yac_above_expectation'],
    drops:['Drops','Dropped passes this season (PFR).','pfr_rec.receiving_drop'],
    yac_per_rec:['YAC per reception','Yards after the catch ÷ receptions.',''],
    team_implied_pts:['Team implied points','What Vegas expects the team to score next week, from the spread and over/under. More points = more fantasy points to go around.','schedules.total_line'],
    implied_pts:['Implied points','What Vegas expects the team to score, from the spread and over/under.','schedules.total_line'],
    earlier_vs_opp:['Earlier vs this opponent','If he already played next week\'s opponent this season: carries (or catches)-yards and PPR points in that game.',''],
    opp_rush_yds_alw:['Opp rush yards allowed','Rushing yards per game next week\'s opponent gives up.',''],
    opp_rush_yds_alw_rk:['Opp rush yards allowed rank','Next opponent\'s rank in rushing yards allowed per game. 1 = gives up the most (best matchup for a runner).',''],
    opp_ypc_alw:['Opp yards per carry allowed','Rushing yards ÷ carries against next week\'s opponent.',''],
    opp_ypc_alw_rk:['Opp YPC allowed rank','1 = allows the most yards per carry.',''],
    opp_rb_ppr_alw_rk:['Opp RB points allowed rank','Next opponent\'s rank in PPR points allowed to RBs per game. 1 = gives up the most.',''],
    opp_pass_yds_alw:['Opp pass yards allowed','Passing yards per game next week\'s opponent gives up.',''],
    opp_pass_yds_alw_rk:['Opp pass yards allowed rank','1 = gives up the most passing yards per game.',''],
    opp_ypa_alw:['Opp yards per pass allowed','Passing yards ÷ pass attempts against next week\'s opponent.',''],
    opp_pos_ppr_alw_rk:['Opp points allowed rank','Next opponent\'s rank in PPR points allowed to this position. 1 = gives up the most.',''],
    next_opp:['Next opponent','Next week\'s opponent.',''],
    matchup_score:['Matchup score','Sum of z-scores (standard deviations from league average). Positive = better than average.',''],
    final_number:['Final number','Weighted sum of z-scores: 1.0 × target share + 0.6 × air share + 1.0 × xFP + 0.4 × snap %. Edit the weights in the query.',''],
    dst_pts_per_g:['D/ST points per game','D/ST fantasy points per game in your Sleeper scoring.',''],
    pressures_per_g:['Pressures per game','Defender pressures per game (PFR).','pfr_def.def_pressures'],
    opp_pressures_allowed:['Opp pressures allowed','How often the opponent\'s QBs get pressured per game.',''],
    opp_sacks_allowed:['Opp sacks allowed','Sacks per game the opponent\'s line gives up.',''],
    opp_implied_pts:['Opp implied points','What Vegas expects the opponent to score. Low = good for a defense.','schedules.total_line'],
    vs_top_defenses:['vs top defenses','PPR per game against the third of defenses that allow the fewest points.',''],
    vs_middle:['vs middle defenses','PPR per game against the middle third of defenses.',''],
    vs_bottom_defenses:['vs bottom defenses','PPR per game against the third of defenses that allow the most points.',''],
    pressured_pct:['Pressured %','Times pressured ÷ dropbacks (PFR).','pfr_pass.times_pressured'],
    spread_line:['Spread','Positive = home team favored by that many points; negative = away team favored.','schedules.spread_line'],
    total_line:['Over/under','Vegas total points line for the game.','schedules.total_line'],
    status:['League status','fa = free agent, mine = on your team, taken = on another team.','']
  };
  /* other names for the same stat (Lab column names, abbreviations) */
  const ALIAS={snap:'offense_pct',snap_pct:'offense_pct',tgt_share:'target_share',air_share:'air_yards_share',xfp_per_g:'xfp',ppr_per_g:'ppr',ppr_minus_xfp:'xfp_diff',
    rush_yds:'rushing_yards',rec_yds:'receiving_yards',ybc_per_att:'ybc_att',yac_per_att:'yac_att',ryoe_per_att:'ryoe',box8_pct:'box8',catch_pct:'catch',
    carry_share_pct:'carry_share',tgt_share_pct:'target_share',air_share_pct:'air_yards_share',touches:'opps',fantasy_points_ppr:'ppr',fantasy_points:'fp',
    rush_att_per_g:'carries',rush_att_l3:'carries',targets_per_g:'targets',targets_l3:'targets',ybc:'ybc_att',yac_rush:'yac_att',opps_before:'opps',opps_recent:'opps',
    snap_pct_before:'offense_pct',snap_pct_recent:'offense_pct',snap_change:'snapD',xfp_recent:'xfp',ppr_recent:'ppr',sacks_per_g:'def_sacks',
    pass_epa_per_g:'passing_epa',opp_pressures_per_g:'def_pressures',faces:'next_opp',opponent:'next_opp',opp:'next_opp',defense:'dst_pts',g_vs_top:'g'};
  const MODS=[[/^(.*)_l3$/,'Last 3 weeks (or the recent_weeks setting).','last 3 weeks'],[/^(.*)_recent$/,'Last 3 weeks.','last 3 weeks'],[/^(.*)_before$/,'Before the last 3 weeks.','earlier'],
    [/^(.*)_per_g$/,'Per game.','per game'],[/^(.*)_pg$/,'Per game.','per game'],[/^(.*)_change$/,'Change: last 3 weeks minus earlier, in percentage points.','change'],[/^(.*)_pct$/,'Shown as a percent.','%'],[/^(.*)_rk$/,'Rank, 1 = most.','rank']];
  let CAT=null;const catP=fetch('data/catalog.json',{cache:'force-cache'}).then(r=>r.ok?r.json():null).then(j=>{if(!j)return;CAT=new Map();
    for(const d of j.datasets)for(const f of d.fields)if(!CAT.has(f.f)&&f.d)CAT.set(f.f,{d:f.d,ds:d.id,dn:d.name})}).catch(()=>{});
  function base(k){if(S[k])return {e:S[k]};if(ALIAS[k]&&S[ALIAS[k]])return {e:S[ALIAS[k]]};if(CAT&&CAT.has(k)){const c=CAT.get(k);return {e:[k,c.d,c.ds+'.'+k]}}return null}
  function lookup(key){
    if(key==null)return null;key=String(key);
    let b=base(key);if(b)return b.e;
    const k=key.replace(/^[a-z]+:/,'');if(k!==key){b=base(k);if(b)return b.e}
    const low=k.toLowerCase();b=base(low);if(b)return b.e;
    let pre='';let rest=low;if(rest.startsWith('opp_')){pre='Next opponent. ';rest=rest.slice(4)}
    const nm=n=>(pre?'Opp ':'')+n;
    b=base(rest);if(b)return [nm(b.e[0]),pre+b.e[1],b.e[2]];
    for(const [re,txt,short] of MODS){const m=rest.match(re);if(m){const bb=base(m[1])||base(m[1].replace(/_pct$/,''));if(bb)return [nm(bb.e[0])+' ('+short+')',(pre+txt+' '+bb.e[1]).trim(),bb.e[2]]}}
    return null;
  }
  function has(key){return !!lookup(key)}
  /* label HTML: dotted underline; hover shows the description (title), a click falls through to the header's sort */
  function label(key,text,tip){const e=lookup(key);if(!e&&!tip)return esc(text);
    return `<span class="gl" data-gl="${esc(key)}"${tip?` data-gltip="${esc(tip)}"`:''}${e?` title="${esc(tipText(e,text))}"`:tip?` title="${esc(tip)}"`:''}>${esc(text)}</span>`}
  const tipText=(e,shown)=>{const [name,desc]=e;return (String(name).toLowerCase()!==String(shown||'').trim().toLowerCase()?name+': ':'')+desc};
  /* descriptions from data/catalog.json arrive a moment later: fill the title in on first hover */
  document.addEventListener('mouseover',e=>{const g=e.target.closest&&e.target.closest('.gl');if(!g||g.title)return;
    const x=lookup(g.dataset.gl);if(x)g.title=tipText(x,g.textContent);else if(g.dataset.gltip)g.title=g.dataset.gltip});
  const close=()=>{};
  window.NFLSGloss={label,lookup,has,ready:catP,close};
})();
