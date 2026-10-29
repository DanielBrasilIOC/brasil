#!/usr/bin/env python3
"""Sincroniza as seis fontes CSV do Drive, valida registros e valores e atualiza data.json."""
import csv, hashlib, json, os, re, tempfile, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA_PATH=ROOT/"data.json"; REPASSES_PATH=ROOT/"repasses.json"; STATE_PATH=ROOT/"source_state.json"
CACHE_PATH=ROOT/".drive_source_ids.json"; DIARIAS_ID_PATH=ROOT/".diarias_source_id"
KEYS=("empenhos","orcamentario","ordens_bancarias","repasses","financeiro","restos")
AUDIT={}

def sources():
    if not CACHE_PATH.exists(): raise RuntimeError("IDs das fontes não foram descobertos nesta execução.")
    x=json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(x,dict) or set(x)!=set(KEYS) or len(set(x.values()))!=6:
        raise RuntimeError("A descoberta não retornou exatamente seis IDs distintos.")
    return x
SOURCES=sources()
if not DIARIAS_ID_PATH.exists(): raise RuntimeError("DIARIAS PAGAS.csv não foi localizada pelo nome na pasta oficial.")
DIARIAS_ID=DIARIAS_ID_PATH.read_text(encoding="utf-8").strip()
if not DIARIAS_ID: raise RuntimeError("ID de DIARIAS PAGAS.csv vazio após descoberta por nome.")

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

def decode_csv_bytes(raw):
    """Decodifica CSV do Drive respeitando BOM e sem substituir bytes inválidos silenciosamente."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text:
        raise ValueError("CSV contém bytes NUL após a decodificação; codificação inesperada.")
    return text

def download(fid):
    urls=[f"https://drive.usercontent.google.com/download?id={urllib.parse.quote(fid,safe='')}&export=download&authuser=0&confirm=t",f"https://drive.google.com/uc?export=download&id={urllib.parse.quote(fid,safe='')}"]
    errors=[]
    for u in urls:
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,text/plain,application/octet-stream,*/*"})
            with urllib.request.urlopen(req,timeout=45) as r: b=r.read()
            text=decode_csv_bytes(b)
            if re.search(r"<(?:!doctype|html|head|body|script|meta)\b",text[:2000],re.I) or "accounts.google.com/ServiceLogin" in text:
                errors.append("resposta HTML/login"); continue
            if not text.strip():
                errors.append("arquivo vazio"); continue
            return text
        except Exception as e: errors.append(str(e))
    raise RuntimeError("Não foi possível baixar/decodificar o CSV do Drive: "+" | ".join(errors))
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

def atomic_json_write(path, payload):
    """Escreve JSON temporário e só troca o destino após gravação completa."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    temp_path.replace(path)

