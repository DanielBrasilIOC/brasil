import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("monitorar_sistemas.py")
SPEC = importlib.util.spec_from_file_location("monitorar_sistemas", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(monitor)


class MonitoramentoTests(unittest.TestCase):
    def test_classificacao_http(self):
        self.assertEqual(monitor.classify_http(200, None)[0], "ACESSIVEL")
        self.assertEqual(monitor.classify_http(302, None)[0], "ACESSIVEL")
        self.assertEqual(monitor.classify_http(403, None)[0], "ACESSO_RESTRITO")
        self.assertEqual(monitor.classify_http(429, None)[0], "INSTABILIDADE")
        self.assertEqual(monitor.classify_http(503, None)[0], "INSTABILIDADE")
        self.assertEqual(monitor.classify_http(None, "TimeoutError")[0], "NAO_VERIFICADO")

    def test_acesso_restrito_nao_e_queda(self):
        self.assertFalse(monitor.is_failure({"status": "ACESSO_RESTRITO"}))
        self.assertFalse(monitor.is_failure({"status": "RESPOSTA_INCONCLUSIVA"}))
        self.assertTrue(monitor.is_failure({"status": "INSTABILIDADE"}))
        self.assertTrue(monitor.is_failure({"status": "NAO_VERIFICADO"}))

    def test_alerta_apos_duas_falhas_consecutivas(self):
        systems = [{"id": "contratos", "name": "Contratos.gov.br", "status": "INSTABILIDADE"}]
        _, alerts = monitor.apply_failure_tracking(
            systems, {"systems": [{"id": "contratos", "failure_streak": 1}]},
            "2026-10-30T18:00:00Z"
        )
        self.assertEqual(systems[0]["failure_streak"], 2)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["type"], "FALHAS_CONSECUTIVAS")

    def test_recuperacao_gera_evento(self):
        systems = [{"id": "pncp", "name": "PNCP", "status": "ACESSIVEL"}]
        _, alerts = monitor.apply_failure_tracking(
            systems, {"systems": [{"id": "pncp", "failure_streak": 3}]},
            "2026-10-30T18:30:00Z"
        )
        self.assertEqual(systems[0]["failure_streak"], 0)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["type"], "RECUPERACAO_DETECTADA")

    def test_parser_de_links(self):
        parser = monitor.LinkParser()
        parser.feed('<a href="/aviso"><span>Nº 45/26 - Manutenção programada no sistema Contratos.gov.br</span></a>')
        self.assertEqual(len(parser.links), 1)
        self.assertIn("Contratos.gov.br", parser.links[0]["title"])

    def test_localiza_comunicado_oficial_por_sistema(self):
        source = monitor.OPERATIONAL_SOURCES["contratos"]["url"]
        page_cache = {
            source: {
                "http_status": 200,
                "final_url": source,
                "error": None,
                "body": '<a href="/comunicado-45">Nº 45/26 - Manutenção programada no sistema Contratos.gov.br</a>',
            }
        }
        result = monitor.operational_check("contratos", page_cache)
        self.assertEqual(result["status"], "COMUNICADO_OPERACIONAL_LOCALIZADO")
        self.assertIn("comunicado-45", result["notices"][0]["url"])

    def test_endpoints_oficiais_dos_sistemas(self):
        urls = {item["id"]: item["url"] for item in monitor.TARGETS}
        self.assertEqual(urls["contratos"], "https://contratos.comprasnet.gov.br/login")
        self.assertEqual(urls["transferegov"], "https://portal.transferegov.sistema.gov.br/")

    def test_estado_inicial_tem_seis_sistemas_e_intervalo_30_min(self):
        import json
        state_path = SCRIPT.parents[2] / "monitoramento-sistemas.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state["systems"]), 6)
        self.assertEqual(state["frequency_target_seconds"], 1800)
        self.assertEqual(state["environment"], "TESTE")
        self.assertEqual(state["scheduler_status"], "AGENDADOR_NAO_CONFIGURADO")


if __name__ == "__main__":
    unittest.main(verbosity=2)
