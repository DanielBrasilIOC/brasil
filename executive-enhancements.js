/*
 * Melhorias executivas — Painel Financeiro e Orçamentário IOC
 * Camada não destrutiva: preserva o dashboard existente e adiciona
 * filtro por fonte, correlação contextual, atualização da base e responsividade.
 */
(function(){
  'use strict';
  const DATA_URL='data.json?v='+Date.now();
  const STYLE_ID='executive-enhancements-style';
  const PANEL_ID='executive-source-panel';

  const brl = n => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(n)||0);
  const num = v => {
    if(typeof v==='number' && Number.isFinite(v)) return v;
    if(v==null || v==='') return 0;
    const s=String(v).replace(/\s/g,'').replace(/R\$/gi,'');
    if(/^-?\d{1,3}(\.\d{3})*,\d+$/.test(s)) return Number(s.replace(/\./g,'').replace(',','.'))||0;
    return Number(s.replace(/,/g,''))||0;
  };
  const norm = v => String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const label = k => String(k).replace(/_/g,' ').replace(/\b\w/g,m=>m.toUpperCase());
  const isSourceKey = k => /fonte|recurso|vinculo|source/i.test(String(k));
  const isDocValueKey = k => /^(doc\s*[-_ ]?\s*valor|doc_valor|valor_doc|valor)$/i.test(String(k).trim()) || /doc.*valor/i.test(String(k));

  function injectStyle(doc){
    if(doc.getElementById(STYLE_ID)) return;
    const s=doc.createElement('style'); s.id=STYLE_ID;
    s.textContent=`
      #${PANEL_ID}{margin:0 0 22px;padding:0;border-radius:18px;border:1px solid rgba(18,44,74,.12);background:linear-gradient(135deg,#fff 0%,#f7fafc 100%);box-shadow:0 12px 32px rgba(18,44,74,.08);overflow:hidden;}
      #${PANEL_ID} .ee-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;padding:18px 20px 14px;border-bottom:1px solid rgba(18,44,74,.08)}
      #${PANEL_ID} .ee-title{font-weight:800;font-size:17px;color:#16324f;margin:0}.ee-sub{font-size:12px;color:#6b7c8f;margin-top:4px}
      #${PANEL_ID} select{min-width:240px;max-width:100%;padding:10px 38px 10px 12px;border:1px solid #cfd8e3;border-radius:10px;background:#fff;font-weight:700;color:#16324f}
      #${PANEL_ID} .ee-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:14px 20px}.ee-kpi{background:#fff;border:1px solid #e4e9ef;border-radius:12px;padding:12px}.ee-kpi b{display:block;font-size:18px;color:#16324f}.ee-kpi span{display:block;margin-top:3px;font-size:11px;color:#748497}
      #${PANEL_ID} .ee-body{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;padding:0 20px 20px}.ee-card{background:#fff;border:1px solid #e4e9ef;border-radius:12px;padding:14px}.ee-card h4{margin:0 0 9px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#52667a}.ee-list{display:grid;gap:7px}.ee-row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid #eef2f6;font-size:12px}.ee-row:last-child{border-bottom:0}.ee-row strong{color:#16324f;text-align:right}.ee-empty{font-size:12px;color:#778899;padding:10px 0}.ee-status{font-size:11px;color:#718197;padding:0 20px 14px}.ee-chip{display:inline-block;padding:4px 8px;border-radius:999px;background:#eef4f9;color:#285477;font-weight:700;margin-right:5px}
      @media(max-width:900px){#${PANEL_ID} .ee-grid{grid-template-columns:repeat(2,minmax(0,1fr))}#${PANEL_ID} .ee-body{grid-template-columns:1fr}}
      @media(max-width:560px){#${PANEL_ID} .ee-head{align-items:stretch;flex-direction:column}#${PANEL_ID} select{width:100%;min-width:0}.ee-grid{grid-template-columns:1fr!important;padding:12px}.ee-body{padding:0 12px 12px!important}.ee-status{padding:0 12px 12px}}
    `;
    doc.head.appendChild(s);
  }

  function getHost(doc){
    return doc.querySelector('main') || doc.querySelector('.container') || doc.querySelector('.content') || doc.body;
  }

  function buildPanel(doc,data){
    injectStyle(doc);
    let panel=doc.getElementById(PANEL_ID);
    if(panel) panel.remove();
    panel=doc.createElement('section'); panel.id=PANEL_ID;
    panel.setAttribute('aria-label','Análise por fonte');
    panel.innerHTML=`<div class="ee-head"><div><h3 class="ee-title">Análise por fonte</h3><div class="ee-sub">Selecione uma fonte para visualizar os registros e indicadores diretamente relacionados a ela.</div></div><select id="ee-source"><option value="">Selecione uma fonte…</option></select></div><div class="ee-grid"><div class="ee-kpi"><b id="ee-records">—</b><span>Registros correlacionados</span></div><div class="ee-kpi"><b id="ee-total">R$ 0,00</b><span>Valor correlacionado</span></div><div class="ee-kpi"><b id="ee-datasets">—</b><span>Bases relacionadas</span></div><div class="ee-kpi"><b id="ee-date">—</b><span>Base atualizada em</span></div></div><div class="ee-body"><div class="ee-card"><h4>Composição financeira</h4><div id="ee-composition" class="ee-list"><div class="ee-empty">Selecione uma fonte para carregar a análise.</div></div></div><div class="ee-card"><h4>Principais correlações</h4><div id="ee-correlations" class="ee-list"><div class="ee-empty">Aguardando seleção.</div></div></div></div><div class="ee-status"><span class="ee-chip">Dados oficiais</span><span id="ee-status-text">Base carregada do repositório publicado.</span></div>`;
    const host=getHost(doc);
    const firstContent=host.querySelector('section, .section, .card, .dashboard-grid, .grid, h2, h3');
    if(firstContent && firstContent.parentNode===host) host.insertBefore(panel,firstContent); else host.insertBefore(panel,host.firstChild);

    const sources=new Set();
    data.datasets.forEach(ds=> (ds.rows||[]).forEach(r=>Object.keys(r).forEach(k=>{if(isSourceKey(k) && r[k]!=null && String(r[k]).trim()) sources.add(String(r[k]).trim())})));
    [...sources].sort((a,b)=>a.localeCompare(b,'pt-BR',{numeric:true})).forEach(v=>{const o=doc.createElement('option');o.value=v;o.textContent=v;panel.querySelector('#ee-source').appendChild(o)});
    panel.querySelector('#ee-source').addEventListener('change',()=>renderSelection(doc,data,panel.querySelector('#ee-source').value));
  }

  function renderSelection(doc,data,source){
    const p=doc.getElementById(PANEL_ID); if(!p) return;
    const rows=[];
    const sourceNorm=norm(source);
    if(source){
      data.datasets.forEach(ds=>{
        (ds.rows||[]).forEach(r=>{
          const keys=Object.keys(r).filter(isSourceKey);
          if(keys.some(k=>norm(r[k])===sourceNorm)) rows.push({ds,r});
        });
      });
    }
    const total=rows.reduce((s,x)=>{
      const key=Object.keys(x.r).find(isDocValueKey);
      if(key) return s+num(x.r[key]);
      const candidates=['saldo','valor','total','liquido','valor_liquido'];
      const k=candidates.find(k=>Object.prototype.hasOwnProperty.call(x.r,k));
      return s+(k?num(x.r[k]):0);
    },0);
    p.querySelector('#ee-records').textContent=source?rows.length.toLocaleString('pt-BR'):'—';
    p.querySelector('#ee-total').textContent=source?brl(total):'R$ 0,00';
    p.querySelector('#ee-datasets').textContent=source?new Set(rows.map(x=>x.ds.id)).size:'—';
    p.querySelector('#ee-date').textContent=data.source_updated_at?new Date(data.source_updated_at+'T12:00:00').toLocaleDateString('pt-BR'):'—';
    const comp=p.querySelector('#ee-composition'), corr=p.querySelector('#ee-correlations');
    if(!source){comp.innerHTML='<div class="ee-empty">Selecione uma fonte para carregar a análise.</div>';corr.innerHTML='<div class="ee-empty">Aguardando seleção.</div>';return;}
    const byDs={}; rows.forEach(x=>{byDs[x.ds.title]=(byDs[x.ds.title]||0)+1});
    comp.innerHTML=Object.entries(byDs).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,v])=>`<div class="ee-row"><span>${label(k)}</span><strong>${v.toLocaleString('pt-BR')} registro(s)</strong></div>`).join('')||'<div class="ee-empty">Nenhum registro relacionado.</div>';
    const counts={}; rows.forEach(({r})=>Object.entries(r).forEach(([k,v])=>{if(isSourceKey(k)||v==null||v==='')return;const str=String(v).trim();if(str.length<3)return;const key=label(k)+' · '+str;counts[key]=(counts[key]||0)+1}));
    corr.innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,v])=>`<div class="ee-row"><span>${k}</span><strong>${v}x</strong></div>`).join('')||'<div class="ee-empty">Nenhuma correlação adicional encontrada.</div>';
  }

  async function init(){
    const frame=document.getElementById('dashboard'); if(!frame) return;
    frame.addEventListener('load', async function(){
      try{
        const doc=frame.contentDocument; if(!doc) return;
        const res=await fetch(DATA_URL,{cache:'no-store'}); const data=await res.json();
        if(!data || !Array.isArray(data.datasets)) throw new Error('Estrutura de dados inválida');
        buildPanel(doc,data);
        const status=doc.querySelector('#ee-status-text');
        if(status) status.textContent=`Fonte atualizada em ${data.source_updated_at||'não informada'} · processamento ${data.generated_at?new Date(data.generated_at).toLocaleString('pt-BR'): 'não informado'}.`;
      }catch(e){console.error('Melhorias executivas:',e)}
    });
    if(frame.contentDocument && frame.contentDocument.readyState==='complete') frame.dispatchEvent(new Event('load'));
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
