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
    if (year === null || age < 0) { unknown.push(r); return; }
    const key = age > 4 ? 'high' : age > 2 ? 'medium' : 'low';
    const group = groups[key];
    group.amount += N(r.saldo);
    group.count += 1;
    group.rows.push(r);
    if (!byYear.has(year)) byYear.set(year, { year, age, amount: 0, count: 0, key });
    const summary = byYear.get(year);
    summary.amount += N(r.saldo);
    summary.count += 1;
  });
  const total = Object.values(groups).reduce((sum, group) => sum + group.amount, 0);
  const totalCount = Object.values(groups).reduce((sum, group) => sum + group.count, 0);
  const pct = amount => total > 0 ? Math.max(0, Math.min(100, amount / total * 100)) : 0;
  const moneyShare = amount => pct(amount).toLocaleString('pt-BR',{maximumFractionDigits:1,minimumFractionDigits:1});
  const columns = [
    ['empenho','Empenho'],['fornecedor','Fornecedor'],['cnpj','CNPJ'],['pi','PI'],
    ['programa','Programa'],['autor_emenda','Autor da emenda'],
    ['natureza_codigo','Código da natureza'],['natureza','Natureza da despesa'],['saldo','Saldo']
  ];
  const details = Object.entries(groups).map(([key,group]) => {
    const records = group.rows.map(r => '<tr>' + columns.map(([field]) =>
      field === 'saldo'
        ? '<td class="money">' + F(N(r[field])) + '</td>'
        : '<td title="' + E(r[field] ?? '') + '">' + (E(r[field] ?? '') || '—') + '</td>'
    ).join('') + '</tr>').join('');
    return '<section class="rap-level-detail ' + group.className + '">' +
      '<div class="rap-level-heading"><div><span class="rap-thermo-label">' + group.label + '</span><h4>' + group.description + '</h4></div>' +
      '<div class="rap-level-total"><strong>' + F(group.amount) + '</strong><span>' + I(group.count) + ' registro(s) • ' + moneyShare(group.amount) + '% do valor classificado</span></div></div>' +
      '<div class="scroll rap-records-scroll"><table><thead><tr>' + columns.map(([,label]) => '<th>' + label + '</th>').join('') + '</tr></thead><tbody>' +
      (records || '<tr><td colspan="' + columns.length + '">Nenhum registro nesta classificação.</td></tr>') +
      '</tbody></table></div></section>';
  }).join('');
  const cards = Object.values(groups).map(group => {
    const share = pct(group.amount);
    return '<article class="rap-thermo-card ' + group.className + '">' +
      '<div class="rap-thermo-card-head"><span class="rap-thermo-label">' + group.label + '</span><span class="rap-thermo-range">' + group.description + '</span></div>' +
      '<div class="rap-thermo-amount">' + F(group.amount) + '</div>' +
      '<div class="rap-thermo-count">' + I(group.count) + ' registro(s) • ' + moneyShare(group.amount) + '% do valor classificado</div>' +
      '<div class="rap-thermo-track"><span style="width:' + share.toFixed(2) + '%"></span></div>' +
    '</article>';
  }).join('');
  const segments = Object.values(groups).map(group => '<span class="' + group.className + '" style="width:' + pct(group.amount).toFixed(2) + '%" title="' + group.label + ': ' + F(group.amount) + '"></span>').join('');
  const yearRows = [...byYear.values()].sort((a,b) => b.year - a.year).map(item => {
    const group = groups[item.key];
    return '<tr><td><b>' + item.year + '</b></td><td>' + item.age + ' ano(s)</td><td><span class="rap-thermo-pill ' + group.className + '">' + group.label + '</span></td><td class="money">' + F(item.amount) + '</td><td>' + I(item.count) + '</td></tr>';
  }).join('');
  return '<section class="rap-thermometer" aria-label="Termômetro de envelhecimento dos Restos a Pagar">' +
    '<div class="head"><div><h3>Termômetro de envelhecimento dos empenhos</h3><p class="desc">Todos os registros não zerados estão apresentados abaixo, separados por nível de envelhecimento. Não há filtro nesta aba.</p></div><span class="badge">' + I(totalCount) + ' registros classificados</span></div>' +
    '<div class="rap-thermo-legend"><span><i class="rap-legend-dot rap-low"></i>Baixo: até 2 anos</span><span><i class="rap-legend-dot rap-medium"></i>Médio: mais de 2 até 4 anos</span><span><i class="rap-legend-dot rap-high"></i>Alto: mais de 4 anos</span></div>' +
    '<div class="rap-thermo-stack" role="img" aria-label="Distribuição percentual do saldo por nível de envelhecimento">' + segments + '</div>' +
    '<div class="rap-thermo-cards">' + cards + '</div>' +
    '<div class="rap-thermo-total"><span><b>Saldo total classificado</b><small>' + I(totalCount) + ' registros com ano reconhecido</small></span><strong>' + F(total) + '</strong></div>' +
    '<div class="rap-thermo-detail"><h4>Resumo por exercício</h4><div class="scroll"><table><thead><tr><th>Exercício</th><th>Idade</th><th>Nível</th><th>Saldo</th><th>Registros</th></tr></thead><tbody>' + (yearRows || '<tr><td colspan="5">Nenhum ano de empenho foi identificado na base publicada.</td></tr>') + '</tbody></table></div></div>' +
    '<div class="rap-levels"><h3>Detalhamento completo por classificação</h3>' + details + '</div>' +
    (unknown.length ? '<div class="alert w"><b>' + I(unknown.length) + ' registro(s) sem classificação automática.</b> Ano do empenho ausente ou posterior ao exercício atual; confira o número do empenho na origem.</div>' : '') +
    '<p class="rap-thermo-note">Os registros são agrupados pelo ano identificado no número do empenho, usando 2026 como ano de referência da classificação desta base. Empenhos do exercício atual ficam em Baixo para não deixar registros recentes sem nível.</p>' +
  '</section>';
}
