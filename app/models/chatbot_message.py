from datetime import datetime

from ..extensions import db


class ChatbotMessage(db.Model):
    __tablename__ = "chatbot_messages"

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

    session_id = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )

    role = db.Column(
        db.String(20),
        nullable=False,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    response = db.Column(
        db.Text,
        nullable=True,
    )

    model_name = db.Column(
        db.String(150),
        nullable=True,
    )

    tokens_used = db.Column(
        db.Integer,
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
        return f"<ChatbotMessage {self.id}: {self.role}>"