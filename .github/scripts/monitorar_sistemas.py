#!/usr/bin/env python3
"""Coleta HTTP de portais governamentais. Não testa operações autenticadas."""
import json,time,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
TARGETS=[
 {"id":"siafi","name":"SIAFI","url":"https://siafi.tesouro.gov.br/","scope":"Portal público; operações internas exigem autenticação."},
 {"id":"contratos","name":"Contratos.gov.br","url":"https://contratos.gov.br/","scope":"Portal; módulos autenticados não são testados."},
 {"id":"compras","name":"Compras.gov.br","url":"https://www.gov.br/compras/pt-br","scope":"Portal público; autenticação e disputa não são testadas."},
 {"id":"sicaf","name":"SICAF","url":"https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/sicaf-digital","scope":"Página informativa; operações autenticadas não são testadas."},
 {"id":"pncp","name":"PNCP","url":"https://www.gov.br/pncp/pt-br","scope":"Portal público; APIs específicas exigem testes próprios."},
 {"id":"transferegov","name":"Transferegov.br","url":"https://transferegov.sistema.gov.br/","scope":"Portal; módulos autenticados não são testados."}]
def probe(x):
 t=time.monotonic(); req=urllib.request.Request(x["url"],headers={"User-Agent":"IOC-Dashboard-Monitor/1.0"})
 try:
  with urllib.request.urlopen(req,timeout=12) as r:
   code=r.status; state="ACESSIVEL" if 200<=code<400 else "INSTABILIDADE"; detail="Portal respondeu; funcionalidades internas não verificadas."
 except urllib.error.HTTPError as e:
  code=e.code; state="ACESSO_RESTRITO" if code in (401,403) else ("INSTABILIDADE" if code==429 or code>=500 else "RESPOSTA_INCONCLUSIVA"); detail="Resposta HTTP; não comprova funcionamento de operações internas."
 except Exception as e:
  code=None; state="NAO_VERIFICADO"; detail=type(e).__name__+": "+str(e)[:180]
 return {**x,"status":state,"http_status":code,"latency_ms":round((time.monotonic()-t)*1000),"detail":detail}
data={"environment":"TESTE","checked_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),"collector":"monitorar_sistemas.py","frequency_target_seconds":60,"schedule_target":"Segunda a sexta-feira","disclaimer":"Resposta do portal público não confirma login, transações ou módulos internos protegidos.","systems":[probe(x) for x in TARGETS]}
Path("monitoramento-sistemas.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(data,ensure_ascii=False))
