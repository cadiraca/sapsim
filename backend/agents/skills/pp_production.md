# SKILL: PP — Production Planning

## Core Concepts

SAP PP covers the Plan-to-Produce process: from demand planning and MRP through production order creation, execution, and goods issue/receipt. It manages the master data and processes for manufacturing operations.

**Key PP sub-areas:**

- **MRP (Material Requirements Planning)**: The engine that converts demand (sales orders, forecasts, PIRs) into supply proposals (planned orders, purchase requisitions, schedule lines). Runs at plant level. Types: MRP (MD), Consumption-Based Planning (reorder point, forecast-based).
- **Production Orders**: Discrete manufacturing. A production order has a header, operations (from routing), components (from BOM), and collects actual costs. Status progression: CRTD → REL → TECO → DLV → CLSD.
- **Process Orders (PP-PI)**: Process manufacturing (chemicals, food, pharma). Based on master recipes instead of routings.
- **Repetitive Manufacturing**: High-volume, line-based production. Uses production versions and run schedule quantities instead of discrete orders.
- **Master Data**: BOM (Bill of Materials), Routing (work center sequences and standard times), Work Centers (capacity, cost center assignment), Production Versions (BOM + Routing combination).

Key MRP parameters on material master (MRP 1-4 views): MRP type (PD=MRP, VB=reorder point, ND=no planning), Lot sizing procedure (EX=lot-for-lot, FX=fixed, MB=monthly), MRP controller, Procurement type (E=in-house, F=external, X=both), Planning horizon, Safety stock.

## Key Transactions / Technical Details

| T-Code | Purpose |
|--------|---------|
| **MD01 / MD02 / MD03** | MRP run — plant / single-item multi-level / single-item single-level |
| **MD04** | Stock/Requirements List — the MRP planner's primary screen |
| **MD06 / MD07** | MRP exception messages list / collective display |
| **CO01 / CO02 / CO03** | Create / Change / Display Production Order |
| **COOIS** | Production order information system |
| **CO11N** | Production order confirmation (time ticket) |
| **MIGO (261/101)** | Goods Issue to production order / GR from production order |
| **CO15** | Goods receipt for production order (collective) |
| **CO88 / KKS2** | Settle production orders / production variances |
| **CS01 / CS02 / CS03** | Create / Change / Display BOM |
| **CA01 / CA02 / CA03** | Create / Change / Display Routing |
| **CR01 / CR02 / CR03** | Create / Change / Display Work Center |
| **CM01 / CM25** | Capacity planning table / Capacity leveling |
| **CK11N / CK40N** | Product cost estimate (single / mass) |
| **MD61 / MD62** | Create / Change Planned Independent Requirements (PIR) |

Key tables: **PLKO/PLPO** (routing header/operations), **STKO/STPO** (BOM header/items), **CRHD** (work center header), **AUFK** (order master — all order types), **AFKO/AFPO** (production order header/positions), **AFVC** (production order operations), **RESB** (reservations — components), **MARA/MARC** (material master MRP fields), **MDKP/MDTB** (MRP planning file).

## Common Challenges

- **MRP master data quality**: MRP is garbage-in-garbage-out. BOMs with wrong quantities, missing components, or incorrect procurement types generate nonsensical planned orders. A BOM completeness check before go-live is mandatory.
- **MRP exception message flood**: On the first MRP run in PRD, thousands of exception messages (reschedule, cancel, new orders) overwhelm planners. Initial stock/requirement alignment before go-live is critical.
- **Routing and work center capacity data**: Standard times in routings are rarely accurate in legacy systems. Incorrect times cause capacity planning to be meaningless and product cost estimates to be wrong.
- **Production order settlement**: Orders must be technically completed (TECO) and settled (CO88) at period end. Unclosed orders are a common audit finding and distort CO reporting.
- **Backflushing pitfalls**: Backflush (automatic GI at confirmation) is convenient but error-prone — it issues the full BOM quantity regardless of actual consumption, generating phantom variances.
- **MTO vs. MTS strategy**: Make-to-Order (individual requirements, strategy 20/25) vs. Make-to-Stock (planning with final assembly, strategy 40/50) must be defined per product and affects how SD sales orders connect to PP.

## Best Practices

- Clean and validate BOM and routing data before the first MRP run — this is the most critical data migration task in PP.
- Run MRP in simulation mode (MD01 with test flag) before first production run to review exception volume.
- Define planning horizons and lot sizing procedures carefully per material group — the defaults are rarely correct for a specific business.
- Use production scheduling profiles to control automatic goods receipt and backflush behavior per plant/order type.
- Configure separate order types for different manufacturing scenarios (PP01 for standard, PP04 for rework, etc.) with appropriate settlement profiles.
- Establish a period-end close checklist: confirm all orders, perform goods receipt for completed orders, run variance calculation (KKS2), settle orders (CO88).
- Test capacity planning scenarios: what happens when a key work center is overloaded? Planners need to know how to resolve capacity overloads before go-live.

## Integration Points with Other Modules

- **PP → MM**: MRP generates purchase requisitions for externally procured components. Goods issues (MIGO 261) consume inventory; goods receipts (MIGO 101) increase finished goods stock.
- **PP → CO**: Production orders are CO account assignment objects. They collect actual costs (material, labor, overhead) and settle variances to CO-PA or cost centers.
- **PP → FI**: Order settlement (CO88) creates FI postings for production variances. GR of finished goods (MIGO 101) creates stock value posting.
- **PP → SD**: MPS/MRP is driven by SD sales order demand in make-to-order scenarios. Available-to-Promise (ATP) check in SD reads PP planned receipts.
- **PP → QM**: Inspection lots can be triggered at goods receipt from production (movement type 101) or at in-process inspection milestones defined in the routing.
- **PP → PM**: Work centers link to functional locations / equipment in Plant Maintenance. Machine breakdown notifications in PM can trigger capacity replanning in PP.
