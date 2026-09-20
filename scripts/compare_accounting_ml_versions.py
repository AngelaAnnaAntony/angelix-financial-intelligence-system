"""
ANGELIX - Accounting ML Model Version Comparison

Compares:
    - Currently active Angelix v2 models
    - Newly enhanced v3 models

This script ONLY evaluates the models.

It does NOT:
    - install models
    - replace active models
    - modify the database
    - modify Angelix application code
"""

from pathlib import Path
import sys

import joblib
import pandas as pd

def description_to_text(data):
    """
    Convert the selected description column into
    a one-dimensional sequence of strings.

    This function must exist when loading the v3
    joblib models because it was used by their
    training pipeline.
    """
    return (
        data.iloc[:, 0]
        .fillna("")
        .astype(str)
    )

# ============================================================================
# PROJECT PATHS
# ============================================================================

# scripts/compare_accounting_ml_versions.py
# parents[0] = scripts
# parents[1] = angelix project root

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ML_ROOT = (
    PROJECT_ROOT
    / "ANGELIX_Supervised_Accounting_ML"
)

V3_MODEL_DIR = ML_ROOT / "models"

# v2 models are the models currently installed for Organization 6.
V2_MODEL_DIR = (
    PROJECT_ROOT
    / "instance"
    / "ml_models"
    / "organization_6"
)


# ============================================================================
# MODEL FILES
# ============================================================================

MODEL_FILES = {
    "account_v2": (
        V2_MODEL_DIR
        / "account_type_classifier_v2.joblib"
    ),

    "account_v3": (
        V3_MODEL_DIR
        / "account_type_classifier_v3.joblib"
    ),

    "dc_v2": (
        V2_MODEL_DIR
        / "debit_credit_classifier_v2.joblib"
    ),

    "dc_v3": (
        V3_MODEL_DIR
        / "debit_credit_classifier_v3.joblib"
    ),
}


# ============================================================================
# REPRESENTATIVE ACCOUNTING TRANSACTIONS
# ============================================================================

TEST_TRANSACTIONS = [
    {
        "name": "Office Electricity Bill",
        "description": "Office electricity bill",
        "amount": 5000,
        "is_recurring": True,
        "source": "manual",
        "month": 9,
        "expected_account": "expense",
        "expected_dc": "debit",
    },
    {
        "name": "Customer Revenue",
        "description": "Customer payment for consulting services",
        "amount": 75000,
        "is_recurring": False,
        "source": "manual",
        "month": 9,
        "expected_account": "revenue",
        "expected_dc": "credit",
    },
    {
        "name": "Office Laptop Purchase",
        "description": "Purchase of office laptop",
        "amount": 85000,
        "is_recurring": False,
        "source": "manual",
        "month": 9,
        "expected_account": "asset",
        "expected_dc": "debit",
    },
    {
        "name": "Business Loan",
        "description": "Business loan received",
        "amount": 500000,
        "is_recurring": False,
        "source": "manual",
        "month": 9,
        "expected_account": "liability",
        "expected_dc": "credit",
    },
    {
        "name": "Owner Capital",
        "description": "Owner capital introduced",
        "amount": 250000,
        "is_recurring": False,
        "source": "manual",
        "month": 9,
        "expected_account": "equity",
        "expected_dc": "credit",
    },
    {
        "name": "Stationery Items",
        "description": "Purchase of office stationery items",
        "amount": 2500,
        "is_recurring": False,
        "source": "manual",
        "month": 9,
        "expected_account": "expense",
        "expected_dc": "debit",
    },
]


# ============================================================================
# HELPERS
# ============================================================================

def build_features(transaction):
    """
    Build the exact feature structure expected by the
    trained accounting models.
    """

    return pd.DataFrame(
        [
            {
                "description": transaction["description"],
                "amount": transaction["amount"],
                "is_recurring": transaction["is_recurring"],
                "source": transaction["source"],
                "month": transaction["month"],
            }
        ]
    )


def predict(model, features):
    """
    Generate a prediction and confidence score.
    """

    prediction = model.predict(features)[0]

    confidence = None

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)[0]
        confidence = float(max(probabilities))

    return prediction, confidence


