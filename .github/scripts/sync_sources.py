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
SOURCE_KEYS = ("empenhos", "orcamentario", "ordens_bancarias", "repasses", "financeiro", "restos")
CACHE_PATH = ROOT / ".drive_source_ids.json"
def resolve_sources():
    if not CACHE_PATH.exists():
        raise RuntimeError("IDs das fontes não foram descobertos nesta execução; não usar IDs antigos.")
    ids = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(ids, dict) or set(ids) != set(SOURCE_KEYS) or len(set(ids.values())) != len(SOURCE_KEYS):
        raise RuntimeError("A descoberta não retornou exatamente seis IDs distintos.")
    return ids
SOURCES = resolve_sources()
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
    # Os seis itens são arquivos CSV listados na pasta pública do Drive.
    # O endpoint antigo /uc pode responder HTTP 400; tenta primeiro o endpoint
    # atual de download e mantém uma alternativa compatível.
    urls = [
        "https://drive.usercontent.google.com/download?id=" + urllib.parse.quote(file_id, safe="") + "&export=download&authuser=0&confirm=t",
        "https://drive.google.com/uc?export=download&id=" + urllib.parse.quote(file_id, safe=""),
    ]
    errors = []
    for url in urls:
        try:
            req=urllib.request.Request(url, headers={
                "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept":"text/csv,text/plain,application/octet-stream,*/*",
            })
            with urllib.request.urlopen(req,timeout=45) as r:
                b=r.read()
            try: s=b.decode("utf-8-sig")
            except UnicodeDecodeError: s=b.decode("cp1252",errors="replace")
            # Não aceitar páginas de erro/login como se fossem CSV.
            if re.search(r"<(?:!doctype|html|head|body|div|script|meta)\\b", s[:2000], re.I) or "accounts.google.com/ServiceLogin" in s:
                errors.append(url.split("?")[0] + ": resposta HTML/login, não CSV")
                continue
            nonempty = [line for line in s.splitlines() if line.strip()]
            if len(nonempty) < 2 and len(s.strip()) < 300:
                errors.append(url.split("?")[0] + ": resposta curta sem conteúdo CSV; caracteres=" + str(len(s)))
                continue
            s=s.replace(r"\\t","\\t").replace(r'\\\"','"')
            s=re.sub(r"\\\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),s)
            return s
        except Exception as exc:
            errors.append(url.split("?")[0] + ": " + str(exc))
    raise RuntimeError("Não foi possível baixar o CSV do Drive: " + " | ".join(errors))

def table(text, delimiter, tokens):
    # Algumas exportações do Drive mudam entre CSV, TSV e ponto-e-vírgula.
    # Detecta o delimitador real pelo cabeçalho esperado antes de interpretar os dados.
    candidates = [delimiter] + [d for d in (",", ";", "\t", "|") if d != delimiter]
    selected = None
    hi = None
    rows = []
    for candidate in candidates:
        parsed = list(csv.reader(io.StringIO(text), delimiter=candidate))
        # Algumas exportações do Drive entregam cada linha CSV como um único
        # campo contendo outra linha CSV. Detecta isso e interpreta uma segunda vez.
        if parsed and max((len(row) for row in parsed), default=0) <= 1:
            nested = []
            for row in parsed:
                cell = row[0] if row else ""
                try:
                    inner = next(csv.reader([cell], delimiter=candidate))
                except Exception:
                    inner = [cell]
                nested.append(inner if len(inner) > 1 else row)
            if max((len(row) for row in nested), default=0) > 1:
                parsed = nested
        for i, row in enumerate(parsed):
            joined = norm(" ".join(row))
            if len(row) > 3 and all(norm(t) in joined for t in tokens):
                selected, hi, rows = candidate, i, parsed
                break
        if selected is not None:
            break
    if hi is None:
        # Não registrar conteúdo financeiro bruto; apenas diagnóstico estrutural.
        first_line = next((line for line in text.splitlines() if line.strip()), "")
        raise ValueError("Cabeçalho não encontrado: " + str(tokens) +
                         "; delimitadores testados=" + repr(candidates) +
                         "; primeira linha chars=" + str(len(first_line)) +
                         "; primeira linha=" + repr(first_line[:160]) +
                         "; separadores=" + repr({d: first_line.count(d) for d in candidates}) +
                         "; linhas_com_colunas=" + repr([row[:18] for row in rows[:40] if len(row)>1][:8]) +
                         "; primeiras_linhas=" + repr([line[:180] for line in text.splitlines()[:12]]))
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

    a=table(src["empenhos"],"\t",["Favorecido do Empenho","Empenho","Saldo"])
    # O CSV oficial atual tem cinco campos nomeados; não atribuir valores a campos ausentes.
    empenhos=[{"empenho":r[1],"ne_ccor":"","subitem":r[2],"natureza":"",
               "cnpj":"","fornecedor":r[0],"observacao":"",
               "fonte_recursos_detalhada":r[4] if len(r)>4 else "",
               "saldo":money(r[6]) if len(r)>6 else None} for r in a]
    te=total(empenhos,"saldo")
    check(50<=len(empenhos)<=150 and all(r["saldo"] is not None for r in empenhos) and 1e6<=te<=30e6,
          f"Validação de Empenhos 2026 falhou: linhas={len(empenhos)}, total={te}")

    a=table(src["orcamentario"],",",["UG Responsável","Natureza Despesa Detalhada","Saldo"])
    # Estrutura confirmada no CSV oficial atual: 8 colunas; o relatório já não
    # contém PTRES nem os campos antigos de programa/unidade na mesma posição.
    orc=[{"ug":r[0],"unidade":r[4],"ptres":"","fonte":r[1],"descricao_fonte":r[2],
          "natureza_codigo":r[3],"natureza":r[3],"ug_responsavel":r[4],
          "responsavel":r[6] if len(r)>6 else "", "pi":r[5],"programa":"",
          "saldo":abs(money(r[7]) or 0)} for r in a]
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
        status_norm=norm(r[8]) if len(r)>8 else ""
        if "AGUARDANDOORCAMENTO" not in status_norm and "AGUARDANDOORAMENTO" not in status_norm: continue
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
    if not changed:
        print(json.dumps({"status":"SEM_ALTERACOES","changed":False,
          "generated_at":data.get("generated_at"),"fontes_alteradas":[],
          "mensagem":"As seis fontes foram lidas e validadas; nenhum conteúdo mudou."},ensure_ascii=False))
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
      "fontes_alteradas":changed_sources,"fontes":{
      "financeiro":{"registros":len(fin),"total":tf},"restos":{"registros":len(rap),"total":trp},
      "empenhos":{"registros":len(empenhos),"total":te},"orcamentario":{"registros":len(orc),"total":to},
      "repasses":{"registros":len(rep),"total":tr},"ordens_bancarias":{"registros":len(ob),"total_doc_valor":tob}
    }},ensure_ascii=False))
if __name__=="__main__": main()
