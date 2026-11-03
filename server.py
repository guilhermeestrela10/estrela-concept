"""Servidor local do MVP Estrela Concept, usando apenas a biblioteca padrão."""

from __future__ import annotations

import json
import smtplib
import os
import secrets
import sys
import time
import hmac
import threading
from collections import defaultdict, deque
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from store import SupabaseStore

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
ADMIN_SETUP_TOKEN = os.environ.get("ESTRELA_ADMIN_SETUP_TOKEN", "")
MAX_IMAGE_SIZE = 4 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "image/webp": b"RIFF"}
ADMIN_PANEL_URL = os.environ.get("ADMIN_PANEL_URL", "https://estrela-concept.onrender.com/admin")


def build_order_notification(order):
    sender = os.environ["GMAIL_SMTP_USER"]
    message = EmailMessage()
    message["From"] = f"Estrela Concept <{sender}>"
    message["To"] = os.environ["ORDER_NOTIFICATION_EMAIL"]
    is_test = order["id"] == "TESTE"
    message["Subject"] = "Teste do aviso de pedidos · Estrela Concept" if is_test else f"Novo pedido recebido · #{order['id']}"
    items = "\n".join(
        f"• {item['quantity']}× {item['name']} · {item['size']} · {item['color']}"
        for item in order["items"]
    )
    total = f"R$ {float(order['total']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    intro = "Este é um e-mail de teste. Nenhum pedido foi criado.\n\n" if is_test else "A Estrela Concept recebeu um novo pedido.\n\n"
    message.set_content(
        intro +
        f"Pedido: #{order['id']}\nItens:\n{items}\nTotal: {total}\n\n"
        "Para ver o telefone do cliente e conversar pelo WhatsApp, acesse o painel administrativo:\n"
        f"{ADMIN_PANEL_URL}\n\nO painel exige login."
    )
    return message


