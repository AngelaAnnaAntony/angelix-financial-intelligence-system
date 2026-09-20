"""Retrain the ANGELIX accounting classifiers."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "accounting_transactions_training.csv"
MODELS = ROOT / "models"
df = pd.read_csv(DATA)

features = ["description", "amount", "is_recurring", "source", "month"]
X = df[features]
num_cols = ["amount", "is_recurring", "month"]
cat_cols = ["source"]

def make_model():
    prep = ColumnTransformer([
        ("text", TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True), "description"),
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler(with_mean=False))
        ]), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])
    return Pipeline([
        ("preprocess", prep),
        ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced"))
    ])

for target, filename in [
    ("account_type", "account_type_classifier.joblib"),
    ("debit_credit", "debit_credit_classifier.joblib")
]:
    y = df[target]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    model = make_model()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    print(f"\n{target}: accuracy={accuracy_score(y_test, pred):.4f}")
    print(classification_report(y_test, pred))
    joblib.dump(model, MODELS / filename)