def format_confidence(value):
    """
    Format a probability as a percentage.
    """

    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 78)
    print("ANGELIX - ACCOUNTING ML V2 vs V3 COMPARISON")
    print("=" * 78)

    # ------------------------------------------------------------------------
    # Display paths
    # ------------------------------------------------------------------------

    print("\nModel locations:")
    print("-" * 78)

    print(f"V2 models:")
    print(f"  {V2_MODEL_DIR}")

    print(f"\nV3 models:")
    print(f"  {V3_MODEL_DIR}")

    # ------------------------------------------------------------------------
    # Check model files
    # ------------------------------------------------------------------------

    print("\n")
    print("=" * 78)
    print("CHECKING MODEL FILES")
    print("=" * 78)

    missing_models = []

    for model_name, model_path in MODEL_FILES.items():

        if model_path.exists():
            print(
                f"[FOUND]   {model_name:<12} "
                f"{model_path}"
            )
        else:
            print(
                f"[MISSING] {model_name:<12} "
                f"{model_path}"
            )
            missing_models.append(model_name)

    if missing_models:

        print("\n")
        print("ERROR: Required model files are missing.")

        print("\nMissing:")
        for model_name in missing_models:
            print(f"  - {model_name}")

        print(
            "\nNo models were modified or installed."
        )

        sys.exit(1)

    # ------------------------------------------------------------------------
    # Load models
    # ------------------------------------------------------------------------

    print("\n")
    print("=" * 78)
    print("LOADING MODELS")
    print("=" * 78)

    try:

        account_v2 = joblib.load(
            MODEL_FILES["account_v2"]
        )

        account_v3 = joblib.load(
            MODEL_FILES["account_v3"]
        )

        dc_v2 = joblib.load(
            MODEL_FILES["dc_v2"]
        )

        dc_v3 = joblib.load(
            MODEL_FILES["dc_v3"]
        )

    except Exception as exc:

        print(
            f"\nERROR while loading models:\n{exc}"
        )

        sys.exit(1)

    print("[SUCCESS] All four models loaded successfully.")

    # ------------------------------------------------------------------------
    # Store results
    # ------------------------------------------------------------------------

    results = []

    # ------------------------------------------------------------------------
    # Test each transaction
    # ------------------------------------------------------------------------

    print("\n")
    print("=" * 78)
    print("REPRESENTATIVE TRANSACTION COMPARISON")
    print("=" * 78)

    for transaction in TEST_TRANSACTIONS:

        features = build_features(transaction)

        # ------------------------------------------------------------
        # Account Type
        # ------------------------------------------------------------

        account_prediction_v2, account_confidence_v2 = predict(
            account_v2,
            features,
        )

        account_prediction_v3, account_confidence_v3 = predict(
            account_v3,
            features,
        )

        # ------------------------------------------------------------
        # Debit / Credit
        # ------------------------------------------------------------

        dc_prediction_v2, dc_confidence_v2 = predict(
            dc_v2,
            features,
        )

        dc_prediction_v3, dc_confidence_v3 = predict(
            dc_v3,
            features,
        )

        # ------------------------------------------------------------
        # Correctness
        # ------------------------------------------------------------

        account_v2_correct = (
            account_prediction_v2
            == transaction["expected_account"]
        )

        account_v3_correct = (
            account_prediction_v3
            == transaction["expected_account"]
        )

        dc_v2_correct = (
            dc_prediction_v2
            == transaction["expected_dc"]
        )

        dc_v3_correct = (
            dc_prediction_v3
            == transaction["expected_dc"]
        )

        # ------------------------------------------------------------
        # Save result
        # ------------------------------------------------------------

        results.append(
            {
                "Transaction": transaction["name"],

                "Expected Account": (
                    transaction["expected_account"]
                ),

                "V2 Account": account_prediction_v2,

                "V2 Account Confidence": (
                    account_confidence_v2
                ),

                "V3 Account": account_prediction_v3,

                "V3 Account Confidence": (
                    account_confidence_v3
                ),

                "Expected D/C": (
                    transaction["expected_dc"]
                ),

                "V2 D/C": dc_prediction_v2,

                "V2 D/C Confidence": (
                    dc_confidence_v2
                ),

                "V3 D/C": dc_prediction_v3,

                "V3 D/C Confidence": (
                    dc_confidence_v3
                ),

                "V2 Account Correct": (
                    account_v2_correct
                ),

                "V3 Account Correct": (
                    account_v3_correct
                ),

                "V2 D/C Correct": (
                    dc_v2_correct
                ),

                "V3 D/C Correct": (
                    dc_v3_correct
                ),
            }
        )

        # ------------------------------------------------------------
        # Display result
        # ------------------------------------------------------------

        print("\n")
        print(transaction["name"])
        print("-" * 78)

        print(
            f"Expected Account : "
            f"{transaction['expected_account']}"
        )

        print(
            f"V2 Account       : "
            f"{account_prediction_v2} "
            f"({format_confidence(account_confidence_v2)})"
        )

        print(
            f"V3 Account       : "
            f"{account_prediction_v3} "
            f"({format_confidence(account_confidence_v3)})"
        )

        print()

        print(
            f"Expected D/C     : "
            f"{transaction['expected_dc']}"
        )

        print(
            f"V2 D/C           : "
            f"{dc_prediction_v2} "
            f"({format_confidence(dc_confidence_v2)})"
        )

        print(
            f"V3 D/C           : "
            f"{dc_prediction_v3} "
            f"({format_confidence(dc_confidence_v3)})"
        )

    # =========================================================================
    # SUMMARY
    # =========================================================================

    results_df = pd.DataFrame(results)

    total = len(results_df)

    v2_account_correct = int(
        results_df["V2 Account Correct"].sum()
    )

    v3_account_correct = int(
        results_df["V3 Account Correct"].sum()
    )

    v2_dc_correct = int(
        results_df["V2 D/C Correct"].sum()
    )

    v3_dc_correct = int(
        results_df["V3 D/C Correct"].sum()
    )

    # ------------------------------------------------------------------------
    # Accuracy
    # ------------------------------------------------------------------------

    v2_account_accuracy = (
        v2_account_correct / total
    )

    v3_account_accuracy = (
        v3_account_correct / total
    )

    v2_dc_accuracy = (
        v2_dc_correct / total
    )

    v3_dc_accuracy = (
        v3_dc_correct / total
    )

    # ------------------------------------------------------------------------
    # Average confidence
    # ------------------------------------------------------------------------

    avg_account_v2 = (
        results_df["V2 Account Confidence"].mean()
    )

    avg_account_v3 = (
        results_df["V3 Account Confidence"].mean()
    )

    avg_dc_v2 = (
        results_df["V2 D/C Confidence"].mean()
    )

    avg_dc_v3 = (
        results_df["V3 D/C Confidence"].mean()
    )

    # =========================================================================
    # PRINT SUMMARY
    # =========================================================================

    print("\n")
    print("=" * 78)
    print("COMPARISON SUMMARY")
    print("=" * 78)

    print("\nAccount Type Accuracy:")
    print(
        f"V2 : {v2_account_correct}/{total} "
        f"({v2_account_accuracy * 100:.2f}%)"
    )
    print(
        f"V3 : {v3_account_correct}/{total} "
        f"({v3_account_accuracy * 100:.2f}%)"
    )

    print("\nDebit / Credit Accuracy:")
    print(
        f"V2 : {v2_dc_correct}/{total} "
        f"({v2_dc_accuracy * 100:.2f}%)"
    )
    print(
        f"V3 : {v3_dc_correct}/{total} "
        f"({v3_dc_accuracy * 100:.2f}%)"
    )

    print("\nAverage Account-Type Confidence:")
    print(
        f"V2 : {avg_account_v2 * 100:.2f}%"
    )
    print(
        f"V3 : {avg_account_v3 * 100:.2f}%"
    )

    print("\nAverage Debit/Credit Confidence:")
    print(
        f"V2 : {avg_dc_v2 * 100:.2f}%"
    )
    print(
        f"V3 : {avg_dc_v3 * 100:.2f}%"
    )

    # =========================================================================
    # SAVE COMPARISON
    # =========================================================================

    output_path = (
        ML_ROOT
        / "data"
        / "accounting_ml_v2_v3_comparison.csv"
    )

    results_df.to_csv(
        output_path,
        index=False,
    )

    print("\n")
    print("=" * 78)
    print("COMPARISON COMPLETED")
    print("=" * 78)

    print(
        f"\nDetailed comparison saved to:"
        f"\n{output_path}"
    )

    print("\nIMPORTANT:")
    print("  - No model was installed.")
    print("  - No model was replaced.")
    print("  - v2 remains the active Angelix model.")
    print("  - v3 remains an evaluation candidate.")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()