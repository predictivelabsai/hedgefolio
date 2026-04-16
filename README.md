# Hedgefolio

**Invest like a hedge fund manager.** A 3-pane agentic chat UI over SEC 13F
filings. Ask questions in natural language; get live queries over hundreds of
hedge-fund portfolios answered with markdown tables, Plotly charts, and
citations from the F13 filing knowledge base.

## Stack

- **Frontend**: [FastHTML](https://fastht.ml) + HTMX + WebSockets + Plotly.js
  (no Streamlit).
- **Agent**: [LangGraph](https://langchain-ai.github.io/langgraph/) react agent
  with tool-calling, streamed token-by-token via `astream_events(v2)` to the
  browser.
- **LLM**: xAI Grok via the OpenAI-compatible `/v1` endpoint.
- **Database**: PostgreSQL (schemas: `hedgefolio`, `hedgefolio_rag`).
- **RAG**: Postgres full-text search (`to_tsvector`) over the official SEC
  Form 13F readme + schema metadata. No extra vector store needed.
- **Deploy**: Docker + docker-compose, exposed on host port `9011` → container
  port `5011`. Coolify reverse-proxies `hedgefolio.app` to that port.

## 3-pane layout

| Pane   | Contents |
|--------|----------|
| Left   | Brand, new-chat button, **5 shortcut buttons** (each pre-fills and submits a chat prompt), recent conversations, email subscribe form |
| Center | AG-UI chat — the *only* view. All analysis happens here, streamed token-by-token from the agent |
| Right  | Live thinking trace — every tool call, argument, and completion event streams in |

## Shortcuts (chat-driven)

Everything is a chat query. The left sidebar surfaces five canned prompts as
shortcut buttons. Clicking one fills the chat input and submits — the agent
picks the right tool and streams the answer back as a markdown table.

| Shortcut             | Prompt                                                                 | Expected tool |
|----------------------|-------------------------------------------------------------------------|----------------|
| Activist Filings     | "Show me the 20 most recent Schedule 13D activist filings …"           | `get_recent_activist_filings` |
| Top Holdings         | "Show me the top 20 holdings of Bridgewater Associates …"              | `get_fund_holdings` |
| Popular Securities   | "What are the 20 most popular securities across all hedge funds? …"    | `get_popular_securities` |
| Top Funds by AUM     | "Who are the top 15 hedge funds by portfolio value? …"                 | `get_top_funds` / `get_fund_concentration` |
| Security Types       | "What is the distribution of security types across all 13F holdings? …"| `get_security_type_distribution` |

Each shortcut has its own end-to-end regression test in
`tests/test_shortcuts.py` that asserts both the tool routing and the shape
of the markdown response.

## Agent tools

The LangGraph agent has access to these tools (see `utils/agent_tools.py`):

- `get_market_overview` — dataset-wide totals
- `search_funds(query)` — fuzzy fund search
- `get_top_funds(top_n)` — leaderboard by AUM
- `get_fund_holdings(fund_name)` — top positions for a fund
- `search_securities(query)` — which funds hold a given stock
- `get_popular_securities(top_n)` — most crowded trades
- `get_fund_concentration(top_n)` — market share by manager
- `get_recent_activist_filings(days, limit, activist_only)` — Schedule 13D/G filings from EDGAR daily index (updated daily)
- `search_activist_filings(query)` — search 13D/G filings by filer or subject
- `get_security_type_distribution(limit)` — instrument-type breakdown across all 13F positions
- `ask_f13_docs(question)` — RAG over the official SEC 13F readme + schema

## Data sources & refresh cadence

| Source | Endpoint | Refresh | Script |
|--------|----------|---------|--------|
| 13F holdings (`hedgefolio.*`) | `sec.gov/files/structureddata/data/form-13f-data-sets/YYYYqQ_form13f.zip` rolling 3-month windows | quarterly | `tasks/download_sec_13f.py` |
| Activist filings (`hedgefolio.activist_filing`) | `sec.gov/Archives/edgar/daily-index/YYYY/QTRQ/form.YYYYMMDD.idx` | **daily** — 13D/G are filed continuously, indexed every business day | `tasks/sync_activist.py` |
| F13 RAG (`hedgefolio_rag.*`) | local `data/FORM13F_readme.htm` + `data/FORM13F_metadata.json` | whenever SEC publishes a new spec | `tasks/setup_rag.py` |

Recommended cron on the Coolify host:

```cron
# Daily at 06:00 UTC — pick up yesterday's 13D/G filings + enrich headers
0 6 * * *   cd /app && .venv/bin/python tasks/sync_activist.py --days 7 --enrich 200

# Monday at 07:00 UTC — re-check for new quarterly 13F window and reload if found
0 7 * * 1   cd /app && .venv/bin/python tasks/download_sec_13f.py
```

## Quickstart

```bash
# 1. Configure .env
cp .env.example .env   # or edit the existing .env
# Required: DB_URL, XAI_API_KEY
# Optional: POSTMARK_API_KEY, JWT_SECRET, GROK_MODEL (default grok-4-fast-reasoning)

# 2. Install dependencies
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Apply chat + RAG schemas and ingest the F13 knowledge base
.venv/bin/python -c "
from sqlalchemy import text
from pathlib import Path
from utils.db_pool import get_pool
pool = get_pool()
with pool.get_session() as s:
    s.execute(text(Path('sql/chat_schema.sql').read_text()))
    s.execute(text(Path('sql/rag_schema.sql').read_text()))
"
.venv/bin/python tasks/setup_rag.py

# 4. Load 13F data (only required for the chart pages + fund/holding tools;
#    the F13 RAG tool and chat infrastructure work without this step).
.venv/bin/python tasks/setup_data.py

# 5. Run
.venv/bin/python web_app.py   # → http://localhost:5011
```

## Docker

```bash
# Web only
docker compose up --build -d web
# → UI: http://localhost:9011    Health: http://localhost:9011/health

# Web + scheduler (daily 13D/G sync, weekly 13F refresh inside a cron sidecar)
docker compose --profile scheduler up --build -d
```

A named volume `hedgefolio-data` persists the SEC 13F zip and extracted TSVs
between container rebuilds, so you don't re-download ~90 MB on every deploy.

## Coolify deployment (hedgefolio.app)

**Requirements**: Postgres reachable from the Coolify network, an xAI Grok
API key.

### 1. Create the app

In Coolify → **New Resource → Docker Compose**:

- **Source**: this Git repo.
- **Compose file**: `docker-compose.yaml` (default).
- **Service name**: `web`.
- **Domain**: `hedgefolio.app`.
- **Port**: set the container port to `5011`. Coolify will publish its own
  reverse proxy, so the `ports: 9011:5011` mapping is only needed for
  bare-docker runs — Coolify routes traffic by hitting the container port
  directly on the internal network.

### 2. Environment variables

Copy from `.env.example`. Minimum:

```
DB_URL=postgresql://user:pass@host:5432/db
XAI_API_KEY=xai-...
SEC_USER_AGENT=Hedgefolio/0.1 (you@example.com)
```

### 3. One-off bootstrap (first deploy only)

Once the `web` service is healthy, open Coolify's **Terminal** on the
container and run:

```bash
# Apply chat + RAG + activist schemas and ingest the F13 knowledge base.
python -c "from sqlalchemy import text; from pathlib import Path; \
  from utils.db_pool import get_pool; pool=get_pool(); \
  [pool.get_session().__enter__().execute(text(Path(f).read_text())) \
   for f in ('sql/chat_schema.sql','sql/rag_schema.sql','sql/activist_schema.sql')]"
python tasks/setup_rag.py

# Load the latest SEC 13F quarter (~10-30 min).
python tasks/download_sec_13f.py

# Backfill 30 days of 13D/G activist filings + resolve the first 500 issuers.
python tasks/sync_activist.py --days 30 --enrich 500
```

### 4. Keep data fresh — choose one

**Option A: Coolify Scheduled Tasks** (recommended — no extra container).
In your web service's settings → **Scheduled Tasks**:

| Name              | Schedule       | Command                                                        |
|-------------------|----------------|----------------------------------------------------------------|
| Daily 13D/G sync  | `0 6 * * *`    | `python tasks/sync_activist.py --days 7 --enrich 300`         |
| Weekly 13F refresh| `0 7 * * 1`    | `python tasks/download_sec_13f.py`                            |

**Option B: Scheduler sidecar container**. Enable the `scheduler` profile in
compose (Coolify UI → "Compose Profile" → add `scheduler`) and the cron
container defined by `Dockerfile.scheduler` will run both jobs on a built-in
schedule.

### 5. Monitoring

- Health: `GET /health` → `{"status":"ok","db":true,"agent":true}`.
- Container logs stream the web request log + any agent tool-call errors.
- Scheduler sidecar logs to `docker logs hedgefolio-scheduler` and to
  `/var/log/hedgefolio.log` inside the container.

## Endpoints

| Path                     | Purpose                                         |
|--------------------------|-------------------------------------------------|
| `/`                      | Chat (with `?new=1` to start a fresh thread, `?thread=<id>` to resume) |
| `/agui/ws/{thread_id}`   | WebSocket — streams chat tokens + tool traces  |
| `/agui-conv/list`        | HTMX fragment — recent conversations           |
| `/subscribe`             | HTMX form — email signup                       |
| `/health`                | JSON liveness probe                            |

All analysis that used to live on `/activist` or `/charts/*` is now driven
through chat via the left-nav shortcut buttons — there's a single view.

## Project layout

```
hedgefolio/
├── web_app.py                    # FastHTML app: routes, 3-pane layout, chart pages
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── sql/
│   ├── schema.sql                # existing 13F schema
│   ├── chat_schema.sql           # chat_conversations + chat_messages
│   ├── rag_schema.sql            # hedgefolio_rag.documents + chunks
│   └── activist_schema.sql       # hedgefolio.activist_filing (13D/G tracker)
├── tasks/
│   ├── setup_data.py             # load 13F TSVs → hedgefolio.*
│   ├── data_sync.py              # ongoing SEC download sync (legacy stub)
│   ├── download_sec_13f.py       # download + extract + load latest SEC 13F zip
│   ├── sync_activist.py          # daily 13D/G sync from EDGAR daily index
│   └── setup_rag.py              # ingest F13 readme + metadata → RAG
├── utils/
│   ├── agui/                     # FastHTML chat runtime (core + chat_store + styles)
│   ├── agent.py                  # LangGraph react agent builder
│   ├── agent_tools.py            # markdown-returning tool functions
│   ├── charts.py                 # Plotly figure builders (JSON output)
│   ├── db_pool.py                # shared SQLAlchemy engine/session pool
│   ├── db_queries.py             # pandas-returning query helpers
│   ├── db_util.py                # ORM models + TSV loaders
│   ├── rag.py                    # F13 docs schema + ingest + search
│   ├── activist.py               # EDGAR daily-index parser + 13D/G queries
│   └── email_util.py             # Postmark subscribe emails
└── data/
    ├── FORM13F_readme.htm        # source for the RAG knowledge base
    ├── FORM13F_metadata.json
    └── company_ticker.csv
```

## Environment variables

| Var                 | Required | Notes |
|---------------------|----------|-------|
| `DB_URL`            | yes      | Postgres connection string |
| `DB_SCHEMA`         | no       | defaults to `hedgefolio` |
| `XAI_API_KEY`       | yes      | xAI Grok via OpenAI-compatible API |
| `GROK_MODEL`        | no       | defaults to `grok-4-fast-reasoning` |
| `LLM_PROVIDER`      | no       | currently informational only (agent always uses xAI) |
| `JWT_SECRET`        | no       | session signing; random generated if absent |
| `POSTMARK_API_KEY`  | no       | email subscribe welcome mail |
| `TO_EMAIL`          | no       | Postmark alerts |
| `FROM_EMAIL`        | no       | Postmark sender |
| `PORT`              | no       | web_app listen port, default `5011` |

## Regression tests

A 55-scenario pytest suite lives in `tests/`. Data-dependent tests skip
automatically when the relevant tables are empty, so the suite can run in
CI even without the SEC 13F load.

```bash
.venv/bin/python -m pytest tests/ -v
```

Coverage:

| File                          | Scenarios | Covers |
|-------------------------------|-----------|--------|
| `tests/test_db.py`            | 7         | schemas, table existence, FK integrity, FTS index |
| `tests/test_tools.py`         | 11        | every agent tool function (markdown output + error paths) |
| `tests/test_web.py`           | 11        | all HTTP routes, shortcut button presence, removed-pages return 404, runShortcut() JS |
| `tests/test_activist_parser.py` | 3        | EDGAR daily-index fixed-width parser |
| `tests/test_rag.py`           | 4         | HTML→text, chunker, FTS retrieval |
| `tests/test_agent.py`         | 3         | LangGraph agent + tool registration |
| `tests/test_chat_scenarios.py`| 6         | end-to-end chat: Laurion, Situational Awareness, top-by-AUM, NVIDIA, recent 13Ds, activist-by-filer |
| `tests/test_shortcuts.py`     | 10        | each of the 5 left-nav shortcuts (end-to-end LLM) + unit guards (keys unique, tool registration, percentage sanity) |

Run only the fast (non-LLM, no-network) subset:

```bash
.venv/bin/python -m pytest tests/ -v -m "not slow" \
    --ignore=tests/test_chat_scenarios.py \
    --ignore=tests/test_shortcuts.py
```

## Disclaimer

Not investment advice. Data comes from SEC 13F filings, which are reported
45 days after quarter-end and therefore 6–8 weeks stale by the time they appear.

## License

MIT — see `LICENSE`.
