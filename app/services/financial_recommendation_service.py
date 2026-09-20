"""
Financial Recommendation Service for Angelix.

Combines deterministic financial analytics and Financial Health Score
with AI-generated financial recommendations.

The application remains the source of truth for financial figures.
AI is used only for interpretation and recommendation generation.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from ..ai.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
)
from ..models.financial_statement import FinancialStatement
from ..services.analytics_service import AnalyticsService
from ..services.financial_health_service import FinancialHealthService


class FinancialRecommendationError(Exception):
    """Raised when financial recommendations cannot be generated."""


class FinancialRecommendationService:
    """
    Generate structured financial recommendations.

    Financial metrics and health scores are deterministic.
    AI is used only for interpretation and recommendations.
    """

    MAX_RECOMMENDATIONS = 4

    DISCLAIMER = (
        "AI-generated recommendations are for informational and "
        "decision-support purposes only. They are based on the "
        "financial data available in Angelix and should not be "
        "considered professional financial, accounting, tax, legal, "
        "or investment advice."
    )

    def __init__(self) -> None:
        self.analytics_service = AnalyticsService()
        self.health_service = FinancialHealthService()

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def generate(
        self,
        organization_id: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:

        organization_id = int(organization_id)

        health_result = self.health_service.calculate(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
        )

        balance_sheet = self._get_latest_balance_sheet(
            organization_id
        )

        # --------------------------------------------------------------
        # Resolve reporting period.
        #
        # Explicit dates supplied by the caller take priority.
        # Otherwise use the latest completed balance-sheet period.
        # Finally fall back to the Health Service period.
        # --------------------------------------------------------------

        resolved_period_start = period_start
        resolved_period_end = period_end

        if (
            resolved_period_start is None
            and balance_sheet is not None
        ):
            resolved_period_start = (
                balance_sheet.period_start
            )

        if (
            resolved_period_end is None
            and balance_sheet is not None
        ):
            resolved_period_end = (
                balance_sheet.period_end
            )

        health_period = health_result.get(
            "reporting_period"
        )

        if health_period:

            if resolved_period_start is None:
                resolved_period_start = (
                    self._parse_date(
                        health_period.get("start")
                    )
                )

            if resolved_period_end is None:
                resolved_period_end = (
                    self._parse_date(
                        health_period.get("end")
                    )
                )

        analytics = self.analytics_service.calculate(
            organization_id=organization_id,
            period_start=resolved_period_start,
            period_end=resolved_period_end,
        )

        balance_sheet_context = (
            self._build_balance_sheet_context(
                balance_sheet
            )
        )

        deterministic_context = {
            "reporting_period": {
                "start": (
                    resolved_period_start.isoformat()
                    if resolved_period_start
                    else None
                ),
                "end": (
                    resolved_period_end.isoformat()
                    if resolved_period_end
                    else None
                ),
            },
            "financial_health": {
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
            },
            "analytics": self._build_ai_analytics_context(
                analytics
            ),
            "balance_sheet": balance_sheet_context,
        }

        recommendations = (
            self._generate_ai_recommendations(
                deterministic_context
            )
        )

        # Final application-level validation.
        recommendations = (
            self._sanitize_recommendations(
                recommendations,
                balance_sheet_context,
            )
        )

        return {
            "available": True,
            "reporting_period": deterministic_context[
                "reporting_period"
            ],
            "financial_health": health_result,
            "analytics": analytics,
            "balance_sheet": balance_sheet_context,
            "recommendations": recommendations,
            "disclaimer": self.DISCLAIMER,
        }

    # ==================================================================
    # BALANCE SHEET
    # ==================================================================

    def _get_latest_balance_sheet(
        self,
        organization_id: int,
    ) -> FinancialStatement | None:

        return (
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
            )
            .first()
        )

    def _build_balance_sheet_context(
        self,
        statement: FinancialStatement | None,
    ) -> dict[str, Any]:

        if statement is None:
            return {
                "available": False,
                "statement_id": None,
                "period_start": None,
                "period_end": None,
                "fiscal_year": None,
                "total_assets": 0.0,
                "total_liabilities": 0.0,
                "total_equity": 0.0,
                "accounting_equation": {
                    "assets": 0.0,
                    "liabilities_plus_equity": 0.0,
                    "difference": 0.0,
                    "balanced": False,
                },
            }

        # --------------------------------------------------------------
        # Approved financial statement line items are the authoritative
        # source for balance-sheet totals.
        # --------------------------------------------------------------

        assets = Decimal("0.00")
        liabilities = Decimal("0.00")
        equity = Decimal("0.00")

        line_items = list(
            getattr(
                statement,
                "line_items",
                [],
            )
            or []
        )

        usable_line_items = 0

        for line_item in line_items:

            account_type = str(
                line_item.account_type or ""
            ).strip().lower()

            amount = self._decimal(
                line_item.amount
            )

            if account_type == "asset":
                assets += amount
                usable_line_items += 1

            elif account_type == "liability":
                liabilities += amount
                usable_line_items += 1

            elif account_type == "equity":
                equity += amount
                usable_line_items += 1

        # --------------------------------------------------------------
        # Use FinancialStatement aggregate fields only when there are
        # no usable approved line items.
        # --------------------------------------------------------------

        if usable_line_items == 0:
            assets = self._decimal(
                statement.total_assets
            )

            liabilities = self._decimal(
                statement.total_liabilities
            )

            equity = self._decimal(
                statement.total_equity
            )

        liabilities_plus_equity = (
            liabilities + equity
        )

        difference = (
            assets - liabilities_plus_equity
        )

        return {
            "available": True,
            "statement_id": statement.id,
            "period_start": (
                statement.period_start.isoformat()
                if statement.period_start
                else None
            ),
            "period_end": (
                statement.period_end.isoformat()
                if statement.period_end
                else None
            ),
            "fiscal_year": statement.fiscal_year,
            "total_assets": float(
                assets
            ),
            "total_liabilities": float(
                liabilities
            ),
            "total_equity": float(
                equity
            ),
            "accounting_equation": {
                "assets": float(
                    assets
                ),
                "liabilities_plus_equity": float(
                    liabilities_plus_equity
                ),
                "difference": float(
                    difference
                ),
                "balanced": (
                    abs(difference)
                    <= Decimal("0.01")
                ),
            },
        }
    # ==================================================================
    # AI ANALYTICS CONTEXT
    # ==================================================================

    @staticmethod
    def _build_ai_analytics_context(
        analytics: dict[str, Any],
    ) -> dict[str, Any]:

        kpis = analytics.get(
            "kpis",
            {}
        )

        ratios = analytics.get(
            "ratios",
            {}
        )

        return {
            "kpis": {
                "total_revenue": kpis.get(
                    "total_revenue"
                ),
                "total_expenses": kpis.get(
                    "total_expenses"
                ),
                "net_profit": kpis.get(
                    "net_profit"
                ),
                "profit_margin": kpis.get(
                    "profit_margin"
                ),
                "net_cash_flow": kpis.get(
                    "net_cash_flow"
                ),
                "total_transactions": kpis.get(
                    "total_transactions"
                ),
            },
            "ratios": {
                "current_ratio": ratios.get(
                    "current_ratio"
                ),
                "debt_to_equity": ratios.get(
                    "debt_to_equity"
                ),
                "gross_profit_margin": ratios.get(
                    "gross_profit_margin"
                ),
                "net_profit_margin": ratios.get(
                    "net_profit_margin"
                ),
            },
            "expense_breakdown": analytics.get(
                "expense_breakdown",
                [],
            ),
            "revenue_breakdown": analytics.get(
                "revenue_breakdown",
                [],
            ),
            "monthly_trend": analytics.get(
                "monthly_trend",
                [],
            ),
            "forecast": analytics.get(
                "forecast",
                {},
            ),
            "data_quality": analytics.get(
                "data_quality",
                {},
            ),
        }

    # ==================================================================
    # AI GENERATION
    # ==================================================================
 
    def _generate_ai_recommendations(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:

        system_prompt = """
