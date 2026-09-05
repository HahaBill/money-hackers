"""Auditable, template-only Tavily research (§19).

The wrapper deliberately exposes no free-form query entry point to the agent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
import json
from time import perf_counter
from urllib.parse import urlparse

import httpx
from prism_setup import emit_trace

ENDPOINT = "https://api.tavily.com/search"
MAX_CALLS = 4


class ResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    content: str
    score: float
    published_date: str | None
    tier: int


def source_tier(url: str, *, supplier_domains: set[str] | None = None) -> int:
    host = (urlparse(url).hostname or "").casefold()
    supplier_domains = {domain.casefold() for domain in (supplier_domains or set())}
    if host in supplier_domains or any(host.endswith(f".{domain}") for domain in supplier_domains):
        return 2
    if host.endswith(".gov") or host.endswith(".gov.au") or host in {
        "fred.stlouisfed.org",
        "www.bls.gov",
        "www.weather.gov",
        "www.bom.gov.au",
    }:
        return 2
    if any(name in host for name in ("reuters.com", "apnews.com", "bloomberg.com")):
        return 3
    return 4


def build_request(template: str, context: dict) -> dict:
    period = str(context.get("period") or "")
    if len(period) != 7:
        raise ValueError("research context requires period in YYYY-MM form")
    year, month = (int(part) for part in period.split("-", 1))
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    month_name = start.strftime("%B %Y")
    common = {
        "search_depth": "advanced",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
    }
    if template == "market_conditions":
        item = context.get("input")
        region = context.get("region")
        if not item or not region:
            raise ValueError("market_conditions requires input and region")
        return {
            **common,
            "query": f"{item} wholesale price {region} {month_name}",
            "topic": "finance",
            "time_range": "month",
        }
    if template == "weather":
        city = context.get("city")
        if not city:
            raise ValueError("weather requires city")
        return {
            **common,
            "query": f"{city} weather {month_name} temperature",
            "topic": "general",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    if template == "local_events":
        city = context.get("city")
        if not city:
            raise ValueError("local_events requires city")
        neighbourhood = context.get("neighbourhood") or ""
        return {
            **common,
            "query": f"{city} {neighbourhood} events road closure {month_name}".strip(),
            "topic": "news",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    if template == "competitor_prices":
        city = context.get("city")
        if not city:
            raise ValueError("competitor_prices requires city")
        request = {
            **common,
            "query": f"{city} café latte price {year}",
            "topic": "general",
        }
        domains = context.get("menu_domains")
        if domains:
            request["include_domains"] = domains
        return request
    if template == "regulatory":
        jurisdiction = context.get("jurisdiction")
        if not jurisdiction:
            raise ValueError("regulatory requires jurisdiction")
        return {
            **common,
            "query": f"{jurisdiction} minimum wage change {year}",
            "topic": "news",
            "time_range": "year",
        }
    raise ValueError(f"unsupported Tavily query template: {template}")


class TavilyResearcher:
    def __init__(self, api_key: str | None = None, *, max_calls: int = MAX_CALLS):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.max_calls = max_calls
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, template: str, context: dict) -> list[SearchResult]:
        if not self.api_key:
            raise ResearchError("TAVILY_API_KEY is not configured")
        if self.calls >= self.max_calls:
            raise ResearchError("Tavily per-run budget exhausted")
        request = build_request(template, context)
        self.calls += 1
        started = perf_counter()
        try:
            response = httpx.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            emit_trace(
                model="tool:tavily.search",
                input_messages=[{"role": "tool_request", "content": json.dumps(request)}],
                output_message="",
                latency_ms=int((perf_counter() - started) * 1000),
                event_type="tool_call",
                status="error",
                metadata={"tool_name": "tavily.search", "error_type": type(exc).__name__},
            )
            raise ResearchError(f"Tavily search failed: {exc}") from exc
        payload = response.json()
        supplier_domains = set(context.get("supplier_domains") or [])
        results = [
            SearchResult(
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                content=str(item.get("content") or ""),
                score=float(item.get("score") or 0.0),
                published_date=item.get("published_date"),
                tier=source_tier(str(item.get("url") or ""), supplier_domains=supplier_domains),
            )
            for item in payload.get("results", [])
        ]
        emit_trace(
            model="tool:tavily.search",
            input_messages=[{"role": "tool_request", "content": json.dumps(request)}],
            output_message=json.dumps(
                [{"title": item.title, "url": item.url, "score": item.score} for item in results]
            ),
            latency_ms=int((perf_counter() - started) * 1000),
            event_type="tool_call",
            metadata={"tool_name": "tavily.search", "result_count": len(results)},
        )
        return results
