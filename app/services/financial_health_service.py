from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..extensions import db
from ..models.financial_statement import FinancialStatement
from ..models.financial_statement_line_item import FinancialStatementLineItem
from .analytics_service import AnalyticsService


class FinancialHealthService:
    """
    Deterministic Financial Health Score service.

    The score is calculated from:
    - Profitability
    - Expense control
    - Asset-to-liability coverage
    - Leverage
    - Balance-sheet structural strength

    No AI-generated values are used in the score.
    """

    PROFITABILITY_WEIGHT = Decimal("25")
    EXPENSE_CONTROL_WEIGHT = Decimal("20")
    LIQUIDITY_WEIGHT = Decimal("20")
    LEVERAGE_WEIGHT = Decimal("20")
    BALANCE_SHEET_WEIGHT = Decimal("15")

    def calculate(
        self,
        organization_id: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:
        """
        Calculate the Financial Health Score.

        If no reporting period is supplied, the latest completed balance
        sheet period is used so that transaction analytics and balance-sheet
        analysis refer to the same reporting window.
        """

        organization_id = int(organization_id)

        balance_sheet = self._get_balance_sheet(organization_id)

        effective_period_start = period_start
        effective_period_end = period_end
        period_source = "requested"

        # When the caller does not provide a period, align the analytics
        # period with the latest completed balance sheet.
        if (
            period_start is None
            and period_end is None
            and balance_sheet.get("available")
            and balance_sheet.get("statement")
        ):
            statement = balance_sheet["statement"]

            effective_period_start = self._parse_date(
                statement.get("period_start")
            )
            effective_period_end = self._parse_date(
                statement.get("period_end")
            )

            period_source = "latest_completed_balance_sheet"

        elif period_start is None and period_end is None:
            period_source = "all_available_transactions"

        analytics = AnalyticsService().calculate(
            organization_id=organization_id,
            period_start=effective_period_start,
            period_end=effective_period_end,
        )

        profitability = self._score_profitability(analytics)
        expense_control = self._score_expense_control(analytics)
        liquidity = self._score_liquidity(balance_sheet)
        leverage = self._score_leverage(balance_sheet)
        balance_sheet_strength = self._score_balance_sheet_strength(
            balance_sheet
        )

        total_score = (
            self._decimal(profitability["score"])
            + self._decimal(expense_control["score"])
            + self._decimal(liquidity["score"])
            + self._decimal(leverage["score"])
            + self._decimal(balance_sheet_strength["score"])
        )

        total_score = self._round_decimal(total_score)

        return {
            "score": self._number(total_score),
            "max_score": 100,
            "health_level": self._health_level(total_score),
            "components": {
                "profitability": profitability,
                "expense_control": expense_control,
                "liquidity": liquidity,
                "leverage": leverage,
                "balance_sheet_strength": balance_sheet_strength,
            },
            "balance_sheet": balance_sheet,
            "analytics": analytics,
            "period": {
                "start": (
                    effective_period_start.isoformat()
                    if effective_period_start
                    else None
                ),
                "end": (
                    effective_period_end.isoformat()
                    if effective_period_end
                    else None
                ),
                "source": period_source,
            },
            "methodology": {
                "profitability_weight": self._number(
                    self.PROFITABILITY_WEIGHT
                ),
                "expense_control_weight": self._number(
                    self.EXPENSE_CONTROL_WEIGHT
                ),
                "liquidity_weight": self._number(
                    self.LIQUIDITY_WEIGHT
                ),
                "leverage_weight": self._number(
                    self.LEVERAGE_WEIGHT
                ),
                "balance_sheet_weight": self._number(
                    self.BALANCE_SHEET_WEIGHT
                ),
                "description": (
                    "The Financial Health Score is a deterministic "
                    "100-point indicator calculated from profitability, "
                    "expense control, asset-to-liability coverage, "
                    "leverage, and balance-sheet structural checks."
                ),
            },
            "disclaimer": (
                "The Financial Health Score is a deterministic analytical "
                "indicator based on the financial data available in "
                "Angelix. It is not a professional financial rating or "
                "investment recommendation."
            ),
        }

    # ------------------------------------------------------------------
    # Balance Sheet
    # ------------------------------------------------------------------

    def _get_balance_sheet(self, organization_id: int) -> dict[str, Any]:
        statement = (
            FinancialStatement.query.filter(
                FinancialStatement.organization_id == organization_id,
                FinancialStatement.statement_type == "balance_sheet",
                FinancialStatement.processing_status == "completed",
            )
            .order_by(
                FinancialStatement.period_end.desc(),
                FinancialStatement.id.desc(),
            )
            .first()
        )

        if statement is None:
            return {
                "available": False,
                "statement": None,
                "line_items": [],
                "totals": {
                    "assets": 0,
                    "liabilities": 0,
                    "equity": 0,
                    "liabilities_plus_equity": 0,
                    "accounting_difference": 0,
                },
                "accounting_equation_balanced": False,
                "message": (
                    "No completed balance sheet is available for this "
                    "organization."
                ),
            }

        line_items = (
            FinancialStatementLineItem.query.filter(
                FinancialStatementLineItem.financial_statement_id
                == statement.id,
                FinancialStatementLineItem.organization_id
                == organization_id,
            )
            .order_by(FinancialStatementLineItem.id.asc())
            .all()
        )

        assets = Decimal("0")
        liabilities = Decimal("0")
        equity = Decimal("0")

        serialized_items = []

        for item in line_items:
            amount = self._decimal(item.amount)
            account_type = (
                str(item.account_type or "")
                .strip()
                .lower()
            )

            if account_type == "asset":
                assets += amount

            elif account_type == "liability":
                liabilities += amount

            elif account_type == "equity":
                equity += amount

            serialized_items.append(
                {
                    "id": item.id,
                    "line_item_name": item.line_item_name,
                    "normalized_name": item.normalized_name,
                    "section": item.section,
                    "account_type": item.account_type,
                    "amount": self._number(amount),
                    "confidence_score": self._number(
                        item.confidence_score
                    ),
                }
            )

        liabilities_plus_equity = liabilities + equity
        accounting_difference = assets - liabilities_plus_equity

        # Financial statements are considered balanced when the difference
        # is within one cent.
        accounting_equation_balanced = (
            abs(accounting_difference) <= Decimal("0.01")
        )

        return {
            "available": True,
            "statement": {
                "id": statement.id,
                "statement_type": statement.statement_type,
                "period_type": statement.period_type,
                "period_start": (
                    statement.period_start.isoformat()
                    if statement.period_start
                    else None
                ),
                "period_end": (
                    statement.period_end.isoformat()
                    if statement.period_end
                    else None
                ),
                "fiscal_year": statement.fiscal_year,
                "source_filename": statement.source_filename,
                "processing_status": statement.processing_status,
            },
            "line_items": serialized_items,
            "totals": {
                "assets": self._number(assets),
                "liabilities": self._number(liabilities),
                "equity": self._number(equity),
                "liabilities_plus_equity": self._number(
                    liabilities_plus_equity
                ),
                "accounting_difference": self._number(
                    accounting_difference
                ),
            },
            "accounting_equation_balanced": accounting_equation_balanced,
        }

    # ------------------------------------------------------------------
    # Scoring Components
    # ------------------------------------------------------------------

    def _score_profitability(
        self,
        analytics: dict[str, Any],
    ) -> dict[str, Any]:
        margin = self._decimal(
            analytics.get("ratios", {}).get("net_profit_margin")
        )

        if margin >= Decimal("25"):
            score = Decimal("25")
            status = "strong"
        elif margin >= Decimal("20"):
            score = Decimal("22")
            status = "strong"
        elif margin >= Decimal("15"):
            score = Decimal("19")
            status = "healthy"
        elif margin >= Decimal("10"):
            score = Decimal("16")
            status = "healthy"
        elif margin >= Decimal("5"):
            score = Decimal("12")
            status = "moderate"
        elif margin > Decimal("0"):
            score = Decimal("8")
            status = "weak"
        else:
            score = Decimal("0")
            status = "critical"

        return {
            "score": self._number(score),
            "max_score": 25,
            "status": status,
            "metric": self._number(margin),
            "unit": "%",
            "reason": (
                f"Net profit margin is {self._format_number(margin)}%."
            ),
        }

    def _score_expense_control(
        self,
        analytics: dict[str, Any],
    ) -> dict[str, Any]:
        revenue = self._decimal(
            analytics.get("kpis", {}).get("total_revenue")
        )
        expenses = self._decimal(
            analytics.get("kpis", {}).get("total_expenses")
        )

        if revenue <= Decimal("0"):
            return {
                "score": 0,
                "max_score": 20,
                "status": "unavailable",
                "metric": None,
                "unit": "%",
                "reason": (
                    "Expense-control scoring requires positive revenue."
                ),
            }

        expense_ratio = (expenses / revenue) * Decimal("100")

        if expense_ratio <= Decimal("40"):
            score = Decimal("20")
            status = "strong"
        elif expense_ratio <= Decimal("50"):
            score = Decimal("18")
            status = "strong"
        elif expense_ratio <= Decimal("60"):
            score = Decimal("15")
            status = "healthy"
        elif expense_ratio <= Decimal("70"):
            score = Decimal("12")
            status = "moderate"
        elif expense_ratio <= Decimal("80"):
            score = Decimal("8")
            status = "weak"
        elif expense_ratio <= Decimal("100"):
            score = Decimal("4")
            status = "weak"
        else:
            score = Decimal("0")
            status = "critical"

        return {
            "score": self._number(score),
            "max_score": 20,
            "status": status,
            "metric": self._number(expense_ratio),
            "unit": "%",
            "reason": (
                f"Expenses represent "
                f"{self._format_number(expense_ratio)}% of revenue."
            ),
        }

    def _score_liquidity(
        self,
        balance_sheet: dict[str, Any],
    ) -> dict[str, Any]:
        if not balance_sheet.get("available"):
            return {
                "score": 0,
                "max_score": 20,
                "status": "unavailable",
                "metric": None,
                "unit": "x",
                "reason": "A completed balance sheet is required.",
            }

        totals = balance_sheet["totals"]

        assets = self._decimal(totals.get("assets"))
        liabilities = self._decimal(totals.get("liabilities"))

        if liabilities == Decimal("0"):
            if assets > Decimal("0"):
                return {
                    "score": 20,
                    "max_score": 20,
                    "status": "strong",
                    "metric": None,
                    "unit": "x",
                    "reason": (
                        "The organization has positive assets and no "
                        "recorded liabilities."
                    ),
                }

            return {
                "score": 0,
                "max_score": 20,
                "status": "critical",
                "metric": None,
                "unit": "x",
                "reason": (
                    "No liabilities are recorded, but positive assets "
                    "are also unavailable."
                ),
            }

        coverage = assets / liabilities

        if coverage >= Decimal("2.50"):
            score = Decimal("20")
            status = "strong"
        elif coverage >= Decimal("2.00"):
            score = Decimal("18")
            status = "strong"
        elif coverage >= Decimal("1.50"):
            score = Decimal("15")
            status = "healthy"
        elif coverage >= Decimal("1.25"):
            score = Decimal("12")
            status = "moderate"
        elif coverage >= Decimal("1.00"):
            score = Decimal("8")
            status = "weak"
        else:
            score = Decimal("0")
            status = "critical"

        return {
            "score": self._number(score),
            "max_score": 20,
            "status": status,
            "metric": self._number(coverage),
            "unit": "x",
            "reason": (
                "Total assets provide "
                f"{self._format_number(coverage)}x coverage of "
                "total liabilities."
            ),
        }

    def _score_leverage(
        self,
        balance_sheet: dict[str, Any],
    ) -> dict[str, Any]:
        if not balance_sheet.get("available"):
            return {
                "score": 0,
                "max_score": 20,
                "status": "unavailable",
                "metric": None,
                "unit": "x",
                "reason": "A completed balance sheet is required.",
            }

        totals = balance_sheet["totals"]

        liabilities = self._decimal(
            totals.get("liabilities")
        )
        equity = self._decimal(
            totals.get("equity")
        )

        if equity <= Decimal("0"):
            return {
                "score": 0,
                "max_score": 20,
                "status": "critical",
                "metric": None,
                "unit": "x",
                "reason": (
                    "Leverage cannot be considered healthy because "
                    "recorded equity is zero or negative."
                ),
            }

        leverage = liabilities / equity

        if leverage <= Decimal("0.50"):
            score = Decimal("20")
            status = "strong"
        elif leverage <= Decimal("0.75"):
            score = Decimal("18")
            status = "strong"
        elif leverage <= Decimal("1.00"):
            score = Decimal("16")
            status = "healthy"
        elif leverage <= Decimal("1.50"):
            score = Decimal("12")
            status = "moderate"
        elif leverage <= Decimal("2.00"):
            score = Decimal("8")
            status = "weak"
        elif leverage <= Decimal("3.00"):
            score = Decimal("4")
            status = "weak"
        else:
            score = Decimal("0")
            status = "critical"

        return {
            "score": self._number(score),
            "max_score": 20,
            "status": status,
            "metric": self._number(leverage),
            "unit": "x",
            "reason": (
                "Total liabilities are "
                f"{self._format_number(leverage)}x total equity."
            ),
        }

    def _score_balance_sheet_strength(
        self,
        balance_sheet: dict[str, Any],
    ) -> dict[str, Any]:
        if not balance_sheet.get("available"):
            return {
                "score": 0,
                "max_score": 15,
                "status": "unavailable",
                "metric": "0/3",
                "unit": "checks",
                "reason": "A completed balance sheet is required.",
                "checks": {
                    "accounting_equation_balanced": False,
                    "positive_assets": False,
                    "positive_equity": False,
                },
            }

        totals = balance_sheet["totals"]

        assets = self._decimal(totals.get("assets"))
        equity = self._decimal(totals.get("equity"))

        equation_balanced = bool(
            balance_sheet.get("accounting_equation_balanced")
        )
        positive_assets = assets > Decimal("0")
        positive_equity = equity > Decimal("0")

        score = Decimal("0")

        if equation_balanced:
            score += Decimal("7")

        if positive_assets:
            score += Decimal("4")

        if positive_equity:
            score += Decimal("4")

        checks_passed = sum(
            [
                equation_balanced,
                positive_assets,
                positive_equity,
            ]
        )

        if checks_passed == 3:
            status = "strong"
        elif checks_passed == 2:
            status = "healthy"
        elif checks_passed == 1:
            status = "weak"
        else:
            status = "critical"

        return {
            "score": self._number(score),
            "max_score": 15,
            "status": status,
            "metric": f"{checks_passed}/3",
            "unit": "checks",
            "reason": (
                "Balance-sheet structural checks completed."
            ),
            "checks": {
                "accounting_equation_balanced": equation_balanced,
                "positive_assets": positive_assets,
                "positive_equity": positive_equity,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _health_level(score: Decimal) -> str:
        if score >= Decimal("80"):
            return "Strong"

        if score >= Decimal("65"):
            return "Healthy"

        if score >= Decimal("50"):
            return "Moderate"

        if score >= Decimal("35"):
            return "Weak"

        return "Critical"

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value is None:
            return None

        if isinstance(value, date):
            return value

        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _round_decimal(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))

    @staticmethod
    def _number(value: Any) -> float | int | None:
        if value is None:
            return None

        if isinstance(value, Decimal):
            value = value.quantize(Decimal("0.01"))
            return float(value)

        if isinstance(value, (int, float)):
            return value

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_number(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01')):,.2f}"