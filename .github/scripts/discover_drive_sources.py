#!/usr/bin/env python3
"""Localiza as seis fontes oficiais do painel pelo nome dentro da pasta do Drive.

O ID do arquivo pode mudar quando um CSV é apagado e reenviado. Por isso, a
regra de produção é: pasta oficial + nome exato normalizado. IDs antigos nunca
são usados como fonte de verdade.
"""
import html
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".drive_source_ids.json"
FOLDER_DEFAULT = "1Ae3_31uGRNvfvnN5euhiNHbk_mdkVg0L"

EXPECTED_NAMES = {
    "empenhos": ("Saldo nos empenhos 2026.csv",),
    "orcamentario": ("Saldo Orçamentário.csv",),
    "ordens_bancarias": ("ORDEM BANCARIAS EMITIDAS.csv",),
    "repasses": ("Aguardando Repasse Orçamentário.csv",),
    "financeiro": ("Saldo Financeiro.csv",),
    "restos": ("Restos a Pagar.csv",),
}

EXTRA_EXPECTED_NAMES = ("DIARIAS PAGAS.csv",)

# IDs do estado anterior são mantidos apenas para histórico/debug; nunca são
# utilizados automaticamente para substituir uma descoberta por nome.
OLD_IDS = {
    "empenhos": "1pDEGc2LAz0fe7c4GH5fh-kzgeW0iuQHh",
    "orcamentario": "1gQYnGiF2zLdCOR-iiW5ptNc-3fXdNuMy",
    "ordens_bancarias": "1dTM5GfqVD63wNf2QYhOydEDd6g1Ca8rU",
    "repasses": "1h7oF_blPx6RpuHsCjPshW-zn7IcNHGB-",
    "financeiro": "10ghNRMaUWvaOcX3q8luLTn9CZ2_z4RSQ",
    "restos": "1CIAIW9t9cKAnu-iUlQJpGUx_sfalHyuu",
}


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def validate_ids(ids):
    if not isinstance(ids, dict) or set(ids) != set(EXPECTED_NAMES):
        raise ValueError("Não foram resolvidas exatamente as seis fontes esperadas")
    if not all(isinstance(v, str) and v.strip() for v in ids.values()):
        raise ValueError("Foi encontrado ID vazio ou inválido")
    if len(set(ids.values())) != len(EXPECTED_NAMES):
        raise ValueError("Duas fontes apontam para o mesmo ID; publicação bloqueada")
    return ids


def select_sources(files, folder_id):
    """Resolve fontes por nome dentro de uma pasta; usado também pelos testes."""
    found = {}
    for item in files:
        if folder_id not in (item.get("parents") or []):
            continue
        if item.get("mimeType") != "text/csv":
            continue
        name = normalize(item.get("name"))
        for key, expected in EXPECTED_NAMES.items():
            if name in {normalize(x) for x in expected}:
                found.setdefault(key, []).append(item.get("id"))
    errors = []
    for key, expected in EXPECTED_NAMES.items():
        values = found.get(key, [])
        if len(values) != 1:
            errors.append(f"{expected[0]}: encontrados {len(values)}, esperado 1.")
    if errors:
        raise ValueError("; ".join(errors))
    return validate_ids({key: values[0] for key, values in found.items()})


def fetch_folder_page(folder_id):
    """Tenta endpoints públicos do Drive e só retorna HTML com evidência da pasta."""
    folder = urllib.parse.quote(folder_id, safe="")
    urls = [
        "https://drive.google.com/embeddedfolderview?id=" + folder + "#list",
        "https://drive.google.com/drive/folders/" + folder + "?usp=sharing",
        "https://drive.google.com/drive/folders/" + folder,
        "https://drive.google.com/drive/u/0/folders/" + folder,
    ]
    errors = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=45) as response:
                body = response.read()
                final_url = response.geturl()
                status = response.status
            text = body.decode("utf-8", errors="replace")
            if status != 200 or not body:
                errors.append(f"{url}: HTTP {status}")
                continue
            if "accounts.google.com" in final_url or "ServiceLogin" in final_url:
                errors.append(f"{url}: redirecionou para login")
                continue
            if folder_id not in text and "flip-entry" not in text:
                errors.append(f"{url}: resposta sem identificador/listagem da pasta")
                continue
            return html.unescape(text)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("Não foi possível ler a listagem pública da pasta do Drive. " + " | ".join(errors))


