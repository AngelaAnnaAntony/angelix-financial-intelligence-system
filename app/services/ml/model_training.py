"""
ANGELIX - Machine Learning Model Training Service

This module provides the model-training pipeline for Angelix.

Responsibilities:
- Prepare ML datasets
- Split data into training and testing sets
- Train supported classification models
- Evaluate trained models
- Compare model performance
- Return trained model artifacts
- Provide reproducible training

Current models:
- Logistic Regression
- Random Forest
- Gradient Boosting

The module is intentionally independent from Flask routes and templates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TEST_SIZE = 0.20
DEFAULT_RANDOM_STATE = 42
DEFAULT_MINIMUM_ROWS = 10

SUPPORTED_MODELS = (
    "logistic_regression",
    "random_forest",
    "gradient_boosting",
)


# ---------------------------------------------------------------------------
# Training result
# ---------------------------------------------------------------------------

@dataclass
class ModelTrainingResult:
    """
    Stores the complete result of a model-training operation.
    """

    model_name: str
    model: Any
    feature_names: list[str]
    target_name: str
    metrics: dict[str, Any]
    classes: list[Any]
    training_rows: int
    testing_rows: int
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Model training service
# ---------------------------------------------------------------------------

class FinancialModelTrainer:
    """
    Machine-learning model training service for ANGELIX.

    The trainer accepts an already prepared feature matrix and target vector.

    This makes the service reusable for:
        - transaction classification
        - financial risk classification
        - anomaly-related classification
        - future supervised ML tasks
    """

    def __init__(
        self,
        random_state: int = DEFAULT_RANDOM_STATE,
    ) -> None:
        self.random_state = random_state

    # -----------------------------------------------------------------------
    # Public training API
    # -----------------------------------------------------------------------

    def train(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        model_name: str = "random_forest",
        target_name: str = "target",
        test_size: float = DEFAULT_TEST_SIZE,
    ) -> ModelTrainingResult:
        """
        Train and evaluate a classification model.

        Parameters:
            features:
                Numerical ML feature matrix.

            target:
                Classification target.

            model_name:
                One of the supported model identifiers.

            target_name:
                Human-readable target name.

            test_size:
                Fraction of the dataset reserved for testing.

        Returns:
            ModelTrainingResult
        """

        model_name = self._normalize_model_name(
            model_name
        )

        X, y = self._prepare_data(
            features=features,
            target=target,
        )

        self._validate_training_data(
            X=X,
            y=y,
            test_size=test_size,
        )

        X_train, X_test, y_train, y_test = (
            self._split_data(
                X=X,
                y=y,
                test_size=test_size,
            )
        )

        pipeline = self._build_model_pipeline(
            model_name
        )

        pipeline.fit(
            X_train,
            y_train,
        )

        predictions = pipeline.predict(
            X_test
        )

        metrics = self._evaluate_model(
            y_true=y_test,
            y_pred=predictions,
        )

        classes = self._get_classes(
            y
        )

        return ModelTrainingResult(
            model_name=model_name,
            model=pipeline,
            feature_names=list(X.columns),
            target_name=target_name,
            metrics=metrics,
            classes=classes,
            training_rows=len(X_train),
            testing_rows=len(X_test),
            metadata={
                "random_state": self.random_state,
                "test_size": test_size,
                "total_rows": len(X),
                "feature_count": len(X.columns),
                "class_count": len(classes),
            },
        )

    # -----------------------------------------------------------------------
    # Train all supported models
    # -----------------------------------------------------------------------

    def train_all_models(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        target_name: str = "target",
        test_size: float = DEFAULT_TEST_SIZE,
    ) -> dict[str, ModelTrainingResult]:
        """
        Train all supported classification models.

        Returns:
            Dictionary keyed by model name.
        """

        results: dict[str, ModelTrainingResult] = {}

        for model_name in SUPPORTED_MODELS:
            try:
                results[model_name] = self.train(
                    features=features,
                    target=target,
                    model_name=model_name,
                    target_name=target_name,
                    test_size=test_size,
                )
            except ValueError:
                raise
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to train {model_name}: {exc}"
                ) from exc

        return results

    # -----------------------------------------------------------------------
    # Data preparation
    # -----------------------------------------------------------------------

    @staticmethod
    def _prepare_data(
        features: pd.DataFrame,
        target: pd.Series,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Clean and normalize feature and target inputs.
        """

        if not isinstance(features, pd.DataFrame):
            raise TypeError(
                "features must be a pandas DataFrame."
            )

        if not isinstance(target, pd.Series):
            target = pd.Series(target)

        X = features.copy()
        y = target.copy()

        if len(X) != len(y):
            raise ValueError(
                "Feature and target row counts must match."
            )

        # Remove completely empty feature columns.
        X = X.dropna(
            axis=1,
            how="all",
        )

        # Convert feature columns to numeric.
        for column in X.columns:
            X[column] = pd.to_numeric(
                X[column],
                errors="coerce",
            )

        # Replace infinite values.
        X = X.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # Remove rows where the target is missing.
        valid_target_mask = y.notna()

        X = X.loc[
            valid_target_mask
        ].reset_index(drop=True)

        y = y.loc[
            valid_target_mask
        ].reset_index(drop=True)

        # Normalize target labels.
        y = y.astype(str).str.strip()

        return X, y

    # -----------------------------------------------------------------------
    # Dataset validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_training_data(
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float,
    ) -> None:
        """
        Validate data before model training.
        """

        if X.empty:
            raise ValueError(
                "Cannot train a model with an empty feature matrix."
            )

        if len(X) < DEFAULT_MINIMUM_ROWS:
            raise ValueError(
                f"At least {DEFAULT_MINIMUM_ROWS} rows are required "
                "for model training."
            )

        if len(X.columns) == 0:
            raise ValueError(
                "No usable ML features are available."
            )

        if y.empty:
            raise ValueError(
                "The target dataset is empty."
            )

        unique_classes = y.nunique()

        if unique_classes < 2:
            raise ValueError(
                "Classification requires at least two target classes."
            )

        if not 0 < test_size < 1:
            raise ValueError(
                "test_size must be between 0 and 1."
            )

        class_counts = y.value_counts()

        if class_counts.min() < 2:
            raise ValueError(
                "Each target class must contain at least two samples "
                "for a stratified train/test split."
            )

    # -----------------------------------------------------------------------
    # Train/test split
    # -----------------------------------------------------------------------

    def _split_data(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float,
    ) -> tuple[
        pd.DataFrame,
        pd.DataFrame,
        pd.Series,
        pd.Series,
    ]:
        """
        Split the dataset using stratification when possible.
        """

        try:
            return train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=self.random_state,
                stratify=y,
            )
        except ValueError as exc:
            raise ValueError(
                "Unable to create a valid stratified train/test split. "
                f"Dataset may be too small or imbalanced: {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Model construction
    # -----------------------------------------------------------------------

    def _build_model_pipeline(
        self,
        model_name: str,
    ) -> Pipeline:
        """
        Build the preprocessing + model pipeline.
        """

        if model_name == "logistic_regression":
            estimator = LogisticRegression(
                max_iter=2000,
                random_state=self.random_state,
            )

            return Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        ),
                    ),
                    (
                        "scaler",
                        StandardScaler(),
                    ),
                    (
                        "model",
                        estimator,
                    ),
                ]
            )

        if model_name == "random_forest":
            estimator = RandomForestClassifier(
                n_estimators=200,
                max_depth=None,
                min_samples_split=2,
                min_samples_leaf=1,
                random_state=self.random_state,
                n_jobs=-1,
                class_weight="balanced",
            )

            return Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        ),
                    ),
                    (
                        "model",
                        estimator,
                    ),
                ]
            )

        if model_name == "gradient_boosting":
            estimator = GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=3,
                random_state=self.random_state,
            )

            return Pipeline(
                steps=[
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median"
                        ),
                    ),
                    (
                        "model",
                        estimator,
                    ),
                ]
            )

        raise ValueError(
            f"Unsupported model: {model_name}"
        )

    # -----------------------------------------------------------------------
    # Model evaluation
    # -----------------------------------------------------------------------

    @staticmethod
    def _evaluate_model(
        y_true: pd.Series,
        y_pred: np.ndarray,
    ) -> dict[str, Any]:
        """
        Calculate classification evaluation metrics.
        """

        accuracy = accuracy_score(
            y_true,
            y_pred,
        )

        precision = precision_score(
            y_true,
            y_pred,
            average="weighted",
            zero_division=0,
        )

        recall = recall_score(
            y_true,
            y_pred,
            average="weighted",
            zero_division=0,
        )

        f1 = f1_score(
            y_true,
            y_pred,
            average="weighted",
            zero_division=0,
        )

        labels = sorted(
            set(y_true.astype(str))
            | set(y_pred.astype(str))
        )

        matrix = confusion_matrix(
            y_true,
            y_pred,
            labels=labels,
        )

        report = classification_report(
            y_true,
            y_pred,
            labels=labels,
            output_dict=True,
            zero_division=0,
        )

        return {
            "accuracy": float(accuracy),
            "precision_weighted": float(precision),
            "recall_weighted": float(recall),
            "f1_weighted": float(f1),
            "confusion_matrix": matrix.tolist(),
            "classification_report": report,
        }

    # -----------------------------------------------------------------------
    # Model name normalization
    # -----------------------------------------------------------------------

    @staticmethod
    def _normalize_model_name(
        model_name: str,
    ) -> str:
        """
        Normalize model identifiers.
        """

        if not isinstance(model_name, str):
            raise TypeError(
                "model_name must be a string."
            )

        normalized = (
            model_name
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        aliases = {
            "logistic": "logistic_regression",
            "lr": "logistic_regression",
            "randomforest": "random_forest",
            "rf": "random_forest",
            "gradientboosting": "gradient_boosting",
            "gb": "gradient_boosting",
        }

        normalized = aliases.get(
            normalized,
            normalized,
        )

        if normalized not in SUPPORTED_MODELS:
            supported = ", ".join(
                SUPPORTED_MODELS
            )

            raise ValueError(
                f"Unsupported model '{model_name}'. "
                f"Supported models: {supported}"
            )

        return normalized

    # -----------------------------------------------------------------------
    # Classes
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_classes(
        target: pd.Series,
    ) -> list[Any]:
        """
        Return stable sorted target classes.
        """

        return sorted(
            target.astype(str).unique().tolist()
        )

    # -----------------------------------------------------------------------
    # Feature importance
    # -----------------------------------------------------------------------

    @staticmethod
    def get_feature_importance(
        training_result: ModelTrainingResult,
    ) -> dict[str, float]:
        """
        Extract feature importance from supported tree-based models.

        Logistic regression uses coefficient magnitude instead.
        """

        model_pipeline = training_result.model

        estimator = model_pipeline.named_steps.get(
            "model"
        )

        if estimator is None:
            return {}

        feature_names = training_result.feature_names

        if hasattr(
            estimator,
            "feature_importances_",
        ):
            importance = estimator.feature_importances_

        elif hasattr(
            estimator,
            "coef_",
        ):
            coefficients = np.asarray(
                estimator.coef_
            )

            if coefficients.ndim == 1:
                importance = np.abs(
                    coefficients
                )
            else:
                importance = np.mean(
                    np.abs(coefficients),
                    axis=0,
                )

        else:
            return {}

        if len(importance) != len(feature_names):
            return {}

        return {
            feature_name: float(value)
            for feature_name, value in zip(
                feature_names,
                importance,
            )
        }


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def train_financial_model(
    features: pd.DataFrame,
    target: pd.Series,
    model_name: str = "random_forest",
    target_name: str = "target",
    test_size: float = DEFAULT_TEST_SIZE,
) -> ModelTrainingResult:
    """
    Convenience wrapper for training one financial ML model.
    """

    trainer = FinancialModelTrainer()

    return trainer.train(
        features=features,
        target=target,
        model_name=model_name,
        target_name=target_name,
        test_size=test_size,
    )