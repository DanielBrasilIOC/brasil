/* Termômetro de Restos a Pagar — regra operacional solicitada para a base atual.
   A base "Restos a Pagar" não traz campo de status; por solicitação da gestão,
   todos os registros são tratados como NÃO PROCESSADOS. O ano é extraído do
   número do empenho (padrão SIAFI ...NEYYYY...). O alerta indica envelhecimento,
   não afirma cancelamento automático ou irregularidade jurídica. */
function rap(rs){
  const total=rs.reduce((s,r)=>s+N(r.saldo),0);
  const b=document.getElementById('rapb');
  const box=document.getElementById('rap');
  if(!rs.length){
    b.className='badge w'; b.textContent='Sem registros'; box.innerHTML=''; return;
  }
  const currentYear=new Date().getFullYear();
  const getYear=r=>{
    const m=String(r.empenho??r.numero_ne??r.ne??'').match(/NE(20\\d{2})/i);
    if(m)return Number(m[1]);
    const candidates=['ano','ano_rap','exercicio','exercicio_rap','year'];
    const k=field([r],candidates);
    const y=k?Number(String(r[k]).match(/20\\d{2}/)?.[0]):NaN;
    return Number.isFinite(y)?y:null;
  };
  const byYear={};
  rs.forEach(r=>{
    const y=getYear(r); const v=N(r.saldo);
    const key=y||'Sem ano';
    if(!byYear[key])byYear[key]={valor:0,registros:0};
    byYear[key].valor+=v; byYear[key].registros++;
  });
  const years=Object.keys(byYear).filter(x=>x!=='Sem ano').map(Number).sort((a,b)=>a-b);
  const aging=years.map(y=>({year:y,age:currentYear-y,...byYear[y]}));
  const old=aging.filter(x=>x.age>=3 && x.valor>0).sort((a,b)=>b.age-a.age);
  const oldest=aging.filter(x=>x.valor>0).sort((a,b)=>b.age-a.age)[0];
  const pct=total>0?100:0;
  const rows=aging.slice().sort((a,b)=>b.year-a.year).map(x=>{
    const level=x.age>=5?'r':x.age>=3?'w':'ok';
    const label=x.age>=5?'ALTO':x.age>=3?'ATENÇÃO':'RECENTE';
    return `<div class="alert ${level==='r'?'r':level==='w'?'w':''}"><b>${x.year} • ${label}</b> — ${F(x.valor)} <span class="tiny">(${I(x.registros)} registro(s), ${x.age} ano(s) de idade)</span></div>`;
  }).join('');
  b.className='badge '+(old.length?'r':'ok');
  b.textContent=old.length?`Atenção: ${old.length} ano(s) envelhecido(s)`:'Dentro do termômetro';
  box.innerHTML=`<div class="donut">
    <div class="ring" style="background:conic-gradient(#b33b3b 0 ${pct}%,#e9eef2 ${pct}% 100%)"></div>
    <div class="legend">
      <div><span class="dot red"></span><b>Não processados:</b> ${F(total)}</div>
      <div><span class="dot gold"></span><b>Processados:</b> R$ 0,00</div>
      <div class="tiny">A base atual é tratada integralmente como RAP não processado, conforme regra operacional definida para este painel.</div>
    </div>
  </div>
  <div class="alert ${old.length?'r':'ok'}"><b>${old.length?'RAP com envelhecimento relevante':'RAP sem alerta de envelhecimento'}</b><br>${old.length?`Há ${I(old.length)} ano(s) com saldo e idade igual ou superior a 3 anos. O painel destaca esses saldos para revisão.`:'Não foram identificados saldos com idade igual ou superior a 3 anos.'}</div>
  ${oldest?`<div class="tiny" style="margin-top:8px">Mais antigo com saldo: <b>${oldest.year}</b> (${oldest.age} ano(s)) — ${F(oldest.valor)}.</div>`:''}
  <div style="margin-top:8px">${rows}</div>`;
}
/* Recalcula a visão após substituir a função original. */
if(typeof overview==='function') overview();
