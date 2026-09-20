"""
OpenRouter API client for Angelix.

This module provides a small OpenAI-compatible client wrapper
for the OpenRouter chat-completions API.

The client supports:
- JSON structured responses
- optional reasoning control
- defensive handling of provider/model response variations
- useful OpenRouter error messages
"""

from __future__ import annotations

from typing import Any

import httpx
from flask import current_app


class OpenRouterError(Exception):
    """
    Raised when an OpenRouter request cannot be completed.
    """


class OpenRouterClient:
    """
    Lightweight OpenRouter API client.
    """

    def __init__(self) -> None:
        self.key = current_app.config[
            "OPENROUTER_API_KEY"
        ]

        self.model = current_app.config[
            "OPENROUTER_MODEL"
        ]

        self.base = current_app.config[
            "OPENROUTER_BASE_URL"
        ].rstrip("/")

        self.timeout = current_app.config[
            "OPENROUTER_TIMEOUT_SECONDS"
        ]

    # ==========================================================
    # CHAT COMPLETION
    # ==========================================================

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 800,
        response_format: dict[str, Any] | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a chat-completion request to OpenRouter.

        Parameters
        ----------
        messages:
            OpenAI-compatible chat messages.

        temperature:
            Sampling temperature.

        max_tokens:
            Maximum number of generated tokens.

        response_format:
            Optional structured-output instruction.

            Example:

                {
                    "type": "json_object"
                }

        reasoning:
            Optional OpenRouter reasoning configuration.

            Example:

                {
                    "exclude": True
                }

        Returns
        -------
        str
            Assistant response content.

        Raises
        ------
        OpenRouterError
            If OpenRouter is not configured or returns an error.
        """

        if not self.key:
            raise OpenRouterError(
                "OpenRouter is not configured. "
                "OPENROUTER_API_KEY is missing."
            )

        if not self.model:
            raise OpenRouterError(
                "OpenRouter is not configured. "
                "OPENROUTER_MODEL is missing."
            )

        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Angelix Financial Intelligence Platform",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # ------------------------------------------------------
        # Structured output
        # ------------------------------------------------------

        if response_format is not None:
            payload["response_format"] = response_format

        # ------------------------------------------------------
        # Reasoning configuration
        #
        # This is especially useful with free routed models.
        # Excluding reasoning prevents reasoning tokens from
        # consuming the output budget needed for the JSON.
        # ------------------------------------------------------

        if reasoning is not None:
            payload["reasoning"] = reasoning

        try:
            response = httpx.post(
                f"{self.base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

        except httpx.TimeoutException as exc:
            raise OpenRouterError(
                "OpenRouter request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise OpenRouterError(
                f"Could not connect to OpenRouter: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise self._build_http_error(
                response
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise OpenRouterError(
                "OpenRouter returned an invalid JSON API response."
            ) from exc

        if not isinstance(data, dict):
            raise OpenRouterError(
                "OpenRouter returned an unexpected response format."
            )

        return self._extract_content(
            data
        )

    # ==========================================================
    # HTTP ERROR HANDLING
    # ==========================================================

    @staticmethod
    def _build_http_error(
        response: httpx.Response,
    ) -> OpenRouterError:
        """
        Build a useful OpenRouter error from an HTTP response.
        """

        status_code = response.status_code

        error_message = (
            f"AI provider returned HTTP {status_code}."
        )

        try:
            error_data = response.json()

        except ValueError:
            error_data = None

        if isinstance(
            error_data,
            dict,
        ):

            provider_error = error_data.get(
                "error"
            )

            if isinstance(
                provider_error,
                dict,
            ):

                message = provider_error.get(
                    "message"
                )

                if message:
                    error_message = (
                        f"OpenRouter error: {message}"
                    )

                metadata = provider_error.get(
                    "metadata"
                )

                if isinstance(
                    metadata,
                    dict,
                ):

                    raw_message = metadata.get(
                        "raw"
                    )

                    if raw_message:
                        error_message = (
                            f"{error_message} "
                            f"Provider details: "
                            f"{raw_message}"
                        )

            elif provider_error:

                error_message = (
                    f"OpenRouter error: "
                    f"{provider_error}"
                )

            elif error_data.get(
                "message"
            ):

                error_message = (
                    f"OpenRouter error: "
                    f"{error_data['message']}"
                )

        return OpenRouterError(
            error_message
        )

    # ==========================================================
    # RESPONSE EXTRACTION
    # ==========================================================

    @classmethod
    def _extract_content(
        cls,
        data: dict[str, Any],
    ) -> str:
        """
        Extract assistant content from an OpenRouter response.

        Different OpenAI-compatible models can return slightly
        different message structures, so this method handles
        common variants safely.
        """

        choices = data.get(
            "choices"
        )

        if not isinstance(
            choices,
            list,
        ) or not choices:

            error = cls._extract_api_error(
                data
            )

            if error:
                raise OpenRouterError(
                    f"OpenRouter error: {error}"
                )

            raise OpenRouterError(
                "OpenRouter returned no choices."
            )

        first_choice = choices[0]

        if not isinstance(
            first_choice,
            dict,
        ):

            raise OpenRouterError(
                "OpenRouter returned an invalid choice."
            )

        message = first_choice.get(
            "message"
        )

        if isinstance(
            message,
            dict,
        ):

            content = message.get(
                "content"
            )

            extracted = cls._normalize_content(
                content
            )

            if extracted:
                return extracted

            refusal = message.get(
                "refusal"
            )

            if refusal:
                raise OpenRouterError(
                    "OpenRouter model refused "
                    f"the request: {refusal}"
                )

        # ------------------------------------------------------
        # Some OpenAI-compatible providers expose text
        # directly on the choice.
        # ------------------------------------------------------

        text = first_choice.get(
            "text"
        )

        extracted = cls._normalize_content(
            text
        )

        if extracted:
            return extracted

        # ------------------------------------------------------
        # Provider error
        # ------------------------------------------------------

        provider_error = cls._extract_api_error(
            data
        )

        if provider_error:
            raise OpenRouterError(
                f"OpenRouter error: {provider_error}"
            )

        # ------------------------------------------------------
        # Finish reason
        # ------------------------------------------------------

        finish_reason = first_choice.get(
            "finish_reason"
        )

        if finish_reason:
            raise OpenRouterError(
                "OpenRouter returned an empty response. "
                f"Finish reason: {finish_reason}."
            )

        raise OpenRouterError(
            "OpenRouter returned an empty response."
        )

    # ==========================================================
    # CONTENT NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_content(
        content: Any,
    ) -> str | None:
        """
        Normalize possible content representations.

        Supported forms include:

        - plain string
        - list of content blocks
        - dictionaries containing text
        """

        if content is None:
            return None

        if isinstance(
            content,
            str,
        ):

            cleaned = content.strip()

            return cleaned or None

        if isinstance(
            content,
            list,
        ):

            parts: list[str] = []

            for item in content:

                if isinstance(
                    item,
                    str,
                ):

                    value = item.strip()

                    if value:
                        parts.append(
                            value
                        )

                    continue

                if isinstance(
                    item,
                    dict,
                ):

                    text_value = item.get(
                        "text"
                    )

                    if isinstance(
                        text_value,
                        str,
                    ):

                        value = (
                            text_value.strip()
                        )

                        if value:
                            parts.append(
                                value
                            )

                    elif isinstance(
                        text_value,
                        dict,
                    ):

                        nested = (
                            text_value.get(
                                "value"
                            )
                        )

                        if isinstance(
                            nested,
                            str,
                        ):

                            value = (
                                nested.strip()
                            )

                            if value:
                                parts.append(
                                    value
                                )

            if parts:
                return "\n".join(
                    parts
                ).strip()

            return None

        if isinstance(
            content,
            dict,
        ):

            for key in (
                "text",
                "value",
                "content",
            ):

                value = content.get(
                    key
                )

                if isinstance(
                    value,
                    str,
                ):

                    cleaned = value.strip()

                    if cleaned:
                        return cleaned

        return None

    # ==========================================================
    # API ERROR EXTRACTION
    # ==========================================================

    @staticmethod
    def _extract_api_error(
        data: dict[str, Any],
    ) -> str | None:
        """
        Extract an error message embedded in a successful
        HTTP response body.
        """

        error_data = data.get(
            "error"
        )

        if isinstance(
            error_data,
            dict,
        ):

            message = error_data.get(
                "message"
            )

            if message:
                return str(
                    message
                )

        if error_data:
            return str(
                error_data
            )

        message = data.get(
            "message"
        )

        if message:
            return str(
                message
            )

        return None