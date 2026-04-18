"""Ollama HTTP adapter for the main gameplay model tier.

Wraps the Ollama /api/generate endpoint for Gemma 4 26B A4B (gemma3:27b).
All inference calls are async; callers own the event loop.

Failure-safe: never raises on model errors — returns a failed GenerateResult
instead. Callers must check GenerateResult.success before using .text.

Per model_routing.md:
  - Latency target: < 5 s for narration calls in standard play
  - Hard timeout: configurable, default 30 s (generous for 26B model)
  - Context window: up to 256K tokens; keep prompts lean for latency
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:27b"
# 30 s default — the 26B model needs more headroom than the fast model.
# Standard narration should resolve well within this ceiling.
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class GenerateResult:
    """Result of a single Ollama inference call."""

    text: str = ""
    prompt_token_count: int = 0
    output_token_count: int = 0
    latency_ms: float = 0.0
    success: bool = False
    failure_reason: str = ""


class OllamaMainAdapter:
    """Async HTTP adapter for the main gameplay model (Ollama Gemma 4 26B A4B).

    Model name is configurable so callers can point at any Ollama model
    identifier (e.g. "gemma3:27b", "gemma3:latest") without code changes.

    Usage::

        adapter = OllamaMainAdapter()
        result = await adapter.generate(prompt, system=system_prompt)
        if result.success:
            data = json.loads(result.text)
        else:
            # fall through to deterministic fallback
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
            expect_json: When True, instructs Ollama to enforce JSON output.
            temperature: Sampling temperature (default 0.7 for narrative
                quality; set lower for structured outputs like ruling proposals).
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
            async with httpx.AsyncClient(timeout=self._timeout) as client:
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