def extract_folder_files(page, folder_id):
    """Extrai os IDs dos CSVs da listagem pública simplificada do Drive."""
    files = []
    all_expected_names = [name for values in EXPECTED_NAMES.values() for name in values] + list(EXTRA_EXPECTED_NAMES)
    # A visualização embeddedfolderview agrupa cada arquivo em um bloco flip-entry.
    starts = [m.start() for m in re.finditer(r"""<div\b[^>]*class=["']flip-entry["']""", page, re.I)]
    if starts:
        chunks = [page[pos:(starts[i + 1] if i + 1 < len(starts) else len(page))] for i, pos in enumerate(starts)]
        for chunk in chunks:
            title_match = re.search(
                r'class=["\'][^"\']*flip-entry-title[^"\']*["\'][^>]*>(.*?)</',
                chunk, re.I | re.S
            )
            if not title_match:
                continue
            name = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
            if normalize(name) not in {normalize(n) for n in all_expected_names}:
                continue
            # O HTML público atual do Drive identifica cada linha como id="entry-<FILE_ID>".
            # As variantes antigas usavam /file/d/<ID> ou ?id=<ID>.
            id_match = re.search(r"""\bid=["']entry-([A-Za-z0-9_-]{20,80})["']""", chunk, re.I)
            if not id_match:
                id_match = re.search(r'/file/d/([A-Za-z0-9_-]{20,80})', chunk, re.I)
            if not id_match:
                id_match = re.search(r'[?&]id=([A-Za-z0-9_-]{20,80})', chunk, re.I)
            if not id_match:
                continue
            file_id = id_match.group(1)
            files.append({
                "id": file_id,
                "name": name,
                "mimeType": "text/csv",
                "parents": [folder_id],
            })
        return files

    # Fallback para variações de HTML: só aceita IDs próximos ao nome exato,
    # e mantém candidatos múltiplos para que a validação bloqueie ambiguidades.
    decoded = page.replace(r"\u0026", "&").replace(r"\u003d", "=").replace(r"\"", '"')
    id_pattern = re.compile(r"[A-Za-z0-9_-]{20,80}")
    for expected in all_expected_names:
        positions = [m.start() for m in re.finditer(re.escape(expected), decoded, re.I)]
        candidates = []
        for pos in positions:
            window = decoded[max(0, pos - 300):pos + 300]
            for candidate in id_pattern.findall(window):
                if candidate != folder_id and candidate not in candidates:
                    candidates.append(candidate)
        for candidate in candidates:
            files.append({"id": candidate, "name": expected, "mimeType": "text/csv", "parents": [folder_id]})
    return files

def discover_source_ids():
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", FOLDER_DEFAULT).strip()
    if not folder_id:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID vazio")
    page = fetch_folder_page(folder_id)
    files = extract_folder_files(page, folder_id)
    try:
        ids = select_sources(files, folder_id)
        diarias = [item for item in files
                   if normalize(item.get("name")) == normalize("DIARIAS PAGAS.csv")
                   and folder_id in (item.get("parents") or [])]
        if len(diarias) != 1:
            raise ValueError(f"DIARIAS PAGAS.csv: encontrados {len(diarias)}, esperado exatamente 1.")
        diarias_id = str(diarias[0].get("id") or "").strip()
        if not diarias_id:
            raise ValueError("DIARIAS PAGAS.csv: ID vazio.")
        (ROOT / ".diarias_source_id").write_text(diarias_id + "\n", encoding="utf-8")
    except ValueError as exc:
        # Diagnóstico seguro para descobrir qual variante de página o Drive está servindo.
        expected_names = [name for values in EXPECTED_NAMES.values() for name in values]
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        diagnostics = {
            "html_chars": len(page),
            "embedded_entries": len(re.findall(r"flip-entry", page, re.I)),
            "expected_names_found": {name: (name.casefold() in html.unescape(page).casefold()) for name in expected_names},
            "has_drive_folder_marker": folder_id in page,
            "has_login_marker": bool(re.search(r"ServiceLogin|accounts\\.google\\.com", page, re.I)),
            "title": (title_match.group(1)[:180] if title_match else "(sem título)"),
            "sample_around_saldo": [
                html.unescape(page[max(0, m.start()-100):m.start()+220]).replace("\n", " ")[:320]
                for m in list(re.finditer("Saldo", page, re.I))[:3]
            ],
        }
        raise ValueError(f"{exc} Diagnóstico da página: {json.dumps(diagnostics, ensure_ascii=False)}")
    CACHE.write_text(json.dumps(ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ids


def main():
    ids = discover_source_ids()
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    message = "Seis fontes localizadas pelo nome dentro da pasta oficial do Drive; os IDs foram resolvidos nesta execução."
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Fontes oficiais do Drive\n\n")
            out.write("- **Status:** FONTES_LOCALIZADAS_POR_NOME\n")
            out.write(f"- **Fontes:** {len(ids)}/6\n")
            out.write(f"- **Pasta:** `{os.environ.get('GOOGLE_DRIVE_FOLDER_ID', FOLDER_DEFAULT)}`\n")
            out.write(f"- {message}\n")
    print(json.dumps({"status": "FONTES_LOCALIZADAS_POR_NOME", "fontes": len(ids), "mensagem": message, "ids": ids}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO NA DESCOBERTA DE FONTES: {exc}")
        raise SystemExit(1)
