"""
WSGI Application Entry Point for Production Deployment
Compatible with Gunicorn, Waitress, uWSGI, Render, Railway, Heroku, AWS, and Docker.
"""
import os
import sys

# Ensure current directory is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
if not os.path.exists(database.DB_PATH):
    print("Initializing production database...")
    database.init_db()
else:
    database.check_and_migrate_db()

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
