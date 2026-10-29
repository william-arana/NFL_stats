import csv,json,re
D='nflreadr/data-raw/'
live=json.load(open('cols.json'))
def rcsv(f,delim=','):
    rows=list(csv.reader(open(D+f,encoding='utf-8-sig'),delimiter=delim))
    h=[x.strip().lower() for x in rows[0]]; out=[]
    fi=next(i for i,x in enumerate(h) if x in('field','field_name'))
    di=h.index('description'); ti=next((i for i,x in enumerate(h) if x in('type','data_type','field_type')),None)
    for r in rows[1:]:
        if len(r)<=di: continue
        out.append((r[fi].strip(),r[di].strip(),r[ti].strip() if ti is not None else ''))
    return out
def rjson(f): return [(x['field'],x['description'],x.get('data_type','')) for x in json.load(open(D+f))]
def cols(lst,desc={}): return [(c,desc.get(c,''),'') for c in lst]

NEW26={'passing_10':'Pass plays gaining 10+ yards','passing_16':'Pass plays gaining 16+ yards (threshold as published; new 2026 field)','passing_20':'Pass plays gaining 20+ yards','passing_40':'Pass plays gaining 40+ yards',
'rushing_10':'Rushes gaining 10+ yards','rushing_12':'Rushes gaining 12+ yards (new 2026 field)','rushing_20':'Rushes gaining 20+ yards','rushing_40':'Rushes gaining 40+ yards',
'receiving_10':'Receptions gaining 10+ yards','receiving_16':'Receptions gaining 16+ yards (new 2026 field)','receiving_20':'Receptions gaining 20+ yards','receiving_40':'Receptions gaining 40+ yards',
'pt_att':'Punts','pt_yards':'Gross punt yards','pt_net_yards':'Net punt yards','pt_long':'Longest punt','pt_inside_20':'Punts downed inside the 20','pt_touchback':'Punt touchbacks','pt_blocked':'Punts blocked','pt_returned':'Punts returned','pt_return_yards':'Punt return yards allowed','pt_return_tds':'Punt return TDs allowed','pt_fair_caught':'Punts fair caught','pt_downed':'Punts downed','pt_out_of_bounds':'Punts out of bounds',
'def_pat_blocks':'Extra points blocked','def_fg_blocks':'Field goals blocked','def_punt_blocks':'Punts blocked','def_2pt_atts':'Opponent 2-pt attempts defended','def_2pt_made':'Opponent 2-pt conversions allowed',
'fumbles_total':'Total fumbles','fumbles_lost_total':'Total fumbles lost','fumbles_forced_by_opp':'Fumbles forced by the opponent','fumbles_not_forced':'Unforced fumbles','fumbles_out_of_bounds':'Fumbles that went out of bounds','game_id':'nflverse game ID (season_week_away_home)'}
def add_new(base,livecols):
    have={f for f,_,_ in base}
    return base+[(c,NEW26.get(c,''),'new2026') for c in livecols if c not in have]

