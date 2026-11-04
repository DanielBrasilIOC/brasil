"""Validação de integridade dos dados preparados para publicação.

Diferenças puramente descritivas são avisos; inconsistências de estrutura,
chaves, valores ou totalizações são impeditivas.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
import json

MONEY_FIELDS = {
    "financeiro": "saldo",
    "restos": "saldo",
    "empenhos": "saldo",
    "orcamentario": "saldo",
    "repasses": "saldo",
    "ordens_bancarias": "valor",
    "publicacoes_pagas": "valor",
    "diarias_pagas": "valor",
}
KEY_FIELDS = {
    "empenhos": ("ne_ccor", "subitem", "cnpj"),
    "orcamentario": ("ug", "fonte", "ptres", "pi", "natureza_codigo"),
    "ordens_bancarias": ("ob",),
    "repasses": ("solicitacao_ne", "numero_ne", "saldo"),
    "financeiro": ("uge", "fonte", "vinculo"),
    "restos": ("empenho",),
    "diarias_pagas": ("documento", "data_pagamento", "favorecido", "valor"),
    "publicacoes_pagas": ("ob",),
}
DESCRIPTIVE_FIELDS = {
    "unidade", "programa", "descricao_fonte", "natureza", "responsavel",
    "fornecedor", "favorecido", "observacao", "note", "source_name",
}


def _money(value, context):
    if value is None or value == "":
        raise ValueError(f"{context}: valor monetário ausente")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{context}: valor monetário inválido: {value!r}")
    if not amount.is_finite():
        raise ValueError(f"{context}: valor monetário não finito")
    return amount


def _key(row, fields):
    # OBs podem repetir quando a fonte pagadora é diferente. Quando a origem
    # traz esse campo, ele integra a chave; sem ele, a OB continua única.
    if fields == ("ob",):
        source = row.get("fonte_pagadora", row.get("fonte", ""))
        return (row.get("ob"), source)
    return tuple(row.get(field) for field in fields)


def validate_dataset(name, expected_rows, actual_rows, expected_total, actual_total):
    """Compara conjunto esperado derivado da fonte e payload efetivamente preparado."""
    errors, warnings = [], []
    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        return {"status": "BLOQUEADO", "errors": [f"{name}: lista de registros inválida"], "warnings": []}
    if len(expected_rows) != len(actual_rows):
        errors.append(f"{name}: quantidade esperada {len(expected_rows)}; preparada {len(actual_rows)}")

    money_field = MONEY_FIELDS.get(name)
    if money_field:
        for label, rows in (("fonte", expected_rows), ("preparado", actual_rows)):
            try:
                computed = sum((_money(row.get(money_field), f"{name}/{label}/{i}") for i, row in enumerate(rows)), Decimal("0.00"))
                declared = _money(expected_total if label == "fonte" else actual_total, f"{name}/{label}/total")
                if computed != declared:
                    errors.append(f"{name}: soma dos registros {computed} difere do total declarado {declared} ({label})")
            except ValueError as exc:
                errors.append(str(exc))

    keys = KEY_FIELDS.get(name)
    if keys:
        counts = Counter(_key(row, keys) for row in actual_rows)
        duplicates = [key for key, count in counts.items() if count > 1]
        if duplicates:
            errors.append(f"{name}: chave de negócio duplicada ({len(duplicates)} chave(s)); exemplos: {duplicates[:5]!r}")

    # A igualdade integral das linhas é a barreira principal: não se normaliza
    # nem se corrige silenciosamente conteúdo vindo da fonte.
    expected_counts = Counter(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in expected_rows)
    actual_counts = Counter(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in actual_rows)
    if expected_counts != actual_counts:
        missing = list((expected_counts - actual_counts).elements())
        extra = list((actual_counts - expected_counts).elements())
        errors.append(f"{name}: registros preparados diferem da estrutura esperada; ausentes={len(missing)}, extras={len(extra)}")

    try:
        if _money(expected_total, f"{name}/total da fonte") != _money(actual_total, f"{name}/total preparado"):
            errors.append(f"{name}: total preparado difere do total esperado")
    except ValueError as exc:
        errors.append(str(exc))

    return {"status": "BLOQUEADO" if errors else ("ALERTA" if warnings else "APROVADO"),
            "errors": errors, "warnings": warnings}


def validate_all(expected, actual):
    """Valida todos os datasets exigidos; falha fechada se algum estiver ausente."""
    results = {}
    for name in MONEY_FIELDS:
        if name not in expected or name not in actual:
            results[name] = {"status": "BLOQUEADO", "errors": [f"{name}: dataset ausente"], "warnings": []}
            continue
        exp = expected[name]
        got = actual[name]
        results[name] = validate_dataset(name, exp.get("rows"), got.get("rows"),
                                         exp.get("total"), got.get("total"))
    blocked = any(item["status"] == "BLOQUEADO" for item in results.values())
    warned = any(item["status"] == "ALERTA" for item in results.values())
    return {"status": "BLOQUEADO" if blocked else ("ALERTA" if warned else "APROVADO"),
            "datasets": results}
