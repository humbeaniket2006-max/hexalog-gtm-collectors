# hexalog-gtm-collectors

Two read-only Python jobs support Hexalog GTM work: a Reddit signal collector and a quota-conscious YouTube competitor-video collector. They use the Notion API with the existing **Competitor Signals**, **Subreddit Rules**, **Intel Digests**, and **Content Ideas** databases. This repository never writes to Intel Digests.

## Scope and architecture

The system collects competitor data and generates content ideas with target keywords and suggested timing. It never posts to Reddit or uploads videos to YouTube. A real Hexalog team member performs both Reddit posting and YouTube uploading manually.

## Local setup

Create and activate a virtual environment, then install the package and copy the environment template:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Fill in `.env`. Share each of the four Notion databases with the Notion integration. Production values belong in GitHub Actions repository secrets and must never be committed.

Run collectors with `python -m hexalog_gtm.reddit_collector` and `python -m hexalog_gtm.youtube_collector`.
