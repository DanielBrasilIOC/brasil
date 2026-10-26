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
    "empenhos": "1pDEGc2LAz0fe7c4GH5fh-kzgeW0iuQHh",
    "orcamentario": "1gQYnGiF2zLdCOR-iiW5ptNc-3fXdNuMy",
    "ordens_bancarias": "1dTM5GfqVD63wNf2QYhOydEDd6g1Ca8rU",
    "repasses": "1h7oF_blPx6RpuHsCjPshW-zn7IcNHGB-",
    "financeiro": "10ghNRMaUWvaOcX3q8luLTn9CZ2_z4RSQ",
    "restos": "1CIAIW9t9cKAnu-iUlQJpGUx_sfalHyuu",
}
LABELS = {"empenhos":"Empenhos","orcamentario":"Orçamentário","ordens_bancarias":"Ordens Bancárias","repasses":"Repasses","financeiro":"Financeiro","restos":"Restos a Pagar"}
FIELDS = ["timestamp_utc","run_id","evento","resultado_execucao","fonte","fonte_id","conteudo_alterado","registros","total","registros_adicionados","registros_removidos","registros_alterados","valores_alterados","dashboard_atualizado","publicacao","mensagem"]

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

KEY_FIELDS = {
    "empenhos": ("empenho","ne_ccor","subitem","cnpj","observacao"),
    "orcamentario": ("ug","unidade","ptres","fonte","natureza_codigo","pi","programa"),
    "ordens_bancarias": ("ob","fonte","processo","data","cnpj","favorecido"),
    "repasses": ("processo","numero_ne","status_empenho","fornecedores"),
    "financeiro": ("uge","fonte","vinculo"),
    "restos": ("empenho","cnpj","natureza_codigo","pi","programa"),
}

def canonical(v):
    if isinstance(v, dict): return {k:canonical(x) for k,x in v.items()}
    if isinstance(v, list): return [canonical(x) for x in v]
    if isinstance(v, (int,float)) and not isinstance(v, bool): return float(v)
    return v

def record_signature(row):
    return json.dumps(canonical(row),ensure_ascii=False,sort_keys=True,separators=(",",":"))

def record_key(name,row):
    fields=KEY_FIELDS.get(name,())
    values=tuple(str(row.get(field,"")).strip() for field in fields)
    # If no configured key fields are present, use the complete row as identity.
    return values if any(values) else (record_signature(row),)

def snapshot(data):
    out={}
    for d in data.get("datasets",[]) if isinstance(data,dict) else []:
        name=d.get("id"); rows=d.get("rows",[])
        if name in SOURCES and isinstance(rows,list):
            out[name]=[r for r in rows if isinstance(r,dict)]
    return out

def row_diff(before, after):
    """Compara registros por chave estável; alterações não viram inclusão/exclusão."""
    result={}
    for name in SOURCES:
        old_groups={}; new_groups={}
        for row in before.get(name,[]):
            old_groups.setdefault(record_key(name,row),Counter())[record_signature(row)] += 1
        for row in after.get(name,[]):
            new_groups.setdefault(record_key(name,row),Counter())[record_signature(row)] += 1
        added=removed=altered=0
        for key in set(old_groups) | set(new_groups):
            old_counts=old_groups.get(key,Counter()).copy()
            new_counts=new_groups.get(key,Counter()).copy()
            exact=min(sum(old_counts.values()),sum(new_counts.values()))
            common=old_counts & new_counts
            old_unmatched=sum((old_counts-common).values())
            new_unmatched=sum((new_counts-common).values())
            changed=min(old_unmatched,new_unmatched)
            altered += changed
            removed += old_unmatched-changed
            added += new_unmatched-changed
        result[name]={"added":added,"removed":removed,"altered":altered,
                      "value_changed":bool(added or removed or altered)}
    return result

def source_details(data,name):
    ds={d.get("id"):d for d in data.get("datasets",[])}
    d=ds.get(name,{})
    rows=d.get("rows",[])
    return (len(rows) if isinstance(rows,list) else 0,d.get("total",""))

