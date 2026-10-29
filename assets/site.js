/* Shared nav tools for every NFL_stats page: theme toggle, league + team picker, Sleeper roster lookups,
   and the little "open player" link menu. */
(function(){
  const LS={get(k){try{return localStorage.getItem('nfls-'+k)}catch(e){return null}},set(k,v){try{localStorage.setItem('nfls-'+k,v)}catch(e){}}};
  const root=document.documentElement;
  const SUN='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const MOON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
  const EXT='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const listeners=[];let leagueCfg=null;
  /* selection = "leagueId|rosterId" (or "none"); older saves held just the league id */
  let sel=LS.get('league');
  const cache={};

  function setTheme(t){if(t==='dark')root.dataset.theme='dark';else delete root.dataset.theme;LS.set('theme',t);paintThemeBtn();window.dispatchEvent(new Event('nfls-theme'))}
  function paintThemeBtn(){const b=document.getElementById('theme-btn');if(!b)return;const dark=root.dataset.theme==='dark';b.innerHTML=(dark?SUN:MOON)+(dark?'Light':'Dark');b.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode')}

  function loadLeagues(){
    if(leagueCfg)return Promise.resolve(leagueCfg);
    const cfgP=fetch('data/leagues.json',{cache:'no-cache'}).then(r=>r.json()).catch(()=>({leagues:[]}));
    const snapP=fetch('data/site/leagues.json',{cache:'no-cache'}).then(r=>r.ok?r.json():null).catch(()=>null);
    return Promise.all([cfgP,snapP]).then(([cfg,snap])=>{
      const leagues=cfg.leagues.map(l=>{const s=snap&&snap.leagues.find(x=>x.id===l.id);const name=rid=>{const r=s&&s.rosters.find(x=>x.roster_id===rid);return r?r.team_name.trim():null};
        const viewers=(l.viewers&&l.viewers.length?l.viewers:[{roster_id:l.my_roster_id}]).map(v=>({roster_id:v.roster_id,label:v.label||name(v.roster_id)||('Team '+v.roster_id)}));
        return {...l,viewers}});
      leagueCfg={snapshot:snap,leagues};
      const opts=allOptions();if(!sel||!opts.some(o=>o.value===sel)){const legacy=sel&&opts.find(o=>o.value.split('|')[0]===sel);const d=legacy||opts.find(o=>o.def)||opts[0];sel=d?d.value:'none'}
      return leagueCfg;
    });
  }
  function allOptions(){const out=[];for(const l of leagueCfg.leagues)for(const v of l.viewers)out.push({value:l.id+'|'+v.roster_id,label:`${l.name} · ${v.label}`,def:l.default&&v.roster_id===l.my_roster_id,group:l.name});return out}
  /* the selected league, with my_roster_id set to whichever team you're viewing as */
  function getLeague(){if(!leagueCfg||!sel||sel==='none')return null;const [id,rid]=sel.split('|');const l=leagueCfg.leagues.find(x=>x.id===id);if(!l)return null;
    const v=l.viewers.find(x=>String(x.roster_id)===rid)||l.viewers[0];return {...l,my_roster_id:v.roster_id,viewer:v.label}}

  /* Who is rostered in a league. Tries Sleeper live first, then the snapshot the GitHub Action saves. */
  function rosterStatus(){
    const cfg=getLeague();if(!cfg)return Promise.resolve(null);const id=cfg.id,key=id+'|'+cfg.my_roster_id;
    if(cache[key])return cache[key];
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
      return build(rs.map(r=>{const u=users[r.owner_id]||{};return {roster_id:r.roster_id,team_name:((u.metadata&&u.metadata.team_name)||u.display_name||('Team '+r.roster_id)).trim(),players:(r.players||[]).map(key).filter(Boolean)}}),'live',new Date().toISOString())});
    cache[key]=live.catch(()=>{clearTimeout(to);return snap?build(snap.rosters,'snapshot',leagueCfg.snapshot.updated_utc):null});
    return cache[key];
  }

  function mount(){
    const host=document.getElementById('navtools');if(!host)return;
    host.innerHTML=`<label for="league-sel">Team</label><select id="league-sel" aria-label="League and team"></select><button class="theme" id="theme-btn" type="button"></button>`;
    paintThemeBtn();
    document.getElementById('theme-btn').onclick=()=>setTheme(root.dataset.theme==='dark'?'light':'dark');
    loadLeagues().then(()=>{const s=document.getElementById('league-sel');const opts=allOptions();const groups=[...new Set(opts.map(o=>o.group))];
      s.innerHTML=groups.map(g=>`<optgroup label="${esc(g)}">${opts.filter(o=>o.group===g).map(o=>`<option value="${o.value}">${esc(o.label)}</option>`).join('')}</optgroup>`).join('')+'<option value="none">No league</option>';
      s.value=sel;
      s.onchange=()=>{sel=s.value;LS.set('league',sel);listeners.forEach(f=>f(getLeague()))};
      listeners.forEach(f=>f(getLeague()));
    });
  }

  /* Sleeper has no public page per player, so links open the league's Players tab; the link menu copies the name first. */
  function leagueUrl(lg){return lg?`https://sleeper.com/leagues/${lg.id}/players`:'https://sleeper.com'}
  function badge(status,lg,name){if(!status||!lg)return '';const t=status==='fa'?'FA':status==='mine'?'MINE':'';if(!t)return '';
    const tip=status==='fa'?`Free agent in ${lg.name}. Opens ${lg.name} players on Sleeper`:`On ${lg.viewer||'your'} roster in ${lg.name}. Opens Sleeper`;
    return `<a class="av ${status}" href="${leagueUrl(lg)}" target="_blank" rel="noopener" title="${esc(tip)}">${t}</a>`}

  /* "open player" link: small icon after a name; opens a menu with Sleeper, ESPN and copy-name */
  let IDS=null;const idsP=()=>IDS?Promise.resolve(IDS):fetch('data/site/ids.json',{cache:'no-cache'}).then(r=>r.ok?r.json():{}).catch(()=>({})).then(j=>IDS=j);
  function plink(id,name){if(!id||!name)return '';return `<button type="button" class="plink" data-pid="${esc(id)}" data-pname="${esc(name)}" aria-label="Open ${esc(name)} on Sleeper or ESPN" title="Open on Sleeper / ESPN">${EXT}</button>`}
  let menu=null,menuBtn=null;
  function closeMenu(){if(menu){menu.remove();menu=null}if(menuBtn){menuBtn.setAttribute('aria-expanded','false');menuBtn=null}}
  function copy(t){try{return navigator.clipboard.writeText(t)}catch(e){return Promise.reject(e)}}
  document.addEventListener('click',e=>{
    const b=e.target.closest('.plink');
    if(b){e.preventDefault();e.stopPropagation();if(menuBtn===b){closeMenu();return}closeMenu();menuBtn=b;b.setAttribute('aria-expanded','true');
      const name=b.dataset.pname,id=b.dataset.pid,lg=getLeague();
      menu=document.createElement('div');menu.className='pmenu';menu.setAttribute('role','menu');
      const paint=()=>{const espn=IDS&&IDS[id];
        menu.innerHTML=`<div class="pm-h">${esc(name)}</div>
          <a role="menuitem" href="${leagueUrl(lg)}" target="_blank" rel="noopener" data-copy="1">Sleeper${lg?' · '+esc(lg.name)+' players':''}<small>copies the name so you can paste it into search</small></a>
          ${espn?`<a role="menuitem" href="https://www.espn.com/nfl/player/_/id/${encodeURIComponent(espn)}" target="_blank" rel="noopener">ESPN player page<small>stats, game log, news</small></a>`:''}
          <a role="menuitem" href="https://www.google.com/search?q=${encodeURIComponent(name+' NFL news')}" target="_blank" rel="noopener">Latest news<small>web search</small></a>
          <button type="button" role="menuitem" data-copyonly="1">Copy name</button>`;
        menu.querySelector('[data-copy]').addEventListener('click',()=>{copy(name).catch(()=>{})});
        menu.querySelector('[data-copyonly]').addEventListener('click',ev=>{copy(name).then(()=>{ev.target.textContent='Copied'},()=>{ev.target.textContent=name});});};
      paint();document.body.appendChild(menu);
      const r=b.getBoundingClientRect(),w=menu.offsetWidth;let left=Math.min(r.left+window.scrollX,window.scrollX+document.documentElement.clientWidth-w-12);left=Math.max(window.scrollX+12,left);
      menu.style.left=left+'px';menu.style.top=(r.bottom+window.scrollY+4)+'px';
      if(!IDS)idsP().then(()=>{if(menu)paint()});return}
    if(menu&&!menu.contains(e.target))closeMenu();
    if(menu&&e.target.closest('.pmenu a'))setTimeout(closeMenu,50);
  },true);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu()});

  window.NFLS={leagueUrl,badge,plink,setTheme,loadLeagues,getLeague,rosterStatus,onLeague(cb){listeners.push(cb);if(leagueCfg)cb(getLeague())}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
