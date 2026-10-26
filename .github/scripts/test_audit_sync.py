#!/usr/bin/env python3
"""Testes sintéticos da comparação de registros; não alteram fontes reais."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_sync.py")
SPEC = importlib.util.spec_from_file_location("audit_sync", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

def orc(ident, saldo):
    return {"ug":"254463","unidade":"IOC","ptres":ident,"fonte":"100",
            "natureza_codigo":"339030","pi":"A1IOC","programa":"IOC","saldo":saldo}

class RowDiffTests(unittest.TestCase):
    def test_inclusao_de_registro(self):
        d = audit.row_diff({"orcamentario":[orc("1",10),orc("2",20)]},
                           {"orcamentario":[orc("1",10),orc("2",20),orc("3",30)]})["orcamentario"]
        self.assertEqual((d["added"],d["removed"],d["altered"]),(1,0,0))

    def test_exclusao_de_registro(self):
        d = audit.row_diff({"orcamentario":[orc("1",10),orc("2",20),orc("3",30)]},
                           {"orcamentario":[orc("1",10),orc("2",20)]})["orcamentario"]
        self.assertEqual((d["added"],d["removed"],d["altered"]),(0,1,0))

    def test_alteracao_de_registro(self):
        d = audit.row_diff({"orcamentario":[orc("1",10),orc("2",20)]},
                           {"orcamentario":[orc("1",15),orc("2",20)]})["orcamentario"]
        self.assertEqual((d["added"],d["removed"],d["altered"]),(0,0,1))
        self.assertTrue(d["value_changed"])

    def test_inclusao_e_exclusao_nao_sao_classificadas_como_alteracao(self):
        d = audit.row_diff({"orcamentario":[orc("1",10),orc("2",20),orc("3",30)]},
                           {"orcamentario":[orc("1",10),orc("3",30),orc("4",40)]})["orcamentario"]
        self.assertEqual((d["added"],d["removed"],d["altered"]),(1,1,0))

    def test_contagens_de_duplicados(self):
        d = audit.row_diff({"orcamentario":[orc("1",10),orc("1",10)]},
                           {"orcamentario":[orc("1",10)]})["orcamentario"]
        self.assertEqual((d["added"],d["removed"],d["altered"]),(0,1,0))

    def test_fingerprint_independe_da_ordem_mas_preserva_duplicados(self):
        a = [{"saldo":10.0},{"saldo":20.0},{"saldo":10.0}]
        b = [{"saldo":10.0},{"saldo":10.0},{"saldo":20.0}]
        c = [{"saldo":10.0},{"saldo":20.0}]
        self.assertEqual(audit.row_fingerprint(a),audit.row_fingerprint(b))
        self.assertNotEqual(audit.row_fingerprint(a),audit.row_fingerprint(c))

    def test_reconciliacao_detecta_divergencia_de_registro_e_total(self):
        names=list(audit.SOURCES)
        data={"datasets":[]}
        report={}
        for name in names:
            rows=[{"saldo":100.0}]
            if name=="ordens_bancarias": rows=[{"valor":100.0}]
            data["datasets"].append({"id":name,"rows":rows,"total":100.0})
            report[name]={"registros":1,"total":100.0,"rows_hash":audit.row_fingerprint(rows)}
        self.assertEqual(audit.reconcile_source_rows(data,report),{})
        data["datasets"][0]["rows"][0]["saldo"]=99.0
        data["datasets"][0]["total"]=99.0
        self.assertIn("empenhos",audit.reconcile_source_rows(data,report))

class MoneyParsingTests(unittest.TestCase):
    def test_moeda_brasileira(self):
        spec = importlib.util.spec_from_file_location("sync_sources", SCRIPT.with_name("sync_sources.py"))
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        self.assertEqual(sync.money("R$ 1.234,56"), 1234.56)
        self.assertEqual(sync.money("(1.234,56)"), -1234.56)
        self.assertIsNone(sync.money("-"))

    def test_moeda_invalida_nao_vira_zero(self):
        spec = importlib.util.spec_from_file_location("sync_sources", SCRIPT.with_name("sync_sources.py"))
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        with self.assertRaises(ValueError):
            sync.money("R$ NÃO É NÚMERO")

if __name__ == "__main__":
    unittest.main(verbosity=2)
