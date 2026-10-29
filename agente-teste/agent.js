let base=null;
const $=id=>document.getElementById(id);
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const dateValue=(r)=>{for(const k of Object.keys(r||{})){const n=k.toLowerCase();if(n.includes('data')||n.includes('pagamento')||n.includes('emissão')||n.includes('emissao')){const v=r[k];if(v&&/^\d{4}-\d{2}-\d{2}/.test(String(v)))return String(v).slice(0,10);if(v&&/^\d{2}\/\d{2}\/\d{4}/.test(String(v))){const [d,m,y]=String(v).slice(0,10).split('/');return `${y}-${m}-${d}`}}}return null};
const findDs=(terms)=>{const ds=base?.datasets||[];return ds.find(d=>terms.some(t=>`${d.id} ${d.title} ${d.short} ${d.source_name}`.toLowerCase().includes(t)))||null};
function rowsOf(d){return Array.isArray(d?.rows)?d.rows:[]}
function answer(q){
 q=q.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
 if(q.includes('ultima')&&q.includes('ob')&&(q.includes('paga')||q.includes('pagamento'))){
   const d=findDs(['ordens bancarias pagas','ob pagas','pagamentos','ordens pagas']);
   if(!d)return 'Não encontrei uma base de Ordens Bancárias Pagas identificável no data.json atual.\n\nNão vou inventar uma resposta.';
   const rows=rowsOf(d).map(r=>({r,date:dateValue(r)})).filter(x=>x.date).sort((a,b)=>b.date.localeCompare(a.date));
   if(!rows.length)return 'A base foi encontrada, mas não há uma data de pagamento reconhecível nos registros.\n\nNão vou inferir a última OB.';
   const x=rows[0].r;const ob=Object.entries(x).find(([k])=>/\bob\b|ordem/.test(k.toLowerCase()));const val=Object.entries(x).find(([k])=>/valor/.test(k.toLowerCase()));const fav=Object.entries(x).find(([k])=>/favorecido/.test(k.toLowerCase()));
   return `A última OB paga registrada na base é de ${new Date(rows[0].date+'T12:00:00').toLocaleDateString('pt-BR')}.\n${ob?`OB: ${ob[1]}\n`:''}${val?`Valor: ${money(val[1])}\n`:''}${fav?`Favorecido: ${fav[1]}\n`:''}\nFonte: ${d.source_name||d.title}`;
 }
 let d=null;
 if(q.includes('saldo financeiro'))d=findDs(['saldo financeiro','financeiro']);
 else if(q.includes('restos a pagar'))d=findDs(['restos a pagar','restos']);
 else if(q.includes('empenhos 2026')||q.includes('empenhos'))d=findDs(['empenhos 2026','empenhos']);
 else if(q.includes('maior pagamento'))d=findDs(['ordens bancarias pagas','ob pagas','pagamentos']);
 if(d){if(q.includes('maior pagamento')){const rows=rowsOf(d);const valKey=r=>Object.keys(r).find(k=>/valor|saldo/.test(k.toLowerCase()));const x=rows.filter(r=>valKey(r)).sort((a,b)=>Number(b[valKey(b)])-Number(a[valKey(a)]))[0];return x?`Maior registro encontrado: ${money(x[valKey(x)])}.\nFonte: ${d.source_name||d.title}`:'Não há valores numéricos suficientes para calcular.'}return `${d.title}: ${money(d.total)}\nRegistros detalhados: ${d.detail_count ?? rowsOf(d).length}\nFonte: ${d.source_name||d.title}`}
 return 'Ainda não reconheço essa pergunta neste protótipo.\n\nNo ambiente de teste, estou priorizando consultas determinísticas às bases do painel. Tente perguntar sobre saldo financeiro, restos a pagar, empenhos 2026, maior pagamento ou última OB paga.';
}
async function load(){try{const r=await fetch('../data.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const raw=await r.json();base=typeof raw.content==='string'?JSON.parse(raw.content):raw;$('status').textContent=`Base carregada: ${base.source_updated_at||'data não informada'} · ${base.datasets?.length||0} conjuntos de dados.`;$('status').className='status ok';}catch(e){$('status').textContent='Não foi possível carregar data.json: '+e.message;$('status').className='status err'}}
function ask(q){if(!base){$('answer').hidden=false;$('answer').textContent='Aguarde o carregamento da base.';return}$('answer').hidden=false;$('answer').textContent=answer(q);}
$('ask').onclick=()=>ask($('q').value);$('q').onkeydown=e=>{if(e.key==='Enter')ask($('q').value)};document.querySelectorAll('.examples button').forEach(b=>b.onclick=()=>{$('q').value=b.dataset.q;ask(b.dataset.q)});load();
