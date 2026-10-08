import os
from flask import Flask
from dotenv import load_dotenv

from .extensions import db, login_manager, migrate
from sqlalchemy import inspect, text

load_dotenv()

def ensure_legacy_schema():
    additions={"attendance_session":{"room":"VARCHAR(100)"},"fee_record":{"last_paid_date":"DATE","installment_count":"INTEGER DEFAULT 0","installments_paid":"INTEGER DEFAULT 0","installment_amount":"FLOAT DEFAULT 0"},"complaint":{"category":"VARCHAR(100) DEFAULT 'OTHER'","department":"VARCHAR(120)","routed_to":"VARCHAR(100) DEFAULT 'HOD + PRINCIPAL'","hod_notified":"BOOLEAN DEFAULT FALSE","principal_notified":"BOOLEAN DEFAULT FALSE"}}
    inspector=inspect(db.engine)
    for table,cols in additions.items():
        if not inspector.has_table(table): continue
        existing={c["name"] for c in inspector.get_columns(table)}
        for name,definition in cols.items():
            if name not in existing: db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    db.session.commit()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///smart_campus.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    # Import models before create_all so newly added tables (including OTPChallenge) exist in existing local databases.
    from . import models  # noqa: F401
    with app.app_context():
        db.create_all()
        ensure_legacy_schema()

    from .auth import auth_bp
    from .main import main_bp
    from .api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
