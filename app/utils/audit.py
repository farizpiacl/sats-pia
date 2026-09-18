from flask import request
from flask_login import current_user
from app import db
from app.models.audit_log import AuditLog


def log_action(action, entity_type=None, entity_id=None, description=None, user_id=None):
    """Record an entry in the audit log. Never raises - failures are swallowed
    so audit logging can't break the main request flow."""
    try:
        actor_id = user_id
        if actor_id is None and current_user and getattr(current_user, "is_authenticated", False):
            actor_id = current_user.id

        entry = AuditLog(
            user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get("User-Agent", "")[:255] if request else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
