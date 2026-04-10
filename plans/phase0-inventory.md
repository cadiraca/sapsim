# Phase 0 — V0 Code Archaeology
## SAP SIM Frontend Inventory

*Generated April 10, 2026 by King Charly*

---

## A. Dependencies Summary

| Package | Version | Purpose |
|---------|---------|---------|
| next | 16.2.0 | App framework (App Router) |
| react / react-dom | ^19 | UI library |
| tailwindcss | ^4.2.0 | CSS utility framework |
| @radix-ui/* | various | Headless UI primitives (20+ packages) |
| lucide-react | ^0.564.0 | Icon library |
| recharts | 2.15.0 | Charts/graphs (used for stakeholder gauges) |
| react-resizable-panels | ^2.1.7 | Resizable panel layout |
| sonner | ^1.7.1 | Toast notifications |
| vaul | ^1.1.2 | Drawer component |
| cmdk | 1.1.1 | Command palette |
| date-fns | 4.1.0 | Date formatting |
| zod | ^3.24.1 | Schema validation |
| react-hook-form | ^7.54.1 | Form handling |
| embla-carousel-react | 8.6.0 | Carousel component |
| next-themes | ^0.4.6 | Theme management (dark only) |
| class-variance-authority | ^0.7.1 | Variant styling |
| clsx + tailwind-merge | latest | Class merging utilities |
| @vercel/analytics | 1.6.1 | Analytics (production only) |

**Fonts:** Inter (sans) + JetBrains Mono (mono) via next/font/google

---

## B. Component Inventory

### 1. TopBar
- **File:** `components/sap-sim/top-bar.tsx`
- **Purpose:** Top header bar — project name, phase, day counter, LiteLLM status, notifications, New Project + Export buttons
- **Props:** `onNewProject: () => void`
- **Mock data:** YES — imports `currentProject` (name, phase, day, totalDays)
- **Children:** None (self-contained)
- **shadcn used:** `Button`
- **Icons:** `Bell, Plus, Download, Wifi` (lucide)
- **Needs backend:**
  - `GET /api/projects/{name}` → project name, phase, day, totalDays
  - LiteLLM connection status (green dot + text)
  - Notification count badge (hardcoded "3")
  - Export report trigger → `GET /api/projects/{name}/report`

### 2. LeftSidebar
- **File:** `components/sap-sim/left-sidebar.tsx`
- **Purpose:** Left panel — project header, simulation controls (Run/Pause/Stop), all 30 agents list with status dots, active meetings list, settings button
- **Props:** `simulationStatus: SimulationStatus`, `onSimulationControl`, `onSettingsClick`, `onAgentClick`
- **Mock data:** YES — imports `agents` (all 30), `currentProject`, `activeMeetings`
- **Children:** `AgentRow` (internal component)
- **shadcn used:** `Button`, `Tooltip`, `TooltipContent`, `TooltipProvider`, `TooltipTrigger`
- **Icons:** `Play, Pause, Square, Settings, Users, Calendar` (lucide)
- **Key features:**
  - Agent avatars color-coded by side (blue=consultant, amber=customer, gray=cross-functional)
  - Status dots: green=speaking, amber=thinking, gray=idle
  - Personality tooltip on hover for customer agents (3 stat bars)
  - Phase badge with color per phase
- **Needs backend:**
  - `GET /api/projects/{name}/agents` → agent list with live status
  - `POST /api/projects/{name}/start|pause|stop` → simulation control
  - `GET /api/projects/{name}/meetings` → active meetings
  - SSE events for real-time status dot updates

### 3. MainFeed
- **File:** `components/sap-sim/main-feed.tsx`
- **Purpose:** Central live feed — scrollable list of agent messages with filter pills
- **Props:** None (standalone)
- **Mock data:** YES — imports `feedCards` (12 items)
- **Children:** `AgentAvatar` (internal), `FeedCardItem` (internal)
- **shadcn used:** None (custom styling)
- **Icons:** `AlertTriangle, Wrench, Users, MessageSquare` (lucide)
- **Key features:**
  - Filter pills: All, Consultant, Customer, Meetings, Decisions, Tools
  - Color-coded left border per tag type (red=blocker/escalation, purple=tool, blue=meeting)
  - Tag badges with icons
  - Reaction avatars at bottom of each card
  - Monospace font for content text
- **Needs backend:**
  - `GET /api/stream/{name}` → SSE for live feed events
  - `GET /api/projects/{name}/feed` → paginated historical feed
  - Filter by agent side, event type

### 4. ContextPanel
- **File:** `components/sap-sim/context-panel.tsx`
- **Purpose:** Right panel with 5 tabs: Meetings, Decisions, Tools, Test Strategy, Lessons
- **Props:** None (standalone)
- **Mock data:** YES — imports `meetings`, `decisions`, `tools`, `lessons`, `testStrategy`
- **Children:** `AgentAvatar`, `MeetingItem`, `DecisionsTab`, `ToolsTab`, `TestStrategyTab`, `LessonsTab` (all internal)
- **shadcn used:** None (custom tabs)
- **Icons:** `ChevronDown, ChevronRight, Users, CheckCircle2, Wrench, FileText, Lightbulb, Clock, AlertCircle` (lucide)
- **Key features:**
  - **Meetings tab:** Expandable meeting cards with agenda, discussion, decisions, action items
  - **Decisions tab:** Kanban board (4 columns: Pending, Approved, Rejected, Deferred), impact badges
  - **Tools tab:** Purple-bordered cards with INVENTED badge, created-by + used-by avatars
  - **Test Strategy tab:** Scope, test types, UAT plan, defect mgmt, progress bars per test type
  - **Lessons tab:** Cards with category badges, validation counts
- **Needs backend:**
  - `GET /api/projects/{name}/meetings` + `/{id}`
  - `GET /api/projects/{name}/decisions`
  - `GET /api/projects/{name}/tools`
  - `GET /api/projects/{name}/test-strategy`
  - `GET /api/projects/{name}/lessons`

### 5. StakeholderView
- **File:** `components/sap-sim/stakeholder-view.tsx`
- **Purpose:** Far-right panel — executive summary with health gauges, escalations, phase progress, decisions, agent leaderboard, milestone
- **Props:** None (standalone)
- **Mock data:** YES — imports `stakeholderMetrics`, `currentProject`
- **Children:** `GaugeRing` (internal SVG ring), `AgentAvatar` (internal)
- **shadcn used:** None
- **Icons:** `AlertTriangle, CheckCircle2, TrendingUp` (lucide)
- **Key features:**
  - 3 SVG ring gauges (Schedule, Budget, Risk) with auto-color (green≥80, amber≥60, red<60)
  - Escalation cards (red-tinted)
  - Phase progress bar (6 segments, color-coded)
  - Recent decisions list with checkmarks
  - Agent leaderboard (top 5 by activity score)
  - Latest milestone card (green-tinted)
- **Needs backend:**
  - `GET /api/projects/{name}/stakeholder` → all metrics in one call

### 6. Modals (3 in one file)
- **File:** `components/sap-sim/modals.tsx`
- **Purpose:** Three modal dialogs — Settings, Project Setup, Agent Detail

#### 6a. SettingsModal
- **Props:** `isOpen: boolean`, `onClose: () => void`
- **Fields:** LiteLLM Base URL, API Key (with show/hide toggle), Model Name, Max Parallel Agents (slider 1-30), Memory Compression Interval (dropdown)
- **shadcn used:** `Button`, `Input`, `Slider`
- **Needs backend:**
  - `GET /api/projects/{name}/settings`
  - `PUT /api/projects/{name}/settings`
  - `POST /api/settings/test`

#### 6b. ProjectSetupModal
- **Props:** `isOpen: boolean`, `onClose: () => void`
- **4-step wizard:**
  1. Project Name + Industry dropdown (7 options)
  2. Scope Document (text upload/paste)
  3. Methodology (optional, text upload/paste)
  4. Customer Personalities — grid of 10 customer agents with personality cards, re-roll per agent or all
- **Key features:** Step indicator (1-4 dots), Back/Next/Launch buttons
- **Archetypes in code:** The Skeptic, Absent Sponsor, Spreadsheet Hoarder, Reluctant Champion, Process Purist, Shadow IT Builder, Hands-On Expert, Change Resistor, Enthusiast, The Overwhelmed
- **Needs backend:**
  - `POST /api/projects` → create project
  - `POST /api/projects/{name}/agents/reroll`

#### 6c. AgentDetailModal
- **Props:** `agent: Agent | null`, `onClose: () => void`
- **Sections:** Header (avatar, name, role, side), Personality bars (customer only), Current Status, Activity Log (mock), Tools used, Frequent Interactions
- **Mock data:** YES — activity log and relationships are hardcoded in component
- **Needs backend:**
  - `GET /api/projects/{name}/agents/{codename}` → full agent detail

### 7. Supporting Files
- **`components/theme-provider.tsx`** — next-themes provider (dark mode only)
- **`hooks/use-mobile.ts`** — responsive breakpoint hook
- **`hooks/use-toast.ts`** — toast state management
- **`lib/utils.ts`** — `cn()` helper (clsx + tailwind-merge)


---

## C. Mock Data Schema

All mock data lives in `lib/mock-data.ts`. These shapes become our API response types.

### Types (direct from source)

```typescript
type AgentSide = 'consultant' | 'customer' | 'cross-functional'
type AgentStatus = 'thinking' | 'speaking' | 'idle'
type Phase = 'Discover' | 'Prepare' | 'Explore' | 'Realize' | 'Deploy' | 'Run'
type SimulationStatus = 'RUNNING' | 'PAUSED' | 'STOPPED'
```

### Interface: Agent
```typescript
interface Agent {
  id: string
  codename: string       // e.g. "PM_ALEX"
  initials: string       // e.g. "PA"
  role: string           // e.g. "Project Manager"
  side: AgentSide
  status: AgentStatus
  personality?: {        // customer agents only
    archetype: string    // e.g. "The Skeptic"
    engagement: number   // 0-100 (displayed as percentage bar)
    trust: number        // 0-100
    riskTolerance: number // 0-100
  }
}
```
**Note:** Mock uses 0-100 scale for personality (percentage). Plan doc uses 1-5 scale. **Backend should use 1-5 internally, API returns 0-100 for frontend.**
**Consumed by:** LeftSidebar, MainFeed, ContextPanel, StakeholderView, Modals

### Interface: FeedCard
```typescript
interface FeedCard {
  id: string
  agent: Agent           // full agent object (nested)
  timestamp: string      // e.g. "10:23am"
  day: number
  phase: Phase
  content: string        // the agent's message text
  tags: string[]         // e.g. ["BLOCKER", "ESCALATION"]
  reactions: Agent[]     // agents who reacted
  replyTo?: string       // thread/reply support (unused in mock)
}
```
**Tag values:** "BLOCKER", "ESCALATION", "DECISION NEEDED", "NEW TOOL", "MEETING"
**Consumed by:** MainFeed

### Interface: Meeting
```typescript
interface Meeting {
  id: string
  title: string
  phase: Phase
  attendees: Agent[]
  duration: string       // e.g. "4 hours"
  date: string           // e.g. "Day 21"
  agenda: string[]
  discussion: string[]
  decisions: string[]
  actionItems: string[]  // e.g. "FI_CHEN: Document new chart of accounts mapping by Day 25"
}
```
**Consumed by:** ContextPanel (Meetings tab)

### Interface: Decision
```typescript
interface Decision {
  id: string
  title: string
  proposedBy: Agent
  impact: 'Low' | 'Medium' | 'High' | 'Critical'
  description: string
  dateRaised: string     // e.g. "Day 21"
  status: 'Pending' | 'Approved' | 'Rejected' | 'Deferred'
}
```
**Consumed by:** ContextPanel (Decisions tab — Kanban layout)

### Interface: Tool
```typescript
interface Tool {
  id: string
  name: string
  createdBy: Agent
  createdDate: string
  description: string
  usedBy: Agent[]
}
```
**Consumed by:** ContextPanel (Tools tab)

### Interface: Lesson
```typescript
interface Lesson {
  id: string
  agent: Agent
  phase: Phase
  category: 'Process' | 'Technical' | 'People' | 'Tools'
  text: string
  validatedBy: number    // count of validating agents
  date: string
}
```
**Consumed by:** ContextPanel (Lessons tab)

### Object: testStrategy
```typescript
{
  scope: string
  testTypes: string[]
  uatPlan: string
  defectManagement: string
  signOffCriteria: string
  progress: { unit: number, integration: number, uat: number, regression: number }
}
```
**Consumed by:** ContextPanel (Test Strategy tab)

### Object: stakeholderMetrics
```typescript
{
  schedule: number       // 0-100 gauge
  budget: number         // 0-100 gauge
  risk: number           // 0-100 gauge
  escalations: Array<{ title: string, severity: 'High' | 'Medium' }>
  recentDecisions: string[]
  topAgents: Array<{ agent: Agent, activity: number }>
  latestMilestone: string
}
```
**Consumed by:** StakeholderView

### Object: currentProject
```typescript
{ name: string, phase: Phase, day: number, totalDays: number, industry: string }
```
**Consumed by:** TopBar, LeftSidebar, StakeholderView

### Object: activeMeetings
```typescript
Array<{ id: string, title: string, time: string, status: 'upcoming' | 'in-progress' | 'completed' }>
```
**Consumed by:** LeftSidebar (bottom section)


---

## D. Color & Design Token Map

### CSS Custom Properties (globals.css)
| Variable | Value | Usage |
|----------|-------|-------|
| `--background` / `--sap-bg` | `#0e0e10` | Page background |
| `--card` / `--sap-card` | `#18181b` | Card/panel backgrounds |
| `--secondary` / `--border` / `--input` | `#27272a` | Borders, input backgrounds, secondary surfaces |
| `--foreground` | `#fafafa` | Primary text |
| `--muted-foreground` / `--sap-muted` | `#71717a` | Secondary/muted text |
| `--primary` / `--sap-blue` | `#3b82f6` | Primary accent, consultant side, active states |
| `--accent` / `--sap-amber` | `#f59e0b` | Customer side, warnings, thinking status |
| `--sap-green` | `#22c55e` | Success, speaking status, running, approved |
| `--destructive` / `--sap-red` | `#ef4444` | Errors, blockers, escalations, stopped |
| `--sap-purple` | `#a855f7` | Tools, invented items, Realize phase |

### Agent Side Colors (used everywhere)
| Side | Background | Text |
|------|-----------|------|
| Consultant | `bg-[#3b82f6]/20` | `text-[#3b82f6]` |
| Customer | `bg-[#f59e0b]/20` | `text-[#f59e0b]` |
| Cross-functional | `bg-[#71717a]/20` | `text-[#71717a]` |

### Status Colors
| Status | Color |
|--------|-------|
| Speaking | `bg-[#22c55e]` (green) |
| Thinking | `bg-[#f59e0b]` (amber) |
| Idle | `bg-[#71717a]` (gray) |
| Running | `bg-[#22c55e]` + ping animation |
| Paused | `bg-[#f59e0b]` |
| Stopped | `bg-[#ef4444]` |

### Phase Colors
| Phase | Color |
|-------|-------|
| Discover | `bg-[#71717a]` |
| Prepare | `bg-[#3b82f6]` |
| Explore | `bg-[#f59e0b]` |
| Realize | `bg-[#a855f7]` |
| Deploy | `bg-[#22c55e]` |
| Run | `bg-[#ef4444]` |

### Tag Colors
| Tag | Style |
|-----|-------|
| BLOCKER | `bg-[#ef4444]/20 text-[#ef4444]` |
| ESCALATION | `bg-[#ef4444]/20 text-[#ef4444]` |
| DECISION NEEDED | `bg-[#f59e0b]/20 text-[#f59e0b]` |
| NEW TOOL | `bg-[#a855f7]/20 text-[#a855f7]` |
| MEETING | `bg-[#3b82f6]/20 text-[#3b82f6]` |

### Impact Colors
| Impact | Style |
|--------|-------|
| Low | `bg-[#22c55e]/20 text-[#22c55e]` |
| Medium | `bg-[#f59e0b]/20 text-[#f59e0b]` |
| High | `bg-[#ef4444]/20 text-[#ef4444]` |
| Critical | `bg-[#ef4444] text-white` (solid!) |

### Gauge Ring Auto-Color
- ≥80: `#22c55e` (green)
- ≥60: `#f59e0b` (amber)
- <60: `#ef4444` (red)

### Fonts
- Sans: Inter (`--font-inter`)
- Mono: JetBrains Mono (`--font-mono`) — used for feed content text
- Theme always dark (`<html lang="en" className="dark">`)

---

## E. Integration Risk List

### High Risk
1. **Personality scale mismatch** — Mock uses 0-100 (percentage), plan doc uses 1-5. Backend must normalize. Decision: store 1-5 internally, API returns 0-100 for frontend.
2. **Nested Agent objects everywhere** — FeedCard, Meeting, Decision, Tool, Lesson all embed full Agent objects. API should return agent codenames + a separate agents map to avoid data duplication. Frontend adapter layer needed.
3. **No loading/error states** — V0 has zero loading skeletons or error boundaries. Must add during Phase 6 wiring.
4. **Agent personality archetypes differ** — Mock has 10 archetypes (includes "The Overwhelmed", "The Process Purist", "The Shadow IT Builder", "The Hands-On Expert", "The Enthusiast"). Plan doc has 8 (different set). **Must reconcile — use the union of both.**

### Medium Risk
5. **SSE feed vs REST feed** — MainFeed needs both: SSE for live events, REST for scroll-back history. Two data sources merging into one list.
6. **Activity log in AgentDetailModal is fully hardcoded** — Not from mock-data.ts, embedded in the component JSX. Will need its own API endpoint.
7. **Relationships in AgentDetailModal** — Uses `agents.slice(0,6)` as mock. Real data needs agent interaction tracking.
8. **shadcn/ui v4 + Tailwind v4** — Using latest versions. No known issues but newer than most tutorials.
9. **Test strategy progress** — Currently just 4 numbers. Backend needs real progress tracking.

### Low Risk
10. **@vercel/analytics** — Only loads in production. Can remove or keep; won't affect development.
11. **No responsive design** — Fixed widths (220px sidebars, 340px context panel). Desktop-only is fine for this app.
12. **date-fns imported but not used in components** — May be needed later for timestamp formatting.

---

## F. API Endpoint Mapping (Mock → Backend)

| Mock Data | Component | API Endpoint |
|-----------|-----------|-------------|
| `agents` | LeftSidebar, all | `GET /api/projects/{name}/agents` |
| `currentProject` | TopBar, LeftSidebar, StakeholderView | `GET /api/projects/{name}` |
| `feedCards` | MainFeed | `GET /api/stream/{name}` (SSE) + `GET /api/projects/{name}/feed` (REST) |
| `meetings` | ContextPanel | `GET /api/projects/{name}/meetings` |
| `decisions` | ContextPanel | `GET /api/projects/{name}/decisions` |
| `tools` | ContextPanel | `GET /api/projects/{name}/tools` |
| `lessons` | ContextPanel | `GET /api/projects/{name}/lessons` |
| `testStrategy` | ContextPanel | `GET /api/projects/{name}/test-strategy` |
| `stakeholderMetrics` | StakeholderView | `GET /api/projects/{name}/stakeholder` |
| `activeMeetings` | LeftSidebar | `GET /api/projects/{name}/meetings?status=active` |
| Settings (modal) | SettingsModal | `GET/PUT /api/projects/{name}/settings` |
| Agent detail | AgentDetailModal | `GET /api/projects/{name}/agents/{codename}` |

---

*Phase 0 complete. Ready for Phase 1: Monorepo Scaffold.*

