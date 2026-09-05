from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, abort
from flask_login import login_required, current_user

from app.models.activity import (
    Activity, ActivityType,
    TSR_TYPES, MIC_TYPES, QUALITY_TYPES,
)
from app.models.station import Station
from app.models.shift import Shift
from app.models.aircraft import Aircraft
from app.models.airline import Airline
from app.models.user import User, UserRole
from app.utils.decorators import roles_required
from app.utils.analytics import AIRCRAFT_TYPE_FILTER_CHOICES, aircraft_ids_for_type_bucket

shift_incharge_bp = Blueprint("shift_incharge", __name__, url_prefix="/shift-incharge")

# Reuse the same category configuration the Engineer module uses, so KPI
# tiles/category charts line up exactly with "My Activities".
from app.routes.engineer import CATEGORIES  # noqa: E402


# --------------------------------------------------------------------------
# Shift scoping - a Shift Incharge may only see/manage activities that
# belong to a shift they are assigned to lead. Super Admin gets full
# oversight (no restriction) for administration/troubleshooting.
# --------------------------------------------------------------------------
def _my_shift_ids():
    if current_user.is_super_admin:
        return None  # None => unrestricted
    return [s.id for s in current_user.shifts_led]


def _scope_query(query):
    shift_ids = _my_shift_ids()
    if shift_ids is None:
        return query
    if not shift_ids:
        return query.filter(Activity.id == -1)  # no shift assigned -> nothing in scope
    return query.filter(Activity.shift_id.in_(shift_ids))


def _check_activity_access(activity):
    shift_ids = _my_shift_ids()
    if shift_ids is None:
        return
    if activity.shift_id not in shift_ids:
        abort(403)


def _my_shifts():
    if current_user.is_super_admin:
        return Shift.query.order_by(Shift.name).all()
    return sorted(current_user.shifts_led, key=lambda s: s.name.value)


