from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, IntegerField, TextAreaField, DateField,
    TimeField, BooleanField, SubmitField, FormField, FieldList,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError

from app.models.activity import (
    ActivityType, MaintenanceType, MaintenanceStatus, TsrMicStatus, QualityStatus,
    CoverageType, MaintenanceCheckType, QariSeverity, QariEntryStatus,
)

# TSR statuses shown to the engineer are relabelled to match the new form's
# wording (Closed / Partially Closed) without touching the underlying
# TsrMicStatus enum/DB values (CLOSED / IN_PROGRESS) that reports already
# rely on.
TSR_STATUS_CHOICES = [
    ("", "-- Select --"),
    (TsrMicStatus.CLOSED.value, "Closed"),
    (TsrMicStatus.IN_PROGRESS.value, "Partially Closed"),
]

# PIREP status is a UI-only concept: "Rectification" (formerly labelled
# "Closed", then "Rectification Prompt") keeps the activity as PIREP /
# Unscheduled Maintenance; "CF" re-files the very same activity under the
# existing ActivityType.CF value (existing system logic for carry-forward),
# so no new enum value is introduced. The stored value is still
# "rectification_prompt" (unchanged DB/data value) - only the label shown
# to users has been renamed to "Rectification".
PIREP_STATUS_CHOICES = [
    ("", "-- Select --"),
    ("rectification_prompt", "Rectification"),
    ("cf", "CF Added"),
]

YES_NO_CHOICES = [("", "-- Select --"), ("yes", "Yes"), ("no", "No")]


class QariEntryForm(FlaskForm):
    """One QARI line item. Up to 2 may be attached to a single QARI
    activity (enforced server-side in the route)."""

    class Meta:
        # Sub-forms in a FieldList must not each render their own CSRF
        # token/field - the parent ActivityForm already carries one.
        csrf = False

    severity = SelectField(
        "Significant / Minor",
        choices=[(s.value, s.label) for s in QariSeverity],
        validators=[Optional()],
    )
    qari_attempted_count = IntegerField("No. of QARI Attempted", validators=[Optional(), NumberRange(min=0)])
    qari_closed_count = IntegerField("No. of QARI Closed", validators=[Optional(), NumberRange(min=0)])
    short_description = TextAreaField("Short Description", validators=[Optional(), Length(max=2000)])
    status = SelectField(
        "Status",
        choices=[("", "-- Select --")] + [(s.value, s.label) for s in QariEntryStatus],
        validators=[Optional()],
    )


class FlightCoverageForm(FlaskForm):
    """Quick-add form for the dedicated Flight Coverage action: just the
    Station and what was performed during the coverage. Engineer + Date/
    Time are set automatically by the route (logged-in user / now)."""

    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    activity_performed = TextAreaField(
        "Activity Performed", validators=[DataRequired(), Length(max=4000)]
    )
    submit = SubmitField("Save Flight Coverage")


