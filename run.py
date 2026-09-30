from app import create_app
from app.extensions import db

app = create_app()

# The project currently ships without generated Alembic revision files.
# For a fresh production database, create the schema on first boot.
with app.app_context():
    db.create_all()
