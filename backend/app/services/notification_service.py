"""Notification repository and service for customer notifications."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from backend.app.config import get_settings
from backend.app.services.supabase_service import get_supabase_client


@runtime_checkable
class NotificationRepository(Protocol):
    async def create_notification(self, data: dict[str, Any]) -> dict[str, Any]: ...
    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]: ...
    async def mark_read(self, notification_id: str, user_id: str) -> dict[str, Any] | None: ...


import json
from functools import lru_cache
from pathlib import Path

NOTIFICATIONS_FILE = Path("backend/data/notifications.json")


class InMemoryNotificationRepository:
    def __init__(self, persistence_file: Path | None = NOTIFICATIONS_FILE) -> None:
        self._file = persistence_file
        self.notifications: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._file and self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            self.notifications[item["id"]] = item
            except Exception:
                pass

    def _save(self) -> None:
        if self._file:
            try:
                self._file.parent.mkdir(parents=True, exist_ok=True)
                self._file.write_text(
                    json.dumps(list(self.notifications.values()), indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

    async def create_notification(self, data: dict[str, Any]) -> dict[str, Any]:
        item = dict(data)
        self.notifications[item["id"]] = item
        self._save()
        return item

    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        user_items = [n for n in self.notifications.values() if n.get("user_id") == user_id]
        return sorted(user_items, key=lambda x: x.get("created_at", ""), reverse=True)

    async def mark_read(self, notification_id: str, user_id: str) -> dict[str, Any] | None:
        item = self.notifications.get(notification_id)
        if not item or item.get("user_id") != user_id:
            return None
        item["is_read"] = True
        item["read_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return item


_shared_notification_fallback = InMemoryNotificationRepository()


class SupabaseNotificationRepository:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client or get_supabase_client()
        self._fallback = _shared_notification_fallback

    async def create_notification(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = {k: v for k, v in data.items() if v is not None}
            response = await asyncio.to_thread(
                lambda: self._client.table("notifications").insert(payload).execute()
            )
            created = dict(response.data[0]) if response.data else payload
            # Also store in local fallback for rapid local querying/fault tolerance
            await self._fallback.create_notification(created)
            return created
        except Exception:
            return await self._fallback.create_notification(data)

    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        sb_items: list[dict[str, Any]] = []
        try:
            response = await asyncio.to_thread(
                lambda: self._client.table("notifications")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            sb_items = list(response.data or [])
        except Exception:
            sb_items = []

        fb_items = await self._fallback.list_by_user(user_id)
        seen_ids = set()
        merged: list[dict[str, Any]] = []
        for item in sb_items + fb_items:
            nid = item.get("id")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                merged.append(item)
        merged.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return merged

    async def mark_read(self, notification_id: str, user_id: str) -> dict[str, Any] | None:
        updated = None
        try:
            now = datetime.now(timezone.utc).isoformat()
            response = await asyncio.to_thread(
                lambda: self._client.table("notifications")
                .update({"is_read": True, "read_at": now})
                .eq("id", notification_id)
                .eq("user_id", user_id)
                .execute()
            )
            if response.data:
                updated = dict(response.data[0])
        except Exception:
            pass

        fb_updated = await self._fallback.mark_read(notification_id, user_id)
        return updated or fb_updated


@lru_cache(maxsize=1)
def get_notification_repository() -> NotificationRepository:
    settings = get_settings()
    if settings.persistence_backend == "supabase":
        return SupabaseNotificationRepository()
    return _shared_notification_fallback


class NotificationService:
    def __init__(self, repository: NotificationRepository | None = None) -> None:
        self.repository = repository or get_notification_repository()

    async def notify_customer(
        self,
        *,
        user_id: str,
        workflow_id: str | None = None,
        claim_id: str | None = None,
        notification_type: str,
        title: str,
        message: str,
    ) -> dict[str, Any]:
        data = {
            "id": f"NOTIF-{uuid4().hex.upper()}",
            "user_id": user_id,
            "workflow_id": workflow_id,
            "claim_id": claim_id,
            "type": notification_type,
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read_at": None,
        }
        return await self.repository.create_notification(data)

    async def list_notifications(self, user_id: str) -> dict[str, Any]:
        items = await self.repository.list_by_user(user_id)
        unread = sum(1 for n in items if not n.get("is_read"))
        return {"items": items, "unread_count": unread}

    async def mark_read(self, notification_id: str, user_id: str) -> dict[str, Any] | None:
        return await self.repository.mark_read(notification_id, user_id)
