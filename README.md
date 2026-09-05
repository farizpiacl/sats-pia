# SATS — Station Activity Tracking System

PIA Engineering — Station Activity Tracking System. A full-stack Flask
application for logging, approving, and reporting on Engineer field
activities (aircraft inspections, maintenance, flight coverage, TSR, MIC,
Quality/RI) across stations and shifts.

**Roles.** The system supports exactly four roles: **Super Admin**, **DCE**
(Deputy Chief Engineer), **Shift Incharge**, and **Engineer**. There is no
"Technician" role anywhere in the system.

**No dummy data.** A freshly migrated database contains zero rows in every
table. Nothing is seeded. Every user, station, shift, aircraft, airline,
category, and activity in the system is data that was entered through the
application by a real person.

---

## Stack

- **Backend:** Flask 3, SQLAlchemy 2, Flask-Migrate (Alembic), Flask-Login,
  Flask-WTF (CSRF)
- **Database:** SQLite by default for local development; PostgreSQL in
  production (via `DATABASE_URL`)
- **Frontend:** Server-rendered Jinja2 templates, Bootstrap 5, a Dark
  Green + Gold PIA theme
- **Exports:** `reportlab` (PDF), `openpyxl` (Excel)

---

## 1. Installation

```bash
git clone <your-repo-url> sats
cd sats

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `SECRET_KEY` — a long, random value. **Never use the default value in
  production** — the app will refuse to start in production mode if you do.
  Generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- `DATABASE_URL` — leave empty for local SQLite (`instance/sats.db`), or
  set a PostgreSQL URL for production, e.g.:
  ```
  DATABASE_URL=postgresql://sats_user:sats_password@localhost:5432/sats_db
  ```

Never commit your real `.env` file. It is already listed in `.gitignore`.

## 3. Database setup & migrations

```bash
export FLASK_APP=wsgi.py
export FLASK_ENV=development   # or production

flask db upgrade
```

This creates every table (users, stations, shifts, aircraft, airlines,
activities, notifications, audit_logs, categories) with **no seeded rows**.

If you ever change a model, generate and apply a new migration:

```bash
flask db migrate -m "Describe the change"
flask db upgrade
```

To build a completely fresh database at any time (e.g. for a new
environment), just point `DATABASE_URL` at an empty database and run
`flask db upgrade` — the migrations recreate the full schema from scratch.

## 4. Create the initial Super Admin

There is no default admin account. Create the first one interactively:

```bash
python create_admin.py
```

You'll be prompted for a full name, employee ID, email, and password
(minimum 8 characters, entered twice to confirm). The script refuses to run
if a Super Admin already exists, so it's safe to leave in place.

## 5. Run the application

**Development:**

```bash
export FLASK_APP=wsgi.py
export FLASK_ENV=development
flask run
```

Visit `http://127.0.0.1:5000` and log in with the Super Admin account you
created.

**Production (example with gunicorn):**

```bash
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

Put this behind a reverse proxy (nginx/Apache) that terminates TLS —
`SESSION_COOKIE_SECURE` is enabled automatically in production, so cookies
will not be sent over plain HTTP.

## 6. Testing commands

There is no bundled automated test suite in this repository; the
recommended manual verification path (also how this build was validated)
is:

```bash
# 1. Fresh DB + migrations
rm -f instance/sats.db && flask db upgrade

# 2. Create the Super Admin
python create_admin.py

# 3. Run the app and walk through each role
flask run
```

Then verify, per role:

- **Super Admin** — Users (add/edit/disable/search/filter/reset password),
  Stations, Shifts (Alpha/Beta/Charlie/Delta + assign Shift Incharge),
  Aircraft, Airlines, Activity/Maintenance/TSR/MIC/RI Categories, Audit Logs.
- **Engineer** — Log New Activity → activity is immediately active and
  visible to IS, DCE, and Super Admin, no submission or review step.
- **Shift Incharge** — Shift Monitoring (view-only across their shift(s));
  confirm a Shift Incharge assigned to one shift gets a
  403 if they try to open an activity that belongs to a different shift.
- **DCE** — Dashboard, all report pages (Station/Shift/Engineer/Aircraft/
  Flight/Maintenance/TSR/MIC/RI/Daily/Monthly), and PDF/Excel exports.
- **Permissions** — confirm Engineers get 403 on `/admin/*` and `/dce/*`,
  and that disabled accounts cannot log in.

## 7. Deployment checklist

- [ ] `SECRET_KEY` set to a unique random value in the production
      environment (not the default — the app enforces this).
- [ ] `DATABASE_URL` pointing at a real PostgreSQL instance.
- [ ] `FLASK_ENV=production` set, so `SESSION_COOKIE_SECURE` is enabled.
- [ ] Served over HTTPS (via a reverse proxy in front of gunicorn).
- [ ] `flask db upgrade` run against the production database.
- [ ] Initial Super Admin created with `python create_admin.py`.
- [ ] `.env` is not committed to source control and is not world-readable.
- [ ] Regular database backups configured (PostgreSQL `pg_dump` or your
      hosting provider's backup feature).

---

## Security notes

- Passwords are hashed with Werkzeug's `generate_password_hash`
  (PBKDF2-SHA256 by default) — never stored or logged in plaintext.
- Every state-changing form (create, edit, disable/enable, delete) is
  protected by Flask-WTF CSRF tokens.
- All database access goes through the SQLAlchemy ORM with parameterized
  queries — there is no raw/string-built SQL anywhere in the codebase.
- Jinja2's autoescaping is on everywhere; no template uses the `|safe`
  filter, so user-supplied text is always escaped before rendering.
- Role checks are enforced at the route level (`@roles_required` /
  `@super_admin_required`), and Shift Incharges are additionally scoped to
  only the shifts they lead — verified by both hiding out-of-scope
  activities from lists and returning 403 on direct URL access.
- Every login, logout, create, update, disable/enable, and export action
  is written to the `audit_logs` table, viewable by Super Admin under
  **Audit Logs**.
- Session cookies are `HttpOnly` and `SameSite=Lax` always, and `Secure`
  in production.

## Project structure

```
sats/
├── app/
│   ├── models/        # SQLAlchemy models (User, Station, Shift, Aircraft,
│   │                     Airline, Activity, Notification, AuditLog, Category)
│   ├── routes/         # Blueprints, one per module/role area
│   ├── forms/          # Flask-WTF forms
│   ├── templates/      # Jinja2 templates (Dark Green + Gold theme)
│   ├── static/          # CSS/JS
│   └── utils/          # decorators, audit logging, notifications, exports,
│                          analytics, helpers
├── migrations/         # Alembic migrations (schema only — no data)
├── config.py
├── wsgi.py
├── create_admin.py     # one-time initial Super Admin setup
├── requirements.txt
└── .env.example
```
