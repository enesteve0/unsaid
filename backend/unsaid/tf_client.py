"""Nebius Token Factory client.

One entry point, `TokenFactory.chat`, routes a request for a *role* (vision, reason, fast, classify) through that
role's model chain and handles the behaviours we measured on Token Factory:

* Nemotron thinks by default. Fast and structured calls switch it off with
  `chat_template_kwargs.enable_thinking=false`; reasoning calls get an explicit, generous token budget because a
  small budget returns HTTP 200 with empty content.
* Reasoning text arrives in `reasoning_content` (occasionally `reasoning`) and never mixes with the answer.
* `response_format` is never combined with `tools`.
* Structured answers are validated with pydantic and repaired once before falling back to the next model.
* 402 stops everything (credit exhausted); 401/403 tries the backup key; 404/409/410 retires a model for a while;
  429 honours Retry-After once; 5xx/529/timeouts open a short circuit breaker.

Every attempt, successful or not, is written to the run's ledger.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from .config import Role, Settings
from .ledger import Ledger, LedgerEntry

TIMEOUTS = {Role.VISION: 180.0, Role.REASON: 360.0, Role.FAST: 60.0, Role.CLASSIFY: 90.0}
CONCURRENCY = {Role.VISION: 4, Role.REASON: 2, Role.FAST: 8, Role.CLASSIFY: 4}
DEFAULT_MAX_TOKENS = {
    # (role, thinking) -> max_tokens. Reasoning tokens count against max_tokens.
    (Role.REASON, True): 24_000,
    (Role.REASON, False): 8_000,
    (Role.VISION, True): 8_000,
    (Role.VISION, False): 4_000,
    (Role.FAST, False): 1_024,
    (Role.FAST, True): 4_000,
    (Role.CLASSIFY, False): 4_000,
    (Role.CLASSIFY, True): 8_000,
}
BREAKER_SECONDS = 60.0
RETIRED_SECONDS = 600.0
MAX_RETRY_AFTER = 30.0


class TokenFactoryError(RuntimeError):
    pass


class CreditExhausted(TokenFactoryError):
    """HTTP 402. The caller switches the whole app to its labelled recorded fallback."""


class AuthFailure(TokenFactoryError):
    pass


class AllModelsFailed(TokenFactoryError):
    pass


@dataclass
class ChatResult:
    content: str
    reasoning: str
    model: str
    finish_reason: str
    message: Any
    tool_calls: list[Any] = field(default_factory=list)
    parsed: BaseModel | None = None


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Inline `$defs`, require every property and forbid extras, as strict structured output expects."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            out = {k: resolve(v) for k, v in node.items() if k not in ("title", "default")}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [resolve(n) for n in node]
        return node

    return resolve(schema)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> str:
    """Pull the JSON object out of a reply that may carry code fences or stray prose."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return cleaned
    return cleaned[start : end + 1]


def _reasoning_of(message: Any) -> str:
    for attr in ("reasoning_content", "reasoning"):
        value = getattr(message, attr, None)
        if value is None and getattr(message, "model_extra", None):
            value = message.model_extra.get(attr)
        if value:
            return str(value)
    return ""


def _usage_numbers(usage: Any) -> tuple[int, int, int, int]:
    if usage is None:
        return 0, 0, 0, 0
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    cdetails = getattr(usage, "completion_tokens_details", None)
    reasoning = (getattr(cdetails, "reasoning_tokens", 0) or 0) if cdetails else 0
    return prompt, cached, completion, reasoning