class ActivityForm(FlaskForm):
    # --- Basic Information ---
    activity_date = DateField("Date", validators=[DataRequired()])
    shift_id = SelectField("Shift", coerce=int, validators=[Optional()])
    # Station is no longer shown/collected on the form - Lahore is the
    # fixed default (see engineer.py's `_inspection_station()`), but the
    # field is kept so the existing station_id column keeps being set the
    # same way it always has been.
    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    engineer_id = SelectField("Aircraft Engineer", coerce=int, validators=[Optional()])

    airline_id = SelectField("Airline", coerce=int, validators=[DataRequired()])
    aircraft_id = SelectField("Aircraft Registration", coerce=int, validators=[Optional()])
    # Non-PIA airlines: registration is entered manually (free text) and
    # the model is picked from a fixed dropdown (see aircraft_model_manual
    # below) rather than being sourced from the Aircraft table. Both are
    # stored in the pre-existing aircraft_registration_manual /
    # aircraft_model_manual columns, so no database change is needed.
    aircraft_registration_manual = StringField("Aircraft Registration", validators=[Optional(), Length(max=20)])
    aircraft_model_manual = SelectField("Aircraft / Plane Model", choices=[], validators=[Optional(), Length(max=100)])

    flight_number = StringField("Flight No.", validators=[Optional(), Length(max=20)])
    coverage_type = SelectField(
        "Coverage Type",
        choices=[("", "-- Select --")] + [(c.value, c.label) for c in CoverageType],
        validators=[DataRequired()],
    )
    # Manual free-text entry (no dropdown / hardcoded station list) shown
    # only when Coverage Type = Flight.
    destination_station = StringField("Destination Station", validators=[Optional(), Length(max=150)])

    activity_type = SelectField(
        "Activity",
        choices=[(t.value, t.label) for t in ActivityType if t != ActivityType.CF],
        validators=[DataRequired()],
    )

    # --- Compulsory for every activity, regardless of type ---
    remarks = TextAreaField(
        "Remarks", validators=[DataRequired(message="Remarks are required."), Length(max=2000)]
    )

    # --- Maintenance Check ---
    maintenance_check_type = SelectField(
        "Type",
        choices=[("", "-- Select --")] + [(t.value, t.label) for t in MaintenanceCheckType],
        validators=[Optional()],
    )
    mc_details = TextAreaField("Details", validators=[Optional(), Length(max=4000)])
    is_crs = SelectField("CRS?", choices=YES_NO_CHOICES, validators=[Optional()])
    crs_engineer_id = SelectField("CRS Aircraft Engineer", coerce=int, validators=[Optional()])
    second_engineer_id = SelectField("Second Aircraft Engineer", coerce=int, validators=[Optional()])

    # --- MIC / Scheduled Maintenance ---
    mic_type = StringField("Type", validators=[Optional(), Length(max=150)])
    mic_description = TextAreaField("Description", validators=[Optional(), Length(max=4000)])

    # --- QARI (up to 2 entries) ---
    qari_entries = FieldList(FormField(QariEntryForm), min_entries=1, max_entries=2)

    # --- TSR ---
    tsr_number = StringField("TSR No.", validators=[Optional(), Length(max=50)])
    tsr_status = SelectField("Status", choices=TSR_STATUS_CHOICES, validators=[Optional()])
    tsr_description = TextAreaField("Description", validators=[Optional(), Length(max=4000)])

    # --- PIREP / Unscheduled Maintenance ---
    pirep_short_description = TextAreaField("Short Description", validators=[Optional(), Length(max=2000)])
    pirep_status = SelectField("Status", choices=PIREP_STATUS_CHOICES, validators=[Optional()])

    # --- CF Removal ---
    cf_removed = SelectField("Removed?", choices=YES_NO_CHOICES, validators=[Optional()])
    cf_removal_details = TextAreaField("Details", validators=[Optional(), Length(max=4000)])

    # --- Removal/Installation ---
    replacement_component = StringField("Equipment/Component", validators=[Optional(), Length(max=150)])
    replacement_details = TextAreaField("Details", validators=[Optional(), Length(max=4000)])

    submit = SubmitField("Add Activity")

    # Maps each activity type to the form field that holds its
    # "Activity Details/Description" so validate() can enforce it
    # generically. QARI is intentionally excluded here - it already
    # enforces "at least one QARI entry" below, which serves the same
    # "details are compulsory" purpose for that activity type.
    DETAIL_FIELD_BY_TYPE = {
        ActivityType.MAINTENANCE_CHECK.value: "mc_details",
        ActivityType.MIC_SCHEDULED_MAINTENANCE.value: "mic_description",
        ActivityType.TSR.value: "tsr_description",
        ActivityType.PIREP_UNSCHEDULED_MAINTENANCE.value: "pirep_short_description",
        ActivityType.CF_REMOVAL.value: "cf_removal_details",
        ActivityType.REPLACEMENT.value: "replacement_details",
    }

    # ---- Cross-field validation, scoped to whichever activity is selected ----
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        ok = True
        at = self.activity_type.data
        is_pia = self._is_pia_selected()

        if self.coverage_type.data == CoverageType.FLIGHT.value:
            if not (self.destination_station.data or "").strip():
                self.destination_station.errors.append("Destination station is required for Flight Coverage.")
                ok = False

        if is_pia:
            if not self.aircraft_id.data:
                self.aircraft_id.errors.append("Select an aircraft registration.")
                ok = False
        else:
            # Non-PIA: registration is entered manually and the model is
            # picked from the fixed dropdown - both are compulsory.
            if not (self.aircraft_registration_manual.data or "").strip():
                self.aircraft_registration_manual.errors.append("Aircraft registration is required.")
                ok = False
            if not (self.aircraft_model_manual.data or "").strip():
                self.aircraft_model_manual.errors.append("Select an aircraft/plane model.")
                ok = False

        detail_field_name = self.DETAIL_FIELD_BY_TYPE.get(at)
        if detail_field_name:
            detail_field = getattr(self, detail_field_name)
            if not (detail_field.data or "").strip():
                detail_field.errors.append("Activity Details/Description is required.")
                ok = False

        if at == ActivityType.MAINTENANCE_CHECK.value:
            if not self.is_crs.data:
                self.is_crs.errors.append("Please specify whether this engineer is CRS.")
                ok = False
            elif self.is_crs.data == "no" and not self.crs_engineer_id.data:
                self.crs_engineer_id.errors.append("Select the CRS engineer.")
                ok = False

        if at == ActivityType.QARI.value:
            filled = [
                e for e in self.qari_entries
                if e.form.qari_attempted_count.data is not None or (e.form.short_description.data or "").strip()
            ]
            if not filled:
                self.qari_entries.errors.append("Add at least one QARI entry.")
                ok = False

        return ok

    def _is_pia_selected(self):
        from app.models.airline import Airline
        if not self.airline_id.data:
            return False
        airline = Airline.query.get(self.airline_id.data)
        return bool(airline and airline.name.strip().upper() == "PIA")


