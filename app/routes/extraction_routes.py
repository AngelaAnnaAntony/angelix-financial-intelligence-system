from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..models.upload import Upload
from ..services.access_service import require_member
from ..services.document_processing_service import (
    DocumentProcessingService,
)
from ..services.extraction_candidate_service import (
    ExtractionCandidateService,
)


extraction_bp = Blueprint(
    "extractions",
    __name__,
    url_prefix="/organizations",
)


# ============================================================================
# ORGANIZATION ACCESS
# ============================================================================

def _require_organization_access(organization_id):
    """
    Ensure the authenticated user belongs to the requested organization.
    """

    try:
        return require_member(organization_id)

    except PermissionError:
        return None


# ============================================================================
# REVIEW LIST
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/extractions",
    methods=["GET"],
)
@login_required
def review_list(organization_id):
    """
    Display all extracted financial candidates awaiting review.
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    candidates = (
        ExtractionCandidateService
        .get_pending_candidates(
            organization_id
        )
    )

    return render_template(
        "extractions/list.html",
        organization=organization,
        organization_id=organization_id,
        candidates=candidates,
    )


# ============================================================================
# REVIEW SINGLE CANDIDATE
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/extractions/<candidate_id>",
    methods=["GET"],
)
@login_required
def review_candidate(
    organization_id,
    candidate_id,
):
    """
    Display a single extraction candidate for review.

    The review page determines whether the candidate belongs to a
    financial statement workflow or a normal transaction workflow.

    Priority:

        1. Persisted DocumentExtraction.statement_type
        2. Linked FinancialStatement.statement_type
        3. Uploaded filename inference
        4. Normal transaction workflow
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    candidate = (
        ExtractionCandidateService
        .get_candidate(
            candidate_id=candidate_id,
            organization_id=organization_id,
        )
    )

    if candidate is None:

        flash(
            "Extraction candidate not found.",
            "error",
        )

        return redirect(
            url_for(
                "extractions.review_list",
                organization_id=organization_id,
            )
        )

    # ========================================================================
    # DETERMINE STATEMENT TYPE
    # ========================================================================

    statement_type = None

    extraction = candidate.extraction

    # ------------------------------------------------------------------------
    # 1. Use persisted extraction statement type
    # ------------------------------------------------------------------------

    if extraction is not None:

        statement_type = (
            getattr(
                extraction,
                "statement_type",
                None,
            )
            or None
        )

    # ------------------------------------------------------------------------
    # 2. Use linked FinancialStatement if available
    # ------------------------------------------------------------------------

    if not statement_type and extraction is not None:

        financial_statement = getattr(
            extraction,
            "financial_statement",
            None,
        )

        if financial_statement is not None:

            statement_type = (
                getattr(
                    financial_statement,
                    "statement_type",
                    None,
                )
                or None
            )

    # ------------------------------------------------------------------------
    # 3. Infer from uploaded filename
    #
    # This is a fallback for older extraction records where
    # statement_type was not populated when the document was processed.
    # ------------------------------------------------------------------------

    upload_filename = ""

    if extraction is not None:

        upload = getattr(
            extraction,
            "upload",
            None,
        )

        if upload is not None:

            upload_filename = (
                getattr(
                    upload,
                    "original_filename",
                    None,
                )
                or ""
            )

    filename_normalized = (
        upload_filename
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )

    if not statement_type and filename_normalized:

        if (
            "profit and loss" in filename_normalized
            or "profit loss" in filename_normalized
            or "p&l" in filename_normalized
            or "p & l" in filename_normalized
            or "income statement" in filename_normalized
        ):

            statement_type = "profit_and_loss"

        elif "balance sheet" in filename_normalized:

            statement_type = "balance_sheet"

        elif (
            "cash flow" in filename_normalized
            or "cashflow" in filename_normalized
        ):

            statement_type = "cash_flow_statement"

        elif "trial balance" in filename_normalized:

            statement_type = "trial_balance"

    # ------------------------------------------------------------------------
    # Normalize supported statement types
    # ------------------------------------------------------------------------

    valid_statement_types = {
        "balance_sheet",
        "income_statement",
        "profit_and_loss",
        "cash_flow_statement",
        "trial_balance",
    }

    if statement_type not in valid_statement_types:

        statement_type = None

    # ========================================================================
    # DETERMINE REVIEW MODE
    # ========================================================================

    is_statement = (
        statement_type in valid_statement_types
    )

    is_pnl = statement_type in {
        "profit_and_loss",
        "income_statement",
    }

    is_balance_sheet = (
        statement_type == "balance_sheet"
    )

    is_cash_flow = (
        statement_type == "cash_flow_statement"
    )

    is_trial_balance = (
        statement_type == "trial_balance"
    )

    # ========================================================================
    # RENDER REVIEW PAGE
    # ========================================================================

    return render_template(
        "extractions/review.html",

        organization=organization,

        organization_id=organization_id,

        candidate=candidate,

        # --------------------------------------------------------------------
        # Explicit statement context
        # --------------------------------------------------------------------

        detected_statement_type=statement_type,

        is_statement=is_statement,

        is_pnl=is_pnl,

        is_balance_sheet=is_balance_sheet,

        is_cash_flow=is_cash_flow,

        is_trial_balance=is_trial_balance,

        # --------------------------------------------------------------------
        # Useful document information
        # --------------------------------------------------------------------

        upload_filename=upload_filename,
    )

