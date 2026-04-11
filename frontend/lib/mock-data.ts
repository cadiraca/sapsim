// Agent types and mock data for SAP SIM

export type AgentSide = 'consultant' | 'customer' | 'cross-functional'
export type AgentStatus = 'thinking' | 'speaking' | 'idle'
export type Phase = 'Discover' | 'Prepare' | 'Explore' | 'Realize' | 'Deploy' | 'Run'
export type SimulationStatus = 'RUNNING' | 'PAUSED' | 'STOPPED'

export interface Agent {
  id: string
  codename: string
  initials: string
  role: string
  side: AgentSide
  status: AgentStatus
  personality?: {
    archetype: string
    engagement: number
    trust: number
    riskTolerance: number
  }
}

export interface FeedCard {
  id: string
  agent: Agent
  timestamp: string
  day: number
  phase: Phase
  content: string
  tags: string[]
  reactions: Agent[]
  replyTo?: string
}

export interface Meeting {
  id: string
  title: string
  phase: Phase
  attendees: Agent[]
  duration: string
  date: string
  agenda: string[]
  discussion: string[]
  decisions: string[]
  actionItems: string[]
}

export interface Decision {
  id: string
  title: string
  proposedBy: Agent
  impact: 'Low' | 'Medium' | 'High' | 'Critical'
  description: string
  dateRaised: string
  status: 'Pending' | 'Approved' | 'Rejected' | 'Deferred'
}

export interface Tool {
  id: string
  name: string
  createdBy: Agent
  createdDate: string
  description: string
  usedBy: Agent[]
}

export interface Lesson {
  id: string
  agent: Agent
  phase: Phase
  category: 'Process' | 'Technical' | 'People' | 'Tools'
  text: string
  validatedBy: number
  date: string
}

// All 30 agents
export const agents: Agent[] = [
  // Consultant side (blue)
  { id: '1', codename: 'PM_ALEX', initials: 'PA', role: 'Project Manager', side: 'consultant', status: 'speaking' },
  { id: '2', codename: 'ARCH_SARA', initials: 'AS', role: 'Solution Architect', side: 'consultant', status: 'thinking' },
  { id: '3', codename: 'BASIS_KURT', initials: 'BK', role: 'BASIS Consultant', side: 'consultant', status: 'idle' },
  { id: '4', codename: 'DEV_PRIYA', initials: 'DP', role: 'ABAP Developer', side: 'consultant', status: 'thinking' },
  { id: '5', codename: 'DEV_LEON', initials: 'DL', role: 'Fiori Developer', side: 'consultant', status: 'idle' },
  { id: '6', codename: 'FI_CHEN', initials: 'FC', role: 'FI Consultant', side: 'consultant', status: 'speaking' },
  { id: '7', codename: 'CO_MARTA', initials: 'CM', role: 'CO Consultant', side: 'consultant', status: 'idle' },
  { id: '8', codename: 'MM_RAVI', initials: 'MR', role: 'MM Consultant', side: 'consultant', status: 'idle' },
  { id: '9', codename: 'SD_ISLA', initials: 'SI', role: 'SD Consultant', side: 'consultant', status: 'thinking' },
  { id: '10', codename: 'PP_JONAS', initials: 'PJ', role: 'PP Consultant', side: 'consultant', status: 'idle' },
  { id: '11', codename: 'WM_FATIMA', initials: 'WF', role: 'WM Consultant', side: 'consultant', status: 'idle' },
  { id: '12', codename: 'INT_MARCO', initials: 'IM', role: 'Integration Lead', side: 'consultant', status: 'speaking' },
  { id: '13', codename: 'SEC_DIANA', initials: 'SD', role: 'Security Consultant', side: 'consultant', status: 'idle' },
  { id: '14', codename: 'BI_SAM', initials: 'BS', role: 'BI Consultant', side: 'consultant', status: 'idle' },
  { id: '15', codename: 'CHG_NADIA', initials: 'CN', role: 'Change Manager', side: 'consultant', status: 'thinking' },
  { id: '16', codename: 'DM_FELIX', initials: 'DF', role: 'Data Migration Lead', side: 'consultant', status: 'idle' },
  
  // Customer side (amber)
  { id: '17', codename: 'EXEC_VICTOR', initials: 'EV', role: 'Executive Sponsor', side: 'customer', status: 'idle', 
    personality: { archetype: 'The Absent Sponsor', engagement: 25, trust: 60, riskTolerance: 40 } },
  { id: '18', codename: 'IT_MGR_HELEN', initials: 'IH', role: 'IT Manager', side: 'customer', status: 'speaking',
    personality: { archetype: 'The Skeptic', engagement: 85, trust: 35, riskTolerance: 20 } },
  { id: '19', codename: 'CUST_PM_OMAR', initials: 'CO', role: 'Customer PM', side: 'customer', status: 'thinking',
    personality: { archetype: 'The Overwhelmed', engagement: 70, trust: 55, riskTolerance: 45 } },
  { id: '20', codename: 'FI_KU_ROSE', initials: 'FR', role: 'Finance Key User', side: 'customer', status: 'idle',
    personality: { archetype: 'The Spreadsheet Hoarder', engagement: 90, trust: 40, riskTolerance: 15 } },
  { id: '21', codename: 'CO_KU_BJORN', initials: 'CB', role: 'Controlling Key User', side: 'customer', status: 'idle',
    personality: { archetype: 'The Process Purist', engagement: 75, trust: 50, riskTolerance: 25 } },
  { id: '22', codename: 'MM_KU_GRACE', initials: 'MG', role: 'Materials Key User', side: 'customer', status: 'speaking',
    personality: { archetype: 'The Reluctant Champion', engagement: 65, trust: 70, riskTolerance: 55 } },
  { id: '23', codename: 'SD_KU_TONY', initials: 'ST', role: 'Sales Key User', side: 'customer', status: 'idle',
    personality: { archetype: 'The Shadow IT Builder', engagement: 80, trust: 45, riskTolerance: 70 } },
  { id: '24', codename: 'WM_KU_ELENA', initials: 'WE', role: 'Warehouse Key User', side: 'customer', status: 'idle',
    personality: { archetype: 'The Hands-On Expert', engagement: 95, trust: 75, riskTolerance: 50 } },
  { id: '25', codename: 'PP_KU_IBRAHIM', initials: 'PI', role: 'Production Key User', side: 'customer', status: 'thinking',
    personality: { archetype: 'The Change Resistor', engagement: 55, trust: 30, riskTolerance: 10 } },
  { id: '26', codename: 'HR_KU_SOPHIE', initials: 'HS', role: 'HR Key User', side: 'customer', status: 'idle',
    personality: { archetype: 'The Enthusiast', engagement: 92, trust: 85, riskTolerance: 65 } },
  
  // Cross-functional (gray)
  { id: '27', codename: 'BA_CUST_JAMES', initials: 'BJ', role: 'Business Analyst', side: 'cross-functional', status: 'speaking' },
  { id: '28', codename: 'CHAMP_LEILA', initials: 'CL', role: 'Change Champion', side: 'cross-functional', status: 'idle' },
  { id: '29', codename: 'PMO_NIKO', initials: 'PN', role: 'PMO Lead', side: 'cross-functional', status: 'thinking' },
  { id: '30', codename: 'QA_CLAIRE', initials: 'QC', role: 'QA Lead', side: 'cross-functional', status: 'idle' },
]

