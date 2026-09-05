from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models.user import User, UserRole
from sqlalchemy.orm import joinedload
from app.models.station import Station
from app.forms.admin_forms import UserForm, ResetPasswordForm
from app.utils.decorators import super_admin_required
from app.utils.audit import log_action
from app.utils.stations import get_lahore_station

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")


def _populate_station_choices(form):
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    form.station_id.choices = [(0, "— No Station —")] + [(s.id, f"{s.code} - {s.name}") for s in stations]


@admin_users_bp.route("/")
@login_required
@super_admin_required
def list_users():
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = User.query.options(joinedload(User.station))
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.full_name.ilike(like), User.employee_id.ilike(like), User.email.ilike(like))
        )
    if role_filter:
        try:
            query = query.filter(User.role == UserRole(role_filter))
        except ValueError:
            pass
    if status_filter == "active":
        query = query.filter(User.is_active_flag.is_(True))
    elif status_filter == "disabled":
        query = query.filter(User.is_active_flag.is_(False))

    users = query.order_by(User.full_name).all()
    return render_template(
        "admin/users_list.html",
        users=users,
        roles=list(UserRole),
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@admin_users_bp.route("/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_user():
    form = UserForm()
    _populate_station_choices(form)
    if request.method == "GET":
        # Lahore is the default/home station for new employees; admins can
        # still pick a different one from the dropdown.
        lahore = get_lahore_station()
        if lahore:
            form.station_id.data = lahore.id

    if form.validate_on_submit():
        if User.query.filter_by(employee_id=form.employee_id.data.strip()).first():
            flash("An employee with this Employee ID already exists.", "danger")
            return render_template("admin/user_form.html", form=form, mode="create")
        if User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash("An employee with this email already exists.", "danger")
            return render_template("admin/user_form.html", form=form, mode="create")
        if not form.password.data:
            flash("A password is required when creating a new user.", "danger")
            return render_template("admin/user_form.html", form=form, mode="create")

        user = User(
            employee_id=form.employee_id.data.strip(),
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip() if form.phone.data else None,
            designation=form.designation.data.strip() if form.designation.data else None,
            role=UserRole(form.role.data),
            station_id=form.station_id.data or None,
            is_active_flag=form.is_active.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        log_action("CREATE", entity_type="User", entity_id=user.id, description=f"Created user {user.full_name} ({user.employee_id})")
        flash(f"User {user.full_name} created successfully.", "success")
        return redirect(url_for("admin_users.list_users"))

    return render_template("admin/user_form.html", form=form, mode="create")


@admin_users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    _populate_station_choices(form)

    if request.method == "GET":
        form.role.data = user.role.value
        form.station_id.data = user.station_id or 0
        form.password.data = ""

    if form.validate_on_submit():
        existing = User.query.filter(User.employee_id == form.employee_id.data.strip(), User.id != user.id).first()
        if existing:
            flash("Another employee already uses this Employee ID.", "danger")
            return render_template("admin/user_form.html", form=form, mode="edit", user=user)
        existing_email = User.query.filter(User.email == form.email.data.strip().lower(), User.id != user.id).first()
        if existing_email:
            flash("Another employee already uses this email.", "danger")
            return render_template("admin/user_form.html", form=form, mode="edit", user=user)

        user.employee_id = form.employee_id.data.strip()
        user.full_name = form.full_name.data.strip()
        user.email = form.email.data.strip().lower()
        user.phone = form.phone.data.strip() if form.phone.data else None
        user.designation = form.designation.data.strip() if form.designation.data else None
        user.role = UserRole(form.role.data)
        user.station_id = form.station_id.data or None
        user.is_active_flag = form.is_active.data
        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()
        log_action("UPDATE", entity_type="User", entity_id=user.id, description=f"Updated user {user.full_name} ({user.employee_id})")
        flash(f"User {user.full_name} updated successfully.", "success")
        return redirect(url_for("admin_users.list_users"))

    return render_template("admin/user_form.html", form=form, mode="edit", user=user)


@admin_users_bp.route("/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@super_admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        log_action(
            "UPDATE", entity_type="User", entity_id=user.id,
            description=f"Developer reset password for {user.full_name} ({user.employee_id})",
        )
        flash(f"Password for {user.full_name} has been reset.", "success")
        return redirect(url_for("admin_users.list_users"))

    return render_template("admin/reset_password.html", form=form, user=user)


@admin_users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for("admin_users.list_users"))

    user.is_active_flag = not user.is_active_flag
    db.session.commit()

    action = "ENABLE" if user.is_active_flag else "DISABLE"
    log_action(action, entity_type="User", entity_id=user.id, description=f"{action.title()}d user {user.full_name}")
    flash(f"User {user.full_name} has been {'enabled' if user.is_active_flag else 'disabled'}.", "success")
    return redirect(url_for("admin_users.list_users"))
