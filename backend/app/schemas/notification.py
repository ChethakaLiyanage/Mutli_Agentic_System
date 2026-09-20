"""Notification schemas for customer alert and status updates."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


from pydantic import BaseModel, ConfigDict, Field, model_validator


class NotificationItemResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    user_id: str
    workflow_id: str | None = None
    claim_id: str | None = None
    notification_type: str = "general"
    type: str | None = None
    title: str
    message: str
    is_read: bool = False
    created_at: Any = None
    read_at: Any = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ntype = data.get("notification_type") or data.get("type") or "general"
            data["notification_type"] = ntype
            data["type"] = ntype
        return data


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notifications: list[NotificationItemResponse]
    unread_count: int
