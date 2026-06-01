# JobOps

An AI-driven, zero-spam job application agent for senior technical professionals.
Automates sourcing, scoring, and applying to high-signal roles so you can focus
entirely on interview preparation and networking.

## The problem it solves

Senior technical professionals waste hours every day on the mechanical loop of
finding fresh roles, filling identical forms, and tracking applications across
spreadsheets. Existing tools either spray hundreds of low-quality applications
(triggering ATS spam filters) or require constant manual effort.

JobOps is a precision agent — it finds a maximum of 10 to 12 high-signal roles
per day, applies to them through real career pages like a human would, and tracks
everything in a local CRM. You focus on interviews. The agent handles the rest.

## What it does

- Scrapes fresh postings (last 24h only) from Wellfound, We Work Remotely, LinkedIn, Remotive
- Scores every role 0-100 against your profile using a local LLM (Ollama/Mistral) — free, offline, private
- Hard daily cap of 10-12 applications — never spams, never triggers portal security flags
- Three-layer deduplication — never applies to the same role or company twice
- Opens a real browser via Playwright MCP and fills career page forms with human-like pacing
- Detects ATS systems automatically — Greenhouse, Lever, Ashby, Workday, custom pages
- Learns unknown form questions and adds them to your profile for future runs
- Saves recruiter email drafts to Gmail for your review before sending
- Tracks everything in a local SQLite CRM — pipeline stages, notes, outreach status
- Sends an end-of-day HTML email report summarising exactly what happened
- Full web UI at localhost:5000 — no terminal needed for daily use

## Tech stack

| Layer | Technology |
|---|---|
| Orchestration | Python 3.11 + Flask |
| Browser automation | TypeScript + Playwright MCP |
| Local LLM scorer | Ollama mistral:7b — free, offline |
| Email drafts | OpenAI gpt-4o-mini — minimal cost |
| Database | SQLite — local file, zero setup |
| Web UI | Flask + plain HTML/JS |
| Python tests | pytest + pytest-cov |
| TypeScript tests | Jest |

## Project structure

```
jobops/
├── agent/                    # Python orchestration brain
│   ├── run.py                # main entry point
│   ├── scraper.py            # job board scrapers
│   ├── dedup.py              # three-layer deduplication
│   ├── scorer.py             # Ollama LLM scoring
│   ├── queue_manager.py      # priority sort + daily cap enforcement
│   ├── outreach.py           # GPT-4o-mini recruiter email drafts
│   ├── reporter.py           # end-of-day HTML email report
│   └── db.py                 # SQLite helpers
├── browser/                  # TypeScript Playwright MCP browser agent
│   └── src/
│       ├── index.ts          # entry — receives job payload from Python
│       ├── form_scanner.ts   # reads and classifies every form field
│       ├── form_filler.ts    # fills fields with human pacing
│       ├── unknown_handler.ts# flags unknown fields, writes to DB
│       └── submitter.ts      # screenshot, submit, return result JSON
├── config/
│   └── profiles/
│       ├── shrawan.yaml      # your profile
│       └── template.yaml     # blank profile for any new user
├── data/
│   └── schema.sql            # SQLite schema — 6 tables, all indexes
├── ui/                       # Flask web interface
│   ├── app.py                # 5 routes + SSE log stream
│   ├── templates/            # dashboard, queue, pipeline, questions, settings
│   └── static/               # CSS + JS
├── tests/
│   ├── agent/                # pytest — one file per agent module
│   ├── browser/              # Jest — one file per browser module
│   └── ui/                   # pytest + Flask test client
├── resumes/                  # gitignored — place your PDF here
├── review/                   # gitignored — pre-submit screenshots
├── logs/                     # gitignored — agent run logs
├── .env.example              # documents all required environment variables
├── .env                      # gitignored — your real keys
├── requirements.txt          # Python dependencies
└── README.md                 # this file
```

## Database schema (6 tables)

| Table | Purpose |
|---|---|
| jobs | Every scraped role — the dedup anchor |
| applications | Every submission — pipeline CRM |
| companies_seen | Company-level cooldown and blocklist |
| outreach | Recruiter email drafts and send status |
| unknown_fields | Form questions the agent could not answer |
| run_logs | Every agent run — sourced, scored, applied, failed |

## Deduplication — three layers

1. Job hash — SHA256(company_domain + normalised_title) — same role on two boards = applied once
2. Company cooldown — 90-day block after any application to a company
3. Daily cap — hard ceiling of 10-12 per day checked before opening any browser

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama running: `ollama pull mistral`
- Chrome browser

### Setup

```bash
git clone https://github.com/ShrawanXIO/jobops.git
cd jobops

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd browser
npm install
npm run install-browsers
cd ..

cp .env.example .env
# Fill in OPENAI_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD in .env

python -c "from agent.db import init_db; init_db()"

python ui/app.py
```

Open `http://localhost:5000` in Chrome and click **Run agent now**.

### Run tests

```bash
pytest tests/ --cov=agent --cov=ui --cov-report=term-missing

cd browser && npm test
```

## Adding another user

```bash
cp config/profiles/template.yaml config/profiles/brother.yaml
# Fill in their details and place resume at resumes/brother_cv.pdf
# Select their profile in Settings at localhost:5000
```

## Environment variables

| Variable | Purpose |
|---|---|
| OPENAI_API_KEY | Email drafts and cover letters only |
| GMAIL_ADDRESS | Daily report destination |
| GMAIL_APP_PASSWORD | 16-char app password from Google |
| OLLAMA_HOST | Default: http://localhost:11434 |
| FLASK_SECRET_KEY | Any random string |

## Responsible use

This agent enforces a strict daily cap and a 65% match threshold by design.
Built for precision — quality applications that get responses, not volume that
triggers spam filters and ruins your portal reputation.

## License

MIT — free to use, modify, and share.
