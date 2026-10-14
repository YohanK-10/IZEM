from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.db import Notification


def _serialize_utc(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.replace(microsecond=0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def get_notifications(db: Session, user_id: int, role: str, limit: int = 10):
    """Get notifications for a user with role-appropriate links.
    Returns dict with 'unread' count and 'items' list."""
    recent = db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(Notification.created_at.desc()).limit(limit).all()

    # Role-specific link prefix
    link_map = {
        "teacher": "/review-request",
        "ta": "/review-request",
        "student": "/student/request",
    }
    default_link_map = {
        "teacher": "/",
        "ta": "/ta-dashboard",
        "student": "/student-home",
    }
    prefix = link_map.get(role, "/")
    default_link = default_link_map.get(role, "/")

    items = []
    for n in recent:
        link = f"{prefix}/{n.help_request_id}" if n.help_request_id else default_link
        items.append({
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "read": n.read,
            "link": link,
            "created_at": _serialize_utc(n.created_at),
        })

    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == False
    ).count()

    return {"unread": unread_count, "items": items}


def mark_read(db: Session, notification_id: int, user_id: int):
    """Mark a notification as read. Ownership-checked."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    if notification:
        notification.read = True
        db.commit()
    return {"status": "ok"}


def mark_all_read(db: Session, user_id: int):
    """Mark all notifications for the user as read."""
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == False
    ).update({"read": True}, synchronize_session=False)
    db.commit()
    return {"status": "ok"}
