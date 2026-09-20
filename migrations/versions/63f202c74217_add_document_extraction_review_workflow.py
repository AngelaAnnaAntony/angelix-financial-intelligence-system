"""Add document extraction review workflow

Revision ID: 63f202c74217
Revises: 2ae043b07424
Create Date: 2026-09-17 22:06:07.802830

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "63f202c74217"
down_revision = "2ae043b07424"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_extractions",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "upload_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "extracted_text",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "document_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "extraction_method",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column(
            "processing_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_document_extractions_created_at",
        "document_extractions",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_document_extractions_document_type",
        "document_extractions",
        ["document_type"],
        unique=False,
    )

    op.create_index(
        "ix_document_extractions_organization_id",
        "document_extractions",
        ["organization_id"],
        unique=False,
    )

    op.create_index(
        "ix_document_extractions_processing_status",
        "document_extractions",
        ["processing_status"],
        unique=False,
    )

    op.create_index(
        "ix_document_extractions_upload_id",
        "document_extractions",
        ["upload_id"],
        unique=False,
    )

    op.create_table(
        "extraction_candidates",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "extraction_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "transaction_date",
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "reference_number",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column(
            "debit_credit",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "transaction_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "category",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "subcategory",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column(
            "raw_text",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "review_status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "correction_notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["document_extractions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_extraction_candidates_created_at",
        "extraction_candidates",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_extraction_id",
        "extraction_candidates",
        ["extraction_id"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_organization_id",
        "extraction_candidates",
        ["organization_id"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_review_status",
        "extraction_candidates",
        ["review_status"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_reviewed_by",
        "extraction_candidates",
        ["reviewed_by"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_transaction_date",
        "extraction_candidates",
        ["transaction_date"],
        unique=False,
    )

    op.create_index(
        "ix_extraction_candidates_transaction_id",
        "extraction_candidates",
        ["transaction_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_extraction_candidates_transaction_id",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_transaction_date",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_reviewed_by",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_review_status",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_organization_id",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_extraction_id",
        table_name="extraction_candidates",
    )

    op.drop_index(
        "ix_extraction_candidates_created_at",
        table_name="extraction_candidates",
    )

    op.drop_table("extraction_candidates")

    op.drop_index(
        "ix_document_extractions_upload_id",
        table_name="document_extractions",
    )

    op.drop_index(
        "ix_document_extractions_processing_status",
        table_name="document_extractions",
    )

    op.drop_index(
        "ix_document_extractions_organization_id",
        table_name="document_extractions",
    )

    op.drop_index(
        "ix_document_extractions_document_type",
        table_name="document_extractions",
    )

    op.drop_index(
        "ix_document_extractions_created_at",
        table_name="document_extractions",
    )

    op.drop_table("document_extractions")