from datetime import datetime

from ..extensions import db


class SystemLog(db.Model):
    __tablename__ = "system_logs"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    level = db.Column(
        db.String(20),
        nullable=False,
        index=True,
    )

    logger_name = db.Column(
        db.String(150),
        nullable=True,
        index=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    exception_type = db.Column(
        db.String(255),
        nullable=True,
    )

    stack_trace = db.Column(
        db.Text,
        nullable=True,
    )

    request_id = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    endpoint = db.Column(
        db.String(255),
        nullable=True,
    )

    method = db.Column(
        db.String(20),
        nullable=True,
    )

    ip_address = db.Column(
        db.String(45),
        nullable=True,
    )

    metadata_json = db.Column(
        db.JSON,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    def __repr__(self):
        return (
            f"<SystemLog {self.id}: "
            f"{self.level}>"
        )