# --------------------------------------------------------------------------
# Dashboard - database-driven KPIs + charts (no dummy numbers). Every
# KPI/chart below simply reflects all activities in scope as plain totals.
# --------------------------------------------------------------------------
@shift_incharge_bp.route("/dashboard")
@login_required
@roles_required(UserRole.SHIFT_INCHARGE, UserRole.SUPER_ADMIN)
def dashboard():
    base = _scope_query(Activity.query)
    total_activities = base.count()

    category_counts = {}
    for key, cfg in CATEGORIES.items():
        category_counts[key] = base.filter(Activity.activity_type.in_(cfg["types"])).count()

    kpis = {
        "activities": total_activities,
        "maintenance_check": category_counts.get("maintenance_check", 0),
        "tsr": category_counts.get("tsr", 0),
        "mic": category_counts.get("mic", 0),
        "replacement": base.filter(Activity.activity_type == ActivityType.REPLACEMENT).count(),
        "quality": category_counts.get("quality", 0),
        "cf": category_counts.get("cf", 0),
        "cf_removal": category_counts.get("cf_removal", 0),
        "carry_forward": base.filter(Activity.activity_type.in_((ActivityType.CF, ActivityType.CF_REMOVAL))).count(),
        "unscheduled": base.filter(Activity.activity_type == ActivityType.PIREP_UNSCHEDULED_MAINTENANCE).count(),
    }

    # QARI Closed KPI: total closed QARI entries in scope, broken
    # down by Significant / Minor severity - same shift scoping as
    # everything else on this dashboard (`base`).
    from app.models.activity import QariEntry, QariSeverity, QariEntryStatus
    closed_qari_entries = (
        QariEntry.query.join(Activity, QariEntry.activity_id == Activity.id)
        .filter(Activity.id.in_(base.filter(Activity.activity_type.in_(QUALITY_TYPES)).with_entities(Activity.id)))
        .filter(QariEntry.status == QariEntryStatus.CLOSED)
    )
    qari_closed = {
        "total": closed_qari_entries.count(),
        "significant": closed_qari_entries.filter(QariEntry.severity == QariSeverity.SIGNIFICANT).count(),
        "minor": closed_qari_entries.filter(QariEntry.severity == QariSeverity.MINOR).count(),
    }

    category_chart = {
        "labels": [cfg["label"] for cfg in CATEGORIES.values()],
        "data": [category_counts.get(key, 0) for key in CATEGORIES.keys()],
    }

    recent_activities = (
        base.order_by(Activity.created_at.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "shift_incharge/dashboard.html",
        kpis=kpis,
        qari_closed=qari_closed,
        category_chart=category_chart,
        recent_activities=recent_activities,
        my_shifts=_my_shifts(),
    )


# --------------------------------------------------------------------------
# Shift Monitoring - shift-wise KPI summary + filterable activity list.
# Every count is a plain total of the activities that were logged.
# --------------------------------------------------------------------------
@shift_incharge_bp.route("/monitoring")
@login_required
@roles_required(UserRole.SHIFT_INCHARGE, UserRole.SUPER_ADMIN)
def shift_monitoring():
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    station_id = request.args.get("station_id", "").strip()
    engineer_id = request.args.get("engineer_id", "").strip()
    aircraft_id = request.args.get("aircraft_id", "").strip()
    airline_id = request.args.get("airline_id", "").strip()
    aircraft_type = request.args.get("aircraft_type", "").strip().lower()
    activity_type = request.args.get("activity_type", "").strip()
    category = request.args.get("category", "").strip()
    page = request.args.get("page", 1, type=int)

    # --- Shift-wise summary ---
    summary = []
    for sh in _my_shifts():
        sh_q = Activity.query.filter(Activity.shift_id == sh.id)
        summary.append({
            "shift": sh,
            "total": sh_q.count(),
            "maintenance_check": sh_q.filter(Activity.activity_type == ActivityType.MAINTENANCE_CHECK).count(),
            "tsr": sh_q.filter(Activity.activity_type.in_(TSR_TYPES)).count(),
            "mic": sh_q.filter(Activity.activity_type.in_(MIC_TYPES)).count(),
            "replacement": sh_q.filter(Activity.activity_type == ActivityType.REPLACEMENT).count(),
            "ri": sh_q.filter(Activity.activity_type.in_(QUALITY_TYPES)).count(),
            "cf_removal": sh_q.filter(Activity.activity_type == ActivityType.CF_REMOVAL).count(),
            "cf": sh_q.filter(Activity.activity_type == ActivityType.CF).count(),
            "unscheduled": sh_q.filter(Activity.activity_type == ActivityType.PIREP_UNSCHEDULED_MAINTENANCE).count(),
        })

    # --- Filtered activity list ---
    query = _scope_query(Activity.query)

    if date_from:
        try:
            query = query.filter(Activity.activity_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Activity.activity_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass
    if station_id:
        query = query.filter(Activity.station_id == int(station_id))
    if engineer_id:
        query = query.filter(Activity.logged_by_id == int(engineer_id))
    if aircraft_id:
        query = query.filter(Activity.aircraft_id == int(aircraft_id))
    if airline_id:
        query = query.join(Aircraft, Activity.aircraft_id == Aircraft.id).filter(Aircraft.airline_id == int(airline_id))
    if aircraft_type:
        ac_ids = aircraft_ids_for_type_bucket(aircraft_type)
        if ac_ids is not None:
            query = query.filter(Activity.aircraft_id.in_(ac_ids) if ac_ids else Activity.id == -1)
    if activity_type:
        try:
            query = query.filter(Activity.activity_type == ActivityType(activity_type))
        except ValueError:
            pass
    category_cfg = CATEGORIES.get(category)
    if category_cfg:
        query = query.filter(Activity.activity_type.in_(category_cfg["types"]))

    severity_filter = request.args.get("severity", "").strip()
    qari_status_filter = request.args.get("qari_status", "").strip()
    if category == "quality" and (severity_filter or qari_status_filter):
        from app.models.activity import QariEntry, QariSeverity, QariEntryStatus
        query = query.join(QariEntry, QariEntry.activity_id == Activity.id)
        if severity_filter:
            try:
                query = query.filter(QariEntry.severity == QariSeverity(severity_filter))
            except ValueError:
                pass
        if qari_status_filter:
            try:
                query = query.filter(QariEntry.status == QariEntryStatus(qari_status_filter))
            except ValueError:
                pass
        query = query.distinct()

    query = query.order_by(Activity.activity_date.desc(), Activity.created_at.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    engineers = User.query.filter_by(role=UserRole.ENGINEER, is_active_flag=True).order_by(User.full_name).all()
    aircraft_list = Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all()
    airlines = Airline.query.filter_by(is_active=True).order_by(Airline.name).all()

    return render_template(
        "shift_incharge/shift_monitoring.html",
        summary=summary,
        pagination=pagination,
        activities=pagination.items,
        stations=stations,
        engineers=engineers,
        aircraft_list=aircraft_list,
        airlines=airlines,
        activity_types=list(ActivityType),
        aircraft_types=AIRCRAFT_TYPE_FILTER_CHOICES,
        filters={
            "date_from": date_from, "date_to": date_to, "station_id": station_id,
            "engineer_id": engineer_id, "aircraft_id": aircraft_id, "airline_id": airline_id,
            "aircraft_type": aircraft_type,
            "activity_type": activity_type, "category": category,
        },
        category=category,
        category_cfg=category_cfg,
    )


# --------------------------------------------------------------------------
# Navigation hub pages (Activities / Inspection / Reports)
#
# These introduce NO new data or business logic beyond activity creation -
# they are pure navigation menus of large, clear cards that link out to
# the routes below. Shift Incharge can log their own activities directly
# (via the shared Engineer activity form, reused here since Shift Incharge
# already has permission on it) and view records.
# --------------------------------------------------------------------------
@shift_incharge_bp.route("/activities-menu")
@login_required
@roles_required(UserRole.SHIFT_INCHARGE, UserRole.SUPER_ADMIN)
def activities_menu():
    cards = []
    if current_user.is_shift_incharge:
        cards.append({"label": "Log New Activity", "desc": "Record a new activity you performed.",
                      "icon": "bi-plus-square", "url": url_for("engineer.create_activity")})
    cards.append({"label": "All Activities", "desc": "Full filterable log for your shift(s).",
                  "icon": "bi-list-check", "url": url_for("shift_incharge.shift_monitoring")})
    for key, cfg in CATEGORIES.items():
        cards.append({
            "label": cfg["label"], "desc": f"{cfg['label']} activity records for your shift(s).",
            "icon": cfg["icon"], "url": url_for("shift_incharge.shift_monitoring", category=key),
        })
    return render_template("shift_incharge/activities_menu.html", cards=cards)


@shift_incharge_bp.route("/inspection-menu")
@login_required
@roles_required(UserRole.SHIFT_INCHARGE, UserRole.SUPER_ADMIN)
def inspection_menu():
    cards = [
        {"label": "Maintenance Checks", "desc": "Individual maintenance check activity records.",
         "icon": "bi-clipboard2-check", "url": url_for("shift_incharge.shift_monitoring", category="maintenance_check")},
    ]
    return render_template("shift_incharge/inspection_menu.html", cards=cards)


# --------------------------------------------------------------------------
# Reports - a single, unified Activities section covering all activity
# types, with the same date/station/engineer/aircraft/airline/type filters
# as Shift Monitoring so any activity record can be found and viewed.
# --------------------------------------------------------------------------
@shift_incharge_bp.route("/reports-menu")
@login_required
@roles_required(UserRole.SHIFT_INCHARGE, UserRole.SUPER_ADMIN)
def reports_menu():
    from datetime import date, timedelta
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    cards = [
        {"label": "Daily Report", "desc": "Activities logged today.",
         "icon": "bi-calendar-day",
         "url": url_for("shift_incharge.shift_monitoring", date_from=today.isoformat(), date_to=today.isoformat())},
        {"label": "Weekly Report", "desc": "Activities logged so far this week.",
         "icon": "bi-calendar-week",
         "url": url_for("shift_incharge.shift_monitoring", date_from=week_start.isoformat(), date_to=today.isoformat())},
        {"label": "Monthly Report", "desc": "Activities logged so far this month.",
         "icon": "bi-calendar-month",
         "url": url_for("shift_incharge.shift_monitoring", date_from=month_start.isoformat(), date_to=today.isoformat())},
    ]

    # Single "Activities" section: one card per activity type, all
    # filterable/viewable through the same Shift Monitoring list.
    activity_cards = [{"label": "All Activities", "desc": "Every activity type, filterable by date, station, engineer, aircraft, airline, and type.",
                        "icon": "bi-list-check", "url": url_for("shift_incharge.shift_monitoring")}]
    for key, cfg in CATEGORIES.items():
        activity_cards.append({
            "label": cfg["label"], "desc": f"{cfg['label']} activity records for your shift(s).",
            "icon": cfg["icon"], "url": url_for("shift_incharge.shift_monitoring", category=key),
        })

    return render_template("shift_incharge/reports_menu.html", cards=cards, activity_cards=activity_cards)
