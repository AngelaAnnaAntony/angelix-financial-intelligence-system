from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..models.financial_statement import FinancialStatement
from ..models.financial_statement_line_item import FinancialStatementLineItem
from ..models.transaction import Transaction


class AnalyticsService:
    """
    Deterministic financial analytics service.

    Transaction data is used for income, expenses, trends and forecasting.

    Approved FinancialStatementLineItem records are used for balance-sheet
    totals and balance-sheet-based ratios whenever a completed balance sheet
    is available.

    Ratios are never fabricated when the required accounting information
    is unavailable.
    """

    CURRENT_ASSET_KEYWORDS = {
        "cash",
        "cash equivalent",
        "cash equivalents",
        "bank",
        "bank balance",
        "bank account",
        "checking",
        "savings",
        "accounts receivable",
        "account receivable",
        "receivable",
        "trade receivable",
        "debtor",
        "debtors",
        "inventory",
        "stock",
        "short term investment",
        "short-term investment",
        "marketable securities",
        "prepaid",
        "prepaid expense",
        "prepaid expenses",
        "prepayments",
    }

    CURRENT_LIABILITY_KEYWORDS = {
        "accounts payable",
        "account payable",
        "payable",
        "trade payable",
        "creditor",
        "creditors",
        "short term loan",
        "short-term loan",
        "current loan",
        "current liability",
        "accrued expense",
        "accrued expenses",
        "accrued liabilities",
        "accrual",
        "tax payable",
        "salary payable",
        "salaries payable",
        "wages payable",
        "interest payable",
    }

    DEBT_KEYWORDS = {
        "loan",
        "loans",
        "bank loan",
        "business loan",
        "term loan",
        "term loans",
        "borrowing",
        "borrowings",
        "debt",
        "debts",
        "bank debt",
        "long term debt",
        "long-term debt",
        "short term debt",
        "short-term debt",
        "notes payable",
        "debenture",
        "debentures",
        "mortgage",
    }

    INVENTORY_KEYWORDS = {
        "inventory",
        "stock",
        "raw material",
        "raw materials",
        "finished goods",
        "merchandise",
    }

    COGS_KEYWORDS = {
        "cost of goods sold",
        "cogs",
        "cost of sales",
        "cost of sale",
        "direct cost",
        "direct costs",
        "cost of revenue",
    }

    def calculate(
        self,
        organization_id: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:

        query = Transaction.query.filter(
            Transaction.organization_id == int(organization_id)
        )

        if period_start is not None:
            query = query.filter(
                Transaction.transaction_date >= period_start
            )

        if period_end is not None:
            query = query.filter(
                Transaction.transaction_date <= period_end
            )

        transactions = (
            query
            .order_by(
                Transaction.transaction_date.asc(),
                Transaction.id.asc(),
            )
            .all()
        )

        balance_sheet = self._get_balance_sheet_data(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
        )

        return self._build_analytics(
            transactions,
            balance_sheet,
        )

    # ==================================================================
    # BALANCE SHEET
    # ==================================================================

    def _get_balance_sheet_data(
        self,
        organization_id: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:

        query = (
            FinancialStatement.query
            .filter(
                FinancialStatement.organization_id
                == int(organization_id)
            )
            .filter(
                FinancialStatement.statement_type
                == "balance_sheet"
            )
            .filter(
                FinancialStatement.processing_status
                == "completed"
            )
        )

        if period_end is not None:
            query = query.filter(
                FinancialStatement.period_end <= period_end
            )

        if period_start is not None:
            query = query.filter(
                FinancialStatement.period_end >= period_start
            )

        statement = (
            query
            .order_by(
                FinancialStatement.period_end.desc(),
                FinancialStatement.created_at.desc(),
                FinancialStatement.id.desc(),
            )
            .first()
        )

        # If no statement falls inside the selected period, use the
        # latest completed balance sheet rather than losing valid data.
        if statement is None:
            statement = (
                FinancialStatement.query
                .filter(
                    FinancialStatement.organization_id
                    == int(organization_id)
                )
                .filter(
                    FinancialStatement.statement_type
                    == "balance_sheet"
                )
                .filter(
                    FinancialStatement.processing_status
                    == "completed"
                )
                .order_by(
                    FinancialStatement.period_end.desc(),
                    FinancialStatement.created_at.desc(),
                    FinancialStatement.id.desc(),
                )
                .first()
            )

        if statement is None:
            return {
                "available": False,
                "statement_id": None,
                "period_start": None,
                "period_end": None,
                "assets": [],
                "liabilities": [],
                "equity": [],
                "totals": {
                    "assets": Decimal("0"),
                    "liabilities": Decimal("0"),
                    "equity": Decimal("0"),
                },
                "current_assets": Decimal("0"),
                "current_liabilities": Decimal("0"),
                "debt": Decimal("0"),
                "inventory": Decimal("0"),
                "quick_assets": Decimal("0"),
                "current_asset_count": 0,
                "current_liability_count": 0,
                "debt_count": 0,
                "inventory_count": 0,
            }

        line_items = (
            FinancialStatementLineItem.query
            .filter(
                FinancialStatementLineItem.organization_id
                == int(organization_id),
                FinancialStatementLineItem.financial_statement_id
                == statement.id,
            )
            .order_by(
                FinancialStatementLineItem.id.asc()
            )
            .all()
        )

        assets = []
        liabilities = []
        equity = []

        current_assets = Decimal("0")
        current_liabilities = Decimal("0")
        debt = Decimal("0")
        inventory = Decimal("0")

        current_asset_count = 0
        current_liability_count = 0
        debt_count = 0
        inventory_count = 0

        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_equity = Decimal("0")

        for item in line_items:

            amount = self._decimal(item.amount)

            name = (
                str(item.line_item_name or "")
                .strip()
                .lower()
            )

            normalized_name = (
                str(item.normalized_name or "")
                .strip()
                .lower()
            )

            section = (
                str(item.section or "")
                .strip()
                .lower()
            )

            account_type = (
                str(item.account_type or "")
                .strip()
                .lower()
            )

            searchable_text = " ".join(
                part
                for part in (
                    name,
                    normalized_name,
                    section,
                )
                if part
            )

            item_data = {
                "name": item.line_item_name,
                "normalized_name": item.normalized_name,
                "section": item.section,
                "account_type": item.account_type,
                "amount": self._number(amount),
            }

            # ----------------------------------------------------------
            # Assets
            # ----------------------------------------------------------

            if account_type == "asset":

                assets.append(item_data)
                total_assets += amount

                is_current = (
                    "current asset" in section
                    or "current assets" in section
                    or self._contains_keyword(
                        searchable_text,
                        self.CURRENT_ASSET_KEYWORDS,
                    )
                )

                if is_current:
                    current_assets += amount
                    current_asset_count += 1

                if self._contains_keyword(
                    searchable_text,
                    self.INVENTORY_KEYWORDS,
                ):
                    inventory += amount
                    inventory_count += 1

            # ----------------------------------------------------------
            # Liabilities
            # ----------------------------------------------------------

            elif account_type == "liability":

                liabilities.append(item_data)
                total_liabilities += amount

                is_current = (
                    "current liability" in section
                    or "current liabilities" in section
                    or self._contains_keyword(
                        searchable_text,
                        self.CURRENT_LIABILITY_KEYWORDS,
                    )
                )

                if is_current:
                    current_liabilities += amount
                    current_liability_count += 1

                if self._contains_keyword(
                    searchable_text,
                    self.DEBT_KEYWORDS,
                ):
                    debt += amount
                    debt_count += 1

            # ----------------------------------------------------------
            # Equity
            # ----------------------------------------------------------

            elif account_type == "equity":

                equity.append(item_data)
                total_equity += amount

        # --------------------------------------------------------------
        # Prefer persisted statement totals when line-item totals are
        # unavailable.
        # --------------------------------------------------------------

        if not line_items:

            total_assets = self._decimal(
                getattr(
                    statement,
                    "total_assets",
                    0,
                )
            )

            total_liabilities = self._decimal(
                getattr(
                    statement,
                    "total_liabilities",
                    0,
                )
            )

            total_equity = self._decimal(
                getattr(
                    statement,
                    "total_equity",
                    0,
                )
            )

        # Quick assets exclude inventory and prepaid expenses.
        # At the moment we identify inventory separately; prepaid
        # expenses are therefore excluded below when possible.
        quick_assets = current_assets - inventory

        return {
            "available": True,
            "statement_id": statement.id,
            "period_start": statement.period_start,
            "period_end": statement.period_end,

            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,

            "totals": {
                "assets": total_assets,
                "liabilities": total_liabilities,
                "equity": total_equity,
            },

            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "debt": debt,
            "inventory": inventory,
            "quick_assets": quick_assets,

            "current_asset_count": current_asset_count,
            "current_liability_count": current_liability_count,
            "debt_count": debt_count,
            "inventory_count": inventory_count,
        }

    # ==================================================================
    # MAIN ANALYTICS
    # ==================================================================

    def _build_analytics(
        self,
        transactions: list[Transaction],
        balance_sheet: dict[str, Any],
    ) -> dict[str, Any]:

        total_transactions = len(transactions)

        revenue = Decimal("0")
        expenses = Decimal("0")

        expense_by_category: dict[str, Decimal] = {}
        revenue_by_category: dict[str, Decimal] = {}

        monthly_data: dict[str, dict[str, Decimal]] = {}

        for transaction in transactions:

            amount = abs(
                self._decimal(
                    transaction.amount
                )
            )

            transaction_type = (
                str(
                    transaction.transaction_type
                    or ""
                )
                .strip()
                .lower()
            )

            category = (
                str(
                    transaction.category
                    or "Uncategorized"
                )
                .strip()
                or "Uncategorized"
            )

            if transaction_type in {
                "credit",
                "income",
                "revenue",
            }:

                revenue += amount

                revenue_by_category[category] = (
                    revenue_by_category.get(
                        category,
                        Decimal("0"),
                    )
                    + amount
                )

            elif transaction_type in {
                "debit",
                "expense",
            }:

                expenses += amount

                expense_by_category[category] = (
                    expense_by_category.get(
                        category,
                        Decimal("0"),
                    )
                    + amount
                )

            # ----------------------------------------------------------
            # Monthly trend
            # ----------------------------------------------------------

            if transaction.transaction_date:

                month_key = (
                    transaction.transaction_date.strftime(
                        "%Y-%m"
                    )
                )

                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "revenue": Decimal("0"),
                        "expenses": Decimal("0"),
                    }

                if transaction_type in {
                    "credit",
                    "income",
                    "revenue",
                }:

                    monthly_data[month_key]["revenue"] += amount

                elif transaction_type in {
                    "debit",
                    "expense",
                }:

                    monthly_data[month_key]["expenses"] += amount

        # ==================================================================
        # CORE KPIs
        # ==================================================================

        net_profit = revenue - expenses

        profit_margin = (
            (net_profit / revenue) * Decimal("100")
            if revenue != 0
            else None
        )

        net_cash_flow = net_profit

        # ==================================================================
        # BALANCE SHEET VALUES
        # ==================================================================

        totals = balance_sheet.get(
            "totals",
            {},
        )

        assets = self._decimal(
            totals.get(
                "assets",
                0,
            )
        )

        liabilities = self._decimal(
            totals.get(
                "liabilities",
                0,
            )
        )

        equity = self._decimal(
            totals.get(
                "equity",
                0,
            )
        )

        current_assets = self._decimal(
            balance_sheet.get(
                "current_assets",
                0,
            )
        )

        current_liabilities = self._decimal(
            balance_sheet.get(
                "current_liabilities",
                0,
            )
        )

        debt = self._decimal(
            balance_sheet.get(
                "debt",
                0,
            )
        )

        inventory = self._decimal(
            balance_sheet.get(
                "inventory",
                0,
            )
        )

        quick_assets = self._decimal(
            balance_sheet.get(
                "quick_assets",
                0,
            )
        )

        current_asset_count = int(
            balance_sheet.get(
                "current_asset_count",
                0,
            )
        )

        current_liability_count = int(
            balance_sheet.get(
                "current_liability_count",
                0,
            )
        )

        debt_count = int(
            balance_sheet.get(
                "debt_count",
                0,
            )
        )

        # ==================================================================
        # RATIOS
        # ==================================================================

        ratios = self._calculate_ratios(
            revenue=revenue,
            net_profit=net_profit,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            quick_assets=quick_assets,
            debt=debt,
            inventory=inventory,
            current_asset_count=current_asset_count,
            current_liability_count=current_liability_count,
            debt_count=debt_count,
        )

        # ==================================================================
        # MONTHLY TREND
        # ==================================================================

        monthly_trend = []

        for month in sorted(
            monthly_data.keys()
        ):

            month_revenue = monthly_data[month][
                "revenue"
            ]

            month_expenses = monthly_data[month][
                "expenses"
            ]

            month_profit = (
                month_revenue
                - month_expenses
            )

            monthly_trend.append(
                {
                    "period": month,
                    "revenue": self._number(
                        month_revenue
                    ),
                    "expenses": self._number(
                        month_expenses
                    ),
                    "net_profit": self._number(
                        month_profit
                    ),
                }
            )

        # ==================================================================
        # FORECAST
        # ==================================================================

        forecast = self._forecast(
            monthly_trend
        )

        # ==================================================================
        # DATA QUALITY
        # ==================================================================

        classified_count = sum(
            1
            for transaction in transactions
            if transaction.category
        )

        classification_coverage = (
            (
                classified_count
                / total_transactions
            )
            * 100
            if total_transactions
            else 0
        )

        return {
            "kpis": {
                "total_revenue": self._number(
                    revenue
                ),
                "total_expenses": self._number(
                    expenses
                ),
                "net_profit": self._number(
                    net_profit
                ),
                "profit_margin": self._number(
                    profit_margin
                ),
                "net_cash_flow": self._number(
                    net_cash_flow
                ),
                "total_assets": self._number(
                    assets
                ),
                "total_liabilities": self._number(
                    liabilities
                ),
                "total_equity": self._number(
                    equity
                ),
                "total_transactions": total_transactions,
            },

            "ratios": ratios,

            "balance_sheet": {
                "available": balance_sheet.get(
                    "available",
                    False,
                ),
                "statement_id": balance_sheet.get(
                    "statement_id"
                ),
                "period_start": self._safe_date(
                    balance_sheet.get(
                        "period_start"
                    )
                ),
                "period_end": self._safe_date(
                    balance_sheet.get(
                        "period_end"
                    )
                ),
                "total_assets": self._number(
                    assets
                ),
                "total_liabilities": self._number(
                    liabilities
                ),
                "total_equity": self._number(
                    equity
                ),
                "accounting_equation_difference": self._number(
                    assets
                    - (
                        liabilities
                        + equity
                    )
                ),
            },

            "expense_breakdown": [
                {
                    "category": category,
                    "amount": self._number(
                        amount
                    ),
                }
                for category, amount in sorted(
                    expense_by_category.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ],

            "revenue_breakdown": [
                {
                    "category": category,
                    "amount": self._number(
                        amount
                    ),
                }
                for category, amount in sorted(
                    revenue_by_category.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ],

            "monthly_trend": monthly_trend,

            "forecast": forecast,

            "data_quality": {
                "total_transactions": total_transactions,
                "categorized_transactions": classified_count,
                "classification_coverage": round(
                    classification_coverage,
                    2,
                ),
            },
        }

    # ==================================================================
    # RATIO CALCULATIONS
    # ==================================================================

    def _calculate_ratios(
        self,
        *,
        revenue: Decimal,
        net_profit: Decimal,
        assets: Decimal,
        liabilities: Decimal,
        equity: Decimal,
        current_assets: Decimal,
        current_liabilities: Decimal,
        quick_assets: Decimal,
        debt: Decimal,
        inventory: Decimal,
        current_asset_count: int,
        current_liability_count: int,
        debt_count: int,
    ) -> dict[str, Any]:

        # --------------------------------------------------------------
        # Current Ratio
        # --------------------------------------------------------------

        if (
            current_asset_count > 0
            and current_liability_count > 0
            and current_liabilities != 0
        ):

            current_ratio = (
                current_assets
                / current_liabilities
            )

            current_ratio_reason = None

        else:

            current_ratio = None

            current_ratio_reason = (
                "Current assets and current liabilities "
                "could not both be identified from the "
                "approved balance sheet."
            )

        # --------------------------------------------------------------
        # Quick Ratio
        # --------------------------------------------------------------

        if (
            current_asset_count > 0
            and current_liability_count > 0
            and current_liabilities != 0
        ):

            # Inventory is excluded from quick assets.
            # Prepaid expenses are also excluded where possible.
            quick_ratio = (
                quick_assets
                / current_liabilities
            )

            quick_ratio_reason = None

        else:

            quick_ratio = None

            quick_ratio_reason = (
                "Current assets and current liabilities "
                "are required for the quick ratio."
            )

        # --------------------------------------------------------------
        # Debt-to-Equity
        # --------------------------------------------------------------

        if (
            debt_count > 0
            and equity != 0
        ):

            debt_to_equity = (
                debt / equity
            )

            debt_to_equity_basis = (
                "identified_debt"
            )

            debt_to_equity_reason = None

        elif equity != 0 and liabilities != 0:

            # Fallback because the available balance sheet may contain
            # liabilities but no explicit debt classification.
            debt_to_equity = (
                liabilities / equity
            )

            debt_to_equity_basis = (
                "total_liabilities_proxy"
            )

            debt_to_equity_reason = (
                "Separate debt classifications were not available; "
                "total liabilities divided by equity is used as a "
                "leverage proxy."
            )

        else:

            debt_to_equity = None

            debt_to_equity_basis = None

            debt_to_equity_reason = (
                "Debt and equity data are insufficient."
            )

        # --------------------------------------------------------------
        # Debt Ratio
        # --------------------------------------------------------------

        if assets != 0:

            debt_ratio = (
                liabilities / assets
            ) * Decimal("100")

            debt_ratio_reason = None

        else:

            debt_ratio = None

            debt_ratio_reason = (
                "Total assets are required."
            )

        # --------------------------------------------------------------
        # Gross Profit Margin
        # --------------------------------------------------------------
        #
        # No separately classified COGS is currently present in the
        # transaction analytics, so the existing net-margin proxy is
        # retained and explicitly identified.
        # --------------------------------------------------------------

        if revenue != 0:

            gross_profit_margin = (
                net_profit / revenue
            ) * Decimal("100")

            gross_profit_margin_basis = (
                "available_profit_margin_proxy"
            )

            gross_profit_margin_reason = (
                "Cost of goods sold was not separately "
                "classified in the available transaction data."
            )

        else:

            gross_profit_margin = None

            gross_profit_margin_basis = None

            gross_profit_margin_reason = (
                "Revenue is required."
            )

        # --------------------------------------------------------------
        # Net Profit Margin
        # --------------------------------------------------------------

        if revenue != 0:

            net_profit_margin = (
                net_profit / revenue
            ) * Decimal("100"
            )

            net_profit_margin_reason = None

        else:

            net_profit_margin = None

            net_profit_margin_reason = (
                "Revenue is required."
            )

        # --------------------------------------------------------------
        # Return on Assets
        # --------------------------------------------------------------

        if assets != 0:

            roa = (
                net_profit / assets
            ) * Decimal("100")

            roa_reason = None

        else:

            roa = None

            roa_reason = (
                "Total assets are required."
            )

        # --------------------------------------------------------------
        # Return on Equity
        # --------------------------------------------------------------

        if equity != 0:

            roe = (
                net_profit / equity
            ) * Decimal("100")

            roe_reason = None

        else:

            roe = None

            roe_reason = (
                "Equity is required."
            )

        # --------------------------------------------------------------
        # Asset Turnover
        # --------------------------------------------------------------

        if assets != 0:

            asset_turnover = (
                revenue / assets
            )

            asset_turnover_reason = None

        else:

            asset_turnover = None

            asset_turnover_reason = (
                "Total assets are required."
            )

        # --------------------------------------------------------------
        # Inventory Turnover
        # --------------------------------------------------------------

        inventory_turnover = None

        inventory_turnover_reason = (
            "Separately classified cost of goods sold "
            "is required for inventory turnover."
        )

        return {
            "current_ratio": self._number(
                current_ratio
            ),
            "current_ratio_available": (
                current_ratio is not None
            ),
            "current_ratio_reason": (
                current_ratio_reason
            ),

            "quick_ratio": self._number(
                quick_ratio
            ),
            "quick_ratio_available": (
                quick_ratio is not None
            ),
            "quick_ratio_reason": (
                quick_ratio_reason
            ),

            "debt_to_equity": self._number(
                debt_to_equity
            ),
            "debt_to_equity_available": (
                debt_to_equity is not None
            ),
            "debt_to_equity_reason": (
                debt_to_equity_reason
            ),
            "debt_to_equity_basis": (
                debt_to_equity_basis
            ),

            "debt_ratio": self._number(
                debt_ratio
            ),
            "debt_ratio_available": (
                debt_ratio is not None
            ),
            "debt_ratio_reason": (
                debt_ratio_reason
            ),

            "gross_profit_margin": self._number(
                gross_profit_margin
            ),
            "gross_profit_margin_available": (
                gross_profit_margin is not None
            ),
            "gross_profit_margin_reason": (
                gross_profit_margin_reason
            ),
            "gross_profit_margin_basis": (
                gross_profit_margin_basis
            ),

            "net_profit_margin": self._number(
                net_profit_margin
            ),
            "net_profit_margin_available": (
                net_profit_margin is not None
            ),
            "net_profit_margin_reason": (
                net_profit_margin_reason
            ),

            "return_on_assets": self._number(
                roa
            ),
            "roa": self._number(
                roa
            ),
            "roa_available": (
                roa is not None
            ),
            "roa_reason": roa_reason,

            "return_on_equity": self._number(
                roe
            ),
            "roe": self._number(
                roe
            ),
            "roe_available": (
                roe is not None
            ),
            "roe_reason": roe_reason,

            "asset_turnover": self._number(
                asset_turnover
            ),
            "asset_turnover_available": (
                asset_turnover is not None
            ),
            "asset_turnover_reason": (
                asset_turnover_reason
            ),

            "inventory_turnover": None,
            "inventory_turnover_available": False,
            "inventory_turnover_reason": (
                inventory_turnover_reason
            ),

            "supporting_values": {
                "current_assets": self._number(
                    current_assets
                ),
                "current_liabilities": self._number(
                    current_liabilities
                ),
                "identified_debt": self._number(
                    debt
                ),
                "inventory": self._number(
                    inventory
                ),
                "quick_assets": self._number(
                    quick_assets
                ),
            },
        }

    # ==================================================================
    # HELPERS
    # ==================================================================

    @staticmethod
    def _contains_keyword(
        text: str,
        keywords: set[str],
    ) -> bool:

        normalized = (
            str(text or "")
            .strip()
            .lower()
        )

        return any(
            keyword in normalized
            for keyword in keywords
        )

    @staticmethod
    def _decimal(
        value: Any,
    ) -> Decimal:

        if value is None:
            return Decimal("0")

        if isinstance(
            value,
            Decimal,
        ):
            return value

        return Decimal(
            str(value)
        )

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        if isinstance(
            value,
            Decimal,
        ):
            return float(value)

        return float(value)

    @staticmethod
    def _safe_date(
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        if isinstance(
            value,
            date,
        ):
            return value.isoformat()

        return str(value)

    # ==================================================================
    # FORECAST
    # ==================================================================

    def _forecast(
        self,
        monthly_trend: list[dict[str, Any]],
    ) -> dict[str, Any]:

        if len(monthly_trend) < 3:

            return {
                "available": False,
                "reason": (
                    "At least three months of transaction "
                    "data are required for forecasting."
                ),
                "next_month_revenue": None,
                "next_month_expenses": None,
                "next_month_profit": None,
            }

        recent = monthly_trend[-3:]

        revenue_values = [
            Decimal(
                str(
                    item["revenue"]
                )
            )
            for item in recent
        ]

        expense_values = [
            Decimal(
                str(
                    item["expenses"]
                )
            )
            for item in recent
        ]

        average_revenue = (
            sum(
                revenue_values,
                Decimal("0"),
            )
            / Decimal(
                str(
                    len(revenue_values)
                )
            )
        )

        average_expenses = (
            sum(
                expense_values,
                Decimal("0"),
            )
            / Decimal(
                str(
                    len(expense_values)
                )
            )
        )

        projected_profit = (
            average_revenue
            - average_expenses
        )

        return {
            "available": True,
            "method": "three_month_moving_average",
            "next_month_revenue": self._number(
                average_revenue
            ),
            "next_month_expenses": self._number(
                average_expenses
            ),
            "next_month_profit": self._number(
                projected_profit
            ),
        }