from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models.audit_log import AuditLog
from app.models.user import User
from app.utils.decorators import super_admin_required

admin_audit_bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit-logs")

ACTION_CHOICES = [
    "LOGIN", "LOGIN_FAILED", "LOGIN_BLOCKED", "LOGOUT",
    "CREATE", "UPDATE", "DELETE", "DISABLE", "ENABLE",
    "EXPORT",
]


@admin_audit_bp.route("/")
@login_required
@super_admin_required
def list_logs():
    action = request.args.get("action", "").strip()
    user_id = request.args.get("user_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = request.args.get("page", 1, type=int)

    query = AuditLog.query

    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        try:
            query = query.filter(AuditLog.user_id == int(user_id))
        except ValueError:
            pass
    if date_from:
        try:
            query = query.filter(AuditLog.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(AuditLog.created_at < datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
        except ValueError:
            pass

    query = query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=30, error_out=False)

    users = User.query.order_by(User.full_name).all()

    return render_template(
        "admin/audit_logs.html",
        pagination=pagination,
        logs=pagination.items,
        users=users,
        action_choices=ACTION_CHOICES,
        filters={"action": action, "user_id": user_id, "date_from": date_from, "date_to": date_to},
    )
