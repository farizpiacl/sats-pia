"""Real, database-backed notification helpers. No dummy/fake notifications
are ever created - every call here is triggered by an actual user action
(e.g. logging a new activity)."""
from app import db
from app.models.notification import Notification


def notify_user(user_id, title, message, link=None):
    """Create a single notification for one user. Never raises - a failed
    notification should not break the calling request."""
    if not user_id:
        return
    try:
        n = Notification(user_id=user_id, title=title[:150], message=message[:500], link=link)
        db.session.add(n)
        db.session.commit()
    except Exception:
        db.session.rollback()


def notify_users(user_ids, title, message, link=None):
    for uid in set(uid for uid in user_ids if uid):
        notify_user(uid, title, message, link=link)


def shift_incharge_ids_for(shift):
    """Return the user id(s) to notify of new activity on this shift. A
    shift has at most one Shift Incharge assigned."""
    if shift is not None and shift.shift_incharge_id:
        return [shift.shift_incharge_id]
    return []
