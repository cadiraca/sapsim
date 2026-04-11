# SKILL: SAP Basis Administration

## Core Concepts

SAP Basis is the technical foundation layer that supports all SAP applications. It encompasses system administration, performance tuning, transport management, and landscape maintenance. A typical SAP landscape consists of three tiers: Development (DEV), Quality Assurance (QAS), and Production (PRD), connected via the Transport Management System (TMS). Basis administrators are responsible for system availability, user management, performance monitoring, and patch/upgrade activities. The ABAP Application Server (AS ABAP) runs work processes categorized as Dialog, Background, Update, Enqueue, and Spool — each with specific roles in processing user requests and batch jobs.

## Key Transactions

- **SM50/SM66**: Work process overview (local/global). Used to monitor active processes, identify long-running or blocked tasks, and cancel stuck processes.
- **SM37**: Job monitoring for background jobs. Filter by user, job name, status. Reschedule or cancel batch jobs.
- **SM21**: System log analysis. Essential for diagnosing dumps, security violations, and system events.
- **ST22**: ABAP runtime error (dump) analysis. Shows stack traces, variable values at time of failure.
- **RZ20**: CCMS Alert Monitor. Threshold-based alerting for CPU, memory, spool, and database metrics.
- **STMS**: Transport Management System. Manages transport routes, imports transports across landscapes.
- **SCC4/SCC8/SCC9**: Client administration, client copy, and client export.
- **SM59**: RFC destination management — define and test connections to remote systems.
- **SICK**: System installation check. Verify kernel, patch levels, and system consistency post-install.
- **DB02**: Database performance analysis. Monitor tablespace usage, missing indexes, and growth trends.

## Common Challenges

**System Lockups**: Enqueue server saturation or deadlocks in database layer can freeze user sessions. Diagnosis via SM50 identifying PRIV mode processes (processes in private memory roll area) consuming dialog work processes.

**Transport Conflicts**: When multiple developers modify the same object in different transports, import conflicts occur. Resolution requires careful sequencing or manual object-level merge.

**Performance Degradation**: Buffer misses (program, table definition, CUA) indicate under-sized SAP buffers. Tune via RZ10 profile parameters. SQL-level bottlenecks diagnosed via ST05 (SQL trace) and SM66.

**Spool Overflow**: High-volume print jobs can exhaust spool work processes. Requires cleanup via SP12 and output device configuration review.

## Best Practices

- Maintain system landscape documentation including kernel versions, patch levels, and instance profiles.
- Schedule regular background jobs for ABAP dumps cleanup (RSSNAPDL), old spool requests (RSPO1041), and job log cleanup.
- Implement dual-stack separation — keep ABAP and Java stacks on separate instances when possible.
- Use Solution Manager for centralized monitoring and change management across the landscape.
- Never transport directly to Production without QAS validation. Enforce four-eyes principle for production changes.
- Monitor work process utilization trends — sustained >80% utilization signals need for scaling.

## Integration Points

Basis interacts with every SAP module since it provides the runtime environment. Key integration areas: ABAP development lifecycle via STMS transports, Security via role authorization profiles (SU01/PFCG), PI/PO middleware requiring RFC and IDOC configuration, and HANA database administration when running on SAP HANA (HANA Studio, HANA Cockpit). Basis also coordinates OS-level scheduling (cron jobs, backup scripts) with SAP application-level job scheduling via SM36/SM37.
