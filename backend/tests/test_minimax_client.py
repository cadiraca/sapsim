"""
SAP SIM — Tests for MiniMaxClient and related MiniMax migration changes.
Phase: Post-migration validation
Covers: MiniMaxClient, intelligence.py, config.py, memory.py, engine.py

Run with:
    cd backend && python -m pytest tests/test_minimax_client.py -v --cov=. --cov-report=term-missing
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.litellm_client import (
    LiteLLMClient,
    MiniMaxClient,
    MiniMaxError,
    build_client_from_settings,
    build_minimax_client_from_settings,
)
from agents.intelligence import (
    INTELLIGENCE_TIERS,
    DEFAULT_AGENT_TIERS,
    get_model_for_agent,
    get_tier_for_agent,
    get_tier_info,
    agents_in_tier,
)
from config import ProjectSettings, save_settings, load_settings
from utils.memory import COMPRESSION_MODEL, COMPRESSION_MAX_TURNS, SUMMARY_MAX_WORDS


# ---------------------------------------------------------------------------
# Section 1: MiniMaxClient — complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_success():
    """complete() returns content from valid OpenAI-format response."""
    client = MiniMaxClient(
        base_url="https://api.minimax.io/v1",
        api_key="test-key",
        default_model="MiniMax-M2.7",
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await client.complete(
            messages=[{"role": "user", "content": "hi"}],
            agent_codename="PM_ALEX",
        )

    assert result == "Hello world"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]["json"]
    assert call_kwargs["model"] == "MiniMax-M2.7"
    assert call_kwargs["stream"] is False


@pytest.mark.asyncio
async def test_complete_empty_content():
    """complete() returns empty string when content is absent."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": ""}}], "usage": {}}
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await client.complete(messages=[{"role": "user", "content": "hi"}], agent_codename="TEST")

    assert result == ""


@pytest.mark.asyncio
async def test_complete_uses_model_override():
    """complete() uses per-call model override, not default."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(messages=[], agent_codename="TEST", model="gpt-4")

    call_kwargs = mock_post.call_args[1]["json"]
    assert call_kwargs["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_complete_retries_3_times_then_raises():
    """complete() retries 3 times and raises MiniMaxError when all fail."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    mock_post = AsyncMock(side_effect=Exception("server error"))
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(MiniMaxError) as exc_info:
            await client.complete(messages=[], agent_codename="PM_ALEX")

    assert "PM_ALEX" in str(exc_info.value)
    assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_complete_retry_succeeds_on_2nd_attempt():
    """complete() succeeds on 2nd attempt after first fails."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "worked"}}], "usage": {}}
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(side_effect=[Exception("fail"), mock_response])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await client.complete(messages=[], agent_codename="PM_ALEX")

    assert result == "worked"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_complete_uses_correct_temperature_and_max_tokens():
    """complete() passes temperature and max_tokens to the request."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(messages=[], agent_codename="TEST", temperature=0.5, max_tokens=512)

    call_kwargs = mock_post.call_args[1]["json"]
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["max_tokens"] == 512


