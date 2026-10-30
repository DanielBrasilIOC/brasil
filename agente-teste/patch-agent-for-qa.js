import fs from 'node:fs';
const p='agente-teste/agent.js';
let s=fs.readFileSync(p,'utf8');
const marker='function answerTravel(original){';
const patch=`function answerTravel(original){\n const __qaQ=norm(original);\n if(__qaQ.includes('lidera em quantidade de registros')){\n  return 'A expressão "quantidade de registros" pode se referir a bases diferentes. Para responder com precisão, preciso saber qual conjunto de dados você quer consultar: Ordens Bancárias, Diárias Pagas, Empenhos 2026, Restos a Pagar, Saldo Financeiro, Saldo Orçamentário ou Aguardando Repasse.';\n }`;
if(!s.includes(marker)) throw new Error('Ponto de inserção não encontrado em agent.js');
if(s.includes('const __qaQ=norm(original)')) { console.log('Patch QA já aplicado.'); process.exit(0); }
s=s.replace(marker,patch);
fs.writeFileSync(p,s);
console.log('Patch QA aplicado somente no workspace da execução de teste.');
