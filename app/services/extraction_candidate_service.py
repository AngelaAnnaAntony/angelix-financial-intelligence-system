from datetime import datetime
from decimal import Decimal, InvalidOperation

from ..extensions import db
from ..models.extraction_candidate import ExtractionCandidate
from ..models.financial_statement import FinancialStatement
from ..models.financial_statement_line_item import (
    FinancialStatementLineItem,
)
from ..models.transaction import Transaction
from ..models.upload import Upload


class ExtractionCandidateService:
    """
    Business logic for reviewing extracted financial candidates.

    Extraction candidates are untrusted until explicitly reviewed by a user.

    Approved transaction candidates are converted into trusted
    Transaction records.

    Approved financial-statement candidates are converted into
    FinancialStatementLineItem records through the financial statement
    approval workflow.

    Profit & Loss / Income Statement:
        income / expense / calculated

    Balance Sheet:
        asset / liability / equity

    Cash Flow Statement:
        operating / investing / financing / calculated
    """

    # ========================================================================
    # VALID VALUES
    # ========================================================================

    VALID_REVIEW_STATUSES = {
        "pending_review",
        "approved",
        "rejected",
    }

    VALID_TRANSACTION_TYPES = {
        "income",
        "expense",
        "asset",
        "liability",
        "equity",
    }

    VALID_STATEMENT_TYPES = {
        "balance_sheet",
        "income_statement",
        "profit_and_loss",
        "cash_flow_statement",
        "trial_balance",
        "other",
    }

    VALID_PERIOD_TYPES = {
        "monthly",
        "quarterly",
        "half_yearly",
        "annual",
        "yearly",
        "custom",
    }

    VALID_STATEMENT_LINE_ITEM_TYPES = {
        "income",
        "expense",
        "asset",
        "liability",
        "equity",
        "calculated",
        "operating",
        "investing",
        "financing",
    }

    STATEMENT_ALLOWED_LINE_ITEM_TYPES = {
        "balance_sheet": {
            "asset",
            "liability",
            "equity",
        },

        "income_statement": {
            "income",
            "expense",
            "calculated",
        },

        "profit_and_loss": {
            "income",
            "expense",
            "calculated",
        },

        "cash_flow_statement": {
            "operating",
            "investing",
            "financing",
            "calculated",
        },

        "trial_balance": {
            "income",
            "expense",
            "asset",
            "liability",
            "equity",
        },

        "other": {
            "income",
            "expense",
            "asset",
            "liability",
            "equity",
            "calculated",
        },
    }

    # ========================================================================
    # CANDIDATE RETRIEVAL
    # ========================================================================

    @classmethod
    def get_pending_candidates(cls, organization_id):
        """
        Return all candidates awaiting review for an organization.

        Duplicate statement candidates are identified in memory and exposed
        through the temporary attributes:

            candidate.is_duplicate
            candidate.duplicate_line_item

        These attributes are not database columns.

        Important:
        A candidate is considered a statement candidate based on the
        associated extraction's statement_type, NOT merely from
        transaction_type.

        This prevents ordinary Income/Expense transactions from being
        incorrectly treated as financial-statement line items.
        """

        candidates = (
            ExtractionCandidate.query
            .filter_by(
                organization_id=int(organization_id),
                review_status="pending_review",
            )
            .order_by(
                ExtractionCandidate.transaction_date.asc(),
                ExtractionCandidate.id.asc(),
            )
            .all()
        )

        for candidate in candidates:
            candidate.is_duplicate = False
            candidate.duplicate_line_item = None

            extraction = candidate.extraction

            statement_type = (
                extraction.statement_type
                if extraction is not None
                else None
            )

            is_statement_candidate = (
                statement_type in {
                    "balance_sheet",
                    "income_statement",
                    "profit_and_loss",
                    "cash_flow_statement",
                    "trial_balance",
                }
            )

            if is_statement_candidate:
                duplicate = cls.find_duplicate_statement_line_item(
                    candidate
                )

                if duplicate is not None:
                    candidate.is_duplicate = True
                    candidate.duplicate_line_item = duplicate

        return candidates

    @classmethod
    def get_candidate(
        cls,
        candidate_id,
        organization_id,
    ):
        """
        Retrieve a candidate while enforcing organization isolation.
        """

        return (
            ExtractionCandidate.query
            .filter_by(
                id=int(candidate_id),
                organization_id=int(organization_id),
            )
            .first()
        )

    # ========================================================================
    # TRANSACTION APPROVAL
    # ========================================================================

    @classmethod
    def approve_candidate(
        cls,
        candidate,
        reviewer,
        transaction_data=None,
        correction_notes=None,
    ):
        """
        Approve an income or expense candidate and create the corresponding
        trusted Transaction record.

        Asset, liability, equity, and financial-statement candidates must use
        approve_statement_line_item().
        """

        if candidate is None:
            raise ValueError(
                "Extraction candidate was not found."
            )

        if reviewer is None:
            raise PermissionError(
                "A valid reviewer is required."
            )

        if candidate.review_status != "pending_review":
            raise ValueError(
                "Only candidates pending review can be approved."
            )

        if candidate.transaction_id is not None:
            raise ValueError(
                "This extraction candidate is already linked "
                "to a transaction."
            )

        # ------------------------------------------------------------------
        # Prevent financial-statement candidates from entering the
        # transaction approval workflow.
        # ------------------------------------------------------------------

        extraction = candidate.extraction

        statement_type = (
            extraction.statement_type
            if extraction is not None
            else None
        )

        if statement_type in {
            "balance_sheet",
            "income_statement",
            "profit_and_loss",
            "cash_flow_statement",
            "trial_balance",
        }:
            raise ValueError(
                "This candidate belongs to a financial statement. "
                "Use the statement line-item approval workflow."
            )

        data = cls._prepare_transaction_data(
            candidate=candidate,
            transaction_data=transaction_data,
        )

        cls._validate_transaction_data(data)

        if data["transaction_type"] not in {
            "income",
            "expense",
        }:
            raise ValueError(
                "Only income and expense candidates can be "
                "approved as transactions."
            )

        transaction = Transaction(
            organization_id=candidate.organization_id,
            financial_statement_id=None,
            transaction_date=data["transaction_date"],
            description=data["description"],
            reference_number=data["reference_number"],
            amount=data["amount"],
            transaction_type=data["transaction_type"],
            category=data["category"],
            subcategory=data["subcategory"],
            source="Document Extraction",
            is_recurring=data["is_recurring"],
            confidence_score=data["confidence_score"],
            notes=data["notes"],
        )

        db.session.add(transaction)
        db.session.flush()

        candidate.transaction_id = transaction.id
        candidate.review_status = "approved"
        candidate.reviewed_by = reviewer.id
        candidate.reviewed_at = datetime.utcnow()
        candidate.correction_notes = correction_notes

        db.session.commit()

        return transaction

    # ========================================================================
    # STATEMENT LINE-ITEM APPROVAL
    # ========================================================================

    @classmethod
    def approve_statement_line_item(
        cls,
        candidate,
        reviewer,
        statement_data,
        line_item_data,
        correction_notes=None,
    ):
        """
        Approve an extracted financial-statement line item.

        Supported statement types:

            Balance Sheet
                asset / liability / equity

            Profit & Loss / Income Statement
                income / expense / calculated

            Cash Flow Statement
                operating / investing / financing / calculated

            Trial Balance
                income / expense / asset / liability / equity

        Approved statement candidates are persisted as
        FinancialStatementLineItem records.

        They are NOT converted into Transaction records.
        """

        if candidate is None:
            raise ValueError(
                "Extraction candidate was not found."
            )

        if reviewer is None:
            raise PermissionError(
                "A valid reviewer is required."
            )

        if candidate.review_status != "pending_review":
            raise ValueError(
                "Only candidates pending review can be approved."
            )

        if candidate.transaction_id is not None:
            raise ValueError(
                "This extraction candidate is already linked "
                "to a transaction."
            )

        statement_data = statement_data or {}
        line_item_data = line_item_data or {}

        # ------------------------------------------------------------------
        # Statement metadata
        # ------------------------------------------------------------------

        statement_type = cls._clean_string(
            statement_data.get("statement_type")
        )

        period_type = cls._clean_string(
            statement_data.get("period_type")
        )

        period_start = cls._parse_date(
            statement_data.get("period_start")
        )

        period_end = cls._parse_date(
            statement_data.get("period_end")
        )

        fiscal_year = cls._parse_integer(
            statement_data.get("fiscal_year")
        )

        # ------------------------------------------------------------------
        # Line-item values
        # ------------------------------------------------------------------

        line_item_name = cls._clean_string(
            line_item_data.get(
                "line_item_name",
                candidate.description,
            )
        )

        section = cls._clean_string(
            line_item_data.get("section")
        )

        account_type = cls._normalize_transaction_type(
            line_item_data.get(
                "account_type",
                candidate.transaction_type,
            )
        )

        amount = cls._parse_decimal(
            line_item_data.get(
                "amount",
                candidate.amount,
            )
        )

        # ------------------------------------------------------------------
        # Validate statement and line item
        # ------------------------------------------------------------------

        cls._validate_statement_data(
            statement_type=statement_type,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            fiscal_year=fiscal_year,
        )

        cls._validate_statement_line_item_data(
            candidate=candidate,
            statement_type=statement_type,
            line_item_name=line_item_name,
            section=section,
            account_type=account_type,
            amount=amount,
        )

        # ------------------------------------------------------------------
        # Extraction validation
        # ------------------------------------------------------------------

        extraction = candidate.extraction

        if extraction is None:
            raise ValueError(
                "The extraction record associated with this candidate "
                "could not be found."
            )

        if extraction.organization_id != candidate.organization_id:
            raise ValueError(
                "The extraction does not belong to the candidate's "
                "organization."
            )

        # ------------------------------------------------------------------
        # Persist statement metadata on extraction.
        # ------------------------------------------------------------------

        extraction.statement_type = statement_type
        extraction.period_type = period_type
        extraction.period_start = period_start
        extraction.period_end = period_end
        extraction.fiscal_year = fiscal_year

        # ------------------------------------------------------------------
        # Find existing FinancialStatement linked to extraction.
        # ------------------------------------------------------------------

        statement = None

        if extraction.financial_statement_id:
            statement = db.session.get(
                FinancialStatement,
                extraction.financial_statement_id,
            )

            if statement is not None:
                cls._validate_existing_statement_context(
                    statement=statement,
                    organization_id=candidate.organization_id,
                    statement_type=statement_type,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    fiscal_year=fiscal_year,
                )

        # ------------------------------------------------------------------
        # Find/create FinancialStatement.
        # ------------------------------------------------------------------

        if statement is None:

            upload = (
                Upload.query
                .filter_by(
                    id=extraction.upload_id,
                    organization_id=candidate.organization_id,
                )
                .first()
            )

            statement = (
                FinancialStatement.query
                .filter_by(
                    organization_id=candidate.organization_id,
                    statement_type=statement_type,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    fiscal_year=fiscal_year,
                )
                .first()
            )

            if statement is None:

                statement = FinancialStatement(
                    organization_id=candidate.organization_id,
                    uploaded_by=(
                        upload.uploaded_by
                        if upload is not None
                        else None
                    ),
                    statement_type=statement_type,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    fiscal_year=fiscal_year,
                    source_filename=(
                        upload.original_filename
                        if upload is not None
                        else None
                    ),
                    source_file_hash=(
                        upload.file_hash
                        if upload is not None
                        else None
                    ),
                    processing_status="completed",
                    processed_at=datetime.utcnow(),
                )

                db.session.add(statement)
                db.session.flush()

            else:
                cls._validate_existing_statement_context(
                    statement=statement,
                    organization_id=candidate.organization_id,
                    statement_type=statement_type,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    fiscal_year=fiscal_year,
                )

        # ------------------------------------------------------------------
        # Link extraction to statement.
        # ------------------------------------------------------------------

        extraction.financial_statement_id = statement.id

        # ------------------------------------------------------------------
        # Prevent duplicate line items.
        # ------------------------------------------------------------------

        existing_line_item = (
            FinancialStatementLineItem.query
            .filter_by(
                organization_id=candidate.organization_id,
                financial_statement_id=statement.id,
                line_item_name=line_item_name,
                amount=amount,
            )
            .first()
        )

        if existing_line_item is not None:

            candidate.review_status = "approved"
            candidate.reviewed_by = reviewer.id
            candidate.reviewed_at = datetime.utcnow()
            candidate.correction_notes = correction_notes

            cls._recalculate_statement_totals(
                statement
            )

            db.session.commit()

            return existing_line_item

        # ------------------------------------------------------------------
        # Create trusted FinancialStatementLineItem.
        # ------------------------------------------------------------------

        normalized_name = cls._normalize_line_item_name(
            line_item_name
        )

        line_item = FinancialStatementLineItem(
            organization_id=candidate.organization_id,
            financial_statement_id=statement.id,
            line_item_name=line_item_name,
            normalized_name=normalized_name,
            section=section,
            account_type=account_type,
            amount=amount,
            source_description=candidate.description,
            confidence_score=candidate.confidence_score,
        )

        db.session.add(line_item)

        # ------------------------------------------------------------------
        # Mark candidate approved.
        # ------------------------------------------------------------------

        candidate.review_status = "approved"
        candidate.reviewed_by = reviewer.id
        candidate.reviewed_at = datetime.utcnow()
        candidate.correction_notes = correction_notes

        db.session.flush()

        # ------------------------------------------------------------------
        # Recalculate statement totals.
        # ------------------------------------------------------------------

        cls._recalculate_statement_totals(
            statement
        )

        db.session.commit()

        return line_item

    @classmethod
    def _recalculate_statement_totals(
        cls,
        statement,
    ):
        """
        Recalculate trusted statement totals from approved
        FinancialStatementLineItem records.

        Calculated P&L rows such as Gross Profit and Net Profit
        are not added together as ordinary income/expense rows.
        """

        line_items = (
            FinancialStatementLineItem.query
            .filter_by(
                organization_id=statement.organization_id,
                financial_statement_id=statement.id,
            )
            .all()
        )

        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")

        net_profit = None

        for item in line_items:

            if item.amount is None:
                continue

            amount = Decimal(str(item.amount))

            account_type = (
                (item.account_type or "")
                .strip()
                .lower()
            )

            normalized_name = (
                (item.normalized_name or item.line_item_name or "")
                .strip()
                .lower()
            )

            if account_type == "income":
                total_revenue += amount

            elif account_type == "expense":
                total_expenses += amount

            elif account_type == "asset":
                total_assets += amount

            elif account_type == "liability":
                total_liabilities += amount

            elif account_type == "equity":
                total_equity += amount

            if account_type == "calculated":
                if (
                    "net profit" in normalized_name
                    or "net income" in normalized_name
                    or "profit after tax" in normalized_name
                ):
                    net_profit = amount

        # ------------------------------------------------------------------
        # P&L / Income Statement
        # ------------------------------------------------------------------

        if statement.statement_type in {
            "income_statement",
            "profit_and_loss",
        }:

            statement.total_revenue = total_revenue
            statement.total_expenses = total_expenses

            if net_profit is not None:
                statement.net_profit = net_profit
            else:
                statement.net_profit = (
                    total_revenue
                    - total_expenses
                )

        # ------------------------------------------------------------------
        # Balance Sheet
        # ------------------------------------------------------------------

        elif statement.statement_type == "balance_sheet":

            statement.total_assets = total_assets
            statement.total_liabilities = total_liabilities
            statement.total_equity = total_equity

        statement.processing_status = "completed"
        statement.processed_at = datetime.utcnow()

    # ========================================================================
    # DUPLICATE DETECTION
    # ========================================================================

    @classmethod
    def find_duplicate_statement_line_item(
        cls,
        candidate,
        statement=None,
        line_item_name=None,
        account_type=None,
        amount=None,
    ):
        """
        Find an existing trusted statement line item that represents
        the same financial record as the supplied candidate.

        Matching criteria:

        - Same organization.
        - Same financial statement.
        - Same normalized line-item name.
        - Same account type.
        - Same amount.
        """

        if candidate is None:
            return None

        if candidate.organization_id is None:
            return None

        if statement is None:
            extraction = candidate.extraction

            if extraction is not None:
                statement = extraction.financial_statement

        if statement is None:
            return None

        if line_item_name is None:
            line_item_name = candidate.description

        if account_type is None:
            account_type = candidate.transaction_type

        if amount is None:
            amount = candidate.amount

        normalized_name = cls._normalize_line_item_name(
            line_item_name
        )

        account_type = cls._normalize_transaction_type(
            account_type
        )

        amount = cls._parse_decimal(amount)

        if not normalized_name:
            return None

        if not account_type:
            return None

        if amount is None:
            return None

        line_items = (
            FinancialStatementLineItem.query
            .filter_by(
                financial_statement_id=statement.id,
                organization_id=candidate.organization_id,
            )
            .order_by(
                FinancialStatementLineItem.id.asc()
            )
            .all()
        )

        for line_item in line_items:

            existing_name = cls._normalize_line_item_name(
                line_item.normalized_name
            )

            existing_account_type = (
                cls._normalize_transaction_type(
                    line_item.account_type
                )
            )

            existing_amount = cls._parse_decimal(
                line_item.amount
            )

            if (
                existing_name == normalized_name
                and existing_account_type == account_type
                and existing_amount == amount
            ):
                return line_item

        return None

    # ========================================================================
    # CANDIDATE REJECTION
    # ========================================================================

    @classmethod
    def reject_candidate(
        cls,
        candidate,
        reviewer,
        correction_notes=None,
    ):
        """
        Reject an extracted candidate without creating a trusted record.
        """

        if candidate is None:
            raise ValueError(
                "Extraction candidate was not found."
            )

        if reviewer is None:
            raise PermissionError(
                "A valid reviewer is required."
            )

        if candidate.review_status != "pending_review":
            raise ValueError(
                "Only candidates pending review can be rejected."
            )

        candidate.review_status = "rejected"
        candidate.reviewed_by = reviewer.id
        candidate.reviewed_at = datetime.utcnow()
        candidate.correction_notes = correction_notes

        db.session.commit()

        return candidate

    # ========================================================================
    # CANDIDATE UPDATE
    # ========================================================================

    @classmethod
    def update_candidate(
        cls,
        candidate,
        values,
    ):
        """
        Update extracted values before approval.

        This method does not approve the candidate.

        Statement-level metadata is stored on the associated
        DocumentExtraction record.

        Statement line-item corrections reuse the existing
        ExtractionCandidate fields:

            line_item_name -> description
            section        -> subcategory
            account_type   -> transaction_type

        This avoids unnecessary schema changes and migrations.
        """

        if candidate is None:
            raise ValueError(
                "Extraction candidate was not found."
            )

        if candidate.review_status != "pending_review":
            raise ValueError(
                "Only candidates pending review can be edited."
            )

        if not isinstance(values, dict):
            raise ValueError(
                "Candidate values must be provided as a dictionary."
            )

        # --------------------------------------------------------------------
        # Standard candidate fields
        # --------------------------------------------------------------------

        if "transaction_date" in values:
            candidate.transaction_date = cls._parse_date(
                values["transaction_date"]
            )

        if "description" in values:
            candidate.description = cls._clean_string(
                values["description"]
            )

        if "reference_number" in values:
            candidate.reference_number = cls._clean_string(
                values["reference_number"]
            )

        if "amount" in values:
            candidate.amount = cls._parse_decimal(
                values["amount"]
            )

        if "debit_credit" in values:
            candidate.debit_credit = cls._clean_string(
                values["debit_credit"]
            )

        if "transaction_type" in values:
            candidate.transaction_type = (
                cls._normalize_transaction_type(
                    values["transaction_type"]
                )
            )

        if "category" in values:
            candidate.category = cls._clean_string(
                values["category"]
            )

        if "subcategory" in values:
            candidate.subcategory = cls._clean_string(
                values["subcategory"]
            )

        # --------------------------------------------------------------------
        # Statement line-item corrections
        # --------------------------------------------------------------------
        #
        # These values are supplied by the statement review interface.
        #
        # line_item_name -> candidate.description
        # section        -> candidate.subcategory
        # account_type   -> candidate.transaction_type
        #
        # This allows P&L rows such as:
        #
        #   Sales Revenue       -> income
        #   Rent                -> expense
        #   Gross Profit        -> calculated
        #   Net Profit          -> calculated
        #
        # without creating a separate database schema.
        # --------------------------------------------------------------------

        if "line_item_name" in values:

            candidate.description = cls._clean_string(
                values["line_item_name"]
            )

        if "section" in values:

            candidate.subcategory = cls._clean_string(
                values["section"]
            )

        if "account_type" in values:

            account_type = cls._normalize_transaction_type(
                values["account_type"]
            )

            if account_type not in (
                cls.VALID_STATEMENT_LINE_ITEM_TYPES
            ):
                raise ValueError(
                    "Invalid statement account type."
                )

            candidate.transaction_type = account_type

        # --------------------------------------------------------------------
        # Correction notes
        # --------------------------------------------------------------------

        if "correction_notes" in values:
            candidate.correction_notes = cls._clean_string(
                values["correction_notes"]
            )

        # --------------------------------------------------------------------
        # Statement context
        # --------------------------------------------------------------------

        statement_keys = {
            "statement_type",
            "period_type",
            "period_start",
            "period_end",
            "fiscal_year",
        }

        statement_values_present = any(
            key in values
            and values.get(key) not in (
                None,
                "",
            )
            for key in statement_keys
        )

        if statement_values_present:

            extraction = candidate.extraction

            if extraction is None:
                raise ValueError(
                    "The extraction record associated with this candidate "
                    "could not be found."
                )

            # --------------------------------------------------------------
            # Statement type
            # --------------------------------------------------------------

            if "statement_type" in values:

                statement_type = cls._clean_string(
                    values["statement_type"]
                )

                if statement_type is not None:

                    if statement_type not in (
                        cls.VALID_STATEMENT_TYPES
                    ):
                        raise ValueError(
                            "Invalid statement type."
                        )

                    extraction.statement_type = statement_type

            # --------------------------------------------------------------
            # Period type
            # --------------------------------------------------------------

            if "period_type" in values:

                period_type = cls._clean_string(
                    values["period_type"]
                )

                if period_type is not None:

                    if period_type not in (
                        cls.VALID_PERIOD_TYPES
                    ):
                        raise ValueError(
                            "Invalid period type."
                        )

                    extraction.period_type = period_type

            # --------------------------------------------------------------
            # Period start
            # --------------------------------------------------------------

            if "period_start" in values:

                period_start = cls._parse_date(
                    values["period_start"]
                )

                if period_start is not None:
                    extraction.period_start = period_start

            # --------------------------------------------------------------
            # Period end
            # --------------------------------------------------------------

            if "period_end" in values:

                period_end = cls._parse_date(
                    values["period_end"]
                )

                if period_end is not None:
                    extraction.period_end = period_end

            # --------------------------------------------------------------
            # Fiscal year
            # --------------------------------------------------------------

            if "fiscal_year" in values:

                fiscal_year = cls._parse_integer(
                    values["fiscal_year"]
                )

                if fiscal_year is not None:

                    if not 1900 <= fiscal_year <= 2200:
                        raise ValueError(
                            "Fiscal year must be between 1900 and 2200."
                        )

                    extraction.fiscal_year = fiscal_year

            # --------------------------------------------------------------
            # Validate period
            # --------------------------------------------------------------

            if (
                extraction.period_start is not None
                and extraction.period_end is not None
                and extraction.period_start
                > extraction.period_end
            ):
                raise ValueError(
                    "Statement period start cannot be after "
                    "the statement period end."
                )

        db.session.commit()

        return candidate

    # ========================================================================
    # TRANSACTION PREPARATION
    # ========================================================================

    @classmethod
    def _prepare_transaction_data(
        cls,
        candidate,
        transaction_data=None,
    ):
        """
        Merge candidate values with optional reviewer corrections.
        """

        transaction_data = transaction_data or {}

        return {
            "transaction_date": cls._parse_date(
                transaction_data.get(
                    "transaction_date",
                    candidate.transaction_date,
                )
            ),
            "description": cls._clean_string(
                transaction_data.get(
                    "description",
                    candidate.description,
                )
            ),
            "reference_number": cls._clean_string(
                transaction_data.get(
                    "reference_number",
                    candidate.reference_number,
                )
            ),
            "amount": cls._parse_decimal(
                transaction_data.get(
                    "amount",
                    candidate.amount,
                )
            ),
            "transaction_type": cls._normalize_transaction_type(
                transaction_data.get(
                    "transaction_type",
                    candidate.transaction_type,
                )
            ),
            "category": cls._clean_string(
                transaction_data.get(
                    "category",
                    candidate.category,
                )
            ),
            "subcategory": cls._clean_string(
                transaction_data.get(
                    "subcategory",
                    candidate.subcategory,
                )
            ),
            "is_recurring": cls._parse_boolean(
                transaction_data.get(
                    "is_recurring",
                    False,
                )
            ),
            "confidence_score": cls._parse_decimal(
                transaction_data.get(
                    "confidence_score",
                    candidate.confidence_score,
                )
            ),
            "notes": cls._clean_string(
                transaction_data.get(
                    "notes",
                    candidate.correction_notes,
                )
            ),
        }

    # ========================================================================
    # TRANSACTION VALIDATION
    # ========================================================================

    @classmethod
    def _validate_transaction_data(cls, data):
        """
        Validate final reviewed transaction values.
        """

        if data["transaction_date"] is None:
            raise ValueError(
                "Transaction date is required."
            )

        if not data["description"]:
            raise ValueError(
                "Transaction description is required."
            )

        if data["amount"] is None:
            raise ValueError(
                "Transaction amount is required."
            )

        if data["amount"] == Decimal("0"):
            raise ValueError(
                "Transaction amount cannot be zero."
            )

        if not data["transaction_type"]:
            raise ValueError(
                "Transaction type is required."
            )

        if (
            data["transaction_type"]
            not in cls.VALID_TRANSACTION_TYPES
        ):
            raise ValueError(
                "Invalid transaction type. "
                "Use income, expense, asset, liability, or equity."
            )

        if data["confidence_score"] is not None:

            if not (
                Decimal("0")
                <= data["confidence_score"]
                <= Decimal("1")
            ):
                raise ValueError(
                    "Confidence score must be between 0 and 1."
                )

    # ========================================================================
    # STATEMENT VALIDATION
    # ========================================================================

    @classmethod
    def _validate_statement_data(
        cls,
        statement_type,
        period_type,
        period_start,
        period_end,
        fiscal_year,
    ):
        """
        Validate statement metadata required for approval.
        """

        if not statement_type:
            raise ValueError(
                "Statement type is required."
            )

        if statement_type not in cls.VALID_STATEMENT_TYPES:
            raise ValueError(
                "Invalid statement type."
            )

        if not period_type:
            raise ValueError(
                "Period type is required."
            )

        if period_type not in cls.VALID_PERIOD_TYPES:
            raise ValueError(
                "Invalid period type."
            )

        if period_start is None:
            raise ValueError(
                "Statement period start is required."
            )

        if period_end is None:
            raise ValueError(
                "Statement period end is required."
            )

        if period_start > period_end:
            raise ValueError(
                "Statement period start cannot be after "
                "the statement period end."
            )

        if fiscal_year is None:
            raise ValueError(
                "Fiscal year is required."
            )

        if not 1900 <= fiscal_year <= 2200:
            raise ValueError(
                "Fiscal year must be between 1900 and 2200."
            )

    @classmethod
    def _validate_statement_line_item_data(
        cls,
        candidate,
        statement_type,
        line_item_name,
        section,
        account_type,
        amount,
    ):
        """
        Validate statement line-item data according to the
        selected financial statement type.
        """

        if not statement_type:
            raise ValueError(
                "Statement type is required."
            )

        if statement_type not in cls.VALID_STATEMENT_TYPES:
            raise ValueError(
                "Invalid statement type."
            )

        if not line_item_name:
            raise ValueError(
                "Statement line item name is required."
            )

        if not section:
            raise ValueError(
                "Statement section is required."
            )

        if not account_type:
            raise ValueError(
                "Statement account type is required."
            )

        if account_type not in cls.VALID_STATEMENT_LINE_ITEM_TYPES:
            raise ValueError(
                "Invalid statement account type."
            )

        allowed_types = (
            cls.STATEMENT_ALLOWED_LINE_ITEM_TYPES.get(
                statement_type,
                set(),
            )
        )

        if account_type not in allowed_types:
            raise ValueError(
                (
                    f"'{account_type}' is not valid for "
                    f"{statement_type.replace('_', ' ')}."
                )
            )

        # ------------------------------------------------------------------
        # Validate section according to statement type.
        # ------------------------------------------------------------------

        if statement_type == "balance_sheet":

            allowed_sections = {
                "assets",
                "liabilities",
                "equity",
            }

        elif statement_type in {
            "income_statement",
            "profit_and_loss",
        }:

            allowed_sections = {
                "revenue",
                "cost of sales",
                "cost of goods sold",
                "cost of goods / services",
                "operating expenses",
                "operating expense",
                "tax",
                "taxation",
                "other income",
                "calculated",
                "profit",
            }

        elif statement_type == "cash_flow_statement":

            allowed_sections = {
                "operating activities",
                "investing activities",
                "financing activities",
                "operating",
                "investing",
                "financing",
                "calculated",
            }

        elif statement_type == "trial_balance":

            allowed_sections = {
                "income",
                "expense",
                "assets",
                "liabilities",
                "equity",
            }

        else:

            allowed_sections = set()

        normalized_section = section.strip().lower()

        if (
            allowed_sections
            and normalized_section not in allowed_sections
        ):
            raise ValueError(
                (
                    f"Invalid statement section '{section}' "
                    f"for {statement_type.replace('_', ' ')}."
                )
            )

        # ------------------------------------------------------------------
        # Reviewer corrections are allowed.
        #
        # OCR/AI extraction can initially classify a row incorrectly.
        # Therefore, we do NOT reject a corrected classification merely
        # because it differs from candidate.transaction_type.
        # ------------------------------------------------------------------

        if amount is None:
            raise ValueError(
                "Statement line item amount is required."
            )

        if amount == Decimal("0"):
            raise ValueError(
                "Statement line item amount cannot be zero."
            )

    # ========================================================================
    # EXISTING STATEMENT VALIDATION
    # ========================================================================

    @classmethod
    def _validate_existing_statement_context(
        cls,
        statement,
        organization_id,
        statement_type,
        period_type,
        period_start,
        period_end,
        fiscal_year,
    ):
        """
        Ensure an existing financial statement belongs to the organization
        and matches the reviewed statement context.
        """

        if statement.organization_id != int(organization_id):
            raise PermissionError(
                "The existing financial statement does not belong "
                "to this organization."
            )

        if statement.statement_type != statement_type:
            raise ValueError(
                "The existing financial statement has a different "
                "statement type."
            )

        if statement.period_type != period_type:
            raise ValueError(
                "The existing financial statement has a different "
                "period type."
            )

        if statement.period_start != period_start:
            raise ValueError(
                "The existing financial statement has a different "
                "period start date."
            )

        if statement.period_end != period_end:
            raise ValueError(
                "The existing financial statement has a different "
                "period end date."
            )

        if statement.fiscal_year != fiscal_year:
            raise ValueError(
                "The existing financial statement has a different "
                "fiscal year."
            )

    # ========================================================================
    # NORMALIZATION HELPERS
    # ========================================================================

    @staticmethod
    def _normalize_transaction_type(value):
        """
        Normalize transaction/account type values.

        Normal transaction types:

            income
            expense
            asset
            liability
            equity

        Financial statement classifications:

            calculated
            operating
            investing
            financing
        """

        if value is None:
            return None

        value = str(value).strip().lower()

        aliases = {
            "income": "income",
            "revenue": "income",
            "credit": "income",

            "expense": "expense",
            "expenses": "expense",
            "debit": "expense",

            "asset": "asset",
            "assets": "asset",

            "liability": "liability",
            "liabilities": "liability",

            "equity": "equity",

            "calculated": "calculated",

            "operating": "operating",

            "investing": "investing",

            "financing": "financing",
        }

        return aliases.get(
            value,
            value,
        )

    @staticmethod
    def _normalize_line_item_name(value):
        """
        Normalize financial statement line-item names for duplicate detection.

        This intentionally performs conservative normalization.

        Examples:

            Cash and Cash Equivalents
            -> cash and cash equivalents

            Property, Plant, and Equipment
            -> property plant and equipment
        """

        if value is None:
            return None

        value = str(value).strip().lower()

        replacements = {
            "deffered": "deferred",
            "deffered tax": "deferred tax",
            "a/c": "account",
        }

        for source, target in replacements.items():
            value = value.replace(
                source,
                target,
            )

        normalized_characters = []

        for character in value:

            if character.isalnum() or character.isspace():
                normalized_characters.append(
                    character
                )
            else:
                normalized_characters.append(" ")

        value = "".join(
            normalized_characters
        )

        return " ".join(
            value.split()
        )

    # ========================================================================
    # GENERAL PARSING HELPERS
    # ========================================================================

    @staticmethod
    def _clean_string(value):
        """
        Clean a text value.
        """

        if value is None:
            return None

        value = str(value).strip()

        return value if value else None

    @staticmethod
    def _parse_decimal(value):
        """
        Convert a value to Decimal.
        """

        if value is None or value == "":
            return None

        if isinstance(value, Decimal):
            return value

        try:

            decimal_value = Decimal(
                str(value)
                .replace(",", "")
                .strip()
            )

            if not decimal_value.is_finite():
                return None

            return decimal_value

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            raise ValueError(
                f"Invalid numeric value: {value}"
            )

    @staticmethod
    def _parse_integer(value):
        """
        Convert a value to integer.
        """

        if value is None or value == "":
            return None

        if isinstance(value, bool):
            raise ValueError(
                "Invalid integer value."
            )

        try:

            return int(
                str(value).strip()
            )

        except (
            ValueError,
            TypeError,
        ):
            raise ValueError(
                f"Invalid integer value: {value}"
            )

    @staticmethod
    def _parse_date(value):
        """
        Parse common financial-document date representations.
        """

        if value is None or value == "":
            return None

        if isinstance(value, datetime):
            return value.date()

        if hasattr(
            value,
            "date",
        ) and not isinstance(
            value,
            str,
        ):

            try:
                return value.date()

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):
                pass

        if (
            hasattr(value, "year")
            and hasattr(value, "month")
            and hasattr(value, "day")
        ):

            try:
                return value

            except (
                AttributeError,
                TypeError,
                ValueError,
            ):
                pass

        value = str(value).strip()

        formats = (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%m/%d/%Y",
        )

        for date_format in formats:

            try:

                return datetime.strptime(
                    value,
                    date_format,
                ).date()

            except ValueError:
                continue

        raise ValueError(
            f"Invalid date value: {value}"
        )

    @staticmethod
    def _parse_boolean(value):
        """
        Parse common boolean representations.
        """

        if value is None:
            return False

        if isinstance(value, bool):
            return value

        value = str(value).strip().lower()

        if value in {
            "true",
            "1",
            "yes",
            "on",
        }:
            return True

        if value in {
            "false",
            "0",
            "no",
            "off",
            "",
        }:
            return False

        raise ValueError(
            f"Invalid boolean value: {value}"
        )