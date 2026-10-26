#!/usr/bin/env python3
"""Executa a sincronização e audita registros, quantidades e valores das seis fontes."""
import csv, hashlib, json, os, subprocess
from collections import Counter
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
    "financeiro": "1p4PyHEK5V5YzIljLeMsHopulzN55yQMqzS6fk56STdEk",
    "restos": "1zzxhemDKryzolkykFSw3JXph1YcQ2pUj",
}
LABELS = {"empenhos":"Empenhos","orcamentario":"Orçamentário","ordens_bancarias":"Ordens Bancárias","repasses":"Repasses","financeiro":"Financeiro","restos":"Restos a Pagar"}
FIELDS = ["timestamp_utc","run_id","evento","resultado_execucao","fonte","fonte_id","conteudo_alterado","registros","total","registros_adicionados","registros_removidos","registros_alterados","valores_alterados","dashboard_atualizado","publicacao","mensagem"]

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def snapshot(data):
    out={}
    for d in data.get("datasets",[]) if isinstance(data,dict) else []:
        name=d.get("id"); rows=d.get("rows",[])
        if name not in SOURCES or not isinstance(rows,list): continue
        out[name]=[hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":" )).encode("utf-8")).hexdigest() for r in rows]
    return out

def row_diff(before, after):
    """Compara cada registro por conteúdo e preserva corretamente duplicidades."""
    result={}
    for name in SOURCES:
        cb, ca = Counter(before.get(name,[])), Counter(after.get(name,[]))
        added=sum((ca-cb).values()); removed=sum((cb-ca).values())
        result[name]={"added":added,"removed":removed,"altered":min(added,removed),"value_changed":bool(added or removed)}
    return result

def source_details(data,name):
    ds={d.get("id"):d for d in data.get("datasets",[])}
    d=ds.get(name,{})
    rows=d.get("rows",[])
    return (len(rows) if isinstance(rows,list) else 0,d.get("total",""))

def row_fingerprint(rows):
    hashes = sorted(hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest() for r in rows)
    return hashlib.sha256("\\n".join(hashes).encode("utf-8")).hexdigest()

def reconcile_source_rows(data, source_report):
    """Confere o conteúdo integral, quantidade e total de cada fonte contra o dashboard."""
    ds={d.get("id"):d for d in data.get("datasets",[])}
    value_fields={"ordens_bancarias":"valor"}
    failures={}
    for name in SOURCES:
        d=ds.get(name,{})
        rows=d.get("rows",[])
        source=source_report.get(name,{})
        problems=[]
        if not isinstance(rows,list):
            rows=[]; problems.append("linhas do dashboard inválidas")
        if len(rows) != source.get("registros"):
            problems.append(f"quantidade dashboard={len(rows)} vs fonte={source.get('registros')}")
        if row_fingerprint(rows) != source.get("rows_hash"):
            problems.append("conteúdo dos registros diverge da fonte original")
        field=value_fields.get(name,"saldo")
        try:
            total=round(sum(float(r.get(field) or 0) for r in rows),2)
            if abs(total-float(source.get("total"))) >= 0.005:
                problems.append(f"total recalculado dashboard={total:.2f} vs fonte={float(source.get('total')):.2f}")
            if abs(float(d.get("total"))-float(source.get("total"))) >= 0.005:
                problems.append(f"total publicado={d.get('total')} vs fonte={source.get('total')}")
        except (TypeError, ValueError):
            problems.append("total não pôde ser recalculado")
        if problems: failures[name]=problems
    return failures

def run_sync():
    p=subprocess.run(["python",str(SYNC)],cwd=ROOT,env=os.environ.copy(),text=True,capture_output=True)
    out=(p.stdout or "").strip(); err=(p.stderr or "").strip(); parsed={}
    for line in reversed(out.splitlines()):
        try:
            x=json.loads(line)
            if isinstance(x,dict) and "status" in x: parsed=x; break
        except Exception: pass
    return p.returncode,parsed,out,err

def append_rows(rows):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    existing=[]
    if LOG.exists() and LOG.stat().st_size:
        with LOG.open("r",encoding="utf-8-sig",newline="") as f: raw=list(csv.reader(f,delimiter=";"))
        if raw:
            old_header=raw[0]
            for r in raw[1:]:
                item=dict(zip(old_header,r))
                existing.append({k:item.get(k,"") for k in FIELDS})
    with LOG.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,delimiter=";"); w.writeheader(); w.writerows(existing); w.writerows(rows)

def output_values(changed,sync_ok):
    path=os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path,"a",encoding="utf-8") as o:
            o.write(f"changed={'true' if changed else 'false'}\n")
            o.write(f"sync_ok={'true' if sync_ok else 'false'}\n")

