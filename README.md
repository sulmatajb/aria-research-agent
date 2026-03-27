# ARIA — Autonomous Research Intelligence Assistant

A multi-agent AI system controlled via Telegram. Send a research question; ARIA coordinates a team of specialized agents and returns a structured brief with verified sources saved directly to your Zotero library.

![ARIA Diagram](aria_diagram.excalidraw)

## How it works

One supervisor agent (Claude Sonnet) receives your message on Telegram, plans the work, and delegates to specialist sub-agents:

| Agent | Tool | Job |
|---|---|---|
| Supervisor | Claude Sonnet 4.6 | Plans, delegates, reports back |
| Perplexity Agent | Perplexity sonar-pro | Academic literature search |
| Firecrawl Agent | Firecrawl | Scrapes and verifies papers |
| Synthesizer Agent | Claude Sonnet 4.6 | APA citations + summaries |
| Zotero Agent | Zotero local API | Files everything into your library |

All agents communicate through a shared SQLite task queue. No hardcoded workflows — the supervisor infers the plan from your request.

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/your-username/aria-research-agent
cd aria-research-agent
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure API keys**
```bash
cp .env.example .env
```
Then open `.env` and fill in your keys:
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `PERPLEXITY_API_KEY` — [perplexity.ai/settings/api](https://perplexity.ai/settings/api)
- `FIRECRAWL_API_KEY` — [firecrawl.dev](https://firecrawl.dev)
- `TELEGRAM_TOKEN` — create a bot via [@BotFather](https://t.me/BotFather) on Telegram
- `ZOTERO_LIBRARY_ID` — your numeric user ID from zotero.org/settings

**4. Start Zotero desktop** (required for local library access)

**5. Launch all agents**
```bash
bash start_all.sh
```

This opens 6 Terminal windows: Supervisor, Perplexity, Firecrawl, Synthesizer, Telegram Bot, and a live dashboard.

**6. Start ARIA**

Open Telegram, find your bot, send `/start` — then send any research question.

## Example requests

```
Find recent papers on LLM agents for home energy management
Verify the authors of arXiv:2602.15219
Find a replacement for the Marzbali 2017 citation
Search for FERC Order 2222 demand response literature
```

## Dashboard

The live dashboard (`dashboard.py`) shows the task queue, agent activity, and logs in real time.

```bash
python3 dashboard.py
```

## Architecture

```
You (Telegram)
     ↕
  Supervisor (Claude Sonnet 4.6)
     |
     ├── Perplexity Agent  →  academic search
     ├── Firecrawl Agent   →  paper scraping + verification
     ├── Synthesizer Agent →  APA citations + summaries
     └── Zotero Agent      →  library filing

All agents share a SQLite task queue (aria.db)
```

## License

MIT
