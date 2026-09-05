from flask import Blueprint, render_template, request, abort, url_for

from flask_login import login_required, current_user

from app.models.user import UserRole
from app.models.activity import ActivityType
from app.models.flight_coverage import FlightCoverage
from app.utils.decorators import roles_required
from app.utils.exports import do_export
from app.utils.audit import log_action
from app.utils import analytics as A

dce_bp = Blueprint("dce", __name__, url_prefix="/dce")


# --------------------------------------------------------------------------
# Activity cards shown on the DCE Dashboard. Each maps to the dedicated
# history report page that already ships with full filtering (station,
# shift, engineer, aircraft, status, custom date range) and export/sort.
# "endpoint"/"report_key" drive the link; "types" drive the 24h stat card.
# --------------------------------------------------------------------------
DASHBOARD_ACTIVITY_CARDS = [
    {"key": "maintenance_check", "label": "Maintenance Check", "icon": "bi-clipboard2-check",
     "types": (A.ActivityType.MAINTENANCE_CHECK,), "endpoint": "dce.other_report_view", "report_key": "maintenance_check"},
    {"key": "mic", "label": "MIC / Scheduled Maintenance", "icon": "bi-clipboard2-pulse",
     "types": A.MIC_TYPES, "endpoint": "dce.other_report_view", "report_key": "mic"},
    {"key": "quality_ri", "label": "QARI", "icon": "bi-patch-check",
     "types": A.QUALITY_TYPES, "endpoint": "dce.other_report_view", "report_key": "quality_ri"},
    {"key": "tsr", "label": "TSR", "icon": "bi-exclamation-triangle",
     "types": A.TSR_TYPES, "endpoint": "dce.other_report_view", "report_key": "tsr"},
    {"key": "pirep_unscheduled_maintenance", "label": "PIREP / Unscheduled Maintenance", "icon": "bi-wrench-adjustable",
     "types": A.DEFECT_TYPES, "endpoint": "dce.other_report_view", "report_key": "pirep_unscheduled_maintenance"},
    {"key": "replacement", "label": "Removal/Installation", "icon": "bi-arrow-repeat",
     "types": (A.ActivityType.REPLACEMENT,), "endpoint": "dce.other_report_view", "report_key": "replacement"},
    {"key": "cf_removal", "label": "CF Removal", "icon": "bi-dash-circle",
     "types": (A.ActivityType.CF_REMOVAL,), "endpoint": "dce.other_report_view", "report_key": "cf_removal"},
    {"key": "cf", "label": "CF Added", "icon": "bi-arrow-repeat",
     "types": (A.ActivityType.CF,), "endpoint": "dce.other_report_view", "report_key": "cf"},
]


def dashboard_activity_cards(station_id=None):
    """Builds the DCE Dashboard activity-card list with live last-24h stats."""
    cards = []
    for cfg in DASHBOARD_ACTIVITY_CARDS:
        stats = A.last_24h_card_stats(cfg["types"], station_id=station_id)
        if cfg["report_key"]:
            url = url_for(cfg["endpoint"], report_key=cfg["report_key"])
        else:
            url = url_for(cfg["endpoint"])
        cards.append({**cfg, "stats": stats, "url": url})
    return cards


def _filters():
    return A.parse_filters(request.args)


def _base_ctx(active_filters):
    ctx = A.filter_options()
    ctx["filters"] = active_filters
    ctx["ActivityType"] = ActivityType
    return ctx


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@dce_bp.route("/dashboard")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def dashboard():
    filters = _filters()
    kpis = A.compute_kpis(filters)

    charts = {
        "daily_trend": A.daily_trend(filters),
        "monthly_trend": A.monthly_trend(filters),
        "shift_comparison": A.shift_comparison(filters),
        "activity_type_breakdown": A.activity_type_breakdown(filters),
        "aircraft_activity": A.aircraft_activity(filters),
        "airline_coverage": A.airline_coverage(filters),
        "pia_vs_third_party": A.pia_vs_third_party(filters),
        "maintenance_breakdown": A.maintenance_breakdown(filters),
        "smcf": A.scheduled_unscheduled_carry_forward(filters),
        "engineer_performance": A.engineer_performance_chart(filters),
        "quality_ri_trend": A.quality_ri_trend(filters),
    }

    ctx = _base_ctx(filters)
    ctx.update(kpis=kpis, charts=charts)
    return render_template("dce/dashboard.html", **ctx)


