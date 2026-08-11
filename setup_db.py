"""Create any missing database tables from the SQLAlchemy models.

Usage:
    python setup_db.py
"""
from PolicyEdge import app, db, Agenda, User, County, City, Meeting, GeoLocation


with app.app_context():
    db.create_all()
    print("Database check complete. Existing tables:",
          sorted(db.engine.table_names()))