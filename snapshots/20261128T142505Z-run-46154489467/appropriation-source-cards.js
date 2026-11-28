(function(){
  const originalShow=show;
  function renderAppropriationSourceCards(){
    const dataset=(data&&Array.isArray(data.datasets)?data.datasets:[]).find(item=>item.id==='apropriacao_pendente');
    const target=document.getElementById('detailKpis');
    if(!dataset||!target)return;
    const rows=(Array.isArray(dataset.rows)?dataset.rows:[]).filter(row=>!/^DOB/i.test(String(row.situacao_despesa??'').trim()));
    const sources=new Map();
    const shared=[];
    let grand=0;
    for(const row of rows){
      const amount=N(row.valor);
      grand+=amount;
      let names=[...new Set(String(row.fontes_recursos??'').split('|').map(value=>value.trim()).filter(Boolean))];
      if(!names.length)names=['Fonte não identificada'];
      for(const name of names){
        if(!sources.has(name))sources.set(name,{name,documents:0,exclusiveDocuments:0,sharedDocuments:0,exclusiveValue:0});
        const item=sources.get(name);
        item.documents+=1;
        if(names.length>1)item.sharedDocuments+=1;
      }
      if(names.length===1){
        const item=sources.get(names[0]);
        item.exclusiveDocuments+=1;
        item.exclusiveValue+=amount;
      }else{
        shared.push({document:String(row.documento_habil??'').trim(),sources:names,amount});
      }
    }
    const totalCard='<article class="kpi ap-source-card ap-source-total"><div class="label">Total pendente consolidado</div><div class="value">'+F(grand)+'</div><div class="ap-source-meta">Soma dos documentos hábeis únicos, sem duplicar valores.</div></article>';
    const sourceCards=[...sources.values()].sort((a,b)=>b.exclusiveValue-a.exclusiveValue||a.name.localeCompare(b.name,'pt-BR')).map(item=>{
      const value=item.exclusiveDocuments?F(item.exclusiveValue):'Não individualizado';
      const hint=item.exclusiveDocuments
        ? I(item.exclusiveDocuments)+' documento(s) com fonte exclusiva. '+I(item.sharedDocuments)+' documento(s) também vinculados a outras fontes.'
        : I(item.documents)+' documento(s) vinculado(s); valor consta no card de múltiplas fontes, sem rateio na base.';
      return '<article class="kpi ap-source-card"><div class="label">Fonte de recurso / pagamento</div><div class="ap-source-name">'+E(item.name)+'</div><div class="value">'+value+'</div><div class="ap-source-meta">'+hint+'</div></article>';
    }).join('');
    const sharedCard=shared.length
      ? '<article class="kpi ap-source-card ap-source-shared"><div class="label">Documentos com múltiplas fontes</div><div class="value">'+F(shared.reduce((sum,item)=>sum+item.amount,0))+'</div><div class="ap-source-meta">'+I(shared.length)+' documento(s) sem rateio individual informado na extração. Valores contabilizados uma única vez. '+E(shared.map(item=>item.document).filter(Boolean).join(' • '))+'</div></article>'
      : '';
    const count=rows.length;
    target.innerHTML=totalCard+'<article class="kpi"><div class="label">Documentos hábeis</div><div class="value">'+I(count)+'</div><div class="ap-source-meta">Registros consolidados por Documento Hábil.</div></article>'+sourceCards+sharedCard;
  }
  if(!document.getElementById('apSourceCardsStyle')){
    const style=document.createElement('style');
    style.id='apSourceCardsStyle';
    style.textContent='#detailKpis .ap-source-card{min-width:0}#detailKpis .ap-source-name{font-size:12px;font-weight:800;color:var(--n);line-height:1.4;margin-top:7px;overflow-wrap:anywhere}#detailKpis .ap-source-meta{font-size:10px;color:var(--m);line-height:1.5;margin-top:7px}#detailKpis .ap-source-total{border-color:#b9cbd4}#detailKpis .ap-source-shared{border-style:dashed}';
    document.head.appendChild(style);
  }
  show=function(id){originalShow(id);if(id==='apropriacao_pendente')renderAppropriationSourceCards();};
})();
