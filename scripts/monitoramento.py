import json, urllib.request, urllib.error, time
from datetime import datetime, timezone
from pathlib import Path

TARGETS = [
    ("Portal GOV.BR", "https://www.gov.br/"),
    ("Serviços GOV.BR", "https://www.gov.br/pt-br/servicos"),
    ("Acesso GOV.BR", "https://acesso.gov.br/"),
    ("SIAFI Tesouro", "https://siafi.tesouro.gov.br/"),
]
TIMEOUT = 15
now = datetime.now(timezone.utc).isoformat()
try:
    previous = json.loads(Path("monitoramento.json").read_text(encoding="utf-8"))
except Exception:
    previous = {"services": []}
old = {x.get("url"): x for x in previous.get("services", [])}
services = []

for name, url in TARGETS:
    started = time.monotonic()
    status = None
    error = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IOC-Service-Monitor/1.0", "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)[:180]
    latency = round((time.monotonic() - started) * 1000)
    # HTTP 2xx/3xx = reachable; 401/403/429 are inconclusive, not outage.
    if status is not None and 200 <= status < 400:
        observation = "up"
    elif status in (401, 403, 429):
        observation = "inconclusive"
    else:
        observation = "down"
    prior = old.get(url, {})
    prior_obs = prior.get("observation")
    streak = (int(prior.get("streak", 0)) + 1) if prior_obs == observation else 1
    stable = observation if streak >= 3 and observation != "inconclusive" else "unknown"
    services.append({
        "name": name, "url": url, "checked_at": now, "http_status": status,
        "latency_ms": latency, "observation": observation, "streak": streak,
        "confirmed_status": stable, "error": error,
        "note": "HTTP 401/403/429 é inconclusivo; não classificar isoladamente como indisponibilidade."
    })

payload = {
    "schema_version": 1, "generated_at": now, "interval_minutes": 10,
    "source": "GitHub Actions runner; verificação HTTP pública",
    "disclaimer": "Resultado de acesso HTTP a partir de um único ponto de verificação; não mede disponibilidade global nem substitui monitoramento oficial.",
    "services": services
}
Path("monitoramento.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
