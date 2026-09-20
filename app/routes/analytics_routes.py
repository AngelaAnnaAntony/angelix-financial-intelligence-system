from datetime import date

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..services.access_service import require_member
from ..services.analytics_service import AnalyticsService
from ..services.financial_ai_analysis_service import (
    FinancialAIAnalysisError,
    FinancialAIAnalysisService,
)
from ..services.financial_health_service import (
    FinancialHealthService,
)
from ..services.financial_recommendation_service import (
    FinancialRecommendationError,
    FinancialRecommendationService,
)


analytics_bp = Blueprint(
    "analytics",
    __name__,
    url_prefix="/organizations",
)


def _parse_reporting_period():
    """
    Parse the requested reporting period.

    Defaults to the current Angelix academic/demo reporting period
    currently used by the analytics page.
    """

    try:
        start = date.fromisoformat(
            request.values.get(
                "start",
                "2026-04-01",
            )
        )

        end = date.fromisoformat(
            request.values.get(
                "end",
                "2027-03-31",
            )
        )

    except ValueError:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        )

    if start > end:
        raise ValueError(
            "Start date cannot be after end date."
        )

    return start, end


def _build_ai_context(
    health_result,
    analytics_data,
    start,
    end,
):
    """
    Build the common deterministic context consumed by the
    AI analysis and recommendation services.

    The deterministic services remain authoritative for all
    financial calculations.
    """

    reporting_period = health_result.get(
        "reporting_period",
        {},
    )

    if not reporting_period:
        reporting_period = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    return {
        "financial_health": {
            "score": health_result.get(
                "score"
            ),
            "health_level": health_result.get(
                "health_level"
            ),
            "components": health_result.get(
                "components",
                [],
            ),
            "methodology": health_result.get(
                "methodology"
            ),
            "disclaimer": health_result.get(
                "disclaimer"
            ),
        },
        "analytics": analytics_data,
        "balance_sheet": health_result.get(
            "balance_sheet",
            {},
        ),
        "reporting_period": reporting_period,
    }


def _load_analytics_context(
    organization_id,
    start,
    end,
):
    """
    Load deterministic analytics and financial health data.
    """

    analytics_data = AnalyticsService().calculate(
        organization_id,
        start,
        end,
    )

    health_result = FinancialHealthService().calculate(
        organization_id,
        start,
        end,
    )

    return analytics_data, health_result


@analytics_bp.route(
    "/<organization_id>/analytics",
    methods=["GET", "POST"],
)
@login_required
def overview(organization_id):
    """
    Display financial analytics for an organization.

    GET:
        Displays deterministic financial analytics,
        financial health and balance-sheet information.

    POST:
        Generates AI financial analysis and AI recommendations
        explicitly requested by the user.
    """

    try:
        require_member(organization_id)
    except PermissionError:
        return ("Forbidden", 403)

    try:
        start, end = _parse_reporting_period()
    except ValueError as exc:
        return (
            str(exc),
            400,
        )

    analytics_data, health_result = (
        _load_analytics_context(
            organization_id,
            start,
            end,
        )
    )

    ai_analysis = None
    ai_recommendations = None
    ai_generated = False

    if request.method == "POST":

        action = request.form.get(
            "action",
            "generate_ai",
        ).strip().lower()

        if action == "generate_ai":

            ai_context = _build_ai_context(
                health_result=health_result,
                analytics_data=analytics_data,
                start=start,
                end=end,
            )

            try:
                ai_analysis = (
                    FinancialAIAnalysisService().generate(
                        ai_context
                    )
                )

                recommendation_result = (
                    FinancialRecommendationService().generate(
                        organization_id
                    )
                )

                ai_recommendations = (
                    recommendation_result.get(
                        "recommendations",
                        [],
                    )
                )

                ai_generated = True

                flash(
                    "AI financial analysis generated successfully.",
                    "success",
                )

            except FinancialAIAnalysisError as exc:

                flash(
                    f"AI financial analysis could not be generated: {exc}",
                    "error",
                )

            except FinancialRecommendationError as exc:

                flash(
                    f"AI recommendations could not be generated: {exc}",
                    "error",
                )

            except Exception as exc:

                flash(
                    f"Unable to generate AI financial insights: {exc}",
                    "error",
                )

        else:

            flash(
                "Unknown analytics action.",
                "error",
            )

    return render_template(
        "analytics/overview.html",
        data=analytics_data,
        health=health_result,
        ai_analysis=ai_analysis,
        ai_recommendations=ai_recommendations,
        ai_generated=ai_generated,
        start=start,
        end=end,
        organization_id=organization_id,
        current_user=current_user,
    )