"""WSGI entry point for the Station Activity Tracking System (SATS).

Local development:
    flask run
`
Production (example with gunicorn):
    gunicorn wsgi:app
"""
import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
