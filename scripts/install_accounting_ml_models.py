"""
ANGELIX - Install Supervised Accounting ML Models

Installs the pre-trained supervised accounting models from the
ANGELIX_Supervised_Accounting_ML package into ANGELIX's managed
organization-specific ML model storage.
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

from app.services.ml.model_manager import ModelManager


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORGANIZATION_ID = 6

MODEL_FILENAMES = (
    "account_type_classifier.joblib",
    "debit_credit_classifier.joblib",
)


# ---------------------------------------------------------------------------
# Locate accounting ML package
# ---------------------------------------------------------------------------

def locate_accounting_model_directory() -> Path:
    """
    Locate the directory containing the two supervised accounting models.

    The function searches inside the ANGELIX project so that the installer
    does not depend on the exact capitalization or name of the extracted
    package directory.
    """

    expected_models = set(MODEL_FILENAMES)

    candidates: list[Path] = []

    # First check the known package location.
    known_directories = [
        PROJECT_ROOT / "ANGELIX_Supervised_Accounting_ML" / "models",
        PROJECT_ROOT / "Angelix_supervised_accounting_model" / "models",
        PROJECT_ROOT / "Angelix_Supervised_Accounting_ML" / "models",
    ]

    for directory in known_directories:
        if directory.is_dir():
            candidates.append(directory)

    # Then search recursively for the model files.
    for model_filename in MODEL_FILENAMES:

        for path in PROJECT_ROOT.rglob(model_filename):

            if path.is_file():
                candidates.append(path.parent)

    # Remove duplicates while preserving order.
    unique_candidates: list[Path] = []

    for candidate in candidates:

        resolved = candidate.resolve()

        if resolved not in unique_candidates:
            unique_candidates.append(resolved)

    # Find a directory containing both required models.
    for directory in unique_candidates:

        available_files = {
            path.name
            for path in directory.iterdir()
            if path.is_file()
        }

        if expected_models.issubset(
            available_files
        ):
            return directory

    raise FileNotFoundError(
        "Unable to locate the supervised accounting ML models.\n\n"
        "The installer searched the ANGELIX project for:\n"
        f"  - {MODEL_FILENAMES[0]}\n"
        f"  - {MODEL_FILENAMES[1]}\n\n"
        "Please make sure the ANGELIX_Supervised_Accounting_ML "
        "package has been extracted inside the angelix project."
    )


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def install_accounting_models() -> None:
    """
    Install and validate the supervised accounting models.
    """

    print()
    print("=" * 70)
    print("ANGELIX - SUPERVISED ACCOUNTING ML MODEL INSTALLATION")
    print("=" * 70)
    print()

    print(
        f"Project root       : {PROJECT_ROOT}"
    )

    print(
        f"Organization ID    : {ORGANIZATION_ID}"
    )

    print()

    # ------------------------------------------------------------------
    # Locate models
    # ------------------------------------------------------------------

    print(
        "Searching for supervised accounting models..."
    )

    accounting_model_directory = (
        locate_accounting_model_directory()
    )

    print()

    print(
        "Model package found:"
    )

    print(
        f"  {accounting_model_directory}"
    )

    print()

    # ------------------------------------------------------------------
    # Verify source files
    # ------------------------------------------------------------------

    print(
        "Checking source models..."
    )

    print()

    for filename in MODEL_FILENAMES:

        model_path = (
            accounting_model_directory
            / filename
        )

        if not model_path.exists():
            raise FileNotFoundError(
                f"Required model file was not found:\n"
                f"{model_path}"
            )

        if not model_path.is_file():
            raise ValueError(
                f"Model path is not a file:\n"
                f"{model_path}"
            )

        print(
            f"  [OK] {filename}"
        )

    print()

    # ------------------------------------------------------------------
    # Model manager
    # ------------------------------------------------------------------

    manager = ModelManager()

    # ------------------------------------------------------------------
    # Install models
    # ------------------------------------------------------------------

    print(
        "Installing supervised accounting models..."
    )

    print()

    imported_models = (
        manager.import_accounting_models(
            organization_id=ORGANIZATION_ID,
            accounting_model_directory=(
                accounting_model_directory
            ),
            overwrite=False,
        )
    )

    print()

    # ------------------------------------------------------------------
    # Display installation results
    # ------------------------------------------------------------------

    for model_name, result in imported_models.items():

        print(
            f"[INSTALLED] {model_name}"
        )

        print(
            f"  Version : v{result['version']}"
        )

        print(
            f"  Path    : {result['model_path']}"
        )

        print()

    # ------------------------------------------------------------------
    # Validate installed models
    # ------------------------------------------------------------------

    print(
        "Validating installed models..."
    )

    print()

    for model_name, result in imported_models.items():

        validation = manager.validate_model(
            organization_id=ORGANIZATION_ID,
            model_name=model_name,
            version=result["version"],
        )

        if not validation["valid"]:

            raise RuntimeError(
                f"Model validation failed for "
                f"{model_name}: "
                f"{validation.get('reason')}"
            )

        print(
            f"  [VALID] {model_name} "
            f"v{result['version']}"
        )

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------

    print()
    print("=" * 70)
    print("ACCOUNTING ML MODEL INSTALLATION COMPLETED")
    print("=" * 70)
    print()

    print(
        "Installed models:"
    )

    print(
        "  1. Account Type Classifier"
    )

    print(
        "     Asset / Liability / Equity / Revenue / Expense"
    )

    print(
        "  2. Debit/Credit Classifier"
    )

    print(
        "     Debit / Credit"
    )

    print()

    print(
        "The models are now available through ANGELIX's "
        "ModelManager and PredictionService."
    )

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    try:

        install_accounting_models()

    except Exception as exc:

        print()
        print("[ERROR]")
        print(str(exc))
        print()

        raise SystemExit(1)