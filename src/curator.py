"""Claude API integration: send raw articles, get back curated newsletter JSON."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a newsletter curator for a Senior IT Administrator and Systems Engineer at BSB Design, a mid-size architecture (AEC) firm. He manages endpoints with Intune, Autopilot, and PDQ Connect; identity with Entra ID; collaboration with M365, SharePoint, and Egnyte; and AEC apps including Revit, AutoCAD, and Bluebeam Revu. He scripts primarily in PowerShell and is expanding into Python. He leads the firm's Innovation Lab focused on AI adoption.

Your job: curate, summarize, and generate a daily newsletter from the raw articles provided. Produce a JSON response with this exact schema:

{
  "date": "YYYY-MM-DD",
  "sections": [
    {
      "title": "IT & Endpoint Management",
      "articles": [
        {
          "headline": "...",
          "summary": "2-3 sentence summary focused on practical relevance",
          "why_it_matters": "One sentence on why this matters for an IT admin at an AEC firm",
          "url": "original article URL",
          "source": "source name"
        }
      ]
    },
    {
      "title": "AI & Machine Learning",
      "articles": [...]
    },
    {
      "title": "AI in Architecture & AEC",
      "articles": [...]
    },
    {
      "title": "BSB Automation & Efficiency Ideas",
      "items": [
        {
          "idea": "Short title",
          "description": "2-3 sentences describing a concrete project BSB could implement, referencing their actual tools and environment where applicable",
          "inspired_by": "Which article(s) from above inspired this idea"
        }
      ]
    }
  ],
  "one_liner": "A short, interesting one-liner or quote from today's news to start the day"
}

Rules:
- Select 3-5 of the MOST relevant articles per section (IT, AI, AEC). Quality over quantity.
- Skip articles that are product press releases with no actionable info.
- The "BSB Automation & Efficiency Ideas" section should have 2-3 ideas. These should be concrete, scoped projects -- not vague suggestions. Reference specific tools in BSB's stack (Intune, PDQ Connect, Entra, PowerShell, Egnyte, Bluebeam, Revit, etc.) where applicable.
- If a section has zero relevant articles from the feed, include the section with an empty articles array. Do not fabricate articles.
- Return ONLY valid JSON. No markdown fences, no preamble.
"""


class CuratorError(RuntimeError):
    """Raised when curation fails irrecoverably."""


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort extract a JSON object from a model response."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to slicing from the first { to the last }.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        return json.loads(candidate)
    raise ValueError("Response did not contain parseable JSON.")


def _build_user_message(articles: list[dict[str, Any]], today: str) -> str:
    payload = {
        "today": today,
        "article_count": len(articles),
        "articles": articles,
    }
    return (
        "Here are the raw articles collected from RSS feeds (and optionally NewsAPI) "
        "in the last ~24 hours. Curate them per the rules in the system prompt and "
        "respond with the JSON object only.\n\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )


def curate(articles: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Call Claude to produce the structured newsletter JSON."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise CuratorError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic()
    model = config.get("claude_model", "claude-sonnet-4-20250514")
    max_tokens = int(config.get("max_tokens", 4096))
    temperature = float(config.get("temperature", 0.3))
    today = datetime.utcnow().strftime("%Y-%m-%d")

    user_message = _build_user_message(articles, today)

    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            logger.info("Calling Claude (%s), attempt %d, %d articles in.", model, attempt, len(articles))
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            data = _extract_json(text)
            data.setdefault("date", today)
            return data
        except (anthropic.APIError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning("Curation attempt %d failed: %s", attempt, exc)
            if attempt == 1:
                time.sleep(10)

    raise CuratorError(f"Curation failed after retries: {last_exc}")
