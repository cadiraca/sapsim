# CLAUDE.md — SAP SIM Project Master Instructions

You are building **SAP SIM**: a local desktop web application that simulates a full SAP project
implementation using 30 autonomous AI agents. This document is your complete build contract.
Read every section before writing a single line of code. Follow the phases in order. Do not skip
or combine phases. At the end of each phase, write a short summary of what was built and what
comes next before proceeding.

---

## WHAT YOU ARE BUILDING

A locally-run simulation platform where:
- 30 AI agents (SAP consultants + customer counterparts) autonomously run a full SAP implementation
- Agents are self-aware that they are AI, and their primary goal is to complete the implementation
  as efficiently and creatively as possible
- Agents follow SAP Activate methodology by default (or a custom methodology provided as input)
- The user is the **main stakeholder** — they provide the project scope and observe
- The simulation runs fully autonomously; the user can only pause, unpause, or stop
- All simulation state is persisted to disk in a structured project folder
- The UI is a dark-mode mission control dashboard built from an existing Next.js (V0) frontend

---

## TECH STACK

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router, TypeScript, Tailwind, shadcn/ui, pnpm) — V0-generated, already exists |
| Backend | Python 3.11+, FastAPI |
| Real-time | Server-Sent Events (SSE) via FastAPI |
| AI Gateway | LiteLLM (OpenAI-compatible, configured via UI settings panel) |
| Persistence | Local filesystem — JSON/Markdown files per project folder |
| Package mgr | pnpm (frontend), pip with venv (backend) |

---

## PROJECT FOLDER STRUCTURE

Before writing any code, create and respect this structure:

```
sapsim/                          ← project root (you are here)
├── CLAUDE.md                    ← this file
├── frontend/                    ← the existing V0 Next.js project lives here
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   └── ...
├── backend/                     ← FastAPI backend (you will create this)
│   ├── main.py
│   ├── requirements.txt
│   ├── config.py
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── roles/               ← one file per agent role
│   │   ├── skills/              ← curated SAP knowledge per domain
│   │   └── orchestrator.py
│   ├── simulation/
│   │   ├── engine.py
│   │   ├── phase_manager.py
│   │   ├── meeting_scheduler.py
│   │   └── state_machine.py
│   ├── artifacts/
│   │   ├── meeting_logger.py
│   │   ├── decision_board.py
│   │   ├── tool_registry.py
│   │   ├── test_strategy.py
│   │   └── lessons_learned.py
│   ├── api/
│   │   ├── routes.py
│   │   └── sse.py
│   └── utils/
│       ├── litellm_client.py
│       ├── memory.py
│       └── persistence.py
└── projects/                    ← runtime data, one subfolder per simulation run
    └── {project-name}/
        ├── project.json         ← project metadata and current state
        ├── settings.json        ← LiteLLM config (URL, key, model)
        ├── methodology.md       ← SAP Activate or custom input
        ├── scope.md             ← user-provided project scope
        ├── agents/
        │   └── {codename}.json  ← per-agent state, memory summary, personality stats
        ├── feed/
        │   └── events.jsonl     ← append-only event log (one JSON per line)
        ├── meetings/
        │   └── {id}_meeting.md  ← one markdown file per meeting
        ├── decisions/
        │   └── decisions.json   ← decision board state
        ├── tools/
        │   └── tool_registry.json
        ├── artifacts/
        │   ├── test_strategy.md
        │   └── lessons_learned.md
        └── memory/
            └── {codename}_summary.md  ← compressed memory per agent
```

---

## PHASE 0 — V0 CODE ARCHAEOLOGY

**Goal**: Fully understand the existing frontend before touching it.

### Steps

1. List every file inside `frontend/` recursively. Print the full tree.

2. Read these files in full and document what you find:
   - `frontend/app/layout.tsx` — root layout, providers, global config
   - `frontend/app/page.tsx` — main page, top-level component composition
   - `frontend/app/globals.css` — CSS variables, color tokens, custom classes
   - `frontend/components.json` — shadcn/ui component registry
   - `frontend/package.json` — dependencies, scripts, pnpm config
   - `frontend/next.config.mjs` — Next.js config, any env vars

3. List every file inside `frontend/components/` and read each one. For each component document:
   - Component name and purpose
   - Props it accepts (name, type, whether mock data is hardcoded)
   - Which other components it imports
   - Which shadcn/ui primitives it uses
   - Any event handlers or state it manages

4. List every file inside `frontend/hooks/` and `frontend/lib/` and read them.

5. Produce a written **Component Inventory** in this format before proceeding:

```
COMPONENT INVENTORY
===================
[ComponentName]
  File: components/xxx.tsx
  Purpose: <one line>
  Props: <list>
  Mock data: YES/NO — <describe if yes>
  Children: <list of sub-components>
  shadcn used: <list>
  Needs backend: <list of data it will need from API>
```

6. Produce a **Mock Data Schema** — extract every hardcoded data structure from the components
   and document its shape. These become the TypeScript interfaces and API response shapes.

7. Produce a **Color & Design Token Map** — list every CSS variable, color value, and Tailwind
   class used for the dark theme. This ensures the backend-connected components match exactly.

