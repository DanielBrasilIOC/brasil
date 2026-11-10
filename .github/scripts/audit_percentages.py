#!/usr/bin/env python3
"""Audita os percentuais da composição das Ordens Bancárias antes da publicação."""
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data.json"
OUT = ROOT / "logs" / "auditoria_percentuais.json"


def cents(value):
    try:
        return int((Decimal(str(value or 0)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Valor monetário inválido: {value!r}")


def rounded_basis_points(value, total):
    # Equivale ao Math.round(value * 10000 / total) usado na interface.
    return (value * 10000 + total // 2) // total


def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    datasets = {item.get("id"): item for item in payload.get("datasets", [])}
    required = ("ordens_bancarias", "diarias_pagas", "publicacoes_pagas")
    missing = [name for name in required if name not in datasets]
    if missing:
        raise RuntimeError("Datasets necessários ausentes: " + ", ".join(missing))

    orders = datasets["ordens_bancarias"]
    rows = orders.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Ordens Bancárias sem registros detalhados.")

    total = cents(orders.get("total"))
    if total <= 0:
        raise RuntimeError("Total de Ordens Bancárias deve ser positivo.")

    bolsistas = sum(
        cents(row.get("valor"))
        for row in rows
        if "bols" in (
            str(row.get("observacao") or "") + " " +
            str(row.get("favorecido") or "")
        ).lower()
    )
    diarias = cents(datasets["diarias_pagas"].get("total"))
    publicacoes = cents(datasets["publicacoes_pagas"].get("total"))
    remainder = total - bolsistas - diarias - publicacoes

    if min(bolsistas, diarias, publicacoes, remainder) < 0:
        raise RuntimeError(
            "Composição inválida: uma categoria é negativa ou as categorias "
            "ultrapassam o total consolidado."
        )

    parts = [
        ("Bolsistas Pagos", bolsistas),
        ("Diárias Pagas", diarias),
        ("Publicações Pagas", publicacoes),
    ]
    rounded = [rounded_basis_points(value, total) for _, value in parts]
    remainder_pct = 10000 - sum(rounded)
    if remainder_pct < 0:
        raise RuntimeError("Percentual residual negativo.")
    if sum(rounded) + remainder_pct != 10000:
        raise RuntimeError("A soma dos percentuais exibidos não fecha em 100,00%.")

    details = []
    for (name, value), pct in zip(parts, rounded):
        exact = Decimal(value) * Decimal(100) / Decimal(total)
        displayed = Decimal(pct) / Decimal(100)
        if abs(exact - displayed) > Decimal("0.005"):
            raise RuntimeError(f"Percentual exibido inconsistente para {name}.")
        details.append({
            "categoria": name,
            "valor_centavos": value,
            "valor": f"{Decimal(value) / 100:.2f}",
            "percentual_exato": f"{exact:.6f}",
            "percentual_exibido": f"{displayed:.2f}",
        })

    remainder_exact = Decimal(remainder) * Decimal(100) / Decimal(total)
    remainder_displayed = Decimal(remainder_pct) / Decimal(100)
    if abs(remainder_exact - remainder_displayed) > Decimal("0.015"):
        raise RuntimeError("Percentual residual inconsistente com o valor residual.")

    report = {
        "status": "APROVADO",
        "generated_at": payload.get("generated_at"),
        "total_ordens_bancarias": f"{Decimal(total) / 100:.2f}",
        "categorias": details,
        "demais_ordens": {
            "valor": f"{Decimal(remainder) / 100:.2f}",
            "percentual_exato": f"{remainder_exact:.6f}",
            "percentual_exibido": f"{remainder_displayed:.2f}",
        },
        "soma_percentuais_exibidos": f"{(sum(rounded) + remainder_pct) / 100:.2f}",
        "regra": "Percentuais recalculados sobre o total de OBs, com arredondamento em duas casas; o residual fecha a soma em 100,00%.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({
            "status": "REPROVADO",
            "erro": str(exc)
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
