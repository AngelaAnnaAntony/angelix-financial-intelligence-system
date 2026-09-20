"""
AI-powered financial analysis service for Angelix.

The deterministic financial calculations are performed by Angelix.
OpenRouter is used only to interpret the supplied financial context.

The service is intentionally defensive because OpenRouter's free
routing can select different models with different response formats
and output limits.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..ai.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
)


class FinancialAIAnalysisError(Exception):
    """
    Raised when AI financial analysis cannot be generated
    or validated.
    """


class FinancialAIAnalysisService:
    """
    Generates concise structured AI financial analysis.
    """

    MAX_INSIGHTS = 3

    # The previous 1200-token limit could truncate the JSON.
    PRIMARY_MAX_TOKENS = 1800

    # Retry is still large enough for three concise insights.
    RETRY_MAX_TOKENS = 1200

    def __init__(self) -> None:
        self.client = OpenRouterClient()

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def generate(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate structured AI financial analysis.

        The service makes several compatible OpenRouter attempts because
        free models can differ in support for JSON mode and reasoning
        controls. Deterministic financial calculations remain outside AI.
        """

        if not isinstance(
            context,
            dict,
        ):
            raise FinancialAIAnalysisError(
                "Financial analysis context must be a dictionary."
            )

        messages = self._build_messages(
            context,
            retry=False,
        )

        attempts = [
            {
                "max_tokens": self.PRIMARY_MAX_TOKENS,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_object",
                },
                "reasoning": {
                    "exclude": True,
                },
            },
            {
                "max_tokens": self.RETRY_MAX_TOKENS,
                "temperature": 0.0,
                "response_format": {
                    "type": "json_object",
                },
                "reasoning": {
                    "exclude": True,
                },
            },
            {
                "max_tokens": self.RETRY_MAX_TOKENS,
                "temperature": 0.0,
                "response_format": None,
                "reasoning": None,
            },
        ]

        errors: list[str] = []

        for attempt_number, options in enumerate(
            attempts,
            start=1,
        ):

            try:

                response = self.client.chat(
                    messages=messages,
                    temperature=options["temperature"],
                    max_tokens=options["max_tokens"],
                    response_format=options["response_format"],
                    reasoning=options["reasoning"],
                )

            except OpenRouterError as exc:

                errors.append(
                    f"attempt {attempt_number}: {exc}"
                )

                messages = self._build_messages(
                    context,
                    retry=True,
                )

                continue

            if not response:

                errors.append(
                    f"attempt {attempt_number}: empty response"
                )

                messages = self._build_messages(
                    context,
                    retry=True,
                )

                continue

            try:

                return self._parse_response(
                    response
                )

            except FinancialAIAnalysisError as exc:

                errors.append(
                    f"attempt {attempt_number}: {exc}"
                )

                messages = self._build_messages(
                    context,
                    retry=True,
                )

                continue

        details = " | ".join(
            errors[-3:]
        )

        raise FinancialAIAnalysisError(
            "OpenRouter could not produce a valid financial analysis "
            f"after {len(attempts)} compatible attempts. {details}"
        )

    # ==========================================================
    # PROMPT CONSTRUCTION
    # ==========================================================

    def _build_messages(
        self,
        context: dict[str, Any],
        retry: bool = False,
    ) -> list[dict[str, str]]:
        """
        Build a compact prompt using the actual AnalyticsService schema.

        AnalyticsService stores KPIs under analytics["kpis"] and forecast
        values under analytics["forecast"]["next_month_*"].
        """

        financial_health = context.get(
            "financial_health",
            {},
        )

        analytics = context.get(
            "analytics",
            {},
        )

        balance_sheet = context.get(
            "balance_sheet",
            {},
        )

        reporting_period = context.get(
            "reporting_period",
            {},
        )

        if not isinstance(
            financial_health,
            dict,
        ):
            financial_health = {}

        if not isinstance(
            analytics,
            dict,
        ):
            analytics = {}

        if not isinstance(
            balance_sheet,
            dict,
        ):
            balance_sheet = {}

        if not isinstance(
            reporting_period,
            dict,
        ):
            reporting_period = {}

        kpis = analytics.get(
            "kpis",
            {},
        )

        if not isinstance(
            kpis,
            dict,
        ):
            kpis = {}

        data_quality = analytics.get(
            "data_quality",
            {},
        )

        if not isinstance(
            data_quality,
            dict,
        ):
            data_quality = {}

        forecast = analytics.get(
            "forecast",
            {},
        )

        if not isinstance(
            forecast,
            dict,
        ):
            forecast = {}

        # ------------------------------------------------------
        # Compact deterministic analytics
        # ------------------------------------------------------

        compact_analytics = {
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
            "net_cash_flow": kpis.get(
                "net_cash_flow",
                0,
            ),
            "transaction_count": kpis.get(
                "total_transactions",
                0,
            ),
            "classification_coverage": data_quality.get(
                "classification_coverage",
                0,
            ),
            "revenue_breakdown": self._compact_breakdown(
                analytics.get(
                    "revenue_breakdown",
                    [],
                )
            ),
            "expense_breakdown": self._compact_breakdown(
                analytics.get(
                    "expense_breakdown",
                    [],
                )
            ),
            "monthly_trend": self._compact_trend(
                analytics.get(
                    "monthly_trend",
                    [],
                )
            ),
            "ratios": self._compact_dict(
                analytics.get(
                    "ratios",
                    {},
                ),
                (
                    "current_ratio",
                    "debt_to_equity",
                    "gross_profit_margin",
                    "net_profit_margin",
                ),
            ),
        }

        # ------------------------------------------------------
        # Compact health score
        # ------------------------------------------------------

        health_components = financial_health.get(
            "components",
            {},
        )

        compact_health = {
            "score": financial_health.get(
                "score",
                financial_health.get(
                    "health_score",
                ),
            ),
            "status": financial_health.get(
                "health_level",
                financial_health.get(
                    "status",
                    financial_health.get(
                        "rating",
                    ),
                ),
            ),
            "components": self._compact_health_components(
                health_components
            ),
        }

        # ------------------------------------------------------
        # Compact balance sheet
        # ------------------------------------------------------

        compact_balance_sheet = self._compact_dict(
            balance_sheet,
            (
                "total_assets",
                "total_liabilities",
                "total_equity",
            ),
        )

        accounting_equation = balance_sheet.get(
            "accounting_equation",
            {},
        )

        if isinstance(
            accounting_equation,
            dict,
        ):

            compact_balance_sheet[
                "accounting_equation"
            ] = self._compact_dict(
                accounting_equation,
                (
                    "assets",
                    "liabilities_plus_equity",
                    "difference",
                    "balanced",
                ),
            )

        # ------------------------------------------------------
        # Compact forecast
        # ------------------------------------------------------

        compact_forecast = {
            "available": forecast.get(
                "available",
                False,
            ),
            "method": forecast.get(
                "method",
                forecast.get(
                    "forecast_method",
                ),
            ),
            "next_period_revenue": forecast.get(
                "next_month_revenue",
                forecast.get(
                    "next_period_revenue",
                    0,
                ),
            ),
            "next_period_expenses": forecast.get(
                "next_month_expenses",
                forecast.get(
                    "next_period_expenses",
                    0,
                ),
            ),
            "next_period_profit": forecast.get(
                "next_month_profit",
                forecast.get(
                    "next_period_profit",
                    0,
                ),
            ),
        }

        payload = {
            "reporting_period": reporting_period,
            "financial_health": compact_health,
            "analytics": compact_analytics,
            "balance_sheet": compact_balance_sheet,
            "forecast": compact_forecast,
        }

        # ------------------------------------------------------
        # Prompt
        # ------------------------------------------------------

        if retry:

            system_message = (
                "You are Angelix AI. "
                "Analyze only the supplied financial data. "
                "Return ONLY valid JSON. "
                "No Markdown. No code fences. "
                "Return exactly 3 concise factual insights. "
                "Never invent values. "
                "Do not provide professional financial advice."
            )

            user_instruction = (
                "Create a concise financial analysis."
            )

        else:

            system_message = (
                "You are Angelix Financial Analysis AI. "
                "Use only the supplied Angelix financial data. "
                "Never invent financial values. "
                "The Financial Health Score and Balance Sheet are "
                "authoritative. "
                "Return ONLY one valid JSON object with exactly "
                "3 concise factual insights. "
                "Do not provide investment, tax, legal, accounting, "
                "or professional financial advice."
            )

            user_instruction = (
                "Analyze financial performance, financial health, "
                "balance-sheet position, trends, forecast and outlook "
                "using only the supplied data."
            )

        schema = {
            "summary": "One concise factual financial summary.",
            "insights": [
                {
                    "title": "Short title",
                    "area": "Financial area",
                    "observation": "One factual observation.",
                    "evidence": "One value or metric from the data.",
                    "implication": "One concise implication.",
                },
                {
                    "title": "Short title",
                    "area": "Financial area",
                    "observation": "One factual observation.",
                    "evidence": "One value or metric from the data.",
                    "implication": "One concise implication.",
                },
                {
                    "title": "Short title",
                    "area": "Financial area",
                    "observation": "One factual observation.",
                    "evidence": "One value or metric from the data.",
                    "implication": "One concise implication.",
                },
            ],
            "outlook": "One concise data-based outlook.",
        }

        schema_text = json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        payload_text = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        user_message = (
            user_instruction
            + "\n\nRequired JSON structure:\n"
            + schema_text
            + "\n\nFinancial data:\n"
            + payload_text
            + "\n\nKeep every field short. "
            + "Do not add any text outside the JSON object."
        )

        return [
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

    # ==========================================================
    # COMPACT CONTEXT HELPERS
    # ==========================================================

    @staticmethod
    def _compact_dict(
        value: Any,
        allowed_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        if not isinstance(
            value,
            dict,
        ):
            return {}

        return {
            key: value.get(key)
            for key in allowed_keys
            if value.get(key) is not None
        }

    @staticmethod
    def _compact_breakdown(
        value: Any,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            value,
            list,
        ):
            return []

        result = []

        for item in value[:limit]:

            if not isinstance(
                item,
                dict,
            ):
                continue

            category = item.get(
                "category",
                item.get(
                    "name",
                ),
            )

            amount = item.get(
                "amount",
                item.get(
                    "value",
                ),
            )

            if category is None:
                continue

            result.append(
                {
                    "category": str(
                        category
                    ),
                    "amount": amount,
                }
            )

        return result

    @staticmethod
    def _compact_trend(
        value: Any,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            value,
            list,
        ):
            return []

        result = []

        for item in value[:limit]:

            if not isinstance(
                item,
                dict,
            ):
                continue

            period = item.get(
                "period",
                item.get(
                    "month",
                ),
            )

            if period is None:
                continue

            result.append(
                {
                    "period": str(
                        period
                    ),
                    "revenue": item.get(
                        "revenue",
                        0,
                    ),
                    "expenses": item.get(
                        "expenses",
                        0,
                    ),
                    "net_profit": item.get(
                        "net_profit",
                        item.get(
                            "profit",
                            0,
                        ),
                    ),
                }
            )

        return result

    @staticmethod
    def _compact_health_components(
        value: Any,
    ) -> list[dict[str, Any]]:
        if isinstance(
            value,
            dict,
        ):

            source_items = list(
                value.items()
            )

        elif isinstance(
            value,
            list,
        ):

            source_items = []

            for item in value:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                source_items.append(
                    (
                        item.get(
                            "name",
                            item.get(
                                "component",
                                "Component",
                            ),
                        ),
                        item,
                    )
                )

        else:

            return []

        result = []

        for name, item in source_items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            result.append(
                {
                    "name": str(
                        name
                    ),
                    "score": item.get(
                        "score",
                    ),
                    "max_score": item.get(
                        "max_score",
                    ),
                    "status": item.get(
                        "status",
                    ),
                    "reason": item.get(
                        "reason",
                    ),
                }
            )

        return result[:6]

    # ==========================================================
    # RESPONSE PARSING
    # ==========================================================

    def _parse_response(
        self,
        raw_response: str,
    ) -> dict[str, Any]:
        """
        Clean and parse an OpenRouter response.
        """

        if not raw_response:

            raise FinancialAIAnalysisError(
                "OpenRouter returned an empty response."
            )

        cleaned = self._clean_raw_response(
            raw_response
        )

        if not cleaned:

            raise FinancialAIAnalysisError(
                "AI response was empty after cleanup."
            )

        # ------------------------------------------------------
        # Direct JSON
        # ------------------------------------------------------

        try:

            parsed = json.loads(
                cleaned
            )

            if isinstance(
                parsed,
                dict,
            ):

                return self._validate_result(
                    parsed
                )

        except json.JSONDecodeError:
            pass

        # ------------------------------------------------------
        # Embedded JSON
        # ------------------------------------------------------

        extracted = self._extract_json_object(
            cleaned
        )

        if extracted is None:

            preview = cleaned[
                :500
            ].replace(
                "\n",
                " ",
            )

            raise FinancialAIAnalysisError(
                "AI response did not contain a JSON object. "
                f"Response preview: {preview}"
            )

        return self._validate_result(
            extracted
        )

    # ==========================================================
    # RESPONSE CLEANING
    # ==========================================================

    @staticmethod
    def _clean_raw_response(
        raw_response: str,
    ) -> str:
        """
        Remove common wrappers produced by AI models.
        """

        text = str(
            raw_response
        ).strip()

        # ------------------------------------------------------
        # Remove reasoning blocks
        # ------------------------------------------------------

        text = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        text = re.sub(
            r"<analysis>.*?</analysis>",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # ------------------------------------------------------
        # Remove Markdown fences
        # ------------------------------------------------------

        text = re.sub(
            r"```(?:json|JSON)?",
            "",
            text,
        )

        text = text.replace(
            "```",
            "",
        )

        text = text.strip()

        # ------------------------------------------------------
        # Remove common prefixes
        # ------------------------------------------------------

        prefixes = (
            "JSON:",
            "json:",
            "Response:",
            "response:",
            "Here is the JSON:",
            "Here is the JSON object:",
        )

        for prefix in prefixes:

            if text.startswith(
                prefix
            ):

                text = text[
                    len(prefix):
                ].strip()

        return text.strip()

    # ==========================================================
    # JSON OBJECT EXTRACTION
    # ==========================================================

    @staticmethod
    def _extract_json_object(
        text: str,
    ) -> dict[str, Any] | None:
        """
        Extract the first valid balanced JSON object.

        Handles braces appearing inside JSON strings.
        """

        start_positions = [
            match.start()
            for match in re.finditer(
                r"\{",
                text,
            )
        ]

        if not start_positions:
            return None

        for start in start_positions:

            depth = 0
            in_string = False
            escaped = False

            for index in range(
                start,
                len(text),
            ):

                character = text[
                    index
                ]

                # --------------------------------------------------
                # Inside string
                # --------------------------------------------------

                if in_string:

                    if escaped:

                        escaped = False

                    elif character == "\\":

                        escaped = True

                    elif character == '"':

                        in_string = False

                    continue

                # --------------------------------------------------
                # Outside string
                # --------------------------------------------------

                if character == '"':

                    in_string = True
                    continue

                if character == "{":

                    depth += 1
                    continue

                if character == "}":

                    depth -= 1

                    if depth == 0:

                        candidate = text[
                            start:index + 1
                        ]

                        try:

                            parsed = json.loads(
                                candidate
                            )

                        except json.JSONDecodeError:

                            break

                        if isinstance(
                            parsed,
                            dict,
                        ):

                            return parsed

                        break

        return None

    # ==========================================================
    # RESULT VALIDATION
    # ==========================================================

    def _validate_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and normalize the AI response.
        """

        summary = self._clean_text(
            result.get(
                "summary"
            )
        )

        if not summary:

            raise FinancialAIAnalysisError(
                "AI response is missing the summary."
            )

        insights = result.get(
            "insights"
        )

        if not isinstance(
            insights,
            list,
        ):

            raise FinancialAIAnalysisError(
                "AI response does not contain an insights list."
            )

        if len(insights) != self.MAX_INSIGHTS:

            raise FinancialAIAnalysisError(
                "AI response must contain exactly "
                f"{self.MAX_INSIGHTS} insights."
            )

        validated_insights = []

        for index, insight in enumerate(
            insights,
            start=1,
        ):

            if not isinstance(
                insight,
                dict,
            ):

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is not a JSON object."
                )

            title = self._clean_text(
                insight.get(
                    "title"
                )
            )

            area = self._clean_text(
                insight.get(
                    "area"
                )
            )

            observation = self._clean_text(
                insight.get(
                    "observation"
                )
            )

            evidence = self._clean_text(
                insight.get(
                    "evidence"
                )
            )

            implication = self._clean_text(
                insight.get(
                    "implication"
                )
            )

            if not title:

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is missing a title."
                )

            if not area:

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is missing an area."
                )

            if not observation:

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is missing an observation."
                )

            if not evidence:

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is missing evidence."
                )

            if not implication:

                raise FinancialAIAnalysisError(
                    f"AI insight {index} is missing an implication."
                )

            validated_insights.append(
                {
                    "title": title,
                    "area": area,
                    "observation": observation,
                    "evidence": evidence,
                    "implication": implication,
                }
            )

        outlook = self._clean_text(
            result.get(
                "outlook"
            )
        )

        if not outlook:

            outlook = (
                "The outlook is based only on "
                "the financial data currently "
                "available in Angelix."
            )

        return {
            "summary": summary,
            "insights": validated_insights,
            "outlook": outlook,
        }

    # ==========================================================
    # TEXT NORMALIZATION
    # ==========================================================

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        """
        Convert an AI field into clean display text.
        """

        if value is None:

            return ""

        if isinstance(
            value,
            list,
        ):

            parts = []

            for item in value:

                if item is None:
                    continue

                item_text = str(
                    item
                ).strip()

                if item_text:

                    parts.append(
                        item_text
                    )

            return "; ".join(
                parts
            )

        if isinstance(
            value,
            dict,
        ):

            return json.dumps(
                value,
                ensure_ascii=False,
            )

        return str(
            value
        ).strip()