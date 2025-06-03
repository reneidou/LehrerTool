# init_db.py - Datenbankinitialisierung
from app import app, db

with app.app_context():
    db.create_all()
    print("Datenbank erfolgreich erstellt!")