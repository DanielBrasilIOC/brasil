#!/usr/bin/env python3
"""Sincroniza as seis fontes CSV do Drive, valida registros e valores e atualiza data.json."""
import csv, hashlib, json, os, re, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA_PATH=ROOT/"data.json"; REPASSES_PATH=ROOT/"repasses.json"; STATE_PATH=ROOT/"source_state.json"
CACHE_PATH=ROOT/".drive_source_ids.json"
KEYS=("empenhos","orcamentario","ordens_bancarias","repasses","financeiro","restos")
AUDIT={}

def sources():
    if not CACHE_PATH.exists(): raise RuntimeError("IDs das fontes não foram descobertos nesta execução.")
    x=json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(x,dict) or set(x)!=set(KEYS) or len(set(x.values()))!=6:
        raise RuntimeError("A descoberta não retornou exatamente seis IDs distintos.")
    return x
SOURCES=sources()

def clean(v):
    s=str(v or "").replace("\ufeff","").strip()
    fixes={"Ã‡":"Ç","Ãƒ":"Ã","Ã‰":"É","Ã“":"Ó","Ãš":"Ú","Ã£":"ã","Ã§":"ç","Ã¡":"á","Ã©":"é","Ã­":"í","Ã³":"ó","Ãº":"ú","Ãª":"ê","Ã´":"ô","Ãµ":"õ"}
    for a,b in fixes.items(): s=s.replace(a,b)
    return s

def norm(v):
    s=unicodedata.normalize("NFKD",clean(v).upper().replace("Ç","C"))
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c))

def money(v):
    s=clean(v).replace("R$","").replace(" ","")
    if not s or s in {"-","—"}: return None
    neg=s.startswith("(") and s.endswith(")"); s=s.strip("()")
    if "," in s: s=s.replace(".","").replace(",",".")
    try: n=Decimal(s)
    except InvalidOperation: return None
    return float(-abs(n) if neg else n)

