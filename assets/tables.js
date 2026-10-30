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
  const isLocked=th=>th.classList.contains('rank')||th.classList.contains('stick')||th.textContent.trim()==='#'||!th.textContent.trim()||!!th.closest('.pc,.pw')&&th.cellIndex===0;
  const cfgOf=id=>{const c=LS.get(id);return {hide:(c&&c.hide)||[],order:(c&&c.order)||[]}};

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
      [...row.cells].forEach((c,i)=>c.classList.toggle('col-off',!locked[perm[i]]&&cfg.hide.includes(hk[i])))
    }
    t.tHead.dataset.colsDone='1';
    bar(t,cfg);
  }
  /* the "Columns" button sits just above the table's scroll box */
  function bar(t,cfg){
    const wrap=t.closest('.tablewrap,.scr')||t;let b=wrap.previousElementSibling;
    if(!b||!b.classList.contains('colbar')){b=document.createElement('div');b.className='colbar';wrap.parentNode.insertBefore(b,wrap)}
    b.dataset.for=t.dataset.cols;
    const hr=headRow(t);const hidden=hr?[...hr.cells].filter(c=>!isLocked(c)&&cfg.hide.includes(keyOf(c))).length:0;
    b.innerHTML=`<button type="button" class="colbtn" aria-haspopup="dialog">Columns${hidden?` <span>${hidden} hidden</span>`:''} ▾</button>`;
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
    const cols=[...hr.cells].filter(c=>!isLocked(c)).map(c=>({k:keyOf(c),l:labelOf(c)}));
    panel.innerHTML=`<div class="cp-h"><b>Columns</b><span>tick to show · arrows to move</span></div><ul>${cols.map((c,i)=>`<li><label><input type="checkbox" data-k="${esc(c.k)}" ${cfg.hide.includes(c.k)?'':'checked'}>${esc(c.l)}</label><button type="button" data-mv="-1" data-k="${esc(c.k)}" ${i===0?'disabled':''} aria-label="Move ${esc(c.l)} left">↑</button><button type="button" data-mv="1" data-k="${esc(c.k)}" ${i===cols.length-1?'disabled':''} aria-label="Move ${esc(c.l)} right">↓</button></li>`).join('')}</ul>
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
    if(cb){const k=cb.dataset.k;cfg.hide=cb.checked?cfg.hide.filter(x=>x!==k):[...new Set([...cfg.hide,k])];save(t,cfg);return}
    const mv=e.target.closest('[data-mv]');
    if(mv){const order=[...panel._cols];const i=order.indexOf(mv.dataset.k),j=i+(+mv.dataset.mv);if(i<0||j<0||j>=order.length)return;[order[i],order[j]]=[order[j],order[i]];cfg.order=order;save(t,cfg);return}
    if(e.target.closest('[data-all]')){cfg.hide=[];save(t,cfg);return}
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
