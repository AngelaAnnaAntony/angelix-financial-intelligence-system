"""
ANGELIX - Financial ML Training Pipeline

End-to-end organization-scoped training workflow.

Pipeline:

    Transactions
        ↓
    Dataset Service
        ↓
    Feature Engineering
        ↓
    Statistical Target Engineering
        ↓
    Target Validation
        ↓
    Model Training
        ↓
    Model Persistence

The generated anomaly labels represent statistical observations that
may warrant review. They are not confirmed fraud labels or financial
risk diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from app.services.ml.dataset_service import (
    FinancialDatasetService,
)

from app.services.ml.model_manager import (
    ModelManager,
)

from app.services.ml.model_training import (
    FinancialModelTrainer,
)

from app.services.ml.target_engineering import (
    FinancialTargetEngineer,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL_NAME = (
    "financial_anomaly_random_forest"
)

DEFAULT_MODEL_TYPE = "random_forest"

DEFAULT_TEST_SIZE = 0.20

DEFAULT_RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class TrainingPipelineResult:
    """
    Structured result returned by the complete ML training pipeline.
    """

    success: bool
    status: str
    message: str

    model_name: Optional[str] = None
    model_version: Optional[str] = None

    model_path: Optional[str] = None
    metadata_path: Optional[str] = None

    metrics: Optional[dict[str, Any]] = None
    feature_importance: Optional[dict[str, float]] = None

    dataset_metadata: Optional[dict[str, Any]] = None
    target_metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the result to a JSON-safe dictionary.
        """

        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_path": self.model_path,
            "metadata_path": self.metadata_path,
            "metrics": self.metrics or {},
            "feature_importance": (
                self.feature_importance or {}
            ),
            "dataset_metadata": (
                self.dataset_metadata or {}
            ),
            "target_metadata": (
                self.target_metadata or {}
            ),
        }


# ---------------------------------------------------------------------------
# Training Pipeline
# ---------------------------------------------------------------------------

