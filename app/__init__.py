import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from dotenv import load_dotenv

# Load the .env file that lives beside wsgi.py in the project root,
# regardless of the process's current working directory (e.g. when the
# app is started via `gunicorn wsgi:app` from a different cwd, or by a
# process manager/systemd unit with its own working directory).
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"))

from config import config_by_name

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    if config_name == "production" and app.config["SECRET_KEY"] == "dev-key-change-me-in-production":
        raise RuntimeError(
            "Refusing to start in production with the default SECRET_KEY. "
            "Set a unique, random SECRET_KEY in your environment (see .env.example)."
        )

    if config_name == "production" and not os.environ.get("DATABASE_URL", "").strip():
        raise RuntimeError(
            "Refusing to start in production without DATABASE_URL set. "
            "Production must point at PostgreSQL/Neon -- without it the app "
            "would silently fall back to an empty local SQLite database. "
            "Set DATABASE_URL in your environment (see .env.example)."
        )

    # Ensure instance folder exists (used for SQLite fallback DB)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # --- Models must be imported so Flask-Migrate can detect them ---
    from app.models import user, station, shift, aircraft, airline, activity, notification, audit_log, category, inspection, flight_coverage  # noqa

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin_users import admin_users_bp
    from app.routes.admin_stations import admin_stations_bp
    from app.routes.admin_shifts import admin_shifts_bp
    from app.routes.admin_aircraft import admin_aircraft_bp
    from app.routes.admin_airlines import admin_airlines_bp
    from app.routes.admin_categories import admin_categories_bp
    from app.routes.admin_audit import admin_audit_bp
    from app.routes.admin_menu import admin_menu_bp
    from app.routes.notifications import notifications_bp
    from app.routes.engineer import engineer_bp
    from app.routes.shift_incharge import shift_incharge_bp
    from app.routes.dce import dce_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_stations_bp)
    app.register_blueprint(admin_shifts_bp)
    app.register_blueprint(admin_aircraft_bp)
    app.register_blueprint(admin_airlines_bp)
    app.register_blueprint(admin_categories_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(admin_menu_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(engineer_bp)
    app.register_blueprint(shift_incharge_bp)
    app.register_blueprint(dce_bp)

    # --- Error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # --- Template context / filters ---
    from app.utils.helpers import register_template_helpers
    register_template_helpers(app)

    return app
