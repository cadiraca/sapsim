# Phase 0: V0 Code Archaeology — SAP SIM Frontend Inventory

> **Generated:** 2026-04-13  
> **Source:** `/home/spider/repos/sapsim/`  
> **Purpose:** Foundation document for all subsequent development phases

---

## Table of Contents

1. [Deliverable A: Component Inventory](#deliverable-a-component-inventory)
2. [Deliverable B: Mock Data Schema](#deliverable-b-mock-data-schema)
3. [Deliverable C: Color & Design Token Map](#deliverable-c-color--design-token-map)
4. [Deliverable D: Integration Risk List](#deliverable-d-integration-risk-list)
5. [Deliverable E: Dependencies Summary](#deliverable-e-dependencies-summary)
6. [Appendix: File Tree & Architecture Overview](#appendix-file-tree--architecture-overview)

---

## Deliverable A: Component Inventory

### Layout & Page

#### `RootLayout`
- **File:** `app/layout.tsx`
- **Purpose:** Root HTML shell — sets dark mode class, loads fonts (Inter + JetBrains Mono), includes Vercel Analytics in production
- **Props:** `children: React.ReactNode`
- **Mock data:** NO
- **Children:** None (wraps everything)
- **shadcn used:** None
- **Notes:** `<html>` hardcoded to `class="dark"`. Theme is always dark — no toggle. Fonts declared via CSS variables `--font-inter` and `--font-mono` but globals.css `@theme` overrides with Geist (Vercel font) — **mismatch to fix**.

---

#### `SAPSimDashboard`
- **File:** `app/page.tsx`
- **Purpose:** Root page — orchestrates the 4-column layout and manages top-level simulation state
- **Props:** None (page component)
- **Mock data:** YES — imports `Agent`, `SimulationStatus` types
- **Children:** `TopBar`, `LeftSidebar`, `MainFeed`, `ContextPanel`, `StakeholderView`, `SettingsModal`, `ProjectSetupModal`, `AgentDetailModal`
- **shadcn used:** None directly
- **State managed here:**
  - `simulationStatus: SimulationStatus` — 'RUNNING' | 'PAUSED' | 'STOPPED'
  - `settingsOpen: boolean`
  - `projectSetupOpen: boolean`
  - `selectedAgent: Agent | null`
- **Needs backend:**
  - Simulation state (should be server-driven, not just local React state)
  - Currently all data flows from mock-data.ts — nothing is passed as props to children (children import directly from mock-data)

---

### `components/sap-sim/` — Core UI Components

#### `TopBar`
- **File:** `components/sap-sim/top-bar.tsx`
- **Purpose:** Fixed top navigation bar showing project name, phase, day counter, LiteLLM connection status, notifications, and action buttons
- **Props:**
  - `onNewProject: () => void`
- **Mock data:** YES — directly imports `currentProject` from mock-data
  - Displays: `currentProject.name`, `currentProject.phase`, `currentProject.day`, `currentProject.totalDays`
- **Children:** None (sub-components are inline JSX only)
- **shadcn used:** `Button`
- **Icons:** `Bell`, `Plus`, `Download`, `Wifi` (lucide-react)
- **Hardcoded values:**
  - Notification badge count: `3` (hardcoded red badge)
  - "LiteLLM Connected" status — always shown as connected (green ping dot)
  - Export Report button — no handler
- **Needs backend:**
  - `GET /api/projects/current` → `{ name, phase, day, totalDays, industry }`
  - `GET /api/notifications/count` → unread count for bell badge
  - `GET /api/llm/status` → connection status for the green dot
  - Export Report: `POST /api/reports/export`

---

#### `LeftSidebar`
- **File:** `components/sap-sim/left-sidebar.tsx`
- **Purpose:** Left panel with simulation controls (Run/Pause/Stop), full agent roster (30 agents), and active meetings list
- **Props:**
  - `simulationStatus: SimulationStatus`
  - `onSimulationControl: (action: 'run' | 'pause' | 'stop') => void`
  - `onSettingsClick: () => void`
  - `onAgentClick: (agent: Agent) => void`
- **Mock data:** YES — directly imports `agents`, `currentProject`, `activeMeetings`
- **Children (internal):** `AgentRow` (inline sub-component), uses `TooltipProvider/Tooltip/TooltipTrigger/TooltipContent` for personality popover
- **shadcn used:** `Button`, `Tooltip`, `TooltipContent`, `TooltipProvider`, `TooltipTrigger`
- **Icons:** `Play`, `Pause`, `Square`, `Settings`, `Users`, `Calendar` (lucide-react)
- **Key behaviors:**
  - Agent rows colored by side: consultant=blue, customer=amber, cross-functional=gray
  - Status dot: thinking=amber, speaking=green, idle=gray
  - Customer agents with `personality` field get a hover tooltip showing Engagement/Trust/RiskTolerance mini progress bars
  - Phase color map hardcoded: Discover=gray, Prepare=blue, Explore=amber, Realize=purple, Deploy=green, Run=red
- **Needs backend:**
  - `GET /api/simulation/status` → SimulationStatus
  - `POST /api/simulation/control` body: `{ action: 'run'|'pause'|'stop' }`
  - `GET /api/agents` → `Agent[]` (all 30 agents with live status)
  - `GET /api/meetings/active` → active meetings list (replaces `activeMeetings`)
  - WebSocket or SSE for live agent status updates (thinking/speaking/idle transitions)

---

#### `MainFeed`
- **File:** `components/sap-sim/main-feed.tsx`
- **Purpose:** Center scrollable feed of agent activity cards (like a project timeline/chat), filterable by side and tag type
- **Props:** None (imports everything from mock-data directly)
- **Mock data:** YES — directly imports `feedCards` (12 items)
- **Children (internal):** `AgentAvatar` (inline), `FeedCardItem` (inline)
- **shadcn used:** None (pure custom UI)
- **Icons:** `AlertTriangle`, `Wrench`, `Users`, `MessageSquare` (lucide-react)
- **Filter types:** `'All' | 'Consultant' | 'Customer' | 'Meetings' | 'Decisions' | 'Tools'`
- **Tag system:**
  - `BLOCKER` → red border + red badge
  - `ESCALATION` → red border + red badge
  - `DECISION NEEDED` → amber badge
  - `NEW TOOL` → purple badge
  - `MEETING` → blue border + blue badge + darker card bg
- **Reactions:** Shows stacked mini-avatars of reacting agents (up to 5 shown)
- **Font:** Card content rendered in `font-mono` (JetBrains Mono) — intentional terminal aesthetic
- **Needs backend:**
  - `GET /api/feed?simulationId=X&page=1&limit=20` → `FeedCard[]` (paginated)
  - WebSocket/SSE for real-time new card streaming as simulation runs
  - Filter params: `?side=consultant`, `?tag=BLOCKER`, etc.
  - The "live" pulsing green dot in the header implies real-time updates are expected

---

#### `ContextPanel`
- **File:** `components/sap-sim/context-panel.tsx`
- **Purpose:** Right-center panel with 5 tabs: Meetings, Decisions (kanban), Tools, Test Strategy, Lessons Learned
- **Props:** None (imports everything from mock-data directly)
- **Mock data:** YES — imports `meetings`, `decisions`, `tools`, `lessons`, `testStrategy`
- **Children (internal):**
  - `AgentAvatar` (inline, used in multiple tabs)
  - `MeetingItem` — expandable accordion for meeting details
  - `DecisionsTab` — 4-column kanban (Pending/Approved/Rejected/Deferred)
  - `ToolsTab` — list of AI-invented tools
  - `TestStrategyTab` — test scope, types, progress bars
  - `LessonsTab` — lessons learned cards with validation count
- **shadcn used:** None (custom tabs, custom accordion-like expand)
- **Icons:** `ChevronDown`, `ChevronRight`, `Users`, `CheckCircle2`, `Wrench`, `FileText`, `Lightbulb`, `Clock`, `AlertCircle` (lucide-react)
- **Tab labels (abbreviated on small screens):** Meetings, Decisions, Tools, Test Strategy, Lessons
- **Needs backend:**
  - `GET /api/meetings?simulationId=X` → `Meeting[]`
  - `GET /api/decisions?simulationId=X` → `Decision[]`
  - `POST /api/decisions/:id/status` → update decision status
  - `GET /api/tools?simulationId=X` → `Tool[]`
  - `GET /api/test-strategy?simulationId=X` → `TestStrategy`
  - `GET /api/lessons?simulationId=X` → `Lesson[]`
  - `POST /api/lessons/:id/validate` → increment validatedBy count

---

#### `StakeholderView`
- **File:** `components/sap-sim/stakeholder-view.tsx`
- **Purpose:** Right panel — executive summary with project health gauges, escalations, phase progress, recent decisions, and agent performance leaderboard
- **Props:** None (imports everything from mock-data directly)
- **Mock data:** YES — imports `stakeholderMetrics`, `currentProject`
- **Children (internal):**
  - `GaugeRing` — SVG circular progress ring (used for Schedule/Budget/Risk)
  - `AgentAvatar` (inline)
- **shadcn used:** None (pure custom SVG + CSS)
- **Icons:** `AlertTriangle`, `CheckCircle2`, `TrendingUp` (lucide-react)
- **GaugeRing logic:** SVG `circle` with `strokeDashoffset` calculated from value (0-100). Color auto-switches: ≥80=green, ≥60=amber, <60=red.
- **Sections:**
  1. PROJECT HEALTH — 3 gauge rings (Schedule %, Budget %, Risk %)
  2. REQUIRES ATTENTION — escalation list with severity badges
  3. PHASE PROGRESS — 6-phase bar (Discover→Run) with current phase highlighted
  4. RECENT DECISIONS — short list with green checkmarks
  5. AGENT PERFORMANCE — top 5 agents by activity score
  6. LATEST MILESTONE — green highlight box
- **Needs backend:**
  - `GET /api/dashboard/health?simulationId=X` → `{ schedule, budget, risk }`
  - `GET /api/escalations?simulationId=X&open=true` → escalation list
  - `GET /api/projects/current/phase` → current phase index
  - `GET /api/decisions/recent?limit=3` → recent approved decisions
  - `GET /api/agents/leaderboard?simulationId=X&limit=5` → top agents by activity

---

### `components/sap-sim/modals.tsx` — Three Modals

#### `SettingsModal`
- **File:** `components/sap-sim/modals.tsx`
- **Purpose:** Configuration modal for LiteLLM connection settings (base URL, API key, model, parallel agent count, memory compression interval)
- **Props:**
  - `isOpen: boolean`
  - `onClose: () => void`
- **Mock data:** NO (all local state, no mock-data imports used)
- **Children:** None
- **shadcn used:** `Button`, `Input`, `Slider`
- **Icons:** `X`, `Eye`, `EyeOff` (lucide-react)
- **Local state:**
  - `showApiKey: boolean`
  - `settings: { baseUrl, apiKey, modelName, maxParallelAgents, memoryCompression }`
- **Default values:** `baseUrl='http://localhost:4000'`, `modelName='gpt-4o'`, `maxParallelAgents=10`, `memoryCompression='every-10'`
- **Issues:** Save button has NO `onClick` handler — it does nothing
- **Needs backend:**
  - `GET /api/settings` → load current settings
  - `POST /api/settings` → save settings
  - `POST /api/llm/test-connection` → test connection with entered URL/key

---

#### `ProjectSetupModal`
- **File:** `components/sap-sim/modals.tsx`
- **Purpose:** 4-step wizard for creating a new simulation: (1) project info, (2) scope document upload/paste, (3) methodology doc, (4) customer personality assignment
- **Props:**
  - `isOpen: boolean`
  - `onClose: () => void`
- **Mock data:** YES — imports `agents` to filter customer-side agents for personality step
- **Children:** None (inline)
- **shadcn used:** `Button`, `Input`
- **Icons:** `X`, `Upload`, `RefreshCw` (lucide-react)
- **Local state:**
  - `step: 1 | 2 | 3 | 4`
  - `projectName: string`
  - `industry: string` (dropdown: Manufacturing, Retail, Services, Pharma, Logistics, Energy, Custom)
  - `scopeDoc: string` (textarea)
  - `methodologyDoc: string` (textarea)
  - `personalities: CustomerPersonality[]` (10 customer agents, each with archetype + 3 sliders)
- **Archetype list (10):** The Skeptic, The Absent Sponsor, The Spreadsheet Hoarder, The Reluctant Champion, The Process Purist, The Shadow IT Builder, The Hands-On Expert, The Change Resistor, The Enthusiast, The Overwhelmed
- **"Launch Simulation" button** has NO actual handler — calls `onClose()` only
- **Needs backend:**
  - `POST /api/simulations` → create new simulation with project info
  - `POST /api/simulations/:id/scope` → upload/store scope document
  - `POST /api/simulations/:id/methodology` → upload/store methodology doc
  - `POST /api/simulations/:id/personalities` → save customer personality assignments
  - `POST /api/simulations/:id/start` → trigger actual simulation startup

---

#### `AgentDetailModal`
- **File:** `components/sap-sim/modals.tsx`
- **Purpose:** Modal showing detailed profile of a selected agent — personality, status, activity log, tools used, frequent interactions
- **Props:**
  - `agent: Agent | null`
  - `onClose: () => void`
- **Mock data:** YES — imports `agents` for the "Frequent Interactions" section (shows first 6 agents minus self — **completely hardcoded, not agent-specific**)
- **Children:** None (inline)
- **shadcn used:** None
- **Icons:** `X`, `MessageSquare`, `Wrench` (lucide-react)
- **Hardcoded mock content:**
  - Activity log is HARDCODED (5 static entries, same for every agent)
  - Current task text is HARDCODED: "Reviewing integration documentation for MM module"
  - Tools shown are HARDCODED: "Integration Touchpoint Tracker" + "Config Drift Detector"
  - Frequent interactions = `agents.slice(0, 6)` minus self — NOT agent-specific
- **Needs backend:**
  - `GET /api/agents/:id` → full agent profile
  - `GET /api/agents/:id/activity?limit=10` → actual activity log
  - `GET /api/agents/:id/tools` → tools this specific agent uses/created
  - `GET /api/agents/:id/interactions?limit=6` → most-interacted-with agents
  - `GET /api/agents/:id/current-task` → current task description

---

### `components/theme-provider.tsx`

- **File:** `components/theme-provider.tsx`
- **Purpose:** Thin wrapper around `next-themes` `ThemeProvider`
- **Props:** `ThemeProviderProps` (spread)
- **Mock data:** NO
- **Notes:** **Never used** — not imported anywhere in the app. The app hardcodes dark mode via `<html class="dark">` in layout.tsx. This component is dead code from the V0 scaffold.

---

## Deliverable B: Mock Data Schema

All data lives in `lib/mock-data.ts`. This is the **complete schema** for every structure.

---

### Types / Enums

```typescript
type AgentSide = 'consultant' | 'customer' | 'cross-functional'
type AgentStatus = 'thinking' | 'speaking' | 'idle'
type Phase = 'Discover' | 'Prepare' | 'Explore' | 'Realize' | 'Deploy' | 'Run'
type SimulationStatus = 'RUNNING' | 'PAUSED' | 'STOPPED'
```

---

### `Agent` Interface

```typescript
interface Agent {
  id: string                    // "1" through "30"
  codename: string              // e.g. "PM_ALEX", "IT_MGR_HELEN"
  initials: string              // e.g. "PA", "IH" (2 chars)
  role: string                  // e.g. "Project Manager", "IT Manager"
  side: AgentSide               // 'consultant' | 'customer' | 'cross-functional'
  status: AgentStatus           // 'thinking' | 'speaking' | 'idle'
  personality?: {               // ONLY on customer-side agents (10 of them)
    archetype: string           // e.g. "The Skeptic", "The Absent Sponsor"
    engagement: number          // 0-100
    trust: number               // 0-100
    riskTolerance: number       // 0-100
  }
}
```

**Sample:**
```typescript
{ id: '17', codename: 'EXEC_VICTOR', initials: 'EV', role: 'Executive Sponsor',
  side: 'customer', status: 'idle',
  personality: { archetype: 'The Absent Sponsor', engagement: 25, trust: 60, riskTolerance: 40 } }
```

**Roster breakdown:**
- IDs 1–16: Consultant side (16 agents) — NO personality field
- IDs 17–26: Customer side (10 agents) — ALL have personality
- IDs 27–30: Cross-functional (4 agents) — NO personality

**Consumed by:** Every component. `LeftSidebar`, `MainFeed`, `ContextPanel`, `StakeholderView`, `AgentDetailModal`, `ProjectSetupModal`

**API endpoint:** `GET /api/agents?simulationId=X`  
**Live updates:** `WS /ws/agents/status` → streaming `{ id, status }` updates

---

### `FeedCard` Interface

```typescript
interface FeedCard {
  id: string
  agent: Agent              // full agent object embedded (denormalized)
  timestamp: string         // e.g. "10:23am" — display string, not Date
  day: number               // simulation day number, e.g. 23
  phase: Phase              // which phase this occurred in
  content: string           // the agent's message/update text
  tags: string[]            // zero or more of: 'BLOCKER', 'ESCALATION', 'DECISION NEEDED', 'NEW TOOL', 'MEETING'
  reactions: Agent[]        // array of full Agent objects who reacted
  replyTo?: string          // optional parent card ID (threading — not rendered yet)
}
```

**Sample:**
```typescript
{ id: '1', agent: agents[5], timestamp: '10:23am', day: 23, phase: 'Explore',
  content: 'Completed the first draft of the FI-CO integration scenarios...',
  tags: ['DECISION NEEDED'], reactions: [agents[6], agents[19], agents[20]] }
```

**12 cards total.** Tags distribution: BLOCKER×2, ESCALATION×1, DECISION NEEDED×3, NEW TOOL×2, MEETING×1, none×4

**Consumed by:** `MainFeed`

**API endpoint:** `GET /api/feed?simulationId=X&page=1&limit=20`  
**Real-time:** `WS /ws/feed` → streaming new cards as simulation progresses  
**Note:** `agent` and `reactions` fields are denormalized in mock data. API should normalize and return agent IDs, with client resolving from agent cache.

---

### `Meeting` Interface

```typescript
interface Meeting {
  id: string
  title: string
  phase: Phase
  attendees: Agent[]        // full Agent objects (denormalized)
  duration: string          // e.g. "4 hours"
  date: string              // e.g. "Day 21" (simulation day string, not Date)
  agenda: string[]          // ordered list of agenda items
  discussion: string[]      // discussion summary points
  decisions: string[]       // decisions made (text only)
  actionItems: string[]     // "AGENT_CODE: task description by Day X" format
}
```

**3 meetings in mock data:**
1. "Blueprint Workshop - Finance" — 5 attendees, 4-item agenda, Day 21
2. "Integration Design Session" — 4 attendees, Day 20
3. "Steering Committee" — 4 attendees, Day 18

**Consumed by:** `ContextPanel` (Meetings tab) via `MeetingItem` component

**API endpoint:** `GET /api/meetings?simulationId=X`  
**Note:** `decisions` here are informal text strings inside a meeting — separate from the `Decision` entity in the decisions list.

---

### `Decision` Interface

```typescript
interface Decision {
  id: string
  title: string
  proposedBy: Agent           // full Agent object (denormalized)
  impact: 'Low' | 'Medium' | 'High' | 'Critical'
  description: string
  dateRaised: string          // e.g. "Day 21"
  status: 'Pending' | 'Approved' | 'Rejected' | 'Deferred'
}
```

**8 decisions in mock data:**
- Approved: Chart of Accounts Consolidation, Integration Platform Selection, Document Splitting Activation
- Pending: MRP Run Schedule Change, Material Master Data Cleansing, Train-the-Trainer Approach
- Rejected: Legacy EDI Retirement
- Deferred: Custom Pricing Procedure

**Impact distribution:** Critical×1, High×3, Medium×3, Low×1

**Consumed by:** `ContextPanel` (Decisions tab) — rendered as kanban by status column

**API endpoint:** `GET /api/decisions?simulationId=X`  
**Mutation:** `PATCH /api/decisions/:id` → `{ status: 'Approved'|'Rejected'|... }`

---

### `Tool` Interface

```typescript
interface Tool {
  id: string
  name: string
  createdBy: Agent            // full Agent object
  createdDate: string         // e.g. "Day 23"
  description: string
  usedBy: Agent[]             // array of Agent objects
}
```

**4 tools in mock data:**
1. "Integration Touchpoint Tracker" — by INT_MARCO, Day 23, 4 users
2. "UAT Defect Triage Matrix" — by QA_CLAIRE, Day 23, 3 users
3. "Config Drift Detector" — by BASIS_KURT, Day 15, 3 users
4. "Key User Readiness Scorer" — by CHG_NADIA, Day 18, 4 users

**Consumed by:** `ContextPanel` (Tools tab)

**API endpoint:** `GET /api/tools?simulationId=X`  
**Note:** Tools are "invented" by agents during simulation — they're agent-generated artifacts, not pre-configured.

---

### `Lesson` Interface

```typescript
interface Lesson {
  id: string
  agent: Agent                // full Agent object
  phase: Phase
  category: 'Process' | 'Technical' | 'People' | 'Tools'
  text: string                // the lesson text
  validatedBy: number         // count of agents who validated this lesson
  date: string                // e.g. "Day 21"
}
```

**4 lessons in mock data** (one per category).

**Consumed by:** `ContextPanel` (Lessons tab)

**API endpoint:** `GET /api/lessons?simulationId=X`  
**Mutation:** `POST /api/lessons/:id/validate` → increment validatedBy

---

### `testStrategy` Object

```typescript
const testStrategy = {
  scope: string,              // narrative description
  testTypes: string[],        // 5 test type descriptions
  uatPlan: string,            // narrative
  defectManagement: string,   // narrative
  signOffCriteria: string,    // narrative
  progress: {
    unit: number,             // 0-100, currently 0
    integration: number,      // currently 15
    uat: number,              // currently 0
    regression: number,       // currently 0
  }
}
```

**Consumed by:** `ContextPanel` (Test Strategy tab)

**API endpoint:** `GET /api/test-strategy?simulationId=X`  
**Note:** Progress values will need to update as the simulation runs through Realize phase.

---

### `currentProject` Object

```typescript
const currentProject = {
  name: string,       // "Apex Manufacturing S/4HANA Transformation"
  phase: Phase,       // 'Explore'
  day: number,        // 23
  totalDays: number,  // 180
  industry: string,   // 'Manufacturing'
}
```

**Consumed by:** `TopBar`, `LeftSidebar`, `StakeholderView`

**API endpoint:** `GET /api/projects/current` or `GET /api/simulations/:id`

---

### `stakeholderMetrics` Object

```typescript
const stakeholderMetrics = {
  schedule: number,           // 0-100, currently 78
  budget: number,             // 0-100, currently 95
  risk: number,               // 0-100, currently 62
  escalations: Array<{
    title: string,
    severity: 'High' | 'Medium' | 'Low'
  }>,
  recentDecisions: string[],  // 3 text strings
  topAgents: Array<{
    agent: Agent,             // full Agent object
    activity: number          // numeric activity score
  }>,
  latestMilestone: string,    // "Blueprint Workshop - Finance completed"
}
```

**Consumed by:** `StakeholderView`

**API endpoint:** `GET /api/dashboard/metrics?simulationId=X`

---

### `activeMeetings` Array

```typescript
const activeMeetings = Array<{
  id: string,
  title: string,
  time: string,    // e.g. "11:00am"
  status: string,  // currently always 'upcoming' in mock
}>
```

**3 items in mock data.**

**Consumed by:** `LeftSidebar` (bottom meetings panel)

**API endpoint:** `GET /api/meetings/active?simulationId=X`

---

## Deliverable C: Color & Design Token Map

### CSS Custom Properties (`app/globals.css` — THE ACTIVE FILE)

These are the actual runtime tokens. `styles/globals.css` is a V0 default with oklch colors — it's **overridden** by `app/globals.css`.

| Variable | Hex Value | Usage |
|---|---|---|
| `--background` | `#0e0e10` | Page background, main content area |
| `--foreground` | `#fafafa` | Default text color |
| `--card` | `#18181b` | Card/panel backgrounds |
| `--card-foreground` | `#fafafa` | Text on cards |
| `--popover` | `#18181b` | Tooltip/popover backgrounds |
| `--popover-foreground` | `#fafafa` | Text in popovers |
| `--primary` | `#3b82f6` | Primary buttons, active states |
| `--primary-foreground` | `#fafafa` | Text on primary elements |
| `--secondary` | `#27272a` | Secondary backgrounds, hover states |
| `--secondary-foreground` | `#fafafa` | Text on secondary |
| `--muted` | `#27272a` | Muted/subtle backgrounds |
| `--muted-foreground` | `#71717a` | Muted text, labels, captions |
| `--accent` | `#f59e0b` | Accent/amber highlights |
| `--accent-foreground` | `#0e0e10` | Text on amber accent |
| `--destructive` | `#ef4444` | Error/destructive states |
| `--destructive-foreground` | `#fafafa` | Text on destructive |
| `--border` | `#27272a` | All borders |
| `--input` | `#27272a` | Input field backgrounds |
| `--ring` | `#3b82f6` | Focus ring color |
| `--radius` | `0.5rem` | Base border radius |

### Sidebar Tokens

| Variable | Hex Value |
|---|---|
| `--sidebar` | `#18181b` |
| `--sidebar-foreground` | `#fafafa` |
| `--sidebar-primary` | `#3b82f6` |
| `--sidebar-primary-foreground` | `#fafafa` |
| `--sidebar-accent` | `#27272a` |
| `--sidebar-accent-foreground` | `#fafafa` |
| `--sidebar-border` | `#27272a` |
| `--sidebar-ring` | `#3b82f6` |

### Chart Tokens

| Variable | Hex Value | Semantic |
|---|---|---|
| `--chart-1` | `#3b82f6` | Blue (consultant) |
| `--chart-2` | `#22c55e` | Green (success/running) |
| `--chart-3` | `#f59e0b` | Amber (customer/warning) |
| `--chart-4` | `#a855f7` | Purple (tools/Realize) |
| `--chart-5` | `#ef4444` | Red (destructive/Run) |

### Custom SAP SIM Color Aliases

| Variable | Hex Value | Used For |
|---|---|---|
| `--sap-blue` | `#3b82f6` | Consultant side, primary actions |
| `--sap-amber` | `#f59e0b` | Customer side, warnings |
| `--sap-green` | `#22c55e` | Success, speaking status, Deploy phase |
| `--sap-red` | `#ef4444` | Blockers, escalations, Run phase |
| `--sap-purple` | `#a855f7` | Tools, Realize phase |
| `--sap-muted` | `#71717a` | Labels, secondary text |
| `--sap-card` | `#18181b` | Card backgrounds |
| `--sap-bg` | `#0e0e10` | Page background |

### Semantic Color Usage (by context)

| Context | Color | Hex |
|---|---|---|
| Consultant agents | Blue | `#3b82f6` |
| Customer agents | Amber | `#f59e0b` |
| Cross-functional agents | Gray | `#71717a` |
| Agent status: speaking | Green | `#22c55e` |
| Agent status: thinking | Amber | `#f59e0b` |
| Agent status: idle | Gray | `#71717a` |
| Tag: BLOCKER | Red | `#ef4444` |
| Tag: ESCALATION | Red | `#ef4444` |
| Tag: DECISION NEEDED | Amber | `#f59e0b` |
| Tag: NEW TOOL | Purple | `#a855f7` |
| Tag: MEETING | Blue | `#3b82f6` |
| Phase: Discover | Gray | `#71717a` |
| Phase: Prepare | Blue | `#3b82f6` |
| Phase: Explore | Amber | `#f59e0b` |
| Phase: Realize | Purple | `#a855f7` |
| Phase: Deploy | Green | `#22c55e` |
| Phase: Run | Red | `#ef4444` |
| Impact: Low | Green | `#22c55e` |
| Impact: Medium | Amber | `#f59e0b` |
| Impact: High | Red | `#ef4444` |
| Impact: Critical | Red bg | `#ef4444` (solid) |
| Gauge ≥80% | Green | `#22c55e` |
| Gauge 60-79% | Amber | `#f59e0b` |
| Gauge <60% | Red | `#ef4444` |
| Lesson: Process | Blue | `#3b82f6` |
| Lesson: Technical | Purple | `#a855f7` |
| Lesson: People | Amber | `#f59e0b` |
| Lesson: Tools | Green | `#22c55e` |

### Hardcoded Tailwind Color Values Used (not via CSS variables)

The V0 code uses **hardcoded hex values** instead of CSS variable tokens extensively. This is a significant pattern.

```
bg-[#0e0e10]    bg-[#18181b]    bg-[#27272a]    bg-[#27272a]/50
bg-[#3b82f6]    bg-[#3b82f6]/20  bg-[#f59e0b]   bg-[#f59e0b]/20
bg-[#22c55e]    bg-[#22c55e]/10  bg-[#ef4444]   bg-[#ef4444]/10  bg-[#ef4444]/20
bg-[#a855f7]    bg-[#a855f7]/20  bg-[#71717a]   bg-[#71717a]/20

text-[#fafafa]  text-white       text-[#e4e4e7]  text-[#71717a]
text-[#3b82f6]  text-[#f59e0b]  text-[#22c55e]  text-[#ef4444]  text-[#a855f7]

border-[#27272a]  border-[#3b82f6]  border-[#22c55e]/20  border-[#ef4444]/20
border-l-[#3b82f6]  border-l-[#f59e0b]  border-l-[#ef4444]  border-l-[#a855f7]
border-l-transparent

stroke: '#22c55e' | '#f59e0b' | '#ef4444' | '#27272a'  (inline SVG in GaugeRing)
```

### Typography

| Variable | Value | Usage |
|---|---|---|
| `--font-inter` | Inter (Google Fonts) | Declared in layout.tsx |
| `--font-mono` | JetBrains Mono (Google Fonts) | Declared in layout.tsx |
| `--font-sans` | 'Geist', 'Geist Fallback' | Declared in globals.css @theme (override!) |
| `--font-mono` | 'Geist Mono', 'Geist Mono Fallback' | Declared in globals.css @theme (override!) |

> ⚠️ **Font conflict:** `layout.tsx` loads Inter + JetBrains Mono from Google Fonts and sets CSS variables. But `globals.css` `@theme` block overrides `--font-sans` and `--font-mono` with Geist fonts (Vercel's font stack). The body has `font-sans` class, so it renders **Geist** (if installed) or falls back to system sans. Feed cards use `font-mono` which maps to Geist Mono.

### Layout Dimensions

| Element | Width/Height |
|---|---|
| Top bar | `h-10` (40px) |
| Left sidebar | `w-[220px]` |
| Main feed | `flex-1` (fills remaining space) |
| Context panel | `w-[340px]` |
| Stakeholder view | `w-[220px]` |
| **Total min-width** | ~780px + flex-1 |

---

## Deliverable D: Integration Risk List

### 🔴 HIGH RISK — Complex to wire

#### 1. MainFeed — Real-time Streaming
The `MainFeed` component imports `feedCards` statically. When wired to a live backend, cards need to stream in as the simulation generates them. This requires:
- Replacing static import with a stateful feed (React Query or SWR)
- Adding WebSocket/SSE for real-time appending
- Implementing infinite scroll / pagination
- The pulsing green "LIVE" indicator implies real-time is expected
- **Estimate:** High complexity refactor

#### 2. AgentDetailModal — Fully Hardcoded Content
The activity log, current task description, tools list, and "frequent interactions" are ALL hardcoded regardless of which agent is selected. Every agent shows the same 5 activity items and the same 2 tools. This is completely non-functional for a real app and needs full backend integration.

#### 3. SimulationStatus — Distributed State Problem
`simulationStatus` is managed in `app/page.tsx` with local `useState`. In the real app, simulation state lives on the server (a long-running LLM process). Frontend state must sync with server state. Options: polling, WebSocket, or Server-Sent Events. The current pattern (local state) will cause desyncs.

#### 4. ProjectSetupModal — "Launch Simulation" Does Nothing
The final step's "Launch Simulation" button calls `onClose()` only. The entire 4-step wizard is currently decorative — no API calls, no persistence. Wiring this requires the full backend simulation-creation flow.

#### 5. ContextPanel Decisions — No Mutation
The Decisions kanban shows 4 status columns but you can't drag cards or click to change status. Adding interactivity means adding drag-and-drop (react-beautiful-dnd or dnd-kit) plus PATCH API calls.

---

### 🟡 MEDIUM RISK — Moderate refactoring

#### 6. Direct Mock Data Imports in Components
Every component except `SettingsModal` directly imports from `lib/mock-data.ts`. When switching to live data, ALL of these imports need to be replaced with API calls + state management. The components have no prop interfaces for data — data is hardwired at import level.

Components with direct mock-data imports:
- `TopBar` → `currentProject`
- `LeftSidebar` → `agents`, `currentProject`, `activeMeetings`
- `MainFeed` → `feedCards`
- `ContextPanel` → `meetings`, `decisions`, `tools`, `lessons`, `testStrategy`
- `StakeholderView` → `stakeholderMetrics`, `currentProject`
- `ProjectSetupModal` → `agents`

**Recommended pattern:** Add props or context for all data; keep mock-data as the initial/fallback value during migration.

#### 7. Hardcoded Hex Colors (No Design Token Usage)
The entire UI uses hardcoded hex values (`bg-[#3b82f6]`) instead of CSS variable-backed tokens (`bg-primary`). This makes theme changes or white-labeling impossible and creates 50+ unique color strings scattered across 6 files. **Should be refactored** to use the CSS variables already defined in globals.css.

#### 8. SettingsModal — Save Button Has No Handler
The "Save Settings" button renders but has no `onClick` on the `<Button>` — it'll just submit a form if wrapped in one, but there's no form. Dead UI.

#### 9. TopBar — LiteLLM Status Always Green
Connection status is hardcoded as always-connected. Needs real backend ping: `GET /api/llm/ping` every 30s.

#### 10. `styles/globals.css` vs `app/globals.css` Conflict
There are TWO globals.css files. `app/globals.css` is the active one (imported in layout.tsx). `styles/globals.css` is the V0 default scaffold with oklch colors and appears unused. It could cause confusion. **Should be deleted.**

---

### 🟢 LOW RISK — Minor issues

#### 11. `theme-provider.tsx` — Dead Code
`components/theme-provider.tsx` is never imported anywhere. The app doesn't use `next-themes` dynamically (it hardcodes dark mode). This file should be deleted or wired up if dynamic theming is wanted.

#### 12. `next.config.mjs` — `ignoreBuildErrors: true`
TypeScript errors are silently ignored during build. Fine for prototyping, but must be set to `false` before production deployment. There may be hidden type errors.

#### 13. `useIsMobile` Hook — Unused
`hooks/use-mobile.ts` is never imported by any sap-sim component. The layout is always 4-column with no responsive adaptation. Mobile is completely unsupported (min-width ~780px), which may be intentional for a dashboard app.

#### 14. `useToast` Hook — Unused
`hooks/use-toast.ts` and `components/ui/toast.tsx` exist but are never used in the app. No toast notifications are shown for any action.

#### 15. Agent `replyTo` Field — Not Rendered
`FeedCard` interface has a `replyTo?: string` field for threading, but `MainFeed` never uses it. Threaded conversations are not implemented in the UI.

#### 16. Font Mismatch
`layout.tsx` loads Inter + JetBrains Mono from Google Fonts (network request), but `globals.css` overrides with Geist fonts. The Google Font loads are wasted network requests. Should unify on one font stack.

#### 17. AgentAvatar Duplicated Across Files
`AgentAvatar` is re-implemented inline in `main-feed.tsx`, `context-panel.tsx`, `left-sidebar.tsx`, and `stakeholder-view.tsx` — 4 nearly-identical copies with slightly different size parameters. Should be extracted to a shared `components/sap-sim/agent-avatar.tsx`.

#### 18. shadcn Version: New York Style + Tailwind v4
The `components.json` specifies `"style": "new-york"` and Tailwind v4 is used (`@tailwindcss/postcss`). Tailwind v4 uses `@import 'tailwindcss'` instead of directives. This is bleeding-edge (v4 released early 2025). Some shadcn components may not be fully compatible — test carefully.

#### 19. `@vercel/analytics` — Vercel Deployment Assumption
Analytics package is included and conditionally rendered in production. If the app is deployed on carlab (not Vercel), this is dead weight. Remove or replace with self-hosted analytics.

---

## Deliverable E: Dependencies Summary

### Core Framework

| Package | Version | Purpose |
|---|---|---|
| `next` | 16.2.0 | React framework (App Router) |
| `react` | ^19 | UI library |
| `react-dom` | ^19 | React DOM renderer |
| `typescript` | 5.7.3 | Type safety |

### Styling

| Package | Version | Purpose |
|---|---|---|
| `tailwindcss` | ^4.2.0 | Utility CSS framework (v4 — major version!) |
| `@tailwindcss/postcss` | ^4.2.0 | Tailwind PostCSS plugin for v4 |
| `autoprefixer` | ^10.4.20 | CSS vendor prefixes |
| `postcss` | ^8.5 | CSS transformation pipeline |
| `tw-animate-css` | 1.3.3 | Pre-built Tailwind animations |
| `class-variance-authority` | ^0.7.1 | Type-safe variant props for shadcn |
| `clsx` | ^2.1.1 | Conditional class names |
| `tailwind-merge` | ^3.3.1 | Merge Tailwind classes without conflicts |

### UI Components (shadcn/Radix)

| Package | Version | Purpose |
|---|---|---|
| `@radix-ui/react-accordion` | 1.2.12 | Accordion (shadcn accordion) |
| `@radix-ui/react-alert-dialog` | 1.1.15 | Alert dialogs |
| `@radix-ui/react-aspect-ratio` | 1.1.8 | Aspect ratio container |
| `@radix-ui/react-avatar` | 1.1.11 | Avatar with fallback |
| `@radix-ui/react-checkbox` | 1.3.3 | Checkbox input |
| `@radix-ui/react-collapsible` | 1.1.12 | Collapsible sections |
| `@radix-ui/react-context-menu` | 2.2.16 | Right-click context menus |
| `@radix-ui/react-dialog` | 1.1.15 | Modal dialogs |
| `@radix-ui/react-dropdown-menu` | 2.1.16 | Dropdown menus |
| `@radix-ui/react-hover-card` | 1.1.15 | Hover card popups |
| `@radix-ui/react-label` | 2.1.8 | Form labels |
| `@radix-ui/react-menubar` | 1.1.16 | Menu bars |
| `@radix-ui/react-navigation-menu` | 1.2.14 | Navigation menus |
| `@radix-ui/react-popover` | 1.1.15 | Popover overlays |
| `@radix-ui/react-progress` | 1.1.8 | Progress bars |
| `@radix-ui/react-radio-group` | 1.3.8 | Radio button groups |
| `@radix-ui/react-scroll-area` | 1.2.10 | Custom scrollbars |
| `@radix-ui/react-select` | 2.2.6 | Select/dropdown |
| `@radix-ui/react-separator` | 1.1.8 | Horizontal/vertical dividers |
| `@radix-ui/react-slider` | 1.3.6 | **USED** — Settings modal parallel agents slider |
| `@radix-ui/react-slot` | 1.2.4 | Composition primitive (used by Button) |
| `@radix-ui/react-switch` | 1.2.6 | Toggle switches |
| `@radix-ui/react-tabs` | 1.1.13 | Tab panels |
| `@radix-ui/react-toast` | 1.2.15 | Toast notifications (unused in app) |
| `@radix-ui/react-toggle` | 1.1.10 | Toggle buttons |
| `@radix-ui/react-toggle-group` | 1.1.11 | Toggle button groups |
| `@radix-ui/react-tooltip` | 1.2.8 | **USED** — Agent personality tooltip in LeftSidebar |

**Note:** Most Radix packages are installed but unused. V0 scaffolds the full shadcn suite by default. Active usage: `Tooltip` (LeftSidebar), `Slider` (SettingsModal), `Button` (multiple), `Input` (modals).

### Form Handling

| Package | Version | Purpose |
|---|---|---|
| `react-hook-form` | ^7.54.1 | Form state management (unused in current UI) |
| `@hookform/resolvers` | ^3.9.1 | Zod integration for react-hook-form |
| `zod` | ^3.24.1 | Schema validation (unused in current UI) |

### Data Visualization

| Package | Version | Purpose |
|---|---|---|
| `recharts` | 2.15.0 | Charts library (installed, NOT YET USED in UI) |

### UI Utilities

| Package | Version | Purpose |
|---|---|---|
| `lucide-react` | ^0.564.0 | Icon library — **heavily used** throughout |
| `next-themes` | ^0.4.6 | Dark/light theme switching (installed, not used — app hardcodes dark) |
| `cmdk` | 1.1.1 | Command palette (unused) |
| `date-fns` | 4.1.0 | Date formatting (unused) |
| `embla-carousel-react` | 8.6.0 | Carousel (unused) |
| `input-otp` | 1.4.2 | OTP input (unused) |
| `react-day-picker` | 9.13.2 | Date picker (unused) |
| `react-resizable-panels` | ^2.1.7 | Resizable panel layouts (unused — but could be useful for this 4-column layout!) |
| `sonner` | ^1.7.1 | Toast notifications (alternative to Radix toast, unused) |
| `vaul` | ^1.1.2 | Drawer/sheet component (unused) |

### Deployment/Analytics

| Package | Version | Purpose |
|---|---|---|
| `@vercel/analytics` | 1.6.1 | Vercel Analytics (only in production builds) |

### Dev Dependencies

| Package | Version | Purpose |
|---|---|---|
| `@types/node` | ^22 | Node.js type definitions |
| `@types/react` | ^19 | React type definitions |
| `@types/react-dom` | ^19 | ReactDOM type definitions |

---

### Dependency Bloat Assessment

**Actively used:** `next`, `react`, `react-dom`, `tailwindcss` stack, `lucide-react`, `@radix-ui/react-tooltip`, `@radix-ui/react-slider`, shadcn UI primitives (Button, Input), `clsx`, `tailwind-merge`, `class-variance-authority`

**Installed, not yet used but likely needed soon:** `recharts` (dashboards/charts), `react-resizable-panels` (panel resizing), `react-hook-form` + `zod` (ProjectSetupModal form validation), `date-fns` (timestamps), `sonner` (notifications)

**Probably unused forever:** `cmdk`, `embla-carousel-react`, `input-otp`, `react-day-picker`, `vaul`, `next-themes`, `@vercel/analytics` (if not deploying to Vercel)

**Safe to uninstall now:** ~8-10 Radix packages that have no corresponding shadcn usage in the app

---

## Appendix: File Tree & Architecture Overview

```
sapsim/
├── app/
│   ├── globals.css          ← ACTIVE CSS (dark theme, SAP SIM colors)
│   ├── layout.tsx           ← Root layout (always dark, Inter + JetBrains Mono)
│   └── page.tsx             ← Main dashboard page (4-column layout orchestrator)
├── components/
│   ├── sap-sim/
│   │   ├── top-bar.tsx       ← Top navigation bar
│   │   ├── left-sidebar.tsx  ← Agent roster + simulation controls
│   │   ├── main-feed.tsx     ← Scrollable activity feed
│   │   ├── context-panel.tsx ← 5-tab detail panel (meetings/decisions/tools/test/lessons)
│   │   ├── stakeholder-view.tsx ← Executive summary panel
│   │   └── modals.tsx        ← Settings + ProjectSetup + AgentDetail modals
│   ├── theme-provider.tsx    ← Dead code (never imported)
│   └── ui/                   ← Full shadcn/ui component library (~50 files)
├── hooks/
│   ├── use-mobile.ts         ← Mobile breakpoint detection (unused)
│   └── use-toast.ts          ← Toast state management (unused)
├── lib/
│   ├── mock-data.ts          ← ALL DATA (30 agents, 12 feed cards, 3 meetings, 8 decisions, 4 tools, 4 lessons, test strategy, metrics)
│   └── utils.ts              ← cn() utility only
├── styles/
│   └── globals.css           ← V0 default CSS (oklch, UNUSED — shadowed by app/globals.css)
├── components.json           ← shadcn config (New York style, Tailwind v4, neutral base)
├── next.config.mjs           ← Next.js config (ignoreBuildErrors: true, images unoptimized)
├── package.json              ← Dependencies (Next 16, React 19, Tailwind v4)
├── postcss.config.mjs        ← PostCSS (@tailwindcss/postcss only)
└── tsconfig.json             ← TypeScript config
```

### Architecture Pattern

```
app/page.tsx (SAPSimDashboard)
├── State: simulationStatus, settingsOpen, projectSetupOpen, selectedAgent
├── TopBar ────────────────────── reads: currentProject (direct import)
├── LeftSidebar ───────────────── reads: agents, currentProject, activeMeetings (direct import)
│                                 writes: simulationStatus (via onSimulationControl callback)
├── MainFeed ──────────────────── reads: feedCards (direct import)
├── ContextPanel ──────────────── reads: meetings, decisions, tools, lessons, testStrategy (direct import)
├── StakeholderView ───────────── reads: stakeholderMetrics, currentProject (direct import)
├── SettingsModal ─────────────── no data (local state only)
├── ProjectSetupModal ─────────── reads: agents (direct import, for personality step)
└── AgentDetailModal ──────────── reads: agent (prop), agents (direct import for relationships)
```

### Key Architectural Observations

1. **No global state management** — no Context, no Zustand, no Redux. Data flows from mock-data.ts directly into each component as module-level constants. This is fine for a prototype but needs to change for real data.

2. **No data fetching layer** — no React Query, no SWR, no fetch calls. All data is static imports. Migration to live data requires adding a data fetching layer.

3. **Props are thin** — most components take no data props. Data coupling is at module level. To inject live data, either: (a) wrap each component to accept data as props, or (b) introduce a context/store.

4. **No routing** — single page app. All views are shown simultaneously in the 4-column layout. No navigation between views.

5. **No authentication** — no user session, no auth checks. The dashboard is open.

6. **Simulation state is local** — `simulationStatus` lives in `page.tsx`. In reality, this needs to come from the backend AI orchestration layer.

7. **Ready for WebSockets** — the "LIVE" indicator on MainFeed and the pulsing status dots clearly expect real-time data. The architecture should add a WebSocket context that pushes updates to the feed and agent statuses.

---

*Phase 0 complete. This document covers 100% of the frontend source files (excluding node_modules and lock files).*
