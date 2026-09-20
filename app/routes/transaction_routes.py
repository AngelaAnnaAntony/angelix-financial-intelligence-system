from datetime import date
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models.transaction import Transaction
from ..services.access_service import require_member
from ..services.ml.prediction_service import (
    FinancialPredictionService,
)


transaction_bp = Blueprint(
    "transactions",
    __name__,
    url_prefix="/organizations",
)


# ======================================================================
# HELPERS
# ======================================================================

def _normalise_prediction_value(value):
    """
    Convert prediction values into clean display-friendly strings.
    """
    if value is None:
        return None

    return str(value).strip().lower()


def _extract_ml_prediction(prediction):
    """
    Extract the accounting ML prediction into a stable dictionary.

    Supports:
    - normal dictionaries
    - PredictionResult dataclass/object responses
    """

    if prediction is None:
        return None

    # --------------------------------------------------------------
    # PredictionResult / object response
    # --------------------------------------------------------------

    if hasattr(prediction, "to_dict"):
        try:
            prediction = prediction.to_dict()
        except Exception:
            pass

    elif not isinstance(prediction, dict):
        prediction = {
            "success": getattr(
                prediction,
                "success",
                None,
            ),
            "status": getattr(
                prediction,
                "status",
                None,
            ),
            "message": getattr(
                prediction,
                "message",
                None,
            ),
            "predictions": getattr(
                prediction,
                "predictions",
                [],
            ),
            "probabilities": getattr(
                prediction,
                "probabilities",
                [],
            ),
            "confidence_scores": getattr(
                prediction,
                "confidence_scores",
                [],
            ),
            "model_name": getattr(
                prediction,
                "model_name",
                None,
            ),
            "model_version": getattr(
                prediction,
                "model_version",
                None,
            ),
            "metadata": getattr(
                prediction,
                "metadata",
                {},
            ),
        }

    # --------------------------------------------------------------
    # Check prediction status
    # --------------------------------------------------------------

    if prediction.get("success") is False:
        raise RuntimeError(
            prediction.get(
                "message",
                "Accounting ML prediction failed.",
            )
        )

    # --------------------------------------------------------------
    # Extract prediction arrays
    # --------------------------------------------------------------

    predictions = (
        prediction.get("predictions")
        or []
    )

    probabilities = (
        prediction.get("probabilities")
        or []
    )

    confidence_scores = (
        prediction.get("confidence_scores")
        or []
    )

    metadata = (
        prediction.get("metadata")
        or {}
    )

    # --------------------------------------------------------------
    # Account-type prediction
    # --------------------------------------------------------------

    account_type = (
        prediction.get("account_type")
        or prediction.get("predicted_account_type")
    )

    if account_type is None and predictions:
        account_type = predictions[0]

    # --------------------------------------------------------------
    # Account confidence
    # --------------------------------------------------------------

    account_confidence = (
        prediction.get(
            "account_confidence"
        )
        or prediction.get(
            "confidence"
        )
    )

    if account_confidence is None and confidence_scores:
        account_confidence = confidence_scores[0]

    # --------------------------------------------------------------
    # Debit/Credit prediction
    # --------------------------------------------------------------

    debit_credit = (
        prediction.get("debit_credit")
        or prediction.get(
            "predicted_debit_credit"
        )
    )

    # --------------------------------------------------------------
    # Debit/Credit confidence
    # --------------------------------------------------------------

    debit_credit_confidence = (
        prediction.get(
            "debit_credit_confidence"
        )
        or prediction.get(
            "dc_confidence"
        )
    )

    # --------------------------------------------------------------
    # Model information
    # --------------------------------------------------------------

    account_model_version = (
        prediction.get(
            "account_model_version"
        )
        or metadata.get(
            "account_model_version"
        )
        or prediction.get(
            "model_version"
        )
    )

    debit_credit_model_version = (
        prediction.get(
            "debit_credit_model_version"
        )
        or metadata.get(
            "debit_credit_model_version"
        )
        or prediction.get(
            "model_version"
        )
    )

    return {
        "account_type": _normalise_prediction_value(
            account_type
        ),
        "account_confidence": (
            float(account_confidence)
            if account_confidence is not None
            else None
        ),
        "debit_credit": _normalise_prediction_value(
            debit_credit
        ),
        "debit_credit_confidence": (
            float(debit_credit_confidence)
            if debit_credit_confidence is not None
            else None
        ),
        "account_model_version": account_model_version,
        "debit_credit_model_version": debit_credit_model_version,
    }


