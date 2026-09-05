import enum

from app import db
from app.models.base import TimestampMixin
from app.models.activity import ActivityType


class InspectionCreditType(enum.Enum):
    """What a credit row represents.

    ``INSPECTION`` is the one-per-form credit (1 inspection = 1 inspection,
    no matter how many checklist activities or engineers are involved).
    Every other value mirrors an ``ActivityType`` and is only created for
    checklist rows the engineer marked "Yes".
    """

    INSPECTION = "inspection"

    @classmethod
    def for_activity_type(cls, activity_type_value):
        # Activity-type credits reuse the ActivityType value string directly
        # (e.g. "wheel_change") so reporting can group by it without a
        # second lookup table.
        return activity_type_value


class InspectionForm(TimestampMixin, db.Model):
    """The header record for an Engineer Inspection Form submission.

    One InspectionForm = exactly one inspection event. It owns a checklist
    of InspectionEntry rows (one per activity type, Yes/No + remarks) and
    an InspectionCredit ledger that is fully regenerated (never appended
    to) every time the form is saved, so credits can never be double
    counted no matter how many times the form is edited.
    """

    __tablename__ = "inspection_forms"

    id = db.Column(db.Integer, primary_key=True)

    inspection_date = db.Column(db.Date, nullable=False, index=True)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False, index=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    airline_id = db.Column(db.Integer, db.ForeignKey("airlines.id", ondelete="RESTRICT"), nullable=False, index=True)
    # aircraft_id drives the PIA branch (existing dropdown, FK into the
    # aircraft table). When the selected airline isn't PIA, aircraft_id is
    # left null and the two manual columns below are used instead - mirrors
    # the same PIA/non-PIA split already used on the Engineer Activity Form.
    aircraft_id = db.Column(db.Integer, db.ForeignKey("aircraft.id", ondelete="RESTRICT"), nullable=True, index=True)
    aircraft_registration_manual = db.Column(db.String(20), nullable=True)
    aircraft_model_manual = db.Column(db.String(100), nullable=True)

    primary_engineer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    second_engineer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    overall_remarks = db.Column(db.Text, nullable=True)

    station = db.relationship("Station")
    shift = db.relationship("Shift")
    airline = db.relationship("Airline")
    aircraft = db.relationship("Aircraft")
    primary_engineer = db.relationship("User", foreign_keys=[primary_engineer_id])
    second_engineer = db.relationship("User", foreign_keys=[second_engineer_id])

    entries = db.relationship(
        "InspectionEntry", back_populates="inspection_form",
        cascade="all, delete-orphan", order_by="InspectionEntry.activity_type",
    )
    credits = db.relationship(
        "InspectionCredit", back_populates="inspection_form",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_inspection_forms_station", "station_id"),
        db.Index("ix_inspection_forms_engineer", "primary_engineer_id"),
    )

    @property
    def is_editable(self):
        return True

    @property
    def performed_entries(self):
        return [e for e in self.entries if e.performed]

    @property
    def is_shared(self):
        return self.second_engineer_id is not None

    def rebuild_credits(self):
        """Recompute the full credit ledger for this form from scratch.

        Always replaces (never appends to) `self.credits`, which is what
        guarantees an edit/resubmit can never double-count an inspection
        or an activity credit.
        """
        self.credits = []

        share = 0.5 if self.is_shared else 1.0

        # 1 inspection = 1 inspection, split evenly if a second engineer
        # is on the form.
        self.credits.append(InspectionCredit(
            engineer_id=self.primary_engineer_id,
            credit_type=InspectionCreditType.INSPECTION.value,
            credit_value=share,
        ))
        if self.is_shared:
            self.credits.append(InspectionCredit(
                engineer_id=self.second_engineer_id,
                credit_type=InspectionCreditType.INSPECTION.value,
                credit_value=share,
            ))

        # Every checklist row marked "Yes" earns activity credit under the
        # same shared-credit split.
        for entry in self.performed_entries:
            self.credits.append(InspectionCredit(
                engineer_id=self.primary_engineer_id,
                credit_type=entry.activity_type.value,
                credit_value=share,
            ))
            if self.is_shared:
                self.credits.append(InspectionCredit(
                    engineer_id=self.second_engineer_id,
                    credit_type=entry.activity_type.value,
                    credit_value=share,
                ))

    def __repr__(self):
        return f"<InspectionForm {self.id} {self.inspection_date}>"


class InspectionEntry(TimestampMixin, db.Model):
    """One row of the inspection checklist: a single activity type marked
    Yes/No with its own remarks."""

    __tablename__ = "inspection_entries"

    id = db.Column(db.Integer, primary_key=True)
    inspection_form_id = db.Column(
        db.Integer, db.ForeignKey("inspection_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    activity_type = db.Column(
        db.Enum(
            ActivityType,
            name="activity_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    performed = db.Column(db.Boolean, nullable=False, default=False)  # Yes / No
    remarks = db.Column(db.String(1000), nullable=True)

    inspection_form = db.relationship("InspectionForm", back_populates="entries")

    __table_args__ = (
        db.UniqueConstraint("inspection_form_id", "activity_type", name="uq_inspection_entry_type"),
    )

    def __repr__(self):
        return f"<InspectionEntry form={self.inspection_form_id} {self.activity_type.value if self.activity_type else None}={self.performed}>"


class InspectionCredit(TimestampMixin, db.Model):
    """One line of the credit ledger for an inspection form.

    Fully regenerated by `InspectionForm.rebuild_credits()` on every
    create/edit - rows are never appended to independently, so an
    inspection (or an activity within it) can never be double counted.
    """

    __tablename__ = "inspection_credits"

    id = db.Column(db.Integer, primary_key=True)
    inspection_form_id = db.Column(
        db.Integer, db.ForeignKey("inspection_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engineer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # "inspection" for the one-per-form credit, or an ActivityType value
    # (e.g. "wheel_change") for a Yes-marked checklist activity.
    credit_type = db.Column(db.String(50), nullable=False, index=True)
    credit_value = db.Column(db.Numeric(4, 2), nullable=False)

    inspection_form = db.relationship("InspectionForm", back_populates="credits")
    engineer = db.relationship("User")

    __table_args__ = (
        db.Index("ix_inspection_credits_engineer_type", "engineer_id", "credit_type"),
    )

    def __repr__(self):
        return f"<InspectionCredit form={self.inspection_form_id} engineer={self.engineer_id} {self.credit_type}={self.credit_value}>"
