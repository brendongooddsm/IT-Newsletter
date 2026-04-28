"""RSS feed fetching, parsing, deduplication, and optional NewsAPI augmentation."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

import feedparser
import requests
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Article:
    title: str
    link: str
    published: datetime
    summary: str
    source_name: str
    category: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup: lowercase host, strip query/fragment, drop trailing slash."""
    if not url:
        return url
    try:
        parts = urlparse(url.strip())
        scheme = parts.scheme.lower() or "https"
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/") or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return url.strip()


def _parse_published(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
        if not value:
            continue
        try:
            dt = date_parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    # feedparser also exposes parsed time tuples
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def _fetch_feed(name: str, url: str, category: str, max_items: int) -> list[Article]:
    logger.info("Fetching feed: %s (%s)", name, url)
    try:
        parsed = feedparser.parse(url, request_headers={"User-Agent": "BSB-Morning-Brief/1.0"})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Feed %s raised exception: %s", name, exc)
        return []

    if getattr(parsed, "bozo", False) and not parsed.entries:
        logger.warning("Feed %s parse error: %s", name, parsed.bozo_exception)
        return []

    articles: list[Article] = []
    for entry in parsed.entries[:max_items]:
        title = _strip_html(entry.get("title", "")).strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        published = _parse_published(entry) or datetime.now(timezone.utc)
        summary = _strip_html(entry.get("summary") or entry.get("description") or "")
        if len(summary) > 800:
            summary = summary[:800].rsplit(" ", 1)[0] + "..."
        articles.append(
            Article(
                title=title,
                link=link,
                published=published,
                summary=summary,
                source_name=name,
                category=category,
            )
        )
    return articles


def _fetch_newsapi(config: dict[str, Any], lookback_hours: int) -> list[Article]:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.info("NEWSAPI_KEY not set; skipping NewsAPI augmentation.")
        return []
    if not config.get("enabled", True):
        return []

    from_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    params = {
        "q": config.get("query", "technology"),
        "language": config.get("language", "en"),
        "pageSize": int(config.get("page_size", 20)),
        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "sortBy": "publishedAt",
        "apiKey": api_key,
    }
    try:
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("NewsAPI fetch failed: %s", exc)
        return []

    if data.get("status") != "ok":
        logger.warning("NewsAPI returned non-ok status: %s", data.get("message"))
        return []

    out: list[Article] = []
    for item in data.get("articles", []):
        title = (item.get("title") or "").strip()
        link = (item.get("url") or "").strip()
        if not title or not link:
            continue
        published = _parse_published({"published": item.get("publishedAt")}) or datetime.now(timezone.utc)
        summary = _strip_html(item.get("description") or item.get("content") or "")
        source = (item.get("source") or {}).get("name") or "NewsAPI"
        out.append(
            Article(
                title=title,
                link=link,
                published=published,
                summary=summary,
                source_name=source,
                category="newsapi",
            )
        )
    logger.info("NewsAPI returned %d articles.", len(out))
    return out


def fetch_all(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch every configured feed, dedupe, filter to lookback window, return as dicts."""
    lookback_hours = int(config.get("lookback_hours", 28))
    max_per_feed = int(config.get("max_articles_per_feed", 10))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    all_articles: list[Article] = []
    feeds_block = config.get("feeds", {}) or {}
    for category, feed_list in feeds_block.items():
        for feed in feed_list or []:
            all_articles.extend(_fetch_feed(feed["name"], feed["url"], category, max_per_feed))

    newsapi_cfg = config.get("newsapi", {}) or {}
    all_articles.extend(_fetch_newsapi(newsapi_cfg, lookback_hours))

    # Filter to window
    fresh = [a for a in all_articles if a.published >= cutoff]
    logger.info("Collected %d articles (%d within %dh window).", len(all_articles), len(fresh), lookback_hours)

    # Dedupe by normalized URL, preferring earliest seen (already in collection order)
    seen: set[str] = set()
    deduped: list[Article] = []
    for article in fresh:
        key = _normalize_url(article.link)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)

    deduped.sort(key=lambda a: a.published, reverse=True)
    logger.info("After dedup: %d articles.", len(deduped))
    return [a.to_dict() for a in deduped]
