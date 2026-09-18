"""Module 4 — shared filtering & aggregation helpers for the DCE Dashboard,
Analytics and Reporting system.

Every number shown as an "official statistic" is computed live from the
`activities` table (plus its lookups) using SQLAlchemy — nothing here is
hardcoded or faked. If there is no data for a given filter, callers get
back 0 / empty lists and templates render "No data available yet."
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.activity import (
    Activity, ActivityType, MaintenanceType, CoverageType,
    INSPECTION_TYPES, MAINTENANCE_TYPES,
    TSR_TYPES, MIC_TYPES, QUALITY_TYPES,
    TRANSIT_CHECK_TYPES, CARRY_FORWARD_TYPES, DAILY_CHECK_TYPES, WEEKLY_CHECK_TYPES, DEFECT_TYPES,
    REPLACEMENT_TYPES, CF_REMOVAL_TYPES,
)
from app.models.station import Station
from app.models.shift import Shift, ShiftName
from app.models.aircraft import Aircraft, AircraftCategory
from app.models.airline import Airline
from app.models.user import User, UserRole


# --------------------------------------------------------------------------
# PIA vs Third Party — every airline in the system is "Third Party" except
# PIA itself. PIA is identified robustly (IATA "PK" / ICAO "PIA" / name
# "PIA" or "Pakistan International Airlines", case-/whitespace-insensitive)
# rather than by a hardcoded id, mirroring the same lookup already used by
# the Engineer Activity Form (app/routes/engineer.py) and Admin Aircraft
# (app/routes/admin_aircraft.py). This is the single source of truth other
# analytics helpers below key off of, so PIA/Third Party is always derived
# from the airline actually selected on the activity/inspection (Activity.
# airline_id / InspectionForm.airline_id) - NOT from the linked Aircraft
# record, which is only ever populated for PIA rows and would silently
# drop every Third Party activity from these figures.
# --------------------------------------------------------------------------
def pia_airline_id():
    airline = Airline.query.filter(
        db.or_(
            db.func.upper(db.func.trim(Airline.iata_code)) == "PK",
            db.func.upper(db.func.trim(Airline.icao_code)) == "PIA",
            db.func.upper(db.func.trim(Airline.name)).in_(
                ["PIA", "PAKISTAN INTERNATIONAL AIRLINES"]
            ),
        )
    ).order_by(
        db.case(
            (db.func.upper(db.func.trim(Airline.iata_code)) == "PK", 0),
            (db.func.upper(db.func.trim(Airline.icao_code)) == "PIA", 1),
            else_=2,
        )
    ).first()
    return airline.id if airline else None


# --------------------------------------------------------------------------
# Aircraft Type filter — coarse family buckets derived from the free-text
# Aircraft.aircraft_type field (e.g. "Boeing 777-300ER", "Airbus A320-200",
# "ATR 72-600"), matched by substring rather than by exact registration or
# exact model number. Only these three buckets exist anywhere in the app.
# --------------------------------------------------------------------------
AIRCRAFT_TYPE_FILTER_CHOICES = [
    ("777", "777"),
    ("320", "320"),
    ("atr", "ATR"),
]

_AIRCRAFT_TYPE_PATTERNS = {
    "777": "%777%",
    "320": "%320%",
    "atr": "%ATR%",
}


def aircraft_ids_for_type_bucket(bucket):
    """Returns the list of Aircraft.id whose free-text aircraft_type matches
    the given family bucket ('777' / '320' / 'atr'), or None if the bucket
    is unrecognized."""
    pattern = _AIRCRAFT_TYPE_PATTERNS.get((bucket or "").strip().lower())
    if not pattern:
        return None
    return [aid for (aid,) in db.session.query(Aircraft.id).filter(Aircraft.aircraft_type.ilike(pattern)).all()]


# --------------------------------------------------------------------------
# Filter parsing
# --------------------------------------------------------------------------
PERIOD_CHOICES = [
    ("today", "Today"),
    ("daily", "Today"),
    ("weekly", "This Week"),
    ("monthly", "This Month"),
    ("custom", "Custom Range"),
    ("all", "All Time"),
]


def parse_filters(args):
    """Read filters from a Flask `request.args`-like mapping into a plain
    dict, with sane defaults (this month) so every DCE screen opens with a
    populated, meaningful view."""
    period = (args.get("period") or "monthly").strip().lower()
    today = date.today()

    date_from = args.get("date_from", "").strip()
    date_to = args.get("date_to", "").strip()

    if period == "custom" and date_from and date_to:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            start, end = today.replace(day=1), today
    elif period in ("today", "daily"):
        start, end = today, today
    elif period == "weekly":
        start, end = today - timedelta(days=today.weekday()), today
    elif period == "all":
        start, end = None, None
    else:  # monthly (default)
        start, end = today.replace(day=1), today

    def _int_or_none(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # --------------------------------------------------------------------
    # "Model" filter — a single combined dropdown (shown first in the
    # filter bar) that lets a user pick either an aircraft-type family
    # bucket (e.g. "B777", "A320", "ATR") or a specific aircraft by its
    # registration (e.g. "AP-BGK"). It is purely additive on top of the
    # existing "aircraft_type" / "aircraft_id" filters below: if no
    # explicit aircraft_type / aircraft_id was supplied, a "model"
    # selection is translated into one of those two existing filters, so
    # the underlying query logic (apply_filters) and every other page is
    # completely unaffected when "model" isn't used.
    # --------------------------------------------------------------------
    model_param = (args.get("model") or "").strip()
    model_aircraft_type = None
    model_aircraft_id = None
    if model_param.startswith("type:"):
        model_aircraft_type = model_param.split(":", 1)[1].strip().lower() or None
    elif model_param.startswith("ac:"):
        model_aircraft_id = _int_or_none(model_param.split(":", 1)[1])

    aircraft_type_val = (args.get("aircraft_type") or "").strip().lower() or model_aircraft_type
    aircraft_id_val = _int_or_none(args.get("aircraft_id"))
    if aircraft_id_val is None:
        aircraft_id_val = model_aircraft_id

    return {
        "period": period if period in dict(PERIOD_CHOICES) else "monthly",
        "date_from": start,
        "date_to": end,
        "station_id": _int_or_none(args.get("station_id")),
        "shift_name": args.get("shift_name") or None,  # alpha/beta/charlie/delta
        "engineer_id": _int_or_none(args.get("engineer_id")),
        "aircraft_id": aircraft_id_val,
        "airline_id": _int_or_none(args.get("airline_id")),
        "aircraft_type": aircraft_type_val,
        "activity_type": args.get("activity_type") or None,
        "model": model_param or None,
    }


def apply_filters(query, filters):
    """Apply the parsed filter dict onto an Activity query."""
    if filters.get("date_from") and filters.get("date_to"):
        query = query.filter(Activity.activity_date.between(filters["date_from"], filters["date_to"]))

    if filters.get("station_id"):
        query = query.filter(Activity.station_id == filters["station_id"])

    if filters.get("shift_name"):
        shift_ids = [sid for (sid,) in db.session.query(Shift.id).filter(Shift.name == ShiftName(filters["shift_name"])).all()]
        query = query.filter(Activity.shift_id.in_(shift_ids) if shift_ids else Activity.id == -1)

    if filters.get("engineer_id"):
        query = query.filter(Activity.logged_by_id == filters["engineer_id"])

    if filters.get("aircraft_id"):
        query = query.filter(Activity.aircraft_id == filters["aircraft_id"])

    if filters.get("airline_id"):
        # Filter directly on Activity.airline_id (the airline actually
        # selected on the form) rather than going through the Aircraft
        # table - Aircraft.airline_id is only ever populated for PIA rows,
        # so the old join here silently returned zero results for every
        # Third Party airline.
        query = query.filter(Activity.airline_id == filters["airline_id"])

    if filters.get("aircraft_type"):
        ac_ids = aircraft_ids_for_type_bucket(filters["aircraft_type"])
        if ac_ids is not None:
            query = query.filter(Activity.aircraft_id.in_(ac_ids) if ac_ids else Activity.id == -1)

    if filters.get("activity_type"):
        try:
            query = query.filter(Activity.activity_type == ActivityType(filters["activity_type"]))
        except ValueError:
            pass

    return query


def base_query():
    return Activity.query


# --------------------------------------------------------------------------
# Sorting helper — shared by every DCE activity-history screen so records
# can be sorted by date, station, shift, engineer, aircraft or status.
# --------------------------------------------------------------------------
SORT_CHOICES = [
    ("date_desc", "Date (Newest)"),
    ("date_asc", "Date (Oldest)"),
    ("station", "Station"),
    ("shift", "Shift"),
    ("engineer", "Aircraft Engineer"),
    ("aircraft", "Aircraft"),
]


def apply_sort(query, sort):
    if sort == "date_asc":
        return query.order_by(Activity.activity_date.asc())
    if sort == "station":
        return query.join(Station, Activity.station_id == Station.id, isouter=True).order_by(
            Station.code.asc(), Activity.activity_date.desc()
        )
    if sort == "shift":
        return query.join(Shift, Activity.shift_id == Shift.id, isouter=True).order_by(
            Shift.name.asc(), Activity.activity_date.desc()
        )
    if sort == "engineer":
        return query.join(User, Activity.logged_by_id == User.id, isouter=True).order_by(
            User.full_name.asc(), Activity.activity_date.desc()
        )
    if sort == "aircraft":
        return query.join(Aircraft, Activity.aircraft_id == Aircraft.id, isouter=True).order_by(
            Aircraft.registration.asc(), Activity.activity_date.desc()
        )
    # default: date_desc
    return query.order_by(Activity.activity_date.desc())


# --------------------------------------------------------------------------
# Last-24-hour card analytics — powers the DCE Dashboard activity cards.
# Always computed across the last rolling 24 hours (by submission time),
# across ALL stations unless a specific station is requested.
# --------------------------------------------------------------------------
def last_24h_card_stats(types, station_id=None):
    since = datetime.utcnow() - timedelta(hours=24)

    def q():
        query = Activity.query.filter(
            Activity.activity_type.in_(types), Activity.created_at >= since
        )
        if station_id:
            query = query.filter(Activity.station_id == station_id)
        return query

    total = q().count()

    stations = q().filter(Activity.station_id.isnot(None)).with_entities(
        func.count(func.distinct(Activity.station_id))
    ).scalar() or 0
    shifts = q().filter(Activity.shift_id.isnot(None)).with_entities(
        func.count(func.distinct(Activity.shift_id))
    ).scalar() or 0
    aircraft = q().filter(Activity.aircraft_id.isnot(None)).with_entities(
        func.count(func.distinct(Activity.aircraft_id))
    ).scalar() or 0
    flights = q().filter(Activity.flight_number.isnot(None)).with_entities(
        func.count(func.distinct(Activity.flight_number))
    ).scalar() or 0

    return {
        "total": total,
        "stations": stations,
        "shifts": shifts,
        "aircraft": aircraft,
        "flights": flights,
    }


_MODEL_TYPE_LABELS = {
    "777": "B777",
    "320": "A320",
    "atr": "ATR",
}


def model_filter_choices():
    """Combined 'Model' dropdown options for the DCE filter bar: aircraft
    family buckets (B777/A320/ATR) plus every active aircraft's own
    registration, populated live from the Aircraft table. Purely additive
    - does not change AIRCRAFT_TYPE_FILTER_CHOICES or the existing
    per-registration "Aircraft" filter."""
    type_options = [
        ("type:" + value, _MODEL_TYPE_LABELS.get(value, label))
        for value, label in AIRCRAFT_TYPE_FILTER_CHOICES
    ]
    aircraft_options = [
        ("ac:" + str(a.id), a.registration)
        for a in Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all()
    ]
    return {"types": type_options, "aircraft": aircraft_options}


def filter_options():
    """Dropdown option lists shared by every DCE filter bar."""
    return {
        "stations": Station.query.filter_by(is_active=True).order_by(Station.name).all(),
        "shifts": list(ShiftName),
        "engineers": User.query.filter_by(role=UserRole.ENGINEER, is_active_flag=True).order_by(User.full_name).all(),
        "aircraft": Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all(),
        "airlines": Airline.query.filter_by(is_active=True).order_by(Airline.name).all(),
        "aircraft_types": AIRCRAFT_TYPE_FILTER_CHOICES,
        "activity_types": list(ActivityType),
        "model_choices": model_filter_choices(),
    }


# --------------------------------------------------------------------------
# KPI computation
# --------------------------------------------------------------------------
def compute_kpis(filters):
    """All headline KPI tiles for the DCE Dashboard."""
    activities_q = apply_filters(base_query(), filters)

    def count_in(types):
        return activities_q.filter(Activity.activity_type.in_(types)).count()

    aircraft_inspected = (
        db.session.query(func.count(func.distinct(Activity.aircraft_id)))
        .select_from(Activity)
    )
    aircraft_inspected = apply_filters(aircraft_inspected, filters).filter(
        Activity.aircraft_id.isnot(None)
    ).scalar() or 0

    # PIA / Third Party is driven by the airline actually selected on the
    # activity (Activity.airline_id), not by the linked Aircraft record -
    # Aircraft.airline_id/category is only ever populated for PIA rows, so
    # joining through Aircraft here silently excluded every Third Party
    # inspection (any airline other than PIA is automatically Third Party).
    _pia_id = pia_airline_id()
    inspections_q = activities_q.filter(Activity.activity_type.in_(INSPECTION_TYPES))
    if _pia_id is not None:
        pia_inspections = inspections_q.filter(Activity.airline_id == _pia_id).count()
        third_party_inspections = inspections_q.filter(
            Activity.airline_id.isnot(None), Activity.airline_id != _pia_id
        ).count()
    else:
        pia_inspections = 0
        third_party_inspections = inspections_q.filter(Activity.airline_id.isnot(None)).count()

    from app.models.activity import QariEntry, QariSeverity, QariEntryStatus
    quality_activity_ids = activities_q.filter(Activity.activity_type.in_(QUALITY_TYPES)).with_entities(Activity.id)
    closed_qari_entries_q = QariEntry.query.filter(
        QariEntry.activity_id.in_(quality_activity_ids),
        QariEntry.status == QariEntryStatus.CLOSED,
    )

    kpis = {
        "total_activities": activities_q.count(),
        "aircraft_inspected": aircraft_inspected,
        "pia_inspections": pia_inspections,
        "third_party_inspections": third_party_inspections,
        "maintenance": count_in(MAINTENANCE_TYPES),
        "maintenance_check": count_in((ActivityType.MAINTENANCE_CHECK,)),
        "flight_coverage": activities_q.filter(Activity.coverage_type == CoverageType.FLIGHT).count(),
        "tsr": count_in(TSR_TYPES),
        "mic": count_in(MIC_TYPES),
        "replacement": count_in(REPLACEMENT_TYPES),
        "quality_ri": count_in(QUALITY_TYPES),
        "qari": count_in(QUALITY_TYPES),
        "qari_closed": closed_qari_entries_q.count(),
        "qari_closed_significant": closed_qari_entries_q.filter(QariEntry.severity == QariSeverity.SIGNIFICANT).count(),
        "qari_closed_minor": closed_qari_entries_q.filter(QariEntry.severity == QariSeverity.MINOR).count(),
        "cf_removal": count_in(CF_REMOVAL_TYPES),
        "cf": count_in((ActivityType.CF,)),
        "pirep_unscheduled": count_in(DEFECT_TYPES),
        "carry_forward": count_in(CARRY_FORWARD_TYPES) or activities_q.filter(
            Activity.maintenance_type == MaintenanceType.CARRY_FORWARD
        ).count(),
        "unscheduled_maintenance": count_in(DEFECT_TYPES) or activities_q.filter(
            Activity.maintenance_type == MaintenanceType.UNSCHEDULED
        ).count(),
    }
    return kpis


# --------------------------------------------------------------------------
# Chart datasets (Chart.js friendly {labels, data} / {labels, datasets})
# --------------------------------------------------------------------------
def daily_trend(filters, days=30):
    end = filters.get("date_to") or date.today()
    start = filters.get("date_from") or (end - timedelta(days=days - 1))
    q = apply_filters(base_query(), {**filters, "date_from": start, "date_to": end})
    rows = (
        q.with_entities(Activity.activity_date, func.count(Activity.id))
        .group_by(Activity.activity_date)
        .order_by(Activity.activity_date)
        .all()
    )
    counts = {d: c for d, c in rows}
    labels, data = [], []
    cur = start
    while cur <= end:
        labels.append(cur.strftime("%d %b"))
        data.append(counts.get(cur, 0))
        cur += timedelta(days=1)
    return {"labels": labels, "data": data}


def _group_by_month(dates, months):
    """Dialect-agnostic month bucketing (avoids DB-specific date functions
    so this works identically on SQLite dev and PostgreSQL production)."""
    counts = {}
    for d in dates:
        if d is None:
            continue
        key = d.strftime("%Y-%m")
        counts[key] = counts.get(key, 0) + 1
    ordered_keys = sorted(counts.keys())[-months:]
    labels = [datetime.strptime(k, "%Y-%m").strftime("%b %Y") for k in ordered_keys]
    return {"labels": labels, "data": [counts[k] for k in ordered_keys]}


def monthly_trend(filters, months=12):
    q = apply_filters(base_query(), {**filters, "date_from": None, "date_to": None})
    dates = [d for (d,) in q.with_entities(Activity.activity_date).all()]
    return _group_by_month(dates, months)


def shift_comparison(filters):
    q = apply_filters(base_query(), {**filters, "shift_name": None})
    rows = (
        q.join(Shift, Activity.shift_id == Shift.id)
        .with_entities(Shift.name, func.count(Activity.id))
        .group_by(Shift.name)
        .all()
    )
    counts = {name: c for name, c in rows}
    order = list(ShiftName)
    return {
        "labels": [n.label for n in order],
        "data": [counts.get(n, 0) for n in order],
    }


def activity_type_breakdown(filters):
    """Replaces the old (single-station, near-useless) Station Comparison
    chart with a breakdown that is meaningful for every filter selection:
    how many logged activities fall under each Activity Type."""
    q = apply_filters(base_query(), {**filters, "activity_type": None})
    rows = (
        q.with_entities(Activity.activity_type, func.count(Activity.id))
        .group_by(Activity.activity_type)
        .all()
    )
    counts = {t: c for t, c in rows}
    order = list(ActivityType)
    return {
        "labels": [t.label for t in order],
        "data": [counts.get(t, 0) for t in order],
    }


def aircraft_activity(filters, limit=10):
    q = apply_filters(base_query(), {**filters, "aircraft_id": None})
    rows = (
        q.join(Aircraft, Activity.aircraft_id == Aircraft.id)
        .with_entities(Aircraft.registration, func.count(Activity.id))
        .group_by(Aircraft.registration)
        .order_by(func.count(Activity.id).desc())
        .limit(limit)
        .all()
    )
    return {"labels": [r[0] for r in rows], "data": [r[1] for r in rows]}


def airline_coverage(filters):
    """Activities per airline, for every airline that has ever been
    selected on an Activity - PIA and every Third Party airline alike.

    Joins straight off Activity.airline_id (the airline actually chosen on
    the form) instead of going through the Aircraft table: Aircraft.
    airline_id is only ever populated for PIA rows (Third Party activities
    use the manual registration/model fields with no Aircraft record), so
    the old Aircraft-join silently dropped every Third Party airline from
    this chart.
    """
    q = apply_filters(base_query(), {**filters, "airline_id": None})
    rows = (
        q.filter(Activity.airline_id.isnot(None))
        .join(Airline, Activity.airline_id == Airline.id)
        .with_entities(Airline.name, func.count(Activity.id))
        .group_by(Airline.name)
        .order_by(func.count(Activity.id).desc())
        .all()
    )
    return {"labels": [r[0] for r in rows], "data": [r[1] for r in rows]}


def pia_vs_third_party(filters):
    """PIA vs Third Party inspection counts, keyed off the airline that
    was actually selected on the activity (Activity.airline_id) - every
    airline except PIA counts as Third Party. See pia_airline_id() above
    for why this can't be derived from the linked Aircraft record."""
    _pia_id = pia_airline_id()
    q = apply_filters(base_query(), filters).filter(
        Activity.activity_type.in_(INSPECTION_TYPES),
        Activity.airline_id.isnot(None),
    )
    rows = q.with_entities(Activity.airline_id, func.count(Activity.id)).group_by(Activity.airline_id).all()
    pia_count = 0
    third_party_count = 0
    for airline_id, n in rows:
        if _pia_id is not None and airline_id == _pia_id:
            pia_count += n
        else:
            third_party_count += n
    return {
        "labels": ["PIA", "Third Party"],
        "data": [pia_count, third_party_count],
    }


