const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const agent=require('../agente-qa.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'..','data.json'),'utf8'));
const cases=[
 ['top 10 ordens bancárias','10 maiores ordens bancárias por valor'],
 ['última OB paga','última ordem bancária paga'],
 ['quem mais viajou','Quem mais viajou'],
 ['listar os nomes de quem viajou','Pessoas com viagens registradas'],
 ['quantas viagens foram feitas','PCDPs únicas'],
 ['total de diárias pagas','Diárias Pagas'],
 ['quantas ordens bancárias existem','ordens bancárias'],
 ['total de publicações pagas','Publicações Pagas'],
 ['quantos empenhos existem','Empenhos 2026'],
 ['saldo financeiro total','Saldo Financeiro'],
 ['restos a pagar total','Restos a Pagar'],
 ['saldo orçamentário total','Saldo Orçamentário'],
 ['aguardando repasse total','Aguardando Repasse Orçamentário'],
 ['quem mais viajou no IOC','Quem mais viajou'],
 ['quantas diárias pagas','Diárias Pagas']
];
let failures=[];
for(const [q,expected] of cases){const out=agent.answerQuestion(q,data);if(!out.text.toLowerCase().includes(expected.toLowerCase()))failures.push({q,expected,actual:out.text.slice(0,180)});}
const stats=agent.tripStats(data.datasets.find(d=>d.id==='diarias_pagas').rows);
assert.equal(stats.trips.length,188,'PCDPs únicas');
assert.equal(stats.people.length,105,'pessoas únicas');
assert.equal(stats.people[0].nome,'ELIZABETH FERREIRA RANGEL');
assert.equal(stats.people[0].viagens,9);
assert.equal(stats.people[1].nome,'JERONIMO AUGUSTO FONSECA ALENCAR');
assert.equal(stats.people[1].viagens,9);
assert.equal(agent.topOrders(data.datasets.find(d=>d.id==='ordens_bancarias').rows,10).length,10);
assert.equal(failures.length,0,JSON.stringify(failures,null,2));
console.log('OK: '+cases.length+' perguntas + validações de PCDP/pessoas/ranking; falhas: '+failures.length);
