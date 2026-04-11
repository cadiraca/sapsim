"""
SAP SIM — LiteLLM Client
Phase: 1.4
Purpose: Async LiteLLM completion wrapper with streaming, retries (max 3, exponential
         backoff), structured logging (agent codename, tokens, latency), and per-call
         model override support.
Dependencies: litellm, config, logging, asyncio
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional

import litellm
from litellm import acompletion

logger = logging.getLogger(__name__)


class LiteLLMError(Exception):
    """Raised when all retry attempts are exhausted or a non-retryable error occurs."""


class LiteLLMClient:
    """
    Async wrapper around LiteLLM completion calls.

    Supports:
    - Streaming via async generator
    - Automatic retries (max 3, exponential backoff: 1s, 2s, 4s)
    - Structured logging per call (agent codename, tokens, latency, model)
    - Per-call model override
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str,
        max_parallel_agents: int = 10,
    ):
        """
        Initialise the client.

        Args:
            base_url: LiteLLM / OpenAI-compatible gateway base URL.
            api_key: API key for the gateway.
            default_model: Default model identifier (e.g. "claude-4-6-opus").
            max_parallel_agents: Not enforced here; passed for context / logging.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.max_parallel_agents = max_parallel_agents

        # Configure LiteLLM globally for this process
        litellm.api_base = self.base_url
        litellm.api_key = self.api_key

    # ------------------------------------------------------------------
    # Public: Non-streaming completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        *,
        agent_codename: str = "UNKNOWN",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        extra_kwargs: Optional[dict] = None,
    ) -> str:
        """
        Call LiteLLM and return the full response text.

        Args:
            messages: OpenAI-style message list [{"role": ..., "content": ...}].
            agent_codename: Codename of the calling agent (used in logs only).
            model: Override the default model for this call.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            extra_kwargs: Additional kwargs forwarded to acompletion().

        Returns:
            The assistant's reply as a plain string.

        Raises:
            LiteLLMError: After all retries are exhausted.
        """
        resolved_model = self._resolve_model(model)
        kwargs = self._build_kwargs(
            messages=messages,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            extra=extra_kwargs or {},
        )

        for attempt in range(1, self.MAX_RETRIES + 1):
            start = time.monotonic()
            try:
                response = await acompletion(**kwargs)
                latency = time.monotonic() - start
                usage = getattr(response, "usage", None)
                self._log_call(
                    agent_codename=agent_codename,
                    model=resolved_model,
                    latency=latency,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    attempt=attempt,
                    streaming=False,
                )
                return response.choices[0].message.content or ""

            except Exception as exc:
                latency = time.monotonic() - start
                logger.warning(
                    "[%s] attempt %d/%d failed after %.2fs — %s: %s",
                    agent_codename,
                    attempt,
                    self.MAX_RETRIES,
                    latency,
                    type(exc).__name__,
                    exc,
                )
                if attempt == self.MAX_RETRIES:
                    raise LiteLLMError(
                        f"[{agent_codename}] All {self.MAX_RETRIES} attempts failed. "
                        f"Last error: {exc}"
                    ) from exc
                delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("[%s] Retrying in %.1fs…", agent_codename, delay)
                await asyncio.sleep(delay)

        # Should be unreachable
        raise LiteLLMError(f"[{agent_codename}] Unexpected exit from retry loop.")

    # ------------------------------------------------------------------
    # Public: Streaming completion
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[dict],
        *,
        agent_codename: str = "UNKNOWN",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        extra_kwargs: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Call LiteLLM in streaming mode and yield text chunks as they arrive.

        Retries restart the stream from the beginning on failure.  If all
        retries are exhausted the generator raises LiteLLMError.

        Args:
            messages: OpenAI-style message list.
            agent_codename: Codename of the calling agent.
            model: Optional per-call model override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            extra_kwargs: Additional kwargs forwarded to acompletion().

        Yields:
            Text delta strings as they arrive from the model.

        Raises:
            LiteLLMError: After all retries are exhausted.
        """
        resolved_model = self._resolve_model(model)
        kwargs = self._build_kwargs(
            messages=messages,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            extra=extra_kwargs or {},
        )

        for attempt in range(1, self.MAX_RETRIES + 1):
            start = time.monotonic()
            total_tokens_estimate = 0
            try:
                response = await acompletion(**kwargs)
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None) or ""
                    if text:
                        total_tokens_estimate += len(text.split())  # rough estimate
                        yield text

                latency = time.monotonic() - start
                self._log_call(
                    agent_codename=agent_codename,
                    model=resolved_model,
                    latency=latency,
                    prompt_tokens=0,  # not available mid-stream
                    completion_tokens=total_tokens_estimate,
                    attempt=attempt,
                    streaming=True,
                )
                return  # success — stop generator

            except GeneratorExit:
                return

            except Exception as exc:
                latency = time.monotonic() - start
                logger.warning(
                    "[%s] stream attempt %d/%d failed after %.2fs — %s: %s",
                    agent_codename,
                    attempt,
                    self.MAX_RETRIES,
                    latency,
                    type(exc).__name__,
                    exc,
                )
                if attempt == self.MAX_RETRIES:
                    raise LiteLLMError(
                        f"[{agent_codename}] All {self.MAX_RETRIES} stream attempts failed. "
                        f"Last error: {exc}"
                    ) from exc
                delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("[%s] Retrying stream in %.1fs…", agent_codename, delay)
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, override: Optional[str]) -> str:
        """Return the override model if provided, otherwise the client default."""
        return override if override else self.default_model

    def _build_kwargs(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
        extra: dict,
    ) -> dict:
        """
        Assemble the keyword arguments for litellm.acompletion().

        Uses openai/<model> prefix so LiteLLM routes via the configured base_url
        instead of hitting the real OpenAI endpoint.
        """
        base = {
            "model": f"openai/{model}",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "api_base": self.base_url,
            "api_key": self.api_key,
        }
        base.update(extra)
        return base

    def _log_call(
        self,
        agent_codename: str,
        model: str,
        latency: float,
        prompt_tokens: int,
        completion_tokens: int,
        attempt: int,
        streaming: bool,
    ) -> None:
        """Emit a structured log entry for every successful LiteLLM call."""
        logger.info(
            "[LiteLLM] agent=%s model=%s latency=%.3fs "
            "prompt_tokens=%d completion_tokens=%d total_tokens=%d "
            "attempt=%d streaming=%s",
            agent_codename,
            model,
            latency,
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            attempt,
            streaming,
        )


# ------------------------------------------------------------------
# Module-level factory — builds a client from a project settings dict
# ------------------------------------------------------------------

def build_client_from_settings(settings: dict) -> LiteLLMClient:
    """
    Convenience factory.  Pass the dict loaded from projects/{name}/settings.json.

    Required keys:
        litellm_base_url, litellm_api_key, litellm_model
    Optional keys:
        max_parallel_agents (default 10)
    """
    return LiteLLMClient(
        base_url=settings["litellm_base_url"],
        api_key=settings["litellm_api_key"],
        default_model=settings["litellm_model"],
        max_parallel_agents=settings.get("max_parallel_agents", 10),
    )
