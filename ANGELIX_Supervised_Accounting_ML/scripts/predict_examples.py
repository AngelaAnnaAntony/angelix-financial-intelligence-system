from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from classifier import AngelixTransactionClassifier

model = AngelixTransactionClassifier()

examples = [
    ("Office electricity bill", 5000, False, "Manual", 9),
    ("Customer payment for consulting services", 75000, False, "Bank", 9),
    ("Purchase of office laptop", 85000, False, "Bank", 9),
    ("Business loan received", 500000, False, "Bank", 9),
    ("Owner capital introduced", 300000, False, "Bank", 9),
]

for item in examples:
    print(item[0], "->", model.predict(*item))
