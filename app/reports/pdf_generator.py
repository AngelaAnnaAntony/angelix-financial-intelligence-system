"""
ANGELIX PDF REPORT GENERATOR

Provides two separate professional PDF reports:

1. Financial Statements Report
   - Profit & Loss Statement
   - Income & Expenditure Statement
   - Balance Sheet
   - Cash Flow Summary when reliable transaction data is available

2. Financial Analysis Report
   - Executive Summary
   - KPIs
   - Revenue / Expense Analysis
   - Financial Ratios
   - Financial Health Score
   - Balance Sheet Analysis
   - Forecast
   - AI Financial Analysis
   - AI Recommendations
   - Financial Outlook

The module intentionally keeps accounting statements separate from
analytical/AI reporting.

ReportLab is used for PDF generation.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ============================================================================
# CONSTANTS
# ============================================================================

PRIMARY_BLUE = colors.HexColor("#2563EB")
DARK_BLUE = colors.HexColor("#1E3A8A")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
VERY_LIGHT_BLUE = colors.HexColor("#F8FAFC")

SUCCESS_GREEN = colors.HexColor("#047857")
LIGHT_GREEN = colors.HexColor("#ECFDF5")

WARNING_ORANGE = colors.HexColor("#B45309")
LIGHT_ORANGE = colors.HexColor("#FFFBEB")

DANGER_RED = colors.HexColor("#B91C1C")
LIGHT_RED = colors.HexColor("#FEF2F2")

TEXT_DARK = colors.HexColor("#172033")
TEXT_MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#CBD5E1")
WHITE = colors.white


DISCLAIMER = (
    "This report is an analytical aid and does not constitute professional "
    "accounting, tax, legal, credit, or investment advice."
)

# ReportLab's built-in Helvetica fonts do not contain the Indian Rupee
# glyph. ANGELIX therefore uses a Unicode-capable font when one is available
# and falls back to Helvetica + the text prefix "INR" when it is not.
PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
PDF_FONT_ITALIC = "Helvetica-Oblique"
PDF_FONT_BOLD_ITALIC = "Helvetica-BoldOblique"
PDF_FONT_FAMILY = "Helvetica"


def _register_pdf_fonts() -> None:
    """Register a Unicode-capable font for reliable currency rendering."""

    global PDF_FONT_REGULAR
    global PDF_FONT_BOLD
    global PDF_FONT_ITALIC
    global PDF_FONT_BOLD_ITALIC
    global PDF_FONT_FAMILY

    # Avoid re-registering fonts on every PDF generation call.
    if "AngelixUnicode" in pdfmetrics.getRegisteredFontNames():
        PDF_FONT_REGULAR = "AngelixUnicode"
        PDF_FONT_BOLD = "AngelixUnicode-Bold"
        PDF_FONT_ITALIC = "AngelixUnicode-Italic"
        PDF_FONT_BOLD_ITALIC = "AngelixUnicode-BoldItalic"
        PDF_FONT_FAMILY = "AngelixUnicode"
        return

    font_sets = [
        {
            "regular": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            "bold": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            "italic": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            "bold_italic": Path(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
            ),
        },
        {
            "regular": Path(r"C:\Windows\Fonts\segoeui.ttf"),
            "bold": Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            "italic": Path(r"C:\Windows\Fonts\segoeuii.ttf"),
            "bold_italic": Path(r"C:\Windows\Fonts\segoeuiz.ttf"),
        },
        {
            "regular": Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            "bold": Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            "italic": Path("/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
            "bold_italic": Path(
                "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"
            ),
        },
    ]

    for font_set in font_sets:
        if not all(path.exists() for path in font_set.values()):
            continue

        try:
            pdfmetrics.registerFont(
                TTFont("AngelixUnicode", str(font_set["regular"]))
            )
            pdfmetrics.registerFont(
                TTFont("AngelixUnicode-Bold", str(font_set["bold"]))
            )
            pdfmetrics.registerFont(
                TTFont("AngelixUnicode-Italic", str(font_set["italic"]))
            )
            pdfmetrics.registerFont(
                TTFont("AngelixUnicode-BoldItalic", str(font_set["bold_italic"]))
            )

            registerFontFamily(
                "AngelixUnicode",
                normal="AngelixUnicode",
                bold="AngelixUnicode-Bold",
                italic="AngelixUnicode-Italic",
                boldItalic="AngelixUnicode-BoldItalic",
            )

            PDF_FONT_REGULAR = "AngelixUnicode"
            PDF_FONT_BOLD = "AngelixUnicode-Bold"
            PDF_FONT_ITALIC = "AngelixUnicode-Italic"
            PDF_FONT_BOLD_ITALIC = "AngelixUnicode-BoldItalic"
            PDF_FONT_FAMILY = "AngelixUnicode"
            return

        except Exception:
            # Try the next installed font family.
            continue


# ============================================================================
# GENERAL HELPERS
# ============================================================================


def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convert common numeric values into float safely.
    """

    if value is None:
        return default

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, Decimal):
        return float(value)

    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, default: str = "N/A") -> str:
    """
    Convert arbitrary values into readable text.
    """

    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()
        return value if value else default

    return str(value)


def _format_currency(
    value: Any,
    currency_symbol: str = "₹",
    decimals: int = 2,
) -> str:
    """
    Format an amount using Indian-style currency notation.

    Example:
        225000 -> ₹2,25,000.00
        2000000 -> ₹20,00,000.00

    If the selected PDF font cannot safely represent the Rupee glyph,
    the caller can use the explicit "INR" fallback by leaving the
    registered-font detection to this function.
    """

    amount = _safe_float(value)

    try:
        negative = amount < 0
        absolute_amount = abs(amount)

        # Do NOT start from "{amount:,}" because the western commas would
        # otherwise be treated as characters during Indian regrouping.
        formatted = f"{absolute_amount:.{decimals}f}"
        integer_part, decimal_part = formatted.split(".")

        if len(integer_part) > 3:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            groups = []

            while len(remaining) > 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]

            if remaining:
                groups.insert(0, remaining)

            integer_part = ",".join(groups) + "," + last_three

        result = f"{integer_part}.{decimal_part}"

        # Helvetica cannot render ₹. Use INR instead of allowing a square
        # glyph to appear in environments where a Unicode font is absent.
        symbol = currency_symbol
        if symbol == "₹" and PDF_FONT_FAMILY == "Helvetica":
            symbol = "INR "

        if negative:
            return f"-{symbol}{result}"

        return f"{symbol}{result}"

    except Exception:
        fallback = f"{amount:.{decimals}f}"
        if currency_symbol == "₹" and PDF_FONT_FAMILY == "Helvetica":
            return f"INR {fallback}"
        return f"{currency_symbol}{fallback}"


def _format_percentage(value: Any) -> str:
    """
    Format a percentage value.
    """

    if value is None:
        return "N/A"

    return f"{_safe_float(value):.2f}%"


def _format_ratio(value: Any) -> str:
    """
    Format a financial ratio.
    """

    if value is None:
        return "N/A"

    return f"{_safe_float(value):.2f}x"


def _format_date(value: Any) -> str:
    """
    Format date-like values for PDF display.
    """

    if value is None:
        return "N/A"

    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")

    if isinstance(value, date):
        return value.strftime("%d %b %Y")

    try:
        return datetime.fromisoformat(
            str(value)
        ).strftime("%d %b %Y")
    except Exception:
        return str(value)


