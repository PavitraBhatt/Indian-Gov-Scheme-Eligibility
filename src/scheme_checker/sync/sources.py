"""Government scheme data sources.

A ``SchemeSource`` fetches *raw* scheme records — loosely-structured blobs as the
upstream provides them. Normalizing those into our strict schema happens later,
in :mod:`scheme_checker.sync.normalize`.

The myScheme data is served through MeitY's official API Setu platform, which
issues free API keys. The endpoint and key are read from the environment so the
sanctioned access path is a config change, not a code change:

    MYSCHEME_ENDPOINT   full search URL (defaults to the known myScheme search)
    MYSCHEME_API_KEY    API key issued by API Setu / data.gov.in
"""

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

# A raw, un-normalized scheme blob from a source.
RawScheme = dict[str, Any]

DEFAULT_ENDPOINT = "https://api.myscheme.gov.in/search/v4/schemes"


class SchemeSource(ABC):
    """Fetches raw scheme records from an upstream provider."""

    @abstractmethod
    def fetch(self) -> list[RawScheme]:
        """Return all available raw scheme records."""
        raise NotImplementedError


class MyySchemeSource(SchemeSource):
    """Fetches schemes from the myScheme search API (via API Setu).

    ``http_get`` is injectable so tests can supply canned pages without network:
    a callable ``(url, params, headers) -> dict`` returning the parsed JSON.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        page_size: int = 100,
        max_schemes: int | None = None,
        http_get: Callable[[str, dict, dict], dict] | None = None,
    ):
        self.endpoint = endpoint or os.environ.get("MYSCHEME_ENDPOINT", DEFAULT_ENDPOINT)
        self.api_key = api_key or os.environ.get("MYSCHEME_API_KEY", "")
        self.page_size = page_size
        self.max_schemes = max_schemes
        self._http_get = http_get or self._default_http_get

    def _default_http_get(self, url: str, params: dict, headers: dict) -> dict:
        import httpx  # imported lazily so tests that inject http_get need no network

        resp = httpx.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _headers(self) -> dict:
        headers = {"Accept": "application/json", "User-Agent": "scheme-checker-sync/1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _get_page(self, from_: int) -> list[dict]:
        params = {
            "lang": "en",
            "q": "",
            "keyword": "",
            "sort": "",
            "from": from_,
            "size": self.page_size,
        }
        payload = self._http_get(self.endpoint, params, self._headers())
        return _extract_items(payload)

    def fetch(self) -> list[RawScheme]:
        raw: list[RawScheme] = []
        from_ = 0
        while True:
            items = self._get_page(from_)
            if not items:
                break
            for item in items:
                raw.append(_to_raw(item))
                if self.max_schemes and len(raw) >= self.max_schemes:
                    return raw
            if len(items) < self.page_size:
                break
            from_ += self.page_size
        return raw


def _extract_items(payload: dict) -> list[dict]:
    """Pull the list of scheme hits out of a myScheme search response.

    The response nests hits under data.hits.items; we read defensively so a
    shape change degrades to "no items" rather than a crash.
    """
    data = payload.get("data")
    # Some variants return a flat list under "data".
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        hits = data.get("hits") or {}
        items = hits.get("items")
        if isinstance(items, list):
            return items
    return []


def _to_raw(item: dict) -> RawScheme:
    """Map one upstream hit to our raw shape.

    Upstream wraps the useful values in a ``fields`` object; we keep the full
    original under ``raw`` so the normalizer has everything it needs.
    """
    fields = item.get("fields") or item
    slug = fields.get("slug") or fields.get("schemeSlug") or ""
    name = fields.get("schemeName") or fields.get("schemeShortTitle") or fields.get("name") or ""
    source_url = f"https://www.myscheme.gov.in/schemes/{slug}" if slug else ""
    text_parts = [
        fields.get("briefDescription") or fields.get("detailedDescription_md") or "",
        fields.get("schemeName") or "",
    ]
    return {
        "source_id": slug or name,
        "name_en": name,
        "source_url": source_url,
        "text": "\n".join(p for p in text_parts if p),
        "raw": fields,
    }
