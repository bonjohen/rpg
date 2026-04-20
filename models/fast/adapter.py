"""Ollama HTTP adapter for the fast local model tier.

Wraps the Ollama /api/generate endpoint for qwen2.5:1.5b.
All inference calls are async; callers own the event loop.

Failure-safe: never raises on model errors — returns a failed GenerateResult
instead. Callers must check GenerateResult.success before using .text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
# Hard cap; the latency target per model_routing.md is < 500 ms but we allow
# up to 10 s to handle cold-start and first-token delay gracefully.
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass
class GenerateResult:
    """Result of a single Ollama inference call."""

    text: str = ""
    prompt_token_count: int = 0
    output_token_count: int = 0
    latency_ms: float = 0.0
    success: bool = False
    failure_reason: str = ""


class OllamaFastAdapter:
    """Async HTTP adapter for the fast local model (Ollama qwen2.5:1.5b).

    Usage::

        adapter = OllamaFastAdapter()
        result = await adapter.generate("Classify this: ...", expect_json=True)
        if result.success:
            data = json.loads(result.text)
        else:
            # fall back to deterministic default
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        expect_json: bool = False,
        temperature: float = 0.0,
    ) -> GenerateResult:
        """Send a prompt to the fast model and return a GenerateResult.

        Never raises. On any error, returns GenerateResult(success=False, ...).
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if expect_json:
            payload["format"] = "json"

        start = time.monotonic()
        try:
            client = self._get_client()
            response = await client.post(
                f"{self._base_url}/api/generate",
                json=payload,
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
        return GenerateResult(
            text=data.get("response", ""),
            prompt_token_count=data.get("prompt_eval_count", 0),
            output_token_count=data.get("eval_count", 0),
            latency_ms=latency_ms,
            success=True,
        )
