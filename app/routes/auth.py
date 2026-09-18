import traceback
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models.user import User, UserRole
from app.forms.auth_forms import LoginForm, ChangePasswordForm
from app.utils.audit import log_action

auth_bp = Blueprint("auth", __name__)


def _default_landing_page():
    """Where a logged-in user lands with no specific `next` target.

    DCE goes straight to Overview (the DCE landing page); every other
    role keeps using the shared dashboard.index page as before.
    """
    if current_user.is_authenticated and current_user.role == UserRole.DCE:
        return url_for("dce.overview_menu")
    return url_for("dashboard.index")


@auth_bp.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        return redirect(_default_landing_page())
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_default_landing_page())

    # Start clean: a previous request on this pooled Postgres connection
    # may have left its transaction aborted if it errored without rolling
    # back. Never let a stale aborted transaction leak into a login attempt.
    db.session.rollback()

    form = LoginForm()
    if form.validate_on_submit():
        employee_id = form.employee_id.data.strip()
        user = User.query.filter_by(employee_id=employee_id).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid employee ID or password.", "danger")
            log_action(
                "LOGIN_FAILED",
                entity_type="User",
                description=f"Failed login attempt for employee_id={employee_id}",
            )
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("Your account has been disabled. Contact the Developer.", "danger")
            log_action(
                "LOGIN_BLOCKED",
                entity_type="User",
                entity_id=user.id,
                description="Login attempt on disabled account",
            )
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        user.last_login_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            # Must roll back on failure -- an uncommitted/aborted transaction
            # here would otherwise be returned to the connection pool dirty
            # and break the *next* request (e.g. the dashboard load right
            # after this redirect) with InFailedSqlTransaction.
            db.session.rollback()
            tb = traceback.format_exc()
            current_app.logger.error("[auth] last_login_at commit failed:\n%s", tb)
            print(f"[auth] last_login_at commit failed:\n{tb}", flush=True)
            # Non-fatal: last_login_at is not required for a successful
            # login, so continue rather than blocking the user out.

        log_action("LOGIN", entity_type="User", entity_id=user.id, description=f"{user.full_name} logged in")

        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/"):
            next_page = _default_landing_page()
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("LOGOUT", entity_type="User", entity_id=current_user.id, description=f"{current_user.full_name} logged out")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        elif form.new_password.data != form.confirm_password.data:
            flash("New password and confirmation do not match.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            log_action("UPDATE", entity_type="User", entity_id=current_user.id, description="Password changed")
            flash("Password updated successfully.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", form=form)
