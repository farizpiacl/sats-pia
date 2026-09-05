from app import db
from app.models.base import TimestampMixin


class FlightCoverage(TimestampMixin, db.Model):
    """A single Flight Coverage record.

    Logged directly by an Engineer (or Shift Incharge / Super Admin acting
    as one) from the Activities hub via the dedicated "Flight Coverage"
    action - separate from the main Engineer Activity form. Deliberately
    minimal: just the Station, what was performed during the coverage, who
    logged it, and when (via TimestampMixin's `created_at`).
    """

    __tablename__ = "flight_coverages"

    id = db.Column(db.Integer, primary_key=True)

    station_id = db.Column(db.Integer, db.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False, index=True)
    activity_performed = db.Column(db.Text, nullable=False)

    logged_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    station = db.relationship("Station", backref=db.backref("flight_coverages", lazy="dynamic"))
    logged_by = db.relationship("User", foreign_keys=[logged_by_id], backref=db.backref("flight_coverages", lazy="dynamic"))

    __table_args__ = (
        db.Index("ix_flight_coverages_station", "station_id"),
        db.Index("ix_flight_coverages_engineer", "logged_by_id"),
    )

    def __repr__(self):
        return f"<FlightCoverage {self.id} station={self.station_id}>"
