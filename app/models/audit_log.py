from datetime import datetime
from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action = db.Column(db.String(50), nullable=False, index=True)  # LOGIN, LOGOUT, CREATE, UPDATE, DISABLE, etc.
    entity_type = db.Column(db.String(50), nullable=True, index=True)  # e.g. "User", "Station"
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(500), nullable=True)

    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="audit_logs")

    __table_args__ = (
        db.Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} by user {self.user_id} @ {self.created_at}>"
