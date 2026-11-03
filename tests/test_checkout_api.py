"""Regression tests for the local checkout API."""

import json
import os
import threading
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import StoreHandler, build_order_notification
import server
from store import Store, SupabaseStore


class IsolatedStoreHandler(StoreHandler):
    store = None
    sessions = {}


class RecoveryStore(SupabaseStore):
    def __init__(self):
        self.recovery_requests = []
        self.password_updates = []

    def request_admin_password_reset(self, username, redirect_to):
        self.recovery_requests.append((username, redirect_to))

    def update_admin_password(self, access_token, password):
        self.password_updates.append((access_token, password))


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
        IsolatedStoreHandler.recovery_attempts.clear()
        IsolatedStoreHandler.checkout_attempts.clear()
        IsolatedStoreHandler.checkout_global.clear()
        IsolatedStoreHandler.login_failures.clear()
        self.admin_cookie = "estrela_admin=api-test"

    def post_checkout(self, items, customer=None, client_ip=None):
        body = json.dumps({"items": items, "customer": customer or {"name": "Ana Teste", "phone": "86999999999"}}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if client_ip:
            headers["X-Forwarded-For"] = client_ip
        request = Request(
            f"{self.base_url}/api/checkout",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            return error.code, json.load(error)
        with response:
            return response.status, json.load(response)

    def post_image_upload(self, image, content_type="image/jpeg", cookie=True):
        headers = {"Content-Type": content_type}
        if cookie:
            headers["Cookie"] = self.admin_cookie
        request = Request(f"{self.base_url}/api/admin/upload-image", data=image, headers=headers, method="POST")
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            return error.code, json.load(error)
        with response:
            return response.status, json.load(response)

    def test_security_headers_are_set(self):
        with urlopen(f"{self.base_url}/api/status") as response:
            headers = response.headers
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")

    def test_static_assets_can_be_cached_briefly(self):
        with urlopen(f"{self.base_url}/static/styles.css") as response:
            self.assertEqual(response.headers["Cache-Control"], "public, max-age=300")

    def test_admin_forms_do_not_prefill_the_username(self):
        with urlopen(f"{self.base_url}/admin") as response:
            page = response.read().decode("utf-8")
        self.assertNotIn('value="login-admin"', page)

    def test_unexpected_api_errors_return_a_generic_response(self):
        with patch.object(IsolatedStoreHandler.store, "products", side_effect=RuntimeError("private backend detail")):
            with self.assertRaises(HTTPError) as error:
                urlopen(f"{self.base_url}/api/products", timeout=2)
        self.assertEqual(error.exception.code, 500)
        body = json.load(error.exception)
        self.assertIn("Erro interno", body["error"])
        self.assertNotIn("private backend detail", body["error"])

    def test_image_upload_requires_admin_session(self):
        status, _ = self.post_image_upload(b"\xff\xd8\xff\xd9", cookie=False)
        self.assertEqual(status, 401)

    def test_image_upload_rejects_non_image_content(self):
        status, result = self.post_image_upload(b"not an image")
        self.assertEqual(status, 400)
        self.assertIn("conteúdo", result["error"])

    def test_image_upload_rejects_oversized_files(self):
        from server import MAX_IMAGE_SIZE, validate_image
        with self.assertRaises(OverflowError):
            validate_image("image/jpeg", b"\xff\xd8\xff" + b"0" * MAX_IMAGE_SIZE)

    def test_checkout_uses_server_price_and_returns_subtotal(self):
        status, result = self.post_checkout([
            {"productId": "legging-lua", "size": "M", "color": "Preto", "quantity": 2, "price": 0}
        ])
        self.assertEqual(status, 200)
        self.assertEqual(result["total"], 279.8)

    def test_checkout_is_rate_limited_per_ip(self):
        statuses = [self.post_checkout([])[0] for _ in range(25)]
        self.assertEqual(statuses.count(429), 5)

    def test_checkout_limits_are_separate_for_forwarded_client_ips(self):
        first_ip = "203.0.113.10"
        second_ip = "203.0.113.11"
        first_ip_statuses = [self.post_checkout([], client_ip=first_ip)[0] for _ in range(21)]
        second_ip_status = self.post_checkout([], client_ip=second_ip)[0]
        self.assertEqual(first_ip_statuses.count(429), 1)
        self.assertEqual(second_ip_status, 400)

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
        with patch.object(server, "queue_order_notification", return_value=True) as notify:
            status, result = self.post_checkout([
                {"productId": "legging-lua", "size": "P", "color": "Preto", "quantity": 1}
            ])
        self.assertEqual(status, 200)
        self.assertIn("id", result)
        self.assertEqual(notify.call_args.args[0]["id"], result["id"])
        with urlopen(Request(f"{self.base_url}/api/admin/orders", headers={"Cookie":self.admin_cookie}), timeout=2) as response:
            orders = json.load(response)["orders"]
        self.assertEqual(orders[0]["id"], result["id"])

    def test_order_notification_links_to_panel_without_customer_phone(self):
        with patch.dict(os.environ, {
            "GMAIL_SMTP_USER": "estrelaconcept0@gmail.com",
            "ORDER_NOTIFICATION_EMAIL": "estrelaconcept0@gmail.com",
        }, clear=False):
            message = build_order_notification({
                "id": "ORDER123", "total": 90, "customerPhone": "5586999999999",
                "items": [{"name": "Legging Lua", "size": "M", "color": "Preto", "quantity": 1}],
            })
        body = message.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("https://estrela-concept.onrender.com/admin", body)
        self.assertIn("ORDER123", body)
        self.assertIn("Legging Lua", body)
        self.assertNotIn("5586999999999", body)
        html_body = message.get_body(preferencelist=("html",)).get_content()
        self.assertTrue(message.is_multipart())
        self.assertIn("Novo pedido recebido", message["Subject"])
        self.assertIn("https://estrela-concept.onrender.com/admin", html_body)
        self.assertIn("Legging Lua", html_body)
        self.assertNotIn("5586999999999", html_body)

    def test_render_order_notification_uses_resend_https_api(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"id":"email-123"}'

        order = {
            "id": "ORDER123", "total": 90, "customerPhone": "5586999999999",
            "items": [{"name": "Legging Lua", "size": "M", "color": "Preto", "quantity": 1}],
        }
        with patch.dict(os.environ, {
            "RENDER": "true", "RESEND_API_KEY": "re_test_key",
            "RESEND_FROM_EMAIL": "Estrela Concept <onboarding@resend.dev>",
            "ORDER_NOTIFICATION_EMAIL": "estrelaconcept0@gmail.com",
        }, clear=True), patch("server.urllib.request.urlopen", return_value=Response()) as post:
            self.assertTrue(server.send_order_notification(order))

        request = post.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.get_header("Authorization"), "Bearer re_test_key")
        self.assertEqual(request.get_header("Idempotency-key"), "ORDER123")
        payload = json.loads(request.data)
        self.assertEqual(payload["to"], ["estrelaconcept0@gmail.com"])
        self.assertIn("ORDER123", payload["text"])
        self.assertIn("ORDER123", payload["html"])
        self.assertNotIn("5586999999999", payload["text"] + payload["html"])

    def test_render_does_not_try_blocked_gmail_smtp_without_resend(self):
        order = {"id": "ORDER124", "total": 10, "items": []}
        with patch.dict(os.environ, {
            "RENDER": "true", "GMAIL_SMTP_USER": "store@example.com",
            "GMAIL_APP_PASSWORD": "test-password", "ORDER_NOTIFICATION_EMAIL": "store@example.com",
        }, clear=True), patch("server.smtplib.SMTP_SSL") as smtp:
            self.assertFalse(server.send_order_notification(order))
        smtp.assert_not_called()

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

    def test_policies_page_is_served_and_has_review_notice(self):
        with urlopen(f"{self.base_url}/politicas", timeout=2) as response:
            page = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("Rascunho para revisão", page)
        self.assertIn("direito de arrependimento", page)

    def test_https_response_includes_hsts(self):
        request = Request(f"{self.base_url}/", headers={"X-Forwarded-Proto": "https"})
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.headers.get("Strict-Transport-Security"), "max-age=31536000")

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

    def test_password_recovery_is_generic_and_password_update_clears_session(self):
        store = RecoveryStore()
        IsolatedStoreHandler.store = store
        status, result, _ = self.admin_request("/api/admin/password-recovery", "POST", {"username": "login-admin"})
        self.assertEqual(status, 200)
        self.assertIn("Se os dados corresponderem", result["message"])
        self.assertEqual(store.recovery_requests, [("login-admin", "https://estrela-concept.onrender.com/admin")])

        status, _, cookie = self.admin_request("/api/admin/password-update", "POST", {
            "accessToken": "recovery-token-which-is-long-enough", "password": "UmaSenhaNovaForte2026!"
        })
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", cookie)
        self.assertEqual(store.password_updates, [("recovery-token-which-is-long-enough", "UmaSenhaNovaForte2026!")])

    def test_password_update_rejects_short_or_missing_recovery_token(self):
        store = RecoveryStore()
        IsolatedStoreHandler.store = store
        status, _, _ = self.admin_request("/api/admin/password-update", "POST", {
            "accessToken": "short", "password": "UmaSenhaNovaForte2026!"
        })
        self.assertEqual(status, 400)
        self.assertFalse(store.password_updates)

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
