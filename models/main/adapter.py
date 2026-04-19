"""OpenAI Chat Completions adapter for the main gameplay model tier.

Wraps the OpenAI API for GPT-5.4 mini.
All inference calls are async; callers own the event loop.

Failure-safe: never raises on model errors — returns a failed GenerateResult
instead. Callers must check GenerateResult.success before using .text.

Per model_routing.md:
  - Latency target: < 5 s for narration calls in standard play
  - Hard timeout: configurable, default 30 s
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass
class GenerateResult:
    """Result of a single OpenAI inference call."""

    text: str = ""
    prompt_token_count: int = 0
    output_token_count: int = 0
    latency_ms: float = 0.0
    success: bool = False
    failure_reason: str = ""


class OpenAIMainAdapter:
    """Async HTTP adapter for the main gameplay model (OpenAI GPT-5.4 mini).

    Uses the OpenAI Chat Completions API via httpx (no SDK dependency).
    The API key is read from the OPENAI_API_KEY environment variable.

    Usage::

        adapter = OpenAIMainAdapter()
        result = await adapter.generate(prompt, system=system_prompt)
        if result.success:
            data = json.loads(result.text)
        else:
            # fall through to deterministic fallback
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._model = model
        self._timeout = timeout_seconds
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url.rstrip("/")

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        expect_json: bool = False,
        temperature: float = 0.7,
    ) -> GenerateResult:
        """Send a prompt to the main gameplay model and return a GenerateResult.

        Never raises. On any error, returns GenerateResult(success=False, ...).

        Args:
            prompt: The user-turn prompt to send.
            system: Optional system prompt prepended to the conversation.
            expect_json: When True, requests JSON output via response_format.
            temperature: Sampling temperature (default 0.7 for narrative
                quality; set lower for structured outputs like ruling proposals).
        """
        if not self._api_key:
            return GenerateResult(
                failure_reason="missing OPENAI_API_KEY",
            )

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return GenerateResult(
                latency_ms=latency_ms,
                failure_reason=f"timeout: {exc}",
            )
        except httpx.HTTPStatusError as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return GenerateResult(
                latency_ms=latency_ms,
                failure_reason=f"http_error: {exc.response.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.monotonic() - start) * 1000
            return GenerateResult(
                latency_ms=latency_ms,
                failure_reason=f"error: {exc}",
            )

        latency_ms = (time.monotonic() - start) * 1000

        # Extract text from Chat Completions response
        text = ""
        choices = data.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")

        # Extract token usage
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return GenerateResult(
            text=text,
            prompt_token_count=prompt_tokens,
            output_token_count=completion_tokens,
            latency_ms=latency_ms,
            success=True,
        )
