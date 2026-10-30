"""Small SQLite data layer for the local Estrela Concept demonstration."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from catalog import PRODUCTS

STATUSES = {"novo", "em_andamento", "concluido", "cancelado"}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def _money_cents(value) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Informe um preço válido.") from None
    if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000"):
        raise ValueError("O preço deve ser maior que zero e menor que R$ 1.000.000.")
    return int((amount * 100).quantize(Decimal("1")))


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category_id TEXT NOT NULL REFERENCES categories(id),
                    tagline TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price_cents INTEGER NOT NULL CHECK(price_cents > 0),
                    image TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS variants (
                    id INTEGER PRIMARY KEY,
                    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    size TEXT NOT NULL,
                    color TEXT NOT NULL,
                    stock INTEGER NOT NULL CHECK(stock >= 0),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    UNIQUE(product_id, size, color)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('novo','em_andamento','concluido','cancelado')),
                    total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY,
                    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    size TEXT NOT NULL,
                    color TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    unit_price_cents INTEGER NOT NULL,
                    line_total_cents INTEGER NOT NULL
                );
            """)
            if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
                for name in dict.fromkeys(product["category"] for product in PRODUCTS):
                    db.execute("INSERT INTO categories(id,name) VALUES(?,?)", (_slug(name), name))
            if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
                for product in PRODUCTS:
                    self._save_product(db, product)

    @staticmethod
    def _validate_product(product):
        if not isinstance(product, dict):
            raise ValueError("Produto inválido.")
        product_id = product.get("id")
        if not isinstance(product_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", product_id) or len(product_id) > 70:
            raise ValueError("O código do produto deve usar letras minúsculas, números e hífens.")
        fields = {key: product.get(key) for key in ("name", "category", "tagline", "description", "image")}
        limits = {"name": 100, "category": 60, "tagline": 160, "description": 1200, "image": 2048}
        for key, value in fields.items():
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limits[key]:
                raise ValueError(f"Preencha {key} com até {limits[key]} caracteres.")
        if not fields["image"].startswith(("https://", "/static/")):
            raise ValueError("A imagem deve usar HTTPS ou um caminho local /static/.")
        price = _money_cents(product.get("price"))
        variants = product.get("variants")
        if not isinstance(variants, list) or not variants or len(variants) > 200:
            raise ValueError("Cadastre ao menos uma variação (máximo de 200).")
        seen = set()
        valid_variants = []
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError("Variação inválida.")
            size, color, stock = variant.get("size"), variant.get("color"), variant.get("stock")
            if not isinstance(size, str) or not size.strip() or len(size) > 30 or not isinstance(color, str) or not color.strip() or len(color) > 40:
                raise ValueError("Informe tamanho e cor para cada variação.")
            if isinstance(stock, bool) or not isinstance(stock, int) or not 0 <= stock <= 1_000_000:
                raise ValueError("O estoque deve ser um número inteiro entre 0 e 1.000.000.")
            key = (size.strip(), color.strip())
            if key in seen:
                raise ValueError("Não repita a mesma combinação de tamanho e cor.")
            seen.add(key)
            valid_variants.append({"size": key[0], "color": key[1], "stock": stock, "active": variant.get("active") is not False})
        return product_id, fields, price, bool(product.get("active", True)), valid_variants

    @staticmethod
    def _save_product(db, product):
        product_id, fields, price, active, variants = Store._validate_product(product)
        category = db.execute("SELECT id FROM categories WHERE name=? AND active=1", (fields["category"].strip(),)).fetchone()
        if not category:
            raise ValueError("Selecione uma categoria ativa.")
        db.execute("""INSERT INTO products(id,name,category_id,tagline,description,price_cents,image,active)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
            category_id=excluded.category_id,tagline=excluded.tagline,description=excluded.description,
            price_cents=excluded.price_cents,image=excluded.image,active=excluded.active""",
            (product_id, fields["name"].strip(), category["id"], fields["tagline"].strip(), fields["description"].strip(), price, fields["image"].strip(), active))
        db.execute("DELETE FROM variants WHERE product_id=?", (product_id,))
        db.executemany("INSERT INTO variants(product_id,size,color,stock,active) VALUES(?,?,?,?,?)",
            [(product_id, v["size"], v["color"], v["stock"], v["active"]) for v in variants])
        return product_id

    def save_product(self, product):
        try:
            with self._connect() as db:
                product_id = self._save_product(db, product)
        except sqlite3.IntegrityError as error:
            raise ValueError("Já existe um produto com este código ou uma combinação repetida.") from error
        return next(item for item in self.products(include_inactive=True) if item["id"] == product_id)

    def set_product_active(self, product_id, active):
        with self._connect() as db:
            result = db.execute("UPDATE products SET active=? WHERE id=?", (bool(active), product_id))
            if not result.rowcount:
                raise ValueError("Produto não encontrado.")

    def products(self, include_inactive=False):
        with self._connect() as db:
            rows = db.execute("""SELECT p.*, c.name AS category FROM products p
                JOIN categories c ON c.id=p.category_id WHERE (? OR p.active=1) ORDER BY p.name""",
                (include_inactive,)).fetchall()
            result = []
            for row in rows:
                variants = db.execute("SELECT size,color,stock,active FROM variants WHERE product_id=? ORDER BY size,color", (row["id"],)).fetchall()
                result.append({"id": row["id"], "name": row["name"], "category": row["category"],
                    "tagline": row["tagline"], "description": row["description"], "price": row["price_cents"] / 100,
                    "image": row["image"], "active": bool(row["active"]),
                    "variants": [{"size": v["size"], "color": v["color"], "stock": v["stock"], "active": bool(v["active"])} for v in variants]})
            return result

    def categories(self):
        with self._connect() as db:
            return [{"id": row["id"], "name": row["name"], "active": bool(row["active"])}
                for row in db.execute("SELECT * FROM categories ORDER BY name")]

    def save_category(self, name):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
            raise ValueError("O nome da categoria deve ter entre 1 e 60 caracteres.")
        name = name.strip()
        category_id = _slug(name)
        if not category_id:
            raise ValueError("Informe um nome de categoria válido.")
        try:
            with self._connect() as db:
                db.execute("INSERT INTO categories(id,name) VALUES(?,?)", (category_id, name))
        except sqlite3.IntegrityError as error:
            raise ValueError("Esta categoria já existe ou gera um código repetido.") from error
        return {"id": category_id, "name": name, "active": True}

    def create_order(self, customer, items):
        if not isinstance(customer, dict):
            raise ValueError("Informe os dados do cliente.")
        name, phone = customer.get("name"), re.sub(r"\D", "", str(customer.get("phone", "")))
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise ValueError("Informe seu nome (até 100 caracteres).")
        if not phone.isdigit() or not 10 <= len(phone) <= 13:
            raise ValueError("Informe um WhatsApp válido com DDD.")
        if not isinstance(items, list) or not items or len(items) > 50:
            raise ValueError("Adicione entre 1 e 50 itens ao carrinho.")
        order_id = uuid.uuid4().hex[:10].upper()
        aggregated = {}
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError("Um item do pedido está inválido.")
                    product_id, size, color, quantity = (item.get("productId"), item.get("size"), item.get("color"), item.get("quantity"))
                    if not isinstance(product_id, str) or not isinstance(size, str) or not isinstance(color, str):
                        raise ValueError("Uma opção do pedido está inválida.")
                    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 10:
                        raise ValueError("A quantidade deve estar entre 1 e 10.")
                    key = (product_id, size, color)
                    aggregated[key] = aggregated.get(key, 0) + quantity
                    if aggregated[key] > 10:
                        raise ValueError("A quantidade máxima por opção é 10.")
                validated = []
                total_cents = 0
                for (product_id, size, color), quantity in aggregated.items():
                    row = db.execute("""SELECT p.name,p.price_cents,p.active,v.stock,v.active AS variant_active
                        FROM products p JOIN variants v ON v.product_id=p.id
                        WHERE p.id=? AND v.size=? AND v.color=?""", (product_id, size, color)).fetchone()
                    if not row or not row["active"] or not row["variant_active"]:
                        raise ValueError("Um dos produtos ou tamanhos não está disponível.")
                    if quantity > row["stock"]:
                        raise ValueError(f"Estoque insuficiente para {row['name']} ({size}).")
                    line = row["price_cents"] * quantity
                    total_cents += line
                    validated.append({"name": row["name"], "size": size, "color": color, "quantity": quantity,
                        "unitPrice": row["price_cents"] / 100, "lineTotal": line / 100,
                        "productId": product_id})
                db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)", (order_id, name.strip(), phone, "novo", total_cents, datetime.now(timezone.utc).isoformat()))
                for item in validated:
                    db.execute("UPDATE variants SET stock=stock-? WHERE product_id=? AND size=? AND color=?",
                        (item["quantity"], item["productId"], item["size"], item["color"]))
                    db.execute("INSERT INTO order_items(order_id,product_id,product_name,size,color,quantity,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?,?,?)",
                        (order_id, item["productId"], item["name"], item["size"], item["color"], item["quantity"], round(item["unitPrice"]*100), round(item["lineTotal"]*100)))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"id": order_id, "status": "novo", "items": [{k:v for k,v in item.items() if k != "productId"} for item in validated], "total": total_cents / 100, "customer": {"name": name.strip(), "phone": phone}}

    def orders(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
            return [{"id": row["id"], "customerName": row["customer_name"], "customerPhone": row["customer_phone"],
                "status": row["status"], "total": row["total_cents"] / 100, "createdAt": row["created_at"],
                "items": [{"name": item["product_name"], "size": item["size"], "color": item["color"],
                    "quantity": item["quantity"], "unitPrice": item["unit_price_cents"] / 100,
                    "lineTotal": item["line_total_cents"] / 100} for item in db.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (row["id"],))]}
                for row in rows]

    def update_order_status(self, order_id, status):
        if status not in STATUSES:
            raise ValueError("Status de pedido inválido.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            order = db.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                db.rollback()
                raise ValueError("Pedido não encontrado.")
            if order["status"] in {"cancelado", "concluido"} and status != order["status"]:
                db.rollback()
                raise ValueError("Pedidos cancelados ou concluídos não podem ser reabertos.")
            if status == "cancelado" and order["status"] != "cancelado":
                db.execute("""UPDATE variants SET stock=stock+(SELECT oi.quantity FROM order_items oi
                    WHERE oi.order_id=? AND variants.product_id=oi.product_id AND variants.size=oi.size AND variants.color=oi.color)
                    WHERE EXISTS (SELECT 1 FROM order_items oi
                    WHERE oi.order_id=? AND variants.product_id=oi.product_id AND variants.size=oi.size AND variants.color=oi.color)""", (order_id, order_id))
            db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
            db.commit()

    def summary(self):
        with self._connect() as db:
            total_products = db.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
            low_stock = db.execute("SELECT COUNT(*) FROM variants WHERE active=1 AND stock<=3").fetchone()[0]
            orders = db.execute("SELECT status,COUNT(*) AS count,COALESCE(SUM(total_cents),0) AS total FROM orders GROUP BY status").fetchall()
            return {"products": total_products, "lowStockVariants": low_stock,
                "orders": sum(row["count"] for row in orders),
                "sales": sum(row["total"] for row in orders if row["status"] == "concluido") / 100,
                "byStatus": {row["status"]: {"count": row["count"], "total": row["total"] / 100} for row in orders}}
