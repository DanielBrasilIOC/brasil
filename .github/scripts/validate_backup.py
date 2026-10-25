#!/usr/bin/env python3
"""Valida snapshots restauráveis do Painel Financeiro e Orçamentário IOC."""
import hashlib
import json
import sys
from pathlib import Path

REQUIRED_FILES = (
    "data.json",
    "repasses.json",
    "source_state.json",
    "dashboard-v2.html",
    "index.html",
)
EXPECTED_DATASETS = {
    "empenhos", "orcamentario", "ordens_bancarias",
    "repasses", "financeiro", "restos",
}
EXPECTED_SOURCES = EXPECTED_DATASETS


def fail(message):
    raise SystemExit("VALIDAÇÃO REPROVADA: " + message)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.name} não é JSON válido: {exc}")


def validate(root, verify_manifest=False):
    root = Path(root)
    for name in REQUIRED_FILES:
        path = root / name
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"arquivo ausente ou vazio: {name}")

    data = load_json(root / "data.json")
    repasses = load_json(root / "repasses.json")
    state = load_json(root / "source_state.json")

    if not isinstance(data, dict) or not isinstance(data.get("datasets"), list):
        fail("data.json não contém a estrutura datasets esperada")
    if not data.get("generated_at"):
        fail("data.json sem generated_at")
    datasets = {}
    for item in data["datasets"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            fail("dataset sem identificador válido")
        if item["id"] in datasets:
            fail("dataset duplicado: " + item["id"])
        datasets[item["id"]] = item
    missing = EXPECTED_DATASETS - set(datasets)
    if missing:
        fail("datasets obrigatórios ausentes: " + ", ".join(sorted(missing)))
    for name in EXPECTED_DATASETS:
        item = datasets[name]
        rows = item.get("rows")
        if not isinstance(rows, list) or not rows:
            fail(f"dataset {name} sem registros válidos")
        if item.get("detail_count") != len(rows):
            fail(f"detail_count incompatível em {name}: {item.get('detail_count')} != {len(rows)}")
        if not isinstance(item.get("total"), (int, float)) or isinstance(item.get("total"), bool):
            fail(f"total ausente ou inválido em {name}")
    if not isinstance(repasses, dict) or not isinstance(repasses.get("rows"), list):
        fail("repasses.json sem lista rows")
    if not repasses["rows"]:
        fail("repasses.json sem registros")
    if not isinstance(repasses.get("total"), (int, float)):
        fail("total inválido em repasses.json")
    if not isinstance(state, dict) or not isinstance(state.get("hashes"), dict):
        fail("source_state.json sem hashes")
    missing_hashes = EXPECTED_SOURCES - set(state["hashes"])
    if missing_hashes:
        fail("hashes de fontes ausentes: " + ", ".join(sorted(missing_hashes)))
    if "dashboard-v2.html" not in (root / "index.html").read_text(encoding="utf-8"):
        fail("index.html não referencia dashboard-v2.html")

    if verify_manifest:
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            fail("manifest.json ausente")
        manifest = load_json(manifest_path)
        expected = manifest.get("files", {}) if isinstance(manifest, dict) else {}
        for name in REQUIRED_FILES:
            expected_hash = expected.get(name)
            actual_hash = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if not expected_hash or actual_hash != expected_hash:
                fail(f"hash incompatível no arquivo {name}")
        if not manifest.get("snapshot_id") or not manifest.get("source_commit"):
            fail("manifesto sem identificação do snapshot ou commit de origem")

    print(json.dumps({
        "status": "VALIDO",
        "arquivos": list(REQUIRED_FILES),
        "datasets": {name: {"registros": len(datasets[name]["rows"]),
                             "total": datasets[name]["total"]}
                     for name in sorted(EXPECTED_DATASETS)},
        "generated_at": data["generated_at"],
        "manifest_verificado": verify_manifest,
    }, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        fail("uso: validate_backup.py DIRETORIO [--verify-manifest]")
    validate(sys.argv[1], verify_manifest=(len(sys.argv) == 3 and sys.argv[2] == "--verify-manifest"))
