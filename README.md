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
SMTP_EMAIL=newsletter@bsbdesign.com
SMTP_PASSWORD=your-m365-app-password
RECIPIENT_EMAIL=brendon@bsbdesign.com
NEWSAPI_KEY=optional
```

### 3. GitHub Actions secrets

In the repo, go to **Settings -> Secrets and variables -> Actions** and add the same names:

- `ANTHROPIC_API_KEY` (required)
- `SMTP_EMAIL` (required)
- `SMTP_PASSWORD` (required)
- `RECIPIENT_EMAIL` (required)
- `NEWSAPI_KEY` (optional)

The workflow at `.github/workflows/newsletter.yml` runs automatically every weekday and can be triggered manually from the **Actions** tab.

### 4. M365 app password for SMTP

`smtp.office365.com` no longer accepts regular Microsoft passwords for most tenants. You will typically need either:

- **App password** (if Security defaults are disabled and the account has MFA enabled): Sign in to <https://mysignins.microsoft.com/security-info>, choose **Add method -> App password**, copy the generated value, and use it as `SMTP_PASSWORD`.
- **Authenticated SMTP enabled per-mailbox** (admin task): In the Microsoft 365 admin center, edit the mailbox -> **Mail -> Email apps -> Manage email apps** -> ensure **Authenticated SMTP** is checked. Authenticated SMTP must also be enabled tenant-wide (PowerShell: `Set-TransportConfig -SmtpClientAuthenticationDisabled $false`).
- A dedicated mailbox with a license is required; shared mailboxes will not authenticate.

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