class FinancialTrainingPipeline:
    """
    Coordinates the complete Angelix financial ML training workflow.
    """

    def __init__(
        self,
        dataset_service: Optional[
            FinancialDatasetService
        ] = None,
        target_engineer: Optional[
            FinancialTargetEngineer
        ] = None,
        model_trainer: Optional[
            FinancialModelTrainer
        ] = None,
        model_manager: Optional[
            ModelManager
        ] = None,
    ) -> None:

        self.dataset_service = (
            dataset_service
            if dataset_service is not None
            else FinancialDatasetService()
        )

        self.target_engineer = (
            target_engineer
            if target_engineer is not None
            else FinancialTargetEngineer()
        )

        self.model_trainer = (
            model_trainer
            if model_trainer is not None
            else FinancialModelTrainer()
        )

        self.model_manager = (
            model_manager
            if model_manager is not None
            else ModelManager()
        )

    # ------------------------------------------------------------------
    # Main training workflow
    # ------------------------------------------------------------------

    def train_for_organization(
        self,
        organization_id: int,
        model_name: str = DEFAULT_MODEL_NAME,
        model_type: str = DEFAULT_MODEL_TYPE,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        test_size: float = DEFAULT_TEST_SIZE,
        random_state: int = DEFAULT_RANDOM_STATE,
    ) -> TrainingPipelineResult:
        """
        Train and persist a financial anomaly model for one organization.
        """

        # --------------------------------------------------------------
        # 1. Build dataset
        # --------------------------------------------------------------

        dataset_result = (
            self.dataset_service.build_training_dataset(
                organization_id=organization_id,
                start_date=start_date,
                end_date=end_date,
            )
        )

        if not dataset_result.success:

            return TrainingPipelineResult(
                success=False,
                status="dataset_error",
                message=dataset_result.message,
                dataset_metadata=(
                    dataset_result.metadata
                ),
            )

        features = dataset_result.features.copy()

        if features.empty:

            return TrainingPipelineResult(
                success=False,
                status="empty_dataset",
                message=(
                    "The training dataset contains no rows."
                ),
                dataset_metadata=(
                    dataset_result.metadata
                ),
            )

        # --------------------------------------------------------------
        # 2. Generate statistical targets
        # --------------------------------------------------------------

        target_result = (
            self.target_engineer.generate_anomaly_targets(
                features
            )
        )

        if not target_result.success:

            return TrainingPipelineResult(
                success=False,
                status="target_error",
                message=target_result.message,
                dataset_metadata=(
                    dataset_result.metadata
                ),
                target_metadata=(
                    target_result.metadata
                ),
            )

        targets = target_result.targets.copy()

        # --------------------------------------------------------------
        # 3. Validate target
        # --------------------------------------------------------------

        validation_result = (
            self.target_engineer.validate_target(
                targets
            )
        )

        if not validation_result.valid:

            return TrainingPipelineResult(
                success=False,
                status="invalid_target",
                message=(
                    "Model training was skipped because the generated "
                    "target is not suitable for supervised learning. "
                    f"{validation_result.message}"
                ),
                dataset_metadata=(
                    dataset_result.metadata
                ),
                target_metadata={
                    **(
                        target_result.metadata
                        or {}
                    ),
                    "validation": (
                        validation_result.to_dict()
                    ),
                },
            )

        # --------------------------------------------------------------
        # 4. Align features and target
        # --------------------------------------------------------------

        common_index = (
            features.index
            .intersection(
                targets.index
            )
        )

        features = features.loc[
            common_index
        ]

        targets = targets.loc[
            common_index
        ]

        if features.empty:

            return TrainingPipelineResult(
                success=False,
                status="empty_training_data",
                message=(
                    "No aligned feature and target rows "
                    "are available for training."
                ),
                dataset_metadata=(
                    dataset_result.metadata
                ),
                target_metadata=(
                    target_result.metadata
                ),
            )

        # --------------------------------------------------------------
        # 5. Train model
        # --------------------------------------------------------------

        training_result = (
            self.model_trainer.train(
                X=features,
                y=targets,
                model_type=model_type,
                test_size=test_size,
                random_state=random_state,
            )
        )

        if not training_result.success:

            return TrainingPipelineResult(
                success=False,
                status="training_error",
                message=training_result.message,
                dataset_metadata=(
                    dataset_result.metadata
                ),
                target_metadata=(
                    target_result.metadata
                ),
                metrics=training_result.metrics,
                feature_importance=(
                    training_result.feature_importance
                ),
            )

        # --------------------------------------------------------------
        # 6. Persist model
        # --------------------------------------------------------------

        try:

            save_result = (
                self.model_manager.save_model(
                    organization_id=organization_id,
                    model_name=model_name,
                    model=training_result.model,
                    metadata={
                        "organization_id": (
                            organization_id
                        ),
                        "model_name": model_name,
                        "model_type": model_type,
                        "target_name": (
                            target_result.target_name
                        ),
                        "metrics": (
                            training_result.metrics
                        ),
                        "feature_importance": (
                            training_result.feature_importance
                        ),
                        "dataset_metadata": (
                            dataset_result.metadata
                        ),
                        "target_metadata": (
                            target_result.metadata
                        ),
                        "target_validation": (
                            validation_result.to_dict()
                        ),
                        "training_configuration": {
                            "test_size": test_size,
                            "random_state": random_state,
                        },
                    },
                )
            )

        except Exception as exc:

            return TrainingPipelineResult(
                success=False,
                status="model_persistence_error",
                message=(
                    f"Model training succeeded, but the model "
                    f"could not be persisted: {exc}"
                ),
                metrics=(
                    training_result.metrics
                ),
                feature_importance=(
                    training_result.feature_importance
                ),
                dataset_metadata=(
                    dataset_result.metadata
                ),
                target_metadata=(
                    target_result.metadata
                ),
            )

        # --------------------------------------------------------------
        # 7. Return successful result
        # --------------------------------------------------------------

        return TrainingPipelineResult(
            success=True,
            status="success",
            message=(
                "Financial anomaly model trained and "
                "persisted successfully."
            ),
            model_name=model_name,
            model_version=(
                save_result.get("version")
                if isinstance(
                    save_result,
                    dict,
                )
                else None
            ),
            model_path=(
                save_result.get("model_path")
                if isinstance(
                    save_result,
                    dict,
                )
                else None
            ),
            metadata_path=(
                save_result.get("metadata_path")
                if isinstance(
                    save_result,
                    dict,
                )
                else None
            ),
            metrics=(
                training_result.metrics
            ),
            feature_importance=(
                training_result.feature_importance
            ),
            dataset_metadata=(
                dataset_result.metadata
            ),
            target_metadata={
                **(
                    target_result.metadata
                    or {}
                ),
                "validation": (
                    validation_result.to_dict()
                ),
            },
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def train_financial_anomaly_model(
    organization_id: int,
    model_name: str = DEFAULT_MODEL_NAME,
    model_type: str = DEFAULT_MODEL_TYPE,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
    test_size: float = DEFAULT_TEST_SIZE,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> TrainingPipelineResult:
    """
    Convenience wrapper for training a financial anomaly model.
    """

    pipeline = FinancialTrainingPipeline()

    return pipeline.train_for_organization(
        organization_id=organization_id,
        model_name=model_name,
        model_type=model_type,
        start_date=start_date,
        end_date=end_date,
        test_size=test_size,
        random_state=random_state,
    )