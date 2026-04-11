# SKILL: SAP Data Migration

## Core Concepts

Data migration is one of the highest-risk activities in any SAP implementation. It involves extracting data from legacy systems, transforming it to conform to SAP's data model and business rules, and loading it into the target SAP system. SAP's recommended methodology for S/4HANA migrations is **SAP Data Migration Cockpit (LTMC/LTMOM)** — a guided, template-based tool that replaces the older LSMW approach. For complex transformations and high-volume scenarios, **SAP Data Services (BODS)** provides ETL capabilities with data quality and profiling features.

Migration objects are grouped into waves, and each wave follows: Extract → Profile → Transform → Validate → Load → Reconcile. **Cutover planning** defines the sequence and timing of all migration activities, typically executed during a go-live weekend with strict timelines. The **migration cockpit** in S/4HANA uses standardized staging tables (prefix: /LTMC/) where data is loaded before being posted into application tables, allowing validation before final commitment.

Key data domains in SAP migrations: Master Data (customers, vendors, materials, chart of accounts, cost centers) and Transactional Data (open items — open POs, open sales orders, open FI items, asset values, stock balances). Historical transactional data is typically loaded as statistical data only (no re-creation of full document flow).

## Key Transactions / Tools

- **LTMC**: SAP Data Migration Cockpit (S/4HANA). Central tool for template-based migrations. Creates migration projects, maps fields, executes loads.
- **LTMOM**: Migration Object Modeler — extend or create custom migration objects in LTMC.
- **LSMW**: Legacy System Migration Workbench (ECC/older systems). Supports direct input, BAPI, IDOC, and recording methods.
- **SHDB**: Batch Input session recording — capture transaction screen sequence for LSMW recording method.
- **SM35**: Batch Input session monitoring and processing.
- **SE16N**: Post-load data validation directly in SAP tables.
- **CKMVFM**: Material ledger migration — special tool for activating material ledger values in production.
- **AS91/AS92**: Legacy asset creation/change — used for fixed asset migration during go-live.

## Common Challenges

**Data Quality Issues**: Legacy systems often contain inconsistent, duplicated, or incomplete records. Customer/vendor deduplication, address standardization, and material master completeness checks must happen before extraction. Budget 40-60% of migration effort for data cleansing alone.

**Mapping Complexity**: Legacy fields don't map 1:1 to SAP fields. Company codes, plant codes, GL accounts, and profit centers must be pre-defined in SAP before migration. Mapping tables (legacy code → SAP code) are critical deliverables.

**Open Item Balancing**: Migrated open FI items (customer invoices, vendor invoices) must balance to zero when combined with the initial balance upload. Reconciliation between legacy AR/AP sub-ledger and GL is mandatory before cutover sign-off.

**Cutover Timing**: Large data volumes (millions of records) can exceed the cutover window. Mock cutovers (dress rehearsals) are essential to measure actual load times and optimize sequence.

**Post-Migration Corrections**: Finding data errors after go-live is expensive — corrections require finance sign-off, retroactive postings, or in extreme cases system re-migration. Early mock loads catch structural issues.

## Best Practices

- Run at least two full mock migrations in QAS before the production cutover weekend.
- Define data migration acceptance criteria (reconciliation thresholds) in advance — e.g., AR balance variance ≤ 0.01%.
- Freeze legacy data as early as possible before cutover to minimize delta migration scope.
- Assign a dedicated migration team with both SAP functional knowledge and data analysis skills (SQL, Excel).
- Use migration templates from SAP's Best Practices Explorer as starting points — they include field mappings and validation rules.

## Integration Points

Data migration touches every SAP module simultaneously. FI migration requires CO cost object structures to be complete. MM stock migration requires both MM and FI (stock value accounts) to be ready. SD open order migration requires customer masters, material masters, and pricing conditions. Sequence matters: Organization structure → Master Data → Open Transactional Data → Historical Data. Integration with HR requires careful handling of employee personal data under GDPR/data privacy regulations.
