from flask import Blueprint, render_template, url_for

from flask_login import login_required

from app.models.user import UserRole
from app.utils.decorators import roles_required

# --------------------------------------------------------------------------
# Pure navigation hub for the Super Admin (SA) sidebar.
#
# These pages introduce NO new data, business logic, permissions, or
# routes for the underlying features - they are just selection/menu pages
# that link out to the exact same admin routes that already existed in the
# old (long) SA sidebar. This lets the SA sidebar stay short (Dashboard /
# Overview / Management / Reports / Activities / Security / Settings)
# while every existing admin page remains fully reachable.
# --------------------------------------------------------------------------
admin_menu_bp = Blueprint("admin_menu", __name__, url_prefix="/admin/menu")


@admin_menu_bp.route("/management")
@login_required
@roles_required(UserRole.SUPER_ADMIN)
def management_menu():
    cards = [
        {"label": "Users / Employees", "desc": "Manage user accounts, roles, and access.",
         "icon": "bi-people", "url": url_for("admin_users.list_users")},
        {"label": "Stations", "desc": "Manage stations / outstations.",
         "icon": "bi-geo-alt", "url": url_for("admin_stations.list_stations")},
        {"label": "Shifts", "desc": "Manage shift definitions.",
         "icon": "bi-clock-history", "url": url_for("admin_shifts.list_shifts")},
        {"label": "Aircraft", "desc": "Manage aircraft records.",
         "icon": "bi-airplane", "url": url_for("admin_aircraft.list_aircraft")},
        {"label": "Airlines", "desc": "Manage airline records.",
         "icon": "bi-building", "url": url_for("admin_airlines.list_airlines")},
        {"label": "Categories", "desc": "Manage Activity / TSR / MIC / RI categories.",
         "icon": "bi-tags", "url": url_for("admin_categories.list_categories", group_key="activity_type")},
    ]
    return render_template("admin/management_menu.html", cards=cards)


@admin_menu_bp.route("/security")
@login_required
@roles_required(UserRole.SUPER_ADMIN)
def security_menu():
    cards = [
        {"label": "Audit Logs", "desc": "Review the full system audit trail.",
         "icon": "bi-journal-text", "url": url_for("admin_audit.list_logs")},
    ]
    return render_template("admin/security_menu.html", cards=cards)
