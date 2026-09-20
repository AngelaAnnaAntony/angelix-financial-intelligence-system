"""ANGELIX supervised transaction classification models."""
from pathlib import Path
import joblib
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_MODEL = PACKAGE_ROOT / "models" / "account_type_classifier.joblib"
SIDE_MODEL = PACKAGE_ROOT / "models" / "debit_credit_classifier.joblib"

class AngelixTransactionClassifier:
    def __init__(self):
        self.account_model = joblib.load(ACCOUNT_MODEL)
        self.side_model = joblib.load(SIDE_MODEL)

    @staticmethod
    def _frame(description, amount, is_recurring=False, source="Manual", month=1):
        return pd.DataFrame([{
            "description": str(description or ""),
            "amount": float(amount or 0),
            "is_recurring": int(bool(is_recurring)),
            "source": str(source or "Manual"),
            "month": int(month or 1),
        }])

    def predict(self, description, amount, is_recurring=False, source="Manual", month=1):
        frame = self._frame(description, amount, is_recurring, source, month)
        account = self.account_model.predict(frame)[0]
        account_probs = self.account_model.predict_proba(frame)[0]
        account_conf = float(max(account_probs))
        side = self.side_model.predict(frame)[0]
        side_probs = self.side_model.predict_proba(frame)[0]
        side_conf = float(max(side_probs))
        return {
            "account_type": account,
            "account_confidence": round(account_conf, 4),
            "debit_credit": side,
            "debit_credit_confidence": round(side_conf, 4),
        }
