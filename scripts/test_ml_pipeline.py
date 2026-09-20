"""
ANGELIX - Machine Learning Pipeline Validation

Validates the complete Angelix ML pipeline:

1. Load organization transactions
2. Build the ML dataset
3. Generate transaction features
4. Generate statistical anomaly targets
5. Validate the target
6. Train the anomaly model when possible
7. Display model metrics and feature importance

Run from the Angelix project root:

    python -u scripts/test_ml_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path


# ============================================================================
# Project path
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Application imports
# ============================================================================

from app import create_app

from app.services.ml.dataset_service import (
    FinancialDatasetService,
)

from app.services.ml.target_engineering import (
    FinancialTargetEngineer,
)

from app.services.ml.training_pipeline import (
    FinancialTrainingPipeline,
)


# ============================================================================
# Configuration
# ============================================================================

ORGANIZATION_ID = 6


# ============================================================================
# Formatting helpers
# ============================================================================

def print_section(number: int, title: str) -> None:
    print()
    print("=" * 72)
    print(f"{number}. {title}")
    print("=" * 72)


# ============================================================================
# Main
# ============================================================================

def main() -> int:

    print()
    print("=" * 72)
    print("ANGELIX MACHINE LEARNING PIPELINE VALIDATION")
    print("=" * 72)
    print(f"Organization ID: {ORGANIZATION_ID}")

    # ------------------------------------------------------------------------
    # Flask application
    # ------------------------------------------------------------------------

    app = create_app()

    with app.app_context():

        # --------------------------------------------------------------------
        # 1. Load financial dataset
        # --------------------------------------------------------------------

        print_section(
            1,
            "Loading Financial Dataset",
        )

        dataset_service = FinancialDatasetService()

        dataset_result = (
            dataset_service.build_training_dataset(
                organization_id=ORGANIZATION_ID,
            )
        )

        print(
            f"Transactions loaded: "
            f"{len(dataset_result.features)}"
        )

        print(
            f"Features generated: "
            f"{dataset_result.features.shape[1] 
            if not dataset_result.features.empty
            else 0}"
        )

        print(
            f"Feature rows: "
            f"{dataset_result.features.shape[0]}"
        )

        print(
            f"Dataset status: "
            f"{dataset_result.status}"
        )

        if not dataset_result.success:

            print()
            print(
                "Dataset loading failed:"
            )

            print(
                dataset_result.message
            )

            return 1

        # --------------------------------------------------------------------
        # 2. Dataset summary
        # --------------------------------------------------------------------

        print_section(
            2,
            "Transaction Dataset Summary",
        )

        metadata = (
            dataset_result.metadata
            or {}
        )

        print(
            f"Total transactions: "
            f"{metadata.get('total_transactions', 0)}"
        )

        print(
            f"Income transactions: "
            f"{metadata.get('income_transactions', 0)}"
        )

        print(
            f"Expense transactions: "
            f"{metadata.get('expense_transactions', 0)}"
        )

        print(
            f"Categorized transactions: "
            f"{metadata.get('categorized_transactions', 0)}"
        )

        print(
            f"Uncategorized transactions: "
            f"{metadata.get('uncategorized_transactions', 0)}"
        )

        transaction_distribution = (
            metadata.get(
                "transaction_type_distribution",
                {},
            )
        )

        if transaction_distribution:

            print()
            print(
                "Transaction type distribution:"
            )

            for transaction_type, count in (
                transaction_distribution.items()
            ):
                print(
                    f"  - {transaction_type}: "
                    f"{count}"
                )

        # --------------------------------------------------------------------
        # 3. Statistical anomaly target
        # --------------------------------------------------------------------

        print_section(
            3,
            "Generating Statistical Anomaly Targets",
        )

        target_engineer = (
            FinancialTargetEngineer()
        )

        target_result = (
            target_engineer.generate_anomaly_targets(
                dataset_result.features
            )
        )

        print(
            f"Target name: "
            f"{target_result.target_name}"
        )

        print(
            f"Target status: "
            f"{target_result.status}"
        )

        if not target_result.success:

            print()
            print(
                "Target generation failed:"
            )

            print(
                target_result.message
            )

            return 1

        target_metadata = (
            target_result.metadata
            or {}
        )

        print(
            f"Normal transactions: "
            f"{target_metadata.get('normal_count', 0)}"
        )

        print(
            f"Transactions requiring review: "
            f"{target_metadata.get('review_count', 0)}"
        )

        print(
            f"Review rate: "
            f"{target_metadata.get('review_rate', 0):.2f}%"
        )

        # --------------------------------------------------------------------
        # 4. Target class distribution
        # --------------------------------------------------------------------

        print_section(
            4,
            "Target Class Distribution",
        )

        target_distribution = (
            target_result.targets
            .value_counts()
            .to_dict()
        )

        for label, count in (
            target_distribution.items()
        ):

            print(
                f"{label}: {count}"
            )

        # --------------------------------------------------------------------
        # 5. Target validation
        # --------------------------------------------------------------------

        print_section(
            5,
            "Target Validation",
        )

        validation_result = (
            target_engineer.validate_target(
                target_result.targets
            )
        )

        if validation_result.valid:

            print(
                "Target validation: PASSED"
            )

            print(
                f"Classes detected: "
                f"{validation_result.class_count}"
            )

        else:

            print(
                "Target validation: FAILED"
            )

            print(
                f"  - "
                f"{validation_result.message}"
            )

        # --------------------------------------------------------------------
        # 6. Generated features
        # --------------------------------------------------------------------

        print_section(
            6,
            "Generated ML Features",
        )

        for column in (
            dataset_result.features.columns
        ):

            print(
                f"  - {column}"
            )

        # --------------------------------------------------------------------
        # 7. Stop if target is not trainable
        # --------------------------------------------------------------------

        if not validation_result.valid:

            print_section(
                7,
                "Model Training",
            )

            print(
                "Model training was skipped because "
                "the generated target is not suitable "
                "for supervised learning."
            )

            print()
            print(
                "This is expected when the current dataset "
                "does not contain enough observations in "
                "both target classes."
            )

            print()
            print("=" * 72)
            print(
                "ML PIPELINE VALIDATION COMPLETED"
            )
            print("=" * 72)

            return 0

        # --------------------------------------------------------------------
        # 8. Model training
        # --------------------------------------------------------------------

        print_section(
            7,
            "Model Training",
        )

        pipeline = (
            FinancialTrainingPipeline()
        )

        training_result = (
            pipeline.train_for_organization(
                organization_id=ORGANIZATION_ID,
            )
        )

        print(
            f"Training status: "
            f"{training_result.status}"
        )

        print(
            f"Training message: "
            f"{training_result.message}"
        )

        if not training_result.success:

            print()
            print(
                "Model training failed."
            )

            return 1

        # --------------------------------------------------------------------
        # 9. Model metrics
        # --------------------------------------------------------------------

        print_section(
            8,
            "Model Performance",
        )

        metrics = (
            training_result.metrics
            or {}
        )

        print(
            f"Accuracy: "
            f"{metrics.get('accuracy', 0):.4f}"
        )

        print(
            f"Precision: "
            f"{metrics.get('weighted_precision', 0):.4f}"
        )

        print(
            f"Recall: "
            f"{metrics.get('weighted_recall', 0):.4f}"
        )

        print(
            f"F1 Score: "
            f"{metrics.get('weighted_f1', 0):.4f}"
        )

        # --------------------------------------------------------------------
        # 10. Feature importance
        # --------------------------------------------------------------------

        print_section(
            9,
            "Feature Importance",
        )

        feature_importance = (
            training_result.feature_importance
            or {}
        )

        if feature_importance:

            sorted_features = sorted(
                feature_importance.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            for feature_name, importance in (
                sorted_features[:15]
            ):

                print(
                    f"{feature_name:<35} "
                    f"{importance:.6f}"
                )

        else:

            print(
                "Feature importance was not available."
            )

        # --------------------------------------------------------------------
        # 11. Saved model
        # --------------------------------------------------------------------

        print_section(
            10,
            "Saved Model",
        )

        print(
            f"Model name: "
            f"{training_result.model_name}"
        )

        print(
            f"Model version: "
            f"{training_result.model_version}"
        )

        print(
            f"Model path: "
            f"{training_result.model_path}"
        )

        print(
            f"Metadata path: "
            f"{training_result.metadata_path}"
        )

        # --------------------------------------------------------------------
        # Final
        # --------------------------------------------------------------------

        print()
        print("=" * 72)
        print(
            "ANGELIX ML PIPELINE VALIDATION COMPLETED SUCCESSFULLY"
        )
        print("=" * 72)

        return 0


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    raise SystemExit(main())