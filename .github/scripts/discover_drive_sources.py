#!/usr/bin/env python3
"""Descobre os seis CSVs oficiais do dashboard pelo nome dentro da pasta do Drive."""
import json, os, re, sys, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".drive_source_ids.json"
FOLDER_DEFAULT = "1Ae3_31uGRNvfvnN5euhiNHbk_mdkVg0L"
STATIC_IDS = {
 "empenhos":"1pDEGc2LAz0fe7c4GH5fh-kzgeW0iuQHh",
 "orcamentario":"1gQYnGiF2zLdCOR-iiW5ptNc-3fXdNuMy",
 "ordens_bancarias":"1dTM5GfqVD63wNf2QYhOydEDd6g1Ca8rU",
 "repasses":"1h7oF_blPx6RpuHsCjPshW-zn7IcNHGB-",
 "financeiro":"10ghNRMaUWvaOcX3q8luLTn9CZ2_z4RSQ",
 "restos":"1CIAIW9t9cKAnu-iUlQJpGUx_sfalHyuu",
}
EXPECTED_NAMES = {
 "empenhos":("Saldo nos empenhos 2026.csv",),
 "orcamentario":("Saldo Orçamentário.csv",),
 "ordens_bancarias":("ORDEM BANCARIAS EMITIDAS.csv",),
 "repasses":("Aguardando Repasse Orçamentário.csv",),
 "financeiro":("Saldo Financeiro.csv",),
 "restos":("Restos a Pagar.csv",),
}
def normalize(value):
 text=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().lower()
 return re.sub(r"[^a-z0-9]+","",text)
def select_sources(files,folder_id):
 selected={}; errors=[]
 for key,aliases in EXPECTED_NAMES.items():
  accepted={normalize(x) for x in aliases}
  matches=[x for x in files if x.get("id") and normalize(x.get("name")) in accepted
    and folder_id in (x.get("parents") or []) and x.get("mimeType")=="text/csv"
    and not x.get("trashed",False)]
  if len(matches)!=1: errors.append(f"{key}: esperado 1 CSV com nome {aliases!r} na pasta, encontrados {len(matches)}")
  else: selected[key]=matches[0]["id"]
 if errors: raise ValueError("Descoberta automática bloqueada: "+"; ".join(errors))
 if len(set(selected.values()))!=len(STATIC_IDS): raise ValueError("Descoberta automática bloqueada: duas fontes apontam para o mesmo ID")
 return selected
def list_drive_files(folder_id):
 secret=os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON","").strip()
 if not secret: return None
 try:
  from google.oauth2 import service_account
  from google.auth.transport.requests import AuthorizedSession
 except ImportError as exc: raise RuntimeError("Dependência google-auth ausente") from exc
 try:
  info=json.loads(secret)
  credentials=service_account.Credentials.from_service_account_info(info,scopes=["https://www.googleapis.com/auth/drive.readonly"])
 except Exception as exc: raise RuntimeError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON não contém credencial de conta de serviço válida") from exc
 session=AuthorizedSession(credentials); url="https://www.googleapis.com/drive/v3/files"
 query=f"'{folder_id}' in parents and trashed = false"; files=[]; token=None
 while True:
  params={"q":query,"pageSize":1000,"orderBy":"name","fields":"nextPageToken,files(id,name,mimeType,parents,modifiedTime,trashed)","supportsAllDrives":"true","includeItemsFromAllDrives":"true"}
  if token: params["pageToken"]=token
  response=session.get(url,params=params,timeout=45)
  if response.status_code!=200:
   raise RuntimeError(f"Falha ao listar pasta do Drive (HTTP {response.status_code}); confirme compartilhamento com a conta de serviço")
  body=response.json(); files.extend(body.get("files",[])); token=body.get("nextPageToken")
  if not token: break
 return files
def discover_source_ids():
 if CACHE.exists():
  cached=json.loads(CACHE.read_text(encoding="utf-8"))
  if set(cached)==set(STATIC_IDS) and all(isinstance(v,str) and v for v in cached.values()): return cached
  raise RuntimeError("Cache de descoberta de fontes incompleto ou inválido")
 folder=os.environ.get("GOOGLE_DRIVE_FOLDER_ID",FOLDER_DEFAULT)
 files=list_drive_files(folder)
 return dict(STATIC_IDS) if files is None else select_sources(files,folder)
def main():
 folder=os.environ.get("GOOGLE_DRIVE_FOLDER_ID",FOLDER_DEFAULT); files=list_drive_files(folder)
 if files is None:
  ids=dict(STATIC_IDS); status="FALLBACK_IDS_FIXOS"
  message="Segredo GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON ausente; IDs conhecidos mantidos temporariamente. Configure o segredo e compartilhe a pasta com a conta de serviço para ativar a descoberta automática."
 else:
  ids=select_sources(files,folder); status="DESCOBERTA_AUTOMATICA_OK"
  message="Seis arquivos CSV identificados por nome na pasta oficial do Drive."
 CACHE.write_text(json.dumps(ids,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 summary=os.environ.get("GITHUB_STEP_SUMMARY")
 if summary:
  with open(summary,"a",encoding="utf-8") as out: out.write(f"## Descoberta de fontes do Drive\n\n- **Status:** {status}\n- **Fontes:** {len(ids)}/6\n- {message}\n")
 print(json.dumps({"status":status,"fontes":len(ids),"mensagem":message,"ids":ids},ensure_ascii=False))
 return 0
if __name__=="__main__":
 try: raise SystemExit(main())
 except Exception as exc:
  print(f"ERRO NA DESCOBERTA DE FONTES: {exc}",file=sys.stderr); raise SystemExit(1)
