from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app import db
from app.models.aircraft import Aircraft, AircraftCategory
from app.models.airline import Airline
from app.forms.admin_forms import AircraftForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action

admin_aircraft_bp = Blueprint("admin_aircraft", __name__, url_prefix="/admin/aircraft")


def _populate_airline_choices(form):
    airlines = Airline.query.filter_by(is_active=True).order_by(Airline.name).all()
    form.airline_id.choices = [(a.id, a.name) for a in airlines]


def _pia_airline_id():
    """Return the real PIA Airline.id using official identifiers.

    The database may display PIA as "PIA" or "Pakistan International
    Airlines", so do not rely on the display name alone. IATA PK and
    ICAO PIA are the authoritative identifiers.
    """
    airline = Airline.query.filter(
        db.or_(
            db.func.upper(db.func.trim(Airline.iata_code)) == "PK",
            db.func.upper(db.func.trim(Airline.icao_code)) == "PIA",
            db.func.upper(db.func.trim(Airline.name)).in_(
                ["PIA", "PAKISTAN INTERNATIONAL AIRLINES"]
            ),
        )
    ).order_by(
        db.case(
            (db.func.upper(db.func.trim(Airline.iata_code)) == "PK", 0),
            (db.func.upper(db.func.trim(Airline.icao_code)) == "PIA", 1),
            else_=2,
        )
    ).first()
    return airline.id if airline else None


@admin_aircraft_bp.route("/")
@login_required
@super_admin_required
def list_aircraft():
    q = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Aircraft.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Aircraft.registration.ilike(like), Aircraft.aircraft_type.ilike(like)))
    if category_filter:
        try:
            query = query.filter(Aircraft.category == AircraftCategory(category_filter))
        except ValueError:
            pass
    if status_filter == "active":
        query = query.filter(Aircraft.is_active.is_(True))
    elif status_filter == "disabled":
        query = query.filter(Aircraft.is_active.is_(False))

    aircraft = query.order_by(Aircraft.registration).all()
    has_airlines = Airline.query.filter_by(is_active=True).count() > 0
    return render_template(
        "admin/aircraft_list.html",
        aircraft=aircraft,
        categories=list(AircraftCategory),
        q=q,
        category_filter=category_filter,
        status_filter=status_filter,
        has_airlines=has_airlines,
    )


@admin_aircraft_bp.route("/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_aircraft():
    if Airline.query.filter_by(is_active=True).count() == 0:
        flash("Please add at least one Airline before adding Aircraft.", "warning")
        return redirect(url_for("admin_airlines.list_airlines"))

    form = AircraftForm()
    _populate_airline_choices(form)

    if form.validate_on_submit():
        if Aircraft.query.filter_by(registration=form.registration.data.strip().upper()).first():
            flash("An aircraft with this registration already exists.", "danger")
            return render_template("admin/aircraft_form.html", form=form, mode="create", pia_airline_id=_pia_airline_id())

        aircraft = Aircraft(
            registration=form.registration.data.strip().upper(),
            aircraft_type=form.aircraft_type.data.strip(),
            airline_id=form.airline_id.data,
            category=AircraftCategory(form.category.data),
            is_active=form.is_active.data,
        )
        db.session.add(aircraft)
        db.session.commit()
        log_action("CREATE", entity_type="Aircraft", entity_id=aircraft.id, description=f"Created aircraft {aircraft.registration}")
        flash(f"Aircraft {aircraft.registration} created successfully.", "success")
        return redirect(url_for("admin_aircraft.list_aircraft"))

    return render_template("admin/aircraft_form.html", form=form, mode="create", pia_airline_id=_pia_airline_id())


@admin_aircraft_bp.route("/<int:aircraft_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_aircraft(aircraft_id):
    aircraft = Aircraft.query.get_or_404(aircraft_id)
    form = AircraftForm(obj=aircraft)
    _populate_airline_choices(form)

    if request.method == "GET":
        form.category.data = aircraft.category.value

    if form.validate_on_submit():
        existing = Aircraft.query.filter(Aircraft.registration == form.registration.data.strip().upper(), Aircraft.id != aircraft.id).first()
        if existing:
            flash("Another aircraft already uses this registration.", "danger")
            return render_template("admin/aircraft_form.html", form=form, mode="edit", aircraft=aircraft, pia_airline_id=_pia_airline_id())

        aircraft.registration = form.registration.data.strip().upper()
        aircraft.aircraft_type = form.aircraft_type.data.strip()
        aircraft.airline_id = form.airline_id.data
        aircraft.category = AircraftCategory(form.category.data)
        aircraft.is_active = form.is_active.data
        db.session.commit()
        log_action("UPDATE", entity_type="Aircraft", entity_id=aircraft.id, description=f"Updated aircraft {aircraft.registration}")
        flash(f"Aircraft {aircraft.registration} updated successfully.", "success")
        return redirect(url_for("admin_aircraft.list_aircraft"))

    return render_template("admin/aircraft_form.html", form=form, mode="edit", aircraft=aircraft, pia_airline_id=_pia_airline_id())


@admin_aircraft_bp.route("/<int:aircraft_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(aircraft_id):
    aircraft = Aircraft.query.get_or_404(aircraft_id)
    aircraft.is_active = not aircraft.is_active
    db.session.commit()
    action = "ENABLE" if aircraft.is_active else "DISABLE"
    log_action(action, entity_type="Aircraft", entity_id=aircraft.id, description=f"{action.title()}d aircraft {aircraft.registration}")
    flash(f"Aircraft {aircraft.registration} has been {'enabled' if aircraft.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin_aircraft.list_aircraft"))
