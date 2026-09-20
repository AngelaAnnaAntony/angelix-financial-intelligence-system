"""
ANGELIX - Supervised Accounting ML Prediction Test

Tests the installed accounting classifiers inside a Flask application
context so the database-backed FinancialDatasetService can access
SQLAlchemy safely.
"""

from __future__ import annotations

import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from app import create_app
from app.services.ml.prediction_service import (
    FinancialPredictionService,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORGANIZATION_ID = 6


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def print_prediction(
    description: str,
    result: dict,
) -> None:

    print()
    print("-" * 70)
    print(f"Transaction : {description}")
    print("-" * 70)

    if not result.get("success"):

        print(
            f"Status  : {result.get('status')}"
        )

        print(
            f"Message : {result.get('message')}"
        )

        return

    print(
        f"Account Type       : "
        f"{result.get('account_type')}"
    )

    print(
        f"Account Confidence : "
        f"{result.get('account_confidence')}"
    )

    print(
        f"Debit/Credit       : "
        f"{result.get('debit_credit')}"
    )

    print(
        f"D/C Confidence     : "
        f"{result.get('debit_credit_confidence')}"
    )

    models = result.get(
        "models",
        {},
    )

    account_model = models.get(
        "account_type",
        {},
    )

    debit_credit_model = models.get(
        "debit_credit",
        {},
    )

    print()

    print(
        "Account Model      : "
        f"{account_model.get('name')} "
        f"v{account_model.get('version')}"
    )

    print(
        "Debit/Credit Model : "
        f"{debit_credit_model.get('name')} "
        f"v{debit_credit_model.get('version')}"
    )


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def main():

    print()
    print("=" * 70)
    print("ANGELIX - SUPERVISED ACCOUNTING ML PREDICTION TEST")
    print("=" * 70)
    print()

    print(
        f"Organization ID : {ORGANIZATION_ID}"
    )

    print()

    # --------------------------------------------------------------
    # Create Flask application.
    #
    # FinancialDatasetService accesses SQLAlchemy, so prediction
    # tests that query the database must run inside app.app_context().
    # --------------------------------------------------------------

    app = create_app()

    with app.app_context():

        service = FinancialPredictionService()

        # ----------------------------------------------------------
        # Test 1 - Existing ANGELIX transaction dataset
        # ----------------------------------------------------------

        print(
            "TEST 1 - Existing ANGELIX Transactions"
        )

        print("-" * 70)

        result = service.predict_for_organization(
            organization_id=ORGANIZATION_ID,
            model_name="account_type_classifier",
        )

        if not result.success:

            print(
                "[FAILED]"
            )

            print(
                f"Status  : {result.status}"
            )

            print(
                f"Message : {result.message}"
            )

        else:

            print(
                "[SUCCESS]"
            )

            print(
                f"Transactions predicted : "
                f"{len(result.predictions)}"
            )

            print(
                f"Model                  : "
                f"{result.model_name}"
            )

            print(
                f"Model version          : "
                f"{result.model_version}"
            )

            print()

            print(
                "First 10 predictions:"
            )

            for index, prediction in enumerate(
                result.predictions[:10],
                start=1,
            ):

                position = index - 1

                if position < len(
                    result.confidence_scores
                ):

                    confidence = (
                        result.confidence_scores[
                            position
                        ]
                    )

                    print(
                        f"  {index:02d}. "
                        f"{prediction} "
                        f"(confidence={confidence:.4f})"
                    )

                else:

                    print(
                        f"  {index:02d}. "
                        f"{prediction}"
                    )

        # ----------------------------------------------------------
        # Test 2 - Office electricity bill
        # ----------------------------------------------------------

        print()
        print(
            "TEST 2 - Office Electricity Bill"
        )

        electricity_result = (
            service.predict_accounting_transaction(
                organization_id=ORGANIZATION_ID,
                description="Office electricity bill",
                amount=5000,
                is_recurring=False,
                source="Manual",
                transaction_date="2026-09-17",
            )
        )

        print_prediction(
            "Office electricity bill",
            electricity_result,
        )

        # ----------------------------------------------------------
        # Test 3 - Customer revenue
        # ----------------------------------------------------------

        print()
        print(
            "TEST 3 - Customer Revenue"
        )

        revenue_result = (
            service.predict_accounting_transaction(
                organization_id=ORGANIZATION_ID,
                description=(
                    "Customer payment for consulting services"
                ),
                amount=75000,
                is_recurring=False,
                source="Bank",
                transaction_date="2026-09-18",
            )
        )

        print_prediction(
            "Customer payment for consulting services",
            revenue_result,
        )

        # ----------------------------------------------------------
        # Test 4 - Asset purchase
        # ----------------------------------------------------------

        print()
        print(
            "TEST 4 - Office Laptop Purchase"
        )

        asset_result = (
            service.predict_accounting_transaction(
                organization_id=ORGANIZATION_ID,
                description="Purchase of office laptop",
                amount=85000,
                is_recurring=False,
                source="Bank",
                transaction_date="2026-09-19",
            )
        )

        print_prediction(
            "Purchase of office laptop",
            asset_result,
        )

        # ----------------------------------------------------------
        # Test 5 - Business loan
        # ----------------------------------------------------------

        print()
        print(
            "TEST 5 - Business Loan"
        )

        liability_result = (
            service.predict_accounting_transaction(
                organization_id=ORGANIZATION_ID,
                description="Business loan received",
                amount=500000,
                is_recurring=False,
                source="Bank",
                transaction_date="2026-09-19",
            )
        )

        print_prediction(
            "Business loan received",
            liability_result,
        )

        # ----------------------------------------------------------
        # Test 6 - Owner capital
        # ----------------------------------------------------------

        print()
        print(
            "TEST 6 - Owner Capital"
        )

        equity_result = (
            service.predict_accounting_transaction(
                organization_id=ORGANIZATION_ID,
                description="Owner capital introduced",
                amount=300000,
                is_recurring=False,
                source="Bank",
                transaction_date="2026-09-19",
            )
        )

        print_prediction(
            "Owner capital introduced",
            equity_result,
        )

    # ------------------------------------------------------------------
    # Final message
    # ------------------------------------------------------------------

    print()
    print("=" * 70)
    print("ACCOUNTING ML PREDICTION TEST COMPLETED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