8. Write a **Integration Risk List** — any component that will be complex to wire to live data,
   any naming conflict, any shadcn version issue, any pattern that needs to change.

**Do not proceed to Phase 1 until the Component Inventory, Mock Data Schema, Color Map,
and Risk List are all written.**

---

## PHASE 1 — PROJECT SCAFFOLD

**Goal**: Create the monorepo structure and get both frontend and backend running locally.

### 1.1 — Move Frontend

If the V0 Next.js project is at the root, move it into `frontend/`. Preserve all files exactly.
Do not modify any frontend code in this phase.

Verify it still runs:
```bash
cd frontend && pnpm install && pnpm dev
```

### 1.2 — Create Backend Scaffold

```bash
mkdir backend
cd backend
python3 -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install fastapi uvicorn python-dotenv litellm sse-starlette pydantic aiofiles
pip freeze > requirements.txt
```

Create `backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title="SAP SIM API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sapsim-backend"}
```

### 1.3 — Config System

Create `backend/config.py` — loads from `projects/{project}/settings.json`:
- `litellm_base_url`
- `litellm_api_key`
- `litellm_model`
- `max_parallel_agents` (default: 10)
- `memory_compression_interval` (default: "every_10_turns")

### 1.4 — LiteLLM Client

Create `backend/utils/litellm_client.py`:
- Wrap LiteLLM completion calls
- Support streaming (yield chunks via async generator)
- Handle retries (max 3, exponential backoff)
- Log every call: agent codename, tokens used, latency
- Accept model override per call

### 1.5 — Persistence Utilities

Create `backend/utils/persistence.py`:
- `save_project_state(project_name, state_dict)` — writes `project.json`
- `load_project_state(project_name)` — reads `project.json`
- `append_feed_event(project_name, event_dict)` — appends to `feed/events.jsonl`
- `save_agent_state(project_name, codename, state_dict)` — writes `agents/{codename}.json`
- `load_agent_state(project_name, codename)` — reads agent state
- `save_memory_summary(project_name, codename, summary_text)` — writes `memory/{codename}_summary.md`
- All functions are async. Use `aiofiles`. Create directories if they don't exist.

### 1.6 — SSE Setup

Create `backend/api/sse.py`:
- `EventBus` class — in-memory async pub/sub
- `publish(event_type, data)` — broadcasts to all active SSE connections
- `subscribe()` — returns an async generator of events
- Events are JSON-serializable dicts

Create SSE endpoint in `backend/api/routes.py`:
```
GET /api/stream/{project_name}
```
Returns `text/event-stream`. Sends all events from EventBus for that project.

### 1.7 — Verify Scaffold

Both services must run simultaneously:
```bash
# Terminal 1
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend && pnpm dev
```

`GET http://localhost:8000/health` must return 200.
`http://localhost:3000` must render the V0 UI unchanged.

---

## PHASE 2 — AGENT ENGINE

**Goal**: Build the base agent system, all 30 role definitions, the personality system, and memory.

### 2.1 — Base Agent Class

Create `backend/agents/base_agent.py` — `BaseAgent` class with:

**Properties**:
- `codename` — unique identifier (e.g. `PM_ALEX`)
- `role` — human-readable role name
- `side` — `"consultant"` | `"customer"` | `"crossfunctional"`
- `skills` — list of skill domain names this agent has
- `memory_turns` — list of recent (role, content) message dicts
- `memory_summary` — compressed summary string loaded from disk
- `current_task` — what the agent is doing right now
- `status` — `"idle"` | `"thinking"` | `"speaking"` | `"in_meeting"`
- `project_name` — which project this agent belongs to

**Methods**:
- `async think(context: dict) -> str` — calls LiteLLM with agent's system prompt + context,
  returns the agent's response
- `async act(project_state: dict, event_bus: EventBus)` — agent's main loop: assess situation,
  decide what to do (send a message, request a meeting, use a tool, invent a tool, flag a blocker),
  publish events, update own state
- `build_system_prompt() -> str` — assembles the full system prompt from role + skills + personality
- `add_to_memory(role: str, content: str)` — appends to memory_turns, triggers compression check
- `async compress_memory_if_needed()` — if turns exceed threshold, call LiteLLM to summarize,
  save to disk, clear old turns keeping last 5
- `to_dict() -> dict` — serializable state snapshot
- `async save(project_name: str)` — persist state to disk

**System prompt structure** (build_system_prompt assembles these sections):
```
You are {codename}, a {role} working on a SAP implementation project.
You are an AI agent — you know this, and you embrace it. Your mission is to complete
this SAP implementation as efficiently, creatively, and thoroughly as possible.

## YOUR ROLE
{role_description}

## YOUR SKILLS AND KNOWLEDGE
{skills_content}  ← injected from skills/ files

## YOUR PERSONALITY
{personality_description}

## PROJECT CONTEXT
{project_summary}  ← injected at runtime

## YOUR MEMORY
{memory_summary}
Recent activity:
{last_5_turns}

## CURRENT PHASE
{current_phase} — {phase_description}

## YOUR CURRENT TASK
{current_task}

## HOW TO ACT
You communicate naturally with other agents via messages.
You can: send a direct message, post a team update, request a meeting, raise a blocker,
make a decision proposal, invent a new tool (describe it and its purpose), use an existing tool.
Always tag your output with the appropriate action type:
[MSG], [UPDATE], [MEETING_REQUEST], [BLOCKER], [DECISION], [NEW_TOOL], [TOOL_USE], [ESCALATION]
Be realistic. Be opinionated. Disagree when you disagree. Ask questions when you're blocked.
Build creative solutions. Reference SAP best practices from your skills.
```