# --------------------------------------------------------------------------
# Navigation hub pages (Overview / Activities / Reports)
# --------------------------------------------------------------------------
# These pages introduce NO new data or business logic - they are pure
# navigation menus that link out to the exact same routes that already
# existed in the sidebar. Grouping them here lets the DCE sidebar stay
# short (Overview / Activities / Reports / Settings) while every existing
# report/activity/summary page remains fully reachable.

# Overview stat tiles. Each maps a KPI (from A.compute_kpis) to the exact
# same filtered Activities report ("report_key") used by the Activities
# menu/history pages, so clicking any number on Overview opens Activities
# pre-filtered to precisely those records (e.g. TSR = 5 -> click 5 -> the
# 5 TSR activities). Current filter-bar selections (station/shift/period/
# date range) are always carried over onto the link, so the number shown
# and the list it opens never disagree.
OVERVIEW_STAT_TILES = [
    {"kpi": "maintenance_check", "label": "Maintenance Check", "icon": "bi-clipboard2-check", "report_key": "maintenance_check"},
    {"kpi": "mic", "label": "MIC / Scheduled Maintenance", "icon": "bi-clipboard2-pulse", "report_key": "mic"},
    {"kpi": "qari", "label": "QARI", "icon": "bi-patch-check", "report_key": "quality_ri"},
    {"kpi": "tsr", "label": "TSR", "icon": "bi-exclamation-triangle", "report_key": "tsr"},
    {"kpi": "pirep_unscheduled", "label": "PIREP / Unscheduled Maintenance", "icon": "bi-wrench-adjustable", "report_key": "pirep_unscheduled_maintenance"},
    {"kpi": "replacement", "label": "Removal/Installation", "icon": "bi-arrow-repeat", "report_key": "replacement"},
    {"kpi": "cf_removal", "label": "CF Removal", "icon": "bi-dash-circle", "report_key": "cf_removal"},
    {"kpi": "cf", "label": "CF Added", "icon": "bi-arrow-repeat", "report_key": "cf"},
]

# Engineer Summary columns shown on Overview: same activity-type buckets as
# the stat tiles above, keyed the same way A.engineer_performance() returns
# them, so every per-engineer number reuses that existing report data.
ENGINEER_SUMMARY_COLUMNS = [
    {"key": "maintenance_check", "label": "Maint. Check", "report_key": "maintenance_check"},
    {"key": "tsr", "label": "TSR", "report_key": "tsr"},
    {"key": "mic", "label": "MIC", "report_key": "mic"},
    {"key": "replacement", "label": "Removal/Installation", "report_key": "replacement"},
    {"key": "ri", "label": "QARI", "report_key": "quality_ri"},
]


def _overview_stats(filters):
    """Builds the clickable KPI stat tiles for Overview, carrying the
    current filter-bar selections through to each tile's Activities link
    so the count and the filtered list it opens always match."""
    kpis = A.compute_kpis(filters)
    link_args = {k: v for k, v in request.args.items() if k != "report_key"}
    tiles = []
    for cfg in OVERVIEW_STAT_TILES:
        tiles.append({
            **cfg,
            "value": kpis.get(cfg["kpi"], 0),
            "url": url_for("dce.other_report_view", report_key=cfg["report_key"], **link_args),
        })
    # Non-activity-type tiles: aircraft coverage numbers. There's no single
    # activity-type filter for these, so they link to the closest existing
    # filtered report (Aircraft Summary) rather than duplicating logic.
    aircraft_url = url_for("dce.aircraft_report_view", **link_args)
    tiles.insert(0, {"kpi": "aircraft_inspected", "label": "Aircraft Inspected", "icon": "bi-airplane",
                      "value": kpis.get("aircraft_inspected", 0), "url": aircraft_url})

    # Flight Coverages: not an Activity-type KPI (separate FlightCoverage
    # table/module), so its count and link are built directly here rather
    # than via A.compute_kpis().
    tiles.append({
        "kpi": "flight_coverages", "label": "Flight Coverages", "icon": "bi-airplane-engines",
        "value": FlightCoverage.query.count(),
        "url": url_for("engineer.list_flight_coverages"),
    })
    return kpis, tiles


