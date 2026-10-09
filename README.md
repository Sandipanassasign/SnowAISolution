# ServiceNow AI Automation

Automated Change Request triage, LLM-based impact extraction, and stakeholder notification platform built for enterprise banking environments.

Features a full-stack web dashboard, asynchronous background scheduler, SQLite audit persistence, and an OpenAI-compatible LLM extraction pipeline.

---

## Table of Contents

- [Overview & Architecture](#overview--architecture)
- [Prerequisites](#prerequisites)
- [Setup Guide](#setup-guide)
  - [Step 1: Clone & Navigate](#step-1-clone--navigate)
  - [Step 2: Create & Activate Virtual Environment](#step-2-create--activate-virtual-environment)
  - [Step 3: Install Dependencies](#step-3-install-dependencies)
  - [Step 4: Configure Environment Variables](#step-4-configure-environment-variables)
  - [Step 5: Configure SSL & Proxy (VDI)](#step-5-configure-ssl--proxy-vdi)
  - [Step 6: Update Stakeholder Mapping](#step-6-update-stakeholder-mapping)
  - [Step 7: Seed Demo Data (Optional)](#step-7-seed-demo-data-optional)
  - [Step 8: Run the Application](#step-8-run-the-application)
- [Web Dashboard & API](#web-dashboard--api)
- [Project Structure](#project-structure)
- [Enterprise VDI Deployment](#enterprise-vdi-deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview & Architecture

### Full-Stack Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Web Dashboard                         │
│             Vanilla HTML5 / CSS3 / JavaScript               │
│                http://localhost:8000                        │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / SSE
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Server                   │
│        (Mounted Static Assets + REST API Endpoints)         │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────▼─────────────┐   ┌─────────────▼──────────────┐
│  APScheduler Background     │   │   SQLite Audit Database    │
│  (In-process CR Poller)    │   │   (data/automation.db)     │
└──────────────┬─────────────┘   └────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                    Core Pipeline Orchestrator               │
│                                                             │
│  [1. ServiceNow API] ──▶ [2. LLM Extraction] ──▶            │
│  [3. LOB Mapping]    ──▶ [4. SMTP Dispatch]                 │
└─────────────────────────────────────────────────────────────┘
```

### Pipeline Flow

1. **Ingest (ServiceNow Table API):** Polls scheduled `change_request` records matching custom filters.
2. **Extract (LLM / LlamaIndex):** Extracts structured impact data (`change_order_number`, `mail_codes`, `lob_impacted`) from free-text descriptions using JSON schema enforcement.
3. **Map (Configuration):** Resolves impacted Line of Business (LOB) to designated QA Leads and team distribution lists via `config/stakeholder_map.json`.
4. **Notify (SMTP):** Dispatches formatted HTML email notifications with impact breakdown and triage details.
5. **Persist (SQLite):** Records every execution, extracted field, status transition, and delivery receipt for compliance auditing.

---

## Prerequisites

| Requirement | Supported Version | Notes |
|-------------|-------------------|-------|
| **Python** | 3.10+ | Required (tested up to 3.14) |
| **ServiceNow** | Utah / Vancouver / Washington+ | Table API enabled with read access to `change_request` |
| **LLM Endpoint** | OpenAI-compatible API | Self-hosted vLLM, Azure OpenAI, or internal banking proxy |
| **SMTP Server** | Internal mail gateway | Port 25 or 587 |
| **Operating System** | Windows / Linux / macOS | Banking VDI or local workstation |

---

## Setup Guide

### Step 1: Clone & Navigate

```bash
git clone <repository-url>
cd ServiceNowSolution
```

### Step 2: Create & Activate Virtual Environment

```bash
python3 -m venv .venv
```

Activate the environment based on your operating system:

| Platform | Activation Command |
|----------|-------------------|
| **macOS / Linux** | `source .venv/bin/activate` |
| **Windows (cmd)** | `.venv\Scripts\activate.bat` |
| **Windows (PowerShell)** | `.venv\Scripts\Activate.ps1` |

Verify activation:
```bash
which python     # macOS/Linux
where python     # Windows
# Output should point inside .venv
```

### Step 3: Install Dependencies

#### Local development (direct internet access):
```bash
pip install -e ".[dev]"
```

#### Banking VDI (via internal Artifactory / Nexus proxy):
```bash
pip install --index-url https://artifactory.internal.bank.com/api/pypi/pypi-remote/simple \
    --trusted-host artifactory.internal.bank.com \
    -e ".[dev]"
```

### Step 4: Configure Environment Variables

Copy the template:
```bash
cp .env.example .env
```

Open `.env` in your editor and configure the parameters:

| Variable | Description | Example |
|----------|-------------|---------|
| `SNOW_INSTANCE_URL` | ServiceNow base URL | `https://bankinstance.service-now.com` |
| `SNOW_USERNAME` | ServiceNow API username | `svc_snow_automation` |
| `SNOW_PASSWORD` | ServiceNow API password | `********` |
| `LLM_API_KEY` | API key for internal LLM endpoint | `sk-...` |
| `LLM_API_BASE_URL` | OpenAI-compatible base URL | `https://llm.internal.bank.com/v1` |
| `LLM_MODEL_NAME` | Model identifier | `claude-opus-4-20250514` |
| `SMTP_HOST` | Internal SMTP mail server | `smtp.internal.bank.com` |
| `SMTP_PORT` | SMTP port | `25` |
| `SMTP_FROM_ADDRESS` | Notification sender address | `servicenow-automation@bank.com` |
| `SNOW_POLL_INTERVAL_SECONDS` | Polling frequency | `300` (5 minutes) |
| `MOCK_MODE` | Set to `true` to test locally without live credentials | `true` or `false` |
| `SERVER_HOST` | FastAPI host bind address | `0.0.0.0` |
| `SERVER_PORT` | Web server port | `8000` |

> 🔒 **Security Notice:** Never commit `.env` or credentials to git. The `.env` file is excluded via `.gitignore`.

### Step 5: Configure SSL & Proxy (VDI)

In enterprise banking VDIs with SSL inspection proxies:

- **Option A (Enterprise CA Bundle - Recommended):** Export the bank root CA certificate as `.pem` and configure:
  ```env
  SSL_CERT_FILE=/path/to/enterprise-ca-bundle.pem
  REQUESTS_CA_BUNDLE=/path/to/enterprise-ca-bundle.pem
  ```
- **Option B (Local Dev SSL Bypass):**
  ```env
  DISABLE_SSL_VERIFY=true
  ```
- **Option C (HTTP/HTTPS Proxy):**
  ```env
  HTTP_PROXY=http://proxy.internal.bank.com:8080
  HTTPS_PROXY=http://proxy.internal.bank.com:8080
  ```

### Step 6: Update Stakeholder Mapping

Define team mappings in `config/stakeholder_map.json`:

```json
{
  "Retail Banking": {
    "qa_lead": "jane.doe@bank.com",
    "qa_team": ["jane.doe@bank.com", "john.smith@bank.com"],
    "escalation": "retail.escalation@bank.com"
  },
  "Commercial Banking": {
    "qa_lead": "alice.wong@bank.com",
    "qa_team": ["alice.wong@bank.com", "bob.kumar@bank.com"],
    "escalation": "commercial.escalation@bank.com"
  }
}
```

### Step 7: Seed Demo Data (Optional)

To test the dashboard immediately with realistic Change Requests, audit history, and charts:

```bash
python scripts/seed_demo_data.py
```

### Step 8: Run the Application

The application supports three operational modes:

#### 1. Web Dashboard & Server (Recommended)
Starts the FastAPI server, serves the web dashboard, and runs background scheduled polling:
```bash
python main.py --serve
```
- **Dashboard:** Open `http://localhost:8000` in your browser.
- **Interactive API Docs (Swagger UI):** Open `http://localhost:8000/docs`.

#### 2. Continuous Background Polling (CLI)
Runs headless polling without the web UI:
```bash
python main.py --poll
```

#### 3. One-Shot Execution (CLI)
Executes a single triage and dispatch cycle and exits:
```bash
python main.py
```

---

## Web Dashboard & API

### Dashboard Features

- **Live System Status:** Displays scheduler state and countdown to the next automated run.
- **KPI Metrics Cards:** Real-time counters for Total Processed, Notifications Sent, Failed Tickets, and Impacted LOBs with ease-out number animations.
- **Manual Trigger ("Run Now"):** Instant pipeline trigger with in-flight button state and notifications.
- **Interactive Filtering:** Filter tickets dynamically by Line of Business or processing status.
- **Change Request Ledger:** Detailed table showing CR Number, Summary, Impacted LOB, Mail Codes, Assigned QA Lead, Status badge, and timestamps.
- **Execution Run History:** Audit list of recent pipeline runs showing trigger source (manual vs. scheduled) and tickets processed.
- **LOB Impact Chart:** Visual breakdown bar chart of Change Requests distributed by business unit.

### API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web dashboard user interface |
| `POST` | `/api/pipeline/run` | Triggers an immediate pipeline run |
| `GET` | `/api/pipeline/status` | Current pipeline execution status |
| `GET` | `/api/pipeline/runs` | History of recent pipeline runs |
| `GET` | `/api/tickets` | Query processed Change Requests (supports `?lob=` and `?status=`) |
| `GET` | `/api/tickets/{cr_number}` | Detailed status for a specific Change Request |
| `GET` | `/api/tickets/stats` | Aggregated dashboard KPI counts and LOB breakdown |
| `GET` | `/api/schedule` | Active scheduler status and next run time |
| `GET` | `/docs` | Interactive OpenAPI / Swagger documentation |

---

## Project Structure

```
ServiceNowSolution/
├── .github/
│   └── copilot-instructions.md     # Enterprise VDI and project rules
├── .env                            # Environment variables (git-ignored)
├── .env.example                    # Template environment variables
├── .gitignore                      # Git ignore patterns (includes data/ and .db)
├── pyproject.toml                  # Python package configuration and dependencies
├── README.md                       # Complete documentation and setup guide
│
├── api/                            # FastAPI backend & orchestration service
│   ├── __init__.py
│   ├── app.py                      # FastAPI application definition and lifespan
│   ├── database.py                 # SQLite engine, connection pool & session factory
│   ├── models.py                   # SQLAlchemy ORM models (ProcessedCR, PipelineRun, etc.)
│   ├── pipeline_service.py         # DB-persisted pipeline execution coordinator
│   ├── scheduler.py                # APScheduler background runner
│   └── routes/
│       ├── pipeline.py             # Pipeline run & status endpoints
│       └── tickets.py              # CR retrieval, search & stats endpoints
│
├── config/
│   └── stakeholder_map.json        # LOB to QA team email address mappings
│
├── data/                           # Local SQLite database directory (auto-created)
│   └── automation.db               # SQLite audit ledger
│
├── docs/                           # Architecture and schema reference documentation
│   ├── 1_architecture_flow.md      # State machine and transition lifecycle
│   ├── 2_servicenow_schema.md      # ServiceNow Table API request/response format
│   └── 3_vdi_ssl_guide.md          # Enterprise SSL certificate troubleshooting
│
├── frontend/                       # Web Dashboard frontend (static assets)
│   ├── index.html                  # Dashboard layout and structure
│   ├── css/
│   │   └── styles.css              # Dark-mode enterprise design system
│   └── js/
│       └── app.js                  # Asynchronous API fetch, auto-refresh & DOM rendering
│
├── scripts/
│   └── seed_demo_data.py           # Demo data generator for local verification
│
├── src/                            # Pipeline core library
│   ├── __init__.py
│   ├── schema.py                   # Pydantic models (ChangeRequestRecord, ImpactData)
│   ├── snow_client.py              # ServiceNow Table API client with VDI SSL handling
│   ├── llm_extractor.py            # LlamaIndex LLM extraction with JSON schema enforcement
│   └── notifier.py                 # Stakeholder lookup and HTML email delivery
│
└── main.py                         # Unified entry point (--serve, --poll, one-shot)
```

---

## Enterprise VDI Deployment

### Running as a Persistent Service (Windows VDI)

For continuous operation on a shared banking Windows VDI or jump box without keeping a terminal open, use **NSSM** (Non-Sucking Service Manager):

1. Download `nssm.exe` into a utility folder.
2. Open an administrative command prompt:
   ```cmd
   nssm install ServiceNowAutomation "C:\path\to\ServiceNowSolution\.venv\Scripts\python.exe" "C:\path\to\ServiceNowSolution\main.py --serve"
   nssm set ServiceNowAutomation AppDirectory "C:\path\to\ServiceNowSolution"
   nssm start ServiceNowAutomation
   ```
3. The service will automatically start with Windows and restart upon failures.

### Running as a systemd Service (Linux VDI / On-Prem VM)

Create `/etc/systemd/system/servicenow-automation.service`:

```ini
[Unit]
Description=ServiceNow AI Automation Service
After=network.target

[Service]
Type=simple
User=service_account
WorkingDirectory=/opt/ServiceNowSolution
ExecStart=/opt/ServiceNowSolution/.venv/bin/python main.py --serve
Restart=always
RestartSec=10
EnvironmentFile=/opt/ServiceNowSolution/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now servicenow-automation
```

---

## Troubleshooting

### `SSL: CERTIFICATE_VERIFY_FAILED`
You are behind an enterprise packet-inspection proxy. Export the root CA certificate as `.pem` and point `SSL_CERT_FILE` in `.env`. Alternatively, set `DISABLE_SSL_VERIFY=true` for local development. See [docs/3_vdi_ssl_guide.md](docs/3_vdi_ssl_guide.md).

### `SNOW_INSTANCE_URL environment variable is not set`
Copy `.env.example` to `.env` and fill in your instance credentials, or set `MOCK_MODE=true` to test locally.

### `No scheduled Change Requests found`
Verify that your ServiceNow instance has Change Requests in "Scheduled" state. Check the filter in `src/snow_client.py` (`state=Scheduled`).

### `No stakeholder mapping found for LOB`
The LOB extracted by the LLM was not found in `config/stakeholder_map.json`. Add the missing LOB name to the JSON file.

### Reviewing Logs
Logs are simultaneously written to standard output and persisted to **`automation.log`** in the project root directory.

---

## License

Internal Enterprise Use Only — Proprietary and Confidential.