def _escape(value: Any) -> str:
    """
    Basic ReportLab-safe text conversion.

    ReportLab Paragraph interprets a small subset of HTML/XML.
    """

    text = _safe_text(value, "")

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _get_nested(
    data: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Safely retrieve nested dictionary values.
    """

    current = data

    for key in keys:

        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


# ============================================================================
# STYLES
# ============================================================================


def _build_styles():
    """
    Build a consistent ANGELIX PDF style system.
    """

    _register_pdf_fonts()
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="AngelixTitle",
            parent=styles["Title"],
            fontName=PDF_FONT_BOLD,
            fontSize=23,
            leading=27,
            textColor=DARK_BLUE,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="AngelixSubtitle",
            parent=styles["Normal"],
            fontName=PDF_FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=PRIMARY_BLUE,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportHeading",
            parent=styles["Heading2"],
            fontName=PDF_FONT_BOLD,
            fontSize=15,
            leading=19,
            textColor=DARK_BLUE,
            spaceBefore=12,
            spaceAfter=7,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubheading",
            parent=styles["Heading3"],
            fontName=PDF_FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=TEXT_DARK,
            spaceBefore=7,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontName=PDF_FONT_REGULAR,
            fontSize=8.7,
            leading=12,
            textColor=TEXT_DARK,
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSmall",
            parent=styles["BodyText"],
            fontName=PDF_FONT_REGULAR,
            fontSize=7.4,
            leading=10,
            textColor=TEXT_MUTED,
            spaceAfter=3,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSmallBold",
            parent=styles["BodyText"],
            fontName=PDF_FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=TEXT_DARK,
            spaceAfter=3,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportTableHeader",
            parent=styles["BodyText"],
            fontName=PDF_FONT_BOLD,
            fontSize=7.8,
            leading=10,
            textColor=DARK_BLUE,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportTableCell",
            parent=styles["BodyText"],
            fontName=PDF_FONT_REGULAR,
            fontSize=7.6,
            leading=10,
            textColor=TEXT_DARK,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportTableCellRight",
            parent=styles["BodyText"],
            fontName=PDF_FONT_REGULAR,
            fontSize=7.6,
            leading=10,
            textColor=TEXT_DARK,
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportMetricValue",
            parent=styles["BodyText"],
            fontName=PDF_FONT_BOLD,
            fontSize=9.2,
            leading=12,
            textColor=DARK_BLUE,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportDisclaimer",
            parent=styles["BodyText"],
            fontName=PDF_FONT_ITALIC,
            fontSize=7,
            leading=9,
            textColor=TEXT_MUTED,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportCallout",
            parent=styles["BodyText"],
            fontName=PDF_FONT_REGULAR,
            fontSize=8,
            leading=11,
            textColor=TEXT_DARK,
        )
    )

    return styles


# ============================================================================
# DOCUMENT / HEADER / FOOTER
# ============================================================================


def _build_document(path: Path):
    """
    Create the ReportLab document.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="ANGELIX Financial Report",
        author="ANGELIX",
        subject="AI-Powered Financial Intelligence",
    )


def _draw_header_footer(canvas, document):
    """
    Draw ANGELIX header/footer on every PDF page.
    """

    _register_pdf_fonts()
    canvas.saveState()

    width, height = A4

    # Top accent line.
    canvas.setFillColor(PRIMARY_BLUE)
    canvas.rect(
        0,
        height - 4,
        width,
        4,
        stroke=0,
        fill=1,
    )

    # Footer line.
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(
        document.leftMargin,
        12 * mm,
        width - document.rightMargin,
        12 * mm,
    )

    canvas.setFont(
        PDF_FONT_REGULAR,
        6.8,
    )

    canvas.setFillColor(TEXT_MUTED)

    canvas.drawString(
        document.leftMargin,
        8 * mm,
        "ANGELIX • AI-Powered Financial Intelligence",
    )

    canvas.drawRightString(
        width - document.rightMargin,
        8 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()


def _append_report_header(
    story: list,
    styles,
    title: str,
    organization: Any,
    period_start: Any,
    period_end: Any,
):
    """
    Add a professional report header.
    """

    organization_name = _safe_text(
        getattr(
            organization,
            "name",
            organization,
        ),
        "Organization",
    )

    story.append(
        Paragraph(
            "ANGELIX",
            styles["AngelixTitle"],
        )
    )

    story.append(
        Paragraph(
            _escape(title),
            styles["AngelixSubtitle"],
        )
    )

    metadata = [
        [
            Paragraph(
                "<b>Organization</b>",
                styles["ReportSmall"],
            ),
            Paragraph(
                _escape(organization_name),
                styles["ReportSmall"],
            ),
        ],
        [
            Paragraph(
                "<b>Reporting Period</b>",
                styles["ReportSmall"],
            ),
            Paragraph(
                f"{_escape(_format_date(period_start))} "
                f"to {_escape(_format_date(period_end))}",
                styles["ReportSmall"],
            ),
        ],
        [
            Paragraph(
                "<b>Generated</b>",
                styles["ReportSmall"],
            ),
            Paragraph(
                datetime.now().strftime(
                    "%d %b %Y, %I:%M %p"
                ),
                styles["ReportSmall"],
            ),
        ],
    ]

    metadata_table = Table(
        metadata,
        colWidths=[
            35 * mm,
            135 * mm,
        ],
    )

    metadata_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    LIGHT_BLUE,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.extend(
        [
            metadata_table,
            Spacer(1, 8),
        ]
    )


# ============================================================================
# TABLE HELPERS
# ============================================================================


def _styled_table(
    data: list[list[Any]],
    col_widths: list[float],
    *,
    header=True,
    header_background=LIGHT_BLUE,
    body_background=WHITE,
    grid=True,
    alignments=None,
):
    """
    Create a consistent report table.
    """

    table = Table(
        data,
        colWidths=col_widths,
        repeatRows=1 if header else 0,
        hAlign="LEFT",
    )

    commands = [
        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE",
        ),
        (
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            5,
        ),
        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            5,
        ),
        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            4,
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            4,
        ),
    ]

    if header:
        commands.extend(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    header_background,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    PDF_FONT_BOLD,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    DARK_BLUE,
                ),
            ]
        )

        body_start = 1

    else:
        body_start = 0

    if body_start <= len(data) - 1:
        commands.append(
            (
                "BACKGROUND",
                (0, body_start),
                (-1, -1),
                body_background,
            )
        )

    if grid:
        commands.append(
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                BORDER,
            )
        )

    if alignments:
        for column_index, alignment in enumerate(
            alignments
        ):
            commands.append(
                (
                    "ALIGN",
                    (column_index, 0),
                    (column_index, -1),
                    alignment,
                )
            )

    table.setStyle(
        TableStyle(commands)
    )

    return table


def _paragraph(
    text: Any,
    styles,
    style_name: str = "ReportBody",
):
    """
    Create a safely escaped Paragraph.
    """

    return Paragraph(
        _escape(text),
        styles[style_name],
    )


# ============================================================================
# FINANCIAL STATEMENTS HELPERS
# ============================================================================


def _extract_kpis(analytics: dict) -> dict:
    """
    Normalize KPI values from the analytics service.
    """

    kpis = analytics.get(
        "kpis",
        {},
    )

    # Some older analytics payloads stored values directly
    # at the root. Support both formats.
    return {
        "revenue": _safe_float(
            kpis.get(
                "total_revenue",
                analytics.get(
                    "revenue",
                    0,
                ),
            )
        ),
        "expenses": _safe_float(
            kpis.get(
                "total_expenses",
                analytics.get(
                    "expenses",
                    0,
                ),
            )
        ),
        "net_profit": _safe_float(
            kpis.get(
                "net_profit",
                analytics.get(
                    "net_profit",
                    0,
                ),
            )
        ),
        "profit_margin": kpis.get(
            "profit_margin",
            analytics.get(
                "profit_margin"
            ),
        ),
        "net_cash_flow": _safe_float(
            kpis.get(
                "net_cash_flow",
                analytics.get(
                    "net_cash_flow",
                    0,
                ),
            )
        ),
    }


