#!/usr/bin/env python3
"""Sincroniza as sete fontes CSV do Drive, valida registros e valores e atualiza data.json."""
import csv, hashlib, json, os, re, tempfile, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA_PATH=ROOT/"data.json"; REPASSES_PATH=ROOT/"repasses.json"; STATE_PATH=ROOT/"source_state.json"
CACHE_PATH=ROOT/".drive_source_ids.json"; DIARIAS_ID_PATH=ROOT/".diarias_source_id"
KEYS=("empenhos","orcamentario","ordens_bancarias","financeiro","restos","diarias","apropriacao_pendente")
AUDIT={}

def sources():
    if not CACHE_PATH.exists(): raise RuntimeError("IDs das fontes nÃ£o foram descobertos nesta execuÃ§Ã£o.")
    x=json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(x,dict) or set(x)!=set(KEYS) or len(set(x.values()))!=7:
        raise RuntimeError("A descoberta não retornou exatamente sete IDs distintos.")
    return x
SOURCES=sources()

def clean(v):
    s=str(v or "").replace("\ufeff","").strip()
    fixes={"Ãâ¡":"Ã","ÃÆ":"Ã","Ãâ°":"Ã","Ãâ":"Ã","ÃÅ¡":"Ã","ÃÂ£":"Ã£","ÃÂ§":"Ã§","ÃÂ¡":"Ã¡","ÃÂ©":"Ã©","ÃÂ­":"Ã­","ÃÂ³":"Ã³","ÃÂº":"Ãº","ÃÂª":"Ãª","ÃÂ´":"Ã´","ÃÂµ":"Ãµ"}
    for a,b in fixes.items(): s=s.replace(a,b)
    return s

def norm(v):
    s=unicodedata.normalize("NFKD",clean(v).upper().replace("Ã","C"))
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c))

def money(v):
    s=clean(v).replace("R$","").replace(" ","")
    if not s or s in {"-","â"}: return None
    neg=s.startswith("(") and s.endswith(")"); s=s.strip("()")
    if "," in s: s=s.replace(".","").replace(",",".")
    try: n=Decimal(s)
    except InvalidOperation: return None
    return float(-abs(n) if neg else n)

def decode_csv_bytes(raw):
    """Decodifica CSV do Drive respeitando BOM e sem substituir bytes invÃ¡lidos silenciosamente."""
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
        raise ValueError("CSV contÃ©m bytes NUL apÃ³s a decodificaÃ§Ã£o; codificaÃ§Ã£o inesperada.")
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
    raise RuntimeError("NÃ£o foi possÃ­vel baixar/decodificar o CSV do Drive: "+" | ".join(errors))
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
        raise ValueError(f"CabeÃ§alho nÃ£o encontrado: {tokens}; primeira linha={first[:180]!r}")
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

def parse_empenhos(text):
    """Interpreta o leiaute SERPRO atual de cinco colunas, sem número do processo."""
    a=table(text,"\t",["NE CCor","Saldo - Moeda Origem"])
    empenhos=[]
    for r in a:
        check(len(r)>=5, f"Registro incompleto em Empenhos 2026 (esperadas 5 colunas): {r!r}")
        v=money(r[4])
        check(v is not None, f"Saldo inválido em Empenhos 2026: {r!r}")
        empenhos.append({
            "empenho":r[0], "ne_ccor":r[0], "subitem":r[3], "natureza":r[3],
            "cnpj":r[1], "fornecedor":r[2], "observacao":"",
            "fonte_recursos_detalhada":"", "saldo":v
        })
    te=total(empenhos,"saldo")
    check(1<=len(empenhos)<=1000 and te>=0,
          f"Validação de Empenhos 2026 falhou: linhas={len(empenhos)}, total={te}")
    return empenhos,te