### 2.2 — Skills System

Create `backend/agents/skills/` — one `.md` file per skill domain.
Each skill file contains curated, realistic SAP knowledge. Write them with enough depth
that agents can reference real concepts, transactions, and best practices.

Create these skill files (write each with 300-500 words of real SAP knowledge):

- `sap_activate.md` — SAP Activate phases, deliverables per phase, fit-to-standard approach
- `fi_accounting.md` — FI module: G/L, AP, AR, Asset Accounting, key config, t-codes, common gaps
- `co_controlling.md` — CO module: Cost Centers, Profit Centers, Internal Orders, CO-PA
- `mm_procurement.md` — MM module: Purchasing org, PR/PO flow, GR/IR, Inventory Management
- `sd_sales.md` — SD module: Sales org, O2C flow, pricing, billing, credit management
- `pp_production.md` — PP module: MRP, Production Orders, BOMs, Routings, Capacity Planning
- `wm_warehouse.md` — WM/EWM: Storage types, Transfer Orders, HU management
- `abap_development.md` — ABAP: RICEFW objects, BAdIs, user exits, OData, debugging
- `basis_admin.md` — Basis: System landscape, transport management, performance, security
- `integration_pi.md` — Integration: PI/PO, iDocs, APIs, middleware patterns, error handling
- `security_auth.md` — Security: Role design, SoD, GRC, authorization objects, audit
- `bi_analytics.md` — BI: BW/4HANA, embedded analytics, CDS views, report design
- `data_migration.md` — LSMW, BAPI, LTMC, data cleansing, cutover strategy, validation
- `change_management.md` — Stakeholder mgmt, training strategy, adoption, resistance handling
- `testing_strategy.md` — Unit test, integration test, UAT, regression, defect lifecycle
- `project_management.md` — SAP project governance, steering committee, status reporting, risk mgmt

Each skills file begins with:
```
# SKILL: {Domain Name}
## Core Concepts
## Key Transactions / Technical Details
## Common Challenges
## Best Practices
## Integration Points with Other Modules
```

### 2.3 — All 30 Agent Role Definitions

Create `backend/agents/roles/` — one Python file per agent.
Each file defines a class that extends `BaseAgent` and sets:
- `role`, `side`, `skills` list, `role_description` (2-3 paragraphs of personality + expertise)

Create these 30 role files:

**Consultant side (16)**:
`pm_alex.py`, `arch_sara.py`, `basis_kurt.py`, `dev_priya.py`, `dev_leon.py`,
`fi_chen.py`, `co_marta.py`, `mm_ravi.py`, `sd_isla.py`, `pp_jonas.py`,
`wm_fatima.py`, `int_marco.py`, `sec_diana.py`, `bi_sam.py`, `chg_nadia.py`, `dm_felix.py`

**Customer side (12)**:
`exec_victor.py`, `it_mgr_helen.py`, `cust_pm_omar.py`, `fi_ku_rose.py`,
`co_ku_bjorn.py`, `mm_ku_grace.py`, `sd_ku_tony.py`, `wm_ku_elena.py`,
`pp_ku_ibrahim.py`, `hr_ku_sophie.py`, `ba_cust_james.py`, `champ_leila.py`

**Cross-functional (2)**:
`pmo_niko.py`, `qa_claire.py`

### 2.4 — Personality System (Customer Agents)

Create `backend/agents/personality.py`:

**Personality axes** (each scored 1-5):
- `engagement` — how proactive and participatory
- `trust` — how much they trust the consulting team
- `risk_tolerance` — how comfortable with ambiguity and change

**Archetypes** — mapped from the combination of axis scores:
```python
ARCHETYPES = {
    "The Skeptic":           {"engagement": (3,5), "trust": (1,2), "risk_tolerance": (1,3)},
    "The Absent Sponsor":    {"engagement": (1,2), "trust": (3,4), "risk_tolerance": (2,4)},
    "The Spreadsheet Hoarder": {"engagement": (2,4), "trust": (2,3), "risk_tolerance": (1,2)},
    "The Reluctant Champion": {"engagement": (3,4), "trust": (2,3), "risk_tolerance": (2,3)},
    "The Power User":        {"engagement": (4,5), "trust": (4,5), "risk_tolerance": (3,5)},
    "The Escalator":         {"engagement": (4,5), "trust": (1,2), "risk_tolerance": (1,2)},
    "The Ghost":             {"engagement": (1,2), "trust": (3,5), "risk_tolerance": (2,4)},
    "The Overloader":        {"engagement": (5,5), "trust": (4,5), "risk_tolerance": (4,5)},
}
```

