from datetime import datetime
from decimal import Decimal

from ..extensions import db


class DocumentExtraction(db.Model):
    """
    Stores the result of processing an uploaded financial document.

    One upload can have multiple extraction records, allowing Angelix
    to preserve processing history and retry failed extraction attempts
    without modifying the original upload record.

    Statement-level metadata is stored at the extraction level because
    multiple candidates extracted from the same document can belong to
    the same financial statement.
    """

    __tablename__ = "document_extractions"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    upload_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "uploads.id",
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

    financial_statement_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "financial_statements.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    statement_type = db.Column(
        db.String(50),
        nullable=True,
        index=True,
    )

    period_type = db.Column(
        db.String(20),
        nullable=True,
        index=True,
    )

    period_start = db.Column(
        db.Date,
        nullable=True,
        index=True,
    )

    period_end = db.Column(
        db.Date,
        nullable=True,
        index=True,
    )

    fiscal_year = db.Column(
        db.Integer,
        nullable=True,
        index=True,
    )

    extracted_text = db.Column(
        db.Text,
        nullable=True,
    )

    document_type = db.Column(
        db.String(50),
        nullable=True,
        index=True,
    )

    extraction_method = db.Column(
        db.String(50),
        nullable=False,
    )

    processing_status = db.Column(
        db.String(50),
        nullable=False,
        default="completed",
        index=True,
    )

    confidence_score = db.Column(
        db.Numeric(5, 4),
        nullable=True,
    )

    processing_error = db.Column(
        db.Text,
        nullable=True,
    )

    processed_at = db.Column(
        db.DateTime(timezone=True),
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

    upload = db.relationship(
        "Upload",
        back_populates="document_extractions",
    )

    organization = db.relationship(
        "Organization",
        back_populates="document_extractions",
    )

    financial_statement = db.relationship(
        "FinancialStatement",
        back_populates="document_extractions",
    )

    candidates = db.relationship(
        "ExtractionCandidate",
        back_populates="extraction",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractionCandidate.id",
    )

    def __repr__(self):
        return (
            f"<DocumentExtraction {self.id}: "
            f"upload={self.upload_id}, "
            f"status={self.processing_status}>"
        )

    @property
    def confidence_decimal(self):
        if self.confidence_score is None:
            return None

        return Decimal(str(self.confidence_score))