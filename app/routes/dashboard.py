import traceback
from datetime import date
from types import SimpleNamespace

from flask import Blueprint, render_template, request, current_app, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app import db
from app.models.user import User, UserRole
from app.models.station import Station
from app.models.aircraft import Aircraft
from app.models.airline import Airline
from app.models.activity import Activity
from app.models.flight_coverage import FlightCoverage
from app.models.audit_log import AuditLog
from app.utils import analytics
from app.utils.stations import get_lahore_station

dashboard_bp = Blueprint("dashboard", __name__)


def _log_and_rollback(context_label):
    """Roll back the aborted transaction and log the FULL traceback.

    current_app.logger.exception() alone can be swallowed by some
    serverless log pipelines if the logger isn't configured with a
    handler/level early enough (common on Vercel cold starts). Printing
    the traceback directly to stderr as well guarantees it shows up in
    `vercel logs` / the Vercel dashboard regardless of logging config.
    """
    db.session.rollback()
    tb = traceback.format_exc()
    current_app.logger.error("[dashboard] %s failed:\n%s", context_label, tb)
    print(f"[dashboard] {context_label} failed:\n{tb}", flush=True)
    return tb


@dashboard_bp.route("/dashboard")
@login_required
def index():
    # The DCE role no longer has a separate "Dashboard" landing page -
    # Overview (dce.overview_menu) is now the DCE landing page. Anyone
    # hitting this URL directly (old bookmark, back button, etc.) is sent
    # straight there instead of rendering the generic dashboard.
    if current_user.role == UserRole.DCE:
        return redirect(url_for("dce.overview_menu"))

    dashboard_error = None

    # Always start this request's queries against a clean transaction.
    # A prior request on the same pooled Postgres connection may have left
    # the transaction aborted (e.g. a failed query whose exception path
    # didn't roll back before the connection was returned to the pool).
    # This MUST run before any query in this view -- including the station
    # lookup below -- or that first query inherits the aborted state and
    # fails with psycopg2.errors.InFailedSqlTransaction.
    db.session.rollback()

    # Station the logged-in user belongs to (None for users, e.g. Super
    # Admin/DCE, who aren't tied to a single station). Loaded explicitly
    # from the user's own station_id -- never hardcoded, never via lazy
    # relationship access -- so the dashboard/template can show it without
    # triggering a query of its own.
    #
    # Snapshotted into a plain SimpleNamespace (not the live ORM object)
    # so that nothing later in this request -- e.g. db.session.rollback()
    # in the except blocks below, which expires every loaded ORM instance
    # -- can cause Jinja to trigger a surprise lazy SELECT while rendering
    # dashboard.html.
    current_user_station = None
    if current_user.station_id:
        try:
            station_obj = db.session.get(Station, current_user.station_id)
            if station_obj is not None:
                current_user_station = SimpleNamespace(
                    id=station_obj.id, code=station_obj.code, name=station_obj.name,
                )
        except Exception:
            _log_and_rollback("current_user_station lookup")
            current_user_station = None
            dashboard_error = "Station info is temporarily unavailable."

    # The Lahore Station is looked up once per request and reused for both
    # the "Lahore Station" dashboard card and the Engineer Overview's
    # "Lahore Activity" figure below, so both numbers are always scoped to
    # the same station row.
    lahore_station = None
    try:
        lahore_station = get_lahore_station()
    except Exception:
        _log_and_rollback("Lahore station lookup")
        lahore_station = None

    try:
        db.session.rollback()
        lahore_activities_total = 0
        lahore_activities_today = 0
        if lahore_station:
            lahore_q = Activity.query.filter_by(station_id=lahore_station.id)
            lahore_activities_total = lahore_q.count()
            lahore_activities_today = lahore_q.filter(Activity.activity_date == date.today()).count()

        stats = {
            "total_users": User.query.filter_by(is_active_flag=True).count(),
            "lahore_station": lahore_station,
            "lahore_activities_total": lahore_activities_total,
            "lahore_activities_today": lahore_activities_today,
            "total_aircraft": Aircraft.query.filter_by(is_active=True).count(),
            # Third-party airlines: every active airline in the DB except
            # PIA itself (PIA is the operator running this system, not a
            # "third party" it services). Excluded here at the query level
            # (not just hidden in the template) via a case-/whitespace-
            # insensitive match on the airline name, so PIA can never slip
            # into this count regardless of how its name was entered.
            "total_airlines": Airline.query.filter(
                Airline.is_active.is_(True),
                db.func.upper(db.func.trim(Airline.name)) != "PIA",
            ).count(),
            "total_activities": Activity.query.count(),
            "flight_coverages_total": FlightCoverage.query.count(),
        }
    except Exception:
        _log_and_rollback("core stats query")
        # These counters are foundational to the page layout (not optional
        # like analytics/activity cards), so if even these fail the DB
        # connection itself is broken. Re-raise so it's still visible as
        # a 500 with a full traceback in the logs, rather than silently
        # rendering a broken page.
        raise

    # NOTE: DCE no longer renders this page at all (see the early redirect
    # to dce.overview_menu above), so the DCE-specific activity-cards
    # branch that used to live here has been removed. activity_cards stays
    # None for every remaining role and dashboard.html's DCE block simply
    # never renders for them.
    activity_cards = None

    engineer_stats = None
    engineer_recent = []
    if current_user.is_engineer:
        # Engineer Dashboard: replace the org-wide counters with the
        # logged-in Engineer's own activity data. `Activity.logged_by_id`
        # is the FK that ties an activity record to the Engineer who
        # logged it (see app/models/activity.py) -- NOT a generic
        # `user_id` column -- so every query here is scoped on that.
        from app.routes.engineer import CATEGORIES

        try:
            db.session.rollback()
            my_activities = Activity.query.filter(Activity.logged_by_id == current_user.id)

            category_counts = {
                key: my_activities.filter(Activity.activity_type.in_(cfg["types"])).count()
                for key, cfg in CATEGORIES.items()
            }

            recent_rows = (
                my_activities.options(joinedload(Activity.station), joinedload(Activity.aircraft))
                .order_by(Activity.created_at.desc())
                .limit(8)
                .all()
            )
            engineer_recent = [
                SimpleNamespace(
                    id=a.id,
                    type_label=a.activity_type.label,
                    station_code=a.station.code if a.station else "-",
                    aircraft_registration=a.aircraft.registration if a.aircraft else None,
                    activity_date=a.activity_date,
                )
                for a in recent_rows
            ]

            engineer_stats = {
                "today": my_activities.filter(Activity.activity_date == date.today()).count(),
                "total": my_activities.count(),
                "categories": category_counts,
                "category_labels": {key: cfg["label"] for key, cfg in CATEGORIES.items()},
                "flight_coverages": FlightCoverage.query.filter(
                    FlightCoverage.logged_by_id == current_user.id
                ).count(),
            }
        except Exception:
            _log_and_rollback("Engineer dashboard stats")
            dashboard_error = "Your activity summary is temporarily unavailable."
            engineer_stats = None
            engineer_recent = []

    si_stats = None
    si_recent = []
    if current_user.is_shift_incharge:
        # Shift Incharge Dashboard: replace the org-wide counters with
        # activity data scoped to the shift(s) this Shift Incharge leads.
        # A Shift Incharge is NOT tied to activities directly -- the link
        # is Activity.shift_id -> Shift, and Shift.shift_incharge ->
        # User (see app/models/shift.py / user.py's `shifts_led`
        # relationship) -- so scoping is done by shift_id, not user_id.
        # Reuses the same shift-scoping helper as the dedicated
        # /shift-incharge/dashboard module for consistency.
        from app.routes.engineer import CATEGORIES
        from app.routes.shift_incharge import _my_shift_ids

        try:
            db.session.rollback()
            shift_ids = _my_shift_ids()
            my_activities = Activity.query
            if shift_ids is None:
                pass  # Super Admin acting as Shift Incharge: unrestricted
            elif not shift_ids:
                my_activities = my_activities.filter(Activity.id == -1)
            else:
                my_activities = my_activities.filter(Activity.shift_id.in_(shift_ids))

            category_counts = {
                key: my_activities.filter(Activity.activity_type.in_(cfg["types"])).count()
                for key, cfg in CATEGORIES.items()
            }

            recent_rows = (
                my_activities.options(joinedload(Activity.station), joinedload(Activity.aircraft))
                .order_by(Activity.created_at.desc())
                .limit(8)
                .all()
            )
            si_recent = [
                SimpleNamespace(
                    id=a.id,
                    type_label=a.activity_type.label,
                    station_code=a.station.code if a.station else "-",
                    aircraft_registration=a.aircraft.registration if a.aircraft else None,
                    activity_date=a.activity_date,
                )
                for a in recent_rows
            ]

            # This dashboard only ever reports plain activity totals for
            # the Shift Incharge.
            si_stats = {
                "today": my_activities.filter(Activity.activity_date == date.today()).count(),
                "total": my_activities.count(),
                "categories": category_counts,
                "category_labels": {key: cfg["label"] for key, cfg in CATEGORIES.items()},
                "flight_coverages": FlightCoverage.query.filter(
                    FlightCoverage.logged_by_id == current_user.id
                ).count(),
            }
        except Exception:
            _log_and_rollback("Shift Incharge dashboard stats")
            dashboard_error = "Your shift activity summary is temporarily unavailable."
            si_stats = None
            si_recent = []

    recent_logs = []
    analytics_data = None
    if current_user.role == UserRole.SUPER_ADMIN:
        try:
            log_rows = (
                AuditLog.query.options(joinedload(AuditLog.user))
                .order_by(AuditLog.created_at.desc())
                .limit(10)
                .all()
            )
            # Snapshot to plain values immediately (including the eager-
            # loaded user's full_name) -- these are rendered by
            # dashboard.html and must survive the analytics block below,
            # which may itself roll back and expire live ORM instances.
            recent_logs = [
                SimpleNamespace(
                    created_at=log.created_at,
                    user_full_name=log.user.full_name if log.user else None,
                    action=log.action,
                    entity_type=log.entity_type,
                    entity_id=log.entity_id,
                    description=log.description,
                )
                for log in log_rows
            ]
        except Exception:
            _log_and_rollback("recent audit logs query")
            recent_logs = []
            dashboard_error = "Recent audit activity is temporarily unavailable."

        # Comprehensive Admin / Super Admin analytics section, computed
        # live from the activities table (Module 5 requirement). Same
        # defensive wrapping as above: analytics is an optional dashboard
        # component and must not be able to take the whole page down.
        filters = analytics.parse_filters(request.args)
        try:
            kpis = analytics.compute_kpis(filters)
            analytics_data = {
                "kpis": kpis,
                "charts": {
                    "monthly_trend": analytics.monthly_trend(filters),
                    "shift_comparison": analytics.shift_comparison(filters),
                    "aircraft_activity": analytics.aircraft_activity(filters),
                },
            }
        except Exception:
            _log_and_rollback("Super Admin analytics")
            dashboard_error = (
                "Analytics are temporarily unavailable. This usually means the production "
                "database schema is behind the latest migration (see server logs)."
            )

    try:
        return render_template(
            "dashboard.html", stats=stats, recent_logs=recent_logs, analytics=analytics_data,
            activity_cards=activity_cards, dashboard_error=dashboard_error,
            current_user_station=current_user_station,
            engineer_stats=engineer_stats, engineer_recent=engineer_recent,
            si_stats=si_stats, si_recent=si_recent,
        )
    except Exception:
        _log_and_rollback("dashboard.html template render")
        raise
