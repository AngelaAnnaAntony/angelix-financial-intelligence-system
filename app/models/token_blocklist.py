from datetime import datetime

from ..extensions import db


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    jti = db.Column(
        db.String(36),
        nullable=False,
        unique=True,
        index=True,
    )

    token_type = db.Column(
        db.String(20),
        nullable=False,
    )

    revoked_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self):
        return f"<TokenBlocklist {self.id}: {self.jti}>"