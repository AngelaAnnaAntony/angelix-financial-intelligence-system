"""
ANGELIX - Machine Learning Feature Engineering

This module prepares financial transaction data for machine learning.

Responsibilities:
- Normalize transaction data
- Create transaction-level numerical features
- Create organization-level financial features
- Handle missing values safely
- Prepare feature matrices for ML models
- Keep feature generation deterministic and reusable

This module does NOT:
- Train models
- Make database queries
- Call AI APIs
- Generate financial health scores
- Replace deterministic financial calculations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANSACTION_TYPES = {
    "income": "Income",
    "expense": "Expense",
    "asset": "Asset",
    "liability": "Liability",
    "equity": "Equity",
}

DEFAULT_NUMERIC_VALUE = 0.0


# ---------------------------------------------------------------------------
# Feature result container
# ---------------------------------------------------------------------------

@dataclass
class FeatureEngineeringResult:
    """
    Container for generated ML features.

    Attributes:
        features:
            Final feature DataFrame used by an ML model.

        feature_names:
            Ordered list of feature names.

        metadata:
            Additional information about feature generation.
    """

    features: pd.DataFrame
    feature_names: list[str]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Main feature engineering class
# ---------------------------------------------------------------------------

class FinancialFeatureEngineer:
    """
    Generates machine-learning features from ANGELIX financial data.

    The class is intentionally independent of SQLAlchemy so that it can be
    used with:
        - database query results
        - pandas DataFrames
        - CSV/XLSX extracted data
        - testing fixtures
        - future batch-processing pipelines
    """

    def __init__(self) -> None:
        self.feature_names: list[str] = []

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def transform(
        self,
        transactions: Optional[
            pd.DataFrame | Iterable[dict[str, Any]]
        ] = None,
    ) -> FeatureEngineeringResult:
        """
        Convert transaction records into ML-ready features.

        Parameters:
            transactions:
                Transaction records as either:
                - pandas DataFrame
                - iterable of dictionaries

        Returns:
            FeatureEngineeringResult
        """

        dataframe = self._to_dataframe(transactions)

        if dataframe.empty:
            empty_features = self._empty_feature_dataframe()

            self.feature_names = list(empty_features.columns)

            return FeatureEngineeringResult(
                features=empty_features,
                feature_names=self.feature_names,
                metadata={
                    "source_rows": 0,
                    "feature_rows": 0,
                    "status": "empty",
                },
            )

        dataframe = self._normalize_columns(dataframe)
        dataframe = self._prepare_dates(dataframe)
        dataframe = self._prepare_amounts(dataframe)
        dataframe = self._prepare_transaction_types(dataframe)

        features = self._build_transaction_features(dataframe)

        features = self._clean_features(features)

        self.feature_names = list(features.columns)

        return FeatureEngineeringResult(
            features=features,
            feature_names=self.feature_names,
            metadata={
                "source_rows": len(dataframe),
                "feature_rows": len(features),
                "feature_count": len(features.columns),
                "status": "success",
            },
        )

    # -----------------------------------------------------------------------
    # DataFrame conversion
    # -----------------------------------------------------------------------

    def _to_dataframe(
        self,
        transactions: Optional[
            pd.DataFrame | Iterable[dict[str, Any]]
        ],
    ) -> pd.DataFrame:
        """
        Convert supported transaction inputs into a DataFrame.
        """

        if transactions is None:
            return pd.DataFrame()

        if isinstance(transactions, pd.DataFrame):
            return transactions.copy()

        try:
            return pd.DataFrame(list(transactions))
        except (TypeError, ValueError):
            return pd.DataFrame()

    # -----------------------------------------------------------------------
    # Column normalization
    # -----------------------------------------------------------------------

    def _normalize_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names and create expected columns where necessary.
        """

        dataframe = dataframe.copy()

        dataframe.columns = [
            str(column).strip().lower().replace(" ", "_")
            for column in dataframe.columns
        ]

        aliases = {
            "date": "transaction_date",
            "transactiondate": "transaction_date",
            "description_text": "description",
            "transaction_description": "description",
            "type": "transaction_type",
            "transactiontype": "transaction_type",
            "value": "amount",
            "transaction_amount": "amount",
        }

        for source, target in aliases.items():
            if source in dataframe.columns and target not in dataframe.columns:
                dataframe[target] = dataframe[source]

        expected_columns = {
            "transaction_date": pd.NaT,
            "description": "",
            "amount": 0.0,
            "transaction_type": "",
            "category": "",
            "subcategory": "",
            "source": "",
            "reference_number": "",
            "is_recurring": False,
            "confidence_score": np.nan,
        }

        for column, default_value in expected_columns.items():
            if column not in dataframe.columns:
                dataframe[column] = default_value

        return dataframe

    # -----------------------------------------------------------------------
    # Date processing
    # -----------------------------------------------------------------------

    def _prepare_dates(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Convert transaction dates and derive calendar features.
        """

        dataframe = dataframe.copy()

        dataframe["transaction_date"] = pd.to_datetime(
            dataframe["transaction_date"],
            errors="coerce",
        )

        dataframe["transaction_year"] = (
            dataframe["transaction_date"]
            .dt.year
            .fillna(0)
            .astype(int)
        )

        dataframe["transaction_month"] = (
            dataframe["transaction_date"]
            .dt.month
            .fillna(0)
            .astype(int)
        )

        dataframe["transaction_day"] = (
            dataframe["transaction_date"]
            .dt.day
            .fillna(0)
            .astype(int)
        )

        dataframe["transaction_day_of_week"] = (
            dataframe["transaction_date"]
            .dt.dayofweek
            .fillna(-1)
            .astype(int)
        )

        dataframe["transaction_quarter"] = (
            dataframe["transaction_date"]
            .dt.quarter
            .fillna(0)
            .astype(int)
        )

        dataframe["is_weekend"] = (
            dataframe["transaction_day_of_week"]
            .isin([5, 6])
            .astype(int)
        )

        return dataframe

    # -----------------------------------------------------------------------
    # Amount processing
    # -----------------------------------------------------------------------

    def _prepare_amounts(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize transaction amounts and derive amount-based features.
        """

        dataframe = dataframe.copy()

        dataframe["amount"] = pd.to_numeric(
            dataframe["amount"],
            errors="coerce",
        ).fillna(DEFAULT_NUMERIC_VALUE)

        dataframe["absolute_amount"] = dataframe["amount"].abs()

        dataframe["is_positive_amount"] = (
            dataframe["amount"] > 0
        ).astype(int)

        dataframe["is_negative_amount"] = (
            dataframe["amount"] < 0
        ).astype(int)

        dataframe["amount_log"] = np.log1p(
            dataframe["absolute_amount"]
        )

        return dataframe

    # -----------------------------------------------------------------------
    # Transaction type processing
    # -----------------------------------------------------------------------

    def _prepare_transaction_types(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize transaction types and generate one-hot indicators.
        """

        dataframe = dataframe.copy()

        dataframe["transaction_type"] = (
            dataframe["transaction_type"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        for transaction_type in TRANSACTION_TYPES:
            column_name = f"type_{transaction_type}"

            dataframe[column_name] = (
                dataframe["transaction_type"]
                == transaction_type
            ).astype(int)

        return dataframe

    # -----------------------------------------------------------------------
    # Feature construction
    # -----------------------------------------------------------------------

    def _build_transaction_features(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build the final transaction-level feature matrix.
        """

        features = pd.DataFrame(index=dataframe.index)

        # Amount-related features
        features["amount"] = dataframe["amount"]
        features["absolute_amount"] = dataframe["absolute_amount"]
        features["amount_log"] = dataframe["amount_log"]
        features["is_positive_amount"] = dataframe["is_positive_amount"]
        features["is_negative_amount"] = dataframe["is_negative_amount"]

        # Calendar features
        features["transaction_year"] = dataframe["transaction_year"]
        features["transaction_month"] = dataframe["transaction_month"]
        features["transaction_day"] = dataframe["transaction_day"]
        features["transaction_day_of_week"] = (
            dataframe["transaction_day_of_week"]
        )
        features["transaction_quarter"] = dataframe["transaction_quarter"]
        features["is_weekend"] = dataframe["is_weekend"]

        # Transaction type features
        features["type_income"] = dataframe["type_income"]
        features["type_expense"] = dataframe["type_expense"]
        features["type_asset"] = dataframe["type_asset"]
        features["type_liability"] = dataframe["type_liability"]
        features["type_equity"] = dataframe["type_equity"]

        # Recurring transaction indicator
        features["is_recurring"] = (
            dataframe["is_recurring"]
            .apply(self._to_boolean)
            .astype(int)
        )

        # Existing extraction/classification confidence
        features["confidence_score"] = pd.to_numeric(
            dataframe["confidence_score"],
            errors="coerce",
        ).fillna(0.0)

        # Description-based features
        description = (
            dataframe["description"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        features["description_length"] = description.str.len()

        features["description_word_count"] = (
            description
            .str.split()
            .str.len()
            .fillna(0)
        )

        features["has_reference_number"] = (
            dataframe["reference_number"]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .astype(int)
        )

        # Source-based feature
        features["has_source"] = (
            dataframe["source"]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .astype(int)
        )

        return features

    # -----------------------------------------------------------------------
    # Cleaning
    # -----------------------------------------------------------------------

    def _clean_features(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Ensure the feature matrix contains only finite numeric values.
        """

        features = features.copy()

        features = features.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        numeric_columns = features.select_dtypes(
            include=[np.number]
        ).columns

        features[numeric_columns] = (
            features[numeric_columns]
            .fillna(0.0)
        )

        features = features.astype(float)

        return features

    # -----------------------------------------------------------------------
    # Boolean normalization
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_boolean(value: Any) -> bool:
        """
        Convert common database/string representations to bool.
        """

        if isinstance(value, bool):
            return value

        if value is None:
            return False

        if isinstance(value, (int, float)):
            return bool(value)

        normalized = str(value).strip().lower()

        return normalized in {
            "true",
            "1",
            "yes",
            "y",
            "on",
        }

    # -----------------------------------------------------------------------
    # Empty feature matrix
    # -----------------------------------------------------------------------

    @staticmethod
    def _empty_feature_dataframe() -> pd.DataFrame:
        """
        Return an empty DataFrame with the expected ML feature schema.
        """

        columns = [
            "amount",
            "absolute_amount",
            "amount_log",
            "is_positive_amount",
            "is_negative_amount",
            "transaction_year",
            "transaction_month",
            "transaction_day",
            "transaction_day_of_week",
            "transaction_quarter",
            "is_weekend",
            "type_income",
            "type_expense",
            "type_asset",
            "type_liability",
            "type_equity",
            "is_recurring",
            "confidence_score",
            "description_length",
            "description_word_count",
            "has_reference_number",
            "has_source",
        ]

        return pd.DataFrame(
            columns=columns,
            dtype=float,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def build_transaction_features(
    transactions: Optional[
        pd.DataFrame | Iterable[dict[str, Any]]
    ] = None,
) -> FeatureEngineeringResult:
    """
    Convenience wrapper around FinancialFeatureEngineer.
    """

    engineer = FinancialFeatureEngineer()

    return engineer.transform(transactions)