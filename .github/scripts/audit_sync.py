#!/usr/bin/env python3
"""Executa a sincronização do dashboard e registra uma trilha de auditoria CSV."""
import csv
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / ".github" / "scripts" / "sync_sources.py"
STATE = ROOT / "source_state.json"
DATA = ROOT / "data.json"
LOG = ROOT / "logs" / "atualizacoes_dashboard.csv"
SOURCES = {
    "empenhos": "137jwUw2WB_LUvnQef6waE8ASKQEvzhup",
    "orcamentario": "1k3dZ890WgqGVSCZLwCxGPLikMutTlOfN",
    "ordens_bancarias": "1lRYujrJRv7ZPam-lYVB2CxCg_WEMbraC",
    "repasses": "1ghcBkPmT-IkfWozLZVDdMvMe7eoD2J6k",
    "financeiro": "1p4PyHEkV5YzIljLeMsHopulzN55yQMqzS6fk56STdEk",
    "restos": "1zzxhemDKryzolkykFSw3JXph1YcQ2pUj",
}
LABELS = {
    "empenhos": "Empenhos", "orcamentario": "Orçamentário",
    "ordens_bancarias": "Ordens Bancárias", "repasses": "Repasses",
    "financeiro": "Financeiro", "restos": "Restos a Pagar",
}
FIELDS = ["timestamp_utc", "run_id", "evento", "resultado_execucao", "fonte", "fonte_id",
          "conteudo_alterado", "registros", "total", "dashboard_atualizado", "publicacao", "mensagem"]

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def old_hashes():
    state = read_json(STATE, {})
    return state.get("hashes", {}) if isinstance(state, dict) else {}

def run_sync():
    proc = subprocess.run(["python", str(SYNC)], cwd=ROOT, env=os.environ.copy(), text=True, capture_output=True)
    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip()
    parsed = {}
    for line in reversed(output.splitlines()):
        try:
            candidate = json.loads(line)
            if isinstance(candidate, dict) and "status" in candidate:
                parsed = candidate
                break
        except Exception:
            pass
    return proc.returncode, parsed, output, error

def source_details(data, name):
    datasets = {d.get("id"): d for d in data.get("datasets", [])}
    d = datasets.get(name, {})
    rows = d.get("rows", [])
    return (len(rows) if isinstance(rows, list) else 0), d.get("total", "")

def append_rows(rows):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    exists = LOG.exists() and LOG.stat().st_size > 0
    with LOG.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)

def output_values(changed, sync_ok):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        out.write("changed=" + ("true" if changed else "false") + "\n")
        out.write("sync_ok=" + ("true" if sync_ok else "false") + "\n")

def main():
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    run_id = os.getenv("GITHUB_RUN_ID", "manual")
    event = os.getenv("GITHUB_EVENT_NAME", "manual")
    before = old_hashes()
    code, result, stdout, stderr = run_sync()
    after = old_hashes()
    data = read_json(DATA, {})
    sync_ok = code == 0 and result.get("status") in {"SEM_ALTERACOES", "ATUALIZADO"}
    changed = bool(result.get("changed")) if sync_ok else False
    changed_sources = [k for k, v in after.items() if v != before.get(k)]

    if sync_ok:
        execution = result.get("status", "OK")
        message = result.get("mensagem", "Sincronização concluída.")
        dashboard_updated = "SIM" if changed else "NÃO"
        publication = "PUBLICAÇÃO PROGRAMADA" if changed else "NÃO NECESSÁRIA"
    else:
        execution = "FALHA"
        message = (stderr or stdout or "Falha sem mensagem registrada.").replace("\n", " ")[-1000:]
        dashboard_updated = "NÃO"
        publication = "NÃO PUBLICADO"

    rows = []
    for name, file_id in SOURCES.items():
        count, total = source_details(data, name)
        rows.append({
            "timestamp_utc": timestamp, "run_id": run_id, "evento": event,
            "resultado_execucao": execution, "fonte": LABELS[name], "fonte_id": file_id,
            "conteudo_alterado": "SIM" if name in changed_sources else "NÃO",
            "registros": count, "total": total, "dashboard_atualizado": dashboard_updated,
            "publicacao": publication, "mensagem": message,
        })
    rows.append({
        "timestamp_utc": timestamp, "run_id": run_id, "evento": event,
        "resultado_execucao": execution, "fonte": "RESUMO DA EXECUÇÃO", "fonte_id": "",
        "conteudo_alterado": "SIM" if changed_sources else "NÃO",
        "registros": sum(source_details(data, n)[0] for n in SOURCES), "total": "",
        "dashboard_atualizado": dashboard_updated, "publicacao": publication,
        "mensagem": f"Fontes alteradas: {', '.join(changed_sources) if changed_sources else 'nenhuma'}. Status: {execution}.",
    })
    append_rows(rows)
    output_values(changed, sync_ok)
    print(json.dumps({"audit": "REGISTRADA", "status": execution, "changed": changed,
                      "sync_ok": sync_ok, "fontes_alteradas": changed_sources,
                      "log": str(LOG.relative_to(ROOT))}, ensure_ascii=False))
    # A falha fica registrada e não deve permitir publicação de dados possivelmente desatualizados.
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
