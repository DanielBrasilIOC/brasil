(function(){
'use strict';
const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const esc=s=>String(s||'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const moneyRx=/R\$\s*[\d\.]+,\d{2}|[\d\.]+,\d{2}/g;
const parseMoney=s=>{const m=(s||'').match(moneyRx);return m?m.reduce((a,v)=>a+parseFloat(v.replace(/R\$\s*/,'').replace(/\./g,'').replace(',','.')),0):0};
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
function sourceSelect(doc){
 const sels=[...doc.querySelectorAll('select')];
 return sels.map(s=>{const meta=norm((s.id||'')+' '+(s.name||'')+' '+(s.getAttribute('aria-label')||'')+' '+(s.getAttribute('title')||'')+' '+(s.parentElement?.textContent||''));const opts=[...s.options];let score=0;if(/fonte|source/.test(meta))score+=100;if(opts.some(o=>/fonte|source/.test(norm(o.textContent))))score+=40;if(opts.length>1)score+=5;return {s,score}}).sort((a,b)=>b.score-a.score)[0]?.s||null;
}
function sourceInfo(doc){const s=sourceSelect(doc);if(!s||s.selectedIndex<0)return null;const o=s.options[s.selectedIndex];const value=(s.value||'').trim(),text=(o?.textContent||'').trim();return {select:s,value,text,label:text||value,tokens:[norm(value),norm(text)].filter(x=>x&&x.length>=2)};}
function target(doc){const n=[...doc.querySelectorAll('h1,h2,h3,h4,strong')].find(x=>norm(x.textContent).includes('termometro de restos a pagar'));return n?(n.closest('.panel')||n.closest('.grid')||n.parentElement):null;}
function rowHaystack(r){let a=r.textContent||'';[...r.attributes].forEach(x=>a+=' '+x.name+' '+x.value);a+=' '+JSON.stringify(r.dataset||{});return norm(a);}
function matches(row,tokens){const h=rowHaystack(row);return tokens.some(t=>h===t||h.includes(t));}
function sectionData(doc,tokens){
 const out=[];
 [...doc.querySelectorAll('.panel')].forEach(panel=>{
  if(panel.id==='sourceCorrelationPanel')return;
  const rows=[...panel.querySelectorAll('tbody tr')];
  if(!rows.length)return;
  const matched=rows.filter(r=>matches(r,tokens));
  if(!matched.length)return;
  const h=panel.querySelector('h3,h2,h4');
  const title=(h?.textContent||'Conteúdo relacionado').trim();
  const value=matched.reduce((a,r)=>a+parseMoney(r.textContent),0);
  const samples=matched.slice(0,5).map(r=>[...r.querySelectorAll('td')].map(c=>c.textContent.trim()).filter(Boolean));
  out.push({title,count:matched.length,value,samples});
 });
 return out;
}
function broaderData(doc,tokens){
 const out=[];
 [...doc.querySelectorAll('.panel')].forEach(panel=>{
  if(panel.id==='sourceCorrelationPanel'||panel.querySelector('table'))return;
  const attrs=[...panel.attributes].map(a=>a.value).join(' ');
  const text=norm((panel.textContent||'')+' '+attrs);
  if(tokens.some(t=>text.includes(t))){const h=panel.querySelector('h3,h2,h4');out.push({title:(h?.textContent||'Conteúdo relacionado').trim(),count:1,value:parseMoney(panel.textContent||''),samples:[[panel.querySelector('.value')?.textContent?.trim()||panel.textContent.trim().slice(0,180)]]});}
 });
 return out;
}
function kpiData(doc,tokens){
 return [...doc.querySelectorAll('.kpi')].filter(k=>!k.closest('#sourceCorrelationPanel')).filter(k=>tokens.some(t=>norm(k.textContent).includes(t))).slice(0,8).map(k=>({label:k.querySelector('.label')?.textContent?.trim()||'Indicador',value:k.querySelector('.value')?.textContent?.trim()||''}));
}
function render(doc){
 const old=doc.getElementById('sourceCorrelationPanel');if(old)old.remove();
 const info=sourceInfo(doc);if(!info||!info.label||/^(selecione|todas?|todos?)$/i.test(info.label))return;
 let sections=sectionData(doc,info.tokens);if(!sections.length)sections=broaderData(doc,info.tokens);
 const kpis=kpiData(doc,info.tokens),totalRows=sections.reduce((a,s)=>a+s.count,0),totalValue=sections.reduce((a,s)=>a+s.value,0);
 const panel=doc.createElement('section');panel.id='sourceCorrelationPanel';panel.className='panel source-correlation';
 let html='<div class="head"><div><h3>Conteúdos relacionados à fonte</h3><p class="desc">Principais conteúdos e indicadores efetivamente relacionados à <strong>'+esc(info.label)+'</strong>.</p></div><span class="badge ok">Fonte selecionada</span></div>';
 html+='<div class="source-correlation-kpis"><div class="kpi"><div class="label">Conteúdos relacionados</div><div class="value">'+sections.length.toLocaleString('pt-BR')+'</div><div class="hint">Áreas com dados vinculados</div></div><div class="kpi"><div class="label">Registros relacionados</div><div class="value">'+totalRows.toLocaleString('pt-BR')+'</div><div class="hint">Registros identificados na fonte</div></div><div class="kpi"><div class="label">Valor financeiro relacionado</div><div class="value">'+money(totalValue)+'</div><div class="hint">Valores dos registros identificados</div></div></div>';
 if(kpis.length)html+='<div class="corr-subtitle">Principais indicadores da fonte</div><div class="corr-indicators">'+kpis.map(k=>'<div class="corr-indicator"><span>'+esc(k.label)+'</span><strong>'+esc(k.value)+'</strong></div>').join('')+'</div>';
 html+='<div class="corr-subtitle">Principais conteúdos</div><div class="corr-content-grid">';
 if(sections.length)html+=sections.map(s=>'<article class="corr-content"><div class="corr-content-head"><div><strong>'+esc(s.title)+'</strong><span>'+s.count.toLocaleString('pt-BR')+' registro(s) relacionado(s)</span></div><b>'+money(s.value)+'</b></div><div class="corr-records">'+s.samples.map(r=>'<div class="corr-record">'+r.slice(0,4).map((c,i)=>'<span class="c'+i+'">'+esc(c)+'</span>').join('')+'</div>').join('')+'</div></article>').join('');
 else html+='<div class="empty"><strong>Nenhum conteúdo relacionado identificado</strong><span>O filtro foi reconhecido, mas os dados da fonte ainda não estão expostos nas linhas atualmente renderizadas.</span></div>';
 html+='</div>';panel.innerHTML=html;
 const t=target(doc);if(t?.parentNode)t.parentNode.insertBefore(panel,t);
}
function enhance(frame){const doc=frame.contentDocument;if(!doc)return;
 if(!doc.getElementById('sourceCorrelationStyles')){const st=doc.createElement('style');st.id='sourceCorrelationStyles';st.textContent='.source-correlation{margin:0 0 15px!important;background:linear-gradient(145deg,#fff,#f9fbfc)}.source-correlation-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;margin:14px 0}.source-correlation-kpis .kpi{min-height:105px}.corr-subtitle{font-size:11px;font-weight:850;letter-spacing:.06em;text-transform:uppercase;color:#587080;margin:18px 0 9px}.corr-indicators{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px}.corr-indicator{padding:11px 13px;border:1px solid var(--l);border-radius:11px;background:#f8fafb}.corr-indicator span{display:block;font-size:10px;color:var(--m);margin-bottom:4px}.corr-indicator strong{display:block;color:var(--n);font-size:13px;overflow-wrap:anywhere}.corr-content-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.corr-content{border:1px solid var(--l);border-radius:12px;background:#fbfcfd;overflow:hidden;min-width:0}.corr-content-head{display:flex;justify-content:space-between;gap:12px;padding:13px 14px;border-bottom:1px solid var(--l);background:#f5f8fa}.corr-content-head strong{display:block;color:var(--n);font-size:12px}.corr-content-head span{display:block;color:var(--m);font-size:10px;margin-top:3px}.corr-content-head b{color:var(--n);white-space:nowrap;font-size:12px}.corr-records{padding:6px 10px}.corr-record{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:8px 4px;border-bottom:1px solid #edf1f4;font-size:10px;color:#506875}.corr-record:last-child{border-bottom:0}.corr-record span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.corr-record .c0{font-weight:750;color:#294b60}@media(max-width:800px){.source-correlation-kpis{grid-template-columns:1fr}.corr-content-grid{grid-template-columns:1fr}.corr-record{grid-template-columns:repeat(2,minmax(0,1fr))}.corr-content-head{align-items:flex-start;flex-direction:column}.corr-content-head b{white-space:normal}}@media(max-width:420px){.corr-record{grid-template-columns:1fr}.corr-indicators{grid-template-columns:1fr}}';doc.head.appendChild(st)}
 const sel=sourceSelect(doc);if(!sel)return;
 if(sel.dataset.correlationBound!=='3'){sel.dataset.correlationBound='3';sel.addEventListener('change',()=>setTimeout(()=>render(doc),250));}
 if(!doc.body.dataset.corrObserver){doc.body.dataset.corrObserver='3';const ob=new MutationObserver(()=>{clearTimeout(doc.body._corrTimer);doc.body._corrTimer=setTimeout(()=>render(doc),300)});ob.observe(doc.body,{subtree:true,childList:true});}
 render(doc);
}
function start(){const frame=document.getElementById('dashboard');if(!frame)return;const run=()=>{try{if(frame.contentDocument?.body)enhance(frame);else setTimeout(run,150)}catch(e){setTimeout(run,300)}};frame.addEventListener('load',run);setTimeout(run,150)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
