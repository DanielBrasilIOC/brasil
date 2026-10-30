(()=>{'use strict';const d=document;if(d.getElementById('iocGovMonitorButton'))return;
const css=`
#iocGovMonitorButton{background:#ffffff12!important;color:#fff!important;border:1px solid #ffffff20!important}
#iocGovMonitorOverlay{position:fixed;inset:0;z-index:99999;background:#f4f7fa;overflow:auto;padding:clamp(14px,3vw,32px);font:14px/1.5 Inter,system-ui,Arial;color:#243746}
#iocGovMonitorOverlay .gm-wrap{max-width:1240px;margin:auto}
#iocGovMonitorOverlay .gm-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
#iocGovMonitorOverlay h2{margin:0;color:#153b57;font-size:clamp(22px,3vw,30px)}
#iocGovMonitorOverlay .gm-muted{color:#667b89;font-size:12px}
#iocGovMonitorOverlay .gm-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:14px 0}
#iocGovMonitorOverlay .gm-summary>div,#iocGovMonitorOverlay .gm-card,#iocGovMonitorOverlay .gm-section{background:#fff;border:1px solid #e0e8ee;border-radius:13px;padding:14px}
#iocGovMonitorOverlay .gm-label{color:#667b89;font-size:10px;text-transform:uppercase;letter-spacing:.06em;font-weight:800}
#iocGovMonitorOverlay .gm-value{color:#153b57;font-weight:800;margin-top:4px;overflow-wrap:anywhere}
#iocGovMonitorOverlay .gm-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px;margin:14px 0}
#iocGovMonitorOverlay .gm-name{font-weight:800;color:#153b57;font-size:15px}
#iocGovMonitorOverlay .gm-status{display:inline-block;border-radius:99px;padding:4px 9px;font-size:10px;font-weight:800;background:#eef2f5;color:#5b6b77}
#iocGovMonitorOverlay .gm-status.ok{background:#e6f3ec;color:#28745b}
#iocGovMonitorOverlay .gm-status.warn{background:#fff3df;color:#956313}
#iocGovMonitorOverlay .gm-status.bad{background:#fdeaea;color:#a33d3d}
#iocGovMonitorOverlay .gm-card p{margin:8px 0 0;color:#667b89;font-size:12px}
#iocGovMonitorOverlay .gm-btn{border:1px solid #d7e2e9;border-radius:9px;background:#fff;padding:9px 13px;color:#244b64;font-weight:700}
#iocGovMonitorOverlay .gm-notice{background:#fff;border:1px solid #dce6ec;border-left:4px solid #b18436;padding:12px;border-radius:10px;margin:12px 0;color:#526777}
#iocGovMonitorOverlay .gm-section{margin:12px 0}
#iocGovMonitorOverlay .gm-section h3{margin:0 0 10px;color:#153b57;font-size:14px}
#iocGovMonitorOverlay .gm-links{margin:8px 0 0;padding-left:17px;font-size:11px}
#iocGovMonitorOverlay .gm-links a{color:#24617e;overflow-wrap:anywhere}
#iocGovMonitorOverlay .gm-table-wrap{overflow:auto}
#iocGovMonitorOverlay table{width:100%;border-collapse:collapse;font-size:11px}
#iocGovMonitorOverlay th,#iocGovMonitorOverlay td{text-align:left;padding:8px;border-bottom:1px solid #edf1f4;white-space:nowrap}
#iocGovMonitorOverlay th{color:#667b89;background:#f7fafb}
#iocGovMonitorOverlay .gm-empty{color:#667b89;font-size:12px;padding:8px 0}
@media(max-width:600px){#iocGovMonitorOverlay .gm-grid{grid-template-columns:1fr}#iocGovMonitorOverlay .gm-summary{grid-template-columns:1fr 1fr}}
`;
const st=d.createElement('style');st.textContent=css;d.head.appendChild(st);
const nav=d.getElementById('nav')||d.querySelector('.nav'),b=d.createElement('button');b.id='iocGovMonitorButton';b.type='button';b.textContent='Monitoramento de Sistemas';if(nav)nav.appendChild(b);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=s=>s?new Date(s).toLocaleString('pt-BR'):'—';
const statusInfo=s=>({ACESSIVEL:['Endpoint acessível','ok'],INSTABILIDADE:['Instabilidade detectada','bad'],ACESSO_RESTRITO:['Acesso restrito','warn'],RESPOSTA_INCONCLUSIVA:['Resposta inconclusiva','warn'],NAO_VERIFICADO:['Não foi possível verificar','warn'],PENDENTE:['Aguardando coleta','']})[s]||['Sem classificação',''];
const opInfo=s=>({COMUNICADO_OPERACIONAL_LOCALIZADO:['Comunicado localizado','warn'],SEM_COMUNICADO_IDENTIFICADO:['Nenhum aviso identificado','ok'],CALENDARIO_OFICIAL_ACESSIVEL:['Calendário oficial consultado','ok'],FONTE_INDISPONIVEL:['Fonte oficial indisponível','bad']})[s]||['Não consultado',''];
let overlay=null,timer=null;
const close=()=>{if(timer)clearInterval(timer);timer=null;if(overlay)overlay.remove();overlay=null};
const render=async()=>{
 const target=overlay&&overlay.querySelector('[data-gm-content]');if(!target)return;
 try{
  const r=await fetch('./monitoramento-sistemas.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
  const data=await r.json(),systems=Array.isArray(data.systems)?data.systems:[];
  const scheduler=data.scheduler_status==='AGENDADOR_NAO_CONFIGURADO'?'Agendamento automático ainda não ativado':(data.scheduler_status||'Não informado');
  const summary='<div class="gm-summary"><div><div class="gm-label">Última coleta registrada</div><div class="gm-value">'+esc(fmt(data.checked_at))+'</div></div><div><div class="gm-label">Agendamento</div><div class="gm-value">'+esc(scheduler)+'</div></div><div><div class="gm-label">Frequência pretendida</div><div class="gm-value">30 minutos · dias úteis</div></div><div><div class="gm-label">Duração da coleta</div><div class="gm-value">'+esc(data.last_run_duration_ms==null?'—':data.last_run_duration_ms+' ms')+'</div></div></div>';
  const cards=systems.map(s=>{const q=statusInfo(s.status),op=opInfo(s.operational&&s.operational.status),notices=s.operational&&Array.isArray(s.operational.notices)?s.operational.notices:[];return '<article class="gm-card"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><div class="gm-name">'+esc(s.name)+'</div><span class="gm-status '+q[1]+'">'+q[0]+'</span></div><p>HTTP: '+esc(s.http_status??'—')+' · Latência: '+esc(s.latency_ms??'—')+' ms · Falhas consecutivas: '+esc(s.failure_streak??0)+'</p><p>'+esc(s.detail||s.scope||'')+'</p><p><b>Comunicados:</b> <span class="gm-status '+op[1]+'">'+op[0]+'</span></p><p>'+esc(s.operational&&s.operational.detail||'')+'</p>'+(notices.length?'<ul class="gm-links">'+notices.map(n=>'<li><a href="'+esc(n.url)+'" target="_blank" rel="noopener noreferrer">'+esc(n.title)+'</a></li>').join('')+'</ul>':'')+(s.operational&&s.operational.source_url?'<p><a href="'+esc(s.operational.source_url)+'" target="_blank" rel="noopener noreferrer">Abrir fonte oficial consultada</a></p>':'')+'</article>'}).join('');
  const alerts=(data.alerts||[]).slice(-8).reverse();
  const alertHtml='<section class="gm-section"><h3>Alertas e recuperações</h3>'+(alerts.length?'<ul class="gm-links">'+alerts.map(a=>'<li><b>'+esc(fmt(a.created_at))+'</b> — '+esc(a.message)+' <span class="gm-muted">('+esc(a.delivery||'')+')</span></li>').join('')+'</ul>':'<div class="gm-empty">Nenhum alerta registrado.</div>')+'</section>';
  const history=(data.history||[]).slice(-10).reverse();
  const historyHtml='<section class="gm-section"><h3>Histórico das coletas</h3>'+(history.length?'<div class="gm-table-wrap"><table><thead><tr><th>Data/hora</th><th>Duração</th><th>Acessíveis</th><th>Instabilidade</th><th>Não verificados</th></tr></thead><tbody>'+history.map(h=>'<tr><td>'+esc(fmt(h.checked_at))+'</td><td>'+esc(h.duration_ms??'—')+' ms</td><td>'+esc(h.accessible??0)+'</td><td>'+esc(h.instability??0)+'</td><td>'+esc(h.not_verified??0)+'</td></tr>').join('')+'</tbody></table></div>':'<div class="gm-empty">Nenhuma coleta foi gravada.</div>')+'</section>';
  target.innerHTML=summary+'<div class="gm-grid">'+cards+'</div>'+alertHtml+historyHtml+'<div class="gm-notice">'+esc(data.disclaimer||'Acessibilidade do portal não comprova funcionamento de módulos autenticados.')+'</div><div class="gm-muted">A tela atualiza a leitura do arquivo a cada 60 segundos. Isso não executa uma nova coleta. O coletor só roda quando um agendador externo autorizado o aciona.</div>';
 }catch(e){target.innerHTML='<div class="gm-notice">Não foi possível ler o arquivo de monitoramento. '+esc(e.message)+' O painel não presumirá que os sistemas estão operacionais.</div>'}
};
const open=()=>{overlay=d.createElement('section');overlay.id='iocGovMonitorOverlay';overlay.innerHTML='<div class="gm-wrap"><div class="gm-head"><div><div class="gm-muted">PAINEL FINANCEIRO E ORÇAMENTÁRIO IOC · TESTE</div><h2>Monitoramento de Sistemas Governamentais</h2><div class="gm-muted">Verificação técnica de endpoints públicos e leitura de fontes oficiais</div></div><button class="gm-btn" type="button" data-gm-close>Voltar ao dashboard</button></div><div data-gm-content><div class="gm-notice">Carregando dados registrados...</div></div></div>';d.body.appendChild(overlay);overlay.querySelector('[data-gm-close]').addEventListener('click',close);render();timer=setInterval(render,60000)};
b.addEventListener('click',open);
})();