def maintenance_breakdown(filters):
    q = apply_filters(base_query(), filters).filter(
        Activity.activity_type.in_(MAINTENANCE_TYPES)
    )
    rows = q.with_entities(Activity.activity_type, func.count(Activity.id)).group_by(Activity.activity_type).all()
    return {"labels": [t.label for t, _ in rows], "data": [c for _, c in rows]}


def scheduled_unscheduled_carry_forward(filters):
    q = apply_filters(base_query(), filters).filter(Activity.maintenance_type.isnot(None))
    rows = q.with_entities(Activity.maintenance_type, func.count(Activity.id)).group_by(Activity.maintenance_type).all()
    counts = {t: c for t, c in rows}
    order = [MaintenanceType.SCHEDULED, MaintenanceType.UNSCHEDULED, MaintenanceType.CARRY_FORWARD]
    return {"labels": [t.label for t in order], "data": [counts.get(t, 0) for t in order]}


def engineer_performance_chart(filters, limit=10):
    q = apply_filters(base_query(), {**filters, "engineer_id": None})
    rows = (
        q.join(User, Activity.logged_by_id == User.id)
        .with_entities(User.full_name, func.count(Activity.id))
        .group_by(User.full_name)
        .order_by(func.count(Activity.id).desc())
        .limit(limit)
        .all()
    )
    return {"labels": [r[0] for r in rows], "data": [r[1] for r in rows]}


