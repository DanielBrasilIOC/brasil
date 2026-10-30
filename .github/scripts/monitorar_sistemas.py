#!/usr/bin/env python3
"""Monitor técnico e operacional de portais governamentais (sem autenticação)."""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "monitoramento-sistemas.json"
TIMEOUT_SECONDS = 15
MAX_BODY_BYTES = 2_000_000
HISTORY_LIMIT = 100
ALERT_AFTER_FAILURES = 2
USER_AGENT = "IOC-Dashboard-Monitor/2.0 (+public-portal-availability-check)"

TARGETS = [
    {"id": "siafi", "name": "SIAFI", "url": "https://siafi.tesouro.gov.br/",
     "scope": "Portal público; login, consultas e operações internas não são testados."},
    {"id": "contratos", "name": "Contratos.gov.br", "url": "https://contratos.gov.br/",
     "scope": "Acesso ao portal; módulos autenticados e transações não são testados."},
    {"id": "compras", "name": "Compras.gov.br", "url": "https://www.gov.br/compras/pt-br",
     "scope": "Página pública; login, sessão de disputa e operações internas não são testados."},
    {"id": "sicaf", "name": "SICAF", "url": "https://www.gov.br/compras/pt-br/sistemas/conheca-o-compras/sicaf-digital",
     "scope": "Página pública informativa; acesso autenticado ao SICAF não é testado."},
    {"id": "pncp", "name": "PNCP", "url": "https://www.gov.br/pncp/pt-br",
     "scope": "Portal público; APIs e operações de publicação não são testadas."},
    {"id": "transferegov", "name": "Transferegov.br", "url": "https://transferegov.sistema.gov.br/",
     "scope": "Endpoint público; módulos autenticados e operações não são testados."},
]

OPERATIONAL_SOURCES = {
    "siafi": {"url": "https://www.gov.br/tesouronacional/pt-br/siafi/consultas-e-servicos/calendario-disponibilidade-siafi",
              "keywords": ["siafi"], "kind": "calendario"},
    "contratos": {"url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados",
                  "keywords": ["contratos.gov.br", "contratos gov.br"], "kind": "comunicados"},
    "compras": {"url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados",
                "keywords": ["compras.gov.br", "compras gov.br"], "kind": "comunicados"},
    "sicaf": {"url": "https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados",
              "keywords": ["sicaf"], "kind": "comunicados"},
    "pncp": {"url": "https://www.gov.br/pncp/pt-br/central-de-conteudo/comunicados/comunicados",
             "keywords": ["pncp"], "kind": "comunicados"},
    "transferegov": {"url": "https://www.gov.br/transferegov/pt-br/comunicados/comunicados-gerais",
                     "keywords": ["transferegov", "transferegov.br"], "kind": "comunicados"},
}