class TokenFactory:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        keys = [settings.api_key]
        if settings.provider == "tokenfactory" and settings.nebius_api_key_backup:
            keys.append(settings.nebius_api_key_backup)
        self._keys = [k for k in keys if k]
        self._key_index = 0
        self._http_client = http_client
        self._client = self._make_client()
        self._semaphores = {role: asyncio.Semaphore(n) for role, n in CONCURRENCY.items()}
        self._retired_until: dict[str, float] = {}
        self._breaker_until: dict[str, float] = {}

    def _make_client(self) -> AsyncOpenAI:
        key = self._keys[self._key_index] if self._keys else "missing-key"
        return AsyncOpenAI(
            api_key=key, base_url=self.settings.base_url, max_retries=0, http_client=self._http_client
        )

    def _available(self, model: str) -> bool:
        now = time.monotonic()
        return self._retired_until.get(model, 0) <= now and self._breaker_until.get(model, 0) <= now

    async def list_models(self) -> list[dict[str, Any]]:
        page = await self._client.models.list(extra_query={"verbose": "true"})
        return [m.model_dump() for m in page.data]

    async def chat(
        self,
        role: Role,
        messages: list[dict[str, Any]],
        *,
        stage: str,
        ledger: Ledger,
        thinking: bool = False,
        max_tokens: int | None = None,
        schema: type[BaseModel] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        temperature: float | None = None,
    ) -> ChatResult:
        if schema is not None and tools:
            raise ValueError("response_format and tools must not be combined on Token Factory")
        chain = self.settings.chain(role)
        last_error: Exception | None = None
        async with self._semaphores[role]:
            for model in chain:
                if not self._available(model):
                    continue
                try:
                    return await self._call_model(
                        role,
                        model,
                        messages,
                        stage=stage,
                        ledger=ledger,
                        thinking=thinking,
                        max_tokens=max_tokens,
                        schema=schema,
                        tools=tools,
                        tool_choice=tool_choice,
                        temperature=temperature,
                    )
                except (CreditExhausted, AuthFailure):
                    raise
                except Exception as exc:
                    last_error = exc
        raise AllModelsFailed(f"{role.value}: every model in {chain} failed: {last_error}")

    async def _call_model(
        self,
        role: Role,
        model: str,
        messages: list[dict[str, Any]],
        *,
        stage: str,
        ledger: Ledger,
        thinking: bool,
        max_tokens: int | None,
        schema: type[BaseModel] | None,
        tools: list[dict[str, Any]] | None,
        tool_choice: Any,
        temperature: float | None,
    ) -> ChatResult:
        convo = list(messages)
        use_thinking = thinking
        repaired = False
        rate_limited_once = False
        key_switched = False
        for _attempt in range(4):
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": convo,
                "max_tokens": max_tokens or DEFAULT_MAX_TOKENS[(role, use_thinking)],
                "temperature": temperature if temperature is not None else (0.6 if use_thinking else 0.2),
                "extra_body": {"chat_template_kwargs": {"enable_thinking": use_thinking}},
                "timeout": TIMEOUTS[role],
            }
            if use_thinking:
                kwargs["top_p"] = 0.95
            if tools:
                kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice
            if schema is not None:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "strict": True,
                        "schema": strict_json_schema(schema),
                    },
                }

            entry = LedgerEntry(stage=stage, role=role.value, model=model, thinking=use_thinking)
            started = time.perf_counter()
            try:
                raw = await self._client.chat.completions.with_raw_response.create(**kwargs)
                completion = raw.parse()
                entry.request_id = raw.headers.get("x-request-id", "") or getattr(completion, "id", "")
            except APIStatusError as exc:
                entry.ok, entry.error = False, f"HTTP {exc.status_code}"
                entry.latency_ms = int((time.perf_counter() - started) * 1000)
                ledger.add(entry)
                status = exc.status_code
                if status == 402:
                    raise CreditExhausted(str(exc)) from exc
                if status in (401, 403):
                    if not key_switched and self._key_index + 1 < len(self._keys):
                        self._key_index += 1
                        self._client = self._make_client()
                        key_switched = True
                        continue
                    raise AuthFailure(str(exc)) from exc
                if status in (404, 409, 410):
                    self._retired_until[model] = time.monotonic() + RETIRED_SECONDS
                    raise
                if status == 429:
                    retry_after = float(exc.response.headers.get("retry-after", "5") or 5)
                    if not rate_limited_once and retry_after <= MAX_RETRY_AFTER:
                        rate_limited_once = True
                        await asyncio.sleep(retry_after)
                        continue
                    raise
                self._breaker_until[model] = time.monotonic() + BREAKER_SECONDS
                raise
            except (APITimeoutError, APIConnectionError) as exc:
                entry.ok, entry.error = False, type(exc).__name__
                entry.latency_ms = int((time.perf_counter() - started) * 1000)
                ledger.add(entry)
                self._breaker_until[model] = time.monotonic() + BREAKER_SECONDS
                raise

            entry.latency_ms = int((time.perf_counter() - started) * 1000)
            prompt, cached, completion_tokens, reasoning_tokens = _usage_numbers(completion.usage)
            entry.prompt_tokens, entry.cached_tokens = prompt, cached
            entry.completion_tokens, entry.reasoning_tokens = completion_tokens, reasoning_tokens

            choice = completion.choices[0]
            message = choice.message
            content = (message.content or "").strip()
            tool_calls = list(message.tool_calls or [])
            finish = choice.finish_reason or ""

            if not content and not tool_calls:
                # Thinking consumed the budget (finish_reason "length") or the model returned nothing.
                entry.ok, entry.error = False, f"empty content (finish_reason={finish})"
                ledger.add(entry)
                if use_thinking and role is not Role.REASON:
                    use_thinking = False
                    continue
                if use_thinking and role is Role.REASON and not max_tokens:
                    max_tokens = 48_000
                    continue
                raise TokenFactoryError(entry.error)

            parsed: BaseModel | None = None
            if schema is not None:
                try:
                    parsed = schema.model_validate_json(extract_json(content))
                except ValidationError as exc:
                    entry.ok, entry.error = False, "schema validation failed"
                    ledger.add(entry)
                    if repaired:
                        raise
                    repaired = True
                    convo = [
                        *convo,
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": "That JSON did not match the schema. Errors: "
                            + json.dumps(exc.errors(include_url=False, include_context=False), default=str)[
                                :2000
                            ]
                            + ". Reply again with only the corrected JSON object.",
                        },
                    ]
                    continue

            ledger.add(entry)
            return ChatResult(
                content=content,
                reasoning=_reasoning_of(message),
                model=model,
                finish_reason=finish,
                message=message,
                tool_calls=tool_calls,
                parsed=parsed,
            )
        raise TokenFactoryError(f"{model}: gave up after repeated attempts")
