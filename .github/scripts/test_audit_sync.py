#!/usr/bin/env python3
"""Testes sintéticos da comparação de registros; não alteram fontes reais."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_sync.py")
SPEC = importlib.util.spec_from_file_location("audit_sync", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

class RowDiffTests(unittest.TestCase):
    def test_inclusao_de_registro(self):
        before = {"orcamentario": ["a", "b"]}
        after = {"orcamentario": ["a", "b", "c"]}
        d = audit.row_diff(before, after)["orcamentario"]
        self.assertEqual((d["added"], d["removed"], d["altered"]), (1, 0, 0))
        self.assertTrue(d["value_changed"])

    def test_exclusao_de_registro(self):
        before = {"orcamentario": ["a", "b", "c"]}
        after = {"orcamentario": ["a", "b"]}
        d = audit.row_diff(before, after)["orcamentario"]
        self.assertEqual((d["added"], d["removed"], d["altered"]), (0, 1, 0))
        self.assertTrue(d["value_changed"])

    def test_alteracao_de_registro(self):
        before = {"orcamentario": ["row-1-old", "row-2"]}
        after = {"orcamentario": ["row-1-new", "row-2"]}
        d = audit.row_diff(before, after)["orcamentario"]
        self.assertEqual((d["added"], d["removed"], d["altered"]), (1, 1, 1))
        self.assertTrue(d["value_changed"])

    def test_inclusao_e_exclusao_simultaneas(self):
        before = {"orcamentario": ["a", "b", "c"]}
        after = {"orcamentario": ["a", "c", "d"]}
        d = audit.row_diff(before, after)["orcamentario"]
        self.assertEqual((d["added"], d["removed"], d["altered"]), (1, 1, 1))
        self.assertTrue(d["value_changed"])

    def test_contagens_de_duplicados(self):
        before = {"orcamentario": ["a", "a"]}
        after = {"orcamentario": ["a"]}
        d = audit.row_diff(before, after)["orcamentario"]
        self.assertEqual((d["added"], d["removed"], d["altered"]), (0, 1, 0))

if __name__ == "__main__":
    unittest.main(verbosity=2)