def quality_ri_trend(filters, months=6):
    q = apply_filters(base_query(), {**filters, "date_from": None, "date_to": None}).filter(
        Activity.activity_type.in_(QUALITY_TYPES)
    )
    dates = [d for (d,) in q.with_entities(Activity.activity_date).all()]
    return _group_by_month(dates, months)


# --------------------------------------------------------------------------
# Tabular report builders
# --------------------------------------------------------------------------
def engineer_overview(lahore_station_id=None):
    """Live Engineer Overview figures for the main Dashboard (Module —
    Engineer Overview). Every number is computed directly from the DB;
    nothing here is hardcoded.

    "Tasks" = Activity records logged by Engineers. A task counts as
    pending when whichever status column applies to its category (TSR /
    MIC / Quality / Maintenance) is still open / in progress / carry
    forward / overdue / pending; everything else (a terminal status, or a
    category that carries no status column at all -- e.g. a plain
    inspection log) counts as completed.
    """
    from app.models.activity import MaintenanceStatus, TsrMicStatus, QualityStatus

    engineers_q = User.query.filter_by(role=UserRole.ENGINEER)
    total_engineers = engineers_q.count()
    active_engineers = engineers_q.filter(User.is_active_flag.is_(True)).count()
    inactive_engineers = total_engineers - active_engineers

    tasks_q = Activity.query.join(User, Activity.logged_by_id == User.id).filter(
        User.role == UserRole.ENGINEER
    )
    assigned_tasks = tasks_q.count()

    pending_tasks = tasks_q.filter(
        db.or_(
            Activity.maintenance_status.in_(
                (MaintenanceStatus.IN_PROGRESS, MaintenanceStatus.CARRY_FORWARD, MaintenanceStatus.OVERDUE)
            ),
            Activity.tsr_status.in_((TsrMicStatus.OPEN, TsrMicStatus.IN_PROGRESS)),
            Activity.mic_status.in_((TsrMicStatus.OPEN, TsrMicStatus.IN_PROGRESS)),
            Activity.quality_status == QualityStatus.PENDING,
        )
    ).count()
    completed_tasks = assigned_tasks - pending_tasks

    workload = round(assigned_tasks / active_engineers, 1) if active_engineers else 0

    lahore_today = lahore_month = 0
    if lahore_station_id:
        lahore_base = tasks_q.filter(Activity.station_id == lahore_station_id)
        lahore_today = lahore_base.filter(Activity.activity_date == date.today()).count()
        lahore_month = lahore_base.filter(
            Activity.activity_date >= date.today().replace(day=1)
        ).count()

    return {
        "total_engineers": total_engineers,
        "active_engineers": active_engineers,
        "inactive_engineers": inactive_engineers,
        "assigned_tasks": assigned_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "workload": workload,
        "lahore_today": lahore_today,
        "lahore_month": lahore_month,
    }


