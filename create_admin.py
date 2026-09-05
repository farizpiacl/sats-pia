"""Secure initial-admin setup script for SATS.

Run this once, after running migrations, to create the very first
Super Admin account. It never seeds any other data.

Usage:
    python create_admin.py
"""
import getpass
import re
import sys

from app import create_app, db
from app.models.user import User, UserRole

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def prompt_nonempty(label):
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print("  This field is required. Please try again.")


def prompt_email():
    while True:
        value = input("Email: ").strip().lower()
        if EMAIL_RE.match(value):
            return value
        print("  Please enter a valid email address.")


def prompt_password():
    while True:
        pwd = getpass.getpass("Password (min 8 characters): ")
        if len(pwd) < 8:
            print("  Password must be at least 8 characters.")
            continue
        confirm = getpass.getpass("Confirm Password: ")
        if pwd != confirm:
            print("  Passwords do not match. Please try again.")
            continue
        return pwd


def main():
    app = create_app()
    with app.app_context():
        existing_admin = User.query.filter_by(role=UserRole.SUPER_ADMIN).first()
        if existing_admin:
            print(
                f"A Super Admin already exists: {existing_admin.full_name} "
                f"({existing_admin.employee_id}). Aborting."
            )
            sys.exit(1)

        print("=" * 60)
        print(" SATS — Initial Super Admin Setup")
        print(" PIA Engineering — Station Activity Tracking System")
        print("=" * 60)

        full_name = prompt_nonempty("Full Name")
        employee_id = prompt_nonempty("Employee ID")

        if User.query.filter_by(employee_id=employee_id).first():
            print(f"  An account with Employee ID '{employee_id}' already exists. Aborting.")
            sys.exit(1)

        email = prompt_email()
        if User.query.filter_by(email=email).first():
            print(f"  An account with email '{email}' already exists. Aborting.")
            sys.exit(1)

        password = prompt_password()

        admin = User(
            employee_id=employee_id,
            full_name=full_name,
            email=email,
            role=UserRole.SUPER_ADMIN,
            is_active_flag=True,
        )
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        print("-" * 60)
        print(f"Super Admin '{full_name}' ({employee_id}) created successfully.")
        print("You can now log in at /login")
        print("-" * 60)


if __name__ == "__main__":
    main()
