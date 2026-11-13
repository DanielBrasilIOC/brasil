import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

TARGETS = [
    ("Portal GOV.BR", "https://www.gov.br/"),
    ("Serviços GOV.BR", "https://www.gov.br/pt-br/servicos"),
    ("Acesso GOV.BR", "https://acesso.gov.br/"),
    ("SIAFI Tesouro", "https://siafi.tesouro.gov.br/"),
]
TIMEOUT = 15
ATTEMPTS = 3
PAUSE_SECONDS = 3
now = datetime.now(timezone.utc).isoformat()

try:
    previous = json.loads(Path("monitoramento.json").read_text(encoding="utf-8"))
except Exception:
    previous = {}

services = []
for name, url in TARGETS:
    attempts = []
    for attempt in range(1, ATTEMPTS + 1):
        started = time.monotonic()
        status = None
        error = None
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "IOC-Service-Monitor/1.1",
                    "Accept": "text/html,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)[:180]

        if status is not None and 200 <= status < 400:
            observation = "up"
        elif status in (401, 403, 429):
            observation = "inconclusive"
        else:
            observation = "down"

        attempts.append({
            "attempt": attempt,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "http_status": status,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "observation": observation,
            "error": error,
        })
        if attempt < ATTEMPTS:
            time.sleep(PAUSE_SECONDS)

    # Confirmar somente três respostas consecutivas iguais no mesmo ciclo.
    last_observation = attempts[-1]["observation"]
    streak = 0
    for item in reversed(attempts):
        if item["observation"] != last_observation:
            break
        streak += 1

    confirmed = (
        "up" if last_observation == "up" and streak == ATTEMPTS else
        "down" if last_observation == "down" and streak == ATTEMPTS else
        "unknown"
    )
    observations = {item["observation"] for item in attempts}
    if observations == {"up"}:
        overall = "up"
    elif observations == {"down"}:
        overall = "down"
    elif observations == {"inconclusive"}:
        overall = "inconclusive"
    else:
        overall = "intermittent"

    valid_statuses = [x["http_status"] for x in attempts if x["http_status"] is not None]
    services.append({
        "name": name,
        "url": url,
        "checked_at": attempts[-1]["checked_at"],
        "http_status": valid_statuses[-1] if valid_statuses else None,
        "latency_ms": round(sum(x["latency_ms"] for x in attempts) / ATTEMPTS),
        "observation": overall,
        "streak": streak,
        "confirmed_status": confirmed,
        "successful_attempts": sum(1 for x in attempts if x["observation"] == "up"),
        "attempts_total": ATTEMPTS,
        "attempts": attempts,
        "error": next((x["error"] for x in reversed(attempts) if x["error"]), None),
        "note": "Três tentativas no mesmo ciclo. HTTP 401/403/429 é inconclusivo; não classificar isoladamente como indisponibilidade.",
    })

history = (previous.get("history") or [])[-95:]
history.append({
    "generated_at": now,
    "services": [
        {
            "name": x["name"],
            "confirmed_status": x["confirmed_status"],
            "http_status": x["http_status"],
            "latency_ms": x["latency_ms"],
            "observation": x["observation"],
        }
        for x in services
    ],
})
payload = {
    "schema_version": 2,
    "generated_at": now,
    "interval_minutes": 10,
    "source": "GitHub Actions runner; três tentativas por endereço",
    "disclaimer": (
        "Resultado de acesso HTTP a partir de um único ponto de verificação. "
        "A confirmação exige três respostas consecutivas no mesmo ciclo. "
        "Não mede disponibilidade global nem autenticação/funcionalidades internas."
    ),
    "services": services,
    "history": history,
}
Path("monitoramento.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=False, indent=2))