def station_summary(filters):
    stations = Station.query.filter_by(is_active=True).order_by(Station.name).all()
    out = []
    for st in stations:
        f = {**filters, "station_id": st.id}
        q = apply_filters(base_query(), f)
        out.append({
            "station": st,
            "activities": q.count(),
            "aircraft_inspected": apply_filters(base_query(), f).filter(
                Activity.aircraft_id.isnot(None)
            ).with_entities(func.count(func.distinct(Activity.aircraft_id))).scalar() or 0,
            "maintenance_check": q.filter(Activity.activity_type == ActivityType.MAINTENANCE_CHECK).count(),
            "tsr": q.filter(Activity.activity_type.in_(TSR_TYPES)).count(),
            "mic": q.filter(Activity.activity_type.in_(MIC_TYPES)).count(),
            "replacement": q.filter(Activity.activity_type.in_(REPLACEMENT_TYPES)).count(),
            "ri": q.filter(Activity.activity_type.in_(QUALITY_TYPES)).count(),
            "unscheduled": q.filter(Activity.activity_type.in_(DEFECT_TYPES)).count(),
            "cf_removal": q.filter(Activity.activity_type == ActivityType.CF_REMOVAL).count(),
            "cf": q.filter(Activity.activity_type == ActivityType.CF).count(),
        })
    return out


