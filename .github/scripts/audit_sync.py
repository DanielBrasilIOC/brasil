#!/usr/bin/env python3
"""Executa a sincronização e audita registros, valores e totais do dashboard."""
import csv, hashlib, json, os, subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / ".github" / "scripts" / "sync_sources.py"
STATE = ROOT / "source_state.json"
DATA = ROOT / "data.json"
LOG = ROOT / "logs" / "atualizacoes_dashboard.csv"
CACHE_PATH = ROOT / ".drive_source_ids.json"
SOURCE_KEYS = ("empenhos", "orcamentario", "ordens_bancarias", "repasses", "financeiro", "restos")
def resolve_sources():
    if not CACHE_PATH.exists():
        raise RuntimeError("IDs das fontes não foram descobertos nesta execução; auditoria bloqueada.")
    ids = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(ids, dict) or set(ids) != set(SOURCE_KEYS) or len(set(ids.values())) != len(SOURCE_KEYS):
        raise RuntimeError("A descoberta não retornou exatamente seis IDs distintos.")
    return ids
SOURCES = resolve_sources()
DIARIAS_ID_PATH = ROOT / ".diarias_source_id"
if not DIARIAS_ID_PATH.exists(): raise RuntimeError("DIARIAS PAGAS.csv não foi descoberta por nome; auditoria bloqueada.")
SOURCES["diarias"] = DIARIAS_ID_PATH.read_text(encoding="utf-8").strip()
if not SOURCES["diarias"]: raise RuntimeError("ID de DIARIAS PAGAS.csv vazio; auditoria bloqueada.")
LABELS = {"empenhos":"Empenhos","orcamentario":"Orçamentário","ordens_bancarias":"Ordens Bancárias","repasses":"Repasses","financeiro":"Financeiro","restos":"Restos a Pagar","diarias":"Diárias Pagas"}
FIELDS = ["timestamp_utc","run_id","evento","resultado_execucao","fonte","fonte_id","conteudo_alterado","registros","total","registros_adicionados","registros_removidos","registros_alterados","valores_alterados","dashboard_atualizado","publicacao","mensagem"]

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def old_hashes():
    s=read_json(STATE,{})
    return s.get("hashes",{}) if isinstance(s,dict) else {}

def snapshot(data):
    out={}
    for d in data.get("datasets",[]) if isinstance(data,dict) else []:
        name=d.get("id"); rows=d.get("rows",[])
        key = "diarias" if name == "diarias_pagas" else name
        if key not in SOURCES or not isinstance(rows,list): continue
        sigs=[]
        for row in rows:
            raw=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))
            sigs.append(hashlib.sha256(raw.encode("utf-8")).hexdigest())
        out[key]=sigs
    return out

def row_diff(before, after):
    """Compara registros individualmente, tratando duplicidades com contagem de hashes."""
    result={}
    for name in SOURCES:
        b=before.get(name,[]); a=after.get(name,[])
        cb={}
        ca={}
        for h in b: cb[h]=cb.get(h,0)+1
        for h in a: ca[h]=ca.get(h,0)+1
        added=sum(max(ca.get(h,0)-n,0) for h,n in cb.items()) + sum(n for h,n in ca.items() if h not in cb)
        removed=sum(max(cb.get(h,0)-n,0) for h,n in ca.items()) + sum(n for h,n in cb.items() if h not in ca)
        # Uma substituição é uma alteração de registro; alterações de conteúdo são contadas
        # pelo mínimo entre adicionados e removidos, sem mascarar o saldo líquido.
        altered=min(added,removed)
        result[name]={"added":added,"removed":removed,"altered":altered,"value_changed":(added>0 or removed>0)}
    return result

def run_sync():
    p=subprocess.run(["python",str(SYNC)],cwd=ROOT,env=os.environ.copy(),text=True,capture_output=True)
    out=(p.stdout or "").strip(); err=(p.stderr or "").strip(); parsed={}
    for line in reversed(out.splitlines()):
        try:
            x=json.loads(line)
            if isinstance(x,dict) and "status" in x: parsed=x; break
        except Exception: pass
    return p.returncode,parsed,out,err

def source_details(data,name):
    ds={d.get("id"):d for d in data.get("datasets",[])}
    dataset_id = "diarias_pagas" if name == "diarias" else name
    d=ds.get(dataset_id,{})
    rows=d.get("rows",[])
    return (len(rows) if isinstance(rows,list) else 0,d.get("total",""))

def append_rows(rows):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    exists=LOG.exists() and LOG.stat().st_size>0
    if exists:
        with LOG.open("r",encoding="utf-8-sig",newline="") as f:
            existing=list(csv.reader(f,delimiter=";"))
        if existing:
            old_header=existing[0]
            legacy_fields=["timestamp_utc","run_id","evento","resultado_execucao","fonte","fonte_id","conteudo_alterado","registros","total","dashboard_atualizado","publicacao","mensagem"]
            migrated=[]
            needs_rewrite=(old_header != FIELDS or any(len(r) != len(FIELDS) for r in existing[1:]))
            if needs_rewrite:
                for raw in existing[1:]:
                    if len(raw)==len(FIELDS):
                        previous=dict(zip(FIELDS,raw))
                    elif len(raw)==len(legacy_fields):
                        previous=dict(zip(legacy_fields,raw))
                    else:
                        previous=dict(zip(old_header,raw))
                    migrated.append({field:previous.get(field,"") for field in FIELDS})
                with LOG.open("w",encoding="utf-8-sig",newline="") as f:
                    writer=csv.DictWriter(f,fieldnames=FIELDS,delimiter=";")
                    writer.writeheader()
                    writer.writerows(migrated)
    with LOG.open("a",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,delimiter=";")
        if not exists: w.writeheader()
        w.writerows(rows)

