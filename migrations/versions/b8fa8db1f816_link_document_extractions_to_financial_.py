"""Link document extractions to financial statements

Revision ID: b8fa8db1f816
Revises: b2a576542367
Create Date: 2026-09-18 12:25:03.060851

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8fa8db1f816"
down_revision = "b2a576542367"
branch_labels = None
depends_on = None


def upgrade():
    """
    Associate document extraction records with their financial statement.
    """

    with op.batch_alter_table(
        "document_extractions",
        schema=None,
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "financial_statement_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_document_extractions_financial_statement_id",
            ["financial_statement_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_document_extractions_financial_statement_id",
            "financial_statements",
            ["financial_statement_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    """
    Remove the financial statement association from document extractions.
    """

    with op.batch_alter_table(
        "document_extractions",
        schema=None,
    ) as batch_op:

        batch_op.drop_constraint(
            "fk_document_extractions_financial_statement_id",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_document_extractions_financial_statement_id",
        )

        batch_op.drop_column(
            "financial_statement_id",
        )