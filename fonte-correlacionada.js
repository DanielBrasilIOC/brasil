(function(){
  'use strict';
  const moneyRx=/R\$\s*[\d\.]+,\d{2}|[\d\.]+,\d{2}/g;
  const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const parseMoney=s=>{const m=(s||'').match(moneyRx);if(!m)return 0;return m.reduce((a,v)=>a+parseFloat(v.replace(/R\$\s*/,'').replace(/\./g,'').replace(',','.')),0)};
  function findSourceSelect(doc){
    const sels=[...doc.querySelectorAll('select')];
    return sels.find(s=>/fonte|source/i.test((s.id||'')+' '+(s.name||'')+' '+(s.getAttribute('aria-label')||'')+' '+(s.getAttribute('title')||''))) || sels.find(s=>[...s.options].some(o=>/fonte/i.test(o.textContent||'')));
  }
  function selectedSource(doc){
    const s=findSourceSelect(doc); return s && s.value ? (s.options[s.selectedIndex]?.textContent||s.value).trim() : '';
  }
  function findTarget(doc){
    const nodes=[...doc.querySelectorAll('h1,h2,h3,h4,strong,.panel .head')];
    const n=nodes.find(x=>norm(x.textContent).includes('termometro de restos a pagar')) || nodes.find(x=>norm(x.textContent).includes('restos a pagar'));
    if(!n)return null;
    return n.closest('.panel') || n.closest('.grid') || n.parentElement;
  }
  function parseVisibleData(doc,source){
    const wanted=norm(source); const groups=[]; let total=0, rows=0;
    [...doc.querySelectorAll('table')].forEach(table=>{
      const tr=[...table.querySelectorAll('tbody tr')]; if(!tr.length)return;
      const matched=tr.filter(r=>norm(r.textContent).includes(wanted)); if(!matched.length)return;
      let title='Registros relacionados';
      const panel=table.closest('.panel');
      if(panel){const h=panel.querySelector('h3,h2,h4'); if(h)title=h.textContent.trim();}
      const value=matched.reduce((a,r)=>a+parseMoney(r.textContent),0);
      groups.push({title,count:matched.length,value}); rows+=matched.length; total+=value;
    });
    return {groups,rows,total};
  }
  function money(v){return v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});}
  function render(doc){
    const old=doc.getElementById('sourceCorrelationPanel'); if(old)old.remove();
    const source=selectedSource(doc); if(!source || /selecione|todas|todos|fonte/i.test(source)&&norm(source).length<8)return;
    const data=parseVisibleData(doc,source);
    const panel=doc.createElement('section'); panel.id='sourceCorrelationPanel'; panel.className='panel source-correlation';
    panel.innerHTML='<div class="head"><div><h3>Visão consolidada da fonte selecionada</h3><p class="desc">Correlação automática dos registros atualmente filtrados para <strong>'+source.replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))+'</strong>.</p></div><span class="badge ok">Fonte selecionada</span></div>'+
      '<div class="source-correlation-kpis">'+
      '<div class="kpi"><div class="label">Registros correlacionados</div><div class="value">'+data.rows.toLocaleString('pt-BR')+'</div><div class="hint">Linhas identificadas nos dados exibidos</div></div>'+ 
      '<div class="kpi"><div class="label">Valor correlacionado</div><div class="value">'+money(data.total)+'</div><div class="hint">Soma dos valores monetários encontrados</div></div>'+ 
      '<div class="kpi"><div class="label">Áreas relacionadas</div><div class="value">'+data.groups.length.toLocaleString('pt-BR')+'</div><div class="hint">Conjuntos de dados com vínculo à fonte</div></div></div>'+
      '<div class="source-correlation-list">'+(data.groups.length?data.groups.map(g=>'<div class="source-correlation-item"><div><strong>'+g.title.replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))+'</strong><span>'+g.count.toLocaleString('pt-BR')+' registro(s)</span></div><b>'+money(g.value)+'</b></div>').join(''):'<div class="empty"><strong>Nenhum vínculo adicional identificado</strong>Não há registros visíveis contendo a fonte selecionada.</div>')+'</div>';
    const target=findTarget(doc); if(target && target.parentNode)target.parentNode.insertBefore(panel,target);
  }
  function enhance(frame){
    const doc=frame.contentDocument; if(!doc)return;
    if(!doc.getElementById('sourceCorrelationStyles')){
      const st=doc.createElement('style');st.id='sourceCorrelationStyles';st.textContent='.source-correlation{margin:0 0 15px!important}.source-correlation-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;margin:14px 0}.source-correlation-kpis .kpi{min-height:105px}.source-correlation-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:9px}.source-correlation-item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 14px;border:1px solid var(--l);border-radius:11px;background:#f8fafb}.source-correlation-item strong{display:block;color:var(--n);font-size:12px}.source-correlation-item span{display:block;color:var(--m);font-size:10px;margin-top:3px}.source-correlation-item b{color:var(--n);white-space:nowrap;font-size:12px}@media(max-width:700px){.source-correlation-kpis{grid-template-columns:1fr}.source-correlation-item{align-items:flex-start;flex-direction:column}.source-correlation-item b{white-space:normal}}';doc.head.appendChild(st);
    }
    const sel=findSourceSelect(doc); if(!sel)return;
    if(sel.dataset.correlationBound!=='1'){sel.dataset.correlationBound='1';sel.addEventListener('change',()=>setTimeout(()=>render(doc),60));}
    const observer=new MutationObserver(()=>{clearTimeout(sel._corrTimer);sel._corrTimer=setTimeout(()=>render(doc),120)}); observer.observe(doc.body,{subtree:true,childList:true});
    render(doc);
  }
  function start(){const frame=document.getElementById('dashboard'); if(!frame)return; const run=()=>{try{if(frame.contentDocument?.body)enhance(frame);else setTimeout(run,100)}catch(e){setTimeout(run,250)}};frame.addEventListener('load',run);setTimeout(run,100);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
