from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app import db
from app.models.shift import Shift, ShiftName
from app.models.station import Station
from app.models.user import User, UserRole
from app.forms.admin_forms import ShiftForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action

admin_shifts_bp = Blueprint("admin_shifts", __name__, url_prefix="/admin/shifts")


def _populate_choices(form):
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    form.station_id.choices = [(s.id, f"{s.code} - {s.name}") for s in stations]

    incharges = User.query.filter_by(role=UserRole.SHIFT_INCHARGE, is_active_flag=True).order_by(User.full_name).all()
    form.shift_incharge_id.choices = [(0, "— Unassigned —")] + [(u.id, f"{u.full_name} ({u.employee_id})") for u in incharges]


@admin_shifts_bp.route("/")
@login_required
@super_admin_required
def list_shifts():
    # Defensive: a prior request may have left this pooled Postgres
    # connection's transaction aborted (e.g. a failed query elsewhere in
    # the request lifecycle, such as the global nav-badge context
    # processor). Starting from a clean transaction here prevents that
    # from surfacing as psycopg2.errors.InFailedSqlTransaction on this
    # view's own queries or on lazy-loads triggered while rendering.
    db.session.rollback()

    q = request.args.get("q", "").strip()
    station_filter = request.args.get("station", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Shift.query.options(joinedload(Shift.shift_incharge), joinedload(Shift.station))
    if station_filter:
        query = query.filter(Shift.station_id == int(station_filter))
    if status_filter == "active":
        query = query.filter(Shift.is_active.is_(True))
    elif status_filter == "disabled":
        query = query.filter(Shift.is_active.is_(False))

    shifts = query.join(Station).order_by(Station.name, Shift.name).all()

    if q:
        like = q.lower()
        shifts = [s for s in shifts if like in s.name.value.lower() or like in s.station.name.lower()]

    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    return render_template("admin/shifts_list.html", shifts=shifts, stations=stations, q=q, station_filter=station_filter, status_filter=status_filter)


@admin_shifts_bp.route("/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_shift():
    form = ShiftForm()
    _populate_choices(form)

    if form.validate_on_submit():
        existing = Shift.query.filter_by(name=ShiftName(form.name.data), station_id=form.station_id.data).first()
        if existing:
            flash("This shift already exists for the selected station.", "danger")
            return render_template("admin/shift_form.html", form=form, mode="create")

        shift = Shift(
            name=ShiftName(form.name.data),
            station_id=form.station_id.data,
            shift_incharge_id=form.shift_incharge_id.data or None,
            is_active=form.is_active.data,
        )
        db.session.add(shift)
        db.session.commit()
        log_action("CREATE", entity_type="Shift", entity_id=shift.id, description=f"Created shift {shift.name.value} at station {shift.station_id}")
        flash("Shift created successfully.", "success")
        return redirect(url_for("admin_shifts.list_shifts"))

    return render_template("admin/shift_form.html", form=form, mode="create")


@admin_shifts_bp.route("/<int:shift_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    form = ShiftForm(obj=shift)
    _populate_choices(form)

    if request.method == "GET":
        form.name.data = shift.name.value
        form.shift_incharge_id.data = shift.shift_incharge_id or 0

    if form.validate_on_submit():
        existing = Shift.query.filter(
            Shift.name == ShiftName(form.name.data),
            Shift.station_id == form.station_id.data,
            Shift.id != shift.id,
        ).first()
        if existing:
            flash("Another shift with this name already exists for the selected station.", "danger")
            return render_template("admin/shift_form.html", form=form, mode="edit", shift=shift)

        shift.name = ShiftName(form.name.data)
        shift.station_id = form.station_id.data
        shift.shift_incharge_id = form.shift_incharge_id.data or None
        shift.is_active = form.is_active.data
        db.session.commit()
        log_action("UPDATE", entity_type="Shift", entity_id=shift.id, description=f"Updated shift {shift.name.value}")
        flash("Shift updated successfully.", "success")
        return redirect(url_for("admin_shifts.list_shifts"))

    return render_template("admin/shift_form.html", form=form, mode="edit", shift=shift)


@admin_shifts_bp.route("/<int:shift_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    shift.is_active = not shift.is_active
    db.session.commit()
    action = "ENABLE" if shift.is_active else "DISABLE"
    log_action(action, entity_type="Shift", entity_id=shift.id, description=f"{action.title()}d shift {shift.name.value}")
    flash(f"Shift has been {'enabled' if shift.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin_shifts.list_shifts"))
