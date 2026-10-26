#!/usr/bin/env python3
"""Testes de resolução das fontes CSV do Drive."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("discover_drive_sources",ROOT/".github/scripts/discover_drive_sources.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
folder="folder-test"
files=[
 {"id":"id-e","name":"Saldo nos empenhos 2026.csv","mimeType":"text/csv","parents":[folder]},
 {"id":"id-o","name":"Saldo Orçamentário.csv","mimeType":"text/csv","parents":[folder]},
 {"id":"id-ob","name":"ORDEM BANCARIAS EMITIDAS.csv","mimeType":"text/csv","parents":[folder]},
 {"id":"id-r","name":"Aguardando Repasse Orçamentário.csv","mimeType":"text/csv","parents":[folder]},
 {"id":"id-f","name":"Saldo Financeiro.csv","mimeType":"text/csv","parents":[folder]},
 {"id":"id-rap","name":"Restos a Pagar.csv","mimeType":"text/csv","parents":[folder]},
]
expected={"empenhos":"id-e","orcamentario":"id-o","ordens_bancarias":"id-ob","repasses":"id-r","financeiro":"id-f","restos":"id-rap"}
assert mod.select_sources(files,folder)==expected
replacement=[dict(x,id="novo-"+x["id"]) for x in files]
assert mod.select_sources(replacement,folder)=={k:"novo-"+v for k,v in expected.items()}
try: mod.select_sources(files+[dict(files[0],id="duplicate")],folder)
except ValueError as exc: assert "encontrados 2" in str(exc)
else: raise AssertionError("Nome duplicado deveria bloquear publicação")
noise=files+[dict(files[0],id="outside",parents=["other"]),dict(files[1],id="sheet",mimeType="application/vnd.google-apps.spreadsheet")]
assert mod.select_sources(noise,folder)==expected
print("Testes de descoberta automática do Drive: OK")
