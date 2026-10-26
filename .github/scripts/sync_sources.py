#!/usr/bin/env python3
"""Sincroniza as seis fontes CSV do Drive, valida os dados e atualiza data.json."""
import csv, hashlib, io, json, os, re, unicodedata, urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data.json"
REPASSES_PATH = ROOT / "repasses.json"
STATE_PATH = ROOT / "source_state.json"
SOURCES = {
    "empenhos": "137jwUw2WB_LUvnQef6waE8ASKQEvzhup",
    "orcamentario": "1k3dZ890WgqGVSCZLwCxGPLikMutTlOfN",
    "ordens_bancarias": "1lRYujrJRv7ZPam-lYVB2CxCg_WEMbraC",
    "repasses": "1ghcBkPmT-IkfWozLZVDdMvMe7eoD2J6k",
    "financeiro": "1p4PyHEkV5YzIljLeMsHopulzN55yQMqzS6fk56STdEk",
    "restos": "1zzxhemDKryzolkykFSw3JXph1YcQ2pUj",
}
MOJI = {"Ã‡":"Ç","Ãƒ":"Ã","Ã‰":"É","Ã“":"Ó","Ãš":"Ú","Ã£":"ã","Ã§":"ç",
        "Ã¡":"á","Ã©":"é","Ã­":"í","Ã³":"ó","Ãº":"ú","Ãª":"ê","Ã´":"ô","Ãµ":"õ"}

def clean(v):
    s = str(v or "").replace("\ufeff","").strip()
    for a,b in MOJI.items(): s=s.replace(a,b)
    return s

def norm(v):
    s=clean(v).upper().replace("Ç","C")
    s=unicodedata.normalize("NFKD",s)
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c))

def money(v):
    s=clean(v).replace("R$","").replace(" ","")
    if not s or s in {"-","—"}: return None
    neg=s.startswith("(") and s.endswith(")")
    s=s.strip("()")
    if "," in s: s=s.replace(".","").replace(",",".")
    try: n=Decimal(s)
    except InvalidOperation: return None
    return float(-abs(n) if neg else n)

