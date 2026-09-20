from datetime import datetime

from ..extensions import db


class FinancialStatement(db.Model):
    """
    Represents a financial statement belonging to an organization.

    A financial statement may contain extracted statement-level line items
    and may also be associated with transactions where applicable.
    """

    __tablename__ = "financial_statements"

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

    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    statement_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    period_type = db.Column(
        db.String(20),
        nullable=False,
        index=True,
    )

    period_start = db.Column(
        db.Date,
        nullable=False,
        index=True,
    )

    period_end = db.Column(
        db.Date,
        nullable=False,
        index=True,
    )

    fiscal_year = db.Column(
        db.Integer,
        nullable=True,
        index=True,
    )

    source_filename = db.Column(
        db.String(255),
        nullable=True,
    )

    source_file_hash = db.Column(
        db.String(128),
        nullable=True,
        index=True,
    )

    processing_status = db.Column(
        db.String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    processing_error = db.Column(
        db.Text,
        nullable=True,
    )

    processed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    total_revenue = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    total_expenses = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    net_profit = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    total_assets = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    total_liabilities = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    total_equity = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    notes = db.Column(
        db.Text,
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
        back_populates="financial_statements",
    )

    uploader = db.relationship(
        "User",
        foreign_keys=[uploaded_by],
    )

    transactions = db.relationship(
        "Transaction",
        back_populates="financial_statement",
    )

    document_extractions = db.relationship(
        "DocumentExtraction",
        back_populates="financial_statement",
        passive_deletes=True,
        order_by="DocumentExtraction.id",
    )

    line_items = db.relationship(
        "FinancialStatementLineItem",
        back_populates="financial_statement",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FinancialStatementLineItem.id",
    )

    def __repr__(self):
        return (
            f"<FinancialStatement "
            f"{self.id}: {self.statement_type}>"
        )