You are Angelix's Financial Recommendation Engine.

Analyze the supplied deterministic financial data.

IMPORTANT RULES:

1. Use ONLY the supplied data.
2. Never invent financial figures.
3. The Financial Health Score is authoritative.
4. The balance_sheet object is authoritative for:
   - total assets
   - total liabilities
   - total equity
   - accounting equation
5. Never state that the balance sheet contains zero values unless
   the supplied balance_sheet object actually contains zero values.
6. Do not confuse transaction analytics with the official balance sheet.
7. Keep recommendations practical and concise.
8. Do not provide investment, tax, legal, or professional advice.
9. Generate exactly 3 recommendations.
10. Return ONLY valid JSON.
11. Do not use Markdown.
12. Do not add text outside the JSON.

Required structure:

{
  "recommendations": [
    {
      "title": "Short title",
      "priority": "high",
      "area": "Financial Area",
      "observation": "Short factual observation.",
      "recommendation": "Short practical action.",
      "evidence": ["One factual item"],
      "expected_focus": "Short expected improvement.",
      "confidence": 0.90
    }
  ]
}

Priority:
high, medium, low

Confidence:
0 to 1

Maximum one evidence item per recommendation.
"""

        health_context = context.get("financial_health", {})
        analytics_context = context.get("analytics", {})
        balance_sheet_context = context.get("balance_sheet", {})
        reporting_period = context.get("reporting_period", {})

        user_prompt = f"""
        Generate exactly 3 financial recommendations for the Angelix user.
        Use ONLY the financial context below.

        FINANCIAL HEALTH:
        {json.dumps(health_context, ensure_ascii=False)}

        ANALYTICS:
        {json.dumps(analytics_context, ensure_ascii=False)}

        BALANCE SHEET:
        {json.dumps(balance_sheet_context, ensure_ascii=False)}

        REPORTING PERIOD:
        {json.dumps(reporting_period, ensure_ascii=False)}

        Return ONLY valid JSON.

        Required structure:

        {{
            "recommendations": [
                {{
                    "title": "short title",
                    "priority": "high|medium|low",
                    "area": "short area",
                    "observation": "one concise factual observation",
                    "recommendation": "one concise actionable recommendation",
                    "evidence": ["short factual evidence"],
                    "expected_focus": "short expected focus",
                    "confidence": 0.0
                }}
            ]
        }}

        Rules:
        - Return exactly 3 recommendations.
        - Keep every field concise.
        - Do not use markdown.
        - Do not use code fences.
        - Do not invent financial figures.
        - Do not claim that balance-sheet values are zero unless the supplied balance sheet actually contains zero values.
        - Treat the supplied balance sheet as authoritative.
        - Use the deterministic financial health score as authoritative.
        - Confidence must be between 0 and 1.
        - Each recommendation should address a distinct issue.
        """

        client = OpenRouterClient()

        messages = [
            {
                "role": "system",
                "content": system_prompt.strip(),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        try:

            raw_response = client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=2400,
                response_format={
                    "type": "json_object"
                },
            )

        except OpenRouterError:

            try:

                raw_response = client.chat(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2400,
                )

            except OpenRouterError as exc:

                raise FinancialRecommendationError(
                    str(exc)
                ) from exc

        return self._parse_json_response(
            raw_response
        )

    # ==================================================================
    # FINAL RECOMMENDATION SANITIZATION
    # ==================================================================

    def _sanitize_recommendations(
        self,
        recommendations: list[dict[str, Any]],
        balance_sheet: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Remove AI recommendations that contradict authoritative
        application data.

        This is an important safety layer because free AI models can
        occasionally misread otherwise correct context.
        """

        if not balance_sheet.get(
            "available"
        ):

            return recommendations[
                : self.MAX_RECOMMENDATIONS
            ]

        assets = balance_sheet.get(
            "total_assets",
            0.0,
        )

        liabilities = balance_sheet.get(
            "total_liabilities",
            0.0,
        )

        equity = balance_sheet.get(
            "total_equity",
            0.0,
        )

        # If the official balance sheet contains actual values,
        # reject recommendations that explicitly claim all three
        # values are zero.
        has_populated_balance_sheet = (
            float(assets) != 0.0
            or float(liabilities) != 0.0
            or float(equity) != 0.0
        )

        if not has_populated_balance_sheet:

            return recommendations[
                : self.MAX_RECOMMENDATIONS
            ]

        sanitized = []

        contradictory_phrases = (
            "balance sheet shows zero",
            "balance sheet has zero",
            "balance sheet contains zero",
            "total assets are zero",
            "total liabilities are zero",
            "total equity are zero",
            "total equity is zero",
            "assets, liabilities, and equity are all zero",
            "assets liabilities and equity are all zero",
        )

        for recommendation in recommendations:

            combined_text = " ".join(
                [
                    self._clean_text(
                        recommendation.get(
                            "title"
                        )
                    ),
                    self._clean_text(
                        recommendation.get(
                            "observation"
                        )
                    ),
                    self._clean_text(
                        recommendation.get(
                            "recommendation"
                        )
                    ),
                    " ".join(
                        recommendation.get(
                            "evidence",
                            [],
                        )
                    ),
                ]
            ).lower()

            contradiction_found = any(
                phrase in combined_text
                for phrase in contradictory_phrases
            )

            if contradiction_found:
                continue

            sanitized.append(
                recommendation
            )

        return sanitized[
            : self.MAX_RECOMMENDATIONS
        ]

    # ==================================================================
    # JSON PARSING
    # ==================================================================

    def _parse_json_response(
        self,
        response: str,
    ) -> list[dict[str, Any]]:

        if not isinstance(
            response,
            str,
        ):

            raise FinancialRecommendationError(
                "AI returned a non-text recommendation response."
            )

        cleaned = response.strip()

        if not cleaned:

            raise FinancialRecommendationError(
                "AI returned an empty recommendation response."
            )

        cleaned = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = cleaned.strip()

        parsed: Any = None

        try:

            parsed = json.loads(
                cleaned
            )

        except json.JSONDecodeError:

            parsed = None

        if parsed is None:

            repaired = re.sub(
                r"^\s*\{\s*\{",
                "{",
                cleaned,
                count=1,
            )

            try:

                parsed = json.loads(
                    repaired
                )

            except json.JSONDecodeError:

                parsed = None

        if parsed is None:

            recommendation_array = (
                self._extract_json_array_after_key(
                    cleaned,
                    "recommendations",
                )
            )

            if recommendation_array:

                try:

                    parsed = json.loads(
                        recommendation_array
                    )

                except json.JSONDecodeError:

                    parsed = None

        if parsed is None:

            array_text = (
                self._extract_first_json_array(
                    cleaned
                )
            )

            if array_text:

                try:

                    parsed = json.loads(
                        array_text
                    )

                except json.JSONDecodeError:

                    parsed = None

        if parsed is None:

            decoder = json.JSONDecoder()

            positions = [
                cleaned.find("{"),
                cleaned.find("["),
            ]

            positions = [
                position
                for position in positions
                if position >= 0
            ]

            for position in sorted(
                set(positions)
            ):

                try:

                    candidate, _ = (
                        decoder.raw_decode(
                            cleaned[position:]
                        )
                    )

                    parsed = candidate

                    break

                except json.JSONDecodeError:

                    continue

        recommendations = (
            self._extract_recommendation_list(
                parsed
            )
        )

        if not recommendations:

            raise FinancialRecommendationError(
                "AI returned an invalid JSON "
                "recommendation response. "
                f"Response preview: {cleaned[:1200]}"
            )

        validated = []

        for item in recommendations:

            normalized = (
                self._validate_recommendation(
                    item
                )
            )

            if normalized is not None:

                validated.append(
                    normalized
                )

        if not validated:

            raise FinancialRecommendationError(
                "AI returned recommendation data, "
                "but none of the recommendations "
                "passed validation."
            )

        return validated[
            : self.MAX_RECOMMENDATIONS
        ]

    # ==================================================================
    # JSON RECOVERY
    # ==================================================================

    @staticmethod
    def _extract_json_array_after_key(
        text: str,
        key: str,
    ) -> str | None:

        pattern = re.compile(
            rf'"{re.escape(key)}"\s*:\s*\[',
            flags=re.IGNORECASE,
        )

        match = pattern.search(
            text
        )

        if not match:

            return None

        array_start = text.find(
            "[",
            match.start(),
        )

        if array_start < 0:

            return None

        return (
            FinancialRecommendationService
            ._extract_balanced_json(
                text,
                array_start,
                "[",
                "]",
            )
        )

    @staticmethod
    def _extract_first_json_array(
        text: str,
    ) -> str | None:

        start = text.find(
            "["
        )

        if start < 0:

            return None

        return (
            FinancialRecommendationService
            ._extract_balanced_json(
                text,
                start,
                "[",
                "]",
            )
        )

    @staticmethod
    def _extract_balanced_json(
        text: str,
        start: int,
        opening: str,
        closing: str,
    ) -> str | None:

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):

            character = text[index]

            if in_string:

                if escaped:

                    escaped = False
                    continue

                if character == "\\":

                    escaped = True
                    continue

                if character == '"':

                    in_string = False

                continue

            if character == '"':

                in_string = True
                continue

            if character == opening:

                depth += 1

            elif character == closing:

                depth -= 1

                if depth == 0:

                    return text[
                        start:index + 1
                    ]

        return None

    # ==================================================================
    # RECOMMENDATION EXTRACTION
    # ==================================================================

    def _extract_recommendation_list(
        self,
        parsed: Any,
    ) -> list[Any]:

        if isinstance(
            parsed,
            list,
        ):

            return parsed

        if not isinstance(
            parsed,
            dict,
        ):

            return []

        accepted_keys = (
            "recommendations",
            "financial_recommendations",
            "suggestions",
            "action_items",
            "actions",
            "recommendation_list",
            "financial_actions",
        )

        for key in accepted_keys:

            value = parsed.get(
                key
            )

            if isinstance(
                value,
                list,
            ):

                return value

        for value in parsed.values():

            if isinstance(
                value,
                dict,
            ):

                nested = (
                    self._extract_recommendation_list(
                        value
                    )
                )

                if nested:

                    return nested

            elif isinstance(
                value,
                list,
            ):

                if all(
                    isinstance(
                        item,
                        dict,
                    )
                    for item in value
                ):

                    if any(
                        any(
                            key in item
                            for key in (
                                "title",
                                "recommendation",
                                "observation",
                            )
                        )
                        for item in value
                    ):

                        return value

        return []

    # ==================================================================
    # VALIDATION
    # ==================================================================

    def _validate_recommendation(
        self,
        item: Any,
    ) -> dict[str, Any] | None:

        if not isinstance(
            item,
            dict,
        ):

            return None

        title = self._clean_text(
            item.get("title")
        )

        recommendation = (
            self._clean_text(
                item.get(
                    "recommendation"
                )
            )
        )

        observation = (
            self._clean_text(
                item.get(
                    "observation"
                )
            )
        )

        if not title or not recommendation:

            return None

        if not observation:

            observation = (
                "The available financial data "
                "indicates an area requiring attention."
            )

        priority = (
            self._clean_text(
                item.get(
                    "priority"
                )
            ).lower()
        )

        if priority not in {
            "high",
            "medium",
            "low",
        }:

            priority = "medium"

        area = self._clean_text(
            item.get(
                "area"
            )
        )

        if not area:

            area = "Financial Management"

        evidence = item.get(
            "evidence"
        )

        if isinstance(
            evidence,
            str,
        ):

            evidence = (
                [evidence.strip()]
                if evidence.strip()
                else []
            )

        elif isinstance(
            evidence,
            list,
        ):

            evidence = [
                self._clean_text(
                    value
                )
                for value in evidence
                if self._clean_text(
                    value
                )
            ]

        else:

            evidence = []

        evidence = evidence[:1]

        expected_focus = (
            self._clean_text(
                item.get(
                    "expected_focus"
                )
            )
        )

        if not expected_focus:

            expected_focus = (
                "Improve financial visibility "
                "and decision-making."
            )

        confidence = self._safe_float(
            item.get(
                "confidence"
            ),
            default=0.70,
        )

        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        return {
            "title": title[:120],
            "priority": priority,
            "area": area[:100],
            "observation": observation[:400],
            "recommendation": recommendation[:500],
            "evidence": evidence,
            "expected_focus": expected_focus[:250],
            "confidence": round(
                confidence,
                2,
            ),
        }

    # ==================================================================
    # UTILITIES
    # ==================================================================

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        if isinstance(
            value,
            str,
        ):

            return value.strip()

        return str(value).strip()

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return default

    @staticmethod
    def _decimal(
        value: Any,
    ) -> Decimal:

        if value is None:

            return Decimal(
                "0"
            )

        if isinstance(
            value,
            Decimal,
        ):

            return value

        try:

            return Decimal(
                str(value)
            )

        except (
            TypeError,
            ValueError,
        ):

            return Decimal(
                "0"
            )

    @staticmethod
    def _parse_date(
        value: Any,
    ) -> date | None:

        if not value:

            return None

        if isinstance(
            value,
            date,
        ):

            return value

        try:

            return date.fromisoformat(
                str(value)
            )

        except ValueError:

            return None