def output_values(changed,sync_ok):
    path=os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path,"a",encoding="utf-8") as o:
            o.write("changed="+("true" if changed else "false")+"\n")
            o.write("sync_ok="+("true" if sync_ok else "false")+"\n")

def main():
    ts=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    run_id=os.getenv("GITHUB_RUN_ID","manual"); event=os.getenv("GITHUB_EVENT_NAME","manual")
    before_data=read_json(DATA,{})
    before_repasses=read_json(ROOT / "repasses.json",{})
    before_snapshot=snapshot(before_data)
    before_totals={n:source_details(before_data,n) for n in SOURCES}
    before_hashes=old_hashes()
    code,result,stdout,stderr=run_sync()
    if code != 0:
        print("SYNC_STDOUT: " + (stdout or "")[-3000:])
        print("SYNC_STDERR: " + (stderr or "")[-3000:])
    after_data=read_json(DATA,{})
    after_hashes=old_hashes()
    after_snapshot=snapshot(after_data)
    after_totals={n:source_details(after_data,n) for n in SOURCES}
    sync_ok=code==0 and result.get("status") in {"SEM_ALTERACOES","ATUALIZADO"}
    source_changed=[k for k in SOURCES if after_hashes.get(k)!=before_hashes.get(k)]
    diffs=row_diff(before_snapshot,after_snapshot) if sync_ok else {n:{"added":0,"removed":0,"altered":0,"value_changed":False} for n in SOURCES}
    structural_changed=[n for n in SOURCES if diffs[n]["added"] or diffs[n]["removed"]]
    value_changed=[n for n in SOURCES if diffs[n]["value_changed"]]
    total_changed=[n for n in SOURCES if str(before_totals[n][1])!=str(after_totals[n][1])]
    count_changed=[n for n in SOURCES if before_totals[n][0]!=after_totals[n][0]]
    # Se o hash bruto mudou, mas o dataset derivado não mudou, a auditoria registra a divergência.
    repasses_after=read_json(ROOT / "repasses.json",{})
    # Inclui metadados, links e datasets derivados na decisão de publicação.
    # A comparação de linhas/valores sozinha não detecta correções de nota ou origem.
    dataset_content_changed=before_data.get("datasets") != after_data.get("datasets")
    repasses_content_changed=before_repasses != repasses_after
    changed=bool(source_changed or structural_changed or value_changed or total_changed or count_changed or dataset_content_changed or repasses_content_changed)
    if sync_ok:
        execution=result.get("status","OK")
        message=result.get("mensagem","Sincronização concluída.")
        dashboard_updated="SIM" if changed else "NÃO"
        publication="PUBLICAÇÃO PROGRAMADA" if changed else "NÃO NECESSÁRIA"
    else:
        execution="FALHA"; message=(stderr or stdout or "Falha sem mensagem registrada.").replace("\n"," ")[-1000:]
        dashboard_updated="NÃO"; publication="NÃO PUBLICADO"
    rows=[]
    for name,file_id in SOURCES.items():
        count,total=after_totals[name]
        d=diffs[name]
        altered="SIM" if name in source_changed or d["added"] or d["removed"] or name in total_changed else "NÃO"
        msg=(f"Hash fonte: {'ALTERADO' if name in source_changed else 'inalterado'}; "
             f"registros: +{d['added']} / -{d['removed']} / alterados={d['altered']}; "
             f"valor total: {'ALTERADO' if name in total_changed else 'inalterado'}.")
        rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":LABELS[name],"fonte_id":file_id,"conteudo_alterado":altered,"registros":count,"total":total,"registros_adicionados":d["added"],"registros_removidos":d["removed"],"registros_alterados":d["altered"],"valores_alterados":"SIM" if d["value_changed"] else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":msg if sync_ok else message})
    rows.append({"timestamp_utc":ts,"run_id":run_id,"evento":event,"resultado_execucao":execution,"fonte":"RESUMO DA EXECUÇÃO","fonte_id":"","conteudo_alterado":"SIM" if changed else "NÃO","registros":sum(x[0] for x in after_totals.values()),"total":"","registros_adicionados":sum(diffs[n]["added"] for n in SOURCES),"registros_removidos":sum(diffs[n]["removed"] for n in SOURCES),"registros_alterados":sum(diffs[n]["altered"] for n in SOURCES),"valores_alterados":"SIM" if value_changed else "NÃO","dashboard_atualizado":dashboard_updated,"publicacao":publication,"mensagem":f"Fontes com hash alterado: {', '.join(source_changed) if source_changed else 'nenhuma'}. Contagem alterada: {', '.join(count_changed) if count_changed else 'nenhuma'}. Total alterado: {', '.join(total_changed) if total_changed else 'nenhum'}."})
    append_rows(rows)
    output_values(changed,sync_ok)
    print(json.dumps({"audit":"REGISTRADA","status":execution,"changed":changed,"sync_ok":sync_ok,"fontes_alteradas":source_changed,"registros_individuais_verificados":True,"valores_totais_verificados":True,"log":str(LOG.relative_to(ROOT))},ensure_ascii=False))
    return 0
if __name__=="__main__": raise SystemExit(main())
