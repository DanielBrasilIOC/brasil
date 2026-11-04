#!/usr/bin/env python3
"""Testes da barreira de integridade; não acessam nem alteram dados reais."""
import unittest
from decimal import Decimal
from integrity_validation import validate_dataset, validate_all

class IntegrityValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"ob": "OB001", "fonte_pagadora": "A", "valor": 100.00}]

    def test_registros_e_total_corretos_aprovam(self):
        result = validate_dataset("ordens_bancarias", self.rows, list(self.rows), 100, 100)
        self.assertEqual(result["status"], "APROVADO")

    def test_inclusao_indevida_bloqueia(self):
        result = validate_dataset("ordens_bancarias", self.rows, self.rows + [{"ob":"OB002","fonte_pagadora":"A","valor":5}], 100, 105)
        self.assertEqual(result["status"], "BLOQUEADO")

    def test_exclusao_bloqueia(self):
        result = validate_dataset("ordens_bancarias", self.rows, [], 100, 0)
        self.assertEqual(result["status"], "BLOQUEADO")

    def test_alteracao_de_valor_bloqueia(self):
        changed = [{"ob":"OB001","fonte_pagadora":"A","valor":101.00}]
        result = validate_dataset("ordens_bancarias", self.rows, changed, 100, 101)
        self.assertEqual(result["status"], "BLOQUEADO")

    def test_total_divergente_bloqueia(self):
        result = validate_dataset("ordens_bancarias", self.rows, self.rows, 100, 99)
        self.assertEqual(result["status"], "BLOQUEADO")

    def test_duplicidade_mesma_fonte_bloqueia(self):
        duplicated = self.rows + list(self.rows)
        result = validate_dataset("ordens_bancarias", self.rows, duplicated, 100, 200)
        self.assertEqual(result["status"], "BLOQUEADO")

    def test_mesma_ob_em_fontes_diferentes_e_permitida(self):
        rows = [{"ob":"OB001","fonte_pagadora":"A","valor":100},
                {"ob":"OB001","fonte_pagadora":"B","valor":200}]
        result = validate_dataset("ordens_bancarias", rows, rows, 300, 300)
        self.assertEqual(result["status"], "APROVADO")

    def test_descricao_vazia_nao_e_divergencia_de_integridade(self):
        rows = [{"ug":"254463","fonte":"1","ptres":"1","pi":"1",
                 "natureza_codigo":"3390","unidade":"","programa":"",
                 "descricao_fonte":"1","saldo":10}]
        result = validate_dataset("orcamentario", rows, rows, 10, 10)
        self.assertEqual(result["status"], "APROVADO")

    def test_diferenca_apenas_descritiva_gera_alerta_sem_bloquear(self):
        source = [{"ob": "OB001", "fonte_pagadora": "A", "valor": 100.00, "observacao": "Descrição original"}]
        prepared = [{"ob": "OB001", "fonte_pagadora": "A", "valor": 100.00, "observacao": "Descrição abreviada"}]
        result = validate_dataset("ordens_bancarias", source, prepared, 100, 100)
        self.assertEqual(result["status"], "ALERTA")
        self.assertFalse(result["errors"])
        self.assertTrue(result["warnings"])

    def test_dataset_ausente_bloqueia(self):
        result = validate_all({}, {})
        self.assertEqual(result["status"], "BLOQUEADO")

if __name__ == "__main__":
    unittest.main(verbosity=2)
