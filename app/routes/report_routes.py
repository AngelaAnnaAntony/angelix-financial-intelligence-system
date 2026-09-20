"""
ANGELIX Financial Report Routes.

Handles:
- Financial Statements Report generation
- Financial Analysis Report generation
- Financial report history
- Report downloads
- Report deletion

Report architecture
-------------------

1. Financial Statements Report
   Generated from ANGELIX transaction/import data when an existing
   uploaded/extracted financial statement is not already available
   for the selected reporting period.

   Contains:
   - Profit & Loss Statement
   - Income & Expenditure Statement
   - Balance Sheet
   - Cash Flow Summary when supported

2. Financial Analysis Report
   Contains:
   - Executive Financial Summary
   - KPIs
   - Revenue analysis
   - Expense analysis
   - Trends
   - Financial ratios
   - Balance Sheet analysis
   - Financial Health Score
   - Forecast
   - AI Financial Analysis
   - AI Recommendations
   - Data quality

The deterministic financial services remain the source of truth.
AI is used only for interpretation and recommendations.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import and_

from ..extensions import db
from ..models.financial_statement import FinancialStatement
from ..models.report import Report
from ..reports.pdf_generator import (
    generate_financial_analysis_pdf,
    generate_financial_statements_pdf,
)
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


report_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/organizations",
)


# ======================================================================
# CONSTANTS
# ======================================================================

REPORT_TYPE_FINANCIAL_STATEMENTS = (
    "financial_statements"
)

REPORT_TYPE_FINANCIAL_ANALYSIS = (
    "financial_analysis"
)

VALID_REPORT_TYPES = {
    REPORT_TYPE_FINANCIAL_STATEMENTS,
    REPORT_TYPE_FINANCIAL_ANALYSIS,
}


# ======================================================================
# HELPERS
# ======================================================================


def _parse_date(
    value: str | None,
) -> date | None:
    """
    Parse an ISO date from a form field.
    """

    if not value:
        return None

    try:
        return date.fromisoformat(
            value
        )

    except ValueError:
        return None


def _normalize_report_type(
    value: str | None,
) -> str:
    """
    Normalize a report type received from the frontend.

    The current Reports page may not yet provide a report_type field.
    In that case Financial Analysis is used as the safe default.
    """

    normalized = (
        str(value or "")
        .strip()
        .lower()
    )

    aliases = {
        "financial_statement": REPORT_TYPE_FINANCIAL_STATEMENTS,
        "financial_statements": REPORT_TYPE_FINANCIAL_STATEMENTS,
        "statements": REPORT_TYPE_FINANCIAL_STATEMENTS,
        "statement": REPORT_TYPE_FINANCIAL_STATEMENTS,
        "pnl": REPORT_TYPE_FINANCIAL_STATEMENTS,
        "financial_analysis": REPORT_TYPE_FINANCIAL_ANALYSIS,
        "financial_analytics": REPORT_TYPE_FINANCIAL_ANALYSIS,
        "analysis": REPORT_TYPE_FINANCIAL_ANALYSIS,
        "summary": REPORT_TYPE_FINANCIAL_ANALYSIS,
        "financial_summary": REPORT_TYPE_FINANCIAL_ANALYSIS,
    }

    return aliases.get(
        normalized,
        REPORT_TYPE_FINANCIAL_ANALYSIS,
    )


def _serialize_for_json(
    value: Any,
) -> Any:
    """
    Convert common Python/database values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _serialize_for_json(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _serialize_for_json(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        (datetime, date),
    ):
        return value.isoformat()

    try:
        if hasattr(
            value,
            "as_tuple",
        ):
            return float(
                value
            )
    except (
        TypeError,
        ValueError,
    ):
        pass

    return value


def _set_optional_report_field(
    report: Report,
    field_name: str,
    value: Any,
) -> None:
    """
    Safely populate an optional Report model field.

    This keeps the route compatible with the existing Report model
    while allowing newer metadata fields when available.
    """

    if hasattr(
        Report,
        field_name,
    ):
        setattr(
            report,
            field_name,
            value,
        )


def _get_report_file_size(
    report: Report,
) -> int:
    """
    Return the physical report file size when available.
    """

    file_path = getattr(
        report,
        "file_path",
        None,
    )

    if not file_path:
        return 0

    try:

        path = Path(
            file_path
        )

        if path.exists():
            return path.stat().st_size

    except (
        OSError,
        ValueError,
    ):
        pass

    return 0


def _serialize_report(
    report: Report,
) -> dict[str, Any]:
    """
    Convert a Report database object into the JSON structure expected
    by report_history.js.
    """

    created_at = getattr(
        report,
        "created_at",
        None,
    )

    period_start = getattr(
        report,
        "period_start",
        None,
    )

    period_end = getattr(
        report,
        "period_end",
        None,
    )

    report_format = getattr(
        report,
        "format",
        None,
    )

    if not report_format:

        report_format = getattr(
            report,
            "file_format",
            None,
        )

    if not report_format:
        report_format = "pdf"

    report_type = getattr(
        report,
        "report_type",
        None,
    )

    # Normalize legacy database values for the frontend.
    normalized_type = _normalize_report_type(
        report_type
    )

    return _serialize_for_json(
        {
            "id": report.id,
            "title": getattr(
                report,
                "title",
                None,
            ),
            "name": getattr(
                report,
                "title",
                None,
            ),
            "report_type": normalized_type,
            "type": normalized_type,
            "status": getattr(
                report,
                "status",
                "pending",
            ),
            "format": report_format,
            "file_format": report_format,
            "file_size": _get_report_file_size(
                report
            ),
            "created_at": created_at,
            "period_start": period_start,
            "period_end": period_end,
        }
    )


def _build_ai_context(
    health_result: dict[str, Any],
    analytics: dict[str, Any],
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """
    Build deterministic context supplied to the AI services.
    """

    reporting_period = (
        health_result.get(
            "reporting_period",
            {},
        )
        or {}
    )

    if not reporting_period:

        reporting_period = {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        }

    balance_sheet = (
        health_result.get(
            "balance_sheet",
            {},
        )
        or {}
    )

    financial_health = {
        "score": health_result.get(
            "score"
        ),
        "health_level": health_result.get(
            "health_level"
        ),
        "components": health_result.get(
            "components",
            {},
        ),
        "methodology": health_result.get(
            "methodology"
        ),
        "disclaimer": health_result.get(
            "disclaimer"
        ),
    }

    return {
        "reporting_period": reporting_period,
        "financial_health": financial_health,
        "analytics": analytics,
        "balance_sheet": balance_sheet,
    }


def _safe_generate_ai_content(
    organization_id: int,
    health_result: dict[str, Any],
    analytics: dict[str, Any],
    period_start: date,
    period_end: date,
) -> tuple[
    dict[str, Any] | None,
    list[dict[str, Any]],
]:
    """
    Generate AI analysis and recommendations.

    AI failures never prevent a deterministic Financial Analysis Report
    from being generated.
    """

    ai_analysis = None

    recommendations: list[
        dict[str, Any]
    ] = []

    context = _build_ai_context(
        health_result=health_result,
        analytics=analytics,
        period_start=period_start,
        period_end=period_end,
    )

    # --------------------------------------------------------------
    # AI Financial Analysis
    # --------------------------------------------------------------

    try:

        ai_analysis = (
            FinancialAIAnalysisService().generate(
                context
            )
        )

    except FinancialAIAnalysisError as exc:

        current_app.logger.warning(
            "AI financial analysis failed during "
            "report generation: %s",
            exc,
        )

    # --------------------------------------------------------------
    # AI Recommendations
    # --------------------------------------------------------------

    try:

        recommendation_result = (
            FinancialRecommendationService().generate(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
            )
        )

        recommendations = (
            recommendation_result.get(
                "recommendations",
                [],
            )
            or []
        )

    except FinancialRecommendationError as exc:

        current_app.logger.warning(
            "AI recommendations failed during "
            "report generation: %s",
            exc,
        )

    return (
        ai_analysis,
        recommendations,
    )


# ======================================================================
# EXISTING FINANCIAL STATEMENT DETECTION
# ======================================================================


def _find_existing_financial_statements(
    organization_id: int,
    period_start: date,
    period_end: date,
) -> list[FinancialStatement]:
    """
    Find existing uploaded/extracted financial statements that overlap
    the requested reporting period.

    FinancialStatement records represent structured financial statements
    already stored in ANGELIX. Their source_filename and processing
    metadata allow ANGELIX to distinguish them from transaction-only
    data.

    We intentionally do not inspect file extensions here.

    A PDF, CSV, XLS/XLSX or any future supported source is treated the
    same way once it has been converted into a FinancialStatement record.
    """

    return (
        FinancialStatement.query
        .filter(
            FinancialStatement.organization_id
            == organization_id,
            FinancialStatement.period_start
            <= period_end,
            FinancialStatement.period_end
            >= period_start,
        )
        .order_by(
            FinancialStatement.period_start.asc(),
            FinancialStatement.id.asc(),
        )
        .all()
    )


def _has_existing_financial_statements(
    organization_id: int,
    period_start: date,
    period_end: date,
) -> bool:
    """
    Return True when an existing financial statement overlaps the
    requested reporting period.

    This is deliberately based on structured statement records rather
    than file extensions.
    """

    statements = _find_existing_financial_statements(
        organization_id=organization_id,
        period_start=period_start,
        period_end=period_end,
    )

    return bool(
        statements
    )


def _build_statement_source_context(
    statements: list[FinancialStatement],
) -> list[dict[str, Any]]:
    """
    Build a small user-facing description of existing statement sources.
    """

    result = []

    for statement in statements:

        result.append(
            {
                "id": statement.id,
                "statement_type": statement.statement_type,
                "period_type": statement.period_type,
                "period_start": statement.period_start,
                "period_end": statement.period_end,
                "fiscal_year": statement.fiscal_year,
                "source_filename": statement.source_filename,
                "processing_status": statement.processing_status,
            }
        )

    return _serialize_for_json(
        result
    )


# ======================================================================
# REPORT OUTPUT HELPERS
# ======================================================================


def _get_report_directory() -> Path:
    """
    Resolve and create the configured report directory.
    """

    report_directory = Path(
        current_app.config[
            "GENERATED_REPORT_FOLDER"
        ]
    )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return report_directory


def _build_unique_report_path(
    report_directory: Path,
    organization_id: int,
    period_start: date,
    period_end: date,
    report_type: str,
) -> Path:
    """
    Build a unique PDF output path.
    """

    if report_type == REPORT_TYPE_FINANCIAL_STATEMENTS:

        prefix = "financial_statements_report"

    else:

        prefix = "financial_analysis_report"

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"{prefix}_"
        f"{organization_id}_"
        f"{period_start.isoformat()}_"
        f"{period_end.isoformat()}_"
        f"{timestamp}.pdf"
    )

    output_path = (
        report_directory / filename
    )

    counter = 1

    while output_path.exists():

        filename = (
            f"{prefix}_"
            f"{organization_id}_"
            f"{period_start.isoformat()}_"
            f"{period_end.isoformat()}_"
            f"{timestamp}_"
            f"{counter}.pdf"
        )

        output_path = (
            report_directory / filename
        )

        counter += 1

    return output_path


def _report_title(
    report_type: str,
) -> str:
    """
    Return the user-facing report title.
    """

    if (
        report_type
        == REPORT_TYPE_FINANCIAL_STATEMENTS
    ):
        return "ANGELIX Financial Statements Report"

    return "ANGELIX Financial Analysis Report"


# ======================================================================
# REPORT GENERATION
# ======================================================================


@report_bp.route(
    "/<organization_id>/reports/generate",
    methods=["GET", "POST"],
)
@login_required
def generate(
    organization_id,
):
    """
    Generate a Financial Statements Report or Financial Analysis Report.

    GET:
        Displays the report-generation and report-history interface.

    POST:
        Generates the requested report type.

    Report type:
        financial_statements
        financial_analysis
    """

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    # --------------------------------------------------------------
    # GET
    # --------------------------------------------------------------

    if request.method == "GET":

        reports = (
            Report.query
            .filter(
                Report.organization_id
                == organization.id
            )
            .order_by(
                Report.created_at.desc()
            )
            .all()
        )

        report_data = [
            _serialize_report(
                report
            )
            for report in reports
        ]

        return render_template(
            "reports/generate.html",
            organization_id=organization.id,
            organization=organization,
            reports=report_data,
            current_user=current_user,
        )

    # --------------------------------------------------------------
    # Parse report type.
    # --------------------------------------------------------------

    report_type = _normalize_report_type(
        request.form.get(
            "report_type"
        )
    )

    # --------------------------------------------------------------
    # Parse reporting period.
    #
    # Current generate.html uses:
    #     start
    #     end
    #
    # Backwards compatibility:
    #     period_start
    #     period_end
    # --------------------------------------------------------------

    period_start = _parse_date(
        (
            request.form.get(
                "start"
            )
            or request.form.get(
                "period_start"
            )
            or ""
        ).strip()
    )

    period_end = _parse_date(
        (
            request.form.get(
                "end"
            )
            or request.form.get(
                "period_end"
            )
            or ""
        ).strip()
    )

    if (
        period_start is None
        or period_end is None
    ):

        flash(
            "Please provide valid start and end dates.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    if period_start > period_end:

        flash(
            "The report start date cannot be after the end date.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    # ==============================================================
    # FINANCIAL STATEMENTS REPORT ELIGIBILITY
    # ==============================================================

    existing_statements = (
        _find_existing_financial_statements(
            organization_id=organization.id,
            period_start=period_start,
            period_end=period_end,
        )
    )

    if (
        report_type
        == REPORT_TYPE_FINANCIAL_STATEMENTS
        and existing_statements
    ):

        source_names = [
            statement.source_filename
            for statement in existing_statements
            if statement.source_filename
        ]

        source_text = ""

        if source_names:

            unique_names = list(
                dict.fromkeys(
                    source_names
                )
            )

            source_text = (
                " Existing source: "
                + ", ".join(
                    unique_names[:3]
                )
                + "."
            )

        flash(
            "A financial statement already exists for or overlaps "
            "the selected reporting period. ANGELIX will analyze the "
            "existing statement instead of generating another "
            "Financial Statements Report."
            + source_text,
            "warning",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    report = None
    output_path: Path | None = None

    try:

        # ==========================================================
        # 1. DETERMINISTIC ANALYTICS
        # ==========================================================

        analytics = AnalyticsService().calculate(
            organization.id,
            period_start,
            period_end,
        )

        # ==========================================================
        # 2. FINANCIAL HEALTH SCORE
        #
        # Required by the Financial Analysis Report.
        #
        # We also calculate it for Financial Statements because it
        # gives us the authoritative structured balance sheet when
        # transaction-derived statement data is available.
        # ==========================================================

        health_result = (
            FinancialHealthService().calculate(
                organization.id,
                period_start,
                period_end,
            )
        )

        # ==========================================================
        # 3. FINANCIAL STATEMENTS REPORT
        # ==========================================================

        if (
            report_type
            == REPORT_TYPE_FINANCIAL_STATEMENTS
        ):

            report_directory = (
                _get_report_directory()
            )

            output_path = (
                _build_unique_report_path(
                    report_directory=report_directory,
                    organization_id=organization.id,
                    period_start=period_start,
                    period_end=period_end,
                    report_type=report_type,
                )
            )

            generate_financial_statements_pdf(
                path=output_path,
                organization=organization,
                period_start=period_start,
                period_end=period_end,
                analytics=analytics,
                statements={},
                health_score=health_result,
            )

            report = Report(
                organization_id=organization.id,
                generated_by=current_user.id,
                report_type="financial_statements",
                title=_report_title(
                    report_type
                ),
                file_path=str(
                    output_path
                ),
                status="completed",
            )

            _set_optional_report_field(
                report,
                "period_start",
                period_start,
            )

            _set_optional_report_field(
                report,
                "period_end",
                period_end,
            )

            _set_optional_report_field(
                report,
                "format",
                "pdf",
            )

            _set_optional_report_field(
                report,
                "file_format",
                "pdf",
            )

            _set_optional_report_field(
                report,
                "summary",
                "Financial statements generated "
                "from transaction and structured "
                "financial data available in ANGELIX.",
            )

            statement_metadata = {
                "report_type": REPORT_TYPE_FINANCIAL_STATEMENTS,
                "source_mode": "transaction_or_import_data",
                "existing_statements_detected": False,
                "reporting_period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
            }

            _set_optional_report_field(
                report,
                "ai_metadata",
                json.dumps(
                    _serialize_for_json(
                        statement_metadata
                    ),
                    ensure_ascii=False,
                ),
            )

            metrics = {
                "analytics": analytics,
                "financial_health": health_result,
                "report_type": REPORT_TYPE_FINANCIAL_STATEMENTS,
            }

            _set_optional_report_field(
                report,
                "metrics",
                json.dumps(
                    _serialize_for_json(
                        metrics
                    ),
                    ensure_ascii=False,
                ),
            )

            db.session.add(
                report
            )

            db.session.commit()

            flash(
                "Financial Statements Report generated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "reports.generate",
                    organization_id=organization.id,
                )
            )

        # ==========================================================
        # 4. FINANCIAL ANALYSIS REPORT
        # ==========================================================

        (
            ai_analysis,
            recommendations,
        ) = _safe_generate_ai_content(
            organization_id=organization.id,
            health_result=health_result,
            analytics=analytics,
            period_start=period_start,
            period_end=period_end,
        )

        report_directory = (
            _get_report_directory()
        )

        output_path = (
            _build_unique_report_path(
                report_directory=report_directory,
                organization_id=organization.id,
                period_start=period_start,
                period_end=period_end,
                report_type=report_type,
            )
        )

        generate_financial_analysis_pdf(
            path=output_path,
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            analytics=analytics,
            health_score=health_result,
            ai_observations=ai_analysis,
            ai_recommendations=recommendations,
        )

        report = Report(
            organization_id=organization.id,
            generated_by=current_user.id,
            report_type="financial_analysis",
            title=_report_title(
                report_type
            ),
            file_path=str(
                output_path
            ),
            status="completed",
        )

        _set_optional_report_field(
            report,
            "period_start",
            period_start,
        )

        _set_optional_report_field(
            report,
            "period_end",
            period_end,
        )

        _set_optional_report_field(
            report,
            "format",
            "pdf",
        )

        _set_optional_report_field(
            report,
            "file_format",
            "pdf",
        )

        if ai_analysis:

            summary = ai_analysis.get(
                "summary"
            )

        else:

            summary = (
                "Financial analysis report generated "
                "from deterministic ANGELIX analytics."
            )

        _set_optional_report_field(
            report,
            "summary",
            summary,
        )

        if ai_analysis is not None:

            analysis_payload = json.dumps(
                _serialize_for_json(
                    ai_analysis
                ),
                ensure_ascii=False,
            )

            _set_optional_report_field(
                report,
                "analysis_content",
                analysis_payload,
            )

            _set_optional_report_field(
                report,
                "analysis",
                analysis_payload,
            )

        recommendations_payload = json.dumps(
            _serialize_for_json(
                recommendations
            ),
            ensure_ascii=False,
        )

        _set_optional_report_field(
            report,
            "recommendations",
            recommendations_payload,
        )

        ai_metadata = {
            "report_type": REPORT_TYPE_FINANCIAL_ANALYSIS,
            "ai_analysis_generated": (
                ai_analysis is not None
            ),
            "recommendations_generated": bool(
                recommendations
            ),
            "health_score": health_result.get(
                "score"
            ),
            "health_level": health_result.get(
                "health_level"
            ),
            "reporting_period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
        }

        _set_optional_report_field(
            report,
            "ai_metadata",
            json.dumps(
                _serialize_for_json(
                    ai_metadata
                ),
                ensure_ascii=False,
            ),
        )

        metrics = {
            "analytics": analytics,
            "financial_health": health_result,
            "report_type": REPORT_TYPE_FINANCIAL_ANALYSIS,
            "existing_financial_statements": (
                _build_statement_source_context(
                    existing_statements
                )
            ),
        }

        _set_optional_report_field(
            report,
            "metrics",
            json.dumps(
                _serialize_for_json(
                    metrics
                ),
                ensure_ascii=False,
            ),
        )

        db.session.add(
            report
        )

        db.session.commit()

        flash(
            "Financial Analysis Report generated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    except Exception as exc:

        db.session.rollback()

        # ----------------------------------------------------------
        # Remove partially generated PDF if database persistence
        # failed.
        # ----------------------------------------------------------

        try:

            if (
                report is None
                and output_path is not None
                and output_path.exists()
            ):

                output_path.unlink()

        except (
            OSError,
            PermissionError,
        ):

            current_app.logger.warning(
                "Unable to remove partially generated "
                "report file: %s",
                output_path,
            )

        current_app.logger.exception(
            "Financial report generation failed."
        )

        flash(
            f"Unable to generate the report: {exc}",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )


# ======================================================================
# REPORT HISTORY
# ======================================================================


@report_bp.route(
    "/<organization_id>/reports",
    methods=["GET"],
)
@login_required
def list_reports(
    organization_id,
):
    """
    Display report history.

    The project currently uses generate.html as the unified
    report-generation and report-history interface.
    """

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    reports = (
        Report.query
        .filter(
            Report.organization_id
            == organization.id
        )
        .order_by(
            Report.created_at.desc()
        )
        .all()
    )

    report_data = [
        _serialize_report(
            report
        )
        for report in reports
    ]

    return render_template(
        "reports/generate.html",
        organization_id=organization.id,
        organization=organization,
        reports=report_data,
        current_user=current_user,
    )


# ======================================================================
# REPORT DETAILS
# ======================================================================


@report_bp.route(
    "/<organization_id>/reports/<int:report_id>",
    methods=["GET"],
)
@login_required
def report_details(
    organization_id,
    report_id,
):
    """
    Temporary report-view route.

    A dedicated report-details page can be added later. For now,
    opening a report returns the user to Report History.
    """

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    report = (
        Report.query
        .filter(
            Report.id == report_id,
            Report.organization_id
            == organization.id,
        )
        .first_or_404()
    )

    flash(
        f"Report #{report.id}: {report.title}",
        "info",
    )

    return redirect(
        url_for(
            "reports.generate",
            organization_id=organization.id,
        )
    )


# ======================================================================
# REPORT DOWNLOAD
# ======================================================================


@report_bp.route(
    "/<organization_id>/reports/<int:report_id>/download",
    methods=["GET"],
)
@login_required
def download_report(
    organization_id,
    report_id,
):
    """
    Download a generated report belonging to the organization.
    """

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    report = (
        Report.query
        .filter(
            Report.id == report_id,
            Report.organization_id
            == organization.id,
        )
        .first_or_404()
    )

    status = str(
        getattr(
            report,
            "status",
            "",
        )
    ).lower()

    if status not in {
        "completed",
        "ready",
    }:

        flash(
            "This report is not ready for download.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    if not report.file_path:

        flash(
            "The requested report file is unavailable.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    file_path = Path(
        report.file_path
    )

    report_directory = Path(
        current_app.config[
            "GENERATED_REPORT_FOLDER"
        ]
    ).resolve()

    try:

        resolved_file = (
            file_path.resolve()
        )

        resolved_file.relative_to(
            report_directory
        )

    except (
        ValueError,
        OSError,
    ):

        current_app.logger.warning(
            "Blocked invalid report file path for report %s.",
            report.id,
        )

        flash(
            "The requested report file is invalid.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    if not resolved_file.exists():

        flash(
            "The requested report file could not be found.",
            "error",
        )

        return redirect(
            url_for(
                "reports.generate",
                organization_id=organization.id,
            )
        )

    return send_file(
        resolved_file,
        as_attachment=True,
        download_name=resolved_file.name,
        mimetype="application/pdf",
    )


# ======================================================================
# REPORT DELETE
# ======================================================================


@report_bp.route(
    "/<organization_id>/reports/<int:report_id>/delete",
    methods=["POST"],
)
@login_required
def delete_report(
    organization_id,
    report_id,
):
    """
    Delete a generated report and its PDF file.
    """

    try:

        organization = require_member(
            organization_id
        )

    except PermissionError:

        return (
            "Forbidden",
            403,
        )

    report = (
        Report.query
        .filter(
            Report.id == report_id,
            Report.organization_id
            == organization.id,
        )
        .first_or_404()
    )

    try:

        if report.file_path:

            file_path = Path(
                report.file_path
            )

            report_directory = Path(
                current_app.config[
                    "GENERATED_REPORT_FOLDER"
                ]
            ).resolve()

            try:

                resolved_file = (
                    file_path.resolve()
                )

                resolved_file.relative_to(
                    report_directory
                )

                if resolved_file.exists():

                    resolved_file.unlink()

            except (
                ValueError,
                OSError,
            ):

                current_app.logger.warning(
                    "Could not safely remove report "
                    "file for report %s.",
                    report.id,
                )

        db.session.delete(
            report
        )

        db.session.commit()

        flash(
            "Report deleted successfully.",
            "success",
        )

    except Exception as exc:

        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete report %s.",
            report_id,
        )

        flash(
            f"Unable to delete the report: {exc}",
            "error",
        )

    return redirect(
        url_for(
            "reports.generate",
            organization_id=organization.id,
        )
    )