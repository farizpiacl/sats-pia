import enum
from app import db
from app.models.base import TimestampMixin


class ActivityType(enum.Enum):
    """The canonical Activity Types used everywhere in the system."""
    MAINTENANCE_CHECK = "maintenance_check"
    MIC_SCHEDULED_MAINTENANCE = "mic_scheduled_maintenance"
    QARI = "qari"
    TSR = "tsr"
    PIREP_UNSCHEDULED_MAINTENANCE = "pirep_unscheduled_maintenance"
    REPLACEMENT = "replacement"
    CF_REMOVAL = "cf_removal"
    CF = "cf"

    @property
    def label(self):
        return {
            ActivityType.MAINTENANCE_CHECK: "Maintenance Check",
            ActivityType.MIC_SCHEDULED_MAINTENANCE: "MIC / Scheduled Maintenance",
            ActivityType.QARI: "QARI",
            ActivityType.TSR: "TSR",
            ActivityType.PIREP_UNSCHEDULED_MAINTENANCE: "PIREP / Unscheduled Maintenance",
            ActivityType.REPLACEMENT: "Removal/Installation",
            ActivityType.CF_REMOVAL: "CF Removal",
            ActivityType.CF: "CF Added",
        }[self]


# Legacy enum values that may still exist in old data / old code paths.
# Kept only as a migration aid (see LEGACY_ACTIVITY_TYPE_MAP below) - the
# canonical set of values going forward is ActivityType above.
LEGACY_ACTIVITY_TYPE_MAP = {
    "aircraft_inspection": ActivityType.MAINTENANCE_CHECK,
    "sari": ActivityType.QARI,
    "technical_inspection": ActivityType.MAINTENANCE_CHECK,
    "transit_inspection": ActivityType.MAINTENANCE_CHECK,
    "flight_inspection": ActivityType.MAINTENANCE_CHECK,
    "maintenance": ActivityType.MAINTENANCE_CHECK,
    "fixing_rectification": ActivityType.PIREP_UNSCHEDULED_MAINTENANCE,
    "wheel_change": ActivityType.REPLACEMENT,
    "mic": ActivityType.MIC_SCHEDULED_MAINTENANCE,
    "quality_inspection_ri": ActivityType.QARI,
    "scheduled_maintenance": ActivityType.MIC_SCHEDULED_MAINTENANCE,
    "unscheduled_maintenance": ActivityType.PIREP_UNSCHEDULED_MAINTENANCE,
    "carry_forward_maintenance": ActivityType.CF,
    "daily_check": ActivityType.MAINTENANCE_CHECK,
    "weekly_check": ActivityType.MAINTENANCE_CHECK,
    "defect": ActivityType.PIREP_UNSCHEDULED_MAINTENANCE,
    "other": ActivityType.MAINTENANCE_CHECK,
}


# Groupings used to power the category-specific list pages & dashboard tiles.
INSPECTION_TYPES = (ActivityType.MAINTENANCE_CHECK,)
TRANSIT_CHECK_TYPES = (ActivityType.MAINTENANCE_CHECK,)
FLIGHT_COVERAGE_TYPES = (ActivityType.MAINTENANCE_CHECK,)
MAINTENANCE_TYPES = (
    ActivityType.MAINTENANCE_CHECK,
    ActivityType.REPLACEMENT,
    ActivityType.MIC_SCHEDULED_MAINTENANCE,
    ActivityType.PIREP_UNSCHEDULED_MAINTENANCE,
)
CARRY_FORWARD_TYPES = (ActivityType.CF, ActivityType.CF_REMOVAL)
TSR_TYPES = (ActivityType.TSR,)
MIC_TYPES = (ActivityType.MIC_SCHEDULED_MAINTENANCE,)
QUALITY_TYPES = (ActivityType.QARI,)  # QARI - Quality / RI
DAILY_CHECK_TYPES = (ActivityType.MAINTENANCE_CHECK,)
WEEKLY_CHECK_TYPES = (ActivityType.MAINTENANCE_CHECK,)
DEFECT_TYPES = (ActivityType.PIREP_UNSCHEDULED_MAINTENANCE,)
REPLACEMENT_TYPES = (ActivityType.REPLACEMENT,)
CF_REMOVAL_TYPES = (ActivityType.CF_REMOVAL,)


