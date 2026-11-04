"""Responses API contract and provider selection tests; no network or API credits."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from loguru import logger
from pydantic import ValidationError

from telegram_bot.config import Settings
from telegram_bot.services.ai_model import OpenAIModel, create_ai_model


@pytest.fixture(autouse=True)
def isolate_provider_environment(monkeypatch):
    for name in (
        "AI_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_REASONING_EFFORT",
        "OPENAI_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def completed(*blocks):
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "status": "completed", "content": list(blocks)},
        ],
    }


def output(text="Summary"):
    return {"type": "output_text", "text": text}


def model_for(handler, **kwargs):
    return OpenAIModel(
        "secret-api-key", transport=httpx.MockTransport(handler), **kwargs
    )


@pytest.mark.asyncio
async def test_responses_contract_and_multiple_output_blocks():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer secret-api-key"
        assert json.loads(request.content) == {
            "model": "gpt-6.1-sol",
            "input": "private transcript",
            "max_output_tokens": 16000,
            "reasoning": {"effort": "low"},
            "store": False,
        }
        return httpx.Response(200, json=completed(output("First"), output("Second")))

    assert (
        await model_for(handler).generate_text("private transcript", max_tokens=16000)
        == "First\nSecond"
    )


@pytest.mark.asyncio
async def test_custom_model_and_reasoning_effort():
    def handler(request):
        data = json.loads(request.content)
        assert data["model"] == "custom-model"
        assert data["reasoning"] == {"effort": "medium"}
        assert data["max_output_tokens"] == 8000
        return httpx.Response(200, json=completed(output()))

    assert (
        await model_for(
            handler, model_name="custom-model", reasoning_effort="medium"
        ).generate_text("x")
        == "Summary"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"status": "incomplete", "output": completed(output())["output"]},
        {"status": "failed", "error": {"message": "private transcript"}},
        completed({"type": "refusal", "refusal": "No"}),
        completed(output("Text"), {"type": "refusal", "refusal": "No"}),
        completed(output("   ")),
        {"status": "completed", "output": [{"type": "reasoning"}]},
        {
            "status": "completed",
            "output": [
                {"type": "message", "status": "in_progress", "content": [output()]}
            ],
        },
        {"status": "completed", "output": None},
    ],
)
async def test_rejects_unusable_outputs(body):
    assert (
        await model_for(lambda r: httpx.Response(200, json=body)).generate_text("x")
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error",
    [
        (401, {"message": "secret-api-key"}),
        (403, {}),
        (400, {}),
        (429, {"code": "insufficient_quota"}),
        (429, {"type": "insufficient_quota"}),
        (429, {"code": "credit_balance_exhausted"}),
        (429, {"type": "credit_balance_exhausted"}),
    ],
)
async def test_permanent_errors_do_not_retry_or_log_credentials(status, error):
    calls = []
    logs = []
    sink = logger.add(lambda m: logs.append(str(m)))
    try:

        def handler(request):
            calls.append(request)
            return httpx.Response(status, json={"error": error})

        assert await model_for(handler).generate_text("private transcript") is None
    finally:
        logger.remove(sink)
    assert len(calls) == 1
    combined = "".join(logs)
    assert "secret-api-key" not in combined
    assert "private transcript" not in combined
    assert f"HTTP {status}" in combined


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_transient_http_errors_retry_bounded(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": "rate_limit_exceeded"}})

    with patch("telegram_bot.services.ai_model.asyncio.sleep", new_callable=AsyncMock):
        assert await model_for(handler).generate_text("x") is None
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_recovers_from_transient_error():
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, json=completed(output()))
        )

    with patch("telegram_bot.services.ai_model.asyncio.sleep", new_callable=AsyncMock):
        assert await model_for(handler).generate_text("x") == "Summary"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_transport_timeout_retries_bounded_without_exception_secrets():
    calls = []
    logs = []
    sink = logger.add(lambda m: logs.append(str(m)))
    try:

        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout(
                "secret-api-key private transcript", request=request
            )

        with patch(
            "telegram_bot.services.ai_model.asyncio.sleep", new_callable=AsyncMock
        ):
            assert await model_for(handler).generate_text("x") is None
    finally:
        logger.remove(sink)
    assert len(calls) == 3
    assert "ReadTimeout" in "".join(logs)
    assert "secret-api-key" not in "".join(logs)
    assert "private transcript" not in "".join(logs)


@pytest.mark.asyncio
async def test_whole_request_has_absolute_deadline():
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=completed(output()))

    assert await model_for(handler, timeout_seconds=0.01).generate_text("x") is None


@pytest.mark.asyncio
async def test_invalid_json_is_rejected():
    assert (
        await model_for(lambda r: httpx.Response(200, text="not json")).generate_text(
            "x"
        )
        is None
    )


def settings(**kwargs):
    values = {
        "ai_provider": "auto",
        "google_api_key": "",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "gemini_model": "legacy-gemini",
        "claude_model": "legacy-claude",
        "openai_model": "gpt-6.1-sol",
        "openai_reasoning_effort": "low",
        "openai_timeout_seconds": 120.0,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_explicit_openai_overrides_stale_gemini_and_claude_keys():
    with patch(
        "telegram_bot.services.ai_model.get_settings",
        return_value=settings(
            ai_provider="openai",
            openai_api_key="openai-key",
            google_api_key="deleted-key",
            anthropic_api_key="old-key",
        ),
    ):
        model = create_ai_model()
    assert isinstance(model, OpenAIModel)
    assert model.api_key == "openai-key"


@pytest.mark.parametrize(
    "provider,key_field,key_env",
    [
        ("openai", "openai_api_key", "OPENAI_API_KEY"),
        ("gemini", "google_api_key", "GOOGLE_API_KEY"),
        ("claude", "anthropic_api_key", "ANTHROPIC_API_KEY"),
    ],
)
def test_explicit_provider_requires_its_own_key(provider, key_field, key_env):
    keys = {
        "google_api_key": "google",
        "anthropic_api_key": "anthropic",
        "openai_api_key": "openai",
    }
    keys[key_field] = ""
    with patch(
        "telegram_bot.services.ai_model.get_settings",
        return_value=settings(ai_provider=provider, **keys),
    ):
        with pytest.raises(ValueError, match=key_env):
            create_ai_model()


def test_auto_accepts_openai_only():
    with patch(
        "telegram_bot.services.ai_model.get_settings",
        return_value=settings(openai_api_key="openai"),
    ):
        assert isinstance(create_ai_model(), OpenAIModel)


@pytest.mark.parametrize(
    "keys,expected",
    [
        (
            {
                "google_api_key": "google",
                "anthropic_api_key": "anthropic",
                "openai_api_key": "openai",
            },
            "GeminiModel",
        ),
        ({"anthropic_api_key": "anthropic", "openai_api_key": "openai"}, "ClaudeModel"),
    ],
)
def test_auto_preserves_legacy_priority(keys, expected):
    with patch(
        "telegram_bot.services.ai_model.get_settings", return_value=settings(**keys)
    ):
        with patch(f"telegram_bot.services.ai_model.{expected}") as constructor:
            assert create_ai_model() is constructor.return_value


def test_new_config_defaults_and_validation():
    base = {
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_API_ID": 1,
        "TELEGRAM_API_HASH": "hash",
        "DEEPGRAM_API_KEY": "deepgram",
        "_env_file": None,
    }
    config = Settings(**base)
    assert config.ai_provider == "auto"
    assert config.openai_api_key == ""
    assert config.openai_model == "gpt-6.1-sol"
    assert config.openai_reasoning_effort == "low"
    assert config.openai_timeout_seconds == 120
    assert (
        Settings(**base, OPENAI_REASONING_EFFORT="max").openai_reasoning_effort == "max"
    )
    for invalid in (
        {"AI_PROVIDER": "typo"},
        {"OPENAI_TIMEOUT_SECONDS": 0},
        {"OPENAI_REASONING_EFFORT": "minimal"},
        {"OPENAI_REASONING_EFFORT": "none"},
    ):
        with pytest.raises(ValidationError):
            Settings(**base, **invalid)


@pytest.mark.asyncio
async def test_gemini_supports_rag_token_limit():
    from telegram_bot.services.ai_model import GeminiModel

    with patch("telegram_bot.services.ai_model.genai.Client") as client:
        client.return_value.aio.models.generate_content = AsyncMock()
        client.return_value.aio.models.generate_content.return_value.text = "Result"
        assert (
            await GeminiModel("key").generate_text("prompt", max_tokens=16000)
            == "Result"
        )
        client.return_value.aio.models.generate_content.assert_awaited_once_with(
            model="gemini-3-pro-preview",
            contents=["prompt"],
            config={"max_output_tokens": 16000},
        )
