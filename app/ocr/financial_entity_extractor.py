import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

DATE_PATTERNS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
)


DATE_REGEX = re.compile(
    r"\b("
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|"
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|"
    r"\d{1,2}\.\d{1,2}\.\d{2,4}"
    r")\b"
)


# ---------------------------------------------------------------------------
# Financial amount parsing
# ---------------------------------------------------------------------------

AMOUNT_REGEX = re.compile(
    r"""
    (?<![\w])
    (?P<currency>₹|Rs\.?|INR)?
    \s*
    (?P<sign>[+-])?
    (?P<number>
        (?:
            \d{1,3}(?:,\d{2})+,\d{3}
            |
            \d{1,3}(?:,\d{3})+
            |
            \d+
        )
        (?:\.\d{1,2})?
    )
    (?![\w])
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Generic transaction keywords
# ---------------------------------------------------------------------------

DEBIT_KEYWORDS = {
    "debit",
    "debited",
    "withdrawal",
    "withdraw",
    "payment",
    "paid",
    "expense",
    "purchase",
    "charge",
    "charges",
    "bill",
    "fee",
    "fees",
    "dr",
}


CREDIT_KEYWORDS = {
    "credit",
    "credited",
    "deposit",
    "deposited",
    "received",
    "income",
    "refund",
    "interest",
    "cr",
}


CATEGORY_KEYWORDS = {
    "salary": "Salary",
    "wages": "Salary",
    "electricity": "Utilities",
    "water bill": "Utilities",
    "electric bill": "Utilities",
    "utility": "Utilities",
    "rent": "Rent",
    "lease": "Rent",
    "groceries": "Food",
    "restaurant": "Food",
    "food": "Food",
    "fuel": "Transportation",
    "petrol": "Transportation",
    "diesel": "Transportation",
    "travel": "Transportation",
    "insurance": "Insurance",
    "tax": "Taxes",
    "gst": "Taxes",
    "subscription": "Subscriptions",
    "interest": "Interest",
    "loan": "Loan",
    "emi": "Loan",
}


# ---------------------------------------------------------------------------
# Balance-sheet sections
# ---------------------------------------------------------------------------

BALANCE_SHEET_SECTIONS = {
    "equity": (
        "equity",
        "shareholders fund",
        "shareholders' fund",
        "shareholder fund",
        "owners equity",
        "owner's equity",
        "capital",
    ),
    "liability": (
        "liabilities",
        "liability",
        "current liabilities",
        "long term liabilities",
        "long-term liabilities",
        "non current liabilities",
        "non-current liabilities",
    ),
    "asset": (
        "assets",
        "asset",
        "current assets",
        "fixed assets",
        "non current assets",
        "non-current assets",
    ),
}


# ---------------------------------------------------------------------------
# Specific balance-sheet items
# ---------------------------------------------------------------------------

BALANCE_SHEET_ITEM_KEYWORDS = {
    "common stock": ("Equity", "equity"),
    "share capital": ("Equity", "equity"),
    "retained earnings": ("Equity", "equity"),
    "owners equity": ("Equity", "equity"),
    "owner equity": ("Equity", "equity"),

    "accounts payable": ("Accounts Payable", "liability"),
    "short term loan": ("Short-Term Loan", "liability"),
    "short-term loan": ("Short-Term Loan", "liability"),
    "accrued liabilities": ("Accrued Liabilities", "liability"),
    "long term loans": ("Long-Term Loan", "liability"),
    "long-term loans": ("Long-Term Loan", "liability"),
    "deferred tax liabilities": (
        "Deferred Tax Liability",
        "liability",
    ),
    "deffered tax liabilities": (
        "Deferred Tax Liability",
        "liability",
    ),

    "cash and cash equivalents": (
        "Cash & Cash Equivalents",
        "asset",
    ),
    "accounts receivable": (
        "Accounts Receivable",
        "asset",
    ),
    "inventory": (
        "Inventory",
        "asset",
    ),
    "prepaid expenses": (
        "Prepaid Expenses",
        "asset",
    ),
    "property plant and equipment": (
        "Property, Plant & Equipment",
        "asset",
    ),
    "property, plant, and equipment": (
        "Property, Plant & Equipment",
        "asset",
    ),
    "accumulated depreciation": (
        "Accumulated Depreciation",
        "asset",
    ),
    "net fixed assets": (
        "Net Fixed Assets",
        "asset",
    ),
}


# ---------------------------------------------------------------------------
# Derived / calculated financial values
# ---------------------------------------------------------------------------
#
# These values should not become independent transactions because they are
# calculated from other line items.
#
# Example:
#
#     Property, Plant, and Equipment     150,000
#     Accumulated Depreciation           -30,000
#     Net Fixed Assets                    120,000
#
# Importing all three as independent records would double-count the assets.
# ---------------------------------------------------------------------------

DERIVED_VALUE_KEYWORDS = (
    "net fixed assets",
    "net current assets",
    "net current liabilities",
    "net assets",
    "net liabilities",
    "net working capital",
    "net worth",
    "total equity",
    "total shareholders fund",
    "total shareholders' fund",
    "total shareholders",
    "total assets",
    "total liabilities",
    "total current assets",
    "total current liabilities",
    "total fixed assets",
    "total long term liabilities",
    "total long-term liabilities",
    "grand total",
    "subtotal",
    "sub total",
    "total",
)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(text):
    """
    Normalize OCR text for keyword matching.
    """
    if not text:
        return ""

    normalized = text.lower()

    normalized = normalized.replace(
        "&",
        " and ",
    )

    normalized = normalized.replace(
        "'",
        "",
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


# ---------------------------------------------------------------------------
# Generic parsing
# ---------------------------------------------------------------------------

def parse_amount(value):
    """
    Convert a financial amount representation into Decimal.

    Supports:
        25000
        60,000
        1,10,000
        ₹50,000
        Rs. 50,000
        INR 50,000
        -30,000
        (30,000)

    Invalid or non-finite values return None.
    """
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    negative_parentheses = (
        text.startswith("(")
        and text.endswith(")")
    )

    cleaned = re.sub(
        r"[^\d.\-+]",
        "",
        text.replace(",", ""),
    )

    if not cleaned:
        return None

    try:
        amount = Decimal(cleaned)

        if negative_parentheses:
            amount = -abs(amount)

        if not amount.is_finite():
            return None

        return amount

    except (InvalidOperation, ValueError):
        return None


def parse_date(value):
    """
    Parse common financial-document date formats.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()

    if not text:
        return None

    for date_format in DATE_PATTERNS:
        try:
            return datetime.strptime(
                text,
                date_format,
            ).date()
        except ValueError:
            continue

    return None


def extract_date(text):
    """
    Extract the first recognizable date from a line.
    """
    if not text:
        return None

    match = DATE_REGEX.search(text)

    if not match:
        return None

    return parse_date(match.group(1))


# ---------------------------------------------------------------------------
# Amount extraction
# ---------------------------------------------------------------------------

def _mask_dates(text):
    """
    Replace dates with spaces before amount extraction.

    This prevents a date such as:

        17/09/2026

    from being incorrectly interpreted as multiple monetary values.
    """
    if not text:
        return ""

    return DATE_REGEX.sub(
        lambda match: " " * len(match.group(0)),
        text,
    )


def extract_amount_matches(text):
    """
    Return detailed amount matches from a line.

    Each result contains:
        raw
        amount
        start
        end
    """
    if not text:
        return []

    searchable_text = _mask_dates(text)

    matches = []

    for match in AMOUNT_REGEX.finditer(
        searchable_text
    ):
        raw_value = match.group(0).strip()

        amount = parse_amount(
            raw_value
        )

        if amount is None:
            continue

        matches.append(
            {
                "raw": raw_value,
                "amount": amount,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return matches


def extract_amounts(text):
    """
    Extract all recognizable numeric financial amounts from a line.

    Returns:
        list[Decimal]
    """
    return [
        match["amount"]
        for match in extract_amount_matches(text)
    ]


# ---------------------------------------------------------------------------
# Debit / credit inference
# ---------------------------------------------------------------------------

def infer_debit_credit(text):
    """
    Infer debit/credit direction only when explicit financial language
    provides a reasonable signal.

    Returns:
        "debit", "credit", or None
    """
    if not text:
        return None

    lowered = text.lower()

    debit_match = any(
        re.search(
            rf"\b{re.escape(keyword)}\b",
            lowered,
        )
        for keyword in DEBIT_KEYWORDS
    )

    credit_match = any(
        re.search(
            rf"\b{re.escape(keyword)}\b",
            lowered,
        )
        for keyword in CREDIT_KEYWORDS
    )

    if debit_match and not credit_match:
        return "debit"

    if credit_match and not debit_match:
        return "credit"

    return None


def infer_transaction_type(debit_credit):
    """
    Map explicit debit/credit direction to a preliminary transaction type.
    """
    if debit_credit == "credit":
        return "income"

    if debit_credit == "debit":
        return "expense"

    return None


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

def infer_category(text):
    """
    Infer a preliminary category from explicit description keywords.
    """
    if not text:
        return None

    lowered = text.lower()

    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in lowered:
            return category

    return None


# ---------------------------------------------------------------------------
# Balance-sheet classification
# ---------------------------------------------------------------------------

def is_balance_sheet_heading(line):
    """
    Determine whether a line represents a balance-sheet section heading.

    Returns:
        "asset"
        "liability"
        "equity"
        None
    """
    normalized = normalize_text(line)

    if not normalized:
        return None

    for section, keywords in BALANCE_SHEET_SECTIONS.items():
        for keyword in keywords:
            if normalize_text(keyword) == normalized:
                return section

    return None


def infer_balance_sheet_item(line):
    """
    Identify known balance-sheet items.

    Returns:
        {
            "category": ...,
            "transaction_type": ...
        }

    or None.
    """
    normalized = normalize_text(line)

    if not normalized:
        return None

    for keyword in sorted(
        BALANCE_SHEET_ITEM_KEYWORDS,
        key=len,
        reverse=True,
    ):
        normalized_keyword = normalize_text(
            keyword
        )

        if normalized_keyword in normalized:
            category, transaction_type = (
                BALANCE_SHEET_ITEM_KEYWORDS[
                    keyword
                ]
            )

            return {
                "category": category,
                "transaction_type": transaction_type,
            }

    return None


def is_derived_value_line(line):
    """
    Determine whether a line represents a calculated, subtotal or total
    value rather than an independent financial item.
    """
    normalized = normalize_text(line)

    if not normalized:
        return False

    for keyword in DERIVED_VALUE_KEYWORDS:
        normalized_keyword = normalize_text(
            keyword
        )

        if normalized == normalized_keyword:
            return True

        if normalized.startswith(
            normalized_keyword + " "
        ):
            return True

    return False


# ---------------------------------------------------------------------------
# Description cleaning
# ---------------------------------------------------------------------------

def clean_description(text):
    """
    Remove dates and recognized numeric amounts from a line while
    preserving the remaining description.
    """
    if not text:
        return ""

    description = DATE_REGEX.sub(
        " ",
        text,
    )

    # Remove recognized monetary values.
    description = AMOUNT_REGEX.sub(
        " ",
        description,
    )

    description = re.sub(
        r"\s+",
        " ",
        description,
    )

    description = description.strip(
        " |,-:;\t"
    )

    return description[:500]


# ---------------------------------------------------------------------------
# Primary amount selection
# ---------------------------------------------------------------------------

def select_primary_amount(amount_matches):
    """
    Select the most likely individual item amount.

    Financial statements often contain:

        Retained Earnings 60,000 1,10,000

    where:
        60,000   = individual item amount
        1,10,000 = subtotal

    Therefore the first monetary value is selected.

    For ordinary transaction lines containing one amount, the same
    behavior naturally selects the only amount.
    """
    if not amount_matches:
        return None

    return amount_matches[0]["amount"]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def calculate_candidate_confidence(
    transaction_date,
    description,
    amount,
    debit_credit,
    transaction_type=None,
    category=None,
    balance_sheet_context=False,
):
    """
    Calculate a conservative extraction confidence.

    This represents extraction quality, not accounting correctness.

    Human review remains mandatory.
    """
    if amount is None:
        return None

    score = Decimal("0.40")

    if transaction_date is not None:
        score += Decimal("0.20")

    if description:
        score += Decimal("0.15")

    if debit_credit is not None:
        score += Decimal("0.15")

    if transaction_type is not None:
        score += Decimal("0.05")

    if category is not None:
        score += Decimal("0.05")

    if balance_sheet_context and transaction_type is not None:
        score = min(
            score,
            Decimal("0.85"),
        )

    return min(
        score,
        Decimal("1.00"),
    )


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------

def extract_candidate_from_line(
    line,
    section_context=None,
):
    """
    Extract a single reviewable financial candidate.

    The function does not invent missing values.

    Uncertain fields remain None and can be completed during manual review.
    """
    if not line:
        return None

    raw_line = line.strip()

    if not raw_line:
        return None

    # Section headings are not transactions.
    if is_balance_sheet_heading(raw_line):
        return None

    # Totals, subtotals and derived values are not independent transactions.
    if is_derived_value_line(raw_line):
        return None

    amount_matches = extract_amount_matches(
        raw_line
    )

    if not amount_matches:
        return None

    amount = select_primary_amount(
        amount_matches
    )

    transaction_date = extract_date(
        raw_line
    )

    debit_credit = infer_debit_credit(
        raw_line
    )

    transaction_type = infer_transaction_type(
        debit_credit
    )

    category = infer_category(
        raw_line
    )

    balance_sheet_item = infer_balance_sheet_item(
        raw_line
    )

    balance_sheet_context = (
        section_context
        in {
            "asset",
            "liability",
            "equity",
        }
    )

    # A clearly recognized balance-sheet item takes precedence over
    # generic debit/credit classification.
    if balance_sheet_item is not None:
        category = balance_sheet_item[
            "category"
        ]

        transaction_type = balance_sheet_item[
            "transaction_type"
        ]

        # Debit/credit is intentionally left unset because these are
        # accounting balances rather than ordinary cash-flow transactions.
        debit_credit = None

    elif balance_sheet_context:
        if section_context == "asset":
            transaction_type = "asset"

        elif section_context == "liability":
            transaction_type = "liability"

        elif section_context == "equity":
            transaction_type = "equity"

    description = clean_description(
        raw_line
    )

    if not description:
        description = raw_line[:500]

    confidence_score = calculate_candidate_confidence(
        transaction_date=transaction_date,
        description=description,
        amount=amount,
        debit_credit=debit_credit,
        transaction_type=transaction_type,
        category=category,
        balance_sheet_context=balance_sheet_context,
    )

    return {
        "date": (
            transaction_date.isoformat()
            if transaction_date
            else None
        ),
        "description": description,

        # IMPORTANT:
        # Do not use abs() here.
        # Negative accounting values such as accumulated depreciation
        # must retain their sign.
        "amount": str(amount),

        "debit_credit": debit_credit,
        "transaction_type": transaction_type,
        "category": category,
        "subcategory": None,
        "reference_number": None,

        "confidence_score": (
            str(confidence_score)
            if confidence_score is not None
            else None
        ),

        "raw_text": raw_line,
        "raw_line": raw_line,
    }


# ---------------------------------------------------------------------------
# Document-level extraction
# ---------------------------------------------------------------------------

def extract_candidates(text):
    """
    Extract financial candidates from cleaned document text.

    Basic balance-sheet section context is tracked so that assets,
    liabilities and equity can be classified appropriately.

    Every candidate remains untrusted until manually reviewed and approved.
    """
    if not text:
        return []

    candidates = []

    section_context = None

    for line in text.splitlines():
        raw_line = line.strip()

        if not raw_line:
            continue

        detected_section = is_balance_sheet_heading(
            raw_line
        )

        if detected_section is not None:
            section_context = detected_section
            continue

        candidate = extract_candidate_from_line(
            raw_line,
            section_context=section_context,
        )

        if candidate is not None:
            candidates.append(candidate)

    return candidates