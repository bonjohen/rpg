"""Gemma 4 26B A4B adapter for the main gameplay model tier.

Wraps an OpenAI-compatible Chat Completions endpoint (vLLM, llama.cpp
server, Ollama /v1, etc.) serving the google/gemma-4-26b-a4b-it model.

All inference calls are async; callers own the event loop.

Failure-safe: never raises on model errors — returns a failed GenerateResult
instead.  Callers must check GenerateResult.success before using .text.

Per model_routing.md:
  - Latency target: < 5 s for narration calls in standard play
  - Hard timeout: configurable, default 60 s (larger model on local network)
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from models.main.adapter import GenerateResult


DEFAULT_MODEL = "gemma-4-26b-a4b-it"
# Local-network inference server — no sensible default; require explicit config.
DEFAULT_BASE_URL = ""
# Gemma 26B on consumer hardware is slower than a cloud API; default higher.
DEFAULT_TIMEOUT_SECONDS = 60.0


class GemmaMainAdapter:
    """Async HTTP adapter for the Gemma 4 26B A4B main-tier model.

    Talks to any server that exposes an OpenAI-compatible
    ``/v1/chat/completions`` endpoint.  The base URL is read from the
    ``GEMMA_BASE_URL`` environment variable or passed directly.

    An API key is optional — most local inference servers don't require one.
    If ``GEMMA_API_KEY`` is set, it will be sent as a Bearer token.

    Usage::

        adapter = GemmaMainAdapter(base_url="http://192.168.1.50:8000/v1")
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
        base_url: str | None = None,
    ) -> None:
        resolved_url = base_url or os.environ.get("GEMMA_BASE_URL", DEFAULT_BASE_URL)
        self._base_url = resolved_url.rstrip("/") if resolved_url else ""
        self._model = model
        self._timeout = timeout_seconds
        self._api_key = api_key or os.environ.get("GEMMA_API_KEY", "")

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
        """Send a prompt to the Gemma model and return a GenerateResult.

        Never raises. On any error, returns GenerateResult(success=False, ...).

        Args:
            prompt: The user-turn prompt to send.
            system: Optional system prompt prepended to the conversation.
            expect_json: When True, requests JSON output via response_format
                if the server supports it.
            temperature: Sampling temperature (default 0.7 for narrative
                quality; set lower for structured outputs).
        """
        if not self._base_url:
            return GenerateResult(
                failure_reason="missing GEMMA_BASE_URL",
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

        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

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
        except httpx.ConnectError as exc:
            latency_ms = (time.monotonic() - start) * 1000
            return GenerateResult(
                latency_ms=latency_ms,
                failure_reason=f"connect_error: {exc}",
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
