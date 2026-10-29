const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const zlib = require("node:zlib");
const { once } = require("node:events");
const { finished } = require("node:stream/promises");

const root = process.cwd();
const base = JSON.parse(fs.readFileSync(path.join(root, "data.json"), "utf8"));
const source = fs.readFileSync(path.join(root, "agente-teste", "agent.js"), "utf8").split("async function load()")[0];
const sandbox = {};
vm.runInNewContext(source + "\nglobalThis.__setBase=(v)=>{base=v}; globalThis.__answer=(q)=>answer(q);", sandbox);
sandbox.__setBase(base);
const prefixes = [
  "Preciso saber: ", "Por favor, informe: ", "Você consegue verificar: ",
  "Gostaria de consultar: ", "Pode me dizer: ", "Na base atual, ",
  "Para a diretoria, ", "Considerando os dados, ", "Em relação aos registros, ",
  "Me ajude a conferir: "
];
const prefixContexts = [
  "com base na base publicada, ", "no Painel IOC, ", "para uma conferência, ",
  "na consulta atual, ", "para um relatório, ", "em relação aos pagamentos, ",
  "para acompanhamento, ", "considerando os registros, ", "no levantamento, ",
  "com os dados disponíveis, "
];
const closes = [
  " por favor?", " com precisão?", " para conferência?", " na base publicada?",
  " com a fonte?", " sem estimativas?", " considerando todos os registros?",
  " para a diretoria?", " conforme os dados atuais?", " por gentileza?"
];
const closeContexts = [
  " Obrigado.", " Traga também a fonte.", " Quero conferir o resultado.",
  " Pode detalhar a resposta.", " Informe os números exatos.",
  " Considere todos os registros.", " Responda de forma objetiva.",
  " Preciso do dado completo.", " Para uso institucional.", " Sem arredondamentos."
];
const allPrefixes = prefixes.flatMap(a => prefixContexts.map(b => a + b));
const allSuffixes = closes.flatMap(a => closeContexts.map(b => a + b));

const groups = [
  {
    name: "ranking_viagens",
    questions: [
      "Quem mais viajou?", "Quem realizou mais viagens?",
      "Quais pessoas têm mais registros de diárias?", "Quem viajou mais vezes?",
      "Quem tem maior número de viagens?", "Quem aparece mais vezes na planilha de diárias?",
      "Quais são os servidores com mais viagens registradas?",
      "Quem lidera a quantidade de diárias pagas?",
      "Quem teve mais deslocamentos registrados?", "Quais favorecidos têm mais viagens?",
      "Mostre quem mais viajou.", "Identifique os maiores viajantes.",
      "Quem tem o maior número de registros de viagem?",
      "Quem aparece no topo do ranking de viagens?",
      "Quem recebeu diárias em mais ocasiões?", "Quais pessoas viajaram mais vezes?",
      "Quem tem mais pagamentos de diárias?", "Quem lidera em quantidade de registros?",
      "Quais são os nomes com maior frequência de diárias?",
      "Quem mais aparece nos pagamentos de viagem?",
      "Liste o ranking de quem mais viajou.", "Quem tem mais viagens na base?",
      "Quais favorecidos mais viajaram?", "Quem acumulou mais registros de viagem?",
      "Mostre o primeiro lugar em número de viagens."
    ],
    check(answer, question) {
      if (question.includes("lidera em quantidade de registros")) return answer.includes("qual conjunto de dados");
      return answer.includes("ELIZABETH FERREIRA RANGEL") && answer.includes("JERONIMO AUGUSTO FONSECA ALENCAR");
    }
  },
  {
    name: "lista_viajantes",
    questions: [
      "Liste os nomes de quem viajou.", "Quais pessoas receberam diárias?",
      "Mostre todos os favorecidos de diárias.", "Quem aparece na planilha de diárias pagas?",
      "Quero a relação de pessoas que viajaram.", "Apresente os nomes dos viajantes registrados.",
      "Quais são os nomes dos favorecidos em diárias?",
      "Liste todos os nomes com pagamentos de viagem.",
      "Mostre a lista de pessoas com diárias pagas.", "Quem teve viagem registrada na base?",
      "Relacione os beneficiários de diárias.", "Quais pessoas constam nos registros de viagem?",
      "Apresente a relação completa de viajantes.", "Mostre os nomes dos servidores com diárias.",
      "Quais favorecidos aparecem na base de diárias?",
      "Preciso dos nomes de todos os viajantes.", "Quem recebeu pagamento de diária?",
      "Liste as pessoas com registros de diárias.", "Quais são os beneficiários de viagens?",
      "Mostre todos os nomes da planilha de diárias.",
      "Traga a lista completa de favorecidos.", "Quem consta como favorecido nas diárias?",
      "Quero saber quem viajou.", "Relacione os nomes que aparecem em diárias pagas.",
      "Exiba os viajantes registrados."
    ],
    check(answer, question) {
      if (question.includes("lista completa de favorecidos")) return answer.includes("qual conjunto de dados");
      return answer.includes("Pessoas com registros de diárias pagas (105)") && answer.includes("ZENEIDA TEIXEIRA PINTO");
    }
  },
  {
    name: "total_jeronimo",
    questions: [
      "Quanto foi pago ao Jerônimo?", "Qual o total pago a Jerônimo Augusto Fonseca Alencar?",
      "Quanto Jerônimo recebeu em diárias?", "Some os pagamentos feitos a Jerônimo.",
      "Quanto foi destinado a Jerônimo nos pagamentos?",
      "Qual o montante pago ao servidor Jerônimo?", "Quanto consta pago para Jerônimo?",
      "Informe o total de pagamentos de Jerônimo.", "Qual o total das OBs de Jerônimo?",
      "Quanto Jerônimo recebeu ao todo?", "Qual o valor acumulado de Jerônimo?",
      "Quanto foi pago ao favorecido Jerônimo?", "Qual a soma dos valores pagos a Jerônimo?",
      "Apure o total pago para Jerônimo Augusto.", "Quanto aparece na base para Jerônimo?",
      "Qual o valor total das diárias de Jerônimo?", "Quanto recebeu Jerônimo na base atual?",
      "Informe a soma dos registros de Jerônimo.", "Quanto foi pago ao Jerônimo no total?",
      "Qual o total financeiro de Jerônimo?", "Calcule os pagamentos de Jerônimo.",
      "Quanto foi liquidado em favor de Jerônimo?", "Qual o valor pago ao favorecido Jerônimo?",
      "Quanto somam os pagamentos de Jerônimo.",
      "Qual o valor total pago a Jerônimo Augusto Fonseca Alencar?"
    ],
    check(answer) {
      return answer.includes("R$ 11.191,28") && answer.includes("Registros considerados: 9");
    }
  },
  {
    name: "top10_ordens_bancarias",
    questions: [
      "Top 10 ordens bancárias.", "Quais são as 10 maiores OBs?",
      "Mostre as dez ordens bancárias de maior valor.", "Liste as 10 OBs mais altas.",
      "Quais foram os dez maiores pagamentos por OB?",
      "Apresente o ranking das maiores ordens bancárias.",
      "Quais OBs têm os maiores valores?", "Mostre as dez maiores ordens bancárias pagas.",
      "Quais são as OBs mais elevadas?", "Traga o top 10 de pagamentos por ordem bancária.",
      "Liste os dez pagamentos de maior valor.", "Quais foram as maiores OBs registradas?",
      "Mostre as 10 maiores despesas pagas por OB.", "Quais ordens bancárias lideram em valor?",
      "Apresente as dez maiores OBs da base.", "Quais são os dez maiores registros de pagamento?",
      "Faça um ranking das 10 maiores OBs.", "Mostre os dez pagamentos mais altos.",
      "Quais ordens bancárias têm maior valor pago?", "Liste as maiores OBs por valor.",
      "Quero as dez OBs de maior valor.", "Quais foram as 10 maiores ordens pagas?",
      "Apresente as OBs que mais movimentaram recursos.",
      "Mostre as dez maiores transferências registradas.",
      "Quais pagamentos estão no topo do ranking?"
    ],
    check(answer) {
      return answer.includes("OB000089") && answer.includes("OB000786") && answer.includes("R$ 3.545.248,00");
    }
  }
];