def _engineer_summary(filters):
    """Per-engineer activity counts for the Overview page's Engineer
    Summary. Reuses A.engineer_performance() (same data as the Engineer
    Performance report) and attaches a filtered-Activities link (scoped to
    that engineer + activity type) to every non-zero number."""
    rows = A.engineer_performance(filters)
    link_args = {k: v for k, v in request.args.items() if k not in ("report_key", "engineer_id")}
    out = []
    for r in rows:
        eng_id = r["engineer"].id
        cells = []
        for col in ENGINEER_SUMMARY_COLUMNS:
            cells.append({
                "label": col["label"],
                "value": r[col["key"]],
                "url": url_for("dce.other_report_view", report_key=col["report_key"], engineer_id=eng_id, **link_args),
            })
        out.append({
            "engineer": r["engineer"],
            "activities": r["activities"],
            "activities_url": url_for("dce.other_report_view", report_key="daily_activity", engineer_id=eng_id, **link_args),
            "cells": cells,
        })
    return out


@dce_bp.route("/overview")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def overview_menu():
    filters = _filters()
    kpis, stat_tiles = _overview_stats(filters)
    engineer_rows = _engineer_summary(filters)

    cards = [
        {"label": "Daily Summary", "desc": "Today's activity at a glance.",
         "icon": "bi-calendar-day", "url": url_for("dce.dashboard", period="daily")},
        {"label": "Weekly Summary", "desc": "Rolled-up view for the current week.",
         "icon": "bi-calendar-week", "url": url_for("dce.dashboard", period="weekly")},
        {"label": "Monthly Summary", "desc": "Trends across the current month.",
         "icon": "bi-calendar-month", "url": url_for("dce.dashboard", period="monthly")},
        {"label": "Shift Summary", "desc": "Performance broken down by shift.",
         "icon": "bi-clock-history", "url": url_for("dce.shifts_report")},
        {"label": "Station Summary", "desc": "Activity totals by station.",
         "icon": "bi-geo-alt", "url": url_for("dce.stations_report")},
        {"label": "Aircraft Summary", "desc": "Activity totals by aircraft.",
         "icon": "bi-airplane", "url": url_for("dce.aircraft_report_view")},
        {"label": "Activity Summary", "desc": "Full log of activity.",
         "icon": "bi-file-earmark-bar-graph", "url": url_for("dce.other_report_view", report_key="daily_activity")},
        {"label": "Aircraft Engineer Overview", "desc": "Aircraft Engineer headcount, task load and Lahore activity.",
         "icon": "bi-person-gear", "url": url_for("dce.engineer_overview")},
    ]

    ctx = _base_ctx(filters)
    ctx.update(cards=cards, kpis=kpis, stat_tiles=stat_tiles, engineer_rows=engineer_rows,
               engineer_summary_columns=ENGINEER_SUMMARY_COLUMNS)
    return render_template("dce/overview_menu.html", **ctx)


@dce_bp.route("/overview/engineers")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def engineer_overview():
    """Dedicated Engineer Overview page: headcount, task load, and Lahore
    activity - reachable from the Overview menu's card grid rather than
    living on the main Dashboard."""
    from app.utils.stations import get_lahore_station

    lahore_station = get_lahore_station()
    overview = A.engineer_overview(lahore_station_id=lahore_station.id if lahore_station else None)
    return render_template(
        "dce/engineer_overview.html",
        overview=overview,
        lahore_station=lahore_station,
    )


