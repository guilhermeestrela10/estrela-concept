"""Fast, deterministic answers for the assistant's suggested questions."""

import unittest
from unittest.mock import patch

from app.rag import RagService


class CatalogStore:
    def products(self):
        return [
            {
                "name": "Top Aurora",
                "price": 89.9,
                "active": True,
                "variants": [
                    {"size": "P", "color": "Azul-marinho", "stock": 2, "active": True},
                    {"size": "M", "color": "Rosa", "stock": 0, "active": True},
                ],
            },
            {
                "name": "Short sem estoque",
                "price": 50,
                "active": True,
                "variants": [{"size": "M", "color": "Preto", "stock": 0, "active": True}],
            },
            {"name": "Produto oculto", "price": 20, "active": False, "variants": []},
        ]


class AssistantFaqTests(unittest.TestCase):
    def setUp(self):
        self.service = RagService(CatalogStore())

    def test_available_products_uses_live_catalog_without_external_ai(self):
        with patch.object(self.service, "_google", side_effect=AssertionError("external call was made")):
            result = self.service.answer("Quais peças estão disponíveis?")

        self.assertIn("Top Aurora (R$ 89,90)", result["answer"])
        self.assertIn("P / Azul-marinho", result["answer"])
        self.assertNotIn("Short sem estoque", result["answer"])
        self.assertNotIn("Produto oculto", result["answer"])
        self.assertEqual(result["sources"], ["Catálogo de produtos"])

    def test_delivery_answer_matches_public_policy_without_external_ai(self):
        with patch.object(self.service, "_google", side_effect=AssertionError("external call was made")):
            result = self.service.answer("Como funciona a entrega?")

        self.assertIn("Teresina/PI", result["answer"])
        self.assertIn("combinar", result["answer"])
        self.assertIn("custo de entrega", result["answer"])
        self.assertEqual(result["sources"], ["Políticas da loja"])

    def test_defect_exchange_answer_matches_public_policy_without_external_ai(self):
        with patch.object(self.service, "_google", side_effect=AssertionError("external call was made")):
            result = self.service.answer("Como faço para trocar uma peça com defeito?")

        self.assertIn("WhatsApp (86) 99926-9836", result["answer"])
        self.assertIn("30 dias", result["answer"])
        self.assertIn("90 dias", result["answer"])
        self.assertEqual(result["sources"], ["Políticas da loja"])


if __name__ == "__main__":
    unittest.main()
