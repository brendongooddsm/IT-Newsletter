# BSB Morning Brief

A daily IT/AI newsletter generator, curated by the Claude API and delivered by email every weekday morning. Runs unattended via GitHub Actions.

## What it does

1. Pulls RSS feeds across IT/endpoint/security, general AI, and AEC industry sources.
2. Optionally augments with [NewsAPI.org](https://newsapi.org).
3. Sends the deduplicated 24-hour article window to Claude, which selects the most relevant items, writes summaries, and proposes 2-3 concrete automation projects for BSB Design.
4. Renders a responsive HTML email (Outlook/Gmail/Apple Mail compatible).
5. Delivers via Microsoft 365 SMTP.

## Setup

### 1. Clone & install

```bash
git clone <this-repo>
cd bsb-morning-brief
python -m venv .venv && source .venv/bin/activate   # or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Local environment

Copy `.env.example` to `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
SMTP_EMAIL=yourname@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
RECIPIENT_EMAIL=brendon@bsbdesign.com
NEWSAPI_KEY=optional
```

### 3. GitHub Actions secrets

In the repo, go to **Settings -> Secrets and variables -> Actions** and add:

- `ANTHROPIC_API_KEY` (required)
- `SMTP_EMAIL` (required) — the Gmail address that sends the newsletter
- `SMTP_PASSWORD` (required) — a Gmail App Password (see below)
- `RECIPIENT_EMAIL` (required) — where the newsletter lands
- `NEWSAPI_KEY` (optional)

The workflow at `.github/workflows/newsletter.yml` runs automatically every weekday and can be triggered manually from the **Actions** tab.

### 4. Gmail App Password for SMTP

The default SMTP provider is Gmail (`smtp.gmail.com:587`). Regular Gmail passwords won't work — you need an **App Password**:

1. Enable **2-Step Verification** on your Google account if not already on: <https://myaccount.google.com/signinoptions/two-step-verification>
2. Go to <https://myaccount.google.com/apppasswords>
3. Enter a name (e.g. "BSB Newsletter") and click **Create**
4. Copy the 16-character password (formatted `xxxx xxxx xxxx xxxx`) — use it as `SMTP_PASSWORD` (spaces optional)

> **Alternative: Microsoft 365 SMTP.** If you prefer to send from an M365 mailbox, add two extra secrets: `SMTP_HOST=smtp.office365.com` and `SMTP_PORT=587`. You'll also need Authenticated SMTP enabled on the mailbox (disabled by default on most tenants).

## Running it

### Manual GitHub Actions run

Actions tab -> **Daily Newsletter** -> **Run workflow**.

### Local test runs

Dry run (build the email, print HTML to stdout, do not send):

```bash
python -m src.main --dry-run
```

Dump raw feed contents (skip Claude entirely):

```bash
python -m src.main --dump-feeds
```

Save the dry run for inspection in a browser:

```bash
python -m src.main --dry-run > out.html && start out.html   # Windows
```

## Adding/removing feeds

Edit `config.yaml`. Feeds are organized into three categories (`it_endpoint_security`, `ai_general`, `ai_aec`); each entry needs a `name` and `url`. You can also tune:

- `max_articles_per_feed`
- `lookback_hours`
- `claude_model`
- `temperature`
- `recipient_email` / `sender_email`
- `newsapi.query`

## Cost

A typical run sends ~50-150 articles to Claude and gets back ~2-3K tokens of curated JSON. With Claude Sonnet 4 pricing this works out to roughly **$0.02-0.05 per day**, or about **$0.50-1.20 per month** for weekday delivery.

## Layout

```
bsb-morning-brief/
  .github/workflows/newsletter.yml   GitHub Actions cron
  src/
    feeds.py                         RSS + NewsAPI fetch & dedup
    curator.py                       Claude API call
    renderer.py                      Jinja2 -> HTML
    mailer.py                        SMTP via M365
    main.py                          Orchestrator + CLI flags
  templates/newsletter.html          Email body
  config.yaml                        Feeds, sections, settings
  requirements.txt
  .env.example
```