def download(fid):
    urls=[f"https://drive.usercontent.google.com/download?id={urllib.parse.quote(fid,safe='')}&export=download&authuser=0&confirm=t",f"https://drive.google.com/uc?export=download&id={urllib.parse.quote(fid,safe='')}"]
    errors=[]
    for u in urls:
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,text/plain,application/octet-stream,*/*"})
            with urllib.request.urlopen(req,timeout=45) as r: b=r.read()
            try: s=b.decode("utf-8-sig")
            except UnicodeDecodeError: s=b.decode("cp1252",errors="replace")
            if re.search(r"<(?:!doctype|html|head|body|script|meta)\\b",s[:2000],re.I) or "accounts.google.com/ServiceLogin" in s:
                errors.append("resposta HTML/login"); continue
            s=s.replace(r"\r\n","\n").replace(r"\n","\n").replace(r"\r","\n").replace(r'\"','"').replace(r"\t","\t")
            return s
        except Exception as e: errors.append(str(e))
    raise RuntimeError("Não foi possível baixar o CSV do Drive: "+" | ".join(errors))

def table(text, delimiter, tokens):
    candidates=[delimiter]+[d for d in (",",";","\t","|") if d!=delimiter]
    selected=None; rows=[]; hi=None
    for d in candidates:
        parsed=[]
        for line in text.splitlines():
            try: row=next(csv.reader([line],delimiter=d))
            except Exception: row=[line]
            if len(row)==1 and d in row[0]:
                try:
                    inner=next(csv.reader([row[0]],delimiter=d))
                    if len(inner)>1: row=inner
                except Exception: pass
            parsed.append(row)
        for i,row in enumerate(parsed):
            joined=norm(" ".join(row))
            if len(row)>=len(tokens) and all(norm(t) in joined for t in tokens):
                selected,rows,hi=d,parsed,i; break
        if selected is not None: break
    if hi is None:
        first=next((x for x in text.splitlines() if x.strip()),"")
        raise ValueError(f"Cabeçalho não encontrado: {tokens}; primeira linha={first[:180]!r}")
    header=[clean(x) for x in rows[hi]]; data=[]; totals=[]
    for row in rows[hi+1:]:
        row=[clean(x) for x in row]
        if not any(row): continue
        if any(norm(x)=="TOTAL" for x in row): totals.append(row); continue
        if len(row)<len(header): row += [""]*(len(header)-len(row))
        data.append(row[:len(header)])
    AUDIT[norm(tokens[0])] = {"header":header,"delimiter":"TAB" if selected=="\t" else selected,"row_count":len(data),"skipped_total_rows":totals}
    return data

def total(rows,key): return round(sum(float(r.get(key) or 0) for r in rows),2)
def check(ok,msg):
    if not ok: raise ValueError(msg)

def main():
    src={k:download(v) for k,v in SOURCES.items()}

    # Empenhos 2026: exportação atual tem 5 campos: NE CCor, CNPJ, favorecido, natureza, saldo.
    a=table(src["empenhos"],"\t",["NE CCor","Saldo - Moeda Origem"])
    empenhos=[]
    for r in a:
        v=money(r[4] if len(r)>4 else None)
        if v is None: continue
        empenhos.append({"empenho":r[0] if len(r)>0 else "","ne_ccor":r[0] if len(r)>0 else "","subitem":r[3] if len(r)>3 else "","natureza":r[3] if len(r)>3 else "","cnpj":r[1] if len(r)>1 else "","fornecedor":r[2] if len(r)>2 else "","observacao":"","fonte_recursos_detalhada":"","saldo":v})
    te=total(empenhos,"saldo"); check(1<=len(empenhos)<=500 and te>=0,f"Validação de Empenhos 2026 falhou: linhas={len(empenhos)}, total={te}")

    # Saldo Orçamentário atual: 8 colunas, saldo no índice 7.
    a=table(src["orcamentario"],",",["UG Executora","Fonte Recursos Detalhada","Saldo - Moeda Origem"])
    orc=[]
    for r in a:
        v=money(r[7] if len(r)>7 else None)
        if v is None: continue
        orc.append({"ug":r[0],"unidade":"","ptres":r[2] if len(r)>2 else "","fonte":r[5] if len(r)>5 else "","descricao_fonte":r[5] if len(r)>5 else "","natureza_codigo":"","natureza":"","ug_responsavel":r[0],"responsavel":"","pi":r[3] if len(r)>3 else "","programa":"","saldo":abs(v)})
    to=total(orc,"saldo"); check(1<=len(orc)<=500 and to>=0,f"Validação orçamentária falhou: linhas={len(orc)}, total={to}")

    a=table(src["ordens_bancarias"],",",["Ordem Bancária","Doc - Valor"])
    ob=[]
    for r in a:
        v=money(r[10] if len(r)>10 else None)
        if v is None: continue
        ob.append({"uge":r[0],"unidade":r[1],"ob":r[2],"data":r[3],"cnpj":r[4],"favorecido":r[5],"processo":r[6],"fonte":r[7],"descricao_fonte":r[8],"observacao":r[9],"valor":v,"movimentacao_liquida":money(r[11]) or 0,"data_pagamento":r[3]})
    tob=total(ob,"valor"); check(1<=len(ob)<=10000 and all(r["valor"] is not None for r in ob),f"Validação de Ordens Bancárias falhou: linhas={len(ob)}, total={tob}")
    pubs=[{"data":r["data"],"ob":r["ob"],"cnpj":r["cnpj"],"favorecido":r["favorecido"],"processo":r["processo"],"fonte":r["fonte"],"valor":r["valor"],"observacao":r["observacao"]} for r in ob if "PUBLICACAO" in norm(r["observacao"]) and "ARTIGO" in norm(r["observacao"])]
    tp=total(pubs,"valor")

    a=table(src["repasses"],";",["PROCESSO","STATUS DO EMPENHO","VALOR"]); rep=[]
    for r in a:
        si=next((i for i,v in enumerate(r) if "AGUARDANDOORCAMENTO" in norm(v) or "AGUARDANDOORAMENTO" in norm(v)),None)
        if si is None: continue
        vi=next((i for i in range(len(r)-1,-1,-1) if money(r[i]) is not None),None)
        if vi is None: continue
        rep.append({"processo":r[0] if r else "","licitacao":"","fornecedor":r[7] if len(r)>7 else "","sub_grupo":r[3] if len(r)>3 else "","elemento_despesa":r[1] if len(r)>1 else "","elemento":r[2] if len(r)>2 else "","sub_grupo_despesa":r[3] if len(r)>3 else "","vigencia":r[4] if len(r)>4 else "","situacao_prioridade":r[5] if len(r)>5 else "","solicitacao_ne":"","numero_ne":"","status_empenho":r[si],"fornecedores":r[7] if len(r)>7 else "","saldo":money(r[vi])})
    tr=total(rep,"saldo"); mr=sum(x["saldo"] is None for x in rep); check(1<=len(rep)<=1000 and mr<=5,f"Validação de repasses falhou: linhas={len(rep)}, total={tr}, sem valor={mr}")

    fl=[]
    for line in src["financeiro"].splitlines():
        try: fl.append(next(csv.reader([line],delimiter=",")))
        except Exception: fl.append([line])
    hi=next((i for i,r in enumerate(fl) if len(r)>=6 and norm(r[0])==norm("UG Executora") and norm(r[1])==norm("Fonte Recursos Detalhada") and "VINCULACAO" in norm(r[3]) and "PAGAMENTO" in norm(r[3])),None)
    check(hi is not None,"Cabeçalho oficial do Saldo Financeiro não encontrado.")
    fin=[]
    for raw in fl[hi+1:]:
        r=[clean(x) for x in raw]
        if len(r)<6 or not r[0] or not r[1] or not norm(r[4]).startswith("SALDOMOEDAORIGEM"): continue
        v=money(r[5]); check(v is not None and r[3],"Saldo financeiro inválido ou sem vinculação.")
        fin.append({"uge":r[0],"unidade":"IOC","fonte":r[1],"vinculo":r[3],"saldo":abs(v)})
    tf=total(fin,"saldo"); check(1<=len(fin)<=100 and all(x["vinculo"] for x in fin),f"Validação do saldo financeiro falhou: linhas={len(fin)}, total={tf}")

    a=table(src["restos"],",",["Empenho","Saldo"]); rap=[]
    for r in a:
        v=money(r[-1]) if r else None
        if v is None or abs(v)<0.005: continue
        rap.append({"empenho":r[0],"cnpj":"","fornecedor":r[1] if len(r)>1 else "","pi":"","programa":"","autor_emenda":"","natureza_codigo":r[2] if len(r)>2 else "","natureza":r[3] if len(r)>3 else "","saldo":v})
    trp=total(rap,"saldo"); check(1<=len(rap)<=1000 and trp>=0,f"Validação de Restos a Pagar falhou: linhas={len(rap)}, total={trp}")

    updates={"financeiro":(fin,tf),"restos":(rap,trp),"empenhos":(empenhos,te),"orcamentario":(orc,to),"repasses":(rep,tr),"ordens_bancarias":(ob,tob)}
    data=json.loads(DATA_PATH.read_text(encoding="utf-8")); data["datasets"]=[d for d in data.get("datasets",[]) if d.get("id")!="documentos_habeis_pendentes"]
    ds={d.get("id"):d for d in data.get("datasets",[])}; check(all(k in ds for k in updates),"Dataset esperado ausente em data.json")
    def brl(x): return f"{x:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    notes={
      "financeiro":f"Extração do SIAFI. Cada linha mantém sua própria Vinculação Pagamento. {len(fin)} registros. Total detalhado: R$ {brl(tf)}.",
      "restos":f"Fonte SIAFI: Restos a Pagar. {len(rap)} registros com saldo diferente de zero. Total detalhado: R$ {brl(trp)}.",
      "empenhos":f"Fonte SIAFI: Saldo nos empenhos 2026. {len(empenhos)} registros detalhados. Total: R$ {brl(te)}.",
      "orcamentario":f"Fonte oficial: Saldo Orçamentário.csv. {len(orc)} registros detalhados. Total: R$ {brl(to)}.",
      "repasses":f"Fonte: Aguardando Repasse Orçamentário.csv. {len(rep)} registros com status AGUARDANDO ORÇAMENTO. Total: R$ {brl(tr)}.",
      "ordens_bancarias":f"Fonte: ORDEM BANCARIAS EMITIDAS.csv. {len(ob)} registros. Total Doc - Valor: R$ {brl(tob)}. Registros mantidos por OB + fonte pagadora.",
    }
    hashes={k:hashlib.sha256(v.encode("utf-8")).hexdigest() for k,v in src.items()}; prev=json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    source_changed=hashes!=prev.get("hashes",{})
    for k,(rows,amount) in updates.items():
        ds[k]["rows"]=rows; ds[k]["total"]=amount; ds[k]["detail_count"]=len(rows); ds[k]["source_url"]="https://drive.google.com/file/d/"+SOURCES[k]+"/view"; ds[k]["note"]=notes[k]
    ds["financeiro"]["source_name"]="Saldo Financeiro"; ds["repasses"]["missing_values"]=mr
    pub=ds.get("publicacoes_pagas",{}); pub["rows"]=pubs; pub["total"]=tp; pub["detail_count"]=len(pubs); pub["source_url"]="https://drive.google.com/file/d/"+SOURCES["ordens_bancarias"]+"/view"; pub["note"]=f"Subconjunto derivado das Ordens Bancárias atuais: {len(pubs)} registros. Total: R$ {brl(tp)}."
    changed=source_changed or any(ds[k].get("rows")!=rows or ds[k].get("total")!=amount or ds[k].get("note")!=notes[k] for k,(rows,amount) in updates.items())
    old_rep=json.loads(REPASSES_PATH.read_text(encoding="utf-8")) if REPASSES_PATH.exists() else {}; rep_data={"rows":rep,"total":tr,"missing_values":mr,"note":notes["repasses"]}; changed=changed or old_rep!=rep_data
    if not changed:
        print(json.dumps({"status":"SEM_ALTERACOES","changed":False,"generated_at":data.get("generated_at"),"fontes_alteradas":[]},ensure_ascii=False)); return
    stamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"); data["generated_at"]=stamp
    DATA_PATH.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    REPASSES_PATH.write_text(json.dumps(rep_data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    STATE_PATH.write_text(json.dumps({"hashes":hashes},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"status":"ATUALIZADO","changed":True,"generated_at":stamp,"fontes_alteradas":[k for k in hashes if hashes[k]!=prev.get("hashes",{}).get(k)],"fontes":{k:{"registros":len(v[0]),"total":v[1]} for k,v in updates.items()}},ensure_ascii=False))

if __name__=="__main__": main()