def shift_summary(filters):
    out = []
    for name in ShiftName:
        f = {**filters, "shift_name": name.value}
        q = apply_filters(base_query(), f)
        out.append({
            "shift": name,
            "activities": q.count(),
            "maintenance_check": q.filter(Activity.activity_type == ActivityType.MAINTENANCE_CHECK).count(),
            "tsr": q.filter(Activity.activity_type.in_(TSR_TYPES)).count(),
            "mic": q.filter(Activity.activity_type.in_(MIC_TYPES)).count(),
            "ri": q.filter(Activity.activity_type.in_(QUALITY_TYPES)).count(),
        })
    return out


def engineer_performance(filters):
    engineers = User.query.filter_by(role=UserRole.ENGINEER, is_active_flag=True).order_by(User.full_name).all()
    out = []
    for eng in engineers:
        f = {**filters, "engineer_id": eng.id}
        q = apply_filters(base_query(), f)
        total = q.count()
        if total == 0:
            continue
        out.append({
            "engineer": eng,
            "activities": total,
            "maintenance_check": q.filter(Activity.activity_type == ActivityType.MAINTENANCE_CHECK).count(),
            "tsr": q.filter(Activity.activity_type.in_(TSR_TYPES)).count(),
            "mic": q.filter(Activity.activity_type.in_(MIC_TYPES)).count(),
            "replacement": q.filter(Activity.activity_type.in_(REPLACEMENT_TYPES)).count(),
            "ri": q.filter(Activity.activity_type.in_(QUALITY_TYPES)).count(),
        })
    out.sort(key=lambda r: r["activities"], reverse=True)
    return out


