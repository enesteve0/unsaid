import sys
import types
from types import SimpleNamespace

from unsaid import context
from unsaid.ledger import Ledger
from unsaid.schemas import ContextNames

PAGE = "Explaining Fourier analysis with a machine. Presented by Bill Hammack (engineerguy). Machine: Michelson's harmonic analyzer."


class FakeTavily:
    calls: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def extract(self, urls, **kwargs):
        FakeTavily.calls.append(("extract", urls))
        return {"results": [{"url": urls[0], "raw_content": PAGE}], "request_id": "req-extract"}

    async def search(self, query, **kwargs):
        FakeTavily.calls.append(("search", query))
        return {
            "results": [
                {
                    "url": "https://arxiv.org/abs/1706.03762",
                    "title": "Attention Is All You Need",
                    "score": 0.9,
                }
            ],
            "request_id": "req-search",
        }


class StubTF:
    async def chat(self, role, messages, **kwargs):
        # The model claims one name that is NOT on the page; it must be dropped.
        return SimpleNamespace(
            parsed=ContextNames(
                title="Fourier machine", people=["Bill Hammack", "Ada Lovelace"], terms=["engineerguy"]
            )
        )


def test_citations_are_found_on_slides():
    found = context.citations_in(
        ["Figure from Vaswani et al., 2017", "see www.example.org/notes", "no citation here"]
    )
    assert "Vaswani et al., 2017" in found
    assert any("example.org" in f for f in found)


async def test_names_must_appear_on_the_source_page(monkeypatch):
    monkeypatch.setitem(sys.modules, "tavily", types.SimpleNamespace(AsyncTavilyClient=FakeTavily))
    FakeTavily.calls = []
    result = await context.gather_context(
        StubTF(),
        Ledger(),
        "tvly-test",
        source_url="https://commons.wikimedia.org/wiki/File:x.webm",
        on_screen_texts=["Figure from Vaswani et al., 2017"],
        session_id="s",
    )
    assert "Bill Hammack" in result.names and "engineerguy" in result.names
    assert "Ada Lovelace" not in result.names  # not on the page, so never allowed
    assert {s.request_id for s in result.sources} == {"req-extract", "req-search"}
    assert ("search", "Vaswani et al., 2017") in FakeTavily.calls


async def test_no_key_means_no_calls():
    result = await context.gather_context(
        StubTF(), Ledger(), "", source_url="https://x", on_screen_texts=[], session_id="s"
    )
    assert result.names == [] and result.sources == []
