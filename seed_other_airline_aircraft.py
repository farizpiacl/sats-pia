"""Seed script: adds/manages Aircraft Models for airlines OTHER THAN PIA.

Idempotent - safe to run more than once. For each of a small set of
"Other Airline" carriers, this creates one Aircraft row (Third Party
category) per required model:

    A333, B787, A320, B777, A350, ATR

These rows are managed the normal way afterwards (Super Admin >
Aircraft: add / edit / disable). This script never touches PIA data.

Usage:
    python seed_other_airline_aircraft.py
"""
from app import create_app, db
from app.models.airline import Airline
from app.models.aircraft import Aircraft, AircraftCategory

# The canonical set of Aircraft/Plane models offered on the Engineer form's
# "Aircraft Model" dropdown for any airline other than PIA.
OTHER_AIRLINE_AIRCRAFT_MODELS = ["A333", "B787", "A320", "B777", "A350", "ATR"]

# A handful of real "Other Airline" carriers to seed so the dropdowns have
# usable data out of the box. iata/icao are best-effort and only used for
# display - add more airlines any time via Admin > Airlines.
OTHER_AIRLINES = [
    {"name": "Qatar Airways", "iata_code": "QR", "icao_code": "QTR"},
    {"name": "Riyadh Air", "iata_code": "RX", "icao_code": "RXI"},
    {"name": "Saudi Arabian Airlines", "iata_code": "SV", "icao_code": "SVA"},
    {"name": "SriLankan Airlines", "iata_code": "UL", "icao_code": "ALK"},
]

# Registration prefix per airline, just to keep generated tail numbers
# unique and readable (e.g. "EK-A333-01").
def _registration(prefix, model, index):
    return f"{prefix}-{model}-{index:02d}"


def main():
    app = create_app()
    with app.app_context():
        created_airlines = 0
        created_aircraft = 0

        for info in OTHER_AIRLINES:
            airline = Airline.query.filter(
                db.func.upper(db.func.trim(Airline.name)) == info["name"].upper()
            ).first()
            if not airline:
                airline = Airline(
                    name=info["name"],
                    iata_code=info["iata_code"],
                    icao_code=info["icao_code"],
                    is_active=True,
                )
                db.session.add(airline)
                db.session.flush()
                created_airlines += 1
                print(f"Created airline: {airline.name}")
            else:
                print(f"Airline already exists: {airline.name}")

            for model in OTHER_AIRLINE_AIRCRAFT_MODELS:
                existing = Aircraft.query.filter_by(
                    airline_id=airline.id, aircraft_type=model
                ).first()
                if existing:
                    continue
                registration = _registration(info["iata_code"], model, 1)
                # Guard against a registration collision with another
                # airline's seeded row (registration is globally unique).
                suffix = 1
                while Aircraft.query.filter_by(registration=registration).first():
                    suffix += 1
                    registration = _registration(info["iata_code"], model, suffix)

                aircraft = Aircraft(
                    registration=registration,
                    aircraft_type=model,
                    airline_id=airline.id,
                    category=AircraftCategory.THIRD_PARTY,
                    is_active=True,
                )
                db.session.add(aircraft)
                created_aircraft += 1
                print(f"  Added aircraft {registration} ({model}) for {airline.name}")

        db.session.commit()
        print("-" * 60)
        print(f"Done. Airlines created: {created_airlines}, Aircraft created: {created_aircraft}")


if __name__ == "__main__":
    main()
