#!/usr/bin/env python3
"""Descobre DIARIAS PAGAS.csv pelo nome exato normalizado na pasta oficial do Drive."""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import discover_drive_sources as drive

FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", drive.FOLDER_DEFAULT).strip()
EXPECTED = "DIARIAS PAGAS.csv"

def main():
    drive.EXPECTED_NAMES["diarias"] = (EXPECTED,)
    page = None
    last_error = None
    for attempt in range(3):
        try:
            page = drive.fetch_folder_page(FOLDER_ID)
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    if page is None:
        raise RuntimeError(f"Não foi possível consultar a pasta oficial após 3 tentativas: {last_error}")
    files = drive.extract_folder_files(page, FOLDER_ID)
    target = drive.normalize(EXPECTED)
    matches = [f for f in files if drive.normalize(f.get("name")) == target and FOLDER_ID in (f.get("parents") or [])]
    if len(matches) != 1:
        raise RuntimeError(f"{EXPECTED}: encontrados {len(matches)} arquivos na pasta oficial; esperado exatamente 1. Sincronização bloqueada.")
    file_id = matches[0].get("id", "").strip()
    if not file_id:
        raise RuntimeError(f"{EXPECTED}: ID vazio após descoberta por nome.")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"file_id={file_id}\n")
    print(json.dumps({"status":"FONTE_LOCALIZADA_POR_NOME","arquivo":EXPECTED,"quantidade":1}, ensure_ascii=False))

if __name__ == "__main__":
    main()
