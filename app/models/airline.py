from app import db
from app.models.base import TimestampMixin


class Airline(TimestampMixin, db.Model):
    __tablename__ = "airlines"

    id = db.Column(db.Integer, primary_key=True)
    iata_code = db.Column(db.String(5), unique=True, nullable=True, index=True)
    icao_code = db.Column(db.String(5), unique=True, nullable=True, index=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    aircraft = db.relationship("Aircraft", back_populates="airline")

    __table_args__ = (
        db.Index("ix_airlines_active", "is_active"),
    )

    def __repr__(self):
        return f"<Airline {self.name}>"