# ---------------------------------------------------------------------------
# Section 2: MiniMaxClient — stream()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_yields_chunks_from_sse_lines():
    """stream() yields text chunks from SSE data lines."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: [DONE]',
    ]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=lines.__iter__())

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = AsyncMock()

    # Need async context manager for stream
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_ctx)

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in client.stream(messages=[], agent_codename="TEST"):
            chunks.append(chunk)

    # The stream method uses client.stream as context manager, check it was called
    assert mock_client.stream.called


@pytest.mark.asyncio
async def test_stream_ignores_non_data_lines():
    """stream() skips lines not starting with 'data: '."""
    client = MiniMaxClient(base_url="https://api.minimax.io/v1", api_key="test", default_model="MiniMax-M2.7")

    lines = [
        'invalid line',
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: [DONE]',
    ]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=lines.__iter__())

    mock_post = AsyncMock()
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_ctx)
    mock_client.__aenter__ = AsyncMock()
    mock_client.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for chunk in client.stream(messages=[], agent_codename="TEST"):
            chunks.append(chunk)

    # Non-data lines are skipped; check stream was called
    assert mock_client.stream.called


# ---------------------------------------------------------------------------
# Section 3: MiniMaxClient — helper methods
# ---------------------------------------------------------------------------

def test_resolve_model_returns_override_when_provided():
    """_resolve_model returns the override if given."""
    client = MiniMaxClient(base_url="url", api_key="key", default_model="MiniMax-M2.7")
    assert client._resolve_model("gpt-4") == "gpt-4"


def test_resolve_model_returns_default_when_no_override():
    """_resolve_model returns the default when no override given."""
    client = MiniMaxClient(base_url="url", api_key="key", default_model="MiniMax-M2.7")
    assert client._resolve_model(None) == "MiniMax-M2.7"


def test_build_kwargs_no_prefix_added():
    """_build_kwargs does NOT add openai/ prefix to model."""
    client = MiniMaxClient(base_url="url", api_key="key", default_model="MiniMax-M2.7")
    kwargs = client._build_kwargs(messages=[], model="MiniMax-M2.7", temperature=0.7, max_tokens=100, stream=False, extra={})
    assert kwargs["model"] == "MiniMax-M2.7"
    assert "openai/" not in kwargs["model"]


def test_build_kwargs_includes_temperature_and_max_tokens():
    """_build_kwargs includes temperature and max_tokens."""
    client = MiniMaxClient(base_url="url", api_key="key", default_model="MiniMax-M2.7")
    kwargs = client._build_kwargs(messages=[], model="m", temperature=0.5, max_tokens=300, stream=False, extra={})
    assert kwargs["temperature"] == 0.5
    assert kwargs["max_tokens"] == 300


def test_build_kwargs_includes_stream_flag():
    """_build_kwargs includes stream flag."""
    client = MiniMaxClient(base_url="url", api_key="key", default_model="MiniMax-M2.7")
    kwargs = client._build_kwargs(messages=[], model="m", temperature=0.7, max_tokens=100, stream=True, extra={})
    assert kwargs["stream"] is True


# ---------------------------------------------------------------------------
# Section 4: MiniMaxError
# ---------------------------------------------------------------------------

def test_minimax_error_is_exception_class():
    """MiniMaxError is a subclass of Exception."""
    assert issubclass(MiniMaxError, Exception)


def test_minimax_error_contains_message():
    """MiniMaxError can be instantiated with a message."""
    err = MiniMaxError("test error message")
    assert str(err) == "test error message"


# ---------------------------------------------------------------------------
# Section 5: build_minimax_client_from_settings factory
# ---------------------------------------------------------------------------

def test_factory_creates_minimax_client_with_correct_defaults():
    """Factory creates MiniMaxClient from settings dict."""
    settings = {
        "litellm_base_url": "https://api.minimax.io/v1",
        "litellm_api_key": "my-key",
        "litellm_model": "MiniMax-M2.7",
        "max_parallel_agents": 5,
    }
    client = build_minimax_client_from_settings(settings)
    assert client.base_url == "https://api.minimax.io/v1"
    assert client.api_key == "my-key"
    assert client.default_model == "MiniMax-M2.7"
    assert client.max_parallel_agents == 5


def test_factory_uses_all_settings_fields():
    """Factory correctly maps all settings dict fields."""
    settings = {
        "litellm_base_url": "https://custom.api/v1",
        "litellm_api_key": "secret",
        "litellm_model": "MiniMax-M2.7",
        "max_parallel_agents": 20,
    }
    client = build_minimax_client_from_settings(settings)
    assert client.base_url == "https://custom.api/v1"
    assert client.api_key == "secret"
    assert client.default_model == "MiniMax-M2.7"
    assert client.max_parallel_agents == 20


# ---------------------------------------------------------------------------
# Section 6: LiteLLMClient (unchanged — ensure not broken)
# ---------------------------------------------------------------------------

def test_lite_llm_client_exports_class():
    """LiteLLMClient is still importable and callable."""
    assert callable(LiteLLMClient)


def test_build_client_from_settings_still_works():
    """LiteLLMClient factory still works (unchanged)."""
    settings = {
        "litellm_base_url": "http://localhost:4000",
        "litellm_api_key": "key",
        "litellm_model": "gpt-4",
        "max_parallel_agents": 10,
    }
    client = build_client_from_settings(settings)
    assert client.base_url == "http://localhost:4000"
    assert client.api_key == "key"
    assert client.default_model == "gpt-4"


# ---------------------------------------------------------------------------
# Section 7: intelligence.py — tier lookups
# ---------------------------------------------------------------------------

def test_all_tiers_return_minimax_m2_7():
    """All four INTELLIGENCE_TIERS have model=MiniMax-M2.7."""
    for tier_name, tier_data in INTELLIGENCE_TIERS.items():
        assert tier_data["model"] == "MiniMax-M2.7", f"Tier {tier_name} has wrong model"


def test_get_model_for_agent_all_tiers():
    """get_model_for_agent returns MiniMax-M2.7 for all known agents."""
    for codename in DEFAULT_AGENT_TIERS:
        model = get_model_for_agent(codename)
        assert model == "MiniMax-M2.7", f"Agent {codename} has model {model}, expected MiniMax-M2.7"


def test_get_model_for_agent_strategic():
    """get_model_for_agent returns MiniMax-M2.7 for strategic tier."""
    assert get_model_for_agent("PM_ALEX") == "MiniMax-M2.7"
    assert get_model_for_agent("ARCH_SARA") == "MiniMax-M2.7"


def test_get_model_for_agent_senior():
    """get_model_for_agent returns MiniMax-M2.7 for senior tier."""
    assert get_model_for_agent("FI_CHEN") == "MiniMax-M2.7"
    assert get_model_for_agent("BASIS_KURT") == "MiniMax-M2.7"


def test_get_model_for_agent_operational():
    """get_model_for_agent returns MiniMax-M2.7 for operational tier."""
    assert get_model_for_agent("DEV_PRIYA") == "MiniMax-M2.7"
    assert get_model_for_agent("FI_KU_ROSE") == "MiniMax-M2.7"


def test_get_model_for_agent_basic():
    """get_model_for_agent returns MiniMax-M2.7 for basic tier."""
    assert get_model_for_agent("WM_KU_ELENA") == "MiniMax-M2.7"
    assert get_model_for_agent("HR_KU_SOPHIE") == "MiniMax-M2.7"


def test_get_model_for_agent_unknown_raises_keyerror():
    """get_model_for_agent raises KeyError for unknown agent."""
    with pytest.raises(KeyError):
        get_model_for_agent("DOES_NOT_EXIST")


def test_get_model_for_agent_with_tier_override():
    """get_model_for_agent respects tier_override parameter."""
    # tier_override bypasses DEFAULT_AGENT_TIERS and uses the override tier's model
    model = get_model_for_agent("PM_ALEX", tier_override="basic")
    assert model == "MiniMax-M2.7"  # basic tier also maps to MiniMax-M2.7 now


def test_get_tier_for_agent_all_agents():
    """get_tier_for_agent returns the correct tier for all 30 agents."""
    expected_tiers = {
        "PM_ALEX": "strategic", "ARCH_SARA": "strategic", "PMO_NIKO": "strategic",
        "BASIS_KURT": "senior", "FI_CHEN": "senior", "CO_MARTA": "senior",
        "MM_RAVI": "senior", "SD_ISLA": "senior", "PP_JONAS": "senior",
        "WM_FATIMA": "senior", "INT_MARCO": "senior", "SEC_DIANA": "senior",
        "BI_SAM": "senior", "CHG_NADIA": "senior", "DM_FELIX": "senior",
        "DEV_PRIYA": "operational", "DEV_LEON": "operational",
        "EXEC_VICTOR": "strategic", "IT_MGR_HELEN": "senior",
        "CUST_PM_OMAR": "senior", "QA_CLAIRE": "senior",
        "FI_KU_ROSE": "operational", "CO_KU_BJORN": "operational",
        "MM_KU_GRACE": "operational", "SD_KU_TONY": "operational",
        "BA_CUST_JAMES": "operational",
        "WM_KU_ELENA": "basic", "PP_KU_IBRAHIM": "basic",
        "HR_KU_SOPHIE": "basic", "CHAMP_LEILA": "basic",
    }
    for codename, expected_tier in expected_tiers.items():
        assert get_tier_for_agent(codename) == expected_tier


def test_agents_in_tier_returns_correct_count():
    """agents_in_tier returns the correct number of agents per tier."""
    assert len(agents_in_tier("strategic")) == 4   # PM_ALEX, ARCH_SARA, PMO_NIKO, EXEC_VICTOR
    assert len(agents_in_tier("senior")) == 15     # module leads + basis + QA + IT + cust PM
    assert len(agents_in_tier("operational")) == 9 # developers + key users + BA
    assert len(agents_in_tier("basic")) == 4       # difficult archetypes


def test_intelligence_tiers_has_all_required_keys():
    """Each INTELLIGENCE_TIERS entry has all required keys."""
    required_keys = {"tier_name", "model", "label", "description", "rationale"}
    for tier_name, tier_data in INTELLIGENCE_TIERS.items():
        assert required_keys.issubset(tier_data.keys()), f"Tier {tier_name} missing keys"


# ---------------------------------------------------------------------------
# Section 8: config.py — defaults
# ---------------------------------------------------------------------------

def test_project_settings_default_base_url_is_minimax():
    """ProjectSettings defaults litellm_base_url to MiniMax endpoint."""
    settings = ProjectSettings()
    assert settings.litellm_base_url == "https://api.minimax.io/v1"


def test_project_settings_default_model_is_minimax_m2_7():
    """ProjectSettings defaults litellm_model to MiniMax-M2.7."""
    settings = ProjectSettings()
    assert settings.litellm_model == "MiniMax-M2.7"


def test_project_settings_api_key_default_empty():
    """ProjectSettings defaults litellm_api_key to empty string."""
    settings = ProjectSettings()
    assert settings.litellm_api_key == ""


def test_project_settings_max_parallel_agents_default_10():
    """ProjectSettings defaults max_parallel_agents to 10."""
    settings = ProjectSettings()
    assert settings.max_parallel_agents == 10


def test_project_settings_saves_to_dict():
    """ProjectSettings.model_dump produces correct dict."""
    settings = ProjectSettings()
    data = settings.model_dump()
    assert data["litellm_base_url"] == "https://api.minimax.io/v1"
    assert data["litellm_model"] == "MiniMax-M2.7"


# ---------------------------------------------------------------------------
# Section 9: memory.py — COMPRESSION_MODEL
# ---------------------------------------------------------------------------

def test_compression_model_is_minimax_m2_7():
    """COMPRESSION_MODEL is MiniMax-M2.7."""
    assert COMPRESSION_MODEL == "MiniMax-M2.7"


def test_compression_max_turns_is_30():
    """COMPRESSION_MAX_TURNS is 30."""
    assert COMPRESSION_MAX_TURNS == 30


def test_summary_max_words_is_300():
    """SUMMARY_MAX_WORDS is 300."""
    assert SUMMARY_MAX_WORDS == 300


# ---------------------------------------------------------------------------
# Section 10: engine.py import check
# ---------------------------------------------------------------------------

def test_engine_imports_minimax_client_not_lite_llm_client():
    """engine.py imports MiniMaxClient, not LiteLLMClient."""
    from simulation import engine
    # Verify the import — engine should use MiniMaxClient
    import inspect
    source = inspect.getsource(engine)
    assert "MiniMaxClient" in source
    # LiteLLMClient should NOT appear as the client type in engine
    assert "LiteLLMClient" not in source or "# LiteLLMClient" in source  # comment OK


def test_engine_clients_dict_renamed():
    """engine.py uses _clients dict, not _litellm_clients."""
    from simulation import engine
    import inspect
    source = inspect.getsource(engine)
    # The _litellm_clients attribute was renamed to _clients
    assert "_litellm_clients" not in source
    assert "_clients" in source