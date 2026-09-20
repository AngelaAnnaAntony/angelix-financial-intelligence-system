from datetime import datetime

from ..extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

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

    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
    )

    def __repr__(self):
        return f"<PasswordResetToken {self.id}>"