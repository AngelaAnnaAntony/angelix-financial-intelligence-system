from datetime import datetime

from ..extensions import db


class FinancialStatementLineItem(db.Model):
    """
    Stores an individual account/line item belonging to a financial
    statement.

    Examples:
        Cash and Cash Equivalents
        Accounts Receivable
        Inventory
        Accounts Payable
        Common Stock
        Retained Earnings

    These are statement-level account balances and should not be treated
    as individual financial transactions.
    """

    __tablename__ = "financial_statement_line_items"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    financial_statement_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "financial_statements.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    line_item_name = db.Column(
        db.String(255),
        nullable=False,
    )

    normalized_name = db.Column(
        db.String(255),
        nullable=True,
        index=True,
    )

    section = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    account_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    source_description = db.Column(
        db.Text,
        nullable=True,
    )

    extraction_candidate_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "extraction_candidates.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    confidence_score = db.Column(
        db.Numeric(5, 4),
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

    financial_statement = db.relationship(
        "FinancialStatement",
        back_populates="line_items",
    )

    organization = db.relationship(
        "Organization",
        back_populates="financial_statement_line_items",
    )

    extraction_candidate = db.relationship(
        "ExtractionCandidate",
        back_populates="financial_statement_line_item",
        foreign_keys=[extraction_candidate_id],
        uselist=False,
    )

    def __repr__(self):
        return (
            f"<FinancialStatementLineItem "
            f"{self.id}: {self.line_item_name} "
            f"{self.amount}>"
        )