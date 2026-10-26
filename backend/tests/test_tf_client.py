import json

import httpx
import pytest
from pydantic import BaseModel

from unsaid import tf_client
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


def as_stream(response: httpx.Response) -> httpx.Response:
    """The server-sent events a streamed request receives for the same chat.completion body."""
    data = response.json()
    choice = data["choices"][0]
    chunk = {"id": data["id"], "object": "chat.completion.chunk", "created": 0, "model": data["model"]}
    events = [
        {
            **chunk,
            "choices": [{"index": 0, "delta": choice["message"], "finish_reason": choice["finish_reason"]}],
        },
        {**chunk, "choices": [], "usage": data["usage"]},
    ]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


def make_tf(*responses):
    """TokenFactory wired to a mock transport that replays `responses` in order and records requests. A JSON
    completion queued for a streamed request is replayed as events."""
    queue, seen = list(responses), []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == URL
        body = json.loads(request.content)
        seen.append(body)
        response = queue.pop(0)
        if body.get("stream") and response.headers.get("content-type") == "application/json":
            return as_stream(response) if response.status_code == 200 else response
        return response

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
    assert body["stream"] is True  # a stalled call is caught by the read timeout, not after the whole budget
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


async def test_json_schema_rejection_downgrades_to_prompt_only():
    tf, seen = make_tf(
        httpx.Response(500, json={"message": "Failed to generate completions"}),
        httpx.Response(200, json=completion('{"value": 3}')),
        httpx.Response(200, json=completion('{"value": 4}')),
    )
    ledger = Ledger()
    first = await tf.chat(
        Role.CLASSIFY, [{"role": "user", "content": "x"}], stage="t", ledger=ledger, schema=Answer
    )
    second = await tf.chat(
        Role.CLASSIFY, [{"role": "user", "content": "y"}], stage="t", ledger=ledger, schema=Answer
    )
    assert (first.parsed.value, second.parsed.value) == (3, 4)
    assert (
        "response_format" in seen[0] and "response_format" not in seen[1] and "response_format" not in seen[2]
    )
    assert "JSON Schema" in seen[1]["messages"][-1]["content"]  # the schema still travels in the prompt


async def test_reasoning_calls_stream_and_collect_usage():
    events = [
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "reasoning_content": "Let me think. "},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": {"content": '{"value": '}, "finish_reason": None}],
        },
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": {"content": "9}"}, "finish_reason": "stop"}],
        },
        {
            "id": "s1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80,
                "completion_tokens_details": {"reasoning_tokens": 22},
            },
        },
    ]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
    tf, seen = make_tf(httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))
    ledger = Ledger()
    result = await tf.chat(
        Role.REASON,
        [{"role": "user", "content": "x"}],
        stage="t",
        ledger=ledger,
        thinking=True,
        schema=Answer,
        constrain=False,
    )
    assert seen[0]["stream"] is True and "response_format" not in seen[0]
    assert result.parsed.value == 9 and result.reasoning == "Let me think. "
    assert (ledger.entries[0].completion_tokens, ledger.entries[0].reasoning_tokens) == (30, 22)


async def test_max_tokens_rejection_retries_with_smaller_budget():
    tf, seen = make_tf(
        httpx.Response(400, json={"error": {"message": "max_tokens must be <= 16384"}}),
        httpx.Response(200, json=completion("ok")),
    )
    result = await tf.chat(
        Role.CLASSIFY, [{"role": "user", "content": "x"}], stage="t", ledger=Ledger(), max_tokens=40_000
    )
    assert result.content == "ok"
    assert seen[0]["max_tokens"] == 40_000 and seen[1]["max_tokens"] == 16_000
    assert seen[1]["model"] == seen[0]["model"]  # same model, not a silent fallback


def test_extract_json_ignores_trailing_characters():
    assert json.loads(extract_json('{"descriptions": [{"t": 1, "text": "x"}]}}')) == {
        "descriptions": [{"t": 1, "text": "x"}]
    }


async def test_transient_server_error_is_retried_on_the_same_model(monkeypatch):
    monkeypatch.setattr(tf_client, "TRANSIENT_PAUSE_SECONDS", 0)
    tf, seen = make_tf(
        httpx.Response(500, json={"message": "Failed to generate completions"}),
        httpx.Response(200, json=completion("ok")),
    )
    ledger = Ledger()
    result = await tf.chat(Role.FAST, [{"role": "user", "content": "x"}], stage="t", ledger=ledger)
    assert result.content == "ok"
    assert seen[1]["model"] == seen[0]["model"]
    assert [e.ok for e in ledger.entries] == [False, True]


async def test_medium_effort_sets_the_template_flag_only_when_thinking():
    tf, seen = make_tf(httpx.Response(200, json=completion("a")), httpx.Response(200, json=completion("b")))
    for thinking in (True, False):
        await tf.chat(
            Role.FAST,
            [{"role": "user", "content": "x"}],
            stage="t",
            ledger=Ledger(),
            thinking=thinking,
            medium_effort=True,
        )
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": True, "medium_effort": True}
    assert seen[1]["chat_template_kwargs"] == {"enable_thinking": False}


async def test_json_schema_downgrade_wears_off(monkeypatch):
    monkeypatch.setattr(tf_client, "RETIRED_SECONDS", 0)
    tf, seen = make_tf(
        httpx.Response(500, json={"message": "Failed to generate completions"}),
        httpx.Response(200, json=completion('{"value": 3}')),
        httpx.Response(200, json=completion('{"value": 4}')),
    )
    for content in ("x", "y"):
        await tf.chat(
            Role.CLASSIFY, [{"role": "user", "content": content}], stage="t", ledger=Ledger(), schema=Answer
        )
    # A single 500 is not proof that the deployment rejects json_schema: constrained decoding comes back.
    assert ["response_format" in body for body in seen] == [True, False, True]
