from flask import Blueprint, render_template, redirect, url_for, flash, request

from app import db
from app.models.station import Station
from app.forms.admin_forms import StationForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action
from flask_login import login_required

admin_stations_bp = Blueprint("admin_stations", __name__, url_prefix="/admin/stations")


@admin_stations_bp.route("/")
@login_required
@super_admin_required
def list_stations():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Station.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Station.name.ilike(like), Station.code.ilike(like), Station.city.ilike(like)))
    if status_filter == "active":
        query = query.filter(Station.is_active.is_(True))
    elif status_filter == "disabled":
        query = query.filter(Station.is_active.is_(False))

    stations = query.order_by(Station.name).all()
    return render_template("admin/stations_list.html", stations=stations, q=q, status_filter=status_filter)


@admin_stations_bp.route("/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_station():
    form = StationForm()
    if form.validate_on_submit():
        if Station.query.filter_by(code=form.code.data.strip().upper()).first():
            flash("A station with this code already exists.", "danger")
            return render_template("admin/station_form.html", form=form, mode="create")

        station = Station(
            code=form.code.data.strip().upper(),
            name=form.name.data.strip(),
            city=form.city.data.strip() if form.city.data else None,
            is_active=form.is_active.data,
        )
        db.session.add(station)
        db.session.commit()
        log_action("CREATE", entity_type="Station", entity_id=station.id, description=f"Created station {station.code}")
        flash(f"Station {station.name} created successfully.", "success")
        return redirect(url_for("admin_stations.list_stations"))

    return render_template("admin/station_form.html", form=form, mode="create")


@admin_stations_bp.route("/<int:station_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_station(station_id):
    station = Station.query.get_or_404(station_id)
    form = StationForm(obj=station)

    if form.validate_on_submit():
        existing = Station.query.filter(Station.code == form.code.data.strip().upper(), Station.id != station.id).first()
        if existing:
            flash("Another station already uses this code.", "danger")
            return render_template("admin/station_form.html", form=form, mode="edit", station=station)

        station.code = form.code.data.strip().upper()
        station.name = form.name.data.strip()
        station.city = form.city.data.strip() if form.city.data else None
        station.is_active = form.is_active.data
        db.session.commit()
        log_action("UPDATE", entity_type="Station", entity_id=station.id, description=f"Updated station {station.code}")
        flash(f"Station {station.name} updated successfully.", "success")
        return redirect(url_for("admin_stations.list_stations"))

    return render_template("admin/station_form.html", form=form, mode="edit", station=station)


@admin_stations_bp.route("/<int:station_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(station_id):
    station = Station.query.get_or_404(station_id)
    station.is_active = not station.is_active
    db.session.commit()
    action = "ENABLE" if station.is_active else "DISABLE"
    log_action(action, entity_type="Station", entity_id=station.id, description=f"{action.title()}d station {station.code}")
    flash(f"Station {station.name} has been {'enabled' if station.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin_stations.list_stations"))
