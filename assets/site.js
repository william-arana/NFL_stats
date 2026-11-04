/* Shared nav tools for every NFL_stats page: theme toggle, league + team picker, Sleeper roster lookups,
   and the little "open player" link menu. */
(function(){
  const LS={get(k){try{return localStorage.getItem('nfls-'+k)}catch(e){return null}},set(k,v){try{localStorage.setItem('nfls-'+k,v)}catch(e){}}};
  const root=document.documentElement;
  const EXT='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const listeners=[];let leagueCfg=null;
  /* selection = "leagueId|rosterId" (or "none"); older saves held just the league id */
  let sel=LS.get('league');
  const cache={};

  function setTheme(t){if(t==='dark')root.dataset.theme='dark';else delete root.dataset.theme;LS.set('theme',t);paintThemeBtn();window.dispatchEvent(new Event('nfls-theme'))}
  function paintThemeBtn(){const b=document.querySelector('#set-menu [data-set="dark"]');if(b)b.checked=root.dataset.theme==='dark'}
  /* Settings menu (gear in the nav): dark mode + how player cards behave. Card settings are read by cards.js
     (JSON in localStorage: nfls-cards-side, nfls-cards-snap, nfls-cards-max) and applied live via the nfls-settings event. */
  const GEAR='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';
  const CS={get(k,d){try{const v=localStorage.getItem('nfls-cards-'+k);return v==null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem('nfls-cards-'+k,JSON.stringify(v))}catch(e){}}};
  function settingsHTML(){const max=CS.get('max',2);
    const sw=(k,label,sub,on)=>`<label class="sm-row"><span><b>${label}</b>${sub?`<small>${sub}</small>`:''}</span><input type="checkbox" class="sw" data-set="${k}" ${on?'checked':''}></label>`;
    return `<div class="sm-h">Settings</div>
      ${sw('dark','Dark mode','',root.dataset.theme==='dark')}
      <div class="sm-sec">Player cards <small>(computer / tablet)</small></div>
      ${sw('side','Side panel','Cards open docked on the right; each new name opens as a tab. Drag a card out by its header to float it.',CS.get('side',false))}
      ${sw('snap','Snap to screen edges','Drop a card on the top edge = full screen, left / right = half',CS.get('snap',true))}
      <div class="sm-row"><span><b>Cards on screen</b><small>Open card + pop-out windows</small></span><span class="seg sm-seg">${[2,3,4,5].map(n=>`<button type="button" data-max="${n}" aria-pressed="${n===max}">${n}</button>`).join('')}</span></div>`}
  function openSettings(btn,menu){const on=menu.hidden;menu.hidden=!on;btn.setAttribute('aria-expanded',String(on));if(on)menu.innerHTML=settingsHTML()}

  function loadLeagues(){
    if(leagueCfg)return Promise.resolve(leagueCfg);
    const cfgP=fetch('data/leagues.json',{cache:'no-cache'}).then(r=>r.json()).catch(()=>({leagues:[]}));
    const snapP=fetch('data/site/leagues.json',{cache:'no-cache'}).then(r=>r.ok?r.json():null).catch(()=>null);
    return Promise.all([cfgP,snapP]).then(([cfg,snap])=>{
      const leagues=cfg.leagues.map(l=>{const s=snap&&snap.leagues.find(x=>x.id===l.id);
        /* Yahoo: team count, your team and the viewer come from the snapshot (Yahoo's API needs a sign-in, so the Action pulls it) */
        if(l.provider==='yahoo'){if(!s)return null;l={...l,name:l.name||s.name||'Yahoo league',teams:s.teams,my_roster_id:s.my_roster_id,viewers:s.viewers,url:s.url}}const name=rid=>{const r=s&&s.rosters.find(x=>x.roster_id===rid);return r?r.team_name.trim():null};
        const viewers=(l.viewers&&l.viewers.length?l.viewers:[{roster_id:l.my_roster_id}]).map(v=>({roster_id:v.roster_id,label:v.label||name(v.roster_id)||('Team '+v.roster_id)}));
        return {...l,viewers}}).filter(Boolean);
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
    if(cfg.provider==='yahoo'){cache[key]=Promise.resolve(snap?build(snap.rosters,'snapshot',leagueCfg.snapshot.yahoo_updated_utc||leagueCfg.snapshot.updated_utc):null);return cache[key]}
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
    host.innerHTML=`<label for="league-sel">Team</label><select id="league-sel" aria-label="League and team"></select><span class="setwrap"><button class="theme" id="set-btn" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="set-menu" title="Settings">${GEAR}<span class="lbl">Settings</span></button><div class="setmenu" id="set-menu" role="dialog" aria-label="Settings" hidden></div></span>`;
    {const btn=document.getElementById('set-btn'),menu=document.getElementById('set-menu');
      btn.onclick=e=>{e.stopPropagation();openSettings(btn,menu)};
      menu.addEventListener('click',e=>{e.stopPropagation();const m=e.target.closest('[data-max]');if(!m)return;CS.set('max',+m.dataset.max);
        menu.querySelectorAll('[data-max]').forEach(b=>b.setAttribute('aria-pressed',String(b===m)));window.dispatchEvent(new CustomEvent('nfls-settings',{detail:'max'}))});
      menu.addEventListener('change',e=>{const k=e.target.dataset.set;if(!k)return;if(k==='dark'){setTheme(e.target.checked?'dark':'light');return}
        CS.set(k,e.target.checked);window.dispatchEvent(new CustomEvent('nfls-settings',{detail:k}))});
      document.addEventListener('click',e=>{if(!menu.hidden&&!e.target.closest('.setwrap')){menu.hidden=true;btn.setAttribute('aria-expanded','false')}});
      document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!menu.hidden){menu.hidden=true;btn.setAttribute('aria-expanded','false');btn.focus()}})}
    loadLeagues().then(()=>{const s=document.getElementById('league-sel');const opts=allOptions();const groups=[...new Set(opts.map(o=>o.group))];
      s.innerHTML=groups.map(g=>`<optgroup label="${esc(g)}">${opts.filter(o=>o.group===g).map(o=>`<option value="${o.value}">${esc(o.label)}</option>`).join('')}</optgroup>`).join('')+'<option value="none">No league</option>';
      s.value=sel;
      s.onchange=()=>{sel=s.value;LS.set('league',sel);listeners.forEach(f=>f(getLeague()))};
      listeners.forEach(f=>f(getLeague()));
    });
  }

  /* Sleeper has no public page per player, so links open the league's Players tab; the link menu copies the name first. */
  function leagueUrl(lg){return !lg?'https://sleeper.com':lg.provider==='yahoo'?(lg.url||'https://football.fantasysports.yahoo.com/f1/'+lg.yahoo_league_id)+'/players':`https://sleeper.com/leagues/${lg.id}/players`}
  const appName=lg=>lg&&lg.provider==='yahoo'?'Yahoo':'Sleeper';
  function badge(status,lg,name){if(!status||!lg)return '';const t=status==='fa'?'FA':status==='mine'?'MINE':'';if(!t)return '';
    const tip=status==='fa'?`Free agent in ${lg.name}. Opens ${lg.name} players on ${appName(lg)}`:`On ${lg.viewer||'your'} roster in ${lg.name}. Opens ${appName(lg)}`;
    return `<a class="av ${status}" href="${leagueUrl(lg)}" target="_blank" rel="noopener" title="${esc(tip)}">${t}</a>`}

  /* "open player" link: small icon after a name; opens a menu with Sleeper, ESPN and copy-name */
  let IDS=null;const idsP=()=>IDS?Promise.resolve(IDS):fetch('data/site/ids.json',{cache:'no-cache'}).then(r=>r.ok?r.json():{}).catch(()=>({})).then(j=>IDS=j);
  let TM=null;const tmP=()=>TM?Promise.resolve(TM):fetch('data/site/teams_meta.json',{cache:'no-cache'}).then(r=>r.ok?r.json():{}).catch(()=>({})).then(j=>TM=j);
  function plink(id,name){if(!id||!name)return '';return `<button type="button" class="plink" data-pid="${esc(id)}" data-pname="${esc(name)}" aria-label="Open ${esc(name)} on Sleeper or ESPN" title="Sleeper / ESPN"><span class="slp" aria-hidden="true"></span></button>`}
  let menu=null,menuBtn=null;
  function closeMenu(){if(menu){menu.remove();menu=null}if(menuBtn){menuBtn.setAttribute('aria-expanded','false');menuBtn=null}}
  function copy(t){try{return navigator.clipboard.writeText(t)}catch(e){return Promise.reject(e)}}
  document.addEventListener('click',e=>{
    const b=e.target.closest('.plink');
    if(b){e.preventDefault();e.stopPropagation();if(menuBtn===b){closeMenu();return}closeMenu();menuBtn=b;b.setAttribute('aria-expanded','true');
      const name=b.dataset.pname,id=b.dataset.pid,lg=getLeague();
      menu=document.createElement('div');menu.className='pmenu';menu.setAttribute('role','menu');
      const isDef=id.startsWith('DEF:'),abbr=isDef?id.slice(4):null;let copyText=name;
      const paint=()=>{const espn=!isDef&&IDS&&IDS[id];const tm=isDef&&TM&&TM[abbr];if(tm)copyText=tm.nick;
        menu.innerHTML=`<div class="pm-h">${esc(isDef&&tm?tm.name+' D/ST':name)}</div>
          <a role="menuitem" href="${leagueUrl(lg)}" target="_blank" rel="noopener" data-copy="1">${appName(lg)}${lg?' · '+esc(lg.name)+' players':''}<small>copies "${esc(copyText)}" so you can paste it into search</small></a>
          ${espn?`<a role="menuitem" href="https://www.espn.com/nfl/player/_/id/${encodeURIComponent(espn)}" target="_blank" rel="noopener">ESPN player page<small>stats, game log, news</small></a>`:''}
          ${tm?`<a role="menuitem" href="https://www.espn.com/nfl/team/_/name/${encodeURIComponent(tm.espn)}" target="_blank" rel="noopener">ESPN team page<small>schedule, stats, roster</small></a>`:''}
          <a role="menuitem" href="https://www.google.com/search?q=${encodeURIComponent((isDef&&tm?tm.name+' defense':name)+' NFL news')}" target="_blank" rel="noopener">Latest news<small>web search</small></a>
          <button type="button" role="menuitem" data-copyonly="1">Copy "${esc(copyText)}"</button>`;
        menu.querySelector('[data-copy]').addEventListener('click',()=>{copy(copyText).catch(()=>{})});
        menu.querySelector('[data-copyonly]').addEventListener('click',ev=>{copy(copyText).then(()=>{ev.target.textContent='Copied'},()=>{ev.target.textContent=copyText});});};
      paint();document.body.appendChild(menu);
      const r=b.getBoundingClientRect(),w=menu.offsetWidth;let left=Math.min(r.left+window.scrollX,window.scrollX+document.documentElement.clientWidth-w-12);left=Math.max(window.scrollX+12,left);
      menu.style.left=left+'px';menu.style.top=(r.bottom+window.scrollY+4)+'px';
      if(isDef?!TM:!IDS)(isDef?tmP():idsP()).then(()=>{if(menu)paint()});return}
    if(menu&&!menu.contains(e.target))closeMenu();
    if(menu&&e.target.closest('.pmenu a'))setTimeout(closeMenu,50);
  },true);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu()});

  /* Sleeper links (menu, card, FA/MINE badges): copy the name first, then open Sleeper.
     Phones / the home-screen app: open in the same window. A new tab is what left a blank page behind when
     the Sleeper app took over; this way the app opens straight away (or Sleeper's site, with a way back).
     Desktop: always the same "Sleeper" tab, so repeat clicks reuse it instead of piling up tabs. A browser
     only lets us reuse a tab this site opened, not one you opened yourself. */
  const touchy=()=>matchMedia('(pointer:coarse)').matches||navigator.standalone===true||matchMedia('(display-mode:standalone)').matches;
  document.addEventListener('click',e=>{
    const a=e.target.closest&&e.target.closest('a[href^="https://sleeper.com"],a[href^="https://sleeper.app"]');
    if(!a||e.defaultPrevented||e.metaKey||e.ctrlKey||e.shiftKey||e.button)return;
    e.preventDefault();
    let name=a.dataset.copyname||'';
    if(!name&&a.dataset.copy){const h=a.closest('.pmenu');const b=h&&h.querySelector('[data-copyonly]');const m=b&&b.textContent.match(/"(.*)"/);if(m)name=m[1]}
    if(!touchy()){   // desktop: start the copy, then open the tab in the same click (a later open gets blocked as a pop-up)
      if(name)copy(name).catch(()=>{});
      const w=window.open(a.href,'nfls-sleeper');if(w){try{w.focus()}catch(err){}}return}
    const go=()=>{location.href=a.href};if(!name){go();return}
    let done=false;const once=()=>{if(!done){done=true;go()}};
    copy(name).then(once,once);setTimeout(once,400);   // phones: copy first (leaving the page can cancel it), but don't wait long
  },true);

  /* phones: narrow the frozen name column while the table is scrolled sideways (see site.css).
     The full width is measured first so the column can animate between two fixed widths. */
  const phone=window.matchMedia('(max-width:640px)');let lockUntil=0;
  function setNarrow(el,on){
    const th=el.querySelector('th.stick')||el.querySelector('td.stick');if(!th)return;
    if(on){if(!el.classList.contains('sized')){const w=Math.ceil(th.getBoundingClientRect().width);if(w<=innerWidth*.34+8)return;/* already slim: nothing to shrink */
        el.style.setProperty('--stick-full',w+'px');el.classList.add('sized');void el.offsetWidth}
      clearTimeout(el._unsize);el.classList.add('narrow')}
    else{el.classList.remove('narrow');clearTimeout(el._unsize);el._unsize=setTimeout(()=>{if(!el.classList.contains('narrow'))el.classList.remove('sized')},340)}
  }
  /* while the width animates, ignore scroll events; then check once more so a quick swipe back isn't missed */
  function check(el){const x=el.scrollLeft,narrow=el.classList.contains('narrow');
    if(!narrow&&x>12){setNarrow(el,true);if(!el.classList.contains('narrow'))return}else if(narrow&&x<=1)setNarrow(el,false);else return;
    lockUntil=Date.now()+320;clearTimeout(el._recheck);el._recheck=setTimeout(()=>check(el),340)}
  /* only player tables slide; team / defense tables keep their size */
  document.addEventListener('scroll',e=>{const el=e.target;if(!phone.matches||!el||!el.classList||!el.classList.contains('tablewrap')||!el.querySelector('td.stick [data-card^="p:"]'))return;
    if(Date.now()<lockUntil)return;check(el)
  },true);
  /* a re-rendered or rotated table re-measures next time */
  phone.addEventListener&&phone.addEventListener('change',()=>document.querySelectorAll('.tablewrap.sized').forEach(el=>{el.classList.remove('narrow','sized')}));
  /* every page: if the server has a newer version than the files this page loaded, reload once with ?v=<new>.
     A new URL skips the browser's cached copy of the page (GitHub Pages lets browsers keep pages ~10 min),
     so Stats, Lab etc. update themselves, not just Home. Once per version per tab, so it can't loop. */
  (function(){const me=document.querySelector('script[src*="assets/site.js"]');const v=me&&(me.src.match(/[?&]v=([^&]+)/)||[])[1];if(!v)return;
    fetch('version.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(j=>{
      if(!j||!j.version||j.version===v||parseFloat(j.version.split('.')[1])<parseFloat(v.split('.')[1]))return;
      const k='nfls-upd-'+j.version;try{if(sessionStorage.getItem(k))return;sessionStorage.setItem(k,'1')}catch(e){return}
      const u=new URL(location.href);u.searchParams.set('v',j.version);location.replace(u.pathname+u.search+u.hash)}).catch(()=>{})})();
  /* every page except Home (which has its own in the big footer): version + "Check for updates" at the bottom */
  function verFoot(){if(document.getElementById('ver')||document.querySelector('.verfoot'))return;
    const me=document.querySelector('script[src*="assets/site.js"]');const v=(me&&(me.src.match(/[?&]v=([^&]+)/)||[])[1])||'?';
    const f=document.createElement('footer');f.className='verfoot';
    f.innerHTML=`<div class="wrap"><span>NFL_stats · data from <a href="https://github.com/nflverse" target="_blank" rel="noopener">nflverse</a> and Sleeper</span><span class="vf-r"><span class="vf-msg"></span><button type="button" class="vf-chk">Check for updates</button><b title="Site version: 1.&lt;pull request number&gt; of the last change">v${v}</b></span></div>`;
    document.body.appendChild(f);const msg=f.querySelector('.vf-msg');
    f.querySelector('.vf-chk').onclick=()=>{msg.textContent='Checking…';
      fetch('version.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.json()).then(j=>{
        if(j.version===v){msg.textContent='Up to date ('+j.date+')';return}
        msg.textContent='Updating to v'+j.version+'…';const u=new URL(location.href);u.searchParams.set('v',j.version);location.replace(u.pathname+u.search+u.hash)
      }).catch(()=>{msg.textContent="Couldn't check right now"})}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',verFoot);else verFoot();
  window.NFLS={leagueUrl,appName,badge,plink,setTheme,loadLeagues,getLeague,rosterStatus,onLeague(cb){listeners.push(cb);if(leagueCfg)cb(getLeague())}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
