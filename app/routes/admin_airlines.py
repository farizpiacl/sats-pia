from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app import db
from app.models.airline import Airline
from app.forms.admin_forms import AirlineForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action

admin_airlines_bp = Blueprint("admin_airlines", __name__, url_prefix="/admin/airlines")


@admin_airlines_bp.route("/")
@login_required
@super_admin_required
def list_airlines():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Airline.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Airline.name.ilike(like), Airline.iata_code.ilike(like), Airline.icao_code.ilike(like)))
    if status_filter == "active":
        query = query.filter(Airline.is_active.is_(True))
    elif status_filter == "disabled":
        query = query.filter(Airline.is_active.is_(False))

    airlines = query.order_by(Airline.name).all()
    return render_template("admin/airlines_list.html", airlines=airlines, q=q, status_filter=status_filter)


@admin_airlines_bp.route("/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_airline():
    form = AirlineForm()
    if form.validate_on_submit():
        if Airline.query.filter_by(name=form.name.data.strip()).first():
            flash("An airline with this name already exists.", "danger")
            return render_template("admin/airline_form.html", form=form, mode="create")

        airline = Airline(
            name=form.name.data.strip(),
            iata_code=form.iata_code.data.strip().upper() if form.iata_code.data else None,
            icao_code=form.icao_code.data.strip().upper() if form.icao_code.data else None,
            is_active=form.is_active.data,
        )
        db.session.add(airline)
        db.session.commit()
        log_action("CREATE", entity_type="Airline", entity_id=airline.id, description=f"Created airline {airline.name}")
        flash(f"Airline {airline.name} created successfully.", "success")
        return redirect(url_for("admin_airlines.list_airlines"))

    return render_template("admin/airline_form.html", form=form, mode="create")


@admin_airlines_bp.route("/<int:airline_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_airline(airline_id):
    airline = Airline.query.get_or_404(airline_id)
    form = AirlineForm(obj=airline)

    if form.validate_on_submit():
        existing = Airline.query.filter(Airline.name == form.name.data.strip(), Airline.id != airline.id).first()
        if existing:
            flash("Another airline already uses this name.", "danger")
            return render_template("admin/airline_form.html", form=form, mode="edit", airline=airline)

        airline.name = form.name.data.strip()
        airline.iata_code = form.iata_code.data.strip().upper() if form.iata_code.data else None
        airline.icao_code = form.icao_code.data.strip().upper() if form.icao_code.data else None
        airline.is_active = form.is_active.data
        db.session.commit()
        log_action("UPDATE", entity_type="Airline", entity_id=airline.id, description=f"Updated airline {airline.name}")
        flash(f"Airline {airline.name} updated successfully.", "success")
        return redirect(url_for("admin_airlines.list_airlines"))

    return render_template("admin/airline_form.html", form=form, mode="edit", airline=airline)


@admin_airlines_bp.route("/<int:airline_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(airline_id):
    airline = Airline.query.get_or_404(airline_id)
    airline.is_active = not airline.is_active
    db.session.commit()
    action = "ENABLE" if airline.is_active else "DISABLE"
    log_action(action, entity_type="Airline", entity_id=airline.id, description=f"{action.title()}d airline {airline.name}")
    flash(f"Airline {airline.name} has been {'enabled' if airline.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin_airlines.list_airlines"))