def main():
    src={k:download(v) for k,v in SOURCES.items()}; src["diarias"]=download(DIARIAS_ID)

    # Empenhos 2026: exportação atual tem 5 campos: NE CCor, CNPJ, favorecido, natureza, saldo.
    a=table(src["empenhos"],"\t",["NE CCor","Saldo - Moeda Origem"])
    empenhos=[]
    for r in a:
        v=money(r[4] if len(r)>4 else None)
        check(v is not None, f"Saldo inválido em Empenhos 2026: {r!r}")
        empenhos.append({"empenho":r[0] if len(r)>0 else "","ne_ccor":r[0] if len(r)>0 else "","subitem":r[3] if len(r)>3 else "","natureza":r[3] if len(r)>3 else "","cnpj":r[1] if len(r)>1 else "","fornecedor":r[2] if len(r)>2 else "","observacao":"","fonte_recursos_detalhada":"","saldo":v})
    te=total(empenhos,"saldo"); check(1<=len(empenhos)<=500 and te>=0,f"Validação de Empenhos 2026 falhou: linhas={len(empenhos)}, total={te}")

    # Saldo Orçamentário atual: 8 colunas, saldo no índice 7.
    a=table(src["orcamentario"],",",["UG Executora","Fonte Recursos Detalhada","Saldo - Moeda Origem"])
    orc=[]
    for r in a:
        v=money(r[7] if len(r)>7 else None)
        check(v is not None, f"Saldo inválido em Saldo Orçamentário: {r!r}")
        orc.append({"ug":r[0],"unidade":"","ptres":r[2] if len(r)>2 else "","fonte":r[5] if len(r)>5 else "","descricao_fonte":r[5] if len(r)>5 else "","natureza_codigo":"","natureza":"","ug_responsavel":r[0],"responsavel":"","pi":r[3] if len(r)>3 else "","programa":"","saldo":abs(v)})
    to=total(orc,"saldo"); check(1<=len(orc)<=500 and to>=0,f"Validação orçamentária falhou: linhas={len(orc)}, total={to}")

    a=table(src["ordens_bancarias"],";",["DIA","OB","VALOR"])
    ob=[]
    for r in a:
        v=money(r[5] if len(r)>5 else None)
        check(v is not None, f"Valor inválido em Ordens Bancárias: {r!r}")
        ob.append({"ob":r[1] if len(r)>1 else "", "data":r[0] if len(r)>0 else "", "data_pagamento":r[0] if len(r)>0 else "", "processo":r[2] if len(r)>2 else "", "cnpj":r[3] if len(r)>3 else "", "favorecido":r[4] if len(r)>4 else "", "observacao":r[6] if len(r)>6 else "", "valor":v})
    unique_obs={r["ob"] for r in ob}
    tob=total(ob,"valor"); check(1<=len(ob)<=10000 and all(r["valor"] is not None for r in ob) and all(r["ob"] for r in ob) and len(unique_obs)==len(ob),f"Validação de Ordens Bancárias falhou: linhas={len(ob)}, OBs únicas={len(unique_obs)}, total={tob}")
    # Publicações Pagas: registros da mesma planilha cujo código do favorecido começa com EX.
    # Exceção intencional: a OB 254463252012026OB000089 NÃO é uma publicação paga;
    # por isso foi retirada desta categoria e deve continuar excluída mesmo que o favorecido comece com EX.
    OB_NAO_E_PUBLICACAO = {"254463252012026OB000089"}
    pubs=[{"data":r["data"],"ob":r["ob"],"cnpj":r["cnpj"],"favorecido":r["favorecido"],"processo":r["processo"],"valor":r["valor"],"observacao":r["observacao"]} for r in ob if norm(r["cnpj"]).startswith("EX") and r["ob"] not in OB_NAO_E_PUBLICACAO]
    tp=total(pubs,"valor")

    a=table(src["repasses"],";",["PROCESSO","STATUS DO EMPENHO","VALOR"]); rep=[]
    rep_headers=AUDIT[norm("PROCESSO")]["header"]
    solicitacao_idx=next((i for i,h in enumerate(rep_headers) if norm(h) in {"NUMERODASOLICITACAO","NUMERODASOLICITACOES","SOLICITACAO","SOLICITACAONE"}),None)
    if solicitacao_idx is None:
        solicitacao_idx=next((i for i,h in enumerate(rep_headers) if "SOLICITACAO" in norm(h) and "STATUS" not in norm(h)),None)
    check(solicitacao_idx is not None, f"Coluna Número da Solicitação não encontrada no CSV oficial. Cabeçalhos: {rep_headers!r}")
    for r in a:
        si=next((i for i,v in enumerate(r) if "AGUARDANDOORCAMENTO" in norm(v) or "AGUARDANDOORAMENTO" in norm(v)),None)
        if si is None: continue
        vi=next((i for i in range(len(r)-1,-1,-1) if money(r[i]) is not None),None)
        check(vi is not None, f"Valor ausente ou inválido em Aguardando Repasse Orçamentário: {r!r}")
        rep.append({"processo":r[0] if r else "","licitacao":"","fornecedor":r[7] if len(r)>7 else "","sub_grupo":r[3] if len(r)>3 else "","elemento_despesa":r[1] if len(r)>1 else "","elemento":r[2] if len(r)>2 else "","sub_grupo_despesa":r[3] if len(r)>3 else "","vigencia":r[4] if len(r)>4 else "","situacao_prioridade":r[5] if len(r)>5 else "","solicitacao_ne":r[solicitacao_idx] if len(r)>solicitacao_idx else "","numero_solicitacao":r[solicitacao_idx] if len(r)>solicitacao_idx else "","numero_ne":"","status_empenho":r[si],"fornecedores":r[7] if len(r)>7 else "","saldo":money(r[vi])})
    tr=total(rep,"saldo"); mr=sum(x["saldo"] is None for x in rep); check(1<=len(rep)<=1000 and mr==0,f"Validação de repasses falhou: linhas={len(rep)}, total={tr}, sem valor={mr}")

    fl=[]
    for line in src["financeiro"].splitlines():
        try: fl.append(next(csv.reader([line],delimiter=",")))
        except Exception: fl.append([line])
    hi=next((i for i,r in enumerate(fl) if len(r)>=6 and norm(r[0])==norm("UG Executora") and norm(r[1])==norm("Fonte Recursos Detalhada") and "VINCULACAO" in norm(r[3]) and "PAGAMENTO" in norm(r[3])),None)
    check(hi is not None,"Cabeçalho oficial do Saldo Financeiro não encontrado.")
    fin=[]
    for raw in fl[hi+1:]:
        r=[clean(x) for x in raw]
        if len(r)<7 or not r[0] or not r[1] or not norm(r[5]).startswith("SALDOMOEDAORIGEM"): continue
        v=money(r[6]); check(v is not None and r[3],"Saldo financeiro inválido ou sem vinculação.")
        fin.append({"uge":r[0],"unidade":"IOC","fonte":r[1],"vinculo":r[3],"saldo":abs(v)})
    tf=total(fin,"saldo"); check(1<=len(fin)<=100 and all(x["vinculo"] for x in fin),f"Validação do saldo financeiro falhou: linhas={len(fin)}, total={tf}")

    a=table(src["restos"],",",["Empenho","Saldo"]); rap=[]
    for r in a:
        v=money(r[-1]) if r else None
        check(v is not None, f"Saldo inválido em Restos a Pagar: {r!r}")
        if abs(v)<0.005: continue
        rap.append({"empenho":r[0],"cnpj":"","fornecedor":r[1] if len(r)>1 else "","pi":"","programa":"","autor_emenda":"","natureza_codigo":r[2] if len(r)>2 else "","natureza":r[3] if len(r)>3 else "","saldo":v})
    trp=total(rap,"saldo"); check(1<=len(rap)<=1000 and trp>=0,f"Validação de Restos a Pagar falhou: linhas={len(rap)}, total={trp}")

    # Diárias Pagas: fonte SERPRO separada, localizada pelo nome na pasta oficial do Drive.
    dl=src["diarias"].splitlines()
    dhi=next((i for i,line in enumerate(dl) if "Favorecido Doc." in line and "OB - Valor Linha" in line),None)
    check(dhi is not None,"Cabeçalho oficial de DIARIAS PAGAS.csv não encontrado.")
    diarias=[]
    for r in csv.reader(dl[dhi+1:],delimiter="\t"):
        if not r or not any(clean(x) for x in r): continue
        if clean(r[0]).upper()=="TOTAL": continue
        check(len(r)>=6, f"Registro incompleto em DIARIAS PAGAS.csv: {r!r}")
        v=money(r[3])
        check(v is not None, f"Valor inválido em DIARIAS PAGAS.csv: {r!r}")
        diarias.append({"favorecido":clean(r[0]),"data_pagamento":clean(r[1]),"classificacao_orcamentaria":clean(r[2]),"valor":v,"documento":clean(r[4]),"observacao":clean(r[5])})
    td=total(diarias,"valor")
    check(1<=len(diarias)<=1000 and all(r["favorecido"] for r in diarias),f"Validação de Diárias Pagas falhou: linhas={len(diarias)}, total={td}")

    updates={"financeiro":(fin,tf),"restos":(rap,trp),"empenhos":(empenhos,te),"orcamentario":(orc,to),"repasses":(rep,tr),"ordens_bancarias":(ob,tob)}
    data=json.loads(DATA_PATH.read_text(encoding="utf-8")); data["datasets"]=[d for d in data.get("datasets",[]) if d.get("id")!="documentos_habeis_pendentes"]
    ds={d.get("id"):d for d in data.get("datasets",[])}; check(all(k in ds for k in updates) and "diarias_pagas" in ds,"Dataset esperado ausente em data.json")
    def brl(x): return f"{x:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    notes={
      "financeiro":f"Extração do SIAFI. Cada linha mantém sua própria Vinculação Pagamento. {len(fin)} registros. Total detalhado: R$ {brl(tf)}.",
      "restos":f"Fonte SIAFI: Restos a Pagar. {len(rap)} registros com saldo diferente de zero. Total detalhado: R$ {brl(trp)}.",
      "empenhos":f"Fonte SIAFI: Saldo nos empenhos 2026. {len(empenhos)} registros detalhados. Total: R$ {brl(te)}.",
      "orcamentario":f"Fonte oficial: Saldo Orçamentário.csv. {len(orc)} registros detalhados. Total: R$ {brl(to)}.",
      "repasses":f"Fonte: Aguardando Repasse Orçamentário.csv. {len(rep)} registros com status AGUARDANDO ORÇAMENTO. Total: R$ {brl(tr)}.",
      "ordens_bancarias":f"Fonte: ORDEM BANCARIAS EMITIDAS.csv. {len(ob)} registros únicos por OB, sem coluna Fonte. Total Valor (R$): R$ {brl(tob)}.",
    }
    diarias_note=f"Diárias Pagas: {len(diarias)} registros da planilha DIARIAS PAGAS.csv. Total: R$ {brl(td)}."
    diarias_url="https://drive.google.com/file/d/"+DIARIAS_ID+"/view"
    diarias_ds=ds["diarias_pagas"]
    diarias_changed=(diarias_ds.get("rows")!=diarias or diarias_ds.get("total")!=td or diarias_ds.get("note")!=diarias_note or diarias_ds.get("source_url")!=diarias_url or diarias_ds.get("source_name")!="DIARIAS PAGAS.csv")
    diarias_ds["rows"]=diarias; diarias_ds["total"]=td; diarias_ds["detail_count"]=len(diarias); diarias_ds["source_url"]=diarias_url; diarias_ds["source_name"]="DIARIAS PAGAS.csv"; diarias_ds["note"]=diarias_note
    hashes={k:hashlib.sha256(v.encode("utf-8")).hexdigest() for k,v in src.items()}; prev=json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    source_changed=hashes!=prev.get("hashes",{})
    for k,(rows,amount) in updates.items():
        ds[k]["rows"]=rows; ds[k]["total"]=amount; ds[k]["detail_count"]=len(rows); ds[k]["source_url"]="https://drive.google.com/file/d/"+SOURCES[k]+"/view"; ds[k]["note"]=notes[k]
    ds["financeiro"]["source_name"]="Saldo Financeiro"; ds["repasses"]["missing_values"]=mr
    pub=ds.get("publicacoes_pagas",{}); pub_note=f"Publicações Pagas: {len(pubs)} registros da planilha de Ordens Bancárias, filtrados pelo código do favorecido iniciado por EX. Total: R$ {brl(tp)}."; pub_url="https://drive.google.com/file/d/"+SOURCES["ordens_bancarias"]+"/view"; pub_changed=pub.get("rows")!=pubs or pub.get("total")!=tp or pub.get("note")!=pub_note or pub.get("source_url")!=pub_url; pub["rows"]=pubs; pub["total"]=tp; pub["detail_count"]=len(pubs); pub["source_url"]=pub_url; pub["source_name"]="ORDEM BANCARIAS EMITIDAS.csv"; pub["note"]=pub_note
    ds["ordens_bancarias"]["source_name"]="ORDEM BANCARIAS EMITIDAS.csv"
    changed=source_changed or pub_changed or diarias_changed or any(ds[k].get("rows")!=rows or ds[k].get("total")!=amount or ds[k].get("note")!=notes[k] for k,(rows,amount) in updates.items())
    old_rep=json.loads(REPASSES_PATH.read_text(encoding="utf-8")) if REPASSES_PATH.exists() else {}; rep_data={"rows":rep,"total":tr,"missing_values":mr,"note":notes["repasses"]}; changed=changed or old_rep!=rep_data
    if not changed:
        print(json.dumps({"status":"SEM_ALTERACOES","changed":False,"generated_at":data.get("generated_at"),"fontes_alteradas":[]},ensure_ascii=False)); return
    stamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    data["generated_at"]=stamp
    data["source_updated_at"]=stamp[:10]
    data["status"]="drive_csv_sync_"+stamp[:10]
    diarias_ds["source_modified_at"]=stamp
    # Só grava após todos os arquivos serem baixados, interpretados e validados.
    # Escrita atômica evita JSON truncado se o processo for interrompido.
    atomic_json_write(DATA_PATH, data)
    atomic_json_write(REPASSES_PATH, rep_data)
    atomic_json_write(STATE_PATH, {"hashes":hashes})
    print(json.dumps({"status":"ATUALIZADO","changed":True,"generated_at":stamp,"fontes_alteradas":[k for k in hashes if hashes[k]!=prev.get("hashes",{}).get(k)],"fontes":{**{k:{"registros":len(v[0]),"total":v[1]} for k,v in updates.items()},"diarias":{"registros":len(diarias),"total":td}}},ensure_ascii=False))

if __name__=="__main__": main()
