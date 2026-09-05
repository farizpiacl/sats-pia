from datetime import datetime
from app import db


class TimestampMixin:
    """Adds created_at / updated_at columns to any model."""

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
