from datetime import datetime

from ..extensions import db


class Upload(db.Model):
    """
    Represents a privately stored document uploaded by an organization.

    The upload stores physical-file metadata and processing state.
    Extracted financial content is stored separately through
    DocumentExtraction records.
    """

    __tablename__ = "uploads"

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

    original_filename = db.Column(
        db.String(255),
        nullable=False,
    )

    stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )

    file_path = db.Column(
        db.Text,
        nullable=False,
    )

    file_extension = db.Column(
        db.String(20),
        nullable=False,
    )

    mime_type = db.Column(
        db.String(100),
        nullable=True,
    )

    file_size = db.Column(
        db.BigInteger,
        nullable=False,
    )

    file_hash = db.Column(
        db.String(128),
        nullable=False,
        index=True,
    )

    document_type = db.Column(
        db.String(50),
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

    extracted_text_available = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    extraction_method = db.Column(
        db.String(50),
        nullable=True,
    )

    is_encrypted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
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

    organization = db.relationship(
        "Organization",
        back_populates="uploads",
    )

    uploader = db.relationship(
        "User",
        foreign_keys=[uploaded_by],
        back_populates="uploads",
    )

    document_extractions = db.relationship(
        "DocumentExtraction",
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentExtraction.id",
    )

    def __repr__(self):
        return f"<Upload {self.id}: {self.original_filename}>"