# SKILL: ABAP Development

## Core Concepts

ABAP (Advanced Business Application Programming) is SAP's proprietary programming language, running on the ABAP Application Server. In SAP projects, ABAP development covers all custom enhancements classified as **RICEFW** objects: Reports, Interfaces, Conversions (data migration), Enhancements, Forms, and Workflows.

**ABAP language evolution:**
- **Classic ABAP**: Procedural, module pool programs, function modules, internal tables with `LOOP AT`/`READ TABLE`.
- **ABAP Objects (OO)**: Class-based, inheriting from `CL_*` SAP standard classes. Best practice for new development.
- **ABAP in Eclipse (ADT)**: Modern development environment replacing SE80. Required for ABAP Cloud and BTP development.
- **ABAP CDS Views**: Core Data Services — SQL-based view definitions with annotations. The foundation for embedded analytics, Fiori apps, and BW datasources in S/4HANA.
- **ABAP RAP (RESTful Application Programming Model)**: The S/4HANA standard for building Fiori apps and OData services. Uses CDS + Behavior Definitions + Service Bindings.

**RICEFW classification:**
- **R — Reports**: ALV Grid (CL_GUI_ALV_GRID, REUSE_ALV_GRID_DISPLAY), custom queries, background jobs
- **I — Interfaces**: IDocs, BAPIs, RFCs, REST/SOAP web services, OData (SEGW or RAP)
- **C — Conversions**: LSMW, BAPI-based migration programs, LTMC/LTMOM for S/4HANA
- **E — Enhancements**: BAdIs (Business Add-Ins), user exits, implicit/explicit enhancements, Business Event Handling
- **F — Forms**: SAPscript (legacy), SmartForms, Adobe Document Services (ADS)
- **W — Workflows**: SAP Business Workflow (SWI*), Flexible Workflow, SAP Process Automation (BTP)

## Key Transactions / Technical Details

| T-Code | Purpose |
|--------|---------|
| **SE80** | ABAP Workbench (classic — use ADT in Eclipse for new dev) |
| **SE38 / SA38** | ABAP Editor / Run program |
| **SE37** | Function Module Builder |
| **SE24** | Class Builder |
| **SE11** | ABAP Dictionary — tables, structures, data elements, domains |
| **SE16N / SE16** | Table content display (use carefully in PRD) |
| **SE93** | Transaction Code maintenance |
| **SNOTE** | SAP Note implementation tool (SNOTE → download → implement) |
| **SE10 / STMS** | Transport Organizer / Transport Management System |
| **SCI / SCII** | Code Inspector — static code analysis |
| **SAT / SE30** | ABAP runtime analysis / trace |
| **ST05** | SQL trace — analyze database queries, find missing indexes |
| **SM50 / SM66** | Work process / global work process overview (performance) |
| **SICF** | HTTP service maintenance (Fiori, OData, web services) |
| **SEGW** | OData service builder (classic — use RAP in S/4HANA) |
| **SPDD / SPAU** | Modification adjustment after support package / upgrade |

Key development objects: **Data Dictionary** (DDIC) — transparent tables, structures, table types, data elements, domains, search helps, lock objects. **Function Groups** (SE37) for legacy RFCs. **Enhancement Framework** — use `ENHANCEMENT-POINT`/`ENHANCEMENT-SECTION` for implicit enhancements; BAdIs via `GET BADI`/`CALL BADI` for explicit.

## Common Challenges

- **Modification vs. enhancement**: Modifying SAP standard code (SE38/SE24) is strongly discouraged — modifications break on upgrades and require SPAU adjustment. Always prefer BAdIs, user exits, and enhancement spots.
- **Performance anti-patterns**: `SELECT *` from large tables (BSEG, ACDOCA, MSEG), `SELECT` inside `LOOP`, missing `WHERE` clauses, using `SORT` on large internal tables without necessity — these are the top causes of production performance issues.
- **Transport discipline**: Development in production (debugging with breakpoints that write data, direct table changes) is a serious governance violation. All changes go through DEV → QAS → PRD via STMS.
- **BAdI implementation gaps**: Not all standard processes have BAdIs where customers need them. When no BAdI exists, the fallback is an implicit enhancement — which is riskier for upgrade stability.
- **OData performance**: Inefficient CDS views used as OData datasources cause Fiori apps to load slowly. CDS views must use proper associations, push-down to HANA, and avoid client-side aggregation.
- **Unicode compliance**: Programs developed on non-Unicode systems may fail Unicode checks. All ABAP in S/4HANA must be Unicode-compliant.
- **Custom code migration to S/4HANA**: Classic ABAP programs using obsolete statements (JOIN on pool/cluster tables, direct BSEG access, old inventory management APIs) must be adapted. Run the **Custom Code Migration app** (SAP Readiness Check) to identify all impacted objects.

## Best Practices

- Every RICEFW object needs a functional spec + technical spec, reviewed and signed off before coding starts.
- Use **Code Inspector (SCI)** checks as a gate before every transport to QAS — enforce naming conventions, performance rules, and security checks automatically.
- Name custom objects with the project namespace prefix (Z or Y, or registered /namespace/) — never use SAP's own naming ranges.
- For S/4HANA: prefer CDS Views + RAP over classic SEGW OData. New Fiori apps should use the RAP programming model.
- Document every BAdI/enhancement spot used: which standard SAP process it hooks into, what the enhancement does, what SAP upgrade risk it carries.
- Implement `ASSERT` and proper exception handling in all developments — silent failures in interfaces cause data quality issues that are hard to diagnose.
- Schedule regular code reviews during Realize phase — catching bad patterns early is 10x cheaper than fixing them post go-live.

## Integration Points with Other Modules

- **ABAP → FI/CO**: Custom validation BAdIs on posting (e.g., `BADI_FDCB_SUBBAS01` for document posting checks). Custom account determination exits.
- **ABAP → MM/SD**: User exits and BAdIs on pricing (`USEREXIT_PRICING_PREPARE_TKOMK`), order saves (`USEREXIT_SAVE_DOCUMENT_PREPARE`), and goods movement (`MB_DOCUMENT_BADI`).
- **ABAP → PP**: Production order BAdIs for automatic scheduling, component substitution, and confirmation validation.
- **ABAP → Interfaces (PI/PO/BTP)**: Custom ABAP programs extract data to IDocs or call RFC-enabled function modules as interface proxies.
- **ABAP → Reporting**: Custom CDS views feed BW/4HANA extractors, embedded analytics tiles, and Report Painter datasources.
- **ABAP → Workflow**: ABAP classes implement workflow task methods; event binding triggers workflow from standard SAP business events (e.g., purchase order creation, invoice parking).
