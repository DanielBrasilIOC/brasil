import { chromium } from "playwright";

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
  const expectedCategories = [
    { name: "Bolsistas Pagos", value: "R$ 2.762.300,00", percent: "4,98%" },
    { name: "Diárias Pagas", value: "R$ 312.922,95", percent: "0,56%" },
    { name: "Publicações Pagas", value: "R$ 2.889.316,07", percent: "5,20%" }
  ];
  if (executive.total !== "R$ 55.521.968,15" || executive.totalPercent !== "100%" ||
      JSON.stringify(executive.categories) !== JSON.stringify(expectedCategories) ||
      !executive.remainder.includes("89,26%") || !executive.remainder.includes("R$ 49.557.429,13")) {
    throw new Error("Nova composição da Visão Executiva divergente: " + JSON.stringify(executive));
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