def _extract_balance_sheet(
    health_score: dict | None,
) -> dict:
    """
    Extract the authoritative balance-sheet structure.

    The Financial Health / Recommendation services currently expose
    the approved balance-sheet line items through health_score.
    """

    if not isinstance(
        health_score,
        dict,
    ):
        return {
            "available": False,
            "line_items": [],
            "totals": {},
        }

    balance_sheet = health_score.get(
        "balance_sheet",
        {},
    )

    if not isinstance(
        balance_sheet,
        dict,
    ):
        return {
            "available": False,
            "line_items": [],
            "totals": {},
        }

    line_items = balance_sheet.get(
        "line_items",
        [],
    )

    totals = balance_sheet.get(
        "totals",
        {},
    )

    return {
        "available": bool(
            balance_sheet.get(
                "available",
                False,
            )
        ),
        "line_items": (
            line_items
            if isinstance(
                line_items,
                list,
            )
            else []
        ),
        "totals": (
            totals
            if isinstance(
                totals,
                dict,
            )
            else {}
        ),
        "accounting_equation_balanced": bool(
            balance_sheet.get(
                "accounting_equation_balanced",
                False,
            )
        ),
    }


def _group_line_items(
    line_items: list[dict],
) -> dict[str, list[dict]]:
    """
    Group balance-sheet line items by account type.
    """

    groups = {
        "asset": [],
        "liability": [],
        "equity": [],
    }

    for item in line_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        account_type = str(
            item.get(
                "account_type",
                "",
            )
        ).strip().lower()

        if account_type in groups:
            groups[account_type].append(
                item
            )

    return groups


