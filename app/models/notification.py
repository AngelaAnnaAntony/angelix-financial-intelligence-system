from datetime import datetime

from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    notification_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(255),
        nullable=False,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    resource_type = db.Column(
        db.String(100),
        nullable=True,
    )

    resource_id = db.Column(
        db.String(100),
        nullable=True,
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    read_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    priority = db.Column(
        db.String(20),
        nullable=False,
        default="normal",
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

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
    )

    def __repr__(self):
        return f"<Notification {self.id}: {self.title}>"