# Activity choices for the Engineer Inspection Form's single Activity
# dropdown. Values map directly onto the existing ActivityType enum so no
# database/model changes are needed.
INSPECTION_ACTIVITY_CHOICES = [(t.value, t.label) for t in ActivityType]


class InspectionFormForm(FlaskForm):
    """The Engineer Inspection Form: date/station/shift/airline/aircraft,
    a single Activity dropdown, a Remarks textarea, and an optional second
    (shared-credit) engineer."""

    inspection_date = DateField("Date", validators=[DataRequired()])
    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    shift_id = SelectField("Shift", coerce=int, validators=[Optional()])
    airline_id = SelectField("Airline", coerce=int, validators=[DataRequired()])
    aircraft_id = SelectField("Aircraft Registration No.", coerce=int, validators=[Optional()])
    aircraft_registration_manual = StringField("Aircraft Registration", validators=[Optional(), Length(max=20)])
    # Non-PIA: Aircraft Model is picked from a dropdown (never typed
    # manually) sourced from the same Superadmin-managed Aircraft table
    # used by the Engineer Activity Form - see _populate_inspection_choices
    # in app/routes/engineer.py. Value is still stored in the pre-existing
    # `aircraft_model_manual` column, so no database change is needed.
    aircraft_model_manual = SelectField("Aircraft Model", choices=[], validators=[Optional(), Length(max=100)])

    primary_engineer_id = SelectField("Aircraft Engineer", coerce=int, validators=[Optional()])
    second_engineer_id = SelectField("Second Aircraft Engineer", coerce=int, validators=[Optional()])

    activity_type = SelectField(
        "Activity",
        choices=INSPECTION_ACTIVITY_CHOICES,
        validators=[DataRequired()],
    )
    overall_remarks = TextAreaField("Remarks", validators=[Optional(), Length(max=4000)])

    submit = SubmitField("Save Inspection")

    def validate_second_engineer_id(self, field):
        if field.data and self.primary_engineer_id.data and field.data == self.primary_engineer_id.data:
            raise ValidationError("Second engineer must be different from the primary engineer.")

    def _is_pia_selected(self):
        from app.models.airline import Airline
        if not self.airline_id.data:
            return False
        airline = Airline.query.get(self.airline_id.data)
        return bool(airline and airline.name.strip().upper() == "PIA")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        ok = True
        if self._is_pia_selected():
            if not self.aircraft_id.data:
                self.aircraft_id.errors.append("Select an aircraft registration.")
                ok = False
        else:
            if not (self.aircraft_registration_manual.data or "").strip():
                self.aircraft_registration_manual.errors.append("Aircraft registration is required.")
                ok = False
            if not (self.aircraft_model_manual.data or "").strip():
                self.aircraft_model_manual.errors.append("Select an aircraft model.")
                ok = False

        return ok



