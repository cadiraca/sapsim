# SAP SIM 🏗️

> **30 autonomous AI agents simulating a full SAP S/4HANA implementation — from Discover to Go-Live.**

SAP SIM is an interactive simulation platform that models an entire SAP implementation project using AI agents. Each agent represents a real project persona — consultants, key users, executives, developers — with distinct personalities, domain expertise, and engagement levels. Watch them collaborate (and clash) through every phase of the SAP Activate methodology in real time.

---

## What It Is

A real SAP implementation involves dozens of people across two sides of the table: the **consulting team** that knows the software, and the **customer team** that knows the business. SAP SIM brings both to life:

- **16 consultant agents** — PM, Solution Architect, module leads (FI, CO, MM, SD, PP, WM), developers, Basis admin, security, BI, change management, data migration, PMO
- **12 customer agents** — Executive Sponsor, IT Manager, Customer PM, functional key users, a business analyst, and the reluctant archetypes every consultant dreads
- **2 cross-functional agents** — QA Lead and PMO

The simulation runs through 6 SAP Activate phases: **Discover → Prepare → Explore → Realize → Deploy → Run**. Agents attend meetings, produce deliverables, raise issues, escalate blockers, and progress (or derail) the project based on their personalities and the decisions you make.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Mission Controller (Next.js 15 + React + Tailwind)         │
│  ┌──────────────┬─────────────┬────────────┬──────────────┐ │
│  │  Left Sidebar│  Main Feed  │  Context   │  Stakeholder │ │
│  │  (agents +   │  (SSE event │  Panel     │  View        │ │
│  │   phases)    │   stream)   │            │              │ │
│  └──────────────┴─────────────┴────────────┴──────────────┘ │
│                       REST + SSE                             │
├─────────────────────────────────────────────────────────────┤
│  Conductor / Orchestrator (FastAPI + asyncio)               │
│  ┌──────────────┬─────────────┬────────────┬──────────────┐ │
│  │  Agent       │  Phase      │  Meeting   │  State       │ │
│  │  Factory     │  Manager    │  Scheduler │  Machine     │ │
│  └──────────────┴─────────────┴────────────┴──────────────┘ │
│                    30 Agent Instances                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  BaseAgent (think / act / memory / persist)            │ │
│  │  Role subclasses × 30  ←→  LiteLLM Gateway            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Frontend:** Next.js 15 · React · Tailwind CSS · shadcn/ui · SSE streaming  
**Backend:** Python 3.12 · FastAPI · asyncio · LiteLLM · Server-Sent Events

---

## Features

- **30 unique AI agents** with deep role descriptions, personalities, and domain expertise
- **SAP Activate methodology** — all 6 phases with per-phase objectives and completion gates
- **Real-time event stream** — watch agents think and act via SSE as the simulation ticks
- **Intelligence tiers** — 4 model tiers map to seniority: Opus for strategy, Sonnet for domain leads, Gemini for operational roles, budget models for difficult archetypes
- **Personality system** — customer-side agents roll engagement levels (champion / neutral / resistant / ghost) that drift over time
- **Meeting scheduler** — phase-appropriate meetings (kick-off, workshops, sprint reviews, go/no-go gates)
- **Artifact generation** — agents produce deliverables: fit-gap lists, config specs, test scripts, cutover plans
- **Mission Controller UI** — 4-column dashboard with agent roster, live feed, context panel, and stakeholder view
- **Admin API** — operator controls: start / pause / stop / step the simulation, inject events
- **Project persistence** — full state save/resume; pick up where you left off

---

## Intelligence Tiers

Agents are assigned LLM models that match their seniority and complexity of reasoning:

| Tier | Label | Model | Agents |
|------|-------|-------|--------|
| 1 | Strategic | `claude-4-6-opus` | PM_ALEX, ARCH_SARA, EXEC_VICTOR, PMO_NIKO |
| 2 | Senior | `claude-4-6-sonnet` | Module leads, Basis, QA, IT Mgr, Cust PM |
| 3 | Operational | `gemini-2.5-pro` | Developers, key users, business analysts |
| 4 | Basic | `qwen3.6-plus` | Low-engagement archetypes (ghost, reluctant) |

This creates realistic variance: strategic agents handle ambiguity and trade-offs, operational agents execute but miss context, and basic agents behave as difficult stakeholders do in real projects.

---

## Agent Roster

### Consultant Side (16)

| Codename | Name | Role | Tier |
|----------|------|------|------|
| PM_ALEX | Alex | Project Manager | Strategic |
| ARCH_SARA | Sara | Solution Architect | Strategic |
| PMO_NIKO | Niko | PMO / Governance | Strategic |
| FI_CHEN | Chen | FI Functional Consultant | Senior |
| CO_MARTA | Marta | CO Functional Consultant | Senior |
| MM_RAVI | Ravi | MM Functional Consultant | Senior |
| SD_ISLA | Isla | SD Functional Consultant | Senior |
| PP_JONAS | Jonas | PP Functional Consultant | Senior |
| WM_FATIMA | Fatima | WM / EWM Consultant | Senior |
| INT_MARCO | Marco | Integration Lead | Senior |
| SEC_DIANA | Diana | Security & Auth Lead | Senior |
| BI_SAM | Sam | BI / Analytics Lead | Senior |
| CHG_NADIA | Nadia | Change Management Lead | Senior |
| DM_FELIX | Felix | Data Migration Lead | Senior |
| BASIS_KURT | Kurt | Basis Administrator | Senior |
| DEV_PRIYA | Priya | ABAP Developer | Operational |
| DEV_LEON | Leon | ABAP Developer | Operational |

