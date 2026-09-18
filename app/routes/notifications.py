from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app import db
from app.models.notification import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_notifications():
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("notifications.html", notifications=notifications)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return redirect(url_for("notifications.list_notifications"))

    notification.is_read = True
    db.session.commit()

    next_url = notification.link or url_for("notifications.list_notifications")
    return redirect(next_url)


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.list_notifications"))
