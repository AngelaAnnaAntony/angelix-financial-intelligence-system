from decimal import Decimal
class StatementCalculator:
    @staticmethod
    def calculate(transactions):
        income=sum((Decimal(str(t.amount)) for t in transactions if t.category=="income"),Decimal("0"))
        expense=sum((Decimal(str(t.amount)) for t in transactions if t.category=="expense"),Decimal("0"))
        assets=sum((Decimal(str(t.amount)) for t in transactions if t.category=="asset"),Decimal("0"))
        liabilities=sum((Decimal(str(t.amount)) for t in transactions if t.category=="liability"),Decimal("0"))
        equity=sum((Decimal(str(t.amount)) for t in transactions if t.category=="equity"),Decimal("0"))
        return {"income":str(income),"expenses":str(expense),"net_profit":str(income-expense),
                "assets":str(assets),"liabilities":str(liabilities),"equity":str(equity+income-expense)}
