"""Shared helper for looking up the Lahore station.

Lahore is the primary/home station for SATS-PIA (the Engineer Inspection
Form is auto-locked to it - see app/routes/engineer.py). Several other
places in the app -- the main Dashboard's "Lahore Station" card, the
Engineer Overview's "Lahore Activity" figure, and new-user defaults --
all need the same station row, so the lookup lives here once instead of
being copy-pasted.
"""
from app import db
from app.models.station import Station

LAHORE_STATION_NAME = "Lahore"
LAHORE_STATION_CODE = "LHE"


def get_lahore_station():
    """Return the Lahore Station row (active preferred), or None if it
    hasn't been configured yet in this environment."""
    match = db.or_(
        Station.name.ilike(f"%{LAHORE_STATION_NAME}%"),
        Station.code == LAHORE_STATION_CODE,
    )
    station = Station.query.filter(match).filter_by(is_active=True).first()
    if not station:
        station = Station.query.filter(match).first()
    return station
