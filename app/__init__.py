from pathlib import Path

from flask import Flask, jsonify

from .extensions import (
    db,
    migrate,
    bcrypt,
    login_manager,
    jwt,
    csrf,
)
from .config import load_config


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or load_config())

    for folder in (
        "UPLOAD_FOLDER",
        "GENERATED_REPORT_FOLDER",
        "LOG_FOLDER",
    ):
        Path(app.config[folder]).mkdir(
            parents=True,
            exist_ok=True,
        )

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)

    from .models import User

    from .routes.auth_routes import auth_bp
    from .routes.dashboard_routes import dashboard_bp
    from .routes.upload_routes import upload_bp
    from .routes.transaction_routes import transaction_bp
    from .routes.statement_routes import statement_bp
    from .routes.analytics_routes import analytics_bp
    from .routes.report_routes import report_bp
    from .routes.advisor_routes import advisor_bp
    from .routes.extraction_routes import extraction_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(statement_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(advisor_bp)
    app.register_blueprint(extraction_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, user_id)

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "application": "Angelix",
            }
        )

    return app