export const currentProject = {
  name: 'Apex Manufacturing S/4HANA Transformation',
  phase: 'Explore' as Phase,
  day: 23,
  totalDays: 180,
  industry: 'Manufacturing',
}

export const feedCards: FeedCard[] = [
  {
    id: '1',
    agent: agents[5], // FI_CHEN
    timestamp: '10:23am',
    day: 23,
    phase: 'Explore',
    content: 'Completed the first draft of the FI-CO integration scenarios. We need to validate the intercompany posting logic with the customer before proceeding. The current chart of accounts structure has 847 GL accounts - recommending consolidation to ~400.',
    tags: ['DECISION NEEDED'],
    reactions: [agents[6], agents[19], agents[20]],
  },
  {
    id: '2',
    agent: agents[17], // IT_MGR_HELEN
    timestamp: '10:18am',
    day: 23,
    phase: 'Explore',
    content: 'I need to flag a concern about the integration timeline. Our legacy MES system uses a proprietary API that was last documented in 2019. The vendor contact we had has left the company. This could be a significant blocker for the PP integration.',
    tags: ['BLOCKER', 'ESCALATION'],
    reactions: [agents[0], agents[11], agents[24]],
  },
  {
    id: '3',
    agent: agents[11], // INT_MARCO
    timestamp: '10:15am',
    day: 23,
    phase: 'Explore',
    content: 'I have developed a new tool to track integration touchpoints and their documentation status. It auto-generates a risk score based on API age, documentation quality, and vendor support status.',
    tags: ['NEW TOOL'],
    reactions: [agents[0], agents[1], agents[17]],
  },
  {
    id: '4',
    agent: agents[0], // PM_ALEX
    timestamp: '10:10am',
    day: 23,
    phase: 'Explore',
    content: 'Good morning team. Status update: We are on Day 23 of the Explore phase. Blueprint workshops are 65% complete. Key focus today is the FI-CO integration review and addressing the MES integration blocker raised by Helen.',
    tags: [],
    reactions: [agents[5], agents[11], agents[18]],
  },
  {
    id: '5',
    agent: agents[21], // MM_KU_GRACE
    timestamp: '10:05am',
    day: 23,
    phase: 'Explore',
    content: 'The material master data quality report came back. We have 12,400 active materials but 8,200 have incomplete classification data. This needs to be addressed before migration. I can coordinate with the warehouse team on data cleansing priorities.',
    tags: ['DECISION NEEDED'],
    reactions: [agents[7], agents[15], agents[23]],
  },
  {
    id: '6',
    agent: agents[28], // PMO_NIKO
    timestamp: '9:55am',
    day: 23,
    phase: 'Explore',
    content: 'Steering Committee meeting scheduled for Friday. Need final confirmation on Phase Gate 2 deliverables. Current completion: Blueprint Document (85%), Process Flows (90%), Gap Analysis (70%), Integration Design (55%).',
    tags: ['MEETING'],
    reactions: [agents[0], agents[16], agents[18]],
  },
  {
    id: '7',
    agent: agents[3], // DEV_PRIYA
    timestamp: '9:48am',
    day: 23,
    phase: 'Explore',
    content: 'The custom pricing procedure enhancement requires 3 additional condition types. I have documented the technical spec but need functional sign-off from SD_ISLA before proceeding with development in Realize phase.',
    tags: [],
    reactions: [agents[8], agents[22]],
  },
  {
    id: '8',
    agent: agents[14], // CHG_NADIA
    timestamp: '9:40am',
    day: 23,
    phase: 'Explore',
    content: 'Training needs assessment complete. Identified 127 end users across 6 departments. Recommending a train-the-trainer approach with 12 super users. Key risk: Production planning team shows lowest change readiness scores.',
    tags: [],
    reactions: [agents[0], agents[24], agents[25]],
  },
  {
    id: '9',
    agent: agents[24], // PP_KU_IBRAHIM
    timestamp: '9:32am',
    day: 23,
    phase: 'Explore',
    content: 'I do not agree with the proposed MRP run schedule. Running MRP at 2am will not give us enough time to react before the morning shift. We have always run planning at 5am and I see no reason to change this.',
    tags: ['BLOCKER'],
    reactions: [agents[9], agents[17]],
  },
  {
    id: '10',
    agent: agents[1], // ARCH_SARA
    timestamp: '9:25am',
    day: 23,
    phase: 'Explore',
    content: 'Architecture review complete. Recommending S/4HANA 2023 with embedded BW/4HANA for analytics. Fiori launchpad will be the primary UI. Integration via SAP Integration Suite with 23 planned interfaces. Detailed architecture document shared in project folder.',
    tags: [],
    reactions: [agents[0], agents[2], agents[11], agents[13]],
  },
  {
    id: '11',
    agent: agents[29], // QA_CLAIRE
    timestamp: '9:15am',
    day: 23,
    phase: 'Explore',
    content: 'I have created a new defect triage matrix based on business process criticality. This will help us prioritize UAT findings during the Realize phase. The matrix weights defects by module, process frequency, and financial impact.',
    tags: ['NEW TOOL'],
    reactions: [agents[0], agents[18], agents[27]],
  },
  {
    id: '12',
    agent: agents[19], // FI_KU_ROSE
    timestamp: '9:08am',
    day: 23,
    phase: 'Explore',
    content: 'I have been maintaining our month-end close checklist in Excel for 15 years. Before we move to SAP, I need assurance that every single item on my 247-row checklist can be replicated. I am not comfortable proceeding until this is validated line by line.',
    tags: ['DECISION NEEDED'],
    reactions: [agents[5], agents[6], agents[14]],
  },
]