def send_order_notification(order):
    try:
        message = build_order_notification(order)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(os.environ["GMAIL_SMTP_USER"], os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
            smtp.send_message(message)
        return True
    except Exception as error:
        print(f"Falha ao enviar aviso por e-mail do pedido #{order.get('id')}: {type(error).__name__}", file=sys.stderr)
        return False


def queue_order_notification(order):
    if not all(os.environ.get(key) for key in ("GMAIL_SMTP_USER", "GMAIL_APP_PASSWORD", "ORDER_NOTIFICATION_EMAIL")):
        return False
    try:
        threading.Thread(target=send_order_notification, args=(order,), daemon=True, name="order-email").start()
        return True
    except RuntimeError as error:
        print(f"Falha ao iniciar aviso por e-mail do pedido #{order.get('id')}: {type(error).__name__}", file=sys.stderr)
        return False


def validate_image(content_type, image):
    if content_type not in IMAGE_TYPES:
        raise ValueError("Envie uma foto JPEG, PNG ou WebP.")
    if not image:
        raise ValueError("O arquivo de imagem está vazio.")
    if len(image) > MAX_IMAGE_SIZE:
        raise OverflowError("A foto deve ter no máximo 4 MB.")
    signature = IMAGE_TYPES[content_type]
    valid = image.startswith(signature) if content_type != "image/webp" else image.startswith(b"RIFF") and image[8:12] == b"WEBP"
    if not valid:
        raise ValueError("O conteúdo não corresponde ao formato de imagem informado.")
    return content_type, image


class StoreHandler(SimpleHTTPRequestHandler):
    store = None
    sessions = {}
    login_attempts = defaultdict(deque)
    recovery_attempts = defaultdict(deque)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
        self.current_admin_token = None

    def get_store(self):
        if self.__class__.store is None:
            self.__class__.store = SupabaseStore.configured()
            if self.__class__.store is None:
                raise ValueError("Configure ESTRELA_EDGE_API_TOKEN para conectar ao Supabase.")
        return self.__class__.store

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https:; connect-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
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
        store = self.get_store()
        if isinstance(store, SupabaseStore):
            if not token:
                return None
            return token.value if store.admin_session_valid(token.value) else None
        session = self.__class__.sessions.get(token.value) if token else None
        if session and session["expires"] > time.monotonic():
            return token.value
        if token:
            self.__class__.sessions.pop(token.value, None)
        return None

    def local_setup_allowed(self):
        try:
            forwarded = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            return HOST in {"127.0.0.1", "::1", "localhost"} and self.client_address[0] in {"127.0.0.1", "::1"} and not forwarded
        except (IndexError, TypeError):
            return False

    def client_ip(self):
        return self.headers.get("CF-Connecting-IP") or self.client_address[0]

    def require_admin(self):
        if not self.origin_is_same():
            self.send_json({"error": "Origem da solicitação não permitida."}, 403)
            return False
        token = self.admin_session()
        if not token:
            self.send_json({"error": "Entre no painel para continuar."}, 401)
            return False
        self.current_admin_token = token
        return True

    def admin_call(self, method, *args, **kwargs):
        store = self.get_store()
        if isinstance(store, SupabaseStore):
            kwargs["session_token"] = self.current_admin_token
        return getattr(store, method)(*args, **kwargs)

    def create_admin_session(self, token=None):
        if token:
            secure = urlparse(self.headers.get("Origin", "")).scheme == "https"
            return f"estrela_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800" + ("; Secure" if secure else "")
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
                "setupAllowed": self.local_setup_allowed() or bool(ADMIN_SETUP_TOKEN),
                "recoveryAvailable": isinstance(self.get_store(), SupabaseStore)})
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
            self.send_json(self.admin_call("summary"))
            return
        if path == "/api/admin/products":
            self.send_json({"products": self.admin_call("products", include_inactive=True) if isinstance(self.get_store(), SupabaseStore) else self.get_store().products(include_inactive=True)})
            return
        if path == "/api/admin/categories":
            self.send_json({"categories": self.admin_call("admin_categories") if isinstance(self.get_store(), SupabaseStore) else self.get_store().categories()})
            return
        if path == "/api/admin/orders":
            self.send_json({"orders": self.admin_call("admin_orders") if isinstance(self.get_store(), SupabaseStore) else self.get_store().orders()})
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

    def read_image_upload(self):
        content_type = self.headers.get("Content-Type", "").lower()
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("O arquivo de imagem está vazio.")
        if length > MAX_IMAGE_SIZE:
            raise OverflowError("A foto deve ter no máximo 4 MB.")
        image = self.rfile.read(length)
        if len(image) != length:
            raise ValueError("O envio da foto foi interrompido.")
        return validate_image(content_type, image)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/admin/upload-image":
                if not self.origin_is_same():
                    self.send_json({"error": "Origem da solicitação não permitida."}, 403)
                    return
                if not self.require_admin():
                    return
                content_type, image = self.read_image_upload()
                store = self.get_store()
                if not isinstance(store, SupabaseStore):
                    self.send_json({"error": "O envio de fotos exige o armazenamento Supabase."}, 503)
                    return
                self.send_json({"url": self.admin_call("upload_product_image", content_type, image)})
                return
            payload = self.read_json()
            if not self.origin_is_same():
                self.send_json({"error": "Origem da solicitação não permitida."}, 403)
                return
            if path == "/api/admin/password-recovery":
                store = self.get_store()
                if not isinstance(store, SupabaseStore):
                    self.send_json({"error": "A recuperação de senha exige conexão com o Supabase."}, 503)
                    return
                attempts = self.__class__.recovery_attempts[self.client_ip()]
                now = time.monotonic()
                while attempts and now - attempts[0] > 300:
                    attempts.popleft()
                if len(attempts) >= 5:
                    self.send_json({"error": "Muitas solicitações. Aguarde 5 minutos antes de tentar novamente."}, 429)
                    return
                attempts.append(now)
                username = payload.get("username")
                if not isinstance(username, str) or not 4 <= len(username) <= 40:
                    self.send_json({"error": "Informe seu usuário do painel."}, 400)
                    return
                try:
                    store.request_admin_password_reset(username, "https://estrela-concept.onrender.com/admin")
                except ValueError:
                    self.send_json({"error": "Não foi possível solicitar a recuperação agora. Tente novamente mais tarde."}, 503)
                    return
                self.send_json({"ok": True, "message": "Se os dados corresponderem à conta, você receberá instruções no e-mail cadastrado."})
                return
            if path == "/api/admin/password-update":
                store = self.get_store()
                token, password = payload.get("accessToken"), payload.get("password")
                if not isinstance(store, SupabaseStore):
                    self.send_json({"error": "A redefinição de senha exige conexão com o Supabase."}, 503)
                    return
                if not isinstance(token, str) or not 20 <= len(token) <= 4096 or not isinstance(password, str) or not 12 <= len(password) <= 256:
                    self.send_json({"error": "Link inválido ou expirado. Solicite uma nova recuperação."}, 400)
                    return
                try:
                    store.update_admin_password(token, password)
                except ValueError:
                    self.send_json({"error": "Link inválido ou expirado, ou senha não aceita. Solicite uma nova recuperação."}, 400)
                    return
                self.send_json({"ok": True}, 200, {"Set-Cookie": "estrela_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
                return
            if path == "/api/admin/setup":
                store = self.get_store()
                if store.admin_configured():
                    self.send_json({"error": "O acesso administrativo já foi configurado."}, 409)
                    return
                if not self.local_setup_allowed() and (not ADMIN_SETUP_TOKEN or not hmac.compare_digest(str(payload.get("setupToken", "")), ADMIN_SETUP_TOKEN)):
                    self.send_json({"error": "A configuração inicial exige autorização local ou o token de configuração."}, 403)
                    return
                if isinstance(store, SupabaseStore):
                    setup = store.setup_admin(payload.get("username"), payload.get("password"))
                    cookie = self.create_admin_session(setup["sessionToken"])
                else:
                    store.setup_admin(payload.get("username"), payload.get("password"))
                    cookie = self.create_admin_session()
                self.send_json({"ok": True}, 201, {"Set-Cookie": cookie})
                return
            if path == "/api/admin/login":
                store = self.get_store()
                if not store.admin_configured():
                    self.send_json({"error": "Configure o acesso administrativo antes de entrar."}, 409)
                    return
                attempts = self.__class__.login_attempts[self.client_ip()]
                now = time.monotonic()
                while attempts and now - attempts[0] > 300:
                    attempts.popleft()
                if len(attempts) >= 5:
                    self.send_json({"error": "Muitas tentativas. Aguarde 5 minutos antes de tentar novamente."}, 429)
                    return
                if isinstance(store, SupabaseStore):
                    try:
                        login = store.admin_login(payload.get("username"), payload.get("password"))
                    except ValueError:
                        login = None
                    if not login:
                        attempts.append(now)
                        self.send_json({"error": "Usuário ou senha incorretos."}, 401)
                        return
                    cookie = self.create_admin_session(login["sessionToken"])
                else:
                    if not store.verify_admin(payload.get("username"), payload.get("password")):
                        attempts.append(now)
                        self.send_json({"error": "Usuário ou senha incorretos."}, 401)
                        return
                    cookie = self.create_admin_session()
                attempts.clear()
                self.send_json({"ok": True}, 200, {"Set-Cookie": cookie})
                return
            if path == "/api/admin/logout":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                token = cookie.get("estrela_admin")
                store = self.get_store()
                if token and isinstance(store, SupabaseStore):
                    store.admin_logout(token.value)
                elif token:
                    self.__class__.sessions.pop(token.value, None)
                self.send_json({"ok": True}, 200, {"Set-Cookie": "estrela_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
                return
            if path.startswith("/api/admin/") and not self.require_admin():
                return
            if path == "/api/checkout":
                order = self.get_store().create_order(payload.get("customer"), payload.get("items"))
                queue_order_notification(order)
                self.send_json({"ok": True, **order, "message": "Pedido registrado."})
            elif path == "/api/admin/products":
                product = self.admin_call("save_product", payload)
                self.send_json({"product": product}, 201)
            elif path == "/api/admin/categories":
                category = self.admin_call("save_category", payload.get("name"))
                self.send_json({"category": category}, 201)
            elif path == "/api/admin/test-email":
                if not all(os.environ.get(key) for key in ("GMAIL_SMTP_USER", "GMAIL_APP_PASSWORD", "ORDER_NOTIFICATION_EMAIL")):
                    self.send_json({"error": "Configure o Gmail no Render antes de enviar o teste."}, 503)
                    return
                sent = send_order_notification({
                    "id": "TESTE", "total": 0,
                    "items": [{"quantity": 1, "name": "Este e-mail é apenas um teste", "size": "—", "color": "—"}],
                })
                if sent:
                    self.send_json({"ok": True, "message": "E-mail de teste enviado. Confira a caixa de entrada e o spam."})
                else:
                    self.send_json({"error": "O Gmail recusou ou não conseguiu enviar. Confira a senha de app e os logs do Render."}, 502)
            else:
                self.send_json({"error": "Endpoint não encontrado."}, 404)
        except OverflowError as error:
            self.send_json({"error": str(error)}, 413)
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
            self.send_json({"product": self.admin_call("save_product", payload)})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_PATCH(self) -> None:
        if not self.require_admin():
            return
        parts = urlparse(self.path).path.strip("/").split("/")
        try:
            payload = self.read_json()
            if len(parts) == 4 and parts[:3] == ["api", "admin", "orders"]:
                self.admin_call("update_order_status", parts[3], payload.get("status"))
                self.send_json({"ok": True})
            elif len(parts) == 4 and parts[:3] == ["api", "admin", "products"]:
                self.admin_call("set_product_active", parts[3], payload.get("active") is True)
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
    print("Avisos de pedidos por e-mail: " + ("ativos" if all(os.environ.get(key) for key in ("GMAIL_SMTP_USER", "GMAIL_APP_PASSWORD", "ORDER_NOTIFICATION_EMAIL")) else "configure GMAIL_SMTP_USER, GMAIL_APP_PASSWORD e ORDER_NOTIFICATION_EMAIL"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
