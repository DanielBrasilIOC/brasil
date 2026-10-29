(function(root){
'use strict';
const norm=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
const money=n=>'R$ '+Number(n||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const integer=n=>Number(n||0).toLocaleString('pt-BR');
const dateValue=s=>{let m=String(s??'').trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);if(m)return new Date(+m[3],+m[2]-1,+m[1]).getTime();m=String(s??'').trim().match(/^(\d{4})-(\d{2})-(\d{2})/);return m?new Date(+m[1],+m[2]-1,+m[3]).getTime():0};
const dateBR=s=>{const t=dateValue(s);return t?new Date(t).toLocaleDateString('pt-BR'):(s||'não informado')};
const aliases=[['ordens_bancarias',['ordem bancaria','ordens bancarias','ob paga','obs pagas','pagamento bancario']],['diarias_pagas',['diaria','diarias','viagem','viagens','viajou','viajaram','viajante','pcdp']],['publicacoes_pagas',['publicacao','publicacoes','artigo','artigos cientificos']],['bolsistas_pagos',['bolsista','bolsistas','bolsa','bolsas']],['financeiro',['saldo financeiro','saldos financeiros','financeiro','vinculacao']],['restos',['restos a pagar','rap']],['empenhos',['empenho','empenhos','nota de empenho']],['orcamentario',['saldo orcamentario','orcamento','orcamentario','dotacao']],['repasses',['aguardando repasse','repasse','repasses','solicitacao ne']]];
const getData=(data,id)=>data?.datasets?.find(d=>d.id===id)||{id,rows:[],total:0,title:id};
const unique=(arr,fn)=>{const m=new Map();for(const x of arr){const k=fn(x);if(k&&!m.has(k))m.set(k,x)}return [...m.values()]};
const pcdpOf=r=>{const m=String(r.observacao||'').match(/PCDP\s+([0-9A-Z/-]+)/i);return m?m[1].toUpperCase():''};
function tripStats(rows){const trips=new Map();for(const r of rows||[]){const id=pcdpOf(r);if(!id)continue;let t=trips.get(id);if(!t){t={id,nome:String(r.favorecido||'').trim(),valor:0,data:r.data_pagamento||''};trips.set(id,t)}t.valor+=Number(r.valor)||0}const people=new Map();for(const t of trips.values()){const k=norm(t.nome);if(!k)continue;const p=people.get(k)||{nome:t.nome,viagens:0,pcdps:[]};p.viagens++;p.pcdps.push(t.id);people.set(k,p)}return {trips:[...trips.values()],people:[...people.values()].sort((a,b)=>b.viagens-a.viagens||a.nome.localeCompare(b.nome,'pt-BR'))}}
function latest(rows){return [...(rows||[])].sort((a,b)=>dateValue(b.data_pagamento||b.data)-dateValue(a.data_pagamento||a.data))[0]}
function topOrders(rows,n){return [...(rows||[])].sort((a,b)=>(Number(b.valor)||0)-(Number(a.valor)||0)).slice(0,n)}
function pickDataset(q){const nq=norm(q);let best=null,score=0;for(const [id,terms] of aliases)for(const term of terms){const t=norm(term);if(nq.includes(t)&&t.length>score){best=id;score=t.length}}return best}
function personFromQuestion(q,rows){const nq=norm(q),names=unique(rows||[],r=>norm(r.favorecido)).map(r=>String(r.favorecido||'')).filter(Boolean).sort((a,b)=>b.length-a.length);return names.find(name=>nq.includes(norm(name)))||''}
function answerQuestion(question,data){
 const q=String(question||'').trim(),nq=norm(q);if(!q)return {text:'Digite uma pergunta sobre os dados do painel.',source:null};
 const id=pickDataset(q);
 if(/viag|viaj|pcdp/.test(nq)||id==='diarias_pagas'){
  const d=getData(data,'diarias_pagas'),rows=d.rows||[],stats=tripStats(rows);
  if(/quem.*(mais|viaj)|maior.*numero.*viag|mais.*viag/.test(nq)){const max=stats.people[0]?.viagens||0,leaders=stats.people.filter(p=>p.viagens===max);return {text:'Quem mais viajou (contagem de PCDPs únicas):\n'+leaders.map(p=>'• '+p.nome+': '+p.viagens+' viagens').join('\n')+'\n\nA contagem considera uma viagem por número de PCDP.',source:d.title,rows:leaders.length}}
  if(/lista.*(nome|pessoa)|nomes.*(viaj|viag)|quem.*viaj|todas.*pessoas/.test(nq))return {text:'Pessoas com viagens registradas ('+stats.people.length+'):\n'+stats.people.map(p=>'• '+p.nome+' — '+p.viagens+' viagens').join('\n'),source:d.title,rows:stats.people.length};
  if(/quantas?.*(viag|pcdp)|numero.*(viag|pcdp)|total.*(viag|pcdp)/.test(nq))return {text:'Foram identificadas '+integer(stats.trips.length)+' PCDPs únicas nos '+integer(rows.length)+' registros de diárias.',source:d.title,rows:stats.trips.length};
  const person=personFromQuestion(q,rows);if(person){const p=stats.people.find(x=>norm(x.nome)===norm(person)),records=rows.filter(r=>norm(r.favorecido)===norm(person));return {text:p?p.nome+' possui '+integer(p.viagens)+' viagens (PCDPs únicas). Valor total de diárias: '+money(records.reduce((s,r)=>s+(Number(r.valor)||0),0))+'.':'Não localizei viagens para '+person+'.',source:d.title}}
  if(/total|soma|valor/.test(nq))return {text:'A base de Diárias Pagas contém '+integer(rows.length)+' registros, totalizando '+money(d.total??rows.reduce((s,r)=>s+(Number(r.valor)||0),0))+'.',source:d.title};
 }
 if(id==='ordens_bancarias'||/ordem.*banc|\bob\b/.test(nq)){
  const d=getData(data,'ordens_bancarias'),rows=d.rows||[];
  if(/ultima|ultimo|mais recente|recente/.test(nq)){const r=latest(rows);return r?{text:'A última ordem bancária paga na base é '+(r.ob||'sem número')+', em '+dateBR(r.data_pagamento||r.data)+', para '+(r.favorecido||'favorecido não informado')+', no valor de '+money(r.valor)+'.',source:d.title}:{text:'Não há ordens bancárias na base.',source:d.title}}
  if(/top|maior|maiores|ranking|mais alta|mais caras/.test(nq)){const m=nq.match(/top\s*(\d{1,2})/),n=Math.min(50,Math.max(1,Number(m?.[1]||10))),rs=topOrders(rows,n);return {text:n+' maiores ordens bancárias por valor:\n'+rs.map((r,i)=>(i+1)+'. OB: '+r.ob+' | Favorecido: '+r.favorecido+' | Valor: '+money(r.valor)+' | Data: '+dateBR(r.data_pagamento||r.data)).join('\n'),source:d.title,rows:rs.length}}
  const obMatch=q.match(/\b\d{6,}\b/);if(obMatch){const r=rows.find(x=>String(x.ob||'').includes(obMatch[0]));return r?{text:'OB '+r.ob+': '+r.favorecido+'; valor '+money(r.valor)+'; pagamento em '+dateBR(r.data_pagamento||r.data)+'.',source:d.title}:{text:'Não encontrei a OB '+obMatch[0]+' na base.',source:d.title}}
  if(/quantas?|quantidade|numero de/.test(nq))return {text:'A base contém '+integer(unique(rows,r=>String(r.ob||'').trim()).length)+' ordens bancárias únicas.',source:d.title};
  if(/total|soma|valor/.test(nq))return {text:'O total das ordens bancárias pagas é '+money(rows.reduce((s,r)=>s+(Number(r.valor)||0),0))+', considerando '+integer(rows.length)+' registros.',source:d.title};
 }
 if(id){const d=getData(data,id),rows=d.rows||[];if(/quant(?:as|os)?|quantidade|numero de|quantitativo/.test(nq))return {text:(d.title||id)+': '+integer(rows.length)+' registros na base.',source:d.title};if(/total|soma|valor|saldo/.test(nq))return {text:(d.title||id)+': total de '+money(d.total??rows.reduce((s,r)=>s+(Number(r.valor??r.saldo)||0),0))+' em '+integer(rows.length)+' registros.',source:d.title};const p=personFromQuestion(q,rows);if(p){const rs=rows.filter(r=>norm(r.favorecido||r.fornecedor)===norm(p));return {text:p+' aparece em '+integer(rs.length)+' registros de '+d.title+'. Total: '+money(rs.reduce((s,r)=>s+(Number(r.valor??r.saldo)||0),0))+'.',source:d.title}}return {text:'Consigo consultar '+d.title+'. Pergunte por quantidade, valor total, favorecido, fornecedor, número de empenho ou situação.',source:d.title}}
 if(/ultima|ultimo|mais recente/.test(nq)){const d=getData(data,'ordens_bancarias'),r=latest(d.rows);if(r)return {text:'A última ordem bancária paga na base é '+r.ob+', em '+dateBR(r.data_pagamento||r.data)+', para '+r.favorecido+', no valor de '+money(r.valor)+'.',source:d.title}}
 return {text:'Não consegui identificar com segurança a informação desejada. Mencione o assunto (ordens bancárias, viagens/diárias, publicações, empenhos, saldo financeiro, saldo orçamentário, restos a pagar ou repasses) e o que deseja saber (quantidade, total, ranking, nome, número ou data). Não vou estimar valores quando a consulta não estiver clara.',source:null};
}
const api={answerQuestion,tripStats,topOrders,latest,norm};if(typeof module!=='undefined'&&module.exports)module.exports=api;if(root)root.IOCAgent=api;
})(typeof window!=='undefined'?window:globalThis);