def parse_apropriacao_pendente(text):
    """Consolida por Documento Hábil: NFs e fontes são discriminadas, sem somar valores repetidos."""
    data_rows=table(text,",",["Documento Hábil","Nota Fiscal","Fonte Recursos Det.","Valor Bruto"])
    header=AUDIT[norm("Documento Hábil")]["header"]
    def idx(label):
        return next((i for i,h in enumerate(header) if norm(h)==norm(label)),None)
    doc_i=idx("Documento Hábil"); cnpj_i=idx("Fornecedor"); nf_i=idx("Nota Fiscal")
    source_i=idx("Fonte Recursos Det."); situation_i=idx("Situação da Despesa")
    amount_i=idx("Valor Bruto"); obs_i=idx("DH - Observação")
    required=[doc_i,cnpj_i,nf_i,source_i,situation_i,amount_i,obs_i]
    check(all(i is not None for i in required),"Cabeçalho incompleto em Apropriação Pendente de Pagamento.")
    check(max(cnpj_i+1,source_i+1,situation_i+1)<len(header),
          "Colunas descritivas ausentes em Apropriação Pendente de Pagamento.")
    groups={}
    for row in data_rows:
        check(len(row)>max(cnpj_i+1,source_i+1,situation_i+1,amount_i,obs_i),
              f"Registro incompleto em Apropriação Pendente de Pagamento: {row!r}")
        doc=clean(row[doc_i]); nf=clean(row[nf_i]); amount=money(row[amount_i])
        check(bool(doc and nf and clean(row[source_i]) and amount is not None),
              f"Documento, Nota Fiscal, fonte ou valor inválido em Apropriação Pendente: {row!r}")
        group=groups.setdefault(doc,{"amounts":set(),"nfs":set(),"sources":set(),
                                     "situations":set(),"cnpjs":set(),"suppliers":set(),
                                     "observations":set(),"source_rows":0})
        group["amounts"].add(round(amount,2)); group["nfs"].add(nf)
        group["cnpjs"].add(clean(row[cnpj_i])); group["suppliers"].add(clean(row[cnpj_i+1]))
        source=clean(row[source_i]); source_desc=clean(row[source_i+1])
        group["sources"].add(source + (" — "+source_desc if source_desc else ""))
        situation=clean(row[situation_i]); situation_desc=clean(row[situation_i+1])
        group["situations"].add(situation + (" — "+situation_desc if situation_desc else ""))
        if clean(row[obs_i]): group["observations"].add(clean(row[obs_i]))
        group["source_rows"]+=1
    result=[]
    for doc,group in groups.items():
        check(len(group["amounts"])==1,
              "Valores divergentes para o mesmo Documento Hábil "+doc+
              "; atualização bloqueada para evitar soma ou escolha arbitrária.")
        value=next(iter(group["amounts"]))
        result.append({
            "documento_habil":doc,
            "cnpj":" / ".join(sorted(x for x in group["cnpjs"] if x)),
            "fornecedor":" / ".join(sorted(x for x in group["suppliers"] if x)),
            "notas_fiscais_pendentes":", ".join(sorted(group["nfs"])),
            "quantidade_notas":len(group["nfs"]),
            "fontes_recursos":" | ".join(sorted(group["sources"])),
            "situacao_despesa":" | ".join(sorted(group["situations"])),
            "valor":value,
            "quantidade_linhas_origem":group["source_rows"],
            "observacao":" | ".join(sorted(group["observations"]))
        })
    result.sort(key=lambda r:r["documento_habil"])
    check(1<=len(result)<=5000,f"Quantidade inválida de Documentos Hábeis pendentes: {len(result)}")
    check(len({r["documento_habil"] for r in result})==len(result),
          "Documento Hábil repetido após consolidação; atualização bloqueada.")
    return result,total(result,"valor")


