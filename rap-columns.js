(function(){
  function apply(){
    if(typeof cols==='undefined'||!cols.restos)return;
    if(document.getElementById('detailTitle')?.textContent!=='Restos a Pagar')return;
    cols.restos=[['empenho','Empenho'],['fornecedor','Fornecedor'],['natureza_codigo','Natureza'],['saldo','Saldo']];
    if(typeof drawTable==='function')drawTable();
  }
  apply();
  setInterval(apply,500);
})();
