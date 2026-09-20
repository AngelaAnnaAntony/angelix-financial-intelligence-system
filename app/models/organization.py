from datetime import datetime

from ..extensions import db


class Organization(db.Model):
    """
    Represents a business or individual financial organization
    using the Angelix platform.
    """

    __tablename__ = "organizations"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    name = db.Column(
        db.String(255),
        nullable=False,
        index=True,
    )

    organization_type = db.Column(
        db.String(50),
        nullable=False,
    )

    registration_number = db.Column(
        db.String(100),
        nullable=True,
        unique=True,
    )

    tax_identifier = db.Column(
        db.String(100),
        nullable=True,
        unique=True,
    )

    email = db.Column(
        db.String(255),
        nullable=True,
    )

    phone = db.Column(
        db.String(30),
        nullable=True,
    )

    address = db.Column(
        db.Text,
        nullable=True,
    )

    city = db.Column(
        db.String(100),
        nullable=True,
    )

    state = db.Column(
        db.String(100),
        nullable=True,
    )

    country = db.Column(
        db.String(100),
        nullable=True,
    )

    postal_code = db.Column(
        db.String(20),
        nullable=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True,
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

    users = db.relationship(
        "User",
        back_populates="organization",
        lazy=True,
    )

    uploads = db.relationship(
        "Upload",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    transactions = db.relationship(
        "Transaction",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    financial_statements = db.relationship(
        "FinancialStatement",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    financial_statement_line_items = db.relationship(
        "FinancialStatementLineItem",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FinancialStatementLineItem.id",
    )

    reports = db.relationship(
        "Report",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    document_extractions = db.relationship(
        "DocumentExtraction",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentExtraction.id",
    )

    extraction_candidates = db.relationship(
        "ExtractionCandidate",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractionCandidate.id",
    )

    def __repr__(self):
        return f"<Organization {self.id}: {self.name}>"