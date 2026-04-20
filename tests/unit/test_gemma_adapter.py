"""Unit tests for the Gemma 4 26B A4B main-tier adapter.

Tests cover:
  - Construction defaults and overrides
  - Missing GEMMA_BASE_URL returns failed GenerateResult
  - Protocol compliance (satisfies MainAdapter)
  - Successful generate with mocked HTTP response
  - Timeout, HTTP error, and connection error handling
  - API key header inclusion when configured
  - expect_json sets response_format in payload
  - Integration with main-tier tasks (via protocol)

All tests use mocked HTTP — no live Gemma instance required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from models.gemma.adapter import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    GemmaMainAdapter,
)
from models.main.adapter import GenerateResult
from models.protocol import MainAdapter


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestGemmaConstruction:
    def test_default_model(self):
        adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
        assert adapter.model == DEFAULT_MODEL

    def test_custom_model(self):
        adapter = GemmaMainAdapter(
            base_url="http://10.0.0.1:8000/v1",
            model="gemma-4-26b-custom",
        )
        assert adapter.model == "gemma-4-26b-custom"

    def test_base_url_trailing_slash_stripped(self):
        adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1/")
        assert adapter._base_url == "http://10.0.0.1:8000/v1"

    def test_default_timeout(self):
        adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
        assert adapter._timeout == DEFAULT_TIMEOUT_SECONDS

    def test_custom_timeout(self):
        adapter = GemmaMainAdapter(
            base_url="http://10.0.0.1:8000/v1",
            timeout_seconds=120.0,
        )
        assert adapter._timeout == 120.0

    def test_env_var_base_url(self):
        with patch.dict("os.environ", {"GEMMA_BASE_URL": "http://env:8000/v1"}):
            adapter = GemmaMainAdapter()
            assert adapter._base_url == "http://env:8000/v1"

    def test_explicit_base_url_overrides_env(self):
        with patch.dict("os.environ", {"GEMMA_BASE_URL": "http://env:8000/v1"}):
            adapter = GemmaMainAdapter(base_url="http://explicit:8000/v1")
            assert adapter._base_url == "http://explicit:8000/v1"

    def test_env_var_api_key(self):
        with patch.dict("os.environ", {"GEMMA_API_KEY": "sk-test"}):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            assert adapter._api_key == "sk-test"

    def test_no_api_key_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            assert adapter._api_key == ""


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_satisfies_main_adapter_protocol(self):
        adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
        assert isinstance(adapter, MainAdapter)


# ---------------------------------------------------------------------------
# Missing base URL
# ---------------------------------------------------------------------------


class TestMissingBaseUrl:
    @pytest.mark.asyncio
    async def test_returns_failure_when_no_base_url(self):
        with patch.dict("os.environ", {}, clear=True):
            adapter = GemmaMainAdapter()
            result = await adapter.generate("Hello")
            assert result.success is False
            assert "GEMMA_BASE_URL" in result.failure_reason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(text: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Build a mock httpx.Response with OpenAI-compatible JSON body."""
    body = {
        "choices": [{"message": {"content": text}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = body
    response.raise_for_status = MagicMock()
    return response


def _mock_client(response):
    """Return an AsyncMock that replaces httpx.AsyncClient context manager."""
    client = AsyncMock()
    client.post.return_value = response
    cm = AsyncMock()
    cm.__aenter__.return_value = client
    cm.__aexit__.return_value = None
    return cm, client


# ---------------------------------------------------------------------------
# Successful generate
# ---------------------------------------------------------------------------


class TestGenerateSuccess:
    @pytest.mark.asyncio
    async def test_returns_text_on_success(self):
        resp = _mock_response("Hello world")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Say hello")

        assert result.success is True
        assert result.text == "Hello world"
        assert result.prompt_token_count == 100
        assert result.output_token_count == 50
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_system_prompt_included_in_messages(self):
        resp = _mock_response("OK")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            await adapter.generate("Hello", system="You are a narrator.")

        call_kwargs = client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        messages = payload["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a narrator."

    @pytest.mark.asyncio
    async def test_expect_json_sets_response_format(self):
        resp = _mock_response('{"narration": "test"}')
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            await adapter.generate("Hello", expect_json=True)

        call_kwargs = client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_no_response_format_when_expect_json_false(self):
        resp = _mock_response("text output")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            await adapter.generate("Hello", expect_json=False)

        call_kwargs = client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "response_format" not in payload

    @pytest.mark.asyncio
    async def test_temperature_passed_through(self):
        resp = _mock_response("OK")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            await adapter.generate("Hello", temperature=0.3)

        call_kwargs = client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_api_key_sent_as_bearer_when_set(self):
        resp = _mock_response("OK")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(
                base_url="http://10.0.0.1:8000/v1",
                api_key="sk-test-key",
            )
            await adapter.generate("Hello")

        call_kwargs = client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_no_auth_header_when_no_api_key(self):
        resp = _mock_response("OK")
        cm, client = _mock_client(resp)

        with patch.dict("os.environ", {}, clear=True):
            with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
                adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
                await adapter.generate("Hello")

        call_kwargs = client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_posts_to_chat_completions_endpoint(self):
        resp = _mock_response("OK")
        cm, client = _mock_client(resp)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            await adapter.generate("Hello")

        url = client.post.call_args[0][0]
        assert url == "http://10.0.0.1:8000/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_empty_choices_returns_empty_text(self):
        body = {"choices": [], "usage": {}}
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = body
        response.raise_for_status = MagicMock()
        cm, _ = _mock_client(response)

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Hello")

        assert result.success is True
        assert result.text == ""


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGenerateErrors:
    @pytest.mark.asyncio
    async def test_timeout_returns_failure(self):
        cm = AsyncMock()
        client = AsyncMock()
        client.post.side_effect = httpx.TimeoutException("timed out")
        cm.__aenter__.return_value = client
        cm.__aexit__.return_value = None

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Hello")

        assert result.success is False
        assert "timeout" in result.failure_reason
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_http_error_returns_failure(self):
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        exc = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )

        cm = AsyncMock()
        client = AsyncMock()
        client.post.side_effect = exc
        cm.__aenter__.return_value = client
        cm.__aexit__.return_value = None

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Hello")

        assert result.success is False
        assert "http_error: 500" in result.failure_reason

    @pytest.mark.asyncio
    async def test_connect_error_returns_failure(self):
        cm = AsyncMock()
        client = AsyncMock()
        client.post.side_effect = httpx.ConnectError("Connection refused")
        cm.__aenter__.return_value = client
        cm.__aexit__.return_value = None

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Hello")

        assert result.success is False
        assert "connect_error" in result.failure_reason

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_failure(self):
        cm = AsyncMock()
        client = AsyncMock()
        client.post.side_effect = RuntimeError("unexpected")
        cm.__aenter__.return_value = client
        cm.__aexit__.return_value = None

        with patch("models.gemma.adapter.httpx.AsyncClient", return_value=cm):
            adapter = GemmaMainAdapter(base_url="http://10.0.0.1:8000/v1")
            result = await adapter.generate("Hello")

        assert result.success is False
        assert "unexpected" in result.failure_reason


# ---------------------------------------------------------------------------
# Integration: Gemma adapter works with main-tier tasks
# ---------------------------------------------------------------------------


class TestGemmaWithMainTasks:
    @pytest.mark.asyncio
    async def test_narrate_scene_accepts_gemma_adapter(self):
        """GemmaMainAdapter is accepted by narrate_scene via MainAdapter protocol."""
        from models.main.schemas import NarrationOutput
        from models.main.tasks import narrate_scene
        from tests.fixtures.main_model_fixtures import (
            VALID_NARRATION_JSON,
            make_tavern_scene,
        )

        adapter = MagicMock(spec=GemmaMainAdapter)
        adapter.model = DEFAULT_MODEL
        adapter.generate = AsyncMock(
            return_value=GenerateResult(
                text=VALID_NARRATION_JSON,
                prompt_token_count=100,
                output_token_count=50,
                latency_ms=800.0,
                success=True,
            )
        )
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [], trace_id="gemma-t1")

        assert isinstance(output, NarrationOutput)
        assert log.tier == "gemma"
        assert log.task_type == "scene_narration"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_gemma_fallback_on_failure(self):
        """GemmaMainAdapter failure triggers deterministic fallback."""
        from models.main.schemas import NarrationOutput
        from models.main.tasks import narrate_scene
        from tests.fixtures.main_model_fixtures import make_tavern_scene

        adapter = MagicMock(spec=GemmaMainAdapter)
        adapter.model = DEFAULT_MODEL
        adapter.generate = AsyncMock(
            return_value=GenerateResult(
                latency_ms=60_000.0,
                success=False,
                failure_reason="timeout: mock",
            )
        )
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [])

        assert isinstance(output, NarrationOutput)
        assert log.fallback_triggered is True
        assert log.tier == "gemma"

    @pytest.mark.asyncio
    async def test_gemma_tier_label_in_log(self):
        """The tier label is 'gemma' when using GemmaMainAdapter."""
        from models.main.tasks import narrate_scene
        from tests.fixtures.main_model_fixtures import (
            VALID_NARRATION_JSON,
            make_tavern_scene,
        )

        adapter = MagicMock(spec=GemmaMainAdapter)
        adapter.model = DEFAULT_MODEL
        adapter.generate = AsyncMock(
            return_value=GenerateResult(
                text=VALID_NARRATION_JSON,
                prompt_token_count=100,
                output_token_count=50,
                latency_ms=500.0,
                success=True,
            )
        )
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.tier == "gemma"
