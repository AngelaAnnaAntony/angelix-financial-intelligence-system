"""
ANGELIX - Machine Learning Services

Central package exports for the Angelix ML subsystem.

The ML subsystem is organization-scoped and provides:

- Transaction feature engineering
- Financial dataset preparation
- Transparent target engineering
- Model training
- Model persistence and versioning
- Transaction predictions
- End-to-end training pipelines
"""

from app.services.ml.feature_engineering import (
    FeatureEngineeringResult,
    FinancialFeatureEngineer,
    build_transaction_features,
)

from app.services.ml.dataset_service import (
    DatasetResult,
    FinancialDatasetService,
    build_training_dataset,
    build_prediction_dataset,
)

from app.services.ml.model_training import (
    ModelTrainingResult,
    FinancialModelTrainer,
    train_financial_model,
)

from app.services.ml.model_manager import (
    ModelManager,
    save_trained_model,
    load_trained_model,
)

from app.services.ml.prediction_service import (
    PredictionResult,
    FinancialPredictionService,
    predict_financial_transactions,
)

from app.services.ml.target_engineering import (
    TargetEngineeringResult,
    TargetValidationResult,
    FinancialTargetEngineer,
)

from app.services.ml.training_pipeline import (
    TrainingPipelineResult,
    FinancialTrainingPipeline,
    train_financial_anomaly_model,
)


__all__ = [
    # Feature engineering
    "FeatureEngineeringResult",
    "FinancialFeatureEngineer",
    "build_transaction_features",

    # Dataset service
    "DatasetResult",
    "FinancialDatasetService",
    "build_training_dataset",
    "build_prediction_dataset",

    # Model training
    "ModelTrainingResult",
    "FinancialModelTrainer",
    "train_financial_model",

    # Model management
    "ModelManager",
    "save_trained_model",
    "load_trained_model",

    # Prediction
    "PredictionResult",
    "FinancialPredictionService",
    "predict_financial_transactions",

    # Target engineering
    "TargetEngineeringResult",
    "TargetValidationResult",
    "FinancialTargetEngineer",

    # Training pipeline
    "TrainingPipelineResult",
    "FinancialTrainingPipeline",
    "train_financial_anomaly_model",
]