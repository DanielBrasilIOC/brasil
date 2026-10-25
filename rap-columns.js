/* Colunas padronizadas da aba Restos a Pagar. Carregado pelo dashboard-v2.html. */
(function(){
  function apply(){
    const title=document.getElementById('detailTitle');
    if(typeof cols==='undefined'||!cols.restos||!title||title.textContent.trim()!=='Restos a Pagar')return;
    const wanted=[['empenho','Empenho'],['fornecedor','Fornecedor'],['natureza_codigo','Natureza'],['saldo','Saldo']];
    if(JSON.stringify(cols.restos)!==JSON.stringify(wanted)){
      cols.restos=wanted;
      if(typeof drawTable==='function')drawTable();
    }
  }
  const title=document.getElementById('detailTitle');
  if(title)new MutationObserver(apply).observe(title,{childList:true,characterData:true,subtree:true});
  document.addEventListener('DOMContentLoaded',apply);
  apply();
})();
