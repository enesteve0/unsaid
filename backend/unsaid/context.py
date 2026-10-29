"""Stage 6, Context: Tavily supplies names the video itself establishes elsewhere.

Audio description may only name what a sighted viewer can know. Two sources qualify and both come through Tavily:

* the video's own source page (course page, upload page): who presents, the title, product names;
* works cited on slides ("Vaswani et al., 2017"): the cited title, so the description can say what the figure is.

Names found here join the registry with source="context"; the name gate then permits them. Every Tavily call is
kept as a `Source` with its request_id so the UI can show "Context via Tavily".
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

from .config import Role
from .ledger import Ledger
from .schemas import ContextNames, Source
from .tf_client import AuthFailure, CreditExhausted, TokenFactory

log = logging.getLogger(__name__)
TAVILY_TIMEOUT = 30.0  # seconds; context is optional, so a slow lookup is dropped rather than waited for

CITATION = re.compile(r"([A-Z][A-Za-z'’-]+(?: et al\.?| and [A-Z][A-Za-z'’-]+)?,? \(?(?:19|20)\d{2}\)?)")
URL_TEXT = re.compile(r"\b(?:https?://|www\.)\S+|\b(?:doi\.org|arxiv\.org)/\S+", re.I)

NAMES_SYSTEM = (
    "Extract names from a web page that describes a lecture video. Return the video or page title, the people "
    "credited as presenters or authors, and other proper nouns (institutions, products, named devices) that may "
    "appear in the video. Only include names that literally appear in the page text."
)


@dataclass
class ContextResult:
    names: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    title: str = ""


def citations_in(texts: list[str], limit: int = 3) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in [*CITATION.findall(text), *URL_TEXT.findall(text)]:
            if match not in found:
                found.append(match)
    return found[:limit]


async def gather_context(
    tf: TokenFactory,
    ledger: Ledger,
    tavily_api_key: str,
    *,
    source_url: str | None,
    on_screen_texts: list[str],
    session_id: str,
) -> ContextResult:
    result = ContextResult()
    if not tavily_api_key:
        return result
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=tavily_api_key, project_id="unsaid", session_id=session_id)

    # Context only adds names: if Tavily is down, out of credit or slow, the run goes on without it.
    try:
        await asyncio.wait_for(_source_page(tf, ledger, client, source_url, result), TAVILY_TIMEOUT * 2)
    except (CreditExhausted, AuthFailure):
        raise
    except Exception as exc:
        log.warning("context: source page skipped: %s", exc)

    async def look_up(citation: str) -> None:
        try:
            found = await asyncio.wait_for(
                client.search(citation[:380], search_depth="basic", max_results=3, include_usage=True),
                TAVILY_TIMEOUT,
            )
        except Exception as exc:
            log.warning("context: citation lookup skipped: %s", exc)
            return
        top = next((r for r in found.get("results", []) if r.get("score", 0) >= 0.5), None)
        if top:
            result.sources.append(
                Source(
                    url=top["url"],
                    title=top.get("title", ""),
                    request_id=found.get("request_id", ""),
                    used_for=f"citation: {citation}",
                )
            )
            result.names.extend(re.findall(r"[A-Z][A-Za-z'’-]+", citation))

    await asyncio.gather(*(look_up(c) for c in citations_in(on_screen_texts)))
    return result


async def _source_page(
    tf: TokenFactory, ledger: Ledger, client, source_url: str | None, result: ContextResult
) -> None:
    if source_url:
        page = await client.extract(
            urls=[source_url], extract_depth="basic", format="markdown", include_usage=True
        )
        hits = page.get("results", [])
        if hits:
            text = hits[0].get("raw_content", "")[:12000]
            names = await tf.chat(
                Role.FAST,
                [{"role": "system", "content": NAMES_SYSTEM}, {"role": "user", "content": text}],
                stage="context",
                ledger=ledger,
                schema=ContextNames,
                max_tokens=800,
            )
            parsed: ContextNames = names.parsed  # type: ignore[assignment]
            lowered = text.lower()
            verified = [n for n in [*parsed.people, *parsed.terms] if n and n.lower() in lowered]
            result.names.extend(verified)
            result.title = parsed.title
            result.sources.append(
                Source(
                    url=source_url,
                    title=parsed.title,
                    request_id=page.get("request_id", ""),
                    used_for="source page names",
                )
            )
