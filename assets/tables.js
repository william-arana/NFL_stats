/* Column chooser for every big table on the site.
   Any <table data-cols="<key>"> gets a "Columns" button above it: hide/show columns and move them up/down.
   The layout is saved per key in this browser (localStorage nfls-cols-<key>) and re-applied every time the
   page re-renders the table, so the page code keeps building tables the normal way.
   The # and the frozen name column (.rank / .stick / "#") always stay put. Sorting stays with each page. */
(function(){
  const LS={get(k){try{return JSON.parse(localStorage.getItem('nfls-cols-'+k)||'null')}catch(e){return null}},set(k,v){try{localStorage.setItem('nfls-cols-'+k,JSON.stringify(v))}catch(e){}},del(k){try{localStorage.removeItem('nfls-cols-'+k)}catch(e){}}};
  const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const keyOf=th=>th.dataset.k||th.dataset.c||th.textContent.trim().replace(/\s+/g,' ');
  const labelOf=th=>th.textContent.trim().replace(/\s+/g,' ')||keyOf(th);
  /* full names shown next to the short column labels in the Columns menu: "Tgt (Targets)" */
  const FULL={'FP':'Fantasy points','xFP':'Expected fantasy points','PPR − xFP':'Actual minus expected points','Snap %':'Share of offensive snaps','Tgt share':'Target share','Tgt %':'Target share',
    'Rush att':'Rushing attempts','Car':'Carries','Tgt':'Targets','Opps':'Carries + targets','TD':'Touchdowns','Rec':'Receptions','Catch %':'Catch rate','Yds':'Yards','Air yds':'Air yards',
    'aDOT':'Average depth of target','YAC':'Yards after catch','Air share':'Share of team air yards','WOPR':'Weighted opportunity rating','RACR':'Receiver air conversion ratio',
    'Rec EPA':'Receiving expected points added','YPC':'Yards per carry','1st dn':'First downs','YBC/att':'Yards before contact per carry','YAC/att':'Yards after contact per carry',
    'Brk tkl':'Broken tackles','Rush EPA':'Rushing expected points added','Fum lost':'Fumbles lost','Cmp':'Completions','Att':'Attempts','INT':'Interceptions','Sacked':'Times sacked',
    'Pressured %':'Pressure rate','Blitzed':'Times blitzed','CPOE':'Completion % over expected','Pass EPA':'Passing expected points added','Y/A':'Yards per attempt','Snaps':'Offensive snaps',
    'FP/snap':'Fantasy points per snap','FP/opp':'Fantasy points per carry + target','Scrim yds':'Scrimmage yards (rush + rec)','Rush TD':'Rushing touchdowns','Rec TD':'Receiving touchdowns',
    'Rec 1st dn':'Receiving first downs','Yds/tgt':'Yards per target','EPA/tgt':'Expected points added per target','EPA/att':'Expected points added per carry','Brk tkl/att':'Broken tackles per carry',
    'YBC':'Yards before contact','Rec yds':'Receiving yards','Cmp %':'Completion %','TD %':'Touchdown rate','INT %':'Interception rate','Sack %':'Sack rate','IAY/att':'Intended air yards per attempt',
    'EPA/db':'Expected points added per dropback','Pressured':'Times pressured','Rush yds':'Rushing yards','YAC (rush)':'Yards after contact','Rush 1D':'Rushing first downs','Rec YAC':'Receiving yards after catch',
    'Pass yds':'Passing yards','Sk':'Sacks','Prs':'Pressures','G':'Games','Tkl':'Tackles','TFL':'Tackles for loss','PD':'Passes defended','FF':'Forced fumbles','Cmp % alw':'Completion % allowed',
    'Yds alw':'Yards allowed','TD alw':'Touchdowns allowed','Rating alw':'Passer rating allowed','Rtg':'Passer rating allowed','Missed tkl':'Missed tackles','Starts':'Games started',
    'Prs % with':'Team pressure rate with him','Prs % without':'Team pressure rate without him','Prs Δ':'Pressure rate change','G without':'Games without him','Sacks/g with':'Sacks per game with him',
    'Sacks/g without':'Sacks per game without him','YBC/carry with':'Yards before contact per carry with him','YBC/carry without':'Yards before contact per carry without him','YBC Δ':'Run blocking change',
    'K pts':'Kicker fantasy points','K pts/g':'Kicker fantasy points per game','Implied':'Implied team points (Vegas)','FGM':'Field goals made','FGA':'Field goals attempted','FG %':'Field goal %',
    'Long':'Longest field goal','0–39':'Field goals made, 0–39 yds','40–49':'Field goals made, 40–49 yds','50+':'Field goals made, 50+ yds','Missed':'Missed field goals','XPM':'Extra points made',
    'XP miss':'Missed extra points','FG':'Field goals made / attempted','XP':'Extra points made / attempted','L3':'Last 3 games','Score':'Waiver score','xFP L3':'Expected fantasy points, last 3',
    'PPR L3':'PPR points, last 3','Snap % L3':'Snap share, last 3','Snap Δ':'Snap share change','Touches L3':'Carries + targets, last 3','Touch Δ':'Touches change','Tgt share L3':'Target share, last 3',
    'PPR season':'PPR points per game, season','Matchup score':'D/ST matchup score','D/ST pts/g':'D/ST fantasy points per game','D/ST':'D/ST fantasy points','Pts alw':'Points allowed',
    'Pass alw':'Passing yards allowed','Rush alw':'Rushing yards allowed','FR':'Fumble recoveries','Opp implied':'Opponent implied points (Vegas)','Slot':'Depth chart slot','Pts':'Points','Weekly FP':'Fantasy points by week','RZ opps':'Red zone carries + targets','I10 opps':'Carries + targets inside the 10','GL car':'Goal-line carries (inside the 5)','RZ tgt':'Red zone targets','RZ car':'Red zone carries','I10 car':'Carries inside the 10','Separation':'Yards from nearest defender at the catch','Cushion':'Yards off the defender at the snap','YACOE':'Yards after catch over expected','Deep tgt':'Targets 20+ air yards','Cont tgt':'Contested targets','Contested':'Contested targets','Cont catch %':'Contested catch rate','Catchable %':'Share of targets that were catchable','Drops':'Dropped passes','Drop %':'Drops per catchable target','Created rec':'Catches made on poor throws','RYOE':'Rushing yards over expected','RYOE/att':'Rushing yards over expected per carry','8+ box %':'Carries vs 8+ defenders in the box','Time to LOS':'Seconds to reach the line of scrimmage','TTT':'Time to throw (seconds)','Aggr %':'Tight-window throw rate','CAY':'Completed air yards per completion','PA %':'Play-action rate','INT-worthy':'Interception-worthy throws','Record':'Win-loss record','Pass %':'Pass rate','Succ %':'Success rate (plays with positive EPA)','3D %':'3rd down conversion rate','RZ TD %':'Red zone touchdown rate','RZ trips':'Red zone trips','Expl plays':'Explosive plays (20+ yards)','Box faced':'Avg defenders in the box on runs','Takeaways':'Interceptions + fumble recoveries','EPA allowed':'Expected points added allowed','EPA/play alw':'EPA per play allowed','Succ % alw':'Success rate allowed','3D % alw':'3rd down conversion rate allowed','RZ TD % alw':'Red zone TD rate allowed','Expl alw':'Explosive plays allowed (20+ yards)','PA EPA alw':'EPA per play-action dropback allowed','Box vs run':'Avg defenders in the box vs the run','Prs % alw':'Pressure rate allowed','Sack % alw':'Sack rate allowed','Prs alw':'Pressures allowed','Sacks alw':'Sacks allowed','Pressures':'QB pressures','QB hits':'Quarterback hits','Blitz %':'Blitz rate (dropbacks with 1+ blitzer)','Avg rushers':'Pass rushers per dropback','Blitzed %':'How often this offense gets blitzed','Pos':'Position','Hurries':'QB hurries','Depth':'Depth chart slot','Ast tkl':'Assisted tackles','Missed tkl %':'Missed tackle rate','TFL yds':'Tackle-for-loss yards','Fum rec':'Fumble recoveries','INT ret yds':'Interception return yards','Blk kicks':'Blocked kicks','Cov aDOT':'Depth of target when he is in coverage','Yds/tgt alw':'Yards per target allowed','Air yds alw':'Air yards allowed on completions','YAC alw':'Yards after catch allowed','ST snaps':'Special teams snaps','Injury':'Injury report','Why':'Reasons behind the score','Pressures/g':'Pressures per game','Opp prs alw':'Opponent pressures allowed per game','Sacks/g':'Sacks per game','Opp sk alw':'Opponent sacks allowed per game','Opp implied':'Opponent implied points (Vegas)','Lineman':'Offensive lineman','without':'Team pressure rate without him','Prs % w/o':'Team pressure rate without him','Sk/g with':'Sacks per game with him','Sk/g w/o':'Sacks per game without him','YBC with':'Yards before contact per carry with him','YBC w/o':'Yards before contact per carry without him','Pass yds alw':'Passing yards allowed','Yds/pass alw':'Yards per pass allowed','Rush yds alw':'Rushing yards allowed','Rush att alw':'Rushing attempts allowed','YPC alw':'Yards per carry allowed','Rush EPA/play':'Rushing EPA per play','Pts allowed':'Points allowed','Yds allowed':'Yards allowed','Off TD':'Offensive touchdowns','Matchup score':'D/ST matchup score','Snap % L3':'Snap share, last 3'};
  const fullOf=(th,label)=>{const k=keyOf(th).replace(/^x-/,'');let f=FULL[label]||(/^Wk \d+$/.test(label)?'Next opponent':'');
    if(!f&&window.NFLSGloss){const e=NFLSGloss.lookup(k);if(e&&e[0])f=e[0]}
    return f&&f.toLowerCase()!==label.toLowerCase()?f:''};
  const isLocked=th=>th.classList.contains('rank')||th.classList.contains('stick')||th.textContent.trim()==='#'||!th.textContent.trim()||!!th.closest('.pc,.pw')&&th.cellIndex===0;
  const cfgOf=id=>{const c=LS.get(id);return {hide:(c&&c.hide)||[],order:(c&&c.order)||[],show:(c&&c.show)||[]}};
  /* <th data-def-off> = an extra stat that starts hidden; ticking it adds it to cfg.show */
  const isOff=(th,k,cfg)=>th.dataset.defOff?!cfg.show.includes(k):cfg.hide.includes(k);

  function headRow(t){return t.tHead&&t.tHead.rows.length===1?t.tHead.rows[0]:null}
  /* put the table's columns in the saved order and hide the hidden ones */
  function apply(t){
    const hr=headRow(t);if(!hr||[...hr.cells].some(c=>c.colSpan>1))return;
    const id=t.dataset.cols;const cfg=cfgOf(id);
    const ths=[...hr.cells];const keys=ths.map(keyOf);const n=ths.length;
    if(!t.tHead.dataset.colsOrig)t.tHead.dataset.colsOrig=JSON.stringify(keys);
    const orig=JSON.parse(t.tHead.dataset.colsOrig);
    const locked=ths.map(isLocked);
    const movable=keys.map((k,i)=>i).filter(i=>!locked[i]);
    const rank=i=>{const o=cfg.order.indexOf(keys[i]);return o>=0?o:1000+orig.indexOf(keys[i])};
    const wanted=[...movable].sort((a,b)=>rank(a)-rank(b));
    const perm=[];let w=0;for(let i=0;i<n;i++)perm.push(locked[i]?i:wanted[w++]);
    const moved=perm.some((p,i)=>p!==i);
    for(const row of t.rows){
      if(row.cells.length!==n)continue;
      if(moved){const cells=[...row.cells];for(const p of perm)row.appendChild(cells[p])}
      const hk=moved?perm.map(p=>keys[p]):keys;
      [...row.cells].forEach((c,i)=>c.classList.toggle('col-off',!locked[perm[i]]&&isOff(ths[perm[i]],hk[i],cfg)))
    }
    t.tHead.dataset.colsDone='1';
    bar(t,cfg);
  }
  /* the "Columns" button sits just above the table's scroll box */
  function bar(t,cfg){
    const wrap=t.closest('.tablewrap,.scr')||t;let b=wrap.previousElementSibling;
    if(!b||!b.classList.contains('colbar')){b=document.createElement('div');b.className='colbar';wrap.parentNode.insertBefore(b,wrap)}
    b.dataset.for=t.dataset.cols;
    const hr=headRow(t);const hidden=hr?[...hr.cells].filter(c=>!isLocked(c)&&!c.dataset.defOff&&cfg.hide.includes(keyOf(c))).length:0;const extra=hr?[...hr.cells].filter(c=>c.dataset.defOff&&cfg.show.includes(keyOf(c))).length:0;
    b.innerHTML=`<button type="button" class="colbtn" aria-haspopup="dialog">Columns${hidden?` <span>${hidden} hidden</span>`:''}${extra?` <span class="plus">+${extra}</span>`:''} ▾</button>`;
    b.querySelector('button')._table=t;
  }
  let panel=null,panelBtn=null;
  function closePanel(){if(panel){panel.remove();panel=null}if(panelBtn){panelBtn.setAttribute('aria-expanded','false');panelBtn=null}}
  function openPanel(btn){
    const t=btn._table;if(!t||!t.isConnected)return;closePanel();panelBtn=btn;btn.setAttribute('aria-expanded','true');
    panel=document.createElement('div');panel.className='colpanel';panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Choose columns');
    document.body.appendChild(panel);paintPanel(t);
    const r=btn.getBoundingClientRect(),w=panel.offsetWidth;
    panel.style.left=Math.max(scrollX+8,Math.min(r.left+scrollX,scrollX+document.documentElement.clientWidth-w-8))+'px';panel.style.top=(r.bottom+scrollY+4)+'px';
  }
  function paintPanel(t){
    const hr=headRow(t);if(!hr||!panel)return;const id=t.dataset.cols;const cfg=cfgOf(id);
    const all=[...hr.cells].filter(c=>!isLocked(c)).map(c=>({k:keyOf(c),l:labelOf(c),off:!!c.dataset.defOff,th:c}));
    const cols=[...all.filter(c=>!c.off),...all.filter(c=>c.off)];
    const row=(c,i)=>`<li${c.off?' class="xtra"':''}><label><input type="checkbox" data-k="${esc(c.k)}" ${c.off?'data-off="1"':''} ${isOff(c.th,c.k,cfg)?'':'checked'}><span>${esc(c.l)}${(f=>f?` <small>(${esc(f)})</small>`:'')(fullOf(c.th,c.l))}</span></label><button type="button" data-mv="-1" data-k="${esc(c.k)}" ${i===0?'disabled':''} aria-label="Move ${esc(c.l)} left">↑</button><button type="button" data-mv="1" data-k="${esc(c.k)}" ${i===cols.length-1?'disabled':''} aria-label="Move ${esc(c.l)} right">↓</button></li>`;
    const firstX=cols.findIndex(c=>c.off);
    panel.innerHTML=`<div class="cp-h"><b>Columns</b><span>tick to show · arrows to move</span></div><ul>${cols.map((c,i)=>(i===firstX?'<li class="cp-sep">More stats (off by default)</li>':'')+row(c,i)).join('')}</ul>
      <div class="cp-f"><button type="button" data-all>Show all</button><button type="button" data-reset>Reset</button><button type="button" data-done>Done</button></div>`;
    panel._table=t;panel._cols=cols.map(c=>c.k);
  }
  function save(t,cfg){LS.set(t.dataset.cols,cfg);t.tHead.dataset.colsDone='';apply(t);paintPanel(t)}
  document.addEventListener('click',e=>{
    const btn=e.target.closest('.colbtn');if(btn){e.preventDefault();if(panelBtn===btn)closePanel();else openPanel(btn);return}
    if(!panel)return;
    if(!panel.contains(e.target)){closePanel();return}
    const t=panel._table;if(!t||!t.isConnected){closePanel();return}const cfg=cfgOf(t.dataset.cols);
    const cb=e.target.closest('input[type=checkbox]');
    if(cb){const k=cb.dataset.k;if(cb.dataset.off)cfg.show=cb.checked?[...new Set([...cfg.show,k])]:cfg.show.filter(x=>x!==k);else cfg.hide=cb.checked?cfg.hide.filter(x=>x!==k):[...new Set([...cfg.hide,k])];save(t,cfg);return}
    const mv=e.target.closest('[data-mv]');
    if(mv){const order=[...panel._cols];const i=order.indexOf(mv.dataset.k),j=i+(+mv.dataset.mv);if(i<0||j<0||j>=order.length)return;[order[i],order[j]]=[order[j],order[i]];cfg.order=order;save(t,cfg);return}
    if(e.target.closest('[data-all]')){cfg.hide=[];cfg.show=[...panel.querySelectorAll('input[data-off]')].map(x=>x.dataset.k);save(t,cfg);return}
    if(e.target.closest('[data-reset]')){LS.del(t.dataset.cols);t.tHead.dataset.colsDone='';apply(t);paintPanel(t);return}
    if(e.target.closest('[data-done]'))closePanel();
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel()});
  /* tables get rebuilt all the time (filters, sorting, league switch): re-apply whenever one appears */
  let queued=false;
  function scan(){queued=false;document.querySelectorAll('table[data-cols]').forEach(t=>{if(t.tHead&&!t.tHead.dataset.colsDone)apply(t)})}
  new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(scan)}}).observe(document.documentElement,{childList:true,subtree:true});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan);else scan();
  window.NFLSTables={apply,scan};
})();
