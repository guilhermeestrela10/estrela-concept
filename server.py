"""Servidor local do MVP Estrela Concept, usando apenas a biblioteca padrão."""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
import hmac
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from store import Store, SupabaseStore

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = Path(os.environ.get("ESTRELA_DB_PATH", ROOT / "data" / "estrela.sqlite3"))
ADMIN_SETUP_TOKEN = os.environ.get("ESTRELA_ADMIN_SETUP_TOKEN", "")


class StoreHandler(SimpleHTTPRequestHandler):
    store = None
    sessions = {}
    login_attempts = defaultdict(deque)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def get_store(self):
        if self.__class__.store is None:
            self.__class__.store = SupabaseStore.configured(DB_PATH) or Store(DB_PATH)
        return self.__class__.store

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data: dict, status: int = 200, headers: dict | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def origin_is_same(self):
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).netloc.casefold() == self.headers.get("Host", "").casefold()

    def admin_session(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("estrela_admin")
        session = self.__class__.sessions.get(token.value) if token else None
        if session and session["expires"] > time.monotonic():
            return token.value
        if token:
            self.__class__.sessions.pop(token.value, None)
        return None

    def local_setup_allowed(self):
        try:
            return HOST in {"127.0.0.1", "::1", "localhost"} and self.client_address[0] in {"127.0.0.1", "::1"}
        except (IndexError, TypeError):
            return False

    def require_admin(self):
        if not self.origin_is_same():
            self.send_json({"error": "Origem da solicitação não permitida."}, 403)
            return False
        if not self.admin_session():
            self.send_json({"error": "Entre no painel para continuar."}, 401)
            return False
        return True

    def create_admin_session(self):
        token = secrets.token_urlsafe(32)
        self.__class__.sessions[token] = {"expires": time.monotonic() + 8 * 60 * 60}
        secure = urlparse(self.headers.get("Origin", "")).scheme == "https"
        return f"estrela_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800" + ("; Secure" if secure else "")

    def do_GET(self) -> None:
        try:
            self._do_GET()
        except (ValueError, OSError) as error:
            self.send_json({"error": str(error)}, 503)

    def _do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json({"backend": "supabase" if isinstance(self.get_store(), SupabaseStore) else "local"})
            return
        if path == "/api/admin/session":
            self.send_json({"configured": self.get_store().admin_configured(), "authenticated": bool(self.admin_session()),
                "setupTokenRequired": bool(ADMIN_SETUP_TOKEN) and not self.local_setup_allowed(),
                "setupAllowed": self.local_setup_allowed() or bool(ADMIN_SETUP_TOKEN)})
            return
        if path.startswith("/api/admin/") and path != "/api/admin/login":
            if not self.require_admin():
                return
        if path == "/api/products":
            self.send_json({"products": self.get_store().products()})
            return
        if path == "/api/categories":
            self.send_json({"categories": [item for item in self.get_store().categories() if item["active"]]})
            return
        if path == "/api/admin/summary":
            self.send_json(self.get_store().summary())
            return
        if path == "/api/admin/products":
            self.send_json({"products": self.get_store().products(include_inactive=True)})
            return
        if path == "/api/admin/categories":
            self.send_json({"categories": self.get_store().categories()})
            return
        if path == "/api/admin/orders":
            self.send_json({"orders": self.get_store().orders()})
            return
        if path == "/admin":
            self.path = "/admin.html"
            super().do_GET()
            return
        if path.startswith("/api/"):
            self.send_json({"error": "Endpoint não encontrado."}, 404)
            return
        if path == "/":
            self.path = "/index.html"
        static_path = unquote(urlparse(self.path).path)
        if "\\" in static_path or ".." in Path(static_path).parts or not (
            static_path in {"/index.html", "/admin.html", "/favicon.ico"}
            or static_path.startswith("/static/")
        ):
            self.send_error(404)
            return
        super().do_GET()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64_000:
            raise ValueError("O conteúdo está vazio ou excede o tamanho permitido.")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Formato de dados inválido.")
        return payload

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            payload = self.read_json()
            if not self.origin_is_same():
                self.send_json({"error": "Origem da solicitação não permitida."}, 403)
                return
            if path == "/api/admin/setup":
                store = self.get_store()
                if store.admin_configured():
                    self.send_json({"error": "O acesso administrativo já foi configurado."}, 409)
                    return
                if not self.local_setup_allowed() and (not ADMIN_SETUP_TOKEN or not hmac.compare_digest(str(payload.get("setupToken", "")), ADMIN_SETUP_TOKEN)):
                    self.send_json({"error": "A configuração inicial exige autorização local ou o token de configuração."}, 403)
                    return
                store.setup_admin(payload.get("username"), payload.get("password"))
                self.send_json({"ok": True}, 201, {"Set-Cookie": self.create_admin_session()})
                return
            if path == "/api/admin/login":
                if not self.get_store().admin_configured():
                    self.send_json({"error": "Configure o acesso administrativo antes de entrar."}, 409)
                    return
                attempts = self.__class__.login_attempts[self.client_address[0]]
                now = time.monotonic()
                while attempts and now - attempts[0] > 300:
                    attempts.popleft()
                if len(attempts) >= 5:
                    self.send_json({"error": "Muitas tentativas. Aguarde 5 minutos antes de tentar novamente."}, 429)
                    return
                if not self.get_store().verify_admin(payload.get("username"), payload.get("password")):
                    attempts.append(now)
                    self.send_json({"error": "Usuário ou senha incorretos."}, 401)
                    return
                attempts.clear()
                self.send_json({"ok": True}, 200, {"Set-Cookie": self.create_admin_session()})
                return
            if path == "/api/admin/logout":
                token = self.admin_session()
                if token:
                    self.__class__.sessions.pop(token, None)
                self.send_json({"ok": True}, 200, {"Set-Cookie": "estrela_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
                return
            if path.startswith("/api/admin/") and not self.require_admin():
                return
            if path == "/api/checkout":
                order = self.get_store().create_order(payload.get("customer"), payload.get("items"))
                self.send_json({"ok": True, **order, "message": "Pedido registrado."})
            elif path == "/api/admin/products":
                product = self.get_store().save_product(payload)
                self.send_json({"product": product}, 201)
            elif path == "/api/admin/categories":
                category = self.get_store().save_category(payload.get("name"))
                self.send_json({"category": category}, 201)
            else:
                self.send_json({"error": "Endpoint não encontrado."}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_PUT(self) -> None:
        if not self.require_admin():
            return
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 4 or parts[:3] != ["api", "admin", "products"]:
            self.send_json({"error": "Endpoint não encontrado."}, 404)
            return
        try:
            payload = self.read_json()
            payload["id"] = parts[3]
            self.send_json({"product": self.get_store().save_product(payload)})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_PATCH(self) -> None:
        if not self.require_admin():
            return
        parts = urlparse(self.path).path.strip("/").split("/")
        try:
            payload = self.read_json()
            if len(parts) == 4 and parts[:3] == ["api", "admin", "orders"]:
                self.get_store().update_order_status(parts[3], payload.get("status"))
                self.send_json({"ok": True})
            elif len(parts) == 4 and parts[:3] == ["api", "admin", "products"]:
                self.get_store().set_product_active(parts[3], payload.get("active") is True)
                self.send_json({"ok": True})
            else:
                self.send_json({"error": "Endpoint não encontrado."}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer((HOST, PORT), StoreHandler)
    except OSError as error:
        if getattr(error, "winerror", None) == 10048 or error.errno in (48, 98, 10048):
            print(f"A porta {PORT} já está em uso. Feche a outra instância da loja e tente novamente.", file=sys.stderr)
            raise SystemExit(1)
        raise

    print(f"Estrela Concept disponível em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