def _format_confidence(value):
    """
    Convert a probability such as 0.9906 into 99.06%.
    """
    if value is None:
        return "N/A"

    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _display_account_type(value):
    """
    Convert model output such as 'expense' into 'Expense'.
    """
    if not value:
        return "Unknown"

    return str(value).replace("_", " ").title()


def _display_debit_credit(value):
    """
    Convert debit/credit prediction into a display-friendly value.
    """
    if not value:
        return "Unknown"

    return str(value).replace("_", " ").title()


# ======================================================================
# TRANSACTION LIST
# ======================================================================

@transaction_bp.get(
    "/<organization_id>/transactions"
)
@login_required
def list_transactions(organization_id):
    """
    Display the financial transactions belonging to an organization.

    Only the authenticated user's organization can be accessed.
    Transactions are ordered newest-first.
    """

    try:
        organization = require_member(organization_id)

    except PermissionError:
        return ("Forbidden", 403)

    try:
        page = request.args.get(
            "page",
            default=1,
            type=int,
        )

        per_page = request.args.get(
            "per_page",
            default=20,
            type=int,
        )

        if page < 1:
            page = 1

        if per_page not in (10, 20, 50, 100):
            per_page = 20

        query = (
            Transaction.query
            .filter(
                Transaction.organization_id
                == int(organization_id)
            )
            .order_by(
                Transaction.transaction_date.desc(),
                Transaction.id.desc(),
            )
        )

        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False,
        )

        return render_template(
            "transactions/list.html",
            organization=organization,
            organization_id=int(organization_id),
            transactions=pagination.items,
            pagination=pagination,
            current_user=current_user,
        )

    except Exception:
        current_app.logger.exception(
            "Failed to load transactions for organization %s.",
            organization_id,
        )

        return (
            "Unable to load transactions.",
            500,
        )


# ======================================================================
# CREATE TRANSACTION
# ======================================================================

