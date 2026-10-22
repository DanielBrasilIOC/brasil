/*
 * Classificação de envelhecimento dos Restos a Pagar.
 * A base atual não traz status de processamento: todos os registros de RAP
 * são apresentados como NÃO PROCESSADOS. A classificação abaixo fica
 * exclusivamente dentro da aba "Restos a Pagar".
 */
(function(){
  const currentYear=new Date().getFullYear();
  const getYear=r=>{
    const text=String(r.empenho??r.numero_ne??r.ne??'');
    // O ano está no campo Empenho imediatamente antes das letras "NE".
    // Exemplos aceitos: 2023NE..., 2023 NE..., ...2023NE...
    const m=text.match(/(?:^|[^0-9])(20\d{2})(?=\s*NE)/i);
    if(m)return Number(m[1]);
    for(const k of ['ano','ano_rap','exercicio','exercicio_rap','year']){
      const y=String(r[k]??'').match(/20\d{2}/);
      if(y)return Number(y[0]);
    }
    return null;
  };
  function renderAging(){
    const title=document.getElementById('detailTitle');
    const detail=document.getElementById('details');
    if(!title||!detail||!/^Restos a Pagar$/i.test(title.textContent.trim())){
      const old=document.getElementById('rap-aging');
      if(old)old.remove();
      return;
    }
    const ds=(data?.datasets||[]).find(d=>d.id==='restos');
    if(!ds)return;
    const byYear={};
    ds.rows.forEach(r=>{
      const y=getYear(r),v=N(r.saldo);
      const key=y||'Sem ano';
      if(!byYear[key])byYear[key]={valor:0,registros:0};
      byYear[key].valor+=v;
      byYear[key].registros++;
    });
    const aging=Object.keys(byYear).filter(k=>k!=='Sem ano').map(Number).sort((a,b)=>b-a).map(y=>({year:y,age:currentYear-y,...byYear[y]}));
    const total=ds.rows.reduce((s,r)=>s+N(r.saldo),0);
    const old=aging.filter(x=>x.age>=3&&x.valor>0);
    const highest=aging.filter(x=>x.valor>0&&x.age>=5);
    const cards=aging.map(x=>{
      const cls=x.age>=5?'rap-high':x.age>=3?'rap-attn':'rap-recent';
      const label=x.age>=5?'🔴 Alto':x.age>=3?'🟡 Atenção':'🟢 Recente';
      return `<div class="rap-age-row ${cls}"><div><b>${x.year}</b><span>${label}</span></div><strong>${F(x.valor)}</strong><small>${I(x.registros)} registro(s) • ${x.age} ano(s) de idade</small></div>`;
    }).join('');
    let box=document.getElementById('rap-aging');
    if(!box){
      box=document.createElement('article');
      box.id='rap-aging';
      box.className='panel';
      const target=detail.querySelector('.kpis');
      if(target)target.insertAdjacentElement('afterend',box); else detail.prepend(box);
    }
    box.innerHTML=`<div class="head"><div><h3>Classificação de envelhecimento</h3><p class="desc">Termômetro aplicado somente aos Restos a Pagar, pelo ano do empenho identificado antes de "NE".</p></div><span class="badge ${highest.length?'r':'ok'}">${highest.length?'Revisão prioritária':'Acompanhamento'}</span></div><div class="rap-aging-legend"><span>🟢 <b>Recente</b>: menos de 3 anos</span><span>🟡 <b>Atenção</b>: 3 anos ou mais</span><span>🔴 <b>Alto</b>: 5 anos ou mais</span></div><div class="alert ${highest.length?'r':old.length?'w':'ok'}"><b>${highest.length?'RAP antigo requer revisão':old.length?'RAP com atenção por envelhecimento':'RAP dentro do critério de envelhecimento'}</b><br>Total de RAP não processado: ${F(total)}. ${highest.length?`Há ${I(highest.length)} ano(s) com 5 anos ou mais.`:old.length?`Há ${I(old.length)} ano(s) com 3 anos ou mais.`:'Nenhum saldo atingiu 3 anos.'}</div><div class="rap-aging-list">${cards||'<div class="empty">Não foi possível identificar o ano nos registros de RAP.</div>'}</div>`;
  }
  const style=document.createElement('style');
  style.textContent=`#rap-aging{margin-bottom:13px}.rap-aging-legend{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0;font-size:12px}.rap-aging-list{display:grid;gap:7px}.rap-age-row{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center;padding:11px 13px;border:1px solid #e1e8ee;border-left:4px solid #438b89;border-radius:9px;background:#fbfcfd}.rap-age-row>div{display:flex;gap:12px;align-items:center}.rap-age-row span{font-size:11px;font-weight:800}.rap-age-row strong{color:#163b5c}.rap-age-row small{color:#6d7e8b}.rap-attn{border-left-color:#a46a16;background:#fffbf3}.rap-high{border-left-color:#b33b3b;background:#fff8f8}.rap-recent{border-left-color:#438b89}@media(max-width:700px){.rap-age-row{grid-template-columns:1fr;gap:5px}}`;
  document.head.appendChild(style);
  setInterval(renderAging,500);
  renderAging();
})();