PFR={ # short desc for pfr season-level abbreviations
 'tm':'Team','pos':'Position','g':'Games','gs':'Games started','att':'Rush attempts','yds':'Yards','td':'Touchdowns','x1d':'First downs','ybc':'Yards before contact','ybc_att':'Yards before contact per attempt','yac':'Yards after contact / after catch','yac_att':'Yards after contact per attempt','brk_tkl':'Broken tackles','att_br':'Attempts per broken tackle','tgt':'Targets','rec':'Receptions','ybc_r':'Yards before catch per reception','yac_r':'Yards after catch per reception','adot':'Average depth of target','rec_br':'Receptions per broken tackle','drop':'Drops','drop_percent':'Drop %','int':'Interceptions (thrown when targeted / made on defense)','rat':'Passer rating when targeted / allowed','cmp':'Completions allowed','cmp_percent':'Completion % allowed','yds_cmp':'Yards allowed per completion','yds_tgt':'Yards allowed per target','dadot':'Average depth of target in coverage','air':'Air yards allowed on completions','bltz':'Times blitzed','hrry':'QB hurries','qbkd':'QB knockdowns','sk':'Sacks','prss':'Pressures','comb':'Combined tackles','m_tkl':'Missed tackles','m_tkl_percent':'Missed tackle %','bats':'Passes batted','loaded':'Date loaded','age':'Age','player':'Player name','pfr_id':'PFR player ID','season':'Season','pocket_time':'Average time in pocket','throwaways':'Throwaways','spikes':'Spikes','bad_throws':'Bad throws','bad_throw_pct':'Bad throw %','drops':'Drops by receivers','drop_pct':'Drop %','times_blitzed':'Times blitzed','times_hurried':'Times hurried','times_hit':'Times hit','times_pressured':'Times pressured','pressure_pct':'Pressure %','batted_balls':'Passes batted down','on_tgt_throws':'On-target throws','on_tgt_pct':'On-target %','rpo_plays':'RPO plays','rpo_yards':'RPO yards','rpo_pass_att':'RPO pass attempts','rpo_pass_yards':'RPO pass yards','rpo_rush_att':'RPO rush attempts','rpo_rush_yards':'RPO rush yards','pa_pass_att':'Play-action pass attempts','pa_pass_yards':'Play-action pass yards','intended_air_yards':'Intended air yards','intended_air_yards_per_pass_attempt':'Intended air yards per attempt','completed_air_yards':'Completed air yards','completed_air_yards_per_completion':'Completed air yards per completion','completed_air_yards_per_pass_attempt':'Completed air yards per attempt','pass_yards_after_catch':'YAC on completions','pass_yards_after_catch_per_completion':'YAC per completion','scrambles':'Scrambles','scramble_yards_per_attempt':'Scramble yards per attempt','team':'Team','pass_attempts':'Pass attempts'}
def pfrdesc(c):
    if c in PFR: return PFR[c]
    return c.replace('_',' ').replace('def ','defense: ').replace(' pct',' %').capitalize()

ffo=[(r['Field'],r['Description'],r['Type']) for r in csv.DictReader(open(D+'dictionary_ffopps.csv')) if 'weekly' in r['Dataframe']]