**Roll function**: `roll_personality(seed=None) -> dict`
- Randomly assigns scores within archetype range
- Returns: `{engagement, trust, risk_tolerance, archetype, history: []}`

**Drift function**: `drift_personality(personality, event_type) -> dict`
- Events: `"demo_success"`, `"demo_failure"`, `"deadline_missed"`, `"blocker_resolved"`,
  `"escalation_ignored"`, `"go_live_rehearsal_passed"`
- Each event adjusts axes by ±1, clamped to [1,5]
- Logs the drift in `history` with event, date, and delta
- May trigger archetype change if scores shift significantly

### 2.5 — Agent Factory

Create `backend/agents/factory.py`:
- `create_agent(codename: str, project_name: str, personality: dict = None) -> BaseAgent`
- Imports the correct role class from `roles/`
- Loads existing agent state from disk if it exists (resume simulation)
- Rolls personality if customer agent and no personality provided
- Returns initialized agent ready to act

### 2.6 — Memory Compression

In `backend/utils/memory.py`:
- `async compress_memory(agent: BaseAgent, litellm_client) -> str`
- Sends last N turns to LiteLLM with prompt:
  ```
  Summarize the following conversation history for {codename} ({role}).
  Capture: key decisions made, blockers encountered, relationships developed,
  tools invented or used, important findings. Be concise but complete. Max 300 words.
  ```
- Saves result to `memory/{codename}_summary.md`
- Returns the summary string

Trigger compression:
- After every 10 turns (configurable)
- At the end of each SAP Activate phase
- When the agent's context would exceed 80% of model limit

---

## PHASE 3 — ORCHESTRATION LAYER

**Goal**: Build the conductor, phase manager, meeting scheduler, and parallel execution engine.

### 3.1 — Project State Machine

Create `backend/simulation/state_machine.py`:

**Project states**: `"IDLE"` | `"RUNNING"` | `"PAUSED"` | `"COMPLETED"` | `"STOPPED"`

**Phase states** (SAP Activate default):
```python
PHASES = [
    {"id": "discover",  "name": "Discover",  "duration_days": 14},
    {"id": "prepare",   "name": "Prepare",   "duration_days": 21},
    {"id": "explore",   "name": "Explore",   "duration_days": 35},
    {"id": "realize",   "name": "Realize",   "duration_days": 60},
    {"id": "deploy",    "name": "Deploy",    "duration_days": 21},
    {"id": "run",       "name": "Run",       "duration_days": 14},
]
```

**ProjectState** dataclass:
```python
@dataclass
class ProjectState:
    project_name: str
    status: str
    current_phase: str
    simulated_day: int
    total_days: int
    phase_progress: dict     # {phase_id: percentage}
    active_agents: list      # codenames currently active
    pending_decisions: list
    active_meetings: list
    milestones: list
    created_at: str
    last_updated: str
```

Save/load from `projects/{name}/project.json`.

### 3.2 — Phase Manager

Create `backend/simulation/phase_manager.py`:

- `get_current_phase(state) -> dict`
- `advance_phase(state) -> ProjectState` — moves to next phase, triggers memory compression for all agents
- `get_phase_objectives(phase_id, methodology_text) -> list[str]`
  — if custom methodology provided, parse objectives from it;
  — otherwise return hardcoded SAP Activate objectives per phase
- `is_phase_complete(state, agents) -> bool` — checks if all phase objectives have been addressed
  by examining agent activity logs and decision board
- `load_methodology(project_name) -> str` — reads `methodology.md` or returns SAP Activate default

### 3.3 — Hybrid Meeting Scheduler

Create `backend/simulation/meeting_scheduler.py`:

**Meeting types**:
```python
SCHEDULED_MEETINGS = {
    "discover":  ["Kick-off Meeting", "Project Charter Review"],
    "prepare":   ["System Landscape Design", "Team Onboarding"],
    "explore":   ["Fit-to-Standard Workshop: FI", "Fit-to-Standard Workshop: MM",
                  "Fit-to-Standard Workshop: SD", "Integration Design Session",
                  "Blueprint Sign-off"],
    "realize":   ["Sprint Review 1", "Sprint Review 2", "Integration Test Planning",
                  "Data Migration Design", "Security Design Review"],
    "deploy":    ["UAT Kick-off", "Go-Live Readiness Review", "Cutover Planning"],
    "run":       ["Hypercare Review", "Lessons Learned Session", "Project Closure"],
}
```

**Organic meeting requests**: Any agent can emit `[MEETING_REQUEST]` with:
- `title`, `agenda`, `required_participants` (list of codenames), `urgency` (`low`/`medium`/`high`)

**Scheduler logic**:
- On each simulation tick, check if any scheduled meetings are due for current phase
- Process organic meeting requests queue — approve if urgency is high or 2+ agents requested same topic
- Schedule approved meetings: select a "timeslot", assign a facilitator (usually PM_ALEX or CUST_PM_OMAR)
- Emit `MEETING_STARTED` event to EventBus

