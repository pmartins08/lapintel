from __future__ import annotations

import json
import unittest

from agent_contracts import (
    DealDecision,
    DiscoveryCandidate,
    LaptopSpecExtraction,
    decision_from_assessment,
    from_legacy_dict,
    to_legacy_dict,
)


class AgentContractsTests(unittest.TestCase):
    def test_discovery_candidate_creation(self):
        candidate = DiscoveryCandidate(
            url="https://example.test/laptop-1",
            loja="Globaldata",
            titulo="Portátil ASUS Gaming V16",
            preco_hint=1299.0,
            discovered_at="2026-11-11T12:00:00Z",
        )
        self.assertEqual(candidate.loja, "Globaldata")
        self.assertEqual(candidate.preco_hint, 1299.0)
        self.assertEqual(candidate.source, "category")

    def test_spec_extraction_from_and_to_legacy_dict(self):
        legacy = {
            "page_url": "https://example.test/legion-5",
            "marca": "Lenovo",
            "submarca": "Legion",
            "cpu_modelo": "Ryzen 7 8845HS",
            "gpu_modelo": "RTX 5060",
            "gpu_tipo": "dedicada",
            "tgp_w": 140,
            "ram_gb": 32,
            "armazenamento_tb": 1.0,
            "bateria_wh": 80.0,
            "ecra_brightness_nits": 350,
            "ecra_srgb_percent": 100.0,
            "os_status": "none",
            "keyboard_layout": "pt",
            "ean": "0198153214501",
            "mpn": "83DH003KPG",
        }
        contract = from_legacy_dict(legacy)
        self.assertEqual(contract.marca, "Lenovo")
        self.assertEqual(contract.tgp_w, 140)
        self.assertEqual(contract.os_status, "none")
        self.assertEqual(contract.keyboard_layout, "pt")

        converted_back = to_legacy_dict(contract)
        self.assertEqual(converted_back["marca"], "Lenovo")
        self.assertEqual(converted_back["tgp_w"], 140)
        self.assertEqual(converted_back["os_status"], "none")
        self.assertEqual(converted_back["page_url"], "https://example.test/legion-5")

    def test_decision_from_assessment_diamond_triggers_notification(self):
        item = {
            "url": "https://example.test/laptop-diamond",
            "loja": "Radio Popular",
            "titulo": "Portátil Lenovo Legion 5",
            "preco": 1299.99,
            "stock": True,
        }
        spec = {"os_status": "windows"}
        assessment = {
            "status": "ACEITE",
            "tier": "DIAMANTE",
            "value_score": 123.6,
            "purchase_total_eur": 1299.99,
            "installation_cost_eur": 0.0,
        }
        decision = decision_from_assessment(item, spec, assessment)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.tier, "DIAMANTE")
        self.assertEqual(decision.value_score, 123.6)
        self.assertTrue(decision.should_notify_ntfy)

    def test_decision_from_assessment_surcharges_no_os_strictly(self):
        item = {
            "url": "https://example.test/laptop-no-os",
            "loja": "UPTECHBOX",
            "titulo": "Portátil ASUS TUF Gaming 16 | S/SO",
            "preco": 1299.99,
            "stock": True,
        }
        spec = {"os_status": "none"}
        assessment = {
            "status": "ACEITE",
            "tier": "PRATA",
            "value_score": 105.0,
            "purchase_total_eur": 1409.99,
            "installation_cost_eur": 110.0,
        }
        decision = decision_from_assessment(item, spec, assessment)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.installation_cost_eur, 110.0)
        self.assertEqual(decision.purchase_total_eur, 1409.99)
        # Prata nunca dispara notificação NTFY (apenas Diamante)
        self.assertFalse(decision.should_notify_ntfy)

    def test_decision_from_assessment_rejection(self):
        item = {
            "url": "https://example.test/laptop-rejected",
            "loja": "Globaldata",
            "titulo": "Portátil Acima do Orçamento",
            "preco": 1750.0,
            "stock": True,
        }
        spec = {"os_status": "windows"}
        assessment = {
            "status": "REJEITADO",
            "alertas": ["Preço excede o teto orçamental máximo de 1600.0 €"],
        }
        decision = decision_from_assessment(item, spec, assessment)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.status, "REJEITADO")
        self.assertIn("teto orçamental", str(decision.rejection_reason))
        self.assertFalse(decision.should_notify_ntfy)