# ============================================================================
# UPDATE CANDIDATE
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/extractions/<candidate_id>/update",
    methods=["POST"],
)
@login_required
def update_candidate(
    organization_id,
    candidate_id,
):
    """
    Save reviewer corrections without approving the candidate.

    Supports both:

        Normal transactions
            transaction_type
            category
            subcategory

        Financial statements
            statement_type
            period_type
            period_start
            period_end
            fiscal_year
            line_item_name
            section
            account_type
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    candidate = (
        ExtractionCandidateService
        .get_candidate(
            candidate_id=candidate_id,
            organization_id=organization_id,
        )
    )

    if candidate is None:

        flash(
            "Extraction candidate not found.",
            "error",
        )

        return redirect(
            url_for(
                "extractions.review_list",
                organization_id=organization_id,
            )
        )

    # ------------------------------------------------------------------------
    # Determine submitted amount.
    #
    # Statement review uses statement_amount.
    # Normal transaction review uses amount.
    # ------------------------------------------------------------------------

    submitted_amount = (
        request.form.get("statement_amount")
        or request.form.get("amount")
    )

    # ------------------------------------------------------------------------
    # Collect all editable fields.
    # ------------------------------------------------------------------------

    values = {

        # Common / transaction fields
        "transaction_date": request.form.get(
            "transaction_date"
        ),

        "description": request.form.get(
            "description"
        ),

        "reference_number": request.form.get(
            "reference_number"
        ),

        "amount": submitted_amount,

        "debit_credit": request.form.get(
            "debit_credit"
        ),

        "transaction_type": request.form.get(
            "transaction_type"
        ),

        "category": request.form.get(
            "category"
        ),

        "subcategory": request.form.get(
            "subcategory"
        ),

        "correction_notes": request.form.get(
            "correction_notes"
        ),

        # --------------------------------------------------------------------
        # Statement context
        # --------------------------------------------------------------------

        "statement_type": request.form.get(
            "statement_type"
        ),

        "period_type": request.form.get(
            "period_type"
        ),

        "period_start": request.form.get(
            "period_start"
        ),

        "period_end": request.form.get(
            "period_end"
        ),

        "fiscal_year": request.form.get(
            "fiscal_year"
        ),

        # --------------------------------------------------------------------
        # Statement line-item corrections
        # --------------------------------------------------------------------

        "line_item_name": request.form.get(
            "line_item_name"
        ),

        "section": request.form.get(
            "section"
        ),

        "account_type": request.form.get(
            "account_type"
        ),
    }

    try:

        ExtractionCandidateService.update_candidate(
            candidate=candidate,
            values=values,
        )

        flash(
            "Candidate corrections saved successfully.",
            "success",
        )

    except ValueError as exc:

        flash(
            str(exc),
            "error",
        )

    except Exception:

        flash(
            "The candidate could not be updated. "
            "Please try again.",
            "error",
        )

    return redirect(
        url_for(
            "extractions.review_candidate",
            organization_id=organization_id,
            candidate_id=candidate_id,
        )
    )


# ============================================================================
# APPROVE CANDIDATE
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/extractions/<candidate_id>/approve",
    methods=["POST"],
)
@login_required
def approve_candidate(
    organization_id,
    candidate_id,
):
    """
    Approve an extracted financial candidate.

    The associated extraction's statement_type is authoritative.

    Financial statement candidates:

        Profit & Loss
            income / expense / calculated

        Income Statement
            income / expense / calculated

        Balance Sheet
            asset / liability / equity

        Cash Flow Statement
            operating / investing / financing / calculated

        Trial Balance
            income / expense / asset / liability / equity

    These become FinancialStatementLineItem records.

    Normal transaction candidates become Transaction records.
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    candidate = (
        ExtractionCandidateService
        .get_candidate(
            candidate_id=candidate_id,
            organization_id=organization_id,
        )
    )

    if candidate is None:

        flash(
            "Extraction candidate not found.",
            "error",
        )

        return redirect(
            url_for(
                "extractions.review_list",
                organization_id=organization_id,
            )
        )

    # =========================================================================
    # IMPORTANT ARCHITECTURAL RULE
    #
    # The extraction's statement_type determines whether this is a financial
    # statement workflow.
    #
    # We MUST NOT use transaction_type for this decision.
    #
    # Why?
    #
    # A P&L row can legitimately have:
    #
    #     income
    #     expense
    #     calculated
    #
    # Those are NOT necessarily Transaction records.
    #
    # =========================================================================

    extraction = candidate.extraction

    statement_type = (
        extraction.statement_type
        if extraction is not None
        else None
    )

    statement_types = {
        "balance_sheet",
        "income_statement",
        "profit_and_loss",
        "cash_flow_statement",
        "trial_balance",
    }

    is_statement_candidate = (
        statement_type in statement_types
    )

    correction_notes = request.form.get(
        "correction_notes"
    )

    try:

        # =====================================================================
        # FINANCIAL STATEMENT WORKFLOW
        # =====================================================================

        if is_statement_candidate:

            # -----------------------------------------------------------------
            # Statement metadata
            # -----------------------------------------------------------------

            statement_data = {

                "statement_type": (
                    request.form.get(
                        "statement_type"
                    )
                    or statement_type
                ),

                "period_type": request.form.get(
                    "period_type"
                ),

                "period_start": request.form.get(
                    "period_start"
                ),

                "period_end": request.form.get(
                    "period_end"
                ),

                "fiscal_year": request.form.get(
                    "fiscal_year"
                ),
            }

            # -----------------------------------------------------------------
            # Statement amount
            # -----------------------------------------------------------------

            statement_amount = (
                request.form.get(
                    "statement_amount"
                )
                or request.form.get(
                    "amount"
                )
            )

            # -----------------------------------------------------------------
            # Account type
            #
            # The statement form sends account_type.
            #
            # If it is not present, use the persisted candidate value.
            # -----------------------------------------------------------------

            account_type = (
                request.form.get(
                    "account_type"
                )
                or candidate.transaction_type
            )

            # -----------------------------------------------------------------
            # Line item data
            # -----------------------------------------------------------------

            line_item_data = {

                "line_item_name": (
                    request.form.get(
                        "line_item_name"
                    )
                    or candidate.description
                ),

                "section": (
                    request.form.get(
                        "section"
                    )
                    or candidate.subcategory
                ),

                "account_type": account_type,

                "amount": statement_amount,
            }

            # -----------------------------------------------------------------
            # Approve as FinancialStatementLineItem
            # -----------------------------------------------------------------

            ExtractionCandidateService.approve_statement_line_item(

                candidate=candidate,

                reviewer=current_user,

                statement_data=statement_data,

                line_item_data=line_item_data,

                correction_notes=correction_notes,
            )

            flash(
                "Financial statement line item approved successfully.",
                "success",
            )

        # =====================================================================
        # NORMAL TRANSACTION WORKFLOW
        # =====================================================================

        else:

            transaction_type = (
                request.form.get(
                    "transaction_type"
                )
                or candidate.transaction_type
                or ""
            ).strip().lower()

            transaction_data = {

                "transaction_date": request.form.get(
                    "transaction_date"
                ),

                "description": request.form.get(
                    "description"
                ),

                "reference_number": request.form.get(
                    "reference_number"
                ),

                "amount": request.form.get(
                    "amount"
                ),

                "transaction_type": transaction_type,

                "category": request.form.get(
                    "category"
                ),

                "subcategory": request.form.get(
                    "subcategory"
                ),

                "is_recurring": request.form.get(
                    "is_recurring"
                ),

                "confidence_score": (
                    candidate.confidence_score
                ),

                "notes": request.form.get(
                    "correction_notes"
                ),
            }

            ExtractionCandidateService.approve_candidate(

                candidate=candidate,

                reviewer=current_user,

                transaction_data=transaction_data,

                correction_notes=correction_notes,
            )

            flash(
                "Transaction approved successfully.",
                "success",
            )

    except ValueError as exc:

        flash(
            str(exc),
            "error",
        )

    except PermissionError as exc:

        flash(
            str(exc),
            "error",
        )

    except Exception:

        flash(
            "The candidate could not be approved. "
            "Please review the extracted values and try again.",
            "error",
        )

    return redirect(
        url_for(
            "extractions.review_candidate",
            organization_id=organization_id,
            candidate_id=candidate_id,
        )
    )