DS=[
# id, fn, name, family, start, grain, blurb, fields, note, tier
('player_stats','load_player_stats()','Player stats','Core box score',1999,'One row per player per week (or season)','Weekly box score for every offensive and defensive player: passing, rushing, receiving, fantasy points, target share, air yards share, WOPR, plus tackles, sacks and kicking.',add_new(rjson('dictionary_player_stats.json'),live['player_stats26']['cols']),'Best main tab for your sheet.',1),
('team_stats','load_team_stats()','Team stats','Core box score',1999,'One row per team per week (or season)','Same stats rolled up to the team: offense, defense, special teams, sacks suffered and made, turnovers, penalties.',add_new(rjson('dictionary_team_stats.json'),live['team_stats']['cols']),'Base for O-line vs. pass rush and defense matchups.',1),
('schedules','load_schedules()','Schedules & lines','Core box score',1999,'One row per game','Every game with the score, Vegas spread, over/under and moneylines, rest days, roof, surface, weather, coaches, starting QBs and referee.',rcsv('dictionary_schedules.csv'),'Spread + total give you implied team totals.',1),
('pbp','load_pbp()','Play-by-play','Play-level',1999,'One row per play','Every snap since 1999 with down, distance, field position, players involved, air yards, YAC, EPA, win probability, CPOE, penalties and much more. Every other stat can be built from it.',rcsv('dictionary_pbp.csv'),'Huge (~50k rows a season). Use it for custom splits, like red zone or 3rd-down usage.',2),
('ff_opportunity','load_ff_opportunity()','Expected fantasy points','Usage & opportunity',2006,'One row per player per week','Expected fantasy points, yards, TDs and first downs based on how the player was used (target depth, field position, etc.) next to actual output. The _diff columns show over- and under-performance.',ffo,'High expected points with low actual points = buy-low or waiver target.',1),
('snap_counts','load_snap_counts()','Snap counts','Usage & opportunity',2012,'One row per player per game','Offensive, defensive and special teams snaps and snap % from Pro Football Reference.',rcsv('dictionary_snap_counts.csv'),'Rising snap % is the earliest waiver signal.',1),
('participation','load_participation()','Participation','Usage & opportunity',2016,'One row per play','Who was on the field each play, plus offensive formation, personnel, defenders in box, number of pass rushers, coverage type (man/zone) and time to throw.',rcsv('dictionary_participation.csv'),'Only through the 2025 season. Not available for 2026 yet.',2),
('ftn_charting','load_ftn_charting()','FTN charting','Usage & opportunity',2022,'One row per play','Hand-charted details on every play: play action, RPO, screens, motion, blitzers, men in box, drops, catchable throws, contested catches, QB out of pocket.',rcsv('dictionary_ftn_charting.csv'),'Scheme detail: who gets screens, who gets schemed touches.',2),
('pfr_pass','load_pfr_advstats(stat_type="pass")','PFR advanced: passing','Advanced',2018,'Week or season level','Pressure, blitzes, hurries, hits, sacks taken, bad throws, drops, pocket time, play action and RPO splits.',[(c,pfrdesc(c),'') for c in dict.fromkeys(live['pfr_pass_week']+live['pfr_pass_season'])],'Pressure allowed to a QB = O-line weakness.',1),
('pfr_rush','load_pfr_advstats(stat_type="rush")','PFR advanced: rushing','Advanced',2018,'Week or season level','Yards before and after contact, broken tackles.',[(c,pfrdesc(c),'') for c in dict.fromkeys(live['pfr_rush_week']+live['pfr_rush_season'])],'Yards before contact tells you about the O-line; after contact is the RB.',2),
('pfr_rec','load_pfr_advstats(stat_type="rec")','PFR advanced: receiving','Advanced',2018,'Week or season level','ADOT, yards before and after catch, broken tackles, drops, INTs and passer rating when targeted.',[(c,pfrdesc(c),'') for c in dict.fromkeys(live['pfr_rec_week']+live['pfr_rec_season'])],'',2),
('pfr_def','load_pfr_advstats(stat_type="def")','PFR advanced: defense','Advanced',2018,'Week or season level','Per defender: pressures, hurries, QB knockdowns, sacks, blitzes, missed tackles, plus coverage stats (targets, completions, yards, rating allowed).',[(c,pfrdesc(c),'') for c in dict.fromkeys(live['pfr_def_week']+live['pfr_def_season'])],'Sum by team for a D/ST pressure rating.',1),
('nextgen','load_nextgen_stats()','Next Gen Stats','Advanced',2016,'One row per player per week (passing / rushing / receiving)','NFL player tracking: time to throw, aggressiveness, completion % over expected, rush yards over expected, 8+ in the box rate, separation, cushion, YAC over expected.',rcsv('dictionary_nextgenstats.csv',';'),'Only qualifying players appear each week.',2),
('espn_qbr','load_espn_qbr()','ESPN QBR','Advanced',2006,'One row per QB per week or season','ESPN Total QBR and its components (pass, run, sack, penalty EPA).',rcsv('dictionary_espn_qbr.csv'),'',3),
('injuries','load_injuries()','Injuries','Roster & context',2009,'One row per player per week','Official weekly injury report: practice participation and game status, with body part.',rcsv('dictionary_injuries.csv'),'Pair with depth charts to see who steps up.',1),
('depth_charts','load_depth_charts()','Depth charts','Roster & context',2001,'One row per player per team per week','Team depth chart position by week.',rcsv('dictionary_depth_charts.csv'),'',1),
('rosters','load_rosters() / load_rosters_weekly()','Rosters','Roster & context',1920,'One row per player per season (weekly from 2002)','Team, position, jersey, status (active, IR, practice squad), age, height, weight, college, experience, all player IDs.',rcsv('dictionary_rosters.csv'),'Weekly version catches call-ups and IR moves.',2),
('players','load_players()','Players','Roster & context',None,'One row per player','Master player table with bio and every ID.',rcsv('dictionary_players.csv'),'',3),
('ff_playerids','load_ff_playerids()','Fantasy player IDs','Fantasy tools',None,'One row per player','Maps one player across Sleeper, ESPN, Yahoo, MFL, Fleaflicker, PFR, Sportradar and more.',rcsv('dictionary_ff_playerids.csv'),'The bridge between Sleeper waivers and the stats.',1),
('ff_rankings','load_ff_rankings()','FantasyPros rankings','Fantasy tools',None,'One row per player per ranking page','Latest FantasyPros consensus ranks (redraft, dynasty, best ball) and weekly ECR.',rcsv('dictionary_ff_rankings.csv'),'Use as a benchmark against your own model.',3),
('combine','load_combine()','Combine','Other',2000,'One row per prospect','40 time, bench, vertical, broad jump, cone, shuttle, height, weight.',rcsv('dictionary_combine.csv'),'',3),
('draft_picks','load_draft_picks()','Draft picks','Other',1980,'One row per pick','Every draft pick with career stats summary (AV, games, Pro Bowls).',rcsv('dictionary_draft_picks.csv'),'',3),
('contracts','load_contracts()','Contracts','Other',None,'One row per contract','Historical contracts from OverTheCap: value, APY, guarantees.',rcsv('dictionary_contracts.csv'),'',3),
('trades','load_trades()','Trades','Other',2002,'One row per asset traded','NFL trades: who got what.',rcsv('dictionary_trades.csv'),'',3),
('officials','load_officials()','Officials','Other',2015,'One row per official per game','Which referee crew worked each game.',cols(live['officials']['cols'],{'official_name':'Official name','position':'Crew position (Referee, Umpire, etc.)','official_id':'Official ID','jersey_number':'Jersey number','game_key':'NFL game key'}),'Join to pbp for penalty tendencies by crew.',3),
('teams','load_teams()','Teams','Other',None,'One row per team','Team names, conference, division, colors and logos.',cols(live['teams']['cols']),'Handy for division and conference groupings.',3),
]

