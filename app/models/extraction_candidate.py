from datetime import datetime
from decimal import Decimal

from ..extensions import db


class ExtractionCandidate(db.Model):
    """
    Represents an individual financial record extracted from a document.

    Candidates remain separate from trusted Transaction records until a
    user reviews and approves or corrects them.
    """

    __tablename__ = "extraction_candidates"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    extraction_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "document_extractions.id",
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

    transaction_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "transactions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    transaction_date = db.Column(
        db.Date,
        nullable=True,
        index=True,
    )

    description = db.Column(
        db.Text,
        nullable=True,
    )

    reference_number = db.Column(
        db.String(100),
        nullable=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=True,
    )

    debit_credit = db.Column(
        db.String(20),
        nullable=True,
    )

    transaction_type = db.Column(
        db.String(50),
        nullable=True,
    )

    category = db.Column(
        db.String(100),
        nullable=True,
    )

    subcategory = db.Column(
        db.String(100),
        nullable=True,
    )

    confidence_score = db.Column(
        db.Numeric(5, 4),
        nullable=True,
    )

    raw_text = db.Column(
        db.Text,
        nullable=True,
    )

    review_status = db.Column(
        db.String(50),
        nullable=False,
        default="pending_review",
        index=True,
    )

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reviewed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    correction_notes = db.Column(
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

    extraction = db.relationship(
        "DocumentExtraction",
        back_populates="candidates",
    )

    organization = db.relationship(
        "Organization",
        back_populates="extraction_candidates",
    )

    transaction = db.relationship(
        "Transaction",
        back_populates="extraction_candidate",
        foreign_keys=[transaction_id],
    )

    financial_statement_line_item = db.relationship(
        "FinancialStatementLineItem",
        back_populates="extraction_candidate",
        foreign_keys="FinancialStatementLineItem.extraction_candidate_id",
        uselist=False,
    )

    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewed_by],
        back_populates="reviewed_extraction_candidates"
    )

    def __repr__(self):
        return (
            f"<ExtractionCandidate {self.id}: "
            f"{self.description!r} - {self.amount}>"
        )

    @property
    def amount_decimal(self):
        if self.amount is None:
            return Decimal("0.00")

        return Decimal(str(self.amount))

    @property
    def is_reviewed(self):
        return self.review_status in {
            "approved",
            "corrected",
            "rejected",
        }

    @property
    def is_approved(self):
        return self.review_status in {
            "approved",
            "corrected",
        }