def aircraft_report(filters):
    aircraft = Aircraft.query.filter_by(is_active=True).order_by(Aircraft.registration).all()
    out = []
    for ac in aircraft:
        f = {**filters, "aircraft_id": ac.id}
        q = apply_filters(base_query(), f)
        total = q.count()
        if total == 0:
            continue
        out.append({
            "aircraft": ac,
            "maintenance_check": q.filter(Activity.activity_type == ActivityType.MAINTENANCE_CHECK).count(),
            "tsr": q.filter(Activity.activity_type.in_(TSR_TYPES)).count(),
            "mic": q.filter(Activity.activity_type.in_(MIC_TYPES)).count(),
            "replacement": q.filter(Activity.activity_type.in_(REPLACEMENT_TYPES)).count(),
            "ri": q.filter(Activity.activity_type.in_(QUALITY_TYPES)).count(),
        })
    out.sort(key=lambda r: r["maintenance_check"], reverse=True)
    return out


def flight_report(filters, sort="date_desc"):
    q = apply_filters(base_query(), filters).filter(
        Activity.coverage_type == CoverageType.FLIGHT
    )
    rows = apply_sort(q, sort).limit(1000).all()
    return rows


def maintenance_report(filters, sort="date_desc"):
    q = apply_filters(base_query(), filters).filter(
        Activity.activity_type.in_(MAINTENANCE_TYPES)
    )
    rows = apply_sort(q, sort).limit(1000).all()
    return rows


