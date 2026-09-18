import enum
from app import db
from app.models.base import TimestampMixin


class ShiftName(enum.Enum):
    ALPHA = "alpha"
    BRAVO = "bravo"
    CHARLIE = "charlie"
    DELTA = "delta"

    @property
    def label(self):
        return self.value.capitalize()


class Shift(TimestampMixin, db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Enum(ShiftName, name="shift_name"), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Each shift can have (at most) one Shift Incharge assigned.
    shift_incharge_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    station = db.relationship("Station", back_populates="shifts")
    shift_incharge = db.relationship("User", back_populates="shifts_led", foreign_keys=[shift_incharge_id])
    activities = db.relationship("Activity", back_populates="shift")

    __table_args__ = (
        db.UniqueConstraint("name", "station_id", name="uq_shift_name_station"),
        db.Index("ix_shifts_station_active", "station_id", "is_active"),
    )

    def __repr__(self):
        return f"<Shift {self.name.value if self.name else None} @ station {self.station_id}>"