def _statement_line_item_rows(
    items: list[dict],
    styles,
):
    """
    Convert financial line items into table rows.
    """

    rows = []

    for item in items:

        name = item.get(
            "line_item_name",
            item.get(
                "normalized_name",
                "Unnamed account",
            ),
        )

        amount = item.get(
            "amount",
            0,
        )

        rows.append(
            [
                Paragraph(
                    _escape(name),
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _format_currency(amount),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ]
        )

    return rows


def _append_financial_statement_section(
    story: list,
    styles,
    title: str,
    subtitle: str,
    rows: list[list[Any]],
    total_label: str,
    total_amount: Any,
    *,
    total_color=LIGHT_BLUE,
):
    """
    Append a standard statement section.
    """

    story.append(
        Paragraph(
            _escape(title),
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            _escape(subtitle),
            styles["ReportSmall"],
        )
    )

    table_data = [
        [
            Paragraph(
                "Description",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Amount",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ]
    ]

    table_data.extend(rows)

    table_data.append(
        [
            Paragraph(
                f"<b>{_escape(total_label)}</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(total_amount)}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    table = _styled_table(
        table_data,
        [
            120 * mm,
            50 * mm,
        ],
        alignments=[
            "LEFT",
            "RIGHT",
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, -1),
                    (-1, -1),
                    total_color,
                ),
                (
                    "LINEABOVE",
                    (0, -1),
                    (-1, -1),
                    0.8,
                    PRIMARY_BLUE,
                ),
            ]
        )
    )

    story.extend(
        [
            table,
            Spacer(1, 6),
        ]
    )


# ============================================================================
# FINANCIAL STATEMENTS REPORT
# ============================================================================


def generate_financial_statements_pdf(
    path,
    organization,
    period_start,
    period_end,
    analytics,
    statements=None,
    health_score=None,
):
    """
    Generate the dedicated Financial Statements Report.

    This report contains accounting statements only. Analytical content
    such as AI recommendations, health-score methodology, forecasts and
    charts belongs in the Financial Analysis Report.

    Parameters
    ----------
    path:
        Destination PDF path.

    organization:
        ANGELIX Organization model/object.

    period_start / period_end:
        Reporting period.

    analytics:
        AnalyticsService output.

    statements:
        Optional statement data. The function supports both structured
        statement dictionaries and the current health-score balance-sheet
        structure.

    health_score:
        Current Financial Health service result. Used only to obtain the
        authoritative balance-sheet line items when available.
    """

    styles = _build_styles()

    path = Path(path)

    document = _build_document(
        path
    )

    story: list = []

    _append_report_header(
        story,
        styles,
        "Financial Statements Report",
        organization,
        period_start,
        period_end,
    )

    kpis = _extract_kpis(
        analytics or {}
    )

    # ------------------------------------------------------------------
    # PROFIT & LOSS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "1. Profit & Loss Statement",
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            "Statement of revenue, expenses and resulting profit or loss "
            "for the selected reporting period.",
            styles["ReportSmall"],
        )
    )

    revenue_breakdown = (
        (analytics or {}).get(
            "revenue_breakdown",
            [],
        )
    )

    expense_breakdown = (
        (analytics or {}).get(
            "expense_breakdown",
            [],
        )
    )

    pnl_rows: list[list[Any]] = []

    if isinstance(
        revenue_breakdown,
        list,
    ):

        for item in revenue_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            category = item.get(
                "category",
                "Revenue",
            )

            amount = item.get(
                "amount",
                0,
            )

            pnl_rows.append(
                [
                    Paragraph(
                        _escape(
                            f"Revenue — {category}"
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            amount
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

    if not pnl_rows:
        pnl_rows.append(
            [
                Paragraph(
                    "Total Revenue",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _format_currency(
                        kpis["revenue"]
                    ),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ]
        )

    pnl_rows.append(
        [
            Paragraph(
                "<b>Total Revenue</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['revenue'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    if isinstance(
        expense_breakdown,
        list,
    ):

        for item in expense_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            category = item.get(
                "category",
                "Expense",
            )

            amount = item.get(
                "amount",
                0,
            )

            pnl_rows.append(
                [
                    Paragraph(
                        _escape(
                            f"Expense — {category}"
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            amount
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

    pnl_rows.append(
        [
            Paragraph(
                "<b>Total Expenses</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['expenses'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    pnl_rows.append(
        [
            Paragraph(
                "<b>Net Profit / (Loss)</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['net_profit'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    pnl_rows.append(
        [
            Paragraph(
                "<b>Profit Margin</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_percentage(kpis['profit_margin'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    pnl_table = _styled_table(
        [
            [
                Paragraph(
                    "Description",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
                Paragraph(
                    "Amount",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
            ]
        ]
        + pnl_rows,
        [
            120 * mm,
            50 * mm,
        ],
        alignments=[
            "LEFT",
            "RIGHT",
        ],
    )

    pnl_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, -3),
                    (-1, -1),
                    LIGHT_GREEN,
                ),
                (
                    "LINEABOVE",
                    (0, -3),
                    (-1, -3),
                    0.8,
                    SUCCESS_GREEN,
                ),
            ]
        )
    )

    story.extend(
        [
            pnl_table,
            Spacer(1, 8),
        ]
    )

    # ------------------------------------------------------------------
    # INCOME & EXPENDITURE
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "2. Income & Expenditure Statement",
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            "A separate presentation of income and expenditure derived "
            "from the structured financial data available in ANGELIX.",
            styles["ReportSmall"],
        )
    )

    income_rows = []

    if isinstance(
        revenue_breakdown,
        list,
    ):

        for item in revenue_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            income_rows.append(
                [
                    Paragraph(
                        _escape(
                            item.get(
                                "category",
                                "Income",
                            )
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            item.get(
                                "amount",
                                0,
                            )
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

    if not income_rows:
        income_rows.append(
            [
                Paragraph(
                    "Total Income",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _format_currency(
                        kpis["revenue"]
                    ),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ]
        )

    income_rows.append(
        [
            Paragraph(
                "<b>Total Income</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['revenue'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    if isinstance(
        expense_breakdown,
        list,
    ):

        for item in expense_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            income_rows.append(
                [
                    Paragraph(
                        _escape(
                            item.get(
                                "category",
                                "Expenditure",
                            )
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            item.get(
                                "amount",
                                0,
                            )
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

    income_rows.append(
        [
            Paragraph(
                "<b>Total Expenditure</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['expenses'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    income_rows.append(
        [
            Paragraph(
                "<b>Surplus / (Deficit)</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(kpis['net_profit'])}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ]
    )

    income_table = _styled_table(
        [
            [
                Paragraph(
                    "Income / Expenditure",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
                Paragraph(
                    "Amount",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
            ]
        ]
        + income_rows,
        [
            120 * mm,
            50 * mm,
        ],
        alignments=[
            "LEFT",
            "RIGHT",
        ],
    )

    income_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, -2),
                    (-1, -1),
                    LIGHT_GREEN,
                ),
            ]
        )
    )

    story.extend(
        [
            income_table,
            Spacer(1, 8),
        ]
    )

    # ------------------------------------------------------------------
    # BALANCE SHEET
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "3. Balance Sheet",
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            "Balance-sheet line items approved and stored in ANGELIX.",
            styles["ReportSmall"],
        )
    )

    balance_sheet = _extract_balance_sheet(
        health_score
    )

    groups = _group_line_items(
        balance_sheet["line_items"]
    )

    balance_rows = [
        [
            Paragraph(
                "Account",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Type",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Amount",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ]
    ]

    section_definitions = [
        (
            "Assets",
            "asset",
        ),
        (
            "Liabilities",
            "liability",
        ),
        (
            "Equity",
            "equity",
        ),
    ]

    for section_name, account_type in section_definitions:

        balance_rows.append(
            [
                Paragraph(
                    f"<b>{section_name}</b>",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                "",
                "",
            ]
        )

        for item in groups.get(
            account_type,
            [],
        ):

            balance_rows.append(
                [
                    Paragraph(
                        _escape(
                            item.get(
                                "line_item_name",
                                "Unnamed account",
                            )
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _escape(
                            item.get(
                                "account_type",
                                account_type,
                            ).title()
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            item.get(
                                "amount",
                                0,
                            )
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

        total_key = {
            "asset": "assets",
            "liability": "liabilities",
            "equity": "equity",
        }[account_type]

        balance_rows.append(
            [
                Paragraph(
                    f"<b>Total {section_name}</b>",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                "",
                Paragraph(
                    f"<b>{_format_currency(balance_sheet['totals'].get(total_key, 0))}</b>",
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ]
        )

    balance_table = _styled_table(
        balance_rows,
        [
            82 * mm,
            35 * mm,
            53 * mm,
        ],
        alignments=[
            "LEFT",
            "LEFT",
            "RIGHT",
        ],
    )

    # Section rows.
    current_row = 1

    for section_name, account_type in section_definitions:

        balance_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, current_row),
                        (-1, current_row),
                        LIGHT_BLUE,
                    ),
                ]
            )
        )

        current_row += (
            1
            + len(
                groups.get(
                    account_type,
                    [],
                )
            )
            + 1
        )

    # Total rows receive a subtle background.
    current_row = 1

    for _, account_type in section_definitions:

        current_row += (
            1
            + len(
                groups.get(
                    account_type,
                    [],
                )
            )
        )

        balance_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, current_row),
                        (-1, current_row),
                        VERY_LIGHT_BLUE,
                    ),
                ]
            )
        )

        current_row += 1

    story.extend(
        [
            balance_table,
            Spacer(1, 6),
        ]
    )

    # Accounting equation.
    totals = balance_sheet[
        "totals"
    ]

    assets = _safe_float(
        totals.get(
            "assets",
            0,
        )
    )

    liabilities = _safe_float(
        totals.get(
            "liabilities",
            0,
        )
    )

    equity = _safe_float(
        totals.get(
            "equity",
            0,
        )
    )

    equation_balanced = balance_sheet[
        "accounting_equation_balanced"
    ]

    equation_text = (
        f"Assets {_format_currency(assets)} "
        f"= Liabilities {_format_currency(liabilities)} "
        f"+ Equity {_format_currency(equity)}"
    )

    equation_table = Table(
        [
            [
                Paragraph(
                    "<b>Accounting Equation</b>",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _escape(
                        equation_text
                    ),
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    "<b>Balanced</b>"
                    if equation_balanced
                    else "<b>Not Balanced</b>",
                    styles[
                        "ReportTableCell"
                    ],
                ),
            ]
        ],
        colWidths=[
            38 * mm,
            105 * mm,
            27 * mm,
        ],
    )

    equation_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT_GREEN
                    if equation_balanced
                    else LIGHT_RED,
                ),
                (
                    "TEXTCOLOR",
                    (-1, 0),
                    (-1, 0),
                    SUCCESS_GREEN
                    if equation_balanced
                    else DANGER_RED,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.extend(
        [
            equation_table,
            Spacer(1, 8),
        ]
    )

    # ------------------------------------------------------------------
    # CASH FLOW SUMMARY
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "4. Cash Flow Summary",
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            "Transaction-based cash-flow summary for the selected period. "
            "This section is presented as a summary because ANGELIX currently "
            "uses transaction data as the available cash-flow proxy.",
            styles["ReportSmall"],
        )
    )

    net_cash_flow = _safe_float(
        kpis.get(
            "net_cash_flow",
            0,
        )
    )

    cash_flow_rows = [
        [
            Paragraph(
                "Cash Flow Metric",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Amount",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ],
        [
            Paragraph(
                "Cash Inflows",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    max(
                        kpis["revenue"],
                        0,
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Cash Outflows",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    max(
                        kpis["expenses"],
                        0,
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "<b>Net Cash Flow</b>",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                f"<b>{_format_currency(net_cash_flow)}</b>",
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
    ]

    cash_table = _styled_table(
        cash_flow_rows,
        [
            120 * mm,
            50 * mm,
        ],
        alignments=[
            "LEFT",
            "RIGHT",
        ],
    )

    cash_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, -1),
                    (-1, -1),
                    LIGHT_BLUE,
                ),
            ]
        )
    )

    story.extend(
        [
            cash_table,
            Spacer(1, 8),
            Paragraph(
                "Note: A dedicated cash-flow classification model can be "
                "introduced as an advanced enhancement when transaction "
                "categories provide sufficient cash-flow classification.",
                styles["ReportSmall"],
            ),
        ]
    )

    # ------------------------------------------------------------------
    # DISCLAIMER
    # ------------------------------------------------------------------

    story.extend(
        [
            Spacer(1, 8),
            Paragraph(
                _escape(DISCLAIMER),
                styles["ReportDisclaimer"],
            ),
        ]
    )

    document.build(
        story,
        onFirstPage=_draw_header_footer,
        onLaterPages=_draw_header_footer,
    )

    return path


# ============================================================================
# FINANCIAL ANALYSIS REPORT
# ============================================================================


def _append_kpi_table(
    story: list,
    styles,
    analytics: dict,
):
    """
    Add a clean KPI summary.
    """

    kpis = _extract_kpis(
        analytics or {}
    )

    data = [
        [
            Paragraph(
                "Metric",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Value",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ],
        [
            Paragraph(
                "Revenue",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    kpis["revenue"]
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Expenses",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    kpis["expenses"]
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Net Profit",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    kpis["net_profit"]
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Profit Margin",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_percentage(
                    kpis["profit_margin"]
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Transactions",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                str(
                    int(
                        _safe_float(
                            kpis.get(
                                "total_transactions",
                                analytics.get(
                                    "kpis",
                                    {},
                                ).get(
                                    "total_transactions",
                                    0,
                                ),
                            )
                        )
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
    ]

    table = _styled_table(
        data,
        [
            120 * mm,
            50 * mm,
        ],
        alignments=[
            "LEFT",
            "RIGHT",
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, 4),
                    WHITE,
                ),
                (
                    "BACKGROUND",
                    (0, 3),
                    (-1, 3),
                    LIGHT_GREEN,
                ),
            ]
        )
    )

    story.append(
        table
    )


def _append_ratio_table(
    story: list,
    styles,
    analytics: dict,
):
    """
    Add financial ratio analysis.
    """

    ratios = (
        analytics or {}
    ).get(
        "ratios",
        {},
    )

    rows = [
        [
            Paragraph(
                "Ratio",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Value",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Interpretation",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ],
        [
            Paragraph(
                "Current Ratio",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_ratio(
                    ratios.get(
                        "current_ratio"
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
            Paragraph(
                "Short-term asset coverage of current liabilities.",
                styles[
                    "ReportTableCell"
                ],
            ),
        ],
        [
            Paragraph(
                "Debt-to-Equity",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_ratio(
                    ratios.get(
                        "debt_to_equity"
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
            Paragraph(
                "Relationship between liabilities and equity.",
                styles[
                    "ReportTableCell"
                ],
            ),
        ],
        [
            Paragraph(
                "Gross Profit Margin",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_percentage(
                    ratios.get(
                        "gross_profit_margin"
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
            Paragraph(
                "Gross profitability based on available analytics.",
                styles[
                    "ReportTableCell"
                ],
            ),
        ],
        [
            Paragraph(
                "Net Profit Margin",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_percentage(
                    ratios.get(
                        "net_profit_margin"
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
            Paragraph(
                "Net profit generated from reported revenue.",
                styles[
                    "ReportTableCell"
                ],
            ),
        ],
    ]

    story.append(
        _styled_table(
            rows,
            [
                45 * mm,
                30 * mm,
                95 * mm,
            ],
            alignments=[
                "LEFT",
                "RIGHT",
                "LEFT",
            ],
        )
    )


def _append_health_score(
    story: list,
    styles,
    health_score: dict | None,
):
    """
    Render the Financial Health Score as a user-facing summary.

    Internal Python dictionaries are never dumped directly into the PDF.
    """

    if not isinstance(
        health_score,
        dict,
    ):
        return

    score = _safe_float(
        health_score.get(
            "score",
            0,
        )
    )

    max_score = _safe_float(
        health_score.get(
            "max_score",
            100,
        )
    )

    level = _safe_text(
        health_score.get(
            "level",
            health_score.get(
                "health_level",
                "N/A",
            ),
        )
    )

    score_table = Table(
        [
            [
                Paragraph(
                    "<b>Financial Health Score</b>",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    f"<b>{score:.0f} / {max_score:.0f}</b>",
                    styles[
                        "ReportMetricValue"
                    ],
                ),
                Paragraph(
                    _escape(level),
                    styles[
                        "ReportTableCell"
                    ],
                ),
            ]
        ],
        colWidths=[
            70 * mm,
            45 * mm,
            55 * mm,
        ],
    )

    score_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT_BLUE,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    PRIMARY_BLUE,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    story.extend(
        [
            score_table,
            Spacer(1, 6),
        ]
    )

    components = health_score.get(
        "components",
        {},
    )

    if not isinstance(
        components,
        dict,
    ):
        return

    rows = [
        [
            Paragraph(
                "Component",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Score",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Status",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Reason",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ]
    ]

    for name, component in components.items():

        if not isinstance(
            component,
            dict,
        ):
            continue

        component_score = _safe_float(
            component.get(
                "score",
                0,
            )
        )

        component_max = _safe_float(
            component.get(
                "max_score",
                0,
            )
        )

        status = _safe_text(
            component.get(
                "status",
                "N/A",
            )
        )

        reason = _safe_text(
            component.get(
                "reason",
                "",
            ),
            "",
        )

        display_name = str(
            name
        ).replace(
            "_",
            " ",
        ).title()

        rows.append(
            [
                Paragraph(
                    _escape(
                        display_name
                    ),
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    f"{component_score:.1f} / "
                    f"{component_max:.1f}",
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
                Paragraph(
                    _escape(status.title()),
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _escape(reason),
                    styles[
                        "ReportTableCell"
                    ],
                ),
            ]
        )

    if len(rows) > 1:

        story.append(
            _styled_table(
                rows,
                [
                    40 * mm,
                    25 * mm,
                    25 * mm,
                    80 * mm,
                ],
                alignments=[
                    "LEFT",
                    "RIGHT",
                    "LEFT",
                    "LEFT",
                ],
            )
        )


def _append_balance_sheet_analysis(
    story: list,
    styles,
    health_score: dict | None,
):
    """
    Add a concise balance-sheet analysis section.
    """

    balance_sheet = _extract_balance_sheet(
        health_score
    )

    if not balance_sheet["available"]:
        story.append(
            Paragraph(
                "Balance-sheet analysis is not available for the selected period.",
                styles["ReportBody"],
            )
        )

        return

    totals = balance_sheet[
        "totals"
    ]

    assets = _safe_float(
        totals.get(
            "assets",
            0,
        )
    )

    liabilities = _safe_float(
        totals.get(
            "liabilities",
            0,
        )
    )

    equity = _safe_float(
        totals.get(
            "equity",
            0,
        )
    )

    lte = _safe_float(
        totals.get(
            "liabilities_plus_equity",
            liabilities + equity,
        )
    )

    difference = _safe_float(
        totals.get(
            "accounting_difference",
            assets - lte,
        )
    )

    rows = [
        [
            Paragraph(
                "Metric",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Value",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ],
        [
            Paragraph(
                "Total Assets",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    assets
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Total Liabilities",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    liabilities
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Total Equity",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    equity
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Liabilities + Equity",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    lte
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Accounting Difference",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    difference
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
    ]

    story.append(
        _styled_table(
            rows,
            [
                120 * mm,
                50 * mm,
            ],
            alignments=[
                "LEFT",
                "RIGHT",
            ],
        )
    )

    story.append(
        Spacer(1, 4)
    )

    if balance_sheet[
        "accounting_equation_balanced"
    ]:

        message = (
            "The balance sheet satisfies the accounting equation: "
            "Assets = Liabilities + Equity."
        )

        story.append(
            Paragraph(
                _escape(message),
                styles[
                    "ReportCallout"
                ],
            )
        )


def _normalize_monthly_trend(analytics: dict) -> list[dict[str, Any]]:
    """Return clean monthly trend rows for PDF visualization."""

    monthly_trend = (analytics or {}).get(
        "monthly_trend",
        [],
    )

    if not isinstance(monthly_trend, list):
        return []

    normalized = []

    for item in monthly_trend:
        if not isinstance(item, dict):
            continue

        period = _safe_text(
            item.get("period", ""),
            "",
        )

        if not period:
            continue

        normalized.append(
            {
                "period": period,
                "revenue": _safe_float(
                    item.get("revenue", 0)
                ),
                "expenses": _safe_float(
                    item.get("expenses", 0)
                ),
                "net_profit": _safe_float(
                    item.get("net_profit", 0)
                ),
            }
        )

    return normalized


def _draw_trend_chart(
    trend: list[dict[str, Any]],
    width: float = 500,
    height: float = 220,
) -> Drawing:
    """
    Draw a compact revenue-vs-expense/net-profit chart.

    The chart is intentionally implemented with ReportLab primitives so the
    generated PDF is self-contained and does not depend on browser Chart.js.
    """

    drawing = Drawing(width, height)

    if not trend:
        drawing.add(
            String(
                width / 2,
                height / 2,
                "No monthly trend data available",
                textAnchor="middle",
                fontName=PDF_FONT_REGULAR,
                fontSize=9,
                fillColor=TEXT_MUTED,
            )
        )
        return drawing

    left = 48
    right = 18
    bottom = 38
    top = 28

    chart_width = width - left - right
    chart_height = height - bottom - top

    maximum = max(
        max(row["revenue"] for row in trend),
        max(row["expenses"] for row in trend),
        max(row["net_profit"] for row in trend),
        1.0,
    )

    # Round the maximum upward to produce readable gridlines.
    magnitude = 10 ** max(0, len(str(int(maximum))) - 1)
    rounded_max = (
        ((maximum / magnitude) // 1) + 1
    ) * magnitude

    # Background.
    drawing.add(
        Rect(
            left,
            bottom,
            chart_width,
            chart_height,
            fillColor=VERY_LIGHT_BLUE,
            strokeColor=BORDER,
            strokeWidth=0.5,
        )
    )

    # Horizontal gridlines and labels.
    grid_count = 4

    for index in range(grid_count + 1):
        ratio = index / grid_count
        y = bottom + chart_height * ratio
        value = rounded_max * ratio

        drawing.add(
            Line(
                left,
                y,
                left + chart_width,
                y,
                strokeColor=colors.HexColor("#E2E8F0"),
                strokeWidth=0.5,
            )
        )

        drawing.add(
            String(
                left - 6,
                y - 3,
                _format_compact_amount(value),
                textAnchor="end",
                fontName=PDF_FONT_REGULAR,
                fontSize=6.5,
                fillColor=TEXT_MUTED,
            )
        )

    # Axes.
    drawing.add(
        Line(
            left,
            bottom,
            left,
            bottom + chart_height,
            strokeColor=TEXT_MUTED,
            strokeWidth=0.7,
        )
    )

    drawing.add(
        Line(
            left,
            bottom,
            left + chart_width,
            bottom,
            strokeColor=TEXT_MUTED,
            strokeWidth=0.7,
        )
    )

    # Bar layout.
    group_width = chart_width / max(len(trend), 1)
    bar_width = min(13, group_width * 0.22)
    bar_gap = 3

    revenue_color = PRIMARY_BLUE
    expense_color = colors.HexColor("#F59E0B")

    # Net-profit line.
    points = []

    for index, row in enumerate(trend):
        center_x = left + group_width * (index + 0.5)

        revenue_height = (
            row["revenue"] / rounded_max * chart_height
        )
        expense_height = (
            row["expenses"] / rounded_max * chart_height
        )

        drawing.add(
            Rect(
                center_x - bar_width - bar_gap / 2,
                bottom,
                bar_width,
                max(0.5, revenue_height),
                fillColor=revenue_color,
                strokeColor=None,
            )
        )

        drawing.add(
            Rect(
                center_x + bar_gap / 2,
                bottom,
                bar_width,
                max(0.5, expense_height),
                fillColor=expense_color,
                strokeColor=None,
            )
        )

        net_y = (
            bottom
            + row["net_profit"] / rounded_max * chart_height
        )

        points.append((center_x, net_y))

        label = row["period"]

        if len(label) > 10:
            label = label[:10]

        drawing.add(
            String(
                center_x,
                bottom - 16,
                label,
                textAnchor="middle",
                fontName=PDF_FONT_REGULAR,
                fontSize=6.5,
                fillColor=TEXT_MUTED,
            )
        )

    # Connect net-profit points.
    for index in range(1, len(points)):
        x1, y1 = points[index - 1]
        x2, y2 = points[index]

        drawing.add(
            Line(
                x1,
                y1,
                x2,
                y2,
                strokeColor=SUCCESS_GREEN,
                strokeWidth=1.8,
            )
        )

    for x, y in points:
        drawing.add(
            Rect(
                x - 2.2,
                y - 2.2,
                4.4,
                4.4,
                fillColor=SUCCESS_GREEN,
                strokeColor=WHITE,
                strokeWidth=0.7,
            )
        )

    # Legend.
    legend_y = height - 12

    legend = [
        ("Revenue", revenue_color),
        ("Expenses", expense_color),
        ("Net Profit", SUCCESS_GREEN),
    ]

    legend_x = left

    for label, color in legend:
        drawing.add(
            Rect(
                legend_x,
                legend_y - 4,
                8,
                8,
                fillColor=color,
                strokeColor=None,
            )
        )

        drawing.add(
            String(
                legend_x + 12,
                legend_y - 2,
                label,
                fontName=PDF_FONT_REGULAR,
                fontSize=7,
                fillColor=TEXT_DARK,
            )
        )

        legend_x += 78

    return drawing


def _draw_breakdown_chart(
    items: list[dict[str, Any]],
    title: str,
    width: float = 500,
    height: float = 205,
) -> Drawing:
    """Draw a horizontal category breakdown chart."""

    drawing = Drawing(width, height)

    cleaned = []

    for item in items:
        if not isinstance(item, dict):
            continue

        category = _safe_text(
            item.get("category", ""),
            "",
        )

        if not category:
            continue

        cleaned.append(
            {
                "category": category,
                "amount": _safe_float(
                    item.get("amount", 0)
                ),
            }
        )

    cleaned = sorted(
        cleaned,
        key=lambda row: abs(row["amount"]),
        reverse=True,
    )[:6]

    if not cleaned:
        drawing.add(
            String(
                width / 2,
                height / 2,
                f"No {title.lower()} data available",
                textAnchor="middle",
                fontName=PDF_FONT_REGULAR,
                fontSize=9,
                fillColor=TEXT_MUTED,
            )
        )
        return drawing

    left = 145
    right = 58
    top = 25
    row_height = 27
    bar_height = 12

    maximum = max(
        abs(row["amount"]) for row in cleaned
    ) or 1.0

    drawing.add(
        String(
            0,
            height - 9,
            title,
            fontName=PDF_FONT_BOLD,
            fontSize=8,
            fillColor=DARK_BLUE,
        )
    )

    for index, row in enumerate(cleaned):
        y = height - top - index * row_height

        label = row["category"]

        if len(label) > 24:
            label = label[:21] + "..."

        drawing.add(
            String(
                left - 8,
                y - 4,
                label,
                textAnchor="end",
                fontName=PDF_FONT_REGULAR,
                fontSize=7,
                fillColor=TEXT_DARK,
            )
        )

        drawing.add(
            Rect(
                left,
                y - bar_height / 2,
                width - left - right,
                bar_height,
                fillColor=colors.HexColor("#E2E8F0"),
                strokeColor=None,
            )
        )

        fill_width = (
            abs(row["amount"]) / maximum
            * (width - left - right)
        )

        drawing.add(
            Rect(
                left,
                y - bar_height / 2,
                max(1, fill_width),
                bar_height,
                fillColor=PRIMARY_BLUE,
                strokeColor=None,
            )
        )

        drawing.add(
            String(
                width - right + 5,
                y - 4,
                _format_currency(row["amount"]),
                fontName=PDF_FONT_REGULAR,
                fontSize=6.5,
                fillColor=TEXT_DARK,
            )
        )

    return drawing


def _format_compact_amount(value: float) -> str:
    """Format chart-axis amounts compactly without losing readability."""

    value = _safe_float(value)

    absolute = abs(value)

    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    if absolute >= 1000:
        return f"{value / 1000:.0f}K"

    return f"{value:.0f}"


def _append_trend_visualizations(
    story: list,
    styles,
    analytics: dict,
):
    """
    Render actual PDF charts for monthly financial performance.

    The web dashboard continues to use Chart.js; these are independent,
    print-friendly ReportLab charts for the downloadable PDF.
    """

    trend = _normalize_monthly_trend(
        analytics
    )

    if not trend:
        story.append(
            Paragraph(
                "No monthly trend data is available for the selected period.",
                styles["ReportSmall"],
            )
        )
        return

    story.append(
        Paragraph(
            "Revenue vs Expenses and Net Profit",
            styles["ReportBody"],
        )
    )

    story.append(
        _draw_trend_chart(
            trend
        )
    )

    story.append(
        Spacer(1, 8)
    )

    revenue_breakdown = (
        analytics or {}
    ).get(
        "revenue_breakdown",
        [],
    )

    expense_breakdown = (
        analytics or {}
    ).get(
        "expense_breakdown",
        [],
    )

    if revenue_breakdown or expense_breakdown:

        story.append(
            _draw_breakdown_chart(
                expense_breakdown,
                "Expense Category Breakdown",
            )
        )

        story.append(
            Spacer(1, 6)
        )

        story.append(
            _draw_breakdown_chart(
                revenue_breakdown,
                "Revenue Category Breakdown",
            )
        )


def _append_forecast(
    story: list,
    styles,
    analytics: dict,
):
    """
    Render forecast values.
    """

    forecast = (
        analytics or {}
    ).get(
        "forecast",
        {},
    )

    if not isinstance(
        forecast,
        dict
    ) or not forecast.get(
        "available",
        False,
    ):
        return

    method = _safe_text(
        forecast.get(
            "method",
            "N/A",
        )
    )

    rows = [
        [
            Paragraph(
                "Forecast Metric",
                styles[
                    "ReportTableHeader"
                ],
            ),
            Paragraph(
                "Projected Value",
                styles[
                    "ReportTableHeader"
                ],
            ),
        ],
        [
            Paragraph(
                "Next Period Revenue",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    forecast.get(
                        "next_month_revenue",
                        0,
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Next Period Expenses",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    forecast.get(
                        "next_month_expenses",
                        0,
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
        [
            Paragraph(
                "Next Period Profit",
                styles[
                    "ReportTableCell"
                ],
            ),
            Paragraph(
                _format_currency(
                    forecast.get(
                        "next_month_profit",
                        0,
                    )
                ),
                styles[
                    "ReportTableCellRight"
                ],
            ),
        ],
    ]

    story.append(
        _styled_table(
            rows,
            [
                120 * mm,
                50 * mm,
            ],
            alignments=[
                "LEFT",
                "RIGHT",
            ],
        )
    )

    story.append(
        Paragraph(
            f"Forecast method: {_escape(method)}",
            styles["ReportSmall"],
        )
    )


def _append_ai_analysis(
    story: list,
    styles,
    ai_observations: dict | None,
):
    """
    Render AI observations as structured content.

    The previous implementation printed raw Python dictionaries.
    This function intentionally renders each field separately.
    """

    if not isinstance(
        ai_observations,
        dict,
    ):
        return

    summary = ai_observations.get(
        "summary",
    )

    if summary:
        story.append(
            Paragraph(
                "AI Financial Analysis",
                styles["ReportHeading"],
            )
        )

        story.append(
            Paragraph(
                _escape(summary),
                styles["ReportBody"],
            )
        )

    insights = ai_observations.get(
        "insights",
        ai_observations.get(
            "recommendations",
            [],
        ),
    )

    if isinstance(
        insights,
        list,
    ) and insights:

        for index, insight in enumerate(
            insights,
            start=1,
        ):

            if not isinstance(
                insight,
                dict,
            ):
                continue

            title = _safe_text(
                insight.get(
                    "title",
                    f"Insight {index}",
                )
            )

            area = _safe_text(
                insight.get(
                    "area",
                    "",
                ),
                "",
            )

            observation = _safe_text(
                insight.get(
                    "observation",
                    insight.get(
                        "description",
                        "",
                    ),
                ),
                "",
            )

            evidence = _safe_text(
                insight.get(
                    "evidence",
                    "",
                ),
                "",
            )

            implication = _safe_text(
                insight.get(
                    "implication",
                    "",
                ),
                "",
            )

            block = [
                [
                    Paragraph(
                        f"<b>{_escape(title)}</b>",
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _escape(area),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                ]
            ]

            table = Table(
                block,
                colWidths=[
                    45 * mm,
                    125 * mm,
                ],
            )

            table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (0, 0),
                            LIGHT_BLUE,
                        ),
                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.4,
                            BORDER,
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "TOP",
                        ),
                        (
                            "LEFTPADDING",
                            (0, 0),
                            (-1, -1),
                            5,
                        ),
                        (
                            "RIGHTPADDING",
                            (0, 0),
                            (-1, -1),
                            5,
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            5,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            5,
                        ),
                    ]
                )
            )

            story.extend(
                [
                    table,
                    Spacer(1, 2),
                ]
            )

            if observation:
                story.append(
                    Paragraph(
                        f"<b>Observation:</b> "
                        f"{_escape(observation)}",
                        styles[
                            "ReportSmall"
                        ],
                    )
                )

            if evidence:
                story.append(
                    Paragraph(
                        f"<b>Evidence:</b> "
                        f"{_escape(evidence)}",
                        styles[
                            "ReportSmall"
                        ],
                    )
                )

            if implication:
                story.append(
                    Paragraph(
                        f"<b>Implication:</b> "
                        f"{_escape(implication)}",
                        styles[
                            "ReportSmall"
                        ],
                    )
                )

    outlook = ai_observations.get(
        "outlook",
    )

    if outlook:
        story.append(
            Paragraph(
                "<b>Financial Outlook</b>",
                styles["ReportSubheading"],
            )
        )

        story.append(
            Paragraph(
                _escape(outlook),
                styles["ReportBody"],
            )
        )


def _append_ai_recommendations(
    story: list,
    styles,
    ai_recommendations: dict | list | None,
):
    """
    Render AI recommendations in a structured format.
    """

    if not ai_recommendations:
        return

    recommendations = ai_recommendations

    if isinstance(
        ai_recommendations,
        dict,
    ):
        recommendations = (
            ai_recommendations.get(
                "recommendations",
                [],
            )
        )

    if not isinstance(
        recommendations,
        list,
    ):
        return

    story.append(
        Paragraph(
            "AI Recommendations",
            styles["ReportHeading"],
        )
    )

    for index, recommendation in enumerate(
        recommendations,
        start=1,
    ):

        if not isinstance(
            recommendation,
            dict,
        ):
            continue

        title = _safe_text(
            recommendation.get(
                "title",
                f"Recommendation {index}",
            )
        )

        priority = _safe_text(
            recommendation.get(
                "priority",
                recommendation.get(
                    "severity",
                    "",
                ),
            ),
            "",
        )

        area = _safe_text(
            recommendation.get(
                "area",
                "",
            ),
            "",
        )

        action = _safe_text(
            recommendation.get(
                "action",
                recommendation.get(
                    "recommendation",
                    recommendation.get(
                        "description",
                        "",
                    ),
                ),
            ),
            "",
        )

        rationale = _safe_text(
            recommendation.get(
                "rationale",
                recommendation.get(
                    "reason",
                    "",
                ),
            ),
            "",
        )

        header = (
            f"{index}. {_escape(title)}"
        )

        if priority:
            header += (
                f" — {_escape(priority.upper())}"
            )

        if area:
            header += (
                f" • {_escape(area)}"
            )

        story.append(
            Paragraph(
                f"<b>{header}</b>",
                styles[
                    "ReportBody"
                ],
            )
        )

        if action:
            story.append(
                Paragraph(
                    f"<b>Action:</b> "
                    f"{_escape(action)}",
                    styles[
                        "ReportSmall"
                    ],
                )
            )

        if rationale:
            story.append(
                Paragraph(
                    f"<b>Why it matters:</b> "
                    f"{_escape(rationale)}",
                    styles[
                        "ReportSmall"
                    ],
                )
            )


def generate_financial_analysis_pdf(
    path,
    organization,
    period_start,
    period_end,
    analytics,
    health_score=None,
    ai_observations=None,
    ai_recommendations=None,
):
    """
    Generate the dedicated Financial Analysis Report.

    This report intentionally does NOT reproduce full financial statements.
    It focuses on performance, analytics, visual-report data, forecasts,
    financial health and AI interpretation.
    """

    styles = _build_styles()

    path = Path(path)

    document = _build_document(
        path
    )

    story: list = []

    _append_report_header(
        story,
        styles,
        "Financial Analysis Report",
        organization,
        period_start,
        period_end,
    )

    analytics = (
        analytics
        if isinstance(
            analytics,
            dict,
        )
        else {}
    )

    # ------------------------------------------------------------------
    # EXECUTIVE SUMMARY
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "1. Executive Financial Summary",
            styles["ReportHeading"],
        )
    )

    kpis = _extract_kpis(
        analytics
    )

    summary_text = (
        f"For the selected reporting period, ANGELIX recorded "
        f"{_format_currency(kpis['revenue'])} in revenue and "
        f"{_format_currency(kpis['expenses'])} in expenses, "
        f"resulting in net profit of "
        f"{_format_currency(kpis['net_profit'])}. "
        f"The reported profit margin is "
        f"{_format_percentage(kpis['profit_margin'])}."
    )

    story.append(
        Paragraph(
            _escape(summary_text),
            styles["ReportBody"],
        )
    )

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "2. Key Financial Indicators",
            styles["ReportHeading"],
        )
    )

    _append_kpi_table(
        story,
        styles,
        analytics,
    )

    # ------------------------------------------------------------------
    # REVENUE ANALYSIS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "3. Revenue Analysis",
            styles["ReportHeading"],
        )
    )

    revenue_breakdown = analytics.get(
        "revenue_breakdown",
        [],
    )

    if isinstance(
        revenue_breakdown,
        list,
    ) and revenue_breakdown:

        rows = [
            [
                Paragraph(
                    "Revenue Category",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
                Paragraph(
                    "Amount",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
            ]
        ]

        for item in revenue_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            rows.append(
                [
                    Paragraph(
                        _escape(
                            item.get(
                                "category",
                                "Revenue",
                            )
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            item.get(
                                "amount",
                                0,
                            )
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

        if len(rows) > 1:
            story.append(
                _styled_table(
                    rows,
                    [
                        120 * mm,
                        50 * mm,
                    ],
                    alignments=[
                        "LEFT",
                        "RIGHT",
                    ],
                )
            )

    # ------------------------------------------------------------------
    # EXPENSE ANALYSIS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "4. Expense Analysis",
            styles["ReportHeading"],
        )
    )

    expense_breakdown = analytics.get(
        "expense_breakdown",
        [],
    )

    if isinstance(
        expense_breakdown,
        list,
    ) and expense_breakdown:

        rows = [
            [
                Paragraph(
                    "Expense Category",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
                Paragraph(
                    "Amount",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
            ]
        ]

        for item in expense_breakdown:

            if not isinstance(
                item,
                dict,
            ):
                continue

            rows.append(
                [
                    Paragraph(
                        _escape(
                            item.get(
                                "category",
                                "Expense",
                            )
                        ),
                        styles[
                            "ReportTableCell"
                        ],
                    ),
                    Paragraph(
                        _format_currency(
                            item.get(
                                "amount",
                                0,
                            )
                        ),
                        styles[
                            "ReportTableCellRight"
                        ],
                    ),
                ]
            )

        if len(rows) > 1:
            story.append(
                _styled_table(
                    rows,
                    [
                        120 * mm,
                        50 * mm,
                    ],
                    alignments=[
                        "LEFT",
                        "RIGHT",
                    ],
                )
            )

    # ------------------------------------------------------------------
    # TRENDS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "5. Financial Trend Analysis",
            styles["ReportHeading"],
        )
    )

    story.append(
        Paragraph(
            "Print-friendly visualizations of monthly performance and "
            "category-level financial activity.",
            styles["ReportSmall"],
        )
    )

    _append_trend_visualizations(
        story,
        styles,
        analytics,
    )

    # ------------------------------------------------------------------
    # RATIOS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "6. Financial Ratio Analysis",
            styles["ReportHeading"],
        )
    )

    _append_ratio_table(
        story,
        styles,
        analytics,
    )

    # ------------------------------------------------------------------
    # BALANCE SHEET ANALYSIS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "7. Balance Sheet Analysis",
            styles["ReportHeading"],
        )
    )

    _append_balance_sheet_analysis(
        story,
        styles,
        health_score,
    )

    # ------------------------------------------------------------------
    # HEALTH SCORE
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "8. Financial Health Score",
            styles["ReportHeading"],
        )
    )

    _append_health_score(
        story,
        styles,
        health_score,
    )

    # ------------------------------------------------------------------
    # FORECAST
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "9. Financial Forecast",
            styles["ReportHeading"],
        )
    )

    _append_forecast(
        story,
        styles,
        analytics,
    )

    # ------------------------------------------------------------------
    # AI ANALYSIS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "10. AI Financial Analysis",
            styles["ReportHeading"],
        )
    )

    resolved_ai_observations = ai_observations

    if not resolved_ai_observations:
        for key in (
            "ai_analysis",
            "ai_observations",
            "ai_financial_analysis",
        ):
            candidate = analytics.get(key)

            if isinstance(candidate, dict) and candidate:
                resolved_ai_observations = candidate
                break

    if resolved_ai_observations:
        _append_ai_analysis(
            story,
            styles,
            resolved_ai_observations,
        )
    else:
        story.append(
            Paragraph(
                "AI financial analysis was not available for this report.",
                styles["ReportBody"],
            )
        )

    # ------------------------------------------------------------------
    # AI RECOMMENDATIONS
    # ------------------------------------------------------------------

    story.append(
        Paragraph(
            "11. AI Recommendations",
            styles["ReportHeading"],
        )
    )

    if ai_recommendations:
        _append_ai_recommendations(
            story,
            styles,
            ai_recommendations,
        )
    else:
        story.append(
            Paragraph(
                "AI recommendations were not available for this report.",
                styles["ReportBody"],
            )
        )

    # ------------------------------------------------------------------
    # DATA QUALITY
    # ------------------------------------------------------------------

    data_quality = analytics.get(
        "data_quality",
        {},
    )

    if isinstance(
        data_quality,
        dict,
    ) and data_quality:

        story.append(
            Paragraph(
                "12. Data Quality",
                styles["ReportHeading"],
            )
        )

        total_transactions = int(
            _safe_float(
                data_quality.get(
                    "total_transactions",
                    0,
                )
            )
        )

        categorized_transactions = int(
            _safe_float(
                data_quality.get(
                    "categorized_transactions",
                    0,
                )
            )
        )

        coverage = data_quality.get(
            "classification_coverage"
        )

        rows = [
            [
                Paragraph(
                    "Metric",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
                Paragraph(
                    "Value",
                    styles[
                        "ReportTableHeader"
                    ],
                ),
            ],
            [
                Paragraph(
                    "Total Transactions",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    str(
                        total_transactions
                    ),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ],
            [
                Paragraph(
                    "Categorized Transactions",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    str(
                        categorized_transactions
                    ),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ],
            [
                Paragraph(
                    "Classification Coverage",
                    styles[
                        "ReportTableCell"
                    ],
                ),
                Paragraph(
                    _format_percentage(
                        coverage
                    ),
                    styles[
                        "ReportTableCellRight"
                    ],
                ),
            ],
        ]

        story.append(
            _styled_table(
                rows,
                [
                    120 * mm,
                    50 * mm,
                ],
                alignments=[
                    "LEFT",
                    "RIGHT",
                ],
            )
        )

    # ------------------------------------------------------------------
    # DISCLAIMER
    # ------------------------------------------------------------------

    story.extend(
        [
            Spacer(1, 8),
            Paragraph(
                _escape(DISCLAIMER),
                styles["ReportDisclaimer"],
            ),
        ]
    )

    document.build(
        story,
        onFirstPage=_draw_header_footer,
        onLaterPages=_draw_header_footer,
    )

    return path


# ============================================================================
# BACKWARD-COMPATIBILITY WRAPPER
# ============================================================================


def generate_pdf(
    path,
    organization,
    period_start,
    period_end,
    analytics,
    statements=None,
    health_score=None,
    ai_observations=None,
    ai_recommendations=None,
):
    """
    Backward-compatible entry point.

    IMPORTANT:
    New route code should call one of:

        generate_financial_statements_pdf()
        generate_financial_analysis_pdf()

    This wrapper currently generates the Financial Analysis Report because
    the old route historically produced a combined analytical report.

    It remains temporarily so existing imports do not break while the
    Reports routes are migrated to the new architecture.
    """

    return generate_financial_analysis_pdf(
        path=path,
        organization=organization,
        period_start=period_start,
        period_end=period_end,
        analytics=analytics,
        health_score=health_score,
        ai_observations=ai_observations,
        ai_recommendations=ai_recommendations,
    )