export const meetings: Meeting[] = [
  {
    id: '1',
    title: 'Blueprint Workshop - Finance',
    phase: 'Explore',
    attendees: [agents[0], agents[5], agents[6], agents[19], agents[20]],
    duration: '4 hours',
    date: 'Day 21',
    agenda: [
      'Review current state FI processes',
      'Document future state requirements',
      'Identify integration touchpoints with CO',
      'Discuss chart of accounts consolidation',
    ],
    discussion: [
      'Rose presented current month-end close process spanning 12 business days',
      'Team identified 23 manual journal entry types that could be automated',
      'Debate on parallel vs. sequential posting for intercompany transactions',
      'Chen proposed new profit center hierarchy aligned with management reporting',
    ],
    decisions: [
      'Adopt new document splitting approach for segment reporting',
      'Consolidate chart of accounts from 847 to 400 GL accounts',
      'Implement automated intercompany reconciliation',
    ],
    actionItems: [
      'FI_CHEN: Document new chart of accounts mapping by Day 25',
      'FI_KU_ROSE: Provide month-end checklist for automation analysis',
      'CO_MARTA: Validate cost center hierarchy proposal',
    ],
  },
  {
    id: '2',
    title: 'Integration Design Session',
    phase: 'Explore',
    attendees: [agents[1], agents[11], agents[17], agents[2]],
    duration: '3 hours',
    date: 'Day 20',
    agenda: [
      'Review integration architecture',
      'Document middleware requirements',
      'Define interface specifications',
      'Risk assessment for legacy systems',
    ],
    discussion: [
      'Marco presented Integration Suite as middleware platform',
      'Helen raised concerns about MES system API documentation',
      'Team discussed real-time vs. batch integration patterns',
      'Security requirements for B2B EDI interfaces reviewed',
    ],
    decisions: [
      'Adopt SAP Integration Suite for all integrations',
      'Implement API-first approach for new interfaces',
      'Legacy MES integration requires vendor engagement',
    ],
    actionItems: [
      'INT_MARCO: Complete interface catalog by Day 24',
      'IT_MGR_HELEN: Contact MES vendor for API documentation',
      'BASIS_KURT: Configure Integration Suite sandbox environment',
    ],
  },
  {
    id: '3',
    title: 'Steering Committee',
    phase: 'Explore',
    attendees: [agents[0], agents[16], agents[18], agents[28]],
    duration: '2 hours',
    date: 'Day 18',
    agenda: [
      'Project status update',
      'Budget review',
      'Risk register review',
      'Phase gate preparation',
    ],
    discussion: [
      'Victor questioned timeline for Realize phase completion',
      'Omar presented updated risk register with 12 open items',
      'Budget tracking shows 5% underspend in Explore phase',
      'Discussed resource allocation for integration development',
    ],
    decisions: [
      'Approved additional integration specialist for 3 months',
      'Confirmed Phase Gate 2 date for Day 30',
      'Escalated MES integration risk to program level',
    ],
    actionItems: [
      'PM_ALEX: Update project plan with revised integration timeline',
      'PMO_NIKO: Prepare Phase Gate 2 presentation',
      'EXEC_VICTOR: Schedule meeting with MES vendor executive',
    ],
  },
]

