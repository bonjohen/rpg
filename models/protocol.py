"""Shared adapter protocol for main-tier model adapters.

Any adapter that implements the MainAdapter protocol can be used by the
main-tier task functions (models.main.tasks) without modification. This
decouples the task pipeline from any specific backend (OpenAI, Gemma, etc.).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from models.main.adapter import GenerateResult


@runtime_checkable
class MainAdapter(Protocol):
    """Protocol that all main-tier adapters must satisfy."""

    @property
    def model(self) -> str: ...

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        expect_json: bool = False,
        temperature: float = 0.7,
    ) -> GenerateResult: ...