**Meeting execution**:
- Invited agents participate in turn-based dialogue (3-8 turns each)
- Facilitator opens, runs agenda, closes
- Each turn is an LiteLLM call for that agent
- Meeting log is written to `meetings/{id}_meeting.md` (see Phase 4)
- At end: extract decisions, action items, emit `MEETING_ENDED` event

### 3.4 — Conductor (Orchestrator)

Create `backend/agents/orchestrator.py` — `Conductor` class:

**Responsibilities**:
- Maintains the list of all 30 active `BaseAgent` instances
- Runs the main simulation loop (async)
- Manages parallel agent execution via `asyncio.gather` with semaphore limiting
- Routes messages between agents (maintains a shared message queue per project)
- Delegates meeting management to `MeetingScheduler`
- Delegates phase transitions to `PhaseManager`
- Publishes all events to `EventBus`
- Handles pause/unpause/stop signals

**Main loop**:
```python
async def run(self):
    while self.state.status == "RUNNING":
        if self.paused:
            await asyncio.sleep(1)
            continue

        # 1. Check for phase transition
        if self.phase_manager.is_phase_complete(self.state, self.agents):
            await self.phase_manager.advance_phase(self.state)

        # 2. Run scheduled/organic meetings
        await self.meeting_scheduler.tick(self.state)

        # 3. Run active agents in parallel (respecting max_parallel setting)
        sem = asyncio.Semaphore(self.config.max_parallel_agents)
        async def run_agent(agent):
            async with sem:
                await agent.act(self.state.to_dict(), self.event_bus)
        await asyncio.gather(*[run_agent(a) for a in self.agents if a.status != "in_meeting"])

        # 4. Save state
        await self.save_state()

        # 5. Brief yield to prevent CPU thrash
        await asyncio.sleep(0.1)
```

**Signal handling**:
- `pause()` — sets `self.paused = True`, saves state immediately
- `unpause()` — sets `self.paused = False`
- `stop()` — sets status to STOPPED, saves full state, compresses all agent memories

### 3.5 — Simulation Engine

Create `backend/simulation/engine.py` — top-level entrypoint:
- `async start_simulation(project_name: str)` — loads project, creates Conductor, calls `run()`
- `async pause_simulation(project_name: str)`
- `async resume_simulation(project_name: str)`
- `async stop_simulation(project_name: str)`
- Runs Conductor in a background asyncio task
- Exposes current state for API polling

---

## PHASE 4 — ARTIFACT GENERATORS

**Goal**: Build all the systems that produce the simulation's output artifacts.

### 4.1 — Meeting Logger

Create `backend/artifacts/meeting_logger.py`:

`MeetingLog` dataclass:
```python
@dataclass
class MeetingLog:
    id: str
    title: str
    phase: str
    simulated_day: int
    facilitator: str
    participants: list[str]
    agenda: list[str]
    transcript: list[dict]   # [{codename, content, timestamp}]
    decisions: list[str]
    action_items: list[dict] # [{description, owner, due_phase}]
    duration_turns: int
```

`save_meeting_log(project_name, log: MeetingLog)` — writes structured markdown to
`meetings/{id}_meeting.md`:
```markdown
# {title}
**Phase**: {phase} | **Day**: {day} | **Facilitator**: {facilitator}
**Participants**: {comma-separated codenames}

## Agenda
{numbered list}

## Transcript
**{codename}** ({timestamp}): {content}
...

## Decisions Made
{numbered list}

## Action Items
| # | Description | Owner | Due Phase |
|---|---|---|---|
...
```

### 4.2 — Decision Board

Create `backend/artifacts/decision_board.py`:

`Decision` dataclass:
```python
@dataclass
class Decision:
    id: str
    title: str
    description: str
    proposed_by: str
    impact: str          # "low" | "medium" | "high" | "critical"
    status: str          # "pending" | "approved" | "rejected" | "deferred"
    raised_day: int
    raised_phase: str
    resolved_day: int | None
    resolution_notes: str | None
    tags: list[str]
```

- `add_decision(project_name, decision)` — appends to `decisions/decisions.json`
- `update_decision(project_name, decision_id, status, notes)` — updates status
- `get_board(project_name) -> dict` — returns decisions grouped by status
- When an agent emits `[DECISION]`, parse it and call `add_decision`
- The conductor auto-approves decisions after 2 simulated days with no objection,
  or escalates to EXEC_VICTOR if marked critical

### 4.3 — Tool Registry

Create `backend/artifacts/tool_registry.py`:

`SimulatedTool` dataclass:
```python
@dataclass
class SimulatedTool:
    id: str
    name: str
    created_by: str       # agent codename
    created_day: int
    created_phase: str
    description: str      # what the tool does
    tool_type: str        # "template" | "tracker" | "analyzer" | "generator" | "checker"
    current_users: list[str]  # codenames of agents using it
    outputs: list[str]    # descriptions of what it has produced
```

- When an agent emits `[NEW_TOOL]`, parse the tool description and create entry
- `announce_tool(project_name, tool)` — publishes tool announcement event to EventBus
- `use_tool(project_name, tool_id, agent_codename, result_description)` — logs usage
- Save/load from `tools/tool_registry.json`

