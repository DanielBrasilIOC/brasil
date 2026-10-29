let base=null;
const $=id=>document.getElementById(id);
const norm=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const rows=d=>Array.isArray(d?.rows)?d.rows:[];
const findDs=terms=>(base?.datasets||[]).find(d=>terms.some(t=>norm(`${d.id} ${d.title} ${d.short} ${d.source_name}`).includes(norm(t))));
const key=(r,terms)=>Object.keys(r||{}).find(k=>terms.some(t=>norm(k).includes(t)));
const parseMoney=v=>typeof v==='number'?v:Number(String(v??'').replace(/[^0-9,.-]/g,'').replace(/\.(?=\d{3}(?:\D|$))/g,'').replace(',','.'))||0;
const dateValue=r=>{for(const [k,v] of Object.entries(r||{})){const n=norm(k);if(n.includes('data')||n.includes('pagamento')||n.includes('emissao')){if(/^\d{4}-\d{2}-\d{2}/.test(String(v)))return String(v).slice(0,10);if(/^\d{2}\/\d{2}\/\d{4}/.test(String(v))){const [d,m,y]=String(v).slice(0,10).split('/');return `${y}-${m}-${d}`}}}return null};
const fmtDate=s=>s?new Date(s+'T12:00:00').toLocaleDateString('pt-BR'):'';
const valueKey=r=>key(r,['valor'])||key(r,['saldo'])||key(r,['total'])||key(r,['liquido'])||key(r,['bruto'])||key(r,['pagamento']);
const payments=()=>{const d=findDs(['ordens bancarias pagas','ob pagas','ordens pagas']);return {d,rows:rows(d)}};
const dateFromText=q=>{const m=q.match(/(?:em|no|na|de)\s+(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+)?(20\d{2})?/);if(!m)return null;const months=['janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];const idx=months.indexOf(m[1]);const y=Number(m[2]||base?.source_updated_at?.slice(0,4)||new Date().getFullYear());const start=`${y}-${String(idx+1).padStart(2,'0')}-01`;const next=new Date(Date.UTC(y,idx+1,1));const end=`${next.getUTCFullYear()}-${String(next.getUTCMonth()+1).padStart(2,'0')}-${String(next.getUTCDate()).padStart(2,'0')}`;const monthLabels=['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];return {start,end,label:`${monthLabels[idx]} de ${y}`};};
const threshold=q=>{const m=q.match(/(?:acima|maior|superior)\s*(?:de|a)?\s*r?\$?\s*([\d\.]+(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(mil|milhao|milhoes)?/);if(!m)return null;let n=Number(m[1].replace(/\./g,'').replace(',','.'));if(m[2]==='mil')n*=1000;if(m[2]&&m[2].startsWith('milhao'))n*=1000000;return n;};
const datasetName=q=>{if(q.includes('saldo orcamentario')||q.includes('orcamentario'))return ['saldo orcamentario','orcamentario'];if(q.includes('diaria'))return ['diarias pagas','diarias'];if(q.includes('publicac'))return ['publicacoes pagas','publicacoes'];if(q.includes('restos'))return ['restos a pagar','restos'];if(q.includes('empenho'))return ['empenhos 2026','empenhos'];if(q.includes('saldo financeiro')||q.includes('saldo'))return ['saldo financeiro','financeiro'];if(q.includes('ob')||q.includes('ordens bancarias')||q.includes('pagamento'))return ['ordens bancarias pagas','ob pagas','ordens pagas'];return null;};
function paymentRows(q){const terms=datasetName(q)||['ordens bancarias pagas'];const d=findDs(terms);return {d,rows:rows(d)}}
const STOP_PERSON_WORDS=new Set(['quanto','qual','quais','foi','foram','pago','paga','pagos','pagas','pagamento','pagamentos','valor','total','de','do','da','dos','das','ao','aos','as','o','os','a','um','uma','no','na','em','por','para','sobre','temos','tem','houve','recebeu','recebido','recebida','ob','obs','ordem','bancaria','bancarias','ultima','ultimo','maior','menor','top','listar','liste','mostre','me','diga','favorecido']);
function answerFavorecido(original){
 const q=norm(original);
 const n=norm(q);
 const wantsPerson=/(pago|paga|pagamento|pagamentos|valor|total|recebeu|recebido|ob|quanto|maior|ultima|ultimo|top)/.test(n);
 if(!wantsPerson)return null;
 let d=null;
 if(n.includes('diaria'))d=findDs(['diarias_pagas','diarias pagas']);
 else if(n.includes('publicac'))d=findDs(['publicacoes_pagas','publicacoes pagas']);
 else d=findDs(['ordens_bancarias','ordens bancarias pagas','ob pagas']);
 const data=rows(d);
 if(!data.length)return null;
 const fk=key(data[0],['favorecido','beneficiario','credor','nome']);
 if(!fk)return null;
 const qTokens=[...new Set(n.split(/[^a-z0-9]+/).filter(t=>t.length>2&&!STOP_PERSON_WORDS.has(t)))];
 if(!qTokens.length)return null;
 const names=[...new Set(data.map(r=>String(r[fk]||'').trim()).filter(Boolean))];
 const scored=names.map(name=>{const tokens=norm(name).split(/[^a-z0-9]+/).filter(t=>t.length>2);return {name,score:tokens.filter(t=>qTokens.includes(t)).length};}).filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
 if(!scored.length)return null;
 const best=scored.filter(x=>x.score===scored[0].score);
 if(best.length!==1)return 'Encontrei mais de um favorecido compatível. Informe o nome completo para evitar atribuir pagamentos à pessoa errada: '+best.slice(0,6).map(x=>x.name).join('; ');
 const name=best[0].name;
 let found=data.filter(r=>norm(r[fk])===norm(name));const range=dateFromText(q);if(range)found=found.filter(r=>{const dt=dateValue(r);return dt&&dt>=range.start&&dt<range.end});
 if(!found.length)return null;
 if(n.includes('ultima')||n.includes('ultimo')){
  const dated=found.map(r=>({r,d:dateValue(r)})).filter(x=>x.d).sort((a,b)=>b.d.localeCompare(a.d));
  if(!dated.length)return 'Encontrei registros de '+name+', mas não há datas válidas para confirmar o último pagamento.';
  const r=dated[0].r;const ok=key(r,['ob','ordem','documento']);const vk=valueKey(r);
  return 'Último registro de pagamento de '+name+': '+fmtDate(dated[0].d)+(ok?'\\nOB/documento: '+r[ok]:'')+(vk?'\\nValor: '+money(parseMoney(r[vk])):'')+'\\n\\nFonte: '+(d.source_name||d.title)+'\\nData da base: '+(base.source_updated_at||'não informada')+'.';
 }
 if(n.includes('maior')||n.includes('top ')){
  found.sort((a,b)=>parseMoney(b[key(b,['valor','pagamento','total'])])-parseMoney(a[key(a,['valor','pagamento','total'])]));
  const m=n.match(/top\\s+(\\d+)|(\\d+)\\s+maiores/);const limit=Math.min(10,Math.max(1,Number(m&&(m[1]||m[2])||1)));
  return 'Maiores pagamentos encontrados para '+name+':\\n'+found.slice(0,limit).map((r,i)=>{const vk=key(r,['valor','pagamento','total']);const ok=key(r,['ob','ordem','documento']);const dt=dateValue(r);return (i+1)+'. '+money(parseMoney(r[vk]))+(dt?' · '+fmtDate(dt):'')+(ok?' · OB/documento '+r[ok]:'');}).join('\\n')+'\\n\\nRegistros considerados: '+found.length+'\\nFonte: '+(d.source_name||d.title)+'\\nData da base: '+(base.source_updated_at||'não informada')+'.';
 }
 const vk=valueKey(found[0]);
 if(!vk)return 'Encontrei registros de '+name+', mas não identifiquei uma coluna de valor; não vou calcular um total sem esse campo.';
 const total=Math.round(found.reduce((s,r)=>s+parseMoney(r[vk]),0)*100)/100;
 return 'Total pago a '+name+(range?' em '+range.label:'')+': '+money(total)+'\\nRegistros considerados: '+found.length+'\\n\\nCritério: soma dos valores dos registros desse favorecido na base consultada.\\nFonte: '+(d.source_name||d.title)+'\\nData da base: '+(base.source_updated_at||'não informada')+'.';
}
function answer(original){const q=norm(original);
 if(!base)return 'Aguarde o carregamento da base.';const respostaFavorecido=answerFavorecido(original);if(respostaFavorecido)return respostaFavorecido;
 const {d,rows:rws}=paymentRows(q);
 if((q.includes('ultima')||q.includes('ultimo'))&&q.includes('ob')){if(!d)return 'Não encontrei a base de Ordens Bancárias Pagas. Não vou inventar uma resposta.';const a=rws.map(r=>({r,date:dateValue(r)})).filter(x=>x.date).sort((a,b)=>b.date.localeCompare(a.date));if(!a.length)return 'A base foi encontrada, mas não há data reconhecível para confirmar a última OB.';const r=a[0].r,ob=key(r,['ob','ordem']),val=valueKey(r),fav=key(r,['favorecido']);return `A última OB paga registrada é de ${fmtDate(a[0].date)}.\n${ob?`OB: ${r[ob]}\n`:''}${val?`Valor: ${money(parseMoney(r[val]))}\n`:''}${fav?`Favorecido: ${r[fav]}\n`:''}\nFonte: ${d.source_name||d.title}`;}
 if(q.includes('maior')||q.includes('top ')){if(!d)return 'Não encontrei a base de pagamentos.';let a=rws.map(r=>({r,v:parseMoney(r[valueKey(r)])})).filter(x=>Number.isFinite(x.v)&&x.v!==0);const range=dateFromText(q);if(range)a=a.filter(x=>{const dt=dateValue(x.r);return dt&&dt>=range.start&&dt<range.end});const rankMatch=q.match(/top\\s+(\\d+)|(\\d+)\\s+maiores/);const lim=Math.min(10,Math.max(1,Number(rankMatch&&(rankMatch[1]||rankMatch[2])||1)));a.sort((x,y)=>y.v-x.v);if(!a.length)return 'Não há registros que atendam aos filtros informados.';return `Maiores pagamentos${range?' no período solicitado':''}:\n`+a.slice(0,lim).map((x,i)=>{const ob=key(x.r,['ob','ordem']),fav=key(x.r,['favorecido']);return `${i+1}. ${money(x.v)}${ob?` · OB ${x.r[ob]}`:''}${fav?` · ${x.r[fav]}`:''}`}).join('\n')+`\n\nFonte: ${d.source_name||d.title}`;}
 if((q.includes('acima')||q.includes('superior')||q.includes('maior que'))&&d){const t=threshold(q);if(t!==null){let a=rws.map(r=>({r,v:parseMoney(r[valueKey(r)])})).filter(x=>x.v>t);const range=dateFromText(q);if(range)a=a.filter(x=>{const dt=dateValue(x.r);return dt&&dt>=range.start&&dt<range.end});const total=a.reduce((s,x)=>s+x.v,0);return `${a.length} registro(s) acima de ${money(t)}${range?' no período solicitado':''}.\nTotal: ${money(total)}\nFonte: ${d.source_name||d.title}`;}}
 if((q.includes('quanto')||q.includes('total'))&&d){const range=dateFromText(q);if(range){const a=rws.filter(r=>{const dt=dateValue(r);return dt&&dt>=range.start&&dt<range.end});const total=a.reduce((s,r)=>s+parseMoney(r[valueKey(r)]),0);return `Total no período solicitado: ${money(total)}\nRegistros: ${a.length}\nFonte: ${d.source_name||d.title}`;}}
 const map=[['saldo orcamentario',['saldo orcamentario','orcamentario'],'Saldo Orçamentário'],['saldo financeiro',['saldo financeiro','financeiro'],'Saldo Financeiro'],['restos a pagar',['restos a pagar','restos'],'Restos a Pagar'],['empenhos 2026',['empenhos 2026','empenhos'],'Empenhos 2026'],['diaria',['diarias pagas','diarias'],'Diárias Pagas'],['publicac',['publicacoes pagas','publicacoes'],'Publicações Pagas']];
 for(const [needle,terms,label] of map)if(q.includes(needle)){const d=findDs(terms);return d?`${label}: ${money(d.total)}\nRegistros: ${d.detail_count??rows(d).length}\nFonte: ${d.source_name||d.title}`:`Não encontrei a base de ${label}.`;}
 return `Não consegui interpretar essa pergunta com segurança.\n\nTente, por exemplo:\n• Qual foi a última OB paga?\n• Quais foram os 5 maiores pagamentos em outubro?\n• Quantas OBs acima de R$ 50 mil foram pagas em outubro?\n• Qual o total de pagamentos em outubro?\n• Qual o saldo financeiro?`;
}
async function load(){try{const r=await fetch('../data.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const raw=await r.json();base=typeof raw.content==='string'?JSON.parse(raw.content):raw;$('status').textContent=`Base carregada: ${base.source_updated_at||'data não informada'} · ${base.datasets?.length||0} conjuntos de dados.`;$('status').className='status ok';}catch(e){$('status').textContent='Não foi possível carregar data.json: '+e.message;$('status').className='status err';}}
function ask(q){$('answer').hidden=false;$('answer').textContent=base?answer(q):'Aguarde o carregamento da base.'}
$('ask').onclick=()=>ask($('q').value);$('q').onkeydown=e=>{if(e.key==='Enter')ask($('q').value)};document.querySelectorAll('.examples button').forEach(b=>b.onclick=()=>{$('q').value=b.dataset.q;ask(b.dataset.q)});load();
