from datetime import datetime

from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    action = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )

    description = db.Column(
        db.Text,
        nullable=True,
    )

    resource_type = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    resource_id = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    ip_address = db.Column(
        db.String(45),
        nullable=True,
    )

    user_agent = db.Column(
        db.Text,
        nullable=True,
    )

    request_id = db.Column(
        db.String(100),
        nullable=True,
        index=True,
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

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
    )

    def __repr__(self):
        return (
            f"<AuditLog {self.id}: "
            f"{self.action}>"
        )