NOTICE_TERMS = re.compile(
    r"manuten|indispon|instabil|interrup|lentid|falha|atualiza[cç][aã]o programada|"
    r"janela técnica|janela tecnica|suspens", re.IGNORECASE
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            label = re.sub(r"\s+", " ", " ".join(self._parts)).strip()
            if label:
                self.links.append({"title": label[:240], "url": self._href})
            self._href = None
            self._parts = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def request_page(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BODY_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "http_status": response.status,
                "final_url": response.geturl(),
                "body": body.decode(charset, errors="replace"),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
        return {
            "http_status": exc.code, "final_url": exc.geturl(), "body": body,
            "latency_ms": round((time.monotonic() - started) * 1000), "error": None,
        }
    except Exception as exc:  # DNS, TLS, timeout, socket and unexpected transport errors
        return {
            "http_status": None, "final_url": url, "body": "",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }


def classify_http(code: int | None, error: str | None) -> tuple[str, str]:
    if error:
        return "NAO_VERIFICADO", error
    if code is not None and 200 <= code < 400:
        return "ACESSIVEL", "O endpoint público respondeu; isso não comprova o funcionamento de módulos internos."
    if code in (401, 403):
        return "ACESSO_RESTRITO", "O servidor respondeu, mas restringiu o acesso público. Não classificar como queda."
    if code == 429 or (code is not None and code >= 500):
        return "INSTABILIDADE", "O endpoint respondeu com sinal de limitação ou erro do servidor."
    return "RESPOSTA_INCONCLUSIVA", f"Resposta HTTP {code}; requer interpretação específica e não confirma indisponibilidade geral."


def probe_system(target: dict[str, str]) -> dict[str, Any]:
    response = request_page(target["url"])
    status, detail = classify_http(response["http_status"], response["error"])
    return {
        **target,
        "status": status,
        "http_status": response["http_status"],
        "latency_ms": response["latency_ms"],
        "final_url": response["final_url"],
        "detail": detail,
        "checked_at": utc_now(),
    }


def absolute_url(base: str, href: str) -> str:
    from urllib.parse import urljoin
    return urljoin(base, href)


def operational_check(system_id: str, page_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = OPERATIONAL_SOURCES[system_id]
    url = source["url"]
    if url not in page_cache:
        page_cache[url] = request_page(url)
    page = page_cache[url]
    if page["error"] or page["http_status"] is None or not (200 <= page["http_status"] < 400):
        return {
            "status": "FONTE_INDISPONIVEL",
            "source_url": url,
            "http_status": page["http_status"],
            "detail": page["error"] or f"Fonte oficial respondeu HTTP {page['http_status']}.",
            "notices": [],
        }

    if source["kind"] == "calendario":
        return {
            "status": "CALENDARIO_OFICIAL_ACESSIVEL",
            "source_url": url,
            "http_status": page["http_status"],
            "detail": "Calendário oficial de disponibilidade do SIAFI consultado. A leitura não testa o acesso autenticado.",
            "notices": [],
        }

    parser = LinkParser()
    parser.feed(page["body"])
    keywords = [term.casefold() for term in source["keywords"]]
    notices = []
    for link in parser.links:
        title = html.unescape(link["title"])
        lowered = title.casefold()
        if any(term in lowered for term in keywords) and NOTICE_TERMS.search(title):
            notices.append({
                "title": title,
                "url": absolute_url(page["final_url"], link["url"]),
            })
    notices = notices[:8]
    return {
        "status": "COMUNICADO_OPERACIONAL_LOCALIZADO" if notices else "SEM_COMUNICADO_IDENTIFICADO",
        "source_url": url,
        "http_status": page["http_status"],
        "detail": (
            f"{len(notices)} comunicado(s) com termos de manutenção/instabilidade localizado(s) na fonte oficial."
            if notices else
            "Fonte oficial consultada; nenhum título correspondente a aviso operacional foi identificado nesta leitura. Isso não prova ausência de manutenção."
        ),
        "notices": notices,
    }


def is_failure(system: dict[str, Any]) -> bool:
    return system["status"] in {"INSTABILIDADE", "NAO_VERIFICADO"}


def apply_failure_tracking(
    current: list[dict[str, Any]], previous: dict[str, Any], checked_at: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    previous_by_id = {item.get("id"): item for item in previous.get("systems", [])}
    new_alerts: list[dict[str, Any]] = []
    for item in current:
        old = previous_by_id.get(item["id"], {})
        old_streak = int(old.get("failure_streak") or 0)
        streak = old_streak + 1 if is_failure(item) else 0
        item["failure_streak"] = streak
        item["alert_state"] = "ALERTA_REGISTRADO" if streak >= ALERT_AFTER_FAILURES else "SEM_ALERTA"
        if streak >= ALERT_AFTER_FAILURES and old_streak < ALERT_AFTER_FAILURES:
            new_alerts.append({
                "id": f"{item['id']}:{checked_at}:falha",
                "system_id": item["id"],
                "system_name": item["name"],
                "type": "FALHAS_CONSECUTIVAS",
                "created_at": checked_at,
                "message": f"{item['name']}: {streak} verificações consecutivas com falha técnica.",
                "delivery": "REGISTRADO_NO_PAINEL",
            })
        if not is_failure(item) and old_streak >= ALERT_AFTER_FAILURES:
            new_alerts.append({
                "id": f"{item['id']}:{checked_at}:recuperacao",
                "system_id": item["id"],
                "system_name": item["name"],
                "type": "RECUPERACAO_DETECTADA",
                "created_at": checked_at,
                "message": f"{item['name']}: endpoint voltou a responder sem sinal técnico de falha.",
                "delivery": "REGISTRADO_NO_PAINEL",
            })
    return current, new_alerts


def self_test() -> None:
    assert classify_http(200, None)[0] == "ACESSIVEL"
    assert classify_http(403, None)[0] == "ACESSO_RESTRITO"
    assert classify_http(503, None)[0] == "INSTABILIDADE"
    assert classify_http(None, "TimeoutError: timed out")[0] == "NAO_VERIFICADO"
    assert not is_failure({"status": "ACESSO_RESTRITO"})
    assert is_failure({"status": "INSTABILIDADE"})
    sample = [{"id": "x", "name": "Teste", "status": "INSTABILIDADE"}]
    _, alerts = apply_failure_tracking(sample, {"systems": [{"id": "x", "failure_streak": 1}]}, "2026-01-01T00:00:00Z")
    assert len(alerts) == 1 and alerts[0]["type"] == "FALHAS_CONSECUTIVAS"
    sample = [{"id": "x", "name": "Teste", "status": "ACESSIVEL"}]
    _, alerts = apply_failure_tracking(sample, {"systems": [{"id": "x", "failure_streak": 2}]}, "2026-01-01T00:30:00Z")
    assert len(alerts) == 1 and alerts[0]["type"] == "RECUPERACAO_DETECTADA"
    print("SELF-TEST OK: classificação HTTP, acesso restrito, falhas consecutivas e recuperação.")


def run_collection() -> dict[str, Any]:
    started = time.monotonic()
    checked_at = utc_now()
    try:
        previous = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}

    systems = [probe_system(target) for target in TARGETS]
    page_cache: dict[str, dict[str, Any]] = {}
    for item in systems:
        item["operational"] = operational_check(item["id"], page_cache)

    systems, new_alerts = apply_failure_tracking(systems, previous, checked_at)
    duration_ms = round((time.monotonic() - started) * 1000)
    history = list(previous.get("history") or [])
    history.append({
        "checked_at": checked_at,
        "duration_ms": duration_ms,
        "systems_total": len(systems),
        "accessible": sum(x["status"] == "ACESSIVEL" for x in systems),
        "instability": sum(x["status"] == "INSTABILIDADE" for x in systems),
        "not_verified": sum(x["status"] == "NAO_VERIFICADO" for x in systems),
        "systems": [
            {"id": x["id"], "name": x["name"], "status": x["status"],
             "http_status": x["http_status"], "latency_ms": x["latency_ms"],
             "failure_streak": x["failure_streak"]}
            for x in systems
        ],
    })
    alerts = list(previous.get("alerts") or []) + new_alerts

    data = {
        "environment": "TESTE",
        "checked_at": checked_at,
        "collector": "monitorar_sistemas.py",
        "scheduler_status": "AGENDADOR_NAO_CONFIGURADO",
        "frequency_target_seconds": 1800,
        "schedule_target": "A cada 30 minutos, de segunda a sexta-feira",
        "last_run_duration_ms": duration_ms,
        "disclaimer": "Verificação de endpoints públicos e leitura de comunicados oficiais. Não testa login, transações nem módulos internos autenticados. Ausência de comunicado identificado não prova ausência de manutenção.",
        "systems": systems,
        "history": history[-HISTORY_LIMIT:],
        "alerts": alerts[-HISTORY_LIMIT:],
    }
    temp_file = STATE_FILE.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_file.replace(STATE_FILE)
    print(json.dumps({
        "environment": data["environment"],
        "checked_at": checked_at,
        "duration_ms": duration_ms,
        "systems": [{"id": x["id"], "status": x["status"], "http_status": x["http_status"],
                     "latency_ms": x["latency_ms"], "operational_status": x["operational"]["status"]}
                    for x in systems],
        "new_alerts": new_alerts,
        "history_entries": len(data["history"]),
        "scheduler_status": data["scheduler_status"],
    }, ensure_ascii=False, indent=2))
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="executa testes locais sem acessar a internet")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run_collection()
