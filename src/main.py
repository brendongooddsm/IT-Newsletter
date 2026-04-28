"""Orchestrator: fetch -> curate -> render -> send."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from . import curator, feeds, mailer, renderer

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _count_feeds(config: dict[str, Any]) -> int:
    return sum(len(v or []) for v in (config.get("feeds") or {}).values())


def _count_curated(newsletter: dict[str, Any]) -> int:
    total = 0
    for section in newsletter.get("sections", []):
        total += len(section.get("articles", []) or [])
        total += len(section.get("items", []) or [])
    return total


def run(dry_run: bool = False, dump_feeds: bool = False) -> int:
    _setup_logging()
    log = logging.getLogger("main")

    try:
        config = _load_config()
    except (OSError, yaml.YAMLError) as exc:
        log.error("Failed to load config.yaml: %s", exc)
        return 1

    log.info("Loaded config with %d feeds.", _count_feeds(config))

    try:
        articles = feeds.fetch_all(config)
    except Exception as exc:  # noqa: BLE001
        log.exception("Feed collection failed: %s", exc)
        return 1

    log.info("Fetched %d articles.", len(articles))

    if dump_feeds:
        json.dump(articles, sys.stdout, indent=2, default=str, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if not articles:
        log.error("No articles found within lookback window. Aborting.")
        return 1

    try:
        newsletter = curator.curate(articles, config)
    except curator.CuratorError as exc:
        log.error("Curation failed: %s", exc)
        return 1

    log.info("Curated newsletter contains %d items across sections.", _count_curated(newsletter))

    try:
        html = renderer.render(newsletter)
    except Exception as exc:  # noqa: BLE001
        log.exception("Rendering failed: %s", exc)
        return 1

    date_str = newsletter.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
    subject = f"BSB Morning Brief - {date_str}"

    if dry_run:
        sys.stdout.write(html)
        if not html.endswith("\n"):
            sys.stdout.write("\n")
        log.info("Dry run complete; email NOT sent.")
        return 0

    recipient = os.getenv("RECIPIENT_EMAIL") or config.get("recipient_email")
    sender_email = os.getenv("SMTP_EMAIL") or config.get("sender_email")
    sender_name = config.get("sender_name", "BSB Morning Brief")
    if not recipient:
        log.error("No recipient email configured.")
        return 1

    try:
        mailer.send(
            html=html,
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
            recipient=recipient,
        )
    except mailer.MailerError as exc:
        log.error("Email delivery failed: %s", exc)
        return 1

    log.info("Done. Sent newsletter for %s to %s.", date_str, recipient)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BSB Morning Brief generator.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but print HTML to stdout instead of emailing.",
    )
    parser.add_argument(
        "--dump-feeds",
        action="store_true",
        help="Fetch feeds and print the raw article list as JSON, then exit.",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, dump_feeds=args.dump_feeds)


if __name__ == "__main__":
    sys.exit(main())