@dce_bp.route("/activities")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def activities_menu():
    cards = [
        {"label": "Maintenance Check", "desc": "Maintenance check activity history.",
         "icon": "bi-clipboard2-check", "url": url_for("dce.other_report_view", report_key="maintenance_check")},
        {"label": "MIC / Scheduled Maintenance", "desc": "MIC / Scheduled Maintenance activity history.",
         "icon": "bi-clipboard2-pulse", "url": url_for("dce.other_report_view", report_key="mic")},
        {"label": "QARI", "desc": "Quality / RI activity history.",
         "icon": "bi-patch-check", "url": url_for("dce.other_report_view", report_key="quality_ri")},
        {"label": "TSR", "desc": "Technical Snag Report history.",
         "icon": "bi-exclamation-triangle", "url": url_for("dce.other_report_view", report_key="tsr")},
        {"label": "PIREP / Unscheduled Maintenance", "desc": "PIREP / Unscheduled Maintenance activity history.",
         "icon": "bi-wrench-adjustable", "url": url_for("dce.other_report_view", report_key="pirep_unscheduled_maintenance")},
        {"label": "Removal/Installation", "desc": "Removal/Installation activity history.",
         "icon": "bi-arrow-repeat", "url": url_for("dce.other_report_view", report_key="replacement")},
        {"label": "CF Removal", "desc": "CF Removal activity history.",
         "icon": "bi-dash-circle", "url": url_for("dce.other_report_view", report_key="cf_removal")},
        {"label": "CF Added", "desc": "Carry Forward activity history.",
         "icon": "bi-arrow-repeat", "url": url_for("dce.other_report_view", report_key="cf")},
    ]
    return render_template("dce/activities_menu.html", cards=cards)


@dce_bp.route("/reports")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def reports_menu():
    cards = [
        {"label": "Aircraft Reports", "desc": "Inspection/maintenance activity per aircraft.",
         "icon": "bi-airplane", "url": url_for("dce.aircraft_report_view")},
        {"label": "Station Reports", "desc": "Activity totals per station.",
         "icon": "bi-geo-alt", "url": url_for("dce.stations_report")},
        {"label": "Employee Reports", "desc": "Aircraft Engineer performance breakdown.",
         "icon": "bi-person-badge", "url": url_for("dce.engineers_report")},
        {"label": "Activity Reports", "desc": "Full log of activity.",
         "icon": "bi-file-earmark-bar-graph", "url": url_for("dce.other_report_view", report_key="daily_activity")},
        {"label": "Maintenance Reports", "desc": "Maintenance check / scheduled/unscheduled maintenance log.",
         "icon": "bi-tools", "url": url_for("dce.maintenance_report_view")},
        {"label": "Inspection Reports", "desc": "Aircraft Engineer inspection form credits.",
         "icon": "bi-clipboard2-pulse", "url": url_for("dce.inspection_credits_report")},
        {"label": "PIREP / Unscheduled Maintenance Reports", "desc": "PIREP / Unscheduled Maintenance activity history.",
         "icon": "bi-wrench-adjustable", "url": url_for("dce.other_report_view", report_key="pirep_unscheduled_maintenance")},
        {"label": "TSR Reports", "desc": "Technical Snag Report history.",
         "icon": "bi-exclamation-triangle", "url": url_for("dce.other_report_view", report_key="tsr")},
        {"label": "MIC / Scheduled Maintenance Reports", "desc": "MIC / Scheduled Maintenance activity history.",
         "icon": "bi-journal-medical", "url": url_for("dce.other_report_view", report_key="mic")},
        {"label": "QARI Reports", "desc": "Quality / RI activity history.",
         "icon": "bi-patch-check", "url": url_for("dce.other_report_view", report_key="quality_ri")},
        {"label": "Removal/Installation Reports", "desc": "Removal/Installation activity history.",
         "icon": "bi-arrow-repeat", "url": url_for("dce.other_report_view", report_key="replacement")},
        {"label": "CF Removal Reports", "desc": "CF Removal activity history.",
         "icon": "bi-dash-circle", "url": url_for("dce.other_report_view", report_key="cf_removal")},
        {"label": "CF Reports", "desc": "Carry Forward activity history.",
         "icon": "bi-arrow-repeat", "url": url_for("dce.other_report_view", report_key="cf")},
    ]
    return render_template("dce/reports_menu.html", cards=cards)


# --------------------------------------------------------------------------
# Station / Shift / Engineer / Aircraft summaries
# --------------------------------------------------------------------------
@dce_bp.route("/reports/stations")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def stations_report():
    filters = _filters()
    rows = A.station_summary(filters)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "stations"
    ctx["link_args"] = {k: v for k, v in request.args.items() if k != "station_id"}
    return render_template("dce/stations_report.html", **ctx)


@dce_bp.route("/reports/shifts")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def shifts_report():
    filters = _filters()
    rows = A.shift_summary(filters)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "shifts"
    ctx["link_args"] = {k: v for k, v in request.args.items() if k != "shift_name"}
    return render_template("dce/shifts_report.html", **ctx)