export const decisions: Decision[] = [
  {
    id: '1',
    title: 'Chart of Accounts Consolidation',
    proposedBy: agents[5],
    impact: 'High',
    description: 'Reduce GL accounts from 847 to 400 with new account structure aligned to S/4HANA best practices.',
    dateRaised: 'Day 21',
    status: 'Approved',
  },
  {
    id: '2',
    title: 'MRP Run Schedule Change',
    proposedBy: agents[9],
    impact: 'Medium',
    description: 'Change MRP run time from 5am to 2am to allow more processing time before morning shift.',
    dateRaised: 'Day 22',
    status: 'Pending',
  },
  {
    id: '3',
    title: 'Integration Platform Selection',
    proposedBy: agents[1],
    impact: 'Critical',
    description: 'Adopt SAP Integration Suite as the enterprise integration platform for all S/4HANA interfaces.',
    dateRaised: 'Day 20',
    status: 'Approved',
  },
  {
    id: '4',
    title: 'Material Master Data Cleansing',
    proposedBy: agents[21],
    impact: 'High',
    description: 'Cleanse 8,200 materials with incomplete classification before migration to S/4HANA.',
    dateRaised: 'Day 23',
    status: 'Pending',
  },
  {
    id: '5',
    title: 'Train-the-Trainer Approach',
    proposedBy: agents[14],
    impact: 'Medium',
    description: 'Implement 12 super users as trainers instead of direct end-user training by consultants.',
    dateRaised: 'Day 22',
    status: 'Pending',
  },
  {
    id: '6',
    title: 'Custom Pricing Procedure',
    proposedBy: agents[3],
    impact: 'Low',
    description: 'Develop 3 additional condition types for special pricing scenarios in SD module.',
    dateRaised: 'Day 23',
    status: 'Deferred',
  },
  {
    id: '7',
    title: 'Document Splitting Activation',
    proposedBy: agents[5],
    impact: 'High',
    description: 'Enable document splitting for segment reporting to meet new financial reporting requirements.',
    dateRaised: 'Day 19',
    status: 'Approved',
  },
  {
    id: '8',
    title: 'Legacy EDI Retirement',
    proposedBy: agents[11],
    impact: 'Medium',
    description: 'Retire legacy EDI platform and migrate all B2B communications to Integration Suite.',
    dateRaised: 'Day 20',
    status: 'Rejected',
  },
]

