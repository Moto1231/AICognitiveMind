"""Optional, lazy provider adapter with a shared quota circuit breaker."""

import asyncio
from collections import deque
from time import time
from typing import Any


class ProviderUnavailable(RuntimeError):
    pass


class StandaloneRuntime:
    def __init__(self, settings: Any, records: Any = None) -> None:
        self.settings = settings
        self.records = records
        self.provider = settings.effective_standalone_reasoning_provider
        self.model = "not started"
        self.engine: Any = None
        self.interpreter: Any = None
        self._lock = asyncio.Lock()
        self._until = 0.0
        self._calls: deque[float] = deque()

    async def _start(self) -> None:
        if self.engine is not None:
            return
        from aicognitive_mind.embodiment import (
            GeminiPerceptInterpreter,
            OpenAIPerceptInterpreter,
            SummaryPerceptInterpreter,
        )
        from aicognitive_mind.engines import (
            EchoReasoningEngine,
            GeminiReasoningEngine,
            OpenAIReasoningEngine,
            resolve_gemini_model,
        )

        settings = self.settings
        if self.provider == "disabled":
            raise ProviderUnavailable("Standalone fallback is disabled; attach an external host.")
        if self.provider == "gemini":
            if not settings.gemini_api_key:
                raise ProviderUnavailable("Standalone Gemini credentials are not configured.")
            await self._reserve()
            self.model = await resolve_gemini_model(settings.gemini_api_key, settings.gemini_model)
            self.engine = GeminiReasoningEngine(settings.gemini_api_key, self.model)
            self.interpreter = GeminiPerceptInterpreter(settings.gemini_api_key, model=self.model)
        elif self.provider == "openai":
            if not settings.openai_api_key:
                raise ProviderUnavailable("Standalone OpenAI credentials are not configured.")
            self.model = settings.openai_model
            self.engine = OpenAIReasoningEngine(settings.openai_api_key, self.model)
            self.interpreter = OpenAIPerceptInterpreter(
                settings.openai_api_key,
                vision_model=self.model,
                transcription_model=settings.openai_transcription_model,
            )
        elif self.provider == "echo":
            self.model = "deterministic-echo"
            self.engine, self.interpreter = EchoReasoningEngine(), SummaryPerceptInterpreter()
        else:
            raise ProviderUnavailable("Unknown standalone reasoning provider")
        for target in (self.engine, self.interpreter):
            if hasattr(target, "_client"):
                target._client = MeteredClient(target._client, self)

    async def _reserve(self) -> None:
        now = time()
        if self.records:
            key = "provider_budget_" + self.provider
            for _ in range(10):
                before = await self.records.get(key)
                if before is None:
                    try:
                        await self.records.create(key, {"calls": [], "until": 0.0, "revision": 0})
                    except Exception:
                        if await self.records.get(key) is None:
                            raise
                    continue
                if now < before["until"]:
                    raise ProviderUnavailable(
                        "Standalone provider is cooling down after a quota failure."
                    )
                calls = [tick for tick in before["calls"] if tick > now - 60]
                if len(calls) >= self.settings.standalone_calls_per_minute:
                    raise ProviderUnavailable(
                        "Standalone request budget reached; wait before retrying."
                    )
                after = {**before, "calls": [*calls, now], "revision": before["revision"] + 1}
                if await self.records.replace(key, before, after):
                    return
            raise ProviderUnavailable("Provider budget is busy; retry later")
        if now < self._until:
            raise ProviderUnavailable("Standalone provider is cooling down after a quota failure.")
        while self._calls and self._calls[0] <= now - 60:
            self._calls.popleft()
        if len(self._calls) >= self.settings.standalone_calls_per_minute:
            raise ProviderUnavailable("Standalone request budget reached; wait before retrying.")
        self._calls.append(now)

    async def _admit(self) -> None:
        async with self._lock:
            if time() < self._until:
                raise ProviderUnavailable(
                    "Standalone provider is cooling down after a quota failure."
                )
            try:
                await asyncio.wait_for(self._start(), self.settings.reasoning_timeout_seconds)
            except Exception as exc:
                await self._failure(exc)
                raise

    async def _failure(self, exc: Exception) -> None:
        if getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == 429:
            self._until = time() + self.settings.standalone_quota_cooldown_seconds
            if self.records:
                key = "provider_budget_" + self.provider
                for _ in range(10):
                    before = await self.records.get(key)
                    if before is None:
                        return
                    if await self.records.replace(
                        key,
                        before,
                        {**before, "until": self._until, "revision": before["revision"] + 1},
                    ):
                        return
                raise ProviderUnavailable("Could not persist provider cooldown")

    async def propose(self, request: Any, tools: tuple = ()) -> Any:
        await self._admit()
        try:
            return await asyncio.wait_for(
                self.engine.propose(request, tools), self.settings.reasoning_timeout_seconds
            )
        except Exception as exc:
            await self._failure(exc)
            raise

    async def interpret(self, percept: Any, *, focus: str | None = None) -> str:
        await self._admit()
        try:
            return await asyncio.wait_for(
                self.interpreter.interpret(percept, focus=focus),
                self.settings.reasoning_timeout_seconds,
            )
        except Exception as exc:
            await self._failure(exc)
            raise


class MeteredClient:
    """Count every SDK inference call, including tool rounds and evidence reviews."""

    def __init__(self, client: Any, owner: StandaloneRuntime) -> None:
        self.client, self.owner = client, owner

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.client, name)
        if name in {"create", "generate_content"} and callable(value):

            async def call(*args: Any, **kwargs: Any) -> Any:
                await self.owner._reserve()
                try:
                    return await value(*args, **kwargs)
                except Exception as exc:
                    await self.owner._failure(exc)
                    raise

            return call
        return MeteredClient(value, self.owner)