def download(file_id):
    if file_id == SOURCES["financeiro"]:
        # Usa a planilha Google Sheets atual, não a cópia CSV desatualizada.
        url = "https://docs.google.com/spreadsheets/d/" + file_id + "/export?format=csv&gid=1275876733"
    else:
        url = "https://drive.google.com/uc?export=download&id=" + file_id
    req=urllib.request.Request(url, headers={"User-Agent":"IOC-Dashboard-Sync/1.0"})
    with urllib.request.urlopen(req,timeout=45) as r: b=r.read()
    try: s=b.decode("utf-8-sig")
    except UnicodeDecodeError: s=b.decode("cp1252",errors="replace")
    # Alguns relatórios SIAFI guardam delimitadores/caracteres como sequências escapadas.
    s=s.replace(r"\t","\t").replace(r'\"','"')
    s=re.sub(r"\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),s)
    return s

def table(text, delimiter, tokens):
    rows=list(csv.reader(io.StringIO(text),delimiter=delimiter))
    hi=None
    for i,row in enumerate(rows[:20]):
        joined=norm(" ".join(row))
        if len(row)>3 and all(norm(t) in joined for t in tokens): hi=i; break
    if hi is None: raise ValueError("Cabeçalho não encontrado: "+str(tokens))
    header=[clean(v) for v in rows[hi]]
    data=[]
    for row in rows[hi+1:]:
        if not row or not any(clean(v) for v in row) or norm(row[0])=="TOTAL": continue
        row=[clean(v) for v in row]
        if len(row)<len(header): row += [""]*(len(header)-len(row))
        data.append(row[:len(header)])
    return data

def total(rows,key): return round(sum(float(r.get(key) or 0) for r in rows),2)
def check(ok,msg):
    if not ok: raise ValueError(msg)

def main():
    src={k:download(v) for k,v in SOURCES.items()}

    a=table(src["empenhos"],"\t",["Conta Corrente","Saldo"])
    empenhos=[{"empenho":r[0],"ne_ccor":r[1],"subitem":r[2],"natureza":r[3],
               "cnpj":r[4],"fornecedor":r[5],"observacao":r[6],"saldo":money(r[7])} for r in a]
    te=total(empenhos,"saldo")
    check(50<=len(empenhos)<=150 and all(r["saldo"] is not None for r in empenhos) and 1e6<=te<=30e6,
          f"Validação de Empenhos 2026 falhou: linhas={len(empenhos)}, total={te}")

    a=table(src["orcamentario"],",",["UG Executora","PTRES","Saldo"])
    orc=[{"ug":r[0],"unidade":r[1],"ptres":r[2],"fonte":r[3],"descricao_fonte":r[4],
          "natureza_codigo":r[5],"natureza":r[6],"ug_responsavel":r[7],"responsavel":r[8],
          "pi":r[9],"programa":r[10],"saldo":abs(money(r[11]) or 0)} for r in a]
    to=total(orc,"saldo")
    check(5<=len(orc)<=50 and 1e5<=to<=10e6,f"Validação orçamentária falhou: linhas={len(orc)}, total={to}")

    a=table(src["ordens_bancarias"],",",["Ordem Bancária","Doc - Valor"])
    ob=[{"uge":r[0],"unidade":r[1],"ob":r[2],"data":r[3],"cnpj":r[4],"favorecido":r[5],
         "processo":r[6],"fonte":r[7],"descricao_fonte":r[8],"observacao":r[9],
         "valor":money(r[10]),"movimentacao_liquida":money(r[11]) or 0,"data_pagamento":r[3]} for r in a]
    tob=total(ob,"valor")
    check(500<=len(ob)<=1500 and all(r["valor"] is not None for r in ob) and 1e7<=tob<=2e8,
          f"Validação de Ordens Bancárias falhou: linhas={len(ob)}, Doc - Valor={tob}")

    a=table(src["repasses"],";",["PROCESSO","STATUS DO EMPENHO","VALOR"])
    rep=[]
    for r in a:
        if norm(r[8]) not in {"AGUARDANDOORCAMENTO","AGUARDANDOORAMENTO"}: continue
        rep.append({"processo":r[0],"licitacao":r[1],"fornecedor":r[9],"sub_grupo":r[3],
                    "elemento_despesa":r[1],"elemento":r[2],"sub_grupo_despesa":r[3],
                    "vigencia":r[4],"situacao_prioridade":r[5],"solicitacao_ne":r[6],
                    "numero_ne":r[7],"status_empenho":r[8],"fornecedores":r[9],"saldo":money(r[10])})
    tr=total(rep,"saldo"); mr=sum(r["saldo"] is None for r in rep)
    check(50<=len(rep)<=150 and tr>=1.5e6 and mr<=5,
          f"Validação de repasses falhou: linhas={len(rep)}, total={tr}, sem valor={mr}")

    a=table(src["financeiro"],",",["UGE","Fonte Detalhada","Total"])
    fin=[{"uge":r[0],"unidade":r[1],"fonte":r[2],"vinculo":r[3],"saldo":money(r[5])} for r in a]
    tf=total(fin,"saldo")
    check(1<=len(fin)<=20 and all(r["saldo"] is not None for r in fin) and 1e5<=abs(tf)<=2e6,
          f"Validação do saldo financeiro falhou: linhas={len(fin)}, total={tf}")

    # Diagnóstico temporário: compara a antiga referência CSV com a planilha atual
    # para localizar a origem da divergência informada, sem usar a referência antiga no painel.
    finance_alternative = {"id":"1ktsiJGTRiWZf83uu5tKtNmErKyAbqyfo"}
    try:
        old_text=download(finance_alternative["id"])
        old_rows=table(old_text,",",["UGE","Fonte Detalhada","Total"])
        old_fin=[{"saldo":money(r[5])} for r in old_rows]
        finance_alternative.update({"registros":len(old_fin),"total":total(old_fin,"saldo"),"status":"LIDA"})
    except Exception as exc:
        finance_alternative.update({"status":"ERRO","erro":str(exc)[:250]})

    a=table(src["restos"],",",["NE CCor","Saldo"])
    rap=[]
    for r in a:
        v=money(r[10])
        if v is None or abs(v)<0.005: continue
        rap.append({"empenho":r[0],"cnpj":r[1],"fornecedor":r[2],"pi":r[3],"programa":r[4],
                    "autor_emenda":r[5],"natureza_codigo":r[7],"natureza":r[8],"saldo":v})
    trp=total(rap,"saldo")
    check(10<=len(rap)<=100 and 1e6<=trp<=15e6,
          f"Validação de Restos a Pagar falhou: linhas={len(rap)}, total={trp}")

    updates={"financeiro":(fin,tf),"restos":(rap,trp),"empenhos":(empenhos,te),
             "orcamentario":(orc,to),"repasses":(rep,tr),"ordens_bancarias":(ob,tob)}
    data=json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # Remove permanentemente a base descontinuada, inclusive em futuras sincronizações.
    obsolete_dataset_present=any(d.get("id")=="documentos_habeis_pendentes" for d in data.get("datasets",[]))
    data["datasets"]=[d for d in data.get("datasets",[]) if d.get("id")!="documentos_habeis_pendentes"]
    ds={d.get("id"):d for d in data.get("datasets",[])}
    check(all(k in ds for k in updates),"Dataset esperado ausente em data.json")

    # Compara o conteúdo bruto das seis fontes e os dados derivados do painel.
    # O estado só é persistido depois de uma publicação bem-sucedida pelo workflow.
    source_hashes={k:hashlib.sha256(v.encode("utf-8")).hexdigest() for k,v in src.items()}
    previous_state=json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    source_changed=source_hashes != previous_state.get("hashes",{})
    dataset_changed=obsolete_dataset_present or any(
        ds[k].get("rows") != rows or ds[k].get("total") != amount or
        ds[k].get("detail_count") != len(rows)
        for k,(rows,amount) in updates.items()
    ) or ds["financeiro"].get("source_name") != "Saldo Financeiro" or ds["financeiro"].get("source_url") != "https://docs.google.com/spreadsheets/d/" + SOURCES["financeiro"] + "/edit"
    rep_data={"rows":rep,"total":tr,"missing_values":mr,
              "note":""}
    old_rep=json.loads(REPASSES_PATH.read_text(encoding="utf-8")) if REPASSES_PATH.exists() else {}
    repasses_changed=any(old_rep.get(k) != rep_data.get(k) for k in ("rows","total","missing_values","note"))
    changed=source_changed or dataset_changed or repasses_changed

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as out:
            out.write("changed="+("true" if changed else "false")+"\n")
    def row_fingerprint(rows):
        # Normaliza inteiros e floats para evitar falso positivo (ex.: 15000 vs 15000.0).
        def canonical(v):
            if isinstance(v, dict): return {k:canonical(x) for k,x in v.items()}
            if isinstance(v, list): return [canonical(x) for x in v]
            if isinstance(v, (int,float)) and not isinstance(v, bool): return float(v)
            return v
        hashes = sorted(hashlib.sha256(json.dumps(canonical(r), ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest() for r in rows)
        return hashlib.sha256("\\n".join(hashes).encode("utf-8")).hexdigest()

    source_report = {
        "financeiro": {"registros":len(fin),"total":tf,"rows_hash":row_fingerprint(fin),
                       "diagnostico_referencia_anterior":finance_alternative},
        "restos": {"registros":len(rap),"total":trp,"rows_hash":row_fingerprint(rap)},
        "empenhos": {"registros":len(empenhos),"total":te,"rows_hash":row_fingerprint(empenhos)},
        "orcamentario": {"registros":len(orc),"total":to,"rows_hash":row_fingerprint(orc)},
        "repasses": {"registros":len(rep),"total":tr,"rows_hash":row_fingerprint(rep)},
        "ordens_bancarias": {"registros":len(ob),"total":tob,"rows_hash":row_fingerprint(ob)}
    }
    if not changed:
        print(json.dumps({"status":"SEM_ALTERACOES","changed":False,
          "generated_at":data.get("generated_at"),"fontes_alteradas":[],
          "fontes":source_report,
          "mensagem":"As seis fontes originais foram lidas, analisadas e comparadas; nenhum conteúdo mudou."},ensure_ascii=False))
        return

    changed_sources=[k for k in source_hashes if source_hashes.get(k) != previous_state.get("hashes",{}).get(k)]
    stamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    for k,(rows,amount) in updates.items():
        ds[k]["rows"]=rows; ds[k]["total"]=amount; ds[k]["detail_count"]=len(rows)
    ds["financeiro"]["source_name"]="Saldo Financeiro"
    ds["financeiro"]["source_url"]="https://docs.google.com/spreadsheets/d/" + SOURCES["financeiro"] + "/edit"
    ds["repasses"]["missing_values"]=mr
    ds["repasses"]["note"]=""
    data["generated_at"]=stamp
    # Nenhum arquivo de saída é alterado até que todas as seis fontes passem nas validações.
    DATA_PATH.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    REPASSES_PATH.write_text(json.dumps(rep_data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    STATE_PATH.write_text(json.dumps({"hashes":source_hashes},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"status":"ATUALIZADO","changed":True,"generated_at":stamp,
      "fontes_alteradas":changed_sources,"fontes":source_report},ensure_ascii=False))
if __name__=="__main__": main()