def main():
    ts=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    run_id=os.getenv("GITHUB_RUN_ID","manual"); event=os.getenv("GITHUB_EVENT_NAME","manual")
    before_data=read_json(DATA,{})
    before_snapshot=snapshot(before_data)
    before_totals={n:source_details(before_data,n) for n in SOURCES}
    before_state=read_json(STATE,{})
    before_hashes=before_state.get("hashes",{}) if isinstance(before_state,dict) else {}

    code,result,stdout,stderr=run_sync()
    after_data=read_json(DATA,{})
    after_snapshot=snapshot(after_data)
    after_totals={n:source_details(after_data,n) for n in SOURCES}
    after_state=read_json(STATE,{})
    after_hashes=after_state.get("hashes",{}) if isinstance(after_state,dict) else {}
    sync_ok=code==0 and result.get("status") in {"SEM_ALTERACOES","ATUALIZADO"}
    source_report=result.get("fontes",{}) if isinstance(result,dict) else {}
    reconciliation=reconcile_source_rows(after_data,source_report) if sync_ok and len(source_report)==len(SOURCES) else {
        n:["métricas completas das seis fontes não foram retornadas"] for n in SOURCES
    }
    if reconciliation:
        sync_ok=False
        stderr=(stderr+"; " if stderr else "")+"Falha na reconciliação fonte/dashboard: "+json.dumps(reconciliation,ensure_ascii=False)

    hash_changed=[n for n in SOURCES if before_hashes.get(n)!=after_hashes.get(n)]
    diffs=row_diff(before_snapshot,after_snapshot) if sync_ok else {n:{"added":0,"removed":0,"altered":0,"value_changed":False} for n in SOURCES}
    count_changed=[n for n in SOURCES if before_totals[n][0]!=after_totals[n][0]]
    total_changed=[n for n in SOURCES if str(before_totals[n][1])!=str(after_totals[n][1])]
    record_changed=[n for n in SOURCES if diffs[n]["added"] or diffs[n]["removed"]]
    changed=bool(hash_changed or count_changed or total_changed or record_changed)

    if sync_ok:
        execution=result.get("status","OK")
        dashboard_updated="SIM" if changed else "NÃO"
        publication="PUBLICAÇÃO PROGRAMADA" if changed else "NÃO NECESSÁRIA"
    else:
        execution="FALHA"; dashboard_updated="NÃO"; publication="NÃO PUBLICADO"
    message=(result.get("mensagem","") if sync_ok else (stderr or stdout or "Falha sem mensagem registrada.")).replace("\n"," ")[-1000:]

    rows=[]
    for name,file_id in SOURCES.items():
        count,total=after_totals[name]; d=diffs[name]
        altered=bool(name in hash_changed or name in count_changed or name in total_changed or d["added"] or d["removed"])
        if sync_ok:
            detail=(f"Fonte original lida; reconciliação=OK; "
                    f"hash={'ALTERADO' if name in hash_changed else 'inalterado'}; registros={count}; "
                    f"+{d['added']} / -{d['removed']} / alterados={d['altered']}; total={total}; "
                    f"fingerprint_registros=OK; total={'ALTERADO' if name in total_changed else 'inalterado'}.")
        else:
            detail=(f"FALHA DE CONFERÊNCIA: {'; '.join(reconciliation.get(name, [])) or message}")
        rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":LABELS[name],"fonte_id":file_id,"conteudo_alterado":"SIM" if altered else "NÃO","registros":count,"total":total,"registros_adicionados":d["added"],"registros_removidos":d["removed"],"registros_alterados":d["altered"],"valores_alterados":"SIM" if d["value_changed"] or name in total_changed else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":detail})
    rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":"RESUMO DA EXECUÇÃO","fonte_id":"","conteudo_alterado":"SIM" if changed else "NÃO","registros":sum(x[0] for x in after_totals.values()),"total":"","registros_adicionados":sum(diffs[n]["added"] for n in SOURCES),"registros_removidos":sum(diffs[n]["removed"] for n in SOURCES),"registros_alterados":sum(diffs[n]["altered"] for n in SOURCES),"valores_alterados":"SIM" if total_changed else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":f"Fontes lidas: 6/6. Reconciliação fonte/dashboard: {'OK' if sync_ok else 'FALHOU'}. Hash alterado: {', '.join(hash_changed) if hash_changed else 'nenhum'}. Registros alterados: {', '.join(record_changed) if record_changed else 'nenhum'}. Quantidade alterada: {', '.join(count_changed) if count_changed else 'nenhuma'}. Total alterado: {', '.join(total_changed) if total_changed else 'nenhum'}. Divergências: {json.dumps(reconciliation, ensure_ascii=False) if reconciliation else 'nenhuma'}."})
    append_rows(rows)
    output_values(changed,sync_ok)
    print(json.dumps({"audit":"REGISTRADA","status":execution,"changed":changed,"sync_ok":sync_ok,
      "fontes_alteradas":hash_changed,"reconciliacao_fonte_dashboard":"OK" if sync_ok else "FALHOU",
      "divergencias":reconciliation,"registros_individuais_verificados":sync_ok,
      "valores_totais_verificados":sync_ok,"fontes_verificadas":6 if len(source_report)==len(SOURCES) else 0,
      "log":str(LOG.relative_to(ROOT))},ensure_ascii=False))
    return 0 if sync_ok else 1

if __name__=="__main__": raise SystemExit(main())
