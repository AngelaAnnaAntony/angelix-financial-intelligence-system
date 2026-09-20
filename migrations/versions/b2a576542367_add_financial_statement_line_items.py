"""Add financial statement line items

Revision ID: b2a576542367
Revises: 63f202c74217
Create Date: 2026-09-18 11:34:49.348207

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2a576542367"
down_revision = "63f202c74217"
branch_labels = None
depends_on = None


def upgrade():
    # Create the financial statement line-item table.
    op.create_table(
        "financial_statement_line_items",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "financial_statement_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "line_item_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "normalized_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "section",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "account_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column(
            "source_description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "extraction_candidate_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=5, scale=4),
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
            ["extraction_candidate_id"],
            ["extraction_candidates.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["financial_statement_id"],
            ["financial_statements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes required by the FinancialStatementLineItem model.
    with op.batch_alter_table(
        "financial_statement_line_items",
        schema=None,
    ) as batch_op:
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_account_type"
            ),
            ["account_type"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_created_at"
            ),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_extraction_candidate_id"
            ),
            ["extraction_candidate_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_financial_statement_id"
            ),
            ["financial_statement_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_normalized_name"
            ),
            ["normalized_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_organization_id"
            ),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_financial_statement_line_items_section"
            ),
            ["section"],
            unique=False,
        )


def downgrade():
    # Remove indexes and table created by this migration.
    with op.batch_alter_table(
        "financial_statement_line_items",
        schema=None,
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_section"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_organization_id"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_normalized_name"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_financial_statement_id"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_extraction_candidate_id"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_created_at"
            )
        )
        batch_op.drop_index(
            batch_op.f(
                "ix_financial_statement_line_items_account_type"
            )
        )

    op.drop_table("financial_statement_line_items")