class MaintenanceType(enum.Enum):
    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"
    CARRY_FORWARD = "carry_forward"

    @property
    def label(self):
        return {
            MaintenanceType.SCHEDULED: "Scheduled",
            MaintenanceType.UNSCHEDULED: "unscheduled",
            MaintenanceType.CARRY_FORWARD: "Carry Forward",
        }[self]


class MaintenanceStatus(enum.Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    CARRY_FORWARD = "carry_forward"
    OVERDUE = "overdue"

    @property
    def label(self):
        return {
            MaintenanceStatus.COMPLETED: "Completed",
            MaintenanceStatus.IN_PROGRESS: "In Progress",
            MaintenanceStatus.CARRY_FORWARD: "Carry Forward",
            MaintenanceStatus.OVERDUE: "Overdue",
        }[self]

    @property
    def badge_class(self):
        return {
            MaintenanceStatus.COMPLETED: "badge-approved",
            MaintenanceStatus.IN_PROGRESS: "badge-role",
            MaintenanceStatus.CARRY_FORWARD: "badge-pending",
            MaintenanceStatus.OVERDUE: "badge-rejected",
        }[self]


class TsrMicStatus(enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

    @property
    def label(self):
        return {
            TsrMicStatus.OPEN: "Open",
            TsrMicStatus.IN_PROGRESS: "In Progress",
            TsrMicStatus.CLOSED: "Closed",
        }[self]

    @property
    def badge_class(self):
        return {
            TsrMicStatus.OPEN: "badge-pending",
            TsrMicStatus.IN_PROGRESS: "badge-role",
            TsrMicStatus.CLOSED: "badge-approved",
        }[self]


class QualityStatus(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    OBSERVATION = "observation"
    PENDING = "pending"

    @property
    def label(self):
        return {
            QualityStatus.PASSED: "Passed",
            QualityStatus.FAILED: "Failed",
            QualityStatus.OBSERVATION: "Observation",
            QualityStatus.PENDING: "Pending",
        }[self]

    @property
    def badge_class(self):
        return {
            QualityStatus.PASSED: "badge-approved",
            QualityStatus.FAILED: "badge-rejected",
            QualityStatus.OBSERVATION: "badge-role",
            QualityStatus.PENDING: "badge-pending",
        }[self]


class CoverageType(enum.Enum):
    GROUND = "ground"
    FLIGHT = "flight"

    @property
    def label(self):
        return "Ground" if self == CoverageType.GROUND else "Flight"


class MaintenanceCheckType(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    TRANSIT = "transit"

    @property
    def label(self):
        return {
            MaintenanceCheckType.DAILY: "Daily",
            MaintenanceCheckType.WEEKLY: "Weekly",
            MaintenanceCheckType.TRANSIT: "Transit",
        }[self]


class QariSeverity(enum.Enum):
    SIGNIFICANT = "significant"
    MINOR = "minor"

    @property
    def label(self):
        return "Significant" if self == QariSeverity.SIGNIFICANT else "Minor"


class QariEntryStatus(enum.Enum):
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"

    @property
    def label(self):
        return {
            QariEntryStatus.OPEN: "Open",
            QariEntryStatus.PARTIALLY_CLOSED: "Partially Closed",
            QariEntryStatus.CLOSED: "Closed",
        }[self]

    @property
    def badge_class(self):
        return {
            QariEntryStatus.OPEN: "badge-pending",
            QariEntryStatus.PARTIALLY_CLOSED: "badge-role",
            QariEntryStatus.CLOSED: "badge-approved",
        }[self]


class Activity(TimestampMixin, db.Model):
    """The core Engineer Operations record.

    A single Engineer Activity form drives every operational list in the
    Engineer module (Aircraft Inspections, Maintenance, Flight Coverage,
    TSR, MIC, Quality/RI) - each of those screens is a filtered view of
    this table keyed on `activity_type`. This keeps one authoritative
    record per activity.
    """

    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)

    # --- Who / where / when ---
    activity_date = db.Column(db.Date, nullable=False, index=True)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False, index=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    logged_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Engineer
    aircraft_id = db.Column(db.Integer, db.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True, index=True)

    # --- Airline / aircraft identification (new UX form) ---
    # airline_id drives the "PIA -> dropdown / Other -> manual entry"
    # branch on the Engineer Activity Form. When the selected airline is
    # PIA, `aircraft_id` above is used (existing dropdown). When it isn't,
    # the engineer types the registration/model manually into these two
    # new nullable columns instead - `aircraft_id` is left null.
    airline_id = db.Column(db.Integer, db.ForeignKey("airlines.id", ondelete="SET NULL"), nullable=True, index=True)
    aircraft_registration_manual = db.Column(db.String(20), nullable=True)
    aircraft_model_manual = db.Column(db.String(100), nullable=True)

    coverage_type = db.Column(
        db.Enum(
            CoverageType,
            name="coverage_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    # --- CRS association (Maintenance Check only) ---
    # crs_engineer_id is whichever engineer is the Certifying Release to
    # Service engineer for this activity; second_engineer_id is the other
    # engineer sharing the record. is_crs records whether the *current
    # user* (logged_by) was the one who chose "CRS = Yes" (i.e. is
    # themself the CRS engineer) - kept so the edit screen can restore the
    # Yes/No radio without having to re-derive it.
    crs_engineer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    second_engineer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_crs = db.Column(db.Boolean, nullable=True)

    maintenance_check_type = db.Column(
        db.Enum(
            MaintenanceCheckType,
            name="maintenance_check_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    activity_type = db.Column(
        db.Enum(
            ActivityType,
            name="activity_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    # --- Aircraft inspection / general ---
    num_aircraft_checked = db.Column(db.Integer, nullable=True)
    inspection_details = db.Column(db.Text, nullable=True)
    inspection_result = db.Column(db.String(50), nullable=True)

    # --- Flight coverage ---
    flight_number = db.Column(db.String(20), nullable=True)
    engineer_sent_with_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    departure_time = db.Column(db.Time, nullable=True)
    arrival_time = db.Column(db.Time, nullable=True)
    inspection_performed = db.Column(db.Boolean, nullable=True)
    # Free-text destination station for a Flight Coverage activity
    # (coverage_type == FLIGHT). Deliberately a manual text field, not a
    # foreign key to Station / a hardcoded list - the engineer types
    # whatever destination the flight was covered to.
    destination_station = db.Column(db.String(150), nullable=True)

    # --- Maintenance ---
    maintenance_type = db.Column(
    db.Enum(
        MaintenanceType,
        name="maintenance_type",
        values_callable=lambda enum_cls: [e.value for e in enum_cls]
    ),
    nullable=True
)
    component = db.Column(db.String(150), nullable=True)
    maintenance_details = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    maintenance_status = db.Column(
        db.Enum(
            MaintenanceStatus,
            name="maintenance_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
        index=True,
    )

    # --- TSR ---
    tsr_number = db.Column(db.String(50), nullable=True)
    tsr_status = db.Column(
        db.Enum(
            TsrMicStatus,
            name="tsr_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    # --- MIC ---
    mic_number = db.Column(db.String(50), nullable=True)
    mic_status = db.Column(
        db.Enum(
            TsrMicStatus,
            name="mic_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    # --- Quality / RI ---
    quality_inspection_type = db.Column(db.String(100), nullable=True)
    quality_finding = db.Column(db.Text, nullable=True)
    quality_status = db.Column(
        db.Enum(
            QualityStatus,
            name="quality_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    remarks = db.Column(db.Text, nullable=True)

    station = db.relationship("Station", back_populates="activities")
    shift = db.relationship("Shift", back_populates="activities")
    aircraft = db.relationship("Aircraft", back_populates="activities")
    airline = db.relationship("Airline")
    logged_by = db.relationship("User", back_populates="activities", foreign_keys=[logged_by_id])
    engineer_sent_with = db.relationship("User", foreign_keys=[engineer_sent_with_id])
    crs_engineer = db.relationship("User", foreign_keys=[crs_engineer_id])
    second_engineer = db.relationship("User", foreign_keys=[second_engineer_id])

    qari_entries = db.relationship(
        "QariEntry", back_populates="activity",
        cascade="all, delete-orphan", order_by="QariEntry.id",
    )

    __table_args__ = (
        db.Index("ix_activities_station", "station_id"),
        db.Index("ix_activities_type", "activity_type"),
        db.Index("ix_activities_engineer", "logged_by_id"),
    )

    @property
    def category(self):
        if self.activity_type == ActivityType.MAINTENANCE_CHECK:
            return "maintenance_check"
        if self.activity_type == ActivityType.MIC_SCHEDULED_MAINTENANCE:
            return "mic"
        if self.activity_type == ActivityType.QARI:
            return "quality"
        if self.activity_type == ActivityType.TSR:
            return "tsr"
        if self.activity_type == ActivityType.PIREP_UNSCHEDULED_MAINTENANCE:
            return "pirep_unscheduled"
        if self.activity_type == ActivityType.REPLACEMENT:
            return "replacement"
        if self.activity_type == ActivityType.CF_REMOVAL:
            return "cf_removal"
        if self.activity_type == ActivityType.CF:
            return "cf"
        return "other"

    @property
    def is_editable(self):
        return True

    @property
    def detail_summary(self):
        """A short one-line summary of the activity's key detail."""
        parts = []
        if self.activity_type == ActivityType.REPLACEMENT and self.component:
            parts.append(self.component)
        if self.category in ("maintenance_check", "cf", "cf_removal", "replacement"):
            if self.component:
                parts.append(self.component)
            if self.maintenance_details:
                parts.append(self.maintenance_details)
            if self.category == "cf" and self.inspection_details:
                parts.append(self.inspection_details)
        elif self.category in ("pirep_unscheduled",):
            if self.inspection_result:
                parts.append(self.inspection_result)
            if self.inspection_details:
                parts.append(self.inspection_details)
        elif self.category == "tsr":
            if self.tsr_number:
                parts.append(f"TSR #{self.tsr_number}")
        elif self.category == "mic":
            if self.mic_number:
                parts.append(f"MIC #{self.mic_number}")
        elif self.category == "quality":
            if self.quality_inspection_type:
                parts.append(self.quality_inspection_type)
            if self.quality_finding:
                parts.append(self.quality_finding)
        if not parts and self.remarks:
            parts.append(self.remarks)
        text = " — ".join(p for p in parts if p)
        if not text:
            return "-"
        return text if len(text) <= 90 else text[:87] + "..."

    def __repr__(self):
        return f"<Activity {self.id} {self.activity_type.value if self.activity_type else None}>"


class QariEntry(TimestampMixin, db.Model):
    """One QARI line item on a QARI activity. A single Activity row of
    type QARI may have up to 2 of these (enforced in the form layer)."""

    __tablename__ = "qari_entries"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)

    severity = db.Column(
        db.Enum(
            QariSeverity,
            name="qari_severity",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    # No. of QARI Attempted - a plain numeric count entered by the
    # engineer (e.g. 11), replacing the old free-text "QARI No." field.
    qari_attempted_count = db.Column(db.Integer, nullable=True)
    qari_closed_count = db.Column(db.Integer, nullable=True)
    short_description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum(
            QariEntryStatus,
            name="qari_entry_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )

    activity = db.relationship("Activity", back_populates="qari_entries")

    def __repr__(self):
        return f"<QariEntry activity={self.activity_id} attempted={self.qari_attempted_count}>"
