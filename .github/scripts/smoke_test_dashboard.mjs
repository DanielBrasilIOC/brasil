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
  await frame.locator('#nav button[data-x="repasses"]').waitFor({ state: "visible", timeout: 20000 });
  await frame.locator('#nav button[data-x="repasses"]').click();
  await frame.locator(".priority-meter .priority-value").nth(2).waitFor({ state: "visible", timeout: 20000 });

  const expected = ["R$ 327.839,00", "R$ 445.215,80", "R$ 42.345,80"];
  const cards = await frame.locator(".priority-meter .priority-value").allTextContents();
  const groups = await frame.locator(".priority-record-group .priority-summary-total").allTextContents();
  if (JSON.stringify(cards) !== JSON.stringify(expected)) {
    throw new Error("Valores dos cartões divergentes: " + JSON.stringify(cards));
  }
  if (JSON.stringify(groups) !== JSON.stringify(expected)) {
    throw new Error("Valores dos grupos expansíveis divergentes: " + JSON.stringify(groups));
  }
  const counts = await frame.locator(".priority-record-group").evaluateAll(nodes =>
    nodes.map(node => node.querySelector("summary")?.innerText || "")
  );
  if (!counts[0].includes("8 registros") || !counts[1].includes("5 registros") || !counts[2].includes("3 registros")) {
    throw new Error("Contagens dos grupos de prioridade divergentes: " + JSON.stringify(counts));
  }

  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(150);
    const layout = await frame.locator("body").evaluate(body => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      totals: [...document.querySelectorAll(".priority-meter .priority-value, .priority-record-group .priority-summary-total")].map(el => ({
        text: el.textContent.trim(),
        display: getComputedStyle(el).display,
        visibility: getComputedStyle(el).visibility,
        width: el.getBoundingClientRect().width
      }))
    }));
    if (layout.scrollWidth > layout.clientWidth + 2) {
      throw new Error("Há rolagem horizontal inesperada na largura " + width + ": " + JSON.stringify(layout));
    }
    if (layout.totals.length !== 6 || layout.totals.some(x => x.display === "none" || x.visibility === "hidden" || x.width <= 0)) {
      throw new Error("Valores financeiros não estão visíveis na largura " + width + ": " + JSON.stringify(layout));
    }
  }

  if (errors.length) throw new Error("Erros JavaScript/console: " + errors.join(" | "));
  console.log(JSON.stringify({ status: "OK", cards, groups, counts, testedWidths: [1440, 390], javascriptErrors: errors.length }));
} finally {
  await browser.close();
}
