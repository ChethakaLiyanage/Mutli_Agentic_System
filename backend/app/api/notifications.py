"""Customer notification API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.notification import NotificationItemResponse, NotificationListResponse
from backend.app.security.dependencies import get_current_user
from backend.app.services.notification_service import (
    NotificationRepository,
    NotificationService,
    get_notification_repository,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repository)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationListResponse:
    """List all notifications for the authenticated customer."""
    try:
        items = await service.repository.list_by_user(current_user.user_id)
        notifications = [NotificationItemResponse.model_validate(item) for item in items]
        unread_count = sum(1 for n in notifications if not n.is_read)
        return NotificationListResponse(
            notifications=notifications,
            unread_count=unread_count,
        )
    except Exception as error:
        logger.exception("Failed to retrieve notifications")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications",
        ) from error


@router.patch("/{notification_id}/read", response_model=NotificationItemResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationItemResponse:
    """Mark a customer notification as read."""
    try:
        updated = await service.repository.mark_read(notification_id, current_user.user_id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        return NotificationItemResponse.model_validate(updated)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to mark notification read")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification",
        ) from error
