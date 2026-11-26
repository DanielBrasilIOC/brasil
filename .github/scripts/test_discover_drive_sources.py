#!/usr/bin/env python3
"""Testes sintéticos da descoberta das sete fontes; sem acesso externo."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT=Path(__file__).with_name("discover_drive_sources.py")
SPEC=importlib.util.spec_from_file_location("discover",SCRIPT)
discover=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discover)

FOLDER="folder-test"
FILES=[{"id":f"id-{i}","name":name[0],"mimeType":"text/csv","parents":[FOLDER]}
       for i,name in enumerate(discover.EXPECTED_NAMES.values(),1)]

class SourceDiscoveryTests(unittest.TestCase):
    def test_seven_fontes_unicas_validas(self):
        ids=discover.select_sources(FILES,FOLDER)
        self.assertEqual(set(ids),set(discover.EXPECTED_NAMES))
        self.assertEqual(len(set(ids.values())),7)

    def test_fonte_ausente_bloqueia(self):
        with self.assertRaises(ValueError):
            discover.select_sources(FILES[:-1],FOLDER)

    def test_fonte_duplicada_bloqueia(self):
        duplicated=FILES+[dict(FILES[0],id="duplicate")]
        with self.assertRaises(ValueError):
            discover.select_sources(duplicated,FOLDER)

    def test_arquivo_em_outra_pasta_ignorado_e_bloqueia_se_ausente(self):
        wrong=[dict(x,parents=["other"]) for x in FILES]
        with self.assertRaises(ValueError):
            discover.select_sources(wrong,FOLDER)

    def test_mime_invalido_bloqueia(self):
        invalid=[dict(x,mimeType="application/pdf") for x in FILES]
        with self.assertRaises(ValueError):
            discover.select_sources(invalid,FOLDER)

    def test_ids_repetidos_entre_fontes_bloqueiam(self):
        duplicated=[dict(x) for x in FILES]
        duplicated[1]["id"]=duplicated[0]["id"]
        with self.assertRaises(ValueError):
            discover.select_sources(duplicated,FOLDER)

if __name__=="__main__":
    unittest.main(verbosity=2)
