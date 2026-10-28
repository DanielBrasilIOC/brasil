#!/usr/bin/env python3
"""Testes sintéticos da comparação de registros; não alteram fontes reais."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit_sync.py")
SPEC = importlib.util.spec_from_file_location("audit_sync", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

SYNC_SCRIPT = Path(__file__).with_name("sync_sources.py")
SYNC_SPEC = importlib.util.spec_from_file_location("sync_sources", SYNC_SCRIPT)
sync = importlib.util.module_from_spec(SYNC_SPEC)
SYNC_SPEC.loader.exec_module(sync)

class CsvDecodeTests(unittest.TestCase):
    def test_utf16_le_com_bom(self):
        raw = "Favorecido;Valor\r\nFundação;1.234,56\r\n".encode("utf-16")
        decoded = sync.decode_csv_bytes(raw)
        self.assertIn("Fundação", decoded)
        self.assertIn("1.234,56", decoded)
        self.assertNotIn("\\x00", decoded)

    def test_utf8_com_bom(self):
        raw = "\\ufeffFavorecido;Valor\\nFundação;12,34".encode("utf-8")
        decoded = sync.decode_csv_bytes(raw)
        self.assertIn("Favorecido", decoded)
        self.assertIn("Fundação", decoded)

    def test_valor_monetario_brasileiro(self):
        self.assertEqual(sync.money("R$ 1.234,56"), 1234.56)
        self.assertEqual(sync.money("-1.234,56"), -1234.56)

    def test_codificacao_invalida_nao_substitui_silenciosamente(self):
        with self.assertRaises(UnicodeDecodeError):
            sync.decode_csv_bytes(b"\\xff\\xfe")

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
