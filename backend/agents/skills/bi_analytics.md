# SKILL: SAP Business Intelligence and Analytics

## Core Concepts

SAP's BI/Analytics portfolio has evolved significantly over decades. The traditional stack — SAP BW (Business Warehouse) with BusinessObjects (BO) front-end tools — remains widely deployed. The modern stack centers on **SAP BW/4HANA** (optimized BW on HANA) and **SAP Analytics Cloud (SAC)**, which combines BI, planning, and predictive capabilities in one cloud platform. At the data layer, **SAP HANA** serves as both operational database and analytical engine, enabling real-time analytics directly on transactional data (the "operational reporting" paradigm that eliminates data replication latency).

Core BW concepts: **InfoObjects** (master data and characteristics), **DataStore Objects (DSO/aDSO)** (staging and reporting layers), **InfoCubes** (now replaced by aDSO in BW/4HANA), **InfoProviders** (any reportable object), **Transformations** (ETL mapping rules), **Data Transfer Processes (DTP)** (load execution), and **Process Chains** (scheduled end-to-end load orchestration). The extraction layer uses **DataSources** in source systems (SAP ERP) connected to BW via **Source System** RFC connections.

## Key Transactions / Tools

- **RSA1**: BW Data Warehousing Workbench — central design and administration tool for all BW objects.
- **RSPC**: Process Chain maintenance and monitoring. Schedule and monitor end-to-end data load chains.
- **SM37**: Background job monitoring for BW load processes (DTP and process chain execution jobs).
- **RSMO**: DTP monitor — detailed load process monitoring, error handling, and restart.
- **RSD1/RSD2/RSD3**: InfoObject maintenance (Characteristic/Key Figure/Time).
- **SE16N/LISTCUBE**: Data browsing in InfoProviders for validation and troubleshooting.
- **RSECADMIN**: BW Analysis Authorizations administration — BW's dedicated authorization layer (separate from standard PFCG, controls what data users see in reports).
- **ST05**: SQL trace — analyze slow BW queries hitting HANA or database layer.

## Common Challenges

**Delta Load Failures**: Incremental (delta) extractions fail when the BW and source system delta queues become inconsistent. Requires delta initialization (full load) to resynchronize, which can mean loading millions of records. Plan delta re-init during off-peak windows.

**Process Chain Failures**: Long process chains with no error handling terminate on the first failed step, leaving subsequent loads unexecuted. Implement conditional process chain steps and alerting via CCMS or Solution Manager.

**Query Performance on Large Datasets**: Reporting on high-cardinality data without proper aggregates or HANA Composite Providers causes timeouts. Use BW composite providers, BEx aggregates, and HANA calculation views for complex scenarios.

**Data Consistency Between BW and Source**: Source data corrections (manual FI postings, retroactive HR changes) don't automatically flow to BW delta queues. Identify and schedule repair requests for corrected data.

## Best Practices

- Design the data model top-down: start from reporting requirements, then define InfoObjects and InfoProviders — not bottom-up from source tables.
- Use aDSO (Advanced DSO) as the universal InfoProvider in BW/4HANA — it replaces both classic DSO and InfoCube with greater flexibility.
- Implement data lifecycle management: archive or delete aged BW data to control system growth. Use Near-Line Storage (NLS) for historical data.
- Separate "reporting" and "staging" layers: keep raw extracted data in write-optimized aDSOs and aggregated reporting data in standard aDSOs.
- Validate data loads with reconciliation reports comparing BW totals against ERP source (e.g., FI GL totals vs. BW financial cube).

## Integration Points

BW connects to SAP ERP via LO Cockpit (logistics), FI-SL/New GL extractors, HR infotype extractors, and generic extractors (DB views, function modules). SAC connects to BW/4HANA as a live data connection for real-time reporting or imports data for planning scenarios. Embedded analytics in S/4HANA use CDS (Core Data Services) views directly on HANA — bypassing BW for operational reporting. BOBJ (BusinessObjects) tools (Crystal Reports, Web Intelligence, Lumira) connect to BW via BICS or JDBC for traditional enterprise reporting.