const report = {
  started_at: new Date().toISOString(),
  branch: process.env.GITHUB_REF_NAME || "agente-teste",
  commit: process.env.GITHUB_SHA || null,
  base_date: base.source_updated_at || null,
  datasets: (base.datasets || []).map(d => ({ id: d.id, title: d.title, rows: (d.rows || []).length })),
  total_questions: 0,
  passed: 0,
  failed: 0,
  groups: [],
  failure_samples: [],
  run_url: process.env.GITHUB_RUN_ID ? "https://github.com/DanielBrasilIOC/brasil/actions/runs/" + process.env.GITHUB_RUN_ID : null
};
const reportsDir = path.join(root, "agente-teste", "reports");
fs.mkdirSync(reportsDir, { recursive: true });
const outputPath = path.join(reportsDir, "respostas-1-milhao.jsonl.gz");
const output = fs.createWriteStream(outputPath);
const gzip = zlib.createGzip({ level: zlib.constants.Z_BEST_SPEED });
gzip.pipe(output);

for (const group of groups) {
  let count = 0, passed = 0, failed = 0;
  for (const prefix of allPrefixes) {
    for (const core of group.questions) {
      for (const suffix of allSuffixes) {
        const question = prefix + core + suffix;
        let answer = "";
        let ok = false;
        try {
          answer = sandbox.__answer(question);
          ok = group.check(answer, question);
        } catch (error) {
          answer = "ERRO DE EXECUÇÃO: " + String(error && error.stack || error);
          ok = false;
        }
        count++;
        report.total_questions++;
        if (ok) {
          passed++;
          report.passed++;
        } else {
          failed++;
          report.failed++;
          if (report.failure_samples.length < 100) {
            report.failure_samples.push({ group: group.name, question, answer: String(answer).slice(0, 1200) });
          }
        }
        const line = JSON.stringify({ group: group.name, question, answer, correct: ok }) + "\n";
        if (!gzip.write(line)) await once(gzip, "drain");
      }
    }
  }
  report.groups.push({ name: group.name, total: count, passed, failed, accuracy: Number((passed / count * 100).toFixed(4)) });
}
gzip.end();
await finished(output);
report.finished_at = new Date().toISOString();
report.accuracy = Number((report.passed / report.total_questions * 100).toFixed(6));
report.answers_archive = "respostas-1-milhao.jsonl.gz";
fs.writeFileSync(path.join(reportsDir, "auditoria-milhao.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
