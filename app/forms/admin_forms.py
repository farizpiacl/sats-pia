from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional, EqualTo, ValidationError

from app.models.user import UserRole
from app.models.shift import ShiftName
from app.models.aircraft import AircraftCategory


class UserForm(FlaskForm):
    employee_id = StringField("Employee ID", validators=[DataRequired(), Length(max=30)])
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    designation = StringField("Designation", validators=[Optional(), Length(max=100)])
    role = SelectField("Role", choices=[(r.value, r.label) for r in UserRole], validators=[DataRequired()])
    station_id = SelectField("Station", coerce=int, validators=[Optional()])
    password = PasswordField(
        "Password",
        validators=[Optional(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save User")


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")


class StationForm(FlaskForm):
    code = StringField("Station Code", validators=[DataRequired(), Length(max=10)])
    name = StringField("Station Name", validators=[DataRequired(), Length(max=150)])
    city = StringField("City", validators=[Optional(), Length(max=100)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Station")


class ShiftForm(FlaskForm):
    name = SelectField("Shift Name", choices=[(s.value, s.label) for s in ShiftName], validators=[DataRequired()])
    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    shift_incharge_id = SelectField("Shift Incharge", coerce=int, validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Shift")


class AircraftForm(FlaskForm):
    registration = StringField("Registration", validators=[DataRequired(), Length(max=20)])
    aircraft_type = StringField("Aircraft Type", validators=[DataRequired(), Length(max=100)])
    airline_id = SelectField("Airline", coerce=int, validators=[DataRequired()])
    category = SelectField("Category", choices=[(c.value, c.label) for c in AircraftCategory], validators=[DataRequired()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Aircraft")

    # Cross-field data-integrity rule: PIA aircraft must be linked to the
    # PIA Airline record, and a "Third Party" aircraft must NOT be linked
    # to PIA - the PIA airline is never valid for a Third Party aircraft,
    # keeping the two groups mutually exclusive in the database (never
    # inferred from the display label, always the real Airline row).
    def validate_airline_id(self, field):
        from app.models.airline import Airline

        airline = Airline.query.get(field.data) if field.data else None
        if not airline:
            return
        # PIA may be stored as "PIA" or "Pakistan International Airlines".
        # Prefer the official IATA/ICAO identifiers so validation does not
        # depend on the display name used in the admin UI.
        name = (airline.name or "").strip().upper()
        iata = (airline.iata_code or "").strip().upper()
        icao = (airline.icao_code or "").strip().upper()
        is_pia_airline = (
            iata == "PK"
            or icao == "PIA"
            or name in {"PIA", "PAKISTAN INTERNATIONAL AIRLINES"}
        )
        category = self.category.data

        if category == AircraftCategory.THIRD_PARTY.value and is_pia_airline:
            raise ValidationError("PIA cannot be selected as the airline for a Third Party aircraft.")
        if category == AircraftCategory.PIA.value and not is_pia_airline:
            raise ValidationError("A PIA-category aircraft must be linked to the PIA airline.")


class AirlineForm(FlaskForm):
    name = StringField("Airline Name", validators=[DataRequired(), Length(max=150)])
    iata_code = StringField("IATA Code", validators=[Optional(), Length(max=5)])
    icao_code = StringField("ICAO Code", validators=[Optional(), Length(max=5)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Airline")


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    description = StringField("Description", validators=[Optional(), Length(max=300)])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save")