OTHER_REPORT_TYPES = {
    "daily_activity": {"label": "Daily Activity", "types": None},
    "monthly_activity": {"label": "Monthly Activity", "types": None},
    "maintenance_check": {"label": "Maintenance Check", "types": (ActivityType.MAINTENANCE_CHECK,)},
    "tsr": {"label": "TSR", "types": TSR_TYPES},
    "mic": {"label": "MIC / Scheduled Maintenance", "types": MIC_TYPES},
    "replacement": {"label": "Removal/Installation", "types": REPLACEMENT_TYPES},
    "quality_ri": {"label": "QARI", "types": QUALITY_TYPES},
    "cf": {"label": "CF Added", "types": (ActivityType.CF,)},
    "cf_removal": {"label": "CF Removal", "types": CF_REMOVAL_TYPES},
    "pirep_unscheduled_maintenance": {"label": "PIREP / Unscheduled Maintenance", "types": DEFECT_TYPES},
}


def other_report(report_key, filters, sort="date_desc", severity=None, qari_status=None):
    cfg = OTHER_REPORT_TYPES.get(report_key)
    if not cfg:
        return [], cfg
    q = apply_filters(base_query(), filters)
    if cfg["types"]:
        q = q.filter(Activity.activity_type.in_(cfg["types"]))
    if report_key == "quality_ri" and (severity or qari_status):
        from app.models.activity import QariEntry, QariSeverity, QariEntryStatus
        q = q.join(QariEntry, QariEntry.activity_id == Activity.id)
        if severity:
            try:
                q = q.filter(QariEntry.severity == QariSeverity(severity))
            except ValueError:
                pass
        if qari_status:
            try:
                q = q.filter(QariEntry.status == QariEntryStatus(qari_status))
            except ValueError:
                pass
        q = q.distinct()
    rows = apply_sort(q, sort).limit(1000).all()
    return rows, cfg
