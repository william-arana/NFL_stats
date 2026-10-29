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
    if(!IX._td){const all=[...IX.byT.keys()].map(t=>{const rr=IX.byT.get(t),m=rr.length||1,s=k=>sum(rr.map(r=>r[k]))/m;return {t,pa:s('points_against'),ya:s('yards_allowed'),pr:s('def_pressures'),sk:s('def_sacks'),tk:s('def_interceptions')+s('fumble_recovery_opp'),dst:s('dst_pts')}});IX._td=all}
    const all=IX._td;const rank=(k,desc)=>[...all].sort((a,b)=>desc?b[k]-a[k]:a[k]-b[k]).findIndex(x=>x.t===team)+1;
    const rr=IX.byT.get(team)||[];const n=rr.length||1;const per=k=>sum(rr.map(r=>r[k]))/n;
    const w=rr.filter(r=>num(r.points_for));
    return {rows:rr,rec:`${w.filter(r=>r.points_for>r.points_against).length}-${w.filter(r=>r.points_for<r.points_against).length}`,g:rr.length,pa:per('points_against'),ya:per('yards_allowed'),pya:per('pass_yards_allowed'),rya:per('rush_yards_allowed'),pr:per('def_pressures'),sk:per('def_sacks'),tk:per('def_interceptions')+per('fumble_recovery_opp'),dst:per('dst_pts'),
      rk:{pa:rank('pa',false),ya:rank('ya',false),pr:rank('pr',true),sk:rank('sk',true),tk:rank('tk',true),dst:rank('dst',true)},n:all.length};
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
  async function liveNews(g){
    const out={items:[],via:[]};
    const espn=D.IDS[g];
    const jobs=[
      espn?getJSON(`https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players?playerId=${encodeURIComponent(espn)}&limit=50`,7000).then(j=>{out.items.push(...espnItems(j.feed));out.via.push('ESPN')}).catch(()=>{}):null,
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
    return NEWS[key]=Promise.all([arch,lv]).then(([a,l])=>{const by=new Map();for(const it of [...(a&&a.items||[]),...l.items])by.set(nkey(it),{...by.get(nkey(it)),...it});
      const rwT=new Set([...by.values()].filter(x=>x.src==='RotoWire').map(x=>x.d&&new Date(x.d).getTime()));const items=[...by.values()].filter(x=>!(x.src==='ESPN fantasy'&&x.d&&rwT.has(new Date(x.d).getTime()))).sort((x,y)=>String(y.d||'').localeCompare(String(x.d||'')));return {items,archived:a?a.items.length:0,live:l.via,updated:a&&a.updated_utc}});
  }
  const fmtDate=s=>{if(!s)return '';const d=new Date(s);if(isNaN(d))return '';const days=(Date.now()-d)/864e5;
    const md=d.toLocaleDateString(undefined,{month:'short',day:'numeric',...(d.getFullYear()!==new Date().getFullYear()?{year:'numeric'}:{})});
    return days<1?`${md} · ${Math.max(1,Math.round(days*24))}h ago`:days<14?`${md} · ${Math.round(days)}d ago`:md};
  function newsHTML(n,all,name){
    if(!n.items.length)return `<p class="dim" style="margin:0">No stories yet. The news archive fills in each time the "Update Sleeper rosters" job runs (3× a day).</p>`;
    const show=all?n.items:n.items.slice(0,6);const oldest=n.items[n.items.length-1].d;
    return `<ul class="pc-news">${show.map(it=>{const fresh=it.d&&(Date.now()-new Date(it.d))<3*864e5;return `<li class="${fresh?'new':''}">${it.url?`<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.h)}</a>`:`<b>${esc(it.h)}</b>`}${it.s?`<p>${esc(it.s)}</p>`:''}<small>${esc(it.src||'')}${it.d?' · '+esc(fmtDate(it.d)):''}</small></li>`}).join('')}</ul>
      ${!all&&n.items.length>show.length?`<button type="button" class="more" data-more>Show all ${n.items.length} stories (back to ${esc(fmtDate(oldest).split(' · ')[0])})</button>`:''}`;
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
    const sc=scoring(),sk=SCORING[sc].k;const s=playerSummary(id,sc);const inj=D.INJ[id];const espn=D.IDS[id];
    if(!s)return `<div class="pc-top"><div><h3>${esc(NAMEHINT[id]||'Player')}</h3><div class="sub">No stats this season</div></div></div>
      <section><p class="dim" style="margin:0">Hasn't recorded an offensive snap in nflverse's weekly data this season (kicker, injured, or rookie yet to play).</p><div class="tags" style="margin-top:6px">${ownerTag(id)}</div></section>
      <section><h4>News <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>${linksHTML(id,NAMEHINT[id]||'',espn,null)}`;
    NAMEHINT[id]=s.name;
    const n=nextOpp(s.team);const cols=POSCOLS[s.pos]||POSCOLS.WR;
    const tot=k=>sum(s.logs.map(l=>l[k])),pg=k=>RATE.has(k)?mean(s.logs.map(l=>l[k])):tot(k)/s.g;
    const cell=(k,v,isPg)=>!num(v)?'<span class="dim">–</span>':RATE.has(k)?pct(v):(isPg||k==='xfp')?f1(v):f0(v);
    const seasonRow=(lbl,isPg)=>`<tr${isPg?'':' class="tot"'}><td class="l">${lbl}</td><td class="fp">${f1(isPg?s.fpg:s.fp)}</td>${cols.map(([k])=>`<td>${cell(k,isPg||RATE.has(k)?pg(k):tot(k),isPg)}</td>`).join('')}</tr>`;
    const logRows=s.logs.map(l=>`<tr><td class="l">${l.week}</td><td class="l">${oppBtn(l.opponent_team,((gameOf(l.team,l.week)||{}).at?'@ ':'vs ')+l.opponent_team,null)}</td><td class="fp">${f1(l[sk])}</td>${cols.map(([k])=>`<td>${cell(k,l[k],false)}</td>`).join('')}</tr>`).join('');
    return `<div class="pc-top">${s.headshot?`<img class="hs" src="${esc(s.headshot)}" alt="" loading="lazy" onerror="this.remove()">`:''}<div><h3>${esc(s.name)}</h3>
      <div class="sub"><span>${s.pos} · ${s.team}</span><span>bye ${byeWeek(s.team)||'–'}</span>${n?`<span>Wk ${D.META.next_week} ${oppBtn(n.opp,(n.at?'@ ':'vs ')+n.opp,s.pos)}</span>`:`<span>Wk ${D.META.next_week} bye</span>`}</div></div></div>
    <section><div class="tags">${inj?`<span class="tag inj" title="${esc(inj[1])} · Wk ${inj[2]} report">${esc(inj[0].replace('Practice: ','Practice '))} · ${esc(inj[1])}</span>`:''}${ownerTag(id)}<span class="sp" style="flex:1"></span>${scoringSeg(sc)}</div>
      <div class="tiles" style="margin-top:8px">
        <div><span>FP / game</span><b>${f1(s.fpg)}</b><small>${[s.rank?s.pos+s.rank:'',s.g+' g'].filter(Boolean).join(' · ')}</small></div>
        <div><span>Last 3</span><b>${f1(s.l3)}</b><small>${num(s.l3)&&num(s.fpg)?(s.l3>=s.fpg?'▲ ':'▼ ')+Math.abs(s.l3-s.fpg).toFixed(1)+' vs avg':''}</small></div>
        <div><span>xFP / game</span><b>${f1(s.xfpg)}</b><small>L3 ${f1(s.xfp3)}</small></div>
        <div><span>Snap %</span><b>${pct(s.snap)}</b><small>L3 ${pct(s.snap3)}</small></div>
        <div><span>Touches / g</span><b>${f1(s.opps)}</b><small>${s.pos==='QB'?'carries + targets':'L3 '+f1(s.opps3)}</small></div>
      </div></section>
    <section><h4>${SCORING[sc].label} points by week <span class="sp"></span><span>high ${f1(s.best)} · low ${f1(s.worst)}${num(s.sd)?' · ±'+s.sd.toFixed(1):''}</span></h4>${bars(s.logs,sk,s.team)}</section>
    <section><h4>Season stats</h4><div class="scr"><table><thead><tr><th class="l"></th><th>FP</th>${cols.map(([,l])=>`<th>${l}</th>`).join('')}</tr></thead><tbody>${seasonRow('Per game',true)}${seasonRow('Total',false)}</tbody></table></div></section>
    <section><h4>Game log</h4><div class="scr"><table><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>FP</th>${cols.map(([,l])=>`<th>${l}</th>`).join('')}</tr></thead><tbody>${logRows}</tbody></table></div><div class="note">Opponent rank = PPR points that defense allows to ${s.pos}s (green = generous). Click an opponent for its defense card.</div></section>
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
    const cov=(D.DEF||[]).filter(x=>x.team===team&&x.tgt>=8).sort((a,b)=>b.yds-a.yds).slice(0,4);
    const rush=(D.DEF||[]).filter(x=>x.team===team&&x.prs>0).sort((a,b)=>b.prs-a.prs).slice(0,3);
    const cell=p=>`<div style="${p===pos?'box-shadow:inset 0 0 0 2px var(--blue)':''}"><span>${p}</span><b>${d?d[p].v.toFixed(1):'–'}</b><span class="mrk ${d?rkClass(d[p].rk,n):'mid'}">${d?ord(d[p].rk):''}</span></div>`;
    const rk=(r,label)=>`<span class="mrk ${rkClass(r,td.n)}" title="${label}">${ord(r)}</span>`;
    const logs=td.rows.map(r=>({week:r.week,fantasy_points_ppr:r.dst_pts}));
    return `<div class="pc-top">${tm.logo?`<img class="logo" src="${esc(tm.logo)}" alt="" loading="lazy" onerror="this.remove()">`:''}<div><h3>${esc(team)} D/ST</h3>
      <div class="sub"><span>${esc(tm.name||team)} · ${td.rec}</span><span>bye ${byeWeek(team)||'–'}</span>${nx?`<span>Wk ${D.META.next_week} ${nx.at?'@':'vs'} ${esc(nx.opp)}${num(nx.opp_implied)?` · opp implied ${nx.opp_implied.toFixed(1)}`:''}</span>`:`<span>Wk ${D.META.next_week} bye</span>`}</div></div></div>
    <section><div class="tags">${ownerTag('DEF:'+team)}</div>
      <div class="tiles" style="margin-top:8px"><div><span>D/ST pts / g</span><b>${f1(td.dst)}</b><small>${ord(td.rk.dst)} of ${td.n}</small></div><div><span>Last 3</span><b>${f1(ds.l3)}</b><small>${num(ds.sd)?'±'+ds.sd.toFixed(1)+' weekly':''}</small></div><div><span>Sacks / g</span><b>${f1(td.sk)}</b><small>${ord(td.rk.sk)}</small></div><div><span>Takeaways / g</span><b>${f1(td.tk)}</b><small>${ord(td.rk.tk)}</small></div></div></section>
    <section><h4>D/ST points by week</h4>${bars(logs,'fantasy_points_ppr',team)}</section>
    <section><h4>PPR points allowed per game · rank (1st = gives up most)</h4><div class="dvp">${['QB','RB','WR','TE'].map(cell).join('')}</div></section>
    <section><h4>Team defense per game</h4><div class="scr"><table><tbody>
      <tr><td class="l">Points allowed</td><td>${td.pa.toFixed(1)}</td><td>${rk(td.rk.pa,'1st = fewest allowed')}</td><td class="l">Pressures</td><td>${td.pr.toFixed(1)}</td><td>${rk(td.rk.pr,'1st = most')}</td></tr>
      <tr><td class="l">Yards allowed</td><td>${td.ya.toFixed(0)}</td><td>${rk(td.rk.ya,'1st = fewest allowed')}</td><td class="l">Sacks</td><td>${td.sk.toFixed(1)}</td><td>${rk(td.rk.sk,'1st = most')}</td></tr>
      <tr><td class="l">Pass / rush yds</td><td>${td.pya.toFixed(0)} / ${td.rya.toFixed(0)}</td><td></td><td class="l">Takeaways</td><td>${td.tk.toFixed(1)}</td><td>${rk(td.rk.tk,'1st = most')}</td></tr>
    </tbody></table></div><div class="note">Defense ranks: green = strong defense (tough matchup), red = weak.</div></section>
    <section><h4>Game log</h4><div class="scr"><table><thead><tr><th class="l">Wk</th><th class="l">Opp</th><th>D/ST</th><th>Pts alw</th><th>Yds alw</th><th>Sk</th><th>Prs</th><th>INT</th><th>FR</th><th>TD</th></tr></thead><tbody>${td.rows.map(r=>`<tr><td class="l">${r.week}</td><td class="l">${(gameOf(team,r.week)||{}).at?'@':'vs'} ${esc(r.opponent_team)}</td><td class="fp">${f1(r.dst_pts)}</td><td>${f0(r.points_against)}</td><td>${f0(r.yards_allowed)}</td><td>${f0(r.def_sacks)}</td><td>${f0(r.def_pressures)}</td><td>${f0(r.def_interceptions)}</td><td>${f0(r.fumble_recovery_opp)}</td><td>${f0((r.def_tds||0)+(r.special_teams_tds||0))}</td></tr>`).join('')}</tbody></table></div></section>
    ${cov.length?`<section><h4>Coverage: most yards allowed</h4><div class="scr"><table><thead><tr><th class="l">Defender</th><th>Tgt</th><th>Yds</th><th>TD</th><th>Rtg</th></tr></thead><tbody>${cov.map(x=>`<tr><td class="l">${esc(x.name)} <span class="dim">${esc(x.pos||'')}</span></td><td>${x.tgt}</td><td>${x.yds}</td><td>${x.td}</td><td>${num(x.rating)?x.rating.toFixed(0):'–'}</td></tr>`).join('')}</tbody></table></div></section>`:''}
    ${rush.length?`<section><h4>Pass rush leaders</h4><div class="scr"><table><tbody>${rush.map(x=>`<tr><td class="l">${esc(x.name)} <span class="dim">${esc(x.pos||'')}</span></td><td>${x.prs} pressures</td><td>${x.sk} sacks</td></tr>`).join('')}</tbody></table></div></section>`:''}
    <section><h4>Team news <span class="sp"></span><span data-news-src></span></h4><div data-news><span class="spin"></span>Loading news…</div></section>
    ${linksHTML('DEF:'+team,team+' D/ST',null,tm)}`;
  }
  const NAMEHINT={};

  /* ---------- popup ---------- */
  let el=null,shade=null,anchor=null,stack=[];
  function close(){if(el){el.remove();el=null}if(shade){shade.remove();shade=null}if(anchor){anchor.setAttribute('aria-expanded','false');anchor=null}stack=[]}
  function place(){
    if(!el||!anchor)return;const phone=matchMedia('(max-width:640px)').matches;
    if(phone){if(!shade){shade=document.createElement('div');shade.className='pc-shade';shade.onclick=close;document.body.appendChild(shade)}return}
    const r=anchor.getBoundingClientRect(),w=el.offsetWidth,h=el.offsetHeight;
    let left=r.left+scrollX;left=Math.min(left,scrollX+document.documentElement.clientWidth-w-12);left=Math.max(scrollX+12,left);
    const below=innerHeight-r.bottom-12,above=r.top-60;let top=r.bottom+scrollY+6;
    if(below<Math.min(h,360)){if(above>=h)top=r.top+scrollY-h-6;else setTimeout(()=>{if(el)el.scrollIntoView({block:'nearest',behavior:'smooth'})},30)}
    el.style.left=left+'px';el.style.top=top+'px';
  }
  function render(){
    const cur=stack[stack.length-1];if(!cur||!el)return;
    const [kind,id]=[cur.key[0],cur.key.slice(2)];
    let html;try{html=kind==='d'?defHTML(id,cur.pos):playerHTML(id)}catch(e){html=`<div class="pc-top"><div><h3>Couldn't build this card</h3></div></div><section class="dim">${esc(e.message)}</section>`}
    el.innerHTML=`<button type="button" class="pc-x" aria-label="Close">×</button>`+html;
    if(stack.length>1){const top=el.querySelector('.pc-top');top.insertAdjacentHTML('afterbegin',`<button type="button" class="pc-back" aria-label="Back">←</button>`)}
    el.scrollTop=0;fillOwner();fillNews(kind==='d'?'DEF:'+id:id,false);
  }
  function fillOwner(){
    if(!window.NFLS||!el)return;const lg=NFLS.getLeague();if(!lg)return;
    NFLS.rosterStatus().then(rs=>{if(!rs||!el)return;el.querySelectorAll('[data-own]').forEach(s=>{const k=s.dataset.own;const m=rs.map.get(k);
      s.outerHTML=m?(m.status==='mine'?`<span class="tag mine">On ${esc(lg.viewer||'your')} roster · ${esc(lg.name)}</span>`:`<span class="tag">Rostered by ${esc(m.team)} · ${esc(lg.name)}</span>`):`<span class="tag fa">Free agent in ${esc(lg.name)}</span>`})}).catch(()=>{});
  }
  function fillNews(key,all){
    const box=el&&el.querySelector('[data-news]');if(!box)return;const me=el;const name=NAMEHINT[key]||'';
    newsFor(key).then(n=>{if(el!==me)return;box.innerHTML=newsHTML(n,all,name);const s=el.querySelector('[data-news-src]');if(s)s.textContent=n.items.length?newsSrc(n):'';
      const m=box.querySelector('[data-more]');if(m)m.onclick=ev=>{ev.stopPropagation();fillNews(key,true)}}).catch(()=>{box.textContent="Couldn't load news."});
  }
  function open(key,a,pos){
    const same=anchor===a&&el;close();if(same)return;
    anchor=a||null;if(anchor)anchor.setAttribute('aria-expanded','true');
    el=document.createElement('div');el.className='pc';el.setAttribute('role','dialog');el.setAttribute('aria-label','Player card');
    el.innerHTML=`<button type="button" class="pc-x" aria-label="Close">×</button><div class="pc-top"><div><h3>${esc(a?a.textContent.trim().split('\n')[0]:'')}</h3><div class="sub"><span><span class="spin"></span>Loading…</span></div></div></div>`;
    document.body.appendChild(el);place();
    stack=[{key,pos}];load().then(()=>{if(stack[0]&&stack[0].key===key){render();place()}}).catch(e=>{if(el)el.innerHTML=`<button type="button" class="pc-x">×</button><section>Couldn't load the season data (${esc(e.message)}).</section>`});
  }
  function push(key,pos){stack.push({key,pos});render()}
  document.addEventListener('click',e=>{
    if(el&&el.contains(e.target)){
      if(e.target.closest('.pc-x')){close();return}
      if(e.target.closest('.pc-back')){stack.pop();render();return}
      const sc=e.target.closest('[data-sc] button');if(sc){LS.set('scoring',sc.dataset.v);IX&&(IX._rank={});render();window.dispatchEvent(new CustomEvent('nfls-scoring',{detail:sc.dataset.v}));return}
      const np=e.target.closest('.pc-news p');if(np){np.classList.toggle('open');return}
      const cp=e.target.closest('[data-copyname]');if(cp){try{navigator.clipboard.writeText(cp.dataset.copyname)}catch(err){}return}
      const t=e.target.closest('[data-card],.opp[data-opp]');if(t){e.preventDefault();const k=t.dataset.card||('d:'+t.dataset.opp);push(k,t.dataset.pos);return}
      return;
    }
    const t=e.target.closest('[data-card],.opp[data-opp]');
    if(t&&!e.target.closest('.plink,.av,a[href]:not([data-card])')){e.preventDefault();e.stopPropagation();const k=t.dataset.card||('d:'+t.dataset.opp);if(t.dataset.name)NAMEHINT[k.slice(2)]=t.dataset.name;open(k,t,t.dataset.pos);return}
    if(el&&!e.target.closest('.pmenu'))close();
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&el)close()});
  addEventListener('hashchange',()=>{if(el&&!location.hash.startsWith('#a='))close()});
  addEventListener('resize',()=>{if(el)place()});

  /* markup helpers for pages */
  function pbtn(id,name,cls){return `<button type="button" class="pname ${cls||''}" data-card="p:${esc(id)}" data-name="${esc(name)}" aria-expanded="false">${esc(name)}</button>`}
  function dbtn(team,label,cls){return `<button type="button" class="pname ${cls||''}" data-card="d:${esc(team)}" aria-expanded="false">${esc(label||team)}</button>`}
  window.NFLSCards={provide,load,open,close,pbtn,dbtn,oppBtn,mrk,newsFor,playerSummary,defSummary,teamDefense,dvp,gameOf,nextOpp,byeWeek,scoring,SCORING,data:()=>D,index:()=>IX};
})();
