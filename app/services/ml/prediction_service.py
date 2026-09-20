"""
ANGELIX - Financial ML Prediction Service

Provides organization-isolated predictions using persisted ANGELIX
machine-learning models.

Supported prediction families:
- Existing financial/anomaly models using ANGELIX feature engineering.
- Supervised accounting classification:
    * Asset / Liability / Equity / Revenue / Expense
    * Debit / Credit

The accounting classifiers are loaded from the same organization-specific
model store managed by ModelManager.

Predictions are analytical outputs and should be reviewed according to
ANGELIX confidence and validation rules before being treated as final
accounting classifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from app.services.ml.dataset_service import (
    FinancialDatasetService,
)
from app.services.ml.feature_engineering import (
    FinancialFeatureEngineer,
)
from app.services.ml.model_manager import (
    ModelManager,
    ACCOUNT_TYPE_MODEL_NAME,
    DEBIT_CREDIT_MODEL_NAME,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL_NAME = "financial_anomaly_random_forest"

ACCOUNTING_MODEL_NAMES = {
    ACCOUNT_TYPE_MODEL_NAME,
    DEBIT_CREDIT_MODEL_NAME,
}

ACCOUNTING_MODEL_FAMILY = "accounting_transaction_classification"


# ---------------------------------------------------------------------------
# Prediction result
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    """
    Structured result returned by the prediction service.
    """

    success: bool
    status: str
    message: str

    predictions: list[Any]
    probabilities: list[dict[str, float]]
    confidence_scores: list[float]

    model_name: Optional[str] = None
    model_version: Optional[str] = None

    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert prediction result to a JSON-safe dictionary.
        """

        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "predictions": self.predictions,
            "probabilities": self.probabilities,
            "confidence_scores": self.confidence_scores,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "metadata": self.metadata or {},
        }


# ---------------------------------------------------------------------------
# Prediction service
# ---------------------------------------------------------------------------

