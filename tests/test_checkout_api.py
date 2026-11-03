"""Regression tests for the local checkout API."""

import json
import os
import threading
import tempfile
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import StoreHandler
from store import Store


class IsolatedStoreHandler(StoreHandler):
    store = None
    sessions = {}


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
        IsolatedStoreHandler.sessions = {"api-test": {"expires": time.monotonic() + 3600}}
        IsolatedStoreHandler.login_attempts.clear()
        self.admin_cookie = "estrela_admin=api-test"

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

    def test_security_headers_are_set(self):
        with urlopen(f"{self.base_url}/api/status") as response:
            headers = response.headers
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")

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
        with urlopen(Request(f"{self.base_url}/api/admin/orders", headers={"Cookie":self.admin_cookie}), timeout=2) as response:
            orders = json.load(response)["orders"]
        self.assertEqual(orders[0]["id"], result["id"])

    def test_admin_can_create_category_and_product(self):
        def post(path, payload):
            request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "Cookie":self.admin_cookie}, method="POST")
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
        with urlopen(Request(f"{self.base_url}/api/admin/summary", headers={"Cookie":self.admin_cookie}), timeout=2) as response:
            summary = json.load(response)
        self.assertEqual(summary["products"], 5)
        self.assertEqual(summary["orders"], 0)

    def admin_request(self, path, method="GET", payload=None, cookie=None, origin=None, client_ip=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(f"{self.base_url}{path}", data=data, method=method,
            headers={"Content-Type":"application/json", "Origin":origin or self.base_url,
                **({"Cookie":cookie} if cookie else {}), **({"CF-Connecting-IP":client_ip} if client_ip else {})})
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.load(response), response.headers.get("Set-Cookie")
        except HTTPError as error:
            return error.code, json.load(error), error.headers.get("Set-Cookie")

    def test_admin_api_requires_login_and_setup_creates_a_session(self):
        status, _, _ = self.admin_request("/api/admin/products")
        self.assertEqual(status, 401)
        status, result, cookie = self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        })
        self.assertEqual(status, 201)
        self.assertTrue(cookie.startswith("estrela_admin="))
        session_status, session, _ = self.admin_request("/api/admin/session", cookie=cookie.split(";",1)[0])
        self.assertEqual(session_status, 200)
        self.assertTrue(session["authenticated"])

    def test_store_api_fails_closed_when_supabase_is_not_configured(self):
        previous_store = IsolatedStoreHandler.store
        previous_token = os.environ.get("ESTRELA_EDGE_API_TOKEN")
        IsolatedStoreHandler.store = None
        os.environ["ESTRELA_EDGE_API_TOKEN"] = ""
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(f"{self.base_url}/api/status", timeout=2)
            self.assertEqual(error.exception.code, 503)
            self.assertIn("Supabase", json.load(error.exception)["error"])
        finally:
            IsolatedStoreHandler.store = previous_store
            if previous_token is None:
                os.environ.pop("ESTRELA_EDGE_API_TOKEN", None)
            else:
                os.environ["ESTRELA_EDGE_API_TOKEN"] = previous_token

    def test_wrong_admin_password_is_rejected(self):
        self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        })
        status, result, _ = self.admin_request("/api/admin/login", "POST", {
            "username":"login-admin", "password":"senha-incorreta-2026"
        })
        self.assertEqual(status, 401)
        self.assertIn("incorret", result["error"])

    def test_admin_setup_can_only_happen_once(self):
        self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        })
        status, _, _ = self.admin_request("/api/admin/setup", "POST", {
            "username":"outro-admin", "password":"OutraSenhaForte2026!"
        })
        self.assertEqual(status, 409)

    def test_admin_can_log_in_and_logout(self):
        self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        })
        status, _, cookie = self.admin_request("/api/admin/logout", "POST", {},
            cookie=None)
        self.assertEqual(status, 200)
        status, _, cookie = self.admin_request("/api/admin/login", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        })
        self.assertEqual(status, 200)
        status, _, _ = self.admin_request("/api/admin/products", cookie=cookie.split(";",1)[0])
        self.assertEqual(status, 200)
        status, _, _ = self.admin_request("/api/admin/logout", "POST", {}, cookie=cookie.split(";",1)[0])
        self.assertEqual(status, 200)
        status, _, _ = self.admin_request("/api/admin/products", cookie=cookie.split(";",1)[0])
        self.assertEqual(status, 401)

    def test_admin_setup_rejects_cross_origin_request(self):
        status, _, _ = self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        }, origin="https://attacker.example")
        self.assertEqual(status, 403)

    def test_admin_setup_rejects_requests_forwarded_from_public_proxy(self):
        status, _, _ = self.admin_request("/api/admin/setup", "POST", {
            "username":"login-admin", "password":"MinhaSenhaForte2026!"
        }, client_ip="203.0.113.20")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
