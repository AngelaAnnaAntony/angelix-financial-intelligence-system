from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from classifier import AngelixTransactionClassifier

def test_prediction_schema():
    model = AngelixTransactionClassifier()
    result = model.predict("Office electricity bill", 5000, False, "Manual", 9)
    assert result["account_type"] in {"asset", "liability", "equity", "revenue", "expense"}
    assert result["debit_credit"] in {"debit", "credit"}
    assert 0 <= result["account_confidence"] <= 1
    assert 0 <= result["debit_credit_confidence"] <= 1
