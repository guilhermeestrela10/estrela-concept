"""Servidor local do MVP Estrela Concept, usando apenas a biblioteca padrão."""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from store import Store

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = Path(os.environ.get("ESTRELA_DB_PATH", ROOT / "data" / "estrela.sqlite3"))


class StoreHandler(SimpleHTTPRequestHandler):
    store = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def get_store(self):
        if self.__class__.store is None:
            self.__class__.store = Store(DB_PATH)
        return self.__class__.store

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
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
            if path == "/api/checkout":
                order = self.get_store().create_order(payload.get("customer"), payload.get("items"))
                self.send_json({"ok": True, **order, "message": "Pedido de demonstração registrado."})
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
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 4 or parts[:3] != ["api", "admin", "orders"]:
            self.send_json({"error": "Endpoint não encontrado."}, 404)
            return
        try:
            payload = self.read_json()
            self.get_store().update_order_status(parts[3], payload.get("status"))
            self.send_json({"ok": True})
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