CAT_ORDER=['IDs & keys','Game & situation','Passing','Rushing','Receiving','Pass rush & pressure','Coverage & tackling','Turnovers','Expected & efficiency','Usage & snaps','Fantasy points & ranks','Special teams','Penalties','Vegas, rest & weather','Injury & roster','Player bio','Formation & scheme']
def cat(f,desc,ds):
    s=f.lower(); t=(f+' '+desc).lower()
    if ds in('injuries',) and not s.endswith('_id'): return 'Injury & roster'
    if ds in('combine','players','draft_picks','contracts') and not re.search(r'(^|_)id$|gsis|pfr_id|espn_id|_id$',s): return 'Player bio'
    if re.search(r'(^|_)(id|gsis|key)$|_id$|_ids$|^gsis|sportradar|^mfl|^sleeper|^espn_id|^yahoo|^fantasypros|^pff|^rotowire|^fleaflicker|^cbs|^nfl_id|^cfbref|^ktc|^stats_|^fantasy_data|^rotoworld|^swish|^pfr_player|^pfr_game|nflverse_game|old_game|^ftn_|^play_id|^drive$|^loaded$|^dt$|headshot|logo|wordmark|color',s): return 'IDs & keys'
    if re.search(r'(^|_)(name|first_name|last_name|display_name|short_name|football_name|mergename|merge_name)$|birth|^height$|^weight$|college|high_school|^age$|jersey|^draft_|years_exp|entry_year|rookie_year|twitter|image_url|player_filename|^player$',s) and ds not in ('trades',): return 'Player bio'
    if ds=='ff_rankings' and re.search(r'ecr|^sd$|best|worst|owned|rank_delta|^bye$|page_type|fp_page',s): return 'Fantasy points & ranks'
    if re.search(r'eight_defenders|in_box',s): return 'Formation & scheme'
    if s in('avg_time_to_los',): return 'Rushing'
    if s in('avg_cushion','avg_yac') : return 'Receiving'
    if s=='yards' and ds=='nextgen': return 'Receiving'
    if ds.startswith('pfr_') and s in('yds','td','yac','x1d','att','tgt','rec','int','g','gs'):
        return {'pfr_rush':'Rushing','pfr_rec':'Receiving','pfr_def':'Coverage & tackling','pfr_pass':'Passing'}[ds] if s not in('g','gs') else 'Usage & snaps'
    if ds=='pfr_def' and s.startswith('def_') and not re.search(r'blitz|hurr|hit|sack|pressur',s): return 'Coverage & tackling'
    if re.search(r'^def_2pt|^def_.*blocks$',s): return 'Special teams'
    if re.search(r'_2pt_|two_point',s) and not s.startswith('def_'):
        return 'Passing' if s.startswith('pass') else 'Rushing' if s.startswith('rush') else 'Receiving' if s.startswith('rec') else 'Game & situation'
    if re.search(r'spread|total_line|moneyline|odds|^temp|wind|roof|surface|weather|stadium|_rest$|div_game|^stadium$',s): return 'Vegas, rest & weather'
    if re.search(r'penalt|^flag',s): return 'Penalties'
    if ds in('participation','ftn_charting') or re.search(r'formation|personnel|motion|play_action|_pa_|^pa_|rpo|screen|shotgun|no_huddle|huddle|in_box|box|coverage|route|blitz.*count|n_pass_rush|number_of_pass_rushers|is_qb_out|out_of_pocket|read_thrown|qb_location|offense_players|defense_players|defenders_in',s): return 'Formation & scheme'
    if re.search(r'fantasy',s): return 'Fantasy points & ranks'
    if re.search(r'_prob$|^xyac|^cp$|^xpass|pass_oe|_exp$|_exp_|_diff|epa|wpa|^wp$|_wp|^ep$|cpoe|qbr|over_expected|above_expect|expected|efficiency|success|aggressiveness|_rating|passer_rating|pacr|racr|dakota|^rat$|^vegas',s): return 'Expected & efficiency'
    if re.search(r'snap|offense_pct|defense_pct|st_pct|target_share|air_yards_share|wopr|_share|^pos(team)?_|position|depth|status|roster|team$|^tm$|^team|_team$',s) and ds in('snap_counts','depth_charts','rosters','ff_playerids','ff_rankings') : return 'Usage & snaps' if ds=='snap_counts' else 'Injury & roster'
    if re.search(r'snap|target_share|air_yards_share|wopr',s): return 'Usage & snaps'
    if re.search(r'(^|_)sack|pressur|hurr|hit|qbkd|knockdown|blitz|bltz|hrry|prss|^sk$|pocket|time_to_throw|time_to_los|batted|bats',s): return 'Pass rush & pressure'
    if re.search(r'tackl|tkl|^comb$|coverage|_allowed|^def_targets|^tgt$|cushion|^def_int|^def_pass_def|pass_defended|cmp_percent|yds_cmp|yds_tgt|dadot|def_adot|def_air|^air$',s) and (ds.startswith('pfr_def') or s.startswith('def_') or ds=='pbp' or 'tackl' in s): return 'Coverage & tackling'
    if re.search(r'interception|(^|_)int$|_ints$|fumble|turnover',s): return 'Turnovers'
    if re.search(r'punt|kick|^fg|_fg|^pat|^pt_|return|touchback|field_goal|extra_point|gwfg|safety',s): return 'Special teams'
    if re.search(r'^pass(ing)?_',s) and 'fantasy' not in s: return 'Passing'
    if re.search(r'recei|^rec_|^rec$|target|catch|separation|^adot$|^ybc_r|^yac_r|^drop|receptions|reception',s): return 'Receiving'
    if re.search(r'rush|carr|^att$|^ybc|^yac_att|brk|broken|scrambl|^att_br|run_',s): return 'Rushing'
    if re.search(r'pass|complet|attempt|air_yards|^cmp|throw|throwaway|spike|on_tgt|qb_|interc|air_distance',s): return 'Passing'
    if re.search(r'^(season|week|game|home|away|posteam|defteam|side|yard|down|ydstogo|goal|quarter|qtr|half|time|drive|score|result|location|play_type|desc|game_date|start_time|weekday|gameday|gametime|season_type|game_type|stadium|opponent|referee|coach|.*_coach|end_|fixed|series|order|nfl_api|replay|aborted|timeout|total$|overtime|first_down|third_down|fourth_down|td_|touchdown|^td$|^yds$|^x1d$|^tm$|^g$|^gs$|player|full_name|first_name|last_name|position|pos$|^name|team|^tm)',s): return 'Game & situation'
    if re.search(r'yard|yds',s): return 'Game & situation'
    return 'Game & situation'

