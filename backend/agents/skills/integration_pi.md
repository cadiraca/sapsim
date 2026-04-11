# SKILL: SAP Process Integration / Process Orchestration (PI/PO)

## Core Concepts

SAP Process Integration (PI), later evolved into Process Orchestration (PO), is SAP's middleware platform for connecting SAP and non-SAP systems across enterprise landscapes. It is built on the Advanced Adapter Engine (AAE) and supports both synchronous (request-reply) and asynchronous (fire-and-forget) messaging patterns. The core processing pipeline consists of: Sender Adapter → Integration Engine → Mapping → Integration Engine → Receiver Adapter. PI/PO supports a wide range of adapters: RFC, IDOC, HTTP, SOAP, REST, JDBC, FILE, SFTP, and many more. In SAP S/4HANA and BTP environments, SAP Integration Suite (formerly Cloud Integration / CPI) has replaced on-premise PI/PO for cloud-first integrations, though many SAP landscapes still run PI/PO for on-premise-to-on-premise scenarios.

## Key Transactions / Tools

- **SXMB_MONI**: PI Integration Engine monitoring. Displays all processed, failed, and in-progress messages with full XML payload visibility.
- **RWB (Runtime Workbench)**: Component and adapter monitoring within PI system. Accessible via http://<host>:5XX00/rwb.
- **ESR (Enterprise Services Repository)**: Design-time repository for data types, message types, interfaces, and mappings.
- **Integration Directory (ID)**: Configuration layer — defines sender/receiver agreements, communication channels, and routing rules.
- **SM59**: RFC destinations connecting PI to backend SAP systems.
- **WE02/WE05**: IDOC monitoring in sending/receiving SAP systems.
- **AL11**: File system access on application server — used to verify FILE adapter input/output directories.

## Common Challenges

**Message Stuck in Queue**: Asynchronous messages can remain in processing state when the receiving system is unavailable. Use SXMB_MONI to identify failed messages and trigger restart once the issue is resolved. Check SMQS (qRFC monitor) in the backend.

**Mapping Failures**: Incorrect XSLT or Java mapping leads to transformation errors. Debug via ESR test mapping tool — always validate with real payload samples before transport to production.

**Adapter Connectivity**: SOAP/HTTP adapters fail silently when SSL certificates expire. Monitor certificate validity in NWA (NetWeaver Administrator) → SSL.

**Duplicate Message Handling**: FILE adapters without proper archival configuration can re-process files after system restart. Use "Archive" processing mode instead of "Delete" for audit trails.

**High Message Volume Performance**: Large payload processing (>1MB XML) can cause memory pressure. Implement message splitting patterns using BPM (Business Process Management) or multi-mapping.

## Best Practices

- Design integrations using the canonical data model approach — define central data types used across all interfaces to simplify future changes.
- Always implement error alerting via Alert Configuration in the Integration Directory — never rely on manual SXMB_MONI monitoring in production.
- Use SWCV (Software Component Versions) to namespace all ESR objects by business domain and system landscape.
- For high-volume interfaces, prefer asynchronous patterns with IDOC or qRFC over synchronous RFC to avoid timeout and coupling issues.
- Document all integration scenarios in a central Integration Landscape Document (ILD) including message volumes, SLAs, and retry policies.

## Integration Points

PI/PO is the hub connecting SAP ERP (SD, MM, FI, HR) to external systems: EDI partners (via IDOC/AS2), legacy systems (via FILE/JDBC), web services (SOAP/REST), and cloud applications. With SAP Integration Suite, hybrid landscapes combine on-premise PI/PO with cloud CPI flows. Key backend integration: RFC-enabled function modules in ABAP act as service endpoints; IDOCs are the native async message format for SAP-to-SAP scenarios; BAPI wrappers expose business functions as synchronous web services.
