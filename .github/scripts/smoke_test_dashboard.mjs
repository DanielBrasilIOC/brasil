import { chromium } from "playwright";
import { readFile } from "node:fs/promises";

const browser = await chromium.launch({ headless: true });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("pageerror", error => errors.push(error.stack || error.message));
  page.on("console", message => {
    if (message.type() === "error" && !/Failed to load resource:.*404/.test(message.text())) errors.push(message.text());
  });
  const response = await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
  if (!response?.ok()) throw new Error("index.html não carregou corretamente.");

  const frame = page.frameLocator("#dashboard");
  await frame.locator('#nav button[data-x="visao"]').waitFor({ state: "visible", timeout: 20000 });
  await frame.locator('#nav button[data-x="repasses"]').click();
  await frame.locator(".priority-meter .priority-value").nth(2).waitFor({ state: "visible", timeout: 20000 });

  // Os valores de prioridade vêm dos dados vigentes; o teste confere a consistência
  // entre cartões e grupos, em vez de congelar valores que mudam a cada atualização.
  const cards = (await frame.locator(".priority-meter .priority-value").allTextContents()).map(x => x.trim());
  const groups = (await frame.locator(".priority-record-group .priority-summary-total").allTextContents()).map(x => x.trim());
  if (cards.length !== 3 || JSON.stringify(cards) !== JSON.stringify(groups)) {
    throw new Error("Cartões e grupos de prioridade não conferem: " + JSON.stringify({ cards, groups }));
  }
  const counts = await frame.locator(".priority-record-group").evaluateAll(nodes =>
    nodes.map(node => node.querySelector("summary")?.innerText || "")
  );
  const recordCounts = counts.map(label => Number((label.match(/(\d+) registros?/) || [])[1] || 0));
  if (counts.length !== 3 || recordCounts.some(value => value <= 0) || recordCounts.reduce((a, b) => a + b, 0) !== 8) {
    throw new Error("Contagens dos grupos de prioridade divergentes: " + JSON.stringify(counts));
  }

  await frame.locator('#nav button[data-x="visao"]').click();
  await frame.locator("#ordersExecutiveSummary").waitFor({ state: "visible", timeout: 20000 });
  const executive = await frame.locator("#ordersExecutiveSummary").evaluate(node => ({
    text: node.innerText.replace(/\s+/g, " ").trim(),
    categories: [...node.querySelectorAll(".ob-category")].map(card => ({
      name: card.querySelector(".ob-category-name")?.textContent.trim(),
      value: card.querySelector(".ob-category-value")?.textContent.trim(),
      percent: card.querySelector(".ob-percent")?.textContent.trim()
    })),
    total: node.querySelector(".ob-total-value")?.textContent.trim(),
    totalPercent: node.querySelector(".ob-total-meta .ob-percent")?.textContent.trim(),
    remainder: node.querySelector(".ob-remainder")?.innerText.replace(/\s+/g, " ").trim()
  }));
  // A Visão Executiva é dinâmica: o teste calcula a expectativa a partir do
  // mesmo data.json publicado, sem congelar valores de uma atualização anterior.
  const data = JSON.parse(await readFile(new URL("../../data.json", import.meta.url), "utf8"));
  const dataset = id => data.datasets.find(item => item.id === id);
  const orders = dataset("ordens_bancarias");
  const daily = dataset("diarias_pagas");
  const publications = dataset("publicacoes_pagas");
  if (!orders?.rows || !daily || !publications) {
    throw new Error("data.json não contém os conjuntos necessários à Visão Executiva.");
  }
  const cents = value => Math.round((Number(value) || 0) * 100);
  const formatMoney = value => "R$ " + new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(value / 100);
  const formatPercent = value => (value / 100).toLocaleString("pt-BR", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }) + "%";
  const totalCents = cents(orders.total);
  const bolsistasCents = orders.rows
    .filter(row => /bols/i.test(String(row.observacao || "") + " " + String(row.favorecido || "")))
    .reduce((sum, row) => sum + cents(row.valor), 0);
  const dailyCents = cents(daily.total);
  const publicationsCents = cents(publications.total);
  const categoryCents = [bolsistasCents, dailyCents, publicationsCents];
  const percentages = categoryCents.map(value => Math.round(value * 10000 / totalCents));
  const remainderCents = totalCents - categoryCents.reduce((sum, value) => sum + value, 0);
  const remainderPercent = 10000 - percentages.reduce((sum, value) => sum + value, 0);
  const expectedCategories = [
    { name: "Bolsistas Pagos", value: formatMoney(bolsistasCents), percent: formatPercent(percentages[0]) },
    { name: "Diárias Pagas", value: formatMoney(dailyCents), percent: formatPercent(percentages[1]) },
    { name: "Publicações Pagas", value: formatMoney(publicationsCents), percent: formatPercent(percentages[2]) }
  ];
  const expectedRemainder = formatMoney(remainderCents);
  if (totalCents <= 0 || remainderCents < 0 ||
      percentages.reduce((sum, value) => sum + value, 0) + remainderPercent !== 10000 ||
      executive.total !== formatMoney(totalCents) || executive.totalPercent !== "100,00%" ||
      JSON.stringify(executive.categories) !== JSON.stringify(expectedCategories) ||
      !executive.remainder.includes(formatPercent(remainderPercent)) ||
      !executive.remainder.includes(expectedRemainder)) {
    throw new Error("Nova composição da Visão Executiva divergente: " + JSON.stringify({
      executive, expectedCategories, expectedTotal: formatMoney(totalCents),
      expectedRemainder, expectedRemainderPercent: formatPercent(remainderPercent)
    }));
  }
  const remainingKpis = await frame.locator("#kpis > .kpi .label").allTextContents();
  const forbidden = remainingKpis.filter(label => /^(Publicações Pagas|Bolsistas pagos|Diárias Pagas|Ordens Bancárias)$/i.test(label.trim()));
  if (forbidden.length) throw new Error("Cartões antigos duplicados na Visão Executiva: " + JSON.stringify(forbidden));

  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(150);
    const layout = await frame.locator("body").evaluate(body => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      summaryWidth: document.querySelector("#ordersExecutiveSummary")?.getBoundingClientRect().width || 0,
      categoryWidths: [...document.querySelectorAll("#ordersExecutiveSummary .ob-category")].map(el => el.getBoundingClientRect().width)
    }));
    if (layout.scrollWidth > layout.clientWidth + 2) {
      throw new Error("Há rolagem horizontal inesperada na largura " + width + ": " + JSON.stringify(layout));
    }
    if (layout.summaryWidth <= 0 || layout.categoryWidths.length !== 3 || layout.categoryWidths.some(x => x <= 0)) {
      throw new Error("Nova composição não está visível na largura " + width + ": " + JSON.stringify(layout));
    }
  }

  if (errors.length) throw new Error("Erros JavaScript/console: " + errors.join(" | "));
  console.log(JSON.stringify({ status: "OK", priorityCards: cards, priorityGroups: groups, counts, executive, testedWidths: [1440, 390], javascriptErrors: errors.length }));
} finally {
  await browser.close();
}
