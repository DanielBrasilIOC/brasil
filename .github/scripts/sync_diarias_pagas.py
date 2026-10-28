#!/usr/bin/env python3
"""Valida e integra Diárias Pagas sem publicar arquivos incompletos."""
import csv, json, os, re, tempfile, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data.json"

def decode_csv(raw):
    if raw.startswith((b"\\xff\\xfe", b"\\xfe\\xff")):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\\xef\\xbb\\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")
    if "\\x00" in text:
        raise ValueError("CSV de diárias contém bytes NUL após a decodificação.")
    if re.search(r"<(?:!doctype|html|head|body|script|meta)\\b", text[:2000], re.I):
        raise ValueError("O Drive retornou HTML em vez do CSV de diárias.")
    return text

def brl(value):
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def main():
    fid = os.environ.get("DRIVE_FILE_ID", "").strip()
    if not fid:
        raise RuntimeError("ID da fonte de diárias não foi resolvido por nome.")
    errors = []
    text = None
    for url in [f"https://drive.usercontent.google.com/download?id={fid}&export=download&authuser=0&confirm=t", f"https://drive.google.com/uc?export=download&id={fid}"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv,text/plain,application/octet-stream,*/*"})
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read()
            text = decode_csv(raw)
            if not text.strip():
                raise ValueError("CSV de diárias vazio.")
            break
        except Exception as exc:
            errors.append(str(exc))
            text = None
    if text is None:
        raise RuntimeError("Não foi possível baixar/decodificar DIARIAS PAGAS.csv: " + " | ".join(errors))
    lines = text.splitlines()
    hi = next((i for i, line in enumerate(lines) if "Favorecido Doc." in line and "OB - Valor Linha" in line), None)
    if hi is None:
        raise RuntimeError("Cabeçalho oficial de DIARIAS PAGAS não encontrado; publicação bloqueada.")
    rows = []
    for row in csv.reader(lines[hi + 1:], delimiter="\\t"):
        if not row or not any(str(value).strip() for value in row):
            continue
        if row[0].strip().upper() == "TOTAL":
            continue
        if len(row) < 6:
            raise RuntimeError(f"Registro incompleto em DIARIAS PAGAS: {row!r}")
        raw_value = row[3].replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            value = round(float(raw_value), 2)
        except Exception as exc:
            raise RuntimeError(f"Valor inválido em DIARIAS PAGAS: {row!r}") from exc
        rows.append({"favorecido": row[0].strip(), "data_pagamento": row[1].strip(), "classificacao_orcamentaria": row[2].strip(), "valor": value, "documento": row[4].strip(), "observacao": row[5].strip()})
    if not rows:
        raise RuntimeError("DIARIAS PAGAS foi lida, mas nenhum registro válido foi encontrado.")
    total = round(sum(row["valor"] for row in rows), 2)
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    existing = next((d for d in data.get("datasets", []) if d.get("id") == "diarias_pagas"), None)
    comparable = {"id": "diarias_pagas", "title": "Diárias Pagas", "short": "Diárias Pagas", "source_name": "DIARIAS PAGAS.csv", "source_url": f"https://drive.google.com/file/d/{fid}/view", "total": total, "detail_count": len(rows), "rows": rows}
    if existing and all(existing.get(k) == v for k, v in comparable.items()):
        print(f"SEM ALTERAÇÕES: Diárias Pagas; {len(rows)} registros; total R$ {brl(total)}.")
        return
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    dataset = dict(comparable)
    dataset["source_modified_at"] = stamp
    data["datasets"] = [d for d in data.get("datasets", []) if d.get("id") != "diarias_pagas"] + [dataset]
    data["generated_at"] = stamp
    data["source_updated_at"] = stamp[:10]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ROOT, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False, separators=(",", ":"))
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    temp_path.replace(DATA_PATH)
    print(f"ATUALIZADO: Diárias Pagas; {len(rows)} registros; total R$ {brl(total)}.")

if __name__ == "__main__":
    main()