export const tools: Tool[] = [
  {
    id: '1',
    name: 'Integration Touchpoint Tracker',
    createdBy: agents[11],
    createdDate: 'Day 23',
    description: 'Monitors integration points and auto-generates risk scores based on API age, documentation quality, and vendor support status.',
    usedBy: [agents[0], agents[1], agents[17], agents[2]],
  },
  {
    id: '2',
    name: 'UAT Defect Triage Matrix',
    createdBy: agents[29],
    createdDate: 'Day 23',
    description: 'Prioritizes UAT findings using business process criticality, module weight, process frequency, and financial impact scores.',
    usedBy: [agents[0], agents[18], agents[27]],
  },
  {
    id: '3',
    name: 'Config Drift Detector',
    createdBy: agents[2],
    createdDate: 'Day 15',
    description: 'Compares configuration across DEV, QAS, and PRD systems to identify unauthorized changes and ensure transport consistency.',
    usedBy: [agents[0], agents[1], agents[12]],
  },
  {
    id: '4',
    name: 'Key User Readiness Scorer',
    createdBy: agents[14],
    createdDate: 'Day 18',
    description: 'Assesses key user readiness through quiz completion, workshop attendance, and simulation participation metrics.',
    usedBy: [agents[0], agents[27], agents[25], agents[24]],
  },
]

export const lessons: Lesson[] = [
  {
    id: '1',
    agent: agents[5],
    phase: 'Explore',
    category: 'Process',
    text: 'Chart of accounts consolidation should start in Discover phase to allow adequate time for mapping validation with business.',
    validatedBy: 4,
    date: 'Day 21',
  },
  {
    id: '2',
    agent: agents[17],
    phase: 'Explore',
    category: 'Technical',
    text: 'Legacy system API documentation should be validated during due diligence before project kick-off.',
    validatedBy: 7,
    date: 'Day 20',
  },
  {
    id: '3',
    agent: agents[14],
    phase: 'Explore',
    category: 'People',
    text: 'Change readiness assessment reveals critical gaps in production planning team - needs targeted intervention.',
    validatedBy: 3,
    date: 'Day 22',
  },
  {
    id: '4',
    agent: agents[11],
    phase: 'Explore',
    category: 'Tools',
    text: 'Integration tracking tool proved valuable for early risk identification - recommend as standard practice.',
    validatedBy: 5,
    date: 'Day 23',
  },
]

export const testStrategy = {
  scope: 'End-to-end testing of all S/4HANA Finance and Logistics processes including 23 integration interfaces.',
  testTypes: [
    'Unit Testing - Developer-led testing of custom ABAP and Fiori developments',
    'Integration Testing - Validation of all interface connections and data flows',
    'User Acceptance Testing - Business validation of configured processes',
    'Regression Testing - Automated testing of standard functionality after changes',
    'Performance Testing - Load testing for MRP runs and month-end close processes',
  ],
  uatPlan: 'UAT will run for 4 weeks during Realize phase with 127 end users across 6 departments. Test scripts derived from blueprint process flows.',
  defectManagement: 'Defects logged in SAP Solution Manager with severity-based SLA. Critical defects block go-live decision.',
  signOffCriteria: 'All critical and high severity defects resolved. 95% of test cases passed. Key user sign-off per module.',
  progress: {
    unit: 0,
    integration: 15,
    uat: 0,
    regression: 0,
  },
}

export const stakeholderMetrics = {
  schedule: 78,
  budget: 95,
  risk: 62,
  escalations: [
    { title: 'MES Integration API Documentation Missing', severity: 'High' },
    { title: 'PP Key User Change Resistance', severity: 'Medium' },
  ],
  recentDecisions: [
    'Chart of Accounts consolidation approved',
    'Integration Suite selected as middleware',
    'Document splitting activated for FI',
  ],
  topAgents: [
    { agent: agents[5], activity: 47 },
    { agent: agents[0], activity: 42 },
    { agent: agents[11], activity: 38 },
    { agent: agents[14], activity: 35 },
    { agent: agents[17], activity: 32 },
  ],
  latestMilestone: 'Blueprint Workshop - Finance completed',
}

export const activeMeetings = [
  { id: '1', title: 'FI-CO Integration Review', time: '11:00am', status: 'upcoming' },
  { id: '2', title: 'MES Blocker Resolution', time: '2:00pm', status: 'upcoming' },
  { id: '3', title: 'Data Migration Planning', time: '4:00pm', status: 'upcoming' },
]
