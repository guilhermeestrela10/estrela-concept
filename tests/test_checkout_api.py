"""Regression tests for the local checkout API."""

import json
import threading
import tempfile
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import StoreHandler
from store import Store


class IsolatedStoreHandler(StoreHandler):
    store = None


class CheckoutApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), IsolatedStoreHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def setUp(self):
        IsolatedStoreHandler.store = Store(Path(self.temp.name) / f"{self._testMethodName}.sqlite3")

    def post_checkout(self, items, customer=None):
        body = json.dumps({"items": items, "customer": customer or {"name": "Ana Teste", "phone": "86999999999"}}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/checkout",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            return error.code, json.load(error)
        with response:
            return response.status, json.load(response)

    def test_checkout_uses_server_price_and_returns_subtotal(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 2, "price": 0}
        ])
        self.assertEqual(status, 200)
        self.assertEqual(result["total"], 279.8)

    def test_checkout_rejects_quantity_above_stock(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 6}
        ])
        self.assertEqual(status, 400)
        self.assertIn("Estoque insuficiente", result["error"])

    def test_checkout_counts_duplicate_variant_lines_together(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 3},
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 3},
        ])
        self.assertEqual(status, 400)
        self.assertIn("Estoque insuficiente", result["error"])

    def test_checkout_rejects_invalid_quantity_type(self):
        status, _ = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": True}
        ])
        self.assertEqual(status, 400)

    def test_checkout_requires_customer_phone(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 1}
        ], {"name": "Ana", "phone": "123"})
        self.assertEqual(status, 400)
        self.assertIn("WhatsApp", result["error"])

    def test_checkout_creates_order_visible_in_admin_api(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "P", "color": "Preto", "quantity": 1}
        ])
        self.assertEqual(status, 200)
        self.assertIn("id", result)
        with urlopen(f"{self.base_url}/api/admin/orders", timeout=2) as response:
            orders = json.load(response)["orders"]
        self.assertEqual(orders[0]["id"], result["id"])

    def test_admin_can_create_category_and_product(self):
        def post(path, payload):
            request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=2) as response:
                return response.status, json.load(response)

        status, category = post("/api/admin/categories", {"name": "Moda casual"})
        self.assertEqual(status, 201)
        self.assertEqual(category["category"]["id"], "moda-casual")
        status, created = post("/api/admin/products", {
            "id": "camiseta-teste", "name": "Camiseta Teste", "category": "Moda casual",
            "tagline": "Para o dia todo", "description": "Produto de demonstração.",
            "price": 59.9, "image": "https://example.com/camiseta.jpg", "active": True,
            "variants": [{"size": "M", "color": "Branca", "stock": 3, "active": True}],
        })
        self.assertEqual(status, 201)
        self.assertEqual(created["product"]["id"], "camiseta-teste")

    def test_admin_summary_reports_catalog_and_orders(self):
        with urlopen(f"{self.base_url}/api/admin/summary", timeout=2) as response:
            summary = json.load(response)
        self.assertEqual(summary["products"], 5)
        self.assertEqual(summary["orders"], 0)


if __name__ == "__main__":
    unittest.main()
