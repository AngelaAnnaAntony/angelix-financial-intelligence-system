"""
ANGELIX - Machine Learning Model Manager

This module manages persistence of trained machine-learning models.

Responsibilities:
- Save trained models to disk
- Load trained models
- Save model metadata
- Load model metadata
- Generate model versions
- Validate persisted model files
- List available models
- Delete obsolete model versions

Models are stored outside the application source code and should not
contain sensitive financial transaction data directly.

The model manager does NOT:
- Train models
- Query PostgreSQL
- Call AI APIs
- Generate predictions
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL_DIRECTORY = Path("instance") / "ml_models"

MODEL_FILE_EXTENSION = ".joblib"
METADATA_FILE_EXTENSION = ".json"

SAFE_NAME_PATTERN = re.compile(
    r"[^a-zA-Z0-9_.-]+"
)

# Pre-trained ANGELIX accounting classifier names.
ACCOUNT_TYPE_MODEL_NAME = "account_type_classifier"
DEBIT_CREDIT_MODEL_NAME = "debit_credit_classifier"

SUPPORTED_PRETRAINED_MODELS = {
    ACCOUNT_TYPE_MODEL_NAME,
    DEBIT_CREDIT_MODEL_NAME,
}


# ---------------------------------------------------------------------------
# Model manager
# ---------------------------------------------------------------------------

class ModelManager:
    """
    Handles persistence and lifecycle management of ANGELIX ML models.

    Model layout:

        instance/
        └── ml_models/
            └── organization_6/
                ├── financial_risk_random_forest_v1.joblib
                ├── financial_risk_random_forest_v1.json
                ├── financial_risk_random_forest_v2.joblib
                └── financial_risk_random_forest_v2.json

    The organization identifier is part of the directory structure so
    models are isolated between organizations.
    """

    def __init__(
        self,
        base_directory: Optional[
            str | os.PathLike[str]
        ] = None,
    ) -> None:
        """
        Initialize the model manager.

        Parameters:
            base_directory:
                Optional custom model-storage directory.

                If omitted:
                    instance/ml_models
        """

        if base_directory is None:
            base_directory = DEFAULT_MODEL_DIRECTORY

        self.base_directory = Path(
            base_directory
        ).resolve()

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # -----------------------------------------------------------------------
    # Save model
    # -----------------------------------------------------------------------

    def save_model(
        self,
        model: Any,
        organization_id: int,
        model_name: str,
        metadata: Optional[dict[str, Any]] = None,
        version: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Save a trained model and its metadata.

        Parameters:
            model:
                Trained sklearn-compatible model/pipeline.

            organization_id:
                Organization owning the model.

            model_name:
                Logical model name.

            metadata:
                Optional model metadata.

            version:
                Optional explicit version.

        Returns:
            Dictionary containing saved model information.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        organization_directory = (
            self._get_organization_directory(
                organization_id
            )
        )

        if version is None:
            version = self._get_next_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version < 1:
            raise ValueError(
                "Model version must be greater than zero."
            )

        model_filename = (
            f"{safe_model_name}_v{version}"
            f"{MODEL_FILE_EXTENSION}"
        )

        metadata_filename = (
            f"{safe_model_name}_v{version}"
            f"{METADATA_FILE_EXTENSION}"
        )

        model_path = (
            organization_directory
            / model_filename
        )

        metadata_path = (
            organization_directory
            / metadata_filename
        )

        # Save model.
        joblib.dump(
            model,
            model_path,
            compress=3,
        )

        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

        model_metadata: dict[str, Any] = {
            "organization_id": organization_id,
            "model_name": safe_model_name,
            "version": version,
            "model_filename": model_filename,
            "created_at": generated_at,
        }

        if metadata:
            model_metadata.update(
                self._make_json_safe(metadata)
            )

        self._write_json(
            metadata_path,
            model_metadata,
        )

        logger.info(
            "ML model saved: organization=%s model=%s version=%s",
            organization_id,
            safe_model_name,
            version,
        )

        return {
            "organization_id": organization_id,
            "model_name": safe_model_name,
            "version": version,
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
            "created_at": generated_at,
        }

    # -----------------------------------------------------------------------
    # Load model
    # -----------------------------------------------------------------------

    def load_model(
        self,
        organization_id: int,
        model_name: str,
        version: Optional[int] = None,
    ) -> Any:
        """
        Load a previously saved model.

        If version is omitted, the latest available version is loaded.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        if version is None:
            version = self.get_latest_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version is None:
            raise FileNotFoundError(
                f"No trained model found for "
                f"organization {organization_id}: "
                f"{safe_model_name}"
            )

        model_path = self._get_model_path(
            organization_id=organization_id,
            model_name=safe_model_name,
            version=version,
        )

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file does not exist: "
                f"{model_path}"
            )

        try:
            model = joblib.load(
                model_path
            )
        except Exception as exc:
            logger.exception(
                "Failed to load ML model: %s",
                model_path,
            )

            raise RuntimeError(
                f"Unable to load ML model: {model_path}"
            ) from exc

        logger.info(
            "ML model loaded: organization=%s model=%s version=%s",
            organization_id,
            safe_model_name,
            version,
        )

        return model

    # -----------------------------------------------------------------------
    # Load metadata
    # -----------------------------------------------------------------------

    def load_metadata(
        self,
        organization_id: int,
        model_name: str,
        version: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Load metadata associated with a persisted model.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        if version is None:
            version = self.get_latest_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version is None:
            raise FileNotFoundError(
                f"No metadata found for model "
                f"{safe_model_name}."
            )

        metadata_path = (
            self._get_metadata_path(
                organization_id=organization_id,
                model_name=safe_model_name,
                version=version,
            )
        )

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Model metadata does not exist: "
                f"{metadata_path}"
            )

        try:
            with metadata_path.open(
                "r",
                encoding="utf-8",
            ) as metadata_file:
                return json.load(
                    metadata_file
                )
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception(
                "Failed to read model metadata: %s",
                metadata_path,
            )

            raise RuntimeError(
                f"Unable to read model metadata: "
                f"{metadata_path}"
            ) from exc

    # -----------------------------------------------------------------------
    # Model existence
    # -----------------------------------------------------------------------

    def model_exists(
        self,
        organization_id: int,
        model_name: str,
        version: Optional[int] = None,
    ) -> bool:
        """
        Check whether a persisted model exists.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        if version is None:
            version = self.get_latest_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version is None:
            return False

        return self._get_model_path(
            organization_id=organization_id,
            model_name=safe_model_name,
            version=version,
        ).exists()

    # -----------------------------------------------------------------------
    # Latest version
    # -----------------------------------------------------------------------

    def get_latest_version(
        self,
        organization_id: int,
        model_name: str,
    ) -> Optional[int]:
        """
        Return the highest available model version.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        directory = self._get_organization_directory(
            organization_id
        )

        pattern = (
            f"{safe_model_name}_v*"
            f"{MODEL_FILE_EXTENSION}"
        )

        versions: list[int] = []

        for path in directory.glob(pattern):
            version = self._extract_version(
                path.name
            )

            if version is not None:
                versions.append(version)

        if not versions:
            return None

        return max(versions)

    # -----------------------------------------------------------------------
    # List models
    # -----------------------------------------------------------------------

    def list_models(
        self,
        organization_id: int,
    ) -> list[dict[str, Any]]:
        """
        List persisted models for an organization.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        directory = self._get_organization_directory(
            organization_id
        )

        if not directory.exists():
            return []

        models: list[dict[str, Any]] = []

        for model_path in sorted(
            directory.glob(
                f"*{MODEL_FILE_EXTENSION}"
            )
        ):
            parsed = self._parse_model_filename(
                model_path.name
            )

            if parsed is None:
                continue

            model_name, version = parsed

            metadata: dict[str, Any] = {}

            metadata_path = (
                directory
                / (
                    f"{model_name}_v{version}"
                    f"{METADATA_FILE_EXTENSION}"
                )
            )

            if metadata_path.exists():
                try:
                    with metadata_path.open(
                        "r",
                        encoding="utf-8",
                    ) as metadata_file:
                        metadata = json.load(
                            metadata_file
                        )
                except (
                    OSError,
                    json.JSONDecodeError,
                ):
                    logger.warning(
                        "Unable to read metadata: %s",
                        metadata_path,
                    )

            models.append(
                {
                    "organization_id": organization_id,
                    "model_name": model_name,
                    "version": version,
                    "model_path": str(
                        model_path
                    ),
                    "metadata_path": str(
                        metadata_path
                    ),
                    "metadata": metadata,
                }
            )

        models.sort(
            key=lambda item: (
                item["model_name"],
                item["version"],
            )
        )

        return models

    # -----------------------------------------------------------------------
    # Delete model
    # -----------------------------------------------------------------------

    def delete_model(
        self,
        organization_id: int,
        model_name: str,
        version: int,
        delete_metadata: bool = True,
    ) -> bool:
        """
        Delete a specific persisted model version.

        Returns:
            True when the model file existed and was deleted.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        model_path = self._get_model_path(
            organization_id=organization_id,
            model_name=safe_model_name,
            version=version,
        )

        deleted = False

        if model_path.exists():
            model_path.unlink()
            deleted = True

        if delete_metadata:
            metadata_path = (
                self._get_metadata_path(
                    organization_id=organization_id,
                    model_name=safe_model_name,
                    version=version,
                )
            )

            if metadata_path.exists():
                metadata_path.unlink()

        if deleted:
            logger.info(
                "ML model deleted: organization=%s model=%s version=%s",
                organization_id,
                safe_model_name,
                version,
            )

        return deleted

    # -----------------------------------------------------------------------
    # Import pre-trained model
    # -----------------------------------------------------------------------

    def import_pretrained_model(
        self,
        source_path: str | os.PathLike[str],
        organization_id: int,
        model_name: str,
        metadata: Optional[dict[str, Any]] = None,
        version: Optional[int] = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Import an already-trained joblib model into an organization's
        managed model directory.

        This is used for the ANGELIX bootstrap accounting classifiers
        that are trained outside the application and then installed into
        the organization's model store.

        The source file is copied rather than moved, so the original
        training package remains intact.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        source = Path(source_path).expanduser().resolve()

        if not source.exists():
            raise FileNotFoundError(
                f"Pre-trained model file does not exist: {source}"
            )

        if not source.is_file():
            raise ValueError(
                f"Pre-trained model path is not a file: {source}"
            )

        if source.suffix.lower() != MODEL_FILE_EXTENSION:
            raise ValueError(
                "Pre-trained model must be a .joblib file."
            )

        # Validate that the file can actually be deserialized before
        # installing it into the application model store.
        try:
            imported_model = joblib.load(source)
        except Exception as exc:
            logger.exception(
                "Unable to validate pre-trained model: %s",
                source,
            )
            raise RuntimeError(
                f"Unable to load pre-trained model: {source}"
            ) from exc

        organization_directory = self._get_organization_directory(
            organization_id
        )

        if version is None:
            version = self._get_next_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version < 1:
            raise ValueError(
                "Model version must be greater than zero."
            )

        model_filename = (
            f"{safe_model_name}_v{version}"
            f"{MODEL_FILE_EXTENSION}"
        )

        metadata_filename = (
            f"{safe_model_name}_v{version}"
            f"{METADATA_FILE_EXTENSION}"
        )

        model_path = organization_directory / model_filename
        metadata_path = organization_directory / metadata_filename

        if model_path.exists() and not overwrite:
            raise FileExistsError(
                f"Model already exists: {model_path}"
            )

        # Copy the validated source model. Using shutil.copy2 preserves
        # useful source-file metadata without modifying the source package.
        shutil.copy2(
            source,
            model_path,
        )

        generated_at = datetime.now(
            timezone.utc
        ).isoformat()

        model_metadata: dict[str, Any] = {
            "organization_id": organization_id,
            "model_name": safe_model_name,
            "version": version,
            "model_filename": model_filename,
            "created_at": generated_at,
            "source": "pretrained_import",
            "source_filename": source.name,
            "source_path": str(source),
            "model_class": (
                f"{imported_model.__class__.__module__}."
                f"{imported_model.__class__.__name__}"
            ),
        }

        if metadata:
            model_metadata.update(
                self._make_json_safe(metadata)
            )

        self._write_json(
            metadata_path,
            model_metadata,
        )

        logger.info(
            "Pre-trained ML model imported: "
            "organization=%s model=%s version=%s source=%s",
            organization_id,
            safe_model_name,
            version,
            source,
        )

        return {
            "organization_id": organization_id,
            "model_name": safe_model_name,
            "version": version,
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
            "created_at": generated_at,
            "source_path": str(source),
        }

    # -----------------------------------------------------------------------
    # Import the ANGELIX bootstrap accounting models
    # -----------------------------------------------------------------------

    def import_accounting_models(
        self,
        organization_id: int,
        accounting_model_directory: str | os.PathLike[str],
        overwrite: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """
        Import the two supervised accounting models shipped with the
        ANGELIX supervised-accounting package.

        Expected source files:

            account_type_classifier.joblib
            debit_credit_classifier.joblib

        The models are installed into the organization's normal
        instance/ml_models/organization_<id>/ directory.
        """

        accounting_directory = (
            Path(accounting_model_directory)
            .expanduser()
            .resolve()
        )

        if not accounting_directory.exists():
            raise FileNotFoundError(
                "Accounting model directory does not exist: "
                f"{accounting_directory}"
            )

        if not accounting_directory.is_dir():
            raise ValueError(
                "Accounting model directory is not a directory: "
                f"{accounting_directory}"
            )

        imported: dict[str, dict[str, Any]] = {}

        model_definitions = {
            ACCOUNT_TYPE_MODEL_NAME: {
                "filename": "account_type_classifier.joblib",
                "purpose": (
                    "Supervised classification of transactions into "
                    "asset, liability, equity, revenue, or expense."
                ),
                "classes": [
                    "asset",
                    "liability",
                    "equity",
                    "revenue",
                    "expense",
                ],
            },
            DEBIT_CREDIT_MODEL_NAME: {
                "filename": "debit_credit_classifier.joblib",
                "purpose": (
                    "Supervised classification of transaction posting "
                    "side as debit or credit."
                ),
                "classes": [
                    "debit",
                    "credit",
                ],
            },
        }

        for model_name, definition in model_definitions.items():
            source_path = accounting_directory / definition["filename"]

            imported[model_name] = self.import_pretrained_model(
                source_path=source_path,
                organization_id=organization_id,
                model_name=model_name,
                metadata={
                    "model_family": "accounting_transaction_classification",
                    "training_source": (
                        "ANGELIX supervised accounting bootstrap package"
                    ),
                    "purpose": definition["purpose"],
                    "classes": definition["classes"],
                    "status": "bootstrap",
                    "requires_real_world_validation": True,
                },
                overwrite=overwrite,
            )

        return imported

    # -----------------------------------------------------------------------
    # Validate persisted model
    # -----------------------------------------------------------------------

    def validate_model(
        self,
        organization_id: int,
        model_name: str,
        version: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Validate that a persisted model can be loaded successfully.

        This does not execute predictions and does not query the database.
        """

        organization_id = self._validate_organization_id(
            organization_id
        )

        safe_model_name = self._sanitize_name(
            model_name
        )

        if version is None:
            version = self.get_latest_version(
                organization_id=organization_id,
                model_name=safe_model_name,
            )

        if version is None:
            return {
                "valid": False,
                "organization_id": organization_id,
                "model_name": safe_model_name,
                "version": None,
                "reason": "model_not_found",
            }

        model_path = self._get_model_path(
            organization_id=organization_id,
            model_name=safe_model_name,
            version=version,
        )

        if not model_path.exists():
            return {
                "valid": False,
                "organization_id": organization_id,
                "model_name": safe_model_name,
                "version": version,
                "reason": "model_file_missing",
                "model_path": str(model_path),
            }

        try:
            model = joblib.load(model_path)
        except Exception as exc:
            logger.exception(
                "Model validation failed: %s",
                model_path,
            )
            return {
                "valid": False,
                "organization_id": organization_id,
                "model_name": safe_model_name,
                "version": version,
                "reason": "model_load_failed",
                "error": str(exc),
                "model_path": str(model_path),
            }

        return {
            "valid": True,
            "organization_id": organization_id,
            "model_name": safe_model_name,
            "version": version,
            "model_path": str(model_path),
            "model_class": (
                f"{model.__class__.__module__}."
                f"{model.__class__.__name__}"
            ),
        }

    # -----------------------------------------------------------------------
    # Organization directory
    # -----------------------------------------------------------------------

    def _get_organization_directory(
        self,
        organization_id: int,
    ) -> Path:
        """
        Get/create the organization's model directory.
        """

        directory = (
            self.base_directory
            / f"organization_{organization_id}"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory

    # -----------------------------------------------------------------------
    # Model paths
    # -----------------------------------------------------------------------

    def _get_model_path(
        self,
        organization_id: int,
        model_name: str,
        version: int,
    ) -> Path:
        """
        Construct a model path.
        """

        directory = self._get_organization_directory(
            organization_id
        )

        return (
            directory
            / (
                f"{model_name}_v{version}"
                f"{MODEL_FILE_EXTENSION}"
            )
        )

    def _get_metadata_path(
        self,
        organization_id: int,
        model_name: str,
        version: int,
    ) -> Path:
        """
        Construct a metadata path.
        """

        directory = self._get_organization_directory(
            organization_id
        )

        return (
            directory
            / (
                f"{model_name}_v{version}"
                f"{METADATA_FILE_EXTENSION}"
            )
        )

    # -----------------------------------------------------------------------
    # Version generation
    # -----------------------------------------------------------------------

    def _get_next_version(
        self,
        organization_id: int,
        model_name: str,
    ) -> int:
        """
        Generate the next model version number.
        """

        latest = self.get_latest_version(
            organization_id=organization_id,
            model_name=model_name,
        )

        if latest is None:
            return 1

        return latest + 1

    # -----------------------------------------------------------------------
    # Filename parsing
    # -----------------------------------------------------------------------

    @staticmethod
    def _extract_version(
        filename: str,
    ) -> Optional[int]:
        """
        Extract a version number from a model filename.
        """

        pattern = re.compile(
            rf"_v(\d+)"
            rf"{re.escape(MODEL_FILE_EXTENSION)}$"
        )

        match = pattern.search(
            filename
        )

        if not match:
            return None

        try:
            return int(
                match.group(1)
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_model_filename(
        filename: str,
    ) -> Optional[tuple[str, int]]:
        """
        Parse:

            model_name_v1.joblib

        into:

            ("model_name", 1)
        """

        version = ModelManager._extract_version(
            filename
        )

        if version is None:
            return None

        suffix = (
            f"_v{version}"
            f"{MODEL_FILE_EXTENSION}"
        )

        if not filename.endswith(
            suffix
        ):
            return None

        model_name = filename[
            : -len(suffix)
        ]

        if not model_name:
            return None

        return model_name, version

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_organization_id(
        organization_id: int,
    ) -> int:
        """
        Validate organization identifier.
        """

        try:
            organization_id = int(
                organization_id
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "organization_id must be an integer."
            ) from exc

        if organization_id <= 0:
            raise ValueError(
                "organization_id must be greater than zero."
            )

        return organization_id

    @staticmethod
    def _sanitize_name(
        value: str,
    ) -> str:
        """
        Sanitize model names used in filenames.

        This prevents path traversal and unsafe filename characters.
        """

        if not isinstance(value, str):
            raise TypeError(
                "Model name must be a string."
            )

        value = value.strip()

        if not value:
            raise ValueError(
                "Model name cannot be empty."
            )

        value = SAFE_NAME_PATTERN.sub(
            "_",
            value,
        )

        value = value.strip(
            "._"
        )

        if not value:
            raise ValueError(
                "Model name contains no usable characters."
            )

        return value

    # -----------------------------------------------------------------------
    # JSON utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _write_json(
        path: Path,
        data: dict[str, Any],
    ) -> None:
        """
        Write JSON metadata atomically.
        """

        temporary_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as json_file:
                json.dump(
                    data,
                    json_file,
                    indent=2,
                    ensure_ascii=False,
                )

            temporary_path.replace(
                path
            )

        except OSError as exc:
            if temporary_path.exists():
                temporary_path.unlink()

            raise RuntimeError(
                f"Unable to write model metadata: {path}"
            ) from exc

    @staticmethod
    def _make_json_safe(
        value: Any,
    ) -> Any:
        """
        Convert common Python/numpy values into JSON-compatible values.
        """

        if value is None:
            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        if isinstance(
            value,
            Path,
        ):
            return str(value)

        if isinstance(
            value,
            datetime,
        ):
            return value.isoformat()

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): ModelManager._make_json_safe(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set),
        ):
            return [
                ModelManager._make_json_safe(
                    item
                )
                for item in value
            ]

        # Handle numpy scalar types without making numpy
        # a hard dependency of this module.
        if hasattr(value, "item"):
            try:
                return value.item()
            except (ValueError, TypeError):
                pass

        return str(value)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------
def import_pretrained_model(
    source_path: str | os.PathLike[str],
    organization_id: int,
    model_name: str,
    metadata: Optional[dict[str, Any]] = None,
    version: Optional[int] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Convenience wrapper for importing a pre-trained model.
    """

    manager = ModelManager()

    return manager.import_pretrained_model(
        source_path=source_path,
        organization_id=organization_id,
        model_name=model_name,
        metadata=metadata,
        version=version,
        overwrite=overwrite,
    )


def import_accounting_models(
    organization_id: int,
    accounting_model_directory: str | os.PathLike[str],
    overwrite: bool = False,
) -> dict[str, dict[str, Any]]:
    """
    Convenience wrapper for installing the ANGELIX accounting models.
    """

    manager = ModelManager()

    return manager.import_accounting_models(
        organization_id=organization_id,
        accounting_model_directory=accounting_model_directory,
        overwrite=overwrite,
    )



def save_trained_model(
    model: Any,
    organization_id: int,
    model_name: str,
    metadata: Optional[dict[str, Any]] = None,
    version: Optional[int] = None,
) -> dict[str, Any]:
    """
    Convenience wrapper for saving a trained model.
    """

    manager = ModelManager()

    return manager.save_model(
        model=model,
        organization_id=organization_id,
        model_name=model_name,
        metadata=metadata,
        version=version,
    )


def load_trained_model(
    organization_id: int,
    model_name: str,
    version: Optional[int] = None,
) -> Any:
    """
    Convenience wrapper for loading a trained model.
    """

    manager = ModelManager()

    return manager.load_model(
        organization_id=organization_id,
        model_name=model_name,
        version=version,
    )