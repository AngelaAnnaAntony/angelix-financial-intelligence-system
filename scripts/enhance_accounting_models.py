from pathlib import Path
import json

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from sklearn.preprocessing import (
    FunctionTransformer,
    OneHotEncoder,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parents[1]

ML_PACKAGE_DIR = (
    BASE_DIR / "ANGELIX_Supervised_Accounting_ML"
)

DATA_DIR = ML_PACKAGE_DIR / "data"
MODEL_DIR = ML_PACKAGE_DIR / "models"

EXISTING_DATASET = (
    DATA_DIR / "accounting_transactions_training.csv"
)

NEW_DATASET = (
    DATA_DIR / "synthetic_financial_dataset_1200.csv"
)

ENHANCED_DATASET = (
    DATA_DIR / "enhanced_accounting_training_dataset.csv"
)

METRICS_FILE = (
    DATA_DIR / "enhanced_accounting_model_metrics.json"
)


# =============================================================================
# VALIDATE INPUT FILES
# =============================================================================

print("=" * 80)
print("ANGELIX ACCOUNTING ML MODEL ENHANCEMENT")
print("=" * 80)

if not EXISTING_DATASET.exists():
    raise FileNotFoundError(
        f"\nExisting dataset not found:\n{EXISTING_DATASET}"
    )

if not NEW_DATASET.exists():
    raise FileNotFoundError(
        f"\nNew dataset not found:\n{NEW_DATASET}"
    )

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =============================================================================
# LOAD DATASETS
# =============================================================================

print("\nLoading datasets...")

existing_df = pd.read_csv(
    EXISTING_DATASET
)

new_df = pd.read_csv(
    NEW_DATASET
)

print(
    f"Existing dataset : {len(existing_df):,} records"
)

print(
    f"New dataset      : {len(new_df):,} records"
)


# =============================================================================
# DISPLAY EXISTING DATASET STRUCTURE
# =============================================================================

print("\nExisting dataset columns:")

print(
    existing_df.columns.tolist()
)


# =============================================================================
# NORMALIZE EXISTING DATASET
#
# The existing dataset structure observed from your file is:
#
# description
# reference
# amount
# is_recurring
# source
# month
# account_type
# debit_credit
#
# We detect the columns instead of relying on fixed positions.
# =============================================================================

def find_column(
    dataframe,
    candidates,
):
    """
    Find a column using case-insensitive matching.
    """

    normalized = {
        str(column).strip().lower(): column
        for column in dataframe.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()

        if key in normalized:
            return normalized[key]

    return None


existing_description_col = find_column(
    existing_df,
    [
        "description",
        "transaction_description",
        "desc",
    ],
)

existing_amount_col = find_column(
    existing_df,
    [
        "amount",
    ],
)

existing_recurring_col = find_column(
    existing_df,
    [
        "is_recurring",
        "recurring",
    ],
)

existing_source_col = find_column(
    existing_df,
    [
        "source",
        "payment_method",
    ],
)

existing_month_col = find_column(
    existing_df,
    [
        "month",
    ],
)

existing_account_type_col = find_column(
    existing_df,
    [
        "account_type",
        "transaction_type",
        "category",
    ],
)

existing_debit_credit_col = find_column(
    existing_df,
    [
        "debit_credit",
        "debit_vs_credit",
    ],
)


required_existing_columns = {
    "description": existing_description_col,
    "amount": existing_amount_col,
    "account_type": existing_account_type_col,
    "debit_credit": existing_debit_credit_col,
}


for name, column in required_existing_columns.items():

    if column is None:
        raise ValueError(
            f"Could not find required existing-dataset "
            f"column for: {name}"
        )


# =============================================================================
# BUILD COMMON EXISTING DATASET
# =============================================================================

existing_common = pd.DataFrame(
    {
        "description": (
            existing_df[
                existing_description_col
            ]
            .fillna("")
            .astype(str)
        ),

        "amount": pd.to_numeric(
            existing_df[
                existing_amount_col
            ],
            errors="coerce",
        ),

        "is_recurring": (
            existing_df[
                existing_recurring_col
            ]
            .fillna(0)
            .astype(int)
            if existing_recurring_col
            else 0
        ),

        "source": (
            existing_df[
                existing_source_col
            ]
            .fillna("unknown")
            .astype(str)
            if existing_source_col
            else "bootstrap"
        ),

        "month": (
            pd.to_numeric(
                existing_df[
                    existing_month_col
                ],
                errors="coerce",
            )
            if existing_month_col
            else 1
        ),

        "account_type": (
            existing_df[
                existing_account_type_col
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        ),

        "debit_credit": (
            existing_df[
                existing_debit_credit_col
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        ),
    }
)


# =============================================================================
# NORMALIZE EXISTING ACCOUNT TYPE LABELS
# =============================================================================

ACCOUNT_TYPE_ALIASES = {
    "income": "revenue",
    "revenue": "revenue",
    "sales": "revenue",

    "expense": "expense",
    "expenses": "expense",

    "asset": "asset",
    "assets": "asset",

    "liability": "liability",
    "liabilities": "liability",

    "equity": "equity",
    "capital": "equity",
}


existing_common["account_type"] = (
    existing_common["account_type"]
    .map(
        lambda value:
        ACCOUNT_TYPE_ALIASES.get(
            value,
            value,
        )
    )
)


# =============================================================================
# NORMALIZE DEBIT / CREDIT LABELS
# =============================================================================

existing_common["debit_credit"] = (
    existing_common["debit_credit"]
    .map(
        {
            "debit": "debit",
            "credit": "credit",
        }
    )
)


# =============================================================================
# PREPARE NEW DATASET
# =============================================================================

required_new_columns = [
    "Date",
    "Description",
    "Amount",
    "Income_vs_Expense",
    "Balance_Sheet_Category",
    "Debit_vs_Credit",
]


missing_new_columns = [
    column
    for column in required_new_columns
    if column not in new_df.columns
]


if missing_new_columns:
    raise ValueError(
        "New dataset is missing columns: "
        + ", ".join(missing_new_columns)
    )


new_common = pd.DataFrame(
    {
        "description": (
            new_df["Description"]
            .fillna("")
            .astype(str)
        ),

        "amount": pd.to_numeric(
            new_df["Amount"],
            errors="coerce",
        ),

        "is_recurring": 0,

        "source": (
            new_df["Payment_Method"]
            .fillna("unknown")
            .astype(str)
        ),

        "month": pd.to_datetime(
            new_df["Date"],
            errors="coerce",
        ).dt.month,

        "debit_credit": (
            new_df["Debit_vs_Credit"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        ),
    }
)


# =============================================================================
# MAP NEW DATASET TO EXISTING ACCOUNT TYPE TARGET
# =============================================================================

def map_new_account_type(row):
    """
    Convert the new dataset's transaction terminology
    into the existing Angelix account_type vocabulary.
    """

    transaction_type = (
        str(
            row["Income_vs_Expense"]
        )
        .strip()
        .lower()
    )

    balance_sheet_category = (
        str(
            row["Balance_Sheet_Category"]
        )
        .strip()
        .lower()
    )

    if transaction_type == "income":
        return "revenue"

    if transaction_type == "expense":
        return "expense"

    if transaction_type in {
        "equity injection",
        "equity withdrawal",
    }:
        return "equity"

    if transaction_type == "asset acquisition":
        return "asset"

    if transaction_type == "transfer":
        """
        In this supplied dataset, Transfer represents:
        - Credit card balance payoff
        - Bank loan principal repayment

        Both are associated with liability accounts.
        """

        return "liability"

    if balance_sheet_category in {
        "asset",
        "liability",
        "equity",
    }:
        return balance_sheet_category

    raise ValueError(
        f"Unable to map transaction type: "
        f"{transaction_type}"
    )


new_common["account_type"] = new_df.apply(
    map_new_account_type,
    axis=1,
)


# =============================================================================
# CLEAN DATA
# =============================================================================

VALID_ACCOUNT_TYPES = {
    "revenue",
    "expense",
    "asset",
    "liability",
    "equity",
}

VALID_DEBIT_CREDIT = {
    "debit",
    "credit",
}


existing_common = existing_common[
    existing_common["account_type"].isin(
        VALID_ACCOUNT_TYPES
    )
].copy()


existing_common = existing_common[
    existing_common["debit_credit"].isin(
        VALID_DEBIT_CREDIT
    )
].copy()


new_common = new_common[
    new_common["account_type"].isin(
        VALID_ACCOUNT_TYPES
    )
].copy()


new_common = new_common[
    new_common["debit_credit"].isin(
        VALID_DEBIT_CREDIT
    )
].copy()


existing_common = existing_common.dropna(
    subset=[
        "description",
        "amount",
    ]
)


new_common = new_common.dropna(
    subset=[
        "description",
        "amount",
        "month",
    ]
)


# =============================================================================
# COMBINE DATASETS
# =============================================================================

combined_df = pd.concat(
    [
        existing_common,
        new_common,
    ],
    ignore_index=True,
)


combined_df = combined_df[
    [
        "description",
        "amount",
        "is_recurring",
        "source",
        "month",
        "account_type",
        "debit_credit",
    ]
]


print(
    "\nCombined dataset:"
)

print(
    f"Existing records retained : "
    f"{len(existing_common):,}"
)

print(
    f"New records retained      : "
    f"{len(new_common):,}"
)

print(
    f"Total records             : "
    f"{len(combined_df):,}"
)


# =============================================================================
# SHOW ENHANCED CLASS DISTRIBUTIONS
# =============================================================================

print(
    "\nEnhanced account type distribution:"
)

print(
    combined_df[
        "account_type"
    ].value_counts()
)


print(
    "\nEnhanced debit/credit distribution:"
)

print(
    combined_df[
        "debit_credit"
    ].value_counts()
)


# =============================================================================
# SAVE COMBINED DATASET
# =============================================================================

combined_df.to_csv(
    ENHANCED_DATASET,
    index=False,
)

print(
    f"\nEnhanced dataset saved to:\n"
    f"{ENHANCED_DATASET}"
)


# =============================================================================
# MODEL FEATURE CONFIGURATION
# =============================================================================

FEATURE_COLUMNS = [
    "description",
    "amount",
    "is_recurring",
    "source",
    "month",
]

def description_to_text(data):
    """
    Convert the selected description column into
    a one-dimensional sequence of strings.
    """
    return (
        data.iloc[:, 0]
        .fillna("")
        .astype(str)
    )

def create_preprocessor():
    """
    Create a fresh preprocessor for every model.

    The description column is converted from the 2-D
    ColumnTransformer output into a 1-D sequence before
    TfidfVectorizer processes it.
    """

    description_pipeline = Pipeline(
        steps=[
            (
                "to_text",
                FunctionTransformer(
                    description_to_text,
                    validate=False,
                ),
            ),
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
        ]
    )

    source_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="most_frequent"
                ),
            ),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "description",
                description_pipeline,
                ["description"],
            ),

            (
                "numeric",
                numeric_pipeline,
                [
                    "amount",
                    "is_recurring",
                    "month",
                ],
            ),

            (
                "source",
                source_pipeline,
                ["source"],
            ),
        ]
    )

