"""
Angelix Dashboard Routes.

The dashboard route assembles organization-scoped financial data
for the presentation layer.

Transaction-based KPIs and analytical data are delegated to
AnalyticsService.

Balance-sheet totals are calculated directly from the approved
FinancialStatementLineItem records so that the dashboard reflects
the financial statement review workflow accurately.

Financial Health Score is calculated by FinancialHealthService using
the same organization-scoped financial data.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..models.financial_statement import FinancialStatement
from ..models.organization import Organization
from ..models.transaction import Transaction
from ..models.upload import Upload
from ..services.access_service import require_member
from ..services.analytics_service import AnalyticsService
from ..services.financial_health_service import FinancialHealthService


# ============================================================================
# BLUEPRINT
# ============================================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
)


# ============================================================================
# HELPERS
# ============================================================================

def _zero_financial_position() -> dict:
    """
    Return an empty financial-position structure.

    Decimal values are used so financial calculations remain precise
    and consistent with PostgreSQL Numeric fields.
    """

    return {
        "total_assets": Decimal("0.00"),
        "total_liabilities": Decimal("0.00"),
        "total_equity": Decimal("0.00"),
    }


def _empty_financial_health() -> dict:
    """
    Return an empty Financial Health Score structure for users who
    do not currently have an organization.
    """

    return {
        "score": 0,
        "max_score": 100,
        "health_level": "Unavailable",
        "components": {},
        "balance_sheet": {
            "available": False,
        },
        "period": {
            "start": None,
            "end": None,
            "source": None,
        },
        "methodology": {},
        "disclaimer": (
            "The Financial Health Score is a deterministic analytical "
            "indicator based on the financial data available in Angelix."
        ),
    }


def _get_latest_balance_sheet(organization_id: int):
    """
    Return the latest completed balance-sheet statement for an
    organization.

    The most recent period_end is preferred. If multiple statements
    have the same period_end, the most recently created statement wins.
    """

    return (
        FinancialStatement.query
        .filter(
            FinancialStatement.organization_id == organization_id,
            FinancialStatement.statement_type == "balance_sheet",
            FinancialStatement.processing_status == "completed",
        )
        .order_by(
            FinancialStatement.period_end.desc(),
            FinancialStatement.created_at.desc(),
            FinancialStatement.id.desc(),
        )
        .first()
    )


def _calculate_financial_position(organization_id: int) -> dict:
    """
    Calculate balance-sheet totals from approved financial statement
    line items.

    Only line items that exist in FinancialStatementLineItem are used.
    These records are created through the candidate approval workflow,
    meaning rejected or pending candidates do not affect the dashboard.

    Account types supported:
        asset
        liability
        equity
    """

    totals = _zero_financial_position()

    statement = _get_latest_balance_sheet(
        organization_id
    )

    if statement is None:
        return totals

    for line_item in statement.line_items:

        account_type = (
            (line_item.account_type or "")
            .strip()
            .lower()
        )

        amount = line_item.amount

        if amount is None:
            continue

        amount = Decimal(str(amount))

        if account_type == "asset":

            totals["total_assets"] += amount

        elif account_type == "liability":

            totals["total_liabilities"] += amount

        elif account_type == "equity":

            totals["total_equity"] += amount

    return totals


# ============================================================================
# DASHBOARD HOME
# ============================================================================

@dashboard_bp.get("/")
@login_required
def home():
    """
    Display the main Angelix financial dashboard.

    The authenticated user's organization is used as the data boundary.

    Transaction-based KPIs and analytical data come from AnalyticsService.

    Balance-sheet totals come from the latest completed balance sheet's
    approved FinancialStatementLineItem records.

    Financial Health Score comes from FinancialHealthService.
    """

    # ------------------------------------------------------------------------
    # No organization assigned
    # ------------------------------------------------------------------------

    if current_user.organization_id is None:

        return render_template(
            "dashboard/index.html",
            organization=None,
            analytics={
                "revenue": Decimal("0.00"),
                "expenses": Decimal("0.00"),
                "net_profit": Decimal("0.00"),
                "profit_margin": Decimal("0.00"),
                "total_assets": Decimal("0.00"),
                "total_liabilities": Decimal("0.00"),
                "total_equity": Decimal("0.00"),
                "total_transactions": 0,
                "monthly_trends": [],
                "category_breakdown": [],
                "revenue_breakdown": [],
                "ratios": {},
                "forecast": {},
                "data_quality": {},
            },
            financial_health=_empty_financial_health(),
            recent_transactions=[],
            recent_uploads=[],
            recent_statements=[],
        )

    # ------------------------------------------------------------------------
    # Organization access
    # ------------------------------------------------------------------------

    try:

        organization = require_member(
            current_user.organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    # ------------------------------------------------------------------------
    # Financial analytics
    # ------------------------------------------------------------------------

    analytics_result = AnalyticsService().calculate(
        organization.id
    )

    kpis = analytics_result.get(
        "kpis",
        {},
    )

    # ------------------------------------------------------------------------
    # Balance-sheet financial position
    #
    # Do not depend on AnalyticsService for these three values.
    #
    # The approved FinancialStatementLineItem records are the trusted
    # source for:
    #
    #     Total Assets
    #     Total Liabilities
    #     Total Equity
    #
    # This is especially important because financial statement data is
    # created through the extraction candidate review workflow.
    # ------------------------------------------------------------------------

    financial_position = _calculate_financial_position(
        organization.id
    )

    # ------------------------------------------------------------------------
    # Financial Health Score
    #
    # FinancialHealthService automatically uses the latest completed
    # balance-sheet reporting period when no explicit period is supplied.
    # ------------------------------------------------------------------------

    financial_health = FinancialHealthService().calculate(
        organization.id
    )

    # ------------------------------------------------------------------------
    # Normalize analytics data for dashboard presentation
    # ------------------------------------------------------------------------

    dashboard_analytics = {

        # Income-statement KPIs
        "revenue": kpis.get(
            "total_revenue",
            0,
        ),

        "expenses": kpis.get(
            "total_expenses",
            0,
        ),

        "net_profit": kpis.get(
            "net_profit",
            0,
        ),

        "profit_margin": kpis.get(
            "profit_margin",
            0,
        ),

        # Balance-sheet totals
        #
        # These come directly from approved financial statement
        # line items rather than potentially incomplete KPI data.
        "total_assets": financial_position[
            "total_assets"
        ],

        "total_liabilities": financial_position[
            "total_liabilities"
        ],

        "total_equity": financial_position[
            "total_equity"
        ],

        # Additional dashboard metrics
        "total_transactions": kpis.get(
            "total_transactions",
            0,
        ),

        "monthly_trends": analytics_result.get(
            "monthly_trend",
            [],
        ),

        "category_breakdown": analytics_result.get(
            "expense_breakdown",
            [],
        ),

        "revenue_breakdown": analytics_result.get(
            "revenue_breakdown",
            [],
        ),

        "ratios": analytics_result.get(
            "ratios",
            {},
        ),

        "forecast": analytics_result.get(
            "forecast",
            {},
        ),

        "data_quality": analytics_result.get(
            "data_quality",
            {},
        ),

    }

    # ------------------------------------------------------------------------
    # Recent transactions
    # ------------------------------------------------------------------------

    recent_transactions = (
        Transaction.query
        .filter(
            Transaction.organization_id == organization.id
        )
        .order_by(
            Transaction.transaction_date.desc(),
            Transaction.id.desc(),
        )
        .limit(8)
        .all()
    )

    # ------------------------------------------------------------------------
    # Recent uploads
    # ------------------------------------------------------------------------

    recent_uploads = (
        Upload.query
        .filter(
            Upload.organization_id == organization.id,
            Upload.is_deleted.is_(False),
        )
        .order_by(
            Upload.created_at.desc(),
            Upload.id.desc(),
        )
        .limit(5)
        .all()
    )

    # ------------------------------------------------------------------------
    # Recent financial statements
    # ------------------------------------------------------------------------

    recent_statements = (
        FinancialStatement.query
        .filter(
            FinancialStatement.organization_id == organization.id
        )
        .order_by(
            FinancialStatement.created_at.desc(),
            FinancialStatement.id.desc(),
        )
        .limit(5)
        .all()
    )

    # ------------------------------------------------------------------------
    # Render dashboard
    # ------------------------------------------------------------------------

    return render_template(
        "dashboard/index.html",

        organization=organization,

        analytics=dashboard_analytics,

        financial_health=financial_health,

        recent_transactions=recent_transactions,

        recent_uploads=recent_uploads,

        recent_statements=recent_statements,
    )