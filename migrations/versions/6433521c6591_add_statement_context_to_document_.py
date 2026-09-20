"""Add statement context to document extractions

Revision ID: 6433521c6591
Revises: b8fa8db1f816
Create Date: 2026-09-18 13:25:33.306666

"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision = "6433521c6591"
down_revision = "b8fa8db1f816"
branch_labels = None
depends_on = None


def upgrade():
    """
    Add statement-level metadata to document extractions.

    These fields allow a reviewer to provide the financial statement
    context extracted from a document without prematurely creating a
    trusted FinancialStatement record.
    """

    with op.batch_alter_table(
        "document_extractions",
        schema=None,
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "statement_type",
                sa.String(length=50),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "period_type",
                sa.String(length=20),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "period_start",
                sa.Date(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "period_end",
                sa.Date(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "fiscal_year",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            batch_op.f(
                "ix_document_extractions_statement_type"
            ),
            ["statement_type"],
            unique=False,
        )

        batch_op.create_index(
            batch_op.f(
                "ix_document_extractions_period_type"
            ),
            ["period_type"],
            unique=False,
        )

        batch_op.create_index(
            batch_op.f(
                "ix_document_extractions_period_start"
            ),
            ["period_start"],
            unique=False,
        )

        batch_op.create_index(
            batch_op.f(
                "ix_document_extractions_period_end"
            ),
            ["period_end"],
            unique=False,
        )

        batch_op.create_index(
            batch_op.f(
                "ix_document_extractions_fiscal_year"
            ),
            ["fiscal_year"],
            unique=False,
        )


def downgrade():
    """
    Remove statement-level metadata from document extractions.
    """

    with op.batch_alter_table(
        "document_extractions",
        schema=None,
    ) as batch_op:

        batch_op.drop_index(
            batch_op.f(
                "ix_document_extractions_fiscal_year"
            )
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_document_extractions_period_end"
            )
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_document_extractions_period_start"
            )
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_document_extractions_period_type"
            )
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_document_extractions_statement_type"
            )
        )

        batch_op.drop_column("fiscal_year")
        batch_op.drop_column("period_end")
        batch_op.drop_column("period_start")
        batch_op.drop_column("period_type")
        batch_op.drop_column("statement_type")