# =============================================================================
# TRAIN ACCOUNT TYPE CLASSIFIER
# =============================================================================

print(
    "\n" + "=" * 80
)

print(
    "TRAINING ACCOUNT TYPE CLASSIFIER"
)

print(
    "=" * 80
)


X_account = combined_df[
    FEATURE_COLUMNS
]

y_account = combined_df[
    "account_type"
]


X_train_account, X_test_account, y_train_account, y_test_account = (
    train_test_split(
        X_account,
        y_account,
        test_size=0.20,
        random_state=42,
        stratify=y_account,
    )
)


account_type_model = Pipeline(
    steps=[
        (
            "preprocessor",
            create_preprocessor(),
        ),

        (
            "classifier",
            RandomForestClassifier(
                n_estimators=300,
                random_state=42,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
    ]
)


account_type_model.fit(
    X_train_account,
    y_train_account,
)


account_predictions = (
    account_type_model.predict(
        X_test_account
    )
)


account_accuracy = accuracy_score(
    y_test_account,
    account_predictions,
)


account_report = classification_report(
    y_test_account,
    account_predictions,
    output_dict=True,
)


account_confusion = confusion_matrix(
    y_test_account,
    account_predictions,
)


print(
    f"\nAccuracy: {account_accuracy:.4f}"
)

print(
    "\nClassification Report:"
)

print(
    classification_report(
        y_test_account,
        account_predictions,
    )
)

print(
    "Confusion Matrix:"
)

print(
    account_confusion
)


# =============================================================================
# TRAIN DEBIT / CREDIT CLASSIFIER
# =============================================================================

print(
    "\n" + "=" * 80
)

print(
    "TRAINING DEBIT / CREDIT CLASSIFIER"
)

print(
    "=" * 80
)


X_debit_credit = combined_df[
    FEATURE_COLUMNS
]

y_debit_credit = combined_df[
    "debit_credit"
]


X_train_dc, X_test_dc, y_train_dc, y_test_dc = (
    train_test_split(
        X_debit_credit,
        y_debit_credit,
        test_size=0.20,
        random_state=42,
        stratify=y_debit_credit,
    )
)


debit_credit_model = Pipeline(
    steps=[
        (
            "preprocessor",
            create_preprocessor(),
        ),

        (
            "classifier",
            RandomForestClassifier(
                n_estimators=300,
                random_state=42,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ),
    ]
)


debit_credit_model.fit(
    X_train_dc,
    y_train_dc,
)


debit_credit_predictions = (
    debit_credit_model.predict(
        X_test_dc
    )
)


debit_credit_accuracy = accuracy_score(
    y_test_dc,
    debit_credit_predictions,
)


debit_credit_report = classification_report(
    y_test_dc,
    debit_credit_predictions,
    output_dict=True,
)


debit_credit_confusion = confusion_matrix(
    y_test_dc,
    debit_credit_predictions,
)


print(
    f"\nAccuracy: {debit_credit_accuracy:.4f}"
)

print(
    "\nClassification Report:"
)

print(
    classification_report(
        y_test_dc,
        debit_credit_predictions,
    )
)

print(
    "Confusion Matrix:"
)

print(
    debit_credit_confusion
)


# =============================================================================
# SAVE V3 MODELS
# =============================================================================

ACCOUNT_TYPE_MODEL_V3 = (
    MODEL_DIR /
    "account_type_classifier_v3.joblib"
)

DEBIT_CREDIT_MODEL_V3 = (
    MODEL_DIR /
    "debit_credit_classifier_v3.joblib"
)


joblib.dump(
    account_type_model,
    ACCOUNT_TYPE_MODEL_V3,
)


joblib.dump(
    debit_credit_model,
    DEBIT_CREDIT_MODEL_V3,
)


# =============================================================================
# SAVE METRICS
# =============================================================================

metrics = {
    "model_version": "v3",

    "dataset": {
        "existing_records": int(
            len(existing_common)
        ),

        "new_records": int(
            len(new_common)
        ),

        "combined_records": int(
            len(combined_df)
        ),
    },

    "account_type_classifier": {
        "accuracy": float(
            account_accuracy
        ),

        "classes": sorted(
            y_account.unique().tolist()
        ),

        "classification_report":
            account_report,

        "confusion_matrix":
            account_confusion.tolist(),
    },

    "debit_credit_classifier": {
        "accuracy": float(
            debit_credit_accuracy
        ),

        "classes": sorted(
            y_debit_credit.unique().tolist()
        ),

        "classification_report":
            debit_credit_report,

        "confusion_matrix":
            debit_credit_confusion.tolist(),
    },
}


METRICS_FILE.write_text(
    json.dumps(
        metrics,
        indent=4,
    ),
    encoding="utf-8",
)


# =============================================================================
# FINAL OUTPUT
# =============================================================================

print(
    "\n" + "=" * 80
)

print(
    "MODEL ENHANCEMENT COMPLETE"
)

print(
    "=" * 80
)

print(
    "\nEnhanced models:"
)

print(
    ACCOUNT_TYPE_MODEL_V3
)

print(
    DEBIT_CREDIT_MODEL_V3
)

print(
    "\nMetrics:"
)

print(
    METRICS_FILE
)

print(
    "\nIMPORTANT:"
)

print(
    "Existing v1/v2 models were NOT modified."
)

print(
    "v3 models have NOT been installed into Angelix yet."
)

print(
    "Review the evaluation results before replacing the active models."
)