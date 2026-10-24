(function(){
'use strict';
const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const esc=s=>String(s||'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const moneyRx=/R\$\s*[\d\.]+,\d{2}|[\d\.]+,\d{2}/g;
const parseMoney=s=>{const m=(s||'').match(moneyRx);return m?m.reduce((a,v)=>a+parseFloat(v.replace(/R\$\s*/,'').replace(/\./g,'').replace(',','.')),0):0};
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
function sourceSelect(doc){const sels=[...doc.querySelectorAll('select')];return sels.find(s=>/fonte|source/i.test((s.id||'')+' '+(s.name||'')+' '+(s.getAttribute('aria-label')||'')+' '+(s.getAttribute('title')||'')))||sels.find(s=>[...s.options].some(o=>/fonte/i.test(o.textContent||'')))}
function source(doc){const s=sourceSelect(doc);return s&&s.value?(s.options[s.selectedIndex]?.textContent||s.value).trim():''}
function target(doc){const n=[...doc.querySelectorAll('h1,h2,h3,h4,strong')].find(x=>norm(x.textContent).includes('termometro de restos a pagar'));return n?(n.closest('.panel')||n.closest('.grid')||n.parentElement):null}
function sectionData(doc,wanted){
 const out=[];
 [...doc.querySelectorAll('.panel')].forEach(panel=>{
  if(panel.id==='sourceCorrelationPanel')return;
  const table=panel.querySelector('table');
  if(!table)return;
  const rows=[...table.querySelectorAll('tbody tr')];
  const matched=rows.filter(r=>norm(r.textContent).includes(wanted));
  if(!matched.length)return;
  const h=panel.querySelector('h3,h2,h4');
  const title=(h?.textContent||'Conteúdo relacionado').trim();
  const value=matched.reduce((a,r)=>a+parseMoney(r.textContent),0);
  const samples=matched.slice(0,4).map(r=>[...r.querySelectorAll('td')].map(c=>c.textContent.trim()).filter(Boolean));
  out.push({title,count:matched.length,value,samples});
 });
 return out;
}
function kpiData(doc,wanted){
 const vals=[];
 [...doc.querySelectorAll('.kpi')].forEach(k=>{if(k.closest('#sourceCorrelationPanel'))return;const txt=k.textContent||'';if(norm(txt).includes(wanted))vals.push({label:k.querySelector('.label')?.textContent?.trim()||'Indicador',value:k.querySelector('.value')?.textContent?.trim()||''})});
 return vals.slice(0,8);
}
function render(doc){
 const old=doc.getElementById('sourceCorrelationPanel');if(old)old.remove();
 const src=source(doc);if(!src||norm(src).length<3||/^(selecione|todas?|todos?)$/i.test(src))return;
 const wanted=norm(src), sections=sectionData(doc,wanted), kpis=kpiData(doc,wanted);
 const panel=doc.createElement('section');panel.id='sourceCorrelationPanel';panel.className='panel source-correlation';
 const totalRows=sections.reduce((a,s)=>a+s.count,0), totalValue=sections.reduce((a,s)=>a+s.value,0);
 let html='<div class="head"><div><h3>Conteúdos relacionados à fonte</h3><p class="desc">Visão executiva dos principais conteúdos que permanecem relacionados à <strong>'+esc(src)+'</strong> após a aplicação do filtro.</p></div><span class="badge ok">Fonte selecionada</span></div>';
 html+='<div class="source-correlation-kpis"><div class="kpi"><div class="label">Conteúdos relacionados</div><div class="value">'+sections.length.toLocaleString('pt-BR')+'</div><div class="hint">Áreas do painel com registros vinculados</div></div><div class="kpi"><div class="label">Registros relacionados</div><div class="value">'+totalRows.toLocaleString('pt-BR')+'</div><div class="hint">Registros encontrados nos conteúdos filtrados</div></div><div class="kpi"><div class="label">Valor financeiro relacionado</div><div class="value">'+money(totalValue)+'</div><div class="hint">Valores monetários presentes nesses registros</div></div></div>';
 if(kpis.length){html+='<div class="corr-subtitle">Principais indicadores da fonte</div><div class="corr-indicators">'+kpis.map(k=>'<div class="corr-indicator"><span>'+esc(k.label)+'</span><strong>'+esc(k.value)+'</strong></div>').join('')+'</div>'}
 html+='<div class="corr-subtitle">Principais conteúdos</div><div class="corr-content-grid">';
 if(sections.length){html+=sections.map(s=>'<article class="corr-content"><div class="corr-content-head"><div><strong>'+esc(s.title)+'</strong><span>'+s.count.toLocaleString('pt-BR')+' registro(s) relacionado(s)</span></div><b>'+money(s.value)+'</b></div><div class="corr-records">'+s.samples.map(r=>'<div class="corr-record">'+r.slice(0,4).map((c,i)=>'<span class="c'+i+'">'+esc(c)+'</span>').join('')+'</div>').join('')+'</div></article>').join('')}else{html+='<div class="empty"><strong>Nenhum conteúdo relacionado identificado</strong>A fonte selecionada não possui registros visíveis nas áreas atualmente carregadas.</div>'}
 html+='</div>';
 panel.innerHTML=html;
 const t=target(doc);if(t&&t.parentNode)t.parentNode.insertBefore(panel,t);
}
function enhance(frame){const doc=frame.contentDocument;if(!doc)return;
 if(!doc.getElementById('sourceCorrelationStyles')){const st=doc.createElement('style');st.id='sourceCorrelationStyles';st.textContent=`
.source-correlation{margin:0 0 15px!important;background:linear-gradient(145deg,#fff,#f9fbfc)}
.source-correlation-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;margin:14px 0}.source-correlation-kpis .kpi{min-height:105px}
.corr-subtitle{font-size:11px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;color:#587080;margin:18px 0 9px}
.corr-indicators{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px}.corr-indicator{padding:11px 13px;border:1px solid var(--l);border-radius:11px;background:#f8fafb}.corr-indicator span{display:block;font-size:10px;color:var(--m);margin-bottom:4px}.corr-indicator strong{display:block;color:var(--n);font-size:13px;overflow-wrap:anywhere}
.corr-content-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.corr-content{border:1px solid var(--l);border-radius:12px;background:#fbfcfd;overflow:hidden;min-width:0}.corr-content-head{display:flex;justify-content:space-between;gap:12px;padding:13px 14px;border-bottom:1px solid var(--l);background:#f5f8fa}.corr-content-head strong{display:block;color:var(--n);font-size:12px}.corr-content-head span{display:block;color:var(--m);font-size:10px;margin-top:3px}.corr-content-head b{color:var(--n);white-space:nowrap;font-size:12px}.corr-records{padding:6px 10px}.corr-record{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:8px 4px;border-bottom:1px solid #edf1f4;font-size:10px;color:#506875}.corr-record:last-child{border-bottom:0}.corr-record span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.corr-record .c0{font-weight:750;color:#294b60}
@media(max-width:800px){.source-correlation-kpis{grid-template-columns:1fr}.corr-content-grid{grid-template-columns:1fr}.corr-record{grid-template-columns:repeat(2,minmax(0,1fr))}.corr-content-head{align-items:flex-start;flex-direction:column}.corr-content-head b{white-space:normal}}
@media(max-width:420px){.corr-record{grid-template-columns:1fr}.corr-indicators{grid-template-columns:1fr}}
`;doc.head.appendChild(st)}
 const sel=sourceSelect(doc);if(!sel)return;
 if(sel.dataset.correlationBound!=='2'){sel.dataset.correlationBound='2';sel.addEventListener('change',()=>setTimeout(()=>render(doc),100))}
 if(!doc.body.dataset.corrObserver){doc.body.dataset.corrObserver='1';const ob=new MutationObserver(()=>{clearTimeout(doc.body._corrTimer);doc.body._corrTimer=setTimeout(()=>render(doc),180)});ob.observe(doc.body,{subtree:true,childList:true})}
 render(doc);
}
function start(){const frame=document.getElementById('dashboard');if(!frame)return;const run=()=>{try{if(frame.contentDocument?.body)enhance(frame);else setTimeout(run,120)}catch(e){setTimeout(run,250)}};frame.addEventListener('load',run);setTimeout(run,120)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
