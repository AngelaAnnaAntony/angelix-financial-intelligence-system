from datetime import datetime
from decimal import Decimal

from ..extensions import db


class Transaction(db.Model):
    """
    Represents a trusted financial transaction belonging to an organization.

    Transactions may originate from manual entry, OCR/document extraction,
    CSV/Excel imports, or AI-assisted processing. Extracted candidates remain
    separate until they are reviewed and converted into a transaction.
    """

    __tablename__ = "transactions"

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

    financial_statement_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "financial_statements.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    transaction_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
    )

    description = db.Column(
        db.Text,
        nullable=False,
    )

    reference_number = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    transaction_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    category = db.Column(
        db.String(100),
        nullable=True,
        index=True,
    )

    subcategory = db.Column(
        db.String(100),
        nullable=True,
    )

    source = db.Column(
        db.String(50),
        nullable=True,
    )

    is_recurring = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    confidence_score = db.Column(
        db.Numeric(5, 4),
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
        back_populates="transactions",
    )

    financial_statement = db.relationship(
        "FinancialStatement",
        back_populates="transactions",
    )

    extraction_candidate = db.relationship(
        "ExtractionCandidate",
        back_populates="transaction",
        foreign_keys="ExtractionCandidate.transaction_id",
        uselist=False,
    )

    def __repr__(self):
        return (
            f"<Transaction {self.id}: "
            f"{self.description} - {self.amount}>"
        )

    @property
    def amount_decimal(self):
        if self.amount is None:
            return Decimal("0.00")

        return Decimal(str(self.amount))