"""Persistence, inventory and order lifecycle tests for the demo store."""

import tempfile
import unittest
from pathlib import Path

from store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "store.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_seeds_products_and_categories_once(self):
        self.assertEqual(len(self.store.products()), 5)
        self.assertIn("Leggings", [item["name"] for item in self.store.categories()])
        self.store.initialize()
        self.assertEqual(len(self.store.products()), 5)

    def test_product_can_be_created_and_hidden(self):
        product = {
            "id": "top-teste", "name": "Top Teste", "category": "Tops",
            "tagline": "Teste", "description": "Produto de teste",
            "price": 50, "image": "https://example.com/top.jpg", "active": True,
            "variants": [{"size": "M", "color": "Rosa", "stock": 2, "active": True}],
        }
        self.store.save_product(product)
        self.assertIn("top-teste", [item["id"] for item in self.store.products()])
        self.store.set_product_active("top-teste", False)
        self.assertNotIn("top-teste", [item["id"] for item in self.store.products()])
        self.assertIn("top-teste", [item["id"] for item in self.store.products(include_inactive=True)])

    def test_checkout_persists_order_and_reserves_stock(self):
        order = self.store.create_order({"name": "Ana Teste", "phone": "86999999999"}, [
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 2}
        ])
        product = next(p for p in self.store.products() if p["id"] == "legging-lua")
        variant = next(v for v in product["variants"] if v["size"] == "M" and v["color"] == "Preto")
        self.assertEqual(variant["stock"], 3)
        self.assertEqual(self.store.orders()[0]["id"], order["id"])
        self.assertEqual(order["total"], 279.8)

    def test_cancelled_order_restores_reserved_stock_only_once(self):
        order = self.store.create_order({"name": "Ana Teste", "phone": "86999999999"}, [
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 2}
        ])
        self.store.update_order_status(order["id"], "cancelado")
        with self.assertRaises(ValueError):
            self.store.update_order_status(order["id"], "em_andamento")
        product = next(p for p in self.store.products() if p["id"] == "legging-lua")
        variant = next(v for v in product["variants"] if v["size"] == "M" and v["color"] == "Preto")
        self.assertEqual(variant["stock"], 5)

    def test_invalid_checkout_does_not_change_stock(self):
        with self.assertRaises(ValueError):
            self.store.create_order({"name": "Ana", "phone": "86999999999"}, [
                {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 6}
            ])
        product = next(p for p in self.store.products() if p["id"] == "legging-lua")
        variant = next(v for v in product["variants"] if v["size"] == "M" and v["color"] == "Preto")
        self.assertEqual(variant["stock"], 5)

    def test_removed_variant_stays_available_for_cancelling_existing_order(self):
        order = self.store.create_order({"name": "Ana Teste", "phone": "86999999999"}, [
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 2}
        ])
        product = next(p for p in self.store.products() if p["id"] == "legging-lua")
        product["variants"] = [item for item in product["variants"] if not (item["size"] == "M" and item["color"] == "Preto")]
        self.store.save_product(product)
        self.store.update_order_status(order["id"], "cancelado")
        archived = next(v for v in next(p for p in self.store.products(include_inactive=True)
            if p["id"] == "legging-lua")["variants"] if v["size"] == "M" and v["color"] == "Preto")
        self.assertFalse(archived["active"])
        self.assertEqual(archived["stock"], 5)

    def test_rejects_duplicate_product_variants(self):
        product = {
            "id": "top-teste", "name": "Top Teste", "category": "Tops",
            "tagline": "Teste", "description": "Produto de teste",
            "price": 50, "image": "https://example.com/top.jpg", "active": True,
            "variants": [
                {"size": "M", "color": "Rosa", "stock": 1, "active": True},
                {"size": "M", "color": "Rosa", "stock": 2, "active": True},
            ],
        }
        with self.assertRaises(ValueError):
            self.store.save_product(product)


if __name__ == "__main__":
    unittest.main()
