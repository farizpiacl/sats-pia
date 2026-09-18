from app import db
from app.models.base import TimestampMixin


class Station(TimestampMixin, db.Model):
    __tablename__ = "stations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)  # e.g. LHE, KHI, ISB
    name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    users = db.relationship("User", back_populates="station", foreign_keys="User.station_id")
    shifts = db.relationship("Shift", back_populates="station", cascade="all, delete-orphan")
    activities = db.relationship("Activity", back_populates="station")

    __table_args__ = (
        db.Index("ix_stations_active", "is_active"),
    )

    def __repr__(self):
        return f"<Station {self.code} - {self.name}>"