out=[]
for (i,fn,name,fam,start,grain,blurb,fields,note,tier) in DS:
    seen=set();F=[]
    for f,desc,typ in fields:
        if not f or f in seen: continue
        seen.add(f); F.append({'f':f,'d':re.sub(r'\s+',' ',desc).strip(),'c':cat(f,desc,i),'n':typ=='new2026'})
    out.append({'id':i,'fn':fn,'name':name,'family':fam,'start':start,'grain':grain,'blurb':blurb,'note':note,'tier':tier,'fields':F})
KEY={'player_stats':['targets','carries','target_share','air_yards_share','wopr','receiving_air_yards','fantasy_points_ppr','sacks_suffered','passing_cpoe','racr','def_sacks','def_qb_hits','def_interceptions'],
'team_stats':['sacks_suffered','def_sacks','def_qb_hits','def_interceptions','def_fumbles','passing_epa','rushing_epa','attempts','carries'],
'schedules':['spread_line','total_line','home_rest','away_rest','roof','wind','temp'],
'pbp':['epa','cpoe','air_yards','yardline_100','down','xpass','pass_oe','success','qb_hit','sack'],
'ff_opportunity':['total_fantasy_points_exp','total_fantasy_points_diff','rec_fantasy_points_exp','rush_fantasy_points_exp','rec_attempt_team','rush_attempt_team','rec_air_yards'],
'snap_counts':['offense_pct','offense_snaps','defense_pct'],
'participation':['was_pressure','route','number_of_pass_rushers','defense_coverage_type','defense_man_zone_type','time_to_throw','offense_personnel'],
'ftn_charting':['is_motion','is_qb_fault_sack','is_screen_pass','is_play_action','n_blitzers','n_pass_rushers','n_defense_box','is_catchable_ball','is_qb_out_of_pocket'],
'pfr_pass':['times_pressured','times_pressured_pct','pressure_pct','times_blitzed','pocket_time','times_hit'],
'pfr_rush':['rushing_yards_before_contact_avg','rushing_yards_after_contact_avg','rushing_broken_tackles'],
'pfr_rec':['adot','yac_r','drop_percent'],
'pfr_def':['def_pressures','def_times_hurried','def_times_hitqb','def_sacks','def_missed_tackle_pct','def_passer_rating_allowed','prss'],
'nextgen':['avg_time_to_throw','completion_percentage_above_expectation','rush_yards_over_expected_per_att','avg_separation','percent_share_of_intended_air_yards','avg_yac_above_expectation','percent_attempts_gte_eight_defenders'],
'injuries':['report_status','practice_status','report_primary_injury'],
'depth_charts':['pos_abb','pos_rank'],
'ff_playerids':['sleeper_id','gsis_id','espn_id'],
'ff_rankings':['ecr','player_owned_avg']}
for d in out:
    for x in d['fields']: x['k']=x['f'] in KEY.get(d['id'],[])
json.dump({'cats':CAT_ORDER,'datasets':out},open('catalog.json','w'),separators=(',',':'))
from collections import Counter
print(sum(len(d['fields']) for d in out))
for d in out: print(d['id'],len(d['fields']),Counter(x['c'] for x in d['fields']).most_common(6))
print(Counter(x['c'] for d in out for x in d['fields']))
