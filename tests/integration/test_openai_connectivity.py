"""Integration test: verify OPENAI_API_KEY is valid and gpt-5.4-mini is accessible.

This test makes a free /v1/models GET request (no tokens consumed) to confirm
the API key from the environment works and the target model is available.

Skipped automatically if OPENAI_API_KEY is not set.
"""

from __future__ import annotations

import os

import httpx
import pytest

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TARGET_MODEL = "gpt-5.4-mini"


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
@pytest.mark.asyncio
async def test_openai_api_key_valid():
    """GET /v1/models returns 200 — proves the key is accepted."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
@pytest.mark.asyncio
async def test_target_model_available():
    """GET /v1/models lists gpt-5.4-mini — confirms the adapter's default model exists."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
    assert resp.status_code == 200
    model_ids = [m["id"] for m in resp.json()["data"]]
    assert TARGET_MODEL in model_ids, (
        f"{TARGET_MODEL!r} not found in available models. "
        f"Available: {sorted(model_ids)[:10]}"
    )
