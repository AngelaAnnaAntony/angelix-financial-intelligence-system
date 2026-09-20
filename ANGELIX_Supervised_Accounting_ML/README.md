# ANGELIX Supervised Accounting Transaction ML

This package contains a **supervised machine-learning prototype** for ANGELIX.

## Models

1. `account_type_classifier.joblib`
   - Predicts: `asset`, `liability`, `equity`, `revenue`, `expense`
2. `debit_credit_classifier.joblib`
   - Predicts: `debit` or `credit`

The models use transaction description (TF-IDF), amount, recurring flag, source and month.

## Validation

- Training rows: 10,000
- Account-type classes: asset, liability, equity, revenue, expense
- Account-type holdout accuracy: 100.00%
- Debit/credit holdout accuracy: 92.00%

**Important:** The included training data is synthetic bootstrap data generated from accounting transaction templates. The validation scores therefore demonstrate that the package trains and predicts correctly on this controlled dataset; they must NOT be interpreted as real-world production accuracy.

## Run

```powershell
pip install -r requirements.txt
python scripts/predict_examples.py
```

Retrain:

```powershell
python scripts/train_models.py
```

## ANGELIX integration

The intended production workflow is:

Upload/extract transaction
-> ML predicts account type + debit/credit + confidence
-> high-confidence prediction can be proposed automatically
-> low-confidence prediction goes to review
-> user correction is stored
-> corrected labels become future supervised training data.

The existing ANGELIX transaction `category` / `transaction_type` fields should remain compatible with this workflow. The ML result should be treated as a recommendation until confidence and validation rules permit automatic application.

## Why the earlier credit-card fraud model is not used here

The credit-card fraud dataset has a `Class` fraud target and PCA-style V1-V28 features. It does not represent ANGELIX accounting classes, so it is not appropriate for transaction account classification.

## Dataset provenance

This package intentionally does not claim that its synthetic data is a public benchmark. For the next ANGELIX iteration, replace/augment the bootstrap data with reviewed real accounting examples or a compatible openly licensed accounting dataset.
