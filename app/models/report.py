from datetime import datetime

from ..extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    generated_by = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    title = db.Column(
        db.String(255),
        nullable=False,
    )

    report_type = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )

    period_start = db.Column(
        db.Date,
        nullable=True,
    )

    period_end = db.Column(
        db.Date,
        nullable=True,
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    generation_error = db.Column(
        db.Text,
        nullable=True,
    )

    generated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    summary = db.Column(
        db.Text,
        nullable=True,
    )

    analysis_content = db.Column(
        db.JSON,
        nullable=True,
    )

    recommendations = db.Column(
        db.JSON,
        nullable=True,
    )

    file_path = db.Column(
        db.Text,
        nullable=True,
    )

    file_format = db.Column(
        db.String(20),
        nullable=True,
    )

    file_hash = db.Column(
        db.String(128),
        nullable=True,
    )

    ai_generated = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    ai_model = db.Column(
        db.String(150),
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

    organization = db.relationship(
        "Organization",
        back_populates="reports",
    )

    generated_by_user = db.relationship(
        "User",
        foreign_keys=[generated_by],
    )

    def __repr__(self):
        return f"<Report {self.id}: {self.title}>"