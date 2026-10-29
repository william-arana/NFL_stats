import nflreadpy as nfl, json
out={}
for st in ["pass","rush","rec","def"]:
    for sl in ["week","season"]:
        try:
            df=nfl.load_pfr_advstats(seasons=[2025],stat_type=st,summary_level=sl)
            out[f"pfr_{st}_{sl}"]=df.columns
        except Exception as e: out[f"pfr_{st}_{sl}"]=str(e)[:200]
for name,fn in [("officials",lambda: nfl.load_officials(seasons=[2025])),("teams",nfl.load_teams),("team_stats",lambda: nfl.load_team_stats(seasons=[2026])),("player_stats26",lambda: nfl.load_player_stats(seasons=[2026])),("ngs_pass",lambda: nfl.load_nextgen_stats(seasons=[2026],stat_type="passing")),("ngs_rush",lambda: nfl.load_nextgen_stats(seasons=[2026],stat_type="rushing")),("ngs_rec",lambda: nfl.load_nextgen_stats(seasons=[2026],stat_type="receiving")),("participation26",lambda: nfl.load_participation(seasons=[2026])),("ftn26",lambda: nfl.load_ftn_charting(seasons=[2026])),("ffopp26",lambda: nfl.load_ff_opportunity(seasons=[2026])),("snap26",lambda: nfl.load_snap_counts(seasons=[2026])),("injuries26",lambda: nfl.load_injuries(seasons=[2026])),("pfr_pass_2026",lambda: nfl.load_pfr_advstats(seasons=[2026],stat_type="pass",summary_level="week"))]:
    try:
        df=fn(); out[name]={"cols":df.columns,"rows":df.height,"maxweek":(int(df["week"].max()) if "week" in df.columns and df.height else None)}
    except Exception as e: out[name]=str(e)[:200]
json.dump(out,open("cols.json","w"),indent=1)