def row_fingerprint(rows):
    def canonical(v):
        if isinstance(v, dict): return {k:canonical(x) for k,x in v.items()}
        if isinstance(v, list): return [canonical(x) for x in v]
        if isinstance(v, (int,float)) and not isinstance(v, bool): return float(v)
        return v
    hashes = sorted(hashlib.sha256(json.dumps(canonical(r), ensure_ascii=False, sort_keys=True,
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
    record_changed=[n for n in SOURCES if diffs[n]["added"] or diffs[n]["removed"] or diffs[n]["altered"]]
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
        dashboard_count,dashboard_total=after_totals[name]; d=diffs[name]
        source=source_report.get(name,{})
        count=source.get("registros",dashboard_count)
        total=source.get("total",dashboard_total)
        altered=bool(name in hash_changed or name in count_changed or name in total_changed or d["added"] or d["removed"])
        if sync_ok:
            detail=(f"Fonte original lida; reconciliação=OK; "
                    f"hash={'ALTERADO' if name in hash_changed else 'inalterado'}; registros fonte={count}; "
                    f"registros dashboard={dashboard_count}; +{d['added']} / -{d['removed']} / alterados={d['altered']}; "
                    f"total fonte={total}; total dashboard={dashboard_total}; fingerprint_registros=OK.")
        else:
            detail=(f"FALHA DE CONFERÊNCIA: {'; '.join(reconciliation.get(name, [])) or message}; "
                    f"registros fonte={count}, dashboard={dashboard_count}; total fonte={total}, dashboard={dashboard_total}")
        rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":LABELS[name],"fonte_id":file_id,"conteudo_alterado":"SIM" if altered else "NÃO","registros":count,"total":total,"registros_adicionados":d["added"],"registros_removidos":d["removed"],"registros_alterados":d["altered"],"valores_alterados":"SIM" if d["value_changed"] or name in total_changed else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":detail})
    rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":"RESUMO DA EXECUÇÃO","fonte_id":"","conteudo_alterado":"SIM" if changed else "NÃO","registros":sum(x[0] for x in after_totals.values()),"total":"","registros_adicionados":sum(diffs[n]["added"] for n in SOURCES),"registros_removidos":sum(diffs[n]["removed"] for n in SOURCES),"registros_alterados":sum(diffs[n]["altered"] for n in SOURCES),"valores_alterados":"SIM" if total_changed else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":f"Fontes lidas: 6/6. Reconciliação fonte/dashboard: {'OK' if sync_ok else 'FALHOU'}. Hash alterado: {', '.join(hash_changed) if hash_changed else 'nenhum'}. Registros alterados: {', '.join(record_changed) if record_changed else 'nenhum'}. Quantidade alterada: {', '.join(count_changed) if count_changed else 'nenhuma'}. Total alterado: {', '.join(total_changed) if total_changed else 'nenhum'}. Divergências: {json.dumps(reconciliation, ensure_ascii=False) if reconciliation else 'nenhuma'}."})
    append_rows(rows)
    output_values(changed,sync_ok)
    print(json.dumps({"audit":"REGISTRADA","status":execution,"changed":changed,"sync_ok":sync_ok,
      "fontes_alteradas":hash_changed,"reconciliacao_fonte_dashboard":"OK" if sync_ok else "FALHOU",
      "divergencias":reconciliation,"registros_individuais_verificados":sync_ok,
      "valores_totais_verificados":sync_ok,"fontes_verificadas":6 if len(source_report)==len(SOURCES) else 0,
      "totais_fontes":{n:{"registros":source_report.get(n,{}).get("registros"),"total":source_report.get(n,{}).get("total")} for n in SOURCES},
      "log":str(LOG.relative_to(ROOT))},ensure_ascii=False))
    return 0 if sync_ok else 1

if __name__=="__main__": raise SystemExit(main())
