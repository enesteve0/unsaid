import json

import httpx
import pytest
from pydantic import BaseModel

from unsaid.config import Role, Settings
from unsaid.ledger import Ledger
from unsaid.schemas import LessonBible
from unsaid.tf_client import CreditExhausted, TokenFactory, extract_json, strict_json_schema

URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"


def completion(
    content, *, model="m", finish="stop", reasoning=None, prompt=100, completion_tokens=20, cached=0
):
    message = {"role": "assistant", "content": content}
    if reasoning:
        message["reasoning_content"] = reasoning
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt + completion_tokens,
            "prompt_tokens_details": {"cached_tokens": cached},
        },
    }


def make_tf(*responses):
    """TokenFactory wired to a mock transport that replays `responses` in order and records requests."""
    queue, seen = list(responses), []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == URL
        seen.append(json.loads(request.content))
        return queue.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(nebius_api_key="test-key", _env_file=None)
    return TokenFactory(settings, http_client=client), seen


class Answer(BaseModel):
    value: int


async def test_fast_call_turns_thinking_off_and_records_ledger():
    tf, seen = make_tf(httpx.Response(200, json=completion("hello", cached=40)))
    ledger = Ledger()
    result = await tf.chat(Role.FAST, [{"role": "user", "content": "hi"}], stage="t", ledger=ledger)
    body = seen[0]
    assert body["model"] == "nvidia/Nemotron-3_5-Lightning"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert result.content == "hello"
    assert ledger.entries[0].prompt_tokens == 100 and ledger.entries[0].cached_tokens == 40
    assert ledger.entries[0].ok


async def test_empty_content_with_thinking_retries_without_thinking():
    tf, _ = make_tf(
        httpx.Response(200, json=completion("", finish="length", reasoning="thinking...")),
        httpx.Response(200, json=completion("done")),
    )
    ledger = Ledger()
    result = await tf.chat(
        Role.FAST, [{"role": "user", "content": "x"}], stage="t", ledger=ledger, thinking=True
    )
    assert result.content == "done"
    assert [e.thinking for e in ledger.entries] == [True, False]
    assert not ledger.entries[0].ok


async def test_retired_model_falls_back_to_next_in_chain():
    tf, seen = make_tf(
        httpx.Response(404, json={"error": {"message": "model_not_found"}}),
        httpx.Response(200, json=completion("ok")),
    )
    ledger = Ledger()
    result = await tf.chat(Role.FAST, [{"role": "user", "content": "x"}], stage="t", ledger=ledger)
    models = [body["model"] for body in seen]
    assert models == ["nvidia/Nemotron-3_5-Lightning", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"]
    assert result.model == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


async def test_credit_exhausted_stops_immediately():
    tf, _ = make_tf(httpx.Response(402, json={"error": {"code": "credit_balance_exhausted"}}))
    with pytest.raises(CreditExhausted):
        await tf.chat(Role.FAST, [{"role": "user", "content": "x"}], stage="t", ledger=Ledger())


async def test_schema_is_repaired_once():
    tf, seen = make_tf(
        httpx.Response(200, json=completion('{"value": "not a number"}')),
        httpx.Response(200, json=completion('```json\n{"value": 7}\n```')),
    )
    ledger = Ledger()
    result = await tf.chat(
        Role.CLASSIFY, [{"role": "user", "content": "x"}], stage="t", ledger=ledger, schema=Answer
    )
    assert result.parsed.value == 7
    assert len(ledger.entries) == 2
    assert seen[0]["response_format"]["type"] == "json_schema"
    assert seen[1]["messages"][-1]["role"] == "user"  # the repair turn carries the validation errors


async def test_schema_and_tools_cannot_combine():
    tf, _ = make_tf()
    with pytest.raises(ValueError):
        await tf.chat(Role.FAST, [], stage="t", ledger=Ledger(), schema=Answer, tools=[{"type": "function"}])


def test_strict_schema_inlines_definitions():
    schema = strict_json_schema(LessonBible)
    assert "$defs" not in json.dumps(schema)
    fact = schema["properties"]["visual_facts"]["items"]
    assert fact["additionalProperties"] is False
    assert set(fact["required"]) == set(fact["properties"])


def test_extract_json_strips_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == '{"a": 1}'
