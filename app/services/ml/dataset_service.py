"""
ANGELIX - Financial ML Dataset Service

Provides organization-isolated transaction datasets for the machine
learning subsystem.

Responsibilities:
- Load transactions from PostgreSQL through SQLAlchemy
- Convert ORM records into DataFrames
- Preserve the original transaction_type values
- Normalize income/expense reporting for ML metadata
- Provide training and prediction datasets
- Prevent cross-organization data leakage
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy import and_

from app.extensions import db
from app.models.transaction import Transaction


# ---------------------------------------------------------------------------
# Dataset result
# ---------------------------------------------------------------------------

@dataclass
class DatasetResult:
    """
    Result returned by the financial dataset service.
    """

    success: bool
    status: str
    message: str
    features: pd.DataFrame
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Financial Dataset Service
# ---------------------------------------------------------------------------

class FinancialDatasetService:
    """
    Loads and prepares transaction data for the Angelix ML subsystem.

    All queries are organization-scoped to prevent cross-organization
    data leakage.
    """

    EXPECTED_COLUMNS = [
        "id",
        "organization_id",
        "financial_statement_id",
        "transaction_date",
        "description",
        "reference_number",
        "amount",
        "transaction_type",
        "category",
        "subcategory",
        "source",
        "is_recurring",
        "confidence_score",
    ]

    INCOME_TYPES = {
        "income",
        "credit",
        "revenue",
    }

    EXPENSE_TYPES = {
        "expense",
        "debit",
        "cost",
    }

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_training_dataset(
        self,
        organization_id: int,
        start_date: Optional[date | datetime] = None,
        end_date: Optional[date | datetime] = None,
    ) -> DatasetResult:
        """
        Build a transaction dataset for model training.
        """

        dataframe = self._load_transactions(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        if dataframe.empty:
            return DatasetResult(
                success=False,
                status="empty",
                message="No transactions were found for the organization.",
                features=pd.DataFrame(),
                metadata={
                    "organization_id": organization_id,
                    "total_transactions": 0,
                },
            )

        metadata = self._build_metadata(dataframe)

        return DatasetResult(
            success=True,
            status="success",
            message="Financial training dataset created successfully.",
            features=dataframe,
            metadata=metadata,
        )

    # ------------------------------------------------------------------

    def build_prediction_dataset(
        self,
        organization_id: int,
        start_date: Optional[date | datetime] = None,
        end_date: Optional[date | datetime] = None,
    ) -> DatasetResult:
        """
        Build a transaction dataset for model prediction.
        """

        dataframe = self._load_transactions(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        if dataframe.empty:
            return DatasetResult(
                success=False,
                status="empty",
                message="No transactions were found for prediction.",
                features=pd.DataFrame(),
                metadata={
                    "organization_id": organization_id,
                    "total_transactions": 0,
                },
            )

        metadata = self._build_metadata(dataframe)

        return DatasetResult(
            success=True,
            status="success",
            message="Financial prediction dataset created successfully.",
            features=dataframe,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Database loading
    # ------------------------------------------------------------------

    def _load_transactions(
        self,
        organization_id: int,
        start_date: Optional[date | datetime] = None,
        end_date: Optional[date | datetime] = None,
    ) -> pd.DataFrame:
        """
        Load organization-scoped transactions from PostgreSQL.
        """

        query = Transaction.query.filter(
            Transaction.organization_id == int(organization_id)
        )

        if start_date is not None:
            query = query.filter(
                Transaction.transaction_date >= start_date
            )

        if end_date is not None:
            query = query.filter(
                Transaction.transaction_date <= end_date
            )

        transactions = query.order_by(
            Transaction.transaction_date.asc(),
            Transaction.id.asc(),
        ).all()

        rows: list[dict[str, Any]] = []

        for transaction in transactions:
            rows.append(
                {
                    "id": transaction.id,
                    "organization_id": transaction.organization_id,
                    "financial_statement_id": (
                        transaction.financial_statement_id
                    ),
                    "transaction_date": transaction.transaction_date,
                    "description": transaction.description,
                    "reference_number": transaction.reference_number,
                    "amount": transaction.amount,
                    "transaction_type": transaction.transaction_type,
                    "category": transaction.category,
                    "subcategory": transaction.subcategory,
                    "source": transaction.source,
                    "is_recurring": transaction.is_recurring,
                    "confidence_score": transaction.confidence_score,
                }
            )

        dataframe = pd.DataFrame(rows)

        if dataframe.empty:
            return pd.DataFrame(columns=self.EXPECTED_COLUMNS)

        for column in self.EXPECTED_COLUMNS:
            if column not in dataframe.columns:
                dataframe[column] = None

        dataframe = dataframe[self.EXPECTED_COLUMNS]

        return dataframe

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _build_metadata(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Build transparent dataset metadata.

        The original transaction_type values are preserved.

        For reporting purposes:
            credit/income/revenue -> income-like
            debit/expense/cost     -> expense-like
        """

        total_transactions = int(len(dataframe))

        transaction_types = (
            dataframe["transaction_type"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        categories = (
            dataframe["category"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        income_mask = transaction_types.isin(self.INCOME_TYPES)

        expense_mask = transaction_types.isin(self.EXPENSE_TYPES)

        categorized_mask = categories.ne("")

        uncategorized_mask = ~categorized_mask

        metadata: dict[str, Any] = {
            "total_transactions": total_transactions,

            "income_transactions": int(
                income_mask.sum()
            ),

            "expense_transactions": int(
                expense_mask.sum()
            ),

            "categorized_transactions": int(
                categorized_mask.sum()
            ),

            "uncategorized_transactions": int(
                uncategorized_mask.sum()
            ),

            "organization_ids": sorted(
                dataframe["organization_id"]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            ),

            "transaction_type_distribution": (
                transaction_types.value_counts()
                .to_dict()
            ),

            "category_distribution": (
                categories[
                    categorized_mask
                ]
                .value_counts()
                .to_dict()
            ),
        }

        return metadata


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def build_training_dataset(
    organization_id: int,
    start_date: Optional[date | datetime] = None,
    end_date: Optional[date | datetime] = None,
) -> DatasetResult:
    """
    Convenience wrapper for building a training dataset.
    """

    service = FinancialDatasetService()

    return service.build_training_dataset(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
    )


def build_prediction_dataset(
    organization_id: int,
    start_date: Optional[date | datetime] = None,
    end_date: Optional[date | datetime] = None,
) -> DatasetResult:
    """
    Convenience wrapper for building a prediction dataset.
    """

    service = FinancialDatasetService()

    return service.build_prediction_dataset(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
    )