@transaction_bp.route(
    "/<organization_id>/transactions/new",
    methods=["GET", "POST"],
)
@login_required
def new(organization_id):
    """
    Create a new financial transaction for an organization.

    The supervised accounting ML models are used as an intelligent
    classification and validation layer.

    The user's selected transaction type remains authoritative.
    The ML prediction is used to provide classification feedback,
    confidence information and validation warnings.
    """

    try:
        require_member(organization_id)

    except PermissionError:
        return ("Forbidden", 403)

    # --------------------------------------------------------------
    # POST
    # --------------------------------------------------------------

    if request.method == "POST":

        ml_prediction = None

        try:
            transaction_date = date.fromisoformat(
                request.form["transaction_date"]
            )

            description = (
                request.form["description"].strip()
            )

            if not description:
                raise ValueError(
                    "Transaction description is required."
                )

            amount = Decimal(
                request.form["amount"].strip()
            )

            if amount < 0:
                raise ValueError(
                    "Transaction amount cannot be negative."
                )

            transaction_type = (
                request.form.get(
                    "transaction_type",
                    "expense",
                )
                .strip()
                .lower()
            )

            allowed_types = {
                "income",
                "expense",
                "asset",
                "liability",
                "equity",
            }

            if transaction_type not in allowed_types:
                raise ValueError(
                    "Invalid transaction type."
                )

            category = (
                request.form.get("category")
                or None
            )

            subcategory = (
                request.form.get("subcategory")
                or None
            )

            reference_number = (
                request.form.get("reference_number")
                or None
            )

            notes = (
                request.form.get("notes")
                or None
            )

            # ------------------------------------------------------
            # Create an in-memory Transaction object first.
            #
            # This allows the ML prediction service to analyse the
            # transaction before the database commit.
            # ------------------------------------------------------

            transaction = Transaction(
                organization_id=int(
                    organization_id
                ),
                transaction_date=transaction_date,
                description=description,
                reference_number=reference_number,
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                subcategory=subcategory,
                source="manual",
                is_recurring=False,
                confidence_score=None,
                notes=notes,
            )

            # ------------------------------------------------------
            # SUPERVISED ACCOUNTING ML
            # ------------------------------------------------------

            try:

                prediction_service = (
                    FinancialPredictionService()
                )

                raw_prediction = (
                    prediction_service
                    .predict_accounting_transaction(
                        organization_id=int(organization_id),
                        description=description,
                        amount=amount,
                    )
                )

                ml_prediction = (
                    _extract_ml_prediction(
                        raw_prediction
                    )
                )

                # --------------------------------------------------
                # Store the account-type ML confidence in the
                # existing confidence_score field.
                #
                # No database migration is required.
                # --------------------------------------------------

                if (
                    ml_prediction
                    and
                    ml_prediction.get(
                        "account_confidence"
                    )
                    is not None
                ):
                    transaction.confidence_score = (
                        ml_prediction[
                            "account_confidence"
                        ]
                    )

                current_app.logger.info(
                    "Accounting ML prediction generated "
                    "for transaction '%s': %s",
                    description,
                    ml_prediction,
                )

            except Exception as exc:

                # --------------------------------------------------
                # ML is an enhancement, not a reason to prevent
                # legitimate manual transaction creation.
                #
                # If the model is unavailable, the transaction can
                # still be saved normally.
                # --------------------------------------------------

                current_app.logger.exception(
                    "Accounting ML prediction failed "
                    "for transaction '%s': %s",
                    description,
                    exc,
                )

                ml_prediction = None

            # ------------------------------------------------------
            # SAVE TRANSACTION
            # ------------------------------------------------------

            db.session.add(transaction)
            db.session.commit()

        except (
            ValueError,
            InvalidOperation,
            KeyError,
        ) as exc:

            db.session.rollback()

            return (
                f"Invalid transaction data: {exc}",
                400,
            )

        except Exception:

            db.session.rollback()

            current_app.logger.exception(
                "Failed to create transaction."
            )

            return (
                "Unable to create the transaction.",
                500,
            )

        # ----------------------------------------------------------
        # ML RESULT FEEDBACK
        # ----------------------------------------------------------

        if ml_prediction:

            predicted_account_type = (
                ml_prediction.get(
                    "account_type"
                )
            )

            predicted_debit_credit = (
                ml_prediction.get(
                    "debit_credit"
                )
            )

            account_confidence = (
                ml_prediction.get(
                    "account_confidence"
                )
            )

            debit_credit_confidence = (
                ml_prediction.get(
                    "debit_credit_confidence"
                )
            )

            # ------------------------------------------------------
            # Compare user's selected accounting type with ML result.
            # ------------------------------------------------------

            if (
                predicted_account_type
                and predicted_account_type
                != transaction_type
            ):

                flash(
                    (
                        "Transaction saved. "
                        "ML classification suggests "
                        f"{_display_account_type(predicted_account_type)} "
                        f"({_format_confidence(account_confidence)}) "
                        "while you selected "
                        f"{_display_account_type(transaction_type)}. "
                        "Please review the classification."
                    ),
                    "warning",
                )

            else:

                flash(
                    (
                        "Transaction saved successfully. "
                        "ANGELIX ML classified it as "
                        f"{_display_account_type(predicted_account_type)} "
                        f"with {_format_confidence(account_confidence)} "
                        "confidence."
                    ),
                    "success",
                )

            if predicted_debit_credit:

                flash(
                    (
                        "ML Debit/Credit classification: "
                        f"{_display_debit_credit(predicted_debit_credit)} "
                        f"({_format_confidence(debit_credit_confidence)} "
                        "confidence)."
                    ),
                    "info",
                )

        else:

            flash(
                (
                    "Transaction saved successfully. "
                    "ML classification was unavailable for this "
                    "transaction."
                ),
                "info",
            )

        return redirect(
            url_for(
                "transactions.list_transactions",
                organization_id=organization_id,
            )
        )

    # --------------------------------------------------------------
    # GET
    # --------------------------------------------------------------

    return render_template(
        "transactions/create.html",
        organization_id=int(organization_id),
        current_user=current_user,
    )