### Customer Side (12)

| Codename | Name | Role | Tier |
|----------|------|------|------|
| EXEC_VICTOR | Victor | Executive Sponsor | Strategic |
| IT_MGR_HELEN | Helen | IT Manager | Senior |
| CUST_PM_OMAR | Omar | Customer Project Manager | Senior |
| QA_CLAIRE | Claire | QA Lead (cross-functional) | Senior |
| FI_KU_ROSE | Rose | FI Key User | Operational |
| CO_KU_BJORN | Björn | CO Key User | Operational |
| MM_KU_GRACE | Grace | MM Key User | Operational |
| SD_KU_TONY | Tony | SD Key User | Operational |
| BA_CUST_JAMES | James | Customer Business Analyst | Operational |
| WM_KU_ELENA | Elena | WM Key User (difficult) | Basic |
| PP_KU_IBRAHIM | Ibrahim | PP Key User (low availability) | Basic |
| HR_KU_SOPHIE | Sophie | HR Key User (peripheral) | Basic |
| CHAMP_LEILA | Leila | Change Champion (reluctant) | Basic |

---

## How to Run

### Prerequisites

- Python 3.12+
- Node.js 18+ with pnpm
- A LiteLLM-compatible gateway (or configure `projects/<name>/settings.json` to point to yours)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Mission Controller available at `http://localhost:3000`

### One-Shot Start (both services)

```bash
./start.sh
```

---

## Project Structure

```
sapsim/
├── README.md
├── start.sh                    # Start both backend + frontend
├── INTEGRATION_TEST.md         # Integration test notes
│
├── backend/
│   ├── main.py                 # FastAPI app factory + CORS + router mount
│   ├── config.py               # Project settings loader (Pydantic)
│   ├── requirements.txt
│   │
│   ├── agents/
│   │   ├── base_agent.py       # BaseAgent: think / act / memory / persist
│   │   ├── factory.py          # Agent instantiation registry (all 30)
│   │   ├── intelligence.py     # Intelligence tier → model mapping
│   │   ├── orchestrator.py     # Conductor: simulation loop, tick, SSE emit
│   │   ├── personality.py      # Customer personality rolls + drift
│   │   ├── roles/              # 30 role subclasses (one file per agent)
│   │   └── skills/             # Domain knowledge .md files (FI, MM, SD, etc.)
│   │
│   ├── api/
│   │   ├── routes.py           # Public REST endpoints
│   │   ├── admin.py            # Admin/operator endpoints (/api/admin/*)
│   │   ├── models.py           # Request/response Pydantic models
│   │   └── sse.py              # EventBus + SSE stream
│   │
│   ├── simulation/
│   │   ├── engine.py           # Simulation engine entry point
│   │   ├── phase_manager.py    # SAP Activate phases + objective tracking
│   │   ├── meeting_scheduler.py# Phase-appropriate meeting generation
│   │   └── state_machine.py    # Project state: IDLE/RUNNING/PAUSED/STOPPED
│   │
│   ├── utils/
│   │   ├── litellm_client.py   # LiteLLM gateway wrapper
│   │   └── persistence.py      # Agent state + memory save/load
│   │
│   ├── artifacts/              # Generated project deliverables (per-project)
│   ├── tests/                  # Backend test suite
│   └── venv/                   # Python virtual environment (not committed)
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx          # Root layout + theme
│   │   └── page.tsx            # SAPSimDashboard — 4-column layout
│   │
│   ├── components/
│   │   └── sap-sim/
│   │       ├── top-bar.tsx         # Project controls + simulation status
│   │       ├── left-sidebar.tsx    # Agent roster + phase navigator
│   │       ├── main-feed.tsx       # Live SSE event feed
│   │       ├── context-panel.tsx   # Agent/meeting context detail
│   │       ├── stakeholder-view.tsx# Stakeholder engagement overview
│   │       └── modals.tsx          # Settings, project setup, agent detail
│   │
│   ├── hooks/                  # React hooks (useSimulationFeed, etc.)
│   ├── lib/                    # Types, API client utilities
│   └── public/                 # Static assets
│
└── projects/                   # Per-project state + settings (gitignored)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend framework | Next.js 15 (App Router) |
| UI components | React 19 + shadcn/ui + Radix UI |
| Styling | Tailwind CSS |
| Real-time updates | Server-Sent Events (SSE) |
| Backend framework | FastAPI 0.135 |
| Async runtime | Python asyncio + uvicorn |
| LLM routing | LiteLLM (multi-model gateway) |
| Data validation | Pydantic v2 |
| State persistence | JSON files (per-project directory) |
| Package manager (FE) | pnpm |

---

## Configuration

Each project stores its settings in `projects/<project-name>/settings.json`:

```json
{
  "litellm_base_url": "http://localhost:4000",
  "litellm_api_key": "your-key-here"
}
```

Point `litellm_base_url` at any OpenAI-compatible gateway (LiteLLM Proxy, OpenAI, SAP AI Core, etc.).

---

## Development

```bash
# Run backend tests
cd backend && python -m pytest tests/

# Check backend health
curl http://localhost:8000/health

# Watch SSE stream (requires a running simulation)
curl -N http://localhost:8000/api/events/<project-id>
```

---

*Built with 30 AI personas and a healthy respect for the chaos of real SAP projects.*