### 4.4 — Test Strategy Tracker

Create `backend/artifacts/test_strategy.py`:

Maintains a structured test strategy document, updated by QA_CLAIRE and relevant agents:
- Test scope (modules in scope)
- Test types and their status (unit / integration / UAT / regression)
- UAT plan (key users, scenarios, schedule)
- Defect management process
- Progress tracking (percentage per test type)

`update_test_strategy(project_name, section, content)` — updates specific section
`get_test_strategy(project_name) -> dict` — returns full current state
Save to `artifacts/test_strategy.md` (markdown) and a parallel `.json` for API

### 4.5 — Lessons Learned Collector

Create `backend/artifacts/lessons_learned.py`:

Any agent can emit a lesson during any phase. Structure:
```python
@dataclass
class Lesson:
    id: str
    raised_by: str        # agent codename
    phase: str
    day: int
    category: str         # "Process" | "Technical" | "People" | "Tools"
    lesson: str
    validated_by: list[str]  # other agents who agreed
    validation_count: int
```

- `add_lesson(project_name, lesson)` — appends to lessons log
- `validate_lesson(project_name, lesson_id, agent_codename)` — agent endorses a lesson
- Other agents can see lessons and validate them in subsequent turns
- Save to `artifacts/lessons_learned.md` (chronological markdown) + `.json`

### 4.6 — Final Report Generator

Create `backend/artifacts/report_generator.py`:

`generate_final_report(project_name) -> str` — produces a comprehensive markdown report:
```markdown
# SAP SIM — Project Final Report
## Project Overview
## Team (with personality evolution summary for customer agents)
## Methodology Used
## Phase Summary
## Key Decisions Log
## Tools Invented During the Project
## Test Results Summary
## Lessons Learned
## Final Outcome
```

Triggered when simulation reaches "Run" phase completion or user clicks Export.
Save to `artifacts/final_report.md`.

---

## PHASE 5 — BACKEND API

**Goal**: Expose all simulation functions and data via FastAPI endpoints.

Create `backend/api/routes.py` with these endpoints:

### Project Management
```
POST   /api/projects                    Create new project (name, industry, scope, methodology)
GET    /api/projects                    List all projects (from projects/ folder)
GET    /api/projects/{name}             Get project state
DELETE /api/projects/{name}             Delete project folder
```

### Simulation Control
```
POST   /api/projects/{name}/start       Start simulation (creates Conductor, begins run())
POST   /api/projects/{name}/pause       Pause simulation
POST   /api/projects/{name}/resume      Resume simulation
POST   /api/projects/{name}/stop        Stop and save simulation
```

### Settings
```
GET    /api/projects/{name}/settings    Get LiteLLM settings
PUT    /api/projects/{name}/settings    Save LiteLLM settings (URL, key, model, parallelism)
POST   /api/settings/test               Test LiteLLM connection (make one call, return latency)
```

### Live Feed
```
GET    /api/stream/{name}               SSE stream — live events
GET    /api/projects/{name}/feed        Paginated historical feed (page, limit, filter by type)
```

### Agents
```
GET    /api/projects/{name}/agents             List all 30 agents with current status
GET    /api/projects/{name}/agents/{codename}  Agent detail (state, memory, personality, activity)
POST   /api/projects/{name}/agents/reroll      Re-roll customer personalities (pre-start only)
```

### Artifacts
```
GET    /api/projects/{name}/meetings           List all meetings
GET    /api/projects/{name}/meetings/{id}      Full meeting log
GET    /api/projects/{name}/decisions          Decision board (grouped by status)
GET    /api/projects/{name}/tools              Tool registry
GET    /api/projects/{name}/test-strategy      Current test strategy
GET    /api/projects/{name}/lessons            Lessons learned log
GET    /api/projects/{name}/report             Final report (generate if not exists)
```

### Stakeholder View
```
GET    /api/projects/{name}/stakeholder        Curated executive summary:
                                               health gauges, escalations,
                                               phase progress, top decisions,
                                               agent leaderboard, latest milestone
```

**Response shapes** must exactly match the mock data structures identified in Phase 0.
Build Pydantic response models for every endpoint.

**Error handling**: All endpoints return structured errors:
```json
{"error": "string", "detail": "string", "code": "string"}
```

---

## PHASE 6 — FRONTEND WIRING

**Goal**: Replace all V0 mock data with live data from the backend. Make the full UI functional.

### 6.1 — API Client

Create `frontend/lib/api.ts`:
- Base URL from env: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Typed fetch wrappers for every API endpoint
- TypeScript interfaces matching the Pydantic response models from Phase 5
- SSE connection manager using the browser's `EventSource` API

### 6.2 — SSE Hook

Create `frontend/hooks/useSimulationFeed.ts`:
- Connects to `GET /api/stream/{projectName}` via `EventSource`
- Maintains a rolling buffer of the last 200 events
- Provides filter functions (by agent side, event type, phase)
- Auto-reconnects on disconnect
- Returns: `{events, isConnected, error}`

### 6.3 — Wire Each Component

