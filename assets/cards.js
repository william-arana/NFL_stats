/* Player + defense cards for every NFL_stats page.
   Click anything with data-card="p:<gsis_id>" (player) or data-card="d:<TEAM>" (defense), or a stats-board
   .opp[data-opp] button, and a card drops down from it: weekly fantasy points, season stats, game log and news.
   Pages that already loaded the season files can hand them over with NFLSCards.provide({P,T,G,META,DEF}),
   otherwise the card loads them itself the first time it opens.
   News: the site's own archive (data/site/news/<id>.json, built 3x a day by update_player_news.py), merged
   with the live per-player feeds from Sleeper (RotoWire, FantasyPros, RotoBaller) and ESPN, read straight from the browser. */
(function(){
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const num=v=>typeof v==='number'&&isFinite(v);
  const mean=a=>{const b=a.filter(num);return b.length?b.reduce((x,y)=>x+y,0)/b.length:null};
  const sum=a=>a.reduce((x,y)=>x+(num(y)?y:0),0);
  const div=(a,b)=>b?a/b:null;
  const ord=n=>n+(['th','st','nd','rd'][(n%100>10&&n%100<14)?0:Math.min(n%10,4)%4]||'th');
  const rows=j=>{const out=new Array(j.rows);for(let i=0;i<j.rows;i++){const r={};for(const c of j.cols)r[c]=j.data[c][i];out[i]=r}return out};
  const LS={get(k,d){try{const v=localStorage.getItem('nfls-'+k);return v==null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem('nfls-'+k,JSON.stringify(v))}catch(e){}}};
  const SCORING={ppr:{k:'fantasy_points_ppr',label:'PPR'},half:{k:'fantasy_points_half',label:'Half'},std:{k:'fantasy_points',label:'Std'}};
  const scoring=()=>{const s=LS.get('scoring','ppr');return SCORING[s]?s:'ppr'};

  /* ---------- data ---------- */
  const D={};let loading=null;
  function provide(o){Object.assign(D,o);index()}
  const getJ=n=>fetch('data/site/'+n+'.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(n);return r.json()});
  function load(){
    if(D.P&&D.T&&D.G&&D.META&&D.IDS&&D.TM&&D.DEF)return Promise.resolve(D);
    if(loading)return loading;
    const need=[];
    if(!D.P)need.push(getJ('players').then(j=>D.P=rows(j)));
    if(!D.T)need.push(getJ('teams').then(j=>D.T=rows(j)));
    if(!D.G)need.push(getJ('schedule').then(j=>D.G=rows(j)));
    if(!D.META)need.push(getJ('meta').then(j=>{D.META=j;D.INJ=j.injuries||{}}));
    if(!D.DEF)need.push(getJ('defenders').then(j=>D.DEF=rows(j)).catch(()=>D.DEF=[]));
    if(!D.IDS)need.push(getJ('ids').catch(()=>({})).then(j=>D.IDS=j));
    if(!D.TM)need.push(getJ('teams_meta').catch(()=>({})).then(j=>D.TM=j));
    loading=Promise.all(need).then(()=>{if(!D.INJ)D.INJ=D.META.injuries||{};index();loading=null;return D});
    return loading;
  }
  let IX=null;
  function index(){
    if(!D.P||!D.T||!D.G||!D.META){IX=null;return}
    const byP=new Map(),byT=new Map();
    for(const r of D.P){let a=byP.get(r.player_id);if(!a)byP.set(r.player_id,a=[]);a.push(r)}
    for(const a of byP.values())a.sort((x,y)=>x.week-y.week);
    for(const r of D.T){let a=byT.get(r.team);if(!a)byT.set(r.team,a=[]);a.push(r)}
    for(const a of byT.values())a.sort((x,y)=>x.week-y.week);
    IX={byP,byT,_dvp:null,_td:null,_rank:{}};
  }
  /* team's game in a week: {opp, at, implied, opp_implied, g} or null (bye) */
  function gameOf(team,week){for(const g of D.G)if(g.week===week){if(g.home_team===team)return {opp:g.away_team,at:false,implied:g.home_implied,opp_implied:g.away_implied,g};if(g.away_team===team)return {opp:g.home_team,at:true,implied:g.away_implied,opp_implied:g.home_implied,g}}return null}
  const nextOpp=team=>gameOf(team,D.META.next_week);
  function byeWeek(team){const ws=new Set(D.G.filter(g=>g.home_team===team||g.away_team===team).map(g=>g.week));for(let w=1;w<=18;w++)if(!ws.has(w))return w;return null}
  function dvp(){ // PPR allowed per game by position; rk 1 = gives up the most
    if(IX._dvp)return IX._dvp;const games={},pts={};
    for(const r of D.P){const d=r.opponent_team;(games[d]=games[d]||new Set()).add(r.week);pts[d]=pts[d]||{QB:0,RB:0,WR:0,TE:0};if(num(r.fantasy_points_ppr)&&pts[d][r.position]!=null)pts[d][r.position]+=r.fantasy_points_ppr}
    const out={};for(const t in pts){out[t]={g:games[t].size};for(const p of ['QB','RB','WR','TE'])out[t][p]={v:pts[t][p]/games[t].size}}
    for(const p of ['QB','RB','WR','TE'])Object.keys(out).sort((a,b)=>out[b][p].v-out[a][p].v).forEach((t,i)=>out[t][p].rk=i+1);
    return IX._dvp=out;
  }
  const rkClass=(rk,n)=>rk<=8?'good':rk>n-8?'bad':'mid';
  function mrk(team,pos){const d=dvp()[team];if(!d||!d[pos])return '';const n=Object.keys(dvp()).length;const rk=d[pos].rk;return `<span class="mrk ${rkClass(rk,n)}" title="${team} allows the ${ord(rk)}-most PPR points to ${pos}s">${ord(rk)}</span>`}
  function oppBtn(team,label,pos){return `<button type="button" class="opp" data-card="d:${esc(team)}" data-pos="${esc(pos||'')}">${esc(label)}</button>${pos?mrk(team,pos):''}`}
  function teamDefense(team){
    if(!IX._td){const all=[...IX.byT.keys()].map(t=>{const rr=IX.byT.get(t),m=rr.length||1,s=k=>sum(rr.map(r=>r[k]))/m;return {t,pa:s('points_against'),ya:s('yards_allowed'),pya:s('pass_yards_allowed'),rya:s('rush_yards_allowed'),pr:s('def_pressures'),sk:s('def_sacks'),tk:s('def_interceptions')+s('fumble_recovery_opp'),dst:s('dst_pts')}});IX._td=all}
    const all=IX._td;const rank=(k,desc)=>[...all].sort((a,b)=>desc?b[k]-a[k]:a[k]-b[k]).findIndex(x=>x.t===team)+1;
    const rr=IX.byT.get(team)||[];const n=rr.length||1;const per=k=>sum(rr.map(r=>r[k]))/n;
    const w=rr.filter(r=>num(r.points_for));
    return {rows:rr,rec:`${w.filter(r=>r.points_for>r.points_against).length}-${w.filter(r=>r.points_for<r.points_against).length}`,g:rr.length,pa:per('points_against'),ya:per('yards_allowed'),pya:per('pass_yards_allowed'),rya:per('rush_yards_allowed'),pr:per('def_pressures'),sk:per('def_sacks'),tk:per('def_interceptions')+per('fumble_recovery_opp'),dst:per('dst_pts'),
      rk:{pa:rank('pa',false),ya:rank('ya',false),pya:rank('pya',false),rya:rank('rya',false),pr:rank('pr',true),sk:rank('sk',true),tk:rank('tk',true),dst:rank('dst',true)},n:all.length};
  }
  /* FP-per-game rank within position (min 2 games) for the chosen scoring */
  function posRank(id,pos,sk){
    const key=pos+'|'+sk;if(!IX._rank[key]){const list=[];for(const [pid,logs] of IX.byP){if(logs[0].position!==pos||logs.length<2)continue;list.push([pid,mean(logs.map(l=>l[sk]))])}list.sort((a,b)=>b[1]-a[1]);IX._rank[key]=new Map(list.map(([p],i)=>[p,i+1]))}
    return IX._rank[key].get(id)||null;
  }
  /* season summary for one player, reused by the Trade page */
  function playerSummary(id,sc){
    sc=sc||scoring();const sk=SCORING[sc].k;const logs=IX&&IX.byP.get(id);if(!logs||!logs.length)return null;
    const lw=D.META.last_completed_week,rec=logs.filter(l=>l.week>lw-3),last=logs[logs.length-1];
    const S=k=>sum(logs.map(l=>l[k]));
    return {id,name:last.player_display_name,pos:last.position,team:last.team,headshot:last.headshot_url,logs,g:logs.length,
      fp:S(sk),fpg:S(sk)/logs.length,l3:mean(rec.map(l=>l[sk])),g3:rec.length,xfpg:mean(logs.map(l=>l.xfp)),xfp3:mean(rec.map(l=>l.xfp)),
      snap:mean(logs.map(l=>l.offense_pct)),snap3:mean(rec.map(l=>l.offense_pct)),tgt:mean(logs.map(l=>l.target_share)),
      opps:(S('carries')+S('targets'))/logs.length,opps3:mean(rec.map(l=>(l.carries||0)+(l.targets||0))),
      best:Math.max(...logs.map(l=>l[sk]||0)),worst:Math.min(...logs.map(l=>num(l[sk])?l[sk]:0)),
      sd:(()=>{const v=logs.map(l=>l[sk]).filter(num);const m=mean(v);return v.length>1?Math.sqrt(mean(v.map(x=>(x-m)**2))):null})(),
      rank:posRank(id,last.position,sk)};
  }
  function defSummary(team){const td=teamDefense(team);const lw=D.META.last_completed_week;const rec=td.rows.filter(r=>r.week>lw-3);
    return {...td,team,l3:mean(rec.map(r=>r.dst_pts)),best:Math.max(0,...td.rows.map(r=>r.dst_pts||0)),sd:(()=>{const v=td.rows.map(r=>r.dst_pts).filter(num);const m=mean(v);return v.length>1?Math.sqrt(mean(v.map(x=>(x-m)**2))):null})()}}

  /* ---------- news ---------- */
  const NEWS={};
  function clean(s,n){s=String(s||'').replace(/<[^>]+>/g,' ').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&#39;|&rsquo;/g,"'").replace(/&quot;|&ldquo;|&rdquo;/g,'"').replace(/\s+/g,' ').trim();return s.length<=n?s:s.slice(0,n-1).replace(/\s+\S*$/,'')+'…'}
  function espnItems(feed){return (feed||[]).map(a=>{const h=clean(a.headline,220);if(!h)return null;const l=a.links||{};const url=(l.web&&l.web.href)||(l.mobile&&l.mobile.href)||null;
    const st=a.story||'';const s=clean(st&&st.length<1200?st:(a.description||st),600);const kind=String(a.type||'').toLowerCase();
    return {h,s:s===h?'':s,d:a.published||a.lastModified||null,src:/rotowire/i.test(a.byline||'')?'RotoWire via ESPN':(kind.includes('headline')?'ESPN fantasy':'ESPN'),url}}).filter(Boolean)}
  async function getJSON(u,ms){const c=new AbortController();const t=setTimeout(()=>c.abort(),ms);try{const r=await fetch(u,{signal:c.signal});if(!r.ok)throw new Error(r.status);return await r.json()}finally{clearTimeout(t)}}
  const SLP_SRC={rotowire:'RotoWire',fantasy_pros:'FantasyPros',rotoballer:'RotoBaller'};
  function sleeperItems(arr){return (arr||[]).map(a=>{const m=a.metadata||{};const h=clean(String(m.title||'').replace(/^.{3,40}? - /,''),220);if(!h)return null;
    return {h,s:clean([m.description,m.analysis].filter(Boolean).join(' '),700),d:a.published?new Date(a.published).toISOString():null,src:SLP_SRC[a.source]||String(a.source||'').replace(/_/g,' '),url:m.url||null}}).filter(Boolean)}
  let SMAPP=null;const sleeperId=g=>(SMAPP||(SMAPP=fetch('data/site/sleeper_map.json',{cache:'no-cache'}).then(r=>r.ok?r.json():{map:{}}).then(j=>{const inv={};for(const [s,x] of Object.entries(j.map||{}))inv[x]=s;return inv}).catch(()=>({})))).then(inv=>inv[g]);
  /* live feeds, straight from the browser (both send Access-Control-Allow-Origin: *) */
  /* ESPN's athlete feed mixes in general NFL headlines: stories that don't name the player are marked gen (shown last) */
  function namesPlayer(g){const full=String(NAMEHINT[g]||'').toLowerCase().replace(/\s+(jr\.?|sr\.?|ii|iii|iv|v)$/,'');const last=full.split(/\s+/).pop()||'';
    return it=>{if(!last)return false;const t=(it.h+' '+(it.s||'')).toLowerCase();return t.includes(full)||new RegExp('\\b'+last.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\b').test(t)}}
  async function liveNews(g){
    const out={items:[],via:[]};
    const espn=D.IDS[g];
    const jobs=[
      espn?getJSON(`https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId=${encodeURIComponent(espn)}&limit=50`,7000).then(j=>{out.items.push(...espnItems(j.feed));if(!out.via.includes('ESPN'))out.via.push('ESPN')}).catch(()=>{}):null,
      /* ESPN's general athlete news covers everyone (defenders, linemen, kickers), not just fantasy-relevant players */
      espn?getJSON(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?athlete=${encodeURIComponent(espn)}&limit=50`,7000).then(j=>{const isP=namesPlayer(g);const it=espnItems(j.articles).map(x=>isP(x)?x:{...x,gen:true});out.items.push(...it);if(it.length&&!out.via.includes('ESPN'))out.via.push('ESPN')}).catch(()=>{}):null,
      sleeperId(g).then(sid=>sid?getJSON(`https://api.sleeper.app/players/nfl/${encodeURIComponent(sid)}/news?limit=50`,7000):null).then(j=>{if(j){out.items.push(...sleeperItems(j));out.via.push('Sleeper')}}).catch(()=>{})
    ].filter(Boolean);
    await Promise.all(jobs);return out;
  }
  const nkey=it=>it.h.toLowerCase().replace(/\W/g,'').slice(0,80);
  /* key = gsis id or "DEF:XX". Resolves {items (newest first), archived: n, live: 'direct'|'worker'|null} */
  function newsFor(key){
    if(NEWS[key])return NEWS[key];
    const isDef=key.startsWith('DEF:');
    const arch=fetch('data/site/news/'+key.replace(':','_')+'.json',{cache:'no-cache'}).then(r=>r.ok?r.json():null).catch(()=>null);
    const lv=isDef?Promise.resolve({items:[],via:[]}):load().then(()=>liveNews(key));
    return NEWS[key]=Promise.all([arch,lv]).then(([a,l])=>{const by=new Map();for(const it of [...(a&&a.items||[]),...l.items]){const k=nkey(it),pr=by.get(k);by.set(k,{...pr,...it,gen:!!(it.gen&&(!pr||pr.gen))})}
      const rwT=new Set([...by.values()].filter(x=>x.src==='RotoWire').map(x=>x.d&&new Date(x.d).getTime()));const items=[...by.values()].filter(x=>!(x.src==='ESPN fantasy'&&x.d&&rwT.has(new Date(x.d).getTime()))).sort((x,y)=>String(y.d||'').localeCompare(String(x.d||'')));return {items,archived:a?a.items.length:0,live:l.via,updated:a&&a.updated_utc}});
  }
  const fmtDate=s=>{if(!s)return '';const d=new Date(s);if(isNaN(d))return '';const days=(Date.now()-d)/864e5;
    const md=d.toLocaleDateString(undefined,{month:'short',day:'numeric',...(d.getFullYear()!==new Date().getFullYear()?{year:'numeric'}:{})});
    return days<1?`${md} · ${Math.max(1,Math.round(days*24))}h ago`:days<14?`${md} · ${Math.round(days)}d ago`:md};
  /* Player first (default): stories about the player newest first, then general NFL stories (ESPN athlete feed)
     under a divider. Newest first: everything mixed by date. Remembered per browser (nfls-newsmix). */
  function newsHTML(n,all,name){
    if(!n.items.length)return `<p class="dim" style="margin:0">No stories yet. The news archive fills in each time the "Update Sleeper rosters" job runs (3× a day).</p>`;
    const mix=LS.get('newsmix',false),anyGen=n.items.some(x=>x.gen);
    const ordered=mix||!anyGen?n.items:[...n.items.filter(x=>!x.gen),...n.items.filter(x=>x.gen)];
    const show=all?ordered:ordered.slice(0,6);const oldest=n.items[n.items.length-1].d;
    const li=it=>{const fresh=!it.gen&&it.d&&(Date.now()-new Date(it.d))<3*864e5;return `<li class="${fresh?'new':''} ${it.gen?'gen':''}">${it.url?`<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.h)}</a>`:`<b>${esc(it.h)}</b>`}${it.s?`<p>${esc(it.s)}</p>`:''}<small>${it.gen?'General NFL · ':''}${esc(it.src||'')}${it.d?' · '+esc(fmtDate(it.d)):''}</small></li>`};
    let body='';let divided=false;for(const it of show){if(!mix&&it.gen&&!divided){divided=true;body+=`<li class="gen-h">General NFL news</li>`}body+=li(it)}
    return `${anyGen?`<div class="nmode seg" role="group" aria-label="News order"><button type="button" data-nmode="player" aria-pressed="${!mix}">Player first</button><button type="button" data-nmode="mix" aria-pressed="${mix}">Newest first</button></div>`:''}<ul class="pc-news">${body}</ul>
      ${!all&&ordered.length>show.length?`<button type="button" class="more" data-more>Show all ${n.items.length} stories (back to ${esc(fmtDate(oldest).split(' · ')[0])})</button>`:''}`;
  }
  function newsSrc(n){const p=[];if(n.live&&n.live.length)p.push(n.live.join(' + ')+' live');if(n.archived)p.push(`site archive (${n.archived})`);return p.length?p.join(' + '):'site archive'}

  /* ---------- card HTML ---------- */
  const f1=v=>num(v)?v.toFixed(1):'–',f0=v=>num(v)?v.toFixed(0):'–',pct=v=>num(v)?Math.round(v*100)+'%':'–';
  const POSCOLS={
    QB:[['completions','Cmp'],['attempts','Att'],['passing_yards','Pass yds'],['passing_tds','TD'],['passing_interceptions','INT'],['sacks_suffered','Sk'],['carries','Car'],['rushing_yards','Rush yds'],['rushing_tds','Rush TD']],
    RB:[['carries','Car'],['rushing_yards','Rush yds'],['rushing_tds','TD'],['targets','Tgt'],['receptions','Rec'],['receiving_yards','Rec yds'],['receiving_tds','Rec TD'],['offense_pct','Snap %','%'],['xfp','xFP',1]],
    WR:[['targets','Tgt'],['receptions','Rec'],['receiving_yards','Yds'],['receiving_tds','TD'],['receiving_air_yards','Air yds'],['target_share','Tgt %','%'],['offense_pct','Snap %','%'],['carries','Car'],['xfp','xFP',1]],
  };POSCOLS.TE=POSCOLS.WR;
  const RATE=new Set(['offense_pct','target_share']);
  function bars(logs,sk,team){
    const lw=D.META.last_completed_week;const W=Math.max(lw,1);const byW=new Map(logs.map(l=>[l.week,l[sk]]));const bye=byeWeek(team);
    const vals=[...byW.values()].filter(num);const max=Math.max(20,...vals);const avg=mean(vals);
    const cw=440/W,H=86,base=70,y=v=>base-(v/max)*56;
    let s=`<svg class="bars" viewBox="0 0 440 ${H}" role="img" aria-label="Fantasy points by week">`;
    if(num(avg))s+=`<line x1="0" x2="440" y1="${y(avg).toFixed(1)}" y2="${y(avg).toFixed(1)}" stroke-dasharray="3 3"><title>Season average ${avg.toFixed(1)}</title></line>`;
    for(let w=1;w<=W;w++){const v=byW.get(w),x=(w-1)*cw+cw*.18,bw=cw*.64;
      if(num(v)){const cls=num(avg)&&v>=avg*1.3?'hi':num(avg)&&v<avg*.6?'lo':'';s+=`<rect class="${cls}" x="${x.toFixed(1)}" y="${y(Math.max(v,0)).toFixed(1)}" width="${bw.toFixed(1)}" height="${(base-y(Math.max(v,0))).toFixed(1)}" rx="2"><title>Wk ${w}: ${v.toFixed(1)}</title></rect><text x="${(x+bw/2).toFixed(1)}" y="${(y(Math.max(v,0))-3).toFixed(1)}">${v.toFixed(v>=10?0:1)}</text>`}
      else s+=`<text x="${(x+bw/2).toFixed(1)}" y="${base-3}" class="wk">${w===bye?'bye':'–'}</text>`;
      s+=`<text class="wk" x="${(x+bw/2).toFixed(1)}" y="${H-3}">${w}</text>`}
    return s+`<line x1="0" x2="440" y1="${base}" y2="${base}"/></svg>`;
  }
  function scoringSeg(sc){return `<span class="seg" data-sc>${Object.entries(SCORING).map(([k,v])=>`<button type="button" data-v="${k}" aria-pressed="${k===sc}">${v.label}</button>`).join('')}</span>`}
  function ownerTag(key){return `<span data-own="${esc(key)}"></span>`}
  function playerHTML(id){
    if(!(IX.byP.get(id)||[]).length){if(X.K.has(id))return kickerHTML(id);if(X.DW.has(id))return defenderHTML(id);if(X.OL.has(id))return linemanHTML(id)}
    const sc=scoring(),sk=SCORING[sc].k;const s=playerSummary(id,sc);const inj=D.INJ[id];const espn=D.IDS[id];
    if(!s)return `<div class="pc-top"><div><h3>${esc(NAMEHINT[id]||'Player')}</h3><div class="sub">No stats this season</div></div></div>
      <section><p class="dim" style="margin:0">Hasn't recorded an offensive snap in nflverse's weekly data this season (kicker, injured, or rookie yet to play).</p><div class="tags" style="margin-top:6px">${ownerTag(id)}</div></section>
      <section><h4>News <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>${linksHTML(id,NAMEHINT[id]||'',espn,null)}`;
    NAMEHINT[id]=s.name;
    const n=nextOpp(s.team);const cols=POSCOLS[s.pos]||POSCOLS.WR;
    const tot=k=>sum(s.logs.map(l=>l[k])),pg=k=>RATE.has(k)?mean(s.logs.map(l=>l[k])):tot(k)/s.g;
    const cell=(k,v,isPg)=>!num(v)?'<span class="dim">–</span>':RATE.has(k)?pct(v):(isPg||k==='xfp')?f1(v):f0(v);
    const seasonRow=(lbl,isPg)=>`<tr${isPg?'':' class="tot"'}><td class="l">${lbl}</td><td class="fp">${f1(isPg?s.fpg:s.fp)}</td>${cols.map(([k])=>`<td>${cell(k,isPg||RATE.has(k)?pg(k):tot(k),isPg)}</td>`).join('')}</tr>`;
    const logRows=s.logs.map(l=>`<tr><td class="l">${gbtn(gameKey(l.team,l.week),l.week)}</td><td class="l">${oppBtn(l.opponent_team,((gameOf(l.team,l.week)||{}).at?'@ ':'vs ')+l.opponent_team,null)}</td><td class="fp">${f1(l[sk])}</td>${cols.map(([k])=>`<td>${cell(k,l[k],false)}</td>`).join('')}</tr>`).join('');
    return `<div class="pc-top">${s.headshot?`<img class="hs" src="${esc(s.headshot)}" alt="" loading="lazy" onerror="this.remove()">`:''}<div><h3>${esc(s.name)}</h3>
      <div class="sub"><span>${s.pos} · ${dbtn(s.team,s.team,'tmlink')}</span><span>bye ${byeWeek(s.team)||'–'}</span>${n?`<span>${gbtn(n.g.game_id,'Wk '+D.META.next_week)} ${oppBtn(n.opp,(n.at?'@ ':'vs ')+n.opp,s.pos)}</span>`:`<span>Wk ${D.META.next_week} bye</span>`}</div></div></div>
    <section><div class="tags">${inj?`<span class="tag inj" title="${esc(inj[1])} · Wk ${inj[2]} report">${esc(inj[0].replace('Practice: ','Practice '))} · ${esc(inj[1])}</span>`:''}${ownerTag(id)}<span class="sp" style="flex:1"></span>${scoringSeg(sc)}</div>
      <div class="tiles" style="margin-top:8px">
        <div><span>FP / game</span><b>${f1(s.fpg)}</b><small>${[s.rank?s.pos+s.rank:'',s.g+' g'].filter(Boolean).join(' · ')}</small></div>
        <div><span>Last 3</span><b>${f1(s.l3)}</b><small>${num(s.l3)&&num(s.fpg)?(s.l3>=s.fpg?'▲ ':'▼ ')+Math.abs(s.l3-s.fpg).toFixed(1)+' vs avg':''}</small></div>
        <div><span>xFP / game</span><b>${f1(s.xfpg)}</b><small>L3 ${f1(s.xfp3)}</small></div>
        <div><span>Snap %</span><b>${pct(s.snap)}</b><small>L3 ${pct(s.snap3)}</small></div>
        <div><span>Touches / g</span><b>${f1(s.opps)}</b><small>${s.pos==='QB'?'carries + targets':'L3 '+f1(s.opps3)}</small></div>
      </div></section>
    <section><h4>${SCORING[sc].label} points by week <span class="sp"></span><span>high ${f1(s.best)} · low ${f1(s.worst)}${num(s.sd)?' · ±'+s.sd.toFixed(1):''}</span></h4>${bars(s.logs,sk,s.team)}</section>
    <section><h4>Season stats</h4><div class="scr"><table data-cols="card-season-${s.pos}"><thead><tr><th class="l"></th><th>FP</th>${cols.map(([,l])=>`<th>${l}</th>`).join('')}</tr></thead><tbody>${seasonRow('Per game',true)}${seasonRow('Total',false)}</tbody></table></div></section>
    <section><h4>Game log</h4><div class="scr"><table data-cols="card-log-${s.pos}"><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>FP</th>${cols.map(([,l])=>`<th>${l}</th>`).join('')}</tr></thead><tbody>${logRows}</tbody></table></div><div class="note">Opponent rank = PPR points that defense allows to ${s.pos}s (green = generous). Click an opponent for its defense card.</div></section>
    <section><h4>News <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>
    ${linksHTML(id,s.name,espn,null)}`;
  }
  function linksHTML(id,name,espn,tm){
    const lg=window.NFLS&&NFLS.getLeague();
    return `<section class="links">${espn?`<a href="https://www.espn.com/nfl/player/_/id/${encodeURIComponent(espn)}" target="_blank" rel="noopener">ESPN</a>`:''}${tm?`<a href="https://www.espn.com/nfl/team/_/name/${encodeURIComponent(tm.espn)}" target="_blank" rel="noopener">ESPN team page</a>`:''}
      <a href="${window.NFLS?NFLS.leagueUrl(lg):'https://sleeper.com'}" target="_blank" rel="noopener" data-copyname="${esc(tm?tm.nick:name)}" title="Copies the name so you can paste it into Sleeper search">Sleeper</a>
      <a href="trade.html#a=${encodeURIComponent(id)}">Compare on Trade page</a>
      <a href="https://www.google.com/search?q=${encodeURIComponent((tm?tm.name+' defense':name)+' NFL news')}" target="_blank" rel="noopener">Web news</a></section>`;
  }
  function defHTML(team,pos){
    const tm=D.TM[team]||{name:team,nick:team};const d=dvp()[team],td=teamDefense(team),n=Object.keys(dvp()).length;const nx=nextOpp(team);const ds=defSummary(team);
    const cell=p=>`<div style="${p===pos?'box-shadow:inset 0 0 0 2px var(--blue)':''}"><span>${p}</span><b>${d?d[p].v.toFixed(1):'–'}</b><span class="mrk ${d?rkClass(d[p].rk,n):'mid'}">${d?ord(d[p].rk):''}</span></div>`;
    const rk=(r,label)=>`<span class="mrk ${rkClass(r,td.n)}" title="${label}">${ord(r)}</span>`;
    const logs=td.rows.map(r=>({week:r.week,fantasy_points_ppr:r.dst_pts}));
    return `<div class="pc-top">${tm.logo?`<img class="logo" src="${esc(tm.logo)}" alt="" loading="lazy" onerror="this.remove()">`:''}<div><h3>${esc(team)} D/ST</h3>
      <div class="sub"><span>${esc(tm.name||team)} · ${td.rec}</span><span>bye ${byeWeek(team)||'–'}</span>${nx?`<span>${gbtn(nx.g.game_id,'Wk '+D.META.next_week)} ${nx.at?'@':'vs'} ${dbtn(nx.opp,nx.opp)}${num(nx.opp_implied)?` · opp implied ${nx.opp_implied.toFixed(1)}`:''}</span>`:`<span>Wk ${D.META.next_week} bye</span>`}</div></div></div>
    <section><div class="tags">${ownerTag('DEF:'+team)}</div>
      <div class="tiles" style="margin-top:8px"><div><span>D/ST pts / g</span><b>${f1(td.dst)}</b><small>${ord(td.rk.dst)} of ${td.n}</small></div><div><span>Last 3</span><b>${f1(ds.l3)}</b><small>${num(ds.sd)?'±'+ds.sd.toFixed(1)+' weekly':''}</small></div><div><span>Sacks / g</span><b>${f1(td.sk)}</b><small>${ord(td.rk.sk)}</small></div><div><span>Takeaways / g</span><b>${f1(td.tk)}</b><small>${ord(td.rk.tk)}</small></div></div></section>
    <section><h4>D/ST points by week</h4>${bars(logs,'fantasy_points_ppr',team)}</section>
    <section><h4>PPR points allowed per game · rank (1st = gives up most)</h4><div class="dvp">${['QB','RB','WR','TE'].map(cell).join('')}</div></section>
    <section><h4>Team defense per game</h4><div class="scr"><table><tbody>
      <tr><td class="l">Points allowed</td><td>${td.pa.toFixed(1)}</td><td>${rk(td.rk.pa,'1st = fewest allowed')}</td><td class="l">Pressures</td><td>${td.pr.toFixed(1)}</td><td>${rk(td.rk.pr,'1st = most')}</td></tr>
      <tr><td class="l">Yards allowed</td><td>${td.ya.toFixed(0)}</td><td>${rk(td.rk.ya,'1st = fewest allowed')}</td><td class="l">Sacks</td><td>${td.sk.toFixed(1)}</td><td>${rk(td.rk.sk,'1st = most')}</td></tr>
      <tr><td class="l">Pass yds allowed</td><td>${td.pya.toFixed(0)}</td><td>${rk(td.rk.pya,'1st = fewest allowed')}</td><td class="l">Takeaways</td><td>${td.tk.toFixed(1)}</td><td>${rk(td.rk.tk,'1st = most')}</td></tr>
      <tr><td class="l">Rush yds allowed</td><td>${td.rya.toFixed(0)}</td><td>${rk(td.rk.rya,'1st = fewest allowed')}</td><td></td><td></td><td></td></tr>
    </tbody></table></div><div class="note">Defense ranks: green = strong defense (tough matchup), red = weak.</div></section>
    <section><h4>Game log</h4><div class="scr"><table data-cols="card-dst-log"><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>D/ST</th><th>Pts alw</th><th>Pass alw</th><th>Rush alw</th><th>Sk</th><th>Prs</th><th>INT</th><th>FR</th><th>TD</th></tr></thead><tbody>${td.rows.map(r=>`<tr><td class="l">${gbtn(gameKey(team,r.week),r.week)}</td><td class="l">${oppBtn(r.opponent_team,((gameOf(team,r.week)||{}).at?'@ ':'vs ')+r.opponent_team,null)}</td><td class="fp">${f1(r.dst_pts)}</td><td>${f0(r.points_against)}</td><td>${f0(r.pass_yards_allowed)}</td><td>${f0(r.rush_yards_allowed)}</td><td>${f0(r.def_sacks)}</td><td>${f0(r.def_pressures)}</td><td>${f0(r.def_interceptions)}</td><td>${f0(r.fumble_recovery_opp)}</td><td>${f0((r.def_tds||0)+(r.special_teams_tds||0))}</td></tr>`).join('')}</tbody></table></div></section>
    ${personnelHTML(team)}
    ${oppLineHTML(team)}
    <section><h4>Team news <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>
    ${linksHTML('DEF:'+team,team+' D/ST',null,tm)}`;
  }
  /* ---------- kickers, defensive players, offensive linemen ----------
     data/site/kickers.json + def_week.json (weekly) and oline.json (season), loaded with the season files.
     A p:<gsis_id> card for one of these players gets its own layout; D/ST cards use them for personnel. */
  const X={K:new Map(),DW:new Map(),OL:new Map(),DT:new Map(),OLT:new Map()};let xP=null;
  function loadX(){
    if(xP)return xP;const g=n=>getJ(n).then(rows).catch(()=>[]);
    xP=Promise.all([g('kickers'),g('def_week'),g('oline')]).then(([k,d,o])=>{
      const grp=(arr,m)=>{for(const r of arr){let a=m.get(r.player_id);if(!a)m.set(r.player_id,a=[]);a.push(r)}for(const a of m.values())a.sort((x,y)=>x.week-y.week)};
      grp(k,X.K);grp(d,X.DW);for(const r of o){X.OL.set(r.player_id,r);let a=X.OLT.get(r.team);if(!a)X.OLT.set(r.team,a=[]);a.push(r)}
      for(const [pid,logs] of X.DW){const l=logs[logs.length-1];const S=k=>sum(logs.map(r=>r[k]));const sp=logs.map(r=>r.snap_pct).filter(num);
        const a={id:pid,name:l.player_display_name,pos:l.position,team:l.team,g:logs.length,snap:sp.length?mean(sp):null,tkl:S('tkl'),tfl:S('tfl'),sk:S('sk'),qbh:S('qbh'),prs:S('prs'),int:S('int'),pd:S('pd'),ff:S('ff'),tgt:S('tgt'),cmp:S('cmp'),yds:S('yds_alw'),tda:S('td_alw')};
        a.rating=a.tgt?((c,at,y,td,i)=>{const cl=v=>Math.max(0,Math.min(2.375,v));return (cl((c/at-.3)*5)+cl((y/at-3)*.25)+cl(td/at*20)+cl(2.375-i/at*25))/6*100})(a.cmp,a.tgt,a.yds,a.tda,a.int):null;
        let t=X.DT.get(a.team);if(!t)X.DT.set(a.team,t=[]);t.push(a);NAMEHINT[pid]=a.name}
      for(const [pid,logs] of X.K)NAMEHINT[pid]=logs[logs.length-1].player_display_name;for(const r of o)NAMEHINT[r.player_id]=r.name;
      return X});
    return xP;
  }
  const loadAll=()=>Promise.all([load(),loadX()]).then(()=>D);
  const nextLine=(team)=>{const n=nextOpp(team);return n?`<span>${gbtn(n.g.game_id,'Wk '+D.META.next_week)} ${oppBtn(n.opp,(n.at?'@ ':'vs ')+n.opp,null)}</span>`:`<span>Wk ${D.META.next_week} bye</span>`};
  const newsBlock=()=>`<section><h4>News <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>`;
  const injTag=id=>{const inj=D.INJ[id];return inj?`<span class="tag inj" title="${esc(inj[1])} · Wk ${inj[2]} report">${esc(inj[0].replace('Practice: ','Practice '))} · ${esc(inj[1])}</span>`:''};
  function kickerHTML(id){
    const logs=X.K.get(id);const l=logs[logs.length-1];const S=k=>sum(logs.map(r=>r[k]));const g=logs.length;
    const fgm=S('fg_made'),fga=S('fg_att');const n=nextOpp(l.team);
    return `<div class="pc-top">${l.headshot_url?`<img class="hs" src="${esc(l.headshot_url)}" alt="" loading="lazy" onerror="this.remove()">`:''}<div><h3>${esc(l.player_display_name)}</h3>
      <div class="sub"><span>K · ${dbtn(l.team,l.team,'tmlink')}</span><span>bye ${byeWeek(l.team)||'–'}</span>${nextLine(l.team)}</div></div></div>
    <section><div class="tags">${injTag(id)}${ownerTag(id)}</div><div class="tiles" style="margin-top:8px">
      <div><span>K pts / g</span><b>${f1(S('k_pts')/g)}</b><small>${g} g · Sleeper default</small></div>
      <div><span>FG</span><b>${fgm}/${fga}</b><small>${fga?Math.round(fgm/fga*100)+'%':''} · long ${Math.max(0,...logs.map(r=>r.fg_long||0))}</small></div>
      <div><span>40+ yd FG</span><b>${S('fg_40_49')+S('fg_50')}</b><small>50+: ${S('fg_50')}</small></div>
      <div><span>XP</span><b>${S('pat_made')}/${S('pat_att')}</b><small>${S('pat_missed')} missed</small></div>
      <div><span>Implied next</span><b>${n&&num(n.implied)?n.implied.toFixed(1):'–'}</b><small>team points (Vegas)</small></div></div></section>
    <section><h4>Kicker points by week <span class="sp"></span><span>FG 0–39 3 · 40–49 4 · 50+ 5 · XP 1 · miss −1</span></h4>${bars(logs.map(r=>({week:r.week,v:r.k_pts})),'v',l.team)}</section>
    <section><h4>Game log</h4><div class="scr"><table data-cols="card-k-log"><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>Pts</th><th>FG</th><th>0–39</th><th>40–49</th><th>50+</th><th>Long</th><th>XP</th></tr></thead><tbody>${logs.map(r=>`<tr><td class="l">${gbtn(gameKey(r.team,r.week),r.week)}</td><td class="l">${oppBtn(r.opponent_team,((gameOf(r.team,r.week)||{}).at?'@ ':'vs ')+r.opponent_team,null)}</td><td class="fp">${f1(r.k_pts)}</td><td>${r.fg_made||0}/${r.fg_att||0}</td><td>${r.fg_0_39||0}</td><td>${r.fg_40_49||0}</td><td>${r.fg_50||0}</td><td>${r.fg_long||'–'}</td><td>${r.pat_made||0}/${r.pat_att||0}</td></tr>`).join('')}</tbody></table></div></section>
    ${newsBlock()}${linksHTML(id,l.player_display_name,D.IDS[id],null)}`;
  }
  function defenderHTML(id){
    const logs=X.DW.get(id);const l=logs[logs.length-1];const a=(X.DT.get(l.team)||[]).find(x=>x.id===id)||{};const g=logs.length;
    return `<div class="pc-top"><div><h3>${esc(l.player_display_name)}</h3>
      <div class="sub"><span>${esc(l.position)} · ${dbtn(l.team,l.team+' D/ST','tmlink')}</span><span>bye ${byeWeek(l.team)||'–'}</span>${nextLine(l.team)}</div></div></div>
    <section><div class="tags">${injTag(id)}</div><div class="tiles" style="margin-top:8px">
      <div><span>Snap %</span><b>${pct(a.snap)}</b><small>${g} g</small></div>
      <div><span>Tackles</span><b>${a.tkl}</b><small>${f1(a.tkl/g)} / g · ${a.tfl} TFL</small></div>
      <div><span>Sacks</span><b>${a.sk}</b><small>${a.qbh} QB hits</small></div>
      <div><span>Pressures</span><b>${a.prs}</b><small>${f1(a.prs/g)} / g</small></div>
      <div><span>INT · PD</span><b>${a.int} · ${a.pd}</b><small>${a.ff} forced fumbles</small></div>
      ${a.tgt?`<div><span>In coverage</span><b>${a.cmp}/${a.tgt}</b><small>${a.yds} yds · ${a.tda} TD · rtg ${num(a.rating)?a.rating.toFixed(0):'–'}</small></div>`:''}</div></section>
    <section><h4>Game log</h4><div class="scr"><table data-cols="card-def-log"><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>Snap %</th><th>Tkl</th><th>TFL</th><th>Sk</th><th>QB hits</th><th>Prs</th><th>INT</th><th>PD</th><th>Tgt</th><th>Cmp</th><th>Yds alw</th><th>TD alw</th></tr></thead><tbody>${logs.map(r=>`<tr><td class="l">${gbtn(gameKey(r.team,r.week),r.week)}</td><td class="l">${oppBtn(r.opponent_team,((gameOf(r.team,r.week)||{}).at?'@ ':'vs ')+r.opponent_team,null)}</td><td>${pct(r.snap_pct)}</td><td>${f0(r.tkl)}</td><td>${f0(r.tfl)}</td><td>${f1(r.sk)}</td><td>${f0(r.qbh)}</td><td>${f0(r.prs)}</td><td>${f0(r.int)}</td><td>${f0(r.pd)}</td><td>${f0(r.tgt)}</td><td>${f0(r.cmp)}</td><td>${f0(r.yds_alw)}</td><td>${f0(r.td_alw)}</td></tr>`).join('')}</tbody></table></div><div class="note">Pressures and coverage are Pro Football Reference charting (via nflverse).</div></section>
    <section class="links"><a href="stats.html#defenders/${esc(l.team)}">All ${esc(l.team)} defenders →</a></section>
    ${newsBlock()}`;
  }
  function linemanHTML(id){
    const r=X.OL.get(id);const P=v=>num(v)?(v*100).toFixed(1)+'%':'–';
    const d=num(r.prs_on)&&num(r.prs_off)?r.prs_off-r.prs_on:null;
    return `<div class="pc-top"><div><h3>${esc(r.name)}</h3>
      <div class="sub"><span>${esc(r.slot||r.pos)} · ${dbtn(r.team,r.team,'tmlink')}</span><span>bye ${byeWeek(r.team)||'–'}</span>${nextLine(r.team)}</div></div></div>
    <section><div class="tags">${injTag(id)}</div><div class="tiles" style="margin-top:8px">
      <div><span>Starts</span><b>${r.starts}</b><small>${r.g} games played</small></div>
      <div><span>Snap %</span><b>${pct(r.snap_pct)}</b><small>${r.snaps} snaps</small></div>
      <div><span>Pressure % with</span><b>${P(r.prs_on)}</b><small>without ${P(r.prs_off)}${r.g_off?' ('+r.g_off+' g)':''}</small></div>
      <div><span>Sacks / g with</span><b>${f1(r.sk_on)}</b><small>without ${f1(r.sk_off)}</small></div>
      <div><span>YBC / carry with</span><b>${num(r.ybc_on)?r.ybc_on.toFixed(2):'–'}</b><small>without ${num(r.ybc_off)?r.ybc_off.toFixed(2):'–'}</small></div></div>
      <div class="note">${num(d)?`The line allowed pressure on ${Math.abs(d*100).toFixed(1)} pts ${d>0?'fewer':'more'} percent of dropbacks in his starts. `:''}Team-level with/without: free data has no per-lineman pressures allowed (that's PFF film charting / NFL tracking data). Small samples swing a lot.</div></section>
    <section class="links"><a href="stats.html#oline/${esc(r.team)}">${esc(r.team)} O-line →</a></section>
    ${newsBlock()}`;
  }
  /* team pressure rates: allowed by the offense, generated by the defense (per dropback) */
  function pressureRates(){
    if(IX._pr)return IX._pr;const out={};
    for(const [t,rr] of IX.byT){const db=sum(rr.map(r=>(r.attempts||0)+(r.sacks_suffered||0)));out[t]={alw:db?sum(rr.map(r=>r.pressures_allowed))/db:null}}
    for(const [t,rr] of IX.byT){let p=0,db=0;for(const r of rr){p+=r.def_pressures||0;const o=(IX.byT.get(r.opponent_team)||[]).find(x=>x.week===r.week);if(o)db+=(o.attempts||0)+(o.sacks_suffered||0)}out[t].gen=db?p/db:null}
    const rk=(k,desc)=>Object.keys(out).filter(t=>num(out[t][k])).sort((a,b)=>desc?out[b][k]-out[a][k]:out[a][k]-out[b][k]).forEach((t,i)=>out[t][k+'_rk']=i+1);
    rk('alw',false);rk('gen',true);return IX._pr=out;
  }
  function personnelHTML(team){
    const ds=(X.DT.get(team)||[]);if(!ds.length)return '';
    const rush=[...ds].filter(a=>a.prs>0).sort((a,b)=>b.prs-a.prs).slice(0,5);
    const cov=[...ds].filter(a=>a.tgt>=6).sort((a,b)=>b.yds-a.yds).slice(0,5);
    const nm=a=>`${pbtn(a.id,a.name)} <span class="dim">${esc(a.pos||'')}</span>`;
    return `<section><h4>Pass rush <span class="sp"></span><span>season</span></h4><div class="scr"><table data-cols="card-dst-rush"><thead><tr><th class="l">Player</th><th>Snap %</th><th>Prs</th><th>Sk</th><th>QB hits</th><th>TFL</th></tr></thead><tbody>${rush.map(a=>`<tr><td class="l">${nm(a)}</td><td>${pct(a.snap)}</td><td>${a.prs}</td><td>${f1(a.sk)}</td><td>${a.qbh}</td><td>${a.tfl}</td></tr>`).join('')}</tbody></table></div></section>
    ${cov.length?`<section><h4>Coverage: most yards allowed</h4><div class="scr"><table data-cols="card-dst-cov"><thead><tr><th class="l">Player</th><th>Tgt</th><th>Cmp</th><th>Yds</th><th>TD</th><th>INT</th><th>PD</th><th>Rtg</th></tr></thead><tbody>${cov.map(a=>`<tr><td class="l">${nm(a)}</td><td>${a.tgt}</td><td>${a.cmp}</td><td>${a.yds}</td><td>${a.tda}</td><td>${a.int}</td><td>${a.pd}</td><td>${num(a.rating)?a.rating.toFixed(0):'–'}</td></tr>`).join('')}</tbody></table></div><div class="note">Rating = passer rating when targeted (higher = easier to throw on). Pro Football Reference charting.</div></section>`:''}
    <section class="links"><a href="stats.html#defenders/${esc(team)}">All ${esc(team)} defenders →</a></section>`;
  }
  function oppLineHTML(team){
    const nx=nextOpp(team);if(!nx)return '';const opp=nx.opp;const ol=(X.OLT.get(opp)||[]);if(!ol.length)return '';
    const pr=pressureRates();const me=pr[team]||{},them=pr[opp]||{};const n=Object.keys(pr).length;
    const order=['LT','LG','C','RG','RT'];
    let st=order.map(s=>ol.find(r=>r.slot===s)).filter(Boolean);if(st.length<5)st=[...ol].sort((a,b)=>b.snap_pct-a.snap_pct).slice(0,5);
    const P=v=>num(v)?(v*100).toFixed(1)+'%':'–';
    return `<section><h4>Wk ${D.META.next_week} matchup: ${esc(team)} pass rush vs ${esc(opp)} O-line</h4>
      <div class="tiles"><div><span>${esc(team)} pressure rate</span><b>${P(me.gen)}</b><small>${me.gen_rk?ord(me.gen_rk)+' of '+n+' (1st = most)':''}</small></div>
      <div><span>${esc(opp)} allows</span><b>${P(them.alw)}</b><small>${them.alw_rk?ord(them.alw_rk)+' of '+n+' (1st = fewest)':''}</small></div></div>
      <div class="scr" style="margin-top:8px"><table data-cols="card-opp-ol"><thead><tr><th class="l">Slot</th><th class="l">Lineman</th><th>Starts</th><th>Snap %</th><th>Prs % with</th><th>without</th><th class="l">Injury</th></tr></thead><tbody>${st.map(r=>`<tr><td class="l">${esc(r.slot||r.pos)}</td><td class="l">${pbtn(r.player_id,r.name)}</td><td>${r.starts}</td><td>${pct(r.snap_pct)}</td><td>${P(r.prs_on)}</td><td>${P(r.prs_off)}</td><td class="l dim">${esc(r.inj||'')}</td></tr>`).join('')}</tbody></table></div>
      <div class="note">Pressure rate = pressures ÷ dropbacks. With/without = the ${esc(opp)} line in games each starter started vs didn't (team-level; no free per-lineman pressure data).</div></section>
    <section class="links"><a href="stats.html#oline/${esc(opp)}">${esc(opp)} O-line →</a>${oppBtn(opp,esc(opp)+' D/ST card',null)}</section>`;
  }
  /* ---------- game card (g:<nflverse game_id>) ---------- */
  const gameById=id=>D.G.find(g=>g.game_id===id)||null;
  const gameKey=(team,week)=>{const x=gameOf(team,week);return x?x.g.game_id:null};
  /* small link to a game card; falls back to plain text when the game isn't in the schedule */
  function gbtn(gid,label,cls){return gid?`<button type="button" class="gl-g ${cls||''}" data-card="g:${esc(gid)}" title="Game card">${label}</button>`:label}
  function qbId(team,name){if(!name)return null;const n=name.toLowerCase();for(const [pid,logs] of IX.byP){const l=logs[logs.length-1];if(l.position==='QB'&&l.team===team&&String(l.player_display_name).toLowerCase()===n)return pid}return null}
  function gameHTML(gid){
    const g=gameById(gid);if(!g)return `<div class="pc-top"><div><h3>Game not found</h3><div class="sub">${esc(gid)}</div></div></div>`;
    const sc=scoring(),sk=SCORING[sc].k;const fin=num(g.home_score)&&num(g.away_score);const A=g.away_team,H=g.home_team,w=g.week;
    const d=new Date(g.gameday+'T12:00:00');const date=isNaN(d)?'':d.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});
    const fav=num(g.spread_line)&&g.spread_line!==0?(g.spread_line>0?H:A):null;
    const spread=num(g.spread_line)?(g.spread_line===0?'Pick’em':`${fav} −${Math.abs(g.spread_line)}`):'–';
    const indoor=/dome|closed/i.test(g.roof||'');
    const weather=indoor?'Indoors ('+esc(g.roof)+')':(num(g.temp)||num(g.wind))?[num(g.temp)?g.temp+'°F':'',num(g.wind)?'wind '+g.wind+' mph':''].filter(Boolean).join(' · ')+(g.roof?' · '+esc(g.roof):''):`${esc(g.roof||'outdoors')} · ${fin?'not recorded':'not posted yet'}`;
    const side=(t,qb,imp,score,rest)=>{const q=qbId(t,qb);const win=fin&&score>(t===H?g.away_score:g.home_score);
      return `<div class="gc-side ${win?'win':''}"><div class="gc-tm" title="Open the ${esc(t)} defense card">${dbtn(t,t)}</div><b class="gc-n">${fin?score:(num(imp)?imp.toFixed(1):'–')}</b><small>${fin?(win?'won':'final'):'implied pts'}</small>
        <div class="gc-qb">QB ${q?pbtn(q,qb):esc(qb||'–')}</div><small>${num(rest)?rest+' days rest':''}</small></div>`};
    /* team form: season per-game, from teams.json */
    const tf=t=>{const rr=(IX.byT.get(t)||[]).filter(r=>r.week<w||!fin);const n=rr.length||1;const s=k=>sum(rr.map(r=>r[k]))/n;return {g:rr.length,pf:s('points_for'),pa:s('points_against'),yds:s('total_yards'),ya:s('yards_allowed'),prs:s('def_pressures'),pra:s('pressures_allowed'),dst:s('dst_pts')}};
    const fa=tf(A),fh=tf(H);const row=(lbl,k,dg,hi)=>{const a=fa[k],h=fh[k];const better=hi===null?'':(hi?(a>h?'a':'h'):(a<h?'a':'h'));
      return `<tr><td class="${better==='a'?'gc-b':''}">${num(a)?a.toFixed(dg):'–'}</td><td class="l gc-l">${lbl}</td><td class="${better==='h'?'gc-b':''}">${num(h)?h.toFixed(dg):'–'}</td></tr>`};
    /* players: in a finished game, who scored; before it, who to watch (season FP/g) */
    let pl;
    if(fin){pl=D.P.filter(r=>r.week===w&&(r.team===A||r.team===H)&&num(r[sk])).sort((a,b)=>b[sk]-a[sk]).slice(0,10).map(r=>({id:r.player_id,name:r.player_display_name,pos:r.position,team:r.team,v:r[sk],sub:statLine(r)}))}
    else{pl=[];for(const t of [A,H]){const opp=t===A?H:A;for(const [pid,logs] of IX.byP){const l=logs[logs.length-1];if(l.team!==t||logs.length<2)continue;const v=mean(logs.map(x=>x[sk]));if(num(v))pl.push({id:pid,name:l.player_display_name,pos:l.position,team:t,v,opp,sub:''})}}
      pl.sort((a,b)=>b.v-a.v);pl=pl.slice(0,10)}
    const plRows=pl.map(p=>`<tr><td class="l">${pbtn(p.id,p.name)} <span class="dim">${p.pos} · ${p.team}</span></td><td class="fp">${f1(p.v)}</td><td class="l dim">${fin?esc(p.sub):mrk(p.opp,p.pos)}</td></tr>`).join('');
    return `<div class="pc-top"><div><h3>${esc(A)} @ ${esc(H)}</h3>
      <div class="sub"><span>Week ${w}</span><span>${esc(date)}${g.gametime?' · '+esc(g.gametime)+' ET':''}</span>${g.div_game?'<span>Division</span>':''}<span>${esc(g.stadium||'')}</span></div></div></div>
    <section><div class="gc-sides">${side(A,g.away_qb_name,g.away_implied,g.away_score,g.away_rest)}<div class="gc-at">@</div>${side(H,g.home_qb_name,g.home_implied,g.home_score,g.home_rest)}</div></section>
    <section><h4>Vegas line</h4><div class="tiles"><div><span>Spread</span><b>${esc(spread)}</b><small>${fin&&num(g.spread_line)?((g.home_score-g.away_score)>g.spread_line?H:(g.home_score-g.away_score)<g.spread_line?A:'push')+(fin&&(g.home_score-g.away_score)!==g.spread_line?' covered':''):'closing/latest'}</small></div>
      <div><span>Over/under</span><b>${num(g.total_line)?g.total_line:'–'}</b><small>${fin&&num(g.total_line)?(g.home_score+g.away_score)+' scored · '+((g.home_score+g.away_score)>g.total_line?'over':(g.home_score+g.away_score)<g.total_line?'under':'push'):''}</small></div>
      <div><span>Implied</span><b>${num(g.away_implied)?g.away_implied.toFixed(1):'–'}–${num(g.home_implied)?g.home_implied.toFixed(1):'–'}</b><small>${esc(A)}–${esc(H)}</small></div></div></section>
    <section><h4>Weather</h4><div>${weather}</div></section>
    <section><h4>${fin?'Top fantasy scorers':'Players to watch'} <span class="sp"></span><span>${SCORING[sc].label}${fin?' this game':' per game this season'}</span></h4><div class="scr"><table><tbody>${plRows||'<tr><td class="dim">No player data yet.</td></tr>'}</tbody></table></div>${fin?'':'<div class="note">Rank = how many points the opponent allows to that position (green = soft matchup).</div>'}</section>
    <section><h4>Team form <span class="sp"></span><span>per game${fin?' before this game':' this season'}</span></h4><div class="scr"><table class="gc-form"><thead><tr><th>${esc(A)}</th><th class="l gc-l"></th><th>${esc(H)}</th></tr></thead><tbody>
      ${row('Points scored','pf',1,true)}${row('Points allowed','pa',1,false)}${row('Yards','yds',0,true)}${row('Yards allowed','ya',0,false)}${row('Pressures made','prs',1,true)}${row('Pressures allowed','pra',1,false)}${row('D/ST points','dst',1,true)}
    </tbody></table></div><div class="note">Bold = the better side.</div></section>`;
  }
  function statLine(r){const p=[];if(r.attempts)p.push(`${r.completions}/${r.attempts}, ${r.passing_yards} yds, ${r.passing_tds} TD${r.passing_interceptions?', '+r.passing_interceptions+' INT':''}`);
    if(r.carries)p.push(`${r.carries} car, ${r.rushing_yards} yds${r.rushing_tds?', '+r.rushing_tds+' TD':''}`);if(r.targets)p.push(`${r.receptions}/${r.targets}, ${r.receiving_yards} yds${r.receiving_tds?', '+r.receiving_tds+' TD':''}`);return p.join(' · ')}
  const NAMEHINT={};

  /* ---------- popup ----------
     The card stack lives in the address bar (?card=p:<id>) and in history.state, so the browser back button
     and the phone back swipe step back one card, a crumb trail jumps back further, and any card can be shared
     or bookmarked. Opening a name inside a card pushes a new card (capped at MAXDEPTH). */
  const MAXDEPTH=12;
  let el=null,shade=null,anchor=null,stack=[];
  let pendingBack=false,afterPop=null;
  const cardState=()=>history.state&&history.state.nflsCard?history.state:null;
  const depth=()=>{const s=cardState();return s?s.nflsDepth||0:0};
  const validKey=k=>typeof k==='string'&&/^[pdg]:[A-Za-z0-9_-]+$/.test(k);
  function urlFor(key){const u=new URL(location.href);if(key)u.searchParams.set('card',key);else u.searchParams.delete('card');return u.pathname+u.search+u.hash}
  function writeState(mode,d){const top=stack[stack.length-1];history[mode]({nflsCard:stack.map(x=>({key:x.key,pos:x.pos||''})),nflsDepth:d},'',urlFor(top&&top.key))}
  function closeLocal(){if(el){el.remove();el=null}if(shade){shade.remove();shade=null}if(anchor){anchor.setAttribute('aria-expanded','false');anchor=null}stack=[]}
  /* close = go back past every card entry we added, so Back afterwards leaves the page normally */
  function close(){
    if(!el)return;const d=depth();closeLocal();
    if(d>0){pendingBack=true;history.go(-d)}else if(new URLSearchParams(location.search).has('card'))history.replaceState(null,'',urlFor(null));
  }
  function place(){
    if(!el)return;const phone=matchMedia('(max-width:640px)').matches;
    if(phone){if(!shade){shade=document.createElement('div');shade.className='pc-shade';shade.onclick=close;document.body.appendChild(shade)}return}
    const w=el.offsetWidth,h=el.offsetHeight,cw=document.documentElement.clientWidth;
    if(!anchor||!anchor.isConnected){el.style.left=Math.max(scrollX+12,scrollX+(cw-w)/2)+'px';el.style.top=(scrollY+64)+'px';return}
    const r=anchor.getBoundingClientRect();
    let left=r.left+scrollX;left=Math.min(left,scrollX+cw-w-12);left=Math.max(scrollX+12,left);
    const below=innerHeight-r.bottom-12,above=r.top-60;let top=r.bottom+scrollY+6;
    if(below<Math.min(h,360)){if(above>=h)top=r.top+scrollY-h-6;else setTimeout(()=>{if(el)el.scrollIntoView({block:'nearest',behavior:'smooth'})},30)}
    el.style.left=left+'px';el.style.top=top+'px';
  }
  const keyName=k=>k[0]==='d'?k.slice(2)+' D/ST':k[0]==='g'?(m=>m?m[2]+' @ '+m[3]+' · Wk '+(+m[1]):k.slice(2))(k.slice(2).match(/^\d{4}_(\d+)_([A-Z]+)_([A-Z]+)$/)):(NAMEHINT[k.slice(2)]||'Player');
  const ICON={pop:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="7" width="14" height="14" rx="2"/><path d="M10 3h11v11"/></svg>',
    link:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>'};
  /* every <section> with a heading gets an id (data-sec) so it can be popped out on its own */
  const slug=s=>s.toLowerCase().replace(/\b(ppr|half|std)\b/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  function tagSections(root,withButtons){
    root.querySelectorAll('section').forEach(sec=>{const h=sec.querySelector(':scope > h4');if(!h)return;
      const label=(h.firstChild&&h.firstChild.nodeType===3?h.firstChild.textContent:h.textContent).trim();const id=slug(label);if(!id)return;
      sec.dataset.sec=id;sec.dataset.secLabel=label;
      if(withButtons&&!h.querySelector('.pc-pop')){if(!h.querySelector('.sp'))h.insertAdjacentHTML('beforeend','<span class="sp"></span>');
        h.insertAdjacentHTML('beforeend',`<button type="button" class="pc-pop" data-pop="${id}" title="Pop out: keep “${esc(label)}” on screen while you browse" aria-label="Pop out ${esc(label)}">${ICON.pop}</button>`)}});
  }
  function cardHTML(key,pos){const kind=key[0],id=key.slice(2);try{return kind==='d'?defHTML(id,pos):kind==='g'?gameHTML(id):playerHTML(id)}catch(e){return `<div class="pc-top"><div><h3>Couldn't build this card</h3></div></div><section class="dim">${esc(e.message)}</section>`}}
  const newsKey=key=>key[0]==='d'?'DEF:'+key.slice(2):key[0]==='g'?null:key.slice(2);
  function render(){
    const cur=stack[stack.length-1];if(!cur||!el)return;
    const html=cardHTML(cur.key,cur.pos);
    const crumbs=stack.length>1?`<nav class="pc-crumbs" aria-label="Card trail">${stack.map((x,i)=>i===stack.length-1?`<span aria-current="true">${esc(keyName(x.key))}</span>`:`<button type="button" data-crumb="${i}">${esc(keyName(x.key))}</button>`).join('<i>›</i>')}</nav>`:'';
    /* header (close, tools, crumbs, name) is one sticky block so it never scrolls out of reach */
    el.innerHTML=`<div class="pc-head"><button type="button" class="pc-x" aria-label="Close">×</button><div class="pc-tools"><button type="button" data-copylink title="Copy a link to this card">${ICON.link}</button><button type="button" data-pin-card title="Pop out the whole card">${ICON.pop}</button></div>${crumbs}</div>`+html;
    {const head=el.querySelector('.pc-head'),top=el.querySelector(':scope > .pc-top');if(head&&top)head.appendChild(top)}
    if(stack.length>1){const top=el.querySelector('.pc-top');if(top)top.insertAdjacentHTML('afterbegin',`<button type="button" class="pc-back" aria-label="Back">←</button>`)}
    if(crumbs){const c=el.querySelector('.pc-crumbs');c.scrollLeft=c.scrollWidth}
    tagSections(el,true);
    el.scrollTop=0;fillOwner(el);fillNews(el,newsKey(cur.key),false);
  }
  function fillOwner(root){
    if(!window.NFLS||!root)return;const lg=NFLS.getLeague();if(!lg)return;
    NFLS.rosterStatus().then(rs=>{if(!rs||!root.isConnected)return;root.querySelectorAll('[data-own]').forEach(s=>{const k=s.dataset.own;const m=rs.map.get(k);
      s.outerHTML=m?(m.status==='mine'?`<span class="tag mine">On ${esc(lg.viewer||'your')} roster · ${esc(lg.name)}</span>`:`<span class="tag">Rostered by ${esc(m.team)} · ${esc(lg.name)}</span>`):`<span class="tag fa">Free agent in ${esc(lg.name)}</span>`})}).catch(()=>{});
  }
  function fillNews(root,key,all){
    const box=root&&root.querySelector('[data-news]');if(!box)return;const name=NAMEHINT[key]||'';
    newsFor(key).then(n=>{if(!box.isConnected)return;box.innerHTML=newsHTML(n,all,name);const s=root.querySelector('[data-news-src]');if(s)s.textContent=n.items.length?newsSrc(n):'';
      const m=box.querySelector('[data-more]');if(m)m.onclick=ev=>{ev.stopPropagation();fillNews(root,key,true)}}).catch(()=>{box.textContent="Couldn't load news."});
  }
  function mk(a){
    anchor=a||null;if(anchor)anchor.setAttribute('aria-expanded','true');
    el=document.createElement('div');el.className='pc';el.setAttribute('role','dialog');el.setAttribute('aria-label','Player card');
    el.innerHTML=`<button type="button" class="pc-x" aria-label="Close">×</button><div class="pc-top"><div><h3>${esc(a?a.textContent.trim().split('\n')[0]:'')}</h3><div class="sub"><span><span class="spin"></span>Loading…</span></div></div></div>`;
    document.body.appendChild(el);place();
  }
  function show(){const want=stack[stack.length-1]&&stack[stack.length-1].key;
    loadAll().then(()=>{if(el&&stack.length&&stack[stack.length-1].key===want){render();place()}}).catch(e=>{if(el)el.innerHTML=`<button type="button" class="pc-x">×</button><section>Couldn't load the season data (${esc(e.message)}).</section>`})}
  function open(key,a,pos){
    if(!validKey(key))return;
    if(pendingBack){afterPop=()=>open(key,a,pos);return}
    if(el&&a&&anchor===a){close();return}
    const d=el?depth():0;closeLocal();mk(a);
    stack=[{key,pos:pos||''}];writeState('pushState',d+1);show();
  }
  function push(key,pos){
    if(!validKey(key))return;
    if(!el){open(key,null,pos);return}
    stack.push({key,pos:pos||''});
    if(stack.length>MAXDEPTH){stack.shift();writeState('replaceState',depth())}else writeState('pushState',depth()+1);
    render();
  }
  function goBack(steps){
    steps=Math.min(steps,stack.length-1);if(steps<=0)return;
    if(depth()>=steps)history.go(-steps);else{stack=stack.slice(0,stack.length-steps);writeState('replaceState',depth());render()}
  }
  addEventListener('popstate',e=>{
    if(pendingBack){pendingBack=false;closeLocal();const f=afterPop;afterPop=null;if(f)f();return}
    const s=e.state&&e.state.nflsCard;
    if(s&&s.length&&s.every(x=>validKey(x.key))){stack=s.map(x=>({key:x.key,pos:x.pos||''}));if(!el)mk(null);show()}
    else if(el)closeLocal();
  });
  /* a ?card= link (shared, bookmarked or reloaded) opens that card when the page loads */
  (function fromURL(){
    const s=cardState();
    if(s&&s.nflsCard.length&&s.nflsCard.every(x=>validKey(x.key))){stack=s.nflsCard.map(x=>({key:x.key,pos:x.pos||''}))}
    else{const k=new URLSearchParams(location.search).get('card');if(!validKey(k))return;stack=[{key:k,pos:''}];writeState('replaceState',0)}
    mk(null);show();
  })();

  /* ---------- pop-out windows ----------
     ⧉ on a card (or on one of its sections) floats it in its own window: drag it by the title bar, resize from
     the corner, minimize, or open it back up as a card. Windows stay put while you browse other cards and
     follow you to other pages in the same tab (sessionStorage). Names inside a window open cards too. */
  const MAXPINS=6,ZBASE=72;
  const SS={get(){try{const v=JSON.parse(sessionStorage.getItem('nfls-pins')||'[]');return Array.isArray(v)?v.filter(p=>p&&validKey(p.key)):[]}catch(e){return []}},set(v){try{sessionStorage.setItem('nfls-pins',JSON.stringify(v))}catch(e){}}};
  let pins=SS.get();const pinEls=new Map();let zTop=ZBASE;
  const savePins=()=>SS.set(pins);
  const pinTitle=p=>keyName(p.key)+(p.sec?' · '+p.label:'');
  function pinBody(p){
    const html=cardHTML(p.key,p.pos);if(!p.sec)return html;
    const t=document.createElement('div');t.innerHTML=html;tagSections(t,false);
    const s=t.querySelector(`section[data-sec="${p.sec}"]`);return s?s.outerHTML:`<section class="dim">That section isn't on this card anymore.</section>`;
  }
  function fillPin(p){const w=pinEls.get(p.id);if(!w)return;const b=w.querySelector('.pw-b');b.innerHTML=pinBody(p);w.querySelector('.pw-h b').textContent=pinTitle(p);fillOwner(b);fillNews(b,newsKey(p.key),false)}
  function front(w){if(zTop>ZBASE+40){zTop=ZBASE;[...pinEls.values()].sort((a,b)=>(+a.style.zIndex)-(+b.style.zIndex)).forEach(x=>x.style.zIndex=++zTop)}w.style.zIndex=++zTop}
  function clampPin(p){const vw=document.documentElement.clientWidth,vh=innerHeight;p.x=Math.max(4-(p.w||300)+60,Math.min(p.x,vw-60));p.y=Math.max(0,Math.min(p.y,vh-36))}
  function mountPin(p){
    const w=document.createElement('div');w.className='pw'+(p.min?' min':'');w.setAttribute('role','dialog');w.dataset.pin=p.id;
    w.innerHTML=`<div class="pw-h"><b></b><span class="sp"></span><button type="button" data-pw-open title="Open as a card">↗</button><button type="button" data-pw-min title="Minimize">${p.min?'▢':'–'}</button><button type="button" data-pw-x title="Close">×</button></div><div class="pw-b"></div>`;
    clampPin(p);w.style.left=p.x+'px';w.style.top=p.y+'px';if(p.w)w.style.width=p.w+'px';if(p.h&&!p.min)w.style.height=p.h+'px';
    document.body.appendChild(w);pinEls.set(p.id,w);front(w);fillPin(p);
    const h=w.querySelector('.pw-h');let drag=null;
    h.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;e.preventDefault();drag={dx:e.clientX-p.x,dy:e.clientY-p.y};h.setPointerCapture(e.pointerId);w.classList.add('drag')});
    h.addEventListener('pointermove',e=>{if(!drag)return;p.x=e.clientX-drag.dx;p.y=e.clientY-drag.dy;clampPin(p);w.style.left=p.x+'px';w.style.top=p.y+'px'});
    const end=()=>{if(!drag)return;drag=null;w.classList.remove('drag');savePins()};h.addEventListener('pointerup',end);h.addEventListener('pointercancel',end);
    w.addEventListener('pointerdown',()=>front(w),true);
    if(window.ResizeObserver){let t=null;new ResizeObserver(()=>{if(p.min||!w.isConnected)return;clearTimeout(t);t=setTimeout(()=>{const r=w.getBoundingClientRect();if(Math.abs(r.width-(p.w||0))>2||Math.abs(r.height-(p.h||0))>2){p.w=Math.round(r.width);p.h=Math.round(r.height);savePins()}},150)}).observe(w)}
  }
  function addPin(key,pos,sec,label){
    if(pins.some(p=>p.key===key&&(p.sec||'')===(sec||''))){const p=pins.find(p=>p.key===key&&(p.sec||'')===(sec||''));const w=pinEls.get(p.id);if(w){front(w);w.classList.add('flash');setTimeout(()=>w.classList.remove('flash'),600)}return}
    const phone=matchMedia('(max-width:640px)').matches,vw=document.documentElement.clientWidth,n=pins.length;
    const width=phone?vw-16:(sec?360:440);
    const p={id:'w'+Date.now().toString(36),key,pos:pos||'',sec:sec||'',label:label||'',w:width,h:0,min:false,
      x:phone?8:vw-width-20-n*26,y:phone?8+n*40:76+n*30};
    pins.push(p);while(pins.length>MAXPINS)removePin(pins[0].id);savePins();loadAll().then(()=>mountPin(p));
  }
  function removePin(id){const w=pinEls.get(id);if(w)w.remove();pinEls.delete(id);pins=pins.filter(p=>p.id!==id);savePins()}
  function refreshPins(){for(const p of pins)fillPin(p)}
  if(pins.length)loadAll().then(()=>pins.forEach(mountPin)).catch(()=>{});
  addEventListener('resize',()=>{for(const p of pins){const w=pinEls.get(p.id);if(!w)continue;clampPin(p);w.style.left=p.x+'px';w.style.top=p.y+'px'}});

  function copyText(t,btn){const ok=()=>{if(btn){btn.classList.add('ok');btn.title='Link copied';setTimeout(()=>btn.classList.remove('ok'),1200)}};try{navigator.clipboard.writeText(t).then(ok,()=>prompt('Copy this link',t))}catch(err){prompt('Copy this link',t)}}
  function refreshNews(){const cur=stack[stack.length-1];if(el&&cur)fillNews(el,newsKey(cur.key),false);for(const p of pins){const w=pinEls.get(p.id);if(w)fillNews(w.querySelector('.pw-b'),newsKey(p.key),false)}}
  function setScoring(v){LS.set('scoring',v);IX&&(IX._rank={});render();refreshPins();window.dispatchEvent(new CustomEvent('nfls-scoring',{detail:v}))}
  document.addEventListener('click',e=>{
    const pw=e.target.closest('.pw');
    if(pw){
      const p=pins.find(x=>x.id===pw.dataset.pin);if(!p)return;
      if(e.target.closest('[data-pw-x]')){removePin(p.id);return}
      if(e.target.closest('[data-pw-min]')){p.min=!p.min;pw.classList.toggle('min',p.min);e.target.closest('[data-pw-min]').textContent=p.min?'▢':'–';pw.style.height=p.min?'':(p.h?p.h+'px':'');savePins();return}
      if(e.target.closest('[data-pw-open]')){push(p.key,p.pos);return}
      const nm=e.target.closest('[data-nmode]');if(nm){LS.set('newsmix',nm.dataset.nmode==='mix');refreshNews();return}
      const sc=e.target.closest('[data-sc] button');if(sc){setScoring(sc.dataset.v);return}
      const np=e.target.closest('.pc-news p');if(np){np.classList.toggle('open');return}
      const cp=e.target.closest('[data-copyname]');if(cp){try{navigator.clipboard.writeText(cp.dataset.copyname)}catch(err){}return}
      const t=e.target.closest('[data-card],.opp[data-opp]');if(t){e.preventDefault();const k=t.dataset.card||('d:'+t.dataset.opp);if(t.dataset.name)NAMEHINT[k.slice(2)]=t.dataset.name;push(k,t.dataset.pos);return}
      return;
    }
    if(el&&el.contains(e.target)){
      if(e.target.closest('.pc-x')){close();return}
      if(e.target.closest('.pc-back')){goBack(1);return}
      const cr=e.target.closest('[data-crumb]');if(cr){goBack(stack.length-1-(+cr.dataset.crumb));return}
      const cur=stack[stack.length-1];
      if(e.target.closest('[data-copylink]')){copyText(location.origin+urlFor(cur.key),e.target.closest('[data-copylink]'));return}
      if(e.target.closest('[data-pin-card]')){addPin(cur.key,cur.pos,'','');return}
      const pp=e.target.closest('.pc-pop');if(pp){const s=pp.closest('section');addPin(cur.key,cur.pos,pp.dataset.pop,s&&s.dataset.secLabel);return}
      const nm=e.target.closest('[data-nmode]');if(nm){LS.set('newsmix',nm.dataset.nmode==='mix');refreshNews();return}
      const sc=e.target.closest('[data-sc] button');if(sc){setScoring(sc.dataset.v);return}
      const np=e.target.closest('.pc-news p');if(np){np.classList.toggle('open');return}
      const cp=e.target.closest('[data-copyname]');if(cp){try{navigator.clipboard.writeText(cp.dataset.copyname)}catch(err){}return}
      const t=e.target.closest('[data-card],.opp[data-opp]');if(t){e.preventDefault();const k=t.dataset.card||('d:'+t.dataset.opp);if(t.dataset.name)NAMEHINT[k.slice(2)]=t.dataset.name;push(k,t.dataset.pos);return}
      return;
    }
    const t=e.target.closest('[data-card],.opp[data-opp]');
    if(t&&!e.target.closest('.plink,.av,a[href]:not([data-card])')){e.preventDefault();e.stopPropagation();const k=t.dataset.card||('d:'+t.dataset.opp);if(t.dataset.name)NAMEHINT[k.slice(2)]=t.dataset.name;open(k,t,t.dataset.pos);return}
    if(el&&!e.target.closest('.pmenu,.glpop,.colpanel'))close();
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&el)close()});
  /* a page changing its own #hash (Stats tabs, Lab, Guide) closes the card; Trade's #a= state doesn't */
  addEventListener('hashchange',()=>{if(location.hash.startsWith('#a='))return;if(el)closeLocal();if(new URLSearchParams(location.search).has('card'))history.replaceState(null,'',urlFor(null))});
  /* phones: drag the card down to close it (from the header, or from the content once it's scrolled to the top).
     Past ~110px or a quick flick it closes; otherwise it snaps back. The page behind never moves. */
  (function(){
    const phone=matchMedia('(max-width:640px)');let drag=null;
    document.addEventListener('touchstart',e=>{
      if(!el||!phone.matches||e.touches.length!==1||!el.contains(e.target))return;
      if(e.target.closest('.pc-crumbs,.scr,.seg,input,select,textarea'))return;
      const inHead=!!e.target.closest('.pc-head');if(!inHead&&el.scrollTop>0)return;
      drag={y0:e.touches[0].clientY,x0:e.touches[0].clientX,t0:Date.now(),dy:0,on:false,inHead};
    },{passive:true});
    document.addEventListener('touchmove',e=>{
      if(!drag||!el)return;const t=e.touches[0];const dy=t.clientY-drag.y0,dx=t.clientX-drag.x0;
      if(!drag.on){if(Math.abs(dx)>Math.abs(dy)&&Math.abs(dx)>8){drag=null;return}
        if(dy<-4&&!drag.inHead){drag=null;return}   /* scrolling the card up: let it scroll */
        if(dy>6&&(drag.inHead||el.scrollTop<=0)){drag.on=true;el.style.transition='none';if(shade)shade.style.transition='none'}else return}
      e.preventDefault();drag.dy=Math.max(0,dy);
      el.style.transform=`translateY(${drag.dy}px)`;if(shade)shade.style.opacity=String(Math.max(0,1-drag.dy/400));
    },{passive:false});
    const end=()=>{
      if(!drag)return;const d=drag;drag=null;if(!d.on||!el)return;
      const fast=d.dy/Math.max(1,Date.now()-d.t0)>0.6;
      el.style.transition='transform .2s ease';if(shade)shade.style.transition='opacity .2s ease';
      if(d.dy>110||(fast&&d.dy>30)){el.style.transform='translateY(100%)';if(shade)shade.style.opacity='0';const me=el;setTimeout(()=>{if(el===me)close()},190)}
      else{el.style.transform='';if(shade)shade.style.opacity='';setTimeout(()=>{if(el){el.style.transition='';}},220)}
    };
    document.addEventListener('touchend',end,{passive:true});document.addEventListener('touchcancel',end,{passive:true});
  })();
  addEventListener('resize',()=>{if(el)place()});

  /* markup helpers for pages */
  function pbtn(id,name,cls){return `<button type="button" class="pname ${cls||''}" data-card="p:${esc(id)}" data-name="${esc(name)}" aria-expanded="false">${esc(name)}</button>`}
  function dbtn(team,label,cls){return `<button type="button" class="pname ${cls||''}" data-card="d:${esc(team)}" aria-expanded="false">${esc(label||team)}</button>`}
  window.NFLSCards={provide,load,loadX,open,push,close,addPin,gbtn,gameKey,pbtn,dbtn,oppBtn,mrk,newsFor,playerSummary,defSummary,teamDefense,dvp,gameOf,nextOpp,byeWeek,scoring,SCORING,data:()=>D,index:()=>IX};
})();
