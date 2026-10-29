/* Shared nav tools for every NFL_stats page: theme toggle, league picker, Sleeper roster lookups. */
(function(){
  const LS={get(k){try{return localStorage.getItem('nfls-'+k)}catch(e){return null}},set(k,v){try{localStorage.setItem('nfls-'+k,v)}catch(e){}}};
  const root=document.documentElement;
  const SUN='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const MOON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
  const listeners=[];let leagueCfg=null,leagueId=LS.get('league');
  const cache={};

  function setTheme(t){if(t==='dark')root.dataset.theme='dark';else delete root.dataset.theme;LS.set('theme',t);paintThemeBtn();window.dispatchEvent(new Event('nfls-theme'))}
  function paintThemeBtn(){const b=document.getElementById('theme-btn');if(!b)return;const dark=root.dataset.theme==='dark';b.innerHTML=(dark?SUN:MOON)+(dark?'Light':'Dark');b.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode')}

  function loadLeagues(){
    if(leagueCfg)return Promise.resolve(leagueCfg);
    return fetch('data/site/leagues.json',{cache:'no-cache'}).then(r=>r.ok?r.json():Promise.reject()).then(j=>({snapshot:j,leagues:j.leagues}))
      .catch(()=>fetch('data/leagues.json').then(r=>r.json()).then(j=>({snapshot:null,leagues:j.leagues})))
      .then(c=>{leagueCfg=c;if(!leagueId||(leagueId!=='none'&&!c.leagues.some(l=>l.id===leagueId))){const d=c.leagues.find(l=>l.default)||c.leagues[0];leagueId=d?d.id:'none'}return c});
  }
  function getLeague(){return leagueCfg&&leagueCfg.leagues.find(l=>l.id===leagueId)||null}

  /* Who is rostered in a league. Tries Sleeper live first, then the snapshot the GitHub Action saves. */
  function rosterStatus(id){
    id=id||leagueId;if(!id||id==='none')return Promise.resolve(null);
    if(cache[id])return cache[id];
    const cfg=leagueCfg.leagues.find(l=>l.id===id);
    const snap=leagueCfg.snapshot&&leagueCfg.snapshot.leagues.find(l=>l.id===id);
    const build=(rosters,source,updated)=>{const map=new Map();for(const r of rosters){const mine=r.roster_id===cfg.my_roster_id;for(const k of r.players)map.set(k,{status:mine?'mine':'taken',team:r.team_name,roster_id:r.roster_id})}
      return {league:cfg,map,source,updated,rosters,status:k=>map.has(k)?map.get(k).status:'fa'}};
    const ctl=new AbortController();const to=setTimeout(()=>ctl.abort(),6000);
    const live=Promise.all([
      fetch(`https://api.sleeper.app/v1/league/${id}/rosters`,{signal:ctl.signal}).then(r=>r.ok?r.json():Promise.reject()),
      fetch(`https://api.sleeper.app/v1/league/${id}/users`,{signal:ctl.signal}).then(r=>r.ok?r.json():Promise.reject()),
      fetch('data/site/sleeper_map.json',{cache:'no-cache'}).then(r=>r.ok?r.json():Promise.reject())
    ]).then(([rs,us,sm])=>{clearTimeout(to);const users=Object.fromEntries(us.map(u=>[u.user_id,u]));const fix=sm.team_fix||{};
      const key=s=>sm.map[s]||(/^[A-Z]{2,3}$/.test(s)?'DEF:'+(fix[s]||s):null);
      return build(rs.map(r=>{const u=users[r.owner_id]||{};return {roster_id:r.roster_id,team_name:(u.metadata&&u.metadata.team_name)||u.display_name||('Team '+r.roster_id),players:(r.players||[]).map(key).filter(Boolean)}}),'live',new Date().toISOString())});
    cache[id]=live.catch(()=>{clearTimeout(to);return snap?build(snap.rosters,'snapshot',leagueCfg.snapshot.updated_utc):null});
    return cache[id];
  }

  function mount(){
    const host=document.getElementById('navtools');if(!host)return;
    host.innerHTML=`<label for="league-sel">League</label><select id="league-sel" aria-label="League"></select><button class="theme" id="theme-btn" type="button"></button>`;
    paintThemeBtn();
    document.getElementById('theme-btn').onclick=()=>setTheme(root.dataset.theme==='dark'?'light':'dark');
    loadLeagues().then(c=>{const sel=document.getElementById('league-sel');
      sel.innerHTML=c.leagues.map(l=>`<option value="${l.id}">${l.name} (${l.teams})</option>`).join('')+'<option value="none">No league</option>';
      sel.value=leagueId;
      sel.onchange=()=>{leagueId=sel.value;LS.set('league',leagueId);listeners.forEach(f=>f(getLeague()))};
      listeners.forEach(f=>f(getLeague()));
    });
  }
  window.NFLS={setTheme,loadLeagues,getLeague,rosterStatus,onLeague(cb){listeners.push(cb);if(leagueCfg)cb(getLeague())}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
