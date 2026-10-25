/*
 * Termômetro de envelhecimento dos Restos a Pagar (RAP).
 * Classifica pelo exercício extraído do campo Empenho, antes de "NE".
 * Baixo: até 2 anos (inclui o exercício atual); Médio: >2 até 4; Alto: >4.
 */
function renderRapThermometer(d) {
  const currentYear = new Date().getFullYear();
  const getYear = r => {
    const text = String(r.empenho ?? r.numero_ne ?? r.ne ?? '');
    const match = text.match(/((?:19|20)\d{2})(?=\s*NE)/i);
    if (match) return Number(match[1]);
    for (const key of ['ano','ano_rap','exercicio','exercicio_rap','year']) {
      const found = String(r[key] ?? '').match(/(?:19|20)\d{2}/);
      if (found) return Number(found[0]);
    }
    return null;
  };
  const groups = {
    low: { label: 'BAIXO', description: 'Até 2 anos', className: 'rap-low', amount: 0, count: 0, rows: [] },
    medium: { label: 'MÉDIO', description: 'Mais de 2 até 4 anos', className: 'rap-medium', amount: 0, count: 0, rows: [] },
    high: { label: 'ALTO', description: 'Mais de 4 anos', className: 'rap-high', amount: 0, count: 0, rows: [] }
  };
  const byYear = new Map();
  const unknown = [];
  (d.rows || []).forEach(r => {
    const year = getYear(r);
    const age = year === null ? null : currentYear - year;
    if (year === null || age < 0) {
      unknown.push(r);
      return;
    }
    const key = age > 4 ? 'high' : age > 2 ? 'medium' : 'low';
    const group = groups[key];
    const amount = N(r.saldo);
    group.amount += amount;
    group.count += 1;
    group.rows.push(r);
    if (!byYear.has(year)) byYear.set(year, { year, age, amount: 0, count: 0, key });
    const summary = byYear.get(year);
    summary.amount += amount;
    summary.count += 1;
  });
  const total = Object.values(groups).reduce((sum, group) => sum + group.amount, 0);
  const totalCount = Object.values(groups).reduce((sum, group) => sum + group.count, 0);
  const pct = amount => total > 0 ? Math.max(0, Math.min(100, amount / total * 100)) : 0;
  const cards = Object.values(groups).map(group => {
    const share = pct(group.amount);
    return '<article class="rap-thermo-card ' + group.className + '">' +
      '<div class="rap-thermo-card-head"><span class="rap-thermo-label">' + group.label + '</span><span class="rap-thermo-range">' + group.description + '</span></div>' +
      '<div class="rap-thermo-amount">' + F(group.amount) + '</div>' +
      '<div class="rap-thermo-count">' + I(group.count) + ' registro(s) • ' + share.toLocaleString('pt-BR',{maximumFractionDigits:1,minimumFractionDigits:1}) + '% do valor classificado</div>' +
      '<div class="rap-thermo-track"><span style="width:' + share.toFixed(2) + '%"></span></div>' +
    '</article>';
  }).join('');
  const segments = Object.values(groups).map(group => '<span class="' + group.className + '" style="width:' + pct(group.amount).toFixed(2) + '%" title="' + group.label + ': ' + F(group.amount) + '"></span>').join('');
  const yearRows = [...byYear.values()].sort((a,b) => b.year - a.year).map(item => {
    const group = groups[item.key];
    return '<tr><td><b>' + item.year + '</b></td><td>' + item.age + ' ano(s)</td><td><span class="rap-thermo-pill ' + group.className + '">' + group.label + '</span></td><td class="money">' + F(item.amount) + '</td><td>' + I(item.count) + '</td></tr>';
  }).join('');
  return '<section class="rap-thermometer" aria-label="Termômetro de envelhecimento dos Restos a Pagar">' +
    '<div class="head"><div><h3>Termômetro de envelhecimento dos empenhos</h3><p class="desc">Classificação automática pelo ano identificado no número do empenho. Valores calculados pela soma do saldo dos registros de Restos a Pagar.</p></div><span class="badge">' + I(totalCount) + ' registros classificados</span></div>' +
    '<div class="rap-thermo-legend"><span><i class="rap-legend-dot rap-low"></i>Baixo: 1 a 2 anos</span><span><i class="rap-legend-dot rap-medium"></i>Médio: mais de 2 até 4 anos</span><span><i class="rap-legend-dot rap-high"></i>Alto: mais de 4 anos</span></div>' +
    '<div class="rap-thermo-stack" role="img" aria-label="Distribuição percentual do saldo por nível de envelhecimento">' + segments + '</div>' +
    '<div class="rap-thermo-cards">' + cards + '</div>' +
    '<div class="rap-thermo-total"><span><b>Saldo total classificado</b><small>' + I(totalCount) + ' registros com ano reconhecido</small></span><strong>' + F(total) + '</strong></div>' +
    '<div class="rap-thermo-detail"><h4>Detalhamento por exercício</h4><div class="scroll"><table><thead><tr><th>Exercício</th><th>Idade</th><th>Nível</th><th>Saldo</th><th>Registros</th></tr></thead><tbody>' + (yearRows || '<tr><td colspan="5">Nenhum ano de empenho foi identificado na base publicada.</td></tr>') + '</tbody></table></div></div>' +
    (unknown.length ? '<div class="alert w"><b>' + I(unknown.length) + ' registro(s) sem classificação automática.</b> Ano do empenho ausente ou posterior ao exercício atual; não foram incluídos nos níveis de risco. Confira o número do empenho na origem.</div>' : '') +
    '<p class="rap-thermo-note">Observação: empenhos do exercício atual (idade inferior a 1 ano) são mantidos em Baixo para que nenhum registro recente fique sem nível. Os limites de Médio e Alto seguem exatamente as faixas definidas.</p>' +
  '</section>';
}