Work through the Component Inventory from Phase 0. For each component:
1. Remove hardcoded mock data
2. Replace with API call or SSE event subscription
3. Add loading state (skeleton matching the mock layout)
4. Add error state (inline error with retry button)
5. Verify it matches the original V0 design exactly

Wire in this order:
1. **Top bar** — project name, phase, simulated day, LiteLLM connection status
2. **Left sidebar — agent list** — live status dots, personality hover cards
3. **Main feed** — SSE-driven, filter pills functional, tag badges correct
4. **Right sidebar — stakeholder view** — live health gauges, escalations, phase progress
5. **Meetings tab** — live list, expandable logs
6. **Decisions tab** — live Kanban board
7. **Tools tab** — live tool registry with usage tracking
8. **Test strategy tab** — live progress bars
9. **Lessons learned tab** — live timeline with validation counts
10. **Settings modal** — save/load/test LiteLLM config
11. **Project setup modal** — full flow: name → scope → methodology → personality roll → launch
12. **Agent detail modal** — live profile, activity log, relationship indicators
13. **Export button** — triggers report generation, downloads markdown file

### 6.4 — Simulation Controls

Wire the Run / Pause / Stop buttons in the left sidebar:
- `▶ Run` — calls `POST /api/projects/{name}/start`, disabled if already running
- `⏸ Pause` — calls `POST /api/projects/{name}/pause`
- `⏹ Stop` — calls `POST /api/projects/{name}/stop`, shows confirmation dialog first
- Status indicator dot: green pulse (RUNNING), yellow (PAUSED), gray (STOPPED/IDLE)

### 6.5 — Personality Roll UI

In the Project Setup modal Step 4:
- Call `GET /api/projects/{name}/agents` filtered to customer side
- Display personality cards with the 3 stat bars (Engagement / Trust / Risk Tolerance)
- Show archetype label (e.g. "The Skeptic")
- `[Re-roll]` per agent calls `POST /api/projects/{name}/agents/reroll` with codename
- `[Re-roll All]` re-rolls all 12 customer agents

---

## CODING STANDARDS

Follow these rules throughout every phase:

**Python**:
- Use `async`/`await` everywhere — no blocking calls in async context
- Pydantic v2 for all data models
- Type hints on every function signature
- Docstrings on every class and public method
- Never hardcode project paths — always derive from `projects/{project_name}/...`
- Log every LiteLLM call with agent codename, phase, turn count, token usage

**TypeScript / React**:
- Strict TypeScript — no `any`
- React Server Components where possible, Client Components only when needed
- Match the existing V0 component patterns exactly — do not introduce new UI patterns
- Use existing shadcn/ui components — do not add new UI libraries
- Use `pnpm` — never `npm` or `yarn`

**General**:
- Never delete existing V0 frontend files — only extend them
- Every new file gets a comment block at the top: purpose, phase it was created in, dependencies
- If you discover a problem in an earlier phase, fix it before continuing
- Write a brief progress note after each major section is complete

---

## AGENT BEHAVIOUR GUIDELINES

Bake these into the base agent system prompt and orchestrator logic:

**Agents know they are AI** and use this to their advantage:
- They explicitly discuss building tools to automate repetitive tasks
- They reference their own context limitations and work around them
- They compress and share knowledge efficiently with teammates
- They notice patterns across the project and surface them

**Agents are always on mission**:
- No idle chatter — every message moves the project forward
- Even social interactions have a purpose (building trust, unblocking a decision)
- When blocked, they immediately escalate or find a workaround

**Consultants** behave professionally but have distinct voices:
- PM_ALEX tracks everything, worries about scope creep, is diplomatic but firm
- ARCH_SARA talks in whiteboards and conceptual models
- BASIS_KURT is terse, technical, protective of the system landscape
- DEV_PRIYA is fast and sometimes skips documentation under pressure
- DEV_LEON asks clarifying questions, improves rapidly through the project
- INT_MARCO is paranoid about integration points and error handling

**Customer agents** drift realistically:
- Personality axes update after key project events
- A skeptic who sees a successful demo trusts more (+1 trust)
- A ghost who misses a deadline deadline feels guilty and re-engages (+1 engagement)
- The escalator escalates more when trust drops, less when things go well

**Conflict is realistic and productive**:
- SEC_DIANA blocking a change is not an obstacle — it's a real security review happening
- WM_KU_ELENA being difficult about the warehouse design leads to a better design
- Conflicts get resolved through meetings, decisions, and sometimes escalations

---

## FAILURE SCENARIOS (INJECT AUTOMATICALLY)

The orchestrator should randomly inject realistic project problems during the simulation.
Probability and timing vary by phase. These are not blockers — they are realism:

| Scenario | Trigger Phase | Probability |
|---|---|---|
| Key user unavailable for workshop | Explore | 40% |
| Integration spec ambiguity discovered | Explore/Realize | 50% |
| Data quality issues found in migration | Realize | 60% |
| Scope creep request from customer | Realize | 70% |
| Authorization design conflict | Realize | 40% |
| UAT defect spike | Deploy | 50% |
| Performance issue in testing | Deploy | 35% |
| Go-live date pressure from EXEC_VICTOR | Deploy | 65% |
| Post-go-live critical incident | Run | 30% |