class FinancialPredictionService:
    """
    Generates predictions using persisted organization-specific models.
    """

    def __init__(
        self,
        dataset_service: Optional[FinancialDatasetService] = None,
        model_manager: Optional[ModelManager] = None,
        feature_engineer: Optional[FinancialFeatureEngineer] = None,
    ) -> None:

        self.dataset_service = (
            dataset_service
            if dataset_service is not None
            else FinancialDatasetService()
        )

        self.model_manager = (
            model_manager
            if model_manager is not None
            else ModelManager()
        )

        self.feature_engineer = (
            feature_engineer
            if feature_engineer is not None
            else FinancialFeatureEngineer()
        )

    # ------------------------------------------------------------------
    # Public prediction method
    # ------------------------------------------------------------------

    def predict_for_organization(
        self,
        organization_id: int,
        model_name: str = DEFAULT_MODEL_NAME,
        model_version: Optional[str] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> PredictionResult:
        """
        Generate predictions for transactions belonging to an organization.

        Accounting classifiers use their own compact input schema because
        their persisted sklearn pipelines already contain TF-IDF,
        categorical encoding and numerical preprocessing.
        Existing anomaly/risk models continue to use the ANGELIX feature
        engineering pipeline.
        """

        dataset_result = self.dataset_service.build_prediction_dataset(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not dataset_result.success:
            return PredictionResult(
                success=False,
                status="dataset_error",
                message=dataset_result.message,
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                metadata={
                    "organization_id": organization_id,
                },
            )

        dataframe = dataset_result.features.copy()

        if dataframe.empty:
            return PredictionResult(
                success=False,
                status="empty_dataset",
                message="No transactions are available for prediction.",
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                metadata={
                    "organization_id": organization_id,
                },
            )

        safe_model_name = str(model_name).strip()

        if safe_model_name in ACCOUNTING_MODEL_NAMES:
            return self._predict_accounting_model(
                organization_id=organization_id,
                dataframe=dataframe,
                model_name=safe_model_name,
                model_version=model_version,
            )

        return self._predict_existing_model(
            organization_id=organization_id,
            dataframe=dataframe,
            model_name=safe_model_name,
            model_version=model_version,
        )

    # ------------------------------------------------------------------
    # Existing ANGELIX ML models
    # ------------------------------------------------------------------

    def _predict_existing_model(
        self,
        organization_id: int,
        dataframe: pd.DataFrame,
        model_name: str,
        model_version: Optional[str],
    ) -> PredictionResult:
        """
        Generate predictions using the existing ANGELIX feature-engineering
        pipeline.
        """

        try:
            model = self.model_manager.load_model(
                organization_id=organization_id,
                model_name=model_name,
                version=self._normalise_version(model_version),
            )

            model_metadata = self._load_model_metadata(
                organization_id=organization_id,
                model_name=model_name,
                model_version=model_version,
            )
        except Exception as exc:
            return PredictionResult(
                success=False,
                status="model_error",
                message=f"Unable to load ML model: {exc}",
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                },
            )

        try:
            feature_result = self.feature_engineer.transform(
                dataframe
            )
        except Exception as exc:
            return PredictionResult(
                success=False,
                status="feature_error",
                message=f"Feature generation failed: {exc}",
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                },
            )

        if not feature_result.success:
            return PredictionResult(
                success=False,
                status="feature_error",
                message=feature_result.message,
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                },
            )

        features = feature_result.features

        return self._run_model(
            organization_id=organization_id,
            model=model,
            model_metadata=model_metadata,
            model_name=model_name,
            model_version=model_version,
            features=features,
            transaction_count=len(dataframe),
            message="Financial transaction predictions generated successfully.",
        )

    # ------------------------------------------------------------------
    # Accounting ML models
    # ------------------------------------------------------------------

    def _predict_accounting_model(
        self,
        organization_id: int,
        dataframe: pd.DataFrame,
        model_name: str,
        model_version: Optional[str],
    ) -> PredictionResult:
        """
        Generate predictions using the supervised accounting classifiers.

        These persisted sklearn pipelines expect:
            description
            amount
            is_recurring
            source
            month

        Keeping this schema here prevents the generic ANGELIX feature
        engineer from changing the inputs expected by the trained pipeline.
        """

        try:
            model = self.model_manager.load_model(
                organization_id=organization_id,
                model_name=model_name,
                version=self._normalise_version(model_version),
            )

            model_metadata = self._load_model_metadata(
                organization_id=organization_id,
                model_name=model_name,
                model_version=model_version,
            )
        except Exception as exc:
            return PredictionResult(
                success=False,
                status="model_error",
                message=(
                    f"Unable to load accounting ML model: {exc}"
                ),
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                model_name=model_name,
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                    "model_family": ACCOUNTING_MODEL_FAMILY,
                },
            )

        try:
            features = self._build_accounting_features(
                dataframe
            )
        except Exception as exc:
            return PredictionResult(
                success=False,
                status="feature_error",
                message=(
                    f"Accounting ML feature preparation failed: {exc}"
                ),
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                model_name=model_name,
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                    "model_family": ACCOUNTING_MODEL_FAMILY,
                },
            )

        return self._run_model(
            organization_id=organization_id,
            model=model,
            model_metadata=model_metadata,
            model_name=model_name,
            model_version=model_version,
            features=features,
            transaction_count=len(dataframe),
            message=(
                "Supervised accounting transaction predictions "
                "generated successfully."
            ),
        )

    # ------------------------------------------------------------------
    # Accounting feature preparation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_accounting_features(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build exactly the feature schema expected by the trained accounting
        sklearn pipelines.
        """

        result = pd.DataFrame(index=dataframe.index)

        if "description" in dataframe.columns:
            result["description"] = (
                dataframe["description"]
                .fillna("")
                .astype(str)
            )
        else:
            result["description"] = ""

        if "amount" in dataframe.columns:
            result["amount"] = pd.to_numeric(
                dataframe["amount"],
                errors="coerce",
            ).fillna(0.0)
        else:
            result["amount"] = 0.0

        if "is_recurring" in dataframe.columns:
            recurring = dataframe["is_recurring"]

            if recurring.dtype == object:
                recurring = (
                    recurring
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .map(
                        {
                            "true": 1,
                            "1": 1,
                            "yes": 1,
                            "y": 1,
                            "false": 0,
                            "0": 0,
                            "no": 0,
                            "n": 0,
                        }
                    )
                )

            result["is_recurring"] = (
                pd.to_numeric(
                    recurring,
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )
        else:
            result["is_recurring"] = 0

        if "source" in dataframe.columns:
            result["source"] = (
                dataframe["source"]
                .fillna("Manual")
                .astype(str)
            )
        else:
            result["source"] = "Manual"

        if "transaction_date" in dataframe.columns:
            dates = pd.to_datetime(
                dataframe["transaction_date"],
                errors="coerce",
            )
            result["month"] = (
                dates.dt.month
                .fillna(1)
                .astype(int)
            )
        elif "month" in dataframe.columns:
            result["month"] = (
                pd.to_numeric(
                    dataframe["month"],
                    errors="coerce",
                )
                .fillna(1)
                .clip(1, 12)
                .astype(int)
            )
        else:
            result["month"] = 1

        return result[
            [
                "description",
                "amount",
                "is_recurring",
                "source",
                "month",
            ]
        ]

    # ------------------------------------------------------------------
    # Execute model
    # ------------------------------------------------------------------

    def _run_model(
        self,
        organization_id: int,
        model: Any,
        model_metadata: dict[str, Any],
        model_name: str,
        model_version: Optional[str],
        features: pd.DataFrame,
        transaction_count: int,
        message: str,
    ) -> PredictionResult:
        """
        Execute a persisted model and construct a common prediction result.
        """

        try:
            predictions = model.predict(features)
        except Exception as exc:
            return PredictionResult(
                success=False,
                status="prediction_error",
                message=f"Model prediction failed: {exc}",
                predictions=[],
                probabilities=[],
                confidence_scores=[],
                model_name=model_name,
                metadata={
                    "organization_id": organization_id,
                    "model_name": model_name,
                },
            )

        prediction_values = predictions.tolist()

        probabilities: list[dict[str, float]] = []
        confidence_scores: list[float] = []

        if hasattr(model, "predict_proba"):
            try:
                probability_matrix = model.predict_proba(
                    features
                )

                classes = getattr(
                    model,
                    "classes_",
                    None,
                )

                for row in probability_matrix:
                    row_probabilities: dict[str, float] = {}

                    for index, probability in enumerate(row):
                        if classes is not None:
                            class_name = str(
                                classes[index]
                            )
                        else:
                            class_name = f"class_{index}"

                        row_probabilities[
                            class_name
                        ] = float(probability)

                    probabilities.append(
                        row_probabilities
                    )

                    confidence_scores.append(
                        float(max(row))
                    )

            except Exception:
                # Some sklearn wrappers expose predict_proba but may not
                # support it for a particular persisted model.
                probabilities = []
                confidence_scores = []

        resolved_version = (
            model_metadata.get("version")
            if isinstance(model_metadata, dict)
            else model_version
        )

        metadata = {
            "organization_id": organization_id,
            "transaction_count": transaction_count,
            "feature_count": int(features.shape[1]),
            "model_name": model_name,
            "model_version": resolved_version,
        }

        if isinstance(model_metadata, dict):
            metadata["model_family"] = model_metadata.get(
                "model_family"
            )
            metadata["model_status"] = model_metadata.get(
                "status"
            )

        return PredictionResult(
            success=True,
            status="success",
            message=message,
            predictions=prediction_values,
            probabilities=probabilities,
            confidence_scores=confidence_scores,
            model_name=model_name,
            model_version=(
                str(resolved_version)
                if resolved_version is not None
                else None
            ),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Model metadata
    # ------------------------------------------------------------------

    def _load_model_metadata(
        self,
        organization_id: int,
        model_name: str,
        model_version: Optional[str],
    ) -> dict[str, Any]:
        """
        Load metadata separately from the model.

        ModelManager.load_model() returns the persisted estimator itself;
        metadata is maintained in its corresponding JSON file.
        """

        version = self._normalise_version(
            model_version
        )

        metadata = self.model_manager.load_metadata(
            organization_id=organization_id,
            model_name=model_name,
            version=version,
        )

        if isinstance(metadata, dict):
            return metadata

        return {}

    # ------------------------------------------------------------------
    # Version normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_version(
        model_version: Optional[str | int],
    ) -> Optional[int]:
        """
        Convert a version supplied by routes/services into an integer.
        """

        if model_version is None:
            return None

        if isinstance(model_version, int):
            if model_version < 1:
                raise ValueError(
                    "model_version must be greater than zero."
                )
            return model_version

        value = str(model_version).strip()

        if not value:
            return None

        # Accept values such as "1" and "v1".
        if value.lower().startswith("v"):
            value = value[1:]

        try:
            version = int(value)
        except ValueError as exc:
            raise ValueError(
                "model_version must be an integer or a value such as 'v1'."
            ) from exc

        if version < 1:
            raise ValueError(
                "model_version must be greater than zero."
            )

        return version

    # ------------------------------------------------------------------
    # Single transaction accounting prediction
    # ------------------------------------------------------------------

    def predict_accounting_transaction(
        self,
        organization_id: int,
        description: str,
        amount: float,
        is_recurring: bool = False,
        source: str = "Manual",
        transaction_date: Optional[Any] = None,
        account_model_version: Optional[str] = None,
        debit_credit_model_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Predict account type and debit/credit for one transaction.

        This method is intended for document-extraction/manual-entry
        workflows where a transaction does not yet need to be persisted.

        Returns a combined result so the caller can present both
        classifications together.
        """

        month = self._extract_month(
            transaction_date
        )

        frame = pd.DataFrame(
            [
                {
                    "description": str(
                        description or ""
                    ),
                    "amount": float(
                        amount or 0
                    ),
                    "is_recurring": int(
                        bool(is_recurring)
                    ),
                    "source": str(
                        source or "Manual"
                    ),
                    "month": month,
                }
            ]
        )

        try:
            account_version = self._normalise_version(
                account_model_version
            )
            side_version = self._normalise_version(
                debit_credit_model_version
            )

            account_model = self.model_manager.load_model(
                organization_id=organization_id,
                model_name=ACCOUNT_TYPE_MODEL_NAME,
                version=account_version,
            )

            side_model = self.model_manager.load_model(
                organization_id=organization_id,
                model_name=DEBIT_CREDIT_MODEL_NAME,
                version=side_version,
            )

            account_metadata = self._load_model_metadata(
                organization_id=organization_id,
                model_name=ACCOUNT_TYPE_MODEL_NAME,
                model_version=account_model_version,
            )

            side_metadata = self._load_model_metadata(
                organization_id=organization_id,
                model_name=DEBIT_CREDIT_MODEL_NAME,
                model_version=debit_credit_model_version,
            )

        except Exception as exc:
            return {
                "success": False,
                "status": "model_error",
                "message": (
                    f"Unable to load accounting classifiers: {exc}"
                ),
                "organization_id": organization_id,
            }

        try:
            account_prediction = account_model.predict(frame)[0]
            side_prediction = side_model.predict(frame)[0]
        except Exception as exc:
            return {
                "success": False,
                "status": "prediction_error",
                "message": (
                    f"Accounting classification failed: {exc}"
                ),
                "organization_id": organization_id,
            }

        account_probability = self._single_prediction_probability(
            account_model,
            frame,
        )
        side_probability = self._single_prediction_probability(
            side_model,
            frame,
        )

        account_confidence = (
            account_probability["confidence"]
            if account_probability is not None
            else None
        )

        side_confidence = (
            side_probability["confidence"]
            if side_probability is not None
            else None
        )

        return {
            "success": True,
            "status": "success",
            "message": (
                "Accounting transaction classification generated successfully."
            ),
            "organization_id": organization_id,
            "account_type": str(account_prediction),
            "account_confidence": account_confidence,
            "account_probabilities": (
                account_probability["probabilities"]
                if account_probability is not None
                else {}
            ),
            "debit_credit": str(side_prediction),
            "debit_credit_confidence": side_confidence,
            "debit_credit_probabilities": (
                side_probability["probabilities"]
                if side_probability is not None
                else {}
            ),
            "models": {
                "account_type": {
                    "name": ACCOUNT_TYPE_MODEL_NAME,
                    "version": account_metadata.get(
                        "version"
                    ),
                },
                "debit_credit": {
                    "name": DEBIT_CREDIT_MODEL_NAME,
                    "version": side_metadata.get(
                        "version"
                    ),
                },
            },
        }

    # ------------------------------------------------------------------
    # Single prediction probability helper
    # ------------------------------------------------------------------

    @staticmethod
    def _single_prediction_probability(
        model: Any,
        features: pd.DataFrame,
    ) -> Optional[dict[str, Any]]:
        """
        Return class probabilities and maximum probability for one row.
        """

        if not hasattr(model, "predict_proba"):
            return None

        try:
            matrix = model.predict_proba(
                features
            )

            if len(matrix) == 0:
                return None

            row = matrix[0]
            classes = getattr(
                model,
                "classes_",
                None,
            )

            probabilities: dict[str, float] = {}

            for index, probability in enumerate(row):
                class_name = (
                    str(classes[index])
                    if classes is not None
                    else f"class_{index}"
                )
                probabilities[
                    class_name
                ] = float(probability)

            return {
                "confidence": float(max(row)),
                "probabilities": probabilities,
            }

        except Exception:
            return None

    # ------------------------------------------------------------------
    # Date helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_month(
        transaction_date: Optional[Any],
    ) -> int:
        """
        Extract transaction month for the accounting model.
        """

        if transaction_date is None:
            return 1

        try:
            parsed = pd.to_datetime(
                transaction_date,
                errors="coerce",
            )

            if pd.isna(parsed):
                return 1

            return int(parsed.month)

        except Exception:
            return 1


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def predict_financial_transactions(
    organization_id: int,
    model_name: str = DEFAULT_MODEL_NAME,
    model_version: Optional[str] = None,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
) -> PredictionResult:
    """
    Convenience wrapper for generating transaction predictions.
    """

    service = FinancialPredictionService()

    return service.predict_for_organization(
        organization_id=organization_id,
        model_name=model_name,
        model_version=model_version,
        start_date=start_date,
        end_date=end_date,
    )


def predict_accounting_transaction(
    organization_id: int,
    description: str,
    amount: float,
    is_recurring: bool = False,
    source: str = "Manual",
    transaction_date: Optional[Any] = None,
    account_model_version: Optional[str] = None,
    debit_credit_model_version: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience wrapper for one-transaction accounting classification.
    """

    service = FinancialPredictionService()

    return service.predict_accounting_transaction(
        organization_id=organization_id,
        description=description,
        amount=amount,
        is_recurring=is_recurring,
        source=source,
        transaction_date=transaction_date,
        account_model_version=account_model_version,
        debit_credit_model_version=debit_credit_model_version,
    )
