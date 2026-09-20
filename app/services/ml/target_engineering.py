"""
ANGELIX - Machine Learning Target Engineering

Creates transparent statistical targets from Angelix transaction data.

Current target:
    Transaction Anomaly

The anomaly target is NOT a confirmed fraud label or financial-risk
diagnosis. It identifies transactions whose observed amounts exhibit
statistical characteristics that may warrant review.

Responsibilities:
- Calculate transaction-level anomaly indicators
- Calculate z-score based signals
- Calculate IQR based signals
- Combine transparent statistical signals
- Generate normal/review labels
- Preserve evidence behind each generated label
- Validate whether a target is suitable for supervised learning
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Result classes
# ---------------------------------------------------------------------------

@dataclass
class TargetEngineeringResult:
    """
    Result produced by target engineering.
    """

    success: bool
    status: str
    message: str

    targets: pd.Series
    evidence: pd.DataFrame

    target_name: str = "anomaly_target"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "target_name": self.target_name,
            "targets": self.targets.tolist(),
            "evidence": self.evidence.to_dict(
                orient="records"
            ),
            "metadata": self.metadata or {},
        }


@dataclass
class TargetValidationResult:
    """
    Result produced when validating a supervised-learning target.
    """

    valid: bool
    message: str
    class_distribution: dict[str, int]
    class_count: int
    minimum_samples_per_class: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "message": self.message,
            "class_distribution": self.class_distribution,
            "class_count": self.class_count,
            "minimum_samples_per_class": (
                self.minimum_samples_per_class
            ),
        }


# ---------------------------------------------------------------------------
# Target Engineer
# ---------------------------------------------------------------------------

class FinancialTargetEngineer:
    """
    Generates transparent statistical anomaly targets.
    """

    TARGET_NAME = "anomaly_target"

    NORMAL_LABEL = "normal"
    REVIEW_LABEL = "review"

    MINIMUM_ROWS = 10
    MINIMUM_SAMPLES_PER_CLASS = 2

    Z_SCORE_THRESHOLD = 2.5

    def __init__(
        self,
        z_score_threshold: float | None = None,
    ) -> None:

        if z_score_threshold is not None:
            self.z_score_threshold = float(
                z_score_threshold
            )
        else:
            self.z_score_threshold = self.Z_SCORE_THRESHOLD

    # ------------------------------------------------------------------
    # Generate anomaly target
    # ------------------------------------------------------------------

    def generate_anomaly_targets(
        self,
        dataframe: pd.DataFrame,
    ) -> TargetEngineeringResult:
        """
        Generate transparent anomaly labels from transaction amounts.
        """

        if dataframe is None or dataframe.empty:
            return TargetEngineeringResult(
                success=False,
                status="empty",
                message="Cannot generate targets from an empty dataset.",
                targets=pd.Series(dtype="object"),
                evidence=pd.DataFrame(),
                metadata={},
            )

        if "amount" not in dataframe.columns:
            return TargetEngineeringResult(
                success=False,
                status="invalid_dataset",
                message="The dataset does not contain an amount column.",
                targets=pd.Series(dtype="object"),
                evidence=pd.DataFrame(),
                metadata={},
            )

        if len(dataframe) < self.MINIMUM_ROWS:
            return TargetEngineeringResult(
                success=False,
                status="insufficient_data",
                message=(
                    f"At least {self.MINIMUM_ROWS} transactions are "
                    "required for statistical target generation."
                ),
                targets=pd.Series(dtype="object"),
                evidence=pd.DataFrame(),
                metadata={
                    "row_count": len(dataframe),
                },
            )

        # --------------------------------------------------------------
        # Amount preparation
        # --------------------------------------------------------------

        amount_series = (
            pd.to_numeric(
                dataframe["amount"],
                errors="coerce",
            )
            .fillna(0.0)
            .astype(float)
        )

        absolute_amount = amount_series.abs()

        amount_mean = float(
            absolute_amount.mean()
        )

        amount_median = float(
            absolute_amount.median()
        )

        amount_std = float(
            absolute_amount.std(
                ddof=0
            )
        )

        # --------------------------------------------------------------
        # Z-score
        # --------------------------------------------------------------

        if (
            not np.isfinite(amount_std)
            or amount_std == 0.0
        ):
            z_scores = pd.Series(
                0.0,
                index=dataframe.index,
            )
        else:
            z_scores = (
                absolute_amount - amount_mean
            ) / amount_std

        z_scores = (
            z_scores
            .replace(
                [np.inf, -np.inf],
                0.0,
            )
            .fillna(0.0)
        )

        # --------------------------------------------------------------
        # IQR calculation
        # --------------------------------------------------------------

        q1 = float(
            absolute_amount.quantile(0.25)
        )

        q3 = float(
            absolute_amount.quantile(0.75)
        )

        iqr = float(q3 - q1)

        if not np.isfinite(iqr) or iqr == 0.0:
            lower_bound = q1
            upper_bound = q3

            iqr_signal = pd.Series(
                False,
                index=dataframe.index,
            )
        else:
            lower_bound = q1 - (
                1.5 * iqr
            )

            upper_bound = q3 + (
                1.5 * iqr
            )

            iqr_signal = (
                (absolute_amount < lower_bound)
                | (
                    absolute_amount
                    > upper_bound
                )
            )

        # --------------------------------------------------------------
        # Z-score signal
        # --------------------------------------------------------------

        z_score_signal = (
            z_scores.abs()
            >= self.z_score_threshold
        )

        # --------------------------------------------------------------
        # Combined anomaly signal
        # --------------------------------------------------------------

        anomaly_signal = (
            z_score_signal
            | iqr_signal
        )

        anomaly_score = (
            z_score_signal.astype(int)
            + iqr_signal.astype(int)
        )

        # --------------------------------------------------------------
        # Labels
        # --------------------------------------------------------------

        targets = pd.Series(
            np.where(
                anomaly_signal,
                self.REVIEW_LABEL,
                self.NORMAL_LABEL,
            ),
            index=dataframe.index,
            name=self.TARGET_NAME,
        )

        # --------------------------------------------------------------
        # Evidence
        # --------------------------------------------------------------

        evidence = pd.DataFrame(
            index=dataframe.index
        )

        if "id" in dataframe.columns:
            evidence["transaction_id"] = (
                dataframe["id"]
            )

        if "transaction_date" in dataframe.columns:
            evidence["transaction_date"] = (
                dataframe["transaction_date"]
            )

        if "description" in dataframe.columns:
            evidence["description"] = (
                dataframe["description"]
            )

        evidence["amount"] = amount_series

        evidence["absolute_amount"] = (
            absolute_amount
        )

        evidence["z_score"] = (
            z_scores.round(6)
        )

        evidence["z_score_signal"] = (
            z_score_signal
        )

        evidence["iqr_signal"] = (
            iqr_signal
        )

        evidence["anomaly_score"] = (
            anomaly_score
        )

        evidence["target"] = targets

        # --------------------------------------------------------------
        # Metadata
        # --------------------------------------------------------------

        normal_count = int(
            (
                targets
                == self.NORMAL_LABEL
            ).sum()
        )

        review_count = int(
            (
                targets
                == self.REVIEW_LABEL
            ).sum()
        )

        review_rate = (
            review_count / len(targets)
        ) * 100.0

        metadata = {
            "row_count": int(len(dataframe)),
            "amount_mean": amount_mean,
            "amount_median": amount_median,
            "amount_std": amount_std,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "z_score_threshold": (
                self.z_score_threshold
            ),
            "normal_count": normal_count,
            "review_count": review_count,
            "review_rate": review_rate,
        }

        return TargetEngineeringResult(
            success=True,
            status="success",
            message=(
                "Statistical anomaly targets generated successfully."
            ),
            targets=targets,
            evidence=evidence,
            target_name=self.TARGET_NAME,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Target validation
    # ------------------------------------------------------------------

    def validate_target(
        self,
        targets: pd.Series,
    ) -> TargetValidationResult:
        """
        Validate whether the target contains sufficient class variation
        for supervised learning.
        """

        if targets is None or targets.empty:
            return TargetValidationResult(
                valid=False,
                message="Target is empty.",
                class_distribution={},
                class_count=0,
                minimum_samples_per_class=(
                    self.MINIMUM_SAMPLES_PER_CLASS
                ),
            )

        clean_targets = (
            targets
            .dropna()
            .astype(str)
        )

        if clean_targets.empty:
            return TargetValidationResult(
                valid=False,
                message="Target contains no valid labels.",
                class_distribution={},
                class_count=0,
                minimum_samples_per_class=(
                    self.MINIMUM_SAMPLES_PER_CLASS
                ),
            )

        distribution = (
            clean_targets
            .value_counts()
            .to_dict()
        )

        class_count = len(distribution)

        if class_count < 2:
            return TargetValidationResult(
                valid=False,
                message=(
                    "At least two target classes are required."
                ),
                class_distribution={
                    str(key): int(value)
                    for key, value in distribution.items()
                },
                class_count=class_count,
                minimum_samples_per_class=(
                    self.MINIMUM_SAMPLES_PER_CLASS
                ),
            )

        insufficient_classes = {
            str(label): int(count)
            for label, count in distribution.items()
            if count < self.MINIMUM_SAMPLES_PER_CLASS
        }

        if insufficient_classes:
            return TargetValidationResult(
                valid=False,
                message=(
                    "Each target class must contain at least "
                    f"{self.MINIMUM_SAMPLES_PER_CLASS} samples. "
                    f"Insufficient classes: {insufficient_classes}"
                ),
                class_distribution={
                    str(key): int(value)
                    for key, value in distribution.items()
                },
                class_count=class_count,
                minimum_samples_per_class=(
                    self.MINIMUM_SAMPLES_PER_CLASS
                ),
            )

        return TargetValidationResult(
            valid=True,
            message=(
                "Target contains sufficient class variation "
                "for supervised learning."
            ),
            class_distribution={
                str(key): int(value)
                for key, value in distribution.items()
            },
            class_count=class_count,
            minimum_samples_per_class=(
                self.MINIMUM_SAMPLES_PER_CLASS
            ),
        )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def generate_anomaly_targets(
    dataframe: pd.DataFrame,
    z_score_threshold: float | None = None,
) -> TargetEngineeringResult:
    """
    Convenience wrapper for anomaly target generation.
    """

    engineer = FinancialTargetEngineer(
        z_score_threshold=z_score_threshold
    )

    return engineer.generate_anomaly_targets(
        dataframe
    )


def validate_anomaly_target(
    targets: pd.Series,
) -> TargetValidationResult:
    """
    Convenience wrapper for anomaly target validation.
    """

    engineer = FinancialTargetEngineer()

    return engineer.validate_target(
        targets
    )