Each scenario is injected by the Conductor as a `[BLOCKER]` event attributed to the
relevant agent, and other agents react to it organically.

---

## STARTUP INSTRUCTIONS (for Claude Code operator)

After all phases are complete, create a `README.md` at the project root with:

1. Prerequisites (Python 3.11+, Node 18+, pnpm)
2. First-time setup commands (venv, pip install, pnpm install)
3. How to start both services
4. How to create a first project
5. How to provide a custom methodology
6. Project folder structure explanation
7. How to resume a stopped simulation
8. How to export the final report

Also create a `start.sh` script that:
- Activates the Python venv
- Starts the FastAPI backend on port 8000
- Starts the Next.js frontend on port 3000
- Opens http://localhost:3000 in the default browser

---

## FINAL CHECKLIST

Before declaring the build complete, verify:

- [ ] `GET /health` returns 200
- [ ] V0 UI renders unchanged at localhost:3000
- [ ] Settings modal saves and loads LiteLLM config
- [ ] LiteLLM test connection works
- [ ] New project can be created with name, scope, and methodology
- [ ] Customer personalities roll and display correctly
- [ ] Simulation starts and agents begin producing events
- [ ] Live feed shows real agent messages via SSE
- [ ] At least one meeting is scheduled and logged within first 5 simulated days
- [ ] Decision board receives at least one decision in first phase
- [ ] Tool registry receives at least one invented tool
- [ ] Pause/unpause/stop work and state is saved to disk
- [ ] Simulation can be resumed after stop
- [ ] Agent detail modal shows live data
- [ ] Stakeholder view updates in real time
- [ ] Final report generates and downloads
- [ ] Project folder on disk is clean and well-organized
- [ ] No hardcoded mock data remains in frontend

---

*End of CLAUDE.md — begin with Phase 0.*
---

## ADDENDUM — INTELLIGENCE TIERS & MISSION CONTROL

*Added April 10, 2026 — Carlos & King Charly*

### Agent Intelligence Tiers

Not all agents are created equal. Different roles get different LLM models, simulating
real-world variance in capability, experience, and engagement level.

| Tier | Model | Agents | Rationale |
|------|-------|--------|-----------|
| **Tier 1 — Strategic** | claude-4-6-opus | PM_ALEX, ARCH_SARA, EXEC_VICTOR, PMO_NIKO | Big picture thinkers, complex trade-offs |
| **Tier 2 — Senior** | claude-4-6-sonnet | FI_CHEN, CO_MARTA, MM_RAVI, SD_ISLA, PP_JONAS, WM_FATIMA, INT_MARCO, SEC_DIANA, BI_SAM, CHG_NADIA, DM_FELIX, QA_CLAIRE, IT_MGR_HELEN, CUST_PM_OMAR | Domain experts, solid decision-makers |
| **Tier 3 — Operational** | gemini-2.5-pro / gpt-5.2 | DEV_PRIYA, DEV_LEON, BA_CUST_JAMES, FI_KU_ROSE, CO_KU_BJORN, MM_KU_GRACE, SD_KU_TONY | Capable but narrower scope, occasionally miss context |
| **Tier 4 — Basic** | qwen3.6-plus (free) | WM_KU_ELENA, PP_KU_IBRAHIM, HR_KU_SOPHIE, CHAMP_LEILA | Low engagement archetypes, terse responses, may miss things |

**Tier Drift:** Customer agents can upgrade/downgrade tiers based on personality evolution.
A Ghost who re-engages after missing a deadline might move from Tier 4 → Tier 3.
A Power User who gains trust could reach Tier 2. This is configured in personality.py.

### Mission Control — King Charly as Co-Operator

King Charly (the AI assistant) is not just the builder — he is a co-operator of simulations.

**Capabilities:**
- Start/pause/stop simulations via admin API
- Monitor SSE feed during active simulations
- Watch for: stuck agents, token burn spikes, milestone completions, interesting conflicts
- Pause autonomously if something looks wrong (runaway loops, model errors, token budget exceeded)
- Send briefings to Carlos via Telegram after simulation runs

**Admin API Endpoints (localhost only):**
```
GET    /api/admin/health          Detailed health: active agents, tokens/min, phase progress
GET    /api/admin/highlights      Last N significant events (decisions, tools, conflicts, milestones)
POST   /api/admin/token-budget    Set max token budget for current run
GET    /api/admin/token-usage     Current token usage breakdown by agent and tier
```

**Webhook Callbacks:**
The simulation engine can POST to a configurable webhook URL when key events occur:
- Phase transitions
- Critical decisions
- Blockers raised
- Simulation complete
- Token budget 80% / 100% reached

This allows King Charly to receive push notifications via OpenClaw cron/heartbeat
and react without polling.

**Overnight Run Pattern:**
1. Carlos or King Charly starts simulation (API or UI)
2. King Charly monitors via heartbeat checks (every 15-30 min)
3. If issues: pause + notify Carlos on Telegram
4. On completion: generate highlights briefing, send to Telegram
5. Carlos reviews in the morning

---