def atomic_json_write(path, payload):
    """Escreve JSON temporÃ¡rio e sÃ³ troca o destino apÃ³s gravaÃ§Ã£o completa."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    temp_path.replace(path)

def main():
    src={k:download(v) for k,v in SOURCES.items()}

    # Empenhos 2026: leiaute SERPRO com NE, processo, CNPJ, favorecido,
    # natureza de despesa detalhada e saldo (seis colunas).
    empenhos,te=parse_empenhos(src["empenhos"])

    # Saldo OrÃ§amentÃ¡rio SERPRO: sete campos (cÃ³digo/descriÃ§Ã£o para UG,
    # Fonte e Natureza, seguidos do saldo). O cabeÃ§alho contÃ©m cÃ©lulas vazias
    # entre os pares cÃ³digo/descriÃ§Ã£o; os registros mantÃªm sete posiÃ§Ãµes.
    a=table(src["orcamentario"],",",["UG Executora","Fonte Recursos Detalhada","Natureza Despesa","Saldo - Moeda Origem"])
    orc=[]
    for r in a:
        check(len(r)>=7, f"Registro incompleto em Saldo OrÃ§amentÃ¡rio (esperadas 7 colunas): {r!r}")
        v=money(r[6])
        check(v is not None, f"Saldo invÃ¡lido em Saldo OrÃ§amentÃ¡rio: {r!r}")
        orc.append({
            "ug":r[0], "unidade":r[1],
            "fonte":r[2], "descricao_fonte":r[3],
            "natureza_codigo":r[4], "natureza":r[5],
            "saldo":abs(v)
        })
    to=total(orc,"saldo"); check(1<=len(orc)<=500 and to>=0,f"ValidaÃ§Ã£o orÃ§amentÃ¡ria falhou: linhas={len(orc)}, total={to}")

    a=table(src["ordens_bancarias"],";",["DIA","OB","VALOR"])
    ob=[]
    for r in a:
        v=money(r[5] if len(r)>5 else None)
        check(v is not None, f"Valor invÃ¡lido em Ordens BancÃ¡rias: {r!r}")
        ob.append({"ob":r[1] if len(r)>1 else "", "data":r[0] if len(r)>0 else "", "data_pagamento":r[0] if len(r)>0 else "", "processo":r[2] if len(r)>2 else "", "cnpj":r[3] if len(r)>3 else "", "favorecido":r[4] if len(r)>4 else "", "observacao":r[6] if len(r)>6 else "", "valor":v})
    unique_obs={r["ob"] for r in ob}
    tob=total(ob,"valor"); check(1<=len(ob)<=10000 and all(r["valor"] is not None for r in ob) and all(r["ob"] for r in ob) and len(unique_obs)==len(ob),f"ValidaÃ§Ã£o de Ordens BancÃ¡rias falhou: linhas={len(ob)}, OBs Ãºnicas={len(unique_obs)}, total={tob}")
    # PublicaÃ§Ãµes Pagas: registros da mesma planilha cujo cÃ³digo do favorecido comeÃ§a com EX.
    # ExceÃ§Ã£o intencional: a OB 254463252012026OB000089 NÃO Ã© uma publicaÃ§Ã£o paga;
    # por isso foi retirada desta categoria e deve continuar excluÃ­da mesmo que o favorecido comece com EX.
    OB_NAO_E_PUBLICACAO = {"254463252012026OB000089"}
    pubs=[{"data":r["data"],"ob":r["ob"],"cnpj":r["cnpj"],"favorecido":r["favorecido"],"processo":r["processo"],"valor":r["valor"],"observacao":r["observacao"]} for r in ob if norm(r["cnpj"]).startswith("EX") and r["ob"] not in OB_NAO_E_PUBLICACAO]
    tp=total(pubs,"valor")

    fl=[]
    for line in src["financeiro"].splitlines():
        try: fl.append(next(csv.reader([line],delimiter=",")))
        except Exception: fl.append([line])
    hi=next((i for i,r in enumerate(fl) if len(r)>=6 and norm(r[0])==norm("UG Executora") and norm(r[1])==norm("Fonte Recursos Detalhada") and "VINCULACAO" in norm(r[3]) and "PAGAMENTO" in norm(r[3])),None)
    check(hi is not None,"CabeÃ§alho oficial do Saldo Financeiro nÃ£o encontrado.")
    fin=[]
    for raw in fl[hi+1:]:
        r=[clean(x) for x in raw]
        if len(r)<7 or not r[0] or not r[1] or not norm(r[5]).startswith("SALDOMOEDAORIGEM"): continue
        v=money(r[6]); check(v is not None and r[3],"Saldo financeiro invÃ¡lido ou sem vinculaÃ§Ã£o.")
        fin.append({"uge":r[0],"unidade":"IOC","fonte":r[1],"vinculo":r[3],"saldo":abs(v)})
    tf=total(fin,"saldo"); check(1<=len(fin)<=100 and all(x["vinculo"] for x in fin),f"ValidaÃ§Ã£o do saldo financeiro falhou: linhas={len(fin)}, total={tf}")

    a=table(src["restos"],",",["Empenho","Saldo"]); rap=[]
    for r in a:
        v=money(r[-1]) if r else None
        check(v is not None, f"Saldo invÃ¡lido em Restos a Pagar: {r!r}")
        if abs(v)<0.005: continue
        rap.append({"empenho":r[0],"cnpj":"","fornecedor":r[1] if len(r)>1 else "","pi":"","programa":"","autor_emenda":"","natureza_codigo":r[2] if len(r)>2 else "","natureza":r[3] if len(r)>3 else "","saldo":v})
    trp=total(rap,"saldo"); check(1<=len(rap)<=1000 and trp>=0,f"ValidaÃ§Ã£o de Restos a Pagar falhou: linhas={len(rap)}, total={trp}")

    # DiÃ¡rias Pagas: fonte SERPRO separada, localizada pelo nome na pasta oficial do Drive.
    dl=src["diarias"].splitlines()
    dhi=next((i for i,line in enumerate(dl) if "Favorecido Doc." in line and "OB - Valor Linha" in line),None)
    check(dhi is not None,"CabeÃ§alho oficial de DIARIAS PAGAS.csv nÃ£o encontrado.")
    diarias=[]
    for r in csv.reader(dl[dhi+1:],delimiter="\t"):
        if not r or not any(clean(x) for x in r): continue
        if clean(r[0]).upper()=="TOTAL": continue
        check(len(r)>=6, f"Registro incompleto em DIARIAS PAGAS.csv: {r!r}")
        v=money(r[3])
        check(v is not None, f"Valor invÃ¡lido em DIARIAS PAGAS.csv: {r!r}")
        diarias.append({"favorecido":clean(r[0]),"data_pagamento":clean(r[1]),"classificacao_orcamentaria":clean(r[2]),"valor":v,"documento":clean(r[4]),"observacao":clean(r[5])})
    td=total(diarias,"valor")
    check(1<=len(diarias)<=1000 and all(r["favorecido"] for r in diarias),f"ValidaÃ§Ã£o de DiÃ¡rias Pagas falhou: linhas={len(diarias)}, total={td}")

    apropriacao,ta=parse_apropriacao_pendente(src["apropriacao_pendente"])
    updates={"financeiro":(fin,tf),"restos":(rap,trp),"empenhos":(empenhos,te),"orcamentario":(orc,to),"ordens_bancarias":(ob,tob),"apropriacao_pendente":(apropriacao,ta)}
    data=json.loads(DATA_PATH.read_text(encoding="utf-8")); data["datasets"]=[d for d in data.get("datasets",[]) if d.get("id")!="documentos_habeis_pendentes"]
    ds={d.get("id"):d for d in data.get("datasets",[])}; check(all(k in ds for k in updates) and "diarias_pagas" in ds,"Dataset esperado ausente em data.json")
    def brl(x): return f"{x:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    notes={
      "financeiro":f"Extração do SIAFI. Cada linha mantém sua própria Vinculação Pagamento. {len(fin)} registros. Total detalhado: R$ {brl(tf)}.",
      "restos":f"Fonte SIAFI: Restos a Pagar. {len(rap)} registros com saldo diferente de zero. Total detalhado: R$ {brl(trp)}.",
      "empenhos":f"Fonte SIAFI: Saldo nos empenhos 2026. {len(empenhos)} registros detalhados. Total: R$ {brl(te)}.",
      "orcamentario":f"Fonte oficial: Saldo Orçamentário.csv. {len(orc)} registros detalhados. Total: R$ {brl(to)}.",
      "repasses":"Fonte: SAORC/PLANEJAMENTO IOC. Aguardando Orçamento da COGEAD.",
      "ordens_bancarias":f"Fonte: ORDEM BANCARIAS EMITIDAS.csv. {len(ob)} registros únicos por OB, sem coluna Fonte. Total Valor (R$): R$ {brl(tob)}.",
       "apropriacao_pendente":f"Fonte: Apropriação Pendente de Pagamento.csv. {len(apropriacao)} documentos hábeis consolidados em {sum(r['quantidade_linhas_origem'] for r in apropriacao)} linhas de origem. Notas fiscais e fontes são discriminadas; valores repetidos por documento hábil são contabilizados uma única vez. Total: R$ {brl(ta)}.",
    }
    diarias_note=f"Diárias Pagas: {len(diarias)} registros da planilha DIARIAS PAGAS.csv. Total: R$ {brl(td)}."
    diarias_url="https://drive.google.com/file/d/"+SOURCES["diarias"]+"/view"
    diarias_ds=ds["diarias_pagas"]
    diarias_changed=(diarias_ds.get("rows")!=diarias or diarias_ds.get("total")!=td or diarias_ds.get("note")!=diarias_note or diarias_ds.get("source_url")!=diarias_url or diarias_ds.get("source_name")!="DIARIAS PAGAS.csv")
    diarias_ds["rows"]=diarias; diarias_ds["total"]=td; diarias_ds["detail_count"]=len(diarias); diarias_ds["source_url"]=diarias_url; diarias_ds["source_name"]="DIARIAS PAGAS.csv"; diarias_ds["note"]=diarias_note
    hashes={k:hashlib.sha256(v.encode("utf-8")).hexdigest() for k,v in src.items()}; prev=json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    source_changed=hashes!=prev.get("hashes",{})
    for k,(rows,amount) in updates.items():
        ds[k]["rows"]=rows; ds[k]["total"]=amount; ds[k]["detail_count"]=len(rows); ds[k]["source_url"]="https://drive.google.com/file/d/"+SOURCES[k]+"/view"; ds[k]["note"]=notes[k]
    ds["financeiro"]["source_name"]="Saldo Financeiro"
    pub=ds.get("publicacoes_pagas",{}); pub_note=f"PublicaÃ§Ãµes Pagas: {len(pubs)} registros da planilha de Ordens BancÃ¡rias, filtrados pelo cÃ³digo do favorecido iniciado por EX. Total: R$ {brl(tp)}."; pub_url="https://drive.google.com/file/d/"+SOURCES["ordens_bancarias"]+"/view"; pub_changed=pub.get("rows")!=pubs or pub.get("total")!=tp or pub.get("note")!=pub_note or pub.get("source_url")!=pub_url; pub["rows"]=pubs; pub["total"]=tp; pub["detail_count"]=len(pubs); pub["source_url"]=pub_url; pub["source_name"]="ORDEM BANCARIAS EMITIDAS.csv"; pub["note"]=pub_note
    ds["ordens_bancarias"]["source_name"]="ORDEM BANCARIAS EMITIDAS.csv"
    ds["apropriacao_pendente"]["source_name"]="Apropriação Pendente de Pagamento.csv"
    changed=source_changed or pub_changed or diarias_changed or any(ds[k].get("rows")!=rows or ds[k].get("total")!=amount or ds[k].get("note")!=notes[k] for k,(rows,amount) in updates.items())
    if not changed:
        print(json.dumps({"status":"SEM_ALTERACOES","changed":False,"generated_at":data.get("generated_at"),"fontes_alteradas":[]},ensure_ascii=False)); return
    stamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    data["generated_at"]=stamp
    data["source_updated_at"]=stamp[:10]
    data["status"]="drive_csv_sync_"+stamp[:10]
    diarias_ds["source_modified_at"]=stamp
    # SÃ³ grava apÃ³s todos os arquivos serem baixados, interpretados e validados.
    # Escrita atÃ´mica evita JSON truncado se o processo for interrompido.
    atomic_json_write(DATA_PATH, data)
    atomic_json_write(STATE_PATH, {"hashes":hashes})
    print(json.dumps({"status":"ATUALIZADO","changed":True,"generated_at":stamp,"fontes_alteradas":[k for k in hashes if hashes[k]!=prev.get("hashes",{}).get(k)],"fontes":{**{k:{"registros":len(v[0]),"total":v[1]} for k,v in updates.items()},"diarias":{"registros":len(diarias),"total":td}}},ensure_ascii=False))

if __name__=="__main__": main()
