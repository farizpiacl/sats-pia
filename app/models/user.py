import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models.base import TimestampMixin


class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    DCE = "DCE"
    SHIFT_INCHARGE = "SHIFT_INCHARGE"
    ENGINEER = "ENGINEER"

    @property
    def label(self):
        return {
            UserRole.SUPER_ADMIN: "Developer",
            UserRole.DCE: "Deputy Chief Engineer",
            UserRole.SHIFT_INCHARGE: "Shift Incharge",
            UserRole.ENGINEER: "Aircraft Engineer",
        }[self]


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
    db.Enum(
        UserRole,
        name="user_role",
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    ),
    nullable=False,
    index=True,
)
    phone = db.Column(db.String(30), nullable=True)
    designation = db.Column(db.String(100), nullable=True)

    station_id = db.Column(db.Integer, db.ForeignKey("stations.id", ondelete="SET NULL"), nullable=True, index=True)

    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    station = db.relationship("Station", back_populates="users", foreign_keys=[station_id])
    shifts_led = db.relationship("Shift", back_populates="shift_incharge")
    activities = db.relationship("Activity", back_populates="logged_by", foreign_keys="Activity.logged_by_id")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="user")

    __table_args__ = (
        db.Index("ix_users_role_active", "role", "is_active"),
    )

    # --- Password handling ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login required property (override UserMixin's is_active) ---
    @property
    def is_active(self):
        return self.is_active_flag

    # --- Role helpers ---
    @property
    def is_super_admin(self):
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_dce(self):
        return self.role == UserRole.DCE

    @property
    def is_shift_incharge(self):
        return self.role == UserRole.SHIFT_INCHARGE

    @property
    def is_engineer(self):
        return self.role == UserRole.ENGINEER

    def has_role(self, *roles):
        return self.role in roles

    def __repr__(self):
        return f"<User {self.employee_id} {self.full_name} ({self.role.value if self.role else None})>"
