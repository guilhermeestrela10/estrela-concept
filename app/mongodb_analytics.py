"""Aggregated product-view analytics stored in MongoDB Atlas."""

from __future__ import annotations

import os
from datetime import datetime, timezone


class ProductViewAnalytics:
    def __init__(self, uri: str, database: str):
        from pymongo import MongoClient

        self.client = MongoClient(uri, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
        self.views = self.client[database]["product_views"]

    @classmethod
    def from_env(cls):
        uri = os.environ.get("MONGODB_URI", "").strip()
        if not uri:
            return None
        try:
            database = os.environ.get("MONGODB_DATABASE", "estrela_concept").strip() or "estrela_concept"
            return cls(uri, database)
        except ImportError:
            return None

    def record_view(self, product_id: str) -> None:
        self.views.update_one(
            {"_id": product_id},
            {"$inc": {"views": 1}, "$set": {"updatedAt": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def top_products(self, limit: int = 5) -> list[dict]:
        return [
            {"productId": item["_id"], "views": item["views"]}
            for item in self.views.find({}, {"views": 1}).sort("views", -1).limit(min(max(limit, 1), 5))
        ]
