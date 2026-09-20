"""
Angelix Financial Statement Routes.

This module presents the organization's financial statements using:

1. Transaction data for:
   - Income Statement
   - Profit & Loss Statement
   - Cash Flow Statement

2. Approved FinancialStatementLineItem records for:
   - Balance Sheet

All data is restricted to the authenticated user's organization.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, render_template, request
from flask_login import login_required

from ..models.financial_statement import FinancialStatement
from ..models.financial_statement_line_item import (
    FinancialStatementLineItem,
)
from ..models.transaction import Transaction
from ..services.access_service import require_member


statement_bp = Blueprint(
    "statements",
    __name__,
    url_prefix="/organizations",
)


# ============================================================================
# HELPERS
# ============================================================================

def _decimal(value) -> Decimal:
    """
    Safely convert a database numeric value to Decimal.
    """

    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _money(value) -> float:
    """
    Convert Decimal values into JSON/template-friendly numbers.
    """

    return float(
        _decimal(value).quantize(
            Decimal("0.01")
        )
    )


def _parse_date(value, default):
    """
    Parse an ISO date or return the supplied default.
    """

    if not value:
        return default

    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _statement_period(organization_id):
    """
    Determine the default reporting period.

    If the organization already has a financial statement, use the
    latest statement period. Otherwise use the current financial year
    represented by the application's existing data.
    """

    latest_statement = (
        FinancialStatement.query
        .filter(
            FinancialStatement.organization_id
            == int(organization_id)
        )
        .order_by(
            FinancialStatement.period_end.desc(),
            FinancialStatement.id.desc(),
        )
        .first()
    )

    if latest_statement:
        return (
            latest_statement.period_start,
            latest_statement.period_end,
        )

    return (
        date(2026, 4, 1),
        date(2027, 3, 31),
    )


# ============================================================================
# INCOME STATEMENT
# ============================================================================

def _build_income_statement(transactions):
    """
    Build an Income Statement / Profit & Loss Statement from transactions.
    """

    revenue_by_category = {}
    expense_by_category = {}

    total_revenue = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for transaction in transactions:

        amount = abs(
            _decimal(transaction.amount)
        )

        transaction_type = (
            str(transaction.transaction_type or "")
            .strip()
            .lower()
        )

        category = (
            str(transaction.category or "Uncategorized")
            .strip()
            or "Uncategorized"
        )

        if transaction_type in {
            "credit",
            "income",
            "revenue",
        }:

            total_revenue += amount

            revenue_by_category[category] = (
                revenue_by_category.get(
                    category,
                    Decimal("0.00"),
                )
                + amount
            )

        elif transaction_type in {
            "debit",
            "expense",
        }:

            total_expenses += amount

            expense_by_category[category] = (
                expense_by_category.get(
                    category,
                    Decimal("0.00"),
                )
                + amount
            )

    net_profit = (
        total_revenue
        - total_expenses
    )

    profit_margin = (
        (net_profit / total_revenue)
        * Decimal("100")
        if total_revenue
        else Decimal("0.00")
    )

    return {
        "revenue": [
            {
                "name": category,
                "amount": _money(amount),
            }
            for category, amount
            in sorted(
                revenue_by_category.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ],

        "expenses": [
            {
                "name": category,
                "amount": _money(amount),
            }
            for category, amount
            in sorted(
                expense_by_category.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ],

        "total_revenue": _money(
            total_revenue
        ),

        "total_expenses": _money(
            total_expenses
        ),

        "net_profit": _money(
            net_profit
        ),

        "profit_margin": _money(
            profit_margin
        ),
    }


# ============================================================================
# BALANCE SHEET
# ============================================================================

def _build_balance_sheet(statement):
    """
    Build the Balance Sheet from approved financial statement line items.
    """

    assets = []
    liabilities = []
    equity = []

    total_assets = Decimal("0.00")
    total_liabilities = Decimal("0.00")
    total_equity = Decimal("0.00")

    if statement is not None:

        line_items = (
            FinancialStatementLineItem.query
            .filter(
                FinancialStatementLineItem.financial_statement_id
                == statement.id
            )
            .order_by(
                FinancialStatementLineItem.id.asc()
            )
            .all()
        )

        for item in line_items:

            amount = _decimal(
                item.amount
            )

            account_type = (
                str(item.account_type or "")
                .strip()
                .lower()
            )

            row = {
                "id": item.id,
                "name": item.line_item_name,
                "amount": _money(amount),
                "section": item.section,
            }

            if account_type == "asset":

                assets.append(row)
                total_assets += amount

            elif account_type == "liability":

                liabilities.append(row)
                total_liabilities += amount

            elif account_type == "equity":

                equity.append(row)
                total_equity += amount

    accounting_equation_difference = (
        total_assets
        - (
            total_liabilities
            + total_equity
        )
    )

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,

        "total_assets": _money(
            total_assets
        ),

        "total_liabilities": _money(
            total_liabilities
        ),

        "total_equity": _money(
            total_equity
        ),

        "accounting_equation_difference": _money(
            accounting_equation_difference
        ),

        "is_balanced": (
            accounting_equation_difference
            == Decimal("0.00")
        ),
    }


# ============================================================================
# CASH FLOW
# ============================================================================

def _build_cash_flow(transactions):
    """
    Build a simplified cash-flow view from available transactions.

    The current database does not contain dedicated cash-flow account
    classifications, therefore this is presented as a transaction-based
    operating cash-flow proxy.
    """

    cash_inflows = Decimal("0.00")
    cash_outflows = Decimal("0.00")

    for transaction in transactions:

        amount = abs(
            _decimal(transaction.amount)
        )

        transaction_type = (
            str(transaction.transaction_type or "")
            .strip()
            .lower()
        )

        if transaction_type in {
            "credit",
            "income",
            "revenue",
        }:

            cash_inflows += amount

        elif transaction_type in {
            "debit",
            "expense",
        }:

            cash_outflows += amount

    net_cash_flow = (
        cash_inflows
        - cash_outflows
    )

    return {
        "cash_inflows": _money(
            cash_inflows
        ),

        "cash_outflows": _money(
            cash_outflows
        ),

        "net_cash_flow": _money(
            net_cash_flow
        ),
    }


# ============================================================================
# MAIN STATEMENT PAGE
# ============================================================================

@statement_bp.get("/<organization_id>/statements")
@login_required
def list_statements(organization_id):
    """
    Display the organization's financial statements.
    """

    # ------------------------------------------------------------------------
    # Verify organization access
    # ------------------------------------------------------------------------

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    # ------------------------------------------------------------------------
    # Determine default reporting period
    # ------------------------------------------------------------------------

    default_start, default_end = (
        _statement_period(
            organization_id
        )
    )

    # ------------------------------------------------------------------------
    # Parse requested reporting period
    # ------------------------------------------------------------------------

    start = _parse_date(
        request.args.get("start"),
        default_start,
    )

    end = _parse_date(
        request.args.get("end"),
        default_end,
    )

    if start > end:

        return (
            "Start date cannot be after end date.",
            400,
        )

    # ------------------------------------------------------------------------
    # Retrieve transactions
    # ------------------------------------------------------------------------

    transactions = (
        Transaction.query
        .filter(
            Transaction.organization_id
            == int(organization_id),

            Transaction.transaction_date
            .between(
                start,
                end,
            ),
        )
        .order_by(
            Transaction.transaction_date.asc(),
            Transaction.id.asc(),
        )
        .all()
    )

    # ------------------------------------------------------------------------
    # Find the financial statement matching the selected period
    # ------------------------------------------------------------------------

    statement = (
        FinancialStatement.query
        .filter(
            FinancialStatement.organization_id
            == int(organization_id),

            FinancialStatement.period_start
            == start,

            FinancialStatement.period_end
            == end,
        )
        .order_by(
            FinancialStatement.id.desc()
        )
        .first()
    )

    # ------------------------------------------------------------------------
    # Build statements
    # ------------------------------------------------------------------------

    income_statement = (
        _build_income_statement(
            transactions
        )
    )

    balance_sheet = (
        _build_balance_sheet(
            statement
        )
    )

    cash_flow = (
        _build_cash_flow(
            transactions
        )
    )

    # ------------------------------------------------------------------------
    # Combined data object
    # ------------------------------------------------------------------------

    data = {

        "income_statement":
            income_statement,

        "profit_loss":
            income_statement,

        "balance_sheet":
            balance_sheet,

        "cash_flow":
            cash_flow,

        "summary": {

            "revenue":
                income_statement[
                    "total_revenue"
                ],

            "expenses":
                income_statement[
                    "total_expenses"
                ],

            "net_profit":
                income_statement[
                    "net_profit"
                ],

            "total_assets":
                balance_sheet[
                    "total_assets"
                ],

            "total_liabilities":
                balance_sheet[
                    "total_liabilities"
                ],

            "total_equity":
                balance_sheet[
                    "total_equity"
                ],

        },

    }

    # ------------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------------

    return render_template(
        "statements/view.html",

        data=data,

        organization=organization,

        organization_id=organization_id,

        start=start,

        end=end,

        statement=statement,

    )