# ============================================================================
# REJECT CANDIDATE
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/extractions/<candidate_id>/reject",
    methods=["POST"],
)
@login_required
def reject_candidate(
    organization_id,
    candidate_id,
):
    """
    Reject an extracted candidate.
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    candidate = (
        ExtractionCandidateService
        .get_candidate(
            candidate_id=candidate_id,
            organization_id=organization_id,
        )
    )

    if candidate is None:

        flash(
            "Extraction candidate not found.",
            "error",
        )

        return redirect(
            url_for(
                "extractions.review_list",
                organization_id=organization_id,
            )
        )

    correction_notes = request.form.get(
        "correction_notes"
    )

    try:

        ExtractionCandidateService.reject_candidate(
            candidate=candidate,
            reviewer=current_user,
            correction_notes=correction_notes,
        )

        flash(
            "Extraction candidate rejected.",
            "success",
        )

    except ValueError as exc:

        flash(
            str(exc),
            "error",
        )

    except PermissionError as exc:

        flash(
            str(exc),
            "error",
        )

    except Exception:

        flash(
            "The candidate could not be rejected. "
            "Please try again.",
            "error",
        )

    return redirect(
        url_for(
            "extractions.review_list",
            organization_id=organization_id,
        )
    )


# ============================================================================
# REPROCESS UPLOAD
# ============================================================================

@extraction_bp.route(
    "/<organization_id>/uploads/<upload_id>/reprocess",
    methods=["POST"],
)
@login_required
def reprocess_upload(
    organization_id,
    upload_id,
):
    """
    Reprocess an uploaded document.

    Deleted uploads cannot be reprocessed.
    """

    organization = _require_organization_access(
        organization_id
    )

    if organization is None:
        return ("Forbidden", 403)

    upload = (
        Upload.query
        .filter_by(
            id=int(upload_id),
            organization_id=int(organization_id),
            is_deleted=False,
        )
        .first()
    )

    if upload is None:

        flash(
            "Upload not found.",
            "error",
        )

        return redirect(
            url_for(
                "extractions.review_list",
                organization_id=organization_id,
            )
        )

    try:

        DocumentProcessingService.process_upload(
            upload
        )

        flash(
            "Document reprocessed successfully.",
            "success",
        )

    except Exception:

        flash(
            "The document could not be reprocessed. "
            "Please try again.",
            "error",
        )

    return redirect(
        url_for(
            "extractions.review_list",
            organization_id=organization_id,
        )
    )