@dce_bp.route("/reports/engineers")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def engineers_report():
    filters = _filters()
    rows = A.engineer_performance(filters)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "engineers"
    ctx["link_args"] = {k: v for k, v in request.args.items() if k != "engineer_id"}
    return render_template("dce/engineers_report.html", **ctx)


@dce_bp.route("/reports/inspection-credits")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def inspection_credits_report():
    """Per-engineer credit totals earned via the Engineer Inspection Form.

    Reads straight off the InspectionCredit ledger - which is always fully
    rebuilt on save - so totals here can never double count an inspection
    or an activity within it.
    """
    from app import db
    from app.models.inspection import InspectionForm, InspectionCredit
    from app.models.user import User
    from app.models.activity import ActivityType

    rows_q = (
        db.session.query(
            User.id, User.full_name, InspectionCredit.credit_type,
            db.func.sum(InspectionCredit.credit_value),
        )
        .join(InspectionCredit, InspectionCredit.engineer_id == User.id)
        .join(InspectionForm, InspectionForm.id == InspectionCredit.inspection_form_id)
        .group_by(User.id, User.full_name, InspectionCredit.credit_type)
        .order_by(User.full_name)
    )

    by_engineer = {}
    for engineer_id, full_name, credit_type, total in rows_q.all():
        row = by_engineer.setdefault(engineer_id, {"full_name": full_name, "inspection_total": 0.0, "activities": {}})
        if credit_type == "inspection":
            row["inspection_total"] = float(total)
        else:
            try:
                label = ActivityType(credit_type).label
            except ValueError:
                label = credit_type
            row["activities"][label] = float(total)

    rows = sorted(by_engineer.values(), key=lambda r: r["full_name"])

    return render_template("dce/inspection_credits_report.html", rows=rows)


@dce_bp.route("/reports/aircraft")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def aircraft_report_view():
    filters = _filters()
    rows = A.aircraft_report(filters)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "aircraft"
    return render_template("dce/aircraft_report.html", **ctx)


@dce_bp.route("/reports/flights")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def flights_report():
    filters = _filters()
    sort = request.args.get("sort", "date_desc")
    rows = A.flight_report(filters, sort=sort)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "flights"
    ctx["sort"] = sort
    ctx["sort_choices"] = A.SORT_CHOICES
    return render_template("dce/flights_report.html", **ctx)


@dce_bp.route("/reports/maintenance")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def maintenance_report_view():
    filters = _filters()
    rows = A.maintenance_report(filters)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "maintenance"
    return render_template("dce/maintenance_report.html", **ctx)


@dce_bp.route("/reports/other/<report_key>")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def other_report_view(report_key):
    filters = _filters()
    sort = request.args.get("sort", "date_desc")
    severity = request.args.get("severity", "").strip() or None
    qari_status = request.args.get("qari_status", "").strip() or None
    rows, cfg = A.other_report(report_key, filters, sort=sort, severity=severity, qari_status=qari_status)
    if not cfg:
        abort(404)
    ctx = _base_ctx(filters)
    ctx["rows"] = rows
    ctx["report_key"] = "other:" + report_key
    ctx["other_key"] = report_key
    ctx["report_label"] = cfg["label"]
    ctx["sort"] = sort
    ctx["sort_choices"] = A.SORT_CHOICES
    return render_template("dce/other_report.html", **ctx)


# --------------------------------------------------------------------------
# Exports — every export re-runs the SAME query used to render the page,
# with the SAME filters (nothing is cached/faked), then streams the file.
# --------------------------------------------------------------------------
def _row_or_dash(v):
    return v if v not in (None, "") else "-"


@dce_bp.route("/export/<report_key>/<fmt>")
@login_required
@roles_required(UserRole.DCE, UserRole.SUPER_ADMIN)
def export_report(report_key, fmt):
    filters = _filters()

    if report_key == "stations":
        data = A.station_summary(filters)
        columns = ["Station", "Activities", "Aircraft Inspected", "Maintenance Check",
                   "TSR", "MIC", "Removal/Installation", "QARI", "PIREP/Unscheduled", "CF Removal", "CF Added"]
        rows = [[r["station"].name, r["activities"], r["aircraft_inspected"], r["maintenance_check"],
                 r["tsr"], r["mic"], r["replacement"], r["ri"],
                 r["unscheduled"], r["cf_removal"], r["cf"]] for r in data]
        title = "Station Summary"

    elif report_key == "shifts":
        data = A.shift_summary(filters)
        columns = ["Shift", "Activities", "Maintenance Check", "TSR", "MIC", "QARI"]
        rows = [[r["shift"].label, r["activities"], r["maintenance_check"], r["tsr"], r["mic"],
                 r["ri"]] for r in data]
        title = "Shift Summary"

    elif report_key == "engineers":
        data = A.engineer_performance(filters)
        columns = ["Aircraft Engineer", "Shift(s)", "Station", "Activities", "Maintenance Check",
                   "TSR", "MIC", "Removal/Installation", "QARI"]
        rows = [[r["engineer"].full_name, "-", r["engineer"].station.code if r["engineer"].station else "-",
                 r["activities"], r["maintenance_check"], r["tsr"], r["mic"],
                 r["replacement"], r["ri"]] for r in data]
        title = "Aircraft Engineer Performance"

    elif report_key == "aircraft":
        data = A.aircraft_report(filters)
        columns = ["Registration", "Aircraft Type", "Airline", "Maintenance Check",
                   "TSR", "MIC", "Removal/Installation", "QARI"]
        rows = [[r["aircraft"].registration, r["aircraft"].aircraft_type, r["aircraft"].airline.name,
                 r["maintenance_check"], r["tsr"], r["mic"], r["replacement"], r["ri"]]
                for r in data]
        title = "Aircraft Report"

    elif report_key == "flights":
        data = A.flight_report(filters)
        columns = ["Flight Number", "Date", "Airline", "Aircraft", "Shift", "Station", "Destination",
                   "Aircraft Engineer", "Aircraft Engineer Sent", "Inspection"]
        rows = [[
            _row_or_dash(a.flight_number), a.activity_date.strftime("%Y-%m-%d"),
            a.aircraft.airline.name if a.aircraft else "-",
            a.aircraft.registration if a.aircraft else "-",
            a.shift.name.label if a.shift else "-",
            a.station.code if a.station else "-",
            _row_or_dash(a.destination_station),
            a.logged_by.full_name if a.logged_by else "-",
            a.engineer_sent_with.full_name if a.engineer_sent_with else "-",
            "Yes" if a.inspection_performed else "No",
        ] for a in data]
        title = "Flight Report"

    elif report_key == "maintenance":
        data = A.maintenance_report(filters)
        columns = ["Aircraft", "Maintenance Type", "Aircraft Engineer", "Shift", "Station", "Date", "Status",
                   "TSR", "MIC", "RI", "Remarks"]
        rows = [[
            a.aircraft.registration if a.aircraft else "-",
            a.maintenance_type.label if a.maintenance_type else "-",
            a.logged_by.full_name if a.logged_by else "-",
            a.shift.name.label if a.shift else "-",
            a.station.code if a.station else "-",
            a.activity_date.strftime("%Y-%m-%d"),
            a.maintenance_status.label if a.maintenance_status else "-",
            _row_or_dash(a.tsr_number), _row_or_dash(a.mic_number),
            a.quality_status.label if a.quality_status else "-",
            _row_or_dash(a.remarks),
        ] for a in data]
        title = "Maintenance Report"

    elif report_key.startswith("other:"):
        key = report_key.split(":", 1)[1]
        data, cfg = A.other_report(key, filters)
        if not cfg:
            abort(404)
        columns = ["Date", "Station", "Shift", "Aircraft Engineer", "Aircraft", "Activity Type", "Remarks"]
        rows = [[
            a.activity_date.strftime("%Y-%m-%d"),
            a.station.code if a.station else "-",
            a.shift.name.label if a.shift else "-",
            a.logged_by.full_name if a.logged_by else "-",
            a.aircraft.registration if a.aircraft else "-",
            a.activity_type.label,
            _row_or_dash(a.remarks),
        ] for a in data]
        title = cfg["label"]

    else:
        abort(404)

    log_action(
        "EXPORT", entity_type="Report", description=f"Exported '{title}' report as {fmt.upper()}"
    )
    return do_export(fmt, title, columns, rows, base_name=report_key.replace(":", "_"))
