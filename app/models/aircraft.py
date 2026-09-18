import enum
from app import db
from app.models.base import TimestampMixin


class AircraftCategory(enum.Enum):
    PIA = "pia"
    THIRD_PARTY = "third_party"

    @property
    def label(self):
        return "PIA" if self == AircraftCategory.PIA else "Third Party"


class Aircraft(TimestampMixin, db.Model):
    __tablename__ = "aircraft"

    id = db.Column(db.Integer, primary_key=True)
    registration = db.Column(db.String(20), unique=True, nullable=False, index=True)
    aircraft_type = db.Column(db.String(100), nullable=False)  # e.g. Boeing 777-300ER
    airline_id = db.Column(db.Integer, db.ForeignKey("airlines.id", ondelete="RESTRICT"), nullable=False, index=True)
    category = db.Column(db.Enum(AircraftCategory, name="aircraft_category"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    airline = db.relationship("Airline", back_populates="aircraft")
    activities = db.relationship("Activity", back_populates="aircraft")

    __table_args__ = (
        db.Index("ix_aircraft_active", "is_active"),
        db.Index("ix_aircraft_category", "category"),
    )

    def __repr__(self):
        return f"<Aircraft {self.